"""官方数据源适配器解析测试（固定 Fixture，不发真实请求）。"""
from __future__ import annotations

import io
import json

import pandas as pd
import pytest

from pipeline.adapters.bfcl import CSV_URL as BFCL_CSV
from pipeline.adapters.bfcl import BFCLAdapter
from pipeline.adapters.kernelbench import COMMITS_URL as KB_COMMITS
from pipeline.adapters.kernelbench import DATA_URL as KB_DATA
from pipeline.adapters.kernelbench import KernelBenchAdapter
from pipeline.adapters.livebench import LiveBenchAdapter
from pipeline.adapters.mteb import CONTENTS_API, MODEL_DIRS, MTEBAdapter
from pipeline.adapters.mteb import RAW_BASE as MTEB_RAW
from pipeline.adapters.superclue import SuperCLUEAdapter
from pipeline.adapters.superclue_longcontext import SuperCLUELongContextAdapter
from pipeline.adapters.superclue_vlm import SuperCLUEVLMAdapter
from pipeline.adapters.swebench import RAW_BASE as SWB_RAW
from pipeline.adapters.swebench import TREE_API as SWB_TREE
from pipeline.adapters.swebench import SWEBenchAdapter
from pipeline.adapters.terminalbench import LEADERBOARD_URL as TB_URL
from pipeline.adapters.terminalbench import TerminalBenchAdapter
from pipeline.paths import REGISTRY_BENCHMARKS
from pipeline.schemas.records import SourceConfig, load_yaml


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
    mock_http.set_metadata(
        "https://livebench.ai/table_2026_06_25.csv",
        {"last_modified": "Sat, 29 Aug 2026 01:34:09 GMT"},
    )
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
    assert a.evaluation_date is None
    assert a.benchmark_version == "2026-06-25"
    assert a.upstream_updated_at == "2026-08-29T01:34:09Z"
    assert len(by_bench["livebench-instruction-following"]) == 2  # b 的 paraphrase 缺失不产出
    price = by_bench["livebench-price-input"][0]
    assert price.score == 1.5
    assert price.higher_is_better is False
    assert any(r.model_is_unmapped for r in reasoning)


def test_superclue_official_xlsx_keeps_month_as_version_not_fake_day(
    normalizer, real_benchmarks, mock_http, monkeypatch, tmp_path,
):
    monkeypatch.setattr("pipeline.normalization.registry.UNMAPPED_FILE", tmp_path / "unmapped.json")
    frame = pd.DataFrame([{
        "排名": "1",
        "模型名称": "test-model-a(max)",
        "机构": "TestCorp",
        "开/闭源": "闭源",
        "总分": 71.48,
        "数学推理": 77.193,
        "幻觉控制": 86.0796,
        "科学推理": 71.93,
        "精确指令遵循": 43.8095,
        "智能体编程": 68.42,
        "智能体任务规划": 90.9386,
        "属地": "海外",
        "使用方式": "API",
        "是否推理": "是",
        "发布日期": "2026.8.6",
    }])
    stream = io.BytesIO()
    with pd.ExcelWriter(stream, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="总排行榜", index=False)

    url = "https://www.superclueai.com/data/generalboard/2026年7月.xlsx"
    mock_http.set(url, stream.getvalue())
    mock_http.set_metadata(url, {"last_modified": "Tue, 18 Aug 2026 05:06:25 GMT"})
    source = SourceConfig(
        source_id="superclue", source_name="SuperCLUE", source_level="B",
        homepage_url="https://www.superclueai.com", attribution="test",
    )
    adapter = SuperCLUEAdapter(source, real_benchmarks, normalizer, mock_http)
    monkeypatch.setattr(adapter, "_discover_release", lambda: "2026年7月")
    records = adapter.fetch_records()

    assert len(records) == 7
    general = next(r for r in records if r.benchmark_id == "superclue-general")
    assert general.model_id == "test-model-a"
    assert general.model_variant == "max"
    assert general.reasoning_effort == "max"
    assert general.benchmark_version == "2026-07"
    assert general.evaluation_date is None
    assert general.upstream_updated_at == "2026-08-18T05:06:25Z"
    assert "不替代模型发布日期或评测运行日" in (general.notes or "")


