# P0 专家依据对照表（v0.7 四步骤 + S-07 历史证据）

> **已被当前四步骤[专家依据矩阵](../p0-v07-plan/P0_EXPERT_EVIDENCE_MATRIX.md)替代。** 本文混合保留 S-07 追溯信息，不得作为当前问题清单。

> 版本：v0.7；日期：2026-09-03；状态：`CURRENT_FOUR_STEP_EVIDENCE / S07_HISTORICAL`。  
> 当前范围：目标蛋白序列 + 宿主物种 + 可选结构；无结构时 S-08 → S-09 → S-04 → 按条件 S-11。  
> 本表是原文提取与差异登记，不是新的科学规范、冻结契约或生产实施授权。  
> 验收说明：按具体工具和生物学场景描述检查要求；原文未提供的测试序列及样本信息待验收准备时补齐。
> 任务 3/4 已完成的 S-07 取证会在对应行明确标出，其余用例不表示已经运行或已获科学签收。

## 1. 使用方式与原文索引

每步均按**输入、输出、执行条件、科学规则、失败处理、验收要求**六项整理。科学规则由后端
确定性执行；LLM 只收集输入、调用工具和解释事实，Dify 只按后端枚举或布尔值路由。

表中的“明确”只表示原文有规定，不表示工具已部署或验收通过。“部分明确”表示仍缺具体条件、
数据载体或实测资产；“冲突”表示原文给出不一致结论；“待实测”表示需要以实际工具输出取证。
`P0-Qxx` 是本表的问题编号，不是新建或已关闭的 OI。具名决定仍在
[开放项清单](../../../docs/project/OPEN_ITEMS.md)登记。

> [!IMPORTANT]
> 2026-09-03 节点 01 内网决定已经把 S-07、RCSB PDB、AlphaFold DB 及其
> BLAST→UniProt→AFDB 回退移出一期。本文 §3、P0-Q02～Q05、S07-EQ-01～05 和相关验收行
> 仅保留为历史取证，不再阻塞 P0 v0.7；当前使用重点是 S-08/S-09/S-04/S-11 与离线输入。

### 1.1 权威来源

以下十一份资料按[权威资料索引](../../../工作流设计/01-业务依据/README.md)分层使用：一期 18 节点图
优先决定范围、裁剪顺序和明确排除项，其余资料用于保留节点的科学细节和历史追溯。
专家包均指当前 `抗原智能体_v10.5_修订版_20260902/`；不引用已移除的旧包。
正文的 `[Agent A SOP] S-07，L218–234` 表示点击来源后按步骤标题与物理行号定位；行号从 1 开始。
PDF 页码按文件物理页计：共 11 页，前 10 页印有页脚，第 11 页是附加流程图。

| 原文文件 | 本表直接使用的位置 |
|---|---|
| [一期 18 节点图](<../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>) | 节点 01/02、S-06 排除、S-11 第 3 裁剪顺位和一期排除清单 |
| [节点 01 内网会议截图](../../../工作流设计/01-业务依据/一期节点01内网裁剪会议截图_20260903.png)及后续用户澄清 | 只删除外部 RCSB PDB/AlphaFold DB 查询；本地 AF3/ESMFold2 正常使用；输入为目标序列、宿主物种和可选结构 |
| [算法图 v10](../../../工作流设计/01-业务依据/T01_算法图_v10_20260821.md) | P0 子图 L15–26；非阻塞项 L242–255；门控汇总 L258–266 |
| [一期边界说明](../../../工作流设计/01-业务依据/抗原智能体一阶段边界及核心能力说明.pdf) | 第 2 页总览、第 3 页输入、第 4 页阶段一、第 10 页交付边界、第 11 页附加流程图 |
| [Agent A 规则总纲](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md) | §2.1 R-01～R-05；§2.4 R-20～R-24；§2.11 R-48/R-58；§3 版本通则；§4 成功标准 |
| [Agent A SOP](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md) | S-04 L139–154；S-07 L216–236；S-08 L238–281；S-09 L283–324；S-11 L384–400；T-01 step0a/0/1/2/2b |
| [Agent A Schema](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md) | CandidateRecord.structure L104–121、topology L123–142、质量标记 L597–610、method_summary L698–717；FailureReport L870–922 |
| [结构预测获取链 ToolSpec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md) | §2a/2b/2c 输入与判定；§3 输出；§5 失败；§6 五个抽象验收用例；§7 对齐口径 |
| [DeepTMHMM ToolSpec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_A5_DeepTMHMM_v10.5.md) | §2 输入；§3 输出与消费；§5 失败；§6 五个抽象验收用例；§7 P/B 与非法输入 |
| [FreeSASA ToolSpec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C34_FreeSASA_v10.5.md) | §2 R-58 与计算口径；§2b 参考面积表；§3 输出；§4 内部消费变量边界 |
| [一期实施环境清单](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期实施环境清单_v10.5.md) | §1 工具与裁剪；§2 数据依赖；§3 E-06 参数；§4 环境、版本与许可证 |

定位使用的文件大小、行数、SHA-256 与 PDF 页数见
[来源快照](P0_EXPERT_EVIDENCE_SOURCES_20260902.json)；新增一期图的来源与哈希见
[一期范围来源清单](../../../docs/project/sources/PHASE1_SCOPE_SOURCE_20260903.json)与
[节点 01 来源清单](../../../docs/project/sources/PHASE1_NODE01_OFFLINE_SOURCE_20260903.json)。快照用于检测原文变化，不替代原件。
原文中的外部工具版本、论文归属和耗时在此仅作为专家交付口径记录，部署能力仍须实测。

### 1.2 当前工程边界与既有决定

| 项目 | 当前口径 | 工程依据与使用限制 |
|---|---|---|
| 当前四步骤范围 | 节点 01=必填序列/宿主+可选结构+S-08/S-09；节点 02=S-04/S-11；S-07/S-06 不进入一期；当前完整 profile 仍保留 S-11 | [一期范围重基线](../project/PHASE1_SCOPE_WITH_P0_MAPPING_20260903.md)与 [P0 范围重基线](../p0-v07-plan/P0_SCOPE_REBASELINE.md)；输入归并由 OI-023 `IN_REVIEW`，未来缩减受 OI-020 阻塞 |
| S-07 历史数据取得 | 旧 v0.6 曾按 RCSB、UniProt、AlphaFold DB API 及本地化 profile 取证；当前一期已删除 | [任务 4 API 报告](../../s07/discovery/p0/s07/p0-s07-task4-uniprot-afdb-20260902-a/reports/TASK4_API_EVIDENCE_REPORT.md)与 D09 只作历史；不得用于恢复当前生产检索 |
| 旧 S-07 实测 | P0-M1/P0-M1B 只证明接口、文件与数据形态 | 不能把旧 discovery 数据库、候选分类或阈值升级成专家规则；见 §3 和 P0-Q02～Q05 |
| 生产状态 | 所有真实科学工具仍为 `NOT_DEPLOYED` | v0.7 已完成工程评审；仍须处理问题、取得 G0/科学验收证据并逐项通过生产门禁 |
| 跨阶段能力 | 外部 `context_scores` 注入不进入一期；S-44 必保留但真实 Agent C/外部接口尚缺，保持 `delivered=false` | [当前状态](../../../docs/project/STATUS.md)；OI-013 关闭前不得宣称交付链路完整，本表不扩大当前交付范围 |

## 2. 当前四步骤总览与 S-07 历史行

