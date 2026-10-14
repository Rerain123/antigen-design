# R-58 与 FreeSASA 边界开发记录 · 2026-09-05

任务与使用限制见 [专项说明](../../../../docs/project/phase1/PHASE1_REAL_W1_R58_SASA_BOUNDARIES.md)，
当前进度见 [STATUS](../../../../docs/project/STATUS.md)。本批只提供开发验证，不签发科学映射或生产结果。

| 入口 | 内容 |
|---|---|
| [before.json](before.json)、before/ | 修改前代码/契约和专家原件 hash；首次准备脚本另留副本 |
| inputs/、[preparation_results.json](preparation_results.json) | 首次准备记录；人工多链 label B 与原水实例冲突，作为缺陷证据保留，不用于实际工具运行 |
| [prepared/case_spec.json](prepared/case_spec.json) | 修正后先行声明的输入与预期；多链采用作者 B / label C，原始 1UBQ 字节保持一致 |
| [prepared/preparation_results.json](prepared/preparation_results.json) | 解析、映射、转换结果；每例保存原输入、清单、映射和适用的派生 PDB |
| [raw-run/execution.json](raw-run/execution.json) | 固定镜像、禁网命令、退出码和实际执行源 hash |
| [raw-run/result/campaign.json](raw-run/result/campaign.json) | 实际 FreeSASA/分类器结果；各例保留原子、半径、面积与开发对齐诊断 |
| [assessment.json](assessment.json) | 编号不变性、缺失位置、多链遮挡、歧义和拒绝路径的核验结果 |
| after/、[manifest.json](manifest.json) | 实际执行源码和契约快照、本批完整文件 hash |
| [verify_evidence.py](verify_evidence.py) | 只读完整性及快照复算；同时核对原 R-58 证据和专家原件未变 |

新案例全部来自已有本地样本；没有查询或下载新结构。人工修改不能继承原始蛋白的科学参考身份。
`normal_rsa_result` 与 `buried_fraction` 均为 null，`usable_for_pipeline=false`；出域原比值仅保存为诊断。
命令、后续新目录执行与校验要求见 [运行手册](../../../../docs/development/RUNBOOK.md#r-58-与-freesasa-边界开发验证)。
