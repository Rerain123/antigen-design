# M1 与 HiMat 工程交付归并记录

> 归并日期：2026-09-25。以下内容保留原记录的时点身份；其中“当前”“下一步”和暂定规则均不是现行任务。新任务见[总计划](../PHASE1_DELIVERY_PLAN.md)，最新能力见[STATUS](../STATUS.md)。专家原件、冻结资产和运行证据未修改。

## 整理前计划记录

## M1 执行计划（2026-09-21）

### PH1-REAL-SEQUENCE-2

**目标：从现有服务提交目标蛋白序列、宿主物种及可选结构，完成候选设计（N11）→设计验证（N12）→表位保护与变体复评（N13）→稳定性打分（N14）→候选排序（N15）→报告交付（N18）。** N01–N10 完成结构、表位、保守性、功能域及 WT 可开发性分析，提供设计输入；密码子优化（N16）与 WT 稳定性参考（N17）按下表覆盖。准确性和结果优劣不作为当前验收条件；父任务成功、空报告或跳过核心链条不算跑通。

只选一个落在已实测支持域的固定蛋白样例，优先可用且耗时低的结构路径。N01 优先已支持的本地结构或 ESMFold2，必要时使用 AlphaFold3；使用已有部署、服务/API 和结果存储，不重做独立工具验收，不等待 W1–W7 整阶段关闭；普通修复在本包连续完成。

P1 复用现有运行层及测试入口，只补必要路由与显式配置，不新建通用模式框架。首轮使用已登记最小测试库；后续已补齐目标 nr 库并在 P4 的目标库新任务中实跑。两种数据库身份和证据分开记录，正式数据库科学资格未签收。

上游业务链：N02 用 DeepTMHMM/FreeSASA 分析拓扑和表面可及性，N03 用 BLAST 检索本地序列库，N04/N05 用 BepiPred、NetMHCpan/NetMHCIIpan 预测 B/T 细胞表位；N06 合成表位地图，N07 扫描糖基化位点；N08 用 MMseqs2/BLAST/MAFFT 完成同源收集与保守性分析，N09 对接本地 UniProt 注释，N10 形成 WT 可开发性基线。节点编号仅用于追踪，不替代业务名称。

### P1–P4 执行顺序

| 顺序 | 工作 | 完成标准 |
|---|---|---|
| P1：上游分析与设计入口 | 增加显式 M1 测试路由，分开内部计算与正式放行；固定蛋白样例、最小数据库和暂定配置，接通 N01–N10 分析结果到 N11 设计输入 | 同一 run_id 的结构、表位、保守性、功能域及 WT 基线可按测试约定供后续设计使用，不再仅因待签收跳过设计；缺项明确处理，来源/序列不匹配仍拒绝。测试模式显式选择，默认正式入口保持 |
| P2：候选设计、验证与排序 | 小批量接通 N11–N15：ProteinMPNN 生成候选，ESM-IF1 打分，ESMFold2/AlphaFold3 复核结构，重跑适用表位与可开发性工具，FoldX 打分，再形成测试排序 | N11 至少生成一条不同于 WT 的测试候选；N12 真实打分且至少一条结构复核；N13 实际执行变体重评；N14 对同一候选与原始 WT 计算稳定性变化；N15 输出真实分数支持的确定性排序。全淘汰保留排除事实，可输出被排除候选的调试排序，不冒充合格候选 |
| P3：WT 参考、条件优化与报告 | N17 用 FoldX/ThermoMPNN 做有限范围 WT 稳定性扫描；N16 用 DNA Chisel 做条件密码子优化，无表达宿主等必要输入时明确跳过，已有支持配置可直接补一例；汇合至 N18 | 报告/ZIP 可组装和回读，候选、步骤与文件属于同一运行；WT 扫描有调用及范围记录，密码子优化执行或条件跳过可核验。Agent C 交接先输出本地载荷，不等待对端；公开链接按既有授权处理 |
| P4：端到端最小验收 | 从服务提交新蛋白任务走完 P1–P3；另验一个 WT 分支和一个失败或取消分支 | 候选设计、验证、重评、打分、排序、报告及来源/终态均有证据；失败/取消不伪装成功。达到工程最小标准即结束 M1；已发现的专家图路由偏差须按下述纠偏包闭合后，才开展 HiMat 直连 MCP，不追加完整故障矩阵或精度考核 |

优先解决阻止本条样例前进的问题。正式数据扩容、全面回测、复杂界面和完整对端接口不抢占 P2/P3。先完成 P1 和首个批次再据实估算余量，不承诺未经测量的天数，不新建准备阶段。

### P3 交付记录（已完成）：WT 扫描、条件密码子处理与 N18 本地交付

**目标：在 P2 真实结果上补齐有限 WT 稳定性扫描和 N16 条件记录，生成可回读的 N18 报告/ZIP 与本地交接预览。** 优先使用原 P1/P2 run 下的新独立子任务，不重做已完成的候选设计与重评。正式 BLAST、N08/N09 覆盖、CamSol/RSA/标签暴露缺项及完整科学签收不作为本包前置。本次管理整理不启动计算任务。

依据：当前专家包 SOP S-30/S-31/S-42/S-43/S-44、T-01 step21/22、C35/C43，入口见 [W7](../phase1/PHASE1_REAL_W7_PLAN.md)与[权威索引](../../../工作流设计/01-业务依据/README.md)；M1 有限范围和暂定口径沿用 A01–A08，不改变科学原件。

1. **接续与来源。** 校验 P2 最终 `final-report.json` 对应任务及 ArtifactRef，使用修复执行器后的最终评分版本；绑定原始 WT 序列、精确结构、P1 约束与 P2 复评。P1 父任务和 P2 审计/产物保持原字节。若旧 N18 适配器不能消费新结果，在本包补适配、测试与部署；不可只打包旧父任务中跳过 N12–N14 的快照。可靠同 run 接续不可用时记录具体阻塞，不能复制旧产物冒充新计算。
2. **N17 有限 WT 扫描。** 在原始 WT 结构上新执行 FoldX PositionScan；满足单体适用条件时同时执行 ThermoMPNN。根据已校验结构覆盖和显式测试权限确定最小非空位点集合，启动前固定请求、选择依据及 FIXED/RESTRICTED 排除集合；缺失 N08/N09 不推定为无保护位点。有限范围只属内部工程测试，不能声称完整科学扫描。保留各引擎原始值、实际计算范围和展示范围；ThermoMPNN 固定 profile 若原生全量 SSM，则如实记录全量计算及后续取范围。历史扫描或 P2 BuildModel 不替代本轮 PositionScan，不跨引擎平均。N17 汇总关联新扫描任务/回执；当前只汇总历史来源的 `scan_invocations=0` 不能单独作为完成证据。
3. **N16 条件处理。** 从实际资格与表达宿主输入判断。当前 24 条均 EXCLUDED、正式候选列表为空，主链记录无合格序列的条件跳过及 `dna=null`，不能为填满报告恢复候选资格，也不把宿主物种当作表达宿主。既有 E.coli/W3110 配置可补一例明确独立用途的 DNA Chisel 工程调用，保留翻译/GC/限制位点验证及独立来源，不能冒充合格候选 DNA；该补例不是主链跳过后的强制扩域。缺宿主、宿主不支持、求解回退与执行失败分别按已有接口记录。
4. **N18 汇合交付。** 在同 run 新组装机器数据、可读报告、逐文件 manifest 与 ZIP，引用 WT 基线、24 条候选处置、3 条代表的调试排序/真实重评/FoldX、新 WT 扫描和 N16 条件结果。明确全部淘汰、未选中 21 条、缺失维度、暂定口径与未评估项，正式 ranked_candidates/Pareto/best_candidate 保持空。P2 原生证据 ZIP 不替代本包交付 ZIP；按既有导出策略保留原始产物引用与 hash，不导出凭据、模型或许可工具。本地 Agent C 预览明确不可交接及缺项，全淘汰时正式载荷可为空并附原因；不构造合格 CandidateRecord/AgentCHandoff，不发送至对端。
5. **验证与收尾。** 测试服实际完成新扫描及汇合；按运行手册完成受影响检查，共享运行层/契约变化再扩大至完整当前根和冻结 Mock 只读检查。回读报告与 ZIP，校验包内路径、size/SHA-256、逐层 ArtifactRef、同 run/序列/WT 结构绑定及来源拒绝守卫；有部署变更则核验实际加载代码，GPU 调用保留单卡串行、离线和停止确认。报告先本地或受控下载；会公开新报告的接口按该报告的授权处理，不把历史两份报告许可扩展到本轮。

**完成标准：** 至少一组可追踪的非空 WT 扫描实际完成，适用引擎有原生回执；N16 执行或条件跳过可核验；N18 新报告与 ZIP 汇入 P2 最终结果和本轮末端结果并通过回读及独立核验。只有 FinalReport 或汇总成功不算全包通过。全淘汰允许 P3 工程通过，正式资格继续 CLOSED / false / NOT_DEPLOYED。

P3 达标后实施方只回填 STATUS，由管理任务核对并安排 P4；普通修复与必要适配在包内连续完成，不自动扩展为全 WT 扫描、正式数据库建设、N16 宿主扩域、公开发布或对端联调。

### P3 后置动作（已完成工程接入）：N03 本地目标库补齐

**目标：为 N03 补齐服务器本地 BLAST 目标蛋白库。** 当前已核实服务器不存在此前假定的库；`engineering-n03` 只能继续作为工程测试库。专家原文没有指定 N03 的具体替代库、来源或许可，故不得直接把 N08 病原库或 S-13 的 `nr` fallback 登记为 N03 主库。

1. 先确认数据库用途为 N03、来源产品/项目、版本或发布日期、许可证/引用、序列范围与预计容量；若使用项目方 FASTA，保留原始 FASTA；若使用预格式化 BLAST 库，保留可追溯来源和原始发布文件。
2. 在服务器的网络维护环境中下载或重建，不在离线科学 Worker 内联网。使用项目锁定的 BLAST+ 工具环境；先写入 staging 目录，完成 `blastdbcmd -info`、索引完整性、逐文件 SHA-256、序列条目数和来源记录。
3. 在保留现有 FASTA 建库路径的基础上，补齐预建多分卷数据库 manifest 适配，登记 `database_id`、`TARGET_DATABASE_UNREVIEWED`、用途、来源、版本、许可、`db_prefix/dbtype/blastdb_version/title/sequence_count` 及全部发布索引文件的大小/hash；预建库保留原始元数据与 alias，不虚构源 FASTA，不为兼容旧契约强制导出整库 FASTA。目录发布后只读挂载到 `/t01/databases/blast/<database_id>`，请求绑定 manifest SHA-256。
4. 用真实目标环境执行至少一条 N03 查询，区分命中、合法无命中和库不可用；普通相似性命中不产生 IEDB、文献表位或 E3/E4 证据。目标库尚未完成科学签收时，资格仍为 `CLOSED / false / NOT_DEPLOYED`。

**完成标准及结论：** 来源和用途已登记；库文件/索引/manifest/hash 一致；服务器只读挂载可见；N03 真实查询及来源回执通过；不存在把测试库、N08 库或 `nr` fallback 误登记为 N03 主库的情况。目标 nr 的 2227 个登记文件已全量 SHA-256 核验，并在 P4 r16/r17 原生查询中使用，工程接入通过；上游校验和及数据库科学用途仍未签收，身份保持 `TARGET_DATABASE_UNREVIEWED`。

### P4 交付记录（已完成）：服务接通、新任务贯通及分支验收

**目标：从服务入口提交新 run，自动贯通已有 P1–P3 能力，并完成 WT 与失败或取消分支的最小验收。** 以下保留交付时要求；目标 nr 设计 r16、WT r17、失败 r07 已分别通过独立审计，[P4/M1 收口证据](../../../discovery/t01-phase1-real/m1-p4-20260922/p4-m1-acceptance-r01.json)为 `P4_M1_MINIMAL_PASS`。原失败批次保留，不计成功路径。

1. **服务主流程接通。** 修复 `src/t01_phase1_real/development/workflow/service.py` 中的 `M1_P2_NOT_IMPLEMENTED` 路径，复用 P2/P3 已验证适配器与执行逻辑，接通 N11–N15、N16 条件处理、N17 WT 扫描及 N18 汇合。不能仅移除错误标志、手工串接独立脚本或拼接历史报告；提交、查询、结果与受控下载须沿同一服务任务完成。
2. **来源和生命周期。** 绑定本轮 run、WT、序列、结构、约束及候选身份；拒绝历史结果冒用、错 run/错序列/hash 不匹配。保留全淘汰、未评估与真实失败；N16 无合格候选时明确跳过，DNA 为 null。GPU 调用维持单卡 FIFO，失败/取消保留原生停止确认及终态，不在后台继续科学执行。
3. **下载期间的验证与适配。** 可以使用显式 `engineering-n03` 配置完成工程链验证，报告保留工程库身份，不作为目标 nr 验收。同步支持预建 nr 多分卷、alias、来源元数据与 manifest，保留原 FASTA 路径及拒绝守卫；用小规模多分卷夹具验证缺卷、损坏、路径逃逸和身份混用。结合约 571.6 GiB 实际规模检查哈希与启动校验成本，不静默删除完整性校验。不得修改、移动下载中的 staging 文件，也不把正在写入的目录挂为可消费数据库。
4. **新任务实跑。** 服务接通后，用既定有限测试输入从服务发起新 run；工程库结果只记工程通过。nr 下载完成并完成上节库验收后，以目标库绑定的新 run 完成最终整链，再验一个 WT 分支和一个失败或取消分支。若 nr 尚未就绪，交付已完成工程证据并仅将目标库实跑标为待完成，不宣布 P4/M1 完成。不手工填结果，不用旧 P1/P2/P3 产物冒充新计算；本轮候选处置由本轮结果确定，不硬编码历史 24 条全淘汰。
5. **验证与交付。** 输出服务请求/任务与 run 对应关系、各节点原生回执、最终报告/ZIP 回读、ArtifactRef/来源拒绝守卫、部署代码核验和单卡离线证据。按运行手册完成受影响及共享运行层回归，核对并处理既有 ProteinMPNN same-run 夹具失败，不跳过来源守卫来变绿；分别报告当前根与冻结资产检查结果。实施方只回填 STATUS 的成果、证据与具体剩余阻塞。

**P4/M1 完成标准（已按工程最小口径达成）：** 上表 P4 三条服务路径及 N03 目标库验收均有实际证据，报告与 ZIP 可回读，来源/终态真实一致；全淘汰可以工程通过，但正式资格继续 CLOSED / false / NOT_DEPLOYED。该验收未覆盖专家图的严格节点顺序；原结论及原证据保留，不改写成路由对齐通过。后续路由纠偏另以新运行验收通过；不扩展为完整故障矩阵、全 WT 扫描、新宿主或公开报告发布。

### P4 后置纠偏：专家一期图线上路由对齐

任务标识：**PH1-REAL-ROUTE-1（工程纠偏已完成）**。这是现有服务设计路径的工程纠偏，不重开 P4/M1 工程最小验收，不改变科学阈值或候选资格。[专家一期图](<../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>)及 SOP T-01 step19/19b/20 给出设计段 **N12 设计验证 → N13 表位保护 → N14 FoldX 稳定性打分 → N15 综合排序**。N15 后 N16 条件优化与 N17 WT 参考扫描分别进入 N18，二者之间没有依赖；串行占用资源不等于业务因果依赖。WT 直达 N18 的既有分支仍保留。

1. **固定偏差与依赖矩阵。** 以 r16 快照和现行 `workflow/m1.py`、`workflow/policy.py`、N13 来源契约、N15 报告实现为基线，列出每个子任务的业务节点、输入来源、执行前置和预期终态。两项前置报告 `selection_report`、`base_report` 目前均登记为 N15，且 `base_report` 含 N14 FoldX 并供 N13 消费；这不是仅调换列表顺序可修复的问题。旧 run、ArtifactRef、审计与报告保持原字节。
2. **修正服务调度与来源契约。** 在 N12 已校验的候选和 ESM-IF1 事实中确定有限代表集；如需中间选择产物，明确标为内部预选事实，不登记为 N15 综合排序。N13 用原始 WT 与代表变体的结构、表位和复评事实完成配对验证，来源契约改为消费 N12/预选事实，不要求 N14 或早期 N15 报告；N14 在 N13 之后对同一代表集、相对原始 WT 完成既定 FoldX 五轮计算；唯一的业务 N15 在 N13 和 N14 完成后消费两者，保留全淘汰、缺项和调试排序。同步调整 N13/N15 的来源验证器、报告节点标签和现有审计代码，不能只重命名旧 N15 子任务或把旧结果搬进新顺序。
3. **分支关系。** N16 只按 N15 的真实候选资格与表达宿主条件执行或跳过；N17 从 N15 后的 WT 结构和已批准扫描范围独立进入，不读取 N16 的产物或以其完成状态为准入。N18 等待 N16 与 N17 各自的适用终态并如实汇合；条件跳过、真实失败、WT 路由和停止确认按现有语义分别处理。单卡资源可让两个分支顺序执行，但任务图和来源中不得形成 N16→N17 边。
4. **回归与静态守卫。** 增加对实际服务 `policy.order`、`node_id`、请求来源及父子任务时间线的断言：N12→N13→N14→N15，N13 前无 N15，N15 只作为最终排序出现，N13 不消费 FoldX，N17 不消费 N16。覆盖 N16 条件跳过而 N17 继续、WT 路由、失败/取消阻断后续、错 run/序列/WT/hash 拒绝及恢复幂等。受影响测试通过后执行当前根完整回归、冻结 Mock 只读核验和文档检查；不通过删弱守卫换取绿灯。
5. **部署与新证据。** 核对测试服实际加载的代码/规则 profile hash，再从服务提交新的目标 nr 设计任务；独立审计原生节点顺序、唯一 N15、ArtifactRef/来源、N16/N17 分支、N18 报告与 ZIP 回读。用新版本验证 WT 与失败/取消路径，旧 r16/r17/r07 只作对照，不冒充纠偏后的实跑。FoldX 维持原五轮和单卡离线约束；按已测耗时预留运行预算，不为赶进度删减原始计算。未通过审计时继续修复，不进入 HiMat 注册或对话联调。

**完成标准：** 部署后新设计任务的节点标签、依赖与实际顺序满足上述专家图；N13 先于 N14、最终且唯一的 N15 在 N14 后，N16/N17 独立汇入 N18；目标 nr、原生回执、报告/ZIP、来源拒绝和部署哈希有新一轮独立证据，WT 与失败/取消不回退。该结论只表示**线上工程路由对齐**，不使 N08/N09、可开发性缺项、科学签收或生产资格自动通过。

