"""SuperCLUE-LongContext 中文超长上下文月度榜适配器（B 级官方 XLSX）。"""
from __future__ import annotations

import hashlib
import io
import math
import re

import pandas as pd

from ..utils.http import http_date_to_iso
from .base import AdapterError, BaseAdapter
from .superclue import INDEX_BUNDLE_RE, RELEASE_RE, SITE_BASE
from .superclue_vlm import UTILS_BUNDLE_RE

FALLBACK_RELEASE = "2026年7月"
LONGCONTEXT_RELEASE_RE = re.compile(r'LongContext:\["(20\d{2}年\d{1,2}月)"')
SUFFIX_RE = re.compile(r"^(.*)\(([^()]+)\)$")
SHEETS = {
    "256K总榜": "superclue-longcontext-256k",
    "1M总榜": "superclue-longcontext-1m",
}


def _release_version(release: str) -> str:
    match = RELEASE_RE.fullmatch(release)
    if not match:
        raise AdapterError(f"SuperCLUE-LongContext 月份格式变化: {release}")
    return f"{match.group(1)}-{int(match.group(2)):02d}"


def _clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _parse_model_label(value: object) -> tuple[str, str, str | None, str | None]:
    raw = _clean_text(value)
    if not raw:
        raise AdapterError("SuperCLUE-LongContext 出现空模型名")
    match = SUFFIX_RE.fullmatch(raw)
    if not match:
        return raw, raw, None, None
    base = match.group(1).strip()
    suffix = match.group(2).strip().lower()
    effort = suffix if suffix in {"low", "medium", "high", "xhigh", "max", "thinking"} else None
    return raw, base, effort, suffix


class SuperCLUELongContextAdapter(BaseAdapter):
    source_id = "superclue_longcontext"

    def _discover_release(self) -> str:
        try:
            html = self.http.get(f"{SITE_BASE}/").decode("utf-8", "ignore")
            index_match = INDEX_BUNDLE_RE.search(html)
            if not index_match:
                raise AdapterError("SuperCLUE-LongContext 首页未找到 index bundle")
            index_js = self.http.get(f"{SITE_BASE}/assets/{index_match.group(1)}").decode(
                "utf-8", "ignore"
            )
            utils_match = UTILS_BUNDLE_RE.search(index_js)
            if not utils_match:
                raise AdapterError("SuperCLUE-LongContext 未找到榜单日期清单 bundle")
            utils_js = self.http.get(f"{SITE_BASE}/assets/{utils_match.group(1)}").decode(
                "utf-8", "ignore"
            )
            release_match = LONGCONTEXT_RELEASE_RE.search(utils_js)
            if release_match:
                return release_match.group(1)
        except Exception:
            pass
        return FALLBACK_RELEASE

    def fetch_records(self):
        release = self._discover_release()
        version = _release_version(release)
        data_url = f"{SITE_BASE}/data/specialized_list/LongContext/{release}.xlsx"
        body = self.http.get(data_url)
        data_sha = hashlib.sha256(body).hexdigest()
        metadata = self.http.metadata(data_url)
        snapshot_at = (
            http_date_to_iso(metadata.get("last_modified")) or metadata.get("fetched_at")
        )
        try:
            workbook = pd.read_excel(
                io.BytesIO(body), sheet_name=list(SHEETS), engine="openpyxl"
            )
        except Exception as exc:
            raise AdapterError(
                f"SuperCLUE-LongContext XLSX 解析失败: {type(exc).__name__}: {exc}"
            ) from exc

        records = []
        for sheet, benchmark_id in SHEETS.items():
            frame = workbook.get(sheet)
            if frame is None:
                raise AdapterError(f"SuperCLUE-LongContext 缺少工作表: {sheet}")
            required = {"模型名称", "机构", "总分"}
            missing = sorted(required - set(frame.columns))
            if missing:
                raise AdapterError(f"SuperCLUE-LongContext {sheet} 缺少列: {missing}")
            for row_index, row in frame.iterrows():
                raw_name, normalization_name, effort, variant = _parse_model_label(
                    row["模型名称"]
                )
                try:
                    score = float(row["总分"])
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(score) or not 0 <= score <= 100:
                    raise AdapterError(
                        f"SuperCLUE-LongContext 非法分数: 模型={raw_name}, 表={sheet}"
                    )
                provider = _clean_text(row.get("机构")) or "未标注"
                records.append(
                    self.make_record(
                        benchmark_id=benchmark_id,
                        raw_model_name=raw_name,
                        normalization_name=normalization_name,
                        score=score,
                        benchmark_version=version,
                        evaluation_date=None,
                        published_at=snapshot_at,
                        model_variant=variant,
                        evaluation_target_type="model_variant" if variant else "api_endpoint",
                        reasoning_effort=effort,
                        record_verification_status="maintainer_verified",
                        data_file_url=data_url,
                        data_json_path=f"xlsx: sheet={sheet}, row={row_index + 2}, column=总分",
                        data_sha256=data_sha,
                        upstream_updated_at=snapshot_at,
                        source_url=f"{SITE_BASE}/",
                        notes=(
                            f"SuperCLUE-LongContext {release} 官方{sheet}；机构={provider}；"
                            "官方只公开评测月份，未公开逐模型运行日"
                        ),
                    )
                )
        if not records:
            raise AdapterError("SuperCLUE-LongContext 官方 XLSX 没有有效记录")
        return records
