"""BigCodeBench 官方结果适配器（A级）。

数据：HF 数据集 bigcode/bigcodebench-results（官方导出 parquet），
包含 complete / instruct 两种模式下的 pass@1 通过率。
"""
from __future__ import annotations

import io
import math

import pandas as pd

from .base import AdapterError, BaseAdapter

PARQUET_URL = "https://huggingface.co/datasets/bigcode/bigcodebench-results/resolve/main/data/train-00000-of-00001.parquet"

MODEL_COL_CANDIDATES = ["model", "model_id", "model_name", "fullname"]
COMPLETE_COL_CANDIDATES = [
    "complete-pass@1", "complete_pass@1", "complete pass@1",
    "pass@1_complete", "complete",
]
INSTRUCT_COL_CANDIDATES = [
    "instruct-pass@1", "instruct_pass@1", "instruct pass@1",
    "pass@1_instruct", "instruct",
]


class BigCodeBenchAdapter(BaseAdapter):
    source_id = "bigcodebench"

    def fetch_records(self):
        import hashlib

        body = self.http.get(PARQUET_URL)
        data_sha = hashlib.sha256(body).hexdigest()
        df = pd.read_parquet(io.BytesIO(body))

        cols = {c.lower(): c for c in df.columns}
        model_col = next((cols[c] for c in MODEL_COL_CANDIDATES if c in cols), None)
        if not model_col:
            raise AdapterError(f"BigCodeBench parquet 列结构变化: {list(df.columns)[:12]}")

        def find_col(cands):
            for c in cands:
                if c.lower() in cols:
                    return cols[c.lower()]
            return None

        complete_col = find_col(COMPLETE_COL_CANDIDATES)
        instruct_col = find_col(INSTRUCT_COL_CANDIDATES)
        if not (complete_col or instruct_col):
            raise AdapterError(f"未找到 BigCodeBench 分数列: {list(df.columns)[:12]}")

        records = []
        for _, row in df.iterrows():
            model_name = str(row[model_col])
            if not model_name or model_name.lower() == "nan":
                continue
            for col, benchmark_id, mode in (
                (complete_col, "bigcodebench-complete", "complete"),
                (instruct_col, "bigcodebench-instruct", "instruct"),
            ):
                if col is None:
                    continue
                raw = row[col]
                if isinstance(raw, (list, tuple)):
                    raw = raw[0] if len(raw) else None
                try:
                    score = float(raw)
                except (TypeError, ValueError):
                    continue
                if math.isnan(score):
                    continue
                if score <= 1.0 and score > 0:
                    score *= 100.0  # 0-1 比例 -> 百分比
                records.append(
                    self.make_record(
                        benchmark_id=benchmark_id,
                        raw_model_name=model_name,
                        score=score,
                        evaluation_target_type="base_model",
                        prompt_mode=mode,
                        record_verification_status="maintainer_verified",
                        data_file_url=PARQUET_URL,
                        data_json_path=f"parquet: model={model_name}, 列={col}",
                        data_sha256=data_sha,
                        notes=f"模式={mode}（官方结果数据集）",
                    )
                )
        return records
