"""Berkeley Function Calling Leaderboard V4 official CSV adapter."""
from __future__ import annotations

import csv
import hashlib
import io
import re

from ..utils.http import http_date_to_iso
from .base import AdapterError, BaseAdapter

CSV_URL = "https://gorilla.cs.berkeley.edu/data_overall.csv"
LEADERBOARD_URL = "https://gorilla.cs.berkeley.edu/leaderboard.html"
MODE_RE = re.compile(r"^(.*?)\s+\(([^()]*)\)\s*$")

METRICS = (
    ("Overall Acc", "bfcl-v4-overall"),
    ("Web Search Acc", "bfcl-v4-web-search"),
    ("Memory Acc", "bfcl-v4-memory"),
)


def _percent(value: str | None) -> float | None:
    text = str(value or "").strip()
    if not text or text.upper() == "N/A":
        return None
    try:
        return float(text.removesuffix("%"))
    except ValueError:
        return None


class BFCLAdapter(BaseAdapter):
    source_id = "bfcl"

    def fetch_records(self):
        body = self.http.get(CSV_URL)
        sha = hashlib.sha256(body).hexdigest()
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
        meta = self.http.metadata(CSV_URL)
        snapshot_at = http_date_to_iso(meta.get("last_modified")) or meta.get("fetched_at")
        records = []
        for row_number, row in enumerate(rows, start=2):
            raw_model = str(row.get("Model") or "").strip()
            if not raw_model:
                continue
            match = MODE_RE.match(raw_model)
            base_model = match.group(1).strip() if match else raw_model
            prompt_mode = match.group(2).strip() if match else None
            for column, benchmark_id in METRICS:
                score = _percent(row.get(column))
                if score is None:
                    continue
                records.append(self.make_record(
                    benchmark_id=benchmark_id,
                    raw_model_name=raw_model,
                    normalization_name=base_model,
                    score=score,
                    benchmark_version="BFCL V4",
                    model_variant=prompt_mode,
                    evaluation_target_type="model_variant",
                    evaluation_date=None,
                    prompt_mode=prompt_mode,
                    source_url=LEADERBOARD_URL,
                    data_file_url=CSV_URL,
                    data_json_path=f"csv: row={row_number}, column={column}, model={raw_model}",
                    data_sha256=sha,
                    upstream_updated_at=snapshot_at,
                    record_verification_status="maintainer_verified",
                    license=row.get("License") or None,
                    notes=("BFCL V4 官方导出；FC/Prompt/Thinking 模式独立保留；"
                           "上游未提供逐模型评测运行日"),
                ))
        if not records:
            raise AdapterError("BFCL V4 官方 CSV 无有效记录")
        return records
