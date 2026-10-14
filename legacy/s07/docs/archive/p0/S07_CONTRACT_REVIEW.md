# S-07 `structure.fetch` 契约评审稿

> 当前范围覆盖：节点 01 内网决定已将 S-07 移出一期；本文全部内容为历史契约探索，OI-018
> 已转 `DEFERRED`，不得作为 P0 v0.7 生产输入或当前专家任务。

> 历史证据入口：[S-07 任务、交付与验收](S07_IMPLEMENTATION_TASKS.md)。本稿保留旧字段候选与
> 开发决定；专家已明确的来源顺序、BLAST→UniProt 用途、严格阈值和 partial 已在专项任务中采用。
> 下文旧 D11-D18 与 P0-M2 结论不能作为新的整包用户问卷或生产编码授权。

> 后续历史进展：任务 3/4 已完成 PDB 与 API 回退取证，共收敛出
> [5 项专家确认问题](S07_EXPERT_CONFIRMATIONS.md)。五项建议均已按用户决定作为暂行工程方案采用，
> 仍待专家确认；本稿其余旧问题只保留历史语境。任务 5 已完成，当前内部结果、错误、ArtifactRef
> 与追溯字段见[任务 5 契约及验证说明](S07_TASK5_RESULT_CONTRACT.md)；离线验证不等于生产冻结。

> 文档状态：`HISTORICAL_DRAFT / DEFERRED_OUT_OF_PHASE1`  
> 版本：v0.2-draft  
> 评审日期：2026-09-02  
> 当前开发评审人：wing（开发者）  
> 证据 campaign：P0-M1 `p0-s07-discovery-20260901-a`；P0-M1B 最终批次
> `p0-s07-m1b-20260901-d`  
> 部署状态：`NOT_DEPLOYED`

> 重基线说明：P0 当前范围见 [P0 范围重基线](../../../../project-history/p0-v07-plan/P0_SCOPE_REBASELINE.md)。本文保留真实输出证据与
> 工程模型，但 D03-D18 及原 P0-M2 进入结论必须先与专家 v10.5 文档逐项复核。

本文把 P0-M1 的真实输出事实转成 S-07 契约候选和待确认决定。它不是已冻结 Schema，不能作为
算法金标准、生产参数档案或 P0-M2 编码授权。当前没有修改 MCP、Mock、Dify DSL 或真实执行路径。
面向项目负责人汇报的简明状态、已确认决定和待协调事项见
[S-07 决策与待确认事项汇报](S07_DECISION_REPORT.md)。

## 1. 评审结论

当前 Mock 契约只有 `structure_found: bool` 和 `result=mock_structure/no_structure`，不足以表达
真实 S-07。P0-M1 已证明至少必须分开表达：

1. 检索是否完成，以及每个来源是有结果、空结果、未执行、无可验证标识，还是失败；
2. 搜索命中、结构候选、被选中的已有结构三种不同状态；
3. target↔entity 序列比对与 entity↔coordinates 坐标映射；
4. entry、entity、chain、model、assembly 与实际 ArtifactRef；
5. 原始检索事实、暂定命中语义与最终科学可用性决定；
6. 成功但没有合格已有结构，与 `ToolError` 的边界。

因此，不能把当前布尔契约直接替换成真实适配器。评审结果分为两包：

- **开发可确认包**：强类型层级、来源状态、ArtifactRef、双层映射、分页/去重、复合来源追溯、
  outcome/error 分离和后端枚举路由；
- **算法/产品确认包**：三类命中最终定义、阈值、链/model/assembly 选择、公共预测结构地位、
  来源优先级、AFDB accession 映射、BLAST 用途以及“可直接使用”的科学门槛。

开发可确认包即使全部通过，也不能单独解除 P0-M2 门禁；影响候选选择和路由的科学决定必须先
由相应负责人确认并进入版本化 profile。

## 2. 评审依据

- [P0 实施方案](../../../../project-history/p0/P0_IMPLEMENTATION_PLAN_v0.6_ARCHIVE.md)中的 P0-D01 至 P0-D07 和 S-07 暂定语义；
- [P0-M1 总结](../../../discovery/p0/s07/p0-s07-discovery-20260901-a/reports/P0_M1_SUMMARY.md)；
- [候选 manifest](../../../discovery/p0/s07/p0-s07-discovery-20260901-a/reports/candidate_structure_manifest.json)；
- [逐候选映射报告](../../../discovery/p0/s07/p0-s07-discovery-20260901-a/reports/sequence_mapping_report.json)；
- [能力缺口表](../../../discovery/p0/s07/p0-s07-discovery-20260901-a/reports/capability_gap_table.md)；
- [当前数据契约](../../../../full-t01-mock-v0.1/工作流设计/02-数据契约/T01_Dify节点-MCP工具映射与数据契约_v0.1.md)
  第 4 节与第 6.2 节；
- 当前实现中的 `StepRequest`、`StepResult`、`ArtifactRef`、`ToolError` 与 `Provenance`。

直接影响契约的实测事实：

