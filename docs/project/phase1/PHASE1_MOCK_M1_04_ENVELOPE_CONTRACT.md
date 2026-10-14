# PH1-MOCK-M1-04 一期 Mock envelope 契约 v0.1

> 状态：`COMPLETED / PHASE1_MOCK_ENVELOPE_v0.1_FROZEN`  
> 日期：2026-09-04  
> 适用范围：严格一期 `N01-N18`、`PHASE1_FULL`、`MOCK_DATA`  
> 机器契约：[JSON Schema v0.1](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_ENVELOPE_SCHEMA_v0.1.json)  
> 交付边界：只冻结请求、运行结果、节点结果、ArtifactRef、错误与审计外壳；不冻结完整科学
> payload，不实现 Mock 代码，不生成 Dify DSL。

## 1. 冻结结论

1. 一期 Mock 只接受 `PHASE1_RUN_REQUEST`，只返回 `PHASE1_RUN_RESULT`；二者共享版本、追踪、
   数据分类和执行模式头。
2. 每个运行结果始终携带恰好 18 个 `node_results`，按 `N01`～`N18` 排列。未运行、分支跳过和
   条件跳过也必须有显式记录，不能删除节点或用空数组隐去。
3. 节点输出由通用 `node_output_envelope` 包裹；其 `data` 在本任务中保持不透明。完整
   CandidateRecord、AgentCHandoff、FailureReport 和各节点科学字段仍受 OI-013/OI-014 等开放项
   约束，不在 M1-04 中臆造。
4. 二进制、大对象和需要跨节点引用的结果只通过不可变 `ArtifactRef` 暴露；不得把服务器路径、
   外部 URL、凭据或内联二进制交给 Dify/LLM。
5. Gate、N12 重算、N16/N17 条件和 N18 汇合的证据分别进入 `control_decisions`、
   `edge_traversals`、节点状态/处置原因和审计事件，不依赖自由文本反推。
6. 所有示例均为 `MOCK_DATA` 且 `scientific_compute=false`。示例中的结果、hash、运行 ID 和
   ArtifactRef 只证明契约可解析，不代表科学结论、真实文件或生产交接。

## 2. 依据与权威边界

| 依据 | 本任务采用内容 | 本任务不扩写内容 |
|---|---|---|
| [M1-01 来源矩阵](PHASE1_MOCK_M1_01_SOURCE_NODE_STEP_TOOL_PRIORITY_MATRIX.md) | 一期范围、输入基线、工具和排除项 | 工具真实返回 Schema |
| [M1-02 节点注册表](PHASE1_MOCK_M1_02_NODE_REGISTRY.md) | `N01-N18` 身份、显示名和输入输出责任 | 节点完整字段定义 |
| [M1-03 控制流](PHASE1_MOCK_M1_03_CONTROL_FLOW_STATE_GRAPH.md) | `E001-E027`、九种节点状态、Gate、三轮重算、条件与汇合 | 新边、新节点或额外科学判据 |
| [一期 18 节点图](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期%2018%20节点%20+%20落地优先级）.md) | 最新一期拓扑、主路径和优先级 | 旧 P0-P7 阶段映射 |
| [AgentA SOP](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md) | 输入语义、N12 轮次、N16/N17 条件 | 未出现的阈值、别名或生产接口 |
| [AgentA Schema](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md) | CandidateRecord、AgentCHandoff、FailureReport、MethodSummary 的类型来源 | 把草案片段宣称为已完成生产 Schema |

用户最新决定和上述当前专家原件优先；冻结旧 Mock 只作隔离参考，不能反向决定本契约。

## 3. 契约文件与版本标识

机器可读文件使用 JSON Schema Draft 2020-12：

- Schema：[`T01_PHASE1_MOCK_ENVELOPE_SCHEMA_v0.1.json`](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_ENVELOPE_SCHEMA_v0.1.json)
- `$id`：`urn:t01:phase1:mock:envelope:v0.1`
- `contract_version`：`T01-PHASE1-ENVELOPE-v0.1`
- `topology_version`：`T01-PHASE1-18NODE-OFFLINE`
- `node_registry_version`：`T01-PHASE1-NODE-REGISTRY-v0.1`
- `control_flow_version`：`T01-PHASE1-CONTROL-FLOW-v0.1`

