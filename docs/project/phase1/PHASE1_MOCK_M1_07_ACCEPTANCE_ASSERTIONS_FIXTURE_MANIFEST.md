# PH1-MOCK-M1-07 验收场景、机器断言与 fixture manifest

> 状态：`COMPLETED / FROZEN_SPEC_ONLY`  
> 冻结日期：2026-09-04  
> 适用范围：严格一期 `N01-N18`、默认完整 profile、Mock v0.1  
> 实现状态：未创建 Mock 代码、fixture payload、Dify DSL、bound 或真实科学结果

## 1. 冻结结论

M1-07 没有新增或改写 M1-05 场景，而是把既有 21 个确定性场景冻结成三层可实施验收合同：

1. **场景 Catalog**继续是控制、节点、attempt、边和运行终态的唯一语义真值；
2. **fixture manifest**冻结输入 fixture、请求变体、提交关系、attempt fixture key 解析和计划路径；
3. **acceptance Catalog**冻结全局断言、逐场景焦点断言、覆盖门禁和后续执行矩阵。

三层以 `scenario_key`、namespaced `scenario_ref`、`fixture_case_id` 和 `acceptance_case_id` 一一闭合。
当前共冻结 **21 个验收案例、23 次提交、22 个请求变体、4 份异步 checkpoint plan（16 个固定
检查点）、18 条全局断言、44 条逐案例焦点断言和 10 个覆盖门禁**。所有断言均为 `BLOCKER`；
不存在 warning-only 绕过路径。

## 2. 权威输入与派生边界

| 层 | 冻结输入 | M1-07 如何使用 |
|---|---|---|
| 拓扑与状态 | [M1-03 控制流](PHASE1_MOCK_M1_03_CONTROL_FLOW_STATE_GRAPH.md) | 只校验 `N01-N18`、`E001-E027`、Gate、重算、条件和汇合是否可被场景观测 |
| 通用数据形状 | [M1-04 envelope](PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md) | 将请求与运行结果的 Schema 校验列为全局阻断断言，不扩展科学 payload |
| 场景语义 | [M1-05 场景模型](PHASE1_MOCK_M1_05_DETERMINISTIC_SCENARIO_MODEL.md) | 21 个场景及其字面量控制、节点、attempt、边和终态是唯一 expected source |
| 资产身份 | [M1-06 隔离规范](PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md) | 复用已冻结的 workflow/tool/scenario/run/template/bound 身份和目录，不另造命名空间 |

本任务没有把专家原件中的科学规则转写成测试数值。Gate、N12、N15、N16、N17 和 N18 入口仍只
允许复制 `SCENARIO_LITERAL`；fixture 只描述 synthetic transport/state stub，不运行或模拟科学算法。

## 3. 机器规格资产

| 资产 | 版本/状态 | 责任 |
|---|---|---|
| [fixture manifest](../../../dify/t01-phase1-mock-v0.1/fixtures/T01_PHASE1_MOCK_FIXTURE_MANIFEST_v0.1.json) | `T01-PHASE1-MOCK-FIXTURE-MANIFEST-v0.1` / `SPEC_ONLY_PAYLOADS_NOT_MATERIALIZED` | 物理 fixture 身份、提交绑定、闭集解析和计划路径 |
| [fixture manifest Schema](../../../dify/t01-phase1-mock-v0.1/fixtures/T01_PHASE1_MOCK_FIXTURE_MANIFEST_SCHEMA_v0.1.json) | Draft 2020-12 | 严格约束 manifest 结构、数量、状态与命名 |
| [acceptance Catalog](../../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_ACCEPTANCE_CATALOG_v0.1.json) | `T01-PHASE1-MOCK-ACCEPTANCE-CATALOG-v0.1` / `FROZEN_SPEC_ONLY` | 可机器消费的断言、案例、覆盖门禁和执行矩阵 |
| [acceptance Catalog Schema](../../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_ACCEPTANCE_CATALOG_SCHEMA_v0.1.json) | Draft 2020-12 | 严格约束断言运算符、selector、案例与门禁 |

这些 JSON 是规格，不是测试代码，也不是运行 fixture payload。M2 才可按 manifest 物化 payload，
M3 才可生成/绑定 Dify DSL，M4 才可把运行证据写入 `regression/runs/`。