| 步骤 | 直接输入 | 主要输出 | 当前主链的执行条件 | 依据 |
|---|---|---|---|---|
| S-07 `fetch_structure` | `seq`、`organism_name`（检索辅助） | 已有结构、来源、方法、分辨率、覆盖；或正常空结果 | `HISTORICAL / EXCLUDED_FROM_PHASE1` | 旧 [Agent A SOP] S-07 与结构链 ToolSpec；只作历史取证 |
| S-08 `predict_structure` | 甲方提供并校验的 `seq`；引擎 profile 待 G0 冻结 | 预测结构、逐残基/平均 pLDDT、pTM、引擎与版本 | 没有合法可选结构时执行；不等待 S-07；AF3/ESMFold2 在甲方服务器本地运行 | [Agent A SOP] S-08 L240–279；[结构链 ToolSpec] §2b/5；[科学规则] R-48 |
| S-09 `assess_structure_quality` | 甲方可选结构或 S-08 的预测 `structure` | `confidence`、`topology_reliable`、低置信区掩码、警告 | 取得可解析结构后；纯后端逻辑，不调用网络或新科学工具 | [Agent A SOP] S-09 L285–324；S-07c L361–379；[结构链 ToolSpec] §2c/3 |
| S-04 `predict_topology` | `protein{seq}` | 四类标签、区段、信号标记、跨膜段数、外侧残基数；或 `null/unreliable` | 主链进入基础分析时必跑；未设置 `confidence!=low` 的前置条件 | [Agent A SOP] S-04 L141–152、T-01 L1885–1892；[DeepTMHMM ToolSpec] §2/3 |
| S-11 `compute_rsa` | `structure{pdb_path}`；R-58 另需原始 `seq` 与映射上下文 | `rsa{per_residue[], buried_fraction}`；或跳过/失败 | `quality.confidence!='low'` 时先通过 R-58 再计算；low 时 `rsa=null` | [Agent A SOP] S-11 L386–398、T-01 L1886–1892；[算法图] L247/265；[FreeSASA ToolSpec] §2 |

“必跑”指主链到达该步骤后的要求，不表示预测结构已经失败时仍强行继续后续步骤。
S-09 的 `topology_reliable` 是**结构质量事实**，S-04 的 `topology` 是**序列拓扑预测结果**；
原文没有允许用前者替代后者，也没有把 `topology_reliable=false` 直接写成 S-11 跳过条件。

| 共同项 | 原文要求与可用结论 | 仍需落实或澄清 | 依据 |
|---|---|---|---|
| 顶层输入 | 必填 `protein_sequence`、`host_species`，可选 `structure`；结构接受 PDB/CIF/mmCIF、chain 可选、保留原格式。S-07 不再消费 `organism_name` | OI-023/P0-V07-M1 负责把专家分散条款归并为请求 Schema、ArtifactRef 和校验表；不是向用户索取规则 | [最新用户决定]；[一期图] L9；[Agent A Schema] L21–32；[Agent A SOP] S-07c L361–379；[结构链 ToolSpec] L48–51 |
| 长度守卫 | `len(seq)<9` 且 `epitope_mode` 为 `both/tcell_only` → failure_report；`bcell_only` 短序列为 WARNING；9～29 aa 进入 `<30` 警告分支；长序列风险在 S-08 处理 | **明确，按 SOP 已有条件执行**。[DeepTMHMM ToolSpec] L69 是工具卡对前置守卫的概括，不据此新增独立长度门槛或模式开放范围决定；已从 P0-Q01 待确认内容移除，见 §10.1 | [Agent A SOP] T-01 step0a L1816–1827；[算法图] L262；[DeepTMHMM ToolSpec] §7 L69 |
| 方法记录 | 名称、版本、参数记录到 `method_summary`；Schema 提供 step/tool/version/parameters/runtime_seconds 及 pipeline_version/timestamp | 工具原始输出与后端规则版本、模型/数据库版本需落实到版本化档案；不能填虚构版本，P0-Q17 | [科学规则] R-05 L77、§3 L223；[Agent A Schema] L698–717；[一期环境清单] §1/4 |
| 错误透明 | R-48 要求失败级 WARNING、该步 unreliable，涉及权限/验证/交付结论时禁止自动交接；具体重试/停机以步骤条款为准 | S-07 正常空结果有明确例外；普通降级不自动等于整条链失败。机器载体和 FailureReport 边界仍须对齐，P0-Q10 | [科学规则] L172；[结构链 ToolSpec] L80–87；[DeepTMHMM ToolSpec] L48–50；[Agent A SOP] L1888–1890 |
| 空值与失败输出 | 未计算的可空字段为 null；pipeline 失败输出 FailureReport，必需 workflow/failed_step/failure_reason；已完成数据可保留在 partial_results | `null` 不等于 0、正常或成功；“跳过/运行失败/映射失败”仍需各自状态，P0-Q10/P0-Q14 | [Agent A Schema] L870–920、L997；[一期边界说明] 第 10 页 |
| 验收层级 | 本表核对 P0 基础事实与降级说明 | SC-05 属 T-06，SC-10 属完整 T-01；均不能直接当作当前 P0 冻结门槛。专家验收用例大多为抽象占位，P0-Q16 | [科学规则] §4 L288/293；[结构链 ToolSpec] §6；[DeepTMHMM ToolSpec] §6；[一期边界说明] 第 4/10 页 |

## 3. S-07：已有结构获取（一期已排除，以下仅作历史证据）

| 维度 | 专家口径 | 原文出处 | 对照结论 / 问题 |
|---|---|---|---|
| 输入 | `seq, organism_name`；序列是检索输入，目标物种名称仅作辅助。RCSB PDB 搜索产生候选后，再取方法、分辨率、提交日期 | [Agent A SOP] S-07 L218–226；[结构链 ToolSpec] §2a L25–27 | 签名明确；物种信息缺省、accession hint 与序列的校验边界待定，P0-Q01/Q04 |
| 输出 | `{pdb_path, source, resolution, method, coverage}`；`source` 为 experimental/alphafolddb；部分覆盖要标注 partial。均无结构返回 null；内部 `source=none` 不能作为 CandidateRecord.structure.source 落盘，最终 structure 整体为 null | [Agent A SOP] L219、L229–232；[结构链 ToolSpec] L28–29、L57；[Agent A Schema] L104–121 | 核心字段与 null 语义明确；coverage/partial 在 structure Schema 中没有已定义字段，P0-Q14 |
| 执行条件 | RCSB PDB 实验结构优先；无结果时查 AlphaFold DB 公共预测结构；无 accession 时经 BLAST 对 UniProt 的 BLAST 取得 accession 后再查 AlphaFold DB；均无则由 T 层调用 S-08 | [Agent A SOP] L223–229、L1880–1882；[结构链 ToolSpec] L25–28、L98 | 来源顺序和 BLAST 的内部 fallback 用途已有依据；服务失败、部分失败与“均无”的界限未完整定义，P0-Q05 |
| 科学规则 | RCSB PDB 候选门槛为 **identity>95% 且 coverage>90%**，均为严格大于；实验候选中“最高分辨率”指 **正 Å 数值的 min**；可比的 X-ray/cryo-EM 用 min；NMR 的 null 分辨率及不可比方法需单列优先级并 WARNING | [Agent A SOP] L223–227；[结构链 ToolSpec] L25–26、L96 | 数值门槛和 min 明确；比对口径、坐标覆盖、同分规则、跨方法优先级未给完整表，P0-Q02/Q03 |
| 失败处理 | 两源正常均无→null，非 failure；partial→缺失位置逐残基输出置 null+WARNING；下游扫描限覆盖区，折叠验证改全序列预测。调用失败另受 R-48 约束 | [Agent A SOP] L229–234；[结构链 ToolSpec] L28–29、L80–81；[科学规则] L172 | partial 不等于正常无结构；不能把 partial 一律改送 S-08，也不能把故障包装为科学无命中，P0-Q02/Q05 |
| 验收要求 | **实验结构命中**：满足门槛的实验命中，source/method/resolution 正确；2.0 Å 与 3.5 Å 的可比候选选 2.0 Å。**公共预测结构回退与无结构转预测**：RCSB PDB 无、AlphaFold DB 有→alphafolddb；正常均无→null 并转 S-08 | [结构链 ToolSpec] §6 用例 1/2，L96–98 | 原文有两个抽象用例，无真实样本/冻结期望；补足 partial、严格边界、不可比方法和故障用例，P0-Q16 |