Schema review draft 已满足 M1-04 的可解析要求；M1-08 仍需做工程、算法和产品一致性评审。
任何破坏已有字段、枚举或条件的修改必须升级契约版本，不能静默改写 `v0.1`。

### 3.1 公共头

| 字段 | 类型/固定值 | 责任 |
|---|---|---|
| `envelope_type` | 请求 `PHASE1_RUN_REQUEST`；结果 `PHASE1_RUN_RESULT` | 区分联合 Schema 分支 |
| `contract_version` | 固定版本 | 定位本 envelope 契约 |
| `topology_version` | 固定版本 | 防止混入旧 P0-P7 或非离线拓扑 |
| `node_registry_version` | 固定版本 | 定位 N01-N18 身份与责任 |
| `control_flow_version` | 固定版本 | 定位 E001-E027 和状态语义 |
| `envelope_id` | `t01-phase1-mock-v01-env-{uuid4}` | envelope 实例身份；物理格式由 [M1-06](PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md) 补充冻结 |
| `created_at` | RFC 3339 `date-time` | envelope 生成时间 |
| `execution_mode` | 固定 `MOCK` | 禁止冒充真实执行 |
| `execution_profile` | 固定 `PHASE1_FULL` | 当前未批准 reduced profile |
| `data_classification` | 固定 `MOCK_DATA` | 数据分类硬标识 |
| `scientific_compute` | 固定 `false` | 明示没有科学计算 |

## 4. 请求 envelope

### 4.1 顶层字段

| 字段 | 必填 | 约束与含义 |
|---|---:|---|
| `request_id` | 是 | 单次请求身份；格式为 `t01-phase1-mock-v01-req-{uuid4}`，Dify 不改写 |
| `idempotency_key` | 是 | 重复提交身份；不得由 Dify 临时改写 |
| `scenario_ref` | 是 | 指向 M1-05 场景；格式为 `t01_phase1_mock_v01.scenario.{scenario_key}` |
| `inputs` | 是 | 规范化目标输入，见下表 |
| `options` | 是 | 显式设计选项；不得从其他字段推断 |
| `input_fingerprints` | 是 | 序列与可选结构的 SHA-256 |
| `audit` | 是 | 请求接收和追踪证据 |

### 4.2 `inputs`

| 字段 | 必填 | 约束 |
|---|---:|---|
| `protein_sequence` | 是 | 去空白并转大写后仅允许 `A-Z`；至少一个字符 |
| `host_species` | 是 | 非空字符串；不把它当作表达宿主 |
| `structure` | 是 | 可为 `null`；非空时只能是本地已接收 ArtifactRef + 格式 + 链选择 |

`A-Z` 是传输层规范化语法，不是对非常规残基、生物学有效性或下游工具兼容性的科学判定。
相关生产字母表没有统一原件时，本任务不猜测。序列 hash 按“规范化序列的 UTF-8 字节、无换行”
计算。

`structure` 非空时：

- `artifact.artifact_role` 固定为 `INPUT_STRUCTURE`；
- `structure_format` 只能为 `PDB`、`CIF` 或 `MMCIF`；
- `chain_selector` 为 `AUTO` 或显式非空链标识；
- `preserve_original_format=true`，结构 SHA-256 按原始文件字节计算；
- `artifact.format` 与 `structure_format` 必须语义一致；JSON Schema 校验后由契约语义检查断言；
- 不接受 PDB ID、UniProt accession、HTTP(S) URL、服务器路径或自由文本作为远程补齐请求；
  N01 也不得触发 RCSB PDB、AlphaFold DB 或其他联网回退。

### 4.3 `options`

