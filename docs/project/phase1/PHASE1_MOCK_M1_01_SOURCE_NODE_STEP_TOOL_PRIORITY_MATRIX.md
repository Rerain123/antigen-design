# PH1-MOCK-M1-01 来源—节点—S 步骤—工具—优先级矩阵

> 状态：`COMPLETED`  
> 日期：2026-09-04  
> 适用基线：`T01-PHASE1-18NODE-OFFLINE`  
> 交付边界：仅规格归并；未编写 Mock 代码、Dify DSL 或生产适配器，未运行科学工具。

## 1. 结论与使用边界

- 当前一期业务节点集合严格为 `N01`～`N18`，共 18 个，无缺号、无重复、无新增节点。
- 设计适用性 Gate 与“不适合设计”的 WT 交付路径是节点间控制语义，不是 `N19`，也不是旧
  `P0-P7` 阶段。
- 默认 profile 是完整一期。当前未批准任何 reduced profile；削减顺序只记录为
  `N16 → N07 → N02/S-11`，不在本任务中启用。
- 下表中的工具是一期目标映射，不代表已安装、已验收或已部署；生产状态统一保持
  `NOT_DEPLOYED`。
- 本矩阵只冻结“来源、成员关系、S/T 步骤归属、工具归属和优先级”。稳定节点注册表、输入输出、
  状态枚举、边和重算状态机分别留给 `PH1-MOCK-M1-02`～`M1-04`。

优先级采用一期语义，不沿用旧 checklist 的 `P0a/P0b/P0c` 作为当前阶段：

| 标记 | 含义 |
|---|---|
| `MUST` | 默认完整一期必须落地；无具名范围变更不得移除 |
| `PROTECTED_KEEP` | 甲方或物理计算链点名保留，不进入削减顺序 |
| `CUT_POOL_1/2/3` | 仅表示若将来具名批准 reduced profile 时的固定削减次序；当前仍包含 |
| `CONDITIONAL` | 业务条件控制是否执行，不等于从一期 profile 删除 |

## 2. 来源登记与权威顺序

| 来源 ID | 来源 | 本矩阵中的用途 |
|---|---|---|
| `SRC-01` | [一期 18 节点最新范围原件](<../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>) | 决定节点成员、主流程、工具主清单、一期排除项、优先级和削减顺序 |
| `SRC-02` | [节点 01 内网决定记录](../sources/PHASE1_NODE01_OFFLINE_SOURCE_20260903.json)与[会议截图](<../../../工作流设计/01-业务依据/一期节点01内网裁剪会议截图_20260903.png>) | 覆盖 `SRC-01` 的 N01 外部查询部分：删除 S-07、RCSB PDB、AlphaFold DB 和联网回退，保留本地 AF3/ESMFold2 |
| `SRC-03` | [Agent A SOP v10.5](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md) | 决定保留步骤的函数名、调用点、复用关系和工具细节；只用于未被 `SRC-01/02` 排除的内容 |
| `SRC-04` | [Agent A SKILL v10.5](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md)与[权威资料索引](../../../工作流设计/01-业务依据/README.md) | 核对工具编号、职责和当前 ToolSpec 入口 |
| `SRC-05` | [一期实施环境清单](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期实施环境清单_v10.5.md) | 核对一期工具、纯计算步骤、本地数据与明确不部署项；与后续用户决定冲突处由 `SRC-02` 覆盖 |
| `SRC-06` | [Agent A Schema v10.5](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md) | 核对 N18 的 CandidateRecord、AgentCHandoff、FailureReport 与 MethodSummary 载体 |
| `SRC-07` | [T-01 算法图 v10](../../../工作流设计/01-业务依据/T01_算法图_v10_20260821.md) | 只补充新图未改写的 T-01 步骤顺序和工具调用细节；不得恢复旧阶段或已排除能力 |
| `SRC-08` | [当前一期范围基线](../PHASE1_SCOPE_REBASELINE.md) | 项目化交叉检查，不反向覆盖原件 |
| `SRC-09` | [新一期 Mock 决定记录](../sources/PHASE1_MOCK_BASELINE_DECISION_20260904.json) | 约束新 Mock 使用 `N01-N18` 独立命名空间，旧 P0-P7 仅作冻结历史参考 |

