# PH1-MOCK-M1-05 确定性场景模型与节点 Mock 输出责任 v0.1

> 状态：`COMPLETED / DETERMINISTIC_SCENARIO_MODEL_v0.1_FROZEN`  
> 日期：2026-09-04  
> 场景模型：`T01-PHASE1-MOCK-SCENARIO-MODEL-v0.1`  
> 场景目录：[机器可读 catalog](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_SCENARIO_CATALOG_v0.1.json)  
> 结构约束：[Draft 2020-12 Schema](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_SCENARIO_CATALOG_SCHEMA_v0.1.json)  
> 交付边界：冻结场景字面量、终态投影和每节点 Mock 输出责任；不运行科学工具、不计算科学值、
> 不编写 Mock 代码或 Dify DSL，不提前建立 M1-07 fixture manifest。

## 1. 冻结结论

1. Mock 运行只能由调用方给出的 `scenario_ref` 精确选择一个场景；M1-06 已将其按
   ``t01_phase1_mock_v01.scenario.{scenario_key}`` 一一绑定。未知、缺失或歧义场景必须拒绝，
   不能回退到 happy path。
2. Gate、N12、N15、N16、N17 和 N18 入口结果全部来自 `SCENARIO_LITERAL`。即便输入或上游
   占位事实看似足以判断，Mock 引擎也不得据此重新计算、推断或改写控制结果。
3. 每个场景显式给出 N01-N18 共 18 个节点的终态、attempt、输出模式、错误/处置原因，及实际
   `E001-E027` 序列。21 个冻结场景合计 378 个节点终态指令。
4. 节点成功输出只能是 `STUB_FACTS_ONLY`：携带 Mock 标识、场景/节点/事实集引用和语义类别，
   不携带可被误认成真实结果的序列、结构、肽段、突变、DNA、分数、阈值判定或排名。
5. 所有场景固定 `MOCK_DATA`、`scientific_compute=false`、`PHASE1_FULL`、`NOT_DEPLOYED`；禁止
   随机数、系统时钟、环境探测、LLM 文本或 Dify 表达式参与分支决定。
6. 场景目录只冻结语义和最终投影。物理命名/目录已由
   [M1-06](PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md)冻结；具体 fixture
   文件、轮询检查点和机器断言由 M1-07 冻结；当前仍没有可运行 Mock 或 Dify DSL。

## 2. 直接上游与权威边界

| 上游 | 本任务消费内容 | 不在本任务扩写 |
|---|---|---|
| [M1-01 来源矩阵](PHASE1_MOCK_M1_01_SOURCE_NODE_STEP_TOOL_PRIORITY_MATRIX.md) | 18 节点工具边界、离线/排除项、优先级 | 真实工具返回值或模拟算法 |
| [M1-02 节点注册表](PHASE1_MOCK_M1_02_NODE_REGISTRY.md) | 稳定 ID、node_key、语义生产/消费责任 | 完整科学字段 Schema |
| [M1-03 控制流](PHASE1_MOCK_M1_03_CONTROL_FLOW_STATE_GRAPH.md) | E001-E027、状态、Gate、三轮重算、条件与汇合 | 新控制值、新边或生产判据 |
| [M1-04 envelope](PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md) | request/run/node/attempt/error/audit/ArtifactRef 外壳 | CandidateRecord 等完整科学 payload |
| [AgentA SOP](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md) | 已保留节点职责、三轮参数和条件语义 | 已裁剪能力、未冻结阈值或生产算法 |

场景中的 `*_STUB`、`fixture_*` 和 `mock://` 引用是工程哨兵，不是专家原件中的科学结论。
旧 P0-P7 的 25 个场景保持冻结，但不作为本目录的名称、内容或覆盖来源。

## 3. 机器交付物

