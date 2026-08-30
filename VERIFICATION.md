# VERIFICATION · 独立验收报告

第二阶段（审计 + 修复 + 上线）的全部验收证据。所有报告文件保存在 `data/reports/`，
均由脚本在真实运行中生成，非手工撰写。

## 1. 项目与 Git 状态

- 报告：`data/reports/phase1-project-status.txt`（真实命令输出）
- 关键文件全部入库：package.json / package-lock.json / requirements.txt / pyproject.toml /
  src / pipeline / public/data / scripts / tests / .github/workflows / 四份文档（303+ 文件）

## 2. 干净环境验收 ✅

- 报告：`data/reports/clean-environment-verification.txt`
- 方法：从本地 Git 仓库全新 `git clone` 到独立目录（无 node_modules / .venv / dist / 缓存），
  依次执行 npm ci → venv → pip install → pytest → ruff → lint → typecheck → vitest → build →
  verify-no-llm → **真实联网数据更新**
- 结果：11/11 步骤全部成功（含 Python 24 测试、前端 4 测试、生产构建、联网抓取 5 个数据源）

## 3. 数据溯源审计 ✅（22/22）

- 报告：`data/reports/provenance-audit.json` + `.md`（seed=20260830，可复现）
- 方法：从站点成绩中分层随机抽取 22 条，覆盖全部 5 个有效来源、
  基础模型 / 模型变体 / Agent 系统 / 中文模型 / 开放权重模型，
  **逐条回到官方源头重新抓取并比对分数**
- 结果：22/22 分数一致；全站无重复行、无缺失来源 URL、无模拟数据/fixture 泄漏；
  每条记录可经"数据溯源抽屉"看到来源、等级、版本、评测日期与原始出处链接
- 关于首页"gpt-5.6-sol-max 91.7"：为 LiveBench 官方推理类别分（4 个官方任务的官方平均值，
  release=2026-06-25），不是本站指数；溯源抽屉直接给出官方 release 与原始数据链接

## 4. 模型别名审计 ✅（0 冲突）

- 报告：`data/reports/model-alias-audit.md`
- 注册表 145 条、别名映射 235 个、**别名冲突 0 个**
- 版本独立性：GPT-4o 三个日期版本 / GPT-5.2 基础与 high-effort / Claude Opus 4.5→5 各版本 /
  InternVL 2 vs 2.5 vs 3（初版曾错误合并，已修复）/ DeepSeek V3→V3.2 / Kimi K2→K3 独立成条
- Agent 系统成绩与基础模型分榜展示，SWE-bench 的 effort 后缀从官方 run 目录名确定性恢复
- 未映射名称 455 个：保留在官方原始榜（以来源原文显示），写入 unmapped-models.json
  等待人工补充别名，不参与综合指数、绝不猜测合并

## 5. 幂等更新验证 ✅（连续 4 轮联网更新 0 文件变化）

- 报告：`data/reports/idempotency-verification.md`
- 修复前确实存在审计指出的缺陷（fetched_at/generated_at 每次变化 → 无意义提交）。
  已修复：
  1. 业务内容不变的记录继承 fetched_at；LKG 规范化排序 + JSON sort_keys
  2. meta / source-health / unmapped 报告改为数据驱动时间戳；response_time 移出健康文件
  3. SWE-bench 并列日期按 run_id 稳定决胜；抓取失败（限流）用 LKG 回补
  4. MTEB 修订版本显式排序；unmapped example_url 取字典序最小
  5. 全部输出显式 LF 写盘 + .gitattributes（根除 Windows CRLF 抖动）
  6. `--sources` 部分更新合并其他来源 LKG（修复过程中发现并修复的真 bug）
- 验证：连续 4 次完整联网更新，每次"写入 0 个数据文件"，git 工作区零变化

## 6. Last Known Good 回退演练 ✅（5/5）

