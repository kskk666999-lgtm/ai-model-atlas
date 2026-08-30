"""pytest 全局夹具：假 HTTP 客户端 + 最小注册表。"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from pipeline.normalization.registry import ModelNormalizer
from pipeline.schemas.records import ModelEntry, SourceConfig


class MockHttpClient:
    """可编程的假 HttpClient：url -> 返回值（bytes / dict / 异常）。"""

    def __init__(self) -> None:
        self.routes: dict = {}
        self.calls: list[str] = []

    def set(self, url: str, value) -> None:
        self.routes[url] = value

    def get(self, url: str, use_cache: bool = True) -> bytes:
        self.calls.append(url)
        v = self.routes[url]
        if isinstance(v, Exception):
            raise v
        if isinstance(v, (dict, list)):
            import json

            return json.dumps(v).encode("utf-8")
        return v

    def get_json(self, url: str, use_cache: bool = True):
        import json

        return json.loads(self.get(url).decode("utf-8"))

    def close(self) -> None:
        pass


@pytest.fixture
def mock_http() -> MockHttpClient:
    return MockHttpClient()


@pytest.fixture
def sample_models() -> list[ModelEntry]:
    return [
        ModelEntry(
            canonical_id="test-model-a",
            display_name="Test Model A",
            provider="TestCorp",
            family="test",
            aliases=["test-model-a", "TestCorp/Test-Model-A", "test_model_A_v1"],
        ),
        ModelEntry(
            canonical_id="test-model-b",
            display_name="Test Model B",
            provider="OtherCorp",
            family="test",
            aliases=["test-model-b"],
        ),
    ]


@pytest.fixture
def normalizer(sample_models) -> ModelNormalizer:
    return ModelNormalizer(sample_models)


@pytest.fixture
def sample_source() -> SourceConfig:
    return SourceConfig(
        source_id="testsource",
        source_name="Test Source",
        source_level="A",
        homepage_url="https://example.com",
        attribution="test",
    )


BENCHMARKS = {
    "bench-x": {
        "benchmark_id": "bench-x",
        "benchmark_name": "Benchmark X",
        "source_id": "testsource",
        "capability": "reasoning",
        "higher_is_better": True,
        "score_unit": "percent",
    },
    "bench-low": {
        "benchmark_id": "bench-low",
        "benchmark_name": "Benchmark Lower Better",
        "source_id": "testsource",
        "capability": "latency",
        "higher_is_better": False,
        "score_unit": "seconds",
    },
}


@pytest.fixture
def benchmarks() -> dict:
    return dict(BENCHMARKS)
