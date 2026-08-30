# AI 模型天梯 · AI Model Atlas

中文优先的「全球 AI 模型能力可视化排行榜」。汇总 LiveBench、SWE-bench、Terminal-Bench、BFCL、BigCodeBench、VLMEvalKit/OpenVLM、MTEB 等官方结构化评测结果，按能力独立成榜：推理、编程、数学、Agent 软件工程、终端 Agent、工具调用、Web Search、Agent Memory、中文、多模态、OCR、检索、价格、速度等。

**纯静态 + 确定性流水线：网站运行和数据更新全程不调用任何大模型 API，不消耗大模型 Token。**

- 技术栈：Vite + React + TypeScript + Tailwind CSS + ECharts + TanStack Table（前端）；Python 3.13 + httpx + pydantic + pandas（数据流水线）
- 部署：GitHub Pages / Cloudflare Pages（免费，无服务器）
- 数据更新：GitHub Actions 每日计划更新两次（北京时间约 09:00 / 21:00）（实际执行时间可能因 GitHub Actions 调度略有延迟）；支持手动触发

## 快速开始（Windows 11 + PowerShell）

```powershell
# 1. 一键初始化并启动（检查环境 → 装依赖 → 抓真实数据 → 启动）
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1

# 之后日常启动
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1

# 只更新数据
powershell -ExecutionPolicy Bypass -File scripts/update-data.ps1

# 生产构建
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

手动方式：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm install
python -m pipeline.update   # 联网抓取真实数据，生成 public/data 下的静态 JSON
npm run dev                 # http://localhost:5173
```

> 首次抓取约 3~5 分钟（SWE-bench 官方实验仓库有数千条运行记录）。之后有 ETag 缓存，更新很快。

## 已接入的真实数据源

| 来源 | 等级 | 覆盖 |
|---|---|---|
| LiveBench 官方排行榜导出 | B | 推理 / 编程 / Agentic 编程 / 数学 / 数据分析 / 语言 / 指令遵循 + 官方统计价格 |
| SWE-bench 官方实验仓库 | A | Verified / Lite / Bash-Only / Multilingual / Multimodal（模型+Agent 系统） |
| Terminal-Bench 4.0 官方榜 | B | 真实终端任务中的完整模型+Agent 系统，含样本量与 95% 置信区间 |
| Berkeley Function Calling Leaderboard V4 | B | 工具调用 / Web Search / Agent Memory，区分 FC、Prompt、Thinking 模式 |
| BigCodeBench 官方结果 | A | 代码生成（complete / instruct） |
| VLMEvalKit / OpenVLM 官方汇总 | A | 多模态、OCR、图表、中文多模态等 20+ 基准 |
| MTEB 官方结果仓库 | A | Embedding 检索 / 重排 / 语义相似度 |
| Artificial Analysis 免费 API（可选） | C | 价格 / 速度 / 首字延迟（需要自备 API Key，Key 只存于 GitHub Secrets） |

暂未启用（在 DATA_SOURCES.md 中说明原因）：LiveCodeBench（无结构化导出）、OpenCompass 文本榜（动态页面无稳定接口）、LMArena（无合法稳定的自动读取方式）。这些能力在前台显示"数据接入中"，绝不生成模拟排名。

## 为什么本项目部署后不消耗大模型 Token

1. **GLM（或其他大模型）只在第一次开发本项目时使用**；建站完成后，所有功能靠确定性程序运行。
2. **网站运行是纯静态页面**：浏览器只读取提前生成好的 JSON 文件，图表全部在浏览器本地绘制（ECharts）。
3. **自动更新是普通 Python 抓取与数据处理**：GitHub Actions 定时运行 `pipeline.update`，用 HTTP 请求获取官方结构化数据，做校验、规范化、排名计算，输出静态 JSON。
4. **排名是确定性算法**：基准内百分位 + 来源等级加权，公式完全公开（见方法论页），没有任何模型参与打分。
5. **推荐器是规则计算**、优势短板由确定性规则生成、综合指数在前端本地重算。
6. 项目内置 `scripts/verify-no-llm-runtime.py` 自动检查依赖与代码中不存在任何推理 API 调用，CI 中执行。

