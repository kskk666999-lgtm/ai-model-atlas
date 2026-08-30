"""确定性排名计算（无任何模型参与）。

规则（与 METHODOLOGY.md 一致）：
1. 官方原始分完整保留，综合指数一律基于"基准内百分位排名"计算，禁止直接平均原始分。
2. 来源权重 A=1.0 / B=0.8 / C=0.6 / D=0（D 级不进入默认综合榜）。
3. 先在每个基准内算百分位；再对同一来源的多个基准取平均；最后按来源权重加权。
4. 并列分数并列排名（competition ranking），并在前端提示"差异可能不显著"。
5. 缺失数据不计为 0，只影响覆盖率与置信度。
6. model_plus_agent 记录不进入基础模型综合指数，Agent 榜单单独展示。
"""
from __future__ import annotations

from collections import defaultdict

from ..schemas.records import SOURCE_LEVELS, BenchmarkRecord

AGENT_TYPES = {"model_plus_agent", "complete_agent_system"}


def source_weight(level: str) -> float:
    return SOURCE_LEVELS.get(level, 0.0)


def benchmark_ranking(records: list[BenchmarkRecord]) -> list[dict]:
    """单个基准的官方原始榜（含并列），返回按排名排序的行。"""
    if not records:
        return []
    hib = records[0].higher_is_better
    # 并列分数用模型标识做确定性决胜（适配器并发完成顺序不得影响输出行序）
    def _sort_key(r: BenchmarkRecord):
        prim = r.score if not hib else -r.score
        return (prim, r.model_id, r.raw_model_name or "", r.agent_scaffold or "",
                r.benchmark_version or "")

    ordered = sorted(records, key=_sort_key)

    # 并列分数组的所有成员都标记并列（1,1,3 式 competition ranking）
    score_counts: dict[float, int] = {}
    for r in ordered:
        score_counts[r.score] = score_counts.get(r.score, 0) + 1

    rows: list[dict] = []
    current_rank = 0
    prev_score: float | None = None
    for i, rec in enumerate(ordered):
        if prev_score is None or rec.score != prev_score:
            current_rank = i + 1
        prev_score = rec.score
        rows.append({
            "rank": current_rank,
            "tie": score_counts[rec.score] > 1,
            "record": rec,
        })
    return rows


def _percentile_positions(ordered_scores: list[float], hib: bool) -> dict[float, float]:
    """分数 -> 平均百分位（并列取平均），映射到 0~100。"""
    n = len(ordered_scores)
    if n == 0:
        return {}
    if n == 1:
        return {ordered_scores[0]: 50.0}
    scores_sorted = sorted(ordered_scores, reverse=hib)
    # competition rank 相同的并列者取其名次区间的平均百分位
    positions: dict[float, list[int]] = defaultdict(list)
    rank = 0
    for i, s in enumerate(scores_sorted):
        if i == 0 or s != scores_sorted[i - 1]:
            rank = i + 1
        positions[s].append(rank)
    out: dict[float, float] = {}
    for s, ranks in positions.items():
        pcts = [(n - r) / (n - 1) * 100.0 for r in ranks]
        out[s] = sum(pcts) / len(pcts)
    return out


MIN_DISTINCT_MAPPED_MODELS = 10
MAX_UNMAPPED_RATE = 0.05


def benchmark_eligibility(records: list[BenchmarkRecord]) -> dict[str, dict]:
    """基准级综合指数门槛：映射覆盖率 >= 95% 且已映射去重模型 >= 10。

    模型身份：已映射用 canonical_id；未映射用来源原始名（不猜测合并）。
    返回 {benchmark_id: {...统计..., eligible, reason}}（仅含 eligible 的键）。
    """
    stats: dict[str, dict] = {}
    for r in records:
        st = stats.setdefault(r.benchmark_id, {
            "total_records": 0, "distinct_models": set(), "mapped_models": set(),
        })
        st["total_records"] += 1
        identity = r.model_id if not r.model_is_unmapped else (r.raw_model_name or r.model_id)
        st["distinct_models"].add(identity)
        if not r.model_is_unmapped:
            st["mapped_models"].add(r.model_id)

    out: dict[str, dict] = {}
    for bid, st in stats.items():
        distinct = len(st["distinct_models"])
        mapped = len(st["mapped_models"])
        unmapped_rate = round(1 - mapped / distinct, 4) if distinct else 1.0
        eligible = mapped >= MIN_DISTINCT_MAPPED_MODELS and unmapped_rate <= MAX_UNMAPPED_RATE
        info = {
            "total_records": st["total_records"],
            "distinct_models": distinct,
            "mapped_distinct_models": mapped,
            "mapped_rate": round(mapped / distinct, 4) if distinct else 0.0,
            "unmapped_rate": unmapped_rate,
            "eligible": eligible,
            "reason": (
                "通过门槛"
                if eligible else
                (f"已映射模型数 {mapped} < {MIN_DISTINCT_MAPPED_MODELS}"
                 if mapped < MIN_DISTINCT_MAPPED_MODELS else
                 f"未映射比例 {unmapped_rate:.0%} > {MAX_UNMAPPED_RATE:.0%}")
            ),
        }
        if eligible:
            out[bid] = info
    return out


