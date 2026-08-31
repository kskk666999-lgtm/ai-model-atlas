"""SuperCLUE 官方月度中文通用榜适配器（B 级官方 XLSX 导出）。

官网把最新版月度榜以可下载 XLSX 公开；适配器从前端清单发现当前月份，
只读取“总排行榜”工作表，并保留总分及六个官方分项。官方没有逐模型
评测运行日，因此月份仅作为 benchmark_version，不能伪装成某一天。
"""
from __future__ import annotations

import hashlib
import io
import math
import re

import pandas as pd

from ..utils.http import http_date_to_iso
from .base import AdapterError, BaseAdapter

SITE_BASE = "https://www.superclueai.com"
FALLBACK_RELEASE = "2026年7月"
SHEET_NAME = "总排行榜"

BENCHMARK_COLUMNS = {
    "总分": "superclue-general",
    "数学推理": "superclue-math",
    "幻觉控制": "superclue-hallucination-control",
    "科学推理": "superclue-science-reasoning",
    "精确指令遵循": "superclue-precise-instruction",
    "智能体编程": "superclue-agentic-coding",
    "智能体任务规划": "superclue-agent-planning",
}

INDEX_BUNDLE_RE = re.compile(r'(?:src|href)=["\'](?:/)?assets/(index-[^"\']+\.js)')
BOARD_BUNDLE_RE = re.compile(r'(?:\./)?(GeneralBoardPage-[A-Za-z0-9_-]+\.js)')
SELECTED_RELEASE_RE = re.compile(r'selectedDate:"(20\d{2}年\d{1,2}月)"')
RELEASE_RE = re.compile(r"^(20\d{2})年(\d{1,2})月$")
EFFORT_RE = re.compile(r"^(.*)\((low|medium|high|xhigh|max)\)$", re.IGNORECASE)


def _clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _release_version(release: str) -> str:
    match = RELEASE_RE.fullmatch(release)
    if not match:
        raise AdapterError(f"SuperCLUE 月份格式变化: {release}")
    return f"{match.group(1)}-{int(match.group(2)):02d}"


def _parse_model_label(value: object) -> tuple[str, str, str | None, str | None]:
    """返回 (来源原名, 用于映射的基础名, 推理档位, 变体)。"""
    raw = _clean_text(value)
    if not raw:
        raise AdapterError("SuperCLUE 出现空模型名")
    preview = raw.endswith("预览版")
    without_preview = raw.removesuffix("预览版").strip()
    match = EFFORT_RE.fullmatch(without_preview)
    if match:
        base = match.group(1).strip()
        effort = match.group(2).lower()
    else:
        base = without_preview
        effort = None
    variant_parts = [part for part in (effort, "preview" if preview else None) if part]
    return raw, base, effort, "-".join(variant_parts) or None


class SuperCLUEAdapter(BaseAdapter):
    source_id = "superclue"

    def _discover_release(self) -> str:
        """从官网当前构建产物读取默认（即最新）月度榜，失败时使用已验证兜底。"""
        try:
            html = self.http.get(f"{SITE_BASE}/").decode("utf-8", "ignore")
            index_match = INDEX_BUNDLE_RE.search(html)
            if not index_match:
                raise AdapterError("SuperCLUE 首页未找到 index bundle")
            index_js = self.http.get(f"{SITE_BASE}/assets/{index_match.group(1)}").decode(
                "utf-8", "ignore"
            )
            board_match = BOARD_BUNDLE_RE.search(index_js)
            if not board_match:
                raise AdapterError("SuperCLUE index bundle 未找到通用榜 bundle")
            board_js = self.http.get(f"{SITE_BASE}/assets/{board_match.group(1)}").decode(
                "utf-8", "ignore"
            )
            release_match = SELECTED_RELEASE_RE.search(board_js)
            if release_match:
                return release_match.group(1)
        except Exception:
            # 实际 XLSX 抓取仍会校验；这里的兜底只避免前端文件名调整导致全源失效。
            pass
        return FALLBACK_RELEASE

    def fetch_records(self):
        release = self._discover_release()
        version = _release_version(release)
        data_url = f"{SITE_BASE}/data/generalboard/{release}.xlsx"
        body = self.http.get(data_url)
        data_sha = hashlib.sha256(body).hexdigest()
        metadata = self.http.metadata(data_url)
        snapshot_at = (
            http_date_to_iso(metadata.get("last_modified")) or metadata.get("fetched_at")
        )

        try:
            frame = pd.read_excel(io.BytesIO(body), sheet_name=SHEET_NAME, engine="openpyxl")
        except Exception as exc:
            raise AdapterError(f"SuperCLUE XLSX 解析失败: {type(exc).__name__}: {exc}") from exc

        required = {"模型名称", "机构", *BENCHMARK_COLUMNS}
        missing = sorted(required - set(frame.columns))
        if missing:
            raise AdapterError(f"SuperCLUE XLSX 缺少列: {missing}")

        records = []
        for row_index, row in frame.iterrows():
            raw_name, normalization_name, effort, variant = _parse_model_label(row["模型名称"])
            provider = _clean_text(row.get("机构")) or "未标注"
            openness = _clean_text(row.get("开/闭源")) or "未标注"
            usage = _clean_text(row.get("使用方式")) or "未标注"
            reasoning = _clean_text(row.get("是否推理")) or "未标注"
            source_release = _clean_text(row.get("发布日期")) or "未标注"

            for column, benchmark_id in BENCHMARK_COLUMNS.items():
                value = row.get(column)
                if value is None or pd.isna(value):
                    continue
                try:
                    score = float(value)
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(score) or not 0 <= score <= 100:
                    raise AdapterError(
                        f"SuperCLUE 非法分数: 模型={raw_name}, 列={column}, 值={value}"
                    )
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
                        prompt_mode=(f"推理={reasoning}；使用方式={usage}"),
                        record_verification_status="maintainer_verified",
                        data_file_url=data_url,
                        data_json_path=(
                            f"xlsx: sheet={SHEET_NAME}, row={row_index + 2}, column={column}"
                        ),
                        data_sha256=data_sha,
                        upstream_updated_at=snapshot_at,
                        source_url=f"{SITE_BASE}/",
                        notes=(
                            f"SuperCLUE {release} 官方月度榜；机构={provider}；{openness}；"
                            f"官方只公开评测月份，未公开逐模型运行日。工作簿“发布日期”="
                            f"{source_release}，因字段语义不足，不替代模型发布日期或评测运行日"
                        ),
                    )
                )

        if not records:
            raise AdapterError("SuperCLUE 官方 XLSX 没有有效记录")
        return records
