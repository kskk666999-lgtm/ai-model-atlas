"""Pydantic 数据模型：基准成绩记录、模型注册项、数据源配置。

所有字段在数据缺失时必须为 None（前台显示"—"），禁止用 0 或编造值填充。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

EvaluationTargetType = Literal[
    "base_model",
    "api_endpoint",
    "model_variant",
    "model_plus_agent",
    "complete_agent_system",
    "image_model",
    "video_model",
    "speech_model",
    "embedding_model",
    "reranker",
]

SOURCE_LEVELS = {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.0}


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class BenchmarkRecord(BaseModel):
    """一条模型在某基准上的成绩，完整保留溯源信息。"""

    source_id: str
    source_name: str
    source_level: Literal["A", "B", "C", "D"]
    source_url: str

    benchmark_id: str
    benchmark_name: str
    benchmark_version: str | None = None
    capability: str

    model_id: str  # canonical_id 或 source-scoped 临时 ID
    raw_model_name: str | None = None  # 来源侧原始名称，用于展示与溯源
    model_is_unmapped: bool = False
    model_variant: str | None = None
    evaluation_target_type: EvaluationTargetType = "base_model"

    score: float
    score_unit: str
    higher_is_better: bool = True
    rank: int | None = None  # 由排名计算阶段填写

    sample_size: int | None = None
    confidence_interval_low: float | None = None
    confidence_interval_high: float | None = None

    evaluation_date: str | None = None
    published_at: str | None = None
    fetched_at: str = Field(default_factory=utc_now_iso)
    source_commit_sha: str | None = None

    reasoning_effort: str | None = None
    prompt_mode: str | None = None
    agent_scaffold: str | None = None
    hardware_or_endpoint: str | None = None
    license: str | None = None
    attribution: str | None = None
    notes: str | None = None

    # ---- 记录级可信度与精确溯源 ----
    # maintainer_verified：官方维护者复现/官方核验
    # third_party_submitted：官方平台收录的第三方提交（不进入严格榜）
    # unknown：未标注（默认不进入严格榜）
    record_verification_status: Literal[
        "maintainer_verified", "third_party_submitted", "unknown"
    ] = "maintainer_verified"
    data_file_url: str | None = None        # 包含该成绩的确切数据文件地址
    data_json_path: str | None = None       # JSON Path / CSV 行列定位
    data_sha256: str | None = None          # 本次抓取的数据文件 SHA256
    upstream_updated_at: str | None = None  # 上游数据文件发布/更新时间（可空）

    @field_validator("score")
    @classmethod
    def _score_must_be_finite(cls, v: float) -> float:
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("score 必须是有限数值")
        return v

    def dedupe_key(self) -> tuple:
        return (
            self.source_id,
            self.benchmark_id,
            self.model_id,
            # 未映射模型按来源原始名称区分（不同大小写/写法不合并）
            self.raw_model_name if self.model_is_unmapped else "",
            self.model_variant or "",
            self.agent_scaffold or "",
            self.benchmark_version or "",
        )


class ModelEntry(BaseModel):
    """模型注册表条目（models.yml）。"""

    canonical_id: str
    display_name: str
    provider: str | None = None  # 未知厂商时为 null，前台显示"未知厂商"
    family: str
    variant: str | None = None
    aliases: list[str] = Field(default_factory=list)
    release_date: str | None = None
    status: str = "active"
    region: str | None = None
    open_weights: bool | None = None
    license: str | None = None
    modalities: list[str] = Field(default_factory=list)
    context_window: int | None = None
    official_model_page: str | None = None
    deprecated: bool = False
    superseded_by: str | None = None


class SourceConfig(BaseModel):
    """数据源配置（sources.yml）。"""

    source_id: str
    source_name: str
    source_level: Literal["A", "B", "C", "D"]
    homepage_url: str | None = None
    method: str = "none"
    description: str | None = None
    license: str | None = None
    attribution: str | None = None
    requires_api_key: bool = False
    included_in_composite: bool = True
    status: Literal["active", "disabled", "optional"] = "active"
    docs_url: str | None = None


class AdapterResult(BaseModel):
    """适配器运行结果：成功数据 + 健康状态。"""

    source_id: str
    status: Literal["ok", "degraded", "failed", "skipped", "disabled"]
    records: list[BenchmarkRecord] = Field(default_factory=list)
    error_message: str | None = None
    response_time_ms: int | None = None
    degraded_from_lkg: bool = False


class UnmappedModel(BaseModel):
    """未能映射到 canonical_id 的来源侧模型名，等待人工补充别名。"""

    source_id: str
    raw_name: str
    temp_id: str
    occurrences: int = 1
    first_seen: str = Field(default_factory=utc_now_iso)
    last_seen: str = Field(default_factory=utc_now_iso)
    example_url: str | None = None


def parse_registry_models(path) -> list[ModelEntry]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [ModelEntry.model_validate(m) for m in (data.get("models") or [])]


def parse_registry_sources(path) -> list[SourceConfig]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [SourceConfig.model_validate(s) for s in (data.get("sources") or [])]


def load_yaml(path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
