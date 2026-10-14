# PH1-MOCK-M1-08 工程/算法/产品一致性评审与缺口清单

> 状态：`COMPLETED / PASS_FOR_PH1_MOCK_M2`  
> 评审日期：2026-09-04  
> 评审基线：`T01-PHASE1-MOCK-M1-BASELINE-v0.1`  
> 评审范围：`PH1-MOCK-M1-01`～`M1-07`  
> 评审执行身份：Codex（项目规格一致性审查）；不冒充业务、算法或 Agent C 人员签字  
> 生产状态：`NOT_DEPLOYED`

## 1. 最终结论

`PH1-MOCK-M1` 规格与验收基线通过一致性评审，可以进入 `PH1-MOCK-M2` 实现。放行含义严格为：

- 可以按冻结的命名、目录、场景、fixture 和断言实现**确定性 Mock 后端与场景引擎**；
- 不得改变 `N01-N18`、`E001-E027`、九种状态、21 个场景或字面量控制结果；
- 不得执行或伪造科学计算，不得创建生产适配器，不得宣称 Dify/Agent C 已部署；
- M2、M3、M4 的运行型断言仍为 `DECLARED_NOT_RUN`，本评审没有提前把它们记为通过。

评审关闭了本轮发现的 5 组规格问题。修正后为 **0 个 M1 blocker、0 个未归属冲突**；现存开放项
均有既有 OI 编号、责任人和最迟时点，且被隔离在生产科学规则、生产接口或未启用的 reduced
profile 之外，不阻塞确定性 Mock M2。

## 2. 具名评审结论

“具名”在本记录中指明确的评审视角、结论 ID、范围和判定；不虚构自然人审批。

| 结论 ID | 评审视角 | 结论 | 判定依据 |
|---|---|---|---|
| `M1-08-ENG` | 工程一致性 | `PASS_FOR_M2` | 版本链、Schema、ID、引用、目录、工具、fixture、断言和新旧隔离闭合；M2 输入可机器解析 |
| `M1-08-ALG` | 算法边界一致性 | `PASS_FOR_MOCK_ONLY` | 所有控制只来自 `SCENARIO_LITERAL`，fixture/输出禁止科学值；未决阈值与算法规则未被猜测 |
| `M1-08-PROD` | 产品范围一致性 | `PASS_FOR_PHASE1_FULL_MOCK` | 恰为默认完整一期 N01-N18，保留 Gate/WT/N12/N16/N17/N18；无 reduced profile、旧 P0-P7 或生产声明 |
| `M1-08-OVERALL` | M1 出口 | `PASS_FOR_PH1_MOCK_M2` | M1-01～07 交付齐全、静态门禁通过、已知生产缺口不被 Mock 掩盖 |

## 3. 评审对象与版本锁

| 工作项 | 冻结对象 | 版本/身份 |
|---|---|---|
| [M1-01](PHASE1_MOCK_M1_01_SOURCE_NODE_STEP_TOOL_PRIORITY_MATRIX.md) | 来源、S/T 步骤、工具、优先级与排除 | `T01-PHASE1-18NODE-OFFLINE` |
| [M1-02](PHASE1_MOCK_M1_02_NODE_REGISTRY.md) | 18 节点稳定 ID、key、显示名和责任边界 | `T01-PHASE1-NODE-REGISTRY-v0.1` |
| [M1-03](PHASE1_MOCK_M1_03_CONTROL_FLOW_STATE_GRAPH.md) | 27 条边、九种状态、Gate/WT/重算/条件/汇合 | `T01-PHASE1-CONTROL-FLOW-v0.1` |
| [M1-04](PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md) | 请求、运行、节点、ArtifactRef、错误、审计 | `T01-PHASE1-ENVELOPE-v0.1` |
| [M1-05](PHASE1_MOCK_M1_05_DETERMINISTIC_SCENARIO_MODEL.md) | 21 个场景、18 项 stub 责任、终态/attempt/边 | `T01-PHASE1-MOCK-SCENARIO-CATALOG-v0.1` |
| [M1-06](PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md) | workflow/tool/scenario/run/template/bound 身份与隔离 | `T01-PHASE1-MOCK-ASSET-REGISTRY-v0.1` |
| [M1-07](PHASE1_MOCK_M1_07_ACCEPTANCE_ASSERTIONS_FIXTURE_MANIFEST.md) | fixture、checkpoint、机器断言和覆盖门禁 | manifest/acceptance Catalog `v0.1` |

