# 当前一期数据契约入口

本目录保存派生契约与场景资产；真实工具公共接口与冻结 Mock 分开维护。科学 payload 必须从
[权威业务资料](../01-业务依据/README.md)归并，不能从 synthetic 示例反推。
当前实施阶段和开放项入口见 [STATUS](../../docs/project/STATUS.md)。

| 契约 | 规格与机器资产 |
|---|---|
| W1 真实运行工程契约 | [v0.1 Schema、登记与验收案例](phase1-real-v0.1/README.md)；上层任务生命周期，逐工具科学 G1 独立 |
| R-58 映射文件与便携检查 | [结构映射规范](tool-interface-v0.1/structure_mapping/README.md)；待核验候选与已批准映射明确区分 |
| 首批真实工具公共接口（独立工程约定） | [规范、Schema、示例与离线校验器](tool-interface-v0.1/README.md)；完整生产 G1 另行评审 |
| 冻结 Mock 请求、运行、节点、ArtifactRef、错误和审计 | [M1-04](../../docs/project/phase1/PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md)、[JSON Schema](T01_PHASE1_MOCK_ENVELOPE_SCHEMA_v0.1.json) |
| 请求与终态示例 | [请求](examples/T01_PHASE1_MOCK_REQUEST_EXAMPLE_v0.1.json)、[候选](examples/T01_PHASE1_MOCK_RUN_CANDIDATE_EXAMPLE_v0.1.json)、[WT](examples/T01_PHASE1_MOCK_RUN_WT_EXAMPLE_v0.1.json)、[失败](examples/T01_PHASE1_MOCK_RUN_FAILURE_EXAMPLE_v0.1.json) |
| 确定性场景和节点输出责任 | [M1-05](../../docs/project/phase1/PHASE1_MOCK_M1_05_DETERMINISTIC_SCENARIO_MODEL.md)、[Catalog](T01_PHASE1_MOCK_SCENARIO_CATALOG_v0.1.json)、[Catalog Schema](T01_PHASE1_MOCK_SCENARIO_CATALOG_SCHEMA_v0.1.json) |
| 命名、资产与绑定 | [Dify 实现入口](../03-Dify实现/README.md) |
| fixture、checkpoint 与验收规格 | [M1-07](../../docs/project/phase1/PHASE1_MOCK_M1_07_ACCEPTANCE_ASSERTIONS_FIXTURE_MANIFEST.md) |
| 实际执行和冻结证据 | [一期评审索引](../../docs/project/phase1/README.md) |

Mock 契约的控制结果只来自 SCENARIO_LITERAL，不能携带科学计算结果；冻结规格不回写后续
执行状态。生产工具 payload、CandidateRecord、AgentCHandoff 与 FailureReport 的派生实现
需单独完成真实阶段契约门禁，不直接继承旧 P0-P7 契约。

旧契约从 [历史工程资产](../../legacy/README.md)追溯。
