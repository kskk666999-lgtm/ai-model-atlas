"""MTEB 官方结果仓库适配器（A级）。

数据：github.com/embeddings-benchmark/results 中按模型按任务保存的官方 JSON。
为控制 GitHub API 用量，仅抓取注册表中登记的 embedding 模型 + 一组代表性任务。
"""
from __future__ import annotations

import concurrent.futures
import os
import re

from .base import AdapterError, BaseAdapter

CONTENTS_API = "https://api.github.com/repos/embeddings-benchmark/results/contents/results/{model_dir}"
RAW_BASE = "https://raw.githubusercontent.com/embeddings-benchmark/results/main/results/{model_dir}/{revision}/{task}.json"

# 注册表 canonical_id -> results 仓库中的目录名（org__model）
MODEL_DIRS = {
    "bge-m3": "BAAI__bge-m3",
    "multilingual-e5-large-instruct": "intfloat__multilingual-e5-large-instruct",
    "gte-qwen2-7b-instruct": "Alibaba-NLP__gte-Qwen2-7B-instruct",
    "text-embedding-3-large": "openai__text-embedding-3-large",
    "voyage-3-large": "voyageai__voyage-3-large",
    "jina-embeddings-v3": "jinaai__jina-embeddings-v3",
    "qwen3-embedding-8b": "Qwen__Qwen3-Embedding-8B",
    "nomic-embed-text-v1.5": "nomic-ai__nomic-embed-text-v1.5",
}

# benchmark_id -> results 仓库中的任务文件名（无 .json 后缀）
TASK_FILES = {
    "mteb-nfcorpus": "NFCorpus",
    "mteb-scifact": "SciFact",
    "mteb-arguana": "ArguAna",
    "mteb-trec-covid": "TREC-COVID",
    "mteb-sts17": "STS17",
    "mteb-stsbenchmark": "STSBenchmark",
    "mteb-askubuntudupquestions": "AskUbuntuDupQuestions",
    "mteb-scidoCSrr": "SciDocsRR",
}

SPLIT_ORDER = ["test", "dev", "validation"]
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


class MTEBAdapter(BaseAdapter):
    source_id = "mteb"

    def fetch_records(self):
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            self.http._client.headers["Authorization"] = f"Bearer {token}"

        records = []
        tasks: list = []
        for canonical_id, model_dir in MODEL_DIRS.items():
            try:
                dirs = self.http.get_json(CONTENTS_API.format(model_dir=model_dir))
            except Exception as e:
                raise AdapterError(f"无法列出 {model_dir} 的版本目录: {e}") from e
            revisions = [
                d["name"] for d in dirs if d.get("type") == "dir"
                and (REVISION_RE.match(d["name"]) or d["name"] == "None")
            ]
            if not revisions:
                continue
            revision = revisions[-1]
            for benchmark_id, task_file in TASK_FILES.items():
                tasks.append((canonical_id, model_dir, revision, benchmark_id, task_file))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(self._fetch_task, *t) for t in tasks]
            for fut in concurrent.futures.as_completed(futures):
                rec = fut.result()
                if rec is not None:
                    records.append(rec)
        return records

    def _fetch_task(self, canonical_id: str, model_dir: str, revision: str, benchmark_id: str, task_file: str):
        url = RAW_BASE.format(model_dir=model_dir, revision=revision, task=task_file)
        try:
            payload = self.http.get_json(url)
        except Exception:
            return None  # 单个任务缺失跳过
        scores = payload.get("scores") or {}
        main_score = None
        for split in SPLIT_ORDER:
            arr = scores.get(split)
            if isinstance(arr, list) and arr:
                cand = arr[0].get("main_score")
                if isinstance(cand, (int, float)):
                    main_score = float(cand)
                    break
        if main_score is None:
            return None
        return self.make_record(
            benchmark_id=benchmark_id,
            raw_model_name=canonical_id,  # 已是 canonical_id，直接复用注册表别名
            score=main_score,
            evaluation_target_type="embedding_model" if "sts" not in benchmark_id else "embedding_model",
            source_commit_sha=revision if REVISION_RE.match(revision) else None,
            source_url=f"https://github.com/embeddings-benchmark/results/tree/main/results/{model_dir}/{revision}/{task_file}.json",
            notes=f"task={task_file}; revision={revision}",
        )
