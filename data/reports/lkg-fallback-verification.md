# Last Known Good 回退演练报告

- 沙箱：`atlas-chaos-x5gdef_5`（public/data / LKG / 历史快照全部重定向，真实数据零接触）
- 全部场景均为【全量运行 + 故障注入】，与 CI 场景一致
- 判定（对齐需求本义）：失败来源的成绩行必须完整保留（LKG 回退）、必须标记 degraded、
  不得出现空榜；上游其他来源若有合法新数据可以正常进入（这不属于回退问题）

- 基线全量更新：exit=0，public/data 文件数=198

- **单来源网络超时（livebench）**：✅ 通过（exit=0，预期 0；失败来源行数保留(前→后)={'livebench': (441, 441)}；健康状态={'livebench': 'degraded'}；新出现空榜=0（已知上游空榜 5 个））
- **单来源解析失败/字段变化（swebench）**：✅ 通过（exit=0，预期 0；失败来源行数保留(前→后)={'swebench': (170, 170)}；健康状态={'swebench': 'degraded'}；新出现空榜=0（已知上游空榜 5 个））
- **单来源空数据（vlmevalkit）**：✅ 通过（exit=0，预期 0；失败来源行数保留(前→后)={'vlmevalkit': (4124, 4124)}；健康状态={'vlmevalkit': 'degraded'}；新出现空榜=0（已知上游空榜 5 个））
- **全部来源同时网络失败**：✅ 通过（exit=0，预期 0；失败来源行数保留(前→后)={'livebench': (441, 441), 'swebench': (170, 170), 'bigcodebench': (280, 280), 'vlmevalkit': (4124, 4124), 'mteb': (23, 23)}；健康状态={'livebench': 'degraded', 'swebench': 'degraded', 'bigcodebench': 'degraded', 'vlmevalkit': 'degraded', 'mteb': 'degraded'}；新出现空榜=0（已知上游空榜 5 个））
- **核心 Schema 校验失败**：✅ 通过（exit=2，预期 2；public/data 任何文件变化=0（必须为 0），线上数据未被覆盖）

## 单元测试补充证据（pytest tests/）

- `test_empty_data_falls_back_to_lkg`：来源返回空数组 → 降级保留上次数据
- `test_http_500_falls_back_to_lkg` / `test_429_and_timeout_fail_isolated`：HTTP 500/429/超时 → 隔离失败
- `test_schema_change_reported_as_parse_error`：来源字段变化 → 明确报解析错误
- `test_lkg_file_roundtrip` / `test_history_retention_and_rank_changes`：LKG 与快照持久化

**总体结论：✅ 全部通过**
