# T-01 科学工具 Discovery 资产

本目录保存真实科学工具在 `discovery` 阶段产生的可复核小型证据，不代表工具已经部署，
也不得直接用于科研结论。

## 目录约定

- `p0/s07/<campaign>/`：Stage 0、S-07 的一次唯一发现或输出审计批次。
- `campaign.json`：批次身份、范围、边界和状态。
- `samples/`：冻结输入及来源。
- `requests/`：发送给外部服务的请求正文。
- `evidence/`：原始 HTTP/CLI 证据；每个 exchange 只写一次，不覆盖。
- `reports/`：候选 manifest、序列映射、字段事实、能力缺口或 P0-M1B 输出审计报告。

大型数据库、模型权重和不可安全再分发的产物不进入本目录；它们应进入受控 artifact store，
这里只保存哈希、版本和引用。

## 已完成批次

- [P0-M1 S-07 discovery：p0-s07-discovery-20260901-a](p0/s07/p0-s07-discovery-20260901-a/README.md)：
  RCSB、AlphaFold DB 与 NCBI BLAST+ 真实输出取证已完成，已作为后续 S-07 契约、任务 5/6
  和 P0 v0.6 的历史输入；所有能力仍为 `NOT_DEPLOYED`。
- [P0-M1B S-07 最终输出审计：p0-s07-m1b-20260901-d](p0/s07/p0-s07-m1b-20260901-d/reports/P0_M1B_OUTPUT_AUDIT.md)：
  57 次来源调用全部成功，完成 19 页 RCSB、RCSB/AFDB 结构组成、4 组 BLAST 三格式输出和
  285 个非报告文件的审计；只用于 S07-D09 重审，仍为 `NOT_DEPLOYED`。
- [S-07 任务 2 隔离关系验证：p0-s07-task2-fixture-20260902-a](p0/s07/p0-s07-task2-fixture-20260902-a/README.md)：
  用 1 条 UniProtKB/Swiss-Prot 记录验证 BLAST DB、accession 回读及 AlphaFold DB v6
  文件关系；11 项机器检查通过，仅为 `PASS_FIXTURE_ONLY / NOT_DEPLOYED`。
- [S-07 任务 3 本地检索与结构读取：p0-s07-task3-mmseqs-20260902-a](p0/s07/p0-s07-task3-mmseqs-20260902-a/README.md)：
  用 wwPDB 2026-08-29、MMseqs2 18-8cc5c 和 4 条冻结输入完成本地检索、entry 元数据连接及
  6Q00/9R2Q 坐标读取；10 个受控用例通过，留下 2 项定点规则确认，仍为 `NOT_DEPLOYED`。
- [S-07 任务 4 UniProt/AFDB API 回退：p0-s07-task4-uniprot-afdb-20260902-a](p0/s07/p0-s07-task4-uniprot-afdb-20260902-a/README.md)：
  用在线 BLAST、UniProt REST 和 AlphaFold DB API 完成 9/9 项证据检查，区分正常零命中、
  无模型、非法标识和歧义；3 项建议已暂行采用并与任务 3 的 2 项合并等待专家确认，仍为
  `NOT_DEPLOYED`。
- [S-07 任务 5 离线契约验证：p0-s07-task5-contract-20260903-b](p0/s07/p0-s07-task5-contract-20260903-b/README.md)：
  复用 136 个任务 3/4 冻结文件，19 个结果场景、20 个非法状态拒绝检查及 7 个文件/恢复检查
  全部通过；19 份结果、252 个内容对象完成只读复核，契约说明与验证报告已交付。仅为
  `PASS_OFFLINE_CONTRACT_ONLY / NOT_DEPLOYED`，没有新的在线检索或完整科学验收；a 批次保留。
- [S-07 任务 6 独立验收：p0-s07-task6-acceptance-20260903-c](p0/s07/p0-s07-task6-acceptance-20260903-c/reports/TASK6_ACCEPTANCE_REPORT.md)：
  在固定 wwPDB/MMseqs2 发布和当前官方 API 上完成 10/10 项检查，验证完整候选读取、结构映射、
  O15116 回退、任务 5 恢复及下游交接形状；仍为 `NOT_DEPLOYED`，五项规则待专家确认。
  `...-a` 的元数据字段失败和 `...-b` 的清单打包失败/恢复均保留为运行历史，最终以 c 为准。

P0-M1B 的 A、B、C 批次分别保留状态解析、Windows BLAST 路径和采集器警告问题的原始失败/噪声
证据，不是最终审计结果。问题、修复和最终批次选择见
[P0-M1B 执行记录](../docs/archive/p0/S07_M1B_RUN_RECORD.md)。
