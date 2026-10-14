# T-01 阶段 0（P0）科学工具实施方案

> **历史版本，已被 [P0 v0.7](../p0-v07-plan/P0_IMPLEMENTATION_PLAN.md) 替代。** 下文所有“当前/有效”表述只代表 v0.6 形成时点，不得恢复 S-07 或据此启动实施。

> 文档状态：`P0_V0_6_ENGINEERING_REVIEWED / PRODUCTION_ENTRY_BLOCKED`  
> 版本：v0.6  
> 日期：2026-09-03  
> 当前范围：S-07 → 按需 S-08 → S-09 → S-04 → 按条件 S-11  
> 当前部署：全部真实科学工具、MCP 适配器和 P0 Dify 工作流均为 `NOT_DEPLOYED`  
> 历史版本：[P0 实施方案 v0.5 归档](P0_IMPLEMENTATION_PLAN_v0.5_ARCHIVE.md)
> 范围同步：2026-09-03 一期 18 节点新基线确认 S-06 排除、S-11 为第 3 削减项；当前未触发削减，
> 因此 v0.6 完整五步骤、里程碑和工程评审结论继续有效。

## 1. 方案结论

v0.6 用五步骤 P0 范围和任务 3～6 的实测事实替换旧 v0.5 的六工具范围与 M0～M11 顺序。
本方案允许继续完成隔离取证、规则确认、生产契约、运行底座和发布准备，但不因文档完成而授权
生产适配器、Dify 真实工作流或科研使用。

当前 P0 的工程结论是：

1. S-07 已完成任务 1～6 的非生产证据、内部契约和独立验收，具备进入生产契约评审的材料；
   五项选择规则仍是 `PROVISIONAL_USER_APPROVED_EXPERT_PENDING`。
2. S-08、S-04 和 S-11 尚未完成锁定工具版本的 G0 实测；S-09 是确定性后端步骤，但实验结构
   分档和预测结构边界仍有权威文本冲突，尚不能冻结生产规则。
3. OI-017 的通用异步原则已决定，但生产状态机、`T01_AwaitJob`、恢复入口和逐工具 execution
   profile 尚未实现。
4. OI-015 继续阻塞 S-11 的 R-58 可执行映射规则；OI-019 已决定 S-06 排除和 S-11 削减顺位，
   OI-020 只承接未来缩减 profile 的触发、命名与下游降级语义。
5. 因此 P0 尚未达到 G1 `CONTRACT_READY`。下一阶段工作是补齐决定与 G0 证据，逐节点通过门禁，
   不能直接跳到旧 P0-M2 或批量实现全部工具。

## 2. 权威依据与版本关系

### 2.1 直接依据

| 依据 | 本方案采用的内容 |
|---|---|
| [一期 18 节点范围重基线](../project/PHASE1_SCOPE_WITH_P0_MAPPING_20260903.md) | 新一期范围、S-06 排除、S-11 第 3 削减顺位；当前默认完整 profile 不变 |
| [P0 范围重基线](../p0-v07-plan/P0_SCOPE_REBASELINE.md) | P0 只包含 S-07/S-08/S-09/S-04/S-11；S-06 不进入当前范围 |
| [五步骤专家依据对照](P0_EXPERT_EVIDENCE_MATRIX_MIXED_20260903.md) | 五步骤的输入、输出、执行条件、科学规则、失败处理、验收要求及 P0-Q01～Q17 |
| [权威业务资料索引](../../../工作流设计/01-业务依据/README.md) | 新一期图优先决定范围；旧算法图、PDF 与 Agent A v10.5 继续约束保留节点的科学细节 |
| [P0-P7 顺序交付计划](../project/P0_P7_STAGE_DELIVERY_PLAN_20260903.md) | G0～G6 门禁、阶段发布包和 P0 未冻结前不进入 P1 |
| [系统架构](../project/ARCHITECTURE_P0_P7_MOCK_20260903.md) | LLM、Dify、MCP/后端、Worker 和产物存储的职责边界 |
| [通用数据契约](../../full-t01-mock-v0.1/工作流设计/02-数据契约/T01_Dify节点-MCP工具映射与数据契约_v0.1.md) | `StepRequest`、`StepResult`、`ArtifactRef`、`ToolError`、Provenance 和异步工具入口 |

### 2.2 S-07 已有工程证据

| 材料 | 可用于 v0.6 的结论 | 不能据此声称 |
|---|---|---|
| [任务 3 固定发布检索](../../s07/discovery/p0/s07/p0-s07-task3-mmseqs-20260902-a/reports/TASK3_EVIDENCE_REPORT.md) | MMseqs2 输出、严格阈值后过滤、entry/chain、mmCIF 与 partial 映射形态 | 生产数据库或最终选择规则已冻结 |
| [任务 4 API 回退](../../s07/discovery/p0/s07/p0-s07-task4-uniprot-afdb-20260902-a/reports/TASK4_API_EVIDENCE_REPORT.md) | BLAST→UniProt→AFDB、正常空结果、无模型、非法标识、一对多和 isoform 的 API 事实 | 三项 accession 规则已获专家确认 |
| [任务 5 结果契约](../../s07/docs/archive/p0/S07_TASK5_RESULT_CONTRACT.md) | 结果、来源状态、候选、文件、错误、路由、不可变读取和重试关系 | 已实现生产状态机或消费方 |
| [任务 6 独立验收](../../s07/docs/archive/p0/S07_TASK6_ACCEPTANCE_AND_HANDOFF.md) | 固定发布和当前 API 的 10/10 非生产检查、资源记录、完整候选、S-08/S-09 交接形状 | G1 科学验收、生产部署或目标服务器本地库已完成 |

