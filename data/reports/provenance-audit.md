# 数据溯源审计报告

- 站点成绩总数：5038；抽样：22（seed=20260830）
- 自动核验通过：**22** / 22
- 全站重复行：0；无来源 URL 行：0
- 模拟数据/fixture 泄漏：0 处 ✅
- 不可达来源 URL：1 个

| 来源 | 基准 | 模型 | 站点分 | 官方核验 | 说明 |
|---|---|---|---|---|---|
| bigcodebench | bigcodebench-complete | DeepCoder-14B-Preview | 49.6 | ✅ | 官方 parquet complete-pass@1=49.600，站点=49.6 |
| bigcodebench | bigcodebench-instruct | CodeLlama-13B-Instruct | 28.5 | ✅ | 官方 parquet instruct-pass@1=28.500，站点=28.5 |
| bigcodebench | bigcodebench-instruct | Phi-3.1-Mini-128K-Instruct | 36.8 | ✅ | 官方 parquet instruct-pass@1=36.800，站点=36.8 |
| bigcodebench | bigcodebench-complete | Qwen2.5-Coder-32B-Instruct | 58.0 | ✅ | 官方 parquet complete-pass@1=58.000，站点=58.0 |
| livebench | livebench-instruction-following | gpt-5.2-2025-12-11-high | 61.77075 | ✅ | 官方表 gpt-5.2-2025-12-11-high 在 IF 的均值=61.771，站点=61.77075 |
| livebench | livebench-reasoning | qwen3.7-max | 83.3365 | ✅ | 官方表 qwen3.7-max 在 Reasoning 的均值=83.337，站点=83.3365 |
| livebench | livebench-price-output | qwen3.8-flash-next | 0.47 | ✅ | 官方 cost CSV output_price_per_million=0.47，站点=0.47 |
| livebench | livebench-price-input | gemini-3.5-flash-lite-high | 0.3 | ✅ | 官方 cost CSV input_price_per_million=0.3，站点=0.3 |
| mteb | mteb-arguana | qwen3-embedding-8b | 0.76852 | ✅ | 官方 main_score=0.76852，站点=0.76852 |
| mteb | mteb-sts17 | gte-qwen2-7b-instruct | 0.8875116705677044 | ✅ | 官方 main_score=0.8875116705677044，站点=0.8875116705677044 |
| mteb | mteb-arguana | gte-qwen2-7b-instruct | 0.54565 | ✅ | 官方 main_score=0.54565，站点=0.54565 |
| mteb | mteb-stsbenchmark | jina-embeddings-v3 | 0.8942710598569711 | ✅ | 官方 main_score=0.8942710598569711，站点=0.8942710598569711 |
| swebench | swebench-verified | claude-3-5-sonnet-20241022 | 49.2 | ✅ | 官方 metadata resolved=49.2，站点=49.2 |
| swebench | swebench-verified | Undisclosed | 40.6 | ✅ | 官方 metadata resolved=40.6，站点=40.6 |
| swebench | swebench-multilingual | claude-haiku-4-5-20251001 | 64.7 | ✅ | 官方 metadata resolved=64.7，站点=64.7 |
| swebench | swebench-verified | MCTS-Refine-7B | 23.2 | ✅ | 官方 metadata resolved=23.2，站点=23.2 |
| vlmevalkit | ovl-mmbench-test-cn-v11 | InternVL3-9B | 82.4 | ✅ | 官方 MMBench_TEST_CN_V11 Overall=82.4，站点=82.4 |
| vlmevalkit | ovl-ai2d | QTuneVL1-2B | 75.2 | ✅ | 官方 AI2D Overall=75.2，站点=75.2 |
| vlmevalkit | ovl-mmbench-test-cn-v11 | GPT-5-20250807 | 86.4 | ✅ | 官方 MMBench_TEST_CN_V11 Overall=86.4，站点=86.4 |
| vlmevalkit | ovl-mmbench-test-cn-v11 | SmolVLM2-500M | 33.4 | ✅ | 官方 MMBench_TEST_CN_V11 Overall=33.4，站点=33.4 |
| vlmevalkit | ovl-realworldqa | XVERSE-V-13B | 60.8 | ✅ | 官方 RealWorldQA Overall=60.8，站点=60.8 |
| vlmevalkit | ovl-qbench | Kimi-VL-A3B-Instruct | 76.9 | ✅ | 官方 QBench Overall=76.9，站点=76.9 |