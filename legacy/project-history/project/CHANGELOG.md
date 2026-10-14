# T-01 项目状态变更记录（历史快照）

> **非当前入口。** 本文保留清理前的详细状态叙事；当前事实、阻塞和下一步只看 [STATUS.md](../../../docs/project/STATUS.md)。

> 更新时间：2026-09-03  
> 当前阶段：Dify/Mock v0.1 工程基线已冻结；一期 18 节点图及节点 01 内网修订已生效。
> 当前输入为目标蛋白序列+宿主物种+可选结构；无结构时执行 S-08 AlphaFold3/ESMFold2，
> 再进入 S-09→S-04→按条件 S-11；
> `P0-V07-M0` 已完成，下一包 `P0-V07-M1`，尚未开始生产适配器编码。
> AI 接手入口：[P0 阶段资料索引](../p0-v07-plan/README.md)。

## 环境快照

- 操作系统：Windows + Docker Desktop/WSL2。
- 本地 Dify：1.17.0。
- Mock MCP：Streamable HTTP，宿主机 `0.0.0.0:8101/mcp`。
- Dify 容器地址：`http://host.docker.internal:8101/mcp`。
- provider 标识：`t01-mock-mcp`。
- 工具：56 个 T-01 工具、3 个作业工具、4 个 Mock 控制工具，共 63 个。
- Mock 场景：25 个；当前只允许 `execution_mode=mock`。
- 本地状态库：`var/t01-mock.sqlite3`。

## 已完成

### 权威资料整理

- 用户在后续会议中根据甲方仅有内网、不能联网搜索的条件，决定删除节点 01 的 RCSB PDB 与
  AlphaFold DB 搜索，只保留 AlphaFold3/ESMFold2。后续明确：内网只影响外部数据库查询，
  不影响部署在甲方服务器上的两种模型正常运行；输入为目标蛋白序列、宿主物种和可选结构。会议截图已原样归档，哈希与
  决定见[节点 01 来源记录](../../../docs/project/sources/PHASE1_NODE01_OFFLINE_SOURCE_20260903.json)。
- 该决定将 S-07 及其 BLAST→UniProt→AFDB 回退移出一期；OI-018 转 `DEFERRED`，S-07 任务 1～6、
  五项暂行规则和候选完整性问题转历史/未来恢复材料。专家资料已给出主要输入字段、PDB/CIF/mmCIF
  及结构解析规则；OI-023 转 `IN_REVIEW`，由工程侧归并，不再等待用户重新定义。
- [P0 v0.7 实施方案](../p0-v07-plan/P0_IMPLEMENTATION_PLAN.md)及
  [工程评审](../p0-v07-plan/P0_V07_M0_REVIEW.md)已经完成；v0.6 原样归档。
- 用户于 2026-09-03 明确确认[一期 18 节点范围重基线](PHASE1_SCOPE_WITH_P0_MAPPING_20260903.md)
  替换旧一期范围。原始图已原样归档到业务依据目录，并登记
  [来源、哈希与决策清单](../../../docs/project/sources/PHASE1_SCOPE_SOURCE_20260903.json)；源文件与归档副本
  SHA-256 均为 `EE4A3E5DFA85F9E19EDA60EDB46BFD6735A2233CBD4D94038D6100A7C66E3F87`。
- 新基线决定一期范围、落地优先级、裁剪顺序和明确排除项；旧算法图、一期边界 PDF 与
  Agent A v10.5 当前专家包继续作为保留节点的科学细节和历史证据，不能反向覆盖新一期范围。
- 博士提供的 Agent A v10.5 当前文件集位于
  [业务依据修订版目录](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902)，
  完整保留 21 个交付文件的原名、字节和包内相对关系。
- [权威业务资料索引](../../../工作流设计/01-业务依据/README.md)已同步上述优先级；保留节点的
  科学细节在并列原件间冲突时仍须登记并由用户裁决。
- 已建立 [P0 范围重基线](../p0-v07-plan/P0_SCOPE_REBASELINE.md)：区分“一期”“P0 阶段”和
  “P0a/P0b/P0c 优先级”；最新 v0.3 将 P0 收敛为必填序列/宿主物种、可选结构及 S-08/S-09/S-04/S-11。
