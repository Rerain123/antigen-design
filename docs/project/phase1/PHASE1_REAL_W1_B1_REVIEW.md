# W1-08B1 本地结构与映射限定评审

本评审将“文件能否完整读取”“序列位置能否形成映射候选”“结果是否具备科学使用资格”分别判断。
任务要求见 [评审准备包](PHASE1_REAL_W1_B1_REVIEW_BACKLOG.md)，当前进度及下一任务见 [STATUS](../STATUS.md)。
[机器评审](PHASE1_REAL_W1_B1_REVIEW.json)记录放行边界；[本轮证据](../../../discovery/t01-phase1-real/w1/b1-review-20260905/README.md)记录实际检查。

## 1. 结论与使用范围

| 对象 | 本地证据支持的结论 | 完整工具放行仍需什么 |
|---|---|---|
| ingest_structure 摄取 | 可完整解析既有支持域，保留原件/原格式、MODEL/链/残基清单，明确摄取链与实际读取失败；可以继续输入预检、原始元数据提取的工程补强 | 生产输入支持域；S-07c 来源适用范围；原子缺失比例口径；目标环境复现与适用 G1 |
| map_structure 映射 | 实体位置或唯一顺序子序列可以生成待核验候选；partial、作者编号、iCode 和多链诊断有可复核样例 | 一般替换/插入/片段的比对方案；构象/模型适用选择；样本科学核验与 verified 决定登记；消费者自身验收 |

本次完成的是 B1-01～04 的准备与限定工程评审。没有算法负责人签收，未将完整 B1 G1 写成通过，
未启用正式 B1 Worker。已有 Python/CLI 运行层 A 的资格不会自动传递到科学适配器。
可以继续的工程工作已列入 [B1 前置工程补强](PHASE1_REAL_W1_B1_ENGINEERING_BACKLOG.md)。

## 2. 原件归并与输入支持域

来源简称：SKILL＝[Agent A SKILL](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md)，
SOP＝[Agent A SOP](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)，
结构卡＝[结构预测获取链 ToolSpec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md)。
全部 22 份当前专家原件及后续用户决定均按 [source_manifest](../../../工作流设计/02-数据契约/phase1-real-v0.1/b1-review/source_manifest.json)留 hash。

| 字段/情况 | 已有依据与适用范围 | B1 工程边界/未决处 |
|---|---|---|
| protein_sequence、host_species | [节点 01 用户决定](../sources/PHASE1_NODE01_OFFLINE_SOURCE_20260903.json)：必填；结构可选 | 序列由用户提供，结构提取出的序列不能覆盖它；结构来源物种不能覆盖 host_species |
| 序列语法、hash | [M1-04 §4.2/4.4](PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md)：规范化 A-Z、非空、无换行 UTF-8 hash；仅传输语法 | B1 请求接收已规范化序列；原始请求另留字节。AA20 是当前候选方法可直接核对的集合，不能据此批准所有工具的生产字母表 |
| 短序列 | SOP T-01 0a：<9 aa 且 both/tcell_only 失败；bcell_only 警告；9～29 aa 警告 | 属于业务流程守卫，不能改成解析器的统一最小长度；3 aa 人工案例仅验证地址和文件，不能作为有效一期业务输入 |
| 无本地结构 | 后续用户决定保留 AF3/ESMFold2 | N01 交预测分支；不向 ingest_structure 提交空结构或检索请求，不用上传结构替代预测引擎验收 |
| 本地 PDB/CIF/mmCIF | SOP S-07c、结构卡 §2d：检测格式、保留原格式、不强制转换 | 草案分别保存声明格式与内容检测结果；不一致须诊断。压缩包、PDB ID、URL、自由路径不属于本地已登记 ArtifactRef |
| chain=AUTO | SOP S-07c 步骤 3 引用 S-07b：第一条 protein chain，排除 DNA/RNA/ligand，多蛋白链警告 | 只产生 chain_used/auto_selected 摄取观察；不表示该链是科学设计链 |
| 显式 chain | SOP S-07b/c：使用指定链 | 不存在/非蛋白链须明确诊断，不回退 AUTO。现有探针只给候选侧 mismatch；正式摄取预检待工程补齐 |
| 多 MODEL | S-07c 要求可追踪摄取；原件没有通用代表模型选择规则 | 保存所有 MODEL，区分 0-based model_index 与文件 model_serial；候选必须显式选择多 MODEL 的索引。选择不是科学批准 |
| 设计链与 fixed 链 | SKILL R-58；SOP S-11：全部蛋白链中按输入序列核验，不能唯一确定则 failure 级警告、复核和禁交接 | 摄取选择和设计链选择分开。即使显式指定 A，两条相同目标链仍保留歧义；其余链不能为了映射方便被删掉 |
| partial/null | SKILL R-58；FreeSASA §2/2b | 长度始终等于输入序列；缺失结构位置为 null，不缩短/补零；缺失残基不等于缺原子比例 |
| 作者编号、label、iCode | SKILL R-58；ProteinMPNN §2；FoldX §2a | 位置 1-based；作者 chain/resSeq/iCode 保留。label 仅定位，不替代作者身份。负编号、42/42A 有实测 |
| 非整数 auth_seq_id | FoldX §2a 的 43A 示例与真实 mmCIF 字段需区分 | 当前探针明确“不支持”；不能把合法格式能力缺口说成用户文件必然损坏，也不能静默拆成 43+iCode A，见 B1-E01 |
| 非标准/未知残基 | SKILL R-48；FreeSASA §2b：原名保留，不能用 G/0 兜底；适用输出 null+警告 | 当前探针 one_letter=null，候选可能 unreliable；此事实不定义 B/J/O/U/X/Z 的全工具科学支持域 |
| altloc/占有率 | R-58 要求身份核验；完整构象选择策略未给出 | 全部记录，候选带复核；不因占有率最高就自动挑选或对坐标求平均 |
| 实验/预测来源 | SOP S-07c 的 Router 场景输出 user_experimental；Schema structure.source 另有实验/预测枚举；S-09 按来源分流 | 当前 N01 接收的可选文件不自动具有“用户实验结构”身份。保存用户声明和文件原始字段，来源解释待 B1-A02；不由 B-factor 猜 pLDDT |
| 原子缺失比例 | SOP S-07c 步骤 5、结构卡 §2d：>20% 警告已有依据 | 未给完整原子模板/分母/末端与 H/D/altloc/非标准处理；比例保持 null，不能把“不知道”记成 0 |
| Biopython 版本 | 环境清单 §1a、结构卡 §1：专家未锁版本 | 本地证据使用 1.88；这是候选环境实测，不改专家版本原件，不自动批准目标服务器环境 |

