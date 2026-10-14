# S-07 任务 5：结果、错误与追溯契约

> 交付状态：`COMPLETED_HISTORICAL_OFFLINE_CONTRACT / DEFERRED_OUT_OF_PHASE1`；文档版本：v0.2；日期：2026-09-03。  
> 机器契约：`s07.task5.v1-review`；验证批次：`p0-s07-task5-contract-20260903-b`。  
> 验证结论：`PASS_OFFLINE_CONTRACT_ONLY`；科学验收：`NOT_RUN`；部署：`NOT_DEPLOYED`。  
> 专家确认：仍为 [S07-EQ-01～05 五项](S07_EXPERT_CONFIRMATIONS.md)，均已获用户暂行批准、待专家确认。

> 后续覆盖：S-07 已移出一期；本契约只保留为历史工程证据，不进入 P0 v0.7 生产实现。

任务 5 已完成内部结果模型、文件保存规则、错误与恢复说明及离线验证。19 个结果场景、20 个
非法结果拒绝检查和 7 个文件/恢复检查全部通过，详见[验证报告][验证报告]。本文是 P0 v0.6
的工程评审输入；任务 6 的[非生产独立验收](S07_TASK6_ACCEPTANCE_AND_HANDOFF.md)已完成，生产
适配器和 OI-017 长任务运行时须按已评审的 P0 v0.6 门禁后续实施。

## 1. 依据与适用范围

| 依据 | 本任务采用的内容 |
|---|---|
| [Agent A SOP][SOP] S-07 L218–234 | PDB→AFDB、缺 accession 时 BLAST→UniProt、正常均无→S-08、partial 和 method_summary |
| [结构链规格][结构链规格] §2a、§3、§5 | 严格 PDB 阈值、元数据全部失败后回退、内部 none 与最终结构空值的区别、保留原始结构 |
| [Agent A SKILL][SKILL] R-48/R-58；SOP L391–393 | 来源失败不得静默、缺失残基 null、明确链/模型/插入码、多链歧义禁止自动交接 |
| [Agent A Schema][专家Schema] structure 与 MethodSummary | S-07 保存结构事实，S-09 生成质量结论；MethodSummary 记录方法和版本 |
| [既有开发决定](S07_DECISION_REPORT.md) D03–D10 | 唯一输入、候选和文件分别去重、不可变结果、错误与正常无命中分开 |
| [五项专家确认问题](S07_EXPERT_CONFIRMATIONS.md) | query coverage、NMR 优先级、AFDB 全长精确回验、多结果消歧、Swiss-Prot 范围均保持暂行状态 |

当前目标 profile 使用 API；本批次执行方式为离线证据回放和受控组合，新增网络调用为 0。
任务 3 的原始检索仍如实标注 `LOCAL`，任务 4 的原始调用标注 `API`，受控部分标注 `OFFLINE`。
目标服务器本地化继续按[任务 2 交接方案](S07_LOCAL_DATA_AND_RUNTIME_PLAN.md)由对方部署团队执行。

## 2. 交付物与校验层次

| 交付物 | 作用 |
|---|---|
| [JSON Schema](S07_TASK5_RESULT_CONTRACT.schema.json) | 字段、类型、枚举、取值范围和禁止额外字段 |
| [离线模型与文件校验器][模型] | 跨字段路由、不变量、文件哈希、输入绑定、来源/候选清单一致性和重试关系 |
| [证据构建与回放脚本][构建器] | 从任务 3/4 的冻结文件构建受控用例；`--verify` 只读取已保存结果 |
| [25 项契约回归测试][测试] | 验证实际文件、路由、错误边界、partial、歧义及恢复行为 |
| [批次与验证报告][验证报告] | 19 份结果、252 个内容对象、46 项检查及本次收尾复核记录 |

JSON Schema 由离线模型生成。JSON Schema 单独通过只说明结构合法；跨字段校验和文件校验
同样必须通过，才能称为本任务的有效结果。当前没有修改通用 `StepRequest/StepResult`、MCP
工具目录、Mock 场景或 Dify DSL，也未提供生产 HTTP/MCP 服务。

## 3. 唯一输入与固定执行档案

每个 `run_id` 绑定一份不可变输入快照和一份 profile，保存在 `bindings/<run_id>.json`。
快照包含 `protein_sequence`、`organism_name`、`accession_hint` 和原 FASTA 的文件引用。
结果只返回输入引用、序列 SHA-256、长度及辅助信息；不再接受第二份序列作为 S-07 输入。