| 字段 | 值 | 路由责任 |
|---|---|---|
| `design_objective` | `general`、`solubility`、`thermostability` | 只保留明确目标；不在此定义 OI-009 权重或科学规则 |
| `expression_host` | `null` 或非空字符串 | `null` 令设计路径上的 N16 为 `SKIPPED_CONDITION`；禁止用 `host_species` 推断 |

表达宿主的边界在本任务固定如下：空字符串属于入口 Schema 错误；`null` 是“未提供”；任意明确
非空值可进入运行契约，若后端支持目录不能识别，则 N16 以 `EXPRESSION_HOST_UNSUPPORTED` 失败，
而不是把该值静默改成 `null`。支持值、别名和生产参数仍留在 OI-004，M1-04 不猜测列表。

### 4.4 指纹与幂等

- `protein_sequence_sha256` 必须与规范化序列一致。
- 无结构时 `structure_sha256=null`；有结构时必须等于结构 ArtifactRef 的 `sha256`。
- 相同 `idempotency_key`、相同规范化输入、相同 options 和相同 `scenario_ref` 表示同一逻辑请求；
  后端应返回既有运行或其当前/最终快照。
- 相同 key 携带不同输入指纹、options 或场景时拒绝为 `REQUEST_IDEMPOTENCY_CONFLICT`，不得覆盖原运行。
- `request_id`、`run_id`、`envelope_id`、场景和文件命名已由
  [M1-06](PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md) 补充冻结；
  UUID 熵只用于身份，不能影响场景或控制结果。

## 5. ArtifactRef

ArtifactRef 是“可审计内容引用”，不是文件路径。字段全部必填：

| 字段 | 约束 | 说明 |
|---|---|---|
| `artifact_id` | 非空不透明字符串 | 内容实例身份 |
| `artifact_role` | 固定枚举 | `INPUT_STRUCTURE`、节点输入/输出、部分/最终结果、日志、方法摘要、失败报告或审计 |
| `uri` | `artifact://...` | 只能使用受控逻辑 URI；不得出现磁盘路径或 HTTP(S) URL |
| `media_type` | 非空 | MIME 类型 |
| `format` | 非空 | 保留原始/交付格式标识 |
| `size_bytes` | 非负整数 | 原始字节长度 |
| `sha256` | 64 位小写十六进制 | 内容完整性指纹 |
| `integrity_status` | 固定 `VERIFIED` | 未完成 hash 校验的对象不能发布为 ArtifactRef |
| `created_at` | RFC 3339 | 内容登记时间 |
| `producer` | ActorRef | 产生或接收该内容的组件 |
| `source_node_id` | N01-N18 或 `null` | 输入附件为 `null`，节点产物指向生产者 |
| `source_attempt_id` | 非空字符串或 `null` | 节点产物必须指向对应 attempt |
| `metadata` | 对象 | 仅存不改变核心语义的补充事实 |

`artifact_id + sha256` 一经发布不可变；内容变化必须创建新 ArtifactRef。节点输出和最终结果可以
重复引用同一 ArtifactRef，但同一 ID 的核心字段必须完全一致。逻辑 URI 的解析、存储路径和
生命周期由后端掌握，Dify/LLM 不可自行拼接或读取服务器路径。

## 6. 节点结果 envelope

每个 `node_results[]` 是一个注册节点的状态快照：

| 字段 | 责任 |
|---|---|
| `node_id` | 唯一使用 `N01-N18` |
| `status` | 使用 M1-03 的九种规范状态 |
| `started_at` / `finished_at` | 节点生命周期；未启动时 `started_at=null` |
| `output_completeness` | `NONE`、`PARTIAL`、`COMPLETE` |
| `output` | 成功时为 node output；无输出时为 `null` |
| `attempts` | 按执行次序保留全部尝试，不覆盖历史轮次 |
| `disposition` | 分支/条件跳过、上游阻断等非执行原因 |
| `issues` | 节点级结构化错误/警告 |
| `upstream_node_ids` | 真实业务上游；控制点不是节点 ID |
| `control_decision_ids` | 与该节点结算直接相关的控制决定 |

### 6.1 状态—字段不变量