- OI-019 已按最新范围决定关闭：S-06/PSORTb 不进入一期，S-11 是第三裁剪项。当前默认完整
  P0 仍包含 S-11；未来缩减 profile 的触发条件、命名、降级和回填语义由 OI-020 阻塞。
- 已建立[当前四步骤专家依据对照表](../p0-v07-plan/P0_EXPERT_EVIDENCE_MATRIX.md)，覆盖输入、输出、
  执行条件、科学规则、失败处理、验收要求；九份权威资料以章节/行号或 PDF 页码定位，并保存
  [来源快照](../p0/P0_EXPERT_EVIDENCE_SOURCES_20260902.json)。21 个专家原件哈希复核通过。
- 对照表状态为 `EXTRACTED_UNDER_NODE_REVIEW`：登记 17 组冲突、缺口及待实测问题，区分原文
  验收用例与建议补测，按具体工具和生物学场景说明检查要求。S-09 分档、R-58、状态载体与验收资产尚待确认；
  对照提取完成不代表科学验收、生产契约或部署完成，OI 状态保持不变。
- 逐项讨论已更正 P0-Q01：SOP 的长度守卫明确，直接按既有条件停止或警告继续；不再作为
  待裁决项，也不追加分析模式选择。该更正已写入对照表，Q01 仅保留输入规范与缺省信息的缺口。
- 按用户最新要求，对照表 v0.3 采用具体来源、工具与验收场景名称，取消前版的匿名化表述；
  专家原文没有提供的真实测试序列和样本信息仍待验收准备时补齐，科学条款与既有讨论结论不变。
- 用户进一步明确：先依据专家已写清楚的规则建设，工程调查和准备由工程执行，具体矛盾再整理
  确认。已形成 [S-07 任务、交付与验收安排](../../s07/docs/archive/p0/S07_IMPLEMENTATION_TASKS.md)，将工作
  分成六项，旧 17 组索引不再作为要求用户逐项作答的清单。
- 已复核 S-07 五个代表观察对象的 24 处文件引用，23 个独立原始文件的大小和登记哈希全部一致；
  [证据复用清单](../../s07/docs/archive/p0/S07_EVIDENCE_REUSE_20260902.json)只证明材料完整性。任务 3/4 后续
  已分别补做 PDB 检索/结构读取和 BLAST→UniProt→AFDB API 取证；完整 S-07 科学验收仍未执行。
- 已完成 S-07 任务 2 的[API 运行与目标服务器部署交接方案](../../s07/docs/archive/p0/S07_LOCAL_DATA_AND_RUNTIME_PLAN.md)：
  盘点现有 PDB/BLAST/UniProt/AlphaFold DB 资产，定义 API 运行证据、数据关系及目标服务器本地化
  的版本化发布与验收要求。新建 `p0-s07-task2-fixture-20260902-a` 单条隔离库，11 项机器检查通过，验证
  UniProt FASTA→BLAST accession→AlphaFold DB v6 文件关系。该结果为 `PASS_FIXTURE_ONLY`；
  完整 PDB/UniProt/AFDB、MMseqs2 和目标 Linux 服务器仍未部署；这些本地化工作由对方部署团队
  在最终交付时执行，不是用户工作站或当前 API 取证的前置任务。
- 任务 2 发现 BLAST 数据库与 taxdb 必须绑定发布；该要求保留给目标服务器本地 profile。专家
  资料未规定 UniProt 搜索采用 Swiss-Prot、TrEMBL 或两者，也未规定多 accession 的选择。
- 已完成 S-07 任务 3 批次 `p0-s07-task3-mmseqs-20260902-a`：固定并校验 MMseqs2
  18-8cc5c，下载同日 wwPDB 2026-08-29 序列与 entry 索引，在 1,093,472 条 protein chain
  上检索 4 条冻结输入；严格后筛得到 2,466 个 query-chain 候选，entry 元数据连接缺失为 0。
- 任务 3 的 10 个严格边界、分辨率和多链受控用例全部通过。6Q00 序列/坐标覆盖为 76/76；
  9R2Q 的 TP53 序列覆盖为 100%，但 K/L/M/N 每条链实际坐标只映射目标 200/393，正确标为
  `partial`；多链歧义直接按 R-58 禁止自动交接。
