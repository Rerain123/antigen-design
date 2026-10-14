# PH1-MOCK-M1 新一期 Mock v0.1 规格与验收基线 Backlog

> 状态：`COMPLETED / M1-01_TO_08_COMPLETED / M2_M3_M4_COMPLETED / MOCK_V0.1_FROZEN`  
> 日期：2026-09-04  
> 上级计划：[一期 18 节点交付计划](../PHASE1_DELIVERY_PLAN.md)  
> 本包只产出可实施规格，不修改冻结旧 Mock、不写新 Mock 代码、不运行科学工具。

## 1. 目标

把最新一期 18 节点图、节点 01 离线决定和专家原件中的现有规则，归并成一套可直接实现、
可自动验证的新一期 Mock v0.1 规格。该规格必须以 `N01-N18` 为业务主键，不复用 P0-P7 作为阶段或范围。

## 2. 已确认约束

- 一期恰有 18 个业务节点，并包含设计适用性 Gate 和 WT 直接交付分支。
- 节点 01 不含 S-07、RCSB PDB、AlphaFold DB 或联网回退；保留本地 AlphaFold3/ESMFold2。
- 当前输入基线为必填目标蛋白序列、宿主物种和可选结构；字段与格式先从专家资料归并。
- 节点 12 需要表达“验证不通过后受控重算”。
- 节点 16 为条件节点；节点 16 与 17 都汇入节点 18。
- 默认 Mock 表达完整一期；削减顺序只能是 16 → 07 → S-11，当前未批准任何 reduced profile。
- 旧 Mock 保持字节/行为基线独立；新 Mock 使用新 workflow、场景、run_id 和输出命名空间。

## 3. 已建立的物理边界

- 根目录 `src/`、`tests/`、`scripts/`、`dify/`、`discovery/` 只接收当前一期资产。
- 旧完整 Mock 已冻结在 `legacy/full-t01-mock-v0.1/`，不得在其生成器内追加一期目标。
- S07 代码、脚本、测试、文档、取证和本地数据已集中到 `legacy/s07/`，不得成为 N01 工具候选。
- M1 建包时根目录尚无一期实现，目录整理不计为功能完成；后续 M2 实现现已通过独立评审。

## 4. 工作项

| 工作项 | 交付内容 | 主责角色 | 状态 | 验收证据 |
|---|---|---|---|---|
| `PH1-MOCK-M1-01` | [来源—节点—S 步骤—工具—优先级矩阵](PHASE1_MOCK_M1_01_SOURCE_NODE_STEP_TOOL_PRIORITY_MATRIX.md) | 文档工程 + 算法复核 | `COMPLETED` | 18 节点无缺号、无旧范围回流 |
| `PH1-MOCK-M1-02` | [节点注册表及稳定 ID/显示名/输入输出责任](PHASE1_MOCK_M1_02_NODE_REGISTRY.md) | 后端 + 文档工程 | `COMPLETED` | `N01-N18` 唯一且可机器校验 |
| `PH1-MOCK-M1-03` | [边、Gate、WT 分支、重算、条件和汇合状态图](PHASE1_MOCK_M1_03_CONTROL_FLOW_STATE_GRAPH.md) | 后端 + Dify | `COMPLETED` | `E001-E027` 与一期原件逐边对照 |
| `PH1-MOCK-M1-04` | [一期请求、运行结果、节点结果、ArtifactRef、错误与审计 envelope](PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md) | 后端 | `COMPLETED` | Schema review draft 与四个示例均可解析 |
| `PH1-MOCK-M1-05` | [确定性场景模型及每节点 Mock 输出责任](PHASE1_MOCK_M1_05_DETERMINISTIC_SCENARIO_MODEL.md) | 测试 + 后端 | `COMPLETED` | 21 个场景只复制字面量控制与 stub 事实，不含科学计算 |
| `PH1-MOCK-M1-06` | [新旧资产命名、目录、生成、绑定和回归隔离](PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md) | Dify + 后端 | `COMPLETED` | 2 个 Workflow、26 个工具、21 个场景引用及路径/绑定/回归边界无覆盖风险 |
| `PH1-MOCK-M1-07` | [验收场景、机器断言和 fixture manifest](PHASE1_MOCK_M1_07_ACCEPTANCE_ASSERTIONS_FIXTURE_MANIFEST.md) | 测试 | `COMPLETED` | 21 案例、23 提交、4/16 checkpoint、18+44 断言与 10 门禁闭合 |
| `PH1-MOCK-M1-08` | [工程/算法/产品一致性评审与缺口清单](PHASE1_MOCK_M1_08_CONSISTENCY_REVIEW.md) | 项目负责人 | `COMPLETED` | 四项具名结论、日期、版本、5 组已解决 finding 和 OI 分级 |