| 状态 | 时间 | 输出 | attempt | disposition / issue |
|---|---|---|---|---|
| `PENDING` | 均为 `null` | `NONE` / `null` | 空 | disposition 为 `null` |
| `RUNNING` | 已开始、未结束 | `NONE` 或 `PARTIAL` | 至少 1 个 | disposition 为 `null` |
| `SUCCEEDED` | 均非空 | `COMPLETE` / 非空 | 至少 1 个 | disposition 为 `null` |
| `SKIPPED_BRANCH` | 未开始、已有结算时间 | `NONE` / `null` | 空 | `BRANCH_NOT_SELECTED` |
| `SKIPPED_CONDITION` | 未开始、已有结算时间 | `NONE` / `null` | 空 | `CONDITION_NOT_MET` |
| `FAILED` / `TIMED_OUT` | 均非空 | `NONE` 或 `PARTIAL` | 至少 1 个 | 至少 1 个 issue |
| `CANCELLED` | 已有结算时间 | `NONE` 或 `PARTIAL` | 可有已启动 attempt | 至少 1 个 issue |
| `NOT_EXECUTED` | 未开始、已有结算时间 | `NONE` / `null` | 空 | 上游阻断、启动阻断或运行取消原因 |

跳过不是成功，失败也不能被汇合控制改写为成功。节点 18 必须逐支保留 N16/N17 的原状态、原因、
attempt 和可用产物。

### 6.2 NodeAttempt

每次真实启动都有独立 `attempt_id`、从 1 开始递增的 `attempt_number`、执行者、参数、输入/输出
artifact IDs、时间、状态、issues 和队列/运行耗时。`attempt_kind` 为：

- `INITIAL`：节点首次尝试；
- `RECALC`：N12 受控重算导致的后续 N11/N12 尝试；
- `RECOVERY`：运行恢复产生的新尝试，并用 `recovery_of_attempt_id` 指回原尝试。

N11/N12 的 `design_cycle` 只能为 1～3，其他普通节点通常为 `null`。固定三轮参数为
`24/0.1 → 48/0.3 → 64/0.5`，累计 candidate budget 上限 136；这三个 attempt 必须并存，不能只
保留最后一次。运行中的 attempt 其 `finished_at` 和 `runtime_ms` 为 `null`；失败、超时或取消的
attempt 必须有 issue。

### 6.3 NodeOutput

`node_output_envelope` 只冻结以下外壳：

| 字段 | 约束 |
|---|---|
| `payload_type` | 非空、可路由的类型名 |
| `payload_version` | 非空版本；未冻结科学体时使用 `UNFROZEN` |
| `data` | JSON 对象；本任务不冻结其科学字段 |
| `artifacts` | ArtifactRef 数组 |

LLM 只能转述后端已给出的 `data` 和 artifact 事实；不得在此对象内补算 Gate、Hard Filter、Pareto、
评分或科学结论。

## 7. 运行结果 envelope

### 7.1 顶层字段

| 字段 | 责任 |
|---|---|
| `run_id` / `request_id` / `idempotency_key` / `scenario_ref` | 把结果绑定到原请求和确定性场景 |
| `run_status` | 运行级状态 |
| `recovery_of_run_id` | 新恢复运行指向原运行；普通运行是 `null` |
| `started_at` / `finished_at` | 运行生命周期 |
| `current_node_ids` | 当前 RUNNING 节点；支持 N16/N17 并行可观察 |
| `input_fingerprints` | 必须逐字段等于已接受请求 |
| `control_decisions` | Gate、N12、N15、N16、N17 的固定决定事实 |
| `edge_traversals` | 实际走过的 E001-E027，含次序和回边重复 |
| `node_results` | 恰好 18 个注册节点结果 |
| `result` | 运行中为 `null`；终态为 Candidate、WT 或 Failure 外壳 |
| `issues` | 运行级错误/警告 |
| `audit` | 端到端追踪事件与审计 artifact |

### 7.2 运行状态