| 文件 | 作用 | 状态 |
|---|---|---|
| [场景 Catalog v0.1](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_SCENARIO_CATALOG_v0.1.json) | 18 节点输出责任 + 21 个完整场景终态投影 | `FROZEN` |
| [Catalog Schema v0.1](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_SCENARIO_CATALOG_SCHEMA_v0.1.json) | 字段、枚举、条件与 Mock 输出 stub 约束 | `FROZEN` |
| [M1-04 Envelope Schema](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_ENVELOPE_SCHEMA_v0.1.json) | 后续把场景投影成运行结果的外层契约 | `FROZEN` |

Catalog 版本头固定以下边界：

- `control_source_policy=SCENARIO_LITERAL_ONLY`
- `node_output_policy=STUB_FACTS_ONLY`
- `scenario_ref_binding=t01_phase1_mock_v01.scenario.{scenario_key}`
- `fixture_manifest_binding=DEFERRED_TO_M1_07`
- `implementation_state=SPEC_ONLY`
- `randomness_allowed=false`
- `clock_dependent_branching_allowed=false`

## 4. 场景模型

每个场景由七块不可省略的计划组成：

| 区块 | 冻结内容 |
|---|---|
| `input_profile` | 仅描述 synthetic fixture、结构入口路线、目标和表达宿主用例；禁止联网 |
| `submission_plan` | 创建运行、同请求重放或幂等冲突；不隐式生成第二个运行 |
| `control_plan` | 六个控制槽及其字面量结果/未到达原因 |
| `node_plan` | N01-N18 全量终态、attempt、输出模式、事实集引用、错误和处置 |
| `edge_plan` | 实际经过的 E001-E027 顺序；N12 回边允许重复 |
| `expected_run` | 运行终态、Candidate/WT/Failure、错误和披露；交接恒为 `NOT_DEPLOYED` |
| assertions | 场景特有工程断言；`scientific_assertions` 必须为空数组 |

### 4.1 输入 profile 不是控制器

`structure_case` 只允许本地提供结构、本地 AF3/ESMFold2 占位路线或本地预测失败；不存在远程
查询枚举。`expression_host_case` 使用支持 fixture、缺失或“不支持 sentinel”，不会宣称某个真实
宿主受到支持或不支持。

输入 profile 与控制计划之间只做**一致性校验**：例如 `OMITTED` 应与 N16 `SKIP_CONDITION`
相符，但 Mock 引擎不能从 `OMITTED` 自己生成该决定。若两者矛盾，应在 catalog 装载时以
`INTERNAL_CONTRACT_VIOLATION` 拒绝，而不是自动修复。

### 4.2 提交与幂等

| `expected_action` | 唯一含义 |
|---|---|
| `CREATE_RUN` | 新 key 创建一个运行 |
| `RETURN_EXISTING_RUN` | 相同 key + 相同规范化请求返回既有运行；不重复发出节点或控制结果 |
| `REJECT_REQUEST` | 相同 key + 不同规范化请求返回 `REQUEST_IDEMPOTENCY_CONFLICT` |

Catalog 自身不生成物理 request/run ID；其格式与签发责任已由 M1-06 注册表冻结。重放只改变
交互响应，不改变既有运行的控制字面量、attempt、artifact 或最终结果。

### 4.3 节点指令

终态场景的 `node_plan` 必须按 N01-N18 全量列出。每项包含：

- `status`：`SUCCEEDED`、`SKIPPED_BRANCH`、`SKIPPED_CONDITION`、`FAILED`、`TIMED_OUT`、
  `CANCELLED` 或 `NOT_EXECUTED`；
- `attempts`：真实启动的字面量尝试；N11/N12 的 `design_cycle` 与 24/0.1、48/0.3、64/0.5
  参数显式保留；
- `output_mode`：`COMPLETE_STUB`、`PARTIAL_STUB` 或 `NONE`；
- `fact_set_key`：未来 fixture 的逻辑引用，不是科学 payload；
- `disposition_reason_code`：分支/条件跳过或未执行原因；
- `error_codes`：失败、超时或取消的稳定机器码。

