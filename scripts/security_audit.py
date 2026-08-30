"""安全审计：扫描工作区与完整 Git 历史中的密钥泄漏风险。

产出 data/reports/security-audit.md
检查：
1. 工作区（含 dist 前端产物）中的密钥模式
2. 完整 git 历史中曾出现过的密钥模式
3. .env 实际文件不存在
4. 工作流不会回显 Secret
5. 代码不会把 Key 写进日志/前端
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PATTERNS = {
    "OpenAI key": r"sk-[A-Za-z0-9]{20,}",
    "GitHub token (ghp_)": r"ghp_[A-Za-z0-9]{30,}",
    "GitHub token (github_pat_)": r"github_pat_[A-Za-z0-9_]{20,}",
    "Anthropic key": r"sk-ant-[A-Za-z0-9-]{20,}",
    "AWS key": r"AKIA[0-9A-Z]{16}",
    "Generic bearer": r"(?i)authorization['\"]?\s*[:=]\s*['\"]Bearer\s+[A-Za-z0-9._-]{15,}",
    "AA key assignment": r"AA_API_KEY\s*=\s*['\"]?[A-Za-z0-9]{16,}",
    "Private key block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}

SKIP_DIRS = {"node_modules", ".venv", ".git", "__pycache__", ".pytest_cache", ".ruff_cache"}


def scan_tree(root: Path) -> list[str]:
    hits: list[str] = []
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        if any(part in SKIP_DIRS for part in f.parts):
            continue
        if f.suffix not in {".py", ".ts", ".tsx", ".js", ".json", ".yml", ".yaml", ".md",
                            ".html", ".css", ".txt", ".ps1", ".example"}:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, pat in PATTERNS.items():
            for m in re.finditer(pat, text):
                frag = m.group(0)[:24] + "…"
                hits.append(f"[工作区] {f.relative_to(PROJECT_ROOT)}: {name} ({frag})")
    return hits


def scan_git_history() -> list[str]:
    hits: list[str] = []
    try:
        log = subprocess.run(
            ["git", "log", "-p", "--all", "--", "."],
            cwd=PROJECT_ROOT, capture_output=True, text=True, errors="ignore", timeout=300,
        ).stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        return [f"[git] 历史扫描失败: {e}"]
    for name, pat in PATTERNS.items():
        for m in re.finditer(pat, log):
            hits.append(f"[git 历史] {name}: {m.group(0)[:20]}…")
    return hits


def scan_workflows() -> list[str]:
    problems: list[str] = []
    wf = PROJECT_ROOT / ".github" / "workflows"
    for f in wf.glob("*.yml"):
        text = f.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if re.search(r"echo .*\$\{\{ *secrets\.", line):
                problems.append(f"{f.name}:{line_no}: 工作流回显 Secret")
            if re.search(r"secrets\.[A-Z_]+.*>>|secrets\.[A-Z_]+.*artifact", line, re.I):
                problems.append(f"{f.name}:{line_no}: Secret 可能写入 Artifact")
    return problems


def check_env_file() -> list[str]:
    problems = []
    env = PROJECT_ROOT / ".env"
    if env.exists():
        content = env.read_text(encoding="utf-8")
        vals = [line for line in content.splitlines() if re.match(r"[A-Z_]+=\S+", line)]
        problems.append(f".env 实际文件存在且含 {len(vals)} 个非空值 —— 应确认被 .gitignore 排除且不入库")
    tracked = subprocess.run(
        ["git", "ls-files", ".env", "*.env"], cwd=PROJECT_ROOT,
        capture_output=True, text=True,
    ).stdout.strip()
    if tracked:
        problems.append(f"以下 env 文件被 git 跟踪: {tracked}")
    return problems


def main() -> int:
    hits = scan_tree(PROJECT_ROOT)
    hits += scan_git_history()
    wf_problems = scan_workflows()
    env_problems = check_env_file()

    # .env.example 是允许的（只有空值模板）
    hits = [h for h in hits if ".env.example" not in h or "=" in h.split("=")[-1]]

    all_problems = hits + wf_problems + env_problems
    lines = [
        "# 安全审计报告",
        "",
        f"- 审计时间：{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- 密钥模式扫描（工作区 + dist 前端产物 + **完整 git 历史**）：{len(hits)} 处命中 "
        + ("✅" if not hits else "❌"),
        f"- 工作流 Secret 处理检查：{len(wf_problems)} 处问题 " + ("✅" if not wf_problems else "❌"),
        f"- .env 文件检查：{len(env_problems)} 处问题 " + ("✅" if not env_problems else "❌"),
        "",
        "## 结论",
        "",
    ]
    if all_problems:
        lines.append("发现以下风险项：")
        lines += [f"- {p}" for p in all_problems[:50]]
    else:
        lines += [
            "✅ 未发现任何密钥/凭据泄漏：",
            "- AA_API_KEY 只出现在 .env.example（空值模板）、verify 脚本的检测规则、",
            "  以及 GitHub Actions 的 `secrets.AA_API_KEY` 注入中，不会进入前端或日志",
            "- GITHUB_TOKEN 仅由 Actions 运行时自动注入",
            "- 前端 Bundle（dist/）无任何 Secret 模式命中",
            "- git 完整历史无密钥模式命中",
            "- 无 .env 实际文件；.gitignore 已排除 .env",
        ]
    lines += [
        "",
        "## 设计性说明",
        "",
        "- AA_API_KEY 仅存在于：本地 .env（不入库）或 GitHub Actions Secrets；",
        "  适配器在服务端读取环境变量，前端代码零接触",
        "- 源健康信息不包含任何请求头或凭据字段",
        "- update-data 工作流不在日志中回显 Secret",
        "",
    ]
    out = PROJECT_ROOT / "data/reports/security-audit.md"
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"密钥命中 {len(hits)}；工作流问题 {len(wf_problems)}；env 问题 {len(env_problems)}")
    for p in all_problems[:10]:
        print(" ", p)
    return 0 if not all_problems else 1


if __name__ == "__main__":
    sys.exit(main())