| `run_status` | 终态 | `result` |
|---|---:|---|
| `QUEUED` | 否 | `null` |
| `RUNNING` | 否 | `null` |
| `COMPLETED` | 是 | `CANDIDATE` 或 `WT` |
| `COMPLETED_WITH_GAPS` | 是 | N18 成功组装但明确保留分支失败/缺口的 `CANDIDATE` 或 `WT` |
| `FAILED` | 是 | `FAILURE`，且至少一个运行级 issue |
| `TIMED_OUT` | 是 | `FAILURE`，且至少一个运行级 issue |
| `CANCELLED` | 是 | `FAILURE`，且至少一个运行级 issue |

终态的 `finished_at` 非空且 `current_node_ids=[]`。`RUNNING` 时该数组必须等于状态为 `RUNNING` 的
节点集合；`QUEUED` 时为空。N16/N17 某支失败但两支均已结算，N18 仍可按 M1-03 进入；只有 N18
成功形成可交付结果时运行才可为 `COMPLETED_WITH_GAPS`，不能把 N18 自身失败包装成完成。

### 7.3 控制决定与边追踪

`control_decisions[]` 使用结构化 `control_type + decision + reason_code`：

| 控制类型 | 合法决定 |
|---|---|
| `DESIGN_SUITABILITY` | `DESIGN_SUITABLE`、`DESIGN_NOT_SUITABLE` |
| `N12_VALIDATION` | `VALIDATED_CANDIDATES_AVAILABLE`、`RECALC_REQUIRED`、`RECALC_EXHAUSTED` |
| `N15_DELIVERY_RECOMMENDATION` | `CANDIDATE_RECOMMENDED`、`WT_FALLBACK_RECOMMENDED` |
| `N16_APPLICABILITY` / `N17_APPLICABILITY` | `EXECUTE`、`SKIP_CONDITION`、`NOT_EXECUTED` |

`edge_traversals[]` 的 `sequence` 严格递增；同一 `edge_id` 可在有依据时重复，例如 N12 回到 N11
会重复 E015/E016。每次受控边必须关联对应 `control_decision_id`，每次节点尝试边应关联
`attempt_id`。M1-03 的源/目标对是语义断言；Gate、WT、分叉、汇合和终止控制以 `null` 表示，
不能伪造为新节点。

### 7.4 最终结果与交接

最终 `result` 只冻结 `result_kind`、不透明 `summary`、ArtifactRef 列表和 `handoff`。交接状态为：

- `NOT_REQUESTED`、`PENDING`、`DECLINED`、`DELIVERED`、`FAILED` 或 `NOT_DEPLOYED`；
- 只有 `DELIVERED` 可令 `delivered=true`，并必须有外部引用和时间；
- 当前 Agent C 接口未部署，示例统一为 `NOT_DEPLOYED`，不能因 N18 成功而宣称已交付生产系统。

## 8. 错误 envelope

错误是机器路由事实，不以 message 文本决定控制流：

| 字段组 | 约束 |
|---|---|
| 身份 | `error_id` 稳定；`code` 为大写机器码 |
| 分类 | `VALIDATION`、`CONTROL`、`TOOL`、`TIMEOUT`、`CANCELLATION`、`ARTIFACT`、`INTEGRITY`、`DEPENDENCY`、`INTERNAL` |
| 严重度 | `WARNING`、`ERROR`、`FATAL` |
| 可恢复性 | `RETRYABLE`、`NON_RETRYABLE`、`MANUAL_REVIEW` |
| 定位 | `node_id`、`attempt_id`、artifact IDs、规则引用、因果 error ID |
| 处置 | `manual_review_required`、`blocks_auto_handoff` |
| 解释 | `message` 面向人；`details` 只能附事实，不可含凭据或秘密 |

M1-04 冻结的最小错误码如下；后续可增加新码，但不得改变既有码语义：