- 用户已决定先采用[专家确认问题总表](../../s07/docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md)中的任务 3 两项建议：
  coverage 使用 query 作分母、target coverage 只记录；有合格 X-ray/cryo-EM 时取其中最小正 Å，
  无可比候选时再回退 NMR。两项均标记 `PROVISIONAL / EXPERT_PENDING`，等待用户向专家确认，
  不得据此标记 `VERIFIED` 或生产冻结。完整证据见
  [任务 3 报告](../../s07/discovery/p0/s07/p0-s07-task3-mmseqs-20260902-a/reports/TASK3_EVIDENCE_REPORT.md)。
- 已完成 S-07 任务 4 API 批次 `p0-s07-task4-uniprot-afdb-20260902-a`：通过 EMBL-EBI BLAST、
  UniProt REST 和 AlphaFold DB API 完成 9/9 项证据检查，覆盖既有/BLAST-derived accession、
  正常零命中、合法 accession 无模型、非法标识、序列不一致、一对多和多 isoform。报告见
  [任务 4 API 证据](../../s07/discovery/p0/s07/p0-s07-task4-uniprot-afdb-20260902-a/reports/TASK4_API_EVIDENCE_REPORT.md)。
- 任务 4 收敛出 BLAST-derived accession 门槛、多 accession/model 选择和 UniProt 搜索范围
  三项问题；用户已决定采用报告建议作为暂行工程方案。任务 3/4 共 **5 项**均已统一到
  [S-07 专家确认问题总表](../../s07/docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md)，状态为
  `PROVISIONAL_USER_APPROVED / EXPERT_CONFIRMATION_PENDING`。
- 用户已恢复任务 5，并于 2026-09-03 完成[内部结果、错误与追溯契约](../../s07/docs/archive/p0/S07_TASK5_RESULT_CONTRACT.md)、
  JSON Schema、文件/恢复说明和[验证报告](../../s07/discovery/p0/s07/p0-s07-task5-contract-20260903-b/reports/TASK5_CONTRACT_VALIDATION_REPORT.md)。
  b 批次的 19 个结果场景、20 个非法状态拒绝检查、7 个文件/恢复检查全部通过；本次收尾
  只读复核 19 份结果和 252 个内容对象，136 个来源文件均与任务 3/4 清单一致。
- 任务 5 验证了同长度损坏的哈希检测、缺失文件、不可覆盖、重复读取、输入绑定、保留前次失败的
  重试以及真实 mmCIF 解析失败。真实 BLAST 正命中达到 100 条上限时明确标为未收集完整，
  与使用受控完整候选集的成功路由分开。结果为 `PASS_OFFLINE_CONTRACT_ONLY`，无新在线调用。
- 任务 6 的[非生产独立验收与 P0 交接](../../s07/docs/archive/p0/S07_TASK6_ACCEPTANCE_AND_HANDOFF.md)已完成。
  权威批次 `p0-s07-task6-acceptance-20260903-c` 在固定 wwPDB/MMseqs2 发布和当前官方 API 上
  取得 10/10 项 PASS，复核完整候选、mmCIF、O15116 回退、任务 5 恢复及 S-08/S-09 交接形状；
  生产适配器、下游消费者和 OI-017 仍为 `NOT_DEPLOYED/NOT_IMPLEMENTED`，五项专家问题不变。
- 用户曾于 2026-09-03 明确 P0 按 API 查询；该口径已被后续节点 01 内网裁剪决定替代。当前
  一期不查询或部署 RCSB/AlphaFold DB/S-07 检索链，也不进行 BLAST→UniProt→AFDB 回退。
- 已完成[专家二次交付差异审阅](../expert/EXPERT_V10_5_REVISION_REVIEW_20260902.md)：
  16 个文件未改、4 个变化、1 个新增；实质补充集中在 CamSol 方法。P0 五步骤非空白规则正文
  未改；该次审阅当时未解除 OI-019，后续已由 2026-09-03 最新一期范围决定关闭。SOP
  缩进/引用残片及 I_pat 计数表述已列为反馈问题，未改科学实现。
- 用户已决定专家包只保留当前修订版；旧版目录和临时接收副本已移除。21 个当前文件再次通过
  SHA-256 校验；AGENTS.md、索引和 P0 范围引用已统一。差异报告和旧哈希只作历史证据，
  不恢复旧包、不把保留一套文件误认为科学问题已经全部解决。

