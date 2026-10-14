# T-01 阶段 0（P0）科学工具实施方案

> 文档状态：`SUPERSEDED_PENDING_V0_6_REWRITE`  
> 版本：v0.5  
> 编写日期：2026-09-02  
> 当前确认人及角色：wing（开发者）  
> 当前边界：本文件保存旧 P0 v0.5 的评审与实测历史，不再授权按其六工具范围或 M0-M11
> 顺序实施。当前范围以 [P0 范围重基线](../p0-v07-plan/P0_SCOPE_REBASELINE.md)为准；专家资料逐项对照和 v0.6
> 完整重写前不进入生产编码。所有真实科学工具仍为 `NOT_DEPLOYED`。

> [!IMPORTANT]
> 2026-09-02 用户决定以专家 v10.5 文档重新建立 P0 需求基线。当前 P0 收敛为
> S-07/S-08/S-09/S-04/S-11；S-06/PSORTb 暂不属于 P0，范围差异登记为 OI-019。
> 本文后续仍出现的 S-06、六工具范围、`P0-M2` 和 M0-M11 仅用于保留旧方案上下文，必须在
> v0.6 重写中逐项处理，不得直接执行。
>
> 2026-09-03 更新：S-07 任务 1～6 已完成到
> [非生产独立验收与交接](../../s07/docs/archive/p0/S07_TASK6_ACCEPTANCE_AND_HANDOFF.md)层级。下一项是以这些实测事实和
> 发布门禁完整重写 v0.6；本文件正文中的旧里程碑与“下一步”仍只作历史记录。

原始业务材料把本段称为“阶段一｜结构与基础分析”，工程工作流把它编号为 P0。本文统一使用
P0。并列权威原件见[权威业务资料索引](../../../工作流设计/01-业务依据/README.md)；本文当前
顺序沿用 [T-01 v10 算法图](../../../工作流设计/01-业务依据/T01_算法图_v10_20260821.md)，
并以[数据契约](../../full-t01-mock-v0.1/工作流设计/02-数据契约/T01_Dify节点-MCP工具映射与数据契约_v0.1.md)
为当前工程契约依据。Agent A v10.5 与本方案的差异须逐项登记并由用户裁决，不能静默覆盖。

如果目的是理解旧六工具方案的背景，而不是查看当前范围，请阅读
[P0 工具通俗说明](P0_TOOL_GUIDE_WITH_EXCLUDED_STEPS_20260903.md)。

## 1. 方案目标

P0 的目标不是简单“把六个软件装起来”，而是形成一条可部署、可复现、可解释、可回滚的
结构与基础分析能力：

1. 从目标蛋白序列出发，获取可用的已有结构；没有可用结构时进入结构预测。
2. 保存结构来源、序列匹配、坐标覆盖和原始质量事实，不把来源或相似性隐藏在一个布尔值里。
3. 对结构质量、膜拓扑和表面暴露形成机器可读证据；旧方案的细菌亚细胞定位已移出当前 P0。
4. 全部科学计算由 MCP/后端完成；LLM 与 Dify 只传参、等待、按固定枚举路由和解释结果。
5. 先完成 P0 科学工具与阶段发布包，再完成 P0 工作流；P0 最终冻结前不开始 P1 真实工具。

P0 不负责表位、安全、保守性、序列设计、候选排序或 Agent C 交付。

## 2. 已确认、开发暂定和待确认事项

### 2.1 已确认

| ID | 决定 | 状态 |
|---|---|---|
| P0-D01 | 权威业务输入是 `protein_sequence`；全流程另有 `host`、`pathogen_type` 等输入 | `CONFIRMED` |
| P0-D02 | 当前不把 UniProt ID 设为必填输入；若以后增加，只能使用稳定的 `uniprot_accession` 作为检索提示，不能覆盖用户序列 | `CONFIRMED` |
| P0-D03 | 旧六工具顺序已被 [P0 范围重基线](../p0-v07-plan/P0_SCOPE_REBASELINE.md)取代；当前为 S-07→按需 S-08→S-09→S-04→按条件 S-11，S-06 由 OI-019 承接 | `SUPERSEDED` |
| P0-D04 | 先用公开样本建立 discovery 发现集；发现集不自动等同算法金标准 | `CONFIRMED` |
| P0-D05 | 先在本地验证，再部署到 Linux GPU 服务器 | `CONFIRMED` |
| P0-D06 | 阶段发布包允许引用多个 CPU/GPU/许可证隔离镜像，不要求合并成一个大镜像 | `CONFIRMED` |
| P0-D07 | 本方案按 M0→M11 严格门禁推进；wing（开发者）于 2026-09-01 确认开始执行 | `CONFIRMED` |

### 2.2 S-07 开发暂定语义

以下语义由 wing（开发者）于 2026-09-01 同意用于 discovery 和方案设计，状态为
`PROVISIONAL_DISCOVERY_POLICY`；算法负责人确认前不能升级为生产科学规则。