S-07/S-07b 的外部查询已被用户节点 01 决定覆盖；只继承 S-07c 对 AUTO 选择的明确引用，不恢复下载入口。
原件检索未给出 R-58 通用 mismatch/gap 评分或接受阈值；S-03 同源检索、S-13/14 MSA 的阈值不能搬来充当 R-58 标准。

## 3. 接口草案怎么连接

草案在 [b1-review](../../../工作流设计/02-数据契约/phase1-real-v0.1/b1-review/README.md)，保持协议 0.1.0。
request/result Schema 及两组示例可独立校验；都标记 DRAFT_REVIEW_ONLY，尚未作为运行层 A 的可执行 payload 登记。

| 内容 | 请求/结果约定 |
|---|---|
| 公共输入 | run_id/request_id、规范化 sequence/hash、host_species、本地 structure_artifact、declared_format、selection、source_declaration |
| 摄取请求 | tool_id=ingest_structure；inventory_artifact=null；只解析已登记原结构，不接命令/URL/路径 |
| 映射请求 | tool_id=map_structure；必须引用前序摄取产生的 inventory_artifact；其所属 run、结构 hash、模型范围须与本请求一致 |
| 摄取输出 | outcome=parsed，结果文件为结构清单；ingestion_observation 仅含 chain_used/auto_selected/model_index/seq_extracted；mapping_status=null |
| 映射输出 | outcome=candidate，结果文件使用现有 mapping.schema.json；mapping_status 只能 unverified/unreliable，科学 review=null |
| 失败输出 | outcome=rejected，error_code 非空，无正常 output_artifact 或 ingestion_observation；原文件留存，诊断不改写为正常结构 |
| 文件绑定 | ArtifactRef 与 A 同结构；输入原件挂 run，输出挂 job+attempt；精确请求字节/序列/结构 hash 关联，两组示例的身份是人工教学身份，不是服务签发 |
| 来源与科学字段 | source_declaration 是用户声明；unresolved_metadata.source/plddt/missing_atom_fraction 均 null，scientific_disposition=not_evaluated；不补 confidence、RSA 或 verified |

结构清单文件沿用探针 0.1.0：format/parser/models/chains/residues、原始与解析原子数、实体表、原始 metadata。
每个残基保留作者链、resSeq、iCode、hetero_flag、原名/标准单字母或 null、altloc、原子名，以及 label_asym/seq/entity。
原始坐标仍由原结构文件承载；清单不是重新生成的结构。映射文件的字段、候选方法和复核载体沿用
[公共映射规范](../../../工作流设计/02-数据契约/tool-interface-v0.1/structure_mapping/README.md)，本次没有修改该规范或历史交接包。

B1 的 INPUT_UNSUPPORTED、FORMAT_MISMATCH、PARSE_FAILED、SELECTION_REQUIRED/NOT_FOUND 是草案的局部诊断码；
未来适配层需在评审后映射到统一 job 错误/科学状态，不向 A 的既有 job Schema 静默增加状态或错误码。
文件不适用与映射不唯一也不同：后者可保留候选诊断文件，但不能产生正常科学消费结果。

## 4. 样本、预期与实际验证

