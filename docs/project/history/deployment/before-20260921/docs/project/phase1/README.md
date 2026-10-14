# 一期任务与证据索引

日常从 [STATUS 当前任务入口](../STATUS.md)接手，再读其链接的交付任务页或计划章节。
整体依赖和放行规则见 [交付计划](../PHASE1_DELIVERY_PLAN.md)。

现行阶段计划：[W1](PHASE1_REAL_W1_BACKLOG.md)、[W2 本地检索与表位分析](PHASE1_REAL_W2_PLAN.md)、[W3 糖基化、同源保守性与功能域](PHASE1_REAL_W3_PLAN.md)、[W4 原蛋白可开发性与设计判断](PHASE1_REAL_W4_PLAN.md)、[W5 候选设计、验证与受控重算](PHASE1_REAL_W5_PLAN.md)、[W6 表位保护、稳定性与综合排序](PHASE1_REAL_W6_PLAN.md)。每阶段只维护一份，当前执行包由 STATUS 指定。
现行范围保留全部 18 节点，N03 仅保留本地 BLAST、移除 IEDB 检索；下方 Mock 及原件/旧任务记录保留原时点工具行为，不能覆盖 [最新范围](../PHASE1_SCOPE_REBASELINE.md)。
下方前序 backlog、准备与评审只作规则/实现/执行时点参考，旧开发停止条件由现行计划覆盖，不逐份作为接手前置。

W1 已有工具用法见 [DeepTMHMM](PHASE1_REAL_W1_BACKLOG.md)与 [本地结构分析链](PHASE1_REAL_W1_BACKLOG.md)；最新验收摘要、批次索引与下一项只在 STATUS 维护。

<details>
<summary>查某个工具的前序实现、规则与证据</summary>