### 3.1 与已有工程材料的差别

1. 旧材料中“来源顺序、阈值、BLAST 用途全部待定”的概括已不适合直接沿用：当前专家原文
   已给 RCSB PDB→AlphaFold DB、BLAST 对 UniProt 的 accession fallback、RCSB PDB 的 >95%/>90% 与 min(Å)。
2. 旧 `TARGET_MATCH/TARGET_DERIVED/HOMOLOG_TEMPLATE` 是 discovery 分类，不是本次发现的
   专家枚举。专家允许 partial 并要求下游降级；与旧分类的映射应在 OI-018 中重审。
3. 旧 BLAST 对 wwPDB 序列库的实测只证明该实测路线可执行，不能代替专家指定的
   **BLAST vs UniProt → accession → AlphaFold DB**。生产数据库、序列映射与门槛需另行取证。
4. D09 已确认本地版本化数据库；[一期环境清单] L65 的 API/下载描述须转成与既有决定相容的来源和
   同步方案。本文不重新请求该决定，也不假定现有缓存已经满足本地生产库要求。

本小节仅重定级文档依据，不更改旧证据与 OI 状态。关联：OI-018、P0-Q02～Q05/P0-Q14。

## 4. S-08：按序列预测结构

| 维度 | 专家口径 | 原文出处 | 对照结论 / 问题 |
|---|---|---|---|
| 输入 | `seq, engine='AF3', mutation_count=0`；当前 P0 首算 `mutation_count==0` 使用 AlphaFold3；变体 MSA 策略由 AlphaFold3 内部处理 | [Agent A SOP] S-08 L240–250、L271；[结构链 ToolSpec] §2b L35–37 | P0 默认明确；复用接口的 R-04 区间不能仅凭该签名完整计算，P0-Q06 |
| 输出 | `structure{pdb_path, plddt[], mean_plddt, ptm, engine, version, source}`；Schema 的逐残基字段名是 `plddt_per_residue`；AlphaFold3/ESMFold2 分别为 af3_predicted/esmfold2_predicted；预测结构 resolution/method 为 null | [Agent A SOP] L241–242、L272–277；[结构链 ToolSpec] §3 L58–60；[Agent A Schema] L107–118 | 字段转换明确；降级标记进入 quality_flags，具体 key 和机器状态待对齐，P0-Q10 |
| 执行条件 | S-07 正常未获得结构时调用；P0 默认 AlphaFold3。1000～1500 aa 发长序列 WARNING；>1500 aa 发超长序列 WARNING；尝试 AlphaFold3 后 OOM 或超时>2h 才按该长度降级链转 ESMFold2 | [Agent A SOP] L247、L251–261、L1880–1882；[结构链 ToolSpec] L35–38 | 长序列链明确；该条款不能外推为所有 AlphaFold3 故障均可自动换引擎；OI-017 的 execution profile 尚待落实 |
| 科学规则 | AlphaFold3 默认 5 个 diffusion 样本：单体按最高 pTM；复合物按 0.2×pTM+0.8×ipTM。per-atom pLDDT 取 Cα 值为逐残基值，mean 为其均值；AlphaFold3 0～100 标度除以 100；ESMFold2 必须检测标度后再决定是否除以 100；无 pTM 能力时取 null | [Agent A SOP] L242、L263–277；[结构链 ToolSpec] L58–60、L110–114 | 简化选样规则明确；须部署对比碰撞惩罚，冻结标度检测和缺失值处理，P0-Q07 |
| 失败处理 | 预测失败→failure_report。规定的长序列降级成功→quality_flag='degraded'，notes 使用固定文本；ESMFold2 也失败→failure_report 并建议截短后重试。mmCIF 原件保留；PDB 转换失败仅 WARNING，不在获取链 halt；仅接受 PDB 的消费步骤自行报失败 | [Agent A SOP] L254–270、L279；[结构链 ToolSpec] §5 L82–85 | 正常失败、长序列降级与格式失败已区分；其他失败的重试次数/资源超时未冻结，P0-Q07/Q10/Q17 |
| 验收要求 | **AlphaFold3 输出后处理**：选择 pTM 最高样本，Cα pLDDT 在 [0,1]，mean_plddt 等于逐残基均值，mmCIF 原件保留 | [结构链 ToolSpec] §6 用例 3，L100 | 原文有一个抽象正常用例；需补两种 pLDDT 标度、长序列 OOM/超时、ESMFold2 失败与格式转换失败，P0-Q16 |

### 4.1 必须保留的细节

| 项目 | 原文内容 | 适用范围与限制 |
|---|---|---|
| 长序列降级 notes | `ESMFold2 fallback due to AF3 OOM on >1500aa sequence` | [Agent A SOP] L256、[结构链 ToolSpec] L38/72 要求固定文本；1000～1500 aa 与“超时”共用该链，文本与实际触发原因的记录方式需在 P0-Q07 明确 |
| R-04 复用 | ≤5 突变且 identity≥98%→AlphaFold3；identity<90%/变化>10%→ESMFold2；5～10%→双跑取较高 pLDDT | [科学规则] L76、[Agent A SOP] L246–250；2～5% 区间、条件冲突、双跑一侧失败与相同分数未展开，P0-Q06。该复用缺口不改变 P0 的零突变默认 |
| AlphaFold3 官方排序对照 | 专家卡同时列含 `fraction_disordered` 和 `has_clash` 的官方 ranking_score，要求部署验证简化排序没有选入碰撞模型 | [Agent A SOP] L264、[结构链 ToolSpec] L114；本表不自行更换专家排序公式，也不声称已完成该对比 |
| 文件类型 | `pdb_path` 是 Schema 字段名，并不意味着文件必为 PDB；AlphaFold3 mmCIF 要保留 | [Agent A SOP] L267–270；[结构链 ToolSpec] L58/70 |

## 5. S-09：结构质量评估