| 错误码 | 典型层级 | 语义 |
|---|---|---|
| `REQUEST_SCHEMA_INVALID` | 请求 | JSON/字段类型/枚举不符合契约 |
| `REQUEST_IDEMPOTENCY_CONFLICT` | 请求 | 相同幂等 key 对应不同规范化请求 |
| `PROTEIN_SEQUENCE_MISSING` | 请求 | 缺失必填序列 |
| `HOST_SPECIES_MISSING` | 请求 | 缺失必填宿主物种 |
| `STRUCTURE_ARTIFACT_INVALID` | 请求/N01 | 结构格式、引用或完整性不合法 |
| `STRUCTURE_SEQUENCE_MISMATCH` | N01 | 后端事实证明结构与序列不一致 |
| `CONTROL_DECISION_MISSING` | 控制层 | 所需控制决定不存在 |
| `CONTROL_DECISION_INVALID` | 控制层 | 决定与类型或当前状态不一致 |
| `NODE_EXECUTION_FAILED` | 节点 | 节点执行失败的通用兜底码 |
| `NODE_TIMED_OUT` | 节点/运行 | 到达固定超时边界 |
| `NODE_CANCELLED` | 节点/运行 | 被明确取消 |
| `ARTIFACT_INTEGRITY_FAILED` | artifact | size/hash/受控引用校验失败 |
| `RECALC_EXHAUSTED` | N12/运行 | 第 3 轮仍无合格候选，走 E018 |
| `UPSTREAM_RESULT_UNAVAILABLE` | 节点 | 必需上游结果不可用，节点未执行 |
| `EXPRESSION_HOST_UNSUPPORTED` | N16 | 明确非空表达宿主不在后端已支持目录 |
| `AGENT_C_NOT_CONNECTED` | N18/交接 | Agent C 连接或交接能力未部署/不可用 |
| `INTERNAL_CONTRACT_VIOLATION` | 运行 | 运行快照违反本契约不变量 |

FailureReport 是面向最终失败交付的科学/方法报告类型，`error_envelope` 是控制与审计结构；两者不能
互相替代。相同 `error_id` 若同时出现在 attempt、node 和 run 层，核心字段必须一致。

## 9. 审计 envelope

`audit` 包含稳定 `trace_id`、`correlation_id`、按 sequence 排列的 append-only `events` 和可选
审计 ArtifactRef。事件类型固定覆盖：请求接收、运行创建/变更、节点变更、控制决定、边经过、
artifact 附加、错误、恢复请求和交接变更。

每个事件必须记录 actor、时间和可选 node/attempt/edge/decision 定位。审计细节不得存储密钥、
访问令牌、完整蛋白序列、原始结构内容或服务器绝对路径；需要证明内容时只记录指纹或 ArtifactRef。
事件只追加，不修改既有 sequence；恢复运行用新的事件和身份关联原运行。

## 10. 跨对象语义断言

JSON Schema 负责形状、必填、枚举和条件字段；以下关系由 M1-07 机器断言实现，在此已冻结：

1. `node_results` 严格为唯一且按序的 `N01`～`N18`；不能只有 18 个重复节点。
2. 请求与结果的 request、幂等、场景和输入指纹一致；有结构时三个格式/hash 事实一致。
3. node、attempt、decision、edge、error、artifact 和 audit 中的引用均能在同一 envelope 内解析，
   或明确指向原请求/原恢复运行。
4. `current_node_ids` 等于当前 RUNNING 节点集合；终态为空。
5. `edge_traversals.sequence` 和 `audit.events.sequence` 分别唯一、严格递增。
6. Gate WT 路径只能走 E012→E013，N11-N17 全为 `SKIPPED_BRANCH`，N18 可产生正常 WT 结果。
7. 设计路径只能走 E014；N12 成功走 E017，第一/二轮需重算走 E016，第三轮耗尽走 E018。
8. N11/N12 同轮 attempt 的 `design_cycle` 相同；最多三轮，预算参数固定且累计不超过 136。
9. `expression_host=null` 时，已到达设计分支的 N16 为 `SKIPPED_CONDITION`；明确非法值不能被改写为缺失。
10. E026 只能在 N16/N17 都处于可汇合终态后出现；N18 不得补算两支缺失结果。
11. `SUCCEEDED` 节点输出中的 ArtifactRef 与 attempt 的 output artifact IDs、最终 result 引用保持一致。
12. `scientific_compute` 在所有本契约 envelope 中恒为 `false`；出现真实生产断言即判失败。

