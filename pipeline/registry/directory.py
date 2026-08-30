"""模型目录（Model Registry）上游：models.dev 结构化 API。

职责分离原则：
- 模型目录负责「现在有哪些模型、谁发的、什么时候发布、什么能力、什么价格」
- Benchmark 适配器只负责「某模型在某基准上得了多少分」

- 上游：https://models.dev/api.json（结构化 JSON，不爬 HTML）
- 失败时回退 Last Known Good（HTTP 缓存），绝不因目录源故障中断流水线
- 元数据匹配保守：精确/别名/规范化键匹配，匹配不上就记 unmatched，不猜测合并
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from ..registry.freshness import (
    freshness_bucket,
    freshness_days,
    is_current,
    lifecycle_status,
    parse_date,
    today_utc,
)

MODELSDEV_API = "https://models.dev/api.json"

# 常见 effort/变体后缀（用于匹配目录条目；不用于合并 benchmark 成绩）
_VARIANT_SUFFIXES = [
    "-thinking", "-high", "-xhigh", "-max", "-medium", "-low", "-effort",
    "-preview", "-latest", "-fast", "-flex",
]


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _strip_variant_suffix(name: str) -> str:
    """去掉 effort/变体后缀，得到族级候选键（迭代去除，如 -xhigh-effort）。"""
    s = _norm(name)
    changed = True
    while changed:
        changed = False
        for suf in _VARIANT_SUFFIXES:
            if s.endswith(suf):
                s = s[: -len(suf)]
                changed = True
    return s


@dataclass
class DirectoryEntry:
    provider_id: str
    model_id: str
    name: str
    family: str | None = None
    release_date: str | None = None
    last_updated: str | None = None
    status: str | None = None
    reasoning: bool | None = None
    tool_call: bool | None = None
    structured_output: bool | None = None
    open_weights: bool | None = None
    context_window: int | None = None
    max_output: int | None = None
    input_price: float | None = None
    output_price: float | None = None
    cached_input_price: float | None = None
    modalities: list[str] = field(default_factory=list)
    source_url: str | None = None

    def to_dict(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "name": self.name,
            "family": self.family,
            "release_date": self.release_date,
            "last_updated": self.last_updated,
            "status": self.status,
            "reasoning": self.reasoning,
            "tool_call": self.tool_call,
            "structured_output": self.structured_output,
            "open_weights": self.open_weights,
            "context_window": self.context_window,
            "max_output": self.max_output,
            "input_price": self.input_price,
            "output_price": self.output_price,
            "cached_input_price": self.cached_input_price,
            "modalities": self.modalities,
            "source_url": self.source_url,
        }


class ModelDirectory:
    """models.dev 目录的规范化视图 + 到本站 canonical_id 的匹配索引。"""

    def __init__(self, raw: dict) -> None:
        self.entries: list[DirectoryEntry] = []
        self._load(raw)
        # 匹配索引：规范化键 -> entry 列表
        self._by_key: dict[str, list[DirectoryEntry]] = {}
        for e in self.entries:
            for key in self._keys_for(e.model_id, e.name):
                self._by_key.setdefault(key, []).append(e)

    def _load(self, raw: dict) -> None:
        for provider_id, provider in raw.items():
            if not isinstance(provider, dict):
                continue
            for model_id, m in (provider.get("models") or {}).items():
                if not isinstance(m, dict):
                    continue
                limit = m.get("limit") or {}
                cost = m.get("cost") or {}
                modalities = (m.get("modalities") or {})
                self.entries.append(DirectoryEntry(
                    provider_id=provider_id,
                    model_id=str(m.get("id") or model_id),
                    name=str(m.get("name") or m.get("id") or model_id),
                    family=m.get("family"),
                    release_date=m.get("release_date"),
                    last_updated=m.get("last_updated"),
                    status=m.get("status"),
                    reasoning=m.get("reasoning"),
                    tool_call=m.get("tool_call"),
                    structured_output=m.get("structured_output"),
                    open_weights=m.get("open_weights"),
                    context_window=limit.get("context") or None,
                    max_output=limit.get("output") or None,
                    input_price=cost.get("input"),
                    output_price=cost.get("output"),
                    cached_input_price=cost.get("cache_read"),
                    modalities=(modalities.get("input") or []) + (modalities.get("output") or []),
                    source_url=f"https://models.dev/#{provider_id}",
                ))

    @staticmethod
    def _keys_for(model_id: str, name: str) -> list[str]:
        keys = []
        for v in (model_id, name):
            n = _norm(str(v))
            keys.append(n)
            # 去掉 provider 前缀（如 deepseek/deepseek-v4 -> deepseek-v4）
            if "/" in n:
                keys.append(n.split("/")[-1])
        stripped_id = _strip_variant_suffix(model_id)
        if stripped_id and stripped_id not in keys:
            keys.append(stripped_id)
        return [k for k in dict.fromkeys(keys) if len(k) >= 3]

    def match(self, canonical_id: str, aliases: list[str] | None = None) -> DirectoryEntry | None:
        """把本站 canonical_id 匹配到目录条目（保守：精确/规范化键，不模糊合并）。"""
        candidates = [canonical_id] + (aliases or [])
        for cand in candidates:
            for key in self._keys_for(cand, cand):
                found = self._by_key.get(key)
                if found:
                    # 多命中时优先 release_date 较新者（同一模型多 provider 挂载）
                    return sorted(
                        found,
                        key=lambda e: e.release_date or e.last_updated or "",
                        reverse=True,
                    )[0]
        # 族级兜底：去后缀键匹配（仅当唯一命中，避免误配）
        for cand in candidates:
            key = _strip_variant_suffix(cand)
            found = self._by_key.get(key)
            if found and len(found) == 1:
                return found[0]
        return None


def load_model_directory(http) -> tuple[ModelDirectory, dict]:
    """拉取 models.dev 目录；返回 (目录, 元信息)。失败由调用方按 LKG 处理。"""
    body = http.get(MODELSDEV_API)
    raw = json.loads(body.decode("utf-8"))
    import hashlib

    meta = {
        "url": MODELSDEV_API,
        "sha256": hashlib.sha256(body).hexdigest(),
        "providers": len(raw),
        "models": sum(len(p.get("models") or {}) for p in raw.values() if isinstance(p, dict)),
    }
    return ModelDirectory(raw), meta


def enrich_entry(entry: DirectoryEntry) -> dict:
    """为目录条目计算新鲜度/生命周期/当前资格。"""
    days = freshness_days(entry.release_date, entry.last_updated, today=today_utc())
    bucket = freshness_bucket(days)
    lifecycle = lifecycle_status(entry.status, bucket, entry.release_date)
    return {
        **entry.to_dict(),
        "freshness_days": days,
        "freshness_bucket": bucket,
        "lifecycle_status": lifecycle,
        "is_current": is_current(lifecycle=lifecycle, bucket=bucket),
    }


def latest_release_entries(enriched: list[dict], days: int) -> list[dict]:
    """目录中最近 N 天发布（或更新）的模型（用于 Latest Releases）。"""
    today = today_utc()
    out = []
    for e in enriched:
        d = parse_date(e.get("release_date")) or parse_date(e.get("last_updated"))
        if d is None:
            continue
        if 0 <= (today - d).days <= days:
            out.append(e)
    out.sort(key=lambda e: e.get("release_date") or e.get("last_updated") or "", reverse=True)
    return out
