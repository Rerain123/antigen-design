# R-58 本地解析与映射记录

[机器结果](campaign_result.json)记录本批命令、源码 hash、输入身份和产物 hash。
[维护检查记录](maintenance_verification.json)记录专项/根测试、历史分区回归及冻结资产核对。
这是开发机上的本地解析与映射候选验证；甲方环境验收、算法签收、完整 W1 门禁与生产部署均未执行。

| 输入 | 本次事实 | 证据 |
|---|---|---|
| 历史本地 1UBQ + 独立来源序列 | 唯一候选 A 链，76 个位置完整对应；仍为 unverified | [映射](real-1ubq/mapping.json)、[重解析检查](real-1ubq/reparse_check.json) |
| 历史本地 5XZC + 全长 TP53 序列 | B/C/D/E 多个链/位置候选，unreliable；原文件仅 Cα，不能当正常全原子 SASA 样本 | [结构清单](real-5xzc/structure_inventory.json)、[候选与问题](real-5xzc/mapping.json) |
| 人工 PDB | 42 与 42A 分开；输入 ARG 中 R 缺失，数组保留 null | [映射](synthetic-pdb/mapping.json) |
| 人工 mmCIF | author 链 AUTH 与 label 链 LABEL 分开，保留原 MODEL 7 与插入码 | [映射](synthetic-mmcif/mapping.json) |

真实文件的来源与复用声明见 [样本清单](../../../../tests/fixtures/structure_mapping/real/SOURCE_MANIFEST.json)。
旧 S07 仅提供已存在的文件，本次程序没有结构数据库查询或模型调用。
候选通过工程检查也不自动升级为 verified；后续独立核验与生产条件见
[专项任务](../../../../docs/project/phase1/PHASE1_REAL_W1_R58_MAPPING.md)。

重跑时使用新输出目录，命令见 [运行手册](../../../../docs/development/RUNBOOK.md#本地结构解析与-r-58-映射)。
当前记录保存实际运行时点的版本与 hash，维护代码后不能据此声称新版本已执行过。
