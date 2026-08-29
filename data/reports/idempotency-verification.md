幂等性验证 2026-08-29T22:07:32Z
连续 4 次完整数据更新（真实联网抓取全部 5 个数据源）：
- 每次 update 命令报告写入 0 个数据文件
- git status 工作区零变化
- 结论：数据无变化时输出逐字节稳定，CI 不会产生无意义提交

修复项：
1. 业务内容不变时记录继承 fetched_at；LKG 规范化排序 + sort_keys
2. meta/source-health/unmapped 改为数据驱动时间戳
3. SWE-bench 并列日期按 run_id 稳定决胜；抓取失败用 LKG 回补
4. MTEB 修订版本显式排序；unmapped example_url 取字典序最小
5. 全部 JSON 输出 sort_keys=True + 显式 LF 写盘 + .gitattributes
6. --sources 部分更新合并其他来源 LKG，不破坏完整数据
