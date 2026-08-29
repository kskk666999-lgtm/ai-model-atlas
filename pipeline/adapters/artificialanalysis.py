"""Artificial Analysis 免费数据 API 适配器（C级，可选来源）。

- 端点: https://artificialanalysis.ai/api/v2/language/models/free（分页）
- 认证: x-api-key 请求头（仅保存在本地环境变量或 GitHub Actions Secrets）
- 限额: 1000 次/天；页面展示时必须注明来源（见 sources.yml attribution）
- 未配置 API Key 时适配器返回 skipped，其余榜单完全不受影响。
"""
from __future__ import annotations

import os

from .base import AdapterError, BaseAdapter

FREE_MODELS_URL = "https://artificialanalysis.ai/api/v2/language/models/free"
LEGACY_MODELS_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"


class ArtificialAnalysisAdapter(BaseAdapter):
    source_id = "artificialanalysis"

    def fetch_records(self):
        api_key = os.environ.get("AA_API_KEY")
        if not api_key:
            raise AdapterError("未配置 AA_API_KEY（可选数据源，跳过本次更新）")

        data = []
        page = 1
        while True:
            payload = self.http.get_json(f"{FREE_MODELS_URL}?page={page}")
            data.extend(payload.get("data") or [])
            pagination = payload.get("pagination") or {}
            if not pagination.get("has_more") or page >= int(pagination.get("total_pages") or 1):
                break
            page += 1

        if not data:
            # 回退到旧端点（部分缓存环境仍可用）
            legacy = self.http.get_json(LEGACY_MODELS_URL)
            data = legacy.get("data") or []
        if not data:
            raise AdapterError("Artificial Analysis API 返回空数据")

        records = []
        for m in data:
            name = m.get("name")
            if not name:
                continue
            evaluations = m.get("evaluations") or {}
            pricing = m.get("pricing") or {}
            performance = m.get("performance") or {}
            creator = (m.get("model_creator") or {}).get("name")
            release = m.get("release_date")

            def num(v):
                return float(v) if isinstance(v, (int, float)) else None

            ii = num(evaluations.get("artificial_analysis_intelligence_index"))
            speed = num(performance.get("median_output_tokens_per_second"))
            ttft = num(performance.get("median_time_to_first_token_seconds"))
            p_in = num(pricing.get("price_1m_input_tokens"))
            p_out = num(pricing.get("price_1m_output_tokens"))

            for benchmark_id, score in (
                ("aa-intelligence-index", ii),
                ("aa-price-input", p_in),
                ("aa-price-output", p_out),
                ("aa-output-speed", speed),
                ("aa-latency", ttft),
            ):
                if score is None:
                    continue  # 缺失即缺失，不用 0 填充
                records.append(
                    self.make_record(
                        benchmark_id=benchmark_id,
                        raw_model_name=str(name),
                        score=score,
                        evaluation_target_type="api_endpoint",
                        evaluation_date=release,
                        source_url=self.source.homepage_url or "",
                        hardware_or_endpoint=f"creator:{creator}",
                        notes="数据来自 Artificial Analysis 免费数据 API；来源需注明 artificialanalysis.ai",
                    )
                )
        return records
