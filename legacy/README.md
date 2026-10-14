# T-01 历史工程资产

本目录把仍需保留但不属于当前一期的工程资产按身份隔离。它不是当前开发入口，也不改变
任何历史结论。

| 目录 | 内容 | 当前地位 |
|---|---|---|
| [full-t01-mock-v0.1](full-t01-mock-v0.1/README.md) | 旧 Master + P0-P7 Mock、Dify、契约、测试和运行记录 | `FROZEN_LEGACY_REFERENCE` |
| [s07](s07/README.md) | S07 专项代码、脚本、测试、文档、取证、本地数据和工具 | `REMOVED_FROM_PHASE1 / BACKUP_ONLY` |
| [project-history](project-history/README.md) | 旧 P0/P0-P7 计划、评审、清理记录和专家资料接收历史 | `HISTORY_ONLY` |

根目录 `docs/`、`src/`、`tests/`、`scripts/`、`dify/` 和 `discovery/` 只服务当前一期 `N01-N18`。
历史包通过回归不代表一期完成，也不代表任何真实科学工具已经部署。

## 历史引用链接的现存入口

2026-09-07 全面检查发现，6 份历史文档中有 29 条引用式链接仍使用搬迁前的相对路径。以下目标文件均实际存在；历史执行报告和原时点文档保留原文，通过下表查阅。检查器单独报告这些历史失效链接，不将其计为现行导航通过，也不恢复旧能力到一期。

<details>
<summary>展开旧引用对应的现存文件</summary>

| 历史引用目标 | 现存文件 |
|---|---|
| candidate_structure_manifest.json | [打开文件](s07/discovery/p0/s07/p0-s07-discovery-20260901-a/reports/candidate_structure_manifest.json) |
| sequence_mapping_report.json | [打开文件](s07/discovery/p0/s07/p0-s07-discovery-20260901-a/reports/sequence_mapping_report.json) |
| P0_M1B_OUTPUT_AUDIT.md | [打开文件](s07/discovery/p0/s07/p0-s07-m1b-20260901-d/reports/P0_M1B_OUTPUT_AUDIT.md) |
| TASK3_EVIDENCE_REPORT.md | [打开文件](s07/discovery/p0/s07/p0-s07-task3-mmseqs-20260902-a/reports/TASK3_EVIDENCE_REPORT.md) |
| TASK4_API_EVIDENCE_REPORT.md | [打开文件](s07/discovery/p0/s07/p0-s07-task4-uniprot-afdb-20260902-a/reports/TASK4_API_EVIDENCE_REPORT.md) |
| artifact_index.json | [打开文件](s07/discovery/p0/s07/p0-s07-task5-contract-20260903-b/artifact_index.json) |
| TASK5_CONTRACT_VALIDATION_REPORT.md | [打开文件](s07/discovery/p0/s07/p0-s07-task5-contract-20260903-b/reports/TASK5_CONTRACT_VALIDATION_REPORT.md) |
| S07_EXPERT_CONFIRMATIONS.md | [打开文件](s07/docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md) |
| S07_IMPLEMENTATION_TASKS.md | [打开文件](s07/docs/archive/p0/S07_IMPLEMENTATION_TASKS.md) |
| S07_LEGACY_RUNBOOK.md | [打开文件](s07/docs/archive/p0/S07_LEGACY_RUNBOOK.md) |
| S07_TASK5_RESULT_CONTRACT.md | [打开文件](s07/docs/archive/p0/S07_TASK5_RESULT_CONTRACT.md) |
| build_s07_task5_contract_evidence.py | [打开文件](s07/scripts/build_s07_task5_contract_evidence.py) |
| s07_task5_contract.py | [打开文件](s07/scripts/s07_task5_contract.py) |
| test_s07_task5_contract.py | [打开文件](s07/tests/test_s07_task5_contract.py) |
| T01_算法图_v10_20260821.md | [打开文件](../工作流设计/01-业务依据/T01_算法图_v10_20260821.md) |
| AgentA_Schema_v10.5_20260902.md | [打开文件](../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md) |
| AgentA_SKILL_v10.5_20260902.md | [打开文件](../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md) |
| AgentA_SOP_v10.5_20260902.md | [打开文件](../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md) |
| ToolSpec_A5_DeepTMHMM_v10.5.md | [打开文件](../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_A5_DeepTMHMM_v10.5.md) |
| ToolSpec_C34_FreeSASA_v10.5.md | [打开文件](../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C34_FreeSASA_v10.5.md) |
| ToolSpec_结构预测获取链_v10.5.md | [打开文件](../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md) |
| 一期实施环境清单_v10.5.md | [打开文件](../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期实施环境清单_v10.5.md) |
| 一期裁剪算法图（一期 18 节点 + 落地优先级）.md | [打开文件](<../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>) |
| 抗原智能体一阶段边界及核心能力说明.pdf | [打开文件](../工作流设计/01-业务依据/抗原智能体一阶段边界及核心能力说明.pdf) |

</details>
