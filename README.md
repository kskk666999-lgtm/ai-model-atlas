# AI Model Atlas · AI 模型天梯

A Chinese-first, static leaderboard website that aggregates **official structured results** of AI models across capabilities (reasoning, coding, math, software engineering, multimodal, OCR, retrieval, pricing, speed, …).

- **Zero LLM runtime**: the site is fully static; data updates are deterministic Python scripts scheduled by GitHub Actions. No generative-model API is ever called at build time or runtime.
- Deploy on GitHub Pages / Cloudflare Pages for free.
- Chinese documentation: see [README_CN.md](README_CN.md).

```powershell
# Windows: one-shot bootstrap (env check, deps, real data fetch, dev server)
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
```

License: MIT (code). Benchmark scores belong to their respective official projects and are always attributed.
