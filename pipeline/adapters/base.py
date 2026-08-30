"""适配器基类：来源级错误隔离 + Last Known Good 回退。

- 成功：解析 → 校验 → 写入 LKG 缓存（data/cache/records/<source_id>.json）
- 失败：自动回退到 LKG，结果标记 degraded，绝不因单源失败中断流水线
"""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from ..normalization.registry import ModelNormalizer
from ..paths import RECORDS_LKG_DIR
from ..schemas.records import (
    AdapterResult,
    BenchmarkRecord,
    SourceConfig,
    load_yaml,
)
from ..utils.http import HttpClient

REGISTRY_BENCHMARKS_PATH = Path(__file__).resolve().parents[2] / "data" / "registry" / "benchmarks.yml"


class AdapterError(Exception):
    pass


def load_benchmarks_registry() -> dict[str, dict]:
    data = load_yaml(REGISTRY_BENCHMARKS_PATH)
    return {b["benchmark_id"]: b for b in (data.get("benchmarks") or [])}


class BaseAdapter(ABC):
    """子类实现 fetch_records()；本基类负责 LKG 与结果封装。"""

    source_id = "base"

    def __init__(
        self,
        source: SourceConfig,
        benchmarks: dict[str, dict],
        normalizer: ModelNormalizer,
        http: HttpClient,
    ) -> None:
        self.source = source
        self.benchmarks = benchmarks
        self.normalizer = normalizer
        self.http = http

    @abstractmethod
    def fetch_records(self) -> list[BenchmarkRecord]:
        """抓取并解析为 BenchmarkRecord 列表；抛异常视为本次抓取失败。"""

    # ---- LKG ----
    @property
    def _lkg_path(self) -> Path:
        RECORDS_LKG_DIR.mkdir(parents=True, exist_ok=True)
        return RECORDS_LKG_DIR / f"{self.source_id}.json"

    def _load_lkg(self) -> list[BenchmarkRecord]:
        if not self._lkg_path.exists():
            return []
        data = json.loads(self._lkg_path.read_text(encoding="utf-8"))
        return [BenchmarkRecord.model_validate(r) for r in data.get("records", [])]

    def _save_lkg(self, records: list[BenchmarkRecord]) -> None:
        self._lkg_path.parent.mkdir(parents=True, exist_ok=True)
        # 适配器并发抓取的完成顺序不确定，必须规范化排序保证 LKG 逐字节稳定
        ordered = sorted(
            records,
            key=lambda r: (r.benchmark_id, r.model_id, r.raw_model_name or "",
                           r.agent_scaffold or "", r.benchmark_version or "", r.score),
        )
        self._lkg_path.write_text(
            json.dumps(
                {"source_id": self.source_id,
                 "fetched_at": max((r.fetched_at for r in ordered if r.fetched_at), default=None),
                 "count": len(ordered),
                 "records": [r.model_dump() for r in ordered]},
                ensure_ascii=False, indent=1, sort_keys=True,
            ),
            encoding="utf-8", newline="\n",
        )

    def run(self) -> AdapterResult:
        started = time.monotonic()
        try:
            records = self.fetch_records()
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.TransportError) as e:
            return self._fallback(f"网络错误: {type(e).__name__}: {e}", started)
        except AdapterError as e:
            return self._fallback(f"适配器错误: {e}", started)
        except Exception as e:  # 解析失败、结构变化等
            return self._fallback(f"解析错误: {type(e).__name__}: {e}", started)

        if not records:
            # 来源返回空数据视为失败，保留上一次有效数据
            return self._fallback("来源返回 0 条有效记录", started)

        self._inherit_fetched_at(records)
        self._save_lkg(records)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return AdapterResult(
            source_id=self.source_id, status="ok", records=records,
            response_time_ms=elapsed_ms,
        )

    def _inherit_fetched_at(self, records: list[BenchmarkRecord]) -> None:
        """业务内容与上次成功数据完全一致的记录，继承其 fetched_at。

        保证"数据没变 → 输出 JSON 逐字节不变 → CI 不产生无意义提交"。
        业务内容 = 除 fetched_at 外的全部字段。
        """
        try:
            old = self._load_lkg()
        except Exception:
            return
        if not old:
            return
        old_by_key: dict[str, str] = {}
        for r in old:
            d = r.model_dump(exclude={"fetched_at"})
            old_by_key[self._business_key(d)] = r.fetched_at
        for rec in records:
            d = rec.model_dump(exclude={"fetched_at"})
            prev = old_by_key.get(self._business_key(d))
            if prev:
                rec.fetched_at = prev

    @staticmethod
    def _business_key(d: dict) -> str:
        import json as _json

        return _json.dumps(d, ensure_ascii=False, sort_keys=True)

    def _fallback(self, message: str, started: float) -> AdapterResult:
        lkg = self._load_lkg()
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if lkg:
            return AdapterResult(
                source_id=self.source_id, status="degraded", records=lkg,
                error_message=message + "（已回退到上次成功数据）",
                response_time_ms=elapsed_ms, degraded_from_lkg=True,
            )
        return AdapterResult(
            source_id=self.source_id, status="failed",
            error_message=message, response_time_ms=elapsed_ms,
        )

    # ---- 帮助方法 ----
    def bench(self, benchmark_id: str) -> dict:
        b = self.benchmarks.get(benchmark_id)
        if not b:
            raise AdapterError(f"benchmarks.yml 中缺少 benchmark_id: {benchmark_id}")
        return b

    def make_record(self, benchmark_id: str, raw_model_name: str, score: float, **kwargs) -> BenchmarkRecord:
        b = self.bench(benchmark_id)
        normalization_name = kwargs.pop("normalization_name", raw_model_name)
        model_id, is_unmapped = self.normalizer.normalize(
            normalization_name, self.source.source_id, example_url=kwargs.get("source_url")
        )
        rec = BenchmarkRecord(
            source_id=self.source.source_id,
            source_name=self.source.source_name,
            source_level=self.source.source_level,
            source_url=kwargs.pop("source_url", self.source.homepage_url or ""),
            benchmark_id=benchmark_id,
            benchmark_name=b["benchmark_name"],
            benchmark_version=kwargs.pop("benchmark_version", None),
            capability=b["capability"],
            model_id=model_id,
            raw_model_name=raw_model_name,
            model_is_unmapped=is_unmapped,
            score=score,
            score_unit=b["score_unit"],
            higher_is_better=b.get("higher_is_better", True),
            attribution=self.source.attribution,
            **kwargs,
        )
        return rec


def build_adapter_runtime(
    source: SourceConfig,
    normalizer: ModelNormalizer,
    http: HttpClient,
    adapter_cls: type[BaseAdapter],
) -> BaseAdapter:
    return adapter_cls(
        source=source,
        benchmarks=load_benchmarks_registry(),
        normalizer=normalizer,
        http=http,
    )
