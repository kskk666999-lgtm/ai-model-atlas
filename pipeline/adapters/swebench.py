"""SWE-bench 官方实验仓库适配器（A级）。

数据：github.com/SWE-bench/experiments 中 evaluation/<split>/<run>/。
- verified / lite / bash-only / multilingual / multimodal 分区
- verified 分区: results/results.json（resolved 实例列表，满分 500）+ metadata.yaml
- 其他分区: metadata.yaml 的 info.resolved
每条运行 = 模型 + Agent 框架 + 推理预算的完整系统，
evaluation_target_type 一律标记为 model_plus_agent，与基础模型榜单分开。
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
from datetime import UTC, datetime

import yaml as pyyaml

from .base import AdapterError, BaseAdapter

TREE_API = "https://api.github.com/repos/SWE-bench/experiments/git/trees/main?recursive=1"
RAW_BASE = "https://raw.githubusercontent.com/SWE-bench/experiments/main/"

SPLIT_TO_BENCHMARK = {
    "verified": "swebench-verified",
    "lite": "swebench-lite",
    "bash-only": "swebench-bash-only",
    "multilingual": "swebench-multilingual",
    "multimodal": "swebench-multimodal",
}
# legacy 数据集版本（旧版 Lite / 完整 test 集）不与现版本混排
SKIPPED_SPLITS = {"lite_20240627", "test", "test_20240627"}

RUN_PATH_RE = re.compile(r"^evaluation/([^/]+)/([^/]+)/metadata\.yaml$")
RUN_DATE_RE = re.compile(r"^(\d{8})_")
VERIFIED_TOTAL = 500


class _RunFetchError(Exception):
    """单条运行的抓取失败（网络/限流），由调用方用 LKG 回补。"""

    def __init__(self, path: str) -> None:
        super().__init__(f"run fetch failed: {path}")
        self.path = path


class SWEBenchAdapter(BaseAdapter):
    source_id = "swebench"

    def fetch_records(self):
        if os.environ.get("GITHUB_TOKEN"):
            self.http._client.headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
        tree = self.http.get_json(TREE_API)
        if tree.get("truncated"):
            raise AdapterError("SWE-bench experiments 目录树被截断，无法保证完整性")
        runs: list[tuple[str, str, str]] = []
        for e in tree.get("tree", []):
            m = RUN_PATH_RE.match(e.get("path", ""))
            if not m:
                continue
            split, run_id = m.group(1), m.group(2)
            if split in SPLIT_TO_BENCHMARK:
                runs.append((split, run_id, m.group(0)))
        if not runs:
            raise AdapterError("SWE-bench experiments 未发现运行记录")

        records: list = []
        failed_paths: list[str] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(self._fetch_run, *r): r for r in runs}
            for fut in concurrent.futures.as_completed(futures):
                try:
                    rec = fut.result()
                except _RunFetchError as e:
                    # 抓取失败（限流/超时）≠ 官方删除。记录路径，稍后用 LKG 回补，
                    # 保证记录集合跨运行确定、输出逐字节稳定。
                    failed_paths.append(e.path)
                    continue
                if rec is not None:
                    records.append(rec)

        if failed_paths:
            lkg_by_url = {r.source_url: r for r in self._load_lkg()}
            for path in failed_paths:
                page_url = "https://github.com/SWE-bench/experiments/tree/main/" + path[
                    : -len("/metadata.yaml")
                ]
                lkg_rec = lkg_by_url.get(page_url)
                if lkg_rec is not None:
                    records.append(lkg_rec)

        # 同一 (benchmark, model, agent_scaffold) 保留最近一次运行；
        # 日期并列时按 run_id 字典序决胜（run_id 以日期开头，字典序即时间序），
        # 消除并发完成顺序带来的不确定性。
        latest: dict[tuple, object] = {}
        for rec in records:
            key = (rec.benchmark_id, rec.model_id, rec.agent_scaffold)
            prev = latest.get(key)
            if prev is None:
                latest[key] = rec
                continue
            prev_run = (prev.source_url or "").rsplit("/", 1)[-1]
            cur_run = (rec.source_url or "").rsplit("/", 1)[-1]
            if ((rec.evaluation_date or ""), cur_run) >= ((prev.evaluation_date or ""), prev_run):
                latest[key] = rec
        return list(latest.values())

    def _fetch_run(self, split: str, run_id: str, path: str):
        try:
            body = self.http.get(RAW_BASE + path)
        except Exception as e:
            raise _RunFetchError(path) from e
        try:
            meta = pyyaml.safe_load(body.decode("utf-8")) or {}
        except Exception:
            return None  # 内容损坏视为该运行无效
        import hashlib

        meta_sha = hashlib.sha256(body).hexdigest()
        meta_url = RAW_BASE + path

        info = meta.get("info") or {}
        tags = meta.get("tags") or {}

        if split == "verified":
            try:
                score = self._verified_score(run_id, path)
            except Exception as e:
                raise _RunFetchError(path) from e
            verified_flag = meta.get("verified")
        else:
            resolved = info.get("resolved")
            score = float(resolved) if isinstance(resolved, (int, float)) else None
            verified_flag = tags.get("checked", True)
        if score is None:
            return None
        if verified_flag is False:
            return None  # 官方未核验的运行不上榜

        raw_model, model_source = self._model_name(tags, meta, run_id)
        if not raw_model:
            return None
        date_match = RUN_DATE_RE.match(run_id)
        evaluation_date = (
            datetime.strptime(date_match.group(1), "%Y%m%d")
            .replace(tzinfo=UTC).strftime("%Y-%m-%d")
            if date_match else None
        )
        agent = str(tags.get("agent") or "unknown")
        attempts = (tags.get("system") or {}).get("attempts")
        agent_scaffold = f"{agent} (attempts={attempts})" if attempts else agent

        rec = self.make_record(
            benchmark_id=SPLIT_TO_BENCHMARK[split],
            raw_model_name=raw_model,
            score=score,
            evaluation_target_type="model_plus_agent",
            agent_scaffold=agent_scaffold,
            evaluation_date=evaluation_date,
            source_url=f"https://github.com/SWE-bench/experiments/tree/main/evaluation/{split}/{run_id}",
            record_verification_status="maintainer_verified",
            data_file_url=meta_url,
            data_json_path=("metadata.yaml: info.resolved" if split != "verified"
                            else "results/results.json: len(resolved) / 500"),
            data_sha256=meta_sha,
            prompt_mode=f"pass@{attempts}" if attempts else None,
            hardware_or_endpoint=f"agent:{agent}",
            notes=(
                f"run={run_id}; name={meta.get('name')}; model_name_from={model_source}; "
                f"cost_usd={info.get('cost')}; os_model={tags.get('os_model')}; "
                f"oss={meta.get('oss')}"
            ),
        )
        return rec

    def _model_name(self, tags: dict, meta: dict, run_id: str = "") -> tuple[str, str]:
        model_tags = tags.get("model") or []
        raw = str(model_tags[0]) if model_tags else ""
        if raw:
            # 官方 run 目录名可能携带 tags.model 省略的变体后缀（如 -high / -xhigh），
            # 这是官方元数据，可确定性恢复，避免同模型不同配置被错误合并。
            for token in run_id.split("_")[1:]:
                if token.startswith(raw + "-") and re.fullmatch(r"[a-z0-9._-]+", token):
                    return token, "run_id_variant"
            return raw, "tags.model"
        if tags.get("model_display"):
            return str(tags["model_display"]), "model_display"
        name = meta.get("name")
        if name and "+" in str(name):
            return str(name).split("+", 1)[1].strip(), "run_name"
        return "", ""

    def _verified_score(self, run_id: str, meta_path: str) -> float | None:
        base = meta_path.rsplit("/", 1)[0]
        try:
            payload = json.loads(
                self.http.get(f"{RAW_BASE}{base}/results/results.json").decode("utf-8"))
        except Exception:
            return None
        resolved = payload.get("resolved")
        if not isinstance(resolved, list):
            return None
        return round(len(resolved) * 100.0 / VERIFIED_TOTAL, 3)