版本链精确闭合为：

```text
18NODE-OFFLINE
  -> NODE-REGISTRY-v0.1
  -> CONTROL-FLOW-v0.1
  -> ENVELOPE-v0.1
  -> SCENARIO-CATALOG-v0.1
  -> ASSET-REGISTRY-v0.1
  -> FIXTURE-MANIFEST-v0.1
  -> ACCEPTANCE-CATALOG-v0.1
```

任一上游版本、稳定 ID、路径或语义变化都必须触发影响分析；不得只改下游 expected 来“修绿”。

## 4. 跨规格一致性结果

### 4.1 产品范围与来源

| 检查 | 结论 | 证据 |
|---|---|---|
| 节点集合 | `PASS` | M1-01、M1-02、M1-05、M1-06 均为同序 `N01-N18`，无 N19、缺号或重复 |
| 当前 profile | `PASS` | 仅 `PHASE1_FULL`；OI-020 未关闭前没有 reduced profile 或物理跳边 |
| N01 离线决定 | `PASS` | 本地提供结构/AF3/ESMFold2 保留；S-07、RCSB、AlphaFold DB 与联网回退为负向断言 |
| 一期控制结构 | `PASS` | Gate WT 直达、N12 最多三轮、N15 WT 建议、N16 条件、N17 保护、N16/N17→N18 汇合全部保留 |
| 旧范围隔离 | `PASS` | P0-P7、旧 25 场景、旧 provider/生成器不成为一期身份或验收来源 |

### 4.2 节点、状态与边

| 检查 | 结论 | 证据 |
|---|---|---|
| 节点身份/责任 | `PASS` | 18 个 `node_id`、18 个唯一 `node_key` 与 18 项 Mock 输出责任逐项相等 |
| 状态词典 | `PASS` | M1-03 九种状态与 M1-04/M1-05 值域兼容；场景终态只使用其中七种合法终态 |
| 边注册 | `PASS` | M1-03 恰有 `E001-E027`；21 个场景的边并集恰覆盖 27 条，无未知边 |
| Gate/WT | `PASS` | `DESIGN_NOT_SUITABLE` 只走 E012/E013，N11-N17 全为 `SKIPPED_BRANCH` |
| N12 | `PASS` | E015 次数等于轮数，E016 次数等于 recalc 数；最多三轮，最终只走 E017 或 E018 |
| N18 入口 | `PASS` | WT direct 对应 E013，design join 对应 E026；N18 仅 `SUCCEEDED` 时出现 E027 |

### 4.3 envelope 与场景投影

M1-05 与 M1-04 的交叉映射固定如下：

| 场景字段 | envelope 投影 | 护栏 |
|---|---|---|
| `COMPLETE_STUB` | `output_completeness=COMPLETE` + 非空 MockNodeOutputStub | 不是科学完成证明 |
| `PARTIAL_STUB` | `output_completeness=PARTIAL` + 非空 partial MockNodeOutputStub | 只含已登记 stub/artifact 引用 |
| `NONE` | `output_completeness=NONE` + `output=null` | 不得换成空对象或伪成功 |
| `error_codes` | 同码 M1-04 issue | 文本 message 不参与路由 |
| `disposition_reason_code` | 节点 disposition 原因 | skip/not-executed 不能互换 |
| 五类可发射控制 | M1-04 `control_decisions[]` | 控制值仍来自场景字面量 |
| `n18_entry` | E013/E026 与断言视图 trace state | 不是新增的 M1-04 `control_type` 或业务节点 |

四个 M1-04 示例、场景 Catalog、资产注册表、fixture manifest 和 acceptance Catalog 均通过各自
Draft 2020-12 Schema。请求、运行、节点、控制、错误、ArtifactRef 与 audit 的完整科学 `data`
仍保持 opaque/`UNFROZEN`，未被场景 stub 反向定义。