完成核对：[部署哈希](../../../discovery/t01-phase1-real/m1-p4-20260922/route-deployment-verification-r01.json)通过；[r18 设计](../../../discovery/t01-phase1-real/m1-p4-20260922/r18/route-audit-summary.json)为 `PH1_REAL_ROUTE_DESIGN_PASS`，[r19 WT](../../../discovery/t01-phase1-real/m1-p4-20260922/r19/route-audit-summary.json)为 `PH1_REAL_ROUTE_WT_PASS`，[r20 错误 manifest](../../../discovery/t01-phase1-real/m1-p4-20260922/r20/route-audit-summary.json)为 `PH1_REAL_ROUTE_FAILURE_PASS`。r18 证实 N12→N13→N14→唯一最终 N15、原始 WT 五轮 FoldX、N16 条件跳过和 N17 独立汇入 N18；成功路径报告/ZIP 与原生回执通过独立回读。r16 旧快照继续记录偏差，不追认为新路由通过。

### P4 后续：HiMat 直连 MCP 最小联调

任务标识：**PH1-REAL-HIMAT-1（当前）**。本包独立于已完成的 M1/P4 工程最小验收；**PH1-REAL-ROUTE-1** 的线上路由新证据已通过。当前先完成后端接口准备与受控验证，再由用户开始 HiMat 注册和对话实跑。

**交付目标：用户在 HiMat 发消息，由 HiMat 中的 LLM 直接调用本项目 Streamable HTTP MCP；MCP/后端在服务器异步执行真实工作流，HiMat 可查询进度与终态，并把受控报告/ZIP 返回给同一用户。** HiMat 与 Dify 是两套独立入口；HiMat 联调不以 Dify 图检查为前置。MCP 只暴露后端固定工具和状态，LLM 不执行科学规则或改写资格。服务直提的 r18/r19/r20 证据不能充当 HiMat 入口证据。

1. **后端契约与最小权限。** 已部署 Service 可从集群内访问，但这只证明网络可达；HiMat 认证发现、工具注册和对话调用尚未验证。现有 `workflow.submit` 要求完整 `request_json` 和 `idempotency_key`，包含 N03 manifest、结构、约束和超时等内部字段。注册前为固定 M1 测试输入实现并验证受限提交工具：只接受用户可提供的必要字段，由后端绑定已登记目标 nr、结构/约束/配置、幂等键及来源校验；拒绝越权参数和错库、错 run、错身份，不让 LLM 拼内部 JSON 或选择科学规则。为专用测试身份配置最小 `submit/query/download` 权限并验证认证、工具发现、任务归属和错误返回；控制、恢复、重试及上传权限按需另行授权，不作为本轮对话默认能力。固定 Bearer 对所有共享者代表同一个后端 principal，本包只验一个专用测试身份。
2. **新增工具并绑定智能体。** 受限提交和受控报告路径完成并验证后，用户在 HiMat“智能体管理→工具列表”新增 MCP 工具，填本项目独立名称、描述、`streamableHttp`、集群内 Service 的 `/mcp` 地址和受控 Bearer；再到“智能体列表”编辑目标智能体，在“工具”栏选择刚新增的工具并设置只收集输入、调用、等待和解释后端事实的提示词。凭据不入仓库、截图或文档。[无凭据配置示例](../../../deploy/himat-mcp-tool.example.json)只供字段核对。注册后验证 `initialize`、`tools/list`、调用 scope、任务归属及错误返回，不能仅凭列表显示或“待处理”状态宣称可调用。HiMat 后台由用户操作，助手只依据脱敏截图和回执协助；截图中的论文搜索服务只是配置格式示例，不能复用其地址、名称或 token。
3. **异步交互。** 从 HiMat 对话提交后返回 job_id；页面离开后仍可用 `workflow.get`/`workflow.wait` 查询，重复提交沿同一幂等键不重复计算。HiMat 只解释后端状态和缺项，显示 CLOSED / false / NOT_DEPLOYED，不把运行中、失败或全淘汰显示成科学成功。
4. **终态卡片和受控报告。** 用户指定沿用截图中的 `type: "primer_design_output"` 作为 HiMat 终态卡片判别值；这只是前端兼容字段，抗原项目的任务、科学状态、报告内容和文件仍由本项目后端生成。终态工具调用的 JSON-RPC `result` 直接是 `{data,type}`；`data` 含 `status`、`reportTitle`、`summaryText`、`primaryAttachmentId`、`attachments[]`、`issues[]`，每个附件含 `attachmentId/fileName/fileType/mimeType/fileUrl`。参考引物服务明确该对象不能再包在 `structuredContent` 或文本通道内；本项目现有 MCP `workflow.report` 正是后一种包装，须做协议适配、固定该输出 Schema 并用实际 HiMat 渲染验证。卡片标题、摘要、issues 由后端从任务终态与报告事实确定，不能由 LLM 编造；`COMPLETED` 只表示报告交付完成，不代表候选科学合格，原始 `CLOSED / false / NOT_DEPLOYED` 随摘要和报告保留。

   当前部署 `RUSTFS_ENABLED=true`，现有 MCP `workflow.report` 一经调用就会将报告上传到匿名可读的 RustFS 前缀并返回公开链接；本轮新任务不得调用该路径。先实现与同一任务调用者绑定的受控 `fileUrl`，例如经服务鉴权的短期签名只读地址，保证浏览器能下载而不泄露 MCP Bearer；或经用户另行明确授权后才使用公开对象。参考的认证 REST ZIP 接口可作后端回读基线，但不能直接视为 HiMat 浏览器可下载链接。验证任务归属、过期和跨身份拒绝、大小/hash、附件渲染与下载；本包不自动公开新报告或扩展 Agent C 对外交接。
5. **现场证据与收口。** 可先用低成本已授权任务验证发现、查询和展示；最终至少有一条**由 HiMat 发起的新真实工作流**完成提交→服务器执行→查询终态→同测试用户下载/查看报告的闭环，绑定 N03 目标库及本轮 run/ArtifactRef。保留 HiMat 请求、MCP/服务 job_id、原生回执、报告回读、失败/权限边界和部署代码证据。r16/r17 已从服务直接提交，不能冒充 HiMat 发起的任务；重计算按单卡资源队列安排。固定 Bearer 会使共享该工具配置的 HiMat 用户在后端成为同一个 principal，本轮仅对专用测试身份验收；正式多用户隔离须通过可信用户身份传递/映射独立解决，不以单用户闭环冒称完成。

**HiMat 后续项完成标准：** 在已通过 P4 工程最小验收与线上路由纠偏的基础上，HiMat 直连 MCP 的一条新真实任务完成对话受限提交、后台执行、终态查询、可渲染的 `{data,type}` 报告卡片及同测试用户受控附件下载；后端回读核对 job/run/ArtifactRef、文件大小/hash，并证明未发生未经授权的公开发布。Dify 工作流检查再单独安排。科学 Gate、正式管线资格和生产状态仍分别保持 CLOSED / false / NOT_DEPLOYED。

[FoldX 耗时诊断](../../../discovery/t01-phase1-real/m1-p4-20260922/foldx-runtime-diagnosis-r01.json)已定位主要耗时在原生 BuildModel；性能优化另行安排，不作为本包前置，也不改写已完成的五轮原始计算证据。

### M1 问题处理表

以下是用户允许精度让步后的工程暂定口径，**逐项实施，不代表全部已验收**；已执行范围见 STATUS 与原始证据。配置、来源、差异、适用域随运行保留；不回写原件或旧产物。

| 业务问题与追踪编号 | M1 默认处理 | 后补内容 |
|---|---|---|
| A01：本地检索、同源与注释数据（N03/N08/N09，OI-028/030/031） | 原先假定的服务器 N03 库不存在；现已下载并登记目标 nr，完成 manifest/hash、只读挂载和目标库真实实跑，`engineering-n03` 仍只代表工程测试。目标 nr 保持 `TARGET_DATABASE_UNREVIEWED`，不自动改用 N08 库或把普通相似性命中当作科学保护证据。N08 同源与 N09 UniProt 注释覆盖分别核对，未知不等于不存在 | N03 正式库身份与覆盖、上游校验和/科学用途签收、注释转移；N08/N09 目标数据与科学消费验收 |
| A02：空热点与表位消费（N06/N07，OI-007/026/028/029） | 已计算空热点继续流程；N13 无验证区间的保护指标记不适用或未评估，其他变体复评仍执行。未计算与计算为空分开，不为制造热点改阈值。BepiPred 的 OI-026 暂选一个已有真实输出列，固定列名/来源并记录差异；T 通道保留 NetMHCpan/NetMHCIIpan 真实结果 | 表位保护正式语义、非空窗口边界及回测 |
| A03：CamSol 溶解性参数（N10，OI-025） | 按原文公式和随机肽标定方法生成派生参数；交替模式采用原文示例支持的固定 5 残基窗口、允许重叠，固定标度表和随机源。H/P 对称互换不单独阻断计算。参数若仍未就绪，溶解性维度保持缺失，M1 暂以可用维度汇总，并声明与正式必需项的差异 | 参数、模式计数及独立参考签收 |
| A04：聚集与 pH 稳定性（N10，OI-032/033） | AGGRESCAN3D 优先走已有结构路径，空间簇暂沿用连通分量实现，不造未定义风险细分档；缺 AGGRESCAN 序列备选时排除对应维度。PROPKA 平坦曲线暂用采样 pH 区间中点作展示值，保留真实曲线、稳定区间和暂定标记。缺失不补零，不阻断其他维度 | 序列版资产、空间簇/分类与平坦曲线正式规则 |
| A05：结构映射与 RSA（N02/N09，OI-015/027） | 首条样例优先 FreeSASA 已支持的结构映射输入；例外保留原始结构，采用可追踪的显式派生投影或将 RSA 等受影响维度记缺失。未知插入码不直接改成已知，不阻断独立序列分析 | 完整结构映射域、RSA 口径及消费者验证 |
| A06：设计权限与结构复核（N11/N12，OI-001/002/006/008/021/022） | 固定显式测试设计约束和允许修改位点，不用未评估证据生成正式自动权限。ProteinMPNN 使用已有首轮配置，全淘汰最多追加一轮有原文依据的配置；再淘汰保留结论并继续调试输出。N12 先选已部署的 ESMFold2 或 AlphaFold3 复核代表候选 | 自动权限、完整结构复核路由、双引擎和受控重算组合 |
| A07：变体复评、稳定性与排序（N13/N14/N15，OI-009/010/011/022） | 首轮最多 3 条代表候选实际重评和评分，记录选择及范围；N15 暂按真实 ESM-IF1 分数降序，平分按稳定候选 ID，其他真实评分列展示，缺失不补零。正式过滤结果另存，不因测试排序改写淘汰结论 | 完整候选池、目标权重、全量表位/可开发性复评和正式选择 |
| A08：WT/候选报告及 Agent C 交接（N18，OI-013/014/021，OPS-001） | 按已有字段组装 WT/候选本地载荷与报告，未定字段明确缺项；Agent C 地址、认证和确认后移。先本地文件或受控下载，不等公开对象处置；调用会公开新报告的接口仍按授权处理 | 正式 Agent C 协议、字段验收及报告对象处置 |

