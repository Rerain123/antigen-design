# P0 科学工具实施方案 v0.7（甲方内网输入版）

> 版本：v0.7  
> 日期：2026-09-03  
> 文档状态：`CURRENT_PLAN / ENGINEERING_REVIEW_PASS_WITH_BLOCKING_GATES`  
> 生产状态：`PRODUCTION_ENTRY_BLOCKED / NOT_DEPLOYED`  
> 当前下一包：`P0-V07-M1` 甲方输入契约归并  
> 工程评审：[v0.7 评审记录](P0_V07_M0_REVIEW.md)

## 1. 本次改版结论

用户根据甲方只有内网、不能联网搜索的部署条件，决定：

1. 节点 01 删除 RCSB PDB 与 AlphaFold DB 搜索；
2. 节点 01 的科学工具只保留 AlphaFold3 与 ESMFold2；
3. 内网限制只影响外部数据库查询，不影响部署在甲方服务器上的 AlphaFold3/ESMFold2；
4. 工作流输入为目标蛋白序列、宿主物种和可选结构；
5. 不允许通过其他名字、辅助步骤或 fallback 恢复联网结构检索。

因此，v0.6 的 S-07 自动已有结构检索链不再属于一期 P0。v0.7 的当前完整 P0 为：

```text
目标蛋白序列 + 宿主物种 + 结构（可选）
  -> 输入校验与可选结构解析
  -> 是否提供且可解析的结构？
       ├─ 是：直接形成结构事实
       └─ 否：S-08 AlphaFold3 / ESMFold2 结构预测
  -> S-09 结构质量确定性评估
  -> S-04 DeepTMHMM 拓扑预测
  -> 结构质量非 low 且 R-58 通过时 S-11 FreeSASA
  -> P0EvidenceBundle
```

S-11 仍是一期第 3 裁剪项，但当前没有触发削减，默认完整 profile 继续包含 S-11。

## 2. 权威依据与适用顺序

| 依据 | 用途 |
|---|---|
| [一期 18 节点范围重基线](../project/PHASE1_SCOPE_WITH_P0_MAPPING_20260903.md) | 决定一期 18 节点、排除项、优先级、裁剪顺序和节点 01 内网修订 |
| [节点 01 会议决定来源记录](../../../docs/project/sources/PHASE1_NODE01_OFFLINE_SOURCE_20260903.json) | 固定会议截图、哈希、显式决定与后续输入澄清 |
| [P0 范围重基线](P0_SCOPE_REBASELINE.md) | 决定当前 P0 四步骤边界及历史范围迁移 |
| [当前四步骤专家依据对照](P0_EXPERT_EVIDENCE_MATRIX.md) | 复用 S-08/S-09/S-04/S-11 的科学依据；S-07 内容转历史 |
| [Agent A v10.5 当前包](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902) | 保留步骤的 SOP、Schema 与 ToolSpec |
| [开放项清单](../../../docs/project/OPEN_ITEMS.md) | 管理 OI-015、017、020、023 等门禁 |

适用顺序：最新用户范围决定先判断“是否属于一期”；保留步骤再按专家资料核对科学规则。旧
v0.6、S-07 discovery 或 Mock 行为不能覆盖当前范围，也不能反向冻结生产 Schema。

## 3. 当前范围

### 3.1 纳入 P0 的步骤

| 顺序 | 步骤 | 生产角色 | 当前状态 |
|---:|---|---|---|
| 入口 | 甲方输入接收与校验 | 必填 `protein_sequence`、`host_species`，可选本地 `structure`；验证格式、哈希、来源和可审计性 | OI-023 `IN_REVIEW` |
| 1 | S-08 `predict_structure` | 未提供合法结构时，使用甲方服务器上的 AlphaFold3/ESMFold2 预测 | `G0_NOT_STARTED` |
| 2 | S-09 `assess_structure_quality` | 对甲方提供结构或 S-08 预测结构计算质量、可靠性和掩码 | Q08/Q09 `DECISION_REQUIRED` |
| 3 | S-04 `predict_topology` | 使用 DeepTMHMM 形成拓扑事实和原生标签证据 | `G0_NOT_STARTED` |
| 4 | S-11 `compute_rsa` | 在质量与 R-58 门禁后使用 FreeSASA 计算 RSA | OI-015 `BLOCKED`；G0 未开始 |
| 出口 | P0EvidenceBundle | 汇总事实、状态、产物引用、缺失原因和追溯 | `REVIEW_DRAFT_REQUIRED` |

