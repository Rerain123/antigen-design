# B1 → FreeSASA 消费者独立证据

本批保留开发工程验证时点，现行阶段与下一步见 [STATUS](../../../../docs/project/STATUS.md)。
评审见 [FreeSASA 消费者评审](../../../../docs/project/phase1/PHASE1_REAL_W1_B1_FREESASA_REVIEW.md)，
复核命令统一见 [运行手册](../../../../docs/development/RUNBOOK.md)。

- expected_cases.json：工具执行前声明的输入、来源 hash、MODEL/链/路径、字面量地址及正反例预期。
- inputs / b1_bundles / prepared：原始输入、实际 B1 调用产物和消费者完整副本；原始事实保持原字节。
- preparation_execution.json：45 次 B1 CLI、44 次消费者 CLI 及 1 次空上下文 Python API 边界调用。
- execution：固定镜像实际禁网调用、软件版本、原子身份/坐标/半径、原始面积及按原地址回连；每例独立记录调用与计算状态。
- assessment.json：18 组原始面积成功、26 组准备拒绝、1 组未知半径计算前拒绝，4 组路径精确对照及乱序回连。
- protected_before.json / after / manifest.json：原件、旧源码/证据、首轮失败记录以及本批执行源码和产物的只读字节校验。
- source_review.json / environment.json：专家条款、后续用户决定、公开 API 文档与实际软件版本。

第一轮 [独立试验记录](../b1-freesasa-consumer-20260906/initial_assessment.json)保留一次夹具坐标精度问题：
浮点加法产生的长小数经 PDB 三位小数转换后不同，不能满足等坐标精确对照的前提。
本批重新声明并生成三位小数工程坐标，原记录没有改写；生产者、消费者和科学容差没有因此放宽。

人工几何只证明工程接口与数值回连，不是科学准确率参考。
原始 1UBQ CIF 的未知 iCode、历史派生 PDB 的非完整占有率继续拒绝，未增加已批准真实样本。
本批统一保留 NOT_DEPLOYED / scientific_approval=null / usable_for_pipeline=false。
