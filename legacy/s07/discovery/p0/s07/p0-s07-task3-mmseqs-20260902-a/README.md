# S-07 任务 3：本地 PDB 检索、筛选与读取取证

状态：`PASS_WITH_TARGETED_RULE_GAPS / NOT_DEPLOYED`

本批次用 wwPDB 2026-08-29 序列和 entry 索引、MMseqs2 18-8cc5c 以及四条已冻结公开输入，
验证本地实验结构路径。它完成 sequence chain 检索、严格阈值后筛、PDB entry 元数据连接、
可比分辨率排序，以及 6Q00/9R2Q mmCIF 的序列与实际坐标覆盖读取。

主要结果：

- 1,093,472 条本地 PDB protein chain 序列已生成版本绑定的 MMseqs2 DB 和 index。
- 宽松候选集经 `identity > 0.95 AND proposed query coverage > 0.90` 后筛得到 2,466 个
  query-chain 候选；用门槛参数重跑得到完全相同的候选键。
- 6Q00 A 链序列和坐标均覆盖 76/76；9R2Q K/L/M/N 四条链的序列检索覆盖均为 100%，
  但实际坐标只映射目标 200/393，必须标注 `partial`。
- 10 个阈值、分辨率和多链受控用例全部符合预期。
- 多条同等匹配链已经由专家 R-58 规则处理为 failure 级 WARNING 并禁止自动交接。
- coverage 分母，以及 NMR 对有正分辨率 X-ray/cryo-EM 的优先级，形成两项定点确认材料。

详细结论见 [任务 3 证据报告](reports/TASK3_EVIDENCE_REPORT.md)，机器结果见
[task3_evidence.json](reports/task3_evidence.json)，文件哈希见
[artifact_manifest.json](reports/artifact_manifest.json)。

本批次没有完整部署本地 mmCIF archive，没有实现生产适配器，也没有接入 MCP 或 Dify。
