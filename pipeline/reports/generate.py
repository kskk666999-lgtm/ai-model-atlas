"""静态 JSON 输出：public/data/** 的唯一生成入口。

- 原子写入（tmp + replace），内容 Hash 变化才写盘
- 任何文件生成失败都不应清空旧文件（先算后写）
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..paths import PUBLIC_DATA_DIR
from ..schemas.records import utc_now_iso


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_json(path: Path, payload) -> bool:
    """写入 JSON；与现有内容一致时跳过。返回是否实际写入。"""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    _atomic_write(path, text)
    return True


def _model_lite(model_entry, capability_indices: dict, overall_row: dict | None) -> dict:
    m = model_entry
    return {
        "model_id": m.canonical_id,
        "display_name": m.display_name,
        "provider": m.provider,
        "family": m.family,
        "variant": m.variant,
        "region": m.region,
        "open_weights": m.open_weights,
        "license": m.license,
        "modalities": m.modalities,
        "context_window": m.context_window,
        "release_date": m.release_date,
        "official_model_page": m.official_model_page,
        "capability_indices": capability_indices,
        "overall_index": overall_row["index"] if overall_row else None,
        "overall_rank": overall_row["rank"] if overall_row else None,
        "overall_benchmark_count": overall_row.get("benchmark_count") if overall_row else None,
        "overall_source_count": overall_row.get("source_count") if overall_row else None,
    }


def _record_row(rec, include_notes: bool = True) -> dict:
    row = {
        "benchmark_id": rec.benchmark_id,
        "benchmark_name": rec.benchmark_name,
        "capability": rec.capability,
        "source_id": rec.source_id,
        "source_name": rec.source_name,
        "source_level": rec.source_level,
        "source_url": rec.source_url,
        "model_id": rec.model_id,
        "raw_model_name": rec.raw_model_name,
        "model_is_unmapped": rec.model_is_unmapped,
        "score": rec.score,
        "score_unit": rec.score_unit,
        "higher_is_better": rec.higher_is_better,
        "rank": rec.rank,
        "evaluation_date": rec.evaluation_date,
        "evaluation_target_type": rec.evaluation_target_type,
        "agent_scaffold": rec.agent_scaffold,
        "prompt_mode": rec.prompt_mode,
        "benchmark_version": rec.benchmark_version,
        "sample_size": rec.sample_size,
        "reasoning_effort": rec.reasoning_effort,
        "fetched_at": rec.fetched_at,
    }
    if include_notes:
        row["notes"] = rec.notes
    return row


def generate_site_data(
    *,
    records: list,
    results: list,
    normalizer,
    models_registry: list,
    sources_registry: list,
    capabilities_registry: list,
    benchmarks_registry: dict,
    capability_weights: dict,
    capability_composites: dict,
    official_rankings: dict,  # benchmark_id -> ranking rows (with record refs)
    overall: dict,
    rank_changes: dict,
    trend_30d: list,
    history_series: dict,  # model_id -> {cap: [{date, rank, index}]}
    history_dates_count: int,
    interval_hours: int = 12,
) -> dict:
    """生成全部前端数据文件，返回统计信息。"""
    stats = {"files_written": 0}
    # 数据驱动时间戳：取所有记录中最大的 fetched_at（而非当前墙钟时间）。
    # 配合适配器的"业务内容不变则继承 fetched_at"策略，保证数据无变化时
    # 输出文件逐字节稳定，CI 不会产生无意义提交。
    all_ts = [r.fetched_at for r in records if r.fetched_at]
    now = max(all_ts) if all_ts else utc_now_iso()

    used_models = {r.model_id for r in records if not r.model_is_unmapped}
    unmapped_ids = {r.model_id for r in records if r.model_is_unmapped}

    # 模型维度：能力指数 / 综合指数 / 价格速度（来自记录）
    by_model_records: dict[str, list] = {}
    for rec in records:
        by_model_records.setdefault(rec.model_id, []).append(rec)

    def latest_score(model_id: str, benchmark_id: str) -> float | None:
        cands = [
            r for r in by_model_records.get(model_id, [])
            if r.benchmark_id == benchmark_id
        ]
        if not cands:
            return None
        cands.sort(key=lambda r: r.evaluation_date or "", reverse=True)
        return cands[0].score

    overall_rows = {m["model_id"]: m for m in overall["models"]}

    cap_names = {c["capability_id"]: c for c in capabilities_registry}
    weight_presets = None
    import yaml as _yaml

    from ..paths import REGISTRY_CAPABILITIES
    cap_yaml = _yaml.safe_load(REGISTRY_CAPABILITIES.read_text(encoding="utf-8"))
    weight_presets = cap_yaml.get("weight_presets") or []

    # ---------- meta.json ----------
    active_sources = [s for s in results if s.status in ("ok", "degraded")]
    failed_sources = [s for s in results if s.status == "failed"]
    last_success = max(
        (r.fetched_at for s in active_sources for r in s.records if r.fetched_at),
        default=None,
    )
    meta = {
        "generated_at": now,
        "pipeline_version": "0.1.0",
        "demo_mode": False,
        "site_name": "AI 模型天梯",
        "latest_commit": os.environ.get("GITHUB_SHA"),
        "counts": {
            "models": len(used_models),
            "unmapped_models": len(unmapped_ids),
            "benchmarks": len({r.benchmark_id for r in records}),
            "capabilities_active": len(capability_composites),
            "records": len(records),
            "sources_active": len(active_sources),
            "history_snapshots": history_dates_count,
        },
        "update": {
            "interval_hours": interval_hours,
            "last_success": last_success,
            "failed_sources": [s.source_id for s in failed_sources],
            "degraded_sources": [s.source_id for s in results if s.status == "degraded"],
        },
        "weight_presets": weight_presets,
    }
    if write_json(PUBLIC_DATA_DIR / "meta.json", meta):
        stats["files_written"] += 1

    # ---------- source-health.json ----------
    state_path = PUBLIC_DATA_DIR / "source-health.json"
    health_sources = []
    for s in sources_registry:
        result = next((r for r in results if r.source_id == s.source_id), None)
        run_status = result.status if result else ("disabled" if s.status == "disabled" else "skipped")
        recs = result.records if result else []
        last_eval = max((r.evaluation_date or "" for r in recs), default=None)
        # 数据驱动的 last_success：该来源记录的最大 fetched_at（内容不变则稳定）
        src_last_success = max((r.fetched_at for r in recs if r.fetched_at), default=None) \
            if run_status in ("ok", "degraded") else None
        health_sources.append({
            "source_id": s.source_id,
            "source_name": s.source_name,
            "source_level": s.source_level,
            "homepage_url": s.homepage_url,
            "docs_url": s.docs_url,
            "description": s.description,
            "license": s.license,
            "attribution": s.attribution,
            "requires_api_key": s.requires_api_key,
            "included_in_composite": s.included_in_composite,
            "registry_status": s.status,
            "run_status": run_status,
            "record_count": len(recs),
            "last_success": src_last_success,
            "error_message": result.error_message if result else None,
            "data_freshness": last_eval,
        })
    health = {
        "generated_at": now,
        "counts": {
            "healthy": sum(1 for x in health_sources if x["run_status"] == "ok"),
            "degraded": sum(1 for x in health_sources if x["run_status"] == "degraded"),
            "failed": sum(1 for x in health_sources if x["run_status"] == "failed"),
            "disabled": sum(1 for x in health_sources if x["run_status"] in ("disabled", "skipped")),
        },
        "sources": health_sources,
    }
    if write_json(state_path, health):
        stats["files_written"] += 1

    # ---------- capabilities/*.json ----------
    caps_dir = PUBLIC_DATA_DIR / "capabilities"
    cap_index_of: dict[str, dict[str, dict]] = {}  # model_id -> {cap: {index, rank}}
    for cap in capabilities_registry:
        cap_id = cap["capability_id"]
        comp = capability_composites.get(cap_id)
        cap_records = [r for r in records if r.capability == cap_id]
        bench_ids = sorted({r.benchmark_id for r in cap_records})
        official_rows = []
        for bid in bench_ids:
            for row in official_rankings.get(bid, []):
                rec = row["record"]
                official_rows.append({
                    **_record_row(rec),
                    "rank": row["rank"],
                    "tie": row["tie"],
                })
        cap_payload = {
            "capability_id": cap_id,
            "name": cap["name"],
            "short": cap.get("short", cap["name"]),
            "status": cap.get("status", "active"),
            "description": cap.get("description"),
            "generated_at": now,
            "benchmarks": [
                {
                    "benchmark_id": bid,
                    "benchmark_name": benchmarks_registry[bid]["benchmark_name"],
                    "source_id": benchmarks_registry[bid]["source_id"],
                    "higher_is_better": benchmarks_registry[bid]["higher_is_better"],
                    "score_unit": benchmarks_registry[bid]["score_unit"],
                    "record_count": sum(1 for r in cap_records if r.benchmark_id == bid),
                }
                for bid in bench_ids
            ],
            "official": official_rows,
            "composite": comp,
        }
        if write_json(caps_dir / f"{cap_id}.json", cap_payload):
            stats["files_written"] += 1
        if comp:
            for m in comp["models"]:
                cap_index_of.setdefault(m["model_id"], {})[cap_id] = {
                    "index": m["index"], "rank": m["rank"],
                }

    # ---------- benchmarks/<id>.json ----------
    bench_dir = PUBLIC_DATA_DIR / "benchmarks"
    for bid, rows in official_rankings.items():
        payload = {
            "benchmark_id": bid,
            "benchmark_name": benchmarks_registry[bid]["benchmark_name"],
            "source_id": benchmarks_registry[bid]["source_id"],
            "higher_is_better": benchmarks_registry[bid]["higher_is_better"],
            "score_unit": benchmarks_registry[bid]["score_unit"],
            "generated_at": now,
            "rows": [{**_record_row(row["record"]), "rank": row["rank"], "tie": row["tie"]} for row in rows],
        }
        if write_json(bench_dir / f"{bid}.json", payload):
            stats["files_written"] += 1

    # ---------- models/index.json ----------
    models_index = []
    for entry in models_registry:
        if entry.canonical_id not in used_models:
            continue
        cap_indices = {c: v["index"] for c, v in cap_index_of.get(entry.canonical_id, {}).items()}
        price_in = latest_score(entry.canonical_id, "aa-price-input")
        price_out = latest_score(entry.canonical_id, "aa-price-output")
        speed = latest_score(entry.canonical_id, "aa-output-speed")
        latency = latest_score(entry.canonical_id, "aa-latency")
        n_benchmarks = len({r.benchmark_id for r in by_model_records.get(entry.canonical_id, [])})
        n_sources = len({r.source_id for r in by_model_records.get(entry.canonical_id, [])})
        models_index.append({
            **_model_lite(entry, cap_indices, overall_rows.get(entry.canonical_id)),
            "price_input_usd_per_mtok": price_in,
            "price_output_usd_per_mtok": price_out,
            "output_speed_tps": speed,
            "latency_seconds": latency,
            "benchmark_count": n_benchmarks,
            "source_count": n_sources,
            "rank_changes": rank_changes.get(entry.canonical_id, {}),
        })
    if write_json(PUBLIC_DATA_DIR / "models" / "index.json", {"generated_at": now, "models": models_index}):
        stats["files_written"] += 1

    # ---------- models/<id>.json ----------
    for entry in models_registry:
        mid = entry.canonical_id
        if mid not in used_models:
            continue
        recs = by_model_records.get(mid, [])
        rows = []
        for rec in sorted(recs, key=lambda r: (r.capability, -r.score if r.higher_is_better else r.score)):
            row = _record_row(rec)
            bench_rank_rows = official_rankings.get(rec.benchmark_id, [])
            rank_row = next((x for x in bench_rank_rows if x["record"] is rec), None)
            if rank_row:
                row["rank"] = rank_row["rank"]
                row["tie"] = rank_row["tie"]
            rows.append(row)
        radar = []
        for cap_id, v in sorted(cap_index_of.get(mid, {}).items()):
            c = cap_names.get(cap_id, {})
            radar.append({
                "capability_id": cap_id,
                "name": c.get("short", c.get("name", cap_id)),
                "index": v["index"],
                "rank": v["rank"],
            })
        payload = {
            "generated_at": now,
            "meta": _model_lite(entry, {c: v["index"] for c, v in cap_index_of.get(mid, {}).items()},
                                overall_rows.get(mid)),
            "radar": radar,
            "records": rows,
            "history": history_series.get(mid, {}),
        }
        if write_json(PUBLIC_DATA_DIR / "models" / f"{mid}.json", payload):
            stats["files_written"] += 1

    # ---------- history/summary.json ----------
    if write_json(
        PUBLIC_DATA_DIR / "history" / "summary.json",
        {"generated_at": now, "trend_30d": trend_30d, "series": history_series},
    ):
        stats["files_written"] += 1

    # ---------- homepage.json ----------
    movers = []
    for mid, caps in rank_changes.items():
        entry = next((e for e in models_registry if e.canonical_id == mid), None)
        if not entry:
            continue
        for cap, ch in caps.items():
            if "d7" in ch and ch["d7"] >= 1:
                movers.append({
                    "model_id": mid,
                    "display_name": entry.display_name,
                    "provider": entry.provider,
                    "capability": cap,
                    "delta": ch["d7"],
                })
    movers.sort(key=lambda x: -x["delta"])
    homepage = {
        "generated_at": now,
        "stats": meta["counts"],
        "update": meta["update"],
        "top3": {},
        "movers_7d": movers[:8],
        "trend_30d": trend_30d,
    }
    for cap_id in ("reasoning", "coding", "math", "chinese", "multimodal", "swe"):
        comp = capability_composites.get(cap_id)
        if not comp:
            continue
        names = {m["model_id"]: next(
            (e.display_name for e in models_registry if e.canonical_id == m["model_id"]), m["model_id"])
            for m in comp["models"][:3]}
        providers = {m["model_id"]: next(
            (e.provider for e in models_registry if e.canonical_id == m["model_id"]), None)
            for m in comp["models"][:3]}
        homepage["top3"][cap_id] = [
            {
                "model_id": m["model_id"],
                "display_name": names[m["model_id"]],
                "provider": providers[m["model_id"]],
                "index": m["index"],
                "rank": m["rank"],
            }
            for m in comp["models"][:3]
        ]
    if write_json(PUBLIC_DATA_DIR / "homepage.json", homepage):
        stats["files_written"] += 1

    return stats
