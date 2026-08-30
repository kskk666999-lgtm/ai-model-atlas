"""LiveBench 官方数据适配器（B级：官方排行榜导出）。

数据：livebench.ai 官方排行榜构建产物
- table_<release>.csv        模型 × 任务 官方分数矩阵
- categories_<release>.json  官方类别 -> 任务映射
- cost_<release>.csv         官方统计的输入/输出价格（每百万 Token）

release 版本号从官网前端 bundle 中提取（YYYY-MM-DD 列表，取最新可用者）。
按官方类别对任务分数取平均，得到各能力官方分。
"""
from __future__ import annotations

import csv
import io
import json
import re

from ..utils.http import http_date_to_iso
from .base import AdapterError, BaseAdapter

SITE_BASE = "https://livebench.ai"
BUNDLE_URL = f"{SITE_BASE}/static/js/main.js"

# 官方类别名 -> benchmarks.yml benchmark_id
CATEGORY_TO_BENCHMARK = {
    "reasoning": "livebench-reasoning",
    "coding": "livebench-coding",
    "agentic coding": "livebench-agentic-coding",
    "mathematics": "livebench-mathematics",
    "data analysis": "livebench-data-analysis",
    "language": "livebench-language",
    "if": "livebench-instruction-following",
    "instruction following": "livebench-instruction-following",
    "social": "livebench-social",
}

DATE_RE = re.compile(r'"(20\d{2}-\d{2}-\d{2})"')


class LiveBenchAdapter(BaseAdapter):
    source_id = "livebench"

    def _discover_release(self) -> str:
        """从官网前端 bundle 中发现最新可用 release（YYYY-MM-DD）。"""
        candidates: list[str] = []
        try:
            html = self.http.get(f"{SITE_BASE}/").decode("utf-8", "ignore")
            bundle_names = re.findall(r"static/js/(main\.[a-z0-9]+\.js)", html)
        except Exception:
            bundle_names = []
        for name in bundle_names or ["main.js"]:
            try:
                body = self.http.get(f"{SITE_BASE}/static/js/{name}").decode("utf-8", "ignore")
                candidates += DATE_RE.findall(body)
            except Exception:
                continue
        # 兜底：已知近期 release（bundle 不可达时仍可运行）
        candidates += ["2026-06-25"]
        seen: set[str] = set()
        for date in sorted(set(candidates), reverse=True):
            if date in seen:
                continue
            seen.add(date)
            token = date.replace("-", "_")
            try:
                self.http.get(f"{SITE_BASE}/categories_{token}.json")
                return date
            except Exception:
                continue
        raise AdapterError("未能发现可用的 LiveBench release")

    def fetch_records(self):
        import hashlib

        release = self._discover_release()
        token = release.replace("-", "_")
        table_url = f"{SITE_BASE}/table_{token}.csv"
        cost_url = f"{SITE_BASE}/cost_{token}.csv"
        table_body = self.http.get(table_url)
        table_meta = self.http.metadata(table_url)
        snapshot_at = http_date_to_iso(table_meta.get("last_modified")) or table_meta.get("fetched_at")
        table_sha = hashlib.sha256(table_body).hexdigest()
        table = csv.DictReader(io.StringIO(table_body.decode("utf-8")))
        rows = list(table)
        categories = json.loads(self.http.get(f"{SITE_BASE}/categories_{token}.json").decode("utf-8"))

        records = []
        for category, tasks in categories.items():
            benchmark_id = CATEGORY_TO_BENCHMARK.get(str(category).strip().lower())
            if not benchmark_id:
                slug = str(category).strip().lower().replace(" ", "-")
                self.normalizer.record_unmapped(
                    f"[livebench-category] {category}", self.source_id,
                    f"unmapped--livebench--category--{slug}",
                )
                continue
            for row in rows:
                model = (row.get("model") or "").strip()
                if not model:
                    continue
                scores = []
                for task in tasks:
                    raw = row.get(task)
                    if raw is None or raw == "":
                        continue
                    try:
                        scores.append(float(raw))
                    except ValueError:
                        continue
                if not scores:
                    continue
                mean_score = sum(scores) / len(scores)
                records.append(self.make_record(
                    benchmark_id=benchmark_id,
                    raw_model_name=model,
                    score=mean_score,
                    # `release` is the benchmark/question-set version. The
                    # export has no per-model evaluation run date.
                    evaluation_date=None,
                    benchmark_version=release,
                    source_url=f"{SITE_BASE}/",
                    record_verification_status="maintainer_verified",
                    data_file_url=table_url,
                    data_json_path=f"csv: model={model}, 类别={category} 的 {len(scores)} 个任务列",
                    data_sha256=table_sha,
                    upstream_updated_at=snapshot_at,
                    notes=(f"官方排行榜导出；基准版本={release}；任务数={len(scores)}"
                           "（官方类别平均）；上游未提供逐模型评测运行日"),
                ))

        # 官方价格（每百万 Token，美元）
        try:
            cost_body = self.http.get(cost_url)
            cost_rows = list(csv.DictReader(io.StringIO(cost_body.decode("utf-8"))))
            cost_meta = self.http.metadata(cost_url)
            cost_snapshot_at = (
                http_date_to_iso(cost_meta.get("last_modified")) or cost_meta.get("fetched_at")
            )
        except Exception:
            cost_rows = []
            cost_snapshot_at = None
        for row in cost_rows:
            model = (row.get("model") or "").strip()
            if not model:
                continue
            for col, benchmark_id in (
                ("input_price_per_million", "livebench-price-input"),
                ("output_price_per_million", "livebench-price-output"),
            ):
                raw = row.get(col)
                if raw is None or raw == "":
                    continue
                try:
                    price = float(raw)
                except ValueError:
                    continue
                records.append(self.make_record(
                    benchmark_id=benchmark_id,
                    raw_model_name=model,
                    score=price,
                    evaluation_date=None,
                    benchmark_version=release,
                    source_url=f"{SITE_BASE}/",
                    record_verification_status="maintainer_verified",
                    data_file_url=cost_url,
                    data_json_path=f"csv: model={model}, 列={col}",
                    upstream_updated_at=cost_snapshot_at,
                    notes=("LiveBench 官方统计的 API 价格（USD / 1M tokens）；"
                           "基准版本不是逐模型评测日期"),
                ))

        if not records:
            raise AdapterError("LiveBench 导出数据为空")
        return records
