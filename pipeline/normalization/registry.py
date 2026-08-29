"""模型名称规范化。

原则（不可违反）：
- 只有显式别名（models.yml aliases 或 aliases.yml）才能建立映射；
- 禁止通过字符串相似度自动猜测合并；
- 未知模型不丢弃、不合并，生成 source-scoped 临时 ID 并写入 unmapped 报告。
"""
from __future__ import annotations

import re
import unicodedata

from ..paths import REGISTRY_ALIASES, UNMAPPED_FILE
from ..schemas.records import ModelEntry, UnmappedModel, load_yaml, utc_now_iso


def _canon_key(name: str) -> str:
    """仅做无损规范化：小写、去首尾空白、统一全角/宽度差异。

    不删除版本号、日期等任何信息，避免错误合并不同版本。
    """
    name = unicodedata.normalize("NFKC", name)
    return re.sub(r"\s+", " ", name.strip().lower())


class ModelNormalizer:
    def __init__(self, models: list[ModelEntry]) -> None:
        self.models = {m.canonical_id: m for m in models}
        self._alias_index: dict[str, str] = {}
        for m in models:
            for alias in m.aliases:
                self._alias_index[_canon_key(alias)] = m.canonical_id
            self._alias_index.setdefault(_canon_key(m.canonical_id), m.canonical_id)
        # aliases.yml 的显式映射（优先级更高，最后写入覆盖同名）
        extra = load_yaml(REGISTRY_ALIASES).get("aliases") or {}
        for raw, canonical in extra.items():
            if canonical in self.models:
                self._alias_index[_canon_key(raw)] = canonical

        # unmapped 状态（跨来源聚合）
        self._unmapped: dict[tuple[str, str], UnmappedModel] = {}

    def normalize(self, raw_name: str, source_id: str, example_url: str | None = None) -> tuple[str, bool]:
        """返回 (model_id, is_unmapped)。未知名称生成 source-scoped 临时 ID。"""
        key = _canon_key(raw_name)
        canonical = self._alias_index.get(key)
        if canonical:
            return canonical, False
        slug = re.sub(r"[^a-z0-9._-]+", "-", key).strip("-") or "unknown"
        temp_id = f"unmapped--{source_id}--{slug}"
        self.record_unmapped(raw_name, source_id, temp_id, example_url)
        return temp_id, True

    def record_unmapped(self, raw_name: str, source_id: str, temp_id: str, example_url: str | None = None) -> None:
        k = (source_id, raw_name)
        now = utc_now_iso()
        existing = self._unmapped.get(k)
        if existing:
            existing.occurrences += 1
            existing.last_seen = now
        else:
            self._unmapped[k] = UnmappedModel(
                source_id=source_id, raw_name=raw_name, temp_id=temp_id,
                first_seen=now, last_seen=now, example_url=example_url,
            )

    def save_unmapped_report(self) -> list[UnmappedModel]:
        items = sorted(
            self._unmapped.values(),
            key=lambda u: (-u.occurrences, u.source_id, u.raw_name),
        )
        UNMAPPED_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "note": "以下模型名称来自数据源原文，尚未建立到注册表的映射。请人工在 models.yml/aliases.yml 中补充别名；同名不同版本禁止自动合并。",
            "count": len(items),
            # 不输出任何墙钟时间戳，保证内容不变时文件逐字节稳定
            "unmapped": [
                {k: v for k, v in u.model_dump().items() if k not in ("first_seen", "last_seen")}
                for u in items
            ],
        }
        import json

        UNMAPPED_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        return items

    def get(self, canonical_id: str) -> ModelEntry | None:
        return self.models.get(canonical_id)