| 事实 | 契约含义 |
|---|---|
| 1UBQ 为 76/76 exact entity 且坐标完整 | exact sequence 和完整坐标可以同时成立，但必须分别记录 |
| 6XRE entity 为 393/393 exact，chain M 坐标仅 314/393 | `TARGET_MATCH` 不等于技术可用，不得直接令布尔值为真 |
| 5XZC 只对应 target 92-356，坐标映射 232/393 | 必须保存 target↔entity 与 entity↔coordinates 两层映射 |
| 6PPV 为 62.5% 局部 identity，只对齐 72/133 target residues | 同源搜索结果不能冒充目标已有结构 |
| O15116 的 RCSB 查询为 HTTP 204，AFDB 返回 exact v6 model | 来源结果必须独立；HTTP 204 是成功空结果，不是故障 |
| RefSeq accession 被 AFDB API 以 HTTP 400 拒绝 | “没有可验证 AFDB ID”不同于“AFDB 中没有模型” |
| RCSB exact 查询可有 1136 个结果，P0-M1 初轮只取前 100 | 必须记录总数、完整性、截断、本地数据库发布和确定性去重 |
| P0-DISC-005 有 42 个弱 BLAST 命中，top e-value=3.4 | 有行不等于有合格结构；阈值不能从 discovery 参数继承 |

## 3. 当前契约与目标契约的差距

| 主题 | 当前 Mock | 评审候选 | 当前结论 |
|---|---|---|---|
| 输入 | 从通用运行输入隐式取得序列 | 显式、强类型的目标序列与可选 accession hint | 需更新 |
| 检索结果 | `structure_found` | 成功 outcome、selection 和逐来源状态 | 需替换布尔语义 |
| 候选层级 | 一个 `structure.json` | source→entry/model→entity→chain→model/assembly→artifact | 需新增 |
| 序列关系 | 无 | target↔entity alignment summary + 完整 mapping artifact | 需新增 |
| 坐标关系 | 无 | entity↔coordinate mapping summary + 完整 mapping artifact | 需新增 |
| 候选分类 | 无 | 三类暂定语义与独立的 eligibility decision | 科学定义待确认 |
| 来源状态 | 无 | RCSB、AFDB、BLAST 各自的 terminal status | 需新增 |
| 大结果集 | 无 | 有界摘要、总数、截断、cursor、candidate manifest 与本地数据库版本 | 需新增 |
| 追溯 | 单一工具 Provenance | facade Provenance + `source_runs` 复合追溯 | 需新增 |
| 无命中/故障 | 都可落成 false | 成功无合格结构与 ToolError 严格分开 | 需新增 |
| Dify 路由 | 对任意值 `bool(...)` | 后端校验固定 outcome 后输出固定 branch | 必须收紧 |

## 4. 输入契约候选

### 4.1 原则

1. `protein_sequence` 是唯一权威序列事实源，沿用已确认的 P0-D01。
2. `uniprot_accession` 只能是可选检索提示，必须回验序列，不能覆盖或修正用户序列，沿用
   P0-D02。
3. `host` 是宿主免疫/安全语境，不得解释为目标蛋白来源物种；`expression_host` 也不得用于
   S-07 来源消歧。
4. identity、coverage、e-value、来源优先级和候选上限只能来自后端批准的版本化
   `retrieval_profile_id`；LLM 和 Dify 不得拼装任意阈值对象。
5. 一个 `run_id` 必须唯一绑定一份不可变的 T-01 输入快照；S-07 的公开参数不重复接收第二份
   `protein_sequence`。控制面从输入快照构造强类型 `S07FetchInput`，适配器仍需校验和规范化
   取得的序列。规范化序列的 SHA-256 由后端计算，调用方提供的哈希不能成为权威事实。
6. `target_taxon_id` 是否进入正式输入仍未确认；当前不得从蛋白名称、host 或 LLM 推断。

### 4.2 建议的强类型参数形态

公开 MCP 调用的顶层 `run_id` 指向不可变输入快照，S-07 `parameters` 只接收由工作流或部署
配置固定的 profile 引用：

```json
{
  "retrieval_profile_id": "s07-production-profile-pending"
}
```

后端控制面解析 `run_id` 后，再构造内部强类型输入；以下只展示职责，不是冻结 Schema：

```json
{
  "input_snapshot_id": "...",
  "protein_sequence": "M...",
  "uniprot_accession": "O15116",
  "retrieval_profile_id": "s07-production-profile-pending"
}
```

| 字段 | 类型 | 必填 | 约束/行为 | 状态 |
|---|---|:---:|---|---|
| `run_id` | string | 是 | StepRequest 顶层字段；唯一绑定不可变 T-01 输入快照 | 2026-09-01 由 wing 确认 |
| `protein_sequence` | string | 内部必填 | 从输入快照取得，不在 S-07 参数中重复；规范化后作为全部查询、比对和回验的事实源 | 位置已确认；字符/长度策略待定 |
| `uniprot_accession` | string/null | 否 | 若以后启用，从同一输入快照取得；仅作 hint，不能覆盖序列 | 原则已确认；启用和冲突行为待定 |
| `retrieval_profile_id` | string | 是 | 由工作流/部署配置固定，必须引用服务端 allowlist 中的不可变 profile | 2026-09-01 由 wing 确认 |
| `target_taxon_id` | string/null | 否 | 若未来加入，只接受稳定 taxonomy ID | 产品/算法待确认，当前不启用 |

生产 Schema 还必须定义大小写、空白/FASTA header、20 个标准氨基酸之外的 B/O/U/X/Z、空序列、
最小/最大长度和 accession hint 与序列不一致时的确定性错误或 warning。当前
`[A-Za-z]+` 的 Mock 校验不能自动升级为生产规则。

## 5. 成功输出候选

### 5.1 顶层形态

建议保留通用 `StepResult` 外壳，并把 S-07 的强类型控制结果放入 `data`。完整原始数据通过
`ArtifactRef` 返回，不把几百或上千候选、完整 alignment 或原始检索输出内嵌进单次 MCP/API 响应。
这是后端可复现性和传输边界设计，不以 Dify 的限制为设计依据。

```json
{
  "contract_version": "s07.structure-fetch.v1-pending",
  "target": {
    "sequence_length": 133,
    "sequence_sha256": "...",
    "verified_uniprot_accession": null
  },
  "retrieval_outcome": "EXISTING_STRUCTURE_SELECTED",
  "selection": {
    "status": "SELECTED",
    "candidate_id": "...",
    "structure_artifact_id": "...",
    "selection_profile_id": "...",
    "reason_code": "..."
  },
  "source_runs": [],
  "candidate_page": {
    "items": [],
    "returned_count": 0,
    "total_discovered_count": 0,
    "capped": false,
    "complete": true,
    "stop_reason": "EXHAUSTED",
    "next_cursor": null
  },
  "candidate_manifest_artifact_id": "...",
  "sequence_mapping_report_artifact_id": "..."
}
```

字段名和枚举仍待确认，但顶层必须保留“结论、选择、来源执行、候选摘要、完整产物”五个分区。

### 5.2 `retrieval_outcome`

成功终态建议只允许两个互斥 outcome：

| 候选枚举 | 含义 | `StepResult.status` | 后续路由 |
|---|---|---|---|
| `EXISTING_STRUCTURE_SELECTED` | 后端依据已批准 profile 选出一个可直接进入后续结构分析的 structure artifact | `SUCCEEDED` 或经确认的 `DEGRADED` | S-09 |
| `NO_ELIGIBLE_EXISTING_STRUCTURE` | 规定的检索已完成，但没有候选满足“已有结构可直接使用”的批准规则 | `SUCCEEDED` | S-08 |

这里故意不使用 `NO_STRUCTURE`：P0-DISC-005 可以有弱同源 hit，6XRE 可以有 exact entity，仍可能
因最终规则得到“没有合格已有结构”。成功 outcome 也不能用于掩盖来源失败；如果所需来源未完成，
必须按第 10 节的状态/error 边界处理。

`selection.status` 建议只允许 `SELECTED` 或 `NONE`，且必须与 outcome 一致。不能同时返回
`NO_ELIGIBLE_EXISTING_STRUCTURE` 和非空 selected candidate。

## 6. 候选结构模型

### 6.1 标识与层级

一个候选至少包含以下层级；不能只保存 PDB ID 或一个下载 URL：

| 分区 | 代表字段 | 说明 |
|---|---|---|
| 通用标识 | `candidate_id`、`source`、`structure_kind` | 适配器生成的稳定 ID、来源与实验/公共预测类型 |
| RCSB entry | `entry_id`、method、resolution 等原生事实 | 不能把 entry 级质量事实复制成序列匹配事实 |
| polymer entity | `entity_id`、canonical sequence、accession refs | target sequence 首先与 entity 对齐 |
| chain instance | `label_asym_id`、`auth_asym_id` | 两种链 ID 都保存，不相互覆盖 |
| model | `model_id` | 多 model 文件必须明确选择或分别建模 |
| assembly | `assembly_id`/null | assembly 是独立选择，不得等同 chain |
| AFDB model | `afdb_entry_id`、`model_version` | 必须保存版本并回验序列 |
| artifact | 原始/规范化 mmCIF 的 ArtifactRef | candidate 不等于文件；文件还需语法、哈希与维度校验 |

RCSB 候选去重主键建议使用 `entry_id + entity_id + label_asym_id + model_id`，同时保留
`auth_asym_id` 供显示和与 BLAST subject ID 对照。assembly 选择未确认前不进入主键。AFDB 候选
使用 `afdb_entry_id + model_version`。最终键规则属于开发可确认项，不能反向决定科学优先级。

### 6.2 命中语义与可用性必须分开

每个候选至少保留：

- `hit_semantic`：当前仅允许暂定的 `TARGET_MATCH`、`TARGET_DERIVED`、
  `HOMOLOG_TEMPLATE`；
- `hit_semantic_policy_status`：当前固定为 `PROVISIONAL_DISCOVERY_POLICY`；
- `eligibility.status`：`ELIGIBLE`、`INELIGIBLE` 或 `UNDECIDED` 的候选；
- `eligibility.profile_id`、`reason_codes` 与实际比较事实。

弱 BLAST 行在算法阈值确认前只是 `search_hit`，不能为了塞进三类枚举而自动晋升为
`HOMOLOG_TEMPLATE`。`TARGET_MATCH` 也不能自动变成 `ELIGIBLE`：6XRE 已证明 exact entity 与
坐标完整性不同，实验方法、分辨率、缺口位置和 chain/assembly 规则仍可能阻止直接使用。

### 6.3 序列与坐标映射

候选摘要至少分成两个对象：

| 对象 | 最小事实 |
|---|---|
| `sequence_alignment` | 引擎/版本、identity、alignment length、query/subject range、aligned target count/fraction、mismatch/indel 概要、e-value/bitscore（若引擎提供） |
| `coordinate_mapping` | coordinate-mapped target count/fraction、mapped/unobserved/unaligned ranges、residue ID 体系、model 与 chain、mapping artifact ID |

这些字段不能互相代替。完整逐残基 alignment、target↔entity 与 entity↔coordinate 对照应进入
版本化 JSON artifact；通用 StepResult 的 `data` 只保留有界摘要和 artifact ID。

### 6.4 技术事实不在 S-07 生成质量档位

S-07 可以原样记录实验方法、分辨率、R-work/R-free、AFDB 原生 global metric、原生 confidence
artifact 是否存在等事实，但不得在本节点生成 S-09 的 high/medium/low，也不得把 PDB B-factor
无证据地解释为 pLDDT。

## 7. 逐来源执行状态

生产 S-07 在服务器上只查询本地、版本化的数据包和索引；P0-M1/P0-M1B 使用的 RCSB/AFDB
在线接口仅作为 discovery 取证来源，不进入生产查询路径。经 S07-D14/D16 最终批准的本地
RCSB、AFDB 和 BLAST 数据来源仍属于同一个 facade 下的不同 `source_run`。建议使用以下
terminal status：

| 枚举候选 | 含义 |
|---|---|
| `SUCCEEDED_WITH_RESULTS` | 调用和解析成功，得到原始结果；不表示结果科学可用 |
| `SUCCEEDED_EMPTY` | 本地查询和解析成功，结果为空；discovery 中的 RCSB HTTP 204 是该语义的证据 |
| `SKIPPED_BY_PROFILE` | 批准 profile 明确不执行该来源 |
| `SKIPPED_SHORT_CIRCUIT` | 该来源原本可执行，但前序来源已经满足批准的停止条件 |
| `SKIPPED_NO_VERIFIED_IDENTIFIER` | 该来源要求 accession，但没有可验证映射；不等于数据库无模型 |
| `FAILED_RETRYABLE` | worker、文件系统或其他本地运行条件暂时不可用 |
| `FAILED_PERMANENT` | 数据包缺失/损坏、版本不兼容、标识不受支持或其他确定性来源错误 |

每个 `source_run` 至少保存：source、adapter/tool 版本、本地数据库发布 ID/版本/哈希、profile ID、
query hash、开始/结束时间、exit code、result/returned/total count、`complete`、`capped`、
`stop_reason`、原始 artifact IDs 和 warning/error code。大清单可放进 source manifest artifact，
顶层只保留摘要。

来源记录还必须说明它是否在本次 profile 的查询计划中、是否实际执行，以及未执行原因。这里的
状态模型不要求每次运行全部来源；查询顺序、requiredness 和短路条件仍由 S07-D14/D16 确认。

RefSeq 不能直接查询 AFDB 的实测应表示为“没有经过验证的 AFDB identifier”或明确的 identifier
rejection，不能伪造 `SUCCEEDED_EMPTY`。如果未来引入 sequence→UniProt 映射服务，它本身也必须
成为可追溯 source run，并记录歧义候选和物种约束。

## 8. ArtifactRef 与复合追溯

S-07 预计至少产生以下 artifact 类型：

| artifact | 作用 |
|---|---|
| normalized target FASTA | 固定实际查询序列与哈希 |
| run/source manifest | 保存本地数据库、工具、profile、查询、完整性和停止原因 |
| canonical raw search output | 每个来源只保存一份规范的原始检索结果，不保存重复请求副本 |
| BLAST archive + tabular/JSON | 保存可重格式化原始检索与有界解析结果 |
| candidate manifest | 保存完整候选、来源 rank、去重与截断事实 |
| sequence mapping report | 保存逐候选双层残基映射 |
| selected original structure mmCIF | 保存最终采用的来源原文件；未选中结构默认引用本地数据库对象 |
| normalized structure mmCIF | 如需规范化，作为新 artifact，绝不覆盖原文件 |

每个 artifact 继续使用通用 `ArtifactRef`，不得在 `logical_name` 或 `resource_uri` 泄漏服务器本地
路径。结构文件的 `artifact_valid=true` 只说明文件经语法/哈希/维度校验，不说明它科学上
`ELIGIBLE`。

通用 `Provenance` 仍记录 facade：`adapter_name=structure.fetch` 适配器及其版本。因为一个
`Provenance` 无法表达多套 API/数据库，复合来源明细进入强类型 `source_runs` 与不可变 manifest
artifact。P0-M2 前需确认是扩展通用 Provenance 还是仅增加 S-07 专用模型；不能把多个来源版本
拼进一个自由文本字段。

## 9. 分页、去重、本地数据版本与文件分类

本节已由 wing（开发者）于 2026-09-02 根据 P0-M1B 真实输出确认。确认的是工程处理原则，不包括
S07-D11 至 D17 的科学筛选、排序和来源优先级。

### 9.1 分页与大结果集

1. S-07 后端自动读取本地查询引擎分批返回的全部轻量候选，直到结果集耗尽，或批准的 profile
   明确给出停止条件；调用方、LLM 和 Dify 不构造来源页码。
2. 每个来源必须记录报告总数、实际取得数、批次数、`complete`、`capped` 和 `stop_reason`。
   未完整取得必要来源时不得得出 `NO_ELIGIBLE_EXISTING_STRUCTURE`。
3. 先取得并整理轻量候选目录，再根据批准规则只为有限候选读取详细元数据和结构坐标；不得因为
   查询到 1136 个 entity 就复制 1136 份结构文件。
