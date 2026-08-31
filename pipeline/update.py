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
    benchmark_eligibility,
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


def _composite_candidate_records(records, sources_registry):
    """只保留注册表明确允许进入综合分的数据源记录。"""
    composite_source_ids = {
        source.source_id for source in sources_registry if source.included_in_composite
    }
    return [record for record in records if record.source_id in composite_source_ids]


def _has_recent_evidence(record, today: date, max_days: int = 120) -> bool:
    """CURRENT 榜兜底必须有近期运行日或上游快照；版本号本身不算日期证据。"""
    from .registry.freshness import parse_date

    evidence_date = parse_date(record.evaluation_date) or parse_date(
        record.upstream_updated_at
    )
    if evidence_date is None:
        return False
    age_days = (today - evidence_date).days
    return 0 <= age_days <= max_days


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
    SOURCE_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


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

    all_records = [r for res in results for r in res.records]

    # 部分更新（--sources）时，未选中来源的数据用其 LKG 合并，
    # 绝不允许部分运行把其他来源的数据从 public/data 里抹掉。
    if source_filter:
        from .paths import RECORDS_LKG_DIR
        from .schemas.records import BenchmarkRecord

        for s in sources_registry:
            if s.source_id in source_filter or s.status != "active":
                continue
            lkg_file = RECORDS_LKG_DIR / f"{s.source_id}.json"
            if lkg_file.exists():
                import json as _json

                lkg = _json.loads(lkg_file.read_text(encoding="utf-8"))
                merged = [BenchmarkRecord.model_validate(r) for r in (lkg.get("records") or [])]
                all_records.extend(merged)
                print(f"    - {s.source_id}: 部分更新模式，合并 LKG {len(merged)} 条")
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

    # ---- 模型目录（models.dev）：新鲜度 / 生命周期 / 当前资格 ----
    print("[4.5/8] 加载模型目录（models.dev）...")
    from .registry.directory import enrich_entry, load_model_directory
    from .registry.freshness import is_current, today_utc

    directory = None
    directory_meta = None
    try:
        directory, directory_meta = load_model_directory(http)
        print(f"    目录条目 {directory_meta['models']} 个（{directory_meta['providers']} 个 provider）")
    except Exception as e:
        print(f"    [warn] 模型目录加载失败（回退 LKG / 元数据缺失）: {type(e).__name__}: {e}")

    def compute_freshness():
        """canonical_id -> 新鲜度/生命周期/当前资格。"""
        today = today_utc()
        out: dict[str, dict] = {}
        # 活跃来源"最新官方榜"兜底信号
        latest_board_models: set[str] = set()
        for board_source in (
            "livebench", "terminalbench", "superclue", "superclue_vlm",
            "superclue_longcontext", "kernelbench"
        ):
            versions = [
                r.benchmark_version for r in all_records
                if r.source_id == board_source and r.benchmark_version
            ]
            latest = max(versions) if versions else None
            latest_board_models.update({
                r.model_id for r in all_records
                if r.source_id == board_source and latest and r.benchmark_version == latest
                and not r.model_is_unmapped
                and _has_recent_evidence(r, today)
            })
        swe_recent_models = {
            r.model_id for r in all_records
            if r.source_id == "swebench" and r.evaluation_date
            and (today - date.fromisoformat(r.evaluation_date)).days <= 120
        }
        for entry in models_registry:
            enriched = None
            if directory is not None:
                hit = directory.match(entry.canonical_id, entry.aliases)
                if hit is not None:
                    enriched = enrich_entry(hit)
            seen_recent = entry.canonical_id in latest_board_models or entry.canonical_id in swe_recent_models
            if enriched:
                if enriched["freshness_bucket"] == "UNKNOWN":
                    enriched["is_current"] = is_current(
                        lifecycle=enriched["lifecycle_status"],
                        bucket="UNKNOWN",
                        seen_in_latest_official_board=seen_recent,
                    )
                    if seen_recent:
                        enriched["freshness_bucket"] = "ACTIVE"
                        enriched["freshness_note"] = "元数据缺失，因出现在活跃来源最新官方榜而视为当前"
                enriched["matched_directory"] = True
            else:
                enriched = {
                    "release_date": entry.release_date,
                    "last_updated": None,
                    "freshness_days": None,
                    "freshness_bucket": None,
                    "lifecycle_status": "unknown",
                    "is_current": seen_recent,
                    "matched_directory": False,
                }
                if entry.release_date:
                    from .registry.freshness import freshness_bucket as _fb
                    from .registry.freshness import freshness_days as _fd
                    enriched["freshness_days"] = _fd(entry.release_date, today=today)
                    enriched["freshness_bucket"] = _fb(enriched["freshness_days"])
                    enriched["is_current"] = is_current(
                        lifecycle=enriched["lifecycle_status"],
                        bucket=enriched["freshness_bucket"],
                        seen_in_latest_official_board=seen_recent,
                    )
                elif seen_recent:
                    enriched["freshness_bucket"] = "ACTIVE"
                    enriched["freshness_note"] = "元数据缺失，因出现在活跃来源最新官方榜而视为当前"
            out[entry.canonical_id] = enriched
        return out

    freshness_map = compute_freshness()
    n_current = sum(1 for v in freshness_map.values() if v.get("is_current"))
    n_legacy = sum(1 for v in freshness_map.values()
                   if v.get("lifecycle_status") in ("legacy", "deprecated")
                   or v.get("freshness_bucket") == "LEGACY")
    print(f"    当前模型 {n_current} 个；legacy/deprecated {n_legacy} 个")
    http.close()

    print("[5/8] 排名计算 ...")
    official_rankings = {bid: benchmark_ranking(
        [r for r in all_records if r.benchmark_id == bid]) for bid in benchmarks_by_id}
    for _bid, rows in official_rankings.items():
        for row in rows:
            row["record"].rank = row["rank"]

    # 基准相关性：当前模型覆盖权重远高于历史记录总量，
    # 避免"100 个旧模型、只有 2 个当前模型"的基准霸占首页。
    def benchmark_relevance(today):
        out: dict[str, dict] = {}
        for bid, rows in official_rankings.items():
            if not rows:
                continue
            recs = [row["record"] for row in rows]
            distinct = {r.model_id if not r.model_is_unmapped else (r.raw_model_name or r.model_id)
                        for r in recs}
            current_ids = {r.model_id for r in recs
                           if not r.model_is_unmapped and
                           freshness_map.get(r.model_id, {}).get("is_current")}
            current_count = len(current_ids)
            coverage = current_count / len(distinct) if distinct else 0.0
            from .registry.freshness import parse_date as _pd

            # Prefer a real per-model run date; otherwise use the upstream
            # leaderboard/file snapshot. Benchmark versions are never dates.
            parsed = [
                d0 for d0 in (
                    _pd(r.evaluation_date) or _pd(r.upstream_updated_at) for r in recs
                ) if d0
            ]
            recency_days = min((today - d0).days for d0 in parsed) if parsed else 9999
            recency = max(0.0, 1 - recency_days / 365)
            score = (0.45 * min(1.0, current_count / 20)
                     + 0.25 * coverage
                     + 0.20 * recency
                     + 0.10 * min(1.0, len(recs) / 200))
            out[bid] = {
                "score": round(score, 4),
                "current_model_count": current_count,
                "distinct_models": len(distinct),
                "current_model_coverage": round(coverage, 3),
                "recency_days": recency_days,
                "record_count": len(recs),
            }
        return out

    relevance = benchmark_relevance(today_utc())
    top_by_relevance = sorted(relevance.items(), key=lambda kv: -kv[1]["score"])
    if top_by_relevance:
        print("    相关性最高的基准："
              + ", ".join(f"{bid}({v['current_model_count']} 当前模型)" for bid, v in top_by_relevance[:3]))

    # 每能力选主基准（供首页 Top 榜/热力图）：按相关性得分
    cap_top_benchmarks: dict[str, str] = {}
    for cap in caps_registry:
        cap_id = cap["capability_id"]
        bids = [bid for bid, b in benchmarks_by_id.items()
                if b["capability"] == cap_id and bid in relevance]
        if bids:
            cap_top_benchmarks[cap_id] = max(bids, key=lambda bid: relevance[bid]["score"])

    # 写出全量模型目录（All Models 页面数据）
    directory_enriched: list = []
    if directory is not None:
        import json as _json
        enriched_dir = [enrich_entry(e) for e in directory.entries]
        directory_enriched = enriched_dir
        enriched_dir.sort(key=lambda x: (x.get("release_date") or "", x["model_id"]), reverse=True)
        from .paths import PUBLIC_DATA_DIR as _PDD
        (_PDD / "directory.json").write_text(
            _json.dumps({"generated_at": utc_now_iso(),
                         "source": "models.dev",
                         "count": len(enriched_dir),
                         "models": enriched_dir},
                        ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8", newline="\n")
        print(f"    directory.json 写入 {len(enriched_dir)} 条目录条目")

    # 基准级门槛只评估注册表明确允许进入综合分的数据源。
    # 新的中文、多模态、长上下文与 Agent 榜先作为可溯源的独立原始榜展示，
    # 不能因为覆盖率达标就绕过 source.included_in_composite 配置。
    composite_records = _composite_candidate_records(all_records, sources_registry)
    # 基准级门槛：映射覆盖率 >= 95% 且已映射去重模型 >= 10
    eligibility = benchmark_eligibility(composite_records)
    print(f"    通过综合门槛的基准：{len(eligibility)} 个")
    _write_mapping_coverage(all_records, eligibility)

    capability_composites = {}
    composite_gates: dict[str, list[dict]] = {}
    for cap in caps_registry:
        cap_id = cap["capability_id"]
        # 完整 Agent 系统能力只提供官方原始榜，不折算基础模型指数。
        if cap_id in {"swe", "agentic_general", "gpu_kernel"}:
            composite_gates[cap_id] = [
                {"reason": "成绩来自「模型 + Agent 框架 + 推理档位」的完整系统，"
                           "不能折算为基础模型能力百分位；请使用官方原始榜"}
            ]
            continue
        cap_records = [
            r for r in all_records
            if r.capability == cap_id
            and not r.model_is_unmapped
            and r.evaluation_target_type not in AGENT_TYPES
        ]
        comp, gate_notes = capability_composite(cap_records, benchmarks_by_id, eligibility)
        composite_gates[cap_id] = gate_notes
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
        composite_gates=composite_gates,
        eligibility=eligibility,
        freshness_map=freshness_map,
        cap_top_benchmarks=cap_top_benchmarks,
        directory_enriched=directory_enriched,
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


def _write_mapping_coverage(records, eligibility) -> None:
    import json as _json
    from collections import defaultdict

    from .paths import MAPPING_COVERAGE_JSON, MAPPING_COVERAGE_MD

    by_bench: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "distinct": set(), "mapped": set(), "sources": set(),
    })
    for r in records:
        st = by_bench[r.benchmark_id]
        st["total"] += 1
        st["distinct"].add(
            r.model_id if not r.model_is_unmapped else (r.raw_model_name or r.model_id))
        st["sources"].add(r.source_id)
        if not r.model_is_unmapped:
            st["mapped"].add(r.model_id)
    rows = []
    for bid, st in sorted(by_bench.items()):
        distinct = len(st["distinct"])
        mapped = len(st["mapped"])
        rate = round(mapped / distinct, 4) if distinct else 0.0
        el = eligibility.get(bid)
        rows.append({
            "benchmark_id": bid,
            "sources": sorted(st["sources"]),
            "total_records": st["total"],
            "distinct_models": distinct,
            "mapped_distinct_models": mapped,
            "mapped_rate": rate,
            "eligible_for_composite": bool(el),
            "reason": (el["reason"] if el else "未通过门槛（映射覆盖率/参评模型数不足）"),
        })
    MAPPING_COVERAGE_JSON.parent.mkdir(parents=True, exist_ok=True)
    MAPPING_COVERAGE_JSON.write_text(
        _json.dumps({"generated_at": utc_now_iso(), "benchmarks": rows},
                    ensure_ascii=False, indent=1),
        encoding="utf-8", newline="\n")
    md = ["# 模型名称映射覆盖率", "",
          "| 基准 | 来源 | 记录数 | 去重模型 | 已映射 | 映射率 | 可进综合 | 说明 |",
          "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(
            f"| {r['benchmark_id']} | {','.join(r['sources'])} | {r['total_records']} "
            f"| {r['distinct_models']} | {r['mapped_distinct_models']} "
            f"| {r['mapped_rate']:.0%} | {'✅' if r['eligible_for_composite'] else '❌'} "
            f"| {r['reason']} |")
    MAPPING_COVERAGE_MD.write_text("\n".join(md), encoding="utf-8", newline="\n")


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
    LATEST_UPDATE_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Model Atlas 数据更新流水线")
    parser.add_argument("--sources", help="仅运行指定来源，逗号分隔", default=None)
    parser.add_argument("--offline", action="store_true", help="离线模式：使用上次成功数据")
    args = parser.parse_args()
    code = run(args.sources.split(",") if args.sources else None, offline=args.offline)
    sys.exit(code)


if __name__ == "__main__":
    main()