| 类别 | 暂定含义 | discovery 阶段的保守路由 |
|---|---|---|
| `TARGET_MATCH` | 目标蛋白自身的候选结构；规范化目标序列与结构 polymer entity 的权威序列相符 | 允许作为“已有结构”候选，但仍必须检查坐标覆盖、链和产物完整性 |
| `TARGET_DERIVED` | 同一目标蛋白的截短体、突变体、标签构建体或存在显著序列/坐标差异的结构 | 保存候选和映射报告；暂不绕过 S-08 |
| `HOMOLOG_TEMPLATE` | 来自不同序列实体的同源结构 | 仅保存模板证据；继续进入 S-08 |

开发阶段不得为 `TARGET_DERIVED` 或 `HOMOLOG_TEMPLATE` 自行设定 identity、coverage 或可接受
缺失残基阈值。最终分类与路由需要算法负责人确认。

### 2.3 尚未确认

- S-07 的最终匹配阈值、链选择、来源优先级和 `TARGET_DERIVED` 是否可直接使用。
- 目标来源物种/Taxonomy 是否需要成为正式输入；当前 `host` 不得自动解释为目标蛋白来源物种。
- S-08 中 AlphaFold3 与 ESMFold2 的生产路由、回退和参数档案。
- S-09 对实验结构与预测结构分别使用哪些质量事实，以及 high/medium/low 的权威阈值。
- S-04 的标准化拓扑枚举和项目门控含义。
- S-11 的 R-58 序列—结构映射与 RSA 参数档案，见 OI-015。
- S-06 所需 Gram/Archaea 模型输入来源和 `psortb_flag` 映射。

## 3. P0 权威流程

```text
protein_sequence
  -> S-07 获取已有结构
       -> TARGET_MATCH 且技术校验通过：采用已有结构
       -> TARGET_DERIVED / HOMOLOG_TEMPLATE / NO_USABLE_STRUCTURE：进入 S-08
  -> S-08 结构预测（需要时）
  -> S-09 结构质量事实与 high/medium/low 分档
  -> S-04 DeepTMHMM 拓扑预测
  -> quality != low 时执行 S-11 FreeSASA；low 时 rsa=null
  -> pathogen_type == bacteria 时执行 S-06 PSORTb
  -> 组装 P0 evidence bundle
```

`NO_USABLE_STRUCTURE` 是一次成功完成的检索结果，不是工具故障。[S-07 契约评审稿](../../s07/docs/archive/p0/S07_CONTRACT_REVIEW.md)
建议把它收敛为明确的成功 outcome，并与 HTTP、解析、产物或内部 `ToolError` 分开；该提案仍待
wing 开发确认，最终“可用”科学边界仍待算法/产品负责人确认。

G0 的 `discovery` 是证据分类，不是新增的 `ExecutionMode`。G0 直接运行冻结候选工具并保存
原始证据；进入 MCP 后，最小真实连通性使用现有 `smoke`，科学验收通过后才允许
`production`。

## 4. 两级交付策略

### 4.1 已检测的本地环境

| 项目 | 实测值 |
|---|---|
| GPU | NVIDIA GeForce RTX 5070 Ti Laptop GPU |
| 显存 | 12227 MiB，约 12 GB |
| Compute Capability | 12.0 |
| 驱动 | 591.74 |
| 驱动报告 CUDA | 13.1 |
| 驱动模式 | Windows WDDM |

### 4.2 里程碑定义

| 里程碑 | 必须完成 | 明确排除 |
|---|---|---|
| `P0_LOCAL_VERIFIED` | 本地真实跑通 S-07、ESMFold2-Fast 路径、S-09、S-04、S-11、S-06；形成本地发布包并完成 P0 本地工作流回归 | AlphaFold3 不得伪装本地已部署；本地结果不等同服务器生产冻结 |
| `P0_SERVER_FROZEN` | 在 Linux GPU 服务器完成 AlphaFold3、服务器 execution profile、许可证/权重授权、完整阶段发布包、金标准和 P0 生产工作流回归 | 不允许仍有影响生产路由的 P0 科学规则依赖临时默认值 |

本地 12 GB GPU 不作为 AlphaFold3 正式验收设备。AlphaFold3 官方重点验证的是 Linux 上的
A100/H100 80 GB；完整数据库可占用约 1 TB，长目标建议至少 64 GB 主内存。可以做额外的
小样本兼容性实验，但成功或失败都不能替代服务器验收。

本地 S-08 候选采用 `biohub/ESMFold2-Fast`，因为它是官方提供的单序列推理优化变体。它在
本机可支持的序列长度、峰值显存、运行时间和 CUDA/PyTorch 兼容性必须由 G0 实测得出，本文
不预设保证值。

只有 `P0_SERVER_FROZEN` 才允许进入 P1 真实工具实现。

## 5. 建议生产架构

