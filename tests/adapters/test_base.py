"""适配器公共行为测试：正常解析 / 空数据 / 结构变化 / 网络错误 / LKG 回退 / 别名。"""
from __future__ import annotations

import httpx

from pipeline.adapters.base import BaseAdapter


class EchoAdapter(BaseAdapter):
    """从 MockHttpClient 读取原始数据，用注入的解析函数生成记录。"""

    source_id = "testsource"

    def __init__(self, *a, parse_fn=None, **kw):
        super().__init__(*a, **kw)
        self.parse_fn = parse_fn

    def fetch_records(self):
        body = self.http.get("https://example.com/data.json")
        return self.parse_fn(body, self)


def build(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http, parse_fn):
    if monkeypatch is not None and tmp_path is not None:
        monkeypatch.setattr("pipeline.adapters.base.RECORDS_LKG_DIR", tmp_path / "lkg")
    return EchoAdapter(sample_source, benchmarks, normalizer, mock_http, parse_fn=parse_fn)


def ok_parse(body, adapter):
    return [
        adapter.make_record("bench-x", "test-model-a", 88.0),
        adapter.make_record("bench-x", "TestCorp/Test-Model-A", 91.0),  # 别名 -> 同一 canonical
    ]


def test_normal_parse_alias_and_lkg_write(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http):
    mock_http.set("https://example.com/data.json", b"[]")
    adapter = build(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http, ok_parse)
    records = adapter.fetch_records()
    assert records[0].model_id == "test-model-a"
    assert records[1].model_id == "test-model-a"  # 别名归一

    result = adapter.run()
    assert result.status == "ok"
    # 两条记录归一后键相同（dedupe 在流水线层），LKG 仍保存全部
    assert len(adapter._load_lkg()) == 2


def test_empty_data_falls_back_to_lkg(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http):
    mock_http.set("https://example.com/data.json", b"[]")
    adapter = build(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http,
                    parse_fn=lambda body, ad: [])
    good = adapter.make_record("bench-x", "test-model-a", 88.0)
    adapter._save_lkg([good])

    result = adapter.run()
    assert result.status == "degraded"
    assert result.records[0].model_id == "test-model-a"
    assert "0 条" in result.error_message


def test_http_500_falls_back_to_lkg(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http):
    mock_http.set("https://example.com/data.json", httpx.HTTPStatusError("500", request=None, response=httpx.Response(500)))
    adapter = build(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http,
                    parse_fn=lambda body, ad: [])
    good = adapter.make_record("bench-x", "test-model-a", 77.0)
    adapter._save_lkg([good])
    mock_http.set("https://example.com/data.json",
                  httpx.HTTPStatusError("500", request=None, response=httpx.Response(500)))

    result = adapter.run()
    assert result.status == "degraded"


def test_429_and_timeout_fail_isolated(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http):
    adapter = build(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http,
                    parse_fn=lambda body, ad: [])
    mock_http.set("https://example.com/data.json",
                  httpx.HTTPStatusError("429", request=None, response=httpx.Response(429)))
    result = adapter.run()
    assert result.status == "failed"
    assert result.records == []

    mock_http.set("https://example.com/data.json", httpx.ReadTimeout("timeout"))
    assert adapter.run().status == "failed"


def test_schema_change_reported_as_parse_error(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http):
    def broken(body, adapter):
        raise KeyError("unexpected_field")

    adapter = build(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http, broken)
    result = adapter.run()
    assert result.status == "failed"
    assert "解析错误" in result.error_message


def test_unknown_model_not_dropped_or_merged(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http):
    monkeypatch.setattr("pipeline.normalization.registry.UNMAPPED_FILE", tmp_path / "unmapped.json")
    adapter = build(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http, ok_parse)
    r = adapter.make_record("bench-x", "Completely-Unknown-Model", 50.0)
    assert r.model_is_unmapped
    assert r.model_id.startswith("unmapped--testsource--")
    assert r.raw_model_name == "Completely-Unknown-Model"
    normalizer.save_unmapped_report()
    import json

    report = json.loads((tmp_path / "unmapped.json").read_text(encoding="utf-8"))
    assert report["count"] == 1


def test_higher_is_better_false_ordering(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http):
    from pipeline.ranking.composite import benchmark_ranking

    adapter = build(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http,
                    parse_fn=lambda body, ad: [])
    recs = [
        adapter.make_record("bench-low", "test-model-a", 1.2),   # 更低更好
        adapter.make_record("bench-low", "test-model-b", 0.9),
    ]
    rows = benchmark_ranking(recs)
    assert rows[0]["record"].model_id == "test-model-b"


def test_missing_optional_fields_are_none(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http):
    adapter = build(tmp_path, monkeypatch, sample_source, normalizer, benchmarks, mock_http, ok_parse)
    rec = adapter.make_record("bench-x", "test-model-a", 55.0)
    assert rec.evaluation_date is None
    assert rec.benchmark_version is None
    assert rec.sample_size is None
    assert rec.agent_scaffold is None
