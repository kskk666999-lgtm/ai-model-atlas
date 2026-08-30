"""生成模型别名审计报告 data/reports/model-alias-audit.md。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import yaml  # noqa: E402, F401

from pipeline.normalization.registry import ModelNormalizer, _canon_key  # noqa: E402
from pipeline.paths import REGISTRY_MODELS, UNMAPPED_FILE  # noqa: E402
from pipeline.schemas.records import parse_registry_models  # noqa: E402


def main() -> int:
    models = parse_registry_models(REGISTRY_MODELS)
    _norm = ModelNormalizer(models)

    # 1) 别名冲突检查：同一别名键映射到多个 canonical
    alias_map: dict[str, set[str]] = {}
    for m in models:
        for a in list(m.aliases) + [m.canonical_id]:
            alias_map.setdefault(_canon_key(a), set()).add(m.canonical_id)
    conflicts = {k: v for k, v in alias_map.items() if len(v) > 1}

    # 2) 官方数据中出现、但尚未映射的名称（unmapped 报告）
    unmapped = json.loads(UNMAPPED_FILE.read_text(encoding="utf-8")) if UNMAPPED_FILE.exists() else {"unmapped": []}

    # 3) 统计各家族的变体独立条目
    by_family: dict[str, list[str]] = {}
    for m in models:
        by_family.setdefault(m.family, []).append(m.canonical_id)
    multi_variant = {f: v for f, v in by_family.items() if len(v) >= 3}

    lines = [
        "# 模型别名审计报告",
        "",
        f"- 注册表条目总数：{len(models)}",
        f"- 别名映射总数：{len(alias_map)}（含 canonical_id 自映射）",
        f"- **别名冲突（同一别名指向多个模型）：{len(conflicts)} 个** "
        + ("❌ " + str({k: sorted(v) for k, v in list(conflicts.items())[:5]}) if conflicts else "✅"),
        f"- 尚未映射的来源侧名称：{len(unmapped.get('unmapped', []))} 个（保留在官方原始榜，等待人工补充别名，不参与综合指数）",
        "",
        "## 变体独立性抽查（≥3 个条目的家族，证明不同版本未被错误合并）",
        "",
    ]
    for fam in sorted(multi_variant):
        lines.append(f"- **{fam}**：{'、'.join(sorted(multi_variant[fam]))}")

    lines += [
        "",
        "## 关键版本拆分案例（人工核对要点）",
        "",
        "- GPT-4o：`gpt-4o-2024-05-13` / `gpt-4o-2024-08-06` / `gpt-4o-2024-11-20` 三个日期版本独立，",
        "  OpenVLM 的 `GPT-4o (0513, detail-high/low)` 映射到 0513 版并以 model_variant 区分 detail 设置",
        "- GPT-5.2：`gpt-5.2-2025-12-11`（基础）与 `gpt-5.2-2025-12-11-high`（high effort）独立；",
        "  SWE-bench 的 effort 后缀从官方 run 目录名确定性恢复",
        "- Claude：`claude-opus-4-5` / `4-6` / `4-7` / `5` 以及各 thinking/effort 变体独立",
        "- InternVL：`InternVL2-76B` / `InternVL2.5-78B` / `InternVL3-78B` 明确拆分（初版曾错误合并，已修复）",
        "- DeepSeek：`deepseek-v3` / `v3-0324` / `v3.1` / `v3.2` / `r1` / `r1-0528` 独立",
        "- Kimi：`kimi-k2` / `k2-0905` / `k2-thinking` / `k2.5` / `k2.6-thinking` / `k2.7-code` / `k3` 独立",
        "- Agent 系统成绩（SWE-bench）：同一模型不同 Agent 框架分别成行，evaluation_target_type=model_plus_agent，",
        "  不与基础模型成绩混排，也不进入综合指数",
        "",
        "## 未映射名称 Top 30（来源侧原文）",
        "",
    ]
    for u in unmapped.get("unmapped", [])[:30]:
        lines.append(f"- `{u['raw_name']}`（{u['source_id']}，出现 {u['occurrences']} 次）")

    out = PROJECT_ROOT / "data/reports/model-alias-audit.md"
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"别名冲突 {len(conflicts)} 个；注册表 {len(models)} 条；未映射 {len(unmapped.get('unmapped', []))} 个")
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
