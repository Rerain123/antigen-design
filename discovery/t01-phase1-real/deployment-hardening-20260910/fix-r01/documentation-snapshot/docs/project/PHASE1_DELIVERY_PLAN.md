# T-01 一期交付计划

> 现行计划；更新：2026-09-07。依据：[交付方式调整](sources/PHASE1_DELIVERY_SIMPLIFICATION_20260906.json)、[N03 只保留 BLAST 的用户决定](DECISIONS.md)。
> 实际进度与当前任务入口只见 [STATUS](STATUS.md)，交付细节见其链接的阶段计划或任务页。

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
  
  当前按三个交付目标推进，用户操作服务器，助手提供配置并一次指导一个操作；主开发承担尚缺的运行层接入，算法负责人承担科学裁决。

1. **控制面在目标集群可用：** 以已验收离线包为输入，生成独立现场渲染件，确认仓库地址、namespace、存储及拉取凭据，导入镜像并部署单副本服务；验证认证、持久化、重启和下载。现有 oligosmith 只作只读参考，不修改其资源。仓库名称尚未确认时不擅自将建议名作为现场事实。
2. **真实工具在 Kubernetes 执行：** 先选资产已齐的工具完成 Job 提交、查询、取消、超时和恢复到报告的真实链，再扩展数据库工具及其他模型。当前仅生成的 Job 模板不是调度后端完成证据；核对并补齐控制器与 Kubernetes API、产物共享和权限接口。缺库只阻断对应工具。
3. **AF3/ESMFold2 自行部署与回连：** 用户按既有部署说明逐个完成合法资产登记、固定环境、禁网推理及真实结构输出，主开发接入任务层与下游结构链。单 GPU 串行运行；两模型分别验收，不等待同事交包。模型加载成功不能替代完整输入到输出的验收。

本地候选r01的4份索引文件及116,909,558字节离线ZIP经管理复核大小/hash一致；归档源码/测试结论沿候选证据保留。候选目录、ZIP及镜像内549份快照保持原字节；现场配置表中旧“同事参与”措辞仅属封存版本，现行责任以本节为准。修改现场配置后另生成版本及hash，不回写旧清单。

完成标准为目标环境新任务的输入、执行、停止/恢复、产物和Dify回连均有可核验收据。部署状态按实际组件回填，完整一期仍需科学开放项、业务分支和正式交付验收。N10、真实热点、N12重算及Agent C等按原开放项继续跟进，不因部署排期而取消。

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

## 4. 每个真实波次的门禁


G0–G6 是证据检查分类。开发、科学消费、目标发布分别判断，不要求完整科学签收和目标复现都先于编写适配器。

| 决策点 | 必须具备 | 尚未具备时如何推进 |
|---|---|---|
| 开始工具开发/内部联调 | 本地原工具事实、固定候选资产、必要工程接口、已知输入/失败守卫、开发验收清单 | 不依赖争议规则的代码可实施；待定分支关闭，模型未实测部分只作准备 |
| 允许科学消费 | 适用 G1 科学规则/输入域、独立参考、指标/容差、具名签收及相关实现验证 | 结果仅供开发复核，usable_for_pipeline=false，禁止自动交接 |
| 目标部署与发布 | 目标环境实际复现、离线安装与资产、全部适用 G0–G6、受影响链验收 | 局部开发成果单独记录，生产保持 NOT_DEPLOYED |

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