def capability_composite(
    records: list[BenchmarkRecord],
    benchmarks: dict[str, dict],
    eligible_benchmarks: dict[str, dict] | None = None,
) -> tuple[dict | None, list[dict]]:
    """能力级综合指数（带严格门槛）。

    门槛（不满足则返回 None 并在 gate_notes 给出原因）：
    - 只有通过基准级门槛的基准参与（eligible_benchmarks 由调用方计算传入）
    - 只使用 maintainer_verified 且已映射的记录
    - 模型须覆盖 >=2 个合格基准，且覆盖合格基准总数的 >=60%

    返回 (composite | None, gate_notes)。
    """
    gate_notes: list[dict] = []
    if eligible_benchmarks is None:
        eligible_benchmarks = {
            bid: {"reason": "未启用门槛（调用方未传入）"}
            for bid in {r.benchmark_id for r in records}
        }
    eligible_ids = set(eligible_benchmarks)

    for bid in sorted({r.benchmark_id for r in records}):
        meta = eligible_benchmarks.get(bid)
        if meta:
            gate_notes.append({"benchmark_id": bid, "included": True, **meta})
        else:
            gate_notes.append({
                "benchmark_id": bid,
                "included": False,
                "reason": "未通过基准级门槛（映射覆盖率/参评模型数不足）",
            })

    verified_mapped = [
        r for r in records
        if not r.model_is_unmapped
        and r.record_verification_status == "maintainer_verified"
        and r.benchmark_id in eligible_ids
    ]
    by_benchmark: dict[str, list[BenchmarkRecord]] = defaultdict(list)
    for r in verified_mapped:
        by_benchmark[r.benchmark_id].append(r)
    total_eligible = len(by_benchmark)
    if total_eligible == 0:
        gate_notes.append({"reason": "无合格基准可用（全部被门槛排除）"})
        return None, gate_notes

    percentile_maps: dict[str, dict[float, float]] = {}
    benchmark_meta: dict[str, dict] = {}
    for bid, recs in by_benchmark.items():
        hib = recs[0].higher_is_better
        percentile_maps[bid] = _percentile_positions([r.score for r in recs], hib)
        benchmark_meta[bid] = {
            "source_id": recs[0].source_id,
            "source_level": recs[0].source_level,
            "count": len(recs),
        }

    # model -> benchmark -> percentile
    model_pcts: dict[str, dict[str, float]] = defaultdict(dict)
    for bid, recs in by_benchmark.items():
        for r in recs:
            model_pcts[r.model_id][bid] = percentile_maps[bid][r.score]

    # 模型级门槛：>=2 个合格基准且覆盖率 >=60%
    min_benchmarks = 2
    coverage_min = 0.6
    gated = {
        m: pb for m, pb in model_pcts.items()
        if len(pb) >= min_benchmarks and len(pb) / total_eligible >= coverage_min
    }
    if not gated:
        gate_notes.append({
            "reason": (
                f"无模型满足覆盖门槛（需覆盖 >= {min_benchmarks} 个合格基准且 "
                f">= {int(coverage_min * 100)}%）；合格基准共 {total_eligible} 个"
            ),
        })
        return None, gate_notes
    model_pcts = gated

    bench_source = {bid: meta["source_id"] for bid, meta in benchmark_meta.items()}
    bench_weight = {bid: source_weight(meta["source_level"]) for bid, meta in benchmark_meta.items()}

    models_out: list[dict] = []
    for model_id, per_bench in model_pcts.items():
        by_source: dict[str, list[float]] = defaultdict(list)
        for bid, pct in per_bench.items():
            by_source[bench_source[bid]].append(pct)
        source_scores = {sid: sum(pcts) / len(pcts) for sid, pcts in by_source.items()}
        src_weights = {
            sid: max(w for bid2, w in bench_weight.items()
                     if bench_source.get(bid2) == sid and bid2 in per_bench)
            for sid in source_scores
        }
        total_w = sum(src_weights.values())
        if total_w <= 0:
            continue
        index = sum(source_scores[sid] * src_weights[sid] for sid in source_scores) / total_w
        n_sources = len(source_scores)
        if n_sources >= 2:
            confidence = ("high" if all(
                source_weight(_level_of(bid, benchmark_meta)) >= 0.8 for bid in per_bench)
                else "medium")
        else:
            only_level = _level_of(next(iter(per_bench)), benchmark_meta)
            confidence = "medium" if only_level in ("A", "B") else "low"
        models_out.append({
            "model_id": model_id,
            "index": round(index, 1),
            "benchmark_count": len(per_bench),
            "benchmark_total": total_eligible,
            "coverage": round(len(per_bench) / total_eligible, 2),
            "source_count": n_sources,
            "source_ids": sorted(source_scores.keys()),
            "single_source": n_sources == 1,
            "confidence": confidence,
            "per_benchmark": [
                {"benchmark_id": bid, "percentile": round(pct, 1)}
                for bid, pct in sorted(per_bench.items())
            ],
        })

    models_out.sort(key=lambda m: (-m["index"], m["model_id"]))
    _assign_competition_ranks(models_out, key="index")
    for m in models_out:
        m["tie"] = _has_tie(models_out, m, "index")
    composite = {
        "method": "percentile-weighted（本站计算的相对百分位，非绝对能力分，非官方榜单）",
        "benchmark_count": len(by_benchmark),
        "source_count": len({meta["source_id"] for meta in benchmark_meta.values()}),
        "model_gate": {"min_benchmarks": min_benchmarks, "coverage_min": coverage_min},
        "models": models_out,
    }
    return composite, gate_notes