- 报告：`data/reports/lkg-fallback-verification.md`（脚本 `scripts/lkg_chaos_drill.py`，
  在完全隔离沙箱中运行，真实数据零接触）
- 场景与结果（全量运行 + 故障注入，与 CI 场景一致）：
  - 单来源网络超时（livebench）→ 行数保留 441→441，标记 degraded ✅
  - 单来源解析失败/字段变化（swebench）→ 170→170 ✅
  - 单来源空数据（vlmevalkit）→ 4124→4124 ✅
  - 全部来源同时失败 → 全部行数保留 ✅
  - 核心 Schema 校验失败 → exit 2，public/data 任何文件不变（拒绝发布）✅
- 单元测试补充：HTTP 500 / 429 / 超时 / 空数组 / 字段变化 / LKG 往返（pytest 24 项内）
- 说明：已知 5 个空榜为上游当前确无数据（LiveBench 现行版无 Social 类、MTEB v2 无
  TREC-COVID、OpenVLM 现行版 OCRBench 无分数、SWE-bench lite/multimodal 无官方核验运行），
  已在报告中登记，前台对应能力显示"数据接入中"

## 7. 安全审计 ✅（0 命中）

- 报告：`data/reports/security-audit.md`（脚本 `scripts/security_audit.py`）
- 扫描范围：工作区全部源码与 **dist 前端产物** + **完整 git 历史**
- 模式：OpenAI/Anthropic/GitHub/AWS key、Bearer 头、AA_API_KEY 赋值、私钥块等 8 类
- 结果：0 处命中；工作流无 Secret 回显/写 Artifact；无 .env 实际文件；
  AA_API_KEY 仅经 GitHub Secrets 注入服务端

## 8. GitHub Actions 审计 ✅

- `update-data.yml`：移除了会引起重复运行的 workflow_run 触发；concurrency 串行化；
  数据完整性门禁（records>0 且 demo_mode=false）；失败日志 Artifact；手动触发可用；
  每日两次 cron（约北京时间 09:00 / 21:00）；fork 无 Secret 时 AA 源自动跳过、其余照常
- `ci.yml`：新增 concurrency 与 timeout；数据提交（public/data、data/**、*.md）走
  paths-ignore 跳过，避免每个数据提交空跑 CI
- `deploy-pages.yml`：仅 push + 手动触发（数据提交经 push 自然触发部署，无双触发）；
  concurrency 去重；timeout；Pages base 用 `VITE_BASE` 环境变量自动适配仓库名
  （本地 Git Bash 亦可测试：`$env:VITE_BASE="ai-model-atlas"; npm run build`）
- 循环风险：无——update-data 提交 → push 触发 ci（被 paths-ignore 跳过）与 deploy-pages（一次）

## 9. 真实浏览器验收 ✅（10 张截图）

- 目录：`data/reports/screenshots/`（生产构建 `vite preview`，非开发服务器）
- 已验收：首页桌面端 / 单源参考综合榜（含"单源"警告徽章与双模式切换）/
  数据溯源抽屉（分数→来源→等级→版本→原始链接）/ 模型对比雷达图 /
  模型详情 / 场景推荐 / 数据来源 / 方法论 / **移动端 393px**（汉堡菜单+浮动更新按钮）/ 404 路由
- 子路径兼容：`VITE_BASE=ai-model-atlas` 构建后在 `/ai-model-atlas/` 子路径实测
  index 与资产全部 200（GitHub Pages 项目页同构场景）

## 10. 已知限制

1. 多源严格综合榜当前仅 2 个模型达标（规则的诚实结果）；首页默认展示"单源参考综合榜"
   （带单源警告），严格榜以 Beta 标签提供
2. 5 个基准上游当前无数据（见第 6 节），对应能力显示"数据接入中"
3. 未映射名称 455 个：多为小众/历史模型，出现在官方原始榜但不参与综合指数
4. gh CLI 未安装且本机无 GitHub 凭据，正式部署需完成一次登录（见 DEPLOYMENT_RESULT.md）
