# Last Known Good 回退演练报告

- 沙箱：`atlas-chaos-bwvpwjqc`（public/data / LKG / 历史快照全部重定向，真实数据零接触）
- 全部场景均为【全量运行 + 故障注入】，与 CI 场景一致
- 判定：榜单/模型/能力/历史数据必须逐字节不变；仅 meta.json 与 source-health.json
  允许变化（健康状态如实反映失败），这就是"失败不清空榜单"的可验证定义

- 基线全量更新：exit=0，public/data 文件数=198

- **单来源网络超时（livebench）**：❌ 失败（exit=0，预期 0；榜单数据变化文件=9（必须为 0）；健康状态={'livebench': 'degraded'}；允许的健康文件变化=2）
- **单来源解析失败/字段变化（swebench）**：❌ 失败（exit=0，预期 0；榜单数据变化文件=40（必须为 0）；健康状态={'swebench': 'degraded'}；允许的健康文件变化=2）
- **单来源空数据（vlmevalkit）**：❌ 失败（exit=0，预期 0；榜单数据变化文件=54（必须为 0）；健康状态={'vlmevalkit': 'degraded'}；允许的健康文件变化=2）
- **全部来源同时网络失败**：❌ 失败（exit=0，预期 0；榜单数据变化文件=43（必须为 0）；健康状态={'livebench': 'degraded', 'swebench': 'degraded', 'bigcodebench': 'degraded', 'vlmevalkit': 'degraded', 'mteb': 'degraded'}；允许的健康文件变化=2）
- **核心 Schema 校验失败**：✅ 通过（exit=2，预期 2；public/data 任何文件变化=0（必须为 0），线上数据未被覆盖）

## 单元测试补充证据（pytest tests/）

- `test_empty_data_falls_back_to_lkg`：来源返回空数组 → 降级保留上次数据
- `test_http_500_falls_back_to_lkg` / `test_429_and_timeout_fail_isolated`：HTTP 500/429/超时 → 隔离失败
- `test_schema_change_reported_as_parse_error`：来源字段变化 → 明确报解析错误
- `test_lkg_file_roundtrip` / `test_history_retention_and_rank_changes`：LKG 与快照持久化

**总体结论：❌ 存在失败**
