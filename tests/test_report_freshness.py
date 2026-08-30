"""报告层的 CURRENT 状态必须 fail closed，避免旧记录在前端默认榜泄漏。"""

from pipeline.reports.generate import FRESHNESS_REF, _dedupe_directory_releases, _record_row
from pipeline.schemas.records import BenchmarkRecord


def _record(*, model_id: str = "test-model", unmapped: bool = False) -> BenchmarkRecord:
    return BenchmarkRecord(
        source_id="source",
        source_name="Source",
        source_level="A",
        source_url="https://example.com",
        benchmark_id="bench",
        benchmark_name="Bench",
        capability="swe",
        model_id=model_id,
        raw_model_name=model_id,
        model_is_unmapped=unmapped,
        evaluation_target_type="model_plus_agent",
        score=80,
        score_unit="percent",
    )


def test_record_row_always_emits_fail_closed_current_status():
    original = FRESHNESS_REF.get("map")
    try:
        FRESHNESS_REF["map"] = {}
        missing = _record_row(_record())
        assert missing["is_current"] is False
        assert "freshness_bucket" in missing

        FRESHNESS_REF["map"] = {
            "test-model": {"is_current": True, "freshness_bucket": "ACTIVE"},
            "unmapped--source--old": {"is_current": True, "freshness_bucket": "ACTIVE"},
        }
        current = _record_row(_record())
        unmapped = _record_row(_record(model_id="unmapped--source--old", unmapped=True))
        assert current["is_current"] is True
        assert current["freshness_bucket"] == "ACTIVE"
        assert unmapped["is_current"] is False
        assert unmapped["freshness_bucket"] is None
    finally:
        FRESHNESS_REF["map"] = original


def test_directory_releases_merge_provider_channels_and_drop_integrations():
    rows = [
        {"model_id": "tencent/hy4-preview", "name": "Tencent Hy4 Preview", "provider_id": "openrouter", "release_date": "2026-08-28"},
        {"model_id": "hy4-preview", "name": "Hy4 preview", "provider_id": "tencent-tokenhub", "release_date": "2026-08-28", "context_window": 1_000_000},
        {"model_id": "Kloker", "name": "Kloker", "provider_id": "klokintegration", "release_date": "2026-08-29"},
    ]

    deduped = _dedupe_directory_releases(rows)

    assert len(deduped) == 1
    assert deduped[0]["channel_count"] == 2
    assert deduped[0]["channels"] == ["openrouter", "tencent-tokenhub"]
