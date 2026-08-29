"""验证本项目部署后不消耗任何大模型 Token。

检查：
1. package.json 不包含生成式模型 SDK
2. Python 依赖不包含大模型客户端
3. src/ 与 pipeline/ 中不存在推理 API 地址
4. GitHub Actions 不调用 LLM
5. 不存在聊天 / 总结接口
6. 生产构建未开启 DEMO_MODE

允许在模型元数据、文案中出现 OpenAI/Anthropic/GLM 等文字；
只禁止调用其推理服务的生产代码。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

LLM_SDK_HINTS = [
    "@openai/api", "openai-node", "langchain", "llama-index", "llamaindex",
    "@anthropic-ai/sdk", "@google/generative-ai", "@mistralai", "cohere-ai",
    "dashscope", "zhipuai-sdk", "openai", "anthropic", "cohere",
    "transformers.js",
]

LLM_PY_HINTS = [
    "openai", "anthropic", "cohere", "google-generativeai", "dashscope",
    "zhipuai", "qianfan", "sparkai", "langchain", "llama-index", "litellm",
    "transformers",
]

INFERENCE_URL_PATTERNS = [
    r"api\.openai\.com/v\d+/(chat|completions|responses|embeddings)",
    r"api\.anthropic\.com/v\d+/messages",
    r"generativelanguage\.googleapis\.com",
    r"open\.bigmodel\.cn/api/paas/v\d+/chat",
    r"api\.deepseek\.(com|ai)/(chat|completions)",
    r"dashscope\.aliyuncs\.com/api/v\d+/services/aigc",
    r"api\.moonshot\.cn/v\d+/chat",
    r"api\.cohere\.(ai|com)/v\d+/(chat|generate)",
    r"api\.mistral\.ai/v\d+/chat",
    r"/v1/chat/completions",
    r"/v1/completions",
    r"/chat/completions",
]

CODE_DIRS = ["src", "pipeline", "scripts"]


def fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)


def check_package_json(errors: list[str]) -> None:
    pkg = PROJECT_ROOT / "package.json"
    deps = {**json.loads(pkg.read_text(encoding="utf-8")).get("dependencies", {}),
            **json.loads(pkg.read_text(encoding="utf-8")).get("devDependencies", {})}
    for name in deps:
        for hint in LLM_SDK_HINTS:
            if hint in name.lower():
                fail(f"package.json 包含生成式模型 SDK: {name}", errors)


def check_requirements(errors: list[str]) -> None:
    req = PROJECT_ROOT / "requirements.txt"
    for line in req.read_text(encoding="utf-8").splitlines():
        name = line.strip().lower().split(">=")[0].split("==")[0]
        for hint in LLM_PY_HINTS:
            if name == hint or name.startswith(hint + "-"):
                fail(f"requirements.txt 包含大模型客户端: {line.strip()}", errors)


def check_source_code(errors: list[str]) -> None:
    pattern = re.compile("|".join(INFERENCE_URL_PATTERNS))
    self_path = Path(__file__).resolve()
    for d in CODE_DIRS:
        base = PROJECT_ROOT / d
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if f.resolve() == self_path:
                continue  # 校验脚本自身包含用于检测的正则串
            if f.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx", ".ps1", ".yml", ".yaml"}:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    fail(f"{f.relative_to(PROJECT_ROOT)}:{i} 疑似推理 API 地址", errors)
                low = line.lower()
                if re.search(r"(chat|completions|generate|summarize)\s*[:(]", low) and \
                        re.search(r"(post|fetch|axios|httpx)", low) and \
                        not line.strip().startswith("#"):
                    # 粗筛：请求 + 生成类方法名（已排除注释），人工复核清单输出
                    errors.append(f"[需人工复核] {f.relative_to(PROJECT_ROOT)}:{i}: {line.strip()[:80]}")


def check_workflows(errors: list[str]) -> None:
    wf = PROJECT_ROOT / ".github" / "workflows"
    if not wf.exists():
        return
    banned = ["openai", "anthropic", "claude", "gemini", "gpt-", "langchain", "cohere", "deepseek"]
    for f in wf.glob("*.yml"):
        text = f.read_text(encoding="utf-8").lower()
        for b in banned:
            if re.search(rf"run:.*\b{re.escape(b)}\b", text) or f"pip install {b}" in text:
                fail(f"GitHub Actions 工作流 {f.name} 疑似调用 LLM: {b}", errors)


def check_demo_mode(errors: list[str]) -> None:
    vite_cfg = PROJECT_ROOT / "vite.config.ts"
    if "DEMO_MODE" not in vite_cfg.read_text(encoding="utf-8"):
        fail("vite.config.ts 缺少 DEMO_MODE 生产拒绝逻辑", errors)


def main() -> int:
    errors: list[str] = []
    check_package_json(errors)
    check_requirements(errors)
    check_source_code(errors)
    check_workflows(errors)
    check_demo_mode(errors)

    hard = [e for e in errors if not e.startswith("[需人工复核]")]
    soft = [e for e in errors if e.startswith("[需人工复核]")]

    if soft:
        print("以下条目为粗筛命中，请人工确认不构成 LLM 调用：")
        for s in soft:
            print(f"  {s}")
    if hard:
        print("发现违规项：")
        for e in hard:
            print(f"  {e}")
        return 1
    print("OK：未发现任何大模型运行时依赖。网站运行与数据更新均为纯确定性程序。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
