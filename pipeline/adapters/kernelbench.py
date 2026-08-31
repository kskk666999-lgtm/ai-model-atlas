"""KernelBench.com v-hard GPU 内核工程榜适配器（C 级公开审计榜）。

该榜测试模型在固定 GPU 内核任务集上的 Agent 式工程能力。聚合分母固定为
完整问题数；未尝试任务不当作成功，reward-hack 等无效结果也不会计入通过数。
"""
from __future__ import annotations

import hashlib
import re

from ..utils.http import http_date_to_iso
from .base import AdapterError, BaseAdapter

DATA_URL = (
    "https://raw.githubusercontent.com/Infatoshi/kernelbench.com/master/"
    "benchmarks/hard/results/leaderboard.json"
)
COMMITS_URL = (
    "https://api.github.com/repos/Infatoshi/kernelbench.com/commits"
    "?path=benchmarks/hard/results/leaderboard.json&per_page=1"
)
SOURCE_PAGE = "https://kernelbench.com/"
VALID_VERDICTS = {"clean", "interesting"}
RUN_DATE_RE = re.compile(r"^(20\d{2})(\d{2})(\d{2})_")


def _run_date(results: dict) -> str | None:
    dates = []
    for result in results.values():
        match = RUN_DATE_RE.match(str(result.get("run_id") or ""))
        if match:
            dates.append(f"{match.group(1)}-{match.group(2)}-{match.group(3)}")
    return max(dates) if dates else None


class KernelBenchAdapter(BaseAdapter):
    source_id = "kernelbench"

    def _commit_metadata(self) -> tuple[str | None, str | None]:
        try:
            payload = self.http.get_json(COMMITS_URL)
            first = payload[0]
            return first.get("sha"), first.get("commit", {}).get("committer", {}).get("date")
        except Exception:
            metadata = self.http.metadata(DATA_URL)
            return None, (
                http_date_to_iso(metadata.get("last_modified")) or metadata.get("fetched_at")
            )

    def fetch_records(self):
        import json

        body = self.http.get(DATA_URL)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdapterError(f"KernelBench JSON 解析失败: {exc}") from exc
        if not isinstance(payload, dict):
            raise AdapterError("KernelBench 根结构不是对象")
        problems = payload.get("problems")
        models = payload.get("models")
        if not isinstance(problems, list) or not problems:
            raise AdapterError("KernelBench 缺少固定问题清单")
        if not isinstance(models, list) or not models:
            raise AdapterError("KernelBench 缺少模型成绩")

        data_sha = hashlib.sha256(body).hexdigest()
        source_sha, snapshot_at = self._commit_metadata()
        hardware = payload.get("hardware") or {}
        hardware_label = (
            f"{hardware.get('name', '未标注')} / {hardware.get('sm', '未知架构')} / "
            f"{hardware.get('vram_gb', '未知')}GB"
        )
        version_tag = (payload.get("generated_from_summary") or {}).get("tag") or "unknown"
        expected = len(problems)

        records = []
        for index, model in enumerate(models):
            if not isinstance(model, dict):
                raise AdapterError(f"KernelBench models[{index}] 不是对象")
            label = str(model.get("label") or "").strip()
            normalization_name = str(model.get("model") or "").strip()
            harness = str(model.get("harness") or "").strip()
            effort = str(model.get("effort") or "").strip() or None
            results = model.get("results")
            if not label or not normalization_name or not harness or not isinstance(results, dict):
                raise AdapterError(f"KernelBench models[{index}] 缺少身份或 results")

            attempted = len(results)
            declared_runs = int(model.get("total_runs") or 0)
            if declared_runs != attempted:
                raise AdapterError(
                    f"KernelBench {label} total_runs={declared_runs}，实际结果={attempted}"
                )
            valid_passes = sum(
                1
                for result in results.values()
                if result.get("correct") is True
                and str(result.get("annotation_verdict") or "").lower() in VALID_VERDICTS
            )
            declared_passes = int(model.get("pass_count") or 0)
            if declared_passes != valid_passes:
                raise AdapterError(
                    f"KernelBench {label} pass_count={declared_passes}，审计重算={valid_passes}"
                )
            invalid = sum(
                1
                for result in results.values()
                if result.get("invalid_reason")
                or str(result.get("annotation_verdict") or "").lower() == "reward_hack"
            )
            score = valid_passes / expected * 100.0
            variant = f"{harness}:{effort or 'default'}"
            records.append(
                self.make_record(
                    benchmark_id="kernelbench-v-hard",
                    raw_model_name=label,
                    normalization_name=normalization_name,
                    score=score,
                    benchmark_version=f"v-hard-{version_tag}",
                    evaluation_date=_run_date(results),
                    published_at=snapshot_at,
                    source_commit_sha=source_sha,
                    model_variant=variant,
                    evaluation_target_type="model_plus_agent",
                    reasoning_effort=effort,
                    agent_scaffold=harness,
                    hardware_or_endpoint=hardware_label,
                    sample_size=attempted,
                    record_verification_status="maintainer_verified",
                    data_file_url=DATA_URL,
                    data_json_path=f"$.models[{index}]",
                    data_sha256=data_sha,
                    upstream_updated_at=snapshot_at,
                    source_url=SOURCE_PAGE,
                    notes=(
                        f"固定完整题集={expected}；有效通过={valid_passes}/{expected}；"
                        f"实际尝试={attempted}；无效/reward-hack={invalid}。"
                        "未尝试题不会被包装成通过，分数可在不同完成度记录间直接比较"
                    ),
                )
            )

        return records