4. 通用结果只返回有界候选摘要和 ArtifactRef；完整候选保存在不可变 candidate manifest。
   `next_cursor` 只读取同一 run 的 candidate manifest，不重新查询本地数据库，也不接受调用方
   自行拼接 offset。
5. 单批大小、候选保护上限和提前停止条件进入版本化 profile。P0-M1/P0-M1B 使用的 `100` 只是
   discovery 参数，不是生产默认。

### 9.2 候选去重与文件去重

1. RCSB 候选按 source + entry + entity + chain + model 识别，不能只按 PDB ID 合并。assembly
   必须保留，是否形成独立候选仍由 S07-D13 决定；确认前不得隐式合并。
2. AFDB 候选至少按 accession/entry + model version 识别，并继续执行已确认的序列回验。
3. 同一候选如果通过多条检索路径发现，只建立一个规范候选，并把各发现路径、原始 rank/score
   和来源证据附在该候选下。BLAST subject 未验证映射到结构对象前只保留 search hit。
4. P0-M1B 没有观察到跨样本 entry/entity 重复；“跨来源发现同一候选”是正式工具必须防范的
   场景，不得写成已经发生的实测事实。
5. 文件内容按 SHA-256 去重，允许多个候选或记录引用同一物理对象；文件去重不得删除候选身份、
   发现路径或来源证据。

### 9.3 本地数据库版本代替在线查询快照

1. 生产 S-07 不查询在线数据库。经科学规则批准的来源以服务器本地、不可修改的版本化数据库包
   或索引提供；更新时创建新发布版本，不得覆盖旧版本。
2. 每次运行记录数据库发布 ID/版本/哈希、检索工具版本、profile 版本和 query hash。这里不建立
   P0-M1B 式的逐次 HTTP 请求/响应快照。
3. 本次 candidate manifest、选择结果、映射和最终结构 artifact 在运行完成后不可修改。重新执行
   查询形成新结果集，不覆盖或拼接旧结果。
4. 最终采用的原始结构单独进入 artifact store；即使后续清理旧数据库发布，仍能还原当时实际
   使用的结构。
5. 如果未来增加任何在线 fallback，必须重新评审来源状态、失败边界和在线快照策略，不能沿用
   本决定直接启用。

### 9.4 文件分类与保留边界

| 分类 | 内容与处理 |
|---|---|
| 运行说明 | 输入引用/序列哈希、数据库/工具/profile 版本、时间、状态；随运行结果保留 |
| 原始科学数据 | 每个来源一份规范原始检索结果、BLAST archive、最终采用的原始结构；只读保留 |
| 整理后的中间结果 | candidate manifest、去重关系、序列比对、坐标映射和规范化结构；版本化保留 |
| 最终结果 | outcome、selection、来源完整性、选中结构和关键 ArtifactRef；供下游默认读取 |
| 日志与临时文件 | 失败证据按运行策略保留；空 stdout/stderr、重复请求副本、下载残片和可重建缓存可清理 |

未选中的结构默认只引用本地数据库对象，不为每次运行重复复制。原始结构和规范化结构必须分开，
任何规范化都不得覆盖来源文件。同一内容只保存一个物理副本，但所有业务引用继续保留。日志保留
天数、数据库旧版本生命周期和其他 TTL 属于 S07-D18，不在 D09 中写死。

## 10. outcome、StepStatus 与 ToolError 边界

| 情形 | 来源状态 | StepStatus / ToolError 候选 | 是否允许当作“无合格结构” |
|---|---|---|:---:|
| 所有 profile 要求来源完成，但没有候选通过规则 | empty/results 均可 | `SUCCEEDED` + `NO_ELIGIBLE_EXISTING_STRUCTURE` | 是 |
| 本地来源查询成功但为空 | `SUCCEEDED_EMPTY` | 继续其他来源；本身无 ToolError | 否，需等所需来源完成 |
| 没有经过验证的 AFDB accession | `SKIPPED_NO_VERIFIED_IDENTIFIER` | warning 或 profile 决定的失败 | 否 |
| 本地 AFDB 数据包不支持给定标识 | `FAILED_PERMANENT` | 标准化 source error；整体行为由来源必需性决定 | 否 |
| worker 或文件系统暂时不可用 | `FAILED_RETRYABLE` | `TOOL_UNAVAILABLE`/`TIMEOUT`，保留 retryable | 否 |
| BLAST DB/taxdb 缺失或启动自检失败 | `FAILED_PERMANENT` | `TOOL_UNAVAILABLE` | 否 |
| 本地原始结果、mmCIF 或 mapping 无法解析 | `FAILED_PERMANENT` | `OUTPUT_INVALID` 或 `OUTPUT_MISSING` | 否 |
| artifact 哈希不一致 | `FAILED_PERMANENT` | `OUTPUT_INVALID` | 否 |
| 输入字符、长度或 profile ID 非法 | 未调用来源 | `FAILED` + `INPUT_VALIDATION` | 否 |
| 用户取消 | 依 OI-017 | `CANCELLED` + `CANCELLED` | 否 |
| deadline 到期 | 未完成来源按失败记录 | `FAILED` + `TIMEOUT` | 否 |

部分来源失败而其他来源选出了候选时，整体使用 `DEGRADED` 还是直接 `FAILED`，取决于
source-requiredness profile。该策略目前未确认；不得默认“至少一个来源成功就算完整成功”。

