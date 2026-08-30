"""VLMEvalKit / OpenVLM 官方结果适配器（A级）。

数据：OpenCompass 官方资产 OpenVLM.json（opencompass.openxlab.space/assets/OpenVLM.json），
由 VLMEvalKit 官方维护，包含 200+ 模型 × 多个多模态基准的 Overall 分数。
"""
from __future__ import annotations

import json

from .base import AdapterError, BaseAdapter

OPENVLM_URL = "http://opencompass.openxlab.space/assets/OpenVLM.json"

# OpenVLM.json 基准名 -> benchmarks.yml benchmark_id
# 同一基准的新旧版本只取其一（优先 V11），避免重复计数。
BENCHMARK_MAP = {
    "MMBench_TEST_CN_V11": "ovl-mmbench-test-cn-v11",
    "MMBench_TEST_CN": "ovl-mmbench-test-cn-v11",  # 回退：无 V11 时用旧版
    "MMBench_TEST_EN_V11": "ovl-mmbench-test-en-v11",
    "MMBench_TEST_EN": "ovl-mmbench-test-en-v11",
    "MMMU_VAL": "ovl-mmmu-val",
    "MathVista": "ovl-mathvista",
    "OCRBench": "ovl-ocrbench",
    "MME": "ovl-mme",
    "MMVet": "ovl-mmvet",
    "SEEDBench_IMG": "ovl-seedbench-img",
    "CCBench": "ovl-ccbench",
    "MMStar": "ovl-mmstar",
    "RealWorldQA": "ovl-realworldqa",
    "AI2D": "ovl-ai2d",
    "ScienceQA_TEST": "ovl-scienceqa-test",
    "HallusionBench": "ovl-hallusionbench",
    "MMT-Bench_VAL": "ovl-mmt-bench-val",
    "BLINK": "ovl-blink",
    "QBench": "ovl-qbench",
    "ABench": "ovl-abench",
}


class VLMEvalKitAdapter(BaseAdapter):
    source_id = "vlmevalkit"

    def fetch_records(self):
        import hashlib

        raw = self.http.get(OPENVLM_URL)
        data_sha = hashlib.sha256(raw).hexdigest()
        data = json.loads(raw.decode("utf-8"))
        results = data.get("results")
        if not isinstance(results, dict) or not results:
            raise AdapterError("OpenVLM.json 结构变化：缺少 results")
        upstream_ts = str(data.get("time") or "") or None

        records = []
        for model_name, entry in results.items():
            meta = entry.get("META") or {}
            eval_date = (meta.get("Time") or "").replace("/", "-") or None
            org = meta.get("Org")
            method_url = ""
            method_field = meta.get("Method")
            if isinstance(method_field, list) and len(method_field) > 1:
                method_url = str(method_field[1] or "")

            # 记录级可信度：官方维护者复现 vs 官方平台收录的第三方提交
            # Verified=yes -> maintainer_verified；no/缺失 -> 不进入严格榜
            verified_raw = str(meta.get("Verified", "")).strip().lower()
            if verified_raw == "yes":
                verification = "maintainer_verified"
            elif verified_raw == "no":
                verification = "third_party_submitted"
            else:
                verification = "unknown"

            # detail-high / detail-low 是官方评测设置差异，必须作为变体区分保留
            variant = None
            for token in ("detail-high", "detail-low"):
                if token in model_name:
                    variant = token

            for bench_key, benchmark_id in BENCHMARK_MAP.items():
                bench_scores = entry.get(bench_key)
                if not isinstance(bench_scores, dict):
                    continue
                # 存在 V11 版本时跳过旧版，避免同基准重复
                if bench_key == "MMBench_TEST_CN" and "MMBench_TEST_CN_V11" in entry:
                    continue
                if bench_key == "MMBench_TEST_EN" and "MMBench_TEST_EN_V11" in entry:
                    continue
                overall = bench_scores.get("Overall")
                if isinstance(overall, str):
                    if overall == "N/A":
                        continue
                    try:
                        overall = float(overall)
                    except ValueError:
                        continue
                if not isinstance(overall, (int, float)):
                    continue
                score = float(overall)
                # OCRBench 官方满分 1000，存储原始绝对值
                if benchmark_id == "ovl-ocrbench" and score <= 1.0:
                    score *= 1000.0

                rec = self.make_record(
                    benchmark_id=benchmark_id,
                    raw_model_name=model_name,
                    score=score,
                    model_variant=variant,
                    evaluation_date=eval_date,
                    source_url=method_url or self.source.homepage_url or "",
                    record_verification_status=verification,
                    data_file_url=OPENVLM_URL,
                    data_json_path=f'results["{model_name}"]["{bench_key}"]["Overall"]',
                    data_sha256=data_sha,
                    upstream_updated_at=upstream_ts,
                    benchmark_version="v11" if bench_key.endswith("V11") else None,
                    notes=(
                        f"官方复现汇总；Org={org}; Verified={verified_raw or 'unknown'}"
                    ),
                )
                if rec.model_is_unmapped and org and "(" not in model_name:
                    # 尝试 "Org 简称" 组合的确定性重试（不加任何猜测后缀）
                    rec.notes = (rec.notes or "") + f"; raw={model_name}"
                records.append(rec)
        return records
