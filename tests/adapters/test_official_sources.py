"""官方数据源适配器解析测试（固定 Fixture，不发真实请求）。"""
from __future__ import annotations

import json

import pytest

from pipeline.adapters.livebench import LiveBenchAdapter
from pipeline.adapters.mteb import CONTENTS_API, MODEL_DIRS, MTEBAdapter
from pipeline.adapters.mteb import RAW_BASE as MTEB_RAW
from pipeline.adapters.swebench import RAW_BASE as SWB_RAW
from pipeline.adapters.swebench import TREE_API as SWB_TREE
from pipeline.adapters.swebench import SWEBenchAdapter
from pipeline.paths import REGISTRY_BENCHMARKS
from pipeline.schemas.records import load_yaml


@pytest.fixture
def real_benchmarks() -> dict:
    data = load_yaml(REGISTRY_BENCHMARKS)
    return {b["benchmark_id"]: b for b in (data.get("benchmarks") or [])}


def test_livebench_table_csv_parsing(sample_source, normalizer, real_benchmarks, mock_http, monkeypatch, tmp_path):
    monkeypatch.setattr("pipeline.normalization.registry.UNMAPPED_FILE", tmp_path / "unmapped.json")
    categories = {"Reasoning": ["sudoku", "typos2"], "IF": ["paraphrase"]}
    table = (
        "model,sudoku,typos2,paraphrase\n"
        "test-model-a,90.0,80.0,70.0\n"
        "test-model-b,50.0,60.0,\n"
        "unknown-model-x,40.0,50.0,60.0\n"
    )
    mock_http.set("https://livebench.ai/categories_2026_06_25.json", categories)
    mock_http.set("https://livebench.ai/table_2026_06_25.csv", table.encode("utf-8"))
    mock_http.set(
        "https://livebench.ai/cost_2026_06_25.csv",
        b"model,input_price_per_million,output_price_per_million\ntest-model-a,1.5,6.0\n",
    )

    ad = LiveBenchAdapter(sample_source, real_benchmarks, normalizer, mock_http)
    monkeypatch.setattr(ad, "_discover_release", lambda: "2026-06-25")
    records = ad.fetch_records()

    by_bench: dict[str, list] = {}
    for r in records:
        by_bench.setdefault(r.benchmark_id, []).append(r)

    reasoning = by_bench["livebench-reasoning"]
    a = next(r for r in reasoning if r.raw_model_name == "test-model-a")
    assert a.score == 85.0  # (90+80)/2 官方类别平均
    assert a.evaluation_date == "2026-06-25"
    assert len(by_bench["livebench-instruction-following"]) == 2  # b 的 paraphrase 缺失不产出
    price = by_bench["livebench-price-input"][0]
    assert price.score == 1.5
    assert price.higher_is_better is False
    assert any(r.model_is_unmapped for r in reasoning)


SWB_BASH = "evaluation/bash-only/20250726_mini-v1.0.0_gemini-2.5-pro/metadata.yaml"
SWB_VER = "evaluation/verified/20251127_openhands_claude-opus-4-5/metadata.yaml"
SWB_VER2 = "evaluation/verified/20251211_mini-v1.17.2_gpt-5.2-2025-12-11-high/metadata.yaml"


def _register_swebench(mock_http, include_verified_true: bool = True):
    paths = [{"path": SWB_BASH}, {"path": SWB_VER}]
    if include_verified_true:
        paths.append({"path": SWB_VER2})
        paths.append({"path": SWB_VER2.replace("metadata.yaml", "results/results.json")})
    mock_http.set(SWB_TREE, {"tree": paths, "truncated": False})
    mock_http.set(SWB_RAW + SWB_BASH, (
        b"info:\n"
        b"  resolved: 53.6\n"
        b"  cost: 144.18\n"
        b"tags:\n"
        b"  checked: true\n"
        b"  model: [gemini-2.5-pro]\n"
        b"  agent: mini-SWE-agent\n"
        b"  system: {attempts: 1}\n"
    ))
    mock_http.set(SWB_RAW + SWB_VER, (
        b"name: OpenHands + Claude Opus 4.5\n"
        b"verified: false\n"
        b"tags:\n"
        b"  agent: OpenHands\n"
        b"  model_display: Claude Opus 4.5\n"
    ))
    mock_http.set(SWB_RAW + SWB_VER2, (
        b"name: mini-swe-agent (high) + GPT 5.2\n"
        b"verified: true\n"
        b"tags:\n"
        b"  agent: mini-SWE-agent\n"
        b"  model_display: GPT 5.2 (high)\n"
    ))
    mock_http.set(
        (SWB_RAW + SWB_VER2).replace("metadata.yaml", "results/results.json"),
        json.dumps({"resolved": [f"i{i}" for i in range(315)]}).encode(),
    )


def test_swebench_metadata_yaml_parsing(sample_source, normalizer, real_benchmarks, mock_http):
    _register_swebench(mock_http, include_verified_true=False)
    ad = SWEBenchAdapter(sample_source, real_benchmarks, normalizer, mock_http)
    records = ad.fetch_records()

    by_bench: dict[str, list] = {}
    for r in records:
        by_bench.setdefault(r.benchmark_id, []).append(r)

    assert len(by_bench["swebench-bash-only"]) == 1
    r = by_bench["swebench-bash-only"][0]
    assert r.score == 53.6
    assert r.evaluation_target_type == "model_plus_agent"
    assert r.agent_scaffold == "mini-SWE-agent (attempts=1)"
    # verified: false 的运行不上榜
    assert "swebench-verified" not in by_bench


def test_swebench_verified_results_json(sample_source, normalizer, real_benchmarks, mock_http):
    _register_swebench(mock_http)
    ad = SWEBenchAdapter(sample_source, real_benchmarks, normalizer, mock_http)
    records = [r for r in ad.fetch_records() if r.benchmark_id == "swebench-verified"]
    assert len(records) == 1
    r = records[0]
    assert abs(r.score - 63.0) < 0.01  # 315/500*100
    assert r.evaluation_date == "2025-12-11"


def test_mteb_task_json_parsing(sample_source, normalizer, real_benchmarks, mock_http):
    revisions = [{"name": "5617a9f61b028005a4858fdac845db406aefb181", "type": "dir"}]
    for mid, mdir in MODEL_DIRS.items():
        mock_http.set(CONTENTS_API.format(model_dir=mdir), revisions if mid == "bge-m3" else [])
    revision = "5617a9f61b028005a4858fdac845db406aefb181"
    mock_http.set(
        MTEB_RAW.format(model_dir="BAAI__bge-m3", revision=revision, task="NFCorpus"),
        json.dumps({"task_name": "NFCorpus", "scores": {"test": [{"main_score": 0.5612}]}}).encode(),
    )
    # 其余任务 URL 未注册 -> 抛异常 -> 单任务跳过

    ad = MTEBAdapter(sample_source, real_benchmarks, normalizer, mock_http)
    records = ad.fetch_records()
    nf = [r for r in records if r.benchmark_id == "mteb-nfcorpus"]
    assert len(nf) == 1
    assert abs(nf[0].score - 0.5612) < 1e-6
    assert nf[0].evaluation_target_type == "embedding_model"
    assert nf[0].source_commit_sha == revision