成功节点必须有至少一个成功 attempt 和完整 stub；跳过/未执行不得有 attempt 或输出；失败与
超时必须有 attempt 和错误；恢复必须增加 `RECOVERY` attempt 并指回旧 attempt，不能覆盖历史。

投影到 M1-04 时使用唯一交叉映射：`COMPLETE_STUB → output_completeness=COMPLETE + 非空
MockNodeOutputStub`，`PARTIAL_STUB → PARTIAL + 非空 partial MockNodeOutputStub`，`NONE → NONE +
output=null`。`error_codes` 投影为同码 issue，`disposition_reason_code` 投影为节点 disposition；
不得把场景字段名直接增补为新的 envelope 字段，也不得用空对象替代 `null`。

### 4.4 活跃快照边界

本目录冻结每个场景的最终语义投影及 attempt 历史，不用真实时间制造 `RUNNING`/`TIMED_OUT`。
M1-07 已为异步场景建立固定的创建/轮询/取消/恢复检查点；后续实现必须遵守：

1. 检查点只推进已声明的 node/attempt 指令，不能产生新控制结果；
2. 超时由固定场景步骤注入，不读取墙上时钟；
3. 取消由显式取消动作触发，不依赖竞态；
4. 恢复按 catalog 中的失败 attempt 与 `recovery_of_attempt_number` 展开；
5. 任意中间快照仍须满足 M1-04 的 18 节点 envelope。

## 5. 控制结果全部由场景给出

### 5.1 六个控制槽

| 控制槽 | `EMIT` 时合法结果 | `NOT_REACHED` 时要求 | 禁止的推断来源 |
|---|---|---|---|
| `design_suitability` | `DESIGN_SUITABLE` / `DESIGN_NOT_SUITABLE` | 上游终止原因 | N10 占位分数、LLM 文本、Dify 条件式 |
| `n12_validation` | 1～3 个逐轮结果：validated/recalc/exhausted | Gate WT 或上游终止原因 | 候选数量、伪验证分数 |
| `n15_delivery_recommendation` | candidate / WT fallback | N15 未到达原因 | 伪排名或 SC-10 数值 |
| `n16_applicability` | execute / skip / not executed | 分支未到达原因 | `host_species` 或宿主字符串猜测 |
| `n17_applicability` | execute / skip / not executed | 分支未到达原因 | 膜蛋白/质量占位值的再计算 |
| `n18_entry` | design join / WT direct / not reached | 终止原因 | 将 PENDING/RUNNING 当 settled |

每个槽都必须写 `source=SCENARIO_LITERAL`、机器原因和事实集引用；未到达不是缺字段或 `null`
默认，而是显式状态。N18 入口不是新业务节点，也不增加 M1-04 `control_type`；它投影为 E013 或
E026 是否出现。

### 5.2 N12 序列约束

- 决定的 `design_cycle` 必须严格为 `1..n`，最多 3；
- 除最后一项外只能为 `RECALC_REQUIRED`，且每项对应一次 E016；
- 最后一项只能为 `VALIDATED_CANDIDATES_AVAILABLE` 或 `RECALC_EXHAUSTED`；
- E015 次数等于轮数，E016 次数等于 recalc 次数；通过走 E017，耗尽走 E018；
- 场景只声明结果，不生成候选、不验证结构、不计算淘汰比例。

## 6. MockNodeOutputStub

M1-04 的 `node_output_envelope.data` 在 Mock 中投影为 Schema `$defs.mock_node_output_stub`：