### 契约与 Mock MCP

- 建立 `StepRequest`、`StepResult`、`ArtifactRef`、`ToolError` 和 Provenance 契约。
- 实现 63 个 MCP 工具入口、25 个确定性场景和统一错误分类。
- 实现 SQLite 运行状态、幂等结果和异步作业状态模拟。
- 实现 Streamable HTTP MCP 冒烟测试。

### Dify 工作流

- 8 个正式阶段 DSL 已生成、绑定、导入并发布为 Workflow Tool。
- 8 个一键 Debug 工作流已生成并导入。
- `T01_Master_v10` 已绑定 P0-P7。
- 修复 Dify 1.17 的 MCP `json` 数组问题：P3/P4 显式导出标量 `stage_route`。
- P0-P7 的独立 Mock 路线已通过。

### Master 回归

- 批次：`master-reg-20260831-a`。
- 场景：25；通过 25；失败 0。
- Dify 父子 Workflow/节点证据：2496 条。
- 正常、降级、停止、跳过、救援、重试、耗尽、MD 和三类故障路径均已覆盖。
- 报告：`dify/regression/runs/master-reg-20260831-a/report.md`（本地忽略目录）。
- 基线：[Dify/Mock v0.1](../../full-t01-mock-v0.1/dify/regression/BASELINE_v0.1.md)。

### P0-M0、P0-M1 与 P0-M1B

- 旧 [P0 科学工具实施方案 v0.5](../p0/P0_IMPLEMENTATION_PLAN_v0.5_ARCHIVE.md)曾由 wing（开发者）
  完成开发评审；现已标记为历史方案，六工具范围和 M0→M11 不再授权实施。
- 已完成 S-07 campaign `p0-s07-discovery-20260901-a`：5 个公开输入、57 次 HTTP/CLI
  exchange、236 个小型证据文件、5 个代表候选和 5 份逐候选序列—坐标映射。
- 已固定并校验 NCBI BLAST+ 2.17.0、2026-08-22 wwPDB protein FASTA、BLAST DB v5
  与 taxdb；4 个输入均保存 archive、tabular 和 JSON 结果。
- 已实测区分 exact entity、目标片段、同源模板、AFDB exact model、HTTP 204 空结果、
  accession 不支持和网络/CLI 故障；P0-DISC-005 未被误判为科学上的“无可用同源结构”。
- 退出证据见 [P0-M1 总结](../../s07/discovery/p0/s07/p0-s07-discovery-20260901-a/reports/P0_M1_SUMMARY.md)、
  [候选 manifest](../../s07/discovery/p0/s07/p0-s07-discovery-20260901-a/reports/candidate_structure_manifest.json)、
  [映射报告](../../s07/discovery/p0/s07/p0-s07-discovery-20260901-a/reports/sequence_mapping_report.json)和
  [能力缺口表](../../s07/discovery/p0/s07/p0-s07-discovery-20260901-a/reports/capability_gap_table.md)。
- discovery 未接入 MCP/Dify，所有真实科学工具仍为 `NOT_DEPLOYED`。
- 已形成 [S-07 契约评审稿](../../s07/docs/archive/p0/S07_CONTRACT_REVIEW.md)：用 outcome + selection 替代模糊布尔值，
  分离逐来源状态、候选层级、sequence alignment、coordinate mapping、ArtifactRef、分页/去重、
  复合追溯和 ToolError；同时把开发确认与算法/产品科学确认拆成两包。
- 已建立持续更新的 [S-07 决策汇报](../../s07/docs/archive/p0/S07_DECISION_REPORT.md)，面向项目负责人汇总
  18 项决定、当前 10 项旧确认结果、8 项旧待确认事项和原 P0-M2 门禁；后续按专家资料重新定级。
- P0-M1 实测暴露的问题原登记为 OI-018 `IN_REVIEW`；节点 01 内网决定后已转 `DEFERRED`。
  评审稿和证据继续保留，但不再定义当前 P0 Schema；未修改 MCP、Mock 或 Dify。
- 已完成 P0-M1B 最终批次 `p0-s07-m1b-20260901-d`：57 次来源调用全部执行成功；RCSB 5 个
  查询完整展开 19 页；RCSB/AFDB 代表产物和 4 组 BLAST archive/TSV/JSON 均已保存。
