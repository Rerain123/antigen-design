# 当前一期源码区

本目录真实实现遵循 [现行范围](../docs/project/PHASE1_SCOPE_REBASELINE.md)：保留 N01-N18，N03 仅保留本地 BLAST、移除 IEDB 检索。原 18 节点 Mock 代码位于
[t01_phase1_mock](t01_phase1_mock)，包括规格加载、fixture、场景投影、生命周期、存储和工具 facade。

Dify 模块位于 [dify](t01_phase1_mock/dify)，模板唯一生成源为
[generator.py](t01_phase1_mock/dify/generator.py)；传输、校验、绑定和回归共享该实现边界。

新增本地解析与 R-58 工程探测位于 [t01_structure_mapping](t01_structure_mapping)，只生成待复核映射；
运行与科学批准分开，任务依据见 [专项](../docs/project/phase1/PHASE1_REAL_W1_R58_MAPPING.md)。

- 组件职责与实现边界：[架构](../docs/project/ARCHITECTURE.md)
- 独立通用运行层：[t01_phase1_real](t01_phase1_real)、[W1-09A 说明](../docs/project/phase1/PHASE1_REAL_W1_RUNTIME_IMPLEMENTATION.md)
- 实施依据与冻结评审：[一期任务索引](../docs/project/phase1/README.md)
- 当前阶段和下一任务：[STATUS](../docs/project/STATUS.md)
- 运行与验证：[运行手册](../docs/development/RUNBOOK.md)

冻结 Mock 源码不得原地替换为生产调用。旧 P0-P7 与 S07 从
[历史工程资产](../legacy/README.md)追溯，不复制回来充当一期实现。
