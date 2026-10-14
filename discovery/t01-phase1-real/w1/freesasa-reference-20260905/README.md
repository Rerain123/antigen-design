# FreeSASA 独立数值参考批次

本批复用历史 1UBQ 的本地 PDB 派生文件，在已有固定 Docker 镜像中禁网执行；不下载新结构。
用于参数收敛、独立数值比较和异常发现，不产生正常项目 RSA 或科学放行。

| 文件 | 用途 |
|---|---|
| [研究规格](reference_spec.json)、[加密原因](refinement_spec.json) | 外部参考、参数扫描、先行数值预算；首轮参考未收敛后追加密度 |
| [输入来源](inputs/SOURCE_MANIFEST.json) | 本批副本及前序 PDB 派生链 |
| [首次运行](run/execution.json)、[加密运行](refinement/execution.json) | 实际 Docker argv、固定镜像、时间、退出码；同目录保留 stdout/stderr/result |
| [比较程序](compare_reference.py)、[加密程序](refine_reference.py) | FreeSASA Lee–Richards 与 Biopython Shrake–Rupley；相同坐标和半径 |
| [评估](assessment.json) | 参数差、收敛、G76 出域和下游诊断；科学结论明确未批准 |
| [manifest](manifest.json)、[只读核验](verify_reference.py) | 程序、输入、产物和裁决草案 hash；复算关键数字及保护未决状态 |
| [维护检查](maintenance_verification.json) | 当前根测试、文档、冻结资产、旧批次及后续用户采用来源核验 |

解释与当前先行采用状态见 [专项决定](../../../../docs/project/phase1/PHASE1_REAL_W1_FREESASA_S09_DECISION.md)。
assessment 保留数值研究时点的待决状态；后续用户先行采用由独立来源记录承载，不修改旧产物。
命令见 [运行手册](../../../../docs/development/RUNBOOK.md#freesasa-独立数值参考)。
原 FreeSASA/S-09 批次、冻结 Mock 和专家原件均不回写。