错误 `details` 中可以放 source、exit code、attempt、database release 和 artifact ID，但不得
包含密钥、完整敏感输出或服务器路径。面向用户的 `user_message` 不能把工具/数据库失败解释成
科学无命中。

## 11. 后端路由契约

`t01.route_existing_structure` 应是纯后端校验器，不再对任意值执行 `bool(...)`。候选规则如下：

```text
StepResult FAILED/CANCELLED
  -> 停止当前阶段，不调用 route_existing_structure

retrieval_outcome == EXISTING_STRUCTURE_SELECTED
  + selection.status == SELECTED
  + selected structure ArtifactRef 存在且校验通过
  -> branch_taken=HAS_EXISTING_STRUCTURE, route=S-09

retrieval_outcome == NO_ELIGIBLE_EXISTING_STRUCTURE
  + selection.status == NONE
  -> branch_taken=NEEDS_STRUCTURE_PREDICTION, route=S-08
```

Dify 只按后端返回的固定 `branch_taken` 路由，不解析 identity、coverage、method、resolution 或
候选来源。`TARGET_DERIVED`、`HOMOLOG_TEMPLATE` 在当前暂定 policy 下仍进入 S-08；
`TARGET_MATCH` 只有通过尚待确认的 eligibility profile 才能进入 S-09。AFDB exact model 是否
视为“已有结构”也必须由 profile 明确，不能按 `source == ALPHAFOLD_DB` 在 Dify 中硬编码。

## 12. 待确认决定清单

状态说明：`CONFIRMED` 继承现有 P0 决定；`READY_FOR_DEV_CONFIRMATION` 是本评审提出的工程决定，
尚未代表 wing 已确认；`EVIDENCE_READY_FOR_REVIEW` 表示指定实测证据已经取得、但 wing 尚未作出
最终开发决定；`BLOCKED_*` 表示开发角色不得代替相应负责人决定。

| ID | 决定 | 建议/待回答内容 | 状态 | 确认角色 |
|---|---|---|---|---|
| S07-D01 | 权威序列 | `protein_sequence` 是唯一序列事实源 | `CONFIRMED` | 已由 wing 确认 P0-D01 |
| S07-D02 | accession 地位 | 可选 hint，必须回验，不能覆盖序列 | `CONFIRMED` | 已由 wing 确认 P0-D02 |
| S07-D03 | 输入模型 | `run_id` 唯一绑定不可变输入快照；控制面构造强类型输入；S-07 不重复接收序列；profile 由工作流/部署固定且只能引用服务端 allowlist | `CONFIRMED` | wing（开发者），2026-09-01 |
| S07-D04 | 候选层级 | 候选必须保留 source/entry/entity/chain/model/assembly/artifact，链同时保存 label/auth ID；不能只用 PDB ID 表示 | `CONFIRMED` | wing（开发者），2026-09-01 |
| S07-D05 | 双层映射 | sequence alignment 与 coordinate mapping 必须分开；完整逐残基结果进入 artifact，主结果只保留摘要 | `CONFIRMED` | wing（开发者），2026-09-01 |
| S07-D06 | 成功 outcome | 使用“选中合格已有结构/没有合格已有结构”，不再用 bool 表示是否搜到结果；候选事实与最终 selection 分开 | `CONFIRMED` | wing（开发者），2026-09-01 |
| S07-D07 | 来源状态 | 逐来源记录是否计划、是否执行、结果及未执行原因；空结果、profile 关闭、短路、无 verified ID 和失败分开；不表示所有来源必查 | `CONFIRMED` | wing（开发者），2026-09-01 |
| S07-D08 | 产物与追溯 | 完整科学产物由后端可靠保存；通用接口返回结构化结果和 ArtifactRef；facade provenance + source_runs；不因 Dify 兼容性削弱后端契约 | `CONFIRMED` | wing（开发者），2026-09-01 |
| S07-D09 | 分页/去重/本地数据版本/文件分类 | 自动取完轻量结果、重文件按需；候选与文件分层去重；生产只用不可变本地数据库发布；五类文件及保留边界按第 9 节执行 | `CONFIRMED` | wing（开发者），2026-09-02 |
| S07-D10 | 错误边界 | 只有必要来源完成且评估完成后才能返回成功无合格结构；故障不得伪装空结果 | `CONFIRMED` | wing（开发者），2026-09-01 |
| S07-D11 | 命中最终语义 | 三类定义、identity/coverage/e-value、突变/标签/截短归类 | `BLOCKED_ALGORITHM` | 算法负责人 |
| S07-D12 | 已有结构 eligibility | 最低坐标覆盖、允许缺口、关键区域、method/resolution 规则 | `BLOCKED_ALGORITHM` | 算法负责人 |
| S07-D13 | 结构选择 | chain/model/assembly 选择、多链/多模型和 alternate location | `BLOCKED_ALGORITHM` | 算法负责人 |
| S07-D14 | 来源优先级 | RCSB/AFDB/BLAST 的 requiredness、优先级、部分失败与公共预测结构地位 | `BLOCKED_ALGORITHM` | 算法负责人 |
| S07-D15 | AFDB 映射 | sequence→UniProt 服务、taxon 约束、歧义与 accession mismatch | `BLOCKED_PRODUCT_ALGORITHM` | 产品 + 算法负责人 |
| S07-D16 | BLAST profile | C6 数据库、阈值、用途、与 RCSB MMseqs2 的去重和排序 | `BLOCKED_ALGORITHM` | 算法负责人 |
| S07-D17 | 序列边界 | B/O/U/X/Z、最大长度、非标准残基和非法 FASTA 的行为 | `BLOCKED_ALGORITHM_DEV` | 算法 + 开发负责人 |
| S07-D18 | execution profile | 同步/异步、deadline、重试、并发、缓存 TTL 和结果保留 | `MEASUREMENT_AND_DEV_CONFIRMATION_REQUIRED` | 开发 + 运维；时长来自实测 |