### 2.3 历史材料的使用方式

- [v0.5 归档](P0_IMPLEMENTATION_PLAN_v0.5_ARCHIVE.md)只用于追溯旧决定和实测背景，旧六工具范围、
  S-06、P0-M2 与 M0～M11 不再构成实施授权。
- [S-07 旧契约评审稿](../../s07/docs/archive/p0/S07_CONTRACT_REVIEW.md)、P0-M1 和 P0-M1B 继续作为输入/文件形态证据；
  `TARGET_MATCH`、`TARGET_DERIVED`、`HOMOLOG_TEMPLATE` 只保留为历史 discovery 分类。
- Dify/Mock v0.1 的 25 个确定性场景和 86 项原有测试继续作为工程回归基线；Mock 节点不能定义
  v0.6 的科学规则或生产范围。

## 3. P0 产品边界

P0 的业务名称是“结构与基础分析”，由两个业务节点、五个 S 步骤组成：

| 业务节点 | 步骤 | 责任 | 执行条件 | 当前成熟度 |
|---|---|---|---|---|
| 01 结构获取 | S-07 `structure.fetch` | 获取合格实验结构或公共预测结构；正常均无时形成 S-08 路由 | 入口守卫通过后必跑 | 非生产验收完成，生产契约待门禁 |
| 01 结构获取 | S-08 `structure.predict` | 无已有结构时用 AlphaFold3，规定条件下回退 ESMFold2 | S-07 明确返回无合格已有结构 | G0 未完成 |
| 01 结构获取 | S-09 `structure.assess_quality` | 从结构来源和原生指标确定质量、可靠性和低置信掩码 | S-07 或 S-08 取得结构后 | 规则冲突待确认 |
| 02 结构基础分析 | S-04 `topology.predict` | 预测拓扑标签、区段和派生事实 | 主链进入基础分析时必跑 | G0 未完成；许可/版本待落实 |
| 02 结构基础分析 | S-11 `structure.compute_rsa` | 经 R-58 映射后计算 SASA/RSA 与埋藏比例 | `quality.confidence != low` | OI-015 阻塞；G0 未完成 |

```text
规范化目标序列
  -> S-07 获取已有结构
       -> 已选结构 --------------------------┐
       -> 正常无合格结构 -> S-08 预测结构 ----┤
       -> 待复核/失败/取消 -> 停止自动路由     │
                                              -> S-09 结构质量
                                              -> S-04 序列拓扑
                                              -> confidence != low ?
                                                   -> 是：S-11 RSA
                                                   -> 否：rsa=null + SKIPPED_LOW_CONFIDENCE
                                              -> P0 evidence bundle
```

S-04 不以结构质量为前置条件。`topology_reliable` 是 S-09 的结构质量事实，不能代替 S-04 的序列
拓扑结果，也不能擅自成为 S-11 的额外跳过条件。

### 3.1 当前排除项

- S-06/PSORTb 已由最新用户范围基线正式排除，不进入 P0 实现、发布包或冻结条件；旧 Mock 节点
  仅为历史兼容，待 P0 G4 迁移时按变更计划处理。
- S-07b/S-07c Router 摄取入口不属于 T-01 P0 主链。本版本可保持接口兼容，不将其作为 P0
  冻结必需项。
- 表位、安全、保守性、可开发性、设计、排序和 Agent C 交付均属于 P1 以后。
- 外部 `context_scores` 注入继续禁用；真实 S-44 继续保持 `delivered=false`。
- 当前未触发削减，完整 P0 继续包含 S-11。未经 OI-020 的具名决定，不得建立、命名或启用删除
  S-11 的生产 profile，也不得隐去其对节点 13 L2 和下游证据的影响。

## 4. 职责与生产架构

### 4.1 职责边界

| 组件 | 可以做 | 不得做 |
|---|---|---|
| LLM/上层 Agent | 收集字段、发起工具、等待、解释已保存事实 | 科学计算、阈值判定、候选排序、权限合成、补猜缺失结果 |
| Dify | 调用阶段工具；依据后端固定枚举/布尔值路由；展示状态 | 解析科学原始文件、合并候选、计算质量/RSA、以异常文本驱动路由 |
| MCP/后端 | 校验契约、确定性规则、状态机、候选与产物索引、错误分类 | 接受任意 Shell/服务器路径；用 Mock/默认值补科学事实 |
| Worker | 在固定环境运行工具，保存输入、stdout/stderr、退出码和原始产物 | 直接形成未定义的产品结论 |
| 对象/元数据存储 | 保存不可变内容、引用、哈希、运行状态和保留信息 | 原位覆盖发布、复用旧结果冒充新运行 |

### 4.2 目标拓扑

```text
Dify T01_P0_Structure
  -> P0 MCP facade
       -> 规范化输入与运行绑定
       -> S-07 API adapter / 后续目标服务器本地 adapter
       -> S-08 GPU worker
       -> S-09 deterministic backend
       -> S-04 licensed worker
       -> S-11 CPU worker + R-58 mapper
       -> shared job state / artifact / provenance services
```

生产适配器与任务 6 的 `src/t01_s07_acceptance/` 必须分开。验收包可以复用纯解析与检查逻辑，
但不能直接作为 MCP 服务发布，也不能把报告内的批次路径暴露给调用方。

## 5. 输入、规范化与运行绑定

### 5.1 P0 直接输入

| 字段 | 要求 | 当前边界 |
|---|---|---|
| `protein_sequence` | 必填；进入后端前形成唯一规范序列和 SHA-256 | 允许字符、特殊字符、FASTA 标题/终止符处理仍归 P0-Q01 |
| `organism_name` | 可选；仅作 S-07 accession 消歧辅助 | 缺失时不得猜物种；不得覆盖序列事实 |
| `accession_hint` | 可选检索提示 | 必须回验序列；不能把提示当权威输入 |
| `epitope_mode` | 顶层守卫所需 | 只执行 SOP 已明确的 `<9 aa` 停止/警告条件，不新增模式规则 |
| `execution_mode` | `mock/smoke/production` | 工程枚举，不进入科学计算 |
| `client_request_id` | 幂等与审计 | 同键不同规范化载荷必须冲突 |

目标宿主与目标蛋白物种是不同概念。当前五步骤不消费宿主来改变科学路由；只有明确的
`organism_name` 才能作为 S-07 辅助信息。

### 5.2 唯一输入绑定

每个 `run_id` 绑定不可变的规范输入、profile、规则版本和执行模式。各节点只能从该绑定取得序列，
不得接收第二份独立序列。改变序列、检索范围、工具版本、规则版本或生产 profile 必须创建新运行；
同一运行的恢复沿用原绑定。

输入快照至少保存：规范序列、长度、SHA-256、原始上传 ArtifactRef、物种/accession 辅助字段、
规范化动作、拒绝或警告原因。未确认的字符支持不得由 Dify 或 LLM先行清洗。

## 6. 共同数据契约

### 6.1 版本与层次

v0.6 采用三层对象，避免把 S-07 中间结果直接冒充完整 CandidateRecord：

1. 通用 `StepRequest/StepResult`：调用、状态、错误、指标、Provenance 和 ArtifactRef。
2. `P0EvidenceBundle`：五步骤内部事实、路由、缺失原因和产物引用；本方案定义语义，精确
   Pydantic/JSON Schema 在 G1 冻结。
3. CandidateRecord：后续阶段的产品模型；P0 只提供组装输入，不在本阶段擅自增加最终字段。

### 6.2 P0EvidenceBundle 最小字段组

| 字段组 | 必需内容 |
|---|---|
| 身份 | `contract_version`、`run_id`、`input_ref`、`input_sequence_sha256`、`execution_mode` |
| 阶段状态 | `status`、`current_step`、`requires_review`、`review_reasons`、`next_action` |
| 结构 | S-07/S-08 来源、候选摘要、选中引用、方法、分辨率、序列比对、坐标映射、原生质量事实 |
| 质量 | S-09 `confidence`、`topology_reliable`、低置信区和警告；未运行时给原因 |
| 拓扑 | S-04 四类标准标签/区段/派生量，或 null；P/B 原生输出通过独立 ArtifactRef 保存 |
| RSA | S-11 逐残基 RSA、null 位置、`buried_fraction`、映射引用，或明确跳过/失败原因 |
| 方法与来源 | 每步工具/适配器/规则、版本、参数、数据库/模型发布、时间、退出码和资源摘要 |
| 错误与产物 | 稳定 `ToolError`、warnings、quality_flags、原始/标准化 ArtifactRef、先前尝试引用 |

所有逐残基数组按规范输入的 1-based 位置解释，并保持与输入等长；JSON 数组索引转换只在后端
实现。缺失位置使用 null，不得删除后缩短数组，也不得把 null 当 0。

### 6.3 共同状态和路由

| 情况 | 步骤/运行状态 | 自动路由 |
|---|---|---|
| 成功取得完整事实 | `SUCCEEDED` | 按明确 `next_action` 继续 |
| 允许继续但事实不完整 | `DEGRADED` | 只在规则明确允许时继续，并携带警告/可靠性 |
| 候选、链或规则无法唯一裁决 | `WAITING_USER` 或 `REVIEW_REQUIRED` | 停止自动交接 |
| 工具、输入、输出、超时或候选完整性失败 | `FAILED` | 不转换成正常空结果 |
| 用户取消完成 | `CANCELLED` | 停止；保留已完成部分和取消事实 |
| 当前调用窗口仍在等待 | `QUEUED/RUNNING` | 返回 `job_id`，由 OI-017 流程处理 |

S-07 的生产 outcome 采用 `EXISTING_STRUCTURE_SELECTED`、
`NO_ELIGIBLE_EXISTING_STRUCTURE`、`REVIEW_REQUIRED`、`FAILED`、`CANCELLED`。旧三类 discovery
分类可作为历史标签保留在 provenance，不能驱动 v0.6 生产路由。

## 7. S-07 实施方案：已有结构获取

### 7.1 已确认流程

1. 用规范输入序列查询 RCSB PDB，候选必须同时满足严格 `identity > 0.95` 和严格
   `coverage > 0.90`；等于阈值不通过。
2. 暂行使用 query coverage 作为筛选分母，target coverage 只记录；该决定附带 S07-EQ-01。
3. 对合格实验候选读取 entry/entity/chain/model/assembly、实验方法、正 Å 分辨率、日期和 mmCIF；
   保存完整候选，不只保留选中条目。
4. 暂行在 X-ray/cryo-EM 可比候选中选择最小正 Å；无可比候选时再回退 NMR。NMR 与 Integrative
   等不可比方法作为候选和 WARNING 保留；该决定附带 S07-EQ-02。
5. 同分辨率、多 NMR、多条等价链、元数据不完整或无法唯一确定链时进入复核，不能按 API 顺序
   打破并列。R-58 多链歧义必须阻止自动交接。