```text
Dify P0 Workflow
  -> T-01 Production MCP facade
       -> request/schema/idempotency layer
       -> persistent run/job state
       -> artifact store + hash/provenance index
       -> retrieval worker       (RCSB / AlphaFold DB / BLAST)
       -> prediction worker      (ESMFold2-Fast local; AF3 server)
       -> topology worker        (DeepTMHMM)
       -> structural worker      (FreeSASA + mapping)
       -> localization worker    (PSORTb)
```

架构要求：

1. Mock 服务继续保持冻结基线；生产工具使用独立服务标识和运行环境，避免 Mock/Production
   产物混用。
2. 契约模型可以抽取为共享包，但真实适配器不得写进确定性 Mock 场景引擎。
3. MCP 只接受业务参数和 `ArtifactRef`，不接受任意 Shell 命令或任意服务器路径。
4. 长任务状态以持久化后端为事实源；`jobs.get_status` 只读，不因轮询次数推进状态。
5. 每个执行器独立固定镜像摘要、模型/数据库哈希、许可证和资源上限。
6. 原始输入、stdout、stderr、退出码、原始产物和标准化产物都必须可追溯。
7. API Key、模型访问凭证和许可证文件只通过部署环境注入，不写入仓库、日志或 DSL。
8. 科学工具与后端契约保持调用方中立；Dify 在 P0 工具包完成后才进行集成验证。Dify 兼容性
   通过单独 projection/adapter 处理，不得反向改变后端权威结果和科学产物。

## 6. 输入与阶段输出边界

### 6.1 输入

当前权威输入继续使用：

- `protein_sequence`：必填，唯一的序列事实源。
- `pathogen_type`：决定是否进入细菌分支，但不足以选择 PSORTb 的 Gram 模型。
- `host`：保留当前业务语义，不得自动当作目标来源物种或表达宿主。
- 现有 StepRequest 的运行、幂等、scope 和 ArtifactRef 字段。

候选但尚未获批的输入：

- `uniprot_accession`：可选检索提示；必须与 `protein_sequence` 重新比对。
- `target_taxon_id`：目标来源物种的稳定标识候选，用于 AlphaFold DB 消歧和 PSORTb 模型选择。
- `psortb_organism_profile`：若不由 `target_taxon_id` 确定性生成，则需要显式、受控枚举。

这些候选字段在业务/算法评审前不得加入生产请求 Schema。

### 6.2 P0 evidence bundle 草案

以下只定义信息分区，不定稿内部科学字段：

| 分区 | 至少承载的信息 |
|---|---|
| structure retrieval | 检索 outcome、全部候选、来源、标识、match class、序列映射、坐标覆盖和选用理由 |
| selected structure | 原始结构、规范化 mmCIF、结构来源、链、序列哈希、坐标残基映射 |
| prediction | 引擎、模型/权重、输入、seed、样本、排名、mmCIF 和原生置信输出 |
| quality | 原生质量事实、来源类型、缺失项、分档 profile ID 和最终枚举 |
| topology | DeepTMHMM 原始输出、区段、类型、`tm_count`、`is_membrane` 和警告 |
| rsa | FreeSASA 原始结果、参数、链/残基映射、绝对 SASA、相对 RSA 和不可映射位点 |
| localization | PSORTb 原始 long/terse 输出、使用的 organism profile、预测、分数和 `psortb_flag` |
| common | ArtifactRef、Provenance、质量标志、警告、错误、耗时和资源摘要 |

原始结构统一优先保留 mmCIF；如某下游只接受 PDB，转换必须形成新的 ArtifactRef，并记录转换
工具、版本和哈希，不能覆盖原始文件。

## 7. 各节点实施方案

### 7.1 S-07 `structure.fetch`

目标：从用户序列出发，分别形成实验结构、公共预测结构和同源模板候选，不把“检索到了命中”
直接等同“可作为目标结构”。

P0-M1/P0-M1B discovery 使用在线官方接口取得真实输出证据。2026-09-02 的 S07-D09 生产决定是
不使用在线数据库，改为服务器本地、不可修改的版本化数据包或索引。候选实现据此调整为：

1. 以本地 RCSB 序列索引查询 polymer entity，保存 identity、E-value、bit score 和匹配边界；
   具体本地查询引擎与索引构建方式在发布包中冻结。
2. 从同版本的本地 RCSB 元数据与坐标存储读取实体、实验方法、分辨率、UniProt 映射、链、序列
   元数据和 mmCIF。
3. 从本地 AlphaFold DB 数据包读取与已验证 UniProt accession 对应的公共预测结构、PAE 和版本
   信息；实际纳入范围仍由 S07-D14/D15 确认。
4. NCBI BLAST+ 对冻结的本地结构序列数据库执行 v10 指定的 BLAST 检索，保存原始归档和机器可读
   表格。

重要边界：RCSB 官方 sequence service 使用 MMseqs2，不能把它标记为 v10 的 C6 BLAST。
RCSB 搜索用于 RCSB 候选发现；独立 BLAST+ 是否必须运行、使用何种数据库与参数，需要在
discovery 后由算法负责人确认。

G0 必测事实：

- 100% 序列实体、多链和同一序列多结构结果。
- 截短、工程突变、标签、缺失坐标、alternate location 和非标准残基。
- 同源命中、仅 AlphaFold DB 命中、完全无命中。
- discovery 中的 RCSB 204、Data API 404、限流、超时、下载中断、内容类型错误和哈希不一致。
- 生产本地数据库包/索引缺失、版本不匹配、读取失败、内容损坏、查询不完整和哈希不一致。
- 每次运行记录本地数据库发布、工具与 profile 版本；数据库更新创建新版本，不覆盖旧版本。

S-07 契约评审前必须产生 `candidate_structure_manifest` 和逐候选 `sequence_mapping_report`。

P0-M1B 已使用独立、未部署的候选执行器完成输出审计。最终批次 `p0-s07-m1b-20260901-d` 保存
57 条来源调用、19 页 RCSB 查询、RCSB/AFDB 结构组成和 4 组 BLAST 三格式输出；审计清单统计
285 个非报告文件、23 类文件，执行失败和非空 stderr 均为 0。详细事实见
[P0-M1B 执行记录](../../s07/docs/archive/p0/S07_M1B_RUN_RECORD.md)。该批次本身只提供证据；wing 已于 2026-09-02 另行确认
D09 的分页、去重、本地数据库版本、文件分类和保留边界。该决定仍不确认任何科学规则。

### 7.2 S-08 `structure.predict`

目标：没有可用已有结构时产生预测结构和原生质量证据。

本地 profile：

- 使用冻结 commit/checkpoint 的 ESMFold2-Fast 候选。
- 先测试短单链公开蛋白，再逐步提高长度；记录 OOM 边界、显存峰值、时长和重复运行差异。
- 固定 seed、循环/采样参数、数值精度和模型哈希；不使用未记录的默认值。
- 保留原始坐标、pLDDT、PAE/PDE、pTM 等实际可得输出；字段以冻结版本实测为准。

服务器 profile：

- 按 v10 将 AlphaFold3 作为默认候选，并保留 ESMFold2 回退能力；最终路由需算法负责人确认。
- 保存 AF3 输入 JSON、数据管线产物、每 seed/sample 的 mmCIF 与 confidence JSON、顶层模型、
  排名和完整版本/参数信息。
- 默认不保存超大 embeddings/distogram；若科学负责人要求，另行评审存储和保留期。
- AF3 源码、模型参数和输出各有适用条款；没有组织授权和权重取得证据不得部署。

S-08 必须异步，按 OI-017 实现提交、只读状态、取消、deadline、结果读取和恢复。

### 7.3 S-09 `structure.assess_quality`

S-09 是确定性后端，不是 LLM 节点。它只解释已保存的原生质量事实，并根据已批准的版本化
profile 返回 high/medium/low。

必须区分：

- AlphaFold3、ESMFold2 和 AlphaFold DB 各自实际提供的置信字段及粒度。
- 实验结构的分辨率、实验方法、R-free/R-work、坐标覆盖等事实与预测结构 pLDDT 的不同语义。
- PDB B-factor 不能在未证明其语义时当作 pLDDT。
- 缺失指标、部分链和质量字段解析失败的行为。

v10 只写明“pLDDT 分档”，但 S-09 同时位于已有实验结构之后。算法负责人必须确认实验结构
质量如何进入统一枚举，以及预测结构的阈值。确认前只输出原始事实，不生成 production 分档。

### 7.4 S-04 `topology.predict`

候选工具为 DeepTMHMM 1.0。官方说明其接受标准 20 种氨基酸单字母序列，并可预测 alpha
helical 与 beta barrel 跨膜蛋白拓扑。

G0 需要保存：

- 原始类别、逐残基标签/概率、区段、图和警告的实际文件形态。
- 可溶性、单跨膜、多跨膜、信号肽、beta barrel 和非法字符样本。
- 单条与批量输入的差异、模型下载/缓存行为、运行时间和资源峰值。
- 从原生输出到 `tm_count`、`is_membrane` 的无损映射候选。

许可证是硬门禁：官方允许服务使用，但商业用户自建服务器需要商业许可证，学术用户不需要。
项目使用性质和部署授权未确认前，只能进行符合条款的 discovery，不能形成可交付生产镜像。

### 7.5 S-11 `structure.compute_rsa`

候选工具为 FreeSASA 2.x 冻结版本。官方提供 CLI、C 与 Python 接口，许可证为 MIT，并支持
PDB/mmCIF 以及 XML/JSON/RSA 等输出形式。

G0 需要比较并固定：

- Lee & Richards 与 Shrake & Rupley 算法选择。
- probe radius、原子半径分类器、切片/点数、线程和未知原子行为。
- mmCIF/PDB、多模型、多链、配体、水、氢、非标准残基和缺失原子的处理。
- 原子、残基、链和整体 SASA 输出，以及相对 RSA 的参考口径。

FreeSASA 成功计算不等于 S-11 验收通过。进入计算前必须按 OI-015 生成序列—结构映射报告；
目标链不明确、关键位点不可映射或覆盖不满足确认规则时不得静默继续。

### 7.6 S-06 `localization.predict_bacteria`

候选版本为 PSORTb 3.0.6 的官方/Brinkman Lab Linux 容器路径，许可证为 GPL。官方文档要求
输入 FASTA，并显式选择 Gram-positive、Gram-negative 或 Archaea；还支持部分特殊膜类型。

当前只有 `pathogen_type=bacteria`，不足以选择正确模型。生产前必须选择一种方案：

1. 增加目标 `target_taxon_id`，由版本化 taxonomy 后端确定性解析 organism profile；或
2. 增加受控 `psortb_organism_profile` 输入，并由用户/业务明确提供；或
3. 算法负责人批准其他确定性来源。

不得由 LLM 根据名称猜 Gram 类型。

G0 使用官方文档提供的 Gram-positive、Gram-negative 和 Archaea 示例，保存 normal、terse 和
long 原始输出。`Unknown`、多定位和“预测位置在该 organism profile 中不存在”必须保留原始
事实，不能强制映射成 PASS。`psortb_flag` 的枚举和合成规则在实测后评审。

PSORTb 依赖栈较旧，官方建议使用 Docker。生产镜像必须重新构建、生成 SBOM、扫描依赖并固定
所有下载物哈希，不能直接把浮动的公共镜像标签视为可交付资产。

## 8. 公开 discovery 发现集

发现集只用于观察工具事实、解析行为和工程边界；算法负责人批准前不称为金标准。

| Case | 类型 | 初始公开来源/选择规则 | 主要覆盖 |
|---|---|---|---|
| P0-DISC-001 | 短小可溶、明确实验结构 | Ubiquitin，PDB 1UBQ；ESMFold2 官方示例也使用该序列 | S-07 `TARGET_MATCH`、S-08 本地基准、S-09、S-11 |
| P0-DISC-002 | 目标衍生结构 | G0 时从 RCSB 选取有截短/工程突变/缺失坐标且来源清楚的条目 | `TARGET_DERIVED`、R-58 映射 |
| P0-DISC-003 | 仅同源结构 | G0 时选取无目标 exact hit、但有可解释同源命中的短蛋白 | `HOMOLOG_TEMPLATE`、BLAST 原始输出 |
| P0-DISC-004 | AlphaFold DB-only | 按 campaign 日期查询并冻结 accession、序列和 API 响应哈希 | AFDB 获取、无实验结构路径 |
| P0-DISC-005 | 无 exact-target 候选 | 按 campaign 日期冻结近期 RefSeq 短序列；同源可用性必须由阈值决定 | accession 映射缺口、S-08 保守路径 |
| P0-DISC-006 | 膜蛋白 | 从 DeepTMHMM 官方示例或权威公开条目选择单跨膜、多跨膜和 beta barrel | S-04、S-11 条件与映射 |
| P0-DISC-007 | 低置信/无序 | 公开、可复核的低置信或长无序蛋白区域 | S-09 low、S-11 跳过 |
| P0-DISC-008 | Gram-positive | PSORTb 官方示例 `SAK_BPP42` | S-06 positive profile |
| P0-DISC-009 | Gram-negative | PSORTb 官方示例 `NP_949347.1` | S-06 negative profile |
| P0-DISC-010 | Archaea 工具控制 | PSORTb 官方示例 `YP_001689002.1`；不自动扩展 T-01 细菌分支 | PSORTb 原生能力边界 |
| P0-DISC-011 | 非法与故障 | 空序列、非法字符、超限、404、204、超时、截断文件、错误格式 | 输入校验和 ToolError |

动态选择的公开样本必须记录选择日期、查询、数据库版本/时间戳、原始响应、序列哈希和保留理由，
防止数据库更新后无法解释结果变化。

### 8.1 P0-M1 S-07 实测结果

Campaign `p0-s07-discovery-20260901-a` 已于 2026-09-01 完成 RCSB、AlphaFold DB 和
NCBI BLAST+ 的原始输出取证，形成 5 个代表候选、逐候选序列—坐标映射、BLAST 依赖清单、
证据 inventory 与能力缺口表。关键事实包括：

- 6XRE 的 entity 序列与 393 aa 目标完全一致，但所选 chain 只有 314 个目标残基有坐标；
- 5XZC 只对齐目标 92-356，其中另有 33 个 entity 残基无坐标；
- 6PPV 是 62.5% identity 的局部同源命中，不能按目标结构使用；
- O15116 在 RCSB target-level 查询（identity cutoff 0.9）得到 HTTP 204，在 AlphaFold DB
  得到 exact 133 aa v6 模型；
- RefSeq accession 不能直接作为 AlphaFold DB API 标识符，P0-DISC-005 的 42 个弱 BLAST
  命中在缺少生产阈值时只能标记为 `HOMOLOG_USABILITY_UNDECIDED`。