| 维度 | 专家口径 | 原文出处 | 对照结论 / 问题 |
|---|---|---|---|
| 输入 | `structure`；按 source 区分实验结构、公共预测结构和本地预测结构，分别读取 method/resolution 或 pLDDT/pTM；低置信掩码读取逐残基 pLDDT | [Agent A SOP] S-09 L285–317；[结构链 ToolSpec] §2c L44–45 | 字段来源明确；缺失/非法数值的完整处理未定义，P0-Q08/Q09 |
| 输出 | `quality{confidence, topology_reliable, low_confidence_regions, warnings[]}`；confidence 为 high/medium/low；掩码同时写 structure 与 quality，消费者读 structure.low_confidence_regions | [Agent A SOP] L286–287、L319–321；[结构链 ToolSpec] L46/61；[Agent A Schema] L113–116 | 双写明确；不能只维护临时 quality。未知来源的 topology_reliable 缺省值未给出，P0-Q08 |
| 执行条件 | S-08 取得可解析预测结构后执行；不新增工具调用。缺逐残基 pLDDT 等情况按待冻结规则处理 | [Agent A SOP] L291–324、L1881–1882；[结构链 ToolSpec] §2c L40–46 | 无结构或不可解析不等于可直接生成 low 质量对象 |
| 科学规则 | 实验结构按 method/resolution 分档；预测结构按 pLDDT 0.70/0.50 分档、pTM 0.50 判可信；无序掩码为 pLDDT<0.50 连续段≥5 aa，相邻段间隔≤3 aa 合并 | [Agent A SOP] L291–321；[科学规则] R-01/R-02 L73–74；[一期环境清单] E-06 L71/79 | 逐条判定见 §5.1；实验边界有冲突，掩码处理细节不完整，P0-Q08/Q09 |
| 失败处理 | 未知来源→confidence='low'+WARNING；AlphaFold DB 无逐残基 pLDDT→medium+WARNING 建议复核、掩码 null；resolution=null 处同时存在 low 与 medium 规定 | [Agent A SOP] L296/305/309/311/323；[结构链 ToolSpec] L86–87、L112 | resolution=null 冲突不能以“保守默认”自行消解，P0-Q08；其他预测源缺均值时不能照搬 AlphaFold DB 特例，P0-Q09 |
| 验收要求 | **低置信区域掩码**：注入低 pLDDT 段，检查≥5 aa、≤3 aa 合并、掩码双写一致、实验结构掩码 null。**结构质量分档**：X-ray 2.5 Å→high；cryo-EM 3.8 Å→medium 且 topology_reliable=true；预测均值 0.60→medium | [结构链 ToolSpec] §6 用例 4/5，L102–104 | 有两个抽象用例；4.0 Å、缺失分辨率、pLDDT 边界与掩码算法须补测，其中冲突项先裁决再固定期望，P0-Q16 |

### 5.1 分档与缺省逐条对照

下表保留原文的区间写法，不将冲突分支改写成可直接执行的规则。

| 条件 | 原文 confidence / topology_reliable | 状态与说明 | 原文出处 |
|---|---|---|---|
| source 为 experimental/user_experimental，X-ray <3.0 Å | high；有分辨率且≤4.0 Å 时 topology_reliable=true | 明确 | [Agent A SOP] L291–296、L306 |
| X-ray 3.0～4.0 Å | 正文写 medium；后续注释却写“X-ray 4.0Å=low” | **冲突：4.0 Å 不能冻结期望** | [Agent A SOP] L295 对 L307–308 |
| X-ray >4.0 Å | low；topology_reliable=false | 明确 | [Agent A SOP] L296、L306 |
| cryo-EM <3.5 Å | high；topology_reliable=true | 明确 | [Agent A SOP] L302–306 |
| cryo-EM 3.5≤resolution≤4.0 Å | medium；topology_reliable=true | 明确，4.0 Å 显式包含 | [Agent A SOP] L304、L306–307 |
| cryo-EM >4.0 Å | low；topology_reliable=false | 明确 | [Agent A SOP] L305–306 |
| X-ray/cryo-EM resolution=null | 方法分支写 low；实验分支末尾和 ToolSpec 失败表写 medium+WARNING | **冲突：是否覆盖方法分支未定义**；实验 topology_reliable 公式在 null 时为 false | [Agent A SOP] L296/305 对 L309；[结构链 ToolSpec] L87；[Agent A SOP] L306 |
| NMR resolution 非 null 且<3.0 Å | high；实验 topology_reliable 公式适用 | 明确，仅覆盖此区间 | [Agent A SOP] L297–306 |
| NMR resolution=null | medium；建议人工参考其他质量信息；topology_reliable=false | 分档明确 | [Agent A SOP] L298–301、L306/309 |
| NMR resolution≥3.0 Å 或其他实验方法 | 未给完整 confidence 规则 | 缺失；不能按相邻方法套用 | [Agent A SOP] L291–309 |
| alphafolddb/af3_predicted/esmfold2_predicted，pLDDT≥0.70 | high | 高档阈值明确；下一行的中档区间端点需统一书写 | [Agent A SOP] L310–314；[科学规则] L73 |
| 同上，pLDDT“0.50–0.70” | medium | 原文未写上界是否排除；0.70 同时触及 high 文本，需确认完整判定顺序 | [Agent A SOP] L312–314；[科学规则] L73 |
| 同上，pLDDT<0.50 | low | 明确；在本 P0 的后果为 S-11 跳过，不能改成跳过 S-04或自动重跑 S-08 | [Agent A SOP] L314、L1885–1892；[算法图] L247/265 |
| 预测结构 pTM≥0.50 / <0.50 或 null | topology_reliable=true / false | 明确；与 confidence 独立 | [Agent A SOP] L315–316；[结构链 ToolSpec] L111 |
| AlphaFold DB 无逐残基 pLDDT | medium+WARNING；low_confidence_regions=null | 已有专门补充；存在均值而没有逐残基数组时与通常均值分档的先后关系待确认 | [Agent A SOP] L311；[结构链 ToolSpec] L112 |
| 未知 source | confidence=low+WARNING，掩码 null；topology_reliable 未赋值 | 部分明确；如何输出 Schema 允许的结构来源及完整质量结果待对齐 | [Agent A SOP] L321–323；[Agent A Schema] L108/116 |

### 5.2 无序掩码的依据与限制

- **已明确**：阈值 `<0.50`、最小连续长度 `≥5aa`、相邻间隔 `≤3aa`、structure/quality 双写；
  实验结构或无逐残基值时为 null。[Agent A SOP] L317–321；[结构链 ToolSpec] L45–46。
- **参数性质**：上述掩码档值进入 E-06 项目经验台账，要求可配置、默认等于规范值，并进行回测；
  本表不把它们写成已完成科学校准的阈值。[一期环境清单] L69–79。
- **仍缺**：先筛长度还是先合并、合并是否跨越高分残基、坐标与数组下标转换、部分结构与
  缺失 pLDDT 的处理、没有命中区段时的空数组约定；归 P0-Q09。例：两个 4 aa 低分段相隔
  2 aa，在不同处理顺序下会得到不同结果，不能由实现者自行选定期望。

## 6. S-04：序列拓扑预测