| 主题 | 实现与执行证据 | 早期准备或补充资料 |
|---|---|---|
| 通用运行层 | [接口与实现](PHASE1_REAL_W1_RUNTIME_IMPLEMENTATION.md)、[文件修复](PHASE1_REAL_W1_RUNTIME_FILE_FIX.md) | [契约设计](PHASE1_REAL_W1_CONTRACT_DESIGN.md)、[原任务](PHASE1_REAL_W1_RUNTIME_BACKLOG.md) |
| DeepTMHMM | [Academic 禁网实测](PHASE1_REAL_W1_DEEPTMHMM_OFFLINE.md)、[原包边界](PHASE1_REAL_W1_B2_BOUNDARIES.md)、[B2 评审](PHASE1_REAL_W1_B2_REVIEW.md) | [SDK/公开资料](PHASE1_REAL_W1_DEEPTMHMM_G0.md)、[B2 准备任务](PHASE1_REAL_W1_B2_REVIEW_BACKLOG.md) |
| 结构与映射 | [B1 评审](PHASE1_REAL_W1_B1_REVIEW.md)、[输入事实](PHASE1_REAL_W1_B1_ENGINEERING_REVIEW.md)、[R-58/面积边界](PHASE1_REAL_W1_R58_SASA_BOUNDARIES.md) | [初始解析](PHASE1_REAL_W1_R58_MAPPING.md)、[B1 原任务](PHASE1_REAL_W1_B1_REVIEW_BACKLOG.md)、[输入补强任务](PHASE1_REAL_W1_B1_ENGINEERING_BACKLOG.md) |
| FreeSASA/S-09 | [消费者验证](PHASE1_REAL_W1_B1_FREESASA_REVIEW.md)、[参数/参考与先行决定](PHASE1_REAL_W1_FREESASA_S09_DECISION.md) | [首次实测](PHASE1_REAL_W1_FREESASA_G0.md)、[规则冲突](PHASE1_REAL_W1_S09_RULE_REVIEW.md)、[消费者原任务](PHASE1_REAL_W1_B1_FREESASA_BACKLOG.md) |
| 结构预测与环境 | [AF3/ESMFold2 身份、资产和输入](PHASE1_REAL_W1_STRUCTURE_PREDICTION_G0.md) | [环境样本登记](PHASE1_REAL_W1_PREPARATION.md)、[原 W1 规则/依赖/案例](PHASE1_REAL_W1_REFERENCE.md) |
| W2 BepiPred / NetMHC / BLAST / N06 | [W2 调用与完成标准](PHASE1_REAL_W2_PLAN.md)、[NetMHC 完成索引](../../../discovery/t01-phase1-real/w2/netmhc-integration-20260907/acceptance-r03/index.json)、[BLAST 引擎索引](../../../discovery/t01-phase1-real/w2/blast-integration-20260907/acceptance-r03/index.json)、[N03→N06 现行联调索引](../../../discovery/t01-phase1-real/w2/epitope-map-integration-20260907/acceptance-r06/index.json) | [NetMHC 原包到齐前预检](../../../discovery/t01-phase1-real/w2/netmhc-integration-20260907/preflight.json)；BLAST 服务器目标库见 OI-028 |
| W3 N07 | [W3 调用与完成标准](PHASE1_REAL_W3_PLAN.md)、[独立扫描索引](../../../discovery/t01-phase1-real/w3/glycosylation-integration-20260907/acceptance-r01/index.json)、[N06 真实来源联调](../../../discovery/t01-phase1-real/w2/epitope-map-integration-20260907/acceptance-r06/index.json) | 非 20 aa 热点窗口换算见 OI-029 |
| W3 N08 | [本机接口与完成标准](PHASE1_REAL_W3_PLAN.md#n08-本机调用与接口)、[最终工程索引](../../../discovery/t01-phase1-real/w3/homology-integration-20260907/acceptance-r05/index.json) | 科学分支与服务器目标验收见 OI-030 |
| W3 N09 | [本机接口](PHASE1_REAL_W3_PLAN.md#n09-本机调用与接口)、[最终工程索引](../../../discovery/t01-phase1-real/w3/domains-integration-20260907/acceptance-r04/index.json) | OI-006/031 与服务器目标注释库验收 |
| W4 N10（部分） | [本机接口与完成边界](PHASE1_REAL_W4_PLAN.md#n10-本机调用与接口)、[现行部分工程索引](../../../discovery/t01-phase1-real/w4/developability-integration-20260908/acceptance-r14/index.json) | OI-025/032/033；GUI 对标已闭合，仍无 overall、N10 未完成、设计 Gate 未评估 |
| W5 N11 ProteinMPNN | [本机接口与工程边界](PHASE1_REAL_W5_PLAN.md#n11-本机调用与接口)、[固定原工具/权重登记](../../../src/t01_phase1_real/development/proteinmpnn/assets.json) | OI-001/002/006/007/015 等适用科学权限、结构消费与目标验收；正式 Gate 和 Agent C 继续关闭 |
| W5 N12 ESM-IF1 | [同 WT 基线与 N11 回连接口](PHASE1_REAL_W5_PLAN.md#n12-本机调用与接口)、[固定模型/环境登记](../../../src/t01_phase1_real/development/esm_if1/assets.json) | OI-008/015/022、完整结构复核与科学签收；完整 N12/W5、正式 Gate 和 Agent C 继续关闭 |
| W5 N11 权限 / N12 负担工程 | [合并后端接口](PHASE1_REAL_W5_PLAN.md#权限与负担本机接口)、[固定标度与工程档值](../../../src/t01_phase1_real/development/design_backend/scales.json) | OI-001/002/006/007/008/015 等科学签收、完整设计与验证；工程结果不改变 R-35 原判定 |
| W6 ThermoMPNN / FoldX | [稳定性工具本机接口](PHASE1_REAL_W6_PLAN.md#稳定性工具本机接口)、[ThermoMPNN r05 工程索引](../../../discovery/t01-phase1-real/w6/thermompnn-integration-20260908/acceptance-r05/index.json)、[FoldX r05 工程索引](../../../discovery/t01-phase1-real/w6/foldx-integration-20260909/acceptance-r05/index.json)、[FoldX 独立复核](../../../discovery/t01-phase1-real/w6/foldx-validation-20260909/evidence-audit-r02.json) | 双引擎本机工程接入完成但未科学签收；完整 N14/N17/W6、跨引擎科学消费、目标复现与部署未完成 |
| W6 N14 回连 / N15 筛选排序工程 | [逐变体报告接口](PHASE1_REAL_W6_PLAN.md#n14n15-逐变体报告本机接口)、[最终真实验收 r03](../../../discovery/t01-phase1-real/w6/variant-report-integration-20260909/acceptance-r03/index.json)、[证据与独立算术审计](../../../discovery/t01-phase1-real/w6/variant-report-validation-20260909/evidence-audit-r01.json) | 原24条全部淘汰；不同WT的FoldX工程突变单列。N13、N10缺项、重算、科学规则与正式交付仍未完成 |
| W6 N13 表位保护工程 | [配对接口](PHASE1_REAL_W6_PLAN.md#n13-表位保护本机接口)、[主批次r05](../../../discovery/t01-phase1-real/w6/n13-integration-20260909/acceptance-r05/index.json)、[独立审计](../../../discovery/t01-phase1-real/w6/n13-validation-20260909/evidence-audit-r01.json)、[补充来源/错链验收](../../../discovery/t01-phase1-real/w6/n13-integration-20260909/supplement-r01/index.json) | WT/变体真实预测仍无热点，原24条淘汰保留；完整科学保护、RMSD/shape/非同一区间对齐与科学交付未开放 |

W4 Gate 与 WT 子路径的工程调用和字段生产者见 [本机接口](PHASE1_REAL_W4_PLAN.md#gate-与-wt-草稿本机接口)，实测见 [WT 草稿 r02 索引](../../../discovery/t01-phase1-real/w4/wt-draft-integration-20260908/acceptance-r02/index.json)；科学 Gate、正式 WT 和 Agent C 生产接口按 OI-013/014/021 保持未完成。

[公共接口](../../../工作流设计/02-数据契约/tool-interface-v0.1/README.md)、[原工具交接资料](handoffs/README.md)、[历次进度与验证摘要](../STATUS_HISTORY_20260906.md)按需查询。
原始执行产物由各评审链接到 discovery；不要把旧准备结论当成最新状态。

</details>

<details>
<summary>查已完成 Mock 的规格、验收与冻结证据</summary>

| 基线 | 规格 | 验收 |
|---|---|---|
| M1 | [任务](PHASE1_MOCK_V01_BACKLOG.md) | [一致性评审](PHASE1_MOCK_M1_08_CONSISTENCY_REVIEW.md) |
| M2 | [任务](PHASE1_MOCK_M2_BACKLOG.md) | [实现评审](PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md) |
| M3 | [任务](PHASE1_MOCK_M3_BACKLOG.md) | [Dify 验收](PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md) |
| M4 | [任务](PHASE1_MOCK_M4_BACKLOG.md) | [冻结评审](PHASE1_MOCK_M4_IMPLEMENTATION_REVIEW.md)、[manifest](../../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_FREEZE_MANIFEST_v0.1.json) |

字段/路由定位：[来源矩阵](PHASE1_MOCK_M1_01_SOURCE_NODE_STEP_TOOL_PRIORITY_MATRIX.md)、[节点注册](PHASE1_MOCK_M1_02_NODE_REGISTRY.md)、[状态图](PHASE1_MOCK_M1_03_CONTROL_FLOW_STATE_GRAPH.md)、[envelope](PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md)、[场景](PHASE1_MOCK_M1_05_DETERMINISTIC_SCENARIO_MODEL.md)、[命名隔离](PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md)、[验收规格](PHASE1_MOCK_M1_07_ACCEPTANCE_ASSERTIONS_FIXTURE_MANIFEST.md)。
Dify 定位：[目标预检](PHASE1_MOCK_M3_01_DIFY_TARGET_DSL_PREFLIGHT.md)、[调用映射](PHASE1_MOCK_M3_02_WORKFLOW_INVOCATION_GRAPH_CONTRACT.md)。

SPEC_ONLY/DECLARED_NOT_RUN 表示冻结时点，不能据此重开已完成任务或回写原件。Mock 不能代替科学验收。
旧完整 Mock、S07 和旧计划仅从 [legacy](../../../legacy/README.md)进入。

</details>
