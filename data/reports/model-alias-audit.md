# 模型别名审计报告

- 注册表条目总数：145
- 别名映射总数：235（含 canonical_id 自映射）
- **别名冲突（同一别名指向多个模型）：0 个** ✅
- 尚未映射的来源侧名称：455 个（保留在官方原始榜，等待人工补充别名，不参与综合指数）

## 变体独立性抽查（≥3 个条目的家族，证明不同版本未被错误合并）

- **claude-4**：claude-opus-4-1-20250805、claude-opus-4-20250514、claude-sonnet-4-20250514
- **deepseek-v3**：deepseek-v3、deepseek-v3-0324、deepseek-v3.1、deepseek-v3.2、deepseek-v3.2-reasoner
- **gemini-2.5**：gemini-2.5-flash、gemini-2.5-flash-lite、gemini-2.5-pro
- **gpt-4o**：gpt-4o-2024-05-13、gpt-4o-2024-08-06、gpt-4o-2024-11-20、gpt-4o-mini
- **internvl**：internvl2-76b、internvl2.5-78b、internvl3-38b、internvl3-78b、internvl3-9b
- **kimi-k2**：kimi-k2、kimi-k2-0905、kimi-k2.5
- **o-series**：o3、o3-mini、o4-mini

## 关键版本拆分案例（人工核对要点）

- GPT-4o：`gpt-4o-2024-05-13` / `gpt-4o-2024-08-06` / `gpt-4o-2024-11-20` 三个日期版本独立，
  OpenVLM 的 `GPT-4o (0513, detail-high/low)` 映射到 0513 版并以 model_variant 区分 detail 设置
- GPT-5.2：`gpt-5.2-2025-12-11`（基础）与 `gpt-5.2-2025-12-11-high`（high effort）独立；
  SWE-bench 的 effort 后缀从官方 run 目录名确定性恢复
- Claude：`claude-opus-4-5` / `4-6` / `4-7` / `5` 以及各 thinking/effort 变体独立
- InternVL：`InternVL2-76B` / `InternVL2.5-78B` / `InternVL3-78B` 明确拆分（初版曾错误合并，已修复）
- DeepSeek：`deepseek-v3` / `v3-0324` / `v3.1` / `v3.2` / `r1` / `r1-0528` 独立
- Kimi：`kimi-k2` / `k2-0905` / `k2-thinking` / `k2.5` / `k2.6-thinking` / `k2.7-code` / `k3` 独立
- Agent 系统成绩（SWE-bench）：同一模型不同 Agent 框架分别成行，evaluation_target_type=model_plus_agent，
  不与基础模型成绩混排，也不进入综合指数

## 未映射名称 Top 30（来源侧原文）

- `Undisclosed`（swebench，出现 24 次）
- `360VL-70B`（vlmevalkit，出现 17 次）
- `AKI-4B`（vlmevalkit，出现 17 次）
- `Aquila-VL-2B`（vlmevalkit，出现 17 次）
- `Aria`（vlmevalkit，出现 17 次）
- `BailingMM-Lite-1203`（vlmevalkit，出现 17 次）
- `BailingMM-Pro-0120`（vlmevalkit，出现 17 次）
- `BlueLM-V-3B`（vlmevalkit，出现 17 次）
- `Bunny-Llama3-8B`（vlmevalkit，出现 17 次）
- `Claude3.7-Sonnet`（vlmevalkit，出现 17 次）
- `DeepSeek-VL-1.3B`（vlmevalkit，出现 17 次）
- `DeepSeek-VL-7B`（vlmevalkit，出现 17 次）
- `Eagle-X5-13B`（vlmevalkit，出现 17 次）
- `Eagle-X5-34B-Chat`（vlmevalkit，出现 17 次）
- `Eagle-X5-7B`（vlmevalkit，出现 17 次）
- `Emu3_chat`（vlmevalkit，出现 17 次）
- `Falcon2-VLM-11B`（vlmevalkit，出现 17 次）
- `GLM-4v-Plus-20250111`（vlmevalkit，出现 17 次）
- `GPT-4.1-nano-20250414`（vlmevalkit，出现 17 次）
- `Gemini-1.5-Flash`（vlmevalkit，出现 17 次）
- `Gemma3-12B`（vlmevalkit，出现 17 次）
- `Gemma3-27B`（vlmevalkit，出现 17 次）
- `Gemma3-4B`（vlmevalkit，出现 17 次）
- `H2OVL-2B`（vlmevalkit，出现 17 次）
- `H2OVL-800M`（vlmevalkit，出现 17 次）
- `HunYuan-Standard-Vision`（vlmevalkit，出现 17 次）
- `IDEFICS2-8B`（vlmevalkit，出现 17 次）
- `InternLM-XComposer2`（vlmevalkit，出现 17 次）
- `InternLM-XComposer2-1.8B`（vlmevalkit，出现 17 次）
- `InternVL-Chat-V1.5`（vlmevalkit，出现 17 次）