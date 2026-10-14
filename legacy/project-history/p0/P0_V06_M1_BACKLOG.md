# P0 v0.6 M1 统一 backlog、分类与依赖矩阵

> 工作包：`P0-V06-M1`  
> 当前状态：`SUPERSEDED_BY_P0_V07 / HISTORICAL`  
> 建立日期：2026-09-03  
> 原下一包：`M1-04 工程契约草案`（已取消；当前任务见 [P0-V07-M1](../p0-v07-plan/P0_V07_M1_BACKLOG.md)）  
> 生产状态：`PRODUCTION_ENTRY_BLOCKED / NOT_DEPLOYED`

> 节点 01 内网决定已将 S-07 和数据库检索移出一期。本文件保留为 v0.6 迁移证据，不再是当前
> 执行台账；其中 S-07 外发、候选完整性 M2 和 M1-04 不再执行。

## 1. 用途、范围与停止线

本文曾是 P0-Q01～Q17、S07-EQ-01～05 以及 OI-015/017/018/019/020 的 v0.6 执行台账。它把问题变成
可分派、可追踪、可验收的工作，不替代[权威专家依据](P0_EXPERT_EVIDENCE_MATRIX_MIXED_20260903.md)、
[S-07 专家确认原稿](../../s07/docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md)或[开放项清单](../../../docs/project/OPEN_ITEMS.md)。

当前已完成：

1. `M1-01`：统一 22 个问题索引、负责人角色、状态、门禁、解除条件和验收证据；
2. `M1-02`：建立三类主视图、消重关系、优先级和执行顺序；
3. `M1-03`：形成 A～D 四批、11 个唯一问题材料；其中 A/B/C 的 9 题待专家答复，D 的 2 题已由
   2026-09-03 最新用户范围基线决定，见[分批材料索引](../README.md)。

本轮没有执行 G0，没有冻结 Schema 或科学规则，没有实现生产适配器、OI-017 状态机或真实 Dify
工作流，也没有开始 P1。M1 完成仍须继续 M1-04～M1-06；M2～M6 的适用门禁满足前不得进入 M7，
M7 达到 G1 前不得进入 M8。

## 2. 台账规则

### 2.1 三类主队列

| 代码 | 主类型 | 可以做什么 | 不可以做什么 |
|---|---|---|---|
| `E` | 工程可直接落实 | 起草解析、Schema、状态、ArtifactRef、校验器和 profile 模板 | 选择科学阈值、补写来源优先级或把草案标为冻结 |
| `D` | 需专家/产品决定 | 整理原文、实测影响、暂行建议、替代规则和边界案例，取得具名结论 | 由后端实现者替专家选默认分支 |
| `G` | 需 G0 实测 | 准备并在隔离环境运行冻结输入，保存版本、原始输出、资源、许可和错误证据 | 接入生产/Dify，或把 discovery/smoke 当科学验收 |

“主类型”只表示该索引进入哪个主队列，不表示它没有次级工作。例如 P0-Q11 的主交付是工程载体，
但最终验收仍依赖 DeepTMHMM G0；P0-Q13 的科学参数需先决定，再用 G0 验证。各轨的退出证据必须
分别记录，工程事实和科学决定不能写入同一项“默认实现”。

### 2.2 状态解释

| 状态 | 含义 |
|---|---|
| `READY_ENGINEERING` | 已有足够依据可起草工程契约；产物仍是 review draft |
| `READY_G0_PREP` | 可准备 fixture manifest；尚未运行 G0 |
| `EXPERT_CONFIRMATION_PENDING` | 已有确认问题，等待具名专家/产品答复 |
| `DECISION_REQUIRED` | 需先形成确认材料或取得决定，不能冻结预期 |
| `PARENT_TRACKING_ONLY` | 只聚合子题、依赖和关闭证据，不再生成重复问题 |
| `BLOCKED_BY_OI_015` | R-58 未形成可执行、具名规则 |
| `DECIDED_BY_PHASE1_BASELINE` | 一期范围已由最新用户基线决定；待契约、迁移和回归后验证 |
| `DEFERRED_NOT_APPLICABLE` | 当前零突变 P0 路径不适用；不得悄悄实现未来规则 |

负责人列记录角色，不虚构尚未指定的姓名。获得答复时，按开放项关闭模板补充姓名、角色、日期、
决定版本和证据路径。