### M1 必要约束与通过判定

- 真实工具必须实际调用；旧产物只作参考，夹具不替代 P2/P3 的真实计算。
- 暂定值由后端确定性计算或显式配置提供；区分原始值、近似、缺失、未评估和被排除。LLM 不补分数、不代算规则。
- 保留单卡串行、离线、许可证、凭据保护、运行归属、必要输入校验和取消后进程停止。身份/hash 不匹配、必要资产不可执行、权限不足及运行层故障才是本轮优先执行阻塞。
- 新增独立内部测试资格，不靠把 scientific_release_gate、usable_for_pipeline 或生产状态改成成功解锁。正式标志保持原义，P1 实现测试与正式入口隔离并做相应回归。计划变化不代表现有代码已具备能力。
- 已知不适合设计的输入走 WT 分支，主线选满足已知设计适用条件的蛋白样例；未签收与已知不适用分开。未知必要约束由显式测试配置处理，保留未知事实。
- 不要求候选优于 WT 或正式合格候选列表非空；必须有本轮真实生成的候选经过结构/模型验证、变体重评、稳定性评分和报告输出。缺项、暂定规则和调试排序在结果中可见。

### M1 之后

| 里程碑 | 目标 | 时点 |
|---|---|---|
| M2：覆盖与准确性 | 替换暂定规则，补正式数据、完整分支/输入域、全量候选验证/表位保护/排序、密码子优化与 WT 扫描条件覆盖及回测；HiMat 更完整的界面与文件体验按实际缺项完善 | M1 通过后安排，不作本轮前置 |
| M3：正式交付 | 适用签收、对端协议、完整生命周期、运行保障和最终发布 | 沿用下方完整验收，不用于否定 M1 完成 |

W1–W7 保留接口细节和最终要求；当前优先级统一服从本节。开放项原状态保留用于后补，不按 BLOCKED 标签整批停工。


## 整理前状态与验证记录

# T-01 当前状态

> 更新：2026-09-25。N09 完整 Swiss-Prot 2026_03 已导入并接入 HiMat，测试服 generation 86 Ready；575748 条原始记录索引约 2.39 GB，DAT/FASTA 逐条核验通过，原 233 aa 精确命中 O56129 并投影出 3 条功能注释。本轮完整回归 2396 passed / 15 skipped。N11 确认接续与报告修复、P1/P2 进度、N03 IEDB 本地检索保持；科学 Gate CLOSED，未新启设计任务。当前 N09 仅支持精确序列注释，不代表同源转移或 core_map 已完成。
> 一期 N01–N18；N03 本轮按用户最新决定恢复 IEDB＋本地 BLAST，待计划管理任务同步旧范围文字。开发 IN_PROGRESS；科学 Gate CLOSED；usable_for_pipeline=false；生产 NOT_DEPLOYED。

## 当前任务入口