适用顺序为：最新用户决定 `SRC-02/09` → 最新一期图 `SRC-01` → 当前专家包
`SRC-03/04/05/06` → 未被覆盖的历史细节 `SRC-07` → 派生交叉检查 `SRC-08`。旧 Mock、旧
P0-P7 计划和旧场景不作为本矩阵来源。

## 3. 18 节点矩阵

| 节点 | 一期能力 | 当前 S/T 步骤映射 | 当前一期工具/资源映射 | 当前优先级 | 权威来源与边界 |
|---|---|---|---|---|---|
| `N01` | 结构获取与质量 | 甲方本地结构摄取/解析为入口责任；无结构时 `S-08 predict_structure`；随后 `S-09 assess_structure_quality`。`S-07 fetch_structure` 明确排除，S-07c 只作为本地文件解析细节参考，不升格为一期节点步骤 | 科学工具：本地 `C12 AlphaFold3`、`C11 ESMFold2`；输入解析辅助：`C1 BioPython`（PDB/CIF/mmCIF）；S-09 为后端纯计算。禁止 `C3 RCSB PDB`、`C4 AlphaFold DB`、C6 搜索和联网补齐 | `MUST` | `SRC-01` + `SRC-02` 覆盖；`SRC-03` S-08/S-09；[结构链 Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md)仅适用 S-08/S-09 与本地文件解析条款 |
| `N02` | 结构基础分析 | `S-04 predict_topology`；`S-11 compute_rsa` | `A5 DeepTMHMM`；`C34 FreeSASA` | 节点 `MUST`；其中 S-11=`CUT_POOL_3`，当前完整 profile 仍执行；未来削减对 N10/N13/N17 复用链的影响须由 OI-020 定义 | `SRC-01/03/05`；[A5 Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_A5_DeepTMHMM_v10.5.md)；[C34 Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C34_FreeSASA_v10.5.md) |
| `N03` | 文献表位检索 | `S-03 query_iedb_prior` | `C20 IEDB 本地镜像` + `C6 BLAST+`，只访问批准的本地镜像/索引 | `MUST` | `SRC-01/03/05`；[C20 Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C20_IEDB镜像_BLAST_v10.5.md) |
| `N04` | B 细胞表位预测 | `S-17 predict_bcell_epitopes` | `A3 BepiPred 3.0` 线性路径；`A4 DiscoTope` 不进入一期 | `MUST` | `SRC-01/03/05`；[A3 Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_A3_BepiPred_v10.5.md) |
| `N05` | T 细胞表位预测 | `S-18 predict_tcell_epitopes` | `A1 NetMHCpan 4.2` + `A2 NetMHCIIpan 4.3`；`A6 IEDB Immunogenicity` 不进入一期 | `MUST` | `SRC-01/03/05`；[A1/A2 Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_A1_NetMHCpan_v10.5.md) |
| `N06` | 表位地图合成 | `S-19 compute_epitope_density` 的当前语义是“三图合成 + E0-E4 证据分级”，不得按旧函数名缩减为单一密度值 | 无新增外部工具；MCP/后端纯计算，消费 N03/N04/N05 与 N02 拓扑输出 | `MUST` | `SRC-01`；`SRC-03` S-19/T-01 step6；`SRC-05` 纯计算说明 |
| `N07` | 糖基化扫描 | `S-12 scan_glycosylation` | `C1 BioPython` 正则/序列计算 | `CUT_POOL_2`；当前完整 profile 仍包含；未来削减是否同时移除 N13 的 S-12 复扫须由 OI-020 定义 | `SRC-01/03/05` |
| `N08` | 同源收集与保守性 | `S-13 collect_homologs` → `S-14 compute_conservation` → `S-15 extract_conserved_regions` | S-13：`C0 本地病原数据库`、`C1 BioPython`、`C6b MMseqs2`、`C6 BLAST` 对批准的本地 nr、`C5 MAFFT`；S-14 复用 S-13 产生的同一次 MSA 做纯计算，不重复对齐；S-15 纯计算 | `MUST` | `SRC-01/03/05/07`；所有数据库访问均受当前本地数据边界约束 |
| `N09` | 功能域识别 | `S-16 identify_functional_domains` | `C2 本地 UniProt 数据`、`C1 BioPython`；复用 S-04 拓扑；结构坐标检测为后端计算。不得以 UniProt REST 作为运行时 fallback | `MUST` | `SRC-01/02/03/05`；[UniProt Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_UniProt注释接口_v10.5.md)仅保留与本地部署兼容的 S-16 条款 |
| `N10` | 原蛋白可开发性基线 | `S-36 predict_solubility`、`S-36a compute_expressibility`、`S-37 predict_aggregation`、`S-38 predict_ph_stability`、`S-39 assess_tag_exposure`、`S-40 assess_developability` | `C44 CamSol-reimpl`、`C1 BioPython/ProtParam`、`C45 AGGRESCAN3D/序列备选`、`C24 PROPKA`；S-39 复用 S-11 RSA，S-40 为后端纯计算 | `PROTECTED_KEEP` | `SRC-01/03/05`；[C44 Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C44_CamSol重实现_v10.5.md)、[C45 Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C45_AGGRESCAN3D_v10.5.md)、[C24 Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C24_PROPKA_v10.5.md) |
| `N11` | 候选序列设计 | `S-27 design_mutations` | 主引擎 `C15 ProteinMPNN`；当前 SOP/Spec 中 `objective='thermostability'` 时可条件复用 `C43 ThermoMPNN` 产生推荐位点。`C16 SolubleMPNN` 明确不进入一期 | `MUST` | `SRC-01/03/05`；[C15 Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C15_ProteinMPNN_v10.5.md)、[C43 Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C43_ThermoMPNN_v10.5.md)。C43 条件路径是否可达由后续请求契约约束，不新增节点 |
| `N12` | 设计验证 | `S-28 validate_design`；`S-29 check_conservative_mutations`；全淘汰时按当前 SOP 返回 N11 受控重算 | `C18 ESM-IF1`；结构复核复用 `C12 AlphaFold3`/`C11 ESMFold2`；S-28 的 mutation burden 与 S-29 为后端纯计算；重算重新调用 N11 工具 | `MUST` | `SRC-01/03/07`；[C18 Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C18_ESM-IF1_v10.5.md)、结构链 Spec。循环上限和状态契约由 M1-03 固化 |
| `N13` | 表位保护验证 | `T-01 step19`；复用 `S-11/S-17/S-18/S-19` 完成 L1-L4，复用 `S-36/36a/37/38/39/40` 做候选可开发性复评，并执行 `S-12` 糖基化复扫。不得恢复 step19 中已裁剪的 S-23 | `C34 FreeSASA`、`A3 BepiPred 3.0`、`A1/A2 NetMHCpan/NetMHCIIpan`、`C44`、`C1`、`C45`、`C24`；其余比较与合成为后端纯计算 | `MUST` | `SRC-01` 的 N13 具体计算清单优先；`SRC-03` step19 仅保留未被裁剪部分；对应各 ToolSpec |
| `N14` | 候选稳定性打分 | `T-01 step19b`，内部复用 `S-31 scan_stability_mutations` 的 variants/BuildModel 模式并由 `S-40` 汇总 | `C35 FoldX 5.0 BuildModel`，设计基座固定为原始 WT；此模式不调用 ThermoMPNN | `PROTECTED_KEEP` | `SRC-01/03/05`；[C35 Spec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C35_FoldX_v10.5.md) |
| `N15` | 综合排序 | `T-01 step20`：Hard Filter → Pareto → 目标权重 → 双层多样性 → SC-10 | 无外部科学工具；MCP/后端确定性计算，序列 identity 可复用 `C1 BioPython`。因 S-23 已裁剪，不得伪造 safety/host-homology 生产者或过滤结果 | `MUST` | `SRC-01` 的 N15 现行计算清单优先；`SRC-03` step20 仅保留有一期生产者的维度；`SRC-05` 纯计算说明 |
| `N16` | 密码子优化 | `S-30 optimize_codons`；仅显式提供 `expression_host` 时执行 | `C17 DNA Chisel` + `C1 BioPython` | `CUT_POOL_1` + `CONDITIONAL`；当前 profile 保留，条件跳过不等于范围削减 | `SRC-01/03/05`；`host_species` 与 `expression_host` 的独立性仍受 OI-004 约束，禁止相互推断 |
| `N17` | 原蛋白稳定性参考扫描 | `S-31 scan_stability_mutations` 的 WT/PositionScan 模式 | `C35 FoldX 5.0 PositionScan` + `C43 ThermoMPNN` 单体交叉引擎；条件不满足时的状态语义由 M1-03 固化 | `PROTECTED_KEEP` | `SRC-01/03/05`；C35 Spec、C43 Spec |
| `N18` | 结果组装与交付 | `S-42 assemble_candidate_json` → `S-43 assemble_agent_c_handoff` → `S-44 handoff_to_agent_c` | 后端纯组装；`C7 Pydantic` 隐式 Schema 校验；Agent C 是交付目标而非已部署科学工具 | `MUST` | `SRC-01/03/06`；S-44 接口、认证和幂等仍为 OI-013，S-42 完整字段仍为 OI-014，不得伪造已接通 |