| 维度 | 专家口径 | 原文出处 | 对照结论 / 问题 |
|---|---|---|---|
| 输入 | `protein{seq}`，序列/FASTA；DeepTMHMM 是序列工具，不要求结构输入，不属于 R-58 结构工具校验清单；默认参数在部署时实测锁定 | [Agent A SOP] S-04 L141–146；[DeepTMHMM ToolSpec] §2 L19–20；[科学规则] L173 | 输入形态明确；空/非法输入的处置原则见 [DeepTMHMM ToolSpec] L69 与 R-48，具体字符支持和解析规范归 P0-Q01，版本与实际默认参数归 P0-Q17 |
| 输出 | `topology{labels[], segments[], has_signal, tm_count, outside_length}`。交付标签为 inside/outside/TMhelix/signal；逐残基序列坐标为 1-based；segments 为 `{type,start,end}`；Schema 的 topology 可为 null | [Agent A SOP] L142/146–150；[DeepTMHMM ToolSpec] L26–28；[Agent A Schema] L123–142 | 正常形态明确；含 P/B 时原生标签的独立承载位置未定义，P0-Q11 |
| 执行条件 | T-01 step2 先对序列调用 S-04，随后才判断是否执行 RSA；结构质量 low 不阻止本步 | [Agent A SOP] L1885–1892；[算法图] L19–21 | 明确；S-05 拓扑筛选不属于当前 P0，不能把预测标签直接变成筛除结论 |
| 科学规则 | 原生 S/O/M/I 对应四种交付含义；P/B 是超域标签。segments 按连续同标签聚合；tm_count 为 TMhelix **区段数**；outside_length 为 outside 残基总数；labels 含 signal 则 has_signal=true | [DeepTMHMM ToolSpec] L13、L26–28；[Agent A SOP] L146–150 | 四标签与派生算法明确；R-20/R-21/R-22 的筛选消费须放在对应消费步骤，不能在 S-04 擅加过滤，见 [DeepTMHMM ToolSpec] L70 |
| 失败处理 | DeepTMHMM 不可用→topology=null+“拓扑预测不可用”WARNING，不 halt。出现 P/B→整步 topology=null、status=unreliable、失败级 WARNING、禁止自动交接并报用户裁决；原生标签保持长度，不丢位置、不缩短、不静默映射。非法输入按 R-48 | [Agent A SOP] L147/152；[DeepTMHMM ToolSpec] L40/48–50/68–69；[科学规则] L172 | 处置明确；null 对象与原生 labels/状态的输出位置须确定，P0-Q10/Q11；null 不能被替换为全 outside/inside |
| 验收要求 | **正常拓扑预测**：labels 长度等于序列长度、四类值域、连续区段与三个派生量一致。**含 N 端信号肽的蛋白**：signal 位于 N 端且 has_signal=true。**DeepTMHMM 不可用**：DeepTMHMM 不可用→null+指定警告。**单跨膜螺旋且具有大胞外域的蛋白**：单 TM 且 outside_length>50 的后续联动。**含周质或 β 链标签的预测输出**：P/B→null/unreliable、保留原生长度、警告、禁自动交接 | [DeepTMHMM ToolSpec] §6 用例 1～5，L54–62 | 原文五例齐全但均抽象；单跨膜螺旋场景涉及 S-16/step22，当前 P0 只验输出事实，跨阶段联动以后续阶段实测闭环，P0-Q16 |

**下游影响只登记、不在 P0 实施**：[DeepTMHMM ToolSpec] L29–32 规定标签供 S-19 热点位置标注、S-16 功能域、
S-27 权限和 T-01 膜蛋白/扫描区门控使用。单 TM 大外侧区域还需要 S-16 交叉验证；
“S-04 已输出标签”不等于已完成这些后续验证。[DeepTMHMM ToolSpec] L38/42/60。

## 7. S-11：SASA / RSA

| 维度 | 专家口径 | 原文出处 | 对照结论 / 问题 |
|---|---|---|---|
| 输入 | 签名为 `structure{pdb_path}`，但 R-58 比对、选链及 buried_fraction 分母都需要原始 `seq`；多链与特殊编号要有可追溯映射 | [Agent A SOP] S-11 L386、L391–397；[FreeSASA ToolSpec] L17–21；[科学规则] L173；[一期边界说明] 第 10 页 | 必需的科学上下文明确，正式输入签名没有承载齐全，P0-Q12 |
| 输出 | 内部变量 `rsa{per_residue[], buried_fraction}`；逐残基值为 [0,1] 的 RSA，可有 null 占位。FreeSASA 原始输出为绝对 SASA，单位 Å²。CandidateRecord 没有独立 rsa 字段 | [Agent A SOP] L387、L394–397；[FreeSASA ToolSpec] L19–22、L62–66、L76 | 内部消费形态明确；P0 阶段输出和审计交付载体待定，不擅自扩充 CandidateRecord，P0-Q14 |
| 执行条件 | `quality.confidence!='low'` 时执行；low 时 `rsa=null`。计算前必须执行 R-58。partial 结构需要按位置降级，不自动等于 low 或全部跳过 | [Agent A SOP] L391–393、L1886–1892；[算法图] L247/265；[FreeSASA ToolSpec] L11/17–22 | 主门控明确；S-09 冲突会改变是否执行本步，依赖 P0-Q08/Q09；R-58 细则仍由 OI-015 承接 |
| 科学规则 | 绝对 SASA 采用残基全表面（主链+侧链）口径；`RSA=SASA(residue)/Theoretical(residue)`，采用 Tien 2013 Gly-X-Gly 表 Theoretical 列；`buried_fraction=count(RSA<0.20)/len(seq)` | [Agent A SOP] L394–397；[FreeSASA ToolSpec] L20–21、L26–55；[科学规则] R-24 L111 | 参考表、单位、0.20 阈值和全长分母明确；不可算值的统计动作、算法参数及超出 [0,1] 的处理未全定义，P0-Q13 |
| 失败处理 | 无法映射的位置保留 null；整体比对失败→失败级 WARNING、unreliable、强制复核；设计链不唯一或插入码无法解析→警告并禁自动交接。未知/非标准残基→RSA=null+WARNING 报用户裁决；原子缺失致不可算→该残基 null+WARNING。若计算返回 None，主链警告并继续，由下游处理缺失 | [Agent A SOP] L391–393、L1888–1890；[科学规则] L173；[FreeSASA ToolSpec] L17–18、L54–55 | 警告/降级要求明确；整体失败与部分空值的界限、工具错误分类及状态载体仍需落实，P0-Q10/Q12/Q13 |
| 验收要求 | 原文要求参考面积数值抽查：丙氨酸（A）129.0、精氨酸（R）274.0、甘氨酸（G）104.0 Å²。其余检查从 R-58、归一化、null 和门控条款推导，见 §9；本卡没有单列完整验收用例章节 | [FreeSASA ToolSpec] §2b L30/31/37/53–56；[Agent A SOP] L391–397 | **已有数值检查点，不等于完整验收方案**；缺具名金标准、浮点容差与边界输入，P0-Q16 |

### 7.1 R-58 必须同时核对的条款

| 条款 | 原文明示 | 尚未给出的可执行细节 | 原文出处 |
|---|---|---|---|
| 序列对应 | 结构序列与输入序列比对；不一致或长度差>0 时按映射表对齐；无法对齐的残基 null 占位 | 比对算法、打分与缺口参数；允许的替换、标签、信号区或截短差异；何时判整体失败 | [Agent A SOP] L391–392；[FreeSASA ToolSpec] L17；关联 P0-Q02/Q12 |
| 多链 | 设计链是与输入 seq 比对一致者；其他链 fixed；链级映射含 chain_id 与 PDB_resSeq；无法唯一确定须禁自动交接 | 完全相同多链、partial、候选同源结构的唯一性规则；model/assembly 选择；固定其他链不等于已决定 SASA 用整个复合物计算 | [Agent A SOP] L393；[FreeSASA ToolSpec] L18；关联 P0-Q12/Q13 |
| 插入码 | 全局 R-58 另要求 resSeq+iCode 唯一识别残基，解析失败须禁自动交接 | 工程映射必须同时保留链和插入码；mmCIF 的作者编号与标准编号转换待冻结，不能只靠 resSeq | [科学规则] L173；关联 P0-Q12 |
| partial | 缺失位置逐残基输出 null+WARNING | 缺失坐标与序列比对覆盖须区分；不可用残基不能删除后缩短数组 | [Agent A SOP] L230–232、L391–392；[FreeSASA ToolSpec] L22/55 |

### 7.2 归一化与内部消费的边界

- 20 种标准残基的锁定分母已完整列于 [FreeSASA ToolSpec] §2b L30–49，使用 **Theoretical** 列，不能改用
  Empirical/Miller/Rose 列，也不能按旧参考表名称替换数值；无需再把“缺整张参考表”作为阻塞项。
