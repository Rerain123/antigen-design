# T-01 系统架构

> 更新：2026-09-10。实际进度只见 [STATUS](STATUS.md)；本页记录组件、约束和接入方向。

## 1. 当前与历史资产隔离

| 路径 | 职责 |
|---|---|
| src/t01_phase1_mock | 冻结的一期 Mock 引擎与 Dify 生成/绑定/回归 |
| src/t01_phase1_real | 真实阶段任务运行层：SQLite、幂等、进程生命周期和文件发布 |
| src/t01_structure_mapping | 结构解析、候选映射、输入事实、FreeSASA 消费者 |
| src/t01_phase1_real/development | 固定本机开发 Worker 登记、DeepTMHMM/本地结构链/BepiPred/NetMHC/BLAST/ThermoMPNN/FoldX 接入、N06–N12 工程计算、WT 草稿及停止与恢复 |
| src/t01_phase1_real/service_api | 带 Bearer 认证和调用者隔离的 REST/Streamable HTTP MCP 服务；复用 development Runtime，不重建科学任务状态 |
| src/t01_phase1_real/process_control / linux_files / linux_service | POSIX 进程组、PID 出生标记、文件锁/原子发布与 Linux 启动选择；冻结 Windows W1 四份源码保持原字节 |
| src/t01_phase1_real/deployment / deploy/t01-phase1-real-target-v0.1 | 只生成不提交的 Kubernetes 资源/Job 与 Linux x86_64 离线候选；目标配置和 Harbor digest 由现场另行绑定 |
| scripts | 当前统一 CLI t01_runtime.py、验收入口，以及保留原身份的历史开发探针 |
| 工作流设计/02-数据契约 | 独立版本化请求/结果、任务/Artifact 与科学草案 |
| dify / discovery / var | 编排资产 / 原始执行证据 / 运行时状态，各自隔离 |
| legacy | 旧完整 Mock 与 S07，仅作历史参考，不导入当前实现 |

## 2. 新一期目标拓扑

```text
LLM 收集输入 → Dify 编排 → MCP/后端提交、查询、取消
                             ↓
                        受控工具 Worker
                             ↓
                原始产物 → 后端校验/规则 → 结果与证据
```

业务按 [现行范围](PHASE1_SCOPE_REBASELINE.md)保留 N01–N18 及 N02 → N03 → N04 路由；N03/S-03 仅调用本地 BLAST，移除 IEDB 检索。设计 Gate/WT、N12 重算、N16 条件以及 N16/N17 汇入 N18 保留。
本地结构或 AF3/ESMFold2 支撑 N01，数据库能力使用批准的本地数据包；运行时不回退公网。
N03 BLAST 需登记本地目标库与索引，地图和最终交付回连其原始比对及来源；普通命中不直接作为文献/E3/E4 表位证据。无 IEDB 时的来源缺省、空热点/验证区间及交付披露按范围基线与适用开放项处理。冻结 18 节点 Mock 保留原 IEDB 行为身份，不能直接代表修订后的真实工具能力或消费资格。

## 3. 新旧命名与写入边界

真实 Python 根为 t01_phase1_real，当前本机服务 provider 为`t01-phase1-real-service-v01`；真实 DSL 使用独立生成源和独立应用身份。
Mock 唯一生成源为 [generator.py](../../src/t01_phase1_mock/dify/generator.py)，不得原地改成生产调用。
真实 run/job/attempt/artifact 使用 t01p1r 身份，Dify run ID 只作关联；输入输出绑定受控 ArtifactRef、字节和 hash。
原科学包、专家原件、Mock 冻结文件和历史执行批次只读；新运行使用新目录，不用旧 hash 覆盖变更。

## 4. 组件职责

| 组件 | 责任 |
|---|---|
| LLM / Agent | 收集、调用、等待、解释事实；不做科学计算、门控、Hard Filter 或 Pareto |
| Dify | 根据后端固定状态路由，汇合分支；不计算科学值或猜失败处置 |
| MCP / 后端 | 校验、任务状态、幂等、错误/复核、数据处理、规则计算、可消费资格和追踪 |
| 科学 Worker | 固定版本/参数/资源下禁网执行，保留输入、原始输出、退出与停止事实 |