校验器核对快照字节、序列哈希/长度、物种和 accession；每个来源记录及候选比对必须绑定
同一个输入。重试沿用相同 `run_id`、输入和 profile；改输入、检索范围或规则版本应创建新运行。
这验证的是本地证据记录的绑定，尚不是已实现的生产输入服务。

当前 profile 为 `s07-api-review-20260903`，声明 `intended_access_mode=API`、
`uniprot_search_scope=uniprotkb_swissprot`，并强制附带全部五个专家问题编号及
`PROVISIONAL_USER_APPROVED_EXPERT_PENDING`。任务 4 的 BLAST 参数原样保存在来源记录中，
标记为取证参数；其中返回上限 100 不是生产默认值，也不是新的科学筛选阈值。

## 4. 结果字段与下游路由

| 字段组 | 主要字段 | 含义 |
|---|---|---|
| 身份与边界 | `contract_version`、`record_kind`、`execution_kind`、`run_id`、`attempt` | 固定为 S-07 内部离线评审结果；明确批次、运行和尝试次数 |
| 执行状态 | `status`、`error`、`warnings` | 成功、降级、待复核、失败、取消分别记录 |
| 检索与选择 | `retrieval_outcome`、`selected_candidate_id`、`selection_reason_codes`、`next_step` | 是否已选结构，以及正常路径拟交给 S-08 还是 S-09 |
| 可信与复核 | `reliability`、`requires_review`、`review_reasons` | 执行完整性和复核要求；不代表 S-09 的结构质量等级 |
| 事实与文件 | `source_runs`、`candidates`、各 manifest 引用、`artifacts` | 来源执行事实、候选摘要、完整文件和追溯 |
| 恢复 | `prior_attempt_result_artifact_id` | 第二次及后续尝试必须引用上一份已保存结果 |

`status`、`retrieval_outcome` 和 `next_step` 必须符合下表。此处 `next_step` 是待对接的路由字段，
本批次没有实际调用 S-08/S-09。

| 情况 | `status` | `retrieval_outcome` | `next_step` | 附加要求 |
|---|---|---|---|---|
| 取得完整实验结构或 AFDB 结构 | `SUCCEEDED` | `EXISTING_STRUCTURE_SELECTED` | `S-09` | 唯一合格候选、完整文件/映射、来源路径闭合 |
| 取得 partial 结构 | `DEGRADED` | `EXISTING_STRUCTURE_SELECTED` | `S-09` | `PARTIAL_STRUCTURE` 警告，缺失位置保留 null |
| PDB 候选元数据全部失败，AFDB 成功 | `DEGRADED` | `EXISTING_STRUCTURE_SELECTED` | `S-09` | 保留来源错误、`UNRELIABLE`、失败级警告及 `requires_review=true` |
| 必要检索正常结束且无合格已有结构 | `SUCCEEDED` | `NO_ELIGIBLE_EXISTING_STRUCTURE` | `S-08` | 无未决候选、无来源错误、所需路径有完整结束证据 |
| 非精确 AFDB 候选、多 accession/model 或多链歧义 | `WAITING_USER` | null | null | 保留候选和复核原因；不按返回顺序选取，也不伪装成正常均无 |
| 超时、取数不全、非法标识、坏文件等 | `FAILED` | null | null | 保存 `ToolError`、已完成部分及原始证据 |
| 已取消 | `CANCELLED` | null | null | 错误类别为 `CANCELLED`，后续未执行来源保持 `NOT_RUN` |

规格仅明确“候选元数据全部失败→AFDB”这一回退。元数据部分失败时不能把余下候选当成全库
最优；全部失败后 AFDB 又无模型时，PDB 仍未查清，也不能声称“正常均无”。R11/R12/R19
分别验证这三种情况。R11 的 S-09 路由只允许继续取得质量事实，失败与复核标志仍须传递给
未来消费方；涉及权限、验证或交付结论的自动交接继续受 R-48 限制。

`WAITING_USER` 在本批次是结果枚举，尚未实现生产人工恢复入口。该状态记录具体运行的歧义，
不增加新的专家规则问题。

## 5. 每个来源必须说明是否真的执行

固定登记七种操作，每种恰好出现一次：`PDB_SEARCH`、`PDB_METADATA`、`PDB_STRUCTURE`、
`BLAST_UNIPROT`、`UNIPROT_RECORD`、`AFDB_LOOKUP`、`AFDB_STRUCTURE`。

| 来源状态 | 可表达的事实 |
|---|---|
| `SUCCEEDED_WITH_RESULTS` | 返回数量大于 0；若存在截断或部分失败，`complete` 必须为 false |
| `SUCCEEDED_EMPTY` | 正常返回 0 条，不得夹带失败；只有完整结束才可支撑正常均无 |
| `FAILED` | 保留错误，不声明完成或可用返回数 |
| `CANCELLED` | 保留取消类别，不声明完成 |
| `NOT_RUN` | 必须注明未执行原因；无请求/响应文件、远端时间、参数或版本，`complete=false` |

`evidence_kind` 区分 `FROZEN_REPLAY`、`CONTROLLED` 和 `NOT_RUN`，不能把受控状态写成新在线
调用。每条操作记录请求/输出文件引用、端点或数据发布、工具/数据版本、原始时间、回放评估时间、
参数、返回数量、`complete`、`capped` 和失败详情。

正常空路径可因缺少合法 accession 而跳过 AFDB。R05 的 BLAST 确认零命中后，后续来源均为
`NOT_RUN / NO_VERIFIED_IDENTIFIER`；这不等于“已经实际查询过 AFDB”。R06 的无模型 404
以合法 accession 和序列回验为前提，不能把所有 404 或非法标识 400 通用地解释为无结构。

任务 4 的真实 BLAST 正命中结果达到 100 条返回上限，R16 保留 `capped=true / complete=false`。
返回上限未解除前，既不能自动选结构，也不能据此宣称检索范围已经查完。

## 6. 候选、坐标与质量信息

实验结构候选保留 entry、entity、`label_asym_id`、`auth_asym_id`、model、assembly；AFDB
候选保留 accession、模型版本及链/模型信息。候选 ID 唯一，完整候选清单与返回摘要逐条核对，
不因结构文件字节相同就合并不同候选。

`alignment` 单独记录序列身份、identity、query/target coverage；`coordinate_mapping` 单独
记录实际坐标覆盖、缺失区段和逐残基映射文件。坐标区间按输入序列 **1-based、两端包含** 解释，
缺失位置为真实 JSON null；残基身份包含链、模型、author/label 编号和 insertion code。

受控 partial 用例 R02 由 6Q00 文件派生，76 个输入位置中 71–76 为 null；真实 9R2Q 的四条
匹配链仍在 R17 保留为歧义，每链映射 200/393。不得把 R02 描述为真实 9R2Q 已可自动选链。

候选 `source` 仅允许 `experimental` 或 `alphafolddb`。正常无结构通过 outcome 和空选择表达，
不创建 `source=none` 候选。AFDB 的实验方法/分辨率字段为 null，实验结构的 B-factor 不冒充
pLDDT。保存原始 confidence、PAE 及可复核的原生指标；AFDB metadata 的 global metric 与
保存的逐残基分数均值分开记录。

所有候选固定 `quality_assessment=PENDING_S09`；S-07 不生成 high/medium/low、
topology_reliable、低置信度掩码或完整 CandidateRecord。质量结论、最终结构组装和消费方
映射验收分别由后续步骤及相应门禁处理。

## 7. 文件保存与追溯

沿用 D09 的分类与不可覆盖原则；本离线批次不设置自动清理期限，也不执行删除。

| 文件组 | 本批次保存方式 |
|---|---|
| 运行说明 | 输入/profile、绑定、来源 manifest、MethodSummary、campaign 及每次尝试结果 |
| 原始科学数据 | 任务 3/4 原始请求/响应、FASTA、检索输出、mmCIF、confidence/PAE；导入前核对旧清单哈希 |
| 整理后的中间结果 | 完整候选、序列回验、逐残基坐标映射及受控派生文件；与原件分开保存 |
| 验证记录 | 46 项检查、非法状态拒绝原因、文件/恢复检查和测试报告 |