- P0-M1B 审计清单统计 285 个非报告文件、23 类文件、约 11.5 MiB；调用记录完整性问题为 0，
  HTTP/CLI 非空 stderr 为 0。分页、entry/entity 层级、19 组请求副本重复和在线来源版本缺口已经
  形成 D09 的最终服务器本地化证据，见
  [P0-M1B 执行记录](../../s07/docs/archive/p0/S07_M1B_RUN_RECORD.md)。
- wing 已于 2026-09-02 根据上述证据确认 D09：自动取得完整轻量候选、重型结构按需读取；候选
  与文件分别去重；最终服务器本地 profile 使用不可修改的版本化数据库；文件分五类并执行
  差异化保留。2026-09-03 澄清当前 P0 先走 API，该本地部署由对方团队执行。本决定没有确认
  科学分类、结构选择、来源优先级或生产参数数值。
- 历史 [P0 科学工具实施方案 v0.6](../p0/P0_IMPLEMENTATION_PLAN_v0.6_ARCHIVE.md)已完成五步骤重写并通过
  [工程评审](../p0/P0_IMPLEMENTATION_PLAN_V0_6_REVIEW.md)。评审覆盖 P0-Q01～Q17、
  任务 3～6 事实、G0～G6、OI-017、发布包、Dify 迁移和停止线；结论不等于 G1 或生产授权。

### 自动化验证

- 116 项 Python 测试全部通过：原有 86 项，加任务 5 的 25 项离线契约/文件/恢复测试和任务 6
  的 5 项阈值、选择、多链及 RCSB matching-context 测试。原有测试
  中 5 项固定 P0-M1 报告事实，6 项约束 P0-M1B 的非生产边界、分页审计、Windows 路径与不可覆盖行为。
- 9 个正式 Workflow 都只有一个 Start/End，节点可达、可到 End、IF 有双出口且图为 DAG。
- 56 个 T-01 工具均有 Dify 覆盖；模板中不存在禁止节点和未绑定占位符。
- 文档入口、关键文件和相对链接由 `scripts/check_docs.py` 校验。

## 当前限制

- Master 当前本地编辑器仍显示“未发布”，未创建 Workflow Service API Key；25 场景回归
  是通过编辑器运行并从本地 PostgreSQL 取证完成的。
- OI-017 已由 wing（开发者）确认通用长任务框架为 `DECIDED`，但数据契约、后端状态机、
  `T01_AwaitJob`、恢复入口和逐工具 execution profile 尚未实现；现有 Mock 轮询/取消行为
  不能作为生产实现。
- OI-005/OI-016 已按当前一期边界 `DEFERRED`：外部 `context_scores` 注入明确不进入一期；
  HIGH/NON_HIGH 仅保留为旧 Mock 拓扑场景，若未来恢复须重新立项评审。
- 已完成 17 项初始开放项的首轮开发评审，并新增 OI-018～OI-023。当前共 23 项：
  2 项 `DECIDED`、4 项 `IN_REVIEW`、13 项 `BLOCKED`、4 项 `DEFERRED`，没有
  未分类的 `OPEN`。
  开发评审只确认工程边界；相应业务和科学内容仍需具名负责人确认。
- OI-013 已改为 `BLOCKED`：S-44 是一期必保留节点，但 Agent C/外部系统的真实接收、认证和
  交付确认接口尚未定义，当前必须保持 `delivered=false`。OI-014 因科学 Schema 和接收方
  载荷要求缺失而 `BLOCKED`。
- 所有真实科学工具仍为 `NOT_DEPLOYED`。
- 真实工具执行模式尚未启用。
- 已确认按 [P0-P7 顺序交付计划](P0_P7_STAGE_DELIVERY_PLAN_20260903.md)逐阶段闭环：每阶段先完成科学工具
  与发布包，再完成该阶段工作流和回归冻结；P0 未 `FROZEN` 前不得开始 P1 真实工具实现。
- 现有 OI 首轮评审仅作为风险和未知项盘点，不表示科学 Schema 已依据真实工具输出定稿。
- P0 v0.5/v0.6 已停用并归档；旧 S-06、S-07、V06 M1/M2 和五步骤顺序不得继续执行。当前按
  v0.7 的甲方直接输入、可选结构分支与四步骤里程碑推进。