`development.variant_report` 以 `t01.real.variant_report / N15` 增量登记，复用本地任务、取消/超时、恢复/重试与发布守卫。后端递归复核设计审计的 N11/N12/结构来源，并按精确 WT、结构 ArtifactRef、样本号、变体 ID 和序列 diff 回连 FoldX BuildModel；保留修复与五次原始输出。`variant-report` 提交/查询整批，`variant-record` 从已核验报告查询单条。来源失效、工程淘汰、缺失科学输入和正式资格分别表达；未执行 N13 不应用无结构表位中性规则。SOP step20 数值验证只接受独立契约夹具，不进入真实候选输入或 Agent C。接口单点见 [W6 报告接口](phase1/PHASE1_REAL_W6_PLAN.md#n14n15-逐变体报告本机接口)。

`development.epitope_protection` 增量登记 `t01.real.epitope_protection / N13`，消费尚未包含 N13 的基准报告和 WT/变体两侧精确结构、N06、N09 来源；按各自序列核验，原设计WT结构必须精确匹配。可信本地后端计算四层已有依据的工程观察并保留未决方法，结果不签收科学保护。新 `variant-report` 可通过 `n13_source` 回连同一基准变体集合，形成“原报告→N13→新报告”的单向链，禁止循环；原R-35及历史报告不回写。字段和范围见 [N13 本机接口](phase1/PHASE1_REAL_W6_PLAN.md#n13-表位保护本机接口)。

## 5. Mock 与生产边界

按 [现行计划](PHASE1_DELIVERY_PLAN.md#4-每个真实波次的门禁)分别控制开发接入、科学消费与目标发布。
工具运行成功不自动授予科学资格。未签收的开发结果保留原始事实，usable_for_pipeline=false，禁止自动交接。
局部开发 Dify 可连接实际已实现模块，使用独立身份并披露未完成部分；不以 synthetic 输出补成真实全链。
完整科学规则、参考与签收控制科研消费；目标复现和 G0–G6 控制发布及冻结生产依赖。

## 真实阶段运行边界

目标Linux可通过显式`T01_KUBERNETES_CONFIG_FILE`启用`deployment.execution`，已准备的科学attempt由HTTPS Job客户端创建/观察/停止，Job UID及spec绑定存入原executions，不新增另一套任务数据库。删除等待所属Pod停止，失联不重建；模板以NetworkPolicy、Job期限及控制面同节点亲和性约束科学Worker。当前仍是目标原始观察/诊断路径，未完成目标结果profile验证，不能继承Docker的已验收资格。具体修复和剩余现场条件单点见[部署前修复](PHASE1_DELIVERY_PLAN.md#部署前缺陷修复与-kubernetes-执行闭环)。

`development.workflow`以`t01.real.local_workflow / N18`登记本地父任务，使用既有jobs/events/executions和Artifact注册表，自动建立依赖与子任务来源。父关联和子任务创建同事务；活动控制器以PID/出生时间防重复派发，取消只停止所属新子任务，历史复用保持只读。恢复核对输入/配置/profile和已完成来源后继续；模型子任务沿用现有容器监督。CLI和`service_api`均调用这一个控制器。服务以固定启动配置创建按principal隔离的Runtime scope，独立`service.sqlite3`只保存ACL、服务幂等及上传登记；科学任务状态仍在原`state.sqlite3`。同一端口上的REST和`/mcp`共同实施Bearer scope、任务归属、受控上传、提交/查询/停止/恢复/重试和验证报告下载。后台调度与客户端连接解耦，启动恢复活动任务，并为子监督器登记保留有界栅栏。独立Dify图只提交/等待/按后端状态路由/下载，不计算科学规则。规则、接口和实测见[服务实施回填](PHASE1_DELIVERY_PLAN.md#真实服务接口与-dify-实施回填)。

`development.codon` 增量登记 `t01.real.optimize_codons / N16`，只接收明确独立工程序列、表达宿主及表 profile。固定本地表、依赖和规则 hash；可信本地 DNA Chisel 进程在 Windows 由原 Job Object 管理，在 Linux 由所属进程组、PID 出生标记及容器 pids/memory 边界管理，并禁止 Python 网络/子进程接口；取消/超时停止所属树，失联恢复不重跑。后端独立核验翻译、GC 与正反向位点，区分缺宿主跳过、优化完成、原生求解失败回退和执行失败。复用原任务、ArtifactRef 与发布守卫，不消费/恢复原排除变体；完整字段和限制见 [W7 N16 接口](phase1/PHASE1_REAL_W7_PLAN.md#n16-本机接口与实施回填)。

`development.wt_reference / N17` 复核真实WT扫描的原始请求、精确结构、原生输出和排除范围，不启动新扫描、不平均跨引擎分数。`development.local_delivery / N18` 递归校验WT草稿、含N13的变体报告和N17来源，核对DNA的序列/对象/表达宿主及独立工程用途，产出机器数据、可读报告和固定路径/逐文件hash的本地ZIP；凭据、模型、许可工具不导出。两者复用已有本地计算停止栅栏、恢复/重试及发布追踪；不生成正式CandidateRecord/AgentCHandoff。字段与实测单点见 [W7末端接口](phase1/PHASE1_REAL_W7_PLAN.md#n17-与-n18-本机接口)。

当前 [统一入口](../../scripts/t01_runtime.py)复用同一 SQLite 任务库，登记 engineering_probe、本机 DeepTMHMM、本地结构分析、BepiPred、NetMHC 双引擎、BLAST、ThermoMPNN/FoldX 开发 Worker、N06–N16 已实现开发模块及本地 WT 草稿。
Windows 原运行底座继续使用已验收 Job Object；其 `runtime.py / files.py / winprocess.py / engineering_worker.py` 四份冻结源码未改字节。Linux 镜像由独立入口在导入服务前选择 POSIX 文件与进程模块，并只替换冻结 Runtime 的平台准入语句；任务、SQLite、幂等、ArtifactRef、父子调度和恢复语义仍为同一实现。Linux 子进程先 `setsid` 并暂停，在所属进程组/PID 出生标记持久登记后继续；停止杀死且确认整个所属进程组，RLIMIT_AS 与 Pod/容器 pids 限制共同提供资源边界。需要科学镜像的 Linux 分支不接 Docker socket，当前只生成 digest 固定、最小权限、非 root/只读根文件系统的 Kubernetes Job；未有真实集群观察前不记 Job 执行通过。Windows 本机原包仍由静态 registry 选择固定 Docker 镜像、只读源码/输入挂载与独立容器槽，network=none。
SQLite 保持任务/幂等、attempt/execution/lease、事件与发布记录；停止确认先于终态，恢复不得重新执行同一 attempt。
输入和输出经受控 ArtifactRef 与 hash 验证；监督进程失联后按精确容器归属停止，完整停止收据与原始清单可恢复发布，未知状态保持 reconciling。
开发 profile 绑定新代码、原底座及模型/镜像身份，后端固定 G0_REAL_OUTPUT / g0_probe / 不可消费资格；未开放 pipeline 或生产开关。

旧 w1_runtime.py 和基础源码保留在原版本，用于封存证据复核；development.Runtime 继承相同存储与控制方法，不建立第二套任务库。
runtime.json 中 engineering_only 是沿用的 v1 存储标记；当前 Worker 的准入资格由统一入口登记和任务 profile 强制校验。旧入口继续拒绝科学工具提交。
Python/CLI 与本机认证 HTTP/MCP、真实 Dify DSL 已完成开发接入；Linux x86_64 控制面离线候选及 Kubernetes 清单已在本地容器验证。目标 Linux 集群、科学 Job 实跑、生产密钥/TLS/网络边界、Harbor digest 和 Dify 目标 endpoint 仍需现场实现与验证，生产保持 `NOT_DEPLOYED`。
实际请求/结果、用法与验收条件见 [W1 DeepTMHMM](phase1/PHASE1_REAL_W1_BACKLOG.md#本机调用与接口)和 [本地结构分析链](phase1/PHASE1_REAL_W1_BACKLOG.md#本地结构调用与接口)。

BepiPred 的 [N04 接口](phase1/PHASE1_REAL_W2_PLAN.md)复用现有任务存储。`development.contracts` 对保留的 W1 Schema 做精确增量校验，仅接受新增 `t01.real.bepipred / N04`，未改写旧 Schema、原运行层或历史 manifest；N04 的存储更新保持同一事务和状态规则。原包 CLI/五折模型与 ESM-2 固定 hash，后端分别发布原始双分数列与分类产物，OI-026 项目后处理保持 null/复核。模型执行失败按 A3 halt 语义暴露，禁止作为无表位成功。

NetMHC 的 [N05 开发接入](phase1/PHASE1_REAL_W2_PLAN.md)同样采用精确增量 Schema，只在开发模式接受 `t01.real.netmhc / N05`。请求必须同时给出包内存在的明确 MHC-I/MHC-II allele，宿主只保存为输入事实，不在 OI-003 未闭合时推断默认面板。固定 `amd64/linux` 镜像内含用户提供的 4.2e/4.3k 学术包；容器禁网、根文件系统只读，只挂载 Worker/请求/FASTA 为只读和单独输出目录为可写。两个原生 CLI 分别消费全长 FASTA；解析器绑定包内二进制/版本/allele、运行环境、命令与原始输出 hash，只消费原包 `BindLevel`，校验 1-based `Pos`、`%Rank_EL`、peptide 回连及 MHC-II core/inverted。开发结果保持未签收和不可自动交接。

N03 的 [BLAST 接口](phase1/PHASE1_REAL_W2_PLAN.md#n03-本机调用与接口)以精确增量 Schema 登记 `t01.real.blast / N03`。固定 NCBI BLAST+ 2.17.0 Linux amd64 镜像，运行前后复核数据库 manifest、源 FASTA和全部索引的大小/hash，并将库目录只读挂载。输出绑定单查询 FASTA、数据库快照、原始命令/表格和 HSP 坐标；按 C20 默认 identity/query coverage 阈值另列合格 HSP，但保留全部原始 HSP、不聚合。未命中与未执行/不可用分开，普通相似性不写 IEDB 文献或 E3/E4。当前工程库验证已完成，目标库与 N06 消费仍关闭。

N06 的 [S-19 接口](phase1/PHASE1_REAL_W2_PLAN.md#n06-本机调用与接口)以精确增量 Schema 登记 `t01.real.epitope_map / N06`。准入和执行各自解析上游 ArtifactRef，并校验任务/尝试/登记/hash/结果 binding/同序列，防止请求自报来源和提交后替换。可信本地计算将 NetMHC 原生 hits 映射到残基最小 rank、非退化 `1-minmax` 分数与多 allele SB 呈递区间，同时回连 BepiPred 原始双列；部分、合法空值和上游失败分别表达。OI-007/026 对应权重、B 峰/热点和密度保持关闭，N03 当前实现仍记未执行，工程回连可先实施而无需等待服务器验收，全部结果保持开发未签收。

N07 的 [S-12 接口](phase1/PHASE1_REAL_W3_PLAN.md#w3-糖基化扫描开发接入)以精确增量 Schema 登记 `t01.real.glycosylation / N07`，不改写 W1 机器 Schema。执行 profile 绑定实现、解释器与 Biopython 1.88，规则 profile 另绑定 S-12、glycosylation Schema、R-25/R-26 原件及固定参数。后端执行支持重叠的 N-X-S/T 扫描并发布原始 observation；请求把热点状态建模为未提供、上游不可用或可用，防止把未计算伪装为合法空列表。真实 N06 来源执行与 N06 相同的 ArtifactRef/hash/序列校验，合同夹具另行标识；当前只消费明确 20 aa 窗口，任意跨度换算保持 OI-029，故来源绑定已完成但热点科学全链未完成。

N08 的 [本机接口](phase1/PHASE1_REAL_W3_PLAN.md#n08-本机调用与接口)增量登记 `t01.real.homology / N08`，复用统一 Docker 监督、SQLite 与 ArtifactRef。独立 `homology` 模块用固定 MMseqs2/MAFFT/BLAST 镜像真实执行收集、一次去冗余及一次全局 MSA；宿主验证原工具命令、版本、数据、cluster、MSA 成员与原序列后计算熵/保守性和明确区域规则。只读数据目录由 `homology_database_root`、ID、manifest hash 绑定，N03 的数据库配置独立。组内复用全局 MSA 行子集并保留原列，查询锚点只作坐标映射，不计入统计。工程集和目标库证据分离，未定科学消费分支按 OI-030 关闭；不新增网络回退或旧 S07 依赖。

N09 的 [本机接口](phase1/PHASE1_REAL_W3_PLAN.md#n09-本机调用与接口)以 `t01.real.domains / N09` 增量注册，独立 domains 模块在可信本机计算，不创建网络能力。数据包绑定 `domains_database_root`、库 ID 和 manifest；上游只接受已登记、同序列、同尝试的 DeepTMHMM/结构 ArtifactRef，结构原字节另校验。L1/L2/motif/用户标注及坐标审计、可用几何分量进入同一结果与原始 observation，未定分支明确复核。N09 与 N06/N07 共用本地计算恢复机制，原 W1 Schema 不改写；正式 core_map 及科学消费按 OI-006/031 保持关闭。

N10 的 [本机接口](phase1/PHASE1_REAL_W4_PLAN.md#n10-本机调用与接口)以 `t01.real.developability / N10` 增量注册。可信本机后端固定 Biopython 1.88 执行 S-36a，绑定结构结果计算 S-39，以固定 digest 的 AGGRESCAN3D 0.9.11 容器执行 S-37 结构开发路径，并以固定 PROPKA 3.5.1 子进程执行 S-38 开发路径；没有结构时保留明确空值。PDB 使用已验证原字节，mmCIF 仅从 N02 原子账本作逐原子往返校验的 PDB 投影；A3D 另作目标链 ATOM 投影，以禁网、只读根文件系统和受限资源运行，原生 CSV/统计/结构/FreeSASA/配置/stdout/stderr 均发布并校验。PROPKA 输入、原生 `.pka`、参数及输出哈希也随任务发布，后端从 pKa/model-pKa 按 C24 计算以 pH 7.0 为零点的相对 ΔG，不消费 CLI folding-energy 表为绝对稳定性。S-40 始终展示六维来源、缺失和排除；CamSol、序列聚集资产、A3D 空间语义及 PROPKA 对标未闭合时 overall、完整 N10 与 Gate 均关闭，开发值不可自动交接。

结构 Worker 复用 input_facts/cif_facts/probe/freesasa_consumer 的原实现；新 structure 子包负责源元数据声明、S-09 先行规则、身份回连和 RSA 归一化守卫。原结构与元数据原子登记为受控输入，既有作者编号观察和映射不改写。结果包含各步状态、复核原因与原始产物；科学映射未批准时只保留开发数值，正常科学 RSA 为 null。宿主另核对运行清单、步骤身份和原始面积回连，不用容器退出 0 代替结果有效性。
AF3/ESMFold2 的资产与目标复现独立推进，两引擎降级链仍需共同联调。远端模型接口不得按教程或人工输出冒充实测契约。

W4 的 [本地 WT 草稿接口](phase1/PHASE1_REAL_W4_PLAN.md#gate-与-wt-草稿本机接口)以独立 `t01.real.wt_draft / N18` 增量注册，使用现有 SQLite/ArtifactRef 与本地计算生命周期，不改 W1 Schema。`wt_draft` 模块复核 N01–N10 生产者的任务、尝试、请求/结果 binding、历史 profile 和全部已发布原始产物大小/hash；按真实任务状态区分缺失、失败、未完成与未签收，不接受调用方分数或资格声明。输出独立 LOCAL_WT_ASSESSMENT_DRAFT、来源 receipts、已执行/未执行检查和机器原因；草稿成功不构成 CandidateRecord/AgentCHandoff 完整契约或科学放行。OI-013/014/021 未闭合时固定 Gate 未评估，N11 正式设计、正式 WT 和 Agent C 继续关闭，模型部署不影响本地草稿工程执行。

N11 的 [ProteinMPNN 本机接口](phase1/PHASE1_REAL_W5_PLAN.md#n11-本机调用与接口)增量登记 `t01.real.proteinmpnn / N11`，复用 Docker 监督与停止收据。`source` 模块在准入、执行和发布前复核真实结构 ArtifactRef、请求与原字节；`mapping` 生成坐标无损、编号可逆的骨架投影；`worker` 调用固定官方 parser/featurizer/CLI 和权重，GPU 禁网运行；`result` 后验校验全链样本、固定/受限硬约束及原生分数。工程明确掩码独立于未签收科学权限，WT 草稿不自动触发 N11；科学 Gate、正式设计及 Agent C 交接继续关闭。原 W1 Schema、冻结 Mock 与历史产物不改写。

N12 的 [ESM-IF1 本机接口](phase1/PHASE1_REAL_W5_PLAN.md#n12-本机调用与接口)增量登记 `t01.real.esm_if1 / N12`，复用已有 GPU 监督、停止、恢复及发布校验。独立 `esm_if1/source` 重新验证 N11 原生序列/突变/约束、WT 结构与转换，在准入、执行及发布前检查来源；基线签名绑定结构/映射、链上下文、模型/镜像、参数与执行 profile，首次计算一次、跨调用只接受已验证 ArtifactRef。官方模型只输出同 WT 骨架条件下全目标残基似然；宿主复核原生坐标/逐位 loss/调用计数，`rules` 单独执行有符号相对公式与有限 R-35 复评。工程规则与完整 validation 分字段，burden、结构复核与科学资格保持空/未执行，不自动消费科学 Gate 或交接 Agent C。

S-27 权限与 S-28 mutation_burden 通过 [合并后端接口](phase1/PHASE1_REAL_W5_PLAN.md#权限与负担本机接口)登记 `t01.real.design_audit / N12`，保持两个科学步骤各自职责，单个可查询审计关联八类真实生产者。`source` 核验同 WT、原生 N11/N12 和所有发布文件；`permissions` 合成逐位工程证据/用户覆盖，`geometry` 读取原始结构原子而非骨架投影，`burden` 计算六维并单列工程档值。掩码转换复用 N11 原实现，只导出明确请求草稿，不调度生成；数值与历史 R-35 判定并存，正式权限/burden/validation 始终为空。复用本地计算停止/恢复与发布校验，不建立独立调度系统。

W6 的 [ThermoMPNN 本机接口](phase1/PHASE1_REAL_W6_PLAN.md#稳定性工具本机接口)增量登记 `t01.real.thermompnn / N17`，复用同一 SQLite、ArtifactRef、GPU 容器槽、停止/恢复与发布校验。`source` 复核已登记结构原字节及完整唯一目标链映射，保留作者编号/iCode；`worker` 在只读、禁网、固定 GPU 镜像中原样运行官方 `analysis/custom_inference.py`；`result` 验证 AA20×L 全量 SSM、WT 自身零值、命令/环境/源码及全部输入输出 hash，再对显式工程范围减排除位点做单引擎排序。多蛋白链按 R-39 跳过且不裁链。结果保持原始有符号 ΔΔG，不做跨引擎平均或科学筛选。FoldX 现以固定内容镜像增量登记 `t01.real.foldx / N14`：用户声明的 5.0 学术包原样保留并哈希绑定，`source` 复核结构映射并生成 canonical FoldX token，`worker` 强制 RepairPDB 后以修复结构调用 PositionScan/BuildModel；`result` 对 PositionScan 的原生 WT 重复及 `e/o` 组氨酸代码做显式完整性核验和 AA20 归一，对 BuildModel 的五次 Dif 原值、Average 均值/总体 std 及对应 mutant/WT PDB 交叉核验。镜像内置标签纳入严格容器所有权集合，停止/删除仍要求全标签相等。两引擎均已完成本机真实禁网工程验收，但仍不做跨引擎平均或科学筛选，不把用户授权声明写成机器许可证明。

查字段时进入 [运行契约设计](phase1/PHASE1_REAL_W1_CONTRACT_DESIGN.md)与 [Schema 目录](../../工作流设计/02-数据契约/phase1-real-v0.1/README.md)；
查实现证据时进入 [主题索引](phase1/README.md)，运行条件见 [RUNBOOK](../development/RUNBOOK.md)。
旧设计和评审中的开发停止条件由最新计划覆盖，其机器 Schema 和原执行证据仍按原版本核验。
