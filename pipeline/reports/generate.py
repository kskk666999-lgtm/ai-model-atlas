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
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def write_json(path: Path, payload) -> bool:
    """写入 JSON；与现有内容一致时跳过。返回是否实际写入。

    sort_keys=True：键序规范化。任何构造顺序差异（如 set 推导的跨进程
    迭代顺序随机）都不再影响输出字节，这是幂等提交的关键保证之一。
    """
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
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


FRESHNESS_REF: dict = {"map": None}  # 由 generate_site_data 注入 freshness_map


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
        "record_verification_status": rec.record_verification_status,
        "data_file_url": rec.data_file_url,
        "data_json_path": rec.data_json_path,
        "data_sha256": rec.data_sha256,
        "upstream_updated_at": rec.upstream_updated_at,
    }
    if include_notes:
        row["notes"] = rec.notes
    fm = (FRESHNESS_REF.get("map") or {}).get(rec.model_id)
    if fm:
        row["is_current"] = fm.get("is_current")
        row["freshness_bucket"] = fm.get("freshness_bucket")
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
    composite_gates: dict | None = None,
    eligibility: dict | None = None,
    freshness_map: dict | None = None,
    cap_top_benchmarks: dict | None = None,
    directory_enriched: list | None = None,
    official_rankings: dict,  # benchmark_id -> ranking rows (with record refs)
    overall: dict,
    rank_changes: dict,
    trend_30d: list,
    history_series: dict,  # model_id -> {cap: [{date, rank, index}]}
    history_dates_count: int,
    interval_hours: int = 12,
) -> dict:
    """生成全部前端数据文件，返回统计信息。"""
    composite_gates = composite_gates or {}
    eligibility = eligibility or {}
    freshness_map = freshness_map or {}
    FRESHNESS_REF["map"] = freshness_map
    cap_top_benchmarks = cap_top_benchmarks or {}
    directory_enriched = directory_enriched or []
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
            "group": cap.get("group", "text_reasoning"),
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
                    "eligible_for_composite": bool(eligibility.get(bid)),
                    "eligibility": eligibility.get(bid),
                }
                for bid in bench_ids
            ],
            "official": official_rows,
            "composite": comp,
            "composite_gate": composite_gates.get(cap_id) or [],
        }
        if write_json(caps_dir / f"{cap_id}.json", cap_payload):
            stats["files_written"] += 1
        if comp:
            for m in comp["models"]:
                cap_index_of.setdefault(m["model_id"], {})[cap_id] = {
                    "index": m["index"], "rank": m["rank"],
                }

    # ---------- capabilities/index.json（前端能力单一事实源）----------
    cap_index_payload = {
        "generated_at": now,
        "groups": cap_yaml.get("groups") or [],
        "capabilities": [
            {
                "capability_id": c["capability_id"],
                "name": c["name"],
                "short": c.get("short", c["name"]),
                "group": c.get("group", "text_reasoning"),
                "status": c.get("status", "active"),
                "description": c.get("description"),
                "planned_source": c.get("planned_source"),
                "benchmark_count": len({r.benchmark_id for r in records
                                        if r.capability == c["capability_id"]}),
                "has_composite": c["capability_id"] in capability_composites,
            }
            for c in capabilities_registry
        ],
        "weight_presets": weight_presets,
    }
    if write_json(PUBLIC_DATA_DIR / "capabilities" / "index.json", cap_index_payload):
        stats["files_written"] += 1

    # ---------- heatmap.json（首页能力×模型热力图，官方原始分 Top N）----------
    heatmap_caps = [
        ("reasoning", None), ("coding", None), ("math", None),
        ("chinese_mm", None), ("multimodal", None), ("swe", "swebench-verified"),
    ]
    heatmap = {"generated_at": now, "capabilities": [], "models": [], "cells": {}}
    model_order: list[str] = []
    for cap_id, bench_filter in heatmap_caps:
        rows = [row for row in (official_rankings.get(
            bench_filter, []) if bench_filter else official_rankings.get(
            next((bid for bid, rows2 in official_rankings.items()
                  if rows2 and benchmarks_registry[bid]["capability"] == cap_id), ""), []))]
        # 基准选择：相关性得分优先（当前模型覆盖为主权重）
        if not bench_filter:
            best_bid = cap_top_benchmarks.get(cap_id)
        if best_bid is None:
            cap_bids = [
                (bid, len(irows)) for bid, irows in official_rankings.items()
                if irows and benchmarks_registry[bid]["capability"] == cap_id
            ]
            eligible_bids = [bid for bid, _ in cap_bids if bid in eligibility]
            best_bid = eligible_bids[0] if eligible_bids else (
                max(cap_bids, key=lambda x: x[1])[0] if cap_bids else None)
        best_rows = official_rankings.get(best_bid or "", []) if best_bid else []
        rows = best_rows
        if not rows:
            continue
        # 首页热力图只展示当前模型与已映射模型
        rows = [row for row in rows
                if not row["record"].model_is_unmapped
                and (FRESHNESS_REF.get("map") or {}).get(
                    row["record"].model_id, {}).get("is_current", False)]
        if not rows:
            continue  # 该基准当前无活跃模型，不出现在首页热力图
        hib = rows[0]["record"].higher_is_better
        top = rows[:12]
        cells = []
        for row in top:
            rec = row["record"]
            entry = next((e for e in models_registry if e.canonical_id == rec.model_id), None)
            cells.append({
                "model_id": rec.model_id,
                "display_name": entry.display_name if entry else (rec.raw_model_name or rec.model_id),
                "provider": entry.provider if entry else None,
                "score": rec.score,
                "rank": row["rank"],
                "tie": row["tie"],
                "agent_scaffold": rec.agent_scaffold,
                "evaluation_date": rec.evaluation_date,
            })
            if rec.model_id not in model_order:
                model_order.append(rec.model_id)
        heatmap["capabilities"].append({
            "capability_id": cap_id,
            "benchmark_id": bench_filter or best_bid,
            "higher_is_better": hib,
            "score_unit": rows[0]["record"].score_unit,
            "cells": cells,
        })
    heatmap["models"] = model_order
    if write_json(PUBLIC_DATA_DIR / "heatmap.json", heatmap):
        stats["files_written"] += 1

    # ---------- benchmarks/<id>.json ----------
    bench_dir = PUBLIC_DATA_DIR / "benchmarks"
    for bid, rows in official_rankings.items():
        if not rows:
            continue  # 无成绩的基准不产出空文件（如未配置 Key 的可选来源）
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
        # 价格：优先 Artificial Analysis（可选来源），缺失时回退 LiveBench 官方统计
        canonical = entry.canonical_id

        def latest_price(bench_aa: str, bench_lb: str, *, cid: str = canonical) -> float | None:
            v = latest_score(cid, bench_aa)
            return v if v is not None else latest_score(cid, bench_lb)

        cap_indices = {c: v["index"] for c, v in cap_index_of.get(entry.canonical_id, {}).items()}
        price_in = latest_price("aa-price-input", "livebench-price-input")
        price_out = latest_price("aa-price-output", "livebench-price-output")
        speed = latest_score(entry.canonical_id, "aa-output-speed")
        latency = latest_score(entry.canonical_id, "aa-latency")
        n_benchmarks = len({r.benchmark_id for r in by_model_records.get(entry.canonical_id, [])})
        n_sources = len({r.source_id for r in by_model_records.get(entry.canonical_id, [])})
        fm_i = freshness_map.get(entry.canonical_id, {})
        models_index.append({
            **_model_lite(entry, cap_indices, overall_rows.get(entry.canonical_id)),
            "is_current": fm_i.get("is_current", False),
            "freshness_bucket": fm_i.get("freshness_bucket"),
            "lifecycle_status": fm_i.get("lifecycle_status"),
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
        for rec in sorted(
            recs,
            key=lambda r: (
                r.capability,
                -r.score if r.higher_is_better else r.score,
                r.benchmark_id,
                r.agent_scaffold or "",
            ),
        ):
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
        # Family Lineage：同家族模型按发布日期排序，标出前代/后代
        fm_meta = freshness_map.get(mid, {})
        family_members = []
        if entry.family:
            for e2 in models_registry:
                if e2.family == entry.family and e2.canonical_id != mid:
                    rel = (freshness_map.get(e2.canonical_id, {}).get("release_date")
                           or e2.release_date)
                    family_members.append({
                        "model_id": e2.canonical_id,
                        "display_name": e2.display_name,
                        "release_date": rel,
                    })
        family_members.sort(key=lambda x: x.get("release_date") or "9999")
        my_rel = fm_meta.get("release_date") or entry.release_date
        lineage = {
            "family": entry.family,
            "previous": next((f for f in reversed(family_members)
                              if (f.get("release_date") or "") < (my_rel or "")), None),
            "next": next((f for f in family_members
                          if (f.get("release_date") or "") > (my_rel or "")), None),
        }
        payload = {
            "generated_at": now,
            "meta": _model_lite(entry, {c: v["index"] for c, v in cap_index_of.get(mid, {}).items()},
                                overall_rows.get(mid)),
            "freshness": {
                "freshness_days": fm_meta.get("freshness_days"),
                "freshness_bucket": fm_meta.get("freshness_bucket"),
                "lifecycle_status": fm_meta.get("lifecycle_status"),
                "is_current": fm_meta.get("is_current"),
                "release_date": fm_meta.get("release_date") or entry.release_date,
                "last_updated": fm_meta.get("last_updated"),
                "matched_directory": fm_meta.get("matched_directory", False),
            },
            "lineage": lineage,
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
    movers.sort(key=lambda x: (-x["delta"], x["model_id"], x["capability"]))
    homepage = {
        "generated_at": now,
        "stats": meta["counts"],
        "update": meta["update"],
        "top3": {},
        "movers_7d": movers[:8],
        "trend_30d": trend_30d,
    }
    # 首页"单项能力前三"：默认官方原始榜（综合指数仅在通过全部门槛时作为次选）
    def _top3_from_official(cap_id: str, benchmark_id: str | None = None):
        # 基准选择：相关性得分（当前模型覆盖为主权重），由 update.py 计算传入
        if benchmark_id is None:
            benchmark_id = cap_top_benchmarks.get(cap_id)
        if benchmark_id is None:
            cap_bids: dict[str, int] = {}
            for r in records:
                if r.capability == cap_id:
                    cap_bids[r.benchmark_id] = cap_bids.get(r.benchmark_id, 0) + 1
            if not cap_bids:
                return None
            eligible_bids = [b for b in cap_bids if b in eligibility]
            benchmark_id = eligible_bids[0] if eligible_bids else max(cap_bids, key=cap_bids.get)
        rows = [r for r in records if r.capability == cap_id and r.benchmark_id == benchmark_id]
        if not rows:
            return None
        total_rows = len(rows)
        # 首页默认只显示当前模型，且禁止未映射名称
        rows = [r for r in rows
                if not r.model_is_unmapped
                and (FRESHNESS_REF.get("map") or {}).get(r.model_id, {}).get("is_current", False)]
        current_count = len(rows)
        if not rows:
            return {"rows": [], "current_count": 0, "total_rows": total_rows,
                    "benchmark_id": benchmark_id}
        hib = rows[0].higher_is_better
        ranked = sorted(rows, key=lambda r: (-r.score if hib else r.score,
                                             r.model_id, r.raw_model_name or ""))
        out, seen_rank, prev = [], 0, None
        for i, r in enumerate(ranked[:3]):
            if prev is None or r.score != prev:
                seen_rank = i + 1
            prev = r.score
            entry = next((e for e in models_registry if e.canonical_id == r.model_id), None)
            fm = (FRESHNESS_REF.get("map") or {}).get(r.model_id, {})
            out.append({
                "model_id": r.model_id,
                "display_name": entry.display_name if entry else (r.raw_model_name or r.model_id),
                "provider": entry.provider if entry else None,
                "score": r.score,
                "rank": seen_rank,
                "benchmark_id": r.benchmark_id,
                "agent_scaffold": r.agent_scaffold,
                "kind": "official",
                "is_current": fm.get("is_current", True),
                "freshness_bucket": fm.get("freshness_bucket"),
            })
        return {"rows": out, "current_count": current_count, "total_rows": total_rows,
                "benchmark_id": benchmark_id}

    def _top3_for(cap_id: str):
        comp = capability_composites.get(cap_id)
        if comp:
            names = {m["model_id"]: next(
                (e.display_name for e in models_registry if e.canonical_id == m["model_id"]), m["model_id"])
                for m in comp["models"][:3]}
            providers = {m["model_id"]: next(
                (e.provider for e in models_registry if e.canonical_id == m["model_id"]), None)
                for m in comp["models"][:3]}
            rows = [{
                "model_id": m["model_id"],
                "display_name": names[m["model_id"]],
                "provider": providers[m["model_id"]],
                "index": m["index"],
                "rank": m["rank"],
                "kind": "composite_relative",
            } for m in comp["models"][:3]]
            return {"rows": rows, "current_count": len(rows), "total_rows": len(rows),
                    "benchmark_id": None}
        if cap_id == "swe":
            return _top3_from_official("swe", cap_top_benchmarks.get("swe", "swebench-verified"))
        return _top3_from_official(cap_id)

    for cap_id in ("reasoning", "coding", "math", "chinese_mm", "multimodal", "swe"):
        block = _top3_for(cap_id)
        if block and block["rows"]:
            homepage["top3"][cap_id] = block
    # Latest Releases：来自模型目录（models.dev），按发布日期窗口
    def releases_within(days: int) -> list[dict]:
        from datetime import datetime as _dt

        today = _dt.strptime(now[:10], "%Y-%m-%d").date()
        out = []
        for e in directory_enriched:
            dstr = e.get("release_date") or e.get("last_updated")
            if not dstr:
                continue
            try:
                d = _dt.strptime(str(dstr)[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            if 0 <= (today - d).days <= days:
                out.append({
                    "model_id": e.get("model_id"),
                    "name": e.get("name"),
                    "provider_id": e.get("provider_id"),
                    "release_date": e.get("release_date"),
                    "last_updated": e.get("last_updated"),
                    "status": e.get("status"),
                    "lifecycle_status": e.get("lifecycle_status"),
                    "freshness_bucket": e.get("freshness_bucket"),
                    "open_weights": e.get("open_weights"),
                    "reasoning": e.get("reasoning"),
                    "tool_call": e.get("tool_call"),
                    "context_window": e.get("context_window"),
                    "input_price": e.get("input_price"),
                    "output_price": e.get("output_price"),
                })
        out.sort(key=lambda x: x.get("release_date") or "", reverse=True)
        return out[:12]

    homepage["latest_releases"] = {
        "7d": releases_within(7),
        "30d": releases_within(30),
        "90d": releases_within(90),
    }
    if write_json(PUBLIC_DATA_DIR / "homepage.json", homepage):
        stats["files_written"] += 1

    return stats