## 4. 跨节点控制锚点

本节只登记来源归属，避免把控制点误建成第 19 个业务节点；完整边和状态图由
`PH1-MOCK-M1-03` 交付。

| 控制点 | 来源归并结论 |
|---|---|
| 设计适用性 Gate | 位于 N10 之后；无独立 S 步骤、无独立工具、不是业务节点。真实判定规则受 OI-021 约束；Mock 只能由具名场景提供后端固定结果 |
| WT 直接交付 | Gate 判定“不适合”时不执行 N11-N17，携带 WT 评估与原因进入 N18；不能把 N11-N17 伪装成成功 |
| N12 受控重算 | N12 验证全淘汰时返回 N11；当前 SOP 已描述最多两轮追加设计，正式状态、计数和停止枚举由 M1-03 固化 |
| N16 条件 | `expression_host` 明确提供才执行 S-30；未提供时应形成条件跳过事实，具体状态枚举由 M1-03 固化 |
| N16/N17 汇合 | N15 后分向 N16、N17，两者都汇入 N18；N18 必须区分完成、条件跳过、失败和未执行 |

## 5. 排除项与来源差异处置

| 项目 | 发现的来源差异 | 本矩阵处置 |
|---|---|---|
| N01 外部结构查询 | 环境清单和结构链 Spec 仍保留 S-07/C3/C4/C6 旧条款 | `SRC-02` 是后续用户决定，明确覆盖；N01 只保留本地结构输入、S-08 和 S-09，外部查询成为负向断言 |
| N09 UniProt 访问形态 | SKILL/ToolSpec 曾写 API/本地二选一，当前项目决定要求数据库型能力使用批准的本地数据包 | N09 只映射本地 UniProt 数据；不得公网 REST fallback。专家原件保留不改写 |
| S-14 与 MAFFT | SOP 的 S-14 工具行写 C5 MAFFT，环境清单又说明 S-14 为纯计算 | 按同一文件的复用契约归并：S-13 运行一次 MAFFT 并产 MSA，S-14 复用该 MSA 计算，不启动第二次对齐 |
| N13 变体安全复评 | 旧 T-01 step19 包含 S-23，最新一期图明确裁剪 S-23 | N13 不调用 S-23，并在交付中披露“一期未评估”；不生成伪安全结果 |
| N15 安全/宿主同源过滤 | 旧 step20 可消费 S-23 字段，但一期没有 S-23 生产者 | 相关过滤维度一期不执行；只保留最新图明确仍有生产者的计算维度 |
| 削减项的跨节点复用 | N02/S-11 同时被 N10、N13、N17 消费，N07/S-12 又被 N13 复扫；最新图只给出削减顺序，未定义跨节点降级后的完整语义 | 当前只允许完整 profile；首次启用削减前由 OI-020 明确影响、状态、披露与补回，不在本矩阵猜测 |
| N11 条件 ThermoMPNN | 最新图节点框只列主引擎 ProteinMPNN；当前 SOP、环境清单和 C43 Spec 均保留 thermostability 条件调用，且最新排除清单未排除 C43 | 作为 S-27 内部条件工具保留，不新增节点；是否可达由后续 `objective` 请求契约决定 |
| N05 MHCflurry | SKILL A1 工具行并列提到 MHCflurry，但最新图、S-18 SOP 工具行、环境清单与 A1/A2 Spec 均未把它列为一期调用点 | 不映射到 N05；这只是成员归并结果，不新增排除决策 |
| N18 Agent C | SOP 描述了 S-44 动作，但当前没有接口冻结或部署证据 | 只映射步骤责任；接口保持 `NOT_DEPLOYED`，由 OI-013/014 后续收敛 |

