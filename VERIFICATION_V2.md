# V2 可信度整改验收报告（v2-trust-ui）

针对第二阶段外部审计指出的问题完成的整改。分支 `v2-trust-ui` 已合入 `main` 并部署上线。
验收自查证据全部来自真实运行（`data/reports/`）。

## 一、排名可信度修复

### 1. 综合指数四级门槛（已实现并生效）

`pipeline/ranking/composite.py`：

- **基准级门槛**：已映射去重模型 ≥10 且未映射率 ≤5%，否则该基准不得参与任何综合指数
- **记录级门槛**：只有 `record_verification_status = maintainer_verified` 的记录参与
- **模型级门槛**：模型须覆盖 ≥2 个合格基准，且覆盖合格基准总数的 ≥60%
- **单一基准能力不产生冠军**：合格基准只有 1 个时综合必然为 None

实测结果（`data/reports/mapping-coverage.{json,md}`）：

| 基准 | 映射率 | 已映射/去重模型 | 可进综合 |
|---|---|---|---|
| livebench 全部 7 基准 + 价格 | **100%** | 49/49 | ✅ |
| bigcodebench-complete/instruct | 6% / 7% | 10/154、9/126 | ❌（映射率过低） |
| mteb 各任务 | 100% | 1~5 个 | ❌（模型数 <10） |
| VLM 各基准（含 MMBench-CN） | 不足 | — | ❌（映射率不足） |
| swebench-verified | 不足 | — | ❌ |

整改前"能力指数 14 个"，整改后**仅 coding 有综合**（2 个合格基准 × 49 模型全覆盖），
第一名 claude-fable-5-max-effort 相对百分位 95.8、覆盖 2/2、单一来源标注——不再是虚高的 100.0。

### 2. 相对百分位口径（已实现）

- 能力页综合 Tab 更名 **"本站相对百分位（次级）"**，表头为"相对排名 / 本站相对百分位"
- 口径说明写明：**100 = 当前参与计算的模型集合中最高，不是能力满分**
- 模型详情页雷达图、优势短板、推荐器全部改用相对口径表述
- 官方原始榜为默认主视图，综合为次级 Tab

### 3. 未映射名称处理

- 未映射记录保留在官方原始榜（以来源原文显示），标注"未映射"
- 每次更新生成映射覆盖率报告（按基准：记录数/去重模型/映射率/是否合格/原因）
- 未映射率超标的基准页面直接不提供综合 Tab

## 二、Gemini 两案例专项解释

### 案例 1：Gemini 2.5 Pro "中文能力第一"（整改前）

- 整改前：中文能力 = MMBench-CN + CCBench 两个中文多模态基准的综合；
  Gemini 只覆盖 MMBench-CN（88.1，官方原始第 2），排除未映射模型后重算百分位 → 本站 100.0 排第 1。
  这就是把"局部基准相对位置"包装成"中文能力第一"，审计判断正确。
- 整改后：
  1. 能力更名 **"中文多模态理解"**，页面顶部内嵌口径说明
     （仅两个中文多模态视觉基准，不代表中文写作/问答/翻译/综合中文能力）
  2. VLM 基准映射率未达 95% → 综合指数被门槛禁止，页面显示"无相对百分位（门槛未通过，仅提供官方原始榜）"
  3. 默认展示官方原始榜：**CongRong-v2.0 88.3 第 1、Gemini 2.5 Pro 88.1 第 2**（官方原始名次），
     附口径说明与评测日期（2025-04-14 等历史日期如实展示）

### 案例 2：Gemini 3 Flash "软件工程第一"（整改前）

- 整改前：软件工程综合把 mini-SWE-agent 的 bash-only/multilingual/verified 运行平均成一个
  "能力百分位"，覆盖 2 个分区的系统反而压过覆盖 3 个分区的 Claude。审计判断正确：这是
  "Gemini 3 Flash + mini-SWE-agent 在特定分区的相对表现"，不是基础模型软件工程能力。