```json
{
  "mock_only": true,
  "scientific_compute": false,
  "scenario_key": "happy_provided_structure",
  "node_id": "N10",
  "mock_output_key": "wt_developability_stub",
  "fact_set_key": "happy_provided_structure.n10.success",
  "emitted_fact_kinds": [
    "WT_BASELINE_REF_STUB",
    "MISSING_DIMENSION_STUB"
  ],
  "entity_refs": [
    "mock://wt/baseline-001"
  ],
  "artifact_ids": [],
  "disclosures": [
    "MOCK_DATA_ONLY",
    "NOT_SCIENTIFIC_EVIDENCE"
  ],
  "scientific_claims": []
}
```

`mock://` 只允许合成实体引用；不得放真实序列、结构坐标、真实样本标识或生产 artifact。外层
`payload_version` 在科学体冻结前继续为 `UNFROZEN`。`emitted_fact_kinds` 必须是该节点责任表的
子集，不能借 stub 向其他节点越权写结果。

## 7. 每节点 Mock 输出责任

下表冻结“成功时可声明哪些类别的占位事实”；不冻结任何科学值。所有节点均固定
`control_outputs_forbidden=true`、`scientific_values_forbidden=true`。

| 节点 | `mock_output_key` | 成功时允许的主要 fact kind | 必须禁止 |
|---|---|---|---|
| N01 | `structure_context_stub` | 结构上下文引用、来源路线、质量/追溯 stub | 坐标、真实质量分数、S-07/RCSB/AFDB 结果 |
| N02 | `structure_basic_analysis_stub` | WT 拓扑、RSA、可用维度 stub | 真实逐残基值、功能域、Gate 结果 |
| N03 | `literature_epitope_stub` | 本地文献命中集、证据和来源 stub | 真实表位、公网 IEDB/BLAST 结果 |
| N04 | `b_cell_epitope_stub` | WT B 细胞区间与来源 stub | 真实区间/概率、DiscoTope、热点图 |
| N05 | `t_cell_epitope_stub` | WT MHC-I/II、panel、降级 stub | 真实肽段/评分、面板推断、排除工具结果 |
| N06 | `epitope_map_stub` | WT B/T/热点三图与证据等级 stub | 真实密度/坐标/E0-E4 判定、设计/排名 |
| N07 | `glycosylation_stub` | WT 位点集、遮蔽风险和表达提示 stub | 真实位点/风险、突变设计、候选复扫 |
| N08 | `conservation_stub` | 同源、MSA、保守性、固定位置与来源 stub | 真实序列/MSA/分数、公网检索、重复对齐 |
| N09 | `functional_domain_stub` | 功能域、core map、来源置信 stub | 真实坐标/core 判定、公网 UniProt、权限决定 |
| N10 | `wt_developability_stub` | WT 维度、基线、缺失维度和风险 stub | 真实分数、候选复评、Gate 结果 |
| N11 | `candidate_design_stub` | 合成候选引用、突变引用、权限追溯、轮次 stub | 类真实候选序列、真实突变/分数、验证/重算 |
| N12 | `design_validation_stub` | 验证、结构引用、负担、违规、可继续候选 stub | 真实验证值/阈值、N12 控制结果、排名 |
| N13 | `candidate_reassessment_stub` | 候选表位保护、可开发性、糖基化复扫及降级 stub | 真实 L1-L4、S-23 结果、覆写 WT 基线 |
| N14 | `candidate_stability_stub` | 候选相对 WT 稳定性与可用性 stub | 真实 ΔΔG/FoldX、N17 扫描、最终选择 |
| N15 | `integrated_ranking_stub` | 剔除/非标准/Pareto/shortlist/建议事实 stub | 真实过滤、权重、分数、名次和控制结果 |
| N16 | `codon_optimization_stub` | DNA 引用、路线与追溯 stub | 真实 DNA/CAI、宿主推断、适用性控制结果 |
| N17 | `wt_stability_reference_stub` | WT 扫描引用、引擎可用性与一致性 stub | 真实 ΔΔG/突变/排序、N14 候选分数、S-32 |
| N18 | `result_assembly_stub` | 组装引用、WT/候选对照、分支状态、方法追溯、交接状态 stub | 补算、完整科学体、虚假 delivered/Agent C 接通 |

