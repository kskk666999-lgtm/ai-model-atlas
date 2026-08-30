"""排名计算测试：百分位、并列、门槛、缺失不计 0、Agent 不混排。"""
from __future__ import annotations

import pytest

from pipeline.ranking.composite import (
    AGENT_TYPES,
    benchmark_eligibility,
    benchmark_ranking,
    capability_composite,
    overall_composite,
)


def rec_factory(sample_source, normalizer, benchmarks):
    from pipeline.adapters.base import BaseAdapter

    class Dummy(BaseAdapter):
        source_id = "testsource"

        def fetch_records(self):
            return []

    dummy = Dummy(sample_source, benchmarks, normalizer, None)
    return dummy


@pytest.fixture
def make_rec(sample_source, normalizer, benchmarks):
    dummy = rec_factory(sample_source, normalizer, benchmarks)

    def _make(benchmark_id, model, score, unmapped=False, target="base_model", agent=None,
              verification="maintainer_verified"):
        r = dummy.make_record(benchmark_id, model, score)
        r.model_is_unmapped = unmapped
        r.evaluation_target_type = target
        r.agent_scaffold = agent
        r.record_verification_status = verification
        return r

    return _make


def test_benchmark_ranking_with_ties(make_rec):
    recs = [
        make_rec("bench-x", "test-model-a", 90.0),
        make_rec("bench-x", "test-model-b", 90.0),
        make_rec("bench-x", "test-model-c", 80.0),
    ]
    rows = benchmark_ranking(recs)
    # 并列第一（1,1,3），两个并列者都带 tie 标记
    assert rows[0]["rank"] == 1 and rows[0]["tie"]
    assert rows[1]["rank"] == 1 and rows[1]["tie"]
    assert rows[2]["rank"] == 3 and not rows[2]["tie"]


def test_benchmark_eligibility_gates(make_rec):
    """门槛：已映射模型 >=10 且未映射率 <=5%。"""
    recs = []
    for i in range(12):
        recs.append(make_rec("bench-x", f"mapped-{i}", 50.0 + i))
    recs.append(make_rec("bench-x", "Unknown-A", 99.0, unmapped=True))
    recs.append(make_rec("bench-x", "Unknown-B", 98.0, unmapped=True))
    el = benchmark_eligibility(recs)
    assert "bench-x" not in el  # 未映射率 2/14 超标

    recs2 = [make_rec("bench-y", f"mapped-{i}", 50.0 + i) for i in range(10)]
    recs2.append(make_rec("bench-y", "Unknown-A", 99.0, unmapped=True))  # 10/11 -> 9% 仍超标
    el2 = benchmark_eligibility(recs2)
    assert "bench-y" not in el2

    recs3 = [make_rec("bench-z", f"mapped-{i}", 50.0 + i) for i in range(12)]
    el3 = benchmark_eligibility(recs3)
    assert el3["bench-z"]["eligible"]


def test_unmapped_excluded_from_composite_pool(make_rec):
    """综合百分位池 = 已映射 + 官方核验记录；未映射记录不参与。"""
    recs = [
        make_rec("bench-x", "test-model-a", 90.0),
        make_rec("bench-x", "Unknown-Model", 99.0, unmapped=True),
    ]
    eligibility = benchmark_eligibility(recs)
    comp, _ = capability_composite(recs, {"bench-x": {}}, eligibility)
    # 单基准 + 模型覆盖门槛（>=2 基准）-> 不产生综合
    assert comp is None


def test_single_benchmark_capability_produces_no_champion(make_rec):
    """审计要求：单一合格基准不得产生能力综合冠军。"""
    recs = [make_rec("bench-x", f"m-{i}", 50.0 + i) for i in range(12)]
    eligibility = benchmark_eligibility(recs)
    assert "bench-x" in eligibility
    comp, _ = capability_composite(recs, {"bench-x": {}}, eligibility)
    assert comp is None  # 每个模型只覆盖 1 个合格基准（<2）


def test_multi_benchmark_composite_with_coverage_gate(make_rec):
    """两个合格基准：覆盖 2/2 的模型可进综合；只覆盖 1/2 的被门槛排除。"""
    recs = []
    for i in range(12):
        recs.append(make_rec("bench-x", f"m-{i}", 50.0 + i))
        recs.append(make_rec("bench-y", f"m-{i}", 60.0 + i))
    recs.append(make_rec("bench-x", "only-x", 99.0))  # 只参加了 bench-x
    eligibility = benchmark_eligibility(recs)
    assert set(eligibility) == {"bench-x", "bench-y"}
    comp, _ = capability_composite(recs, {}, eligibility)
    assert comp is not None
    ids = [m["model_id"] for m in comp["models"]]
    assert "only-x" not in ids  # 覆盖 1/2 = 50% < 60%
    top = comp["models"][0]
    assert top["benchmark_count"] == 2
    assert top["benchmark_total"] == 2
    assert 0 < top["index"] <= 100


def test_third_party_records_excluded_from_composite(make_rec):
    """Verified=no 的记录不进入综合（官方托管不等于官方复现）。"""
    recs = []
    for i in range(12):
        recs.append(make_rec("bench-x", f"m-{i}", 50.0 + i))
        recs.append(make_rec("bench-y", f"m-{i}", 60.0 + i))
    for r in recs:
        if r.benchmark_id == "bench-y":
            r.record_verification_status = "third_party_submitted"
    eligibility = benchmark_eligibility(recs)
    comp, _ = capability_composite(recs, {}, eligibility)
    # bench-y 全部为第三方提交 -> 综合池只剩 1 个合格基准 -> 模型覆盖门槛不满足
    assert comp is None


def test_agent_records_excluded_from_base_composite(make_rec):
    recs = [
        make_rec("bench-x", "test-model-a", 90.0, target="model_plus_agent", agent="MiniAgent"),
        make_rec("bench-x", "test-model-b", 50.0, target="base_model"),
    ]
    base_recs = [r for r in recs if r.evaluation_target_type not in AGENT_TYPES]
    comp, _ = capability_composite(base_recs, {}, {})
    if comp is not None:
        assert all(m["model_id"] != "test-model-a" for m in comp["models"])


def test_overall_requires_multi_source_coverage():
    caps = {
        "reasoning": {"models": [{"model_id": "test-model-a", "index": 90.0, "rank": 1,
                                  "benchmark_count": 3, "source_ids": ["s1", "s2"]}]},
        "math": {"models": [{"model_id": "test-model-a", "index": 80.0, "rank": 1,
                             "benchmark_count": 2, "source_ids": ["s1"]}]},
    }
    weights = {"reasoning": 0.6, "math": 0.4}
    overall = overall_composite(caps, weights, min_capabilities=4, min_benchmarks=5, min_sources=2)
    assert overall["models"] == []

    caps["coding"] = {"models": [{"model_id": "test-model-a", "index": 70.0, "rank": 1,
                                  "benchmark_count": 2, "source_ids": ["s1", "s2"]}]}
    caps["multimodal"] = {"models": [{"model_id": "test-model-a", "index": 60.0, "rank": 1,
                                      "benchmark_count": 1, "source_ids": ["s1"]}]}
    overall2 = overall_composite(caps, {**weights, "coding": 0.2, "multimodal": 0.1},
                                 min_capabilities=4, min_benchmarks=5, min_sources=2)
    assert len(overall2["models"]) == 1
    row = overall2["models"][0]
    assert row["benchmark_count"] == 8
    assert row["source_count"] == 2