- 整改后：
  1. **软件工程能力不设综合指数**（update.py 显式排除，gate 说明："软件工程成绩来自
     「模型 + Agent 框架」的完整系统，不能折算为基础模型能力百分位"）
  2. 首页 Agent 软件工程 Tab 使用 **SWE-bench Verified 官方原始榜**（金标准分区），
     每行显示 **Agent 框架列** 与"模型+Agent"徽章；第一名现为 claude-opus-4-5-20251101
     （79.2，Sonar Foundation Agent / live-SWE-agent 等多 Scaffold 运行并列分列）
  3. 基础模型与 Agent 系统在全站任何综合口径中不再混排（测试
     `test_agent_records_excluded_from_base_composite` 覆盖）

## 三、记录级可信度与精确溯源

- 新增字段：`record_verification_status`（maintainer_verified / third_party_submitted / unknown）、
  `data_file_url`、`data_json_path`、`data_sha256`、`upstream_updated_at`
- VLMEvalKit 的 `Verified` 字段现在**真正参与规则**：yes → 官方核验；no → 第三方提交
  （不进严格榜）；缺失 → unknown。溯源抽屉显示验证徽章
- 溯源抽屉新增：**精确数据文件链接**（如 OpenVLM.json）、**文件内定位**
  （如 `results["InternVL3-78B"]["CCBench"]["Overall"]`）、**数据年龄**
  （评测日期 2025-04-14 → 抓取 2026-08-30，标注"数据年龄约 503 天"）、上游更新时间
- LiveBench/SWE-bench/BigCodeBench/MTEB 全部提供数据文件 URL + 文件内定位 + SHA256
- "今天抓取"与"今天评测"在 UI 与文档中严格区分

## 四、能力单一事实源

- `data/registry/capabilities.yml`：能力定义 + 五大能力域分组（文本与推理 / 编程与 Agent /
  多模态 / 成本与效率 / 安全与可靠性）+ 权重预设
- 流水线生成 `public/data/capabilities/index.json`；前端 `useCapabilities()` 统一消费，
  删除了手写 CAPABILITIES 数组，前后端不再漂移
- "中文能力"更名为 **"中文多模态理解"**（id: chinese_mm），预设同步更新

## 五、对比页与首页重设计

- **对比页**：主视图改为能力矩阵热力图（按五大能力域分组，单元格为官方原始分，
  行内色深表示相对高低，缺失为"—"不按 0 分）；雷达图降为可选视图（勾选 ≤8 维，缺失断开）
- **首页**：
  - 第一屏 = 六 Tab 官方原始分核心榜（文本推理/编程/Agent 软件工程/多模态/中文多模态/性价比）
  - 每Tab注明口径（如 Agent Tab："SWE-bench Verified 官方榜 · 模型+Agent 框架系统成绩"）
  - 性价比 Tab：编程相对百分位 ÷ 输入价格（客户端计算，公式公开）
  - 第二屏 = 能力 × 模型热力图（每行主基准 Top 12，优先选通过门槛的基准）
  - 第三屏 = 价格 × 编程相对百分位散点
  - 更新状态收成顶部 **状态圆点**（绿/黄/红 + N/M 来源），点击展开；首页不再有大状态栏

## 六、测试与验收

- pytest **27/27**（新增门槛测试：映射率门、样本量门、单基准无冠军、60% 覆盖门、
  第三方记录排除、Agent 不混排）
- vitest **10/10**（首页官方榜主位、热力图、门槛禁用 Tab disabled、抽屉验证状态与数据年龄、
  数据缺失空状态）
- ruff / tsc / eslint / build 全部通过；`npm run build` 拒绝 DEMO_MODE 逻辑不变
- 截图（`data/reports/screenshots/`）：v2-01 首页 after、v2-02 中文多模态官方榜、
  v2-03 对比矩阵、v2-04 抽屉数据年龄、v2-05 线上首页

## 七、遗留与下一步

- P1 数据源（BFCL / LongBench v2 / RULER）与 P2（OSWorld / Terminal-Bench / HarmBench）
  需逐一确认官方结构化结果形态后再接入，接入前显示"数据接入中"（capabilities.yml 已登记计划来源）
- Artificial Analysis 适配器已就绪，配置 `AA_API_KEY` Secret 即接入价格/速度/延迟
- 多源严格综合榜当前为空（门槛诚实结果）；随着各来源映射覆盖率提升会自动恢复