## 核心功能

- **40+ 能力维度**：有可信数据的榜单正式展示，没有的显示"数据接入中"，不用模拟分数
- **官方原始榜 / 综合指数双模式**：综合指数为本站计算并明确标注，公式公开
- **每条分数可溯源**：点击任意分数打开"数据溯源抽屉"，看到来源、等级、基准版本、评测运行日、榜单快照、Agent 框架和原始出处链接；缺失日期诚实显示 `—`
- **能力雷达图、模型对比（2~6 个，URL 可分享）、场景推荐（纯规则）**
- **首页右侧自动更新状态栏**：上次/下次更新时间、健康数据源数、最新数据 Commit、过期提示（移动端折叠为抽屉）
- **模型名称规范化制度**：显式别名表 + 未知模型不丢弃不合并，写入 unmapped-models.json 等人工确认
- **Agent 系统与基础模型分开展示**，thinking/effort/日期等变体不错误合并
- **数据安全机制**：来源级错误隔离、Last Known Good 回退、核心校验失败禁止覆盖线上数据、历史每日快照自动聚合
- 深色科技风界面、中文优先、响应式（手机/平板/桌面）、Loading 骨架 / 空状态 / 错误状态、键盘可达

## 目录结构

```
ai-model-atlas/
├─ src/                 # React 前端（页面 / 组件 / 图表 / 类型 / 规则引擎）
├─ public/data/         # 流水线生成的静态 JSON（网站唯一数据来源）
├─ data/
│  ├─ registry/         # models.yml / aliases.yml / sources.yml / benchmarks.yml / capability-weights.yml
│  ├─ cache/            # 逐来源 LKG 数据（Last Known Good，随仓库提交）
│  ├─ reports/          # unmapped-models.json / latest-update.{json,md}
│  └─ history/          # 每日排名快照（自动周/月聚合）
├─ pipeline/            # Python 数据流水线（adapters / normalization / ranking / validation / reports）
├─ tests/               # pytest（适配器夹具、排名、校验、LKG）+ vitest（前端）
├─ scripts/             # PowerShell 脚本 + verify-no-llm-runtime.py
├─ .github/workflows/   # update-data.yml / ci.yml / deploy-pages.yml
└─ README_CN.md · DEPLOYMENT_CN.md · METHODOLOGY.md · DATA_SOURCES.md · NOTICE_DATA.md
```

## 测试与质量

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q        # Python 测试
.\.venv\Scripts\python.exe -m ruff check pipeline tests scripts
npm run lint          # ESLint
npm run typecheck     # TypeScript
npm run test          # vitest
npm run build         # 生产构建（DEMO_MODE=true 会被拒绝）
npm run verify-no-llm # 无 LLM 运行时校验
```

独立验收工具（第二阶段审计产物，报告在 data/reports/）：

```powershell
.\.venv\Scripts\python.exe scripts/provenance_audit.py   # 溯源抽查：抽样成绩对照官方源
.\.venv\Scripts\python.exe scripts/alias_audit.py        # 别名审计：冲突/变体拆分/未映射
.\.venv\Scripts\python.exe scripts/lkg_chaos_drill.py    # LKG 故障演练（沙箱隔离）
.\.venv\Scripts\python.exe scripts/security_audit.py     # 安全审计（含 git 历史）
```

综合榜分两级：「单源参考综合榜」（默认，带单源警告）与「多源验证综合榜 Beta」
（≥4 能力 / ≥5 基准 / ≥2 来源才收录）。区别详见方法论页与 VERIFICATION.md。
部署：完成一次 `gh auth login` 后运行 `scripts\deploy.ps1` 一键上线（见 DEPLOYMENT_RESULT.md）。

## 部署

见 [DEPLOYMENT_CN.md](DEPLOYMENT_CN.md)：从创建 GitHub 仓库到上线只需 9 步，全部在浏览器和 PowerShell 里完成，无需服务器。

## 许可与数据

- 本项目代码：MIT
- 各基准分数版权归其官方所有，展示时均注明来源与出处链接，综合指数明确标注为本站计算
- 数据使用政策详见 [NOTICE_DATA.md](NOTICE_DATA.md)