## 4. fixture manifest 冻结项

### 4.1 闭集清单

| 对象 | 数量 | 冻结规则 |
|---|---:|---|
| input fixture | 2 | `input.synthetic.standard` 与 `input.synthetic.no_structure`；仅声明 synthetic 特征，payload 未物化 |
| request variant | 22 | 21 个 base；幂等冲突案例另有 1 个 changed 变体 |
| fixture case | 21 | 与 M1-05 场景同序一一对应 |
| submission | 23 | 21 次首提 + 幂等重放第二次 + 幂等冲突第二次 |
| node terminal directive | 378 | 21 × 18，全部来自 M1-05 `node_plan` |
| attempt | 334 | 保留初始、重算和恢复 attempt，不压缩历史 |
| 非 null attempt fixture key | 326 | 只能解析 Catalog 已声明的 key |
| null attempt fixture key | 8 | 明确表示不创建 fixture 文件、也不产生 output 引用 |
| async checkpoint plan | 4 | N16 partial timeout、整次取消、N08 恢复、N08 超时 |
| checkpoint step | 16 | 每份计划恰 4 步；无墙钟或 sleep 驱动 |

`fixture_result_key` 即使匹配正则，只要没有出现在 M1-05 Catalog 的非 null 集合中，也必须拒绝；
不存在按模式猜测、默认 fixture 或最相近 key 回退。逻辑 key 解析到：

```text
dify/t01-phase1-mock-v0.1/fixtures/node-results/{scenario_key}/n{node_number}/attempt-{attempt_number}.json
```

解析后还必须验证路径位于当前一期 fixture 根内，且不得通过 symlink、junction 或 `..` 跨入
`legacy/`、S07 或其他工作区。

### 4.2 请求与幂等

- 每次提交产生新的 namespaced `request_id`；该规则与幂等 key 是否复用相互独立。
- `idempotent_replay` 的第二次提交使用同一 key、同一规范化请求，动作固定为
  `RETURN_EXISTING_RUN`，并复用第一次的 `run_id`。
- `idempotency_conflict` 的 changed 变体只在规范化请求 `/options/design_objective` 上执行
  `REPLACE "solubility"`；第二次提交固定为 `REJECT_REQUEST`、错误码
  `REQUEST_IDEMPOTENCY_CONFLICT`，不得创建新 `run_id` 或改写原运行。
- 上述值只用于传输层幂等差异，不是科学目标推荐或计算结果。

### 4.3 异步检查点

只有四个需要观察中间动作的场景登记 checkpoint plan，其余场景使用确定性终态投影：

| 场景 | 固定动作序列 | 终态 |
|---|---|---|
| `n16_branch_timeout_partial` | create → poll N16 active → 注入 N16 timeout → poll terminal | `COMPLETED_WITH_GAPS` |
| `run_cancelled_before_join` | create → poll N16 active → 显式 cancel → poll terminal | `CANCELLED` |
| `n08_retryable_recovery` | create → poll attempt 1 retryable failure → 显式 recovery → poll terminal | `COMPLETED` |
| `n08_upstream_timed_out` | create → poll N08 active → 注入 N08 timeout → poll terminal | `TIMED_OUT` |

这些是场景驱动的离散检查点，不是毫秒计划。禁止读墙钟、sleep 后自动推进、隐式取消或隐式恢复；
每个 checkpoint 只暴露已登记事实，终态仍精确投影 M1-05 Catalog。

### 4.4 未物化边界

manifest 中所有 input、request 和 attempt payload 均为 `DECLARED_NOT_MATERIALIZED`。当前没有：

- synthetic 序列、结构、宿主或候选内容；
- DNA、密码子、结构评分、稳定性、免疫原性、排序或阈值结果；
- 远程数据库返回、URL、外部结构 ID 或生产 Agent C 交付；
- API key、token、实例凭据或本机绝对绑定值。

## 5. 机器断言合同

### 5.1 selector 语义

acceptance Catalog 使用 `T01-PHASE1-ASSERTION-PATH-v0.1`。未来 harness 必须把实现映射成下列
规范化语义视图，再执行断言：

```text
catalog | fixture | acceptance | request | submission[n] | run | trace | workflow | original_run
```