### 4.4 场景、fixture 与断言

| 对象 | 重算值 | 一致性结论 |
|---|---:|---|
| 场景 / fixture case / acceptance case | 21 / 21 / 21 | 同序一一映射，scenario_ref 全部 namespaced |
| 提交 / 唯一请求变体 | 23 / 22 | 21 首提 + 1 重放 + 1 冲突；每次请求 ID 新建 |
| 节点终态指令 | 378 | 每个场景恰有 N01-N18 |
| attempt | 334 | 轮次与恢复历史不覆盖 |
| 非 null / null fixture key | 326 / 8 | 非 null key 唯一闭集；null 不创建文件或 output 引用 |
| async checkpoint plan / step | 4 / 16 | timeout/cancel/recovery 由离散场景动作驱动，不读墙钟或 sleep |
| 全局 / 焦点断言 | 18 / 44 | 共 62 条，ID 唯一、operator 已登记、全部 `BLOCKER` |
| 覆盖门禁 | 10 | 门禁所列 scenario 并集恰为全部 21 个场景 |

### 4.5 资产与目录

| 检查 | 结论 |
|---|---|
| Workflow | 恰为 main/debug 两个登记身份，模板当前未生成 |
| 工具 | 1 initializer + 18 node stub + 6 control literal + 1 finalizer = 26；节点和控制 key 一一对应 |
| provider | 只允许 `t01-phase1-mock-mcp-v01` 及登记绑定 token；实例值和秘密未写入规格 |
| run/request/envelope | 后端签发的一期 UUIDv4 命名；Dify system ID 仅作外部关联 |
| 当前物理资产 | 只有 M1-07 的 4 个规格 JSON；无 input/request/node-result payload、YAML、bound、run 或科学产物 |
| legacy/S07 | 路径、import、provider、campaign 和写入根均隔离；历史回归不计一期功能完成度 |

## 5. 本次发现与处置

| Finding | 级别 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| `M1-08-F01` | blocker | M1-05 Catalog 的 `fixture_manifest_binding` 仍为 M1-07 占位符 | Catalog 与 Schema 同步绑定 `T01-PHASE1-MOCK-FIXTURE-MANIFEST-v0.1` | `RESOLVED` |
| `M1-08-F02` | blocker | 两个 N01 本地路由断言的 structure-case 字面量与 Catalog 精确值不一致 | 改为 `ABSENT_ROUTE_LOCAL_AF3/ESMFOLD2`，并同时断言对应 N01 fact key | `RESOLVED` |
| `M1-08-F03` | blocker | N16 缺失表达宿主断言指向错误请求层级；partial stub 与 envelope 名称未显式桥接 | selector 改为 `request.options.expression_host=null`；补齐三种 output mode 映射 | `RESOLVED` |
| `M1-08-F04` | blocker | acceptance selector 缺 `acceptance` 根，注册表 ID/tool 路径名称不精确，导航把新 DSL 生成源时点误写成 M1/M2；`n18_entry` 可能被误解为新 control type | 修正根、source selector 与导航时点为 M3；明示 `n18_entry` 仅由 E013/E026 映射 | `RESOLVED` |
| `M1-08-F05` | blocker | 初版 manifest 只有终态 fixture 绑定，未落实 M1-05 的异步创建/轮询/取消/恢复检查点 | 新增 4 份 checkpoint plan、16 个固定步骤及禁止墙钟/sleep/隐式动作策略 | `RESOLVED` |

所有修正都发生在 M1 规格层，未改写 21 个场景的控制、节点终态、attempt、边或 expected run，
也未创建实现资产。修正后重新执行完整 Schema 与跨规格审计并通过。

## 6. 未决项分级

### 6.1 不阻塞 M2、但继续阻塞对应生产冻结