## 3. 22 个问题索引唯一台账（M1-01）

“验收证据”列描述关闭该索引必须存在的证据；已有证据会明确写成“已有”，否则均为待形成产物。

| 索引 / 唯一工作范围 | 主类 | 原文来源与现有证据 | 负责人角色 | 当前状态 | 阻塞门禁 | 解除条件 | 验收证据 |
|---|---|---|---|---|---|---|---|
| `P0-Q01` 输入解析、字符、规范化、哈希与输入错误；长度守卫不再提问 | `E` | [依据对照 §8](P0_EXPERT_EVIDENCE_MATRIX_MIXED_20260903.md#8-待确认与待实测问题清单)：Agent A SOP L218/L1816–1827、DeepTMHMM ToolSpec L19/69、一期边界第 3/4 页；§10.1 已更正长度守卫 | 后端负责人；产品/算法仅确认字符支持与物种缺省 | `READY_ENGINEERING` | 五步骤共同输入；M7 | 形成唯一规范序列规则、FASTA/空白/大小写/终止符/特殊字符表、物种缺失行为和稳定错误码；科学支持范围获具名确认 | `InputNormalizationSpec` 草案、Schema、规范化向量、同输入哈希/非法输入拒绝测试；不得出现新长度规则 |
| `P0-Q02` S-07 可用性的剩余边界：比对、多片段、替换/截短/未建模、chain/model/assembly；coverage 子题只由 EQ-01 外发 | `D` | 结构链 ToolSpec L25/29、Agent A SOP L391–393；任务 3 的序列/坐标 coverage 证据；[EQ-01](../../s07/docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md#2-s07-eq-01coverage-到底覆盖哪一边) | 算法负责人 + 后端负责人 | `DECISION_REQUIRED` | M2、M6、M7；OI-018/OI-015 | EQ-01 获答复，并形成比对/多片段/partial/链选择的无歧义 eligibility 与 review 规则 | 具名规则版本、边界决策表、完整/partial/多链/替换样本及映射报告 |
| `P0-Q03` S-07 候选裁决的剩余边界：同分辨率、多个 NMR、异常/缺失值、撤回、元数据部分失败和 deposited_date；NMR 主问题只由 EQ-02 外发 | `D` | 结构链 ToolSpec L26、Agent A SOP L225–227；任务 3/6 的混合方法候选事实；[EQ-02](../../s07/docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md#3-s07-eq-02nmr-与-x-raycryo-em-的优先级) | 算法负责人 + 产品负责人 | `DECISION_REQUIRED` | M2、M7；OI-018 | EQ-02 获答复，并给出覆盖全部可比/不可比、并列和元数据异常的选择表 | 具名排序表、tie/no-comparable/partial-metadata fixtures 和确定性预期 |
| `P0-Q04` S-07 BLAST→UniProt→AFDB 父索引；只聚合 EQ-03～05、API/local profile 等价和候选闭合，不另提总问题 | `D` | Agent A SOP L228、结构链 ToolSpec L28、一期环境清单 L57–67；任务 4 API 9/9、任务 6 交接证据 | 算法负责人 + 后端负责人 | `PARENT_TRACKING_ONLY` | M2、M7；OI-018 | EQ-03～05 均获答复；M2 解除 BLAST 100 条触顶；API 与未来本地 profile 契约不变量明确 | 三项具名答复、完整候选 manifest、profile 对照表、序列/物种/isoform/无模型边界回测 |
| `P0-Q05` 正常无命中、部分结果、复核、预算耗尽、失败、重试与恢复的状态/路由契约 | `E` | 结构链 ToolSpec L26/L28/L80、科学规则 L172；任务 4 已区分零命中/404/400，任务 5 已有非生产结果契约 | 后端负责人；算法/产品确认跨来源与 S-08 转移条件 | `READY_ENGINEERING` | M2、M7；OI-018/OI-017 | 状态矩阵区分正常空、候选不完整、部分失败、全失败、复核、跳过；科学转移条件另获具名确认 | 状态转移表、稳定错误码、零命中/100 条触顶/HTTP 故障/恢复 fixtures；与任务 5 契约差异记录 |
| `P0-Q06` R-04 变体复用规则 | `D` | Agent A SOP L240–250、科学规则 L76 | 算法负责人；后端负责人后续实现 | `DEFERRED_NOT_APPLICABLE` | 不阻塞当前 `mutation_count=0` P0；未来复用前门禁 | 当前契约显式拒绝/排除非零突变复用；未来启用前再确认 WT 基准、区间、冲突与双跑处置 | 当前范围排除记录和非零突变拒绝用例；未来具名复用决策表（本 M1 不冻结） |
| `P0-Q07` S-08 原始输出解析、标度、缺值、碰撞、降级与资源事实 | `G` | Agent A SOP L242/L251–277、结构链 ToolSpec L58–60/L110–114 | G0 执行：后端/平台/运维；科学签收：算法负责人 | `READY_G0_PREP` | M3、M7；OI-017 profile | 锁定 AF3/ESMFold2 版本、模型、容器、许可和 GPU 环境；跑齐正常、长序列、OOM/>2h、缺指标、碰撞和格式转换 | S-08 fixture manifest、原始排名/pLDDT/pTM/mmCIF、资源曲线、失败日志、许可与版本哈希、算法签收 |
| `P0-Q08` S-09 实验结构 method/resolution/source 分档 | `D` | Agent A SOP L295/L307、L296/L305/L309；结构链 ToolSpec L87 | 算法专家 | `DECISION_REQUIRED` | M4、M6、M7 | 形成无重叠且覆盖 X-ray/cryo-EM/NMR/其他/未知、null/非法值和边界的决策表 | 具名规则版本；4.0 Å、null、NMR 边界、未知方法逐行期望和回测清单 |
| `P0-Q09` S-09 预测分档、pLDDT 缺值和低置信掩码算法 | `D` | Agent A SOP L311–321、结构链 ToolSpec L45–46/L112、一期环境清单 L79 | 算法专家 + 后端负责人 | `DECISION_REQUIRED` | M4、M6、M7 | 冻结 0.50/0.70 边界、AFDB 特例、均值/数组顺序、长度筛选与区段合并、空/partial 语义 | 具名伪代码/决策表；E-06、边界、缺失/不等长/NaN/合并样本和确定性预期 |
| `P0-Q10` 步骤降级、人工复核、全链失败和 FailureReport 的产品/科学语义 | `D` | 科学规则 L172、DeepTMHMM ToolSpec L50、Agent A SOP L1888–1890、Agent A Schema L600–610/L872/L988 | 产品负责人 + 算法负责人；后端负责契约映射 | `DECISION_REQUIRED` | M5、M7；OI-017/OI-014 | 具名确认继续、停止、FailureReport、requires_review/unreliable 的唯一条件 | 决策记录、机器状态矩阵、每个终态/降级/复核路径 fixtures；不得只靠 WARNING 文本 |
| `P0-Q11` S-04 原生 P/B 标签、四标签 projection、null topology 与审计载体 | `E` | DeepTMHMM ToolSpec L50/L62/L68、Agent A Schema L123–142 | 后端负责人；算法负责人验收 | `READY_ENGINEERING` | M5、M7；依赖 Q10/Q14 | 草拟独立原生标签 ArtifactRef 和状态字段；再用锁定 DeepTMHMM G0 验证 P/B、长度和区段一致性 | Schema 草案、P/B 原件引用、四标签/P/B/不等长/缺输出测试；原生 P/B 不进入四枚举数组 |
| `P0-Q12` S-11 R-58 输入、比对、链/残基/插入码映射与复核转移 | `D` | Agent A SOP L386/L391–397、科学规则 L173、FreeSASA ToolSpec L17–18 | 算法负责人 + 后端负责人 | `BLOCKED_BY_OI_015` | M6、M7；OI-015 | OI-015 形成具名、可执行的比对参数、允许差异、覆盖/失败阈值、位点可映射性和链选择规则 | OI-015 关闭记录、版本化 mapping profile、完整/partial/多链/插入码/替换报告和金标准签收 |
| `P0-Q13` S-11 FreeSASA 数值与参数口径 | `D` | FreeSASA ToolSpec L19–22/L53–55；A/R/G 和全长分母已有依据 | 算法负责人 + 后端/G0 执行负责人 | `DECISION_REQUIRED` | M6、M7 | 冻结算法、探针、半径集、复合物/链/model、替代构象、非标准原子、null/全空/NaN/RSA>1 规则并实测 | 具名 parameter profile、FreeSASA 版本/命令、原始 SASA、等长 RSA、A/R/G/0.20/异常值回测 |
| `P0-Q14` P0EvidenceBundle、ArtifactRef 与最终 CandidateRecord 的边界 | `E` | 结构链 ToolSpec L57、FreeSASA ToolSpec L62/L66/L76、Agent A Schema L104–121、一期边界第 4 页 | 后端负责人 + 产品负责人；算法审阅字段语义 | `READY_ENGINEERING` | M7；OI-014 只在最终模型变化时介入 | 冻结 P0 内部事实/引用/空值原因位置；CandidateRecord 新字段必须另获版本决定 | P0EvidenceBundle Schema 草案、ArtifactRef/Provenance 示例、P0→Candidate 映射表、缺失/复核/跳过样本 |
| `P0-Q15` S-06 一期归属与 S-11 削减顺位/披露 | `D` | [一期 18 节点新基线](<../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>)；原 D 包保留历史差异 | 用户（产品范围决策）+ 后端负责人 | `DECIDED_BY_PHASE1_BASELINE` | 完整 P0 不再受 OI-019 阻塞；缩减 profile 受 OI-020 阻塞 | S-06 排除、S-11 第 3 削减顺位已决定；默认完整 P0 含 S-11，削减触发/命名/下游另由 OI-020 决定 | OI-019 决定记录、新范围/P0/阶段计划同步；未来缩减 profile 需 OI-020 决定、manifest 和回归 |
| `P0-Q16` 五步骤验收样本、期望、容差、失败/降级和签收 | `G` | 结构链/DeepTMHMM ToolSpec §6、FreeSASA ToolSpec L56、一期边界第 10 页；原文样本多为抽象占位 | fixture 准备：后端/G0 执行负责人；期望与签收：算法/产品负责人 | `READY_G0_PREP` | M2～M6 各适用门禁、M7/G3/G5 | 每个步骤建立冻结输入和版本、样本来源、hash、期望/容差、失败/资源/许可检查及签收人；冲突分支先决定后写期望 | S-07/S-08/S-09/S-04/S-11 fixture manifests、机器预期、原始证据目录和具名签收记录 |
| `P0-Q17` 版本、许可、资源、execution profile、release 与目标服务器交接基线 | `G` | 科学规则 L223、一期环境清单 L8 及工具行；D09 目标服务器交接决定 | 运维/平台 + 后端负责人；算法负责人签收科学版本；接收方部署团队验收本地 profile | `READY_G0_PREP` | M2/M3/M5/M6、M7/G3；OI-017 | 分工具冻结 commit/version/digest、模型/数据库、参数、许可、资源；澄清 ESMFold2 名称；本地 profile 明确包含或排除 | execution/release profile、许可记录、资源报告、预检/回滚清单、目标服务器交接模板；不得把耗时估计当证据 |
| `S07-EQ-01` coverage 分母（Q02 的唯一外发 coverage 子题） | `D` | [专家确认 §2](../../s07/docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md#2-s07-eq-01coverage-到底覆盖哪一边)；任务 3 同一输入 1,333 对 792 entry 的影响 | 算法专家 | `EXPERT_CONFIRMATION_PENDING` | M2、M7；OI-018 | 书面确认 query/target coverage 定义、阈值是否同时要求及边界等号 | 具名答复、规则版本、候选池差异回测；当前 query coverage 方案保持 provisional |
| `S07-EQ-02` NMR 与 X-ray/cryo-EM 优先级（Q03 的唯一外发跨方法子题） | `D` | [专家确认 §3](../../s07/docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md#3-s07-eq-02nmr-与-x-raycryo-em-的优先级)；任务 3 的 537 X-ray/694 cryo-EM/102 NMR | 算法专家 + 产品负责人 | `EXPERT_CONFIRMATION_PENDING` | M2、M7；OI-018 | 书面确认跨方法顺序、仅多个 NMR 时的选择/复核和不可比方法处置 | 具名答复、排序表、混合/仅 NMR/无可比候选回测；当前 min 正 Å 后回退方案保持 provisional |
| `S07-EQ-03` BLAST-derived accession 自动采用门槛（Q04 子题 1/3） | `D` | [专家确认 §4](../../s07/docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md#4-s07-eq-03blast-相似-accession-的使用门槛)；任务 4 O15116 单点差异事实 | 算法专家 | `EXPERT_CONFIRMATION_PENDING` | M2、M7；OI-018 | 书面给出 identity/双侧 coverage/E-value/长度/indel/物种及等号边界 | 具名答复、精确/单点替换/indel/无模型 fixtures；当前只自动采用全长精确序列保持 provisional |
| `S07-EQ-04` 多 accession/model 排序与并列（Q04 子题 2/3） | `D` | [专家确认 §5](../../s07/docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md#5-s07-eq-04多个-accession-或模型怎样选择)；任务 4 三个精确 accession/四 isoform 事实 | 算法专家 + 产品负责人 | `EXPERT_CONFIRMATION_PENDING` | M2、M7；OI-018 | 书面给出 sequence、organism、canonical/isoform、reviewed、质量值顺序和无法唯一时的路由 | 具名答复、同分/跨物种/isoform/歧义回测；当前歧义停止自动选择保持 provisional |
| `S07-EQ-05` Swiss-Prot/UniProtKB 搜索范围与分层停止条件（Q04 子题 3/3） | `D` | [专家确认 §6](../../s07/docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md#6-s07-eq-05uniprot-搜索范围)、一期环境清单与任务 4 API 事实 | 算法专家 + 产品负责人 | `EXPERT_CONFIRMATION_PENDING` | M2、M7；OI-018 | 书面确认数据集、查询顺序、停止条件、候选合并及命中无 AFDB 模型时行为 | 具名答复、版本化 BLAST profile、分层/无模型/零命中回测；当前 Swiss-Prot profile 保持 provisional |

## 4. 消重与索引完整性（M1-02）

22 个索引全部保留用于追溯，但专家外发问题只从唯一子题生成：

| 父索引 | 唯一外发/执行项 | 父索引仍负责 | 消重规则 |
|---|---|---|---|
| P0-Q02 | S07-EQ-01 | 比对、多片段、partial、chain/model/assembly 与 R-58 衔接 | 不再以 Q02 名义重复询问 coverage 分母 |
| P0-Q03 | S07-EQ-02 | tie-break、异常/缺失分辨率、撤回、元数据失败和 deposited_date | 不再以 Q03 名义重复询问 NMR 优先级 |
| P0-Q04 | S07-EQ-03、04、05 | 三答复聚合、候选闭合、API/local profile 等价 | Q04 是父索引，不另发“BLAST/AFDB 怎么办”的总问题 |
| P0-Q10 / Q11 / Q14 | 各自独立 | Q10=状态/继续语义；Q11=P/B 原生标签载体；Q14=P0 与最终模型边界 | 不用一个“Schema 问题”合并三种不同决定 |
| P0-Q12 / Q13 | 各自独立 | Q12=R-58 映射；Q13=FreeSASA 数值参数 | 映射通过不代表数值口径已冻结，反之亦然 |
| P0-Q16 / Q17 | 各自独立 | Q16=验收样本与期望；Q17=版本/许可/资源/部署基线 | smoke/安装材料不得替代科学验收资产 |

P0-Q01 只保留字符、格式、规范化和物种缺省，不再询问 SOP 已明确的长度停止/警告条件，也不
新增分析模式选择。已明确的 PDB 严格 `identity>95%`、`coverage>90%`、正 Å 取最小值、normal
no-hit 与 ToolError 区分等事实，不作为新问题重复提交。

## 5. 三类分类视图（M1-02）

每个索引只在下表出现一次；次级依赖回到 §3 查看。

| 主队列 | 索引 | 数量 | 当前动作 |
|---|---|---:|---|
| `E` 工程可直接落实 | P0-Q01、P0-Q05、P0-Q11、P0-Q14 | 4 | M1-04 起草输入、状态/错误、P/B ArtifactRef 和 P0EvidenceBundle；只产出 review draft |
| `G` 需 G0 实测 | P0-Q07、P0-Q16、P0-Q17 | 3 | M1-05 先准备 S-07/S-08/S-04/S-11 manifests，不在 M1 执行真实 G0 |
| `D` 专家/产品决定类 | P0-Q02、Q03、Q04、Q06、Q08、Q09、Q10、Q12、Q13、Q15；S07-EQ-01～05 | 15 | Q15 已由最新基线决定；其余按 M1-03/后续阶段确认，Q04 不单独外发，Q06 当前路径延后 |
| **合计** | **P0-Q01～Q17 + S07-EQ-01～05** | **22** | 无遗漏；外发问题已消重 |

## 6. OI 与里程碑依赖矩阵

本表只建立关联，不改变开放项状态。

| 依赖/门禁 | 当前状态 | 关联索引 | 直接影响 | 本 M1 的退出要求 |
|---|---|---|---|---|
| `OI-015` R-58 | `BLOCKED` | Q02、Q12、Q13、Q16、Q17 | M6、M7；S-11 不得生产实现 | M1-03 形成确认包，M1-05 准备映射/FreeSASA fixture；保持 BLOCKED |
| `OI-017` 异步框架 | `DECIDED`，实现/profile 未完成 | Q05、Q07、Q10、Q14、Q17 | M7 profile、M8 状态机/AwaitJob/恢复 | M1-04 只准备状态机与 profile 模板；参数留给 G0，不实现生产底座 |
| `OI-018` S-07 检索契约 | `IN_REVIEW` | Q01～Q05、Q14、EQ-01～05 | M2、M7 | 五项外发包、候选完整性 gate、S-07 状态/契约草案均可追踪；不关闭 OI |
| `OI-019` P0 范围 | `DECIDED` | Q15 | 当前完整 P0 不再受其阻塞；待迁移后 VERIFIED | 用户已确认 S-06 排除、S-11 为第 3 削减项；D 包停止外发 |
| `OI-020` 削减 profile | `BLOCKED` | Q15、Q17；节点 13 L2/S-12 复扫 | 仅阻塞未来缩减 profile；不阻塞默认完整 P0 | M1-04 只定义 capability/status 占位；触发、命名和下游语义待产品/算法决定 |
| `EXEC-S07-CANDIDATE-COMPLETE` | `BLOCKED_BY_BLAST_100_CAP` | Q04、Q05、Q16、Q17；OI-018 | M2；自动选择和 G1 | 只在 M1 登记冻结输入、complete/capped 语义和 M2 解除证据，不在本轮执行 M2 |
| 输入共同契约 | `READY_FOR_DRAFT` | Q01、Q05、Q10、Q14 | M7 与五步骤 | M1-04 草案区分正常空、复核、降级、失败、跳过和恢复 |
| S-08 G0 | `NOT_STARTED` | Q07、Q16、Q17；OI-017 | M3→M7 | M1-05 manifest 覆盖版本/许可/GPU/长序列/失败/资源 |
| S-09 决策 | `BLOCKED_BY_Q08_Q09` | Q08、Q09、Q10、Q16 | M4→M6/M7 | M1-03 取得可外发的决策表问题；未答复前不冻结期望 |
| S-04 G0 | `NOT_STARTED` | Q01、Q10、Q11、Q16、Q17 | M5→M7 | M1-05 manifest 覆盖四标签、P/B、许可、版本和错误 |
| S-11 G0 | `BLOCKED_BY_OI_015` | Q08、Q09、Q12、Q13、Q16、Q17 | M6→M7 | M1-03/05 分开准备规则确认与 G0 输入；OI-015 未解前不做生产适配器 |
| `P0-V06-M7` G1 | `BLOCKED_BY_M2_TO_M6` | 全部适用索引 | M8 生产实现 | M2～M6 各适用决定和 G0 均满足；Q06 以当前零突变明确排除 |

依赖顺序为：

```text
M1 backlog / 确认包 / 契约草案 / G0 manifests
  -> M2 S-07 候选完整性
  -> M3 S-08 G0
  -> M4 S-09 决策与验证
  -> M5 S-04 G0
  -> M6 S-11 G0
  -> M7 汇总适用门禁并达到 G1
  -> M8 才允许生产底座与五步骤适配器
```

M2、M3、M5 的取证准备可以并行；实际编辑同一规则/profile 时按其依赖顺序合并。M7 必须等待
M2～M6 的全部适用门禁，不以单个步骤通过替代整阶段 G1。

## 7. 优先级与执行顺序

### 第一优先级

1. `P0-Q01`：先完成公共输入解析、字符、规范化、哈希和稳定输入错误草案；
2. `S07-EQ-01～05`：沿用现有暂行建议形成第一批专家材料，不重复 Q02/Q03/Q04 父问题；
3. `P0-Q08/Q09`：形成 S-09 无重叠分档与掩码确认包，直接解除 M4 的决定输入阻塞；
4. `EXEC-S07-CANDIDATE-COMPLETE`：M1 只准备 M2 的冻结输入、profile 和证据要求，M2 再解决
   BLAST 100 条触顶。

### 第二优先级

1. S-08：Q07/Q16/Q17，准备 AF3/ESMFold2 版本、许可、硬件、短/长/失败输入；
2. S-04：Q10/Q11/Q16/Q17，准备 DeepTMHMM 版本、许可、四标签及 P/B/不等长输入；
3. S-11：OI-015、Q12/Q13/Q16/Q17，分开准备 R-58 决策和 FreeSASA 参数/数值取证。

### 第三优先级

1. OI-017：只准备生产状态机和逐工具 execution profile 模板，实际数值等待 G0；
2. OI-019/Q15 已由最新一期基线决定；OI-020 继续承接缩减 profile 的触发、命名和下游语义；
3. Q17：准备 P0 release manifest 和目标服务器交接模板骨架，不声明任何 profile 已部署。

## 8. M1 子包状态与下一动作

| 子包 | 状态 | 本文或后续交付 | 完成判定 |
|---|---|---|---|
| M1-01 统一任务台账 | `COMPLETED` | 本文 §3、§6 | 22 项均有来源、类型、负责人角色、状态、门禁、解除条件和验收证据 |
| M1-02 问题分类与排期 | `COMPLETED` | 本文 §4、§5、§7 | 17+5 索引无遗漏；父子关系消重；三类、优先级和顺序明确 |
| M1-03 专家确认材料 | `COMPLETED_MATERIAL_READY / A_B_C_RESPONSES_PENDING / D_DECIDED` | [A～D 分批材料](../README.md) | A/B/C 共 9 题待专家；D 共 2 题由最新用户范围基线决定并停止外发 |
| M1-04 工程契约草案 | `READY_NEXT` | 待形成 Schema/契约变更清单 | 不填造科学规则；正常空、复核、降级、失败、跳过可区分 |
| M1-05 G0 取证准备 | `NOT_STARTED` | 待形成 S-07/S-08/S-04/S-11 manifests | 每个样本有 ID/hash；正常、边界、失败、资源、许可、版本齐全 |
| M1-06 评审与文档同步 | `BLOCKED_BY_M1_04_M1_05` | 待形成 M1 评审记录并完成最终状态同步 | backlog 完整、文档检查和 116 项测试通过；不误写 G1/部署/科学验收完成 |

M1-03 已按四批形成材料：A=`S07-EQ-01～05`，B=`P0-Q08/Q09`，C=`OI-015 + Q12/Q13`，
D=`OI-019 + Q15`。A/B/C 材料完成不表示专家答复已取得；D 已由最新用户范围基线决定，不再外发。
Q10 的产品状态决定可在 M1-04 作为契约确认附包，Q06 保持当前路径不适用。

## 9. M1-01/M1-02 验收记录

| 检查 | 结果 |
|---|---|
| P0-Q 索引 | 17/17，各出现一个主台账行 |
| S07-EQ 索引 | 5/5，各出现一个主台账行 |
| 三类主视图 | `E=4`、`G=3`、`D=15`，合计 22 |
| 重复问题 | 0；Q02/Q03/Q04 与 EQ 子题按 §4 分工 |
| OI 关联 | OI-015/017/018/019/020 全部进入依赖矩阵；OI-019 已决定，OI-020 新增且只阻塞缩减 profile |
| M1-03 分批材料 | A=5、B=2、C=2 共 9 题待专家；D=2 已由用户决定；父项不重复提问 |
| 生产边界 | M1 保持 `NOT_DEPLOYED`；未开始 G0、M2、生产适配器、真实 Dify 或 P1 |
| 提前文档回归 | `scripts/check_docs.py` PASS；61 个 Markdown 文件 |
| 提前测试回归 | `pytest -q` PASS；116 项 |

最终 M1 文档检查、116 项测试和状态入口复核属于 M1-06。提前回归通过不把 M1-04～M1-06
标记为完成，也不表示专家已经答复、G1 或科学验收通过。
