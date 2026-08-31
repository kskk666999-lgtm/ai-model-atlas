"""数据校验与 LKG 层面测试：分数范围、重复、Agent 混排、Schema 失败拒绝覆盖。"""
from __future__ import annotations

import pytest

from pipeline.update import _composite_candidate_records, _has_recent_evidence
from pipeline.validation.quality import dedupe_conflicting, validate_records


def test_score_out_of_range_is_warning_not_error(sample_source, normalizer, benchmarks):
    from tests.adapters.test_base import build

    adapter = build(None, None, sample_source, normalizer, benchmarks, None,
                    parse_fn=lambda b, a: [])
    rec = adapter.make_record("bench-x", "test-model-a", 150.0)  # percent 超范围
    errors, warnings = validate_records([rec], benchmarks)
    assert errors == []
    assert any("超出" in w for w in warnings)


def test_unknown_benchmark_is_error(sample_source, normalizer, benchmarks):
    from tests.adapters.test_base import build

    adapter = build(None, None, sample_source, normalizer, benchmarks, None, parse_fn=lambda b, a: [])
    rec = adapter.make_record("bench-x", "test-model-a", 50.0)
    rec.benchmark_id = "nonexistent-bench"
    errors, _ = validate_records([rec], benchmarks)
    assert errors


def test_livebench_version_cannot_masquerade_as_evaluation_date(
    sample_source, normalizer, benchmarks,
):
    from tests.adapters.test_base import build

    adapter = build(None, None, sample_source, normalizer, benchmarks, None,
                    parse_fn=lambda b, a: [])
    rec = adapter.make_record(
        "bench-x", "test-model-a", 50.0,
        benchmark_version="2026-06-25",
        evaluation_date="2026-06-25",
        upstream_updated_at="2026-08-29T01:34:09Z",
    )
    rec.source_id = "livebench"
    errors, _ = validate_records([rec], benchmarks)
    assert any("不得把基准版本" in error for error in errors)


def test_source_registry_can_exclude_raw_boards_from_composite(
    sample_source, normalizer, benchmarks,
):
    from types import SimpleNamespace

    from tests.adapters.test_base import build

    adapter = build(None, None, sample_source, normalizer, benchmarks, None,
                    parse_fn=lambda b, a: [])
    included = adapter.make_record("bench-x", "test-model-a", 50.0)
    included.source_id = "included"
    raw_only = adapter.make_record("bench-y", "test-model-b", 60.0)
    raw_only.source_id = "raw-only"
    sources = [
        SimpleNamespace(source_id="included", included_in_composite=True),
        SimpleNamespace(source_id="raw-only", included_in_composite=False),
    ]

    selected = _composite_candidate_records([included, raw_only], sources)

    assert [record.benchmark_id for record in selected] == ["bench-x"]


def test_current_board_fallback_requires_recent_real_evidence_date(
    sample_source, normalizer, benchmarks,
):
    from datetime import date

    from tests.adapters.test_base import build

    adapter = build(None, None, sample_source, normalizer, benchmarks, None,
                    parse_fn=lambda b, a: [])
    recent = adapter.make_record(
        "bench-x", "test-model-a", 50.0,
        benchmark_version="2026-07",
        evaluation_date=None,
        upstream_updated_at="2026-08-18T05:06:25Z",
    )
    stale = recent.model_copy(update={"upstream_updated_at": "2025-04-17T00:00:00Z"})
    version_only = recent.model_copy(update={"upstream_updated_at": None})

    today = date(2026, 8, 31)
    assert _has_recent_evidence(recent, today)
    assert not _has_recent_evidence(stale, today)
    assert not _has_recent_evidence(version_only, today)


def test_duplicate_same_score_deduped(sample_source, normalizer, benchmarks):
    from tests.adapters.test_base import build

    adapter = build(None, None, sample_source, normalizer, benchmarks, None, parse_fn=lambda b, a: [])
    r1 = adapter.make_record("bench-x", "test-model-a", 50.0)
    r2 = adapter.make_record("bench-x", "test-model-a", 50.0)
    out = dedupe_conflicting([r1, r2])
    assert len(out) == 1

    r3 = adapter.make_record("bench-x", "test-model-a", 99.0)
    out2 = dedupe_conflicting([r1, r3])
    assert len(out2) == 2  # 分数冲突全部保留


def test_agent_records_tagged_so_boards_can_separate(sample_source, normalizer, benchmarks):
    from tests.adapters.test_base import build

    adapter = build(None, None, sample_source, normalizer, benchmarks, None, parse_fn=lambda b, a: [])
    r = adapter.make_record("bench-x", "test-model-a", 50.0,
                            evaluation_target_type="model_plus_agent", agent_scaffold="MiniAgent")
    assert r.evaluation_target_type == "model_plus_agent"
    assert r.agent_scaffold == "MiniAgent"


def test_core_schema_rejects_invalid_record():
    """score 必须是有限数值——pydantic 校验失败即核心 Schema 失败。"""
    from pydantic import ValidationError

    from pipeline.schemas.records import BenchmarkRecord

    base = dict(
        source_id="s", source_name="s", source_level="A", source_url="u",
        benchmark_id="b", benchmark_name="b", capability="c",
        model_id="m", score_unit="percent",
    )
    with pytest.raises(ValidationError):
        BenchmarkRecord(**base, score=float("nan"))
    with pytest.raises(ValidationError):
        BenchmarkRecord(**base, score=float("inf"))


def test_lkg_file_roundtrip(tmp_path, monkeypatch, sample_source, normalizer, benchmarks):
    from tests.adapters.test_base import EchoAdapter

    monkeypatch.setattr("pipeline.adapters.base.RECORDS_LKG_DIR", tmp_path / "lkg")
    adapter = EchoAdapter(sample_source, benchmarks, normalizer, None, parse_fn=lambda b, a: [])
    recs = [adapter.make_record("bench-x", "test-model-a", 88.0, evaluation_date="2026-01-01")]
    adapter._save_lkg(recs)
    loaded = adapter._load_lkg()
    assert loaded[0].model_id == "test-model-a"
    assert loaded[0].score == 88.0
    assert loaded[0].evaluation_date == "2026-01-01"


def test_history_retention_and_rank_changes(tmp_path):
    from datetime import date, timedelta

    from pipeline.history.store import HistoryStore

    store = HistoryStore(snapshots_dir=tmp_path)
    today = date(2026, 8, 30)
    # 100 天前 / 40 天前 / 今天 三份快照（推理榜：m1 从第 3 升到第 1）
    for days_ago, rank in ((100, 3), (40, 2), (0, 1)):
        d = today - timedelta(days=days_ago)
        store.append_snapshot(d, {"reasoning": {"m1": {"index": 50.0, "rank": rank}}})

    store.apply_retention(today)
    snaps = store.load_snapshots()
    assert len(snaps) == 3  # 全部保留（周/月聚合文件仍存在，只是文件名变化）
    changes = store.rank_changes(today)
    # d7 基线：40 天前 rank=2 -> 变化 +1
    assert changes["m1"]["reasoning"]["d7"] == 1.0