### 12.1 S07-D03 确认记录

- 具名确认人及角色：wing（开发者）。
- 确认日期：2026-09-01。
- 决定：一个 `run_id` 唯一绑定一份不可变 T-01 输入快照，其中只有一条权威
  `protein_sequence`；相同序列可以出现在不同 run 中。S-07 不在参数中重复接收序列，后端控制面
  从快照构造强类型输入。`retrieval_profile_id` 由工作流或部署配置固定并受服务端 allowlist
  约束，用户与 LLM 不得传入任意科学参数。
- 未在本决定中确认：accession hint 的启用/冲突行为、target taxon、特殊氨基酸与长度规则。

### 12.2 S07-D04 确认记录

- 具名确认人及角色：wing（开发者）。
- 确认日期：2026-09-01。
- 决定：结构候选不能只用 PDB ID 表示；必须保存来源、entry、polymer entity、具体 chain、
  model、assembly 元数据和实际结构 ArtifactRef。链同时保留 `label_asym_id` 与 `auth_asym_id`，
  避免不同来源的链标识无法对照。候选必须能够唯一定位实际结构对象，不能因条目级合并造成
  信息丢失或使用错误结构。
- 未在本决定中确认：最终选择哪条 chain、哪个 model/assembly，以及相应科学优先级；这些仍由
  S07-D13 的算法规则决定。

### 12.3 S07-D05 确认记录

- 具名确认人及角色：wing（开发者）。
- 确认日期：2026-09-01。
- 决定：目标序列到结构 entity 的 sequence alignment，与 entity residue 到具体 chain/model
  坐标的 coordinate mapping 必须分别建模，不能合并为一个覆盖率。完整逐残基对应关系进入
  版本化 artifact，主结果只保留 identity、对齐/坐标覆盖数量与比例、范围和缺失区段摘要。
- 原因：序列完全匹配仍可能缺少坐标；若合并两层映射，后续结构计算会把没有坐标的残基误当成
  可计算残基。
- 未在本决定中确认：最低 identity、序列覆盖、坐标覆盖和允许缺口规则；这些仍由 S07-D11、
  S07-D12 的算法决定。

### 12.4 S07-D06 确认记录

- 具名确认人及角色：wing（开发者）。
- 确认日期：2026-09-01。
- 决定：生产契约删除 `structure_found` 的科学/路由语义。成功终态使用
  `EXISTING_STRUCTURE_SELECTED` 或 `NO_ELIGIBLE_EXISTING_STRUCTURE`；前者必须有一致的
  selected candidate 与结构 ArtifactRef，后者必须没有 selected candidate。搜索命中和候选列表
  独立保存，不能因为“有返回行”就判定已有结构可用。
- 路由：选出合格已有结构进入 S-09；检索正常完成但没有合格已有结构进入 S-08。来源未完成或
  工具故障不得伪装成后一种成功 outcome。
- 未在本决定中确认：候选满足何种科学条件才算 `ELIGIBLE`；由 S07-D11 至 S07-D16 决定。

### 12.5 S07-D07 确认记录

- 具名确认人及角色：wing（开发者）。
- 确认日期：2026-09-01。
- 决定：每个已知检索来源必须如实记录是否属于本次查询计划、是否实际执行、执行结果或未执行
  原因。成功有结果、成功空结果、profile 关闭、前序命中后短路、缺少 verified identifier、
  可重试失败和永久失败必须语义分离；精确枚举拼写在 Schema 冻结时统一。
- 边界：本决定不要求 RCSB、AlphaFold DB、BLAST 每次全部执行，也不决定它们的先后顺序。
  source-requiredness、短路条件和 BLAST 地位仍由 S07-D14/D16 的算法规则确认。

### 12.6 S07-D08 确认记录

- 具名确认人及角色：wing（开发者）。
- 确认日期：2026-09-01。
- 决定：完整查询响应、候选清单、BLAST 原始结果、逐残基映射和结构文件由后端可靠保存并生成
  ArtifactRef；通用 MCP/API 只返回强类型控制结果、必要摘要和产物引用。产物必须记录类型、
  大小、SHA-256 与来源，不暴露服务器本地路径。
- 架构边界：科学工具和后端契约必须保持调用方中立。Dify 只在 P0 工具包完成后用于集成验证与
  编排；若 Dify 对数据形态或大小存在限制，应增加单独的 Dify projection/adapter，不得修改或
  削弱后端权威结果、科学产物和通用契约。

### 12.7 S07-D09 取证与确认记录

- 具名决定人及角色：wing（开发者）。
- 原取证决定日期：2026-09-01；最终确认日期：2026-09-02。
- 原暂缓决定：不凭文档和估计确认分页、去重、快照与 artifact type，先运行独立的非生产候选
  工具。该工具不得接入 MCP/Dify、标记 `DEPLOYED`、形成生产路由或用于科研结论。