上述表描述本批次实际资产；生产临时文件、缓存及保留周期继续按
[D09 文件分类](S07_CONTRACT_REVIEW.md#94-文件分类与保留边界)和未来发布 profile 落实。

文件内容按 SHA-256 存入 `objects/<sha256>`，多个引用可共用同一物理对象。`ArtifactRef`
沿用通用字段，`logical_name` 为业务文件名，`resource_uri=artifact://<artifact_id>`；本地路径
只用于批次内部审计，不作为消费方的读取接口。

读取同时核对 `size_bytes` 与 SHA-256，因此同长度字节损坏也会被发现。结构解析还需检查
实际 mmCIF 格式；哈希正确只表示文件字节未变，不表示格式正确或科学上可用。故意损坏的
storage probe 单独放在 `controlled/storage-probes/`，不属于 252 个正常索引对象。

结果按 `results/<run_id>/attempt-NNN.json` 保存。结果自身的哈希登记在外部
[artifact_index.json][文件索引]，避免结果内部包含自身哈希的循环。索引同时保留原始来源路径。
`method_summary` 从来源事实确定性生成；原始时间或版本未报告时保留 null/`UNREPORTED`，
不将回放时间冒充远端运行耗时，也不把未执行来源写成已调用。

## 8. 错误、重复读取与恢复

错误沿用通用 `ToolError`：`code`、`category`、`retryable`、技术/用户说明和详情；来源错误
保留在 `source_runs[].failures`。结果失败/取消使用顶层 error，合法降级把原错误保留在来源中。
类别覆盖本批次的 `INPUT_VALIDATION`、`TOOL_UNAVAILABLE`、`TIMEOUT`、`OUTPUT_MISSING`、
`OUTPUT_INVALID`、`CANCELLED` 等，不把这些工程错误转换为科学上的“没有结构”。

重复读取同一尝试只校验并返回原字节；不会重新检索、生成时间戳或创建新尝试。尝试写入同路径
的不同字节会被拒绝，相同字节可重复保存。重试使用 `attempt+1`，引用上一结果，核对 run、输入
与 profile；R13 的超时失败和 R14 的成功分别保留为 `attempt-001` 与 `attempt-002`。

`retryable` 只记录该错误的恢复属性。任务 5 没有自动重试调度器、生产取消/断点续跑服务或
`T01_AwaitJob`；并发写入、崩溃中断、原子提交、权限和保留策略须在 OI-017/生产文件服务中验收。
同一冻结结果可重复读取并保持字节一致；重新调用在线 API 可能得到新数据发布，必须记录该变化。

## 9. 验证边界与后续交接

本批次复用 136 个任务 3/4 原始文件，共 3,458,076 字节，全部与先前 manifest 一致。已保存
19 份结果和 252 个内容对象；46 项检查通过。本次收尾再次核对文件、Schema 与来源一致性，
并运行全套 111 项测试，其中任务 5 为 25 项，详见[验证报告][验证报告]。

任务 6 已补充当前在线 S-07 连续执行、固定发布完整候选、真实多候选选择、资源/耗时及
S-08/S-09 交接形状验证；其余生产部署、消费方接入和恢复状态机仍需在完整 P0 v0.6 中处理。
R01 是单候选受控池；R04 使用受控的完整
BLAST 候选集；R06/R12 的 12 aa 输入只是来源组件探针，完整 T-01 会先在长度守卫处停止。
这些用例不能替代完整真实输入的端到端验收。

专家规则仍只有原来的五项。任务 5 不关闭 OI-018/015/019，不改变 P0 范围，也不使 P0 达到
`CONTRACT_READY` 或 `FROZEN`。后续按[任务安排](S07_IMPLEMENTATION_TASKS.md)和
[顺序交付计划](../../../../project-history/project/P0_P7_STAGE_DELIVERY_PLAN_20260903.md)推进；v0.6 工程评审已完成，但生产编码继续
等待对应科学规则、契约、G0 和发布门禁。
复核命令见[运行手册](../../../../full-t01-mock-v0.1/docs/development/RUNBOOK.md#11-s-07-任务-5-离线契约验证)。

[SOP]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md
[结构链规格]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md
[SKILL]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md
[专家Schema]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md
[模型]: ../../../../../scripts/s07_task5_contract.py
[构建器]: ../../../../../scripts/build_s07_task5_contract_evidence.py
[测试]: ../../../../tests/test_s07_task5_contract.py
[文件索引]: ../../../../../discovery/p0/s07/p0-s07-task5-contract-20260903-b/artifact_index.json
[验证报告]: ../../../../../discovery/p0/s07/p0-s07-task5-contract-20260903-b/reports/TASK5_CONTRACT_VALIDATION_REPORT.md