完整 fact kind、ArtifactRole、下游责任和披露文本以机器 catalog 的
`node_output_responsibilities` 为准。N10/N12/N15 可以产生供控制器消费的**占位事实引用**，但
不能在节点输出中产生控制枚举；控制枚举仍只从 `control_plan` 复制。

## 8. 冻结场景目录

| # | `scenario_key` | 核心字面量与预期终态 |
|---:|---|---|
| 01 | `happy_provided_structure` | 本地提供结构；Gate suitable；N12 首轮通过；N16/N17 成功；Candidate |
| 02 | `happy_no_structure_local_af3` | 无结构；场景直接指定本地 AF3 stub 路线；完整成功 |
| 03 | `happy_no_structure_local_esmfold2` | 无结构；场景直接指定本地 ESMFold2 stub 路线；完整成功 |
| 04 | `gate_wt_direct` | Gate not suitable；E012/E013；N11-N17 branch skip；WT |
| 05 | `n12_pass_cycle_2` | cycle1 recalc、cycle2 validated；一次 E016；Candidate |
| 06 | `n12_pass_cycle_3` | 两次 recalc、cycle3 validated；两次 E016；Candidate |
| 07 | `n12_recalc_exhausted` | 三轮后 exhausted；E018；N13-N18 not executed；Failure |
| 08 | `n15_wt_fallback` | 设计路径到 N15；WT fallback；N16 无候选未执行；N17 后汇合；WT |
| 09 | `n16_missing_expression_host` | N16 skip condition；N17 成功；Candidate |
| 10 | `n17_not_applicable` | N17 仍保留且 condition skip；N16 成功；Candidate |
| 11 | `n16_unsupported_expression_host` | synthetic unsupported sentinel；N16 failed；N18 完成并披露缺口 |
| 12 | `n17_branch_failed` | N16 成功、N17 failed；宽容汇合；completed with gaps |
| 13 | `n16_branch_timeout_partial` | N16 timed out + partial stub；N17 成功；completed with gaps |
| 14 | `n08_upstream_tool_failed` | N08 failed；无 E009；N09-N18 not executed；Failure |
| 15 | `n01_local_prediction_failed_no_remote_fallback` | 本地预测 stub 失败；只走 E001；禁止公网回退；Failure |
| 16 | `run_cancelled_before_join` | N16 cancelled、N17/N18 not executed；无 E026/E027；Cancelled |
| 17 | `n08_retryable_recovery` | N08 初始 attempt failed，RECOVERY attempt succeeded；保留历史 |
| 18 | `idempotent_replay` | 第二次相同请求返回既有运行，不重复创建/发出控制结果 |
| 19 | `idempotency_conflict` | 相同 key + 不同请求在创建新运行前拒绝 |
| 20 | `n18_assembly_failed` | E026 已进入 N18，但 N18 failed、无 E027；Failure |
| 21 | `n08_upstream_timed_out` | N08 timed out；无 E009；N09-N18 not executed；运行 TIMED_OUT |

这 21 项是 M1-05 的**语义场景目录**，不是物理 fixture manifest。M1-07 已在不改变场景控制
结果的前提下补充 fixture 身份、计划路径、引用闭合和机器断言，见
[M1-07](PHASE1_MOCK_M1_07_ACCEPTANCE_ASSERTIONS_FIXTURE_MANIFEST.md)。

## 9. 全局禁止项

机器 catalog 对所有场景统一禁止：

- S-07、RCSB PDB、AlphaFold DB；
- S-06、S-23、S-32；
- 公网 UniProt REST 与联网 BLAST fallback；
- 任意科学计算；
- LLM 或 Dify 产生控制结果；
- 生产交接或虚假 `DELIVERED`。

此外禁止使用随机 seed、当前时间、系统负载、工具是否安装、网络是否可达或语言模型输出选择
场景结果。需要失败、超时、部分结果、取消或恢复时，必须由相应 scenario directive 注入。