- 取证结果：P0-M1B 最终批次 `p0-s07-m1b-20260901-d` 已完成 57 次来源调用，执行失败为 0；
  审计清单统计 285 个非报告文件、23 类文件，合计约 11.5 MiB。RCSB 5 个查询共 19 页，三个
  有结果的查询完整取得 1136、236、125 个 entity，对应 1004、235、103 个 entry；两个空结果
  均明确保存为 HTTP 204。
- 产物事实：4 个 RCSB 观察对象各产生 entry/entity/chain/mmCIF；两个合法 AFDB accession 各产生
  metadata/CIF/confidence/PAE；4 个 BLAST 样本均产生 archive/TSV/JSON。前三个 BLAST 样本达到
  discovery profile 的 100 条上限，不能据此批准生产上限。
- 重复事实：19 组非空字节重复均为分页请求原件与 exchange 请求副本。entity 与 entry 也存在
  明确的多对一关系；业务对象去重不能用文件哈希或单一 PDB ID 代替。
- 证据入口：[P0-M1B 执行记录](S07_M1B_RUN_RECORD.md)、
  [最终输出审计](../../../discovery/p0/s07/p0-s07-m1b-20260901-d/reports/P0_M1B_OUTPUT_AUDIT.md)和
  [机器可读摘要](../../../discovery/p0/s07/p0-s07-m1b-20260901-d/reports/output_audit.json)。
- 最终决定：后端自动取得完整轻量候选，重型结构按批准规则按需读取；主结果有界，完整候选进入
  candidate manifest；候选身份与文件内容分别去重，多条发现路径不丢失。
- 数据部署决定：生产只查询服务器本地、不可修改的版本化数据库包/索引；每次运行记录数据库、
  工具、profile 和 query 版本/哈希，不保存逐次在线请求快照。在线 fallback 若未来启用必须重审。
- 文件决定：运行说明、原始科学数据、整理中间结果、最终结果、日志/临时文件五类分开管理；保留
  能解释查询、候选、选择和最终使用结构的证据，清理空日志、重复副本、残片和可重建缓存。
- 未在 D09 确认：科学筛选/排序、assembly 选择、来源 requiredness、具体页大小/候选上限、日志
  保留天数和数据库生命周期；分别由 S07-D11 至 D18 承接。

### 12.8 S07-D10 确认记录

- 具名确认人及角色：wing（开发者）。
- 确认日期：2026-09-01。
- 决定：只有版本化 profile 标记为必要的来源均到达可判定终态、候选评估已经完成，并且确实没有
  合格候选时，整体才能返回 `SUCCEEDED + NO_ELIGIBLE_EXISTING_STRUCTURE` 并进入 S-08。
- 错误边界：输入非法、必要来源超时或失败、输出缺失/损坏以及任务取消必须形成明确的
  StepStatus/ToolError，不得伪装为“无合格结构”，也不得进入 S-08。
- 部分失败：是否允许 `DEGRADED` 以及此时能否形成科学 outcome，只能依据版本化
  source-requiredness profile；S07-D10 不决定哪些来源必要，该内容仍由 S07-D14/D16 确认。
- 编排边界：Dify 只消费后端已经校验的终态和路由，不根据空数组、null 或异常文本自行推断。

## 13. 评审包与建议确认顺序

### 13.1 先由 wing 确认的开发包

S07-D03 至 S07-D10 已全部由 wing 确认。开发确认只代表同意契约结构、分页/去重、本地数据版本、
文件边界和错误边界，不代表科学阈值或来源优先级已经批准。

已确认的开发边界包括：删除生产语义中的 `structure_found`，改为 outcome + selection；保留候选
层级、双层 mapping、逐来源状态和有界 data/ArtifactRef；由后端 route 工具校验枚举，Dify 不做
科学判断。OI-018 仍保持 `IN_REVIEW`，直到科学包和最终实施输入共同完成。

### 13.2 再交算法/产品负责人的科学包

至少提供 1UBQ、6XRE、5XZC、6PPV、AFDB O15116 和 P0-DISC-005 六类证据，并逐项确认
S07-D11 至 S07-D17。不能只询问“这三个类别是否可以”，还必须取得可编码、可测试的阈值、
缺口规则、选择顺序和无结果边界。

### 13.3 最后冻结实施输入

科学决定形成后，开发/运维完成 S07-D18，并共同冻结：

1. S-07 request/result JSON Schema 与版本迁移规则；
2. retrieval parameter profile 与 source-requiredness profile；
3. execution profile；
4. artifact type 注册表、source provenance、本地数据库发布和缓存策略；
5. outcome/ToolError 枚举、路由契约及正常/边界/故障 fixtures。

## 14. P0-M2 进入结论

当前结论：`BLOCKED_BY_ROLE_CONFIRMATION`。

已经完成的只是基于真实输出形成评审稿；尚未满足以下 P0-M2 进入条件：

- 算法/产品负责人尚未确认 S07-D11 至 S07-D17；
- 尚未形成不可变 parameter/execution profile；
- 当前数据契约、Pydantic Schema、Mock 兼容策略和 Dify 路由尚未按冻结决定更新。

因此下一动作应是把科学包交给相应负责人，取得 D11-D17 的可编码反馈，再结合实测完成 D18 和
最终实施输入冻结。此前不写生产适配器，不修改 P0 工作流，不把 discovery 参数升级为 production
默认，也不把任何真实工具标记为 `DEPLOYED`。