- 一期明确不包含 S-23 安全三联检、S-32 MD、context 注入、分支 4 稳定性救援、DiscoTope、
  IEDB Immunogenicity、SolubleMPNN 和 C29/C30；旧 Mock/契约中的对应路径仅是冻结回归资产，
  不再代表生产一期范围。
- 节点 01 同样明确不包含 S-07、RCSB PDB、AlphaFold DB 及 BLAST→UniProt→AFDB 联网回退；
  这不限制本地 AF3/ESMFold2。OI-023 归并完成前不冻结生产入口或启动 S-08 G0。
- S-07 契约评审稿、S07-D03～D18 和 discovery 只作历史工程证据；不再逐项推进或要求当前
  专家答复。未来用户恢复 S-07 时，才按届时范围与数据源重新评审。

## 当前应该做什么

1. 执行 [P0-V07-M1 甲方输入契约归并](../p0-v07-plan/P0_V07_M1_BACKLOG.md)：从专家原文汇总
   `protein_sequence`、`host_species`、可选结构、PDB/CIF/mmCIF、校验、来源、错误与工程追溯，关闭 OI-023。
2. M1 不向用户发散询问已有规则；只有原件真实冲突或科学缺口才定点提交专家。完成后执行
   AlphaFold3/ESMFold2 内网 G0；模型在甲方服务器正常运行，但运行时不得访问公网数据库或下载依赖。
3. 原 M1-03 B 的 S-09 Q08/Q09 迁入 V07-M3；C 的 OI-015/Q12/Q13 迁入 V07-M5。S-07 A 包、
   P0-Q02～Q05、五项专家问题和候选完整性 M2 均延后，不再阻塞一期。
4. 相应规则、契约和 G0 条件满足后，才依 v0.7 顺序实现 OI-017 底座、四步骤适配器、离线
   发布包、P0 工作流与新批次断网回归；历史非生产验收不替代 G1 科学验收。
5. P1-P7 按新 18 节点基线重新收敛，不恢复任何明确排除项；S-44 接口在 OI-013 关闭前禁用，
   外部 `context_scores` 注入不进入一期。

不要宣称 Mock 工具已经具备真实科学能力，也不要在 P0 冻结前开始 P1 的真实工具实现。

## 恢复工作时的最小检查

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe .\scripts\check_docs.py
```

只有需要 Dify 联调时才启动 Docker 与 Mock MCP。运行步骤见
[开发运行手册](../../full-t01-mock-v0.1/docs/development/RUNBOOK.md)。

## 2026-09-04：一期计划改为 18 节点独立 Mock

- 用户确认旧 Master/P0-P7 Mock 仅保留给未来完整 T-01 开发，不得影响当前一期计划。
- 当前一期须先建立与最新 18 节点图一致的独立 Mock，再沿相同拓扑实施真实工具。
- 原 P0 v0.7 及 P0-P7 生产计划已归档；原“当前应该做什么”是 2026-09-03 快照，不再执行。
- 当前下一任务改为 `PH1-MOCK-M1` 规格与验收基线；详情以[当前状态](../../../docs/project/STATUS.md)为准。

## 2026-09-04：旧源码与 S07 物理分区

- 根目录 `src/`、`tests/`、`scripts/`、`dify/`、`discovery/` 改为当前一期专用入口。
- 旧 Master + P0-P7 Mock 完整移入 `legacy/full-t01-mock-v0.1/`；S07 专项资产集中移入
  `legacy/s07/`，没有删除历史代码、证据或约 10.9 GiB 本地数据。
- 文档链接已修复，当前/旧完整 Mock/S07 三套测试分别为 1/74/41 项通过；整理记录见
  [源码与 S07 历史资产整理](SOURCE_LEGACY_REORGANIZATION_20260904.md)。

## 2026-09-04：旧项目计划移出 docs

- 原 `docs/archive/` 的 34 个历史文件整体迁入 `legacy/project-history/`。
- `docs/` 只保留当前一期控制文档与运行入口；旧 P0/P0-P7 计划不再与当前文档并列。
- 129 条本地 Markdown 链接已按新位置修复，文件未删除，历史结论未改写。
