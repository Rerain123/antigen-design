# 当前一期 Dify 资产区

一期 Mock 的模板、绑定、实例证据和回归资产位于 [t01-phase1-mock-v0.1](t01-phase1-mock-v0.1)。
生成、绑定、导入和冻结记录统一从 [Dify 实现入口](../工作流设计/03-Dify实现/README.md)进入。

| 内容 | 目录 |
|---|---|
| 单一生成源派生的未绑定 DSL | [templates](t01-phase1-mock-v0.1/templates) |
| provider 配置与派生绑定 | [config](t01-phase1-mock-v0.1/config)、[bound](t01-phase1-mock-v0.1/bound) |
| Mock 输入和节点产物 | [fixtures](t01-phase1-mock-v0.1/fixtures) |
| 实例执行证据与回归冻结 | [evidence](t01-phase1-mock-v0.1/evidence)、[regression](t01-phase1-mock-v0.1/regression) |

日常验证使用 [运行手册](../docs/development/RUNBOOK.md)中的只读命令，不手改冻结模板、bound
或 manifest。规格中的 SPEC_ONLY/DECLARED_NOT_RUN 是冻结时点声明，实际执行结果另见评审。

当前任务与生产状态见 [STATUS](../docs/project/STATUS.md)。Mock 资产不代表科学能力；
旧 Master + P0-P7 从 [历史工程资产](../legacy/README.md)追溯，不导入为一期应用。