S-09 和入口校验属于后端确定性逻辑，不虚构成外部科学工具。AlphaFold3/ESMFold2、DeepTMHMM、
FreeSASA 是当前完整 P0 的科学工具集合。

### 3.2 明确排除

- S-07 自动已有结构检索；
- RCSB PDB、AlphaFold DB 的查询、下载和联网解析；
- 为 S-07 服务的 BLAST→UniProt→AFDB accession fallback；
- 自动把 accession、名称或自由文本解析成远程结构；
- S-06/PSORTb；
- 任何通过 Dify HTTP、LLM、MCP adapter 或运维脚本绕过内网边界的联网 fallback。

这些能力即使仍存在于 v0.1 Mock、旧数据契约或 discovery 中，也只作历史回归/证据，不进入
一期 release bundle、生产 Workflow、部署清单或完成统计。

## 4. 甲方输入基线与专家依据归并

### 4.1 已明确

- 必填输入为 `protein_sequence`（目标蛋白序列）和 `host_species`（宿主物种）；`structure` 为可选。
- 有合法结构时按输入结构进入 S-09；没有结构时在甲方服务器运行 AlphaFold3/ESMFold2，再进入 S-09。
- 内网限制只删除外部数据库查询；不限制本地部署的 AlphaFold3/ESMFold2 正常使用。
- 系统不通过互联网补齐结构、accession 或其他缺失数据。
- 输入内容必须在调用科学工具前完成确定性校验和哈希。
- LLM 只负责收集/转交甲方明确提供的值，不生成、修复或推断序列、结构和元数据。
- 输入缺失或非法时必须返回稳定错误，不得自动联网、静默替换或使用历史缓存冒充本次输入。

### 4.2 专家文档已经给出的口径

| 项目 | 已有依据 | v0.7 使用方式 |
|---|---|---|
| 目标序列 | 一期图写“目标蛋白序列”；T-01 SOP 输入为“蛋白序列”；Schema 字段为 `protein_sequence: string` | 作为唯一权威序列事实源，必填并保存规范值与 SHA-256 |
| 宿主物种 | 一期图/T-01 SOP 明确“宿主”；Schema 字段为 `host_species: string`，说明可用学名/通用名 | 当前请求规范字段固定为 `host_species`；旧 `host` 只作迁移别名，不产生第二份事实 |
| 可选结构 | 用户最新确认结构可选；S-07c 与结构链 ToolSpec 已定义本地结构文件摄取 | 作为可选本地输入；不得把 PDB ID、URL 或 accession 当结构文件并联网解析 |
| 结构格式 | S-07c 明确 `file_path(PDB/CIF/mmCIF)`，检测格式并解析，原格式保留 | 接受 PDB、CIF、mmCIF；传输层使用 ArtifactRef，内部解析层再绑定受控路径 |
| chain | S-07c：可选，默认 auto；自动取第一条 protein chain，排除 DNA/RNA/ligand，多蛋白链告警 | 迁入输入解析规则；后续结构工具前仍执行 R-58 一致性校验 |
| 结构异常 | 格式无法解析→`failure_report`；原子缺失比例 >20%→WARNING | 形成稳定错误/警告用例，不改写为正常结构 |
| 原格式与转换 | mmCIF 保持 mmCIF、PDB 保持 PDB；仅下游工具确需 PDB 时内部转换 | 原件作为不可变 Artifact；转换产物另建引用和哈希 |
| 序列—结构映射 | R-58 规定输入序列比对、多链、缺失残基和 insertion code 处理 | 结构依赖步骤消费前强制执行，不由 LLM/Dify 判断 |

一期图另有设计目标、表达宿主等可选顶层输入，但它们不改变 P0 的结构入口必填集合；按消费阶段
再进入相应契约，不能为了 P0 强制甲方补填。

### 4.3 OI-023 当前工作性质

OI-023 已从“等待甲方/用户定义输入”改为 `IN_REVIEW`：工程侧负责把上述分散原文归并为统一
`P0InputBundle`、字段映射、校验表和 fixtures。以下仅是需要在归并中核对的具体文档问题：