文档写入分工：实施 AI 仅更新本页的事实、验证、阻塞和建议；计划及其他文档由用户指定的管理任务维护，详见 [AGENTS](../../../AGENTS.md#2-推进任务)。本页不能作为实施方自行调整目标或验收标准的入口。

当前任务：[PH1-REAL-HIMAT-1](../PHASE1_DELIVERY_PLAN.md#p4-后续himat-直连-mcp-最小联调)

当前包：PH1-REAL-HIMAT-1 首个 HiMat 任务 `t01p1r-job-120f08a88827456e83bfdf5e6ef19b92`（run `t01p1r-run-44199d1960334909b953022f05a43858`，233 aa、宿主猪）于北京时间 2026-09-24 13:17:41–14:07:04 运行，父任务 `succeeded`，报告结论为 `DESIGN_INPUTS_UNAVAILABLE`。[完整只读复盘](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-first-review-r01/review.json)核验 139 个 ArtifactRef、11 个子任务（9 成功、2 失败）。N01 ESMFold2 被实际 `/backend` 的 76 aa 旧策略拒绝；N03 原生 BLAST 退出码 0、输出 500 条 HSP，但 4 条 232/233 覆盖率被解析器误拒，节点为 `OUTPUT_INVALID`。用户报告已在 HiMat 获得报告；助手已核验同测试身份终态卡片及服务内受控附件，未独立验证浏览器渲染/下载，不据此计完整工具链通过。既有路由纠偏与目标 nr 工程验收保持原身份；Dify 检查后移，助手不操作 HiMat 后台。

HiMat 首轮复盘的 5 项 P1（F1/F2/F3/F4/F6）已实现并部署，证据见[验证汇总](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-p1-validation-r07.json)与[线上核验](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-p1-deployment-r07.json)。测试服 generation 80、Pod Ready：ESMFold2 原生 `/backend` 与服务端的策略/资源哈希一致，上限 999 aa，原生解释器接受 233 aa 策略探针；旧 BLAST 原生契约及 500 条 HSP 回放通过，精确覆盖率仍用于原阈值判定。普通入口真实子任务失败在调度/恢复时均终止父任务；缺少预测来源等按条件跳过。主报告视图加入已校验的外层工作流事实，卡片显示 N01/N03 失败；新 N18 披露递归缺项、N10 部分计算及 N17 引擎来源，扫描是否执行不再只看组装器调用次数。原任务与 ZIP 保持原字节，不追认旧失败成功。

用户明确仅提供序列＋宿主，无位点掩码。HiMat 提交 `BACKEND_EVIDENCE_V1`，在适用 Gate 后进行同 run 的 S-27 审计；未知证据仍保守约束，不复用旧样例。空 FIXED 的 T4 确认现已接通：`workflow_check` 返回 `awaiting_confirmation`、警告及绑定审计 hash 的确认标识；新工具 `workflow_confirm_design` 接受用户明确决定，同意沿用原 run 接续，拒绝仅交付已有分析。确认等待不消耗计算期限，重复同一决定幂等，错用户/错审计/已停止任务拒绝。新请求支持高精度 mmCIF 转 PDB 的三位小数投影，原始坐标与逐原子舍入来源保留；旧请求仍按原规则回放。无有效导出继续披露 `N11_MASK_EXPORT_BLOCKED`，不保证任意序列进入设计。旧终态任务不重开、旧 ZIP 不改；查询卡片及报告预览优先显示实际执行事实。设计目标/表达宿主按用户决定暂不新增入口；N05 面板、N08 数据与科学签收仍缺失；N09 Swiss-Prot 精确查询现已接通，范围见当前验证。

已完成的 P4 目标库新任务最小验收：[P4/M1 收口证据](../../../discovery/t01-phase1-real/m1-p4-20260922/p4-m1-acceptance-r01.json)为 `P4_M1_MINIMAL_PASS`：目标 nr 库只读挂载及全量 SHA-256 验证通过；服务设计 r16、WT r17、失败 r07 三条路径分别通过独立审计，r16/r17 的 N03 均实际查询目标 nr，成功路径的报告与 ZIP 已受控下载并核验。旧目标任务暴露的地址空间、Worker 配置、900 秒截止、`blastp.REAL` 结果契约与持久化回执 `mount_path` 问题均已定位修复并部署，原证据保留。正式资格继续 CLOSED / false / NOT_DEPLOYED。

计划管理任务已将[线上路由纠偏](../PHASE1_DELIVERY_PLAN.md#p4-后置纠偏专家一期图线上路由对齐)按新证据收口，并把[HiMat 接入](../PHASE1_DELIVERY_PLAN.md#p4-后续himat-直连-mcp-最小联调)列为当前包。P4/M1 既有工程最小验收保持原身份，不追认为科学签收。

M1 已按[最新决定](../DECISIONS.md#m1-跑通优先与业务计划)完成有限测试路径验收；暂定口径、精度让步和未签收开放项如实保留，不扩大为科学放行。

**P3 已在原 P1/P2 run 下完成新扫描和 N18 本地交付，独立审计通过。** 原始 WT 的位点 3 完成 FoldX PositionScan；ThermoMPNN 原生全量单体扫描产生 1520 条，取同一位点展示 20 条。显式排除 1、2、76，N08/N09 缺失不推定为无保护位点。P2 的 24 条候选均保留 EXCLUDED，3 条代表真实重评与 FoldX、其余 21 条未选中状态汇入新报告；N16 为 `SKIPPED / NO_QUALIFIED_CANDIDATE / dna=null`。正式资格继续 CLOSED / false / NOT_DEPLOYED。P1/P2 已归并过程见[历史索引](README.md)。

既有 P3 [N18 报告](../../../discovery/t01-phase1-real/m1-p3-20260922/r01/delivery/report.md)、[交付 ZIP](../../../discovery/t01-phase1-real/m1-p3-20260922/r01/delivery/package.zip)及 [Agent C 本地预览](../../../discovery/t01-phase1-real/m1-p3-20260922/r01/delivery/agent-c-preview.json)保持原字节。P4 已替换 `M1_P2_NOT_IMPLEMENTED`：服务事务调度接通同 run 的评分、代表重算、稳定性、条件 N16、WT 扫描和 N18；候选处置读取本轮结果，不硬编码历史全淘汰。r01 暴露的 WT 基线误路由已修复，r01 留作诊断，不计设计链通过；[r02 部署哈希](../../../discovery/t01-phase1-real/m1-p4-20260922/deployment-verification-r02.json)通过。范围和完成标准单点见[交付计划](../PHASE1_DELIVERY_PLAN.md)。

P4 工程库主设计 run `t01p1r-job-b8c44ac8765d4e98834a240d46ae16c4` 已成功终止；47 个子节点回执归档，N11 设计、N12 验证、N13 复评、N14 FoldX、N15 排序、N17 WT 扫描及 N18 交付均成功，N16 因无合格候选按条件跳过。[报告](../../../discovery/t01-phase1-real/m1-p4-20260922/r02/report.md)与[交付 ZIP](../../../discovery/t01-phase1-real/m1-p4-20260922/r02/delivery.zip)经认证 REST 受控下载和逐文件 hash 回读；[独立审计](../../../discovery/t01-phase1-real/m1-p4-20260922/r02/audit-summary.json)为 `P4_ENGINEERING_DESIGN_PASS`，核验 1508 个 ArtifactRef。该 run 使用 `engineering-n03`，不计目标库整链通过。

工程分支已核验：[WT 分支审计](../../../discovery/t01-phase1-real/m1-p4-20260922/r03/audit-summary.json)通过，低置信结构保留 `R57_LOW_CONFIDENCE_DESIGN_SKIPPED`、扫描条件跳过，服务自动生成的[报告](../../../discovery/t01-phase1-real/m1-p4-20260922/r03/report.md)及 [ZIP](../../../discovery/t01-phase1-real/m1-p4-20260922/r03/delivery.zip)经认证 REST 受控下载和回读；[失败分支审计](../../../discovery/t01-phase1-real/m1-p4-20260922/r04/audit-summary.json)通过，错误库 hash 终止为 `HASH_MISMATCH`，后续设计/交付未执行。两者均使用 engineering-n03，不代表目标 nr 验收；公开报告发布接口未调用。

执行和验收单点维护在总计划；已完成过程从[历史索引](README.md)查阅。

## 已完成与当前能力

| 能力 | 已有证据与边界 |
|---|---|
| 工具与工程基础 | 本地结构、DeepTMHMM、BepiPred、NetMHC、BLAST、同源/注释、设计与稳定性工具已有独立工程成果；不代表相应节点已获科学签收 |
| ESMFold2 | 76 aa 标准结果、统一任务→N01、N12 同 run、取消及推理前超时已有证据；393 aa 是独立容量案例；P1 修复后服务与实际 `/backend` 策略上限均为 999 aa，233 aa 策略探针通过，尚无本次修复后的新推理证据 |
| AF3 标准链 | r14 在指定 A100 64GB 上完成四库本地搜索、五个 native sample、最高 pTM 选择、标准 ArtifactRef/hash/source binding、N01/S-09 与 N18 同 run；12 个节点成功、8 个按边界跳过、0 失败。报告接口未调用 |
| 单卡执行 | Deployment 只有 `worker-unified-gpu` 申请一张完整 A100 64GB；AF3、ESMFold2、ProteinMPNN、ESM-IF1、ThermoMPNN 共用全局 FIFO，终态停止确认后才释放。三个受影响 GPU 工具代表性任务已严格串行通过，旧双 GPU/RBAC 入口守卫通过 |
| P1 内部测试设计入口 | 固定 76 aa 1UBQ、已有可追溯 PDB 派生输入、显式逐位点约束和首轮 24 条/温度 0.1/seed 17；结构、拓扑、最小库 BLAST、B/T 表位、N06/N07、WT 部分基线及 N11 在同一 run 新执行成功；N08/N09 unavailable。输入来源与缺项见[本轮证据](../../../discovery/t01-phase1-real/m1-p1-20260921/r01/input-provenance.json) |
| N06→N07 空热点 | 仅无 IEDB E3/E4 的原预测来源集合按 S-19 上界 B≤0.2、T≤0.5、双通道≤0.35，均不能满足严格 `>0.5`；N06 输出 `computed_empty_unreviewed` 和可复核证明，N07 保留已验证空集合且不把它写成科学通过；本轮有 IEDB E3 时撤销该证明、hotspots=null/review_required，不把尚未计算写为空集合 |
| R-57 业务 Gate | 保留三态与 `WT_PATH_REVIEW`；默认正式入口仍不释放 N11。显式 M1 P1 与 HiMat 后端证据工程路由仅对已知适合、无额外膜/低置信约束且掩码验证通过的输入提交既有 ProteinMPNN；`n11_release=false`、科学 Gate CLOSED 和正式管线不可用保持 |
| 服务与报告 | P4 服务同 run 自动接续已部署；旧目标库 r16/r17/r07 维持原工程审计身份。纠偏代码在测试服按哈希核验，新目标库 [r18 设计](../../../discovery/t01-phase1-real/m1-p4-20260922/r18/route-audit-summary.json)、[r19 WT](../../../discovery/t01-phase1-real/m1-p4-20260922/r19/route-audit-summary.json)、[r20 失败](../../../discovery/t01-phase1-real/m1-p4-20260922/r20/route-audit-summary.json)均通过独立严格路由审计，成功路径的报告/ZIP 经认证 REST 回读及逐文件校验；未触发公开发布。HiMat 首个 233 aa 任务已交付缺项报告，N01/N03 失败及通用入口差异见当前包复盘；终态卡片与服务内附件已回读，浏览器渲染/下载未独立核验。Dify 图检查后移且不位于 HiMat 与 MCP 之间 |

各子包成果和原证据统一从 [已完成成果](README.md)查阅；完整支持域与接口见 [工具接口参考](../../development/TOOL_INTERFACES.md)。

## 当前阻塞与后补项

| 类别 | 判断与处理 |
|---|---|
| 设计入口 | 已解除仅因待签收跳过 N11 的阻断。既有显式 M1 配置及新的 HiMat 后端证据审计均须验证完整约束，拒绝历史复用、错 run/错序列/hash 不匹配；无用户掩码不再要求人工注册配置，后端导出失败或必要结构/适用性未知仍阻断，已知不适合仍走 WT |
| 业务数据库 | N03 当前新入口已切换 `iedb-20260924-r01`（202501 条蛋白，929905671 bytes，详见当前验证），全量哈希及真实 Worker 查询通过，E4 坐标缺失。历史目标 nr 蛋白库保留，下载完成，1113 个发布文件共 740587289460 bytes；[大小分组](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-sizes-r01.json)说明与核心分卷元数据的差额。[索引检查](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-info-r01.json)识别 123 分卷、935749080 条序列、v5；[登记 manifest](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-manifest-r01.json)绑定 2227 个文件，[独立全量 SHA-256](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-hash-r01.json)逐件通过，[来源契约](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-contract-r01.json)通过。上游校验和未核验，资格为 `TARGET_DATABASE_UNREVIEWED`。服务与 BLAST Worker 已只读挂载；BLAST 地址空间 1TiB，Worker 实际资源为 16Gi/4 CPU，直连 `blastp.REAL` 已在目标库 r16/r17 原生查询中执行成功。服务现使用持久化全量校验回执并逐文件检查文件状态，Pod 内回执复用实测 0.13 秒；原生查询上限 7200 秒。目标库 P4/M1 工程验收已通过，不代表数据库科学资格签收 |
| 局部计算与适配 | 本轮保留 N06 已计算空热点并传 N07；M1 输入包暂选 `BepiPred-3.0 score / ensemble_probability`，保存 76 个真实值与 OI-026 差异，不改热点阈值。FreeSASA 实际执行，RSA 越域维度仍缺失。N10 有真实表达性、A3D 与 PROPKA 原始事实，CamSol/标签暴露/稳定性维度缺失或未执行，overall=null、n10_complete=false；精度与暂定汇总后补不阻断显式设计 |
| 设计链与报告 | N11 T4 确认、同 run 接续、拒绝与报告实际执行结论已部署；旧终态及原 ZIP 不改写。当前线上仍只有首轮最多 24 条生成、最多 3 条代表重评，N13 未接回 IEDB 先验且 L3 非专家规定的叠合 RMSD，N15 正式候选/Pareto/最优候选链未接通，N17 仅选一个 OPEN 位点。上述为实际功能差距，不能仅归因于尚未签收；建议计划管理任务按对照证据安排处理，实施方未调整计划或验收标准 |
| 目标库新任务 | [设计 r16 审计](../../../discovery/t01-phase1-real/m1-p4-20260922/r16/audit-summary.json)为 `P4_TARGET_DESIGN_PASS`，核验 1508 个 ArtifactRef；[WT r17 审计](../../../discovery/t01-phase1-real/m1-p4-20260922/r17/audit-summary.json)为 `P4_TARGET_WT_PASS`；[失败 r07 审计](../../../discovery/t01-phase1-real/m1-p4-20260922/r07/audit-summary.json)为 `P4_TARGET_FAILURE_PASS`。三条服务路径和目标 nr N03 验收汇入[P4/M1 收口证据](../../../discovery/t01-phase1-real/m1-p4-20260922/p4-m1-acceptance-r01.json)。r16 [报告](../../../discovery/t01-phase1-real/m1-p4-20260922/r16/report.md)与[ZIP](../../../discovery/t01-phase1-real/m1-p4-20260922/r16/delivery.zip)、r17 报告/ZIP 均已受控回读。旧失败批次及其幂等键、原始证据保留，不计成功路径 |
| 业务路由核对 | [r16 原始节点快照](../../../discovery/t01-phase1-real/m1-p4-20260922/r16/workflow-snapshot.json)保留旧偏差：代表预选和基座报告误标 N15，N14 先于 N13。已依据[专家一期图](<../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>)修正代码：代表预选为 N12 内部事实，N13 只读 N12/配对事实，N14 对原始 WT 做五轮 FoldX，最终仅 N15；N17 请求不读取 N16，N18 等待两支适用终态。[部署哈希](../../../discovery/t01-phase1-real/m1-p4-20260922/route-deployment-verification-r01.json)及新 r18/r19/r20 严格审计通过；旧 r16 经新审计明确不能充当纠偏证据，P4/M1 旧工程结论不改。快照将代表子工具标为所属业务阶段 N12/N13，子工具回执保留原工具编号；严格审计分别核验这两层标签 |
| 正式资格与交接 | 完整签收、正式数据规模、复杂分支和 WT/Candidate/Agent C 正式交接留待 M2/M3；OPS-001 不阻断本地报告，公开操作单独处理 |
| 单卡基础设施 | OPS-002 保持关闭；资源身份或执行入口变化才重验 |

## 下一步

1. 当前 [HiMat 直连 MCP 最小联调](../PHASE1_DELIVERY_PLAN.md#p4-后续himat-直连-mcp-最小联调)的 P1 代码和测试服部署已完成；下一项仍是从 HiMat 发起新的独立序列任务，核验实际 N01 推理、后续条件路由、进度/卡片及同测试用户受控附件。此次只读核验未新建任务，9–999 aa 策略接收不等于全域推理通过。用户此前暂停 P2 优先处理 BLAST，IEDB 已部署；最新要求继续修复 P2，r12 已基于当前 IEDB 版本部署并核验。已取消两条活动任务并核验全局空闲，P2 本轮恢复依据为用户最新明确指令。用户后续已明确按专家建议恢复 IEDB＋BLAST 并授权下载/导入/完成 N03，当前数据库、N03/E3 接入、测试服部署及有界真实验证已完成，E4 原子坐标与热点合成待补；已取消任务不自动重提。排队与进程归属问题保留核验结果；N05/N08/N09 配置缺口仍待处理；建议计划管理任务按用户“序列＋宿主、可选项暂不新增”更新派生入口说明。宿主物种不替代 MHC 面板或表达宿主；条件不足保留缺项，真实失败明确失败。未调用 `workflow.report` 公开发布路径，助手不操作 HiMat 后台。
2. [FoldX 耗时诊断](../../../discovery/t01-phase1-real/m1-p4-20260922/foldx-runtime-diagnosis-r01.json)已记录同输入、同命令的两次原生时间线及当前容器资源快照；性能优化单独后排，不减少已通过新 run 的既有 5 轮计算，也不改写原证据。
3. 最新用户要求的 N11 确认接续、报告结论修复与专家对照已完成工程交付，generation 85 及验证见下方。新任务实际用户确认后到候选生成的线上整链尚待独立验证；本轮不自动提交科学任务。N06/N13/N15 等实际功能缺口与其余科学签收分别保留，后续范围和顺序由计划管理任务维护。

## 当前验证

- N09 完整库接入：官方 Swiss-Prot 2026_03 原始 DAT/FASTA 共 794102700 bytes，原件位于 `/var/lib/t01/database-downloads/swissprot-2026_03-r01`，官方 MD5/gzip/条目数量校验见[下载证据](../../../discovery/t01-phase1-real/m1-p4-20260922/swissprot-download-r01.json)。已流式建立 575748 条记录、2391158784 bytes 的 SQLite 原始 DAT 压缩索引，位于 `/var/lib/t01/databases/domains/swissprot-2026_03-r01`；每条 canonical 序列与官方 FASTA 独立核验一致，[导入证据](../../../discovery/t01-phase1-real/m1-p4-20260922/swissprot-import-r01.json)。新 0.2 数据格式按序列 hash 索引取有限命中，不再受全库 500 条/16 MiB 限制；每次任务保留命中原始 DAT、来源 hash、投影和复核原因。旧 0.1 小库及旧产物回放保持。来源物种 null 时不加物种过滤，宿主猪不冒充抗原来源；未命中/多命中保留明确状态，不自动转移同源注释；异构体坐标、不确定坐标和非对应成熟链不推测。HiMat 新提交自动启用 N09 并绑定数据库版本的新幂等身份，同 run 的既有下游接续保留。
- [N09 线上核验](../../../discovery/t01-phase1-real/m1-p4-20260922/n09-swissprot-deployment-r01.json)：generation 86 Ready，6 个源码 hash 与本地一致，服务数据库根配置和 HiMat→N09 请求契约通过。P69905 正例、未命中负例、原 233 aa 精确命中 O56129（3 条功能注释）均通过；冷查询含全库 hash 检查约 7.25 秒、缓存后约 0.0067 秒。旧任务/工作流仍可核验且未改写，未新建科学工作流，尚无新完整设计整链证据。[完整当前根回归](../../../discovery/t01-phase1-real/m1-p4-20260922/n09-swissprot-full-r01.junit.xml)2396 passed / 15 skipped / 0 failed；457 份冻结资产只读校验通过，未跨历史分区，不重跑旧完整 Mock/S07。索引当前使用 20 GiB 运行卷，核验时剩余 2267275264 bytes；扩库前须迁独立数据库卷或扩容。N09 同源注释转移、深层 core_map 和科学签收仍未完成；建议计划管理任务同步 N09 当前能力及存储后续项。

- N11 与报告修复：[部署核验](../../../discovery/t01-phase1-real/m1-p4-20260922/n11-confirm-deployment-r15.json)确认 generation 85 Ready、15 个修改文件与部署源一致、其余 165 个既有源码文件未漂移，MCP 可发现提交/查询/确认三工具。真实历史 233 aa 审计按旧规则回放相等；新握手只读回放为 FIXED=0、RESTRICTED=233、OPEN=0，转换有效且需要确认，内存中的确认后请求通过原生契约校验。932 个骨架原子按 PDB 三位小数转换，最大单坐标舍入约 0.0005 Å，原结构保留。原任务及 ZIP hash 未变，卡片明确 `DESIGN_NOT_EXECUTED / N11_MASK_EXPORT_BLOCKED`。没有记录真实用户确认、没有新科学工作流、没有新的候选生成证据；部署前后无活动任务且 GPU idle。确认/权限/恢复/拒绝/报告及坐标格式回归通过；[完整当前根回归](../../../discovery/t01-phase1-real/m1-p4-20260922/n11-confirm-full-r03.junit.xml)为 2392 passed / 15 skipped / 0 failed。前一轮 r02 因 Docker 引擎停止导致 3 项结构前置失败，原记录保留；引擎恢复且固定镜像核验后完整重跑通过。457 份冻结 Mock 只读核验通过；未跨历史分区，旧完整 Mock/S07 未重跑。
- [专家原件—线上实现对照](../../../discovery/t01-phase1-real/m1-p4-20260922/n11-confirm-r01/expert-comparison.json)共 20 项，绑定专家文件与线上源码 hash，覆盖输入、Gate 和 N01–N18。主要剩余差距：N03 E4 坐标、N04 分数口径、N05 面板、N06 热点合成、N07 遮蔽计算、N08/N09 数据接入、N10 RSA/CamSol/综合评分、N12 48/64 追加生成与完整候选池、N13 IEDB 接续及叠合 RMSD、N15 正式筛选/排序/交接、N17 扫描覆盖。设计目标/表达宿主暂不新增、禁止联网结构回退等用户认可范围单列，不当作未授权扩展需求。建议由计划管理任务维护后续范围和顺序。

- HiMat P2 进度修复已按用户最新要求恢复。[r12 部署预检](../../../deploy/m1-p4/himat-progress-r12/preflight.json)及 server dry-run 通过后已部署，generation 83、Pod Ready；[线上核验](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-progress-deployment-r12.json)确认服务 4 文件 hash 一致、MCP 新工具说明、取消任务卡片、旧 nr 500 HSP/报告/ZIP 回读均通过；仅服务状态接口/HiMat 投影/MCP 说明变更，逐文件对比线上确认无额外业务改动，IEDB 提交方法 AST 与已部署 r11 一致。按 N01–N18 统计业务节点、内部步骤单列，reconciling/stop_requested 纳入当前节点；失败、取消、跳过分别计数，节点所有子步骤结束前不提前算完成，节点数不当作耗时百分比。新增只读 Worker 观察，先验证同 run/child/attempt/execution/request hash 与受控路径：waiting_worker=请求提交但无 Worker 执行回执、executing=绑定回执记录运行、finalizing=已停止等待收集、unknown=不可确认；不扫描其他任务进程、不把回执当实时 CPU 采样、不调度/取消任务。[定向回归](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-progress-targeted-r02.junit.xml)54 项通过，[观察层与服务接线](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-progress-observation-r01.junit.xml)27 项通过，[真实历史快照回放与冻结核验](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-progress-replay-r02.json)确认原 3/51→业务 2/18、当前 N03；457 份冻结资产通过，未启动新科学任务。[本轮完整回归](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-progress-full-r02.junit.xml)2376 passed / 15 skipped / 0 failed；补充服务接线测试纳入上述 27 项通过。线上实际代码回放原历史活动快照为 2/18、当前 N03，并用真实停止回执回放 finalizing，未伪造或改写服务器任务状态，未新建科学工作流；实时新活动工作流的前端显示尚未另行验证。[验证汇总](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-progress-validation-r02.json)，部署前后活动任务均为零、GPU idle。早期 r08 预检未部署、旧回归保持历史身份。任务 `429765bb…`（233 aa）的 ESMFold2 真实推理、结构处理与 DeepTMHMM 成功，N03 实际等待单 Worker；此前“仍在原生计算”的归属判断错误。[任务/执行归属核验](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-blast-job-attribution-r01.json)确认 [17:14 原生采样](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-second-blast-progress-r01.json)中的 CPU/读库活动属于 15:59 提交的 `df485abb…`（453 aa），不属于 `429765bb…` 或已出报告的 `120f08a…`。原始采样保留，不能用于证明第二条任务正在计算。`120f08a…` 的 BLAST 原生退出码 0 且 stopped_confirmed=true，解析器失败为 OUTPUT_INVALID，14:07 父任务已结束；未发现该旧任务残留执行证据。两条活动任务按用户明确授权于北京时间 17:27:32–33 取消，[取消回执](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-blast-cancel-confirm-r02.json)与 [17:30 进程/空闲核验](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-blast-stopped-r03.json)确认父子任务 cancelled、停止确认、无 blastp 进程、活动任务为零；`429765bb…` 的原生进程未启动，不能计本轮整链通过。

- 用户提供专家建议保留 IEDB＋BLAST，随后授权下载、导入并完成 N03；该最新决定覆盖旧“移除 IEDB”范围文字，建议计划管理任务同步范围/计划/决定。专家 C20 v10.5 §1–7 为本次实现依据：本地 IEDB 蛋白库、identity≥70%、query 区间覆盖≥80%、可追溯 E3 逐残基映射；nr 保留其既有工程与 N08 补充检索身份，不删除、不追认旧 nr 结果为 IEDB 证据。IEDB 当轮部署保留暂停时的 check 方法；后续用户已恢复 P2，当前 r12 状态见上条。
- [官方下载完成](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-download-complete-r01.json)：SQL gzip 688025297 bytes，SHA-256 `f788be3a2dcdc568bb40c572ae5a031762b5eb42b5ace8b1a6ebf3311cc1ddcb`，gzip CRC/长度与独立落盘 hash 校验通过，原压缩包保留；上游校验和未提供。服务器路径 `/var/lib/t01/runtime/datasets/iedb/20260924-r01`。[导入完成](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-import-complete-r01.json)：流式读取 SQL、仅导入 N03 相关 12 表列，不执行来源 SQL；数据库 9788280832 bytes，索引和 SQLite 完整性检查通过。
- [IEDB 投影完成](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-projection-complete-r02.json)：202501 条蛋白、3618877 条表位关联，其中 3344640 条源序列区间校验通过；缺失区间、修饰肽、区间不匹配和缺少完整来源序列分别披露。官方来源表存在同 ID 完全重复行，构建按全部导入字段去重；冲突版本不任意选取。关联复合物 5439 条，当前导出投影不含可核验原子坐标，E4 为 unavailable，不从编号推定接触或硬约束。[索引构建](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-index-build-r01.json)采用服务器固定 BLAST 2.17，4.89 秒；[数据包 manifest](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-database-manifest-r01.json)绑定 929905671 bytes，manifest SHA-256 `96be17e60c108013d320558817037d081edbf8e3c0ed2f9facf83a2d818b6e12`。
- N03/N06/S27 本地代码已接通显式 IEDB 元数据与 E3 来源链；命中而无法映射保留命中与 warning；未查询不写无命中。E3 按 B/T/mixed/unknown 分流并保留来源 ID，N06 有 E3 时不再使用“只有预测来源”的空热点证明，热点合成保持 review_required；S27 E3 为 RESTRICTED，不提升为 HARD。HiMat 新入口使用 IEDB/70/80，库 hash 进入幂等键，旧任务不重提。最终部署包见 [r11 预检](../../../deploy/m1-p4/iedb-n03-r11/preflight.json)，[线上核验](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-deployment-r11.json)确认 generation 82、Ready、服务 10 个文件和 Worker 2 个文件 hash 一致，HiMat 固定 IEDB/70/80 且 P2 check 保持线上旧方法，旧 nr 500 条 HSP 与原报告/ZIP 回读通过。首轮完整回归的遗留 nr hash 测试断言已修正；[最终完整回归](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-full-r02.junit.xml)2363 passed / 15 skipped / 0 failed；其后真实精确命中发现旧解析器将 alignment length 限于 max(query,subject)，现按含 gap 的列数处理并保留坐标/双 gap 守卫，[定向 88 项](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-gapped-hsp-r01.junit.xml)全部通过，失败 r01 原证据不改。[其他最终定向 65 项](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-final-targeted-r02.junit.xml)通过；[冻结只读核验](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-frozen-readonly-r01.json)457 份通过。未跨历史分区，旧完整 Mock/S07 未重跑。文档检查 306 份现行导航零错误，31 条既有历史引用问题。
- [最终 N03 真实验证](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-native-r02/summary.json)三个新任务全部 succeeded，核验 45 份 ArtifactRef；原 233 aa 原生 BLAST 0.88 秒 / E3 61 条，609 aa 人白蛋白精确命中 1.64 秒 / E3 2217 条，固定随机无命中 0.86 秒 / iedb_hit=false / E3 空；均停止确认。耗时为本轮原生计算，不含所有排队、提交或前端耗时，不承诺全序列固定延迟。[同 run N03→N06](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-native-r01/n06-chain.json)新 BepiPred 与 N03 产物接续成功，45 B＋16 T 区间的来源 ID/ArtifactRef 均保留，空热点证明已撤销；未复用旧运行、未启动完整设计。[收口核验](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-final-idle-r01.json)无活动任务、无残留 blastp、GPU idle，runtime 可用 5555949568 bytes。[验证汇总](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-validation-r01.json)仅为 N03 IEDB 检索/E3 工程通过；E4 坐标、热点科学合成与正式签收未完成，不能计 C20 全科学验收通过。
- [原 233 aa 原生查询](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-native-benchmark-r01.json)在新 IEDB 库用时 5.75 秒、退出码 0、46 条原生 HSP；[真实映射预检](../../../discovery/t01-phase1-real/m1-p4-20260922/iedb-original-mapping-preview-r01.json)返回命中与 61 条 E3 区间、62 条 warning，E4 unavailable。此为有界工具验证，不代表完整新工作流已运行或科学签收；集成 Worker 的最终验证见上条，早期直接查询与映射预检保留原身份。

- P1 [完整当前根回归](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-p1-full-r02.junit.xml)：2320 passed / 15 skipped / 0 failed；Docker 未运行导致首轮 3 条结构夹具失败，Docker 恢复后夹具及完整回归通过。[验证器补充回归](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-p1-verifier-r02.junit.xml)8 项通过，修正 ConfigMap 符号链接路径检查及只读回放的 Linux 存储初始化；业务代码未因此改变。[冻结 Mock 只读核验](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-p1-frozen-readonly-r01.json)457 份通过，未跨历史分区，旧完整 Mock/S07 未重跑。文档检查 306 份 Markdown 当前导航零错误，31 条既有历史引用问题。线上 8 个源码哈希与预检一致；旧 500 HSP、MCP 工具发现、卡片失败披露、报告 2258 bytes/ZIP 85515 bytes 的受控签名下载均通过，任务数未变。新 233 aa 推理与 HiMat 浏览器侧闭环未验证。首任务[139 份原始 ArtifactRef](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-first-review-r01/snapshot.json)、[只读复盘](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-first-review-r01/review.json)及早期[运行中快照](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-first-job-inspection-r01.json)保持原身份。

- HiMat 通用序列后端：先前固定 1UBQ 提交入口已停用并从当前工具目录移除，测试身份只发现 `workflow.submit_sequence`、`workflow.check`；前者收 9–999 aa 大写 AA20 与显式宿主、后台异步运行，后者单次返回节点进度或终态卡片。N18 `report.md` 优先从同一任务已校验的嵌套交付 ZIP 提取，签名报告/ZIP 链接仍限定调用身份、哈希和有效期；HiMat 不暴露会在当前 RustFS 配置公开发布的旧 `workflow.report`。[r04 测试服源码哈希核验](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-sequence-deployment-r04.json)确认服务端和 GPU Worker 的 `/opt/t01/src` 策略/资源配置为 999 aa，Pod 1/1 Ready；该核验遗漏 ESMFold2 原生进程实际导入的 `/backend`，当时限制为 76 aa，233 aa 首轮 N01 因此失败；P1 r07 已修复实际路径并完成只读核验，详见当前摘要。原 393 aa 独立容量案例不追认全域成功。固定 1UBQ 样例结构与掩码没有进入通用请求。用户最终决定按真实门控：缺项透明记录，后续只推进无依赖节点，N18 可交付 WT/缺项报告；不强制 N11 设计链。计划中“固定 M1 测试输入”的表述与本次用户最新决定不一致，建议计划管理任务更新，不由实施任务改写计划。

- HiMat 测试身份 `himat-t01-test` 的 Secret 凭据未入仓库；先在无活动任务时撤去 `submit`，部署与[完整回归](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-sequence-full-r04.junit.xml)通过后恢复 `submit/query/download`，[激活后无任务核验](../../../discovery/t01-phase1-real/m1-p4-20260922/himat-sequence-activation-r04.json)确认 8 aa 非法输入被拒绝、旧公开报告接口不可见且未创建任务。完整回归 2300 passed / 15 skipped / 0 failed；首次沙箱运行因 Docker 管道与 JUnit 目录权限有 3 条同 run 结构夹具失败，6 条夹具在可访问 Docker 的环境复测全通过，完整回归同环境全绿。HiMat 实际工具调用已创建并结束新任务；用户报告已获得报告，助手完成后端卡片及服务内受控下载核验，浏览器侧闭环未独立核验，不扩大既有 P4 验收。[无凭据工具配置示例](../../../deploy/himat-mcp-tool.example.json)供字段核对；文档检查为 `PASS_WITH_HISTORICAL_LINK_ISSUES`，304 份 Markdown 当前导航零错误、31 条既有历史失效引用。助手不查看或操作 HiMat 后台。
- P4 [最终当前根回归](../../../discovery/t01-phase1-real/m1-p4-20260922/full-tests-final.junit.xml)：2267 passed / 15 skipped / 0 failed；另有定向检查 95 项、自动收尾权限边界测试 2 项通过，详见[验证汇总](../../../discovery/t01-phase1-real/m1-p4-20260922/validation-summary.json)。此前两次回归中的瞬时超时测试失败及报告 manifest 漏导出均保留原记录；最终复核通过。报告 manifest 已按 ZIP 原字节导出。

- P4 [来源拒绝检查](../../../discovery/t01-phase1-real/m1-p4-20260922/r02/source-rejections.json)：错 run、错 WT、历史结果冒用、伪造结构 hash、代表候选身份混用共 5 类通过，未改服务器原件。[单卡入口守卫](../../../discovery/t01-phase1-real/m1-p4-20260922/gpu-entry-guard.json)通过；[冻结资产只读核验](../../../discovery/t01-phase1-real/m1-p4-20260922/frozen-mock-readonly.json)457 份通过。未跨历史分区，旧完整 Mock/S07 未重跑。
- N03 v0.2 预建多分卷/alias/元数据 manifest 已适配，旧源 FASTA 路径保留；[真实离线 4 分卷建库与 N03 查询](../../../discovery/t01-phase1-real/m1-p4-20260922/prebuilt-native-r02/verification.json)通过，工程身份保留。123 分卷/1113 原生文件及 gs 快照格式、缺卷/损坏/逃逸/混用守卫纳入[定向回归](../../../discovery/t01-phase1-real/m1-p4-20260922/final-checks.junit.xml)。[目标元数据只读核对](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-metadata-readonly.json)一致；未修改、移动或挂载下载中的 staging。
- 目标 nr [独立全量 SHA-256](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-hash-r01.json)在只读卷核验 2227 文件、740587510662 bytes，耗时 1346.5 秒；[下载盘点](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-inspect-r01.json)、[只读部署](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-deployment-verification-r01.json)及[单卡守卫](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-gpu-entry-guard.json)通过。后续已部署持久化核验回执、BLAST 直连、16Gi/4 CPU 与延长的截止；r12 原生 BLAST 退出码 0，按当前结果契约对原字节回放通过，父任务因当时旧契约失败。最新策略修复持久化回执 `mount_path`，服务 Pod 上 2227 文件回执验证耗时 0.13 秒；本轮 BLAST 契约、缓存及部署补丁定向回归 36 项通过。r16/r17 目标库服务整链均已成功并通过独立审计。
- 本轮 N03 契约和只读挂载变更的[完整当前根回归](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-full-tests-final.junit.xml)：2272 passed / 15 skipped / 0 failed。首次回归因本机 Docker 未运行，same-run 结构夹具 3 项失败；Docker 恢复后[6 项真实 same-run 回归](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-same-run-r01.junit.xml)和完整回归均通过。未跨历史分区，旧完整 Mock/S07 未重跑。
- BLAST 地址空间配置生成与部署补丁共 4 项定向测试通过；新配置只提高 BLAST resident `RLIMIT_AS` 至 1TiB，worker-blast Pod 物理内存限制维持 8GiB。[服务部署核验](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-lmdb-deployment-r02.json)与[Worker 配置核验](../../../discovery/t01-phase1-real/m1-p4-20260922/nr-lmdb-worker-deployment-r03.json)确认固定命令一致，未修改目标库或旧运行证据。P4 最终收口器已改为显式接收设计、WT、失败批次以排除旧失败批次冒用；相关定向回归 10 项通过。

- [P3 独立审计](../../../discovery/t01-phase1-real/m1-p3-20260922/r01/audit-summary.json)：`M1_P3_WT_SCAN_LOCAL_DELIVERY_PASS`，1376 个 ArtifactRef、13 文件 ZIP、同 run/WT 来源及 4 类错误来源拒绝守卫通过；P1 父任务及 P1/P2 本地证据原字节未变。新扫描原始请求与范围见[固定请求](../../../discovery/t01-phase1-real/m1-p3-20260922/r01/scan-requests.json)、[选区依据](../../../discovery/t01-phase1-real/m1-p3-20260922/r01/scan-scope.json)，FoldX 为 21 原生行/20 AA 记录，ThermoMPNN 为 1520 原生记录/20 展示记录。
- [P3 部署核验](../../../discovery/t01-phase1-real/m1-p3-20260922/r01/deployment-verification-r02.json)通过，实际代码哈希一致，单 GPU 入口保持；新扫描的离线限制与原生停止回执均通过。N18 适配及 FoldX 解析相关检查通过；P3 定向回归 39 passed，当前根 UTF-8 回归 2237 passed / 15 skipped / 1 failed，失败为既有 same-run ProteinMPNN 夹具；[冻结 Mock 只读核验](../../../discovery/t01-phase1-real/m1-p3-20260922/r01/frozen-mock-readonly.json)457 份通过。未跨历史分区，旧完整 Mock/S07 未重跑。
- [P2 独立审计](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/audit-summary.json)：`M1_P2_N12_N15_PASS`，1705 个 ArtifactRef 通过，3 条非 WT 候选完成真实接续；[FinalReport](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/final-report.json)仅含调试排序，正式候选/Pareto/best_candidate 为空。
- [验证汇总](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/validation-summary.json)与[完整 JUnit](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/full-tests.junit.xml)：2228 passed / 15 skipped / 0 failed；部署代码、单卡与原生离线核验通过。457 份冻结 Mock 只读核验通过，未跨历史分区，旧完整 Mock/S07 未重跑。
- 管理核对：JUnit 为 2243 项、15 跳过、0 失败/错误；按 P2 审计中的 SHA-256 清单只读复核 24 份 P1 文件，全部未变。审计明确 `report_api_called=false`、`p3_p4_executed=false`，本次不重跑科学审计或计算。
- 本轮文档只读检查：`PASS_WITH_HISTORICAL_LINK_ISSUES`，302 份 Markdown 的现行导航零错误；31 条既有历史失效引用单列，冻结原文未修改。此次仅回填 STATUS 的已完成事实，不重跑业务计算；历史验证与原始回执统一从[历史索引](README.md)查阅。

## 当前边界

缺少签收已不再阻止本轮显式内部测试 N11 路径；未执行、未知和被排除仍如实记录。资源、离线、身份与权限约束保持；默认正式入口、scientific_release_gate、usable_for_pipeline 和生产状态未放行。完整范围和 M2/M3 见[范围](../PHASE1_SCOPE_REBASELINE.md)及[总计划](../PHASE1_DELIVERY_PLAN.md)。P4/M1 工程最小验收通过不等于科学签收、HiMat 用户入口跑通或生产部署。

阶段入口：[W1](../phase1/PHASE1_REAL_W1_BACKLOG.md)、[W2](../phase1/PHASE1_REAL_W2_PLAN.md)、[W3](../phase1/PHASE1_REAL_W3_PLAN.md)、[W4](../phase1/PHASE1_REAL_W4_PLAN.md)、[W5](../phase1/PHASE1_REAL_W5_PLAN.md)、[W6](../phase1/PHASE1_REAL_W6_PLAN.md)、[W7](../phase1/PHASE1_REAL_W7_PLAN.md)。
