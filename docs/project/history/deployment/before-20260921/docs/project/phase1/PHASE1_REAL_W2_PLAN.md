# PH1-REAL-W2 阶段计划：本地检索与表位分析

> 更新：2026-09-08。范围、完成标准和工具用法在本页维护；实际进度与当前执行包只见 [STATUS](../STATUS.md)。总体依赖与放行条件见 [一期交付计划](../PHASE1_DELIVERY_PLAN.md)。

## W2 阶段计划表

**阶段目标**：完成 N03–N06 的本地 BLAST、B/T 预测与表位地图，形成可追溯的局部真实链。N03 保留 BLAST、移除 IEDB 检索；以下四包包含各自原包/数据核验、实现、测试与必要补证，实际状态与最新证据只在 [STATUS](../STATUS.md)维护。

| 交付包 | 节点 | 交付内容与完成标准 | 依赖与科学使用条件 |
|---|---|---|---|
| [BepiPred 本地接入](#w2-bepipred-开发接入) | N04 / S-17 | 统一入口真实禁网执行、逐残基原始分数解析/查询与产物回连，生命周期和完整性守卫通过 | 独立序列工具；OI-026 未定项目后处理保留 null/复核，在地图包中按确认规则接通 |
| [NetMHCpan / NetMHCIIpan 接入](#w2-netmhc-开发接入) | N05 / S-18 | 两引擎固定版本真实执行，分别验证输入切分、坐标、等位基因及原始输出解析；统一查询与失败/停止/恢复可复现 | 需对应原包、模型、许可及实际支持的 allele；OI-003 约束宿主默认面板，原包实测与明确 allele 的开发验证可独立推进 |
| [BLAST 本地检索接入](#w2-blast-本地检索接入) | N03 / S-03 | 固定 BLAST 与本地目标库/索引，统一提交、禁网比对、解析、查询和产物回连；验证命中、未命中、库不可用及生命周期 | 本地目标序列库、版本/来源与许可待落实；不恢复 IEDB 服务，不把相似性命中视为文献表位证据；数据与消费问题见 OI-028 |
| [表位地图与 W2 联调发布](#w2-n06-表位地图与局部联调) | N06 / S-19，汇合 N04–N05，回连 N03 执行事实 | 绑定 BepiPred 原始列并仅落实已确认的后处理，按 SOP/Schema 保留部分合成 B 细胞图、T 细胞呈递图与抗原热点图；验证 N03 BLAST 回连、无 IEDB 服务依赖、证据缺省、坐标/空值/失败路由及局部 Dify/离线链，满足适用 G0–G6 后冻结 | 开发可先用明确标识的契约夹具与未签收原始结果；科学消费需相应输入资格及 OI-001/003/007/026/028 等适用规则闭合；BLAST 命中不直接进入实验表位通道，不得虚构 E3/E4 或以空热点宣称表位保护通过 |

W2 默认开发顺序为 BepiPred → NetMHC 两引擎 → BLAST 本地检索 → 地图汇合；不再排期或等待 IEDB 服务。遇到原包或目标库的外部阻塞时，转入具备输入条件的独立包，包括 W3 的 N07 序列扫描；资产到齐后在原包内续做，不重建准备阶段。BLAST 目标库未明确不阻断 NetMHC 和已明确地图规则的工程工作；当前执行优先级只在 STATUS 维护。
NetMHC 依据 [ToolSpec A1 v10.5 §1–7](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_A1_NetMHCpan_v10.5.md)；地图按 [SOP S-19](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)与 [Schema 表位对象](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md)的保留部分实施，[现行来源边界](../PHASE1_SCOPE_REBASELINE.md)覆盖其中 IEDB 生产依赖。具体规则缺口统一见 [开放项](../OPEN_ITEMS.md)。

### W2 N06 表位地图与局部联调

**交付目标**：把已接入的 BepiPred、NetMHC 原始结果接到统一 N06 后端，形成可查询、可回连来源的地图开发结果，并接通 N07 的真实产物引用校验。工作归本页原有“表位地图与 W2 联调发布”包，开发接入、科学消费与整波冻结分别验收，不新增准备或补证包。

**输入与开发边界**：通过任务/产物引用读取已完成工具输出，校验序列 hash、坐标、版本、尝试与结果完整性；不能仅信任请求中自报的来源字符串。真实未签收输出只用于显式开发调用或回放，保持原资格，禁止自动交接；契约夹具单独标识。N03 真实目标库暂缺时记录未执行，不伪造 BLAST 命中或 IEDB E3/E4。

在同一包内连续推进：

1. 实现 N04/N05 原始结果绑定、字段/坐标转换及 N06 统一提交/查询；BepiPred 原始列与项目后处理分开，按 OI-026 核实已有规则，不私选分数列、补峰或重算工具标签。
2. 按 SOP S-19/Schema 实现有明确依据的 T 细胞肽段到残基映射、呈递区间及 B/T/热点数据结构；保留不同输入可用性，区分缺失、失败、合法空值和局部结果。E 级/权重/归一化按 OI-007 等逐项归并，未定或退化输入没有明确处理依据时只关闭受影响分支，禁止猜默认值或降阈值造热点。
3. 将 N07 来源声明升级为实际 N06 ArtifactRef 校验，覆盖同序列绑定、缺失/损坏/替换产物和上游失败。恰 20 aa 的开发契约案例与真实 N06 输出分开记证据；非 20 aa 热点换算仍按 OI-029 等算法确认，不能用测试窗口冒充真实热点联调完成。
4. 用现有真实工具产物完成可复现的开发联调，并验证部分/全部输入不可用、序列不一致、空结果、来源篡改和适用生命周期；共享层按实际影响回归。记录每个已执行计算、关闭分支及具体原因，不以“任务成功”代替地图完整或科学通过。

**开发完成标准**：一条命令能绑定实际 N04/N05 开发产物，取得 N06 已明确分支的真实计算结果、来源和未完成分支清单；具备 N07 实际来源校验及异常路径证据，受影响回归通过。若只完成绑定或夹具，不记整个 N06 开发接入完成。全部科学规则与真实热点消费闭合前不宣称三图科学完成或 N06→N07 全链通过；N03 未完成时不宣布完整 W2 通过。实现、命令和批次索引回填本节，实际状态只在 STATUS 维护。

#### N06 本机调用与接口

N04、N05 与 N06 必须使用同一运行根；命令接收已终态的上游任务 ID，运行时据此生成精确 ArtifactRef，并在准入和执行前分别校验任务/尝试/产物登记、文件大小与 SHA-256、结果身份及序列 SHA-256：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <绝对运行目录> epitope-map --sequence <严格大写AA20序列> --user-id <别名> --blast-job-id <N03任务ID> --bepipred-job-id <N04任务ID> --netmhc-job-id <N05任务ID> --key <幂等键> --run
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <同一绝对运行目录> glycosylation --sequence <同一序列> --user-id <别名> --n06-job-id <N06任务ID> --key <幂等键> --run
```

N06 精确请求为 `protein_sequence/user_sequence_id/bepipred_input/netmhc_input/blast_input/timeout_seconds`；N04/N05 输入分别区分 `available/upstream_unavailable/not_provided`，N03 输入区分 `available/upstream_unavailable/not_executed`，非空来源必须是已登记结果或诊断 ArtifactRef。N03→N06 工程回连已实现：后端在提交和执行时复核任务/尝试、ArtifactRef 登记与 hash、同序列 SHA-256，并核对 BLAST 结果内的库 ID 与 manifest SHA-256；命中、合法无命中和执行不可用分别保留，后者不得解释为 no-hit。N06 只复制普通相似性 HSP 与工程数据库身份，`iedb_evidence/epitope_evidence_level/epitope_regions/contact_residues` 保持 null，不生成 E3/E4、不进入表位权重。服务器目标库验收仍由 OI-028 独立跟进。当前已计算地图分支包括 NetMHC 原生肽段字段到 1-based 残基映射、覆盖残基最小 `%Rank_EL`、非退化区间的 `1-minmax` 同向分数、SB 至少两个不同 allele 的呈递区间及相隔不超过 10 aa 的合并；合法空命中与部分通道单独保留。原生 `SB/WB/NB` 不重算。

BepiPred 两列逐残基原始分数已回连，但 OI-026 未定的选列、峰和后处理不计算；OI-007 未签收的证据权重、B 细胞抗原热点及 `density_per_residue` 保持 null/复核，退化 rank 范围也不猜归一值。N07 现在验证真实 N06 结果 ArtifactRef；当前 N06 不会把未完成的 B 细胞热点换算成测试窗口，因此会返回已验证来源和 `N06_HOTSPOTS_REVIEW_REQUIRED`，遮蔽判定为 `NOT_PERFORMED`，非 20 aa 换算继续受 OI-029 约束。

[实现](../../../src/t01_phase1_real/development/epitope_map/result.py)、[针对性测试](../../../tests/test_epitope_map_development.py)与[验收脚本](../../../scripts/run_epitope_map_acceptance.py)可直接复核。[现行完成索引](../../../discovery/t01-phase1-real/w2/epitope-map-integration-20260907/acceptance-r06/index.json)含 24 个案例、304 份索引前文件和 161 项发布产物校验；在同一运行根用固定 BLAST+ 2.17.0 实际建立命中/无命中工程库，回连真实 N03、BepiPred、NetMHC 产物，并覆盖 N03 不可用、序列错配和 BLAST 来源 hash 篡改。真实地图链继续产生 102 个 BepiPred 残基记录、644 个 MHC-I 命中和 60 个有效 MHC-II 命中，并保持 N06→N07 来源回连。r05 是沙箱内无法访问 Docker 管道的未完成尝试，不计 PASS；r01–r03 的既有未完成原因和 r04 的前版 PASS 均保留。以上只完成本机工程回连和 N06 开发接入，不代表服务器目标库验收、科学签收、真实热点全链、完整 W2 或生产部署。

### W2 BLAST 本地检索接入

**交付目标**：在 N03 保留本地 BLAST，将查询序列与明确登记的目标序列库进行禁网比对，经统一任务入口取得原始输出、解析结果和可追溯产物。依据最新用户澄清及 ToolSpec C20 的 BLAST 适用条款；其 IEDB 数据/文献语义不直接套用到未指定的新目标库。
在同一包内完成 BLAST 版本及目标库/索引核验、可追溯输入实跑、解析与统一生命周期接入。数据库必须有来源、版本、许可、输入格式和索引 hash；以实测明确比对字段/坐标，不擅自选择公共库、下载 IEDB 镜像或将 N08 的同源库自动当作 N03 文献库。

**N03→N06 工程回连完成标准**：可先使用本机真实 BLAST 工程产物验证状态、来源和普通相似性结果的 ArtifactRef 回连，不等待服务器目标库验收。后端核验来源任务/尝试、产物登记/hash、同序列绑定及库 ID/manifest，保留工程库和开发未签收身份；覆盖命中、合法未命中、上游不可用、来源不符与产物篡改。结果继续 `usable_for_pipeline=false`、禁止自动交接，不生成 IEDB 文献或 E3/E4 资格。工程回连完成与服务器目标库实跑分别记证据，目标验收缺失不反向阻断工程联调。
**开发完成标准**：一条可复现命令对登记的真实目标库执行本地查询，区分命中/未命中/不可用，结果回连原序列、数据库及原始比对；取消/超时/恢复/幂等和完整性守卫通过。仅用工程 FASTA 建库验证时保留夹具身份，不宣称目标数据或文献表位能力已交付；未定证据映射保持复核。
按 [用户对数据库位置的澄清](../DECISIONS.md)，本机暂时无数据库、部署服务器已有数据库。本机用工程样本验证引擎，目标库在部署服务器核验与实跑，不要求完整库先复制到开发机。服务器库名/用途/路径及适用性尚待核实，缺项与关闭证据集中在 OI-028；实施用法回填本节，执行事实回填 STATUS 和单批次索引。

**目标库未落实时的可执行范围**：在本包内完成 BLAST 引擎工程接入，不另建准备任务。依据 [C20 的 BLAST 适用条款](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C20_IEDB镜像_BLAST_v10.5.md)，由主开发核验并固定 BLAST+ 工具及来源/许可，实测 `makeblastdb`、`blastp` 的本地入口和输出，再复用统一提交、查询与任务生命周期。

- 使用明确标为工程夹具的小型蛋白 FASTA 建库，真实执行比对，固定源序列、ID、数据库清单、索引 hash、命令与原始 HSP 输出。解析查询/目标坐标、identity、query coverage 和原始统计量；过滤与聚合规则保留来源，原 IEDB 文献证据映射不得移植到普通命中。
- 验证命中、合法未命中、非法序列/ID、库缺失或损坏、工具失败、取消/超时/恢复/重试/幂等、输入及产物篡改；运行时禁网，缺资产不联网拉取。共享层按实际影响回归，不能用模拟结果代替工具实跑。
- 数据资产身份与引擎执行身份分别登记。数据库位置通过执行环境配置与批准的库标识绑定，不硬编码开发机路径；服务器既有库核实后，配置目标 Worker 可访问的本地路径/只读挂载，并在服务器复用同一接口执行目标库验收。登记用途、来源/版本/许可、序列与索引；未明确时不替用户选择公共库、恢复 IEDB 或复用旧 S07 数据。
- 与 N06 衔接时只回连 N03 的实际执行及来源事实。工程库命中始终保留测试用途，未检索/不可用/无命中分别表达，不赋予 E3/E4 或科研资格。

**工程交付证据**：一条命令可用固定 BLAST 对工程库完成真实查询、解析和产物回连，上述守卫通过，并明确报告目标库未验收。可以记“引擎工程接入完成”，但 N03 整个包仍为 `IN_PROGRESS`；仅登记接口或缺资产诊断不构成引擎完成。目标库验收继续采用上面的开发完成标准，证据和用法均回填本节。

#### N03 本机调用与接口

本机工程接入固定 NCBI BLAST+ `2.17.0+` 官方 Linux amd64 镜像，镜像 ID 与仓库 digest 均为 `sha256:81f118d2e4f7e11494d27fdbb99c9430423105afff50c4ae158db41d58a3fc57`。`blastp` 和 `makeblastdb` 已分别断网实测；工具身份与数据库身份分开登记，固定工具不推断数据库来源或许可。

数据库位置只能由受信任执行环境的全局 `--blast-database-root` 配置，任务请求不接受路径或命令。该目录下以 `<database_id>/manifest.json` 登记库；manifest 固定记录库 ID、工程/目标未复核资格、用途、来源名称/版本/日期/许可/引用、源 FASTA，以及 `db_prefix/dbtype/BLAST DB 版本/标题/序列数/makeblastdb 身份` 和每份源文件/索引的大小与 SHA-256。请求再绑定精确 manifest SHA-256，Worker 执行前后都逐文件复核并只读挂载该库。当前只允许 `ENGINEERING_FIXTURE` 或 `TARGET_DATABASE_UNREVIEWED`，不允许以自报字段直接宣称目标库已批准。

从项目根执行以下一条命令即可查询已登记库；参数位置中的库根、ID 和 manifest hash 必须替换为同一登记项：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <绝对运行目录> --blast-database-root <绝对数据库根目录> blast --sequence <严格大写AA20序列> --user-id <别名> --database-id <登记库ID> --database-manifest-sha256 <64位小写SHA-256> --identity-min 70 --query-coverage-min 80 --key <幂等键> --run --wait 60
```

等价 JSON 必须且只能包含 `protein_sequence/user_sequence_id/database_id/database_manifest_sha256/thresholds/timeout_seconds`；序列为 9～20,000 aa 的大写 AA20。默认阈值来自 C20：identity ≥70%、query coverage ≥80%，其中 coverage 由 HSP 的 1-based query 区间除以查询全长计算，并保留 BLAST 原生取整值供复核。原始 HSP 不因阈值删除，结果同时返回 `raw_hsps` 和 `qualifying_hsps`，不做跨 HSP/subject 聚合；空表或只有阈值以下 HSP 均为合法 `no_hit`。库/工具不可用返回 `unreliable`，绝不伪装成 no-hit。

结果只表达普通蛋白相似性：`iedb_hit/evidence_level/epitope_regions/contact_residues` 明确为 null，工程库命中带 `ENGINEERING_DATABASE_ONLY` 警告，所有结果保持 `usable_for_pipeline=false`、`automatic_handoff=false` 和 `NOT_DEPLOYED`。N06 现可消费同一运行层已登记的工程 N03 结果以验证接口、身份和失败路由；该动作不赋予科学资格，也不替代服务器目标库验收。

[Worker/解析器](../../../src/t01_phase1_real/development/blast/worker.py)、[引擎收据](../../../src/t01_phase1_real/development/blast/assets.json)、[针对性测试](../../../tests/test_blast_development.py)与[验收脚本](../../../scripts/run_blast_acceptance.py)可直接复核。[完成索引](../../../discovery/t01-phase1-real/w2/blast-integration-20260907/acceptance-r03/index.json)含 18 个场景、368 份索引前文件和 227 项发布产物校验；覆盖真实工程 FASTA 建库、命中/未命中/阈值以下 HSP、非法输入、库缺失/manifest 不符/索引损坏、工具与输出失败、重试、排队/运行取消、超时、崩溃恢复、幂等及发布产物篡改。r01 因官方镜像自带标签未纳入容器所有权预期、r02 因 BLAST 原生 coverage 整数取整未纳入容差而在完成前停止，均保留且不计 PASS。N03→N06 工程回连另由 [N06 r06](../../../discovery/t01-phase1-real/w2/epitope-map-integration-20260907/acceptance-r06/index.json)完成；服务器目标库适用性、目标环境实跑及相应科学消费仍按 OI-028 跟进，科学签收与生产部署未完成，故整个 N03 包保持 `IN_PROGRESS`。

### W2 NetMHC 开发接入

**交付目标**：在现有运行层接入 NetMHCpan 4.2 与 NetMHCIIpan 4.3，统一提交、禁网执行、解析和查询可追溯开发结果；两引擎作为同一包推进，各自保留版本、输入和失败事实。

1. 在本项目适用资产范围核验原包/模型、许可、可执行入口和支持的 allele 清单；据实际支持项选取有来源的开发调用，不声称该选择已构成宿主科学面板。缺资产先记录具体缺项与获取责任，能继续的另一引擎或工程工作照常推进。
2. 分别实测全长 FASTA/肽段输入、切分方式、Pos 基址、%Rank_EL、BindLevel 和 MHC-II core 等原始输出，再明确请求/结果契约。A1 切片不得直接充当 A2 输入，classification 按原包 BindLevel 消费，不以项目阈值重算。
3. 复用现有任务、监督、幂等与 ArtifactRef；未知宿主面板与降级只按 ToolSpec 及已登记可执行列表处理，OI-003 未确认部分保持复核。区分单通道不可用、部分行失败和全部不可用，保留原件规定的 WARNING/继续语义及未签收标识。
4. 验证两引擎真实正常输出与坐标回连、非法输入/allele、部分/全部解析失败、工具不可用及取消/超时/恢复/幂等，按共享代码影响补已有工具回归。源码、接口与一条可复现调用命令回填本节，执行事实归一个批次索引并链接到 STATUS。

**开发完成标准**：两引擎都具备真实执行及统一查询证据，适用输出/生命周期守卫通过；未定面板和科学规则不伪装为已支持。仅一引擎完成时按实际进度记录，不宣布整个包完成；科学签收、目标复现与完整 W2 发布分别判断。

#### NetMHC 本机调用与接口

2026-09-07 用户提供 `netMHCpan-4.2e.Linux.tar.gz` 与 `netMHCIIpan-4.3k.Linux.tar.gz` 并明确要求接入。本项目核验二者为 Linux x86_64 包，原始 SHA-256 分别为 `716e6ef6fbdb5cb2dd6aeb12ea4ff0115a492f0e6ceb3c0b3bb9bad36a8dd529` 与 `020edc7f402908823b09ab0dc7c144707184640bf31bc5dd0a04b6456368d095`；固定本地镜像为 `sha256:c0a7239d4005484c1248b78de91bf7a76acffe0ed41f52614a54b6c20b3cf094`（`amd64/linux`）。包内条款只登记为本地学术开发，不推断商业或生产许可。

从项目根执行一条命令，返回任务与真实双通道原始预测。示例序列和明确 allele 只用于开发验证，不构成宿主科学面板：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\netmhc-demo netmhc --sequence MRYGFVRKKHRGLFLTTVAALPIWNPISEFVKWYKSHKLSQHCIRICGHLCQKHLDMFLSVIGQRWPIDVFSSVFDHQVSAIGSDIIWWFLKLFLVSFFFFF --user-id development108 --host "Homo sapiens" --mhc-i-allele HLA-A02:01 --mhc-ii-allele HLA-DPA10202-DPB11901 --key n05-demo --run --wait 60
```

等价 JSON 必须且只能包含 `protein_sequence`、`user_sequence_id`、`host_species`、`mhc_i_alleles`、`mhc_ii_alleles`、`timeout_seconds`。序列为 15～20,000 aa 的大写 AA20；I/II allele 必须来自固定包内清单，上限分别为 20/15，并受每通道 150,000 原生行的输出边界限制。OI-003 未闭合前只接受明确 allele，不按宿主推断默认面板。

两个原生 CLI 分别接收同一全长 FASTA：MHC-I 明确生成 8–14mer，MHC-II 生成 15mer；实测 `Pos` 为 1-based。解析器将短安全 Identity 回连完整序列 SHA，按包内 `allelenames` 接受 MHC-I 原生展示名（如请求 `HLA-A02:01`、输出 `HLA-A*02:01`），只消费原生 `BindLevel`，不以项目阈值重算；MHC-II inverted 行保留计数但不形成 hit。结果区分 `raw_predictions_unreviewed`、`partial_unreliable` 与全部 `unreliable`，始终保持 `usable_for_pipeline=false`、`automatic_handoff=false`、`NOT_DEPLOYED`。

[Worker/解析器](../../../src/t01_phase1_real/development/netmhc/worker.py)、[资产收据](../../../src/t01_phase1_real/development/netmhc/assets.json)、[镜像构建记录](../../../discovery/t01-phase1-real/w2/netmhc-integration-20260907/environment/build.json)、[针对性测试](../../../tests/test_netmhc_development.py)与[验收脚本](../../../scripts/run_netmhc_acceptance.py)可直接复核。[完成索引](../../../discovery/t01-phase1-real/w2/netmhc-integration-20260907/acceptance-r03/index.json)含 12 个场景、251 份索引前文件和 167 项发布产物校验；r01/r02 是保留的未完成编排运行，不计 PASS。本包开发接入完成，OI-003、科学签收、目标复现和完整 W2 发布仍分别判断。

### W2 BepiPred 开发接入

**交付目标**：统一入口提交序列，真实禁网执行 BepiPred 3.0，返回可追溯逐残基原始分数、产物和后处理复核原因。原包核验、实跑、封装与验收连续完成，作为 W2 的一个交付包；完整 W2 包含上表 N03–N06 的保留能力。

依据：[当前专家包 ToolSpec A3 v10.5 §1–4](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_A3_BepiPred_v10.5.md)、其引用的 SOP S-17/S-19 与 [OI-026](../OPEN_ITEMS.md)。一期仅线性路径，A3 不消费结构；独立开发不等待结构科学签收、AF3/ESMFold2 或 NetMHC 全部就绪。旧同事工具包只作历史参考。

1. 核验 BepiPred 3.0 原包、依赖权重、许可与可追溯输入，在本项目独立运行资产中固定版本/hash。确认本地禁网入口，先取得真实原始输出、错误及资源事实；未发现资产不写成已安装，缺项只登记其实际阻断动作。
2. 依据实跑确认输出列、逐位身份、长度与失败语义，再复用现有运行层接入提交、执行、解析、查询和产物发布，不复制任务系统。工具原始分数与项目后处理结果分开保存。
3. OI-026 的分数列/平滑、Top20%、桥接顺序等先检索适用原件与原包事实；能明确的规则直接实现，剩余歧义定点交算法确认。未定后处理输出保持 null/需复核，不猜科学规则；不得把缺失 A3 的失败伪装成无表位的成功结果。
4. 验证真实正常输入、非法输入、损坏或长度不符输出、工具失败、取消/超时、恢复、幂等与产物回连；按共享代码影响补 DeepTMHMM/结构链回归。真实计算、夹具和故障注入分列，未受影响的完整检查沿用证据。

**开发完成标准**：一条可复现命令取得真实原始分数及其可用性/复核状态，受影响生命周期与结果守卫通过，开发未签收和禁止自动交接标识保持；源码、用法及一份执行批次索引可回连。未定后处理的科学完成与本包工程完成分别判断，不能宣布 N04 科学验收或完整 W2 已完成。
本节即实施入口；必要接口、用法与精确工具资产缺项先回填本节，进度只更新 STATUS，不另开原包准备、契约评审或补证任务页。预测结构资产与科学签收按既有 W1 记录独立跟进。

#### BepiPred 本机调用与接口

统一入口 [t01_runtime.py](../../../scripts/t01_runtime.py) 的 `bepipred` 子命令登记 `t01.real.bepipred / N04`，复用现有 SQLite、run/job/attempt、幂等、事件、容器监督与 ArtifactRef。原 W1 Schema 保持原字节；[增量契约校验](../../../src/t01_phase1_real/development/contracts.py) 仅增加该工具与节点组合，其他形状及状态规则不变，旧入口仍拒绝科学工具。

从项目根执行一条命令，返回任务与真实原始分数。这个 51 aa 输入仅为开发运行样本，不代表独立科学验收：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\bepipred-demo bepipred --sequence MQLRHIGDSVNHRVIQEHLAQEVGDVLAPFVALVFVRGQVLLRFFWNNHLL --user-id development51 --key bepipred-demo-1 --run --wait 120
```

前提为 Windows、本项目 `.venv`、Docker Desktop Linux Engine 与以下本地资产。实际运行不拉取镜像、不下载权重；资源槽等待最长 900 秒，执行期限由请求控制，`--wait` 仅限制客户端等待。同 key 与原请求字节返回同一任务，字节不同报 IDEMPOTENCY_CONFLICT；新执行使用新 key。

| 接口/资产 | 固定开发口径 |
|---|---|
| 请求 | Python `Runtime.submit_sequence(raw, key, tool_id='t01.real.bepipred')`；严格三个 JSON 字段 protein_sequence、user_sequence_id、timeout_seconds，CLI 支持 `--input` 读取原字节 |
| 序列/别名 | 大写 AA20，9～1022 aa，不改写空白/大小写/非常规符号；1022 是本机验收上限，不宣称为模型最大长度。用户别名至多 512 字符，仅元数据；原包 ID 为 `t01seq_` + 序列 SHA-256 |
| 执行 | timeout_seconds 整数 1～900、默认 900；CPU 8/亲和 0–7、10 GiB、512 PID、独立单容器槽、只读模型/输入、network=none、内部硬期限。无 GPU、无联网回退 |
| 官方仓库 | [BepiPred-3.0](https://github.com/UberClifford/BepiPred-3.0/tree/98bedf2471e04766c981585180c20da7961c6804)，固定提交 `98bedf2471e04766c981585180c20da7961c6804`；[源码与哈希收据](../../../discovery/t01-phase1-real/w2/bepipred-integration-20260906/source-receipt.json) |
| 模型/环境 | bp3 0.0.12.7、fair-esm 1.0.3、ESM-2 `esm2_t33_650M_UR50D` 与 contact regression；PyTorch 2.5.1+cpu、NumPy 1.22.0、Pandas 1.4.3、Plotly 5.8.0、Python 3.10.21。[104 项固定资产](../../../src/t01_phase1_real/development/bepipred/assets.json) 包含源码、许可、模型、安装报告与专家原件 |
| 镜像 | `sha256:e1aff495e254ca4da513286f4ada0e1e0a071a2ffd9e0bc8ae3d2e6c91384149`；[构建、安装及系统报告](../../../discovery/t01-phase1-real/w2/bepipred-integration-20260906/environment/build.json)。依赖准备允许下载，推理完全禁网 |
| 原包调用 | 未修改官方 CLI；vt_pred，threshold=0.1512，top=0.2，rolling_window=9，CLI 默认 add_seq_len=false（BP3C50IDFFNN 五折）。模型选项与原包参数不是项目科学放行决定 |
| 原始结果 | raw_scores 每位包含 sequence_position（1-based）、residue、ensemble_probability、linear_epitope_score；两列原值分别保存。raw_record 保留 CSV 列名、阈值/Top20% FASTA、原包参数、嵌入形状和五折身份 |
| 原包行为 | 概率为五折正类概率均值；平滑为 `convolve(..., ones(9), same)/9`，两端零填充。Top20% 数量用 Python round，并列沿输入顺序；原包分类比较 ≥阈值（float32），项目峰定义为严格 >，不将原包 FASTA 直接认作项目峰 |
| 后处理 | postprocessing.status=review_required / OI-026；linear_scores、linear_peaks、conf_scores、conf_peaks、epitope_map 均为 null。原包分数列、平滑、Top20%、桥接及模型特征分支的科学签收条件集中在 OPEN_ITEMS；不伪造 DiscoTope 或 E2 |
| 错误/资格 | A3 执行/产物不可用时 failed/cancelled/timed_out、raw_scores=null、A3_UNAVAILABLE_HALT；不可伪装为无表位成功。有效原始结果为 raw_scores_unreviewed，DEVELOPMENT_UNREVIEWED、usable_for_pipeline=false、automatic_handoff=false、scientific_signoff=null、NOT_DEPLOYED |

同一 `--root` 下使用 `get / result / events / execution --job-id …` 查询；`artifact --job-id … --artifact-id … --output …` 校验 hash 后导出到新文件；`cancel / retry --job-id … --key …` 控制任务，显式重试后用 `dispatch` 启动；`recover --job-id …` 处理监督进程中断。容器停止确认先于终态，缺失/损坏产物或收据不得恢复为有效原始分数。

每次输出回连请求/序列 hash、run/request/job/attempt/execution/profile；原包输出清单、嵌入、五折观测、原 CSV、三份 FASTA 和原生 HTML 分别发布。宿主校验列、长度、逐位字母与安全 ID、有限概率、五折与平滑一致性、分类产物及环境身份。HTML 原件是引用 Plotly CDN 的片段，作为未渲染原始产物保存；命令行分数查询不依赖该网页。

输入失败事实：[原包含 `*` 的输入](../../../discovery/t01-phase1-real/w2/bepipred-integration-20260906/raw-runs/invalid-star/index.json)退出 1；[8 aa 原包输入](../../../discovery/t01-phase1-real/w2/bepipred-integration-20260906/raw-runs/short8/index.json)退出 0，但原始概率 8 位、窗口平滑 9 位，CSV 只保留 8 行。项目仍在准入前拒绝 <9 aa，并在解析时要求原始观测/分数/输入等长；不把退出 0 等同于支持。9 aa 与 1022 aa 的整长回连仅为本机开发覆盖事实。

许可按来源分别保留：仓库 README 声明学术非商业条件，bp3 wheel 携带 MIT 文本，ESM 携带 MIT 文本；不以 wheel 元数据覆盖仓库/数据条款，不据本机开发验收授予商业或目标发布资格。原包示例属于随包参考，不是独立留出测试集。

[Worker/解析器](../../../src/t01_phase1_real/development/bepipred/worker.py)、[针对性测试](../../../tests/test_bepipred_development.py)与 [验收命令](../../../scripts/run_bepipred_acceptance.py)可直接执行。全组验收使用 `--root <新的绝对目录> --batch <W2 discovery 下的新目录>`，真实原包输入、工程边界输入及受控故障分列；实际结果与统一批次索引见 STATUS。

