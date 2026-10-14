# S-07 任务 6 独立验收报告

> 批次：`p0-s07-task6-acceptance-20260903-c`  
> 状态：`COMPLETE_NONPRODUCTION_ACCEPTANCE_WITH_RELEASE_GATES / NOT_DEPLOYED`  
> 科学验收：`NOT_RUN`；规则：`PROVISIONAL_USER_APPROVED_EXPERT_PENDING`。

## 验收结论

本批次完成 S-07 的非生产独立验收：固定 wwPDB 发布的新 MMseqs2 实跑、当前官方 API 的
RCSB 完整候选读取、O15116 的 RCSB→UniProt→AlphaFold DB 连续回退、代表 mmCIF 的序列与
坐标读取，以及任务 5 的失败/恢复和 S-08/S-09 交接形状复核。10/10
项验收检查通过。

本结论不发布 MCP/Dify 适配器，不把 S-08/S-09 写成已部署，也不把五项暂行规则升级为专家
确认或科研金标准。缺 accession 的真实正命中 BLAST 仍观察到 100 条 profile 上限，因此禁止
用该批次自动选择 accession；它作为 P0 v0.6 的生产门禁保留。

## 固定发布新实跑

| 输入 | 严格 chain | entry | 结果 | 候选 |
|---|---:|---:|---|---|
| P0-DISC-002 | 24 | 8 | REVIEW_REQUIRED | — |
| P0-DISC-001 | 2442 | 1333 | SELECTED_PROVISIONAL | 6Q00 |
| P0-DISC-004 | 0 | 0 | NO_STRICT_CANDIDATE | — |
| P0-DISC-005 | 0 | 0 | NO_STRICT_CANDIDATE | — |

6Q00 A 链为 76/76 坐标完整；9R2Q K 链为
200/393，且 K/L/M/N 四链歧义继续按
R-58 阻止自动交接。运行墙钟为 3.608 秒；工具日志报告的最大估计
内存为 3221225472 B，采样到的主进程峰值工作集为
9949184 B。

## 当前 API 连续运行

| 用例 | API 总命中 | 严格实体 | GraphQL 批次 | 处理 |
|---|---:|---:|---:|---|
| API-1UBQ | 1623 | 1588 | 16 | SELECTED_PROVISIONAL |
| API-O15116 | 0 | 0 | 0 | NO_STRICT_CANDIDATE |

O15116 在本轮 RCSB 严格候选为空后，UniProt `2026_03` 与 AlphaFold DB
`AF-O15116-F1` v6 完成逐层序列回验，模型、confidence
与 PAE 维度一致，形成 `source=alphafolddb` 的 S-09 交接候选。全批次共
25 次 HTTP 往返，累计下载
3041793 B。

## 检查矩阵

| ID | 检查 | 结果 |
|---|---|---|
| T6-C01 | fresh frozen-release candidate collection stays below the declared per-query cap | PASS |
| T6-C02 | 1UBQ fixed-release selection is reproducible | PASS |
| T6-C03 | TP53 four-chain ambiguity blocks automatic handoff | PASS |
| T6-C04 | fixed-release O15116 PDB search completes empty | PASS |
| T6-C05 | experimental full and partial coordinate mappings remain distinct | PASS |
| T6-C06 | live RCSB return_all_hits and metadata collection are complete | PASS |
| T6-C07 | live O15116 fallback is sequence-exact and ready for S-09 handoff | PASS |
| T6-C08 | task 5 failure, immutable replay and retry evidence remains valid | PASS |
| T6-C09 | S-08 and S-09 handoff shapes validate while consumers remain undeployed | PASS |
| T6-C10 | all five provisional rules stay attached and pending expert confirmation | PASS |

## 仍受门禁约束的项目

1. S07-EQ-01～05 继续 `PENDING`；专家结论不同需要换规则版本并重算。
2. 缺 accession 的真实 BLAST 正命中候选收集未完成；不得用 100 条封顶结果自动选 accession。
3. S-08/S-09 当前只完成交接结构验证，实际工具尚未部署。
4. OI-017 的生产状态机、等待/取消/恢复入口和逐工具 execution profile 等待 P0 v0.6。
5. 目标服务器本地数据库由接收方按既有交接方案部署和验收。

机器报告见 [task6_acceptance.json](task6_acceptance.json)，逐文件清单见
[artifact_manifest.json](artifact_manifest.json)。