- `count(RSA<0.20)/len(seq)` 的分母是全长，不能未经决定改成可计算残基数；null 不能当作 0
  参与阈值比较。null 的统计约定、全数组不可算时如何返回、RSA>1 是否裁剪等仍待 P0-Q13
  明确。[FreeSASA ToolSpec] L21、L53–55；这与“分母已经明确”并不矛盾。
- [FreeSASA ToolSpec] L63–65 明示下游 `burial_score=1−RSA`、末端 10 aa 平均暴露和 R-24 优先序消费，
  它们分别属于 S-16、S-39 或后续筛选，不作为 S-11 新增交付字段或当前 P0 额外计算步骤。
- [一期边界说明] 第 4 页要求表面暴露结果与可用性说明，[FreeSASA ToolSpec] L76 又明确逐残基 RSA 是内部变量、
  扩大交付需裁决。P0 中间状态保存与对外交付的界面必须明确，不能用新增顶层字段默默解决。

## 8. 待确认与待实测问题清单

本轮登记 **17 组问题**。它们包括规则冲突、定义缺口、工程落地和实测准备，不能合称为
“17 个科学规则缺失”。既有 OI 的状态不因本表完成而改变。表内责任是待确认的角色，不表示
已经取得具名答复；原文冲突由用户/专家裁决，工程实现不能代替裁决。

> v0.7 状态覆盖：P0-Q02～Q05 与 S07-EQ-01～05 全部转为
> `DEFERRED_OUT_OF_PHASE1_S07`，不再外发、不再阻塞 P0；OI-018 同步 `DEFERRED`。
> P0-Q01 的离线输入部分迁入 OI-023/P0-V07-M1，其余 Q07～Q17 按当前四步骤继续处理。

> 历史暂行决定（2026-09-02）：P0-Q02 中的 coverage 先采用 query coverage，target coverage 只记录；
> P0-Q03 中有合格 X-ray/cryo-EM 时先取其中最小正 Å，无可比候选时再回退 NMR。两项均为
> 当时为 `PROVISIONAL_USER_APPROVED / EXPERT_CONFIRMATION_PENDING`；现随 S-07 移出一期而延后，
> 不表示原文
> 缺口已由专家关闭。

> 历史暂行决定（2026-09-03，节点 01 内网裁剪前）：P0-Q04 的三项建议也曾由用户批准，包括仅全长精确序列自动采用
> BLAST-derived accession、序列合格后用 organism_name 消歧且剩余并列不自动选择，以及当前
> profile 使用 Swiss-Prot。任务 3/4 共 5 项统一见 [S-07 专家确认问题总表](../../s07/docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md)。

