"""排名计算测试：百分位、并列、缺失不计 0、Agent 不混排、综合指数。"""
from __future__ import annotations

import pytest

from pipeline.ranking.composite import (
    AGENT_TYPES,
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

    def _make(benchmark_id, model, score, unmapped=False, target="base_model", agent=None):
        r = dummy.make_record(benchmark_id, model, score)
        r.model_is_unmapped = unmapped
        r.evaluation_target_type = target
        r.agent_scaffold = agent
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


def test_unmapped_excluded_from_composite(make_rec):
    recs = [
        make_rec("bench-x", "test-model-a", 90.0),
        make_rec("bench-x", "Unknown-Model", 99.0, unmapped=True),
    ]
    comp = capability_composite(recs, {"bench-x": {"capability": "reasoning"}})
    assert comp is not None
    ids = [m["model_id"] for m in comp["models"]]
    assert "test-model-a" in ids
    assert all(not i.startswith("unmapped--") for i in ids)
    # 百分位池 = 已映射模型；单模型基准的百分位为中位 50（未映射 99 分不影响）
    assert comp["models"][0]["index"] == 50.0


def test_agent_records_excluded_from_base_composite(make_rec):
    recs = [
        make_rec("bench-x", "test-model-a", 90.0, target="model_plus_agent", agent="MiniAgent"),
        make_rec("bench-x", "test-model-b", 50.0, target="base_model"),
    ]
    base_recs = [r for r in recs if r.evaluation_target_type not in AGENT_TYPES]
    comp = capability_composite(base_recs, {"bench-x": {"capability": "reasoning"}})
    ids = [m["model_id"] for m in comp["models"]]
    assert "test-model-a" not in ids
    assert "test-model-b" in ids


def test_composite_percentile_not_raw_average(make_rec):
    """两个基准原始分数量级不同，百分位后加权应该一致。"""
    recs = []
    # bench-x: 0~100 分
    for i, (m, s) in enumerate([("test-model-a", 90.0), ("test-model-b", 50.0)]):
        recs.append(make_rec("bench-x", m, s))
    # bench-low: 0~2 秒（数值越小越好）
    for m, s in [("test-model-a", 0.5), ("test-model-b", 1.5)]:
        recs.append(make_rec("bench-low", m, s))
    comp = capability_composite(recs, {"bench-x": {"capability": "reasoning"}})
    a = next(m for m in comp["models"] if m["model_id"] == "test-model-a")
    b = next(m for m in comp["models"] if m["model_id"] == "test-model-b")
    assert a["index"] > b["index"]
    assert a["index"] == 100.0
    assert b["index"] == 0.0


def test_overall_requires_multi_source_coverage(make_rec):
    caps = {
        "reasoning": {"models": [{"model_id": "test-model-a", "index": 90.0, "rank": 1,
                                  "benchmark_count": 3, "source_ids": ["s1", "s2"]}]},
        "math": {"models": [{"model_id": "test-model-a", "index": 80.0, "rank": 1,
                             "benchmark_count": 2, "source_ids": ["s1"]}]},
    }
    weights = {"reasoning": 0.6, "math": 0.4}
    overall = overall_composite(caps, weights, min_capabilities=4, min_benchmarks=5, min_sources=2)
    # 只覆盖 2 个能力、3 个基准、1 个真实多源能力 -> 不达标
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
    # 加权：(90*.6 + 80*.4 + 70*.2 + 60*.1) / (0.6+0.4+0.2+0.1)
    assert abs(row["index"] - (90 * 0.6 + 80 * 0.4 + 70 * 0.2 + 60 * 0.1) / 1.3) < 0.2