6. PDB 正常没有合格结构时查询 AlphaFold DB；缺 accession 时先以 BLAST 对 UniProt 取得候选。
7. BLAST-derived accession 只有在输入、UniProt 和 AFDB 模型全长序列完全一致时才可暂行自动采用；
   序列合格后可用精确 `organism_name` 缩小，多项仍并列则进入复核；当前搜索范围暂用 Swiss-Prot。
   三项分别附带 S07-EQ-03～05。
8. 所需来源正常完成且均无合格结构时，返回 `NO_ELIGIBLE_EXISTING_STRUCTURE` 并路由 S-08。
   请求失败、取数不全、触顶、坏文件或解析失败不得改写成该 outcome。

### 7.2 候选完整性门禁

- RCSB API 使用完整返回或可证明闭合的分页/游标；保存 reported/returned count 和查询原文。
- 元数据按 entity/chain 关联，不能只按 PDB ID 合并；结构文件去重与候选去重分开。
- BLAST 命中数达到配置上限时必须标记 `candidate_collection_complete=false`，禁止自动选择。
  任务 6 已观察到 100 条恰好触顶；生产 profile 必须给出可证明闭合的收集方法及受控上限策略。
- 任一必要候选字段批量读取部分失败时，不能声称剩余集合包含全局最优候选。
- API 与目标服务器本地 profile 必须产生相同语义、状态和完整性证据；返回数量无需逐字相同。

### 7.3 文件与交接

保留原始请求/响应、候选清单、选中 mmCIF、序列比对、坐标映射和来源版本。实验结构或 AFDB
结构取得后交给 S-09；partial 保持结构并记录等长 null 映射。S-07 不生成 high/medium/low，所有
候选保持 `quality_assessment=PENDING_S09`。

### 7.4 S-07 进入 G1 的门禁

- S07-EQ-01～05 获专家书面确认，或正式发布范围明确排除依赖这些规则的自动路径；
- 完成候选并列、多个 NMR、异常/缺失分辨率、撤回条目和部分元数据失败的确定性选择表；
- 解决 BLAST 正命中候选触顶问题，并冻结 API profile；
- 将任务 5 契约转为生产 Pydantic/JSON Schema，与通用 StepResult 对齐；
- 固定错误、人工复核、S-08/S-09 路由和 OI-017 恢复状态；
- 目标服务器本地 profile 若进入本次 release，由接收方完成发布/索引/哈希验收；否则明确排除。

上述门禁未齐前，只能维护 discovery/验收代码和生产契约草案，不启用生产 MCP。

## 8. S-08 实施方案：按序列预测结构

### 8.1 当前规则边界

- 当前 P0 首算固定 `mutation_count=0`，默认引擎为 AlphaFold3。R-04 的变体复用区间不属于本次
  零突变实现门禁，后续复用前单独解决 P0-Q06。
- 1000～1500 aa 输出长序列 WARNING；>1500 aa 输出超长序列 WARNING。只有专家规定的
  AlphaFold3 OOM 或超时大于 2 小时路径才自动回退 ESMFold2，不能外推到所有故障。
- AlphaFold3 单体 5 个 diffusion 样本按最高 pTM 选择；部署前必须比较官方碰撞相关排序，避免
  简化规则选入 `has_clash` 模型。
- AlphaFold3 per-atom pLDDT 取 Cα，0～100 除以 100；ESMFold2 必须先识别原生标度。缺 pTM
  能力时为 null，不得编造。
- 保留 AlphaFold3 mmCIF 原件。PDB 转换失败为 WARNING，不删除 mmCIF；只接受 PDB 的后续
  工具自行产生明确失败。

### 8.2 G0 取证包

在目标 Linux/GPU 候选环境中分别锁定 AlphaFold3 和 ESMFold2 的代码、模型、数据库、容器、
CUDA/驱动/PyTorch 和许可证/权重授权。至少保存：

- 短单体正常运行的全部样本、排名原文、pLDDT/pTM、mmCIF 和资源曲线；
- 0～100 与 0～1 pLDDT 标度、缺 Cα、NaN、缺 pTM、样本分数并列和碰撞模型；
- 1000、1500 和 >1500 aa 边界，AlphaFold3 OOM、超时、取消及 ESMFold2 成功/失败；
- 重复运行、随机种子、模型缓存、网络依赖、磁盘、GPU 显存与峰值内存；
- mmCIF→PDB 成功和失败，同时证明原件不被覆盖。

### 8.3 进入 G1/G2 的门禁

P0-Q07 的标度、缺失值、碰撞与固定 notes 规则经确认；OI-017 execution profile 填完；锁定版本
和授权证据齐全；算法负责人签收具名正常、边界、降级与失败样本。完成前不得把环境清单中的
“约 5～30 分钟/约 5～10 秒”当生产 deadline。

## 9. S-09 实施方案：结构质量评估

S-09 是纯后端确定性步骤，不调用新科学工具。它只能消费 S-07/S-08 已保存的原生事实，不能从
B-factor、文件名、来源顺序或缺失值推测质量。

### 9.1 已明确规则

- 输出 `confidence=high/medium/low`、`topology_reliable`、`low_confidence_regions` 和 warnings。
- 预测结构：mean pLDDT `>=0.70` 为 high，`<0.50` 为 low；pTM `>=0.50` 时
  `topology_reliable=true`，否则含 null 为 false。
- 低置信掩码使用逐残基 pLDDT `<0.50`、连续长度 `>=5 aa`、相邻段间隔 `<=3 aa`，并同时写入
  structure 与 quality；实验结构或无逐残基值时为 null。