def test_kernelbench_reaudits_reward_hack_and_uses_fixed_suite_denominator(
    normalizer, real_benchmarks, mock_http, monkeypatch, tmp_path,
):
    monkeypatch.setattr("pipeline.normalization.registry.UNMAPPED_FILE", tmp_path / "unmapped.json")
    payload = {
        "schema_version": 1,
        "environment": "v2_containerized",
        "hardware": {"name": "Test GPU", "sm": "sm_test", "vram_gb": 96},
        "problems": ["task-a", "task-b"],
        "models": [
            {
                "label": "test/test-model-a [max]",
                "harness": "test",
                "model": "test-model-a",
                "effort": "max",
                "results": {
                    "task-a": {
                        "run_id": "20260820_000000_test_a",
                        "correct": True,
                        "annotation_verdict": "clean",
                    },
                    "task-b": {
                        "run_id": "20260821_000000_test_b",
                        "correct": True,
                        "annotation_verdict": "reward_hack",
                        "invalid_reason": "reward_hack",
                    },
                },
                "pass_count": 1,
                "total_runs": 2,
            },
            {
                "label": "test/test-model-b",
                "harness": "test",
                "model": "test-model-b",
                "effort": "",
                "results": {
                    "task-a": {
                        "run_id": "20260822_000000_test_a",
                        "correct": True,
                        "annotation_verdict": "clean",
                    },
                },
                "pass_count": 1,
                "total_runs": 1,
            },
        ],
        "generated_from_summary": {"tag": "v2"},
    }
    mock_http.set(KB_DATA, payload)
    mock_http.set(KB_COMMITS, [{
        "sha": "abc123",
        "commit": {"committer": {"date": "2026-08-23T13:46:17Z"}},
    }])
    source = SourceConfig(
        source_id="kernelbench", source_name="KernelBench", source_level="C",
        homepage_url="https://kernelbench.com", attribution="test",
    )
    records = KernelBenchAdapter(source, real_benchmarks, normalizer, mock_http).fetch_records()

    assert len(records) == 2
    assert {r.score for r in records} == {50.0}
    first = next(r for r in records if r.model_id == "test-model-a")
    assert first.evaluation_date == "2026-08-21"
    assert first.sample_size == 2
    assert first.agent_scaffold == "test"
    assert first.evaluation_target_type == "model_plus_agent"
    assert first.source_commit_sha == "abc123"
    assert "无效/reward-hack=1" in (first.notes or "")
    partial = next(r for r in records if r.model_id == "test-model-b")
    assert partial.sample_size == 1
    assert "实际尝试=1" in (partial.notes or "")


def test_superclue_vlm_xlsx_keeps_understanding_separate_from_generation(
    normalizer, real_benchmarks, mock_http, monkeypatch, tmp_path,
):
    monkeypatch.setattr("pipeline.normalization.registry.UNMAPPED_FILE", tmp_path / "unmapped.json")
    frame = pd.DataFrame([{
        "排名": "1",
        "模型名称": "test-model-a(high)",
        "机构": "TestCorp",
        "总分": 75.81,
        "基础认知能力": 78.33,
        "视觉推理能力": 81.02,
        "视觉应用能力": 68.07,
        "开/闭源": "闭源",
    }])
    stream = io.BytesIO()
    with pd.ExcelWriter(stream, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="总榜", index=False)

    url = "https://www.superclueai.com/data/multimodal_list/VLM/2026年7月.xlsx"
    mock_http.set(url, stream.getvalue())
    mock_http.set_metadata(url, {"last_modified": "Mon, 13 Jul 2026 03:42:50 GMT"})
    source = SourceConfig(
        source_id="superclue_vlm", source_name="SuperCLUE-VLM", source_level="B",
        homepage_url="https://www.superclueai.com", attribution="test",
    )
    adapter = SuperCLUEVLMAdapter(source, real_benchmarks, normalizer, mock_http)
    monkeypatch.setattr(adapter, "_discover_release", lambda: "2026年7月")
    records = adapter.fetch_records()

    assert len(records) == 4
    overall = next(r for r in records if r.benchmark_id == "superclue-vlm-overall")
    assert overall.capability == "multimodal"
    assert overall.model_id == "test-model-a"
    assert overall.model_variant == "high"
    assert overall.evaluation_date is None
    assert overall.benchmark_version == "2026-07"
    assert overall.upstream_updated_at == "2026-07-13T03:42:50Z"
    assert {r.capability for r in records} == {
        "multimodal", "visual_cognition", "visual_reasoning", "visual_application",
    }