节点使用 `run.node[N01..N18]`，控制对象使用六个 M1-05 control key，提交使用
`submission[1..n]`。其中 `n18_entry` 只在断言视图中由场景与 E013/E026 推导，不新增为 M1-04
`control_decision`。selector 只是测试适配层的读取约定，不授权在 M1-04 envelope 中新增字段；
运行实现若无法构造某 selector，结果是 `BLOCKER FAIL`，不能跳过。

### 5.2 断言分类

18 条全局断言分为五组：

| 组 | 机器检查 |
|---|---|
| 结构闭合 | 四类上游 JSON/Schema、21/23/22/378/334/326/8/44 数量、三目录一一映射 |
| 语义投影 | submission、六类 control、18 节点、attempt、边和 expected run 精确等于选中场景 |
| 数据与引用 | `MOCK_DATA`、`scientific_compute=false`、`NOT_DEPLOYED`、Artifact/error/attempt/audit 引用闭合 |
| 身份与编排 | ID 正则、2 个 Workflow、26 个工具、provider、main/debug 规范化结果一致 |
| 隔离与冻结 | 禁止旧身份/路径、禁止科学值与远程回退；M4 必须 21 案例/23 提交且 0 blocker failure |

运算符共 28 个，均在 Catalog 的 `operator_contract` 中闭集登记。未知 operator、缺失 selector、
缺失 fixture、Catalog 投影不一致均 fail closed。

### 5.3 逐案例焦点断言

M1-05 的 44 条自然语言断言已逐条保留在 `source_text`，并转换为 operator、actual selector 和
expected literal/source selector。案例与核心阻断点如下：

| # | scenario_key | 焦点阻断点 |
|---:|---|---|
| 1 | `happy_provided_structure` | N01 本地结构 stub；N16/N17 在 E026 前 settled |
| 2 | `happy_no_structure_local_af3` | 无 S-07/RCSB/AFDB；路由只来自场景字面量 |
| 3 | `happy_no_structure_local_esmfold2` | 无远程 fallback；不得按运行质量比较选路 |
| 4 | `gate_wt_direct` | N11-N17 全为 `SKIPPED_BRANCH`；Gate 不由 N10 stub 推断 |
| 5 | `n12_pass_cycle_2` | 决策序列 recalc→pass；N11 budget 为 24、48 |
| 6 | `n12_pass_cycle_3` | 决策序列 recalc→recalc→pass；budget 为 24、48、64 |
| 7 | `n12_recalc_exhausted` | N11/N12 恰三轮、无第四轮；不伪造科学拒绝原因 |
| 8 | `n15_wt_fallback` | E021-E026 均保留；N16 为 `NOT_EXECUTED` 而非 branch skip |
| 9 | `n16_missing_expression_host` | 不从 `host_species` 推断；N16 无成功输出 |
| 10 | `n17_not_applicable` | 不执行膜/置信度计算；N17 与 E023/E025 仍可观察 |
| 11 | `n16_unsupported_expression_host` | 仅 synthetic sentinel；N18 保留 N16 错误 |
| 12 | `n17_branch_failed` | N17 失败不改写；E025/E026 可观察 |
| 13 | `n16_branch_timeout_partial` | partial stub 无 DNA/科学值；timeout 与 partial 引用保留 |
| 14 | `n08_upstream_tool_failed` | 无 E009；上游终止后不得生成控制决定 |
| 15 | `n01_local_prediction_failed_no_remote_fallback` | 无 E002；无外部结构 ID/URL |
| 16 | `run_cancelled_before_join` | 取消不进入 tolerant join；无 E026/E027 |
| 17 | `n08_retryable_recovery` | attempt 1 失败仍保留；attempt 2 指回 1；记录只追加不覆盖 |
| 18 | `idempotent_replay` | 第二次返回既有运行；控制字面量只发射一次 |
| 19 | `idempotency_conflict` | 第二次在新运行前拒绝；原运行及控制哈希不变 |
| 20 | `n18_assembly_failed` | 有 E026、无 E027；上游 stub 不提升为完成结果 |
| 21 | `n08_upstream_timed_out` | 无 E009；超时由场景注入而非墙钟；后续控制均未到达 |

## 6. 覆盖门禁

以下 10 个门禁全部由具名 scenario key 构成，不能以标签、抽样或“等价案例”替代：