- unknown source 输出 low+WARNING；AlphaFold DB 无逐残基 pLDDT 有专门的 medium+WARNING
  条款，但其与存在均值时的先后关系尚未冻结。

### 9.2 阻止生产实现的冲突

- X-ray 4.0 Å、resolution=null、NMR 未覆盖区间、其他/未知方法存在重叠或未赋值条款；
- pLDDT 0.70 同时落入“>=0.70 high”和原文“0.50–0.70 medium”的文字边界；
- 掩码的“先筛长度还是先合并”、数组缺失/不等长、partial 和空数组语义未定义；
- `topology_reliable` 对未知来源的完整输出未定义。

进入 G1 前，算法负责人必须给出无重叠、覆盖全部输入的决策表和掩码算法顺序，对
P0-Q08/Q09 形成具名版本。工程可先实现原生事实校验器和决策表执行框架，但不能选择默认分支。

## 10. S-04 实施方案：序列拓扑预测

### 10.1 已明确规则

- 输入为规范序列，S-04 在基础分析主链必跑，不依赖结构质量。
- 标准输出为与序列等长的 inside/outside/TMhelix/signal 标签、连续 segments、`has_signal`、
  `tm_count` 和 `outside_length`；坐标为 1-based、两端包含。
- `tm_count` 是 TMhelix 区段数，`outside_length` 是 outside 残基数；signal 出现即
  `has_signal=true`。
- 工具不可用时 topology=null+“拓扑预测不可用”WARNING，不伪造全 inside/outside。
- 原生 P/B 标签出现时 topology=null、unreliable、失败级 WARNING并禁止自动交接；原生等长标签
  必须通过独立 ArtifactRef 保留，不能塞入四枚举数组。

### 10.2 G0 与实现门禁

锁定 DeepTMHMM 实际版本、服务/模型标识、默认参数、pybiolib/网络行为和 DTU 学术许可。
取证正常四标签、N 端 signal、单跨膜大 outside、P/B、工具不可用、非法输入、标签不等长和
segments 不一致。P0-Q11 必须确定原生标签、unreliable 和状态字段的载体；P0-Q10 必须确定何时
继续、何时产生 FailureReport。下游 S-16/step22 的联动不作为 P0 完成条件。

## 11. S-11 实施方案：SASA/RSA

### 11.1 已明确规则

- 只在 `quality.confidence != low` 时执行；low 时不调用 FreeSASA，返回
  `rsa=null / SKIPPED_LOW_CONFIDENCE`。
- 计算前执行 R-58：输入序列、链、model/assembly、author/label 残基编号和 insertion code
  必须形成可追溯映射；无法唯一选链或解析插入码时禁止自动交接。
- FreeSASA 计算全原子绝对 SASA，单位 Å²；RSA 使用 Tien 2013 Gly-X-Gly `Theoretical` 列。
- `buried_fraction=count(RSA<0.20)/len(input_sequence)`；0.20 本身不计入 buried，全长为分母。
- A/R/G 的锁定参考面积为 129.0/274.0/104.0 Å²；缺失或不可算残基保持等长 null+WARNING。

### 11.2 阻塞与 G0 要求

OI-015 保持 `BLOCKED`。算法负责人需确认比对算法和参数、允许替换/截短/标签差异、链/model/
assembly 选择、覆盖/失败阈值、目标位点可映射性和强制复核状态。P0-Q13 还需冻结 FreeSASA
算法、探针半径、原子半径、复合物范围、替代构象、非标准原子、null 计数、全空、NaN 和 RSA>1
处置。

G0 至少覆盖完整、partial、多链、插入码、非标准残基、缺原子、全空、低置信跳过和工具失败；
输出原始 SASA、逐残基映射、等长 RSA 和参数档案。OI-015 未解除前不得实现生产 S-11 适配器，
也不得用任务 6 的 S-07 映射替代 S-11 金标准。

## 12. API、本地数据与运行 profile

### 12.1 S-07 当前 API profile

首个候选 release 走官方 API：RCSB Search/Data/structure、UniProt 和 AlphaFold DB；BLAST 对
UniProt 的具体服务、数据库范围、返回上限、重试和候选闭合方式在 G1 固定。允许的 host、TLS、
请求预算、分页/批量大小、退避、deadline、缓存和响应版本都写入 `s07-api` execution profile。

API 返回是运行时事实。每次运行保存请求、响应、HTTP 状态、远端版本/日期、返回数量和哈希；
API 更新后不得用旧幂等结果冒充新查询。

### 12.2 目标服务器本地 profile

最终本地数据库由接收方部署团队按
[S-07 本地数据交接方案](../../s07/docs/archive/p0/S07_LOCAL_DATA_AND_RUNTIME_PLAN.md)实施。17 组索引/资源是部署清单，
不要求用户逐项作答。接收方需要完成容量、许可、发布目录、manifest、索引构建、哈希、离线
运行、更新与回滚验收。

若本地 profile 不进入首个 P0 release，发布清单必须明确标记
`TARGET_SERVER_LOCAL_PROFILE_EXCLUDED_PENDING_RECEIVING_TEAM`。若进入，则其候选、状态、错误和
ArtifactRef 必须与 API profile 契约等价，并用同一验收集比较不变量。

### 12.3 其余工具 profile

AlphaFold3/ESMFold2、DeepTMHMM 和 FreeSASA 分别使用隔离运行环境。发布清单记录精确
commit/version、模型/数据库、容器 digest、OS、Python、CUDA/驱动、依赖、许可、CPU/GPU、
内存/显存、磁盘、网络与临时空间。专家材料中的估计耗时只用于 G0 设计，不直接成为生产数值。

## 13. OI-017 异步状态机与恢复

S-07 API 可在 execution profile 证明足够短时同步执行；S-08 必须按长任务设计。其他工具根据
G0 实测决定同步或异步，不能仅按工具名称猜测。

### 13.1 必须实现的语义

- 同一幂等键+同一规范载荷返回同一 `job_id`；同键不同载荷返回确定性冲突。
- 一个 v10 串行 `run_id` 同时最多一个活动科学作业，重复进入不能重复提交。
- 后端持久状态是事实源；`jobs.get_status` 只读，不因轮询次数推进。
- `QUEUED/RUNNING` 不返回完整结果；终态由 `jobs.get_result` 幂等、不可变读取。
- 工具 deadline 与 run deadline 超时进入 `FAILED/TIMEOUT`，不得混同取消。
- 取消先记录 `cancel_requested=true`；首次持久化终态胜出，重复取消返回原终态。
- `T01_AwaitJob` 使用有界等待；窗口结束仍未终结时返回 run/job/status/resume_after。
- 恢复以相同 `run_id` 重入，通过幂等绑定找到原作业和已完成步骤。

### 13.2 每个 execution profile 的必填字段

同步/异步分类、初始轮询间隔、退避与最大查询频率、工具/run deadline、取消能力、可重试查询
错误、并发/队列限制、资源等级、结果与产物保留期、失败清理和恢复策略。任一生产工具缺这些
字段时不得启用 `production`。

### 13.3 OI-017 验收

验证幂等提交/冲突、只读轮询、超时、取消前后竞态、完成/取消竞态、重复取消、结果不可变、
短等待返回、跨调用恢复、worker 崩溃、存储暂时不可用和过期产物。任务 5 的离线重试证据可复用
为输入，但不能替代生产并发、原子提交和恢复测试。

## 14. 产物、追溯与保留

- 原始输入、请求/响应、stdout/stderr、退出码、原始结构/质量/标签/SASA、标准化结果和测试报告
  均使用不可变 ArtifactRef；服务响应不返回服务器绝对路径。
- 每次运行记录 adapter/tool/rule/model/database/profile 版本、参数、环境摘要、输入与产物哈希、
  开始/结束时间和资源指标。未报告字段保持 null/`UNREPORTED`。
- 内容去重与业务候选分开；相同字节可共用对象，不合并不同 accession/entity/chain/model 语义。
- 读取同时校验 size 和 SHA-256；哈希正确不代表格式或科学可用，仍执行格式/Schema 检查。
- 失败尝试、取消和重试记录不覆盖。恢复引用上一尝试；新数据发布或 profile 创建新运行。
- 原始、标准化、日志、缓存、临时文件和测试证据分别配置保留期。自动清理策略必须在 release
  profile 明示并经过恢复/回滚验证。

## 15. v0.6 实施里程碑

| 里程碑 | 工作与退出证据 | 状态 |
|---|---|---|
| `P0-V06-M0` 方案重写与工程评审 | v0.5 归档；五步骤范围、证据、门禁、顺序、验收和停止线写入 v0.6；形成评审记录 | `COMPLETED_ENGINEERING_REVIEW` |
| `P0-V06-M1` 决定与证据 backlog | 将 P0-Q01～Q17、S07-EQ-01～05 和受影响 OI 拆成具名决定、工程契约、G0 实测三类；为每项绑定负责人、证据、解除条件和验收资产 | `IN_PROGRESS_M1_01_TO_M1_03_COMPLETE`；见 [统一 backlog](P0_V06_M1_BACKLOG.md)与[专家分批材料](../README.md) |
| `P0-V06-M2` S-07 G0 收口 | 解除候选触顶；补齐选择边界输入证据、API profile 和可追溯 G0 证据 | `BLOCKED_BY_CANDIDATE_COMPLETENESS` |
| `P0-V06-M3` S-08 G0 | 锁定 AF3/ESMFold2 候选环境，完成正常/边界/故障/资源证据 | `NOT_STARTED` |
| `P0-V06-M4` S-09 决策与验证证据 | 取得无重叠决策表、掩码算法、边界样例和确定性后端验证预期 | `BLOCKED_BY_P0_Q08_Q09` |
| `P0-V06-M5` S-04 G0 | DeepTMHMM 版本/许可、正常/P/B/失败证据和输出载体输入齐全 | `NOT_STARTED` |
| `P0-V06-M6` S-11 G0 与 R-58 证据 | FreeSASA 参数、映射、数值、partial/多链/插入码和失败证据齐全 | `BLOCKED_BY_OI_015` |
| `P0-V06-M7` P0 契约冻结 | 基于 M2～M6 证据冻结规则、Schema、状态、路由、验收预期和 OI-017 profile；达到 G1 | `BLOCKED_BY_RULE_SCHEMA_AND_G0_GATES` |
| `P0-V06-M8` 生产底座与五步骤适配器 | 实现输入绑定、ArtifactRef、状态机、`T01_AwaitJob`、恢复及五步骤适配器；通过 G2 | `NOT_STARTED` |
| `P0-V06-M9` P0 release bundle | 镜像/环境、manifest、许可、安装、smoke、金标准、失败、资源、回滚全部完成；通过 G3 | `NOT_STARTED` |
| `P0-V06-M10` P0 Dify 工作流 | 只改生成源，重新生成、绑定、导入、发布并刷新 Workflow Tool；通过 G4 | `NOT_STARTED` |
| `P0-V06-M11` 阶段验收与冻结 | 新 run_id 完成 P0 独立、故障/恢复及受影响 Master 前缀回归；完成 G5/G6 并同步基线 | `NOT_STARTED` |