完整证据见 [P0-M1 总结](../../s07/discovery/p0/s07/p0-s07-discovery-20260901-a/reports/P0_M1_SUMMARY.md)
和[能力缺口表](../../s07/discovery/p0/s07/p0-s07-discovery-20260901-a/reports/capability_gap_table.md)。
这些结果不构成算法金标准，也不表示 S-07 已部署。

基于上述证据形成的输入、outcome、候选层级、双层 mapping、来源状态、ArtifactRef、分页/去重、
错误边界和角色决定见 [S-07 契约评审稿](../../s07/docs/archive/p0/S07_CONTRACT_REVIEW.md)。相关未决事项已登记为
OI-018；评审稿完成不等于 Schema 或科学 profile 已获批准。
面向项目负责人的确认进度、责任分工和上报请求见 [S-07 决策汇报](../../s07/docs/archive/p0/S07_DECISION_REPORT.md)。

## 9. Discovery 证据规范

每次 discovery 使用唯一 campaign，例如 `p0-discovery-20260901-a`。每个 case/tool 至少保存：

1. 规范化输入 FASTA/JSON 及 SHA-256。
2. 工具、代码 commit、模型/checkpoint、数据库和容器摘要。
3. 完整命令参数或 HTTP 请求描述；凭证必须脱敏。
4. 原始 response/stdout/stderr、HTTP 状态、退出码和所有原始产物。
5. 墙钟时间、CPU、GPU、显存、主内存、磁盘和网络摘要。
6. 重复运行结果与随机性差异。
7. 原生字段事实表：字段、类型、单位、坐标系、枚举、空值和异常形态。
8. “直接提供 / 可无损解析 / 工具未提供”三类 v10 信息映射。
9. ArtifactRef 清单、哈希验证和来源/许可证记录。

仓库只保留小型 manifest、事实表、许可说明和允许再分发的最小样例。模型权重、数据库、大型
结构产物和可能受条款限制的输出进入受控 artifact store，由 ArtifactRef 引用。

## 10. 从实测到契约的收敛方法

每个节点使用同一微循环：

```text
冻结候选版本
  -> G0 正常/边界/失败实测
  -> 原始输出事实表
  -> v10 所需信息差距
  -> 相关算法/业务问题
  -> 负责人确认
  -> Schema + parameter profile + execution profile
  -> 适配器实现与测试
```

只有依赖真实输出的问题才等待 G0。纯工程原则如幂等、ArtifactRef、错误分类和 OI-017 状态机
可以先设计，但逐工具 deadline、轮询和资源数值必须来自实测。

如工具不能提供 v10 所需事实，应明确记录能力缺口并评审替代工具或流程；不得由适配器、LLM
或 Dify 伪造字段。

## 11. 实施里程碑与严格顺序

| 里程碑 | 工作 | 退出证据 | 状态 |
|---|---|---|---|
| P0-M0 方案评审 | 评审本文的边界、架构、两级交付和停止线 | wing 开发确认；科学问题有负责人/待确认标记 | `COMPLETED` |
| P0-M1 S-07 discovery | RCSB、AFDB、BLAST 公开发现集取证 | 原始 evidence、候选 manifest、映射报告和缺口表 | `COMPLETED` |
| P0-M1B S-07 输出审计 | 构建非生产可执行候选工具并调用公开发现集，盘点实际文件、大小、层级、重复与分页行为 | [执行记录](../../s07/docs/archive/p0/S07_M1B_RUN_RECORD.md)、最终批次 D 的输出清单、大小分布、重复关系和追溯缺口报告 | `COMPLETED_EVIDENCE_ONLY` |
| P0-M2 S-07 实现 | 契约确认后实现生产检索适配器 | 单测、故障测试、smoke、可重复取证 | `BLOCKED_BY_S07_ROLE_CONFIRMATION` |
| P0-M3 S-08 discovery/实现 | 本地 ESMFold2-Fast；服务器准备 AF3 | 本地 profile；AF3 资源/授权清单和服务器 profile 草案 | `NOT_STARTED` |
| P0-M4 S-09 | 基于 S-07/S-08 原始质量事实收敛分档 | 算法确认 profile、纯后端测试和边界样例 | `NOT_STARTED` |
| P0-M5 S-04 | DeepTMHMM 实测、许可确认和适配器 | 原始拓扑证据、许可证据、解析与失败测试 | `NOT_STARTED` |
| P0-M6 S-11 | FreeSASA 与 R-58 映射 | OI-015 决定、参数 profile、逐残基金标准 | `NOT_STARTED` |
| P0-M7 S-06 | 旧方案 PSORTb 里程碑 | OI-019 专家答复；当前 P0 不实施 | `REMOVED_FROM_CURRENT_P0` |
| P0-M8 本地发布包 | 固定本地全部镜像、Schema、profiles 和证据 | `P0_LOCAL_TOOLS_PACKAGED` | `NOT_STARTED` |
| P0-M9 本地工作流 | 生成、绑定、导入、发布并回归 P0 local profile | `P0_LOCAL_VERIFIED` 新 run_id 批次 | `NOT_STARTED` |
| P0-M10 服务器发布包 | Linux GPU 部署 AF3 与全部 P0 工具 | 不可变镜像、权重/数据库、资源和回滚证据 | `NOT_STARTED` |
| P0-M11 服务器工作流 | 更新 profile 并执行生产阶段回归 | `P0_SERVER_FROZEN` | `NOT_STARTED` |