1. 旧请求字段 `host` 与专家 Schema `host_species` 的迁移方式；
2. CandidateRecord 要求的 `organism` 是下游输出字段，不得误升为本次 P0 用户必填项；
3. 外部 `structure`、解析参数 `file_path` 与内部输出 `structure.pdb_path` 的层级映射；
4. 专家原文只规定非法序列失败，但未完整列出非标准残基允许表，需要结合 AF3/ESMFold2/DeepTMHMM
   实际支持范围形成定点算法复核材料；
5. API 上传、对象存储或受控目录属于后端/运维实现选择，采用 ArtifactRef 抽象，不作为科学问题回问用户。

一致条款直接落契约；只有原件间出现会改变科学结果的真实冲突或确实缺失时，才带出处、影响和
建议提交相应专家，不再向用户发送宽泛字段问卷。

## 5. 组件职责

| 组件 | 允许职责 | 禁止职责 |
|---|---|---|
| 甲方输入方 | 提供目标蛋白序列、宿主物种和可选本地结构 | 只给 accession、URL 或数据库名称并要求系统联网补齐 |
| LLM | 收集、提示缺失、发起工具调用、解释后端事实 | 改写序列、推断结构、判断阈值、选择候选 |
| Dify | 编排、按固定状态路由、展示输入缺失和任务进度 | HTTP 联网检索、科学计算、用自由文本决定降级 |
| MCP/后端 | Schema 校验、哈希、幂等、状态、门控、ArtifactRef、错误和审计 | 隐式联网、把旧 S-07 cache 当当前输入 |
| Worker | 固定版本运行 AF3/ESMFold2、DeepTMHMM、FreeSASA | 接收任意命令或未校验路径 |
| 运维/接收方 | 在甲方内网部署版本化镜像、模型、依赖和存储 | 运行时临时从互联网下载模型或数据库 |

## 6. P0 共同契约草案边界

v0.7 的正式 Schema 在 G1 前不得定稿，但 M1 必须覆盖以下稳定概念：

### 6.1 `P0InputBundle`

- `input_id`、`run_id`、`request_id`；
- 必填 `protein_sequence`、`host_species` 及内容 SHA-256；
- 可选 `structure` ArtifactRef、格式、chain 提示、原始文件 SHA-256 和提供方来源；
- 甲方提供的其他可选业务元数据及逐字段来源；
- `input_contract_version`、提交批次、提供方、时间和替换关系；
- `execution_mode`，生产路径不得接受 `mock` 结果作为科学输入。

### 6.2 步骤结果

每步至少区分：

- `SUCCEEDED`：产物完整且通过本步确定性结构校验；
- `SKIPPED_BY_RULE`：由已冻结规则跳过，并带原因码；
- `REQUIRES_REVIEW`：事实可用但禁止自动向下游交接；
- `FAILED_RETRYABLE` / `FAILED_TERMINAL`：稳定错误类别；
- `NOT_RUN`：因上游停止或 profile 排除而未执行。

状态名称仍是工程草案，M1/G1 需与现有 `StepResult`、任务 5 契约和 OI-017 对照后冻结。Dify
只能消费后端固定枚举，不能从日志文本推断科学状态。

### 6.3 `ArtifactRef` 与追溯

- 输入、原始工具输出、解析结果、结构文件、掩码、拓扑、RSA 和报告均使用内容哈希引用；
- 不向 Dify/LLM 泄漏服务器绝对路径；
- 记录工具/镜像/模型/参数、硬件、随机种子、时间、退出码和父子产物关系；
- 相同 `run_id` 不覆盖旧失败或旧结果；重试必须形成新 attempt 并可追溯前次状态。

## 7. 四步骤实施要求

### 7.1 S-08：AlphaFold3 / ESMFold2

- 仅在未提供合法结构时执行；内网条件不构成禁用，两种模型部署在甲方服务器后正常运行；
- G0 固定实际可在甲方内网部署的版本、镜像、模型权重、许可证与硬件；
- 保存原始 ranking、pLDDT/pTM、结构文件、日志、耗时和资源曲线；
- 用正常、长序列、非法输入、OOM、超时、缺指标、转换失败和重试样本取证；
- AF3/ESMFold2 的选择、fallback、长度和超时条件必须来自专家规则与 G0 事实，不自行补默认值；
- 两个工具均不得在运行时访问公网下载权重、模板或数据库。