### 15.1 严格推进顺序

```text
M0 v0.6 工程评审
  -> M1 决定与证据 backlog
  -> M2/M3/M4/M5/M6 补齐五步骤 G0 与决策输入
  -> M7 基于 G0 证据达到 G1
  -> M8 生产底座与五步骤实现（G2）
  -> M9 阶段工具打包（G3）
  -> M10 Dify 工作流（G4）
  -> M11 阶段验收与冻结（G5/G6）
  -> 才能开始 P1 真实工具
```

M1 只建立可追踪工作包，不冻结生产契约。G0 取证和具名规则确认可并行准备，但依赖同一事实的
编辑必须顺序收敛；M2～M6 的适用 G0 证据齐全后才进入 M7。任一节点在 G1 前不得进入其生产
适配器；阶段发布包完成前不得把真实工具接入 Dify。

## 16. 验收矩阵

### 16.1 工具与后端

| 步骤 | 必须覆盖的正常/边界 | 必须覆盖的失败/降级 | 当前状态 |
|---|---|---|---|
| S-07 | 完整实验结构、partial、AFDB、正常均无、严格阈值、全候选与可比/不可比方法 | 并列、多链、触顶、元数据部分/全部失败、404/400、坏文件、超时、取消/恢复 | 任务 6 非生产 PASS；G1 待门禁 |
| S-08 | AF3 多样本、Cα pLDDT、pTM、mmCIF、ESMFold2 标度 | 长度边界、OOM、>2h 超时、fallback 双失败、碰撞、缺指标、格式转换失败、取消/恢复 | G0 未执行 |
| S-09 | X-ray、cryo-EM、NMR、AFDB/AF3/ESMFold2、0.50/0.70 边界、掩码合并 | null/非法 resolution、未知方法/source、数组缺失/不等长/NaN、partial | 决策表待确认 |
| S-04 | 四标签、signal、单 TM 大 outside、区段和派生量 | P/B、工具不可用、非法输入、标签/区段不一致 | G0 未执行 |
| S-11 | A/R/G 参考值、完整/partial、0.20 边界、全长分母、多链/插入码 | low 跳过、链歧义、映射失败、非标准/缺原子、全空、NaN/RSA>1、工具失败 | OI-015 阻塞 |

### 16.2 P0 路径

1. 合格实验结构→S-09→S-04→非 low 时 S-11。
2. 无实验结构、AFDB 精确结构→S-09→S-04→S-11 门控。
3. 所需已有结构来源正常均无→S-08 AF3→S-09→S-04→S-11 门控。
4. 规定的长序列 AF3 OOM/超时→ESMFold2 成功与双失败。
5. S-09 low→S-04 仍执行，S-11 不调用且 rsa=null/原因明确。
6. S-04 不可用→topology=null+WARNING；P/B→unreliable 并禁止自动交接。
7. S-07/S-08/S-11 partial、坐标缺失和 R-58 映射保持逐残基对齐。
8. 候选不完整、链歧义、规则无法唯一裁决时停在复核，不自动落入 S-08/S-09。
9. 同步、异步、超时、取消、重试和跨调用恢复均能回到同一输入、作业和不可变产物。
10. 每条路径可从 P0 bundle 追溯到原始输入、工具/规则/profile、来源文件和哈希。

### 16.3 发布与工作流

- 全新目标环境按 manifest 完成安装/预检；错误版本、缺数据、缺权重、缺许可和哈希不一致会停止。
- 每个工具 smoke、算法负责人批准的金标准、失败/降级、资源和回滚均有机器报告。
- P0 Dify 只按 `next_action/status/confidence` 等后端枚举或布尔值路由，无 LLM/Code/HTTP 科学计算。
- 阶段 Workflow 和受影响 Master 路径使用新 run_id，覆盖成功、无结构、low、降级、失败、取消和恢复。
- `execution_mode` 在工具、阶段输出和最终审计中一致；Mock/smoke 不得标成 production。

## 17. P0 release bundle

阶段发布包允许多个隔离镜像/环境，由一个 `p0-release-manifest` 统一引用，至少包含：

1. release ID、P0 contract/workflow 版本、五个 MCP tool name、明确排除项和 profile 列表；
2. 每个工具/adapter/rule 的版本/commit、镜像 digest、模型/数据库发布及 SHA-256；
3. 输入输出 Schema、状态/错误/路由、ArtifactRef、Provenance 和兼容迁移说明；
4. OI-017 execution profile、资源/并发/deadline/取消/恢复/保留配置；
5. 安装、许可证/授权、网络白名单、数据准备、预检、健康检查和卸载说明；
6. smoke、金标准、故障、恢复、性能、完整性和回滚报告；
7. API 与本地 profile 的包含/排除状态；S-11 若未包含，必须使用经 OI-020 批准的缩减版名称；
8. P0 Workflow 所绑定的准确 release 摘要和回滚目标。

工具在 G3 前保持 `NOT_DEPLOYED`。发布包形成不等于 P0 冻结，仍须完成工作流与阶段验收。

## 18. Dify 迁移

