"""LKG 回退故障演练：在完全隔离的沙箱中模拟故障，验证回退与数据保全。

设计对齐 CI 真实场景：全部为【全量运行 + 故障注入】。
- 单来源网络失败 / 解析失败 / 空数据 → 该来源降级 LKG；榜单数据逐字节不变；
  仅 meta.json / source-health.json 允许变化（健康状态本应反映失败）
- 全部来源失败 → 榜单数据逐字节不变
- 核心校验失败 → 退出码 2，public/data 任何文件都不变
- 沙箱：public/data、LKG、历史快照全部重定向到临时目录，真实数据零接触
产出 data/reports/lkg-fallback-verification.md
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

ALLOWED_DRIFT = {"meta.json", "source-health.json"}  # 健康状态本应反映失败


def dir_hash(p: Path) -> dict[str, str]:
    return {
        str(f.relative_to(p)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted(p.rglob("*.json"))
    }


def main() -> int:
    from pipeline import update as update_mod
    from pipeline.adapters import base as base_mod
    from pipeline.history import store as store_mod
    from pipeline.reports import generate as generate_mod

    tmp = Path(tempfile.mkdtemp(prefix="atlas-chaos-"))
    sandbox_public = tmp / "public-data"
    sandbox_lkg = tmp / "lkg"
    sandbox_snaps = tmp / "snaps"
    shutil.copytree(PROJECT_ROOT / "public/data", sandbox_public)
    shutil.copytree(PROJECT_ROOT / "data/cache/records", sandbox_lkg)
    if (PROJECT_ROOT / "data/history/snapshots").exists():
        shutil.copytree(PROJECT_ROOT / "data/history/snapshots", sandbox_snaps)

    generate_mod.PUBLIC_DATA_DIR = sandbox_public
    base_mod.RECORDS_LKG_DIR = sandbox_lkg
    orig_init = store_mod.HistoryStore.__init__
    store_mod.HistoryStore.__init__ = lambda self, snapshots_dir=None: orig_init(
        self, snapshots_dir or sandbox_snaps)

    orig_run = base_mod.BaseAdapter.run
    fail_mode: dict[str, str] = {}

    def patched_run(self):
        msg = fail_mode.get(self.source_id)
        if msg is not None:
            return self._fallback(msg, 0.0)
        return orig_run(self)

    base_mod.BaseAdapter.run = patched_run

    lines = [
        "# Last Known Good 回退演练报告",
        "",
        f"- 沙箱：`{tmp.name}`（public/data / LKG / 历史快照全部重定向，真实数据零接触）",
        "- 全部场景均为【全量运行 + 故障注入】，与 CI 场景一致",
        "- 判定：榜单/模型/能力/历史数据必须逐字节不变；仅 meta.json 与 source-health.json",
        "  允许变化（健康状态如实反映失败），这就是\"失败不清空榜单\"的可验证定义",
        "",
    ]

    all_pass = True

    def scenario(name: str, fail_map: dict[str, str], expect_exit: int = 0):
        nonlocal all_pass
        fail_mode.clear()
        fail_mode.update(fail_map)
        before = dir_hash(sandbox_public)
        code = update_mod.run(offline=False)
        after = dir_hash(sandbox_public)
        changed = [k for k in before if before[k] != after.get(k)]
        unexpected = [k for k in changed if Path(k).name not in ALLOWED_DRIFT]
        health = json.loads((sandbox_public / "source-health.json").read_text(encoding="utf-8"))
        st = {s["source_id"]: s["run_status"] for s in health["sources"] if s["source_id"] in fail_map}
        ok = code == expect_exit and not unexpected
        all_pass = all_pass and ok
        lines.append(
            f"- **{name}**：{'✅ 通过' if ok else '❌ 失败'}（exit={code}，预期 {expect_exit}；"
            f"榜单数据变化文件={len(unexpected)}（必须为 0）；健康状态={st}；"
            f"允许的健康文件变化={len(changed) - len(unexpected)}）"
        )
        fail_mode.clear()

    code0 = update_mod.run(offline=False)
    lines += [f"- 基线全量更新：exit={code0}，public/data 文件数={len(dir_hash(sandbox_public))}", ""]

    scenario("单来源网络超时（livebench）",
             {"livebench": "演练: ReadTimeout"})
    scenario("单来源解析失败/字段变化（swebench）",
             {"swebench": "演练: 解析错误 KeyError: unexpected_field"})
    scenario("单来源空数据（vlmevalkit）",
             {"vlmevalkit": "演练: 来源返回 0 条有效记录"})
    scenario("全部来源同时网络失败",
             {sid: "演练: 全部来源网络不可达"
              for sid in ("livebench", "swebench", "bigcodebench", "vlmevalkit", "mteb")})

    # 核心校验失败 → 拒绝发布（patch update 模块实际引用的名字）
    before = dir_hash(sandbox_public)
    orig_validate = update_mod.validate_records
    update_mod.validate_records = lambda recs, b: (["注入的 Schema 错误（演练）"], [])
    code = update_mod.run(offline=False)
    update_mod.validate_records = orig_validate
    after = dir_hash(sandbox_public)
    changed = [k for k in before if before[k] != after.get(k)]
    ok = code == 2 and len(changed) == 0
    all_pass = all_pass and ok
    lines.append(
        f"- **核心 Schema 校验失败**：{'✅ 通过' if ok else '❌ 失败'}"
        f"（exit={code}，预期 2；public/data 任何文件变化={len(changed)}（必须为 0），线上数据未被覆盖）"
    )

    lines += [
        "",
        "## 单元测试补充证据（pytest tests/）",
        "",
        "- `test_empty_data_falls_back_to_lkg`：来源返回空数组 → 降级保留上次数据",
        "- `test_http_500_falls_back_to_lkg` / `test_429_and_timeout_fail_isolated`：HTTP 500/429/超时 → 隔离失败",
        "- `test_schema_change_reported_as_parse_error`：来源字段变化 → 明确报解析错误",
        "- `test_lkg_file_roundtrip` / `test_history_retention_and_rank_changes`：LKG 与快照持久化",
        "",
        f"**总体结论：{'✅ 全部通过' if all_pass else '❌ 存在失败'}**",
        "",
    ]

    base_mod.BaseAdapter.run = orig_run
    out = PROJECT_ROOT / "data/reports/lkg-fallback-verification.md"
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n".join(lines[4:]))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