## 5. 最低场景集

1. 完整主链：适合设计，节点 01～18 按图完成。
2. 甲方提供合法结构：节点 01 不运行结构预测，但仍形成节点 01 结果并进入 S-09 语义。
3. 无结构：模拟本地 AF3/ESMFold2 路由；不得出现外部数据库工具或网络补齐。
4. 不适合设计：节点 10 后进入 WT 说明并直接到节点 18，节点 11～17 不伪装为成功。
5. 节点 12 首轮不通过：按 24/0.1 → 48/0.3 → 64/0.5 表达最多三轮、累计 136 个设计，
   并保留每轮尝试与停止原因。
6. 无表达宿主：节点 16 以明确条件跳过状态进入节点 18，不以失败或空结果冒充完成。
7. 节点 16/17 汇合：节点 18 能区分完成、条件跳过、失败和未执行。
8. 工具失败、部分结果、取消、超时、恢复和重复提交：只使用稳定状态/错误枚举。
9. 排除项扫描：S-07、S-06、S-23、S-32 及其他一期排除能力不可调用。
10. Mock 隔离：所有结果标记 `MOCK_DATA`、`scientific_compute=false`，且不改变旧 25 场景结果。

## 6. 必须先查专家资料的内容

- 顶层字段、可选设计目标/表达宿主及节点 16 条件，关联 OI-004。
- 各节点输入输出、失败语义、重试/停止条件和下游消费。
- 节点 13/15 的现行规则，关联 OI-022；Mock 只表达确定性状态，不自行补阈值。
- 节点 18 的 S-42/43/44 输出与 Agent C 边界，关联 OI-013/OI-014。

已有原文直接归并；只有真实互斥或会改变业务路由的缺口才形成定点问题，不向用户发送宽泛字段问卷。

## 7. 退出条件

- 18 个节点逐项对应最新图，无缺号、无新增、无 P0-P7 阶段映射。
- 当前节点 01 离线决定及一期排除项成为机器可测断言。
- 输入、边、Gate、WT 分支、重算、条件、汇合和终态均有唯一契约。
- 新旧 Mock 的 workflow/tool/scenario/run_id/template/bound 命名与存储完全隔离。
- fixture manifest 和预期断言可直接交给 `PH1-MOCK-M2` 实现。
- 所有未决规则附来源和影响，Mock 不用臆测值填空。
- 当前文档检查、冻结旧完整 Mock 74 项测试和 S07 备用包 41 项测试分别通过；历史合计与
  当前控制面测试合计仍为 116，但不得计入一期功能完成度。

本包已通过并冻结为 `T01-PHASE1-MOCK-M1-BASELINE-v0.1`。其后
[M2 Backlog](PHASE1_MOCK_M2_BACKLOG.md)的 `M2-01～09` 已实施并通过
[M2 实现评审](PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md)；M3 随后独立建立 Dify 资产并通过
[M3 实现评审](PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md)。M1/M2 历史交付仍未提前写入 Dify DSL；
M4 随后通过独立回归并冻结 Mock v0.1，详见
[M4 实现与冻结评审](PHASE1_MOCK_M4_IMPLEMENTATION_REVIEW.md)。下一项为 `PH1-REAL-W1 READY`。