1. 正常路径与三种 N01 本地入口；
2. Gate 不适合设计与 WT 直达；
3. N12 两轮通过、三轮通过和三轮耗尽；
4. N15 WT fallback；
5. N16/N17 条件跳过、失败、超时 partial 与 tolerant join；
6. N01/N08 上游失败和 N08 超时；
7. 全运行取消与 retryable recovery；
8. 幂等重放与幂等冲突；
9. N18 汇合后装配失败；
10. 节点 01 离线排除与新旧资产隔离。

“规格覆盖通过”只说明每个门禁已有案例和断言，不说明代码行为已通过。

## 7. 执行状态与放行规则

| 阶段 | 要求 | M1-07 当前状态 |
|---|---|---|
| `M1_07_SPEC_STATIC` | Schema、数量、集合、引用与覆盖闭合 | `VERIFIED_AT_M1_07` |
| `M2_BACKEND` | 21 案例 / 23 提交运行后端断言 | `DECLARED_NOT_RUN` |
| `M3_DIFY_MAIN` | 21 / 23 运行 main Workflow | `DECLARED_NOT_RUN` |
| `M3_DIFY_DEBUG` | 21 / 23 运行 debug Workflow | `DECLARED_NOT_RUN` |
| `M3_MAIN_DEBUG_PARITY` | 21 个规范化结果逐项一致 | `DECLARED_NOT_RUN` |
| `M4_REGRESSION_FREEZE` | 21 / 23 全执行、0 blocker，并通过隔离回归 | `DECLARED_NOT_RUN` |

未来报告不得把 `DECLARED_NOT_RUN`、fixture 未物化、工具未部署或 Workflow 未生成写成 `PASS`。
M4 只有在全部案例与提交执行、main/debug parity 通过、当前测试/旧 74 项/S07 41 项分别通过且
blocker 为零时，才可冻结 Mock v0.1。

## 8. M2/M3 实施约束

M2 必须按以下顺序消费规格：

1. 严格校验 scenario Catalog、fixture manifest、acceptance Catalog 及各自 Schema；
2. 用 manifest 物化 synthetic 输入/请求/节点结果 payload，保持 key、路径与哈希可追溯；
3. 按 scenario 的 submission plan 和 exact projection 生成状态，不从 fixture 内容计算控制结果；
4. 暴露 selector contract 所需的只读规范化视图；
5. 执行适用于 M2 的全局和焦点断言，任何缺失或未知对象立即失败；
6. 不执行科学程序、不访问公网、不调用旧 Mock/S07、不声称 Agent C 已部署。

M3 只能在 M2 已通过后，让两个登记 Workflow 编排同一后端真值；Dify 不得重算 Gate、Hard Filter、
Pareto、重算决策、条件或 join 结论。

## 9. M1-07 验收记录

| 检查 | 结果 | 证据 |
|---|---|---|
| JSON 与 Schema | `PASS` | 两个 M1-07 Schema 自校验，manifest 与 acceptance Catalog 严格验证且无重复 key |
| 场景/案例闭合 | `PASS` | 21 个 scenario、fixture case、acceptance case 同序一一对应 |
| 提交/请求闭合 | `PASS` | 23 次提交、22 个唯一 request variant；重放与冲突关系显式 |
| 节点 fixture 闭合 | `PASS` | 378 个终态、334 个 attempts、326 个非 null key、8 个 null key 重算一致 |
| 异步检查点 | `PASS` | 4 份 plan / 16 个离散步骤；timeout、cancel、recovery 均由场景动作驱动，不读墙钟 |
| 断言闭合 | `PASS` | 18 条全局断言、44 条焦点断言；ID 唯一、operator 已登记、引用可解析 |
| 覆盖门禁 | `PASS` | 正常、分支、重算、条件、失败、超时、取消、恢复、幂等、排除/隔离均有具名案例 |
| 科学与实现停止线 | `PASS` | 科学执行为 0；未创建 payload、Mock 源码、Dify YAML 或 bound |

下一项为 `PH1-MOCK-M1-08`：对 M1-01～07 做工程、算法边界与产品范围的一致性评审，记录具名
结论、版本、日期、缺口和放行决定；该评审通过前不进入 M2。