## 10. 装载与投影规则

后续 Mock 实现只能按以下顺序消费本规格：

1. 加载 catalog，并用本任务 Schema 严格校验；
2. 对 18 个输出责任和 scenario_key 做唯一性/顺序检查；
3. 按 M1-06 资产注册表将 namespaced `scenario_ref` 精确解析为一个 `scenario_key`；
4. 校验请求与 `input_profile` 一致，但不从输入计算控制结果；
5. 按 `submission_plan` 创建、重放或拒绝；
6. 原样复制 `control_plan`、`node_plan`、`edge_plan` 与 `expected_run` 的语义；
7. 成功/部分输出按责任表生成 MockNodeOutputStub，只解析 M1-07 manifest 已登记的 synthetic fixture 引用；
8. 投影为 M1-04 envelope，并验证所有引用、状态、边和错误闭合；
9. 任意矛盾以 `INTERNAL_CONTRACT_VIOLATION` 停止，不做默认补齐或“最可能”修复。

在同一 catalog 版本、同一规范化请求和同一场景下，控制结果、节点终态、attempt 序列、事实集键、
错误码、边序列和结果种类必须一致。物理 ID、运行/artifact/bound 根路径已由 M1-06 冻结；
M1-07 已冻结 fixture 身份、计划路径和断言。任何物理差异都不能改变业务语义。

## 11. M1-06 补充绑定与 M1-07 边界

| 后续工作项 | 允许新增 | 禁止改写 |
|---|---|---|
| M1-06（已完成） | 新旧 workflow/tool/scenario/run/template/bound 的命名空间、目录和绑定 | 21 个场景的语义 key、控制/节点/边结果 |
| M1-07（已完成） | synthetic 输入/输出 fixture 身份、manifest、Schema 与跨对象断言 | 科学 payload、控制结果、N01-N18 职责、E001-E027 |
| M2 | 按冻结规格实现确定性状态投影与 Mock 工具外壳 | 运行科学程序、根据 stub 计算结果、恢复旧 Mock 行为 |

如果后续需要新增场景，可以增加新 `scenario_key` 并评审覆盖；改变已有场景的控制或终态语义需要
升级 catalog 版本，不能静默修改 v0.1。

## 12. 验收记录

| 检查 | 结果 | 证据 |
|---|---|---|
| Catalog/Schema | `PASS` | Draft 2020-12 元 Schema 与实例校验通过；无重复 JSON key |
| 节点责任 | `PASS` | N01-N18 恰好 18 项，node_key/output_key 均唯一 |
| 场景完整性 | `PASS` | 21 个唯一 scenario_key；每项含 18 节点，共 378 个终态指令 |
| 控制来源 | `PASS` | 六个控制槽全部显式；source 恒为 `SCENARIO_LITERAL` |
| 控制覆盖 | `PASS` | Gate、N12、N15、N16、N17、N18 入口全部合法结果均有场景覆盖 |
| 异常覆盖 | `PASS` | 上游失败、分支失败、部分结果、超时、取消、恢复、重放、幂等冲突、N18 失败 |
| 离线/排除项 | `PASS` | 无远程路线；全局禁止项包含 S-07/S-06/S-23/S-32 与公网 fallback |
| 科学边界 | `PASS` | 所有 `scientific_assertions=[]`；节点只允许 stub fact kind，禁止科学值 |
| 实现停止线 | `PASS` | M1-07 仅新增规格 manifest/断言；未新增 Mock 代码、真实工具调用、fixture payload 或 Dify DSL |

后续 fixture 与断言绑定见
[PH1-MOCK-M1-07](PHASE1_MOCK_M1_07_ACCEPTANCE_ASSERTIONS_FIXTURE_MANIFEST.md)；M1-05 的场景语义
保持不变，任何改写均须升级 Catalog 版本。
