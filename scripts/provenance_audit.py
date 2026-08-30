"""数据溯源审计：随机抽取成绩，回到官方来源逐条重新比对。

产出 data/reports/provenance-audit.{json,md}。
- 覆盖全部 5 个有效来源、≥5 模型、≥6 能力、基础模型/变体/Agent 系统
- 每条记录：重新从官方源拉取原始数据，比对分数是否一致
- 检查项：来源 URL 可达性、模拟/fixture 泄漏、无来源 URL、重复行
"""
from __future__ import annotations

import csv
import io
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.utils.http import HttpClient  # noqa: E402

SAMPLE_N = 22
SEED = 20260830


def load_all_rows() -> list[dict]:
    rows = []
    for f in (PROJECT_ROOT / "public/data/benchmarks").glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        rows.extend(d.get("rows") or [])
    return rows


def verify_livebench(row: dict, http: HttpClient) -> tuple[bool, str]:
    release = row.get("benchmark_version") or row.get("evaluation_date")
    token = str(release).replace("-", "_")
    cat_bench = {
        "livebench-reasoning": "Reasoning", "livebench-coding": "Coding",
        "livebench-agentic-coding": "Agentic Coding", "livebench-mathematics": "Mathematics",
        "livebench-data-analysis": "Data Analysis", "livebench-language": "Language",
        "livebench-instruction-following": "IF", "livebench-social": "Social",
    }
    if row["benchmark_id"] in ("livebench-price-input", "livebench-price-output"):
        cost = csv.DictReader(io.StringIO(
            http.get(f"https://livebench.ai/cost_{token}.csv").decode("utf-8")))
        field = "input_price_per_million" if row["benchmark_id"] == "livebench-price-input" else "output_price_per_million"
        target0 = row["raw_model_name"] or row["model_id"]
        for r in cost:
            if (r.get("model") or "").strip() == target0:
                expected = float(r[field])
                ok = abs(expected - row["score"]) < 0.0001
                return ok, f"官方 cost CSV {field}={expected}，站点={row['score']}"
        return False, f"官方 cost CSV 未找到 {target0}"
    cat = cat_bench[row["benchmark_id"]]
    categories = json.loads(http.get(f"https://livebench.ai/categories_{token}.json").decode("utf-8"))
    tasks = categories[cat]
    table = csv.DictReader(io.StringIO(
        http.get(f"https://livebench.ai/table_{token}.csv").decode("utf-8")))
    target = row["raw_model_name"] or row["model_id"]
    for r in table:
        if (r.get("model") or "").strip() == target:
            scores = [float(r[t]) for t in tasks if r.get(t) not in (None, "")]
            expected = sum(scores) / len(scores)
            ok = abs(expected - row["score"]) < 0.051
            return ok, f"官方表 {target} 在 {cat} 的均值={expected:.3f}，站点={row['score']}"
    return False, f"官方表未找到模型 {target}"


def verify_swebench(row: dict, http: HttpClient) -> tuple[bool, str]:
    url = row["source_url"]
    # .../tree/main/evaluation/<split>/<run> -> raw metadata 路径
    tail = url.split("/tree/main/")[-1]
    meta_url = f"https://raw.githubusercontent.com/SWE-bench/experiments/main/{tail}/metadata.yaml"
    import yaml as pyyaml

    meta = pyyaml.safe_load(http.get(meta_url).decode("utf-8")) or {}
    if tail.startswith("evaluation/verified/"):
        res_url = f"https://raw.githubusercontent.com/SWE-bench/experiments/main/{tail}/results/results.json"
        resolved = json.loads(http.get(res_url).decode("utf-8")).get("resolved") or []
        expected = round(len(resolved) * 100.0 / 500, 3)
    else:
        expected = float((meta.get("info") or {}).get("resolved"))
    ok = abs(expected - row["score"]) < 0.01
    return ok, f"官方 metadata resolved={expected}，站点={row['score']}"


