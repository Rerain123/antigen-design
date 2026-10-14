# T-01 一期交付计划

> 现行计划；更新：2026-09-20。依据：[交付方式调整](sources/PHASE1_DELIVERY_SIMPLIFICATION_20260906.json)、[N03 只保留 BLAST 的用户决定](DECISIONS.md)。当前执行顺序见[专家流程校准与单卡执行计划](#专家流程校准与单卡执行计划2026-09-19)，下方历次计划保留历史背景。
> 实际进度与当前任务入口只见 [STATUS](STATUS.md)，交付细节见其链接的阶段计划或任务页。

## 专家流程校准与单卡执行计划（2026-09-19）

本节依据用户本次“根据专家文档调整计划、服务器只允许一张A100 64G”的要求，作为当前执行顺序，覆盖下文较早排期；仍在 `PH1-REAL-TARGET-DEPLOY` 内推进，不新增波次。依据为[一期18节点原图](<../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>)、[专家SOP v10.5](../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)的S-27～31及T-01 step16～22，叠加N01离线、N03只保留BLAST的用户决定。工程链到达N18不再作为完整科学流程的完成标准。

**2026-09-20执行校准：** 用户已在无法创建Role/RoleBinding的条件下选定“一个常驻GPU Worker、完整申请一张A100 64GB、内部串行启动不同工具进程”。统一镜像和r03不可变配置已上线，唯一设备守卫、四工具登记、跨spool全局FIFO及ESMFold2真实推理通过；原动态Deployment/RBAC候选停止推进。顺序0的物理单卡纠偏与基础执行层已完成，剩余代表性工具回归并入顺序1的接入验收，不再要求每次切换释放/重建GPU Pod。AF3资产、环境、CPU数据搜索、权重加载和5样本原生推理也已完成；顺序1已进入标准封装与统一任务/N01/S-09的本地实现阶段，但第一版代码尚未通过回归或部署，AF3尚未成为线上第五个命令。

| 顺序 | 当前包内交付内容 | 完成标准与具体依赖 |
|---|---|---|
| 0：GPU资源纠偏；AF3无GPU解压继续 | **基础层已完成。** 现行统一常驻Worker是唯一GPU申请者，完整绑定一张指定`NVIDIA A100-SXM-64GB`；四个既有GPU工具只在其内部串行启动，禁止另起并行GPU Job | Pod/HAMi/运行时唯一设备及ESMFold2真实回归已通过。物理资源约束由唯一Kubernetes申请者和精确启动守卫保证，全局FIFO/停止回执负责进程互斥。剩余三个工具的代表性回归及旧入口守卫并入顺序1，不重开RBAC动态调度方案 |
| 1：AF3部署与结构链接入 | **原生阶段已完成，本地适配器实现中。** 解压/全量文件核验、固定环境、离线数据搜索、权重加载和短样本5次推理均有独立证据；第一版policy/profile/native/standard/result/source及统一任务/N01/S-09接入代码已落盘，但尚未完成本地回归、真实原件标准化或部署 | 保留5个原生样本及最高pTM选择证据；专家原件没有同分科学优先级，全部保留并以最低seed/最低sample序号作确定性工程选择，不得用官方`ranking_score`偷换项目pTM选择。验证通过后登记第五个命令，做AF3一条真实任务及三个受影响既有GPU工具的代表性串行回归；下载、解压、推理和业务接入仍分别报告 |
| 2：N01–N10有效输入与Gate/WT | 并行准备N03目标BLAST库、N08同源库、N09注释；补N06热点和N10可开发性缺项；接入实际设计适用性判断与WT分支 | 工程缺项由后端实现；原件已有规则直接落实，具体冲突留在对应OI，不把整个节点仅因未签收永久置空。区分适合、不适合、输入不足/未评估；固定CLOSED不是业务Gate判定，不适合设计须形成WT评估及原因 |
| 3：N11–N12设计、验证与受控重算 | 证据合成权限→ProteinMPNN→同WT基线ESM-IF1→R-04结构路由→保守检查及六维负担；按SOP执行全淘汰再设计 | 初轮24/0.1，全淘汰后48/0.3，再全淘汰后64/0.5；另核对R-35的10%→15%→20%放宽及留痕。两层重算的组合/停止点若有原件歧义按OI-022定点裁决，不用进程重试代替科学重算。R-04覆盖AF3/ESMFold2及双引擎分支，同卡串行；保存同run/WT/sample/attempt来源，不恢复历史淘汰候选 |
| 4：N13完整变体复评 | 对验证后变体重新执行适用表位预测/地图、结构质量、FreeSASA、局部几何、可开发性五维及糖基化，输出L1–L4与明确降级原因 | L2差值>-0.15、L3两项<2Å、L4差值<0.2按原文实现；L4前20池来源与N15最终top20区分，具体池关系按OI-022闭合。比较模块存在不等于已自动重跑上游；未知热点不得等同已计算空热点 |
| 5：N14–N15评分与选择 | 五维粗评前40池→FoldX BuildModel相对原始WT→六维终评→硬过滤→Pareto→目标权重→家族配额/序列去重→top20→SC-10 | 按原件落实池来源、结构/膜蛋白守卫、缺失稳定性中性值、同分/空池及SC-10处置。移除S-23/宿主同源作为一期必需排序阻塞的残留，保留“一期未评估”披露；不能把空报告或排序夹具当真实排名 |
| 6：N16/N17→N18汇合 | 有表达宿主且有合格序列才做DNA Chisel；适用WT稳定性扫描实际调用FoldX PositionScan/ThermoMPNN；汇合候选/WT/失败、证据和缺项 | N17校验扫描域、FIXED/RESTRICTED排除、单体限制和比较集合；参考组装的scan_invocations=0不算扫描完成。N16/N17按条件汇合，不把任一分支成功当完整交付；报告发布须显式授权 |
| 7：整链与入口验收 | 满足适用科学消费条件后执行真实目标整链，再集中HiMat与最终交接验收 | 覆盖适合设计、WT、不足/失败、全淘汰重算、条件DNA和受影响生命周期；保留实际调用清单与来源。科学/生产门禁继续独立判断，不强求所有输入均产生候选 |

已通过的ESMFold2、ProteinMPNN、ESM-IF1、FoldX、ThermoMPNN等独立工程验收保留，仅做新编排、GPU迁移和来源绑定影响到的回归。AF3遗传/模板数据库不得直接视为N03/N08/N09业务库。ESMFold2长度扩展和Pod崩溃恢复保持后续支持域工作，不抢占本轮流程补齐主线。

职责：助手准备实现、测试、部署清单和核验；用户执行上传、apply、切换/重启及新实跑。算法负责人只裁决具体科学冲突及签收，不将已有原文规则再次列为泛化待确认。当前进度只见STATUS，W5/W6/W7继续承载各包细节。

## 1. 总体策略

按 [现行范围](PHASE1_SCOPE_REBASELINE.md)交付 N01–N18 全部业务节点；N03 只保留本地 BLAST，移除 IEDB 检索。冻结 Mock 提供原范围的工程参考，真实能力使用独立源码、契约、运行根与 DSL，并落实现行工具边界。
以可调用的工具和可复现的局部链作为开发交付单位；设计、实现、测试和评审在同一个包内完成。
日常不为每次准备、补证或修复再建立任务包。一个包推进到约定完成标准或具体外部阻塞。

### 计划维护

依据 [用户的管理授权](DECISIONS.md)，由本次承接授权的管理任务统筹计划与文档维护，实施任务负责回填可核验的交付事实。

| 层级 | 维护内容 | 唯一位置 |
|---|---|---|
| 整体实施计划 | 一期交付目标、W1–W7 依赖与放行条件 | 本页；范围以范围基线为准 |
| 阶段与交付包计划 | 当前波次的交付包、范围、完成标准与必要接口 | W1 任务页、W2–W7 阶段计划；跨波次集成包见本页；见下文链接 |
| 当前执行安排 | 已完成、正在推进、具体阻塞、下一项 | STATUS；实现细节链接到对应任务章节 |

收到交付结果、阻塞变化或用户决定时，核对代码与证据后更新适用层级；定期检查三层计划与文档是否一致。阶段计划随实际交付滚动细化，不预先展开全部远期小任务。
管理任务可直接调整既定范围内的顺序、合并过碎步骤、纠正状态与整理派生文档；范围取舍仍由用户决定，科学裁决由算法专家负责。已有开发完成证据的包不因科学签收未齐而重新列为开发待办。
每次安排给出明确交付目标、完成标准和依赖它的具体条件；达到标准即转入下一可执行包。文档巡检规则见 [文档入口](../README.md)，不另建管理台账或周期报告目录。

## 2. 新一期 Mock 路线

M1 规格、M2 后端、M3 Dify、M4 冻结的历史入口见 [基线索引](phase1/README.md)。
冻结资产只读验证；Mock 的 MOCK_DATA、scientific_compute=false 身份不能改作科研结果。
旧 P0–P7 属于 [历史工程资产](../../legacy/README.md)，不参与一期范围或完成度。

## 3. 真实能力实施波次

W1–W7 保留为业务交付分组，不要求所有独立工具开发严格串行。

| 波次 | 节点 | 交付目标 |
|---|---|---|
| [PH1-REAL-W1](phase1/PHASE1_REAL_W1_BACKLOG.md) | N01–N02 | 输入、本地结构/AF3/ESMFold2、S-09、DeepTMHMM、条件 FreeSASA |
| [PH1-REAL-W2](phase1/PHASE1_REAL_W2_PLAN.md) | N03–N06 | 本地 BLAST、B/T 预测、表位地图与局部联调；无 IEDB 检索 |
| [PH1-REAL-W3](phase1/PHASE1_REAL_W3_PLAN.md) | N07–N09 | 条件糖基化、同源保守性、功能域 |
| [PH1-REAL-W4](phase1/PHASE1_REAL_W4_PLAN.md) | N10 + Gate | WT 可开发性、设计判断及 WT 交付子路径 |
| [PH1-REAL-W5](phase1/PHASE1_REAL_W5_PLAN.md) | N11–N12 | 候选设计、验证、受控重算 |
| [PH1-REAL-W6](phase1/PHASE1_REAL_W6_PLAN.md) | N13–N15 | 表位保护、稳定性、综合排序 |
| [PH1-REAL-W7](phase1/PHASE1_REAL_W7_PLAN.md) | N16–N18 | 条件密码子、WT 稳定性参考、完整交付 |

### 开发顺序与生产依赖

- 各工具具备自身原始实测、必要接口和可执行守卫后，可开发适配器、独立测试和局部联调。
- 目标服务器、无关模型或其他工具的科学签收缺失，只阻断依赖它的动作。W2 独立序列工具可提前开发与验证，成果归 W2。
- 按[用户安排](DECISIONS.md#n08-安排与工程回连依赖)，N08 可用本机工程序列集完成真实收集、去冗余、比对、保守性计算与区域提取，服务器数据库另作目标验收；N03→N06 工程回连不依赖服务器验收，沿链保留工程数据身份，完成标准见 W2/W3 原包。
- 未定规则分支明确拒绝或标记需复核；只能实现有来源的规则，不以“开发模式”猜测科学判据。
- 上游未批准时可做标明用途的契约夹具测试；真实工具调用、回放、故障注入与 Mock 分开记证据。
- 后续波次的生产依赖仍须采用已完成适用门禁并冻结的真实输出；局部通过不能宣布整波或全链通过。
- 局部离线包和独立真实 Dify 调试入口可提前验证；未完成节点不以 Mock 冒充真实能力。完整包与生产发布仍等待全部必需能力。

### W1 四个交付包

通用运行底座 → DeepTMHMM 接入 → 本地结构分析链；预测结构链按服务器/资产条件推进，最后汇合完整 W1 发布。
实现范围与完成标准集中在 [W1 任务页](phase1/PHASE1_REAL_W1_BACKLOG.md)。
旧 W1-00～13 与 A/B/C 编号保留用于追溯，不再作为逐项停下来另建准备任务的顺序。

### 跨波次接口与外部准备

保留工具的许可证、权重、BLAST 目标库/索引、本地同源/注释数据和 CamSol 参数持续准备，按 [开放项](OPEN_ITEMS.md)落实责任与使用前条件；IEDB 检索服务与专用部署任务取消。
W1–W2 启动 N18 字段生产者、WT/Candidate/Failure、认证/幂等/确认核对；W4 在 N01–N10、Gate 和 N18 WT 子路径满足适用门禁后做真实 WT 联调。
OI-021 在 Gate 科学消费前闭合；OI-022 在 W5 N12 输出契约冻结前先明确前 20 池与排序关系。
FoldX/ProteinMPNN 的实际交付属于后续波次，不扩大 W1。AF3/ESMFold2 改由用户亲自部署，助手逐步指导；同事部署分工取消。主开发负责统一运行层与下游结构链接入。[部署与接口说明](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md)保留技术要求，原同事工具包仅为历史参考。

## 已完成交付包：本地真实流程集成

任务标识：`PH1-REAL-INTEGRATION`。

本包连接现有工具、任务状态与本地交付入口，完成一次提交到报告导出的工程闭环；不新增 W8，不重复实现已验收工具。实际执行状态只在 STATUS 维护；逐节点剩余能力与外部依赖见 [W7 盘点](phase1/PHASE1_REAL_W7_PLAN.md#全项目剩余工程与外部依赖盘点)。

**交付目标：** 可信本地操作者提交序列、宿主、可选本地结构及明确的工具参数后，由后端管理同一流程的子任务、依赖、产物引用、停止与报告。用户不再手工逐工具拼接 job_id / ArtifactRef。复用已有任务库、Worker 与资格守卫，不由 LLM 计算路由判据。

- 输入与执行：明确 allele、登记数据库和必要参数由输入或已批准配置提供；缺少参数、资产或科学资格时分别说明具体未执行原因。首批使用本地结构和现有合法资产；无结构而预测服务未部署时明确阻断依赖结构的动作，不联网回退。
- 依赖与身份：流程记录节点到子任务的绑定、同序列/结构身份、固定配置和原始产物。按已有契约允许的工程回连执行，工程回连不等于科研消费；设计 Gate 未放行时不自动生成候选。不把所有节点均执行作为本包通过条件，也不把未执行标成成功。
- 生命周期：一次提交、整流程/单节点查询、取消、超时、进程中断后恢复及幂等重提可用；恢复不重复运行已完成子任务，父流程取消后不继续启动子任务。任务失败重试与 N12 科学重算分开，未定重算规则不开放。
- 交付：接通现有 N18 适用的本地报告/ZIP 组装，列出执行、跳过、失败和待复核节点及原因；有完整来源证据可复用，不能把历史回放写作本次新执行。正式 WT/CandidateRecord、科学排名、Agent C 和生产放行继续遵循原门禁。

**完成标准：** 至少一条新批次真实本地输入→可执行分析链→本地报告路径完成，记录实际调用而非仅回放；对缺结构服务、缺数据库/allele、上游失败、Gate 未放行、取消与恢复、幂等和来源篡改验证适用行为。原24条全淘汰仅作保留身份的历史回连回归，不强求产生候选。报告及ZIP链接可解析，产物完整性通过，执行受影响集成与运行层回归。新增代码和证据回填本节，接口实现后再补真实路径与复现命令，不预建空链接。

本包完成后接入真实 HTTP/MCP 与 Dify 调试，再汇合目标 Linux 部署与全链验收；具体安排根据本包成果校准。服务器 AF3/ESMFold2、目标数据库与科学开放项沿既有责任继续跟进，只阻断其依赖动作。S-32/MD 已被一期范围排除，不作为剩余待办。

### 本地真实流程接口与实施回填

实施证据：2026-09-10 [acceptance-r02索引](../../discovery/t01-phase1-real/integration-20260910/acceptance-r02/index.json)，610份文件、329项发布产物、26个父/子任务。新1UBQ本地原件完成N01结构、N02 DeepTMHMM、N04 BepiPred、N06/N07、WT草稿、N15缺项报告、N17缺扫描参考、N18组装，共9个新子任务；不是历史回放。另一流程保留缺库的BLAST失败、缺allele参数阻断和N06真实失败，继续输出缺项报告。历史流程仅显式复用原结构/变体报告，原24条仍全部淘汰，无最佳候选、DNA或Agent C载荷。

入口为[统一CLI](../../scripts/t01_runtime.py)的`workflow-submit / workflow-get / workflow-export`，实现为[workflow](../../src/t01_phase1_real/development/workflow/service.py)。父任务登记`t01.real.local_workflow / N18`；父子复用同一SQLite任务、事件、幂等和Artifact表，不建立第二套任务库。子任务创建与父关联同事务，停止意图阻止后续派发；控制器用进程身份防重复调度，恢复核对已记录子任务，不重跑成功任务。模型任务沿用原容器监督与停止确认。父期限自首次启动计时，子任务期限受剩余时间约束。

一次新提交并执行（可信本地操作者，Windows/Docker已就绪）：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:/work/蛋白智能体/var/t01-phase1-real/my-local-flow workflow-submit --input discovery/t01-phase1-real/integration-20260910/acceptance-r02/inputs/fresh-structure-predictors-report.json --structure-file discovery/t01-phase1-real/integration-20260910/acceptance-r02/inputs/fresh-structure-predictors-report.structure --key my-local-flow-01 --run
```

该例使用归档的明确工程输入，启动新任务；`--run`在本地进程中持续调度至终态。不带`--run`仅提交排队；进程中断后可用同一根恢复，当前包不包含常驻HTTP/MCP服务或Dify。

| 请求字段 | 约束 |
|---|---|
| protein_sequence / user_sequence_id / host_species | 必填；精确9–2000 aa AA20序列、标识和明确宿主，不替用户归一化 |
| expression_host / organism | 明确值或null；不猜宿主面板，不自动把WT输入送入独立N16优化 |
| structure | null或现有本地结构metadata，去掉由父流程提供的protein_sequence/host_species；与`--structure-file`同时提供，结构字节注册并校验hash |
| analysis | 必须列出topology、blast、bepipred、netmhc、homology、domains、developability；null表示本分支未启用/未提供。对象只给该工具既有明确参数，序列/宿主/结构和拓扑来源由后端填入，禁止覆盖 |
| reuse_jobs | 默认空对象；可显式指定structure、variant_report、wt_reference的同库历史job_id。后端解析ArtifactRef并标记HISTORICAL_REUSE；序列、宿主、产物hash和N18递归结构批次校验仍执行 |
| timeout_seconds | 父流程总期限1–7200秒；不在恢复时重置 |

数据库根沿用CLI顶层`--blast-database-root / --homology-database-root / --domains-database-root`；工具参数仍需登记ID和manifest hash。父流程固定配置与实现profile，子任务记录各自固定规则、工具profile及原始请求；配置或来源变化不静默接续。

运行根`--root`必须为绝对路径。取得提交返回的父job_id后，以下操作作为上述CLI子命令，使用同一`--root`：

```text
workflow-get --job-id <父job_id>
workflow-get --job-id <父job_id> --node bepipred
cancel --job-id <父job_id> --key stop-01
recover --job-id <父job_id>
wait --job-id <父job_id> --seconds 1000
workflow-export --job-id <父job_id> --output local-workflow.zip
```

`recover`接续同一父任务；仍运行时由`wait`或后续恢复调用推进。已取消终态不会被恢复成运行；显式`retry`创建新父任务/尝试，属于工程任务重试，不开启N12科学重算。`workflow-get`复核关联产物；普通`get/events/execution/result/artifact`仍可用于父子任务。导出使用已核验产物且不覆盖既有目标文件。取消/超时/完整性失败不提供流程ZIP。报告中的父生命周期快照标明为终态发布前采集；当前状态以任务查询为准。

可直接查阅[新执行流程摘要](../../discovery/t01-phase1-real/integration-20260910/acceptance-r02/cases/fresh-structure-predictors-report/workflow-report.md)、[机器报告](../../discovery/t01-phase1-real/integration-20260910/acceptance-r02/cases/fresh-structure-predictors-report/workflow.json)、[本地流程ZIP](../../discovery/t01-phase1-real/integration-20260910/acceptance-r02/cases/fresh-structure-predictors-report/package.zip)和[原24条历史回连包](../../discovery/t01-phase1-real/integration-20260910/acceptance-r02/cases/historical-24-retained-exclusions/package.zip)。流程包内包含节点记录、hash清单及已有N18 ZIP；N18内部保留原报告/数据/方法/缺项。全部结果仍为DEVELOPMENT_UNREVIEWED、usable_for_pipeline=false、NOT_DEPLOYED；执行成功不是科学签收。Gate关闭、缺结构服务、缺库/allele和未执行分别列示，不生成正式候选，不自动交接，不把S-32/MD列为待办。

最终当前根回归1683项通过、1项跳过；专项回归85项通过，覆盖父子生命周期、终态发布前取消不导出ZIP、恢复不重复任务、并发调度栅栏、CLI和证据检查。r01为初批记录；r02已包含终态取消边界修复，执行profile与当前代码一致。两个批次各610份文件均独立核验，原生DeepTMHMM容器内链接保留原字节，文档检查器仅排除对应原生产物路径并增加回归。CLI导出的ZIP与r02封存包逐字节一致。[最终验收汇总](../../discovery/t01-phase1-real/integration-validation-20260910/summary.json)、[当前根日志](../../discovery/t01-phase1-real/integration-validation-20260910/current-root-final.txt)、[专项测试日志](../../discovery/t01-phase1-real/integration-validation-20260910/targeted-final.txt)、[r02独立复核](../../discovery/t01-phase1-real/integration-validation-20260910/acceptance-r02-audit.json)与[CLI复核](../../discovery/t01-phase1-real/integration-validation-20260910/cli-profile-verification.json)单独归档。

检查入口与复核命令见[运行手册](../development/RUNBOOK.md#本地真实流程集成检查)。本包工程实现不等于全项目/一期完成；HTTP/MCP、Dify、目标Linux、模型/目标库部署与科学签收继续按原计划及责任安排。

## 真实服务接口与 Dify 局部联调

任务标识：`PH1-REAL-SERVICE`。

**交付目标：** 将已验收本地真实流程通过认证服务供 Dify 调用，完成真实提交、查询、取消、结果与报告获取。复用现有 Runtime、SQLite、父子任务和 ArtifactRef；不另建科学计算或任务状态实现。本包仍是开发接入，目标 Linux Worker 与生产部署另验。

- 服务契约：实现适合现有 Dify 环境的 HTTP/MCP 接入，先核对环境和现有协议再确定传输方式，避免为名称重复建设两套业务接口。包括结构文件受控上传/登记、流程提交与幂等键、流程/节点查询、取消、受控恢复/重试及已校验报告下载。请求不得指定服务器任意路径、命令、运行根或数据库根；数据库仍以登记身份引用。
- 运行与访问：服务端固定运行配置、认证与资源边界，凭据由环境或本地受控配置注入，不写入仓库和日志。提交后后台执行，不依赖客户端连接存活；服务重启能协调现有任务，避免多控制器重复派发。查询、取消和下载校验调用者权限；无凭据、越权、非法路径与篡改请求明确拒绝。
- Dify：采用独立真实 DSL 生成源和 provider 身份，不改冻结 Mock。输入收集、提交、等待/查询、后端固定状态路由、报告获取及失败说明贯通；Dify/LLM 不计算科学规则，不以超时轮询冒充完成。实际导入、绑定、回读与新运行留证据，凭据不进入导出 DSL。
- 完成标准：经认证服务完成至少一条新批次真实工具执行到报告下载；验证重复提交、断开连接、取消、服务重启恢复、权限拒绝、产物完整性和科学 Gate 关闭行为，执行受影响服务/运行层回归。可用 Dify 环境完成同链实际联调后才记该部分完成；环境不可用时保留具体阻塞，不能用模拟请求宣称 Dify 已接入。

本包实现、接口与证据回填本节；不预建无内容文档或链接。原24条全淘汰保持；科学消费、正式交付与 Agent C 不开放。服务器模型/数据库部署和科学裁决沿既有责任跟进。完成本包后依据实际剩余条件安排目标环境集成，不把本机服务验收等同于一期发布。

### 真实服务接口与 Dify 实施回填

2026-09-10 本机开发接入与真实 Dify 局部联调完成。`service_api`在同一监听端口提供 REST 与 Streamable HTTP `/mcp`；Bearer 凭据只从进程环境读取，映射到调用者和`submit/query/control/download/upload`权限。服务 ACL/幂等/受控上传元数据与原 Runtime 同根但分库存放，科学任务、事件、执行与 Artifact 仍只有原`state.sqlite3`一份权威状态。调用者按独立`t01p1r` scope隔离；结构只接受有界 base64 上传并返回不透明 ID，请求不能传服务器路径、命令、运行根或数据库根。响应和日志不记录令牌。

REST 提供`/healthz`、`POST /v1/uploads`、`POST /v1/workflows`、流程/节点查询、`cancel/recover/retry`及验证后 ZIP 下载；MCP provider `t01-phase1-real-service-v01`登记对应8个工具。提交先持久化再后台调度，不依赖客户端连接；进程启动扫描本调用者活动任务。模型子任务在“持久化保留→监督器登记”间有有界注册栅栏，避免快速查询把启动窗口误判为中断；超过窗口仍交给原 Runtime 的停止确认/恢复规则。相同幂等键同字节重放原任务，不同字节冲突；控制操作另行幂等。所有查询、控制和下载先校验任务归属。

独立 DSL 生成源位于[service Dify generator](../../src/t01_phase1_real/service_api/dify.py)，模板和本机 Dify 1.17 绑定分别位于[template](../../dify/t01-phase1-real-v0.1/templates/T01_Phase1_Real_Service_v0.1.template.dify.yml)与[bound](../../dify/t01-phase1-real-v0.1/bound/local_dify_1_17/T01_Phase1_Real_Service_v0.1.bound.dify.yml)。应用身份为`T01_Phase1_Real_Service_v0.1 / t01_phase1_real_service_v01.workflow.main`，只执行提交或读取已有任务、等待后端固定状态、成功取报告、否则原样返回失败；不包含 Mock provider、科学计算或凭据。实际创建 provider、认证枚举8个工具、导入、图回读及两次 Dify debugger 运行均完成：成功路径为新服务任务到报告，失败路径保留`PROFILE_NOT_APPROVED`。导出不含凭据，Dify 只保存其加密 header；本轮一次性明文传输文件已删除。验收结束后开发服务已停止，不能把留存的本地 app/provider 视为生产可用端点。

最终[acceptance-r02索引](../../discovery/t01-phase1-real/service-integration-20260910/acceptance-r02/index.json)含36份文件、9个服务案例与2次真实 Dify 运行；真实断线后的 BepiPred 任务成功，取消后不提供报告、恢复保持取消终态、重试新任务成功，服务重启接续同一任务，配置漂移失败关闭，缺凭据/错误凭据/跨调用者访问与外来上传均被拒绝。两个下载 ZIP 与 Dify base64 报告逐字节一致并递归核验清单。r01保留首次实跑中发现监督器登记竞态与未捕获 Windows 断线异常的未完成事实，不计 PASS。

[独立复核](../../discovery/t01-phase1-real/service-validation-20260910/evidence-audit-r01.json)确认36份索引文件、14份源码/配置快照、6个关联任务、4层 ZIP/28个成员、8个 provider 工具、2次 Dify 运行及0条凭据泄漏命中一致。新增服务专项7项通过；最终当前根1690项通过、1项既有跳过，457份 Mock 冻结资产只读核验通过，旧完整 Mock/S07未跨分区因而未重跑，见[测试汇总](../../discovery/t01-phase1-real/service-validation-20260910/test-summary-r01.json)。运行与复核入口见[运行手册](../development/RUNBOOK.md#真实服务与-dify-局部联调检查)。本包继续固定`scientific_gate=CLOSED / usable_for_pipeline=false / production_status=NOT_DEPLOYED`；原24条淘汰、正式候选、Agent C、目标 Linux 与生产发布均未改变。

管理复核以 r02、独立审计和测试汇总作为本包冻结输入；r01 仅保留启动注册竞态的未完成事实，不作为后续部署的有效验收基线。

## 目标 Linux 部署候选包

任务标识：`PH1-REAL-TARGET-PACKAGE`。

**交付目标：** 将本机已验收的真实服务、流程运行层和 Dify 资产整理为可在目标 Linux 环境离线安装、配置、验证和回滚的发布候选；现场改由用户操作、助手逐步指导。发布候选完成和目标部署完成分别记录，不能以安装说明或本机容器代替服务器证据。

- **固定基线：** 输入只采用真实服务 r02、其独立审计与测试汇总；记录源码、依赖、服务契约、Dify 模板/provider、数据库迁移和运行配置的版本与 hash。r01 不进入发布候选。
- **可移交安装包：** 提供 Linux x86_64 的离线依赖、安装/升级/回滚、服务与 Worker 启停、健康检查、日志和数据目录约定。凭据、许可受限模型和大型数据库不打入仓库通用包；以受控 profile、manifest 和现场路径绑定，缺失时预检明确失败。
- **Linux 运行适配：** 复用现有任务、幂等、ArtifactRef 与父子调度语义，补齐 Linux 进程/容器停止、崩溃恢复、权限和并发边界；不得沿用未经验证的 Windows Job Object 假设。目标服务使用持久密钥、受限账号和明确网络边界，Dify 绑定目标 endpoint 后重新导入、回读和实跑。
- **外部资产汇合：** AF3/ESMFold2 按[服务器部署交接说明](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md)独立交付；BLAST、N08、N09 等服务器数据库分别登记身份、用途、版本、许可、manifest 与索引。现场已有数据库不能仅凭路径存在即获得项目资格。
- **完成标准：** 本地候选包在干净 Linux x86_64 验证环境完成离线安装、启动、升级/回滚和无资产失败预检，且内容清单、SBOM/依赖锁定、hash、复现命令及运维说明齐全；目标 A100 环境另完成资源盘点、资产绑定、禁网工具实跑、服务重启恢复、认证隔离、Dify 成功/失败链与报告下载。只有后者有现场证据时才更新目标部署状态，科学 Gate 和生产发布仍独立判断。

本包实施与目标回填继续集中在本节及 STATUS，不新建空计划页。若暂时拿不到服务器访问或资产，先完成可独立验证的发布候选和精确预检，把阻塞限定到具体现场动作；不等待科学开放项才做部署工程，也不把部署成功写成科研可用。

### 当前实施：本地 Linux / Kubernetes 发布候选

服务器现场信息与管理员协作暂不可用时，先完成本子包；它是 `PH1-REAL-TARGET-PACKAGE` 的本地部分，不新增波次。

**资源规划基线（2026-09-10）：** 用户确认项目可使用 1 张 A100、可用显存 64 GB。首轮按 GPU 工具串行规划项目容量为 32 vCPU、192 GiB 内存、1 GPU；这是部署估算，不冒充集群 ResourceQuota。控制面单副本请求 2 vCPU/8 GiB、上限 4 vCPU/16 GiB；AF3 合并数据准备与推理任务请求 16 vCPU/160 GiB 和 1 GPU；ESMFold2 请求 8 vCPU/64 GiB 和 1 GPU。其他现有 CPU 工具沿已验收的 2–8 CPU/适用内存配置串行或受控并发，不能与 AF3 同时超出总预算。A100 的物理型号、整卡/MIG/vGPU 方式及 Kubernetes 资源名仍由目标预检记录；未实测前不承诺最大输入长度。

持久存储继续按 2 TiB 规划：任务状态和运行产物使用独立可写卷，模型与数据库使用只读共享卷；AF3 数据库优先使用高速缓存。具体 PVC 容量、StorageClass 和可用高速盘由目标环境确认后冻结。

**本轮范围：** 在 T-01 项目内建立独立发布候选，不修改或复用根目录“工具部署”独立项目的发布身份。固定 Python/Linux 依赖和服务源码，构建 Linux x86_64 控制面镜像及离线镜像包；提供单副本 API/控制器、Service、PVC、Secret/ConfigMap 模板和最小权限 ServiceAccount/RBAC。运行状态与产物使用同一持久卷，模型与数据库使用单独只读卷占位及受控 profile，不把路径、令牌或许可资产写入镜像。

将执行层从 Windows 专用监督实现中抽出明确平台接口：Windows 现有行为保持回归；Linux 实现必须具备进程树停止、超时、崩溃恢复和任务归属核验。需要科学镜像的子任务形成确定的 Kubernetes Job 规格和状态映射，禁止 Docker-in-Docker 或挂载宿主 Docker socket；本轮可在无集群条件下验证清单生成、拒绝非法配置和状态转换，只有真实集群执行后才记 Job 运行通过。

**本轮验收：**

- 从服务 r02 固定基线构建可复现候选，生成版本、依赖锁、镜像 digest、文件清单/hash、SBOM、安装/升级/回滚和备份恢复说明；r01 不进入候选。
- 在干净 Linux 容器环境断网导入并启动服务，以临时凭据验证健康检查、认证、上传、提交、查询、取消、恢复、重试和报告下载；至少执行不依赖外部科学资产的真实路径，缺模型/数据库时由预检准确关闭相应分支。
- 验证单副本和持久卷约束、进程重启接续、只读根文件系统、非 root、受控可写目录、Secret 不入日志/产物、路径越界拒绝及候选篡改检测；执行受影响运行层、服务、Dify生成/绑定和文档检查。
- 生成但不应用目标 Kubernetes 清单；默认填入上述估算并允许现场收紧，不能把集群总容量写成项目配额。输出一份现场待填 profile，预填 1 张 A100/64 GB 可用显存，保留 namespace、Harbor 地址、GPU 分配方式和资源名、StorageClass/PVC、Ingress/Dify endpoint 及数据库/模型资产身份待确认。

本子包完成状态只可写“本地发布候选完成 / 目标未验证”。后续现场包负责推送 Harbor、创建资源、绑定资产、实际 Kubernetes Job、Dify 目标 endpoint 和断网端到端；应用资源前另按现场权限与配置复核。

### 本地 Linux / Kubernetes 发布候选实施回填

2026-09-10 本地子包完成。服务 r02、独立审计和测试汇总以 [BASELINE](../../deploy/t01-phase1-real-target-v0.1/BASELINE.json) 的大小/hash 固定，r01 未进入候选。Windows 四份早期冻结运行源码恢复为历史验收原字节；新增 Linux 入口在加载服务前选择 POSIX 文件锁/原子 no-replace 发布、进程组、PID 出生标记和资源边界，Windows 原 Job Object 行为继续通过回归。Linux 科学执行明确拒绝 Docker socket，并形成只生成不提交的 Kubernetes Job/状态映射。

[扩展发布目录](../../deploy/t01-phase1-real-target-v0.1)含固定 Linux/amd64 镜像 tar、17份 wheel、SPDX 2.3 SBOM、源码索引、逐文件索引、安装/升级/回滚/备份说明、现场配置表，以及 Namespace、ServiceAccount、Secret、ConfigMap、2 TiB PVC、最小 Role/RoleBinding、单副本 Recreate Deployment、Service 和10份科学 Job 模板。控制面采用非 root、只读根、受控写卷；资源按 2 CPU/8 GiB 请求、4 CPU/16 GiB 上限，现场表预填 1张A100/64 GiB 与32 CPU/192 GiB估算，但不写作 ResourceQuota。科学镜像字段保留现场 Harbor digest 占位，原本机 image ID 另作来源收据，避免混淆两种 digest。

本地 Docker Desktop Linux/amd64、internal-only 网络和全新卷完成无网络启动；实际验证认证、结构上传、路径越界拒绝、提交/查询、取消、显式与启动恢复、重试、幂等冲突、跨调用者拒绝、报告 ZIP 递归 hash、单引擎 `ASSET_MISSING`、rc1→rc0→rc1、停止写入后的完整卷备份及新卷恢复。服务中断后的最终 rc1 日志观察 `recovered=1`；独立运行层真实超时得到`TIMEOUT`并确认进程树停止，POSIX 进程组停止由活动数1降为0。Secret 未写入日志/产物，目标服务器未连接，Kubernetes 资源未应用。最终镜像、SBOM、离线 ZIP 和验收索引以本节链接的机器收据为准。

结论严格为：**本地发布候选完成 / 目标未验证**。`production_status=NOT_DEPLOYED`、`scientific_gate=CLOSED`、`usable_for_pipeline=false`和原24条排除全部保持；真实集群 Job、Harbor、资产 PVC、TLS/域名和目标 Dify endpoint 留给后续现场包。

## 服务器部署与真实运行验收

任务标识：`PH1-REAL-TARGET-DEPLOY`。本地发布候选已完成，以上章节保留原验收范围，不再作为未完成开发清单。
  
当前执行顺序以[部署续行计划](#部署续行计划2026-09-16)为准，[测试服流程优先安排](#测试服流程优先安排2026-09-15)的完成标准继续适用，覆盖本页历史批次中“首个工具完整验收后再扩展”及生产检查前置的排期。用户操作服务器，助手提供批量配置和清晰操作步骤；主开发承担运行层与 HiMat 接入，算法负责人承担科学裁决。以下三项目标保留长期职责与历史部署背景，不作为当前逐项串行清单。

1. **控制面在目标集群可用：** 以已验收离线包为输入，生成独立现场渲染件，确认仓库地址、namespace、存储及拉取凭据，导入镜像并部署单副本服务；验证认证、持久化、重启和下载。现有 oligosmith 只作只读参考，不修改其资源。名称按[项目命名决定](DECISIONS.md#项目命名)执行，仓库实际地址仍待建立后确认。
2. **真实工具在 Kubernetes 执行：** 先选资产已齐的工具完成 Job 提交、查询、取消、超时和恢复到报告的真实链，再扩展数据库工具及其他模型。当前仅生成的 Job 模板不是调度后端完成证据；核对并补齐控制器与 Kubernetes API、产物共享和权限接口。缺库只阻断对应工具。
3. **AF3/ESMFold2 自行部署与回连：** 用户按既有部署说明逐个完成合法资产登记、固定环境、禁网推理及真实结构输出，主开发接入任务层与下游结构链。单 GPU 串行运行；两模型分别验收，不等待同事交包。模型加载成功不能替代完整输入到输出的验收。

本地候选r01的4份索引文件及116,909,558字节离线ZIP经管理复核大小/hash一致；归档源码/测试结论沿候选证据保留。候选目录、ZIP及镜像内549份快照保持原字节；现场配置表中旧“同事参与”措辞仅属封存版本，现行责任以本节为准。修改现场配置后另生成版本及hash，不回写旧清单。

当前测试服完成标准见下节，实际用户链路采用 HiMat；既有 Dify 回连保留为历史局部联调。部署状态按实际组件回填，完整一期仍需科学开放项、业务分支和正式交付验收。N10、真实热点、N12重算及Agent C等按原开放项继续跟进，不因部署排期而取消。

### 模型接入续行计划（2026-09-17）

**N12同次运行工程验收准备（2026-09-18）：** 为避免独立成功任务被错误拼成“同run”来源，已将`expected_run_id`强制传入runtime/supervisor及ProteinMPNN、ESM-IF1、ThermoMPNN、FoldX和N12预测来源验证；同run辅助测试4/4、N12适配/来源测试9/9通过。新验收入口`scripts/run_n12_esmfold2_acceptance.py`只接受一条新同run工程链：N01结构→ProteinMPNN→ESM-IF1→原sample_number显式选样→ESMFold2→N12只读证据绑定；不修改旧24条全排除结果，不开放R-04自动选择，R-35、科学Gate和`usable_for_pipeline=false`均保持。r04部署准备同时发现控制面service缺少所需代码卷，现以不可变`antigen-n12-same-run-code-r04`向service逐文件只读挂载7份更新源码，并保留ESMFold2 worker的`/backend`挂载；准备测试与N12测试合计12/12、验收静态守卫2/2、payload `--check`均通过。真实启动前脚本按`.tmp/n12-same-run-backend-r04-20260918-r01/source-hashes.json`锁定8份源码SHA-256并拒绝漂移；r04服务器dry-run已通过。本地准备到此完成，尚未apply/rollout或启动模型；只有用户执行真实链且随后完成独立产物、hash、run_id和样本身份复核后，才可关闭本项工程验收。OI-015/022与R-04科学决策仍保持开放。

**r04首次现场应用回归与r04b修复（2026-09-18）：** 用户应用旧r04时 ConfigMap 已存在但 Deployment JSON patch 被服务器拒绝，随后真实验收在 service 源码 hash 检查阶段发现缺少`esmfold2/source.py`；该失败正确阻止了任务启动。已将`esmfold2/source.py`加入 service 的 immutable ConfigMap 和逐文件只读 subPath 挂载，并改用不可变`antigen-n12-same-run-code-r04b`。相关准备/验收测试16项通过；用户需从当前线上 Deployment 重新运行生成器的服务器 dry-run，再应用 r04b 产物后重跑同一验收入口。

**r04b导入根修复（2026-09-18）：** r04b源码守卫通过后，真实链在 service 内导入`n12_prediction_evidence`失败；控制面镜像的`PYTHONPATH`为`/app/src`，而旧覆盖只挂载`/opt/t01/src`。现保留旧挂载并为同一8份源码增加`/app/src`逐文件只读挂载，验收探针同步检查`/app/src`。线上 r04b ConfigMap 已完整，不再创建新 ConfigMap；补丁仅更新 service volumeMounts。19项相关测试通过。

**临时Python进程Linux入口修复（2026-09-18）：** r04b挂载修复后，`kubectl exec`的独立Python进程未执行service主入口的`install_platform_modules()`，误加载Windows限定的冻结runtime；验收payload现显式安装Linux平台模块后再导入Runtime。该修复仅在本地验收脚本中生效，不需新镜像或集群变更；payload编译、静态检查和19项相关测试通过。

**优先级2实施回填：** ESMFold2新任务登记、显式预测路由、保持G0 ArtifactRef的N01回连已本地实现，13项新增后端、4项部署渲染及既有35项流程/API测试通过；Linux导入/禁网socket/GPU锁探针通过。完整根首轮1993通过/15跳过/5失败中4项冻结源问题已恢复原hash并重验通过，余1项为旧报告已知断链。镜像已由用户构建上传，正式增量服务器dry-run通过，活动任务0；下一步由用户应用清单并进行目标新任务验收，助手未应用集群变更，详见[接入记录](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md#统一任务与n01接入准备2026-09-17)。

**标准封装完成回执：** 用户已生成`standard-r01`并verify，助手再次本地只读复核通过：25文件、76残基，manifest SHA-256 `b5e0d7ca19af8c53aabd0640ca06a48c35084ca97839d30c195852d12f8c0797`。下表优先级1已完成，当前转入优先级2的统一任务层与N01接入；本次只关闭已登记r03结果封装，不等于新预测任务或生命周期已接通。详细回执见[标准封装记录](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md#esmfold2标准封装2026-09-17)。

**标准封装实施回填：** r03离线适配器与本地CLI已实现；37项受影响测试及真实原件生成/复核通过，25文件包保留原始8文件，包含结构索引、76条逐残基置信度、参数/来源hash与实现快照。用户正式生成`standard-r01`的命令见[标准封装步骤](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md#esmfold2标准封装2026-09-17)，本轮未重跑模型、未更新集群。该适配器固定r03来源，后续统一任务接入仍需新任务来源登记与执行生命周期验收；不将本次封装写成N01/N12已接通。

本节是当前执行顺序，接续下方09-16批次，不新建交付包。实际状态以[STATUS顶部摘要](STATUS.md#当前任务入口)和[模型交接当前步骤](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md#现行统一常驻gpu-worker2026-09-20)为准；下方较早回填保留其发生时点，不反向列作现行待办。已通过的工具独立验收与RustFS本次报告入桶保留成果，只做新增实现影响到的回归。HiMat继续后移；助手按用户最新要求在既有授权范围内直接完成可操作的上传、apply、任务启动与核验，仅将缺权限或需用户决定的动作交回。

**现行复核起点：** ThermoMPNN/N16适配、RustFS已授权报告、ESMFold2标准封装/统一任务/N01/N12/生命周期及首条工程链均保留完成成果。统一常驻单卡Worker现为唯一GPU申请者，四个既有GPU工具登记于全局FIFO，ESMFold2真实r03回归通过；历史40GB身份和失败批次不改写。AF3数据库/权重、固定环境、CPU本地数据搜索、单张64GB五样本原生推理及独立审计均已完成；当前关键路径缩小为AF3标准封装、pTM并列规则、统一任务/N01/S-09及同一Worker命令登记。常驻ESMFold2仍限制76残基，393不自动扩展支持域，Pod崩溃恢复未覆盖。决定边界见[决定登记](DECISIONS.md#统一常驻单卡-worker)。

| 优先级 | 下一项与实施内容 | 完成标准及具体依赖 |
|---|---|---|
| 已完成：首条工程链 | 1UBQ/76 aa显式ESMFold2 r03已到达N18：12分支真实成功、8分支按差距表透明跳过、0失败；206个ArtifactRef唯一且同run，报告内外层完整性及ESMFold2→N01→N17/N18来源经独立审计通过 | 工程闭环已关闭；科学Gate、自动交接和生产状态未放行。新增r03报告被后端默认公开且匿名200，超出旧两份报告授权，等待用户决定保留或精确撤回，并须修复后续默认发布边界 |
| 已完成：N12同次运行 | r05已精确登记两项A100环境并覆盖Worker/service；r02新run完成N01结构→ProteinMPNN→ESM-IF1→原sample_number显式选样→ESMFold2→N12证据绑定，独立审计通过 | 135个ArtifactRef、127个唯一落盘文件、同run/样本/序列/突变/分数/GPU身份和结构完整性一致。r01失败保留；R-04、科学Gate和自动交接保持关闭 |
| 后移：ESMFold2支持域收尾 | 评估常驻后端长度扩展和Pod崩溃恢复；保留已通过的标准封装、N01/N12、禁网、恢复/取消/超时和393残基独立案例 | 不阻塞首条全链。常驻76残基上限不因393单例自动改变；1000–1500及更长输入继续标记NOT_RUN，不把工程链通过写成科学签收 |
| 已完成基线 | ESMFold2标准结果/逐残基confidence封装、统一任务/attempt/ArtifactRef、GPU串行调度、显式无结构预测和N01回连 | 既有真实目标证据与损坏拒绝继续有效，不重跑模型或重开已关闭工程项；仅在N12新增实现影响范围内回归 |
| 已完成：AF3前置盘点 | r02只读检查成功：9份归档238784443666字节；数据库卷可用842299772928字节，规划需求698719476736，`provisionally_sufficient=true`；权重1020545840字节且SHA固定，权重卷可用19920080896字节 | 只证明归档/回执/空间满足进入解压的工程前置，不证明已解压可搜索；科学Gate与生产状态不变 |
| 1：AF3安全解压已完成 | r01因流式libzstd EOF边界bug失败，r02在第3个归档因`OOMKilled`/退出码137失败，均保留原归档、partial和日志。r03改用有界1MiB解码复制、256KiB tar缓冲和周期性写回，重算源归档SHA并逐成员安全检查；用户回传`AF3_DATABASES_EXTRACTED_VERIFIED 195867 672435030513`，输出已原子发布为`unpacked-r03`并生成清单/回执 | 保留9份归档、旧下载/盘点Job及r01/r02失败证据；不重新下载、不删除或覆盖已有输出。解压回执只放行独立只读目录/清单核验，不放行搜索、推理或科学消费 |
| 当前：AF3标准与统一接入 | 第一版本地适配器与registry/runtime/workflow/N01/S-09接入改动已落盘；下一步依次完成模块自包含、语法/导入、合成夹具回归、真实五样本只读标准化、部署清单与服务器dry-run，再登记统一Worker第五个命令 | sample 1/4 pTM并列时保留全部，最低seed/最低sample序号仅作可复现工程主模型，不解释为科学优先；不用官方`ranking_score`替代。随后做一条AF3真实统一任务及三个既有GPU工具的代表性串行回归；不重做下载、解压、搜索或ESMFold2已关闭验收，科学Gate继续独立判断 |
| 并行准备B：业务数据库 | 核对N03 BLAST、N08同源/补充库、N09注释包的用途、路径、来源/版本、索引和批准条件；准备本地格式适配及新目标任务 | AF3遗传/模板数据库不自动等于这三类业务库。只对可验证的各自数据包登记/实跑，不把缺库扩大为全部工程停止条件 |
| 后续汇合 | 继续N10缺项、Gate/WT、N11–N15完整设计/复核/重算/保护/排序、N16业务DNA与N17/N18汇合；科学工具跑通后再集中HiMat联调，正式交付/生产门禁最后收口 | 具体科学缺项仍见OPEN_ITEMS；不重复已闭合工程问题。RustFS公开授权只覆盖已批准的1UBQ两份报告，新增数据不能自动沿用公开授权 |

#### 首条 N01–N18 工程链差距表（2026-09-19）

首条链固定使用已登记的1UBQ/人泛素76 aa序列，SHA-256为`233b4b0b8c4616095bc3249f9375fc345d32af7deaef07117d0383c51d6f19aa`；`host_species=Homo sapiens`，`organism=Homo sapiens`，工程表达宿主为`Escherichia coli K-12 W3110`。本次不上传或复用结构，显式请求`prediction.engine=esmfold2`、seed 1；不复用历史任务。N05沿用已在目标环境跑通的显式HLA-I/II测试allele。N03/N08/N09不绑定未经登记的数据库，保留为透明条件跳过；总期限3600秒。

本地批次`.tmp/cluster-workflow-probe-r03/batch.json`固定独立幂等键和上述请求；用户已提交并完成父任务`t01p1r-job-850250a8eeef47fc84ea534198effeca`，重复提交幂等通过。`scripts/run_cluster_workflow_probe.py`的`esmfold2`模式未上传结构；终态、报告与独立审计结果见本表后回填。

| 节点/边界 | 首链预计行为与现有证据 | 差距分类 | 本轮关闭口径或后续条件 |
|---|---|---|---|
| N01 结构 | 新run先执行ESMFold2，再以同run原始ArtifactRef进入结构Worker；76 aa预测、标准输出及N01回连已有独立通过证据 | 可直接执行 | 新run的prediction和structure均终态成功，序列/结构/hash/来源闭环；G76 RSA若再次出域须原样记录，不截断或伪造正常RSA |
| N02 拓扑 | DeepTMHMM目标实跑已通过，按同一序列新执行 | 可直接执行 | 新子任务成功且与父run/序列绑定；科学输入域签收仍独立开放 |
| N03 BLAST | workflow未提供目标库，预期`skipped/DATABASE_NOT_PROVIDED` | 缺业务资产 | 登记目标库用途、来源/版本/许可、索引与manifest并完成目标检索；不恢复IEDB、不把普通同源命中当文献证据 |
| N04 B细胞预测 | BepiPred目标实跑已通过，按同一序列新执行 | 可直接执行 | 新子任务成功并保留原始双列；OI-026后处理科学签收不属于本轮工程闭环 |
| N05 T细胞预测 | 使用已验收的显式HLA-I/II测试allele新执行 | 可直接执行但输入显式 | 新子任务双通道成功；不把显式测试面板写成OI-003宿主默认面板已确认 |
| N06 表位地图 | 消费N04/N05，明确记录N03未执行；既有目标局部汇总已通过 | 可直接执行但科学部分缺项 | 新子任务成功并披露缺失来源；热点、无IEDB语义及窗口换算仍受OI-026/028/029约束 |
| N07 糖基化 | 执行sequon扫描，并按N06实际热点状态决定是否做遮蔽判断 | 可直接执行但可能条件缺项 | 扫描任务成功；缺少可消费热点时记录未执行遮蔽，不写成无风险或PASS |
| N08 同源保守性 | workflow未提供目标同源/补充库，预期`skipped/DATABASE_NOT_PROVIDED` | 缺业务资产与科学决定 | 登记服务器目标库并完成大库适配/目标实跑；其余科学语义见OI-030 |
| N09 功能域 | workflow未提供目标注释包，预期`skipped/DATABASE_NOT_PROVIDED` | 缺业务资产与科学决定 | 登记注释库、适配并目标实跑；core_map与合并/几何语义见OI-006/031 |
| N10 可开发性 | 新执行现有部分维度；预测结构RSA出域可能令S-39不可用，overall仍为null | 可执行的部分链 | 子任务成功并逐维披露可用/缺失/不可靠；CamSol、序列聚集、A3D空间语义、PROPKA权重和科学签收仍见OI-025/032/033 |
| Gate/WT草稿 | `wt_draft`复核N01–N10实际状态并生成工程草稿，Gate保持未评估 | 可直接执行的缺项汇总 | 草稿成功且逐项保留缺失/失败/未签收；OI-013/014/021未关闭前不得放行设计或正式WT |
| N11 设计 | workflow预期`skipped/SCIENTIFIC_GATE_CLOSED`；ProteinMPNN仅有独立工程验收 | 缺科学Gate与正式权限 | 不为追求全绿改Gate；待OI-021及适用权限/上游科学字段签收后接正式设计 |
| N12 复核/重算 | workflow预期随Gate跳过；同run ProteinMPNN→ESM-IF1→ESMFold2的独立工程链已通过 | 缺正式候选与科学规则 | 待前20池、R-04/结构复核、burden与有限重算规则闭合后接入主workflow；不重复独立验收 |
| N13 表位保护 | workflow预期随Gate跳过；后端已有独立工程分量 | 缺候选、真实热点与科学方法 | 待真实配对候选及RMSD/shape/缺位规则签收后执行，不用空验证区间声明保护通过 |
| N14 稳定性 | workflow预期随Gate跳过；FoldX和ThermoMPNN已有独立工程实跑 | 缺候选与跨引擎消费规则 | 待正式候选和OI-011/022等规则闭合后回连，不重跑无关独立工具验收 |
| N15 综合筛选 | 当前会生成无候选的缺项报告而成功，不代表正式筛选或排名 | 可执行的缺项报告 | 报告须明确`DESIGN_INPUTS_UNAVAILABLE`或等价事实、best candidate为null；正式Hard/Pareto/排名待N11–N14真实输入 |
| N16 密码子 | 已给出W3110表达宿主，但因无合格候选预期`skipped/NO_ELIGIBLE_SEQUENCE` | 正确条件跳过 | 不生成占位DNA；待正式WT/候选资格、批准宿主/CAI及业务DNA绑定后执行 |
| N17 WT稳定性参考 | 当前可汇总实际可用的结构/拓扑来源并把设计、FoldX、ThermoMPNN缺失列为复核项 | 可执行的部分汇总 | 新子任务成功且缺失来源透明；完整N17需目标新扫描及适用科学签收 |
| N18 交付 | 组装WT草稿、N15缺项报告、N17部分参考，生成父workflow报告和ZIP | 当前闭环终点 | 父任务与`local_delivery`成功；下载后核对大小、SHA-256和ZIP CRC，并确认所有节点状态如实。新报告不沿用既有两份1UBQ报告的公开RustFS授权 |

首链工程闭环的通过条件是：同一新run从显式ESMFold2请求到N18报告/ZIP，实际执行、条件跳过、失败和阻塞均可追溯；不是18个节点全部成功，也不开放科学Gate、自动交接或生产状态。r03已满足该条件：[独立审计](../../discovery/t01-phase1-real/workflow-first-chain-20260919/r03/audit-summary.json)核验12成功/8跳过/0失败、206个唯一且同run的ArtifactRef、ESMFold2→N01证据、报告内外层manifest/hash/CRC及关闭的放行状态。N18交付结果为`DESIGN_INPUTS_UNAVAILABLE`，与差距表一致。

报告下载调用同时触发RustFS公开发布，新的r03 Markdown/ZIP匿名HEAD均返回200；旧授权仅覆盖此前两份报告，不能自动扩展。本轮不擅自删除或改桶策略，等待用户对这两个精确对象作保留公开或撤回授权决定；后续接口须改为显式发布授权。该运营问题与工程链是否通过分别记录。

**当前交付给实施任务的目标：首条N01–N18工程链已闭环，AF3只读盘点及r03安全解压已成功；用户回传终标记和JSON回执一致，`unpacked-r03`含195867个登记文件、总计672435030513字节。下一步先以独立只读Job挂载复核`extraction-receipt.json`、`extracted-manifest.json`与AF3必需路径，再依据实际清单准备固定环境、本地数据搜索、权重加载与5次短样本推理。** 不重新下载或删除归档，不在Completed下载Pod中exec，不覆盖已有输出；r01/r02 partial和日志保留供审计。另需用户决定新的r03报告是否继续公开；未经授权不删除对象、不改桶策略。新发布须对照当前线上镜像与未提交源码，防止Jenkins覆盖已上线能力；未经用户要求不提交或推送。没有重新开展科学验收，历史测试数字沿各批次保留。

### 部署续行计划（2026-09-16）

> 当前执行顺序已由[09-17模型接入计划](#模型接入续行计划2026-09-17)接续；下表保留整体范围与各批完成标准，不把已完成的批次1/2重新列作待办。

本节依据用户“完整查看目前项目完成情况，然后制定新的部署计划”的要求，在同一 `PH1-REAL-TARGET-DEPLOY` 内安排剩余工作。保留 N01–N18、双结构模型、WT/设计/重算及最终交付；沿用 HiMat、常驻 Worker 和 Codeup `test` 通道。以下是实施目标与完成标准，不代表已经发布或取得科学签收。实际状态单点见 [STATUS](STATUS.md)。

**现行优先级：科学工具部署与实跑优先，HiMat联调后移。** 依据[09-16最新用户决定](DECISIONS.md#科学工具优先与-himat-联调后移)，当前报告只需正常写入RustFS的`antigen-design`桶并完成完整性回读；HiMat文件、异步交互、卡片与附件显示不作为本轮完成条件。可直接通过既有后端接口提交、查询与发布报告，继续沿用既有认证和任务归属。下表已按此调整，不等待HiMat即可推进模型、数据库与工具真实计算。

#### 完成情况复核依据

本次查看 STATUS、范围、W1–W7 交付入口、开放项、现行部署记录、运行手册及相关实现，重点复核服务入口、常驻执行、流程调度、报告发布和模型准备；未将根目录“工具部署”纳入 T-01 验收。历史工具实跑沿用其索引与审计，不宣称本轮重新执行了全部科学工具。

- 只读回查测试服：Deployment generation/observedGeneration 均为 11，单副本 Recreate；Pod `antigen-design-6844f9cd6c-xhg7w` 位于 `k8s-a100-02`，控制面及 9 个 Worker 全部 Ready、0 重启。控制面实际摘要仍为 `sha256:78b5875032698cafe2ef82057622dd40949e3afbae5eaf69d701effe600b7dc1`。运行卷和工具资产卷各 20Gi、Bound；GPU Worker 为 10GiB 显存、4 CPU/12Gi 内存上限，不能视为双结构模型的容量验收。未见 `antigen-esmfold2-models` PVC，service 环境尚无 RustFS 配置。
- 直接重验 r02 已保存 ZIP：158295 字节、4 个成员，大小、SHA-256 和 CRC 一致；原回执明确 `actual_himat=false`。流程表包含 19 个内部条目，对应 18 个业务节点，11 成功/8 跳过不是“完成 11/18 节点”的比例。N10 成功只表示部分工程结果产生，N15/N17/N18 汇总成功不证明候选排序、双引擎新扫描或正式交付通过。
- [流程实现](../../src/t01_phase1_real/development/workflow/service.py)明确：无结构输入返回 `PREDICTION_SERVICE_NOT_DEPLOYED`；N11–N14 固定跳过 `SCIENTIFIC_GATE_CLOSED`；N16 即使给表达宿主也因无合格序列跳过；N17 只汇总来源，不在这里启动扫描。因此完整链缺口同时包含编排实现、真实输入与科学规则，不能只改 Gate 常量或部署环境变量。
- RustFS 上传及附件代码存在于未提交工作区，存储小对象实测已通过，正式服务未接入；[MCP](../../src/t01_phase1_real/service_api/transport.py)目前提供结构字节上传及 submit/get/wait/report 等 8 个工具。HiMat 文件引用、异步状态和卡片兼容性须以实际入口验证，不能由这些工具名推定完成。
- ESMFold2 标准版 `asset-manifest.json` 已为 `ASSETS_DOWNLOADED_NOT_DEPLOYED`；本次逐份复验 23 个文件、26791863243 字节，大小/hash 全部通过。已下载完整模型资产不等于 Python 3.12 环境、推理 Worker 或 N01/N12 接入已完成。AF3 尚无本轮可核验的目标部署/推理证据。具体固定版本继续单点见[模型部署说明](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md)。
- 当前根测试本轮为 **1873通过、15跳过、0失败、2条DeprecationWarning**，日志`.tmp/project-review-20260916/pytest-r02.txt`；15项跳过不作为Linux真实执行证明。首轮因Windows沙箱临时目录权限产生684项setup错误，另有1200通过/4跳过，未作为有效全绿；在专用新目录重跑才得到上述结果。2条告警来自NetMHC解析正则的`\d`字符串，不是本次文档修改引入。文档检查292份通过，29处既有历史断链单列。未跨历史分区，旧完整Mock及S07未重跑；本轮不改实现、不重跑科学模型、不发布。

#### 实施批次与完成标准

| 顺序 | 交付目标与具体工作 | 完成标准 | 依赖与主责 |
|---|---|---|---|
| 1：剩余已部署工具集中实跑 | 用适用的新小样本集中验证 ProteinMPNN→ESM-IF1、ThermoMPNN、FoldX RepairPDB/PositionScan/五次 BuildModel，以及完整 N10→A3D 路径；明确宿主的独立 N16 工程调用按已支持 profile 验证 | 每种原生工具有目标任务/attempt、原生命令与结果、镜像/资产身份、解析结果和报告回连；GPU 工具共用串行执行约束；用代表案例补目标取消/中断恢复，失败不由总汇总成功掩盖 | 主开发、用户；现有资产与挂载已具备，直接使用后端入口，不等待RustFS或HiMat。10GiB不足时依据实际资源记录调整配额/支持输入，不能静默裁剪样本或改变期限。独立 N16 不伪装成候选 DNA |
| 2：真实报告写入RustFS | 发布已实现的RustFS控制面改动，应用本项目Secret引用和环境配置；通过后端workflow.report将真实任务Markdown/ZIP发布到antigen-design桶既定data前缀 | 桶中存在可追溯到job_id的真实报告对象，大小与SHA-256回读一致；记录对象键和发布回执，发布失败可仅重试发布、不重算任务；小对象探针不能代替报告入桶 | 主开发负责代码/配置及校验，用户操作现场发布；可与工具实跑独立推进，无需HiMat提交、卡片或附件显示验收；桶地址见用户决定 |
| 3A：ESMFold2 标准版接入 | 在已下载资产上构建固定 Python 3.12/依赖环境；落实独立60Gi模型卷及传输校验；实现常驻预测适配、原生结构/置信度归一、取消/超时；接入 N01 无结构输入与 N12 结构复核 | 禁网、无未登记缓存，真实序列生成结构及原生置信度；模型版本/MSA实际模式/资源可追溯；N01→结构分析可回连；N12 可使用真实预测来源完成适用工程验证 | 主开发构建/接入，用户部署，算法签收结构消费。先核实所需主存/显存与可申请配额，不能直接套用现有10GiB GPU配置；不切换 Fast/旧 ESMFold |
| 3B：AF3 接入 | 盘点合法权重、固定代码环境、本地遗传/模板数据和实际存储；补齐缺失资产，沿相同任务/产物边界完成禁网预测、置信度归一及 N01/N12 适用路由 | 真实输入到原生结构输出及下游回连完整，保留失败/取消/恢复证据和资源上限；两模型分别记录通过，不能由 ESMFold2 代替 AF3 | 用户落实资产与目标资源，主开发适配，算法确认消费规则。资产盘点与3A并行；GPU执行串行。历史2TiB/192Gi估算不是现有配额或已需全量申请的结论 |
| 3C：三类业务数据库 | 登记 N03 BLAST、N08 同源/补充库、N09 注释包的用途、来源/版本/许可、格式、索引和hash；挂载只读本地数据，补实际格式适配并分别实跑 | 正式登记库上命中/无命中及坏库守卫可验证，上游身份和报告回连正确；三个分支按各自证据转为已验证，不用开发小库冒充目标库 | 数据接口人提供现有资产，主开发转换/实跑，算法签收对应消费；OI-028/030/031仅约束各自分支。独立于3A/3B，不等待模型 |
| 4：完整业务链 | 完成 N10 剩余维度与汇总、真实表位/权限、Gate→WT或设计；串联 N11、N12 结构复核/负担/有限重算、N13 四层保护、N14、N15 Hard/Pareto/权重/多样性、N16条件、N17新扫描与N18汇合；把固定跳过改为有证据的后端路由 | 新的合格输入贯通候选分支；另覆盖 WT、全淘汰/失败、重算上限、无宿主/支持宿主分支；每个“通过”有完整输入和科学判据，未决分支保持关闭；旧24条淘汰不重新授予资格 | 主开发负责工程补齐，算法/业务按下表签收；模型、数据库只阻断依赖它们的部分，可先编写不含争议规则的适配和契约测试 |
| 5：HiMat集中联调（后移） | 科学工具跑通后核对HiMat文件入口、MCP发现/认证、异步提交/查询、报告卡片和RustFS附件，按实际协议补适配 | 从HiMat提交新任务、查询真实进度/终态并下载一致的报告；断开页面不丢任务、重复提交不重复计算 | 主开发、用户、HiMat接口方；后于科学工具部署与实跑，不要求等待全部科学签收或生产验收；不阻断批次1–4 |
| 6：正式交付与生产发布 | 落实 Candidate/WT/Failure 字段和 Agent C 认证/幂等/回执；在目标完成容量、网络隔离、持久化、升级回滚/备份恢复及适用安全/许可核验；冻结最终镜像/配置/资产/证据 | N01–N18及保留分支具备适用G0–G6；目标支持输入/并发/资源明确；正式交付收到真实回执后才开放自动交接，完成发布后才改变生产状态 | 用户/运维、主开发、算法、Agent C接口方；完整生产检查在测试链稳定后进行，不前置阻断批次1/2 |

执行关系：立即推进1的科学工具实跑，2的报告入桶独立补齐；3A/3B/3C的环境、资产与接口工作可同步准备，GPU实跑始终按单卡约束串行。科学规则收敛从现在开始，供4逐项消费；5在科学工具跑通后集中开展，6在适用完整链通过后收口。1–4不以HiMat联调为前置。不预设缺数据、资源配额或科学签收的完成日期；实际工具耗时、模型短样本资源及数据交付时间明确后再排日历，不用未知条件承诺全量上线日期。

#### 科学与接口条件的对应关系

| 具体条件 | 关闭证据与责任 | 影响的交付 |
|---|---|---|
| OI-003/007/026/028/029：面板、B分数/峰、无IEDB证据消费、真实热点与20aa窗口 | 算法按已有原件签收明确分支、边界和独立参考；后端落实和验证，不重问已有阈值 | N04–N07、N11权限和N13保护的科学消费；不阻断原始工具实跑或批次1 |
| OI-015/023/024/027、DeepTMHMM适用输入域与参考 | 算法签收结构映射/质量/RSA及拓扑参考，后端核验原生字段和下游接受域 | 结构相关N02/N10/N12/N13/N17；不把“原工具成功”直接变为批准输入 |
| OI-025/032/033：CamSol、聚集分支及PROPKA平坦权重 | 对具体冲突定点裁决；后端补标度/标定资产、官方序列聚集资产及独立数值参考 | 完整N10、overall和Gate，不阻断已明确维度及A3D目标实跑 |
| OI-001/002/006/008/009/011/021/022及N13方法缺口 | 算法/业务签收权限、负担、Gate、结构保护、跨引擎与排序/重算；工程按完整来源实现 | 批次4的自动设计、验证和排序，不能通过改固定常量绕过 |
| OI-004/010/013/014 | 业务/算法签收宿主与正式分支；Agent C接口方与后端完成字段、认证、幂等和真实确认 | 业务DNA、Candidate/WT/Failure及自动交接；RustFS附件可先完成 |

具体问题定义和来源仍只在 [OPEN_ITEMS](OPEN_ITEMS.md)维护。本节不新增科学裁决，不将部署计划代替算法签收。

#### 每批发布与回退边界

1. 发布前记录当时 Deployment/ConfigMap、实际镜像digest及任务状态，准备只覆盖本批字段的变更；保护运行卷、资产卷与旧任务。当前工作区包含多个未提交主题，按批次审阅后选择文件，不把本机权重/临时数据随Git发布。
2. 控制面继续由 Codeup `test`→现有 Jenkins 发布，显式选择 `service`；Worker 仅发布受影响镜像。保存源码提交、构建/运行digest及原生来源校验，保留已完成的LF/CRLF修复；公共流水线不承担9镜像批量构建。
3. 应用前确认无活动科学任务或已按既有流程停止并取得回执；同Pod Recreate会影响所有Worker，须计入本次变更窗口。不能在模型切换或扩容时同时申请多个整卡入口；GPU模型环境与资源配置按实测结果选定后再发布。
4. 回退仅恢复本批已记录的镜像/环境/配置，检查现场漂移后执行；旧 `deploy_resident_cluster.py rollback` 快照对应更早部署，不能直接覆盖generation11及之后的更新。RustFS发布异常可关闭其开关恢复既有下载方式，保留原任务/报告和已写入对象，不重算或批量删除。
5. 每批只做受影响测试与代表性目标链验证；发布后检查真实任务终态、子节点与附件。完成事实回填本包及STATUS；不凭Ready、总任务succeeded、Mock或旧报告记为新批次通过。

### RustFS报告入桶与模型配置续行（2026-09-17）

**模型与数据库后续回填（2026-09-17）：** ESMFold2模型及独立环境已上卷；ESMC布局修复后的r03在A100完成76残基单链预测，8份原始产物67351字节已取回并独立核验：序列一致、601原子坐标有限、主链完整、逐残基置信度与原始摘要一致，见[审计证据](../../discovery/t01-phase1-real/esmfold2-target-20260917/r03/audit-summary.json)。20项审计/收集守卫测试通过；旧失败和原始输出保留。当前转入标准结果封装与后端接入，仍需禁网实际效果、生命周期和较长输入验收，不把短序列独立Job成功写成完整部署或科学签收。AF3权重r02已完成；9项固定官方v3.0数据库归档（238784443666字节）的独立1Ti PVC下载Job已由用户回传Complete及全部校验通过终标记，尚未独立挂卷复核或解压；下一步先核对空间与回执，不再等待下载，不影响ESMFold2工作。细节单点见[模型部署说明](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md#r03结果读取与核验2026-09-17)。后续上传/导入/任务启动尽量由用户操作，助手提供文件、命令和核验；科学Gate保持CLOSED。以下RustFS记录保留当时执行事实。

用户自行上传ESMFold2模型，同时授权助手继续其他任务。本轮未操作该上传进程、模型PVC或创建推理Job。HiMat保持后移，科学Gate仍CLOSED。

- **前批两项适配已关闭：** 提交`69c80ff4f3594a0b97f65db0c36bf54cab059a3d`在generation12发布后，ThermoMPNN新任务`t01p1r-job-344d196cdd2345c585c28b1ce04a9bc0`在A100上完整解析180行、选择140行，保留源码、依赖、输入输出及数值校验；N16建立独立Linux依赖profile并补colorama，保留Windows原清单。新E.coli任务`t01p1r-job-43efc7e63cbd40d2b45af119f5fe8151`生成60nt，翻译为`ACDEFGHIKLMNPQRSTVWY`、GC=0.516667、约束通过；无解样本返回明确未优化fallback。详见[封存摘要](../../discovery/t01-phase1-real/target-science-20260916/r02/summary.json)，旧失败不改写。
- **RustFS控制面发布：** 本轮从当前未提交工作区禁网构建`antigen-design:rustfs-20260917-r01`，非特权UID10001、只读/断网容器导入通过；通过已建立的独立Harbor中继发布`qcyz/antigen-design:rustfs-20260917-r01`并回读固定digest `sha256:fba5a32c0550e56a5310160e2fc49d647fcd27d76851073a2d82cc935fb4c2fc`。本次采用本地构建直接发布，没有Git提交/推送或触发Jenkins，不冒称来自新源码提交；后续Jenkins发布须先纳入当前RustFS源码，避免覆盖线上能力。发布回执在`.tmp/rustfs-image-publish-20260917-r01`，前后部署摘要在`.tmp/rustfs-release-20260917-r01`。
- **变更窗口与状态：** 更新前只读检查3个任务库、44个任务，无queued/running/stop_requested/reconciling项。只将service镜像及本项目RustFS环境配置打入Deployment，9个Worker的digest不变；服务器dry-run通过后应用，generation/observed=13，Pod `antigen-design-65fcd884f5-5mm9k`的10容器Ready、0重启。未复制或输出凭据、未修改桶策略。
- **真实报告验收：** 自动审批要求当轮直接授权匿名访问，用户明确回复“允许这两份报告公开只读”后，通过认证MCP `workflow.report`发布已有1UBQ分析任务`t01p1r-job-b5c8b65e06914192b4de20f2290598bd`，未重算科学工具。ZIP 158295字节、4成员，SHA-256 `f5f5a1ec8b2bc9afa0ee3dd318b1738185961d5e3acbf03c5c6ae9913dd9d0f0`；Markdown 1198字节。后端HEAD大小/hash和匿名GET验证通过，本机再次匿名下载核对大小/hash及ZIP CRC；ZIP与原留存报告逐字节一致，重复发布附件URL及hash不变。对象键、回执及独立索引见[验收摘要](../../discovery/t01-phase1-real/rustfs-report-20260917/r01/summary.json)与[索引](../../discovery/t01-phase1-real/rustfs-report-20260917/r01/index.json)。仅证明本次报告发布链，HiMat业务入口和完整科学流程不在本轮验收内。
- **受影响回归：** RustFS发布、Secret配置、服务API、ESMFold2 worker、环境准备与下载器共36项通过；此前Windows沙箱临时目录拒绝导致的setup错误不计实现失败，也不计通过，权限审批重跑后完成。镜像构建22项固定来源检查通过。ESMFold2轻量镜像清单固定为已发布digest，ConfigMap更新，Job服务器dry-run通过；仍待环境包上卷及真实A100预测，详见[模型部署记录](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md#环境构建与轻量部署进度2026-09-17)。

发布后独立比对线上`app.py`、`transport.py`、`object_storage.py`与本地受测字节，3项SHA-256全部一致；源码快照、前后部署状态及Harbor回执见[发布证据](../../discovery/t01-phase1-real/rustfs-release-20260917/r01/summary.json)。文档扫描本轮未全绿：仅旧`target-science-20260916/r01/backend-report.md`的`data.json`/`manifest.json`两条ZIP包内相对链接在仓库展开目录缺失，本次现行页面未新增错误；原报告及封存索引保持原字节，不为消除导航错误改写证据。

### 已部署科学工具集中实跑回填（2026-09-16）

按用户“已部署科学工具的集中真实实跑，直接通过后端执行”实施批次1，未重做此前文档检查。通过用户提供的集群连接，在`him-ws/antigen-design`控制面直接调用已部署Runtime；新运行根`/var/lib/t01/target-science-20260916-r01`，GPU三个工具及GPU生命周期样本按目标任务起止时间核验为串行。输入是已有生成器的9残基合成几何、新生成工程样本及独立AA20密码子片段，不是生产候选；原24条淘汰序列未读取或重跑。

| 本批动作 | 目标结果与边界 |
|---|---|
| ProteinMPNN→ESM-IF1 | 新生成1条，回评分1条，WT基线`computed_once`；两个任务成功，保留原命令、权重/源码hash、A100原生观测及ArtifactRef回连。完整N11/N12科学资格仍未开放 |
| ThermoMPNN | 原生CLI退出0、输出180行SSM；后端任务`f441d025…`为`failed/OUTPUT_INVALID`，诊断`ThermoMPNN environment differs: gpu_name`。现行parser把原本机RTX 5070 Ti的型号及能力写入结果准入，A100原生计算事实不能转写为解析成功 |
| FoldX补齐及重跑 | 首轮scan/build分别`ASSET_MISSING`，原生尚未启动。缺的是卷内`foldx-20270131/assets.json`；17份现有文件大小/hash全部通过后，用同节点临时Pod独占新建原登记文件（4508字节，SHA-256 `638dc84d07aa602ab10c9a6a5ba4d87f8da5bec310cde0ce357155aa361aa5d9`）。临时Pod已删除、PVC保留，未覆盖原包。新任务`f63de62a…`与`e7eee307…`均成功：RepairPDB、PositionScan 40条解析记录、3个变体各5次BuildModel（15条原生差值）；旧两次失败保留 |
| N10→A3D/PROPKA | 新结构任务及N10成功，A3D通过常驻嵌套路径执行，global score约-2.2966；PROPKA曲线41点。CamSol/稳定性等未完成维度、平坦曲线规则和科学签收缺口仍保留，`n10_complete=false`、`overall_score=null` |
| 独立N16 | 明确E.coli支持profile、`INDEPENDENT_ENGINEERING_SEQUENCE`。任务`dd67e746…`在计算启动前`DEPENDENCY_MISMATCH`，首个诊断为`Bio/Affy/CelFile.py`内容不同。进一步只读核验发现登记清单为Windows依赖：含`.pyd`/`.dll`、Windows换行及安装器元数据，另缺colorama；其余8个已安装包版本与登记相同。不是修改一个换行即可完整关闭，未启动优化、未生成DNA。探针首轮工具名拼写错误在请求准入前被拒绝并保留harness-error，不计后端任务 |
| 取消/恢复 | FoldX样本`f498bddb…`确认原生启动且尚未停止后发起取消，真实回执`cancelled/stopped_confirmed=true`。ProteinMPNN `623c0405…`在前一控制调用退出后，通过`recover`沿用相同job/attempt/execution及resident目录，最终成功。短GPU取消`c60cfdc0…`与原生完成竞争，后端取消、原生已成功，只作为取消意图生效证据；不充当运行中杀停。未重启或故障注入共享Worker/Pod |
| 后端报告回连 | 新N17→N18工程汇总保留成功FoldX与失败ThermoMPNN，结果`DESIGN_NOT_EXECUTED`，未产生正式候选。后端ZIP 470837字节，SHA-256 `13c22102ccaac2169e8ace19a04ae3966178ae884ad37d91a7b21ed32ea81bd0`，下载大小/hash及ZIP CRC通过；该报告只覆盖其声明的扫描来源，全批状态见summary，不冒充全流程报告、RustFS入桶或HiMat验收 |

**证据与现场：** [索引](../../discovery/t01-phase1-real/target-science-20260916/r01/index.json)包含583份文件，逐项大小/hash复核通过；[批次摘要](../../discovery/t01-phase1-real/target-science-20260916/r01/summary.json)登记16个新后端任务（10成功、4失败、2取消）及469份产物核验。4次失败中包含已补齐后成功重跑的两次FoldX首轮；当前未关闭的是ThermoMPNN与N16。任务成功数不等于N01–N18完成数。结束快照generation/observed=11，原Pod、10容器Ready、0重启；仅补入上述漏传登记文件，没有修改Deployment/镜像、提交或推送。本轮未修改生产实现，不以文档检查或本地单测代替服务器实跑；未跨历史分区，旧完整Mock/S07未重跑。科学Gate保持CLOSED，生产NOT_DEPLOYED。

**本批剩余关闭动作（主责：后端/部署工程）：** ThermoMPNN需将目标GPU观测与旧本机环境区分，同时保留源码、依赖、原生输入输出hash及数值检查，发布后以新目标任务验证180行解析；N16需基于批准Linux wheel建立独立依赖profile并补齐适用包，保留Windows原清单，发布后新跑独立E.coli案例。两项都不通过改旧hash、清空校验或改科研Gate关闭；不影响既有成功结果或批次2的独立报告入桶工作。

### 测试服流程优先安排（2026-09-15）

> 本节保留09-15安排。09-16用户已将HiMat联调后移：当前科学工具部署与实跑优先，报告以实际写入RustFS桶并校验为完成标准。涉及HiMat首轮提交、卡片及附件的要求不再前置，现行顺序和完成标准见[部署续行计划](#部署续行计划2026-09-16)。

执行后端已按[常驻 Worker 调整](#常驻-worker-执行调整2026-09-15)进入改造；本节批量接入、集中联调及完成标准继续适用，下表原 Job SA/RBAC 与目标 Job 结果适配改为常驻进程执行配置和结果适配，不再前置申请 Job 权限。

依据[用户决定](DECISIONS.md#测试服流程优先与-himat-入口)，当前目标是让用户在 HiMat 提交测试任务，后端执行已接入的真实能力、汇合结果并提供可下载报告。控制面已部署的现场状态见 STATUS；不重新制作已完成本地工程的工具，不为每个工具再建准备/评审包。

**实施方式：一个集成批次，批量接入，集中验证。** 权限、共享卷、资产目录、镜像映射和目标执行证据共用配置；各工具保留必要原生解析与校验。资产齐备的工具一次纳入集成批次，缺库/缺模型仅阻断对应分支。可以用小型探针快速定位公共问题，但不要求首个工具完成整套生命周期验收才能继续其他工具。单 GPU 任务仍按容量串行调度，批量接入不等于同时占用所有 GPU 任务。

| 工作 | 当前交付目标 |
|---|---|
| 公共运行配置 | 核对实际 `antigen-design` Deployment/Service、版本与镜像，统一落实 Job SA/RBAC、运行卷、只读工具资产/数据库挂载及离线策略；旧生成器中的 `t01-control-plane` 名称按现场兼容处理，不能仅凭名称猜测 Service 端口 |
| 工具批量接入 | 集中登记资产齐备的结构/FreeSASA、DeepTMHMM、BepiPred、NetMHC、BLAST/同源、A3D及设计稳定性工具；已在控制面执行的确定性模块复用原路径。共用目标运行校验并对接各原生解析器，补齐当前通用 `PROFILE_NOT_APPROVED` 结果分支，不逐工具重新制作运行底座 |
| HiMat 与报告 | 验证集群内 MCP 认证和工具发现，补 HiMat 文件引用到受控输入的接收、后台查询和终态卡片；报告按本项目存储配置发布 RustFS 并校验可下载。当前固定 Bearer、Base64 报告与 HiMat 实际要求逐项适配，不直接复制引物业务类型或公开存储策略 |
| 集中流程联调 | 固定同一组小型序列/本地结构输入，一次批次覆盖已接入工具、上游来源和报告汇合；集中修复影响流程的共同问题，再重跑受影响部分。设计模块可通过明确工程输入独立联调；完整 Gate/重算/排序尚缺的分支逐项回填，不能把其跳过记成全流程通过 |

**首轮完成标准：** HiMat 能发现工具并提交一个新任务；已选择且依赖齐备的分支真实执行，输入/结果/原生产物可追溯；查询可读到实际进度和终态，报告卡片及附件下载可用。基础错误传播、重复提交和代表性的取消/中断恢复用少量集成案例验证一次，复用公共层证据，不对所有工具重复完整矩阵。缺库、未部署模型和未定科学分支必须在报告中明确标记。达到这些条件记为“测试服局部流程贯通”，不记为完整 N01–N18 科研流程通过；完整业务链仍在本部署包后续迭代中推进。

**后移检查：** 最大规模/长时间负载、逐工具完整故障矩阵、完整升级回滚与备份灾备演练、生产漏洞审计及发布冻结文档，在流程稳定后按实际发布需求完成。初始输入输出校验、认证与任务隔离、可停止的有界执行、Worker 离线运行和必要资产来源检查继续随接入实施；不重跑无变化的本地验收，不为普通测试批次重建完整离线交付包。新增实现仅运行受影响测试和对应集成验证。

AF3/ESMFold2、缺失数据库、CamSol 和具体科学开放项各自继续准备，首轮可使用用户提供的本地结构；它们不阻断无关工程分支。测试结果保留工程身份，正式科学消费/Agent C 放行另行判断。首轮结束后依据实际缺项继续完整链，不能长期用缺项报告替代保留能力。

### 常驻 Worker 执行调整（2026-09-15）

用户提供的运维反馈为“你起个进程不就好了”“这样运维太不方便了”，要求评估其他方式，并在讨论常驻 Worker 后继续索取操作步骤。当前按常驻执行服务接收任务、内部启动科学工具子进程的方式实施；HiMat 入口、已有任务存储、原生解析和报告链复用。此为待实现方案，不把当前 Docker/Kubernetes 桥接写成已有常驻执行能力。

1. **本地准备：** 启动 Docker Desktop Linux engine，核对已登记工具镜像是否齐备；按真实 Python/CUDA/依赖划分环境，不预设全部工具可以合并为单镜像。本轮 CLI 可执行，但 `dockerDesktopLinuxEngine` 管道不存在，尚未取得镜像库存。
2. **统一适配：** 后端对接固定 Worker，Worker 使用登记命令启动子进程，保留任务身份、队列、超时/取消和原生产物校验；新增进程执行记录，不伪造 Docker/Job 验收字段。沿用一套业务任务状态，不把调度交给 HiMat/LLM。工具计算继续离线，控制通信与附件发布按各自边界配置；不挂载宿主 Docker socket。
3. **批量部署：** 完成本地受影响验证后，准备常驻服务镜像、原包/权重批量迁移清单和匹配现有服务的部署配置。一次部署后处理多个任务，运行时不调用 Kubernetes API 创建/删除 Job；仍需普通 Deployment、存储和 GPU 资源配置权限。GPU 执行入口及环境共享方式按单 GPU 实际配置确定，禁止默认多个常驻 Worker 各占整卡。
4. **HiMat 集成：** 验证认证、上传文件引用、后台状态、多个真实工具结果汇合和 RustFS 报告下载，按本页测试服标准记录缺失分支并继续完整链。

共享 Job Role/RoleBinding 申请暂停，现有清单及代码保留历史用途，不删除冻结资产。现有 `antigen-design` 测试服继续运行，待新执行方式可验证后再更新。镜像实际库存、环境分组和目标资产传输方式未确定前，不给出可直接上线的占位 Worker 清单。

### 常驻执行基础层回填（2026-09-15）

用户启动 Docker 后已实查 Linux engine 29.5.3，11 类科学镜像 ID 与现行登记一致；对每个镜像均以禁网、只读、非root容器读取实际环境，全部退出0。[镜像环境记录](../../discovery/t01-phase1-real/resident-worker-20260915/engineering-r01/image-environments.json)保留版本和分层身份，不把镜像大小相加当作实际传输量。

| 工具环境 | 实际观察及装配边界 |
|---|---|
| 结构/FreeSASA、NetMHC、同源工具 | Python 3.11.16；原生依赖不同，不能只按 Python 版本判定可合并 |
| BLAST / FoldX | 分别 Python 3.10.12 / 3.10.21，沿用对应原生二进制 |
| DeepTMHMM | Python 3.8.20、torch 1.5.0+cu92，当前登记为CPU工具，保留原环境 |
| BepiPred | Python 3.10.21、torch 2.5.1+cpu、fair-esm 1.0.3，保留原环境 |
| ProteinMPNN / ESM-IF1 / ThermoMPNN | Python 3.10.21、torch 2.7.1+cu128、numpy 1.26.4；ESM-IF1 与 ThermoMPNN 的 scipy 等版本不同，未认定统一环境兼容，单GPU解释器环境装配仍待实现 |
| A3D | Python 2.7.15，独立保留科学解释器；不能直接用它运行新的Python3.11监督器 |

新增 [resident_process.py](../../src/t01_phase1_real/resident_process.py) 和 [resident_worker.py](../../src/t01_phase1_real/resident_worker.py)：可信启动配置登记工具/解释器/命令，控制方提供原任务绑定与有界输入字节，常驻 Worker 轮询共享执行目录并串行启动子进程。输入/命令重放一致性、取消、期限、持久化启动记录、输出清单/hash及停止确认复用原POSIX进程归属原语。缺失进程登记保持未确认，不假设已停止；不自动重跑中断尝试。Worker 的 `.processes` 登记随执行目录持久化。它只管理执行收据，不新建业务任务数据库，也不调用Kubernetes/Docker API。

最终[Linux专项](../../discovery/t01-phase1-real/resident-worker-20260915/engineering-r01/linux-tests.txt)为17通过，包含监督进程真实强制终止后的恢复、进程树超时、运行中取消、重复/篡改/越界拒绝、同一监督进程两次原生FreeSASA双原子计算，以及常驻CLI接收两批不同时间到达的任务。[Windows专项](../../discovery/t01-phase1-real/resident-worker-20260915/engineering-r01/windows-tests.txt)为8通过/9项Linux专属跳过。原生FreeSASA探针验证输入到原生数值及执行层，不代替完整结构映射/RSA验收。命令、执行边界及源码hash见[汇总](../../discovery/t01-phase1-real/resident-worker-20260915/engineering-r01/summary.json)。本轮不重跑未修改工具的完整科学验收。

**尚未完成：** 业务 Runtime 到共享执行目录的桥接、各原生worker固定绝对路径的装配、各工具结果profile、老Python科学环境与新监督器共存、单GPU环境切换/资源配置、HiMat文件与报告接口、镜像资产迁移和服务器部署。当前通用Job分支仍保留原行为，不能仅启动新CLI就宣布科学工具接入完成。后续在本包内批量适配，不重新开发科学算法，不请求恢复Job权限。

### 常驻业务桥接与原生解析回填（2026-09-15）

本批继续现有部署包，完成`resident_execution.py`到业务Runtime的派发/恢复/取消/超时/终态发布桥接。配置在服务启动侧登记，每个attempt保留原job/attempt/execution身份；控制面中断后重放相同输入，不另开科学任务。配置变化、外来停止收据或未确认进程保持reconciling；已确认停止但原生产物缺失/篡改则明确失败。原Windows冻结运行文件和历史验收资产未修改。

十类原生结果解析器（结构、DeepTMHMM、BepiPred、NetMHC、BLAST、同源、ProteinMPNN、ESM-IF1、ThermoMPNN、FoldX）批量使用独立常驻执行记录，保留真实CPU/网络接口、源镜像身份和输入/输出hash，不伪造旧Docker镜像/CPU/loopback观察。原数值、完整性、版本和科学资格检查保留，N11到N12/负担核验携带常驻原始收据。A3D是N10内嵌执行，未包含在本批十类适配中。GPU型号等更细的环境差异仍须在环境装配及真实执行中闭合，不能仅据解析器修改宣布A100已适配。

新增`resident_offline.py`在登记子进程exec前安装继承到子进程的Linux/amd64 socket限制；Internet套接字创建被拒绝，本地IPC与接口枚举可用。机制依据[Linux seccomp文档](https://www.kernel.org/doc/html/v5.15/userspace-api/seccomp_filter.html)，它不代替工具资产校验或容器隔离，也不作为通用不可信代码沙箱。现有进程组停止机制不变。

`Dockerfile.resident`基于本机已核验FreeSASA镜像离线构建，以固定路径别名切换每次输入与原生输出；监督日志单独保存。新完整结构探针在一个常驻Worker生命周期内连续提交两个新任务，真实完成结构映射和FreeSASA，结果经原解析器进入任务查询，计算值一致。两次任务的原始输出随结果以base64保存，主机侧逐份核对大小/hash通过；历史案例仅提供原始请求与结构文件。本批定位并修复OpenBLAS默认线程过多触发虚拟内存限制的环境问题，结构命令显式设置`OPENBLAS_NUM_THREADS=1`。

受影响十类工具及目标结构旧路径专项481通过；常驻Linux执行专项18通过，包含子进程继承禁网限制的实测。另在存在eth0的容器中实际确认工具子进程创建Internet套接字仍被拒绝。全仓首轮1809通过/1失败/11跳过，唯一失败为旧CI测试仍断言部署名`t01-control-plane`；按已确认的Jenkins和现场部署名`antigen-design`修正后，最终相关104项通过，未重复整套全仓。最终文档检查通过，保留29处既有历史断链。完整命令、首轮失败及修正后验证、镜像ID和源码hash见[r02汇总](../../discovery/t01-phase1-real/resident-worker-20260915/engineering-r02/summary.json)及其日志；不把专项复测写成另一次全仓全绿。r01原证据保留不覆盖。

**下一项：** 批量装配其余原生工具的固定路径、包/权重和不同解释器环境，处理A3D嵌套执行与单GPU调度；随后补HiMat文件引用/RustFS报告接口、资产迁移清单和现有Deployment更新配置。当前仅结构环境已取得新的完整常驻实跑证据，未迁移全部镜像/资产，未修改服务器，完整科学Gate与正式交付资格不变。测试服流程优先标准继续适用，不恢复逐工具生产验收顺序。

### 常驻环境批量装配回填（2026-09-15）

按用户“先完成1”完成本地批量环境装配。新增[装配器](../../scripts/assemble_resident_workers.py)和[固定环境配置](../../src/t01_phase1_real/resident_assembly.py)，从逐一核对ID的本机原镜像禁网构建9个派生镜像：结构、DeepTMHMM、BepiPred、NetMHC、BLAST、同源、FoldX、A3D及GPU。NetMHC组含两个MHC工具，同源组含MMseqs2/MAFFT/BLAST。GPU组在一个Worker内串行调用ProteinMPNN、ESM-IF1和ThermoMPNN，三套Python依赖分别保留；监督层单独使用Python3.11。A3D保留原Python2.7/conda，不移植科学代码。

每个执行切换独立输入、输出及临时目录；ThermoMPNN的动态local.yaml通过执行目录视图提供，原包只读不改。模型包固定挂载到`/t01/assets`，数据库按登记ID映射`/t01/databases/<group>/<database_id>`。装配时修正同源BLAST路径、ESM-IF1原包导入路径及FoldX探针参数；这些是工程启动问题，不改科学阈值。CPU工具和GPU工具均由固定注册表选择解释器，运行时不创建Docker容器或Kubernetes Job。

验证：9个实际Worker CLI入口均启动成功；11类原生环境各连续2次，共22次，原Python版本及原包版本逐项比较一致。工具启动/关键依赖导入、FreeSASA双原子计算、任务临时目录隔离和Internet套接字拒绝通过；GPU组在同一监督进程中执行6次，三套环境均实际完成CUDA张量运算且仅可见一张卡。本机GPU为RTX5070Ti Laptop，不能替代目标A100验收。Linux专项25通过，Windows专项30通过/14项Linux专属跳过；十类现有资产校验器只读核验通过。构建记录、具体检查范围、原始输出、固定ID和源码快照见[装配索引](../../discovery/t01-phase1-real/resident-worker-20260915/assembly-r01/index.json)，操作见[运行手册](../development/RUNBOOK.md#常驻环境批量装配)。旧r01/r02业务桥接证据不覆盖。

本批完成的是环境装配与启动验证，未进行全部模型权重加载/推理、数据库检索或N01–N18整链验证。A3D原生环境已装配，N10的嵌套业务派发仍待接通。原包/权重挂载使用本机只读资产，未导出大镜像、上传Harbor、迁移资产或修改服务器。下一项为镜像/资产批量打包及迁移配置，随后集中真实计算与HiMat联调；原24条淘汰候选未重跑，科学Gate及正式交付资格不变。

### Codeup发布通道现场补充（2026-09-15）

**发布修复与线程实跑回填（2026-09-16）：** 用户明确授权将修复及4份BepiPred来源文件推送至现有Codeup仓库`test`并继续部署验证，提交`3ecb280`已推送。根构建现按原hash恢复结构来源及BepiPred仓库内来源的换行，并补齐原包wheel、python-freeze和两份安装报告；冻结原件、资产清单及旧任务未改。最终Git LF候选镜像20项来源核验通过、恢复8项，挂载原始资产后的BepiPred 104项校验通过，232项受影响测试通过。初次沙箱测试因临时目录权限产生43项setup错误，换独立目录后上述回归通过；非完整根回归，未跨旧完整Mock/S07，二者未重跑。旧批次的BepiPred还有ASSET_MISSING（4份来源未打包及文档换行不符），现已纳入本次构建修复；原失败报告已下载并核对大小/hash/ZIP CRC，保存在`.tmp/cluster-workflow-probe-r01`。

DeepTMHMM线上观察为192个可见CPU、cgroup `cpu.max=400000 100000`（4核上限）；冻结`predict.py`原样调用`set_num_threads(192)`及`set_num_interop_threads(194)`，覆盖已有2线程环境设置，且cgroup存在明显节流。新增`development/torch_threads.py`仅在常驻启动适配层执行登记的OMP/MKL线程预算，记录requested/applied，保留原包字节、真实CPU观察、科学计算和600秒期限。非resident路径维持原行为。线程修复镜像已以新标签发布，平台摘要`sha256:f44806c4a2e66a229ef1bfcba9c6fa2ada8c788ebdbab8259e081796c9c1fe88`；原子patch仅更新DeepTMHMM镜像，generation=9的10个容器Ready且0次重启。本机同序列禁网实跑33.98秒；独立服务器新任务`t01p1r-job-126e860be9204cab97c14f098c59ec1e` succeeded、无错误，模型全程13.32秒，实际线程2/2，全部Artifact通过读取校验，仍`usable_for_pipeline=false`。

本轮发布快照、Worker发布回执及独立任务证据位于`.tmp/cluster-fixes-20260916-r01`。用户确认Jenkins正在构建后，助手回读generation=observedGeneration=11、Pod `antigen-design-6844f9cd6c-xhg7w`的10容器Ready且0重启；控制面实际摘要`sha256:78b5875032698cafe2ef82057622dd40949e3afbae5eaf69d701effe600b7dc1`。4份运行源码与Git提交`3ecb280be15f873afea69101b4b1c9a99de8a29b`逐一hash相同，线上20份来源及104项BepiPred资产验证通过，回执`control-release-verification.json`。用户未提供本次完整Jenkins日志，源码和运行镜像已直接对应，但不冒称已归档流水线全过程日志。

随后使用`run_cluster_workflow_probe.py prepare/start/status/download --batch r02`新建独立批次，任务`t01p1r-job-b5c8b65e06914192b4de20f2290598bd`已完成，重复提交复用同一ID。逐节点11项succeeded、8项skipped、0 failed/timed_out：结构、拓扑、BepiPred、NetMHC、表位汇总、糖基化、developability及交付汇总成功；无库、无表达宿主与科学门控关闭项按原理由跳过。`.tmp/cluster-workflow-probe-r02/report.zip`为158295字节、4成员，SHA-256 `f5f5a1ec8b2bc9afa0ee3dd318b1738185961d5e3acbf03c5c6ae9913dd9d0f0`，下载大小/hash/ZIP CRC全部通过。r01保持原身份与失败事实。本批仅确认认证MCP分析及直接报告链工程通过；未运行GPU/FoldX及完整A3D，未验证HiMat业务界面，科学Gate仍CLOSED。RustFS报告代码与环境补丁仍未纳入本提交；下一项发布报告接入并验证HiMat附件。文档检查通过，保留29处既有历史断链。

**首轮服务器失败定位及构建修复（2026-09-16）：** 本次workflow `t01p1r-job-8a450e87e18f4b58868fb585ed6524da`最终succeeded表示流程汇总完成，结构子任务`245d03be…`failed/HASH_MISMATCH，DeepTMHMM子任务`f08a0d79…`timed_out/TIMEOUT。只读核对线上structure/sources.json的15项来源，7份文档/JSON为LF而原清单对应CRLF；各文件仅恢复换行即可精确匹配原SHA-256，确认发布字节变化，本地core.autocrlf=true。新增[scripts/restore_pinned_build_sources.py](../../scripts/restore_pinned_build_sources.py)，根Dockerfile与.dockerignore接入：只在构建副本恢复与既有hash完全一致的LF/CRLF候选；有内容差异则失败，拒绝Git工作树，不改原件和冻结清单。真实HEAD blob模拟15项验证通过、恢复7项；与任务脚本合计6项本地回归通过，未构建新镜像/提交/推送/部署。DeepTMHMM原生日志显示1条76aa样本embedding计算388.6秒，含加载至embedding完成约481.6秒，随后拓扑预测超600秒被停止，stopped_confirmed=true；可见CPU affinity为192核，但是否线程过多/配额限制仍待查，未直接放宽期限。用户应保留本批失败报告，发布修复并调整有证据的运行配置后新建批次；不得覆盖原任务或宣称科学全通过。status脚本新增失败/超时节点提示，避免总状态误读。

**服务器分析链操作准备（2026-09-16）：** 用户选择自行操作；同事HiMat异步文档仅作参考，当前先完成测试服真实计算。新增[scripts/run_cluster_workflow_probe.py](../../scripts/run_cluster_workflow_probe.py)，使用既有本地真实1UBQ mmCIF夹具，通过kubectl exec容器内认证MCP调用上传/提交/查询/报告，凭据留在service容器内。`prepare`只生成`.tmp/cluster-workflow-probe-r01/batch.json`固定请求、输入hash与幂等键；`start`保存upload/job ID并验证重复提交复用，`status`单次查询，`download`核对ZIP大小/hash/CRC并保存报告。用户在项目根运行`.\.venv\Scripts\python.exe -B -X utf8 scripts/run_cluster_workflow_probe.py start`，随后将末尾动作改为status、完成后download。本次prepare已执行；3项测试覆盖请求契约/无历史候选复用、提交响应丢失后的幂等恢复、错误报告hash拒绝；线上仅认证initialize成功（2024-11-05），未提交科学任务。此分析样本包含结构/FreeSASA、DeepTMHMM、BepiPred、NetMHC双通道、表位/糖基化及developability，沿用本地已验证请求；数据库关闭，mmCIF案例不代表完整A3D执行，GPU三工具与FoldX另用合适样本。结果明确保留工程资格及未执行项，不宣称完整科学验收。本轮直接下载验证现有线上报告接口；RustFS接入尚待发布，HiMat业务链另行验收。

**RustFS实际存储验证与接口实现（2026-09-16）：** 用户确认完成凭据录入；助手通过[scripts/verify_rustfs_cluster.py](../../scripts/verify_rustfs_cluster.py)从正在运行的service容器访问`https://rustfs.ne.scqcyz.cn/antigen-design/data/_probes/<随机ID>.txt`，只用本项目Secret，凭据在内存和exec stdin中传递。实际PUT、带元数据HEAD、匿名GET字节/hash核验、仅删除该测试对象及HEAD 404回读均通过；本地回执`.tmp/rustfs-verification/probe.json`为ready/write_verified/public_download_verified/test_object_deleted全真。该结果确认现有账号的本桶所测读写清理权限，不宣称该账号只有本桶权限或已创建专用IAM身份；未修改桶策略或原报告文件。

新增[object_storage.py](../../src/t01_phase1_real/service_api/object_storage.py)使用标准库HTTPS和S3 SigV4，端点来自运维配置、强制TLS且不跟随重定向。报告按`data/<principal-scope>/<job_id>/<内容hash>/report.zip或report.md`发布，重试复用且验证已有对象，首次PUT采用If-None-Match防覆盖。HEAD大小及SHA-256元数据、公开GET完整内容hash均通过后才返回附件。`Service.report_for_json`先执行既有任务归属和本地产物验证，再发布两份附件；启用时用`attachments`和`publication_status=verified`替代Base64，未启用仍保留原接口。上传失败返回REPORT_PUBLICATION_FAILED/503，调用workflow.report可重试，不重算科学任务；直接REST ZIP下载仍兼容。MCP输出Schema增添附件字段，workflow.report标注可能写入对象，不再声明只读。

8项存储专项、10项服务回归（含跨调用者拒绝、失败重试及Base64兼容）、3项凭据脚本测试共21通过。已准备[control-env.patch.json](../../deploy/rustfs/control-env.patch.json)，只向service注入端点/桶/前缀和两项Secret引用，服务器战略合并dry-run通过；未应用该补丁。Jenkinsfile显式增加`containerName: 'service'`，防止多容器发布时依赖列表顺序。本轮没有提交/推送或部署新代码，线上仍未自动发布报告；下一步Codeup test发布控制面后应用环境补丁，并以新任务验证MCP报告URL和HiMat附件显示。当前回退脚本原计划会拒绝后续环境/镜像漂移，继续发布前需保留当时部署快照。

**RustFS下载方式确认（2026-09-16）：** 用户明确选择“和oligosmith一样的策略”，采用`antigen-design/data/*`公开只读及应用专用凭据写入；[公开读取策略](../../deploy/rustfs/antigen-design-public-read-policy.optional.json)现为选定配置，文件保留原名。助手提供给用户在当前桶策略窗口粘贴保存；未操作浏览器，未应用远端策略，保存及匿名下载结果待回读。该决定关闭下方记录中下载方式待选项；后端上传实现和AK/SK配置仍待完成。

**RustFS报告交付配置回填（2026-09-16）：** 用户提供已创建但未配置的`antigen-design`桶，要求报告放入该桶。核对`service_api/app.py`发现`report`只组装已校验的Markdown及ZIP，`report_for_json`仍返回Base64，尚未实现S3上传；此前就绪检查不覆盖该缺口。参考引物项目运维文档，其Endpoint/Public base为`https://rustfs.ne.scqcyz.cn`、region为`us-east-1`，本项目拟使用独立`antigen-design/data/<job_id>/...`对象路径。已准备[应用身份策略](../../deploy/rustfs/antigen-design-app-policy.json)，允许本桶data前缀读写、按前缀列举及删除`data/_probes/*`验收对象；另备[可选公开读取桶策略](../../deploy/rustfs/antigen-design-public-read-policy.optional.json)，仅允许匿名GetObject。策略草案均未应用，应用身份策略不应粘到桶策略窗口，参考项目公开策略不自动继承。用户正在选择公开只读或私有签名下载方式；专用应用AK/SK及本项目Secret尚未配置，未读取引物项目凭据，未操作RustFS控制台。后续补上传、大小/hash校验和下载链接输出，完成现场小对象写入/下载/清理及HiMat报告验收；本轮未配置桶、上传对象或修改正式Deployment。

**批量Worker启动回读（2026-09-16）：** 用户执行apply得到`ASSET_UPLOAD_POD_REMOVAL_REQUESTED; PVC RETAINED`和`DEPLOYMENT_SUBMITTED`。助手只读status确认Deployment generation=observedGeneration=8、readyReplicas=1；新Pod `antigen-design-75cf69d8c8-mmlvt`位于`k8s-a100-02`，service与9个worker全部Ready且重启次数为0，9组日志均有`resident_worker_ready`、共登记11项命令。控制面经Linux安全配置读取入口加载`/etc/t01/resident.json`成功，摘要`ef41993f840a9b3e1a65757125a61877707d10d43cab89ee2303c4071981b1ee`；9个共享执行根均存在且进程权限检查为可写，8个工具资产目录已挂入控制面。回执见本地`.tmp/antigen-resident-deploy-r01/mount-check.json`。从HiMat api容器请求集群内healthz成功，8个MCP工具、Gate CLOSED、生产NOT_DEPLOYED和三个未登记数据库摘要不变。此轮启动/挂载检查未重新执行230文件hash验收、科学模型推理、认证业务提交或报告下载；下一项集中真实小样本计算和HiMat业务验收。

**批量Worker部署准备回填（2026-09-16）：** 已添加[scripts/deploy_resident_cluster.py](../../scripts/deploy_resident_cluster.py)，提供prepare/apply/status/rollback。prepare只读核对单副本Recreate控制面、当前运行摘要、原Secret引用、两块PVC Bound、HAMi成功Pod，以及控制面/本机/集成构建输入中的11项原生命令一致；生成Git忽略目录`.tmp/antigen-resident-deploy-r01`，包含`resident-config.json`、`deployment.before.json`、`deployment.target.json`和`plan.json`。ConfigMap和Deployment服务器dry-run均通过，未创建ConfigMap或更新正式服务。目标为service加9个固定摘要Worker，共享`/var/lib/t01`，资产卷在控制面挂`/app/var/t01-phase1-real/tool-assets`、Worker挂`/t01/assets`，均只读；控制配置使用subPath常规挂载以兼容无符号链接文件读取，每个Worker有独立`/run/t01-slot`临时卷。GPU采用实测准入值runtimeClassName=nvidia、schedulerName=hami-scheduler，先申请10240MiB小样本集成配额，未声明正式容量充足；数据库未登记，未提供虚构数据库。apply先检查部署未漂移，再应用配置、核对并删除临时资产上传Pod以释放RWO资产卷（保留PVC），最后以UID/resourceVersion原子前置条件更新Deployment。rollback同样拒绝覆盖其他人的后续变更，恢复原控制面及其已运行摘要；status使用单次查询避免watch stream中断。生成器4项测试覆盖共享路径/凭据隔离/单GPU分配、拒绝未核验镜像或已有旁车、部署漂移阻断和原子版本检查；装配回归4项通过，合计8通过。下一项用户执行apply并返回status，再进行真实任务及HiMat验收。本次未提交/推送代码、未触发Jenkins、未实际启动Worker。

**HAMi GPU轻量实跑回填（2026-09-16）：** 用户创建`antigen-gpu-probe-r01`，随后`kubectl get -w`发生watch stream INTERNAL_ERROR。助手使用独立短请求回读Pod和事件，确认Completed、0次重启、节点`k8s-a100-02`；HAMi过滤与绑定成功，既定GPU镜像拉取约132.817秒，之后正常创建并启动容器。回读日志为`TORCH_VERSION 2.7.1+cu128`、`CUDA_RUNTIME 12.8`、`GPU_DEVICE {"name": "NVIDIA A100-SXM-64GB", "reported_memory_MiB": 10240}`及`GPU_COMPUTE_PASS`。此证据关闭下方准备阶段的调度/基础CUDA运行待验证项；仅验证微小矩阵运算与报告显存，不代替模型加载、科学任务、超额显存隔离或正式配额验收。本轮仅只读检查及文档回填，已完成Pod暂留以便查看日志，正式Deployment未修改。

**HAMi GPU配置与轻量验证准备（2026-09-16）：** 用户转发同事提供的[HAMi vGPU验证文档](https://project-hami.io/zh/docs/get-started/verify-hami)及`nvidia.com/gpu: 1`、`nvidia.com/gpumem: 10240`截图。该示例提供GPU和显存资源键，10240对应示例10GiB配额，不代表本项目正式显存需求或已获得64GB。助手准备`.tmp/antigen-gpu-probe.yaml`，引用已发布GPU平台摘要`2079483853695089e1924d839221aa016481bc9e822b6e436dae8277a428ab8a`，在him-ws申请同示例配额并执行128×128 CUDA矩阵运算；不加载模型或挂载PVC，无SA token、非root、15分钟期限。`kubectl create --dry-run=server`通过，未真正创建Pod；该结果仅证明准入校验通过，不证明调度、驱动兼容性或HAMi配额隔离已通过。下一项用户运行并返回`GPU_COMPUTE_PASS`或Pod失败事件，结束后删除该临时Pod。实际GPU型号、显存上限和正式Worker申请值据现场结果继续落实；本次未安装HAMi、修改节点/共享组件或更新正式Deployment。

**9个Worker镜像发布完成回填（2026-09-16）：** 用户返回GPU续传完整输出，末尾为`VERIFIED_REMOTE gpu sha256:2079483853695089e1924d839221aa016481bc9e822b6e436dae8277a428ab8a`、`ALL_PUBLISHED 9`、`TEMP_RELAY_REMOVED`。助手读取`deploy/antigen-resident-publish-20260916-r01/publish-receipts.json`，确认9个分组均为VERIFIED、GPU摘要与日志一致；此次未另行远端复核。该结果关闭下方交接时点的GPU镜像上传未完成项，临时镜像中转Pod按脚本输出已清理。下一项核实GPU调度配置、将既有资产卷挂入正式Pod并批量接入Worker；镜像发布不代表容器已运行或科研流程通过。ESMFold2模型下载为独立任务，不包含在该GPU镜像中。

**Worker镜像发布与GPU续传交接（2026-09-16）：** 按用户授权，核对9个本地integration-r01镜像ID及linux/amd64身份，导出D盘`deploy/antigen-resident-publish-20260916-r01/workers-linux-amd64.tar`（15,457,793,536字节），逐blob哈希及Docker/OCI绑定校验通过；目录加入Git忽略。通过临时`antigen-registry-relay-r01`（仅Pod回环18483监听，无SA token）及本机127.0.0.1端口转发，按Registry V2分块推送本项目独立标签`integration-20260916-r01`，复用已有层并拒绝覆盖不同manifest。结构、DeepTMHMM、BepiPred、NetMHC、BLAST、同源、FoldX、A3D共8镜像已完成远端manifest逐字节摘要及层大小回读，结果在发布目录`publish-receipts.json`。GPU未完成，曾并行上传两个大层后合并续传记录；进程中断后恢复8镜像核验及GPU续传。用户随后要求GPU自行上传，助手已停止本轮两个Python进程及一个专用端口转发，未删远端数据；中转Pod仍Running、续传记录保留。入口`.tmp/resume_resident_publish.py`读取既有导出和内存凭据，检查中转Pod身份后恢复；已发布层跳过，完成后写入9项回执并清理中转Pod。该入口无需Docker继续运行，需本机保持联网；失败可检查后同命令重试。当前正式Deployment、资产卷和上传Pod未变，不声称9镜像发布或科学流程完成。

**既有Harbor凭据权限实查（2026-09-16）：** 用户提供Rancher `him-ws/harbor` Secret页面，指明现成机器人账号。助手从`antigen-assets-upload`请求内部`/v2/`，收到401及同主机`/service/token`认证挑战；随后在本机进程内读取该Secret，仅向已核实的内部认证主机传递相应凭据，禁止认证重定向，没有打印密码/令牌或保存凭据副本。对`qcyz/antigen-design-resident-{structure,deeptmhmm,bepipred,netmhc,blast,homology,foldx,aggrescan3d,gpu}`请求pull/push范围，Harbor返回令牌内九项授权均含两种操作。该结果确认现有账号权限，不冒充镜像推送回执；本次没有Registry写入。下一步准备经已授权Kubernetes连接建立内网传输/发布通道，复用现有凭据批量发布已验证的integration-r01镜像，并回读远端digest。无需新申请公网入口或机器人账号；旧段“推送权限待落实”是核实前时点。

**公共Pipeline源码审阅（2026-09-16）：** 用户提供`qcyz`配置页及完整Groovy脚本；只提取非敏感结论，不保存含通知凭据的原件副本。`projectConfig.imageName`可覆盖镜像名；`matched.containerName`可显式选容器，缺省才读取首个容器。Build固定`buildctl build --frontend dockerfile.v0 --local context=. --local dockerfile=. --output type=image,...,push=true`，没有配置化Dockerfile路径、构建target或多镜像循环。`findTarget`从targets返回单个最匹配项，不是遍历部署列表；配置多个targets不能自动批量构建。匹配目标但workloadName为空可跳过Deploy，但仍只构建一个根镜像。现有脚本可解析本项目以后新增的`containerName: 'service'`，不必修改共享任务；本次仅核对并记录，未编辑公共脚本、本项目Jenkinsfile或触发部署。首次Worker部署优先复用9个已验证`integration-r01`镜像批量发布，需确认已有Harbor可达推送入口及项目级推送权限，或由获准的内网构建节点批量导入发布。不可把本地基础镜像标签当作Jenkins端可拉取资产，不直接将旧assembly大包冒充修复后的集成镜像。本阶段不强制新建公网Harbor入口或改动公司共享流水线。

**资产卷迁移与解包验收（2026-09-16）：** 用户应用本地`.tmp/antigen-assets-upload.yaml`，创建20Gi ceph-rbd RWO资产PVC `antigen-design-assets`（Bound，PV `pvc-43532483-d30b-4350-af86-1c59c8483ec6`）和Ready的`antigen-assets-upload`临时Pod。Pod复用已发布控制面镜像但仅运行等待进程，使用UID/GID 10001，未执行科学工具。用户上传`tool-assets.tar`到`/assets/.incoming`，回传SHA-256为`4fe3b7711a7fd3fe435b930f66e305eaa2a9265c1e63123e0e6d073b5316639c`，与已登记归档一致；以`tar --no-same-owner -xpf`解到卷根。助手经kubectl exec只读按原`metadata/assets.json`逐文件校验大小、SHA-256和模式，结果230/230 PASS、errors为空（228个0644，2个0755），可用空间5,815,529,472字节。原归档保留，无删除动作；正式Deployment未挂载该卷，Worker镜像及GPU尚未部署，不代表科研流程验收完成。下一项落实9个Worker镜像发布通道和GPU配置，更新正式Pod挂载前移除临时上传Pod以释放RWO挂载，PVC保留。用户继续自行操作浏览器；本次只读验证与文档更新未触发CI。

**本机连接与权限实查：** 用户自行下载kubeconfig，助手按要求复制到Git忽略的`.tmp/himat.kubeconfig`，源/副本SHA-256一致，原下载保留，未输出认证内容。通过本机kubectl只读连接Rancher集群入口成功；Deployment为Ready 1、`service`单容器、Recreate、imagePullPolicy Always，请求500m CPU/1Gi内存、上限2 CPU/4Gi内存。运行PVC为20Gi ceph-rbd且Bound，仍仅挂载运行卷、凭据和256Mi临时卷。`auth can-i`确认create pods、pods/exec、pods/portforward、persistentvolumeclaims、configmaps，patch deployments.apps，以及get pods、pods/log均为yes。权限查询不替代实际传输验收；此次未创建资源、读取Secret内容或变更Deployment。下一动作准备独立资产卷与传输入口，落实Worker镜像发布与GPU配置；本人连接可用不等同于Harbor推送权限。下段默认kubeconfig缺失为此前时点，现已使用显式私有路径连接。

**重触发后的目标回读：** 用户返回`antigen-design-77c777d64c-shb7l`为Ready true，实际imageID为`harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:1601b336499ffbd6ec8446b7a5d6a03741aec45299a5babb3eec40dc2d8c9592`，已区别于原`497e7826…88661be`。Deployment配置引用`latest`，rollout成功；HiMat `api`访问healthz为ok、8工具、Bearer认证，数据库根仍为null，Gate CLOSED、NOT_DEPLOYED。代码提交`c5f5200`后增加Dockerfile构建标签的`07ee0b9`再次推送，现已取得新控制面镜像运行证据；随后提供的Jenkins日志已绑定精确提交，见下一段，不据此声称科学Worker/权重已部署。下一项继续资产传入与Worker装配。本机已装kubectl，但默认`%USERPROFILE%/.kube/config`不存在；可由用户从Rancher下载本人有权取得的kubeconfig到Git忽略的私有目录，先确认本机连通和实际文件传输权限，再准备资产传输。该连接不等同于Harbor推送权限，不申请Nodes或base Ingress权限。

**Jenkins日志核对：** 用户取得查询账号并自行提供`qcyz`实际构建日志，上游为`qcyz_webhook #992`。Checkout为`origin/test`的`07ee0b9fa4507fe350bdfcd353683a9e064aba8f`；BuildKit以仓库根为context和Dockerfile目录，构建并推送`antigen-design:latest`，输出manifest摘要与上述Pod的`1601b336…d8c9592`完全一致。Deploy先读取`.spec.template.spec.containers[0].name`，本次得到`service`，随后执行`kubectl set image`、`rollout restart`及`rollout status --timeout=5m`，最终SUCCESS。此次执行只发布一个控制面镜像，没有构建9个Worker、导入权重或创建挂载资源。后续如添加同Pod Worker，需保持`service`为首个容器或核实流水线的显式容器选择支持，避免公共发布更新错容器；公共脚本的其他扩展能力尚未核实。日志另含通知凭据明文，本仓库仅记录上述非敏感事实，不复制原日志或凭据。

**此前试推授权（已执行）：** “我没有权限去看公司的流水线。先推到test分支试试。”据此完成本轮代码提交及普通快进推送，未等待公共脚本；提交范围为常驻适配、装配/验证脚本、测试和现行文档，本地镜像/权重/业务数据及生成ZIP未进入Git。现有根Dockerfile和Jenkins目标保持，控制面发布已由上方构建日志与目标回读对应。科学Worker和资产仍需实际落盘/挂载，不能由源码推送推定完成。

用户再次明确通过`agent/antigen-design`仓库的`test`分支触发公共流水线自动部署；继续沿用该通道，不以申请公网Harbor推送账号为前置。用户返回：账号`m-mcm7t`不能列出`base`命名空间Ingress或集群Nodes；`him-ws`内ResourceQuota/LimitRange查询为`items: []`。这仅说明该命名空间没有这两类配置对象，不证明CPU/内存/GPU资源无限，也不说明用户不能使用GPU。无需扩大集群查询权限来继续准备发布。

本地核对：当前分支为`test`，origin匹配用户仓库，`Jenkinsfile`声明`him-ws/antigen-design`目标；根Dockerfile仅构建控制面，构建上下文不包含本机Worker镜像及权重。公共构建/推送/更新脚本不在当前Jenkinsfile中；此次执行路径已由上方日志确认，多镜像扩展及本机科学基础镜像如何供服务器取得仍待落实。下一项先打通本机到集群的受权连接，确认资产传输条件，再落实批量Worker镜像发布；约7GB资产需一次性传入测试服资产卷或既有制品通道，不能当作普通Git源码随推送带入。GPU资源键及调度字段可由同事提供已运行GPU工作负载的脱敏配置，不再要求用户重复查询Nodes。本次日志核对仅更新文档，未再次提交、推送或触发部署。

### 常驻业务集中联调回填（2026-09-15）

按用户“完成第三步”实施，本地业务接通与集中实跑完成；HiMat服务器验收尚未执行。新增`resident_a3d.py`接通N10嵌套常驻A3D，复用原任务身份、原生解析和结果发布；超时/取消及中断恢复须确认原请求停止，不重新提交计算。消费结果时再次核验请求、收据及原生文件hash。

实跑修复两项装配问题：BepiPred的`/app`搜索路径曾覆盖镜像内已登记的bp3 wheel，改为从原安装环境导入；ThermoMPNN沿`realpath(__file__)`找配置，原软链接布局读到了原包中的实验室路径，改为逐字节复制Python源码到任务视图，权重继续只读链接，`local.yaml`指向已登记的运行配置。未修改原包、权重或科学阈值，未放宽版本/hash校验。

| 验证 | 结果与边界 |
|---|---|
| 原生工具 | 结构/FreeSASA、DeepTMHMM、BepiPred、NetMHC双通道、BLAST、MMseqs2/MAFFT、A3D、ProteinMPNN、ESM-IF1、ThermoMPNN、FoldX共11类均取得新真实计算结果；另有PROPKA真实计算 |
| 输入范围 | BLAST和同源库仅使用ENGINEERING_FIXTURE；GPU使用新的9残基工程结构、单样本生成和回评分；原24条淘汰候选未读取或重跑 |
| HTTP MCP | 本地认证枚举8工具，上传、幂等提交、等待、查询、报告下载通过；无认证返回401；ZIP为157,365字节，递归14成员校验通过 |
| 证据与测试 | 4个成功批次共21个新任务，452份任务产物大小/hash通过；含失败诊断和源码的索引共1,151文件；受影响Windows测试183通过，Linux进程/装配测试26通过；未重跑全仓 |
| 新镜像 | 控制面及9个Worker构建为`integration-r01`，镜像源码hash及禁网启动逐个通过；真实计算使用原装配镜像加只读源码/配置挂载，未在新镜像重复执行全部模型 |

证据：[集中联调索引](../../discovery/t01-phase1-real/resident-worker-20260915/integration-r01/index.json)、[摘要](../../discovery/t01-phase1-real/resident-worker-20260915/integration-r01/summary.json)。增量包`deploy/antigen-design-resident-integration-20260915-r01.zip`共534,188字节，包含源码/配置/Dockerfile；复用第2步镜像层及权重，不重复导出大包。第2步完成包保持原字节，尚不包含本轮修复或新控制面镜像，部署须使用匹配的新镜像及配置。

MCP的1UBQ mmCIF案例中，N10保留结构格式不支持状态；另一个9残基结构样本独立跑通A3D与PROPKA。完整设计Gate、CamSol和未闭合科学规则、AF3/ESMFold2、正式数据库及科学资格不变。本地MCP通过不代表HiMat现场或RustFS附件已验证。下一项是落实镜像上传通道、服务器资产卷和GPU挂载，更新测试服后由HiMat完成提交→查询→下载；现场由用户操作，不恢复动态Job/RBAC前置要求。

### 常驻镜像与资产打包回填（2026-09-15）

用户完成Docker Desktop磁盘迁移后继续第2步。回读确认`CustomWslDistroDir=D:\DockerData\DockerDesktopWSL`，C盘可用空间由约15GiB恢复到107.65GiB；49条镜像记录的ID/标签、19个容器、22个卷均保留，迁移前16个运行容器全部恢复，无unhealthy。迁移由用户在Docker设置中操作，助手仅备份清单、回读核对并继续D盘打包。

新增[批量打包/独立验证器](../../scripts/resident_bundle.py)，以第1步已核验索引为输入，将9个现有Worker镜像一次性导出为`workers-linux-amd64.tar`（15,457,519,616字节，14.40GiB），另将230份已登记原包/权重/许可相关文件按原路径打包为`tool-assets.tar`（7,562,240,000字节，7.04GiB）。所有输出在D盘；不复制整个Docker虚拟磁盘，不重建镜像，不打包业务任务、Secret或未登记数据库。大包目录为`deploy/antigen-design-resident-20260915-r01`，配置、逐文件索引、SHA256SUMS和标准库独立验证器随包提供。

首次Docker导出成功，但初版检查器将顶层OCI索引ID与导出平台的配置hash直接比较，导致校验失败；修正后逐个从本地Docker回读`linux/amd64`平台摘要，与包内OCI清单、Docker清单、配置和全部blob关联核验。复用原导出文件，未重复生成第二份大镜像包。`metadata/images.json`分别登记原本地ID和`export_manifest_digest`；接收端导入单平台包后显示的平台ID可能不同，不能当成镜像丢失，也不能冒充Harbor推送完成。

挂载方案记录在包内`configuration/mount-plan.json`，当前为`PROPOSED_NOT_APPLIED`：控制面与9个Worker放入同一Pod共享现有RWO运行卷，拟新建20Gi资产PVC并只读挂到控制面原资产路径及Worker `/t01/assets`，GPU组仅一处申请GPU并串行执行。每个Worker单独临时卷，单副本Recreate；现场GPU资源名、CPU/内存配额、资产卷创建及镜像上传通道仍待落实。本批仅提供挂载方案，不产生可直接应用的完整Deployment，也未更新控制面镜像或服务器。

资产包逐成员大小/hash及可执行权限、镜像包完整性、包内独立标准库验证器的本机全量校验和Linux专项测试结果见[打包回填索引](../../discovery/t01-phase1-real/resident-worker-20260915/packaging-r01/index.json)。原计划在Docker挂载Windows目录运行Linux全包校验，因跨系统大文件读取缓慢由助手停止（退出137），该次不计通过；改为本机隔离Python全量校验并在Linux测试检查逻辑，不把它写成Linux实际接收/导入验收。使用步骤单点见[运行手册](../development/RUNBOOK.md#常驻镜像与资产批量迁移包)。后续在同一部署包接通A3D嵌套业务路径、完成批量真实计算和HiMat文件/报告联调，落实Harbor上传/资产落盘与匹配现代码的控制面更新。数据库、AF3/ESMFold2、科学签收条件另按原范围继续；原24条淘汰不重跑，完整科学Gate和正式交付仍关闭。

### 测试服资源快照（2026-09-15）

来源为用户本会话返回的四组 kubectl 输出，助手未直连集群。以下记录 Deployment 的镜像引用，不冒充 Pod 实际 imageID 或本机独立部署验收。

| 项目 | 本次观察 |
|---|---|
| Deployment | `him-ws/antigen-design`，readyReplicas=1，容器名 `service`，容器端口 18083 |
| 镜像引用 | `harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:497e7826aa52cdcd61a99c30c39c0635d8035b5edd224f3ce8944f2c788661be` |
| Service | `antigen-design`，ClusterIP，80/TCP；HiMat 候选 MCP 地址为 `http://antigen-design.him-ws.svc.cluster.local/mcp`，尚未实测路由/认证 |
| 运行卷 | `antigen-design-runtime`，Bound，20Gi，RWO，ceph-rbd；挂载 `/var/lib/t01`，无 subPath；不能把历史 2Ti 规划写成实配容量 |
| 其他挂载 | `antigen-design-credentials` Secret → `/run/secrets/t01`；`tmp` → `/tmp`。未读取 Secret 内容 |
| SA 与接入缺项 | Deployment 的 serviceAccountName 未显式设置；未见工具资产或 launcher ConfigMap 挂载。Pod 实际账号权限尚未验证，不由默认账号推定可创建 Job |

公共权限可复用[已有管理员清单](../../deploy/t01-phase1-real-target-v0.2/kubernetes/administrator-bootstrap-him-ws.yaml)：`t01-control-plane` SA、`t01-scientific-job-controller` Role、`t01-control-plane-jobs` RoleBinding；该 SA 名称独立于 Deployment 名称，不要求更名已有服务。已对照当前 launcher 的 Job 创建/查询/删除、Pod 观察和策略回读核对清单；当前仅准备好，未应用或验证。此前用户不能创建 Role/RoleBinding，该授权由管理员一次落实。后续应用层配置再将现有 Deployment 绑定此 SA 并明确挂载 token；本次不直接替换已有 Deployment/Service/PVC。

用户随后从实际调用者 `deployment/api` 请求 `http://antigen-design.him-ws.svc.cluster.local/healthz`，返回 `status=ok`、`authentication=bearer`、`tool_count=8`、服务版本 `0.1.0`、`max_workers=2`，三类数据库根摘要均为 null。此输出确认 HiMat api 到服务健康端点可达；工具数是健康接口声明，尚不是带认证 `initialize/tools/list/tools/call` 验收。`scientific_gate=CLOSED` 与 `production_status=NOT_DEPLOYED` 为现行服务固定工程标记，不代表测试服进程没有部署，也不能将该 `0.1.0` 协议服务版本当作镜像发布版本。

本机只读盘点 `var/t01-phase1-real/tool-assets`：8 个目录、231 个普通文件，约 7.04 GiB，包含 BepiPred/ESM-2、DeepTMHMM、ESM-IF1、FoldX、NetMHC、ProteinMPNN、ThermoMPNN。仅统计现存文件大小，未重做完整性验收；不含容器镜像、服务器数据库、AF3/ESMFold2，也不能据目录存在推定可直接迁移运行。工具资产卷及各镜像在目标仓库的可用性仍待批量确认，当前 PVC 列表不足以证明服务器其他位置没有资产。现有其他应用卷不作为可直接复用的工具卷。

用户随后明确“科学工具都还在本地”，因此下一动作按批量迁移工具镜像及原包/权重准备，不再要求用户重复确认是否已经上传。上述现存目录统计不包含镜像体积；目标镜像推送途径及工具专用资产卷仍需落实。Job 权限是现行独立工具容器执行方式的运行依赖，非生产验收附加要求；引物项目将 BLAST/MAFFT 等安装在应用镜像内并通过子进程调用，不需要应用动态创建 Kubernetes Job 的权限。

### 目标环境只读盘点（2026-09-10）

来源：用户在本会话粘贴的网页终端命令输出及此前截图，由助手整理；不是助手直连集群的独立实测。以下为查询时点快照，不代表目标部署验收。后续现场信息集中更新本节，冻结候选中的 SITE_CONFIGURATION 不回写。

| 项目 | 已观察事实与边界 |
|---|---|
| 管理入口 | https://k8s.matai.center/dashboard/home；截图集群名 maic-gpu-lab；网页终端 current-context 为 default，仅为配置名称 |
| 目标命名空间 | him-ws；当前查询账号报错标识为 m-mcm7t |
| 用户账号 Job 权限 | create、delete、list、get、watch jobs.batch 均为 yes；list pods、get pods/log 为 yes |
| 用户账号资源创建权限 | deployments.apps、services、persistentvolumeclaims、networkpolicies.networking.k8s.io、serviceaccounts、secrets、configmaps 均为 yes |
| RBAC 阻塞 | create roles.rbac.authorization.k8s.io 与 rolebindings.rbac.authorization.k8s.io 均为 no；尚未核验专用 ServiceAccount 的有效权限，用户权限不能代替服务权限 |
| 配额 | him-ws 的 ResourceQuota、LimitRange 均无资源；不等于无限资源，也不证明已获得 32 CPU/192 GiB |
| 网络 | him-ws 无 NetworkPolicy；无权 list kube-system 的 DaemonSet，CNI 类型及实际禁网能力仍待确认 |
| 节点可见性 | 无权 list nodes；当前可见的 7 个 Pod 都在 k8s-a100-01，不推断集群只有一个节点，不推断剩余算力 |
| GPU | 用户另行确认可使用 1 张 A100、64 GB 可用显存；整卡/MIG/vGPU、扩展资源名及实际可调度量仍未机器核验 |
| 新项目仓库 | 2026-09-10 盘点时尚未建立。2026-09-14 同事已建立 Codeup 源码仓库 `https://codeup.aliyun.com/6549a8ea3aaed849b035cf92/agent/antigen-design.git`；它不是 Harbor 镜像仓库。历史代码路径、任务 ID 和冻结资产本轮不更名 |

**存储查询快照：** 三个 StorageClass 均为 Immediate、允许扩容；ceph-rbd 为默认类，驱动 rbd.csi.ceph.com、回收策略 Delete；ceph-rbd-retain 为同驱动、Retain；cephfs-retain 为 cephfs.csi.ceph.com、Retain。名称存在不证明新卷申请一定成功；容量、访问模式、调度与挂载仍需实测。

| 已有 PVC | 状态 | 容量 | 访问模式 | StorageClass |
|---|---|---|---|---|
| agentd-jobs | Bound | 20Gi | RWO | ceph-rbd |
| oligosmith-jobs | Bound | 20Gi | RWO | ceph-rbd |
| storage-ws-qdrant-ws-0 | Bound | 500Gi | RWO | ceph-rbd-retain |
| vol-himat-ws | Bound | 100Gi | RWO | cephfs-retain |
| vol-sandbox-ws | Bound | 200Gi | RWO | ceph-rbd |

这些卷属于现有应用，不作为新项目可直接复用的空闲卷。新项目申请独立存储；CephFS 现有 PVC 显示 RWO，不把它写成已验收 RWX。

**工作负载查询快照：** admin、api、knowledge、oligosmith、sandbox、sandbox-dep 共 6 个 Deployment，READY/UP-TO-DATE/AVAILABLE 均为 1；对应 6 个 Pod 加 qdrant-ws-0 共 7 个 Pod，均 Running、READY 1/1；本次输出无 Job。oligosmith 使用 harbor-core.base.svc.cluster.local/qcyz/oligosmith:latest，只证明现有应用镜像引用，不证明新项目仓库已建、外部可推送或新服务已有拉取权限。其余应用和重启计数不作为本项目验收数据。

**后续动作：** 按已确认名称建立镜像仓库并取得实际地址，准备专用 ServiceAccount 和管理员最小 RBAC 清单（依据当前 launcher 的实际 API 调用核对，不只复制口头权限列表）。无权创建 Role/RoleBinding 只阻断对应授权动作，其余本地工程继续。登记真实资产卷、镜像 manifest digest、拉取凭据引用及网络方案后，另构建包含修复的新候选，执行控制面与小型科学 Job 的现场验收。原离线包不包含本轮修复，不直接作为修复后版本部署。当前仍 NOT_DEPLOYED，科学 Gate 和原 24 条排除保持。

### 部署前缺陷修复与 Kubernetes 执行闭环

依据用户2026-09-10的部署前复核，本包统一处理运行层、发布目录安全、服务边界和Kubernetes生命周期，不再拆分准备或评审阶段。已验收的本地候选、镜像和离线包保持原字节；以下新代码不反向改写其验收结论，也不自动应用到集群。

| 问题 | 本轮实现及剩余条件 |
|---|---|
| Linux停止归属 | [POSIX控制](../../src/t01_phase1_real/process_control/posix.py)停止前核验出生身份与组归属，使用pidfd定位并冻结/停止所属进程，不再调用killpg；失效领导进程且仍有组成员时返回归属未确认，不冒充停止成功。现有Linux镜像内真实进程已验证过期身份不会停止进程、有效归属能停止 |
| 发布目录误删 | [发布脚本](../../scripts/build_target_linux_candidate.py)不再递归删除用户目标；stage只接受不存在的新目录，临时目录生成后重命名；render先验证镜像和全部Job参数，拒绝已有清单；ZIP拒绝覆盖及输出到自身源目录。既有候选不可原地重建 |
| Worker网络/期限/存储 | [模板](../../src/t01_phase1_real/deployment/kubernetes.py)新增选择科学Worker的Ingress/Egress拒绝策略、activeDeadlineSeconds、非主机网络/进程命名空间；Worker强制与控制面同节点以约束RWO挂载。CNI实际拒绝连接、节点容量和卷挂载尚待真实集群实测 |
| 逐工具迁移 | BepiPred补回只读package到/app及TORCH_HOME；DeepTMHMM/BepiPred/结构按CPU，GPU仅用于ProteinMPNN/ESM-IF1/ThermoMPNN；补回其他package、环境与所需native挂载。科学工具的镜像、资产目录、权限、实际资源行为仍须现场核验，模板不是可运行证明 |
| HTTP容量与慢连接 | 接收socket先设10秒读取超时；每次请求另有15秒读完期限；最多32个连接处理线程；服务任务队列默认64项，可在ServiceConfig设置max_pending_tasks，上限1024。超容量结构化503，恢复操作进入后台队列 |
| MCP权限与输入 | 身份认证和操作scope分离，仅upload凭据可以进入MCP上传但不能查询；media_type先验证类型。真实HTTP测试确认media_type数组返回422/INVALID_REQUEST |
| Kubernetes调度 | [HTTPS客户端](../../src/t01_phase1_real/deployment/launcher.py)和[任务桥接](../../src/t01_phase1_real/deployment/execution.py)已接入Runtime；固定执行名/输入身份/spec hash/Job UID，重启重新观察原Job，UID前置条件删除，等待所属Pod终止。失联或名称被复用保持未确认，不自动重建旧执行；不使用Docker socket |

**当前边界：部署前修复的本地验证已建立，真实Kubernetes到科学报告的闭环尚未完成。** 本机`kubectl config current-context`返回未配置。Kubernetes网络策略的存在不是CNI执行证明；现有科学结果验证器要求Docker的loopback网络与指定CPU亲和性，不能凭Job成功或伪造这些字段绕过。当前桥接发布原始目标观察与`PROFILE_NOT_APPROVED`诊断，不产出可消费的科学值；现场验证后须完成独立目标profile及原生结果验证，再打开该工程分支。这个缺口属于本包，不另开准备阶段。

本地证据见[修复索引](../../discovery/t01-phase1-real/deployment-hardening-20260910/fix-r01/index.json)与[结果摘要](../../discovery/t01-phase1-real/deployment-hardening-20260910/fix-r01/summary.json)。全仓1730通过/1跳过；该进程在最后一次Job终态守卫加强前已加载代码，最后变更由48项最终专项覆盖。中间专项47通过/1失败为旧测试仅提供成功计数所致，补齐Job完成条件后48通过；失败日志保留。Linux真实停止、原候选只读和现行文档检查通过，集群未执行。

启用接口仅供可信Linux操作者：环境变量`T01_KUBERNETES_CONFIG_FILE`指向绝对配置路径；不设置时维持原Linux缺launcher的失败边界。JSON必须包含server（明确HTTPS API origin）、token_file、ca_file（绝对凭据/CA路径）、namespace、runtime_claim、runtime_volume_root（共享卷在控制面上的绝对挂载根）、control_image（registry digest）、tools。每个tools条目是已支持工具名到image、asset_claim、gpu_resource_key的映射，CPU工具gpu_resource_key为null。配置由后台读取并固定hash，不接受工作流请求覆盖；TLS校验启用，HTTP重定向及环境代理禁用，凭据不写入产物。

控制面须能读到固定原始工具资产；当前worker.verify_assets仍核验原登记路径，未挂载时明确ASSET_MISSING。资产PVC的package、models或database子目录需与模板匹配；各工具目录/数据库、部署镜像digest和真实集群访问仍是现场输入，不能拿占位模板直接运行。NetworkPolicy由现场部署流程先应用，launcher只核验、不暗中改网络策略。

参考行为：[Kubernetes NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/)与[Job期限](https://kubernetes.io/docs/concepts/workloads/controllers/job/)。策略效果、真实取消/恢复清理、共享存储和目标输出校验需分别保留现场证据。AF3/ESMFold2部署仍在上述缺陷及执行闭环之后；科学规则签收、依赖安全审计、Agent C和正式发布均未被本轮测试替代。

### 全项目部署就绪复核（2026-09-12）

依据用户本次“完整检查整个项目，包括权威专家文档，并给出部署测试漏洞与解决方案”的要求，复核当前 N01–N18、服务/流程/部署代码、专家 v10.5 原件、现行开放项及已归档交付证据；根目录“工具部署”按项目约定排除。本次没有连接集群、重新执行科学模型、修改实现或签收科学结果。原件和冻结包只读。实际进度摘要见 [STATUS](STATUS.md)，科学问题单点归并在 [OPEN_ITEMS](OPEN_ITEMS.md)。

**结论：已有工具建设足以继续当前部署实施包，但尚不能把现有离线候选视为可直接执行真实工具全链的部署版本。** 控制面隔离部署/认证/存储冒烟可以在现场权限和配置落实后进行；真实工具到报告的部署验收还需关闭下列工程缺口；完整一期科学验收另需模型、数据、科学规则与正式交付闭合。不能因科学未签收暂停无关工程，也不能用 Job 成功、旧包完整性或本地测试通过替代目标执行证据。

#### 本次复核证据与限制

| 检查 | 本次结果及解释 |
|---|---|
| 当前根全量测试 | **1730 通过、1 失败、1 跳过**，353.04 秒；失败为 `tests/test_docs.py::test_progressive_documentation_layout_and_links`，180 条问题均来自 09-10 修复证据中的四份封存文档快照。不能继续表述为当前全仓全绿。[完整日志](../../discovery/t01-phase1-real/deployment-review-20260912/root-tests.txt) |
| 专家原件 | 21 份文件逐一匹配 09-02 修订清单 SHA-256；CamSol 参数 sidecar 一致；Schema 中四个 JSON Schema 块通过语法检查。只证明完整性/语法，不证明科学规则一致或参考结果正确。[探针结果](../../discovery/t01-phase1-real/deployment-review-20260912/probes.json) |
| 当前一期 Mock 冻结 | 457 份冻结资产只读验证 PASS；不能用 Mock 证明真实计算。[日志](../../discovery/t01-phase1-real/deployment-review-20260912/mock-freeze.txt) |
| 原 Linux 离线候选 | 40 份索引文件及 ZIP 校验 PASS；旧源码索引中已有 12 个路径与当前工作树不同，另有后加模块不在旧索引内。完整性通过不等于包含最新修复。[日志](../../discovery/t01-phase1-real/deployment-review-20260912/candidate-verify.txt) |
| 当前 Dify 生成一致性 | `build_real_service_dify.py --check` 通过；没有重跑 Dify 或目标集群，不代表完整 18 节点已接通。[日志](../../discovery/t01-phase1-real/deployment-review-20260912/dify-check.txt) |
| 工程/规则复现 | 只读源码核验、模拟 API 对象、最小候选契约夹具和有限数学枚举，均明确不算集群或科研实跑。[探针源码](../../discovery/t01-phase1-real/deployment-review-20260912/review_probes.py) |
| 历史分区 | 本轮未改旧完整 Mock 或 S07，未重跑其独立测试；上述 457 份属于当前一期冻结 Mock，不混报为旧分区回归 |

#### 工程缺口、解决方案与关闭证据

下表 P1 表示阻断其对应的目标执行/交付动作，P2 表示回归或支持域缺口；不等同于漏洞利用评级。新发现与已登记未完成项分别注明，主责为后端/部署实施，现场授权由用户与集群管理员协作。

| 项目 | 核验事实与影响 | 解决方案与关闭证据 |
|---|---|---|
| DR-01 / P1：Kubernetes 结果闭环未完成（既有缺口再确认） | [execution.py](../../src/t01_phase1_real/deployment/execution.py) 将 `succeeded` 明确转换为 `PROFILE_NOT_APPROVED`，只回收诊断；测试也锁定此行为。即使工具 Pod 成功，当前路径仍不提供正常工程结果 | 建立独立目标 execution/result profile：固定镜像、来源、参数、原生产物及执行身份；复用数值解析，替换适用的目标运行证据验证。先以一个真实 CPU 工具完成提交→执行→解析→报告及取消/恢复。不得伪造旧 Docker loopback/CPU 字段，不将工程成功直接升级科学可消费 |
| DR-02 / P1：NetworkPolicy 回读比较错误（新复现） | [launcher.py](../../src/t01_phase1_real/deployment/launcher.py) 对 `spec` 做字典全等；去掉空 `ingress/egress` 的等价拒绝全部流量策略会被拒绝为 `NETWORK_ISOLATION_UNVERIFIED`。Kubernetes API 的空列表带 `omitempty`，实际回读可能没有这些字段 | 只对等价缺省做规范化：缺省/空规则、集合型 policyTypes；继续严格校验 selector 和禁止新增允许规则。增加真实 API 序列化/defaulting 契约用例。另核查所有选中 Pod 的策略与 CNI，实际探测 DNS/TCP 出站失败；单份策略存在不证明禁网，允许策略具有累加语义。[官方 API 定义](https://raw.githubusercontent.com/kubernetes/api/master/networking/v1/types.go)、[策略语义](https://kubernetes.io/docs/concepts/services-networking/network-policies/) |
| DR-03 / P1：控制面到 launcher/资产的配置未装配（既有缺口具体化） | [清单生成器](../../src/t01_phase1_real/deployment/kubernetes.py) 只提供认证环境变量，无 `T01_KUBERNETES_CONFIG_FILE`、launcher JSON 或工具资产挂载；`worker.verify_assets()` 仍查原登记路径。仅 apply 当前清单会停在缺 launcher/资产边界 | 完成现场渲染器与启动预检：配置文件/环境变量、服务账号 token/CA 路径、runtime/asset PVC、目标资产路径登记、数据库根、真实镜像 digest 与拉取凭据引用。对现有 `him-ws` 不直接创建/重标 Namespace；管理员补专用 SA 的最小授权。先证明镜像离线可拉、资产 hash、挂载及 SA 实际权限，再调度工具 |
| DR-04 / P1：结构 worker 缺少必读目录（新发现） | [structure/worker.py](../../src/t01_phase1_real/development/structure/worker.py) 读取 `/worker/sources.json`，当前结构 Job 有 `/code`、`/profile.json` 等挂载，却没有 `/worker`；复制到 `/t01/launcher` 不能满足该绝对路径 | 补只读 worker 目录挂载，或通过受控参数统一读取来源清单路径；逐项审计十类 Job 的命令、输入、工作目录和资产挂载。用实际目标镜像完成本地结构→FreeSASA 的 CPU 实跑及来源清单验证 |
| DR-05 / P1：A3D 未迁移到 Linux/Kubernetes（新发现） | [developability/service.py](../../src/t01_phase1_real/development/developability/service.py) 的 `run_a3d` 仍调用 Docker backend；[docker.py](../../src/t01_phase1_real/development/docker.py) 明确只允许 Windows。十类 Job 不含 A3D，因此修好通用 Job 桥也不能自动修好 N10 | 为固定 A3D/Python 2.7 环境建立独立目标 worker/Job，接入相同来源校验、输出收集和生命周期；不开放 Docker socket。以真实结构验证原生输出、失败/取消/恢复，再单独处理 OI-032 的科学空间语义 |
| DR-06 / P1：新生成器与候选校验器不兼容（新复现） | 生成器现在输出 10 类控制面资源（新增 NetworkPolicy），[verify_target_linux_candidate.py](../../scripts/verify_target_linux_candidate.py) 仍精确接受旧 9 类；最小夹具稳定复现 `control-plane resource set differs`。旧离线 ZIP 通过是因为它仍是旧格式 | 为候选清单加版本化校验：旧封存版本维持只读旧规则，新版本强制包含所需策略；增加生成→校验契约回归。工程修复后在新路径重建镜像/离线包、索引/SBOM/操作说明，验证安装、重启、升级、回滚及备份恢复，不覆盖旧候选 |
| DR-07 / P2：封存文档快照被当作现行导航（新复现） | [check_docs.py](../../scripts/check_docs.py) 的已校验快照登记未包含 `deployment-hardening-20260910/fix-r01/documentation-snapshot`；180 条断链使全仓回归失败 | 将该批快照纳入已有 index 的大小/hash 验证机制，并测试缺索引、篡改、异常条目；不能笼统忽略 discovery，也不能修写原快照的相对链接。修复后文档检查与受影响测试通过，再形成最终全仓结果 |
| DR-08 / P2：输入/期限仍是小规模开发域（新核验） | [FoldX policy](../../src/t01_phase1_real/development/foldx/policy.py) 最多 900 秒，而 C35 §1 的 500 aa 扫描耗时示例约 8 小时；通用 Job 最多 7200 秒。流程接受至 2000 aa，但 BepiPred、FoldX 等子工具上限不同；N09 工程注释包上限 16 MiB/500 条，不等于能直接消费服务器完整 UniProt 库 | 提交前给出逐工具能力预检；按实际批准输入域配置工具期限/工作流预算，必要时可追溯分块并验证完整覆盖，区分排队与执行超时。目标数据做批准的离线转换/索引，保留原库身份。先用短样本冒烟，再做所承诺最大输入与故障恢复；不得静默截短或宣称 2000 aa 全链均支持 |
| DR-09 / P1：自动设计与正式交付仍未接入（既有缺口再确认） | [workflow/service.py](../../src/t01_phase1_real/development/workflow/service.py) 对 design/rescore/protection/stability 直接返回 `SCIENTIFIC_GATE_CLOSED`；无结构返回 `PREDICTION_SERVICE_NOT_DEPLOYED`。真实报告已有 24 条均淘汰；阳性排序夹具不是真实入选候选 | 在有依据的后端实现 Gate/WT、真实新设计、N12 有限重算、N13/14 验证、N15 排序、N16 条件/N17 汇合与 N18 交付状态机，分支按签收资格开放。验收成功候选、WT、全淘汰、缺输入、条件跳过与重算耗尽；不以改布尔开关或复活原24条替代实现 |

#### N01–N18 与专家依据核对

专家依据均指 2026-09-02 v10.5 修订包，通过[权威索引](../../工作流设计/01-业务依据/README.md)定位。已有公式/阈值不再重复索要；需要算法确认的具体问题及来源保留在既有 OI。以下是部署/科学验收差距，不撤销原本地工程成果。

| 节点/分支 | 已有基础 | 完整验收剩余项与责任 |
|---|---|---|
| N01–N02 | 本地结构、映射、FreeSASA、DeepTMHMM 工程链 | AF3/ESMFold2 的候选模型身份已有交接依据，但目标资产/worker/实跑未完成；部署实施落实权重、数据库、GPU/存储和禁网证据，后端接入预测及置信度归一。算法关闭 R-58 映射/结构消费 OI-015/023/027 与 R-04 路由边界 |
| N03 | 本地 BLAST 引擎及 N03→N06 事实回连 | 数据接口人核实服务器目标库用途、来源/版本、索引/hash及真实检索；OI-028。普通同源命中不变为 E3/E4，不恢复 IEDB |
| N04–N05 | BepiPred 原生双列、NetMHC 双通道与明确 allele 执行 | OI-026：BepiPred 消费分数列、Top20% 与桥接/过滤顺序及适用模型；OI-003：默认宿主面板与回退。已明确 0.1512/min6/gap2 和显式 allele 路径无需重新裁决 |
| N06–N07 | 地图工程输入/身份校验、独立 sequon 扫描 | OI-007/028：按现有默认权重推导无 IEDB 条件下热点阈值不可达，须确认零热点的正式消费；OI-029：非20aa热点到20aa窗口的换算。详见 OPEN_ITEMS 的上界推导；不能把未算/空区间记 PASS |
| N08–N09 | 同源比对/保守性与工程注释/结构分量 | OI-030：目标/补充库与选择、未知分型、去冗余/桥接/缺值；OI-006/031：core_map、packing/network、注释迁移与坐标接受域。服务器已有库不等于当前格式已适配 |
| N10 | 部分可开发性维度、A3D 原生工程事实、PROPKA GUI 公式对标 | OI-025：CamSol 表/标定资产尚空，I_pat 长段计数措辞有歧义；整体 H/P 对换不改变对称交替模式，不能把纯命名冲突无限扩大。OI-032：A3D 空间簇/球邻域与分档；OI-033：PROPKA 平坦曲线权重。已有非平坦曲线数值对标保留，overall 不补造 |
| 设计 Gate/WT、N11 | Gate/WT 草稿，ProteinMPNN、权限与原生掩码工程链 | OI-021：唯一 Gate 判据；OI-001/002：策略、冲突与自动权限；依赖明确的 N06/N09/N10 科学字段。后端按签收规则完成真实自动设计和 WT 分支 |
| N12 | ESM-IF1 原生分数、WT 基线、六维负担、10→15→20 的有限 R-35 复评 | OI-015/022：结构复核 R-04 路由、前20池及缺值/并列与重算关系。C18 的似然名称/解释与固定官方原生实现差异已登记。任务失败重试不等于科学重新设计 |
| N13 | 来源配对、保护分量与明确缺项的报告 | L1/L2/L3/L4 数值阈值已有；OI-015/022/028 剩余为 RMSD 叠合/点集/缺失策略、shape 方法、预测区间配对及空保护结论；不能将距离变化统计冒充 RMSD |
| N14–N15 | FoldX 五次 BuildModel、ThermoMPNN、逐变体回连和全淘汰报告 | OI-011/022：跨引擎消费、完整 Hard/Pareto/目标权重/多样性与缺值/并列。保留原始有符号 ΔΔG 和 R-40 边界；需新的真实合格输入检验阳性链，夹具不授予科学资格 |
| N16–N18 | E.coli/W3110 密码子工程、WT 扫描回连、本地报告/ZIP | OI-004：批准宿主/CAI与参数；OI-010/013/014：Candidate/WT/Failure 正式字段、SC-10/交付门控与 Agent C 认证/幂等/回执。条件 N16 与独立 N17 汇合需要真实完整链验证，本地 ZIP 不能代替正式交接 |

#### 当前包内的解决顺序

1. **先关闭目标执行工程缺陷。** DR-02/03/04/05/06/07 可直接实现；DR-01 用一个 CPU 工具建立合格目标结果 profile 后逐工具扩展。同步补现场仓库地址、专用 SA 权限、CNI、PVC/GPU 与资产清单。产出新版本候选，旧包保留。
2. **执行分层部署测试。** 在项目独立资源内完成控制面认证/权限/持久化 → CPU 工具原生结果 → GPU 工具及 AF3/ESMFold2 → 上述适用链。各层检验禁网、超时、取消、Pod/服务重启、恢复、幂等、资产/产物完整性；DR-08 用批准的输入规模做容量验收。目标成功前保持 NOT_DEPLOYED，不把参数模板当实测配额。
3. **并行闭合定点科学问题，最后验收完整一期。** 算法针对 OPEN_ITEMS 的具体冲突提供规则/参考值与签收；后端据此完成 DR-09 和科学消费链。最终用可追溯真实样本覆盖候选成功、WT、全淘汰、重算、N16条件/N17汇合和 N18/Agent C。适用 G0–G6 齐备后才讨论发布与科学可消费资格。

### 部署修复实施回填（2026-09-12）

本批在用户“开始执行修复计划／继续完成任务”的授权下实施，仍归属PH1-REAL-TARGET-DEPLOY。代码及测试已落地，新的本地候选为[t01-phase1-real-target-v0.2](../../deploy/t01-phase1-real-target-v0.2/OPERATIONS.md)，最终镜像版本0.2.0-rc3；旧0.1.0候选、专家原件与既有冻结证据只读。目标现场尚未执行，不能将本批记为整个修复计划、完整一期或生产部署完成。

| 复核项 | 本批实际修复与验证 | 尚未关闭的具体动作 |
|---|---|---|
| DR-02 | NetworkPolicy接受API省略空ingress/egress与policyTypes换序；仍拒绝允许规则、selector变化、缺少隔离方向及未知字段；增加回读契约回归 | 现场核验全部有效策略与实际CNI禁网效果 |
| DR-03 | 新增site渲染器，绑定launcher JSON、服务账号token/CA、原路径资产PVC、数据库目录和imagePullSecrets；launcher使用subPath文件挂载以兼容拒绝符号链接的读取器。应用与管理员RBAC分开，不重建/重标him-ws | 用户2026-09-12最新确认Harbor仓库与专用SA尚未建立；需实际仓库地址、最小授权及资产/PVC/GPU配置。已附[管理员审阅清单](../../deploy/t01-phase1-real-target-v0.2/kubernetes/administrator-bootstrap-him-ws.yaml)，未应用 |
| DR-04 | 补结构worker的/worker来源目录只读挂载；固定FreeSASA镜像在禁网/非root/只读根容器中真实完成输入检查、映射、FreeSASA与RSA，15份原生产物hash复核通过 | 同一镜像在目标Job/PVC上复现；本地Docker不冒充Kubernetes实跑 |
| DR-05 | 新增固定Python2.7 A3D worker与独立Job；N10按目标配置选择Kubernetes；将Job意图/收据/输入身份写入原execution，失联保持非终态，恢复只观察/清理旧Job。固定原镜像实际执行成功，6份必需原生产物齐备；丢提交响应、异主Job与恢复不重POST有回归 | 目标节点实跑与CNI/取消恢复证据；OI-032科学空间语义仍未签收 |
| DR-06 | 新候选索引0.2.0要求含NetworkPolicy的10类控制面资源及11类Job；旧0.1.0仍按原9类/10Job验证。重复索引/ZIP成员拒绝。新rc3已离线构建、导出并实际load | 注册表推送与平台digest现场绑定、完整升级/回滚/持久卷备份恢复及目标验收仍需完成 |
| DR-07 | 四份09-10封存文档快照按原index逐项大小/hash免于现行导航解析；缺文件/索引、篡改、重复项仍失败，邻近普通文档仍检查。原180条误报消除 | 29条原有legacy历史引用继续独立披露，不改原件消除历史记录 |
| DR-01（部分） | 结构结果新增独立目标校验，复用原生输入/产物/版本/RSA逻辑，并验证实际Job/Pod、零重启、镜像digest、节点、策略UID及固定现场收据；保留真实eth0/CPU观察，不伪装Docker。A3D同样要求目标收据。未登记现场证据继续关闭 | 结构/A3D目标实跑与收据未取得；其余9类通用工具结果仍是PROFILE_NOT_APPROVED诊断分支，需逐项接入。正常工程结果不授予科学资格 |
| DR-08（部分） | 流程提交前检查已启用BepiPred/DeepTMHMM长度上限，不静默截短；BLAST/同源库控制面与Job要求同一claim并使用database/id，提交前核验登记库 | FoldX长任务预算、其他输入域、大库转换和最大规模容量/恢复仍未完成，不扩大现有科学支持声明 |
| DR-09 | 保留既有Gate/WT、原24条淘汰、科学关闭和正式交付边界，没有以开关代替实现 | 完整自动设计/重算/保护/排序/汇合与Agent C仍未接通；依赖具体科学字段的分支按OPEN_ITEMS签收后实现，无关工程可继续 |

真实容器验证另发现并修复两项：CLI以位置参数构造ServiceConfig导致启动延迟被误传为max_pending_tasks，现改为字段名并暴露队列容量CLI；Linux的TIME_WAIT导致同端口立即重启失败，现仅POSIX启用SO_REUSEADDR，不启用SO_REUSEPORT，Windows策略不变。最终rc3容器实测认证、上传/越界拒绝、提交、取消、同端口重启、恢复、幂等/越权、重试和报告hash通过；无资产分支准确失败。验证使用临时tmpfs及进程重启，没有将其声称为持久PVC备份恢复或真实集群验证。

本地证据位于[本批目录](../../discovery/t01-phase1-real/deployment-fixes-20260912/fix-r01)，其中[控制面实跑](../../discovery/t01-phase1-real/deployment-fixes-20260912/fix-r01/control-container-r04.txt)、[结构/A3D与原件复核](../../discovery/t01-phase1-real/deployment-fixes-20260912/fix-r01/native-and-preservation-verification.json)、[专项135通过](../../discovery/t01-phase1-real/deployment-fixes-20260912/fix-r01/final-specialist-tests.txt)均保留。**最终源码全仓回归1782通过/1跳过，267.56秒，进程退出0**，见[root-tests-final-r02.txt](../../discovery/t01-phase1-real/deployment-fixes-20260912/fix-r01/root-tests-final-r02.txt)。中间全仓早于最后Linux端口修复加载；首次全仓和首次最终重跑没有完整退出回执，保留日志，不计通过。旧离线候选40份索引/ZIP、457份当前一期Mock、21份专家原件与56份上批封存证据复核通过；旧完整Mock/S07未改且未重跑。

[新离线包](../../deploy/t01-phase1-real-target-v0.2-offline.zip)为116882010字节，SHA-256为`98ebd6e59d52dcbf16a652a24a689b0253f43db7088f4f30c14257dd1d22ca18`。包内50份索引文件、11类Job通过校验，并使用包内源码完成独立离线校验，不依赖开发仓库导入。rc3构建源码与当前实现逐字节一致；最终批次状态、失败记录与完整性清单见[证据索引](../../discovery/t01-phase1-real/deployment-fixes-20260912/fix-r01/index.json)。这些验证放行本地候选进入分层目标测试，不放行科学消费或生产发布。

构建失败记录保留：首次临时目录ACL拒绝读取、第二次BuildKit通信失败，正常继承权限的新副本构建成功；rc1/rc2控制面验证暴露上述启动/重启问题，rc3通过。自动审批因可能外传依赖元数据拒绝Scout，已改用network=none容器内dpkg-query/importlib.metadata生成125个安装包的SPDX。该清单不是漏洞库审计，也不与旧Scout187条结果直接比较；安全审计及适用G0–G6仍单独验收。

下一动作限定为：按用户授权将已在本地禁网构建验证的根目录 Dockerfile、有界构建输入及 Jenkinsfile 提交并推送至 Codeup `test` 分支，核对公共 Jenkins 首次构建的 `qcyz/antigen-design` 推送与实际 platform digest；该流水线只更新已存在 Deployment，因此管理员仍须一次性建立 `t01-control-plane` 专用 SA/最小 RBAC，用户再以实际 digest、`harbor` 拉取 Secret 和独立 PVC/资产渲染初始化资源。后端继续其余目标结果profile与容量支持，按首个CPU目标实跑核验配置、来源和结果，再扩展GPU/AF3/ESMFold2。科学问题按既有OI定点闭合，不恢复IEDB、不改专家阈值、不自动交接。

## 4. 每个真实波次的门禁


G0–G6 是证据检查分类。开发、科学消费、目标发布分别判断，不要求完整科学签收和目标复现都先于编写适配器。

| 决策点 | 必须具备 | 尚未具备时如何推进 |
|---|---|---|
| 开始工具开发/内部联调 | 本地原工具事实、固定候选资产、必要工程接口、已知输入/失败守卫、开发验收清单 | 不依赖争议规则的代码可实施；待定分支关闭，模型未实测部分只作准备 |
| 允许科学消费 | 适用 G1 科学规则/输入域、独立参考、指标/容差、具名签收及相关实现验证 | 结果仅供开发复核，usable_for_pipeline=false，禁止自动交接 |
| 测试服接入与流程联调 | 真实资产、必要运行配置、输入输出/来源校验及受影响链测试；按当前测试服完成标准汇合 HiMat 与报告 | 批量推进可执行分支，缺项明确记录；无需先完成生产发布全部检查 |
| 正式目标发布 | 目标环境实际复现、离线安装与资产、全部适用 G0–G6、受影响链验收 | 测试服部署与局部流程成果单独记录，生产保持 NOT_DEPLOYED |

各检查分类保留以下证据，并在对应使用时点完成：

| 分类 | 保留的检查内容与时点 |
|---|---|
| G0 事实摸底 | 原工具版本、输入输出、错误、资源、许可及禁网实测；本地与目标证据分别记录，目标复现在目标发布前完成 |
| G1 契约就绪 | 必要工程接口在开发前明确；完整科学规则、支持域、独立参考及验收责任在科学消费前闭合 |
| G2 后端实现 | 适配器与确定性计算由后端实现，开发过程完成单测与集成验证；科学未批准不阻止开发代码形成 |
| G3 离线打包 | 镜像/权重/数据、hash、安装预检、smoke、金标准与回滚；逐包验证，完整发布前汇合 |
| G4 工作流接入 | 独立真实 DSL 生成、绑定、回读及固定状态路由；可先做局部调试，完整波次另验收 |
| G5 波次验收 | 工具/契约/Dify、断网、失败、取消/恢复/幂等及受影响真实链；科学结论需对应签收 |
| G6 波次冻结 | 全部必需能力齐备，固定版本、证据、手册与 manifest，确认无 Mock/smoke 混用 |

纯计算节点按原件完成规则、契约、实现和参考验证；科学规则不由 LLM 或 Dify 执行。
补证只针对未满足的完成标准或实际新发现；记录影响、关闭证据、主责及阻断哪一决策点，不无限扩展前置任务。

## 5. 一期最终验收

N01–N18、设计 Gate/WT、N12 重算、N16 条件及 N16/N17 汇合均须有真实执行和唯一机器语义；N03 验收本地 BLAST 及目标库，不依赖 IEDB 检索服务，并验证相应证据缺省与消费边界。
所有保留能力达到适用 G6；全链失败、取消、恢复、幂等、重复提交和交付回归通过。
结果含版本、参数、输入 hash、原始产物、来源和 run_id；使用批准本地数据包，禁公网查询/预测回退。
AF3/ESMFold2 仍必交付，完整范围与削减规则见 [范围基线](PHASE1_SCOPE_REBASELINE.md)。
普通开发顺序调整不改变范围；N03 只保留 BLAST 依据最新用户澄清。范围调整不授予科学资格，也不把局部验收记作一期完成。
