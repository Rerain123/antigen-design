# B1 本地结构与映射评审证据

本批范围见 [限定评审](../../../../docs/project/phase1/PHASE1_REAL_W1_B1_REVIEW.md)，阶段见 [STATUS](../../../../docs/project/STATUS.md)。

- [expected_cases.json](expected_cases.json)：执行前声明的工程预期、原始来源/hash、文件选择。
- [assessment.json](assessment.json)：逐例实测及未授予科学资格的结论。
- inputs/、results/：独立输入、全结构清单、映射候选或明确拒绝诊断。
- [environment.json](environment.json)：本机 Python/Biopython 环境。
- [manifest.json](manifest.json)：源码、草案、评审、输入与产物 hash；最终维护记录另见 [验证记录](../../../../docs/project/phase1/PHASE1_REAL_W1_B1_VERIFICATION.json)。

输入含两个用户授权的历史真实结构，其余均为人工或既有人工派生边界。短序列与人工坐标仅用于工程验证，
不能作为一期正常业务输入、独立科学留出或预测结果。没有运行 FreeSASA、AF3/ESMFold2 或生产适配器。
只读核验可加 --reparse 重新解析文件；命令见 [运行手册](../../../../docs/development/RUNBOOK.md#w1-08b1-评审准备复核)。
prepare_w1_b1_review.py 保留首次构造过程，已拒绝覆盖本批和现有草案，不能当日常重跑命令。