def _level_of(benchmark_id: str, benchmark_meta: dict[str, dict]) -> str:
    return benchmark_meta.get(benchmark_id, {}).get("source_level", "D")


def _assign_competition_ranks(rows: list[dict], key: str) -> None:
    rank = 0
    for i, row in enumerate(rows):
        if i == 0 or row[key] != rows[i - 1][key]:
            rank = i + 1
        row["rank"] = rank


def _has_tie(rows: list[dict], row: dict, key: str) -> bool:
    return sum(1 for r in rows if r[key] == row[key]) > 1


def overall_composite(
    capability_indices: dict[str, dict],
    capability_weights: dict[str, float],
    min_capabilities: int = 4,
    min_benchmarks: int = 5,
    min_sources: int = 2,
) -> dict:
    """综合榜：按能力权重加权能力指数；覆盖率不达标的模型不进入默认综合榜。

    capability_indices: capability_id -> capability_composite() 的返回值
    """
    per_model: dict[str, dict] = defaultdict(lambda: {"caps": {}, "benchmarks": 0, "sources": set()})
    for cap_id, comp in capability_indices.items():
        weight = capability_weights.get(cap_id)
        if weight is None or weight <= 0:
            continue
        for m in comp["models"]:
            entry = per_model[m["model_id"]]
            entry["caps"][cap_id] = m["index"]
            entry["benchmarks"] += m["benchmark_count"]
            entry["sources"].update(m.get("source_ids", []))

    rows = []
    for model_id, entry in per_model.items():
        caps = entry["caps"]
        if len(caps) < min_capabilities or entry["benchmarks"] < min_benchmarks \
                or len(entry["sources"]) < min_sources:
            continue
        total_w = sum(capability_weights[c] for c in caps)
        index = sum(caps[c] * capability_weights[c] for c in caps) / total_w
        rows.append({
            "model_id": model_id,
            "index": round(index, 1),
            "capability_count": len(caps),
            "capability_indices": dict(sorted(caps.items())),
            "benchmark_count": entry["benchmarks"],
            "source_count": len(entry["sources"]),
        })

    rows.sort(key=lambda r: (-r["index"], r["model_id"]))
    _assign_competition_ranks(rows, key="index")
    for r in rows:
        r["tie"] = _has_tie(rows, r, "index")
    return {
        "method": "capability-weighted（本站计算，Agent 系统成绩不参与）",
        "min_capabilities": min_capabilities,
        "min_benchmarks": min_benchmarks,
        "min_sources": min_sources,
        "models": rows,
    }