不得在 P0-M8 前修改 P0 工作流为真实工具路径；不得在 P0-M11 前开始 P1 真实工具实现。

## 12. 验收矩阵

### 12.1 工具级

- 输入 Schema、非法输入、空值、超限和幂等冲突。
- 正常、无命中、部分成功、可重试错误、永久错误、超时、取消和恢复。
- 原始产物存在、格式正确、哈希一致、ArtifactRef 不泄漏服务器路径。
- 工具、模型、数据库、参数、seed、计算环境和耗时完整记录。
- 冻结输入重复运行的确定性或允许随机范围。
- 许可证、引用、再分发和模型输出条款满足当前使用场景。

### 12.2 P0 路径级

- RCSB `TARGET_MATCH` 采用已有结构。
- `TARGET_DERIVED`、`HOMOLOG_TEMPLATE` 和无命中进入 S-08。
- AlphaFold DB exact target 路径。
- 本地 ESMFold2-Fast 成功、OOM、取消和恢复。
- 预测结构 high/medium/low；实验结构质量事实路径。
- low 结构确定性跳过 S-11，并输出 `rsa=null` 和原因。
- 膜/非膜、单跨膜、多跨膜和 beta barrel。
- FreeSASA 多链、缺失残基、未知原子和映射失败。
- bacteria 执行 PSORTb；非 bacteria 禁止调用。
- Gram profile 缺失时确定性阻断，不由 LLM 猜测。
- 任一本地数据库或检索工具失败时不把“未知”误报为“无命中”。

### 12.3 发布级

- 全新环境按 manifest 可重建或拉取完全相同的镜像。
- 所有镜像有摘要、SBOM、漏洞与许可证报告。
- 模型/数据库有版本、日期、SHA-256、获取和回滚方式。
- smoke、科学金标准和故障样例相互区分。
- 使用唯一 run_id 批次完成 P0 阶段工作流和受影响 Master 前缀回归。
- Mock、local smoke、server production 结果无法被错误混用。

## 13. 阶段发布包

建议 P0 release bundle 引用以下隔离单元；最终镜像名称在实施时冻结：

| 单元 | 内容 | 本地 | 服务器 |
|---|---|:---:|:---:|
| retrieval | 本地 RCSB/AFDB 版本化数据包与索引、BLAST+、检索适配器 | 是 | 是 |
| fold-esmfold2 | ESMFold2-Fast 与 checkpoint | 是 | 是/按路由 |
| fold-af3 | AlphaFold3、数据库、权重和 GPU profile | 否 | 是 |
| topology | DeepTMHMM 与模型 | 许可允许后 | 是 |
| structure-analysis | FreeSASA 与序列—结构映射 | 是 | 是 |
| localization | PSORTb 3.0.6 及固定依赖 | Linux 容器 | Linux 容器 |
| control-plane | MCP facade、job state、artifact/provenance | 是 | 是 |

release bundle 至少包含：阶段/工具清单、明确排除项、Schema 版本、镜像摘要、模型/数据库哈希、
parameter/execution profiles、许可证/SBOM、发现集与金标准报告、安装预检、回滚说明，以及 P0
工作流引用的准确摘要。

## 14. 风险与停止线

| 风险/缺口 | 当前处理 | 解除条件 |
|---|---|---|
| S-07 命中语义未获算法确认 | 使用三类暂定语义；仅 TARGET_MATCH 进入已有结构候选 | 算法负责人确认分类、阈值、链与覆盖规则 |
| AFDB 以 accession 获取，而当前只保证 sequence | accession 只作为内部候选并回验序列 | 确认映射策略及是否需要 target_taxon_id |
| RCSB sequence search 不是 BLAST | 分开保存 RCSB/MMseqs2 与 NCBI BLAST+ 证据 | 算法负责人确认 C6 BLAST 的数据库与用途 |
| 生产改用本地结构数据库 | 数据包/索引不可原位覆盖，运行记录发布 ID/版本/哈希；不启用在线 fallback | D14-D16 确认纳入来源与范围，D18/发布包冻结构建、更新、容量和生命周期 |
| 本地 GPU 仅 12 GB | 本地使用 ESMFold2-Fast；AF3 标记未部署 | Linux GPU 服务器达到确认的 AF3 profile |
| AlphaFold3 资源与权重条款 | 不在本地发布包宣称部署 | 服务器、组织授权、权重、数据库和条款证据齐备 |
| DeepTMHMM 自建许可取决于使用性质 | 先完成许可判定，不把服务可用等同自建许可 | 使用性质和授权证据明确 |
| S-09 分档缺权威规则 | G0 只保存质量事实 | 算法负责人确认实验/预测结构 profile |
| OI-015 阻塞 S-11 | 先生成映射事实，不执行生产门控 | OI-015 至少 `DECIDED` 且测试已更新 |
| PSORTb 缺 Gram profile | discovery 样本显式携带 profile；生产阻断 | 输入/解析来源和 `psortb_flag` 映射确认 |
| PSORTb 依赖较旧 | 独立 Linux 镜像、SBOM、漏洞扫描 | 镜像可重复构建且风险被接受或修复 |