def test_superclue_longcontext_keeps_256k_and_1m_as_separate_boards(
    normalizer, real_benchmarks, mock_http, monkeypatch, tmp_path,
):
    monkeypatch.setattr("pipeline.normalization.registry.UNMAPPED_FILE", tmp_path / "unmapped.json")
    short = pd.DataFrame([{
        "排名": "1", "模型名称": "test-model-a(high)", "机构": "TestCorp",
        "总分": 98.24, "4K-8K": 99.52, "128K-256K": 90.18,
    }])
    long = pd.DataFrame([{
        "排名": "1", "模型名称": "test-model-a(high)", "机构": "TestCorp",
        "总分": 91.98, "4K-8K": 99.52, "512K-1M": 53.21,
    }])
    stream = io.BytesIO()
    with pd.ExcelWriter(stream, engine="openpyxl") as writer:
        short.to_excel(writer, sheet_name="256K总榜", index=False)
        long.to_excel(writer, sheet_name="1M总榜", index=False)

    url = "https://www.superclueai.com/data/specialized_list/LongContext/2026年7月.xlsx"
    mock_http.set(url, stream.getvalue())
    mock_http.set_metadata(url, {"last_modified": "Mon, 20 Jul 2026 07:09:07 GMT"})
    source = SourceConfig(
        source_id="superclue_longcontext", source_name="SuperCLUE-LongContext",
        source_level="B", homepage_url="https://www.superclueai.com", attribution="test",
    )
    adapter = SuperCLUELongContextAdapter(source, real_benchmarks, normalizer, mock_http)
    monkeypatch.setattr(adapter, "_discover_release", lambda: "2026年7月")
    records = adapter.fetch_records()

    assert len(records) == 2
    assert {r.benchmark_id for r in records} == {
        "superclue-longcontext-256k", "superclue-longcontext-1m",
    }
    assert {r.score for r in records} == {98.24, 91.98}
    assert all(r.capability == "long_context" for r in records)
    assert all(r.evaluation_date is None for r in records)
    assert all(r.upstream_updated_at == "2026-07-20T07:09:07Z" for r in records)


def test_terminalbench_structured_hydration_keeps_date_semantics(
    sample_source, normalizer, real_benchmarks, mock_http,
):
    payload = {
        "leaderboard": {
            "name": "4-0-0",
            "title": "Terminal-Bench 4.0",
            "created_at": "2026-08-27T18:30:27+00:00",
            "updated_at": "2026-08-29T01:40:34+00:00",
        },
        "rows": [{
            "id": "row-a",
            "rank": 1,
            "status": "display",
            "metadata": {
                "date": "2026-07-24",
                "model_display": {"label": "test-model-a", "url": "https://example.com/model"},
                "agent_display": {"label": "Test Agent", "url": "https://example.com/agent"},
                "reasoning_effort": "max",
            },
            "metrics": {
                "accuracy": 51.82,
                "accuracy_ci95_half_width": 3.39,
                "n_trials": 330,
            },
            "created_at": "2026-08-27T18:30:27+00:00",
            "updated_at": "2026-08-29T01:40:34+00:00",
        }],
    }
    stream = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    html = f"<script>self.__next_f.push({json.dumps([1, stream])})</script>"
    mock_http.set(TB_URL, html.encode())

    records = TerminalBenchAdapter(sample_source, real_benchmarks, normalizer, mock_http).fetch_records()
    assert len(records) == 1
    rec = records[0]
    assert rec.model_id == "test-model-a"
    assert rec.evaluation_date is None
    assert rec.upstream_updated_at == "2026-08-29T01:40:34+00:00"
    assert rec.agent_scaffold == "Test Agent"
    assert rec.reasoning_effort == "max"
    assert rec.sample_size == 330
    assert rec.confidence_interval_low == pytest.approx(48.43)
    assert "模型发布日期=2026-07-24" in (rec.notes or "")


def test_bfcl_csv_splits_submission_mode_and_snapshot(
    sample_source, normalizer, real_benchmarks, mock_http,
):
    body = (
        b"Rank,Overall Acc,Model,Web Search Acc,Memory Acc,License\n"
        b"1,77.47%,test-model-a (FC),84.50%,73.76%,Proprietary\n"
        b"2,50.00%,unknown-model (Prompt),N/A,44.00%,Apache-2.0\n"
    )
    mock_http.set(BFCL_CSV, body)
    mock_http.set_metadata(BFCL_CSV, {"last_modified": "Mon, 13 Apr 2026 03:20:44 GMT"})

    records = BFCLAdapter(sample_source, real_benchmarks, normalizer, mock_http).fetch_records()
    mapped = next(r for r in records if r.benchmark_id == "bfcl-v4-overall" and not r.model_is_unmapped)
    assert mapped.model_id == "test-model-a"
    assert mapped.raw_model_name == "test-model-a (FC)"
    assert mapped.prompt_mode == "FC"
    assert mapped.model_variant == "FC"
    assert mapped.evaluation_date is None
    assert mapped.upstream_updated_at == "2026-04-13T03:20:44Z"
    assert {r.benchmark_id for r in records} == {
        "bfcl-v4-overall", "bfcl-v4-web-search", "bfcl-v4-memory",
    }


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
