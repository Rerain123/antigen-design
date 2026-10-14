# 当前一期 Dify 实现入口

本目录保存一期 Mock 的实现注册；DSL、绑定及证据位于
[dify/t01-phase1-mock-v0.1](../../dify/t01-phase1-mock-v0.1)。
当前任务与生产状态统一见 [STATUS](../../docs/project/STATUS.md)。

## 规格与资产

| 内容 | 入口 |
|---|---|
| 命名、目录、生成与绑定隔离 | [M1-06](../../docs/project/phase1/PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md) |
| 机器注册 | [资产注册表](T01_PHASE1_MOCK_ASSET_REGISTRY_v0.1.json)、[注册表 Schema](T01_PHASE1_MOCK_ASSET_REGISTRY_SCHEMA_v0.1.json) |
| 未绑定模板 | [main](../../dify/t01-phase1-mock-v0.1/templates/T01_Phase1_Mock_v0.1.template.dify.yml)、[debug](../../dify/t01-phase1-mock-v0.1/templates/T01_Phase1_Mock_v0.1_Debug.template.dify.yml) |
| 环境绑定 | [provider manifest](../../dify/t01-phase1-mock-v0.1/config/provider-bindings.local_dify_1_17.json)、[main bound](../../dify/t01-phase1-mock-v0.1/bound/local_dify_1_17/T01_Phase1_Mock_v0.1.bound.dify.yml)、[debug bound](../../dify/t01-phase1-mock-v0.1/bound/local_dify_1_17/T01_Phase1_Mock_v0.1_Debug.bound.dify.yml) |
| fixture 与验收规格 | [fixture manifest](../../dify/t01-phase1-mock-v0.1/fixtures/T01_PHASE1_MOCK_FIXTURE_MANIFEST_v0.1.json)、[acceptance Catalog](../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_ACCEPTANCE_CATALOG_v0.1.json) |

## 实施与冻结证据

- [M3 构建、绑定、导入与实例验收评审](../../docs/project/phase1/PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md)
- [M3 机器验收结果](../../dify/t01-phase1-mock-v0.1/evidence/m3/local_dify_1_17/T01_PHASE1_MOCK_M3_ACCEPTANCE_RESULT_v0.1.json)
- [M4 独立回归与冻结评审](../../docs/project/phase1/PHASE1_MOCK_M4_IMPLEMENTATION_REVIEW.md)
- [Mock v0.1 freeze manifest](../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_FREEZE_MANIFEST_v0.1.json)
- [完整一期任务索引](../../docs/project/phase1/README.md)

注册表中的 SPEC_ONLY 表示 M1-06 冻结时点，后续生成、导入与执行由上面的证据记录。
模板只能来自单一生成源，bound 只能由模板和 provider manifest 派生；日常只读检查及实例操作条件
见 [运行手册](../../docs/development/RUNBOOK.md)。这些都是 Mock 资产，不构成生产部署。