| ID / 类别 | 原文位置与差异 | 需要的明确答复或证据 | 影响 / 责任 / 跟踪 |
|---|---|---|---|
| **P0-Q01** 输入规范；部分明确 | [Agent A SOP] L218、L1816–1827；[DeepTMHMM ToolSpec] L19/69；[一期边界说明] 第 3/4 页。**长度守卫已明确，空/非法输入按 R-48 的原则也已给出**；剩余缺口是具体字符支持、输入解析/规范化与检索物种缺省 | 明确允许字符和特殊字符处置、大小写/空白/FASTA 标题/终止符处理、长度与哈希采用的规范序列，以及目标物种信息缺失时行为；不再要求重新裁决停止/警告条件或另选分析模式 | P0 入口与 S-07/S-04；后端拟定格式规范，涉及科学支持/产品缺省的内容再由对应角色确认；关联 OI-018；讨论更正见 §10.1 |
| **P0-Q02** S-07 可用性；部分明确 | [结构链 ToolSpec] L25/29 与 [Agent A SOP] L391–393。检索允许 >95% 同一性和 partial，R-58 要求结构↔输入一致；序列覆盖不等于坐标覆盖 | **暂行采用 query coverage，target coverage 只记录，待专家确认**；仍需定义比对与多片段合并规则，并确认含替换/截短/未建模位置的命中何时可直接用于后续计算、何时需预测；给 chain/model/assembly 选择与旧分类映射 | S-07→S-08/S-09 及 S-11；算法+后端；OI-018/015；暂行决定见 S07-T3-P01 |
| **P0-Q03** S-07 候选裁决；缺失 | [结构链 ToolSpec] L26 指明 min(正 Å)，但 NMR/null 与不可比方法只要求“单列优先级”；[Agent A SOP] L225–227 取了日期但未定义用途 | **暂行采用 X-ray/cryo-EM 最小正 Å 优先、NMR 无可比候选时回退，待专家确认**；仍需给同分辨率并列、多个 NMR、缺失/非正/异常分辨率、撤回候选、候选元数据部分失败的完整选择表；明确 deposited_date 是否及如何参与选择 | S-07 科学选择与稳定复现；算法/产品；OI-018；暂行决定见 S07-T3-P02 |
| **P0-Q04** AlphaFold DB 与 BLAST；API 实测完成/暂行规则待专家确认 | [Agent A SOP] L228；[结构链 ToolSpec] L28；[一期环境清单] L57–67。任务 4 已完成 BLAST→UniProt REST→AFDB API 往返、一对多、序列不符、无模型和多 isoform 取证 | API 形态已取证；三项建议已获用户批准作为暂行方案，仍需专家冻结 BLAST-derived accession 门槛、物种辅助与一对多裁决、UniProt 子库范围。见 [S-07 专家确认问题总表](../../s07/docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md) | S-07 来源映射；算法+后端；OI-018。当前 API profile 与最终对方服务器本地 profile 必须保持同一契约 |
| **P0-Q05** 无命中与故障；主要形态已实测/路由规则部分待定 | [结构链 ToolSpec] L26 写候选取数“全部失败→AlphaFold DB”，L28/80 写均无是正常；[科学规则] L172 要求故障透明。任务 4 已区分 BLAST 正常零命中、AFDB HTTP 404 无模型与 HTTP 400 非法标识 | 已有来源级状态证据；任务 5 继续定义请求失败、部分结果、预算/时间耗尽、重试/恢复及何时可转下一源或 S-08，不能用一个 null 覆盖全部情况 | S-07 路由与任务恢复；后端+算法/产品；OI-018/017；证据见任务 4 API 报告 |
| **P0-Q06** R-04 复用；缺失 | [Agent A SOP] L240–250；[科学规则] L76。≤5 突变/identity≥98%、变化 5～10%、identity<90% 不能穷尽所有条件；签名缺比较基准 | 对复用接口提供 WT/比较基准、identity 和突变比例计算法、2～5% 区间、绝对数量与比例冲突、双跑一侧失败/同分处置 | 当前 P0 的零突变 AlphaFold3 默认已明确；变体复用前由算法确认，不自行把复用范围写入当前 P0 |
| **P0-Q07** S-08 后处理与降级；部分明确/待实测 | [Agent A SOP] L242、L251–277；[结构链 ToolSpec] L58–60/110–114。标度检测、简化排名的碰撞对比、固定 notes 与实际降级原因仍待落地 | 提供锁定引擎的原始输出证据；确认标度检测方式、缺 Cα/NaN/缺 pTM 或样本分数、均值计算和碰撞模型处置；验证 1000～1500 与 >1500 aa 的 OOM/超时链及固定 notes 的触发原因记录 | S-08 结果可信性与长任务；算法+后端；执行档案关联 OI-017 |
| **P0-Q08** S-09 实验分档；冲突/缺失 | [Agent A SOP] L295 对 L307（X-ray 4.0 Å）；L296/305 对 L309 与 [结构链 ToolSpec] L87（null 分辨率）；NMR≥3.0 Å/其他方法/未知源未完整赋值 | 给无重叠、覆盖所有输入的 method/resolution/source 决策表，明确边界、null/非法值、未知方法和 topology_reliable 输出；给冲突条件的权威修订或具名澄清 | **直接决定 S-11 执行与后续质量门控**；专家（算法）裁决；不得由后端选默认 |
| **P0-Q09** S-09 预测分档与掩码；部分明确 | [Agent A SOP] L311–321；[结构链 ToolSpec] L45–46/112；[一期环境清单] L79。0.70 区间书写重合，AlphaFold DB 无逐残基特例与已有均值先后未写；掩码只有阈值 | 给 pLDDT 均值与数组缺失/不一致/越界处理、0.50/0.70 边界、AlphaFold DB 特例优先级；冻结掩码的长度筛选/合并顺序、坐标制式、无命中空值与 partial 处理，并提供 E-06 回测计划 | S-09/S-11 及后续掩码消费；算法+后端；规则明确后再定测试期望 |
| **P0-Q10** 失败与状态载体；契约差异 | [科学规则] L172、[DeepTMHMM ToolSpec] L50、[Agent A SOP] L1888–1890；[Agent A Schema] L600–610 不含 unreliable，L872/988 又分别写 pipeline失败/任何步骤失败输出 FailureReport | 区分步骤降级、人工复核、全链失败；明确 unreliable/失败级 WARNING/禁止自动交接的机器字段、quality_flags 的 key 与兼容方式；给继续执行与 FailureReport 替代 CandidateRecord 的条件 | 五步共同契约；专家（产品/算法）+后端；与 OI-017/014 协同，不能只靠警告文本路由 |
| **P0-Q11** S-04 标签载体；部分明确/待实测 | [DeepTMHMM ToolSpec] L50/62/68 要求 topology=null 且保留原生 labels；[Agent A Schema] L123–142 只定义四类 labels，无独立原生标签字段 | 明确保留原生标签的内部产物/字段及引用、status 的位置；用锁定版本验证原生标签、区段坐标、序列长度与标签/区段不一致、缺输出的处理；不能把 P/B 塞入四枚举数组 | S-04 输出与降级审计；后端+算法；关联 P0-Q10/Q14 |
| **P0-Q12** S-11 R-58；部分明确 | [Agent A SOP] L386 对 L391–397；[科学规则] L173；[FreeSASA ToolSpec] L17–18。签名缺原始 seq；存在链/残基/插入码要求但无完整比对规范 | 补输入上下文；冻结比对、链唯一性、缺失/替换/插入/标签处理、坐标体系、覆盖与失败阈值、目标位点可映射性、强制复核的状态转移；给对应实测映射报告 | S-11 生产实现与冻结前门禁；算法+后端；**OI-015 保持 BLOCKED** |
| **P0-Q13** S-11 数值口径；部分明确/待实测 | [FreeSASA ToolSpec] L19–22/53–55 规定全表面、归一化与全长分母，但未列算法/探针/半径等参数及 RSA>1 处置 | 冻结算法、探针半径、原子半径集、模型/链与复合物范围、替代构象、非标准原子处理；确认 null 如何参与 count、全空结果、超界/NaN 与浮点误差处理；提供完整参数档案 | RSA 数值与可复现性；算法+后端；全长 len(seq) 分母和参考表已有依据，不另造默认值 |
| **P0-Q14** 中间结果与交付；契约缺口 | [结构链 ToolSpec] L57 的 coverage/partial 不在 [Agent A Schema] L104–121 的定义中；[FreeSASA ToolSpec] L62/66/76 明示 rsa 为内部变量；[一期边界说明] 第 4 页要求暴露与可用性说明 | 明确 P0 中间结果、ArtifactRef/审计产物与最终 CandidateRecord 的边界；确定 coverage/partial、映射报告、原生标签、逐残基 RSA、空值原因保存和交付位置；需新增字段时取得明确版本决定 | P0 阶段契约与后续组装；产品+后端+算法；S-07 部分关联 OI-018，最终模型关联 OI-014 |
| **P0-Q15** 阶段范围；`DECIDED_BY_PHASE1_BASELINE` | 旧资料曾冲突；最新[一期 18 节点图](<../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>)明确 S-06 移出一期、S-11 为第 3 裁剪项 | 范围结论已关闭；当前完整 P0 仍含 S-11。删减触发、profile 名、缺失披露、节点 13 L2/S-12 复扫降级和下游回填另由 OI-020 决定 | **OI-019 DECIDED**；D 包停止外发；OI-020 未关闭前不得实现无 S-11 自动裁剪 profile |
| **P0-Q16** 验收资产；待准备/待实测 | [结构链 ToolSpec] §6、[DeepTMHMM ToolSpec] §6 明示“抽象占位，无真实序列”；[FreeSASA ToolSpec] L56 只给数值抽查点；[一期边界说明] 第 10 页要求缺失与风险说明 | 确定验收样本及其版本、具体输入、期望结果、误差容限、失败/降级用例、评审责任人及签收标准；已有样本按实际名称或数据库编号登记并注明来源，原文没有提供的样本待准备；冲突分支先答复后固定期望 | 五步发布与科学验收；算法/产品+后端；未执行的抽象用例不能标 PASS |
| **P0-Q17** 部署基线；待实测/文句矛盾 | [科学规则] L223；[一期环境清单] L8 一边要求“部署首日实测冻结”，一边称同措辞已废止；工具行仍沿用，版本/资源多未锁 | 澄清部署基线声明；冻结版本/commit/digest、API/模型/数据库版本、运行参数、实际耗时/资源、安装及许可记录；确认 ESMFold2 版本称谓。最终本地库由对方部署团队按 D09 交接验收，当前 P0 API 证据不等待该部署 | 发布/运维与可复现性；后端+专家+对方部署团队；按 OI-017 落地长任务，不将名称或耗时估计视为部署证据 |

## 9. 验收要求与后续补测矩阵

“原文用例”可直接追溯到 ToolSpec 的编号；“规则推导”是为了验证原文要求提出的检查点，
尚未获批为冻结验收方案；“待裁决”不得先写死期望。下列验收场景直接使用工具名称和生物学术语。
专家原文未给出具体序列的场景，实际测试样本待准备。任务 3/4 的来源级取证已执行；完整 S-07
组合验收和其余步骤仍未执行，不能把局部证据标成 P0 科学验收通过。