1. 五步骤适配器和阶段发布包先独立验收。
2. 仅修改 `src/t01_dify_workflows/generator.py`；不批量手改生成 YAML。
3. 从生产 P0 主链移除旧 S-06 路由，但保留 v0.1 Mock 模板和历史回归资产；迁移前后分别验证。
4. 为异步步骤调用可复用 `T01_AwaitJob`，短窗口未完成时返回恢复信息，不在 Dify 内自行推进状态。
5. 重新生成与绑定、覆盖导入、发布更新、刷新 Workflow Tool。
6. 先跑 P0 独立场景，再跑受影响 Master 前缀；每次使用新 run_id，保留真实 Dify 追踪。

Dify 只消费后端 projection；若画布字段大小或形态受限，在 MCP facade 增加展示投影，不改变后端
权威结果或原始产物。

## 19. 风险与停止线

| 风险/缺口 | 当前处置 | 停止条件 |
|---|---|---|
| S-07 五项暂行规则 | 继续附带专家问题 ID；生产契约不得去掉状态 | 专家未确认且自动路径依赖这些规则时停在 G1 |
| BLAST 候选触顶 | `complete=false`，禁止自动选择 | 不能证明候选闭合时不得发布该自动路径 |
| S-09 分档冲突 | 等待无重叠决策表 | 不得由实现者选默认后写生产测试 |
| DeepTMHMM 版本/许可 | G0 锁定并取得授权 | 无可审计许可/版本不得打包 |
| R-58 与 RSA 参数 | OI-015 保持 BLOCKED | 未具名确认不得实现生产 S-11 |
| S-11 削减 profile | 最新基线确认其为第 3 削减项；当前完整 P0 默认包含 | OI-020 未决定不得创建无 S-11 的生产 profile |
| 异步运行 | 按 OI-017 实现 | 无状态机/profile/恢复测试不得启用 production |
| 目标服务器本地库 | 接收方部署；首发可明确排除本地 profile | 未完成交接验收不得标本地 profile DEPLOYED |
| API 或工具缺事实 | 保存缺口、错误或 null | LLM/Dify/adapter 不得补猜 |
| 科学金标准缺失 | smoke 与科学验收分开 | 无具名金标准不得通过 G1/G3/G5 |

所有真实工具继续视为 `NOT_DEPLOYED`。未完成对应 G0、G1 和 execution profile 的节点不进入生产
编码；P0 未按当前完整 profile `FROZEN` 前不开始 P1 真实工具。未来若触发 S-11 削减，必须先
关闭 OI-020、对本方案升版并重新评审 P0 的 G6 与 P1 解锁条件。

## 20. 完成定义

### 20.1 本方案工程评审完成

- v0.5 已归档且主入口为 v0.6；五步骤范围、证据、门禁、里程碑、验收和停止线一致；
- 没有把任务 6、Mock、smoke 或局部实测写成生产/科学验收；
- 所有已知 P0-Q/OI/专家问题有责任、影响和进入条件；
- 文档链接、状态入口和阶段计划同步并通过检查。

满足这些条件只完成 `P0-V06-M0`，不等于 G1。

### 20.2 `P0_CONTRACT_READY`

- 五步骤所需科学规则形成无冲突、覆盖边界的具名版本；
- S-07 五项、S-09 分档/掩码、S-04 状态载体、S-11 R-58/RSA 及 P0 bundle Schema 满足 G1；
- 受影响 OI 已 `DECIDED` 或被明确排除，逐工具 G0 证据和验收样例可追溯。

### 20.3 `P0_TOOLS_PACKAGED`

- 五步骤适配器、共享运行底座、固定 profile 和 release bundle 完成；
- 全新环境安装、许可、smoke、金标准、失败/恢复、性能、完整性和回滚全部通过；
- 所有工具状态与 release manifest 一致，无浮动版本或未声明能力。

### 20.4 `P0_FROZEN`

- P0 Dify 工作流只调用已打包工具，独立与 Master 前缀新批次全部通过；
- 成功、无结构、low、partial、复核、故障、超时、取消和恢复路径均有真实证据；
- 状态、路线图、运行手册、数据契约、开放项、版本与基线同步；
- 专家/业务/后端/Dify/运维验收责任和签收记录齐全。

只有达到 `P0_FROZEN` 才允许进入 P1 真实工具实施。

## 21. v0.6 评审入口与下一动作

工程评审见 [P0 v0.6 评审记录](P0_IMPLEMENTATION_PLAN_V0_6_REVIEW.md)。评审已逐项检查：

1. 五步骤范围与 S-06/S-11 边界；后续一期新基线已决定 S-06 排除和 S-11 削减顺位；
2. 任务 3～6 的事实、五项暂行规则和 BLAST 候选完整性；
3. S-08/S-09/S-04/S-11 的 G0、科学规则和许可证门禁；
4. P0 bundle、错误/复核状态、OI-017 和 ArtifactRef；
5. G0～G6、release bundle、Dify 迁移、验收与停止线。

评审结论为 `ENGINEERING_REVIEW_PASS_WITH_BLOCKING_GATES`。后续最新一期基线没有改变当前默认
五步骤，因此不需要重开 v0.6 工程评审；若触发无 S-11 的缩减 profile，则必须升版重审。
`P0-V06-M1` 已启动：[统一 backlog](P0_V06_M1_BACKLOG.md)完成 M1-01～M1-03，
[专家分批材料](../README.md)完成 M1-03。A/B/C 的 9 题待专家答复，D 的 2 项范围问题已由用户
决定并停止外发。下一包是 M1-04 工程契约草案；之后准备 S-08/S-04/S-11 的 G0 fixture
manifests。M1 尚未完成，生产停止线不变。
