"""数据质量校验：结构、范围、重复、方向一致性。

返回 (errors, warnings)。errors 非空 = 核心 Schema 校验失败，
流水线必须拒绝覆盖线上数据（update.py 退出码 2）。
"""
from __future__ import annotations

from collections import defaultdict

from ..schemas.records import BenchmarkRecord

# score_unit -> 合理范围（仅告警，不篡改数据）
RANGE_HINTS = {
    "percent": (0.0, 100.0),
    "index_0_100": (0.0, 100.0),
    "ndcg_0_1": (0.0, 1.0),
    "spearman_0_1": (0.0, 1.0),
    "map_0_1": (0.0, 1.0),
    "absolute_0_1000": (0.0, 1000.0),
    "absolute_0_2800": (0.0, 2800.0),
}


def validate_records(records: list[BenchmarkRecord], benchmarks: dict[str, dict]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for rec in records:
        bench = benchmarks.get(rec.benchmark_id)
        if bench is None:
            errors.append(f"[{rec.source_id}] 未登记的 benchmark_id: {rec.benchmark_id}")
            continue
        if rec.capability != bench["capability"]:
            errors.append(
                f"[{rec.source_id}] {rec.benchmark_id} capability 不一致: "
                f"记录={rec.capability} 注册表={bench['capability']}"
            )
        if rec.higher_is_better != bench.get("higher_is_better", True):
            errors.append(f"[{rec.source_id}] {rec.benchmark_id} higher_is_better 与注册表不一致")
        if rec.score_unit != bench.get("score_unit"):
            warnings.append(f"[{rec.source_id}] {rec.benchmark_id} score_unit={rec.score_unit} 与注册表不同")
        rng = RANGE_HINTS.get(rec.score_unit or bench.get("score_unit"))
        if rng and not (rng[0] - 1e-9 <= rec.score <= rng[1] + 1e-9):
            warnings.append(
                f"[{rec.source_id}] {rec.benchmark_id} {rec.model_id} 分数 {rec.score} 超出 {rec.score_unit} 常见范围"
            )

    # 重复键检查：同一键出现多条记录时告警（保留全部，由官方原始榜并列展示）
    key_counts: dict[tuple, int] = defaultdict(int)
    for rec in records:
        key_counts[rec.dedupe_key()] += 1
    for key, count in key_counts.items():
        if count > 1:
            warnings.append(f"重复记录 {count} 条: {key}")

    return errors, warnings


def dedupe_conflicting(records: list[BenchmarkRecord]) -> list[BenchmarkRecord]:
    """同一 dedupe_key 且分数相同的重复记录只保留一条；分数冲突则全部保留并告警。"""
    seen: dict[tuple, BenchmarkRecord] = {}
    out: list[BenchmarkRecord] = []
    for rec in records:
        prev = seen.get(rec.dedupe_key())
        if prev is None:
            seen[rec.dedupe_key()] = rec
            out.append(rec)
        elif prev.score == rec.score:
            continue
        else:
            out.append(rec)
    return out
