"""Terminal-Bench 4.0 official leaderboard adapter.

The public page is server rendered. Its Next.js hydration payload contains a
typed leaderboard object, so no browser automation or private API is needed.
The leaderboard exposes model release dates and row/snapshot timestamps, but
not per-run evaluation dates; those semantics stay separate in our schema.
"""
from __future__ import annotations

import hashlib
import json
import re

from .base import AdapterError, BaseAdapter

LEADERBOARD_URL = "https://www.tbench.ai/?version=4.0"
SCRIPT_RE = re.compile(r"<script>self\.__next_f\.push\((.*?)\)</script>", re.DOTALL)


def _extract_payload(html: str) -> dict:
    chunks: list[str] = []
    for encoded in SCRIPT_RE.findall(html):
        try:
            frame = json.loads(encoded)
        except json.JSONDecodeError:
            continue
        if isinstance(frame, list) and len(frame) > 1 and isinstance(frame[1], str):
            chunks.append(frame[1])
    stream = "".join(chunks)
    marker = '{"leaderboard":'
    start = stream.find(marker)
    if start < 0:
        raise AdapterError("Terminal-Bench 页面中未找到官方 leaderboard 数据")
    try:
        payload, _ = json.JSONDecoder().raw_decode(stream[start:])
    except json.JSONDecodeError as exc:
        raise AdapterError(f"Terminal-Bench leaderboard JSON 解析失败: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise AdapterError("Terminal-Bench leaderboard 结构变化：缺少 rows")
    return payload


class TerminalBenchAdapter(BaseAdapter):
    source_id = "terminalbench"

    def fetch_records(self):
        body = self.http.get(LEADERBOARD_URL)
        sha = hashlib.sha256(body).hexdigest()
        payload = _extract_payload(body.decode("utf-8", "ignore"))
        board = payload.get("leaderboard") or {}
        version = str(board.get("name") or "4-0-0")
        title = str(board.get("title") or "Terminal-Bench 4.0")
        board_updated_at = board.get("updated_at")

        records = []
        for row in payload["rows"]:
            if not isinstance(row, dict) or row.get("status") not in (None, "display"):
                continue
            metadata = row.get("metadata") or {}
            metrics = row.get("metrics") or {}
            model = (metadata.get("model_display") or {}).get("label")
            agent = (metadata.get("agent_display") or {}).get("label")
            score = metrics.get("accuracy")
            if not model or not agent or not isinstance(score, (int, float)):
                continue
            ci = metrics.get("accuracy_ci95_half_width")
            ci_low = max(0.0, float(score) - float(ci)) if isinstance(ci, (int, float)) else None
            ci_high = min(100.0, float(score) + float(ci)) if isinstance(ci, (int, float)) else None
            effort = str(metadata.get("reasoning_effort") or "").strip() or None
            row_id = str(row.get("id") or row.get("rank") or model)
            updated_at = row.get("updated_at") or board_updated_at
            model_release = metadata.get("release_date") or metadata.get("date")
            records.append(self.make_record(
                benchmark_id="terminalbench-4",
                raw_model_name=str(model),
                score=float(score),
                benchmark_version=version,
                model_variant=effort,
                evaluation_target_type="complete_agent_system",
                evaluation_date=None,
                published_at=row.get("created_at") or board.get("created_at"),
                reasoning_effort=effort,
                agent_scaffold=str(agent),
                sample_size=int(metrics.get("n_trials") or row.get("n_trials") or 0) or None,
                confidence_interval_low=ci_low,
                confidence_interval_high=ci_high,
                source_url=LEADERBOARD_URL,
                data_file_url=LEADERBOARD_URL,
                data_json_path=f"hydration: rows[id={row_id}]",
                data_sha256=sha,
                upstream_updated_at=updated_at,
                record_verification_status="maintainer_verified",
                notes=(f"{title} 官方完整 Agent 系统成绩；模型发布日期={model_release or '未提供'}；"
                       "上游未提供逐条评测运行日"),
            ))
        if not records:
            raise AdapterError("Terminal-Bench 官方榜单无有效记录")
        return records