| 验收场景 | 类型 | 要验证的结果 | 出处 / 前置事项 |
|---|---|---|---|
| 结构获取：实验结构命中、公共预测回退与无结构转预测 | 原文用例/来源级取证已执行 | 任务 3 已取证实验检索/partial；任务 4 已取证 AFDB 回退和正常空结果；任务 5/6 再验证统一路由及正确 source/null | [结构链 ToolSpec] §6 用例 1/2，L96–98；任务 3/4 报告 |
| 结构获取：序列一致性与覆盖率边界、部分覆盖 | 规则推导/任务 3 已执行 | identity=95% 或 coverage=90% 不通过；partial 与坐标覆盖分开。coverage 分母暂行规则仍待专家确认 | [结构链 ToolSpec] L25/29；S07-T3-P01 |
| 结构获取：检索故障与候选选择 | 规则推导/部分已执行 | 任务 4 已区分正常零命中、404 无模型、400 非法标识；不可比方法、并列、服务失败及部分取数继续在任务 5/6 验证 | [结构链 ToolSpec] L26/80；[科学规则] L172；P0-Q03/Q05 |
| 结构预测：AlphaFold3 样本选择与输出解析 | 原文用例 | AlphaFold3 单体最高 pTM、Cα 逐残基归一化、均值一致、mmCIF 原件保留 | [结构链 ToolSpec] §6 用例 3，L100 |
| 结构预测：pLDDT 标度、pTM 缺失与模型碰撞 | 规则推导/待实测 | 已知 0～100 与 0～1 标度各有样例，避免重复除以 100；无 pTM 能力时 null；简化排序碰撞对比 | [Agent A SOP] L242/264/273–277；[结构链 ToolSpec] L110–114；P0-Q07 |
| 结构预测：长序列失败回退与文件格式转换 | 规则推导 | 1000/1500/>1500 aa 长度边界、OOM/超时>2h→ESMFold2、ESMFold2 也失败；PDB 转换失败保持 mmCIF 与正确降级信息 | [Agent A SOP] L251–270；P0-Q07/Q10/Q17 |
| 结构质量：低置信区域掩码与常规分档 | 原文用例 | ≥5 aa/≤3 aa 掩码双写；实验结构掩码 null；2.5 Å X-ray、3.8 Å cryo-EM、均值 0.60 的既定分档 | [结构链 ToolSpec] §6 用例 4/5，L102–104；歧义组合须待 P0-Q09 |
| 结构质量：分档边界、信息缺失与掩码合并 | 待裁决后补测 | X-ray 4.0 Å、缺失分辨率、NMR 未覆盖区间、未知源；pLDDT 0.50/0.70、均值/数组缺失、短低分段合并 | [Agent A SOP] L291–323；P0-Q08/Q09，当前不能固定 PASS 期望 |
| 拓扑预测：逐残基标签与 N 端信号肽 | 原文用例 | 标签长度/四类值域/连续区段/三个派生量一致；signal 的 N 端位置和 has_signal | [DeepTMHMM ToolSpec] §6 用例 1/2，L54–56 |
| 拓扑预测：工具不可用与周质/β 链标签 | 原文用例 | DeepTMHMM 不可用→null+指定警告；P/B→null/unreliable、原生长度保留、禁自动交接 | [DeepTMHMM ToolSpec] §6 用例 3/5，L58/62；先确定 P0-Q10/Q11 的状态与证据载体 |
| 拓扑预测：单跨膜螺旋大胞外域的下游联动 | 原文跨阶段用例 | P0 核对 tm_count=1、outside_length>50 的事实；S-16 交叉验证与 step22 扫描限定在相应阶段闭环 | [DeepTMHMM ToolSpec] §6 用例 4，L60；不把未进入的下游能力列为 P0 已验收 |
| 拓扑预测：非法输入与结果长度不一致 | 规则推导/待实测 | 空/非法输入按 R-48；具体字符是否合法以确认后的支持范围为准；标签与序列不等长、标签与区段不一致有明确失败状态，不用默认标签补全 | [DeepTMHMM ToolSpec] L19/69；[科学规则] L172；P0-Q01/Q11；长度守卫直接采用 SOP 已有条件 |
| 溶剂可及性：参考面积数值核对 | 原文检查点 | Theoretical 参考面积：丙氨酸 129.0、精氨酸 274.0、甘氨酸 104.0 Å²，单位与列选择正确 | [FreeSASA ToolSpec] §2b L30/31/37/56 |
| 溶剂可及性：RSA 归一化与埋藏比例 | 规则推导/待实测 | SASA→RSA 使用锁定分母；0.20 不计入严格 `<0.20` 的埋藏数；全长分母保持；超界值依明确规则处理 | [FreeSASA ToolSpec] L20–21/53；P0-Q13 的算法参数、null 与超界规则先冻结 |
| 溶剂可及性：缺失残基、多链与插入码映射 | 规则推导/待实测 | partial 缺失位置保留 null；插入码、多链及映射失败不会错位或误用；失败级警告与强制复核可观察 | [Agent A SOP] L391–393；[科学规则] L173；[FreeSASA ToolSpec] L54–55；OI-015/P0-Q12 |
| 溶剂可及性：低置信跳过与计算失败 | 规则推导 | 明确 low 时不调用 FreeSASA 且 rsa=null；非 low 时调用；计算 None 时披露原因并触发正确下游降级 | [算法图] L247/265；[Agent A SOP] L1886–1892；S-09 冲突输入待 P0-Q08/Q09 |
| 阶段整体：来源追溯、缺失披露与状态解释 | 共同检查 | 来源/版本/参数可追溯；缺失与失败不得变成正常数值；结构、拓扑、RSA 的状态和原因能按步解释 | [科学规则] R-05/R-48；[Agent A Schema] L698–717、L915–920；[一期边界说明] 第 4/10 页；P0-Q10/Q14/Q17 |

## 10. 本次产物与下一步入口

本表保留原五步骤的六维提取、原文定位、17 组问题登记与验收场景矩阵；当前 P0 只继续使用
S-08/S-09/S-04/S-11 的内容，S-07 部分转历史。未修改专家原件、
生产代码、Mock 或 Dify。任务 3/4 只执行了 discovery 取证；旧九份资料继续由来源快照保存定位
基线，新增一期图由独立来源清单保存哈希，当前专家包继续沿用既有 21 文件哈希清单。

本表先用于历史 [P0 v0.6](P0_IMPLEMENTATION_PLAN_v0.6_ARCHIVE.md)，现已迁入
[P0 v0.7](../p0-v07-plan/P0_IMPLEMENTATION_PLAN.md)并通过[工程评审](../p0-v07-plan/P0_V07_M0_REVIEW.md)。
后续只按当前四步骤适用项收集具名答复和原始工具证据，
回填相应 OI；方案工程评审不解除 OI-015 或生产编码门禁。OI-019 已由后续最新一期范围决定，
未来缩减 profile 仍受 OI-020 阻塞。具体测试样本、序列和数据库编号应在验收资产中注明来源
与版本，并与对应验收场景关联。

### 10.1 讨论更正：P0-Q01 长度守卫（2026-09-02）

用户在逐项讨论中指出：SOP 已清楚规定何时停止、何时警告并继续，不需要重复裁决。
本次复核确认，v0.1 将工具卡的概括表述升级为“规则冲突”，并追加“一期是否开放三种模式”
的问题，扩大了原文缺口。现作提取更正：

- 长度守卫直接依据 [Agent A SOP] T-01 step0a L1816–1827 和 [算法图] L262；保留按已有模式区分的条件。
- 不把 [DeepTMHMM ToolSpec] L69 的概括作为新增长度门槛，不要求用户重复选择原文已有的分析模式。
- 空/非法输入的 R-48 处置原则已有依据；需要进一步明确的是哪些具体字符与格式受支持。
- P0-Q01 的输入主体已由最新决定明确为必填序列、宿主物种和可选结构；解析/规范化先按专家
  文档归并。只有非标准残基等原文确实未闭合且会改变科学结果的细节才定点提交算法专家，
  不再作为宽泛用户问题。17 组历史索引保留；这不是新增科学阈值或生产实施授权。

本次只修改派生对照和讨论记录；九份权威来源的内容与哈希基线未变化，来源快照继续适用。

[算法图]: ../../../../../工作流设计/01-业务依据/T01_算法图_v10_20260821.md
[一期图]: <../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>
[一期边界说明]: ../../../../../工作流设计/01-业务依据/抗原智能体一阶段边界及核心能力说明.pdf
[科学规则]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md
[Agent A SOP]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md
[Agent A Schema]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md
[结构链 ToolSpec]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md
[DeepTMHMM ToolSpec]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_A5_DeepTMHMM_v10.5.md
[FreeSASA ToolSpec]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C34_FreeSASA_v10.5.md
[一期环境清单]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期实施环境清单_v10.5.md