def verify_bigcodebench(row: dict, http: HttpClient) -> tuple[bool, str]:
    import pandas as pd

    body = http.get("https://huggingface.co/datasets/bigcode/bigcodebench-results/resolve/main/data/train-00000-of-00001.parquet")
    df = pd.read_parquet(io.BytesIO(body))
    target = row["raw_model_name"] or row["model_id"]
    col = {c.lower(): c for c in df.columns}
    model_col = next(col[c] for c in ("model", "model_id", "model_name", "fullname") if c in col)
    match = df[df[model_col].astype(str) == target]
    if match.empty:
        return False, f"官方数据集未找到模型 {target}"
    mode = row.get("prompt_mode") or "complete"
    score_col = next((col[c] for c in (f"{mode}-pass@1", f"{mode}_pass@1", mode) if c in col), None)
    if score_col is None:
        return False, f"官方 parquet 无分数列 {mode}（现有列：{list(df.columns)[:10]}）"
    raw = match.iloc[0][score_col]
    if isinstance(raw, (list, tuple)):
        raw = raw[0]
    expected = float(raw)
    if expected <= 1.0:
        expected *= 100.0
    ok = abs(expected - row["score"]) < 0.01
    return ok, f"官方 parquet {mode}-pass@1={expected:.3f}，站点={row['score']}"


def verify_vlmevalkit(row: dict, http: HttpClient) -> tuple[bool, str]:
    data = json.loads(http.get("http://opencompass.openxlab.space/assets/OpenVLM.json").decode("utf-8"))
    target = row["raw_model_name"] or row["model_id"]
    entry = data["results"].get(target)
    if entry is None:
        return False, f"官方 OpenVLM.json 未找到 {target}"
    bench_key = {
        "ovl-mmbench-test-cn-v11": "MMBench_TEST_CN_V11", "ovl-mmbench-test-en-v11": "MMBench_TEST_EN_V11",
        "ovl-mmmu-val": "MMMU_VAL", "ovl-mathvista": "MathVista", "ovl-ocrbench": "OCRBench",
        "ovl-mme": "MME", "ovl-mmvet": "MMVet", "ovl-seedbench-img": "SEEDBench_IMG",
        "ovl-ccbench": "CCBench", "ovl-mmstar": "MMStar", "ovl-realworldqa": "RealWorldQA",
        "ovl-ai2d": "AI2D", "ovl-scienceqa-test": "ScienceQA_TEST", "ovl-hallusionbench": "HallusionBench",
        "ovl-mmt-bench-val": "MMT-Bench_VAL", "ovl-blink": "BLINK", "ovl-qbench": "QBench", "ovl-abench": "ABench",
    }.get(row["benchmark_id"])
    expected = entry.get(bench_key, {}).get("Overall")
    if expected == "N/A" or expected is None:
        return False, f"官方 {bench_key} Overall 缺失"
    expected = float(expected)
    ok = abs(expected - row["score"]) < 0.051
    return ok, f"官方 {bench_key} Overall={expected}，站点={row['score']}"


def verify_mteb(row: dict, http: HttpClient) -> tuple[bool, str]:
    url = row["source_url"]
    if "/blob/" in url:
        url = url.replace("/blob/", "/raw/")
    url = url.replace("https://github.com/embeddings-benchmark/results/tree", "https://raw.githubusercontent.com/embeddings-benchmark/results")
    payload = json.loads(http.get(url).decode("utf-8"))
    expected = None
    for split in ("test", "dev", "validation"):
        arr = (payload.get("scores") or {}).get(split) or []
        if arr and isinstance(arr[0].get("main_score"), (int, float)):
            expected = float(arr[0]["main_score"])
            break
    if expected is None:
        return False, "官方任务 JSON 无 main_score"
    ok = abs(expected - row["score"]) < 1e-6
    return ok, f"官方 main_score={expected}，站点={row['score']}"


VERIFIERS = {
    "livebench": verify_livebench,
    "swebench": verify_swebench,
    "bigcodebench": verify_bigcodebench,
    "vlmevalkit": verify_vlmevalkit,
    "mteb": verify_mteb,
}