任何一项出现以下情况必须停止对应工具生产化：许可证不允许、权重来源不合法、原始输出无法
稳定解析、v10 所需事实不可获得、算法规则仍依赖猜测、ArtifactRef/Provenance 不完整，或金标准
无法复现。

## 15. P0 完成定义

### `P0_LOCAL_VERIFIED`

- 本地 release bundle 已形成，AlphaFold3 被明确排除并标记 `NOT_DEPLOYED_LOCAL`。
- S-07、ESMFold2-Fast、S-09、S-04、S-11、S-06 的本地包含范围均有真实证据。
- P0 local profile 工作流在发布包完成后生成、绑定、导入、发布并通过新批次回归。
- 输出明确标注 smoke/local，不得用于生产科研结论。

### `P0_SERVER_FROZEN`

- Linux GPU 服务器上的 AlphaFold3 与全部 P0 生产工具均通过预检、金标准和故障验收。
- 所有影响生产路由的 P0 科学规则已由具名负责人确认并进入版本化 profile。
- P0 server release bundle 可重建、可回滚，许可证、权重、模型和数据库证据完整。
- P0 生产工作流及受影响 Master 路径使用新 run_id 全部通过。
- 状态、运行手册、数据契约、开放项和基线已同步。

只有满足 `P0_SERVER_FROZEN` 才视为阶段 0 完成。

## 16. 官方工具资料

- [RCSB PDB Search API](https://search.rcsb.org/)：序列查询、匹配上下文和结果标识。
- [RCSB Data API](https://data.rcsb.org/)与
  [文件下载服务](https://www.rcsb.org/docs/programmatic-access/file-download-services)：元数据与 mmCIF。
- [AlphaFold Protein Structure Database](https://alphafold.ebi.ac.uk/)及
  [API 文档](https://alphafold.ebi.ac.uk/api-docs)。
- [NCBI BLAST+ 官方手册](https://www.ncbi.nlm.nih.gov/books/NBK279690/)。
- [AlphaFold3 安装要求](https://github.com/google-deepmind/alphafold3/blob/main/docs/installation.md)、
  [输出说明](https://github.com/google-deepmind/alphafold3/blob/main/docs/output.md)和
  [权重条款](https://github.com/google-deepmind/alphafold3/blob/main/WEIGHTS_TERMS_OF_USE.md)。
- [Biohub ESMFold2-Fast 模型页](https://huggingface.co/biohub/ESMFold2-Fast)和
  [Biohub ESM 仓库](https://github.com/Biohub/esm)。
- [DeepTMHMM 1.0 官方服务与许可说明](https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/)。
- [FreeSASA 官方文档](https://freesasa.github.io/)及
  [CLI 文档](https://freesasa.github.io/doxygen/CLI.html)。
- [PSORTb 官方文档](https://psort.org/documentation/index.html)、
  [下载与许可](https://psort.org/downloads/)和
  [Brinkman Lab Docker 路径](https://github.com/brinkmanlab/psortb_commandline_docker)。

以上链接只证明候选工具的官方能力与边界；实际 release 必须冻结精确版本/commit、下载物和
哈希，不能使用浮动的 `latest` 或 `main` 作为生产版本。

## 17. S-07 契约评审稿完成后的下一步

S07-D03 至 S07-D10 已由 wing 确认，其中 D09 根据 P0-M1B 真实输出确定了自动取得轻量候选、
分层去重、本地版本化数据库、五类文件和保留边界。S07-D11 至 S07-D17 已整理为向上汇报项，
当前等待算法/产品负责人正式反馈。开发包覆盖强类型输入、
检索 outcome、候选/实体/链/model/assembly 层级、ArtifactRef、双层映射、来源状态、分页去重和
ToolError 边界；科学包覆盖三类命中、阈值、候选选择、来源优先级和 accession 映射。

P0-M1B 已按上述边界完成：候选工具保留原始输出，未进入 MCP/Dify，未作生产路由，也未用于科研
结论。下一步取得 D11-D17 的角色反馈，再完成 D18 与 parameter/execution profile 冻结，之后才
进入 P0-M2 生产适配器编码；不得把 discovery 参数直接复制为 production profile。