以下能力不进入任何 N01-N18 当前工具映射：`S-07`、`S-06`、`S-23`、`S-32/MD`、
`0b` 上下文注入、分支 4 稳定性补救、`A4 DiscoTope`、`A6 IEDB Immunogenicity`、
`C16 SolubleMPNN`、`C29/C30`。它们不得因仍出现在 SOP、ToolSpec 或冻结旧 Mock 中而回流一期。

## 6. 覆盖验收

| 检查 | 结果 | 证据 |
|---|---|---|
| 节点集合 | `PASS` | `{N01, N02, N03, N04, N05, N06, N07, N08, N09, N10, N11, N12, N13, N14, N15, N16, N17, N18}` |
| 节点数 | `PASS` | 18 |
| 缺号/重复/新增 | `PASS` | 缺号 0；重复 0；`N19+` 0 |
| 优先级覆盖 | `PASS` | 13 个 `MUST` + 3 个 `PROTECTED_KEEP` + 2 个节点级削减池；另有 N02/S-11 组件级 `CUT_POOL_3` |
| 默认 profile | `PASS` | 完整一期；未启用 reduced profile |
| 旧范围回流 | `PASS` | 无 P0-P7 阶段映射；明确列出全部一期排除能力 |
| N01 离线修订 | `PASS` | S-07/C3/C4/C6 外部检索均未映射，本地 AF3/ESMFold2 保留 |
| 实现越界 | `PASS` | 本任务只新增/更新规格与状态文档；未新增 Mock 代码、Dify DSL 或生产实现 |

## 7. 后续交接

- `PH1-MOCK-M1-02` 以本矩阵的 18 行建立唯一节点注册表，但不得把工具名或 T 层控制点当作新节点。
- `PH1-MOCK-M1-03` 固化 Gate、WT 分支、N12 重算、N16 条件和 N16/N17→N18 汇合状态。
- `PH1-MOCK-M1-04` 处理 OI-004/OI-023 的请求字段，并保持本矩阵已登记的本地数据与 N01 离线边界。
- OI-013/014、OI-021、OI-022 未因本矩阵完成而关闭；后续规格不得用猜测值填补。