### 7.2 S-09：质量评估

- 只消费 S-08 的可追溯原始事实，不调用网络或 LLM；
- Q08/Q09 必须形成覆盖 method/source、pLDDT/pTM、缺失/NaN/越界、0.50/0.70 边界和掩码的
  无重叠决策表；
- 输出 `confidence`、`topology_reliable`、掩码和告警的机器字段及规则版本；
- 未冻结的边界不得用现有 Mock 行为替代。

### 7.3 S-04：DeepTMHMM

- G0 固定版本、模型、许可、CPU/GPU、原生标签和输出文件；
- 保留 P/B 原生标签 ArtifactRef，并确定性投影到当前四标签 Schema；
- 测试标签/序列不等长、空输出、非法字符、模型失败及 P/B 降级；
- S-04 结果不由 S-09 的 `topology_reliable` 替代。

### 7.4 S-11：FreeSASA

- 当前完整 profile 保留；结构质量 `low` 时按既有规则跳过并给出显式原因；
- OI-015 先冻结 R-58 的序列—结构比对、链/model/assembly、缺口、插入码、覆盖和复核规则；
- G0 固定 FreeSASA 版本、算法、探针、半径集、复合物/链范围和非标准原子处理；
- 输出逐残基 RSA、聚合事实、映射报告、原始 SASA 产物和参数档案；
- OI-020 未关闭前不得启用无 S-11 的缩减 profile。

## 8. G0～G6 阶段门禁

| 门禁 | v0.7 退出条件 |
|---|---|
| G0 | AF3/ESMFold2、DeepTMHMM、FreeSASA 的冻结候选版本在隔离内网等价环境完成原始取证；S-09 规则样本准备完成 |
| G1 | OI-023、Q08/Q09、OI-015 等直接依赖形成具名决定；输入、状态、错误、ArtifactRef、P0EvidenceBundle 与 execution profile 冻结 |
| G2 | OI-017 生产状态机和四步骤适配器实现，所有网络检索入口在生产 profile 中不可达 |
| G3 | 形成可离线安装、可复现、可回滚的 P0 release bundle；模型、镜像、参数、许可和金标准齐全 |
| G4 | 只修改生成源，形成 v0.7 P0 Workflow；移除生产 S-07 分支，旧 Mock v0.1 保留 |
| G5 | 工具、契约、Dify、故障、取消、恢复和内网断网测试使用新唯一批次全部通过 |
| G6 | 状态、运行手册、release manifest 和基线同步；确认无 RCSB/AFDB/S-07 生产调用后标记 `FROZEN` |

G0 只形成 discovery 事实；G1 前不得生产编码，G3 前不得标记 `DEPLOYED`，G6 前不得开始 P1。

## 9. v0.7 里程碑

| 里程碑 | 内容 | 当前状态 |
|---|---|---|
| `P0-V07-M0` | 节点 01 内网范围重基线、v0.6 归档、计划重写与工程评审 | `COMPLETED` |
| `P0-V07-M1` | 从专家资料归并目标序列、宿主物种、可选结构及工程校验/追溯契约；关闭 OI-023 | `READY_NEXT` |
| `P0-V07-M2` | AlphaFold3/ESMFold2 内网 G0、路由/失败 profile 与冻结样本 | `BLOCKED_BY_M1` |
| `P0-V07-M3` | S-09 Q08/Q09 决策表、质量/掩码实现前验证 | `DECISION_MATERIAL_READY` |
| `P0-V07-M4` | DeepTMHMM G0、P/B ArtifactRef 和四标签契约 | `NOT_STARTED` |
| `P0-V07-M5` | OI-015/R-58 决定与 FreeSASA G0 | `BLOCKED_BY_OI_015` |
| `P0-V07-M6` | 汇总四步骤输入/状态/错误/ArtifactRef/P0EvidenceBundle，达到 G1 | `BLOCKED_BY_M1_TO_M5` |
| `P0-V07-M7` | 实现 OI-017 状态机、AwaitJob、取消、恢复和逐工具 execution profile | `BLOCKED_BY_G1` |
| `P0-V07-M8` | 实现 AF3/ESMFold2、S-09、DeepTMHMM、FreeSASA 生产适配器与单测 | `BLOCKED_BY_M7` |
| `P0-V07-M9` | 离线 release bundle、预检、安装、金标准、许可、资源与回滚 | `BLOCKED_BY_M8` |
| `P0-V07-M10` | 生成、绑定、导入并发布 P0 v0.7 Workflow；旧 Mock 不覆盖 | `BLOCKED_BY_M9` |
| `P0-V07-M11` | P0 独立与受影响 Master 回归、断网验证、失败/恢复验收 | `BLOCKED_BY_M10` |
| `P0-V07-M12` | 文档、运行手册、基线和 release manifest 冻结 | `BLOCKED_BY_M11` |