[expected_cases.json](../../../discovery/t01-phase1-real/w1/b1-review-20260905/expected_cases.json)在执行前写入，
[assessment.json](../../../discovery/t01-phase1-real/w1/b1-review-20260905/assessment.json)逐项记录实测。
预期来自明确文件编辑、已有独立序列/编号核对及专家失败边界；没有把同一算法复算当独立科学金标准。

- 真实本地样本仍只有历史授权复用的 1UBQ、5XZC；甲方真实样本和独立留出未新增。
- 文件实测覆盖 PDB/CIF 作者与 label 关系、42/42A、重复缺失、替换/插入、实际双 MODEL、显式选择、AUTO 与设计链不同、错误请求链、altloc、MSE、非整数/缺失 auth 字段和破损格式。
- 复用前批已标注人工派生的实体缺失第 75 位、替换冲突、越界 label、两条同源链、唯一目标链+上下文，以及多字符作者链。没有再次运行 FreeSASA。
- 原始 1UBQ 全文件为 660 个原子，其中蛋白 602、水 58；本次摄取不预先剥水。5XZC 保持受限多链案例。
- 23 个案例均符合声明的工程预期：20 个解析/候选记录、3 个明确解析拒绝；成功候选仍未批准。源码与旧证据保持原字节。

这些检查实际读取文件、生成候选并核对地址/长度/状态，不调用生产适配器、模型、服务器或 Dify。
业务长度守卫、来源解释、原子完整性科学预期尚未执行，不能从人工短序列案例推导科学通过。

## 5. OI-015/023 剩余项的定点关闭条件

| 子项 | 具体问题与影响 | 主责及需要的关闭材料 |
|---|---|---|
| B1-M01 / OI-015 | 结构与输入存在替换、插入、片段关系时，什么比对与接受条件可用于 R-58 | 算法提供适用方法/参数/接受域与具名预期；工程实现后用留出及歧义反例验证。当前 exact/entity 候选不构成通用答案 |
| B1-M02 / OI-015 | 多 MODEL、altloc/占有率怎样选择，是否按工具区别处理 | 算法明确科学计算基座与构象规则；工程保留原件/选择记录并做消费者回归。用户选择不等于 G1 |
| B1-M03 / OI-015 | 哪些真实候选可签发 verified，凭什么允许哪个工具消费 | 算法验收样本/映射表；服务端登记决定来源、版本、结构/序列 hash 和适用消费者；禁止客户端改字段自批准 |
| B1-E01 / OI-015 | 字符型作者 ID、iCode、多字符链如何无损进入工具 | 后端先保留原始字段与一一对应关系，证明无碰撞；工具适配验证可表示性。原义不明的 43A 样例再定点交算法，不擅自字符串拆分 |
| B1-A01 / OI-023 | A-Z 中非常规字母在各工具上的支持与科学处置 | 算法/工具负责人给 B/J/O/U/X/Z 等支持矩阵及失败/复核口径；已有 DeepTMHMM 单个 X 输入成功不能代替全工具规则 |
| B1-A02 / OI-023 | 可选上传文件的来源声明、文件方法/分辨率与预测置信度冲突如何解释 | 后端保留 PDB/MMCIF 原字段及来源位置；算法确定来源资格和冲突处理，连接 B3 S-09。结构来源物种仍不等于用户宿主 |
| B1-A03 / OI-023 | >20% 缺原子比例的模板、分母和 H/D/末端/altloc/非标准边界 | 算法给可执行统计对象与独立边界样本，工程复算 20% 两侧及 null；阈值已知，不再追问阈值本身 |

非整数作者 ID 的处理不需要先指定新的比对阈值。wwPDB 将 auth_seq_id 定义为可非数值的作者标识，
iCode 另有字段，见 [auth_seq_id](https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_atom_site.auth_seq_id.html) 与
[pdbx_PDB_ins_code](https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_atom_site.pdbx_PDB_ins_code.html)。
这是格式依据；FoldX 原件 §2a 的 43A 对照例保留原意和原文，不自动推广成所有文本作者 ID 的拆分算法。

OI-015/023 保持 IN_REVIEW；B1 范围内的工程字段、来源位置与案例已收窄，但整体关闭仍需上表材料。
FreeSASA G76 出域、S-09 六项算法确认，以及后续 FoldX/ProteinMPNN 等消费门禁保持各自范围。

## 6. 下一步与验证入口

继续 [B1 前置工程补强](PHASE1_REAL_W1_B1_ENGINEERING_BACKLOG.md)：输入文件预检、选择诊断、PDB/mmCIF 原始元数据出处和无损作者地址记录。
这属于原 W1-03/W1-07 的准备工作，可以在本机完成；正式 W1-09B1 仍等适用资格评审。
科学规则可按上表一次性向算法负责人定点确认，本任务没有代替用户发送消息或填写专家签名。

只读校验、重新解析和负测命令见 [运行手册](../../development/RUNBOOK.md#w1-08b1-评审准备复核)。
最终回归结果见 [维护验证](PHASE1_REAL_W1_B1_VERIFICATION.json)。
