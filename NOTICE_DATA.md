# 数据使用与许可声明 · NOTICE_DATA

## 代码许可

本项目代码（前端、流水线、脚本、配置）以 **MIT License** 发布。

## 第三方数据版权与使用方式

本项目不重新分发任何第三方数据集的完整副本，只保存**必要的聚合结果**（每模型每基准的单个分数 + 溯源元数据），并遵守以下约定：

| 数据 | 版权归属 | 本站处理方式 |
|---|---|---|
| LiveBench 分数与价格 | LiveBench（Abacus.AI 等） | 保存按官方类别聚合的平均分与标价，页面及溯源抽屉注明来源并链接官方榜 |
| SWE-bench 运行结果 | SWE-bench 官方 | 保存 resolved 百分比与运行元数据，链接到原始运行记录 |
| BigCodeBench 通过率 | BigCodeBench 官方 | 保存官方通过率，注明来源 |
| OpenVLM / VLMEvalKit 分数 | OpenCompass / VLMEvalKit 官方 | 保存官方复现的 Overall 分，注明来源 |
| MTEB 任务分数 | embeddings-benchmark | 保存代表性任务的 main_score，记录结果 commit sha |
| Artificial Analysis 数据 | Artificial Analysis | 遵循其免费 API 条款：注明来源、不批量转售、遵守 1000 次/天限额 |

## 遵循的规则

1. 尊重各来源的 robots.txt、服务条款与请求频率限制；不绕过任何登录、验证码或反爬机制
2. 抓取请求使用明确标识项目的 User-Agent；每个来源独立限速并带重试
3. 对没有明确数据许可的来源，只保存聚合分数与来源链接，不复制完整原始数据集
4. 各能力指数 / 综合指数为本站基于官方原始分的确定性计算，页面明确标注"本站计算，非官方榜单"
5. 如你是数据权利方并希望调整展示方式，请开 Issue，我们会尽快配合处理
