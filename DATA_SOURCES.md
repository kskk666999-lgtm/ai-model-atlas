# 数据来源说明 · DATA_SOURCES

本站全部数据来自下列官方或第三方机构公开发布的结构化结果。等级制度：

- **A 级（权重 1.0）**：官方基准仓库 / 官方结构化结果文件 / 官方数据 API，有版本号、提交记录或可复现评测材料
- **B 级（权重 0.8）**：官方排行榜导出（官方生成，但复现材料不完整）
- **C 级（权重 0.6）**：有公开方法论的独立第三方评测
- **D 级（权重 0）**：厂商自报 / 无法验证的数据。**默认综合排名不使用 D 级数据**，本站目前也不展示 D 级来源

## 已启用来源

| source_id | 来源 | 等级 | 获取方式 | 说明 |
|---|---|---|---|---|
| `livebench` | [LiveBench](https://livebench.ai)（官方） | B | 官网 `table_<release>.csv` / `categories_<release>.json` / `cost_<release>.csv` | release（如 `2026-06-25`）是基准/题集版本，不是逐模型评测日期；类别分数按官方类别对任务取平均；榜单快照取官方文件 `Last-Modified`；价格列为 LiveBench 官方统计的 API 标价 |
| `swebench` | [SWE-bench Official Experiments](https://github.com/SWE-bench/experiments)（官方） | A | GitHub 仓库 `evaluation/<split>/<run>/` | verified 分区读 `results/results.json`（resolved/500），其余分区读 `metadata.yaml` 的 `info.resolved`；只收录官方核验（checked/verified）通过的运行；所有成绩为「模型 + Agent 框架」系统级结果 |
| `terminalbench` | [Terminal-Bench 4.0](https://www.tbench.ai/?version=4.0)（官方） | B | 官网服务端结构化榜单数据 | 覆盖完整「模型 + Agent」终端任务系统；保留 Agent、推理档位、330 题样本量、95% 置信区间和榜单更新时间；官方未提供逐提交运行日 |
| `bfcl` | [Berkeley Function Calling Leaderboard V4](https://gorilla.cs.berkeley.edu/leaderboard.html)（官方） | B | 官方 `data_overall.csv` | 覆盖工具调用综合准确率、Web Search 和 Memory；FC / Prompt / Thinking 模式分别保留；官方未提供逐模型运行日，榜单快照取文件 `Last-Modified` |
| `bigcodebench` | [BigCodeBench 官方结果数据集](https://huggingface.co/datasets/bigcode/bigcodebench-results) | A | HF parquet | complete / instruct 两种模式的官方通过率 |
| `vlmevalkit` | [OpenVLM 官方汇总](http://opencompass.openxlab.space/assets/OpenVLM.json)（VLMEvalKit / OpenCompass 官方） | A | 官方 JSON 资产 | 200+ 模型 × 20+ 多模态基准的官方复现 Overall 分；detail-high/low 作为变体区分 |
| `mteb` | [embeddings-benchmark/results](https://github.com/embeddings-benchmark/results)（官方） | A | GitHub 仓库按模型按任务 JSON | 代表性任务（检索 / 重排 / 语义相似度），记录版本 commit sha |
| `artificialanalysis` | [Artificial Analysis 免费 API](https://artificialanalysis.ai)（可选） | C | REST API（`x-api-key`） | 价格 / 输出速度 / 首字延迟 / 智能指数；需要 API Key（只存 GitHub Secrets，绝不进入前端）；限额 1000 次/天；展示时按要求注明来源 |

## 暂未启用来源（及原因）

| source_id | 来源 | 状态 | 原因 |
|---|---|---|---|
| `livecodebench` | LiveCodeBench | disabled | 官方榜单为编译后的 JS 包，官方仓库（含 feat--new-autograder 分支）无结构化结果文件。逆向解析 JS 包属于脆弱做法，与本项目"不使用脆弱抓取"的原则冲突。待官方提供结构化导出后接入。 |
| `opencompass_text` | OpenCompass 中文学术评测 | disabled | 官方排行榜为动态渲染页面，无稳定公开的数据接口。其中文多模态部分已由 `vlmevalkit` 来源（MMBench CN、CCBench）覆盖。 |
| `arena` | LMArena（人类偏好） | disabled | 无稳定、公开、允许自动读取的数据接口，页面有访问限制。本项目不绕过任何登录 / 验证码 / 反爬机制。待其提供合法数据形式后接入。 |

## 数据完整性机制

- 日期分四类保存并分列展示：**模型发布日期**、**评测运行日**、**基准/题集版本**、**上游榜单快照时间**。来源没有发布逐模型运行日时显示 `—`，不会拿版本号、发布日期、抓取时间冒充
- 每个来源独立运行、独立失败：一个来源挂掉不影响其他榜单，该来源自动回退到**上次成功数据**（Last Known Good，随仓库保存在 `data/cache/records/`）
- 前台 `数据来源` 页展示每个来源的实时健康状态（`public/data/source-health.json`）
- 核心校验失败（结构 / 方向 / 能力映射不一致）时流水线以退出码 2 终止，**绝不覆盖线上数据**
- 原始响应带 ETag / Last-Modified 协商缓存，存在 `data/cache/http/`（不入库）