def main() -> int:
    rng = random.Random(SEED)
    rows = load_all_rows()
    # 分层抽样：每个来源至少 3 条，保证类型/模型/能力多样性
    by_source: dict[str, list[dict]] = {}
    for r in rows:
        by_source.setdefault(r["source_id"], []).append(r)
    sample: list[dict] = []
    for _sid, lst in sorted(by_source.items()):
        rng.shuffle(lst)
        sample.extend(lst[:4])
    while len(sample) < SAMPLE_N:
        sample.append(rng.choice(rows))
    sample = sample[:SAMPLE_N]

    http = HttpClient(timeout=40)
    results = []
    seen_keys = set()
    dup = 0
    no_url = 0
    for r in rows:
        key = (r["source_id"], r["benchmark_id"], r["model_id"], r["raw_model_name"],
               r.get("agent_scaffold"), r.get("benchmark_version"), r["score"])
        if key in seen_keys:
            dup += 1
        seen_keys.add(key)
        if not r.get("source_url"):
            no_url += 1

    url_fail = []
    for r in sample:
        sid = r["source_id"]
        verifier = VERIFIERS.get(sid)
        url_ok = True
        u = r.get("source_url") or ""
        if u.startswith("http"):
            try:
                http.get(u)
            except Exception:
                url_ok = False
                url_fail.append(u)
        entry = {
            "source_id": sid,
            "benchmark_id": r["benchmark_id"],
            "model_id": r["model_id"],
            "raw_model_name": r.get("raw_model_name"),
            "model_variant": None,
            "evaluation_target_type": r["evaluation_target_type"],
            "score_site": r["score"],
            "score_unit": r["score_unit"],
            "evaluation_date": r.get("evaluation_date"),
            "benchmark_version": r.get("benchmark_version"),
            "source_url": u,
            "source_url_reachable": url_ok,
            "fetched_at": r.get("fetched_at"),
            "agent_scaffold": r.get("agent_scaffold"),
            "in_composite": False,
        }
        if verifier:
            try:
                ok, msg = verifier(r, http)
            except Exception as e:
                ok, msg = False, f"核验异常: {type(e).__name__}: {e}"
            entry["verified"] = ok
            entry["detail"] = msg
        else:
            entry["verified"] = None
            entry["detail"] = "该来源无自动核验器（可选来源）"
        results.append(entry)
    http.close()

    # fixture/模拟数据泄漏扫描
    leak_hits = []
    for f in (PROJECT_ROOT / "public/data").rglob("*.json"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        for bad in ("test-model-a", "test-model-b", "fixture", '"demo_model"', "mock-model"):
            if bad in text:
                leak_hits.append(f"{f.relative_to(PROJECT_ROOT)}: {bad}")

    n_ok = sum(1 for e in results if e["verified"] is True)
    n_bad = sum(1 for e in results if e["verified"] is False)
    report = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": SEED,
        "total_records_in_site": len(rows),
        "sampled": len(results),
        "verified_ok": n_ok,
        "verified_fail": n_bad,
        "duplicate_rows_in_site": dup,
        "rows_without_source_url": no_url,
        "mock_fixture_leaks": leak_hits,
        "unreachable_source_urls": url_fail,
        "samples": results,
    }
    out = PROJECT_ROOT / "data/reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "provenance-audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = [
        "# 数据溯源审计报告",
        "",
        f"- 站点成绩总数：{len(rows)}；抽样：{len(results)}（seed={SEED}）",
        f"- 自动核验通过：**{n_ok}** / {n_ok + n_bad}",
        f"- 全站重复行：{dup}；无来源 URL 行：{no_url}",
        f"- 模拟数据/fixture 泄漏：{len(leak_hits)} 处 {'✅' if not leak_hits else '❌ ' + str(leak_hits[:5])}",
        f"- 不可达来源 URL：{len(url_fail)} 个",
        "",
        "| 来源 | 基准 | 模型 | 站点分 | 官方核验 | 说明 |",
        "|---|---|---|---|---|---|",
    ]
    for e in results:
        mark = "✅" if e["verified"] is True else ("❌" if e["verified"] is False else "—")
        lines.append(
            f"| {e['source_id']} | {e['benchmark_id']} | {e['raw_model_name'] or e['model_id']} "
            f"| {e['score_site']} | {mark} | {e['detail']} |"
        )
    (out / "provenance-audit.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"抽样 {len(results)}：通过 {n_ok}，失败 {n_bad}；泄漏 {len(leak_hits)}；无URL {no_url}；重复 {dup}")
    for e in results:
        if e["verified"] is False:
            print("  FAIL:", e["source_id"], e["benchmark_id"], e["raw_model_name"], "-", e["detail"])
    return 0 if n_bad == 0 and not leak_hits else 1


if __name__ == "__main__":
    sys.exit(main())