## 11. 可解析示例

| 示例 | 覆盖重点 | Schema 结果 |
|---|---|---|
| [请求示例](../../../工作流设计/02-数据契约/examples/T01_PHASE1_MOCK_REQUEST_EXAMPLE_v0.1.json) | 规范化序列、宿主、可选本地结构 ArtifactRef、N16 缺省条件 | `PASS` |
| [候选完成示例](../../../工作流设计/02-数据契约/examples/T01_PHASE1_MOCK_RUN_CANDIDATE_EXAMPLE_v0.1.json) | 18 节点、设计支路、N16 条件跳过、N17 成功、N18 汇合 | `PASS` |
| [Gate WT 示例](../../../工作流设计/02-数据契约/examples/T01_PHASE1_MOCK_RUN_WT_EXAMPLE_v0.1.json) | E012/E013、N11-N17 分支跳过、WT 正常完成 | `PASS` |
| [N12 耗尽失败示例](../../../工作流设计/02-数据契约/examples/T01_PHASE1_MOCK_RUN_FAILURE_EXAMPLE_v0.1.json) | 三轮 attempt、两次 E016、E018、N13-N18 未执行、Failure 外壳 | `PASS` |

四个文件均已通过严格 JSON 解析、Draft 2020-12 Schema 校验和 RFC 3339 format 检查。示例中的
`payload_version=UNFROZEN` 是刻意的边界标记，不是完整科学 Schema 的版本；物理 ID 与
`scenario_ref` 已同步采用 M1-06 命名空间。

## 12. 未决项隔离

| 开放项 | 本任务已冻结 | 仍未冻结 |
|---|---|---|
| OI-004 | 缺失/空值/明确非空值边界；禁止从宿主物种推断；未知明确值归 N16 失败 | 支持表达宿主、别名和生产参数目录 |
| OI-009 | `design_objective` 三个请求值 | 目标权重、Pareto 与科学计算规则 |
| OI-010 | WT 和 Failure 的 envelope 表达、Gate WT 正常完成 | 生产阈值触发后的用户选择接口 |
| OI-013/014 | N18 启动、结果/交接外壳、`NOT_DEPLOYED` 事实 | 完整 CandidateRecord/AgentCHandoff/FailureReport 与 Agent C 协议 |
| OI-021/022 | 控制决定的结构化承载 | Gate 生产判据、N13/N15 完整排序规则 |
| OI-023 | 请求字段、格式、校验层级、指纹、追踪和 ArtifactRef 已在本任务收敛 | 生物学字母表等科学策略若无权威原件仍不得猜测 |

## 13. 验收结果与后续交接

| 验收项 | 结果 | 证据 |
|---|---|---|
| 六类 envelope | `PASS` | request、run、node、ArtifactRef、error、audit 均有必填和条件约束 |
| 状态与控制流兼容 | `PASS` | 九种节点状态、E001-E027、Gate、N12、N16/N17、N18 汇合均可追踪 |
| 18 节点完整性 | `PASS` | 三个终态示例均有 N01-N18；跨对象唯一/次序列入 M1-07 断言 |
| Mock 边界 | `PASS` | 固定 `MOCK_DATA`、`scientific_compute=false`、`PHASE1_FULL` |
| 科学字段不越界 | `PASS` | 节点和最终 summary 保持 opaque/UNFROZEN，OI-013/014 未被伪关闭 |
| 可解析示例 | `PASS` | 1 个请求 + 3 个结果均通过 Schema 与 format 校验 |
| 实现停止线 | `PASS` | 未新增 Mock 运行代码、工具适配器或 Dify DSL |

下一项为 `PH1-MOCK-M1-05`：在本 envelope 之上冻结确定性场景模型及每节点 Mock 输出责任；
不得把示例中的 opaque 数据当成已冻结科学 payload。
