"""数据更新主流程（python -m pipeline.update）。

流程：加载注册表 → 逐源抓取（错误隔离 + LKG 回退）→ 校验 → 排名计算
→ 历史快照 → 生成静态 JSON → 更新报告。
核心 Schema 校验失败时退出码 2，且不触碰 public/data。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from .adapters import ADAPTERS, build_adapter_runtime
from .history.store import HistoryStore
from .normalization.registry import ModelNormalizer
from .paths import (
    LATEST_UPDATE_JSON,
    LATEST_UPDATE_MD,
    REGISTRY_BENCHMARKS,
    REGISTRY_CAPABILITIES,
    REGISTRY_MODELS,
    REGISTRY_SOURCES,
    SOURCE_STATE_FILE,
)
from .ranking.composite import (
    AGENT_TYPES,
    benchmark_ranking,
    capability_composite,
    overall_composite,
)
from .reports.generate import generate_site_data
from .schemas.records import (
    load_yaml,
    parse_registry_models,
    parse_registry_sources,
    utc_now_iso,
)
from .utils.http import HttpClient
from .validation.quality import dedupe_conflicting, validate_records

UPDATE_INTERVAL_HOURS = 12


def load_capability_config() -> tuple[list[dict], dict[str, float]]:
    data = load_yaml(REGISTRY_CAPABILITIES)
    caps = data.get("capabilities") or []
    weights = data.get("default_capability_weights") or {}
    return caps, weights


def load_source_state() -> dict:
    if SOURCE_STATE_FILE.exists():
        return json.loads(SOURCE_STATE_FILE.read_text(encoding="utf-8"))
    return {"sources": {}}


def save_source_state(state: dict) -> None:
    SOURCE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def run(source_filter: list[str] | None = None, offline: bool = False) -> int:
    print("[1/8] 加载注册表 ...")
    models_registry = parse_registry_models(REGISTRY_MODELS)
    sources_registry = parse_registry_sources(REGISTRY_SOURCES)
    benchmarks_registry = load_yaml(REGISTRY_BENCHMARKS).get("benchmarks") or []
    benchmarks_by_id = {b["benchmark_id"]: b for b in benchmarks_registry}
    caps_registry, cap_weights = load_capability_config()
    normalizer = ModelNormalizer(models_registry)
    http = HttpClient()

    active_sources = [s for s in sources_registry if s.status == "active"]
    if source_filter:
        active_sources = [s for s in active_sources if s.source_id in source_filter]

    results = []
    if offline:
        print("[2/8] 离线模式：直接使用 Last Known Good 数据 ...")
        for s in active_sources:
            adapter = build_adapter_runtime(s, normalizer, http, ADAPTERS[s.source_id])
            results.append(adapter.run() if False else _offline_result(adapter))
    else:
        print(f"[2/8] 抓取 {len(active_sources)} 个数据源（来源级错误隔离）...")
        for s in active_sources:
            adapter = build_adapter_runtime(s, normalizer, http, ADAPTERS[s.source_id])
            result = adapter.run()
            results.append(result)
            flag = {"ok": "OK", "degraded": "降级(LKG)", "failed": "失败", "skipped": "跳过"}[result.status]
            print(f"    - {s.source_id}: {flag}，{len(result.records)} 条记录"
                  + (f"，耗时 {result.response_time_ms}ms" if result.response_time_ms else "")
                  + (f"，原因: {result.error_message}" if result.error_message else ""))

    # 未运行的可选来源与 disabled 来源也纳入健康面板
    run_ids = {r.source_id for r in results}
    for s in sources_registry:
        if s.source_id not in run_ids and s.status in ("optional", "disabled"):
            results.append(_unrun_result(s))
    http.close()

    all_records = [r for res in results for r in res.records]
    print(f"[3/8] 共获得 {len(all_records)} 条原始记录")

    print("[4/8] 校验与去重 ...")
    errors, warnings = validate_records(all_records, benchmarks_by_id)
    for w in warnings[:20]:
        print(f"    [warn] {w}")
    if len(warnings) > 20:
        print(f"    ... 共 {len(warnings)} 条警告")
    if errors:
        print("核心校验失败，禁止覆盖线上数据：")
        for e in errors[:30]:
            print(f"    [error] {e}")
        return 2
    all_records = dedupe_conflicting(all_records)

    unmapped = normalizer.save_unmapped_report()
    print(f"    未映射模型名 {len(unmapped)} 个（详见 data/reports/unmapped-models.json）")

    print("[5/8] 排名计算 ...")
    official_rankings = {bid: benchmark_ranking(
        [r for r in all_records if r.benchmark_id == bid]) for bid in benchmarks_by_id}
    for _bid, rows in official_rankings.items():
        for row in rows:
            row["record"].rank = row["rank"]

    capability_composites = {}
    for cap in caps_registry:
        cap_id = cap["capability_id"]
        cap_records = [
            r for r in all_records
            if r.capability == cap_id
            and not r.model_is_unmapped
            and (cap_id == "swe" or r.evaluation_target_type not in AGENT_TYPES)
        ]
        comp = capability_composite(cap_records, benchmarks_by_id)
        if comp and comp["models"]:
            capability_composites[cap_id] = comp

    overall = overall_composite(
        {k: v for k, v in capability_composites.items() if k != "swe"},
        cap_weights,
    )
    print(f"    能力指数 {len(capability_composites)} 个；综合榜收录 {len(overall['models'])} 个模型")

    print("[6/8] 历史快照 ...")
    store = HistoryStore()
    today = date.today()
    snapshot_payload = {}
    for cap_id, comp in capability_composites.items():
        snapshot_payload[cap_id] = {
            m["model_id"]: {"index": m["index"], "rank": m["rank"]}
            for m in comp["models"]
        }
    if overall["models"]:
        snapshot_payload["overall"] = {
            m["model_id"]: {"index": m["index"], "rank": m["rank"]}
            for m in overall["models"]
        }
    store.append_snapshot(today, snapshot_payload)
    removed = store.apply_retention(today)
    if removed:
        print(f"    历史快照聚合清理 {removed} 个旧文件")
    rank_changes = store.rank_changes(today)
    active_caps = sorted(capability_composites.keys()) + ["overall"]
    history_series = {
        mid: store.series_for(mid, active_caps)
        for mid in {m["model_id"] for comp in capability_composites.values() for m in comp["models"]}
    }
    history_series.update({
        m["model_id"]: store.series_for(m["model_id"], ["overall"])
        for m in overall["models"] if m["model_id"] not in history_series
    })
    snapshots_count = len(store.load_snapshots())

    print("[7/8] 生成静态 JSON ...")
    stats = generate_site_data(
        records=all_records,
        results=results,
        normalizer=normalizer,
        models_registry=models_registry,
        sources_registry=sources_registry,
        capabilities_registry=caps_registry,
        benchmarks_registry=benchmarks_by_id,
        capability_weights=cap_weights,
        capability_composites=capability_composites,
        official_rankings=official_rankings,
        overall=overall,
        rank_changes=rank_changes,
        trend_30d=store.trend_30d(),
        history_series=history_series,
        history_dates_count=snapshots_count,
        interval_hours=UPDATE_INTERVAL_HOURS,
    )

    _write_reports(results, len(all_records), unmapped, overall, stats)
    print(f"[8/8] 完成：写入 {stats['files_written']} 个数据文件")
    return 0


def _offline_result(adapter) -> object:
    from .schemas.records import AdapterResult

    lkg = adapter._load_lkg()
    return AdapterResult(
        source_id=adapter.source_id,
        status="degraded" if lkg else "failed",
        records=lkg,
        error_message=None if lkg else "离线模式且无历史数据",
    )


def _unrun_result(source) -> object:
    from .schemas.records import AdapterResult

    return AdapterResult(
        source_id=source.source_id,
        status="skipped" if source.status == "optional" else "disabled",
        error_message=None if source.status == "disabled" else "本次未运行（可选来源）",
    )


def _write_reports(results, n_records, unmapped, overall, stats) -> None:
    payload = {
        "generated_at": utc_now_iso(),
        "records": n_records,
        "overall_models": len(overall["models"]),
        "unmapped_count": len(unmapped),
        "files_written": stats["files_written"],
        "sources": [
            {
                "source_id": r.source_id,
                "status": r.status,
                "records": len(r.records),
                "error": r.error_message,
                "response_time_ms": r.response_time_ms,
            }
            for r in results
        ],
    }
    LATEST_UPDATE_JSON.parent.mkdir(parents=True, exist_ok=True)
    LATEST_UPDATE_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        f"# 数据更新报告 · {payload['generated_at']}",
        "",
        f"- 成绩记录：**{n_records}** 条；综合榜模型：**{payload['overall_models']}** 个；未映射模型名：{len(unmapped)} 个",
        "",
        "## 数据源状态",
        "",
        "| 来源 | 状态 | 记录数 | 耗时 | 备注 |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.source_id} | {r.status} | {len(r.records)} | "
            f"{r.response_time_ms or '-'}ms | {(r.error_message or '-').replace('|', '/')} |"
        )
    if unmapped:
        lines += ["", "## 待人工映射的模型名（Top 20）", ""]
        for u in unmapped[:20]:
            lines.append(f"- `{u.raw_name}`（来自 {u.source_id}，出现 {u.occurrences} 次）")
    LATEST_UPDATE_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Model Atlas 数据更新流水线")
    parser.add_argument("--sources", help="仅运行指定来源，逗号分隔", default=None)
    parser.add_argument("--offline", action="store_true", help="离线模式：使用上次成功数据")
    args = parser.parse_args()
    code = run(args.sources.split(",") if args.sources else None, offline=args.offline)
    sys.exit(code)


if __name__ == "__main__":
    main()