| OI | 未冻结内容 | M1/M2 隔离方式 | 最迟时点维持不变 |
|---|---|---|---|
| OI-001/002 | `epitope_policy`、`regions_permissions` 详细契约 | Mock 只保留 opaque 输入/权限追溯 stub，不构造规则 | N06/N11 真实契约前 |
| OI-003 | MHC 面板与宿主映射 | N05 只发 synthetic stub，不推断面板 | N05 真实实现前 |
| OI-004 | 表达宿主支持值、别名与生产参数 | 只冻结 null→skip、非空 unsupported sentinel→N16 failed | N16 真实契约前 |
| OI-006～009 | core map、E0-E4、mutation burden、objective 权重 | payload opaque；无数值、权重、阈值或排名 | 对应真实节点契约前 |
| OI-010 | SC-10 的生产分叉 | `n15_wt_fallback` 只复制场景字面量，不执行 `<0.30` | N15/N18 全链验收前 |
| OI-011 | ΔΔG 符号、单位和阈值 | N14/N17 不输出真实 ΔΔG | N14/N17 真实实现前 |
| OI-013/014 | Agent C 接口和完整 Candidate/Failure 模型 | handoff 恒披露 `NOT_DEPLOYED`，不伪造 delivered | N18 生产契约前 |
| OI-015 | R-58 详细条款 | N02/N10/N12 只发 stub，不推断科学校验 | 对应真实实现前 |
| OI-021 | Gate 完整科学判据 | Mock Gate 只读 `SCENARIO_LITERAL` | N10 Gate 生产契约前 |
| OI-022 | N13/N15 缺值、并列、top20 | Mock 不计算过滤、Pareto 或排序 | N13/N15 生产契约前 |

### 6.2 未启用能力

OI-020 仍阻止任何 reduced profile。M1/M2 唯一允许的是 `PHASE1_FULL`；即使 N16 单次运行因条件
跳过，也不等于从产品范围删除 N16。任何 reduced profile 都需新决定、状态/边影响分析、场景和
验收扩展，不能在 M2 中以配置开关暗加。

### 6.3 M1 缺口结论

没有无编号、无责任人或需要由实现方猜测的 M1 缺口。上述 OI 不允许 M2 自行选择科学值；如果
实现需要它们才能推进，正确行为是保持 stub/opaque 或 fail closed，而不是补默认值。

## 7. 验证证据

本次一致性审查执行并通过以下静态门禁：

1. 4 份 M1-04 示例及场景 Catalog、资产注册表、fixture manifest、acceptance Catalog 分别通过
   Draft 2020-12 Schema，并严格检查重复 JSON key；
2. Markdown 表中 18 节点、27 条边、九种状态与机器资产逐项比对；
3. 场景的 Gate、N12、N18 边/终态关系逐场景重算；
4. 2/26/21、21/23/22、378/334/326/8、4/16、18/44/10 等数量从源数据重算；
5. 断言 source text 与 M1-05 的 44 条原始场景断言逐条同序相等；
6. 当前一期目录确认无 YAML、fixture payload、bound、run 或生产资产。

仓库级文档检查、当前控制面测试、旧完整 Mock 74 项和 S07 41 项回归的最终结果记录在
[当前状态](../STATUS.md)，并作为本工作项退出证据。历史 115 项测试仍不计为一期功能测试。

## 8. M2 放行包与停止线

M2 的读取顺序固定为：

1. M1-02 节点注册表与 M1-03 状态/边；
2. [M1-04 Schema](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_ENVELOPE_SCHEMA_v0.1.json)；
3. [M1-05 场景 Catalog](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_SCENARIO_CATALOG_v0.1.json)；
4. [M1-06 资产注册表](../../../工作流设计/03-Dify实现/T01_PHASE1_MOCK_ASSET_REGISTRY_v0.1.json)；
5. [M1-07 fixture manifest](../../../dify/t01-phase1-mock-v0.1/fixtures/T01_PHASE1_MOCK_FIXTURE_MANIFEST_v0.1.json)；
6. [M1-07 acceptance Catalog](../../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_ACCEPTANCE_CATALOG_v0.1.json)；
7. 本评审的映射、finding 和未决项隔离结论。

M2 可创建登记在 M1-06 中的 `src/t01_phase1_mock/`、`tests/t01_phase1_mock/` 与必要 fixture payload，
但不得创建/绑定 Dify DSL（M3）、声称全场景运行冻结（M4）或越过真实工具门禁。M1 基线后续若有
语义修改，必须重新打开影响项并升级相关版本；不能静默编辑 v0.1。