M2、M4、M5 的 G0 准备可以在不共享修改同一契约的前提下并行，但实际运行仍需符合资源、许可和
用户授权。M6 必须等待全部适用决定和证据，不用单一工具通过替代整阶段 G1。

## 10. 历史迁移承接

旧 v0.5/v0.6、S-07 与 V06 工作包统一从[历史索引](../README.md)追溯，不再逐项出现在当前计划。仍有效的 Q08/Q09、OI-015/Q12/Q13 与通用工程不变量已分别迁入 [M3、M5、M6 承接材料](P0_FUTURE_MILESTONES.md)。冻结 Mock v0.1 继续保留，但不得映射为生产 v0.7 路由。

## 11. 发布包与内网验收

P0 v0.7 release bundle 至少包含：

1. 不依赖公网的镜像、模型权重、依赖包和校验清单；
2. AF3/ESMFold2、DeepTMHMM、FreeSASA 的版本、参数、许可证、硬件和资源档案；
3. 甲方输入模板、Schema、示例、上传/引用方式和错误码；
4. 输入、结构预测、质量、拓扑、RSA 和 P0EvidenceBundle 的机器契约；
5. OI-017 异步状态机、取消、恢复、幂等和不可覆盖验证；
6. 正常、边界、非法、缺失、OOM、超时、文件损坏和重复提交样本；
7. 断开公网情况下的安装、启动、运行和回归证据；
8. 明确列出 `EXCLUDED_FROM_PHASE1` 的 S-07/RCSB/AFDB/BLAST-UniProt 回退和 S-06；
9. 安装、预检、smoke、金标准、回滚和接收方签收记录。

smoke 只证明可调用，不能替代科学验收。运行时若检测到公网请求，应视为发布失败而不是降级成功。

## 12. 当前停止线

- OI-023 归并评审未完成前，不冻结入口 Schema，不实现生产入口；该项不再等待用户重新定义已有规则。
- AF3/ESMFold2 未完成内网等价 G0、许可证和模型权重取证前，不实现 S-08 生产适配器。
- Q08/Q09 未形成无歧义规则前，不冻结 S-09。
- OI-015 未关闭且 FreeSASA G0 未完成前，不冻结 S-11。
- OI-017 的数据契约、状态机、等待/恢复和逐工具 profile 未实现前，不接入真实长任务。
- 不修改 v0.1 Mock 结果来伪装 v0.7 生产能力；不复用旧 run_id 冒充新验收。
- 不启动 RCSB、AlphaFold DB、BLAST/UniProt 结构检索，也不在 Dify/LLM 中变相联网。
- P0 未达到 G6 `FROZEN` 前不开始 P1 真实工具。

## 13. 当前下一工作包：P0-V07-M1

M1 的交付不是代码，也不是面向用户的字段问卷，而是一份基于专家原文的甲方输入契约包：

1. `P0InputBundle` Schema review draft；
2. 专家来源—字段—规则对照矩阵；
3. `protein_sequence`、`host_species` 和可选 `structure` 的字段字典；
4. 序列及 PDB/CIF/mmCIF 的格式、哈希、来源、chain 与 R-58 校验表；
5. 输入接收、驳回、补交、替换、重复提交和幂等状态图；
6. 覆盖正常、缺失、非法、多记录、非标准残基、超长、重复、损坏结构和多链结构的 fixture manifest；
7. 明确“不得联网补齐”和“accession/URL 单独输入不可触发查询”的验收用例；
8. 仅针对真实冲突/缺口的专家复核清单，以及 OI-023 的关闭证据。

M1 完成后才能启动 AlphaFold3/ESMFold2 G0；M1 不执行科学计算，不修改生产代码或 Dify。
