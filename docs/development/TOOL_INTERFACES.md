# 当前真实工具接口参考

> 从既有 W1–W7 说明中归并的工程调用与字段参考。科学资格和当前排期分别见 [开放项](../project/OPEN_ITEMS.md)和 [STATUS](../project/STATUS.md)。不以历史接口示例代替当前源码与批准 profile。

命令与检查入口见 [RUNBOOK](RUNBOOK.md)；原版本完整语境见 [历史索引](../project/history/README.md)。

## W1 N01–N02 输入、结构与基础分析

### 本机调用与接口

当前统一入口为 [t01_runtime.py](<../../scripts/t01_runtime.py>)，登记 engineering_probe、DeepTMHMM 和下节本地结构分析 Worker。
[development.Runtime](<../../src/t01_phase1_real/development/runtime.py>) 在原 SQLite 运行层上扩展固定 Worker，沿用相同任务表、事务、幂等、状态和 ArtifactRef；旧工程入口及封存源码保留原字节。
前提：Windows、本项目 `.venv`、本机 Docker Desktop Linux Engine，以及已登记的 Academic 1.0 镜像和 41 项包/模型资产。镜像不拉取，运行不联网。

从项目根执行以下一条命令，等待完成后同时返回 job 和解析结果：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\deeptmhmm-dev deeptmhmm --sequence MQLRHIGDSVNHRVIQEHLAQEVGDVLAPFVALVFVRGQVLLRFFWNNHLL --user-id Q8K459 --key deeptmhmm-demo-1 --run --wait 120
```

相同 key 和完全相同请求字节返回同一任务及 attempt；不同字节报 IDEMPOTENCY_CONFLICT。独立新执行使用新 key。
`--wait` 仅限制客户端等待时长；模型执行期限由请求 timeout_seconds 控制。未终态可用 `wait --job-id … --seconds 120` 继续等待。
同一 `--root` 下，`get / result / events / execution --job-id …` 查询状态、结果、事件和停止证据；`artifact --job-id … --artifact-id … --output …` 按 hash 校验后导出到新文件。
`cancel --job-id … --key …` 持久化停止请求；`recover --job-id …` 接管同一次执行；`retry --job-id … --key …` 为已确认停止的失败任务建立有来源关系的新任务，再用 `dispatch --job-id …` 执行。

| 接口 | 开发口径 |
|---|---|
| 请求 JSON / Python `submit_sequence(raw, key)` | 严格三个字段：protein_sequence、user_sequence_id、timeout_seconds；CLI 支持 `--input` 读取原始 JSON 字节 |
| protein_sequence | 大写 AA20，9～1023 aa；不去空白、不替换 X/`*`；1023 为本机资源覆盖上限，不是生物学或模型上限 |
| user_sequence_id / 安全 ID | 用户原字符串只作元数据，至多 512 字符；原包 ID 固定为 `t01seq_` + 序列 SHA-256，路径及产物按此回连 |
| timeout_seconds / 资源 | 整数 1～900，默认 900；固定 8 CPU/亲和 0–7、10 GiB、512 PID；跨本机开发根共用一个模型容器槽，等待槽位最长 900 秒 |
| 成功解析 | topology 包含逐位四枚举标签、1-based 闭区间连续区段、tm_count（M 段数）、outside_length（O 位数）、has_signal；status=parsed_unverified |
| P/B | 任务执行可 succeeded，结果 status=unreliable、topology=null、null_reason=PB_OUT_OF_DOMAIN、failure/WARNING；原六标签、区段和原包类型完整留在 raw_record |
| 执行或产物错误 | failed / cancelled / timed_out；topology=null，保留 error_code、诊断和可读原始产物；未知执行维持 reconciling，禁止重复启动或重试 |
| 追踪与资格 | result.binding 绑定 run/request/job/attempt/execution/profile 和输入/序列 hash；raw_artifacts 带路径及 ArtifactRef；DEVELOPMENT_UNREVIEWED、usable_for_pipeline=false、automatic_handoff=false、scientific_signoff=null |

内部验收故障开关只存在于 Python 测试工具，不是业务请求字段或 CLI 选项。
容器内观察器在原包执行后记录输出字节 hash；宿主还核验输入、token 回拼、标签/区段、概率、PNG、环境、退出事实和恢复清单，再原子发布结果。停止收据的 hash 同步记入任务数据库，损坏收据不能用于恢复发布。
宿主退出不能代替容器停止；创建后按已登记的不可变容器 ID 查询/停止/恢复，并精确匹配当前 run/job/attempt/execution。存活监督进程继续原执行，监督进程中断时停止已归属容器；完整停止收据可用于恢复发布，运行中断不自动重跑。

针对性回归为 [test_deeptmhmm_development.py](<../../tests/test_deeptmhmm_development.py>)。实际批次由 [run_deeptmhmm_acceptance.py](<../../scripts/run_deeptmhmm_acceptance.py>)生成，用新 `--root` 和新 `--batch` 运行；执行结果索引见 STATUS 的当前验证。

### 本地结构调用与接口

统一入口的 `structure` 子命令原子登记序列/宿主元数据、原结构字节、请求 ArtifactRef 和任务；随后在固定 FreeSASA/Biopython 镜像中执行输入事实→严格解析→候选映射→S-09→条件 FreeSASA→RSA 回连。沿用上节的查询、取消、恢复、重试和产物导出命令，无须另起服务。

从项目根执行以下一条命令，可复现整链面积计算并同时取得任务与分析结果。此输入为明确标记的工程夹具：九个残基使用最小骨架/CB 几何，不能作为科学准确率或重原子完整性的参考。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\structure-demo structure --structure-file discovery/t01-phase1-real/w1/structure-integration-20260906/acceptance-r02/inputs/normal-cif.structure --input discovery/t01-phase1-real/w1/structure-integration-20260906/acceptance-r02/inputs/normal-cif.json --key structure-demo-1 --run --wait 120
```

自有文件可使用 `--structure-file <本地路径> --sequence <序列> --host <宿主> --format PDB或MMCIF --source experimental --context-chain A --key <唯一键> --run --wait 120`。`--source` 默认为 unknown；只有明确声明 experimental 才评估原文件实验方法与分辨率。结构宿主字段不覆盖用户宿主，不根据 B-factor 推断 pLDDT，不从普通 ELECTRON MICROSCOPY 自动推定 cryo-EM。文件名仅作元数据，不用于容器命令或产物路径。

| 接口/结果 | 开发口径 |
|---|---|
| Python | `development.Runtime.submit_structure(raw_metadata, key, structure_bytes)`；`dispatch / wait / result` 与其他 Worker 共用同一任务库 |
| `--input` 元数据 JSON | 严格八字段：protein_sequence、host_species、structure_name、declared_format、selection、context_chain_ids、source_declaration、timeout_seconds；具体类型及验证见 [policy.py](<../../src/t01_phase1_real/development/structure/policy.py>) |
| 输入范围 | 大写 AA20、9～2000 aa；原结构 1 byte～4 MiB，PDB/CIF/MMCIF；宿主非空且至多 256 字符。本机工程限额不声明为一期或模型最大支持域 |
| 模型与链 | selection 包含 model_index（null 或非负整数）及 chain_selector（AUTO 或明确作者链）；多模型必须指定。context_chain_ids 为调用方明确提供的蛋白计算上下文，不自动选择生物学装配体 |
| 幂等 | key + 原元数据字节 hash + 原结构字节 hash；完全相同提交复用原任务，不同字节报 IDEMPOTENCY_CONFLICT。运行中代码 profile 变化拒绝发布，历史结果保留执行时 profile |
| 资源 | 固定 FreeSASA 2.2.1/Biopython 1.88 镜像；禁网、不拉取、2 CPU/亲和 0–1、1 GiB、64 PID、单结构容器槽；timeout_seconds 为 1～120 秒，默认 60。槽位等待最长 900 秒；`--wait` 仅为客户端等待 |
| 分析 | analysis 包含 input、steps、mapping、quality、freesasa、rsa、warnings 和 method_summary；步骤区分 executed、skipped、blocked、review_required。映射始终为候选，未授予批准 |
| S-09 / 未定分支 | 按已采用的六项先行规则；低质量跳过 FreeSASA，NMR ≥3 Å/未知实验方法/冲突元数据/未验证预测来源需复核。缺原子比例、预测置信度与局部 mask 不猜测，保持 null |
| 面积与 RSA | 原生原子接口，精确回连作者地址与工具原子身份，ProtOr/Lee–Richards/200 slices/1.4 Å；全序列逐位对齐，缺失残基为 null。buried_fraction 分母为完整序列长度，阈值严格 <0.20。RSA >1 保留原面积与比值、OUTPUT_INVALID，不截断，development_result=null |
| 科学隔离 | 即使计算完成，normal_rsa_result 仍为 null；未出域的数值仅置于 development_result。全链 DEVELOPMENT_UNREVIEWED、usable_for_pipeline=false、automatic_handoff=false、scientific_signoff=null、NOT_DEPLOYED |
| 错误与追踪 | 无效文件在 job 层归 INVALID_REQUEST，原预检码保留在 analysis.error_code / execution.input_error_code；损坏结果为 OUTPUT_INVALID、analysis=null。binding 包含任务、执行、profile、请求/序列/结构 hash；raw_artifacts 逐项携带路径、ArtifactRef 和 hash |

原件验收与受控夹具分列：未改写的 1UBQ CIF 返回 ICODE_UNKNOWN；原 PDB 在来源 unknown 时条件跳过。RSA 出域夹具另行记录 28 处 occupancy 修改及合成质量元数据，原坐标和原件保持不变；这一派生输入仅用于验证拒绝守卫。
宿主在发布前校验原始清单 hash、运行隔离、输入/步骤身份和逐位 RSA 回连；停止确认先于终态，缺失/损坏输出不产生有效分析。具体源码见 [structure](<../../src/t01_phase1_real/development/structure/worker.py>)，针对性测试见 [test_structure_development.py](<../../tests/test_structure_development.py>)。
完整开发验收可用 [run_structure_acceptance.py](<../../scripts/run_structure_acceptance.py>) 的 `--root <新的绝对运行目录> --batch <W1 discovery 下的新批次目录>` 复跑；受控故障只在内部验收使用。实际结果与本批统一索引见 STATUS。


## W2 N03–N06 本地检索与表位分析

#### N06 本机调用与接口

N04、N05 与 N06 必须使用同一运行根；命令接收已终态的上游任务 ID，运行时据此生成精确 ArtifactRef，并在准入和执行前分别校验任务/尝试/产物登记、文件大小与 SHA-256、结果身份及序列 SHA-256：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <绝对运行目录> epitope-map --sequence <严格大写AA20序列> --user-id <别名> --blast-job-id <N03任务ID> --bepipred-job-id <N04任务ID> --netmhc-job-id <N05任务ID> --key <幂等键> --run
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <同一绝对运行目录> glycosylation --sequence <同一序列> --user-id <别名> --n06-job-id <N06任务ID> --key <幂等键> --run
```

N06 精确请求为 `protein_sequence/user_sequence_id/bepipred_input/netmhc_input/blast_input/timeout_seconds`；N04/N05 输入分别区分 `available/upstream_unavailable/not_provided`，N03 输入区分 `available/upstream_unavailable/not_executed`，非空来源必须是已登记结果或诊断 ArtifactRef。N03→N06 工程回连已实现：后端在提交和执行时复核任务/尝试、ArtifactRef 登记与 hash、同序列 SHA-256，并核对 BLAST 结果内的库 ID 与 manifest SHA-256；命中、合法无命中和执行不可用分别保留，后者不得解释为 no-hit。N06 只复制普通相似性 HSP 与工程数据库身份，`iedb_evidence/epitope_evidence_level/epitope_regions/contact_residues` 保持 null，不生成 E3/E4、不进入表位权重。服务器目标库验收仍由 OI-028 独立跟进。当前已计算地图分支包括 NetMHC 原生肽段字段到 1-based 残基映射、覆盖残基最小 `%Rank_EL`、非退化区间的 `1-minmax` 同向分数、SB 至少两个不同 allele 的呈递区间及相隔不超过 10 aa 的合并；合法空命中与部分通道单独保留。原生 `SB/WB/NB` 不重算。

BepiPred 两列逐残基原始分数已回连，但 OI-026 未定的项目选列、峰和后处理仍不计算；`density_per_residue` 保持 null，退化 rank 范围也不猜归一值。N06 现在对当前来源集合执行独立于具体分数列的 S-19 上界证明：BepiPred 最高 E1、NetMHC 最高 E2，双通道各0.5时最大0.35，单通道重归一后最大分别0.2/0.5，均不能满足严格 `>0.5`。结果返回 `b_cell_antigenic_hotspot_map.status=computed_empty_unreviewed`、空 `hotspots`，并记录可用通道、权重、分量、阈值和结论；`weighted_hotspots_computed=false` 与 `weighted_hotspot_emptiness_proved=true` 分开，避免把未构造逐残基曲线写成已计算分数。

N07 验证真实 N06 结果 ArtifactRef、hash、序列和热点状态。对上述已计算空集合，运行时生成 `state=available, hotspots=[]`，N07 记录 `EVALUATED`、零窗口和 `scientific_consumption=false`；这与未提供/上游失败的 `NOT_PERFORMED` 不同。只有未来非空且跨度不等于20 aa的热点才继续受 OI-029 窗口转换约束。

[实现](<../../src/t01_phase1_real/development/epitope_map/result.py>)、[针对性测试](<../../tests/test_epitope_map_development.py>)与[验收脚本](<../../scripts/run_epitope_map_acceptance.py>)可直接复核。[现行完成索引](<../../discovery/t01-phase1-real/w2/epitope-map-integration-20260907/acceptance-r06/index.json>)含 24 个案例、304 份索引前文件和 161 项发布产物校验；在同一运行根用固定 BLAST+ 2.17.0 实际建立命中/无命中工程库，回连真实 N03、BepiPred、NetMHC 产物，并覆盖 N03 不可用、序列错配和 BLAST 来源 hash 篡改。真实地图链继续产生 102 个 BepiPred 残基记录、644 个 MHC-I 命中和 60 个有效 MHC-II 命中，并保持 N06→N07 来源回连。r05 是沙箱内无法访问 Docker 管道的未完成尝试，不计 PASS；r01–r03 的既有未完成原因和 r04 的前版 PASS 均保留。以上只完成本机工程回连和 N06 开发接入，不代表服务器目标库验收、科学签收、真实热点全链、完整 W2 或生产部署。

#### N03 本机调用与接口

本机工程接入固定 NCBI BLAST+ `2.17.0+` 官方 Linux amd64 镜像，镜像 ID 与仓库 digest 均为 `sha256:81f118d2e4f7e11494d27fdbb99c9430423105afff50c4ae158db41d58a3fc57`。`blastp` 和 `makeblastdb` 已分别断网实测；工具身份与数据库身份分开登记，固定工具不推断数据库来源或许可。

数据库位置只能由受信任执行环境的全局 `--blast-database-root` 配置，任务请求不接受路径或命令。该目录下以 `<database_id>/manifest.json` 登记库；manifest 固定记录库 ID、工程/目标未复核资格、用途、来源名称/版本/日期/许可/引用、源 FASTA，以及 `db_prefix/dbtype/BLAST DB 版本/标题/序列数/makeblastdb 身份` 和每份源文件/索引的大小与 SHA-256。请求再绑定精确 manifest SHA-256，Worker 执行前后都逐文件复核并只读挂载该库。当前只允许 `ENGINEERING_FIXTURE` 或 `TARGET_DATABASE_UNREVIEWED`，不允许以自报字段直接宣称目标库已批准。

从项目根执行以下一条命令即可查询已登记库；参数位置中的库根、ID 和 manifest hash 必须替换为同一登记项：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <绝对运行目录> --blast-database-root <绝对数据库根目录> blast --sequence <严格大写AA20序列> --user-id <别名> --database-id <登记库ID> --database-manifest-sha256 <64位小写SHA-256> --identity-min 70 --query-coverage-min 80 --key <幂等键> --run --wait 60
```

等价 JSON 必须且只能包含 `protein_sequence/user_sequence_id/database_id/database_manifest_sha256/thresholds/timeout_seconds`；序列为 9～20,000 aa 的大写 AA20。默认阈值来自 C20：identity ≥70%、query coverage ≥80%，其中 coverage 由 HSP 的 1-based query 区间除以查询全长计算，并保留 BLAST 原生取整值供复核。原始 HSP 不因阈值删除，结果同时返回 `raw_hsps` 和 `qualifying_hsps`，不做跨 HSP/subject 聚合；空表或只有阈值以下 HSP 均为合法 `no_hit`。库/工具不可用返回 `unreliable`，绝不伪装成 no-hit。

结果只表达普通蛋白相似性：`iedb_hit/evidence_level/epitope_regions/contact_residues` 明确为 null，工程库命中带 `ENGINEERING_DATABASE_ONLY` 警告，所有结果保持 `usable_for_pipeline=false`、`automatic_handoff=false` 和 `NOT_DEPLOYED`。N06 现可消费同一运行层已登记的工程 N03 结果以验证接口、身份和失败路由；该动作不赋予科学资格，也不替代服务器目标库验收。

[Worker/解析器](<../../src/t01_phase1_real/development/blast/worker.py>)、[引擎收据](<../../src/t01_phase1_real/development/blast/assets.json>)、[针对性测试](<../../tests/test_blast_development.py>)与[验收脚本](<../../scripts/run_blast_acceptance.py>)可直接复核。[完成索引](<../../discovery/t01-phase1-real/w2/blast-integration-20260907/acceptance-r03/index.json>)含 18 个场景、368 份索引前文件和 227 项发布产物校验；覆盖真实工程 FASTA 建库、命中/未命中/阈值以下 HSP、非法输入、库缺失/manifest 不符/索引损坏、工具与输出失败、重试、排队/运行取消、超时、崩溃恢复、幂等及发布产物篡改。r01 因官方镜像自带标签未纳入容器所有权预期、r02 因 BLAST 原生 coverage 整数取整未纳入容差而在完成前停止，均保留且不计 PASS。N03→N06 工程回连另由 [N06 r06](<../../discovery/t01-phase1-real/w2/epitope-map-integration-20260907/acceptance-r06/index.json>)完成；服务器目标库适用性、目标环境实跑及相应科学消费仍按 OI-028 跟进，科学签收与生产部署未完成，故整个 N03 包保持 `IN_PROGRESS`。

#### NetMHC 本机调用与接口

2026-09-07 用户提供 `netMHCpan-4.2e.Linux.tar.gz` 与 `netMHCIIpan-4.3k.Linux.tar.gz` 并明确要求接入。本项目核验二者为 Linux x86_64 包，原始 SHA-256 分别为 `716e6ef6fbdb5cb2dd6aeb12ea4ff0115a492f0e6ceb3c0b3bb9bad36a8dd529` 与 `020edc7f402908823b09ab0dc7c144707184640bf31bc5dd0a04b6456368d095`；固定本地镜像为 `sha256:c0a7239d4005484c1248b78de91bf7a76acffe0ed41f52614a54b6c20b3cf094`（`amd64/linux`）。包内条款只登记为本地学术开发，不推断商业或生产许可。

从项目根执行一条命令，返回任务与真实双通道原始预测。示例序列和明确 allele 只用于开发验证，不构成宿主科学面板：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\netmhc-demo netmhc --sequence MRYGFVRKKHRGLFLTTVAALPIWNPISEFVKWYKSHKLSQHCIRICGHLCQKHLDMFLSVIGQRWPIDVFSSVFDHQVSAIGSDIIWWFLKLFLVSFFFFF --user-id development108 --host "Homo sapiens" --mhc-i-allele HLA-A02:01 --mhc-ii-allele HLA-DPA10202-DPB11901 --key n05-demo --run --wait 60
```

等价 JSON 必须且只能包含 `protein_sequence`、`user_sequence_id`、`host_species`、`mhc_i_alleles`、`mhc_ii_alleles`、`timeout_seconds`。序列为 15～20,000 aa 的大写 AA20；I/II allele 必须来自固定包内清单，上限分别为 20/15，并受每通道 150,000 原生行的输出边界限制。OI-003 未闭合前只接受明确 allele，不按宿主推断默认面板。

两个原生 CLI 分别接收同一全长 FASTA：MHC-I 明确生成 8–14mer，MHC-II 生成 15mer；实测 `Pos` 为 1-based。解析器将短安全 Identity 回连完整序列 SHA，按包内 `allelenames` 接受 MHC-I 原生展示名（如请求 `HLA-A02:01`、输出 `HLA-A*02:01`），只消费原生 `BindLevel`，不以项目阈值重算；MHC-II inverted 行保留计数但不形成 hit。结果区分 `raw_predictions_unreviewed`、`partial_unreliable` 与全部 `unreliable`，始终保持 `usable_for_pipeline=false`、`automatic_handoff=false`、`NOT_DEPLOYED`。

[Worker/解析器](<../../src/t01_phase1_real/development/netmhc/worker.py>)、[资产收据](<../../src/t01_phase1_real/development/netmhc/assets.json>)、[镜像构建记录](<../../discovery/t01-phase1-real/w2/netmhc-integration-20260907/environment/build.json>)、[针对性测试](<../../tests/test_netmhc_development.py>)与[验收脚本](<../../scripts/run_netmhc_acceptance.py>)可直接复核。[完成索引](<../../discovery/t01-phase1-real/w2/netmhc-integration-20260907/acceptance-r03/index.json>)含 12 个场景、251 份索引前文件和 167 项发布产物校验；r01/r02 是保留的未完成编排运行，不计 PASS。本包开发接入完成，OI-003、科学签收、目标复现和完整 W2 发布仍分别判断。

#### BepiPred 本机调用与接口

统一入口 [t01_runtime.py](<../../scripts/t01_runtime.py>) 的 `bepipred` 子命令登记 `t01.real.bepipred / N04`，复用现有 SQLite、run/job/attempt、幂等、事件、容器监督与 ArtifactRef。原 W1 Schema 保持原字节；[增量契约校验](<../../src/t01_phase1_real/development/contracts.py>) 仅增加该工具与节点组合，其他形状及状态规则不变，旧入口仍拒绝科学工具。

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
| 官方仓库 | [BepiPred-3.0](https://github.com/UberClifford/BepiPred-3.0/tree/98bedf2471e04766c981585180c20da7961c6804)，固定提交 `98bedf2471e04766c981585180c20da7961c6804`；[源码与哈希收据](<../../discovery/t01-phase1-real/w2/bepipred-integration-20260906/source-receipt.json>) |
| 模型/环境 | bp3 0.0.12.7、fair-esm 1.0.3、ESM-2 `esm2_t33_650M_UR50D` 与 contact regression；PyTorch 2.5.1+cpu、NumPy 1.22.0、Pandas 1.4.3、Plotly 5.8.0、Python 3.10.21。[104 项固定资产](<../../src/t01_phase1_real/development/bepipred/assets.json>) 包含源码、许可、模型、安装报告与专家原件 |
| 镜像 | `sha256:e1aff495e254ca4da513286f4ada0e1e0a071a2ffd9e0bc8ae3d2e6c91384149`；[构建、安装及系统报告](<../../discovery/t01-phase1-real/w2/bepipred-integration-20260906/environment/build.json>)。依赖准备允许下载，推理完全禁网 |
| 原包调用 | 未修改官方 CLI；vt_pred，threshold=0.1512，top=0.2，rolling_window=9，CLI 默认 add_seq_len=false（BP3C50IDFFNN 五折）。模型选项与原包参数不是项目科学放行决定 |
| 原始结果 | raw_scores 每位包含 sequence_position（1-based）、residue、ensemble_probability、linear_epitope_score；两列原值分别保存。raw_record 保留 CSV 列名、阈值/Top20% FASTA、原包参数、嵌入形状和五折身份 |
| 原包行为 | 概率为五折正类概率均值；平滑为 `convolve(..., ones(9), same)/9`，两端零填充。Top20% 数量用 Python round，并列沿输入顺序；原包分类比较 ≥阈值（float32），项目峰定义为严格 >，不将原包 FASTA 直接认作项目峰 |
| 后处理 | postprocessing.status=review_required / OI-026；linear_scores、linear_peaks、conf_scores、conf_peaks、epitope_map 均为 null。原包分数列、平滑、Top20%、桥接及模型特征分支的科学签收条件集中在 OPEN_ITEMS；不伪造 DiscoTope 或 E2 |
| 错误/资格 | A3 执行/产物不可用时 failed/cancelled/timed_out、raw_scores=null、A3_UNAVAILABLE_HALT；不可伪装为无表位成功。有效原始结果为 raw_scores_unreviewed，DEVELOPMENT_UNREVIEWED、usable_for_pipeline=false、automatic_handoff=false、scientific_signoff=null、NOT_DEPLOYED |

同一 `--root` 下使用 `get / result / events / execution --job-id …` 查询；`artifact --job-id … --artifact-id … --output …` 校验 hash 后导出到新文件；`cancel / retry --job-id … --key …` 控制任务，显式重试后用 `dispatch` 启动；`recover --job-id …` 处理监督进程中断。容器停止确认先于终态，缺失/损坏产物或收据不得恢复为有效原始分数。

每次输出回连请求/序列 hash、run/request/job/attempt/execution/profile；原包输出清单、嵌入、五折观测、原 CSV、三份 FASTA 和原生 HTML 分别发布。宿主校验列、长度、逐位字母与安全 ID、有限概率、五折与平滑一致性、分类产物及环境身份。HTML 原件是引用 Plotly CDN 的片段，作为未渲染原始产物保存；命令行分数查询不依赖该网页。

输入失败事实：[原包含 `*` 的输入](<../../discovery/t01-phase1-real/w2/bepipred-integration-20260906/raw-runs/invalid-star/index.json>)退出 1；[8 aa 原包输入](<../../discovery/t01-phase1-real/w2/bepipred-integration-20260906/raw-runs/short8/index.json>)退出 0，但原始概率 8 位、窗口平滑 9 位，CSV 只保留 8 行。项目仍在准入前拒绝 <9 aa，并在解析时要求原始观测/分数/输入等长；不把退出 0 等同于支持。9 aa 与 1022 aa 的整长回连仅为本机开发覆盖事实。

许可按来源分别保留：仓库 README 声明学术非商业条件，bp3 wheel 携带 MIT 文本，ESM 携带 MIT 文本；不以 wheel 元数据覆盖仓库/数据条款，不据本机开发验收授予商业或目标发布资格。原包示例属于随包参考，不是独立留出测试集。

[Worker/解析器](<../../src/t01_phase1_real/development/bepipred/worker.py>)、[针对性测试](<../../tests/test_bepipred_development.py>)与 [验收命令](<../../scripts/run_bepipred_acceptance.py>)可直接执行。全组验收使用 `--root <新的绝对目录> --batch <W2 discovery 下的新目录>`，真实原包输入、工程边界输入及受控故障分列；实际结果与统一批次索引见 STATUS。


## W3 N07–N09 糖基化、保守性与功能域

#### N09 本机调用与接口

[N09 实现](<../../src/t01_phase1_real/development/domains>)、[参考测试](<../../tests/test_domains_development.py>)与[工程验收脚本](<../../scripts/run_domains_acceptance.py>)使用独立 `t01.real.domains / N09` 注册，复用同一 SQLite 任务、幂等、事件、ArtifactRef 与停止/恢复机制。N09 在可信本机 Python/Biopython 1.88 中计算，不联网；真实 DeepTMHMM 和结构上游沿用各自固定禁网镜像。工程注释中的 reviewed 标记仅用于测试规则路由，所有结果保留 `DEVELOPMENT_UNREVIEWED / usable_for_pipeline=false / automatic_handoff=false / NOT_DEPLOYED`。

从已完成批次的真实拓扑来源运行一条命令（引用 ArtifactRef 必须与 N09 任务属于同一个 `run_id`；新 key 创建新 N09 任务）：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\domains-acceptance-r04 --domains-database-root D:\work\蛋白智能体\discovery\t01-phase1-real\w3\domains-integration-20260907\acceptance-r04\databases domains --input D:\work\蛋白智能体\discovery\t01-phase1-real\w3\domains-integration-20260907\acceptance-r04\requests\documented.json --key documented --run-id <上游任务所属 run_id> --run
```

上述 `documented` key 回读已执行结果；`--run-id` 必须取该 ArtifactRef 的 `run_id`，不带上游引用的 N09 请求可省略。验收末尾会受控篡改上游拓扑发布副本以验证守卫，因此该批次结束后不再用旧上游创建新任务，原始拓扑证据保存在批次中。需要全新可调用上游时运行下方完整新批次，或在新运行根实际提交 DeepTMHMM 后构造对应 ArtifactRef；不可只复制 JSON 到另一个任务库冒充已登记来源。

请求精确字段为 `protein_sequence/user_sequence_id/organism_name/database_id/database_manifest_sha256/entry_id/parent/topology_input/structure_input/user_annotations/timeout_seconds`。序列为严格 AA20 大写 1–20000 aa；上游另遵守各自输入域。`entry_id` 可为空或显式 accession；查询仅采用序列与 organism 精确匹配，多命中不自动择一，不作同源注释转移。`parent` 为空或 `{id,offset,sequence}`，必须验证成熟序列等于原序列的声明切片。用户标注使用成熟坐标 `{type,start,end,note}`，逐条保留 `user_annotation / user_high`。

`topology_input/structure_input` 均为 `{state,artifact,reason_code}`，区分 `not_provided/available/upstream_unavailable`。真实来源核对任务、尝试、登记、hash、同序列及成功/失败身份；结构进一步回连原文件字节及已验证映射/RSA，N09 不接受请求自报 RSA 数组。已在成熟序列上计算的拓扑和结构坐标不再次偏移。真实拓扑 TM/signal 保留为 source-verified observation；其 S-16 confidence 未定义时保持 null，不自行赋高置信功能域。

本机工程注释包以环境根 + 登记 ID + manifest hash 定位，固定 N09 用途、资格、来源/版本/日期/许可/引用及 payload hash。当前包包含 `manifest.json` 与 `entries.json`，后者最多 500 条 UniProt-shaped 条目（每条最多 500 features），不代表服务器大库适配已完成。原 feature 的 `type/description/location` 和每条 `coordinate_spaces` 一起保存。精确/不确定坐标分开；成熟 Chain 不减 offset；parent feature 依 ToolSpec 减 offset−1，并记录裁剪/丢弃。具体校验见 [policy.py](<../../src/t01_phase1_real/development/domains/policy.py>)。

后端实现 12 类 L1、3 类 L2 关键词与 5 类独立重叠 motif 扫描。已明确重叠按 overlap/min(length)≥0.80 去重，原文全局/排序语义发生分歧时记录复核。TrEMBL 未定义降级档、不确定坐标、多类别冲突、拓扑缺省等均保留原始事实及原因，不变为无功能域科学结论。

结构分支回连现有映射与 FreeSASA 资格守卫；开发计算 Cys Cβ 距离 <6 Å、链间重原子距离 <4.5 Å、packing/contact 分量与接触图。Gly 无 Cβ 不补 CA，归一化零分母为 null。network 两种接触计数解释均记录，仅结果一致时输出开发布尔值；三态条件按 S-16 实现，操作数不足时不猜状态。无结构、无 RSA、RSA 出域和映射不唯一分别记录，缺失或出域 RSA 不生成 burial。正式 `core_map` 继续 null，开发分量仅在 `structure_assessment.components` 提供；OI-006 与 [OI-031](<../project/OPEN_ITEMS.md#n09-注释与结构分支的具体待确认项oi-031>) 控制相应科学消费。

复核及全新批次命令（root/batch 必须不存在，完成索引不可覆盖）：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_domains_development.py tests/test_homology_development.py tests/test_epitope_map_development.py tests/test_glycosylation_development.py tests/test_structure_development.py tests/test_deeptmhmm_development.py -q
.\.venv\Scripts\python.exe -X utf8 scripts/run_domains_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\domains-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w3\domains-acceptance-new
```

#### N08 本机调用与接口

统一入口以 `t01.real.homology / N08` 接入原任务库；[实现](<../../src/t01_phase1_real/development/homology>)、[验收脚本](<../../scripts/run_homology_acceptance.py>)与[参考测试](<../../tests/test_homology_development.py>)独立于旧 Mock/S07。固定镜像包含 MMseqs2 `14-7e284+ds-1+b2`、MAFFT `7.505`、原 NCBI BLAST+ `2.17.0+` 的二进制与共享库；镜像 ID、版本实测、来源与包内许可见 [资产收据](<../../src/t01_phase1_real/development/homology/assets.json>)。构建安装工具时联网，序列执行一律 `network=none`、根只读、2 CPU/4 GiB、独立容器槽。MMseqs2 原生工作流要执行其生成的 shell 脚本，因此仅 N08 容器内 `/tmp` 允许执行；不授予宿主额外命令能力。

本机一条命令提交并取得真实结果（示例数据已标为工程用途，重复 key 返回原任务；新运行使用新 root/key）：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\homology-local --homology-database-root D:\work\蛋白智能体\discovery\t01-phase1-real\w3\homology-integration-20260907\acceptance-r05\databases homology --input D:\work\蛋白智能体\discovery\t01-phase1-real\w3\homology-integration-20260907\acceptance-r05\requests\documented.json --key n08-example-001 --run --wait 60
```

请求精确字段为 `protein_sequence/user_sequence_id/organism_name/protein_name/database_id/database_manifest_sha256/source_filter/group_by/sequence_weighting/query_range/timeout_seconds`。序列要求严格 AA20 大写、9–20000 aa；字符不替换。9 aa 工程集已观察到原生 MMseqs2 无法提取 k-mer 并失败，准入不保证所有长度可执行，失败不作空成功。`source_filter=wild_type`、`sequence_weighting=off`；`group_by=subtype|host_species|both`；`query_range=null` 或 1-based 闭区间；超时 1–900 秒。CLI 同时提供 `get/result/events/artifact/cancel/retry/recover`，使用同一 job/attempt/ArtifactRef 生命周期。

数据库通过操作者配置的绝对本地根、登记 ID 与 manifest SHA-256 解析，请求不能指定文件路径或命令。当前开发包每库最多 500 条，每条最多 20000 aa，包含 `sequences.fasta`、`annotations.json`、`manifest.json` 三个文件，适用于本机工程验收，尚非大库服务器适配。manifest 固定 N08 用途、`ENGINEERING_FIXTURE` 或 `TARGET_DATABASE_UNREVIEWED`、来源/版本/日期/许可/引用与逐文件大小/hash；注释精确字段及完整验证见 [policy.py](<../../src/t01_phase1_real/development/homology/policy.py>)。前后两次核验、容器内复核、原数据副本和结果回读互相绑定；N03 数据库不能自动用于 N08。

收集按 organism/protein 原始注释精确匹配，分离疫苗株并保存 lab/unknown 排除事实，对 wild 输入全集一次 MMseqs2 `--min-seq-id 0.99 --alignment-mode 3` 去冗余，其余采用固定版默认参数；保留所有 cluster 成员及代表原注释，不生成虚构谱系。少于 20 条时真实本地建库/BLAST 补充检索，保留原始命中和索引 hash，因补充准入科学阈值未定义，`automatic_admission=false`，不冒充 NCBI nr 或联网补齐。

MAFFT 全局执行一次，查询序列作为单独坐标锚点，明确不计入 N_eff、熵、gap 或分组统计。S-14 与各组复用同一 MSA/原列；输出逐列熵、分数、分级、不可靠位置、MSA 列↔查询残基映射及查询逐位数组。组内结果分别保存；混合分型全局值仅为诊断，不代替目标分型选择。置信度不足独立分层证据时降档，工程标签不构成科学谱系。S-15 已明确连续段按三档提取，输出固定位置与逐档历史；无段为 `quality_flag=failed / regions=[] / fixed_positions=[]`。全 gap、不可靠位点、短段桥接及未知分型相关歧义分支保持 null/复核；区间查询返回 mean/min/max，未定义的整体 class 保持 null。具体冲突、主责和关闭证据集中在 [OI-030](<../project/OPEN_ITEMS.md#n08-同源保守性的具体待确认项oi-030>)。

所有输出为 `G0_REAL_OUTPUT / DEVELOPMENT_UNREVIEWED / usable_for_pipeline=false / automatic_handoff=false / NOT_DEPLOYED`。本机工程参考、原生失败、故障注入与服务器目标验收分别标识。整包 N08 的目标库适配/实跑和科学签收仍需完成，不因本机链通而关闭。

复核与新批次命令如下；新批次必须使用尚不存在的 root 和 batch，已完成索引不覆盖：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_homology_development.py tests/test_blast_development.py tests/test_epitope_map_development.py tests/test_glycosylation_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_homology_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\homology-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w3\homology-acceptance-new
```


## W4 N10 可开发性、设计 Gate 与 WT 交付

### N10 本机调用与接口

请求为严格 JSON：`protein_sequence`、`user_sequence_id`、`structure_input`、`target_ph`、`target_ph_range`、`dimension_weights`、`timeout_seconds`。无结构时 `structure_input={"state":"not_provided","artifact":null,"reason_code":null}`；有结构时必须传统一结构任务发布的同序列 result ArtifactRef，不能直接自报路径或数值。`dimension_weights` 可为 null；若提供，必须包含六个维度，但当前仍不能生成 overall。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\developability-new developability --input D:\path\n10-request.json --key n10-example --run --wait 60
```

普通复核与全新验收批次：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_developability_development.py tests/test_domains_development.py tests/test_glycosylation_development.py tests/test_epitope_map_development.py tests/test_deeptmhmm_development.py tests/test_structure_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_developability_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\developability-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w4\developability-integration-new
```

第二条使用尚不存在的运行根和 W4 批次，实际执行结构链、AGGRESCAN3D 结构路径及 PROPKA，并覆盖 PDB/mmCIF、无结构、低质量/RSA 异常、明确权重、故障、生命周期和来源篡改；不能覆盖完成批次，且要求 Docker Desktop Linux daemon 可用、上述固定 A3D digest 已在本机。当前完成证据为 [acceptance-r14](<../../discovery/t01-phase1-real/w4/developability-integration-20260908/acceptance-r14/index.json>)：13 个 N10 场景、5 个真实结构上游、343 份索引前文件与 265 项发布产物核验，验收 profile 与现行实现一致，完整绑定 A3D 镜像/配置/原生输出及 PROPKA 源码、`propka.cfg`、依赖清单与 GUI 公式来源，对三条实际曲线完成 41 点逐点对标并全部 PASS；`propka_gui_benchmark_complete=true`、`propka_flat_curve_weighting_complete=false`，`N10_S36A_S37_STRUCTURE_S38_DEVELOPMENT_S39_S40_PARTIAL_ENGINEERING` 为 PASS。r11 因官方 A3D 0.9.11 的 `-C` 读取短 `END` 行触发 `IndexError` 中止，r12 因去掉 `END` 后工具重复末原子并令 FreeSASA 输出 `N/A` 中止；r13 闭合目标链投影和标准 `END`，r14 在相同 A3D 边界上新增 PROPKA GUI 对标，未放宽解析和来源守卫。r08、r09 因 Docker daemon 尚未可用在 normal-cif 前置阶段中止；更早未完成/前版证据继续保留，均不替代 r14。所有结果仍为开发未签收、不可科研消费、`NOT_DEPLOYED`。

### Gate 与 WT 草稿本机接口

已新增独立 `t01.real.wt_draft / N18` 工程 Worker，复用统一 SQLite、幂等、事件、取消、显式重试、恢复及 ArtifactRef；`N18` 登记只表示本地草稿组装，不表示完整 N18 已交付。执行不调用模型或网络。后端按 R-57 计算业务 Gate，并与固定关闭的科学发布 Gate 分开：

| 业务状态 | 路由与原因 | 下游边界 |
|---|---|---|
| `SUITABLE_FOR_DESIGN` | `DESIGN_PATH_REVIEW`；膜/低质量确认后保留限制或 caveat | 工作流仍以 `SCIENTIFIC_CONSUMPTION_NOT_RELEASED` 阻止 N11–N14，不自动生成候选 |
| `NOT_SUITABLE_FOR_DESIGN` | `WT_PATH_REVIEW`；`membrane_expected_poor` 或 `skipped_low_confidence` | 本地交付结果为 `WT_ROUTE_REVIEW_REQUIRED`，不是正式 WT 交付 |
| `INPUT_INSUFFICIENT_OR_NOT_EVALUATED` | `HOLD_FOR_INPUTS` 并列出缺失的拓扑、结构质量，或明确包膜病毒场景下缺失的功能域事实 | 本地交付结果为 `DESIGN_INPUTS_UNAVAILABLE`，缺值不等同不适合 |

膜判定逐条执行原件四条件：TM 数≥3；有 TM 且胞外长度<100 aa；有 TM 且胞外比例<0.25；或至少一条 TM、病原体为 `virus_enveloped` 且 N09 `functional_domains` 含 `TMhelix`。`pathogen_type=null` 按原件表示第四条件不触发；若明确为包膜病毒而 N09 功能域事实缺失，则保持输入不足。膜蛋白未给 `membrane_design_confirm` 时进入 WT 复核；确认后仅允许胞外区域，TM/胞内区域固定。结构质量为 low 且未给 `low_conf_design_confirm` 时进入 WT 复核；确认后继续设计但仍保留 `skipped_low_confidence` quality flag 与 caveat。N09 仅有 confidence=null 的拓扑 observation 不冒充 `functional_domains`。

请求字段为 `protein_sequence`、`user_sequence_id`、`host_species`、`organism`、`upstream`、`timeout_seconds`，可增加严格对象 `design_context={pathogen_type,membrane_design_confirm,low_conf_design_confirm}`；省略时兼容为 `{null,false,false}`。`pathogen_type` 只接受 `virus_enveloped / virus_non_enveloped / bacteria / null`，两项确认必须是布尔值。序列为精确大写 AA20（1–20000 aa，工程容量边界）；物种可为明确输入字符串或 null，超时为 1–60 秒。`upstream` 必须显式列出 `structure/topology/blast/bepipred/netmhc/epitope_map/glycosylation/homology/domains/developability` 十个槽位，分别对应已登记 N01–N10 生产者。缺失槽为 null；提供时为 `{"job_id":"实际任务 ID","artifact":实际 result/diagnostic ArtifactRef 或 null}`。只有任务确无结果/诊断文件时 artifact 才能为 null，适用于排队、未启动取消或 preflight 失败。请求不接受自报状态、分数、签收、阈值或交接开关。

后端在准入、执行前及发布前复核同一运行根/授权 scope 内的任务与尝试、精确 ArtifactRef 登记、原请求序列、请求与结果 hash、结果 binding、历史执行 profile 和资格，以及上游全部发布原始产物的大小/hash。已提交后发生变化阻断执行或发布。历史产物按其记录的 profile 追溯，不要求它匹配修改后当前代码的 profile；不会重写旧结果。错误身份、错序列、哈希损坏返回明确 `FORBIDDEN/OUTPUT_INVALID/HASH_MISMATCH` 等错误，拒绝消费；合法缺失、失败、排队和未签收输入可以生成带阻断原因的草稿。

调用前将 `$runtimeRoot` 指向已有上游任务的本地运行根，`$n10JobId`、`$sequence` 取该任务的真实 ID 与原序列。CLI 自动解析其精确 ArtifactRef，其余槽位默认 null；也可通过其他 `--<槽位>-job-id` 参数绑定更多上游，或 `--input` 传完整严格 JSON：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root $runtimeRoot wt-draft --sequence $sequence --developability-job-id $n10JobId --pathogen-type virus_enveloped --membrane-design-confirm --key wt-local-example --run --wait 30
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root $runtimeRoot result --job-id $wtJobId
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root $runtimeRoot artifact --job-id $wtJobId --artifact-id $draftArtifactId --output D:\path\wt-draft.json
```

第一条返回 `job` 和 `result`，从中取 `$wtJobId`；`result.raw_artifacts` 中 `path=output/wt-draft.json` 对应 `$draftArtifactId`，第三条按该发布引用导出并校验。原请求、FASTA、上游请求/结果快照、source receipts、observation 与草稿均可通过统一 artifact 查询，不能用任意文件路径冒充上游来源。`get/events/execution/cancel/retry/recover` 沿用统一入口。


## W5 N11–N12 设计、验证与受控重算

## N11 本机调用与接口

统一入口新增 `proteinmpnn`，登记 `t01.real.proteinmpnn / N11`，复用现有 SQLite、ArtifactRef、事件、容器监督与恢复，不从 WT 草稿或未签收 Gate 自动触发。后端实现位于 [proteinmpnn](<../../src/t01_phase1_real/development/proteinmpnn/policy.py>)。

请求为严格 JSON，字段全部显式提供：

| 字段 | 本包工程口径 |
|---|---|
| `protein_sequence` / `user_sequence_id` | 精确 AA20 大写序列及可追溯输入标签；1–1000 aa 是本机工程准入界限 |
| `structure_artifact` | 同一运行根/访问域内成功的 `t01.real.ingest_structure` 结果 ArtifactRef；复核任务/尝试、请求、同序列、原始结构、映射和输入事实 hash |
| `constraints` | `purpose=ENGINEERING_EXPLICIT_MASKS`、非空 `source_id`、`fixed_positions`、`restricted_positions=[{position,allowed_residues}]`、`open_positions`；1-based 全长逐位恰好覆盖一次，不允许缺省开放 |
| 固定与受限集合 | FIXED 非空；每个 RESTRICTED 的允许集为包含 WT 的明确 AA20 真子集。WT-only 合法；不从 BLOSUM、表位、core_map 或未签收科学输入自动合成 |
| `n_designs` / `sampling_temperature` / `seed` | 工作流标准调用显式传 `24 / 0.1 / 非零正整数`；开发计数支持 1–24，温度固定 0.1 |
| `timeout_seconds` | 显式 1–900 秒；容器硬期限和宿主监督共同控制。每个输入最多 8 条单字符链、总上下文最多 1000 aa |

结构载体须能唯一映射到目标链，具有完整标准 N/CA/C/O 骨架；不自动选择替代构象、不归一化非完整占有率、不补缺原子。PDB/mmCIF 从原子账本构造只含骨架的独立 PDB，要求坐标能无损表示为三位小数；原结构保持原字节，逐原子比较官方 parser 实际读入的坐标。目标链按序列映射排序，其他蛋白链全部固定；转换表保留 chain、原作者编号、iCode、原始 residue ID、工具 resSeq 和工具数组位置。FIXED 无法转换即拒绝；本包没有能在缺坐标时正确固定的旁路，RESTRICTED 遇同类问题也中止。

工具固定为官方 commit `8907e6671bfbfc92303b5f79c4b5e6ce47cdef57`、`vanilla_model_weights/v_48_020.pt`、MIT 许可，原源码/权重逐项校验官方 Git blob 和 SHA-256；[资产登记](<../../src/t01_phase1_real/development/proteinmpnn/assets.json>)保存九份文件及固定镜像身份。镜像为 `sha256:5b6baa8ebc5660bd3de9cf8b6d1694c7de35fadd23fea6cd7a8352a536e3f3af`，Python 3.10.21、PyTorch 2.7.1+cu128、CUDA 12.8、NumPy 1.26.4；[环境收据](<../../discovery/t01-phase1-real/w5/proteinmpnn-assets-20260908/environment.json>)保留依赖安装来源/hash、完整 pip/dpkg 版本和禁网 GPU 张量实测。构建时下载依赖；实际生成固定 `network=none`，根文件系统/源码/权重/输入只读，输出独立可写，GPU device 0、2 CPU、4 GiB 主存、128 PID，无 CPU 或联网回退。资源上限是工程准入策略，不是最大长度性能保证。

固定版 `--help` 与实际 featurizer 均确认逐位点 `--omit_AA_jsonl` 硬排除；不使用 bias 参数。实际格式为 `{"target":{"A":[[[2],"禁止残基串"]]}}`，固定位置格式为 `{"target":{"A":[1]}}`；数字是解析后的链内位置。由于工程 PDB 的 resSeq 特意重编为 1..L，工具 resSeq 与数组位置相同，原作者编号则留在转换表中。C15 §4 的原编号/示例差异与后续科学签收见 [OI-002/015 对齐记录](<../project/OPEN_ITEMS.md#n11-原工具坐标与权限边界oi-002015>)，不修改专家原件。

成功结果为 `generated_unreviewed`，`generation.records` 保留真实样本数、原生 `score/global_score/seq_recovery`、1-based mutations、`is_wt` 和 `duplicate_of_sample`，不去重凑数。校验原生 FASTA 与全链采样张量一致、FIXED 不变、RESTRICTED 允许集及禁止残基概率为零、非目标链不变，并从保存的逐位 log probability 回算原生分数；任何不一致都隔离整组输出。没有可设计位置时只执行原生解析/掩码审计，返回 `not_generated_no_designable_positions`、0 条及明确原因，不声称调用生成器。

失败结果为 `unreliable`，`generation=null`，保留机器错误、复核原因与原始输出；取消/超时确认实际停止后发布。恢复核验原执行收据/清单，不重跑同一个 attempt；显式 retry 创建新尝试。所有结果固定 `design_permissions=null`、`formal_candidates=null`、`scientific_gate=NOT_EVALUATED`、`usable_for_pipeline=false`、`automatic_handoff=false`、`NOT_DEPLOYED`，原生 ProteinMPNN 分数不替代 ESM-IF1 或候选排序。

### 已验证调用

以下一条命令使用 r02 运行根中已登记的正常 PDB 结构上游，另建工程任务；请求文件显式包含 24、0.1、seed 17 与逐位掩码。相同 key、相同字节幂等；换输入须换 key。已验收 CLI 的原始参数与输出见 [调用记录](<../../discovery/t01-phase1-real/w5/proteinmpnn-integration-20260908/acceptance-r02/cli/documented.json>)。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\proteinmpnn-acceptance-r02 proteinmpnn --input D:\work\蛋白智能体\discovery\t01-phase1-real\w5\proteinmpnn-integration-20260908\acceptance-r02\requests\normal-pdb.json --key w5-n11-local-example --run --wait 180
```

只读查询已完成、未用于篡改测试的正常 PDB 结果：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\proteinmpnn-acceptance-r02 result --job-id t01p1r-job-8d4419d5da9b4b418680f154f734534b
```

同一入口支持 `get/events/execution/artifact/cancel/retry/recover/wait`；控制操作各用独立幂等 key。全新验收命令见 [RUNBOOK](<RUNBOOK.md#w5-n11-proteinmpnn-独立工程接入>)，不得覆盖 r02。

## N12 本机调用与接口

统一入口 `esm-if1` 登记 `t01.real.esm_if1 / N12`，复用任务库、ArtifactRef、事件与 GPU 容器监督。后端 [source](<../../src/t01_phase1_real/development/esm_if1/source.py>)重新验证真实 N11 原生记录、硬约束、结构字节和坐标映射；[result](<../../src/t01_phase1_real/development/esm_if1/result.py>)复核官方 parser 实际读入的 N/CA/C、逐残基 loss、平均范围、模型调用数和输出清单。

请求是字段全部显式提供的严格 JSON：

| 字段 | 工程接口 |
|---|---|
| `protein_sequence` / `user_sequence_id` | 精确 WT AA20 序列（1–1000 aa）及来源标签；与 N11 请求完全一致 |
| `structure_artifact` / `n11_artifact` | 同运行根内已登记成功结果的完整 ArtifactRef；核验任务、尝试、请求、大小/hash 和原生输入输出，结构引用须与 N11 一致 |
| `sample_numbers` | 明确选择原 N11 样本号，唯一整数 1–24，实际存在且保留请求顺序；`[]` 合法，明确不打分 |
| `baseline_artifact` | 首次为 `null`；复用仅接受当前执行 profile 下成功 N12 结果的完整 ArtifactRef，不接受浮点基线 |
| `timeout_seconds` | 整数 1–900；硬期限与宿主停止确认共同控制 |

结构支持域继承 N11 的完整标准骨架、唯一目标链、最多 8 链/总上下文 1000 aa 和可无损投影坐标。固定官方 `load_structure/extract_coords_from_complex` 解析全部蛋白链；目标链放首位，链间填充 10 个 NaN 坐标作为官方上下文分隔符。其他链参与骨架上下文，分数平均仅覆盖目标链全部残基；分隔符不进入分母。缺原子/映射异常不走补坐标旁路。

工具固定为 [官方 ESM 实现](https://github.com/facebookresearch/esm/tree/2b369911bb5b4b0dda914521b9475cad1656b2ac/examples/inverse_folding) commit `2b369911bb5b4b0dda914521b9475cad1656b2ac`、模型 `esm_if1_gvp4_t16_142M_UR50`；[资产登记](<../../src/t01_phase1_real/development/esm_if1/assets.json>)保存 36 份原源码/许可文件和权重的大小/SHA-256，源码另核验官方 Git blob。权重为 1,700,450,121 bytes，SHA-256 `be4ba36edec22a9bfaa4946ff6b2815f1f19d8a3d7e0eada8b796d5a0eae9fd4`；源许可 MIT，保留原件。

固定镜像 `sha256:926d4619df9759cd2417dcc9056b7bd648dca1d2adf15631aaad2e84a88d39cc`，Python 3.10.21、PyTorch 2.7.1+cu128、CUDA 12.8、NumPy 1.26.4、Biotite 0.39.0、SciPy 1.15.3、torch-geometric 2.6.1；[环境收据](<../../discovery/t01-phase1-real/w5/esm-if1-assets-20260908/environment-r01.json>)保存完整 pip/dpkg 版本、安装来源/hash、GPU 与原生 API 对标。构建依赖时联网，实际打分 `network=none`，GPU 0、2 CPU、6 GiB 主存、128 PID，只读源码/权重/输入和容器根，独立输出；无联网或 CPU 回退。实际模型参数 141,662,150，eval/float32、seed 17、禁用 TF32。官方本地 checkpoint 加载使用 PyTorch `safe_globals([argparse.Namespace])`，未修改官方源码或关闭受限加载器。

每条序列调用一次官方 `get_sequence_loss`，保留逐位负对数似然和 padding mask，按全目标链负均值回算原始有符号分数。与官方 `score_sequence` 的独立数值对标差为 `4.23855e-7`，工程容差 `1e-6`；探针的 2 次调用只作 API 对标，生产批次基线为 1 次。原件的“伪似然/越接近 WT”描述与原工具条件自回归似然的差异见 [OI-015/022 对齐](<../project/OPEN_ITEMS.md#n12-原生分数与完整验证边界oi-015022>)，不据此推断稳定性或完整验证资格。

基线签名绑定 WT 序列、原结构、投影骨架、映射/转换、目标链/上下文顺序、模型/源码清单、镜像、参数与执行 profile。首次每批计算一次；跨调用重新核验原始产物和逐位 loss 后复用，保留最初 `origin_job_id` 与直接来源。任何签名变化拒绝复用。负值基线不取反；零分母、NaN/Infinity 或无效 loss 均隔离，不裁剪原分数。

`scoring` 保留每条真实原始分数/突变与失败原因；`engineering_rules` 按 C18 存 `(variant-baseline)/abs(baseline)*100` 的 `delta_pct`。仅恶化严格超过 10% 才排除，恰好边界保留；只有全部正常打分样本均被排除时依次复评 15%、20%，保留 R-35 规定的历史及 `standard/relaxed/minimal`，不重新调用模型或生成器。若 20% 仍全排除，保留 `ALL_EXCLUDED_AFTER_20_PERCENT`；任务可成功打分而工程规则不通过。

单条打分失败为 null、`VARIANT_SCORE_FAILED`，其余仍可查询；全部失败任务为 `TOOL_FAILED`，该失败结果不能作为可复用基线源。空选择不加载模型、不计算基线，返回 `not_scored_empty_selection`。取消、超时、输出损坏与输入篡改按统一生命周期隔离；恢复消费原收据，不重跑同一 attempt。`validation/formal_candidates/mutation_burden` 固定 null，`structure_recheck.status=NOT_EXECUTED`，科学 Gate 未评估、不可科研消费、不可自动交接、`NOT_DEPLOYED`。

### N12 已验证调用

以下调用使用 r01 中未用于篡改负例的多链 N11 工程来源，新建独立打分任务；请求选原样本 1、2，同一 WT 骨架。相同 key/字节幂等，改变输入须换 key：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\esm-if1-acceptance-r01 esm-if1 --input D:\work\蛋白智能体\discovery\t01-phase1-real\w5\esm-if1-integration-20260908\acceptance-r01\requests\multichain-wt-identical.json --key w5-n12-local-example --run --wait 180
```

只读查询已完成、未被篡改的多链结果：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\esm-if1-acceptance-r01 result --job-id t01p1r-job-2bc386be715547288932f9fc9aa73dcc
```

统一入口另支持 `get/events/execution/artifact/cancel/retry/recover/wait`。原批 [CLI 打分与基线复用记录](<../../discovery/t01-phase1-real/w5/esm-if1-integration-20260908/acceptance-r01/cli/documented.json>)及查询输出已归档；其中 documented 运行根结果随后作为篡改负例，不能作为正常查询示例。完整验收必须使用新根/批次，见 [RUNBOOK](<RUNBOOK.md#w5-n12-esm-if1-独立工程接入>)。

## 权限与负担本机接口

新增统一入口 `design-audit`，工具 `t01.real.design_audit / N12` 代表合并的 S-27/S-28 本地工程审计，不替换 N11 生成器或 N12 ESM-IF1。实现位于 [design_backend](<../../src/t01_phase1_real/development/design_backend/policy.py>)，复用现有任务库、ArtifactRef、事件、幂等和本地计算停止/恢复机制。所有计算由后端执行；输出不自动提交 ProteinMPNN，不调用预测模型。

请求使用严格 JSON，字段全部显式给出：

| 字段 | 当前工程接口 |
|---|---|
| `protein_sequence` / `user_sequence_id` | WT AA20 大写序列，1–1000 aa，及非空来源标签；所有上游须同序列 |
| `upstream` | 固定八键：`structure/topology/epitope_map/glycosylation/homology/domains/n11/esm_if1`；缺失为 null，否则 `{job_id,artifact}`。artifact 是该任务实际发布的完整 result/diagnostic 引用；排队或无产物失败时显式 null |
| `user_regions` | `{start,end,permission,allowed_residues,source_id}` 数组；1-based 闭区间，permission 为 FIXED/RESTRICTED/OPEN。仅 RESTRICTED 可给 AA20 真子集，须包含区间各 WT 残基；null 表示采用固定 BLOSUM62 正分集合 |
| `objective` | `general/solubility/thermostability`，选择 C18 负担工程档值；本包仅 general 导出已有 ProteinMPNN 请求草稿，其他值不启动或部署任何生成器 |
| `epitope_policy` / `epitope_mode` | 本 profile 仅接受明确 PRESERVE；mode 为 both/bcell_only/tcell_only，后者才消费 N06 presentation_hotspots 作 RESTRICTED 工程证据 |
| `membrane_design_confirm` | 显式布尔值；true 且有真实拓扑时，TMhelix/inside 固定；不是科学 Gate 放行 |
| `sample_numbers` | 0–24 个唯一原 N11 样本号；空数组为明确不计算变体负担。没有可用 N11 时记录 `VARIANTS_UNAVAILABLE_NO_BURDEN_COMPUTED`，不伪造变体 |
| `timeout_seconds` | 本地计算期限 1–60 秒；保留现有 32 MiB 单产物及总发布数量上限，长序列不保证所有组合可在限额内完成 |

来源在提交、执行和发布前复核生产者、开发身份、请求/序列、任务/尝试、历史 profile 和全部发布产物大小/hash；缺失、未终态、失败、成功未签收分别留 receipt。N11 重新解析原生样本、硬掩码与分数，绑定其原 WT 结构和映射。N12 校验同 N11/WT、原始 observation、逐位 loss/均值、签名、历史模型/执行身份及 R-35 结果；历史 profile 保留原值，不改成当前版本、不重跑旧模型。成功执行仍不取得科学资格。

### 权限合成与掩码

`audit.permissions.per_residue` 每位记录自动约束状态、最终工程约束/权限、允许集合、逐项规则/来源路径/ArtifactRef、用户原指令和覆盖原因。非结构推断来源的高/user_high 功能域进入 HARD→FIXED，其余功能域进入 RESTRICTED；二硫键来源不按两端之间整段扩展。明确单亚型、中/高置信且不在不可靠位点中的保守分数按 ≥0.93/0.80–0.93 进入 RESTRICTED；无 mechanistic 生产者明确空，不把高保守升级为 HARD。低置信或跨亚型 pooled diagnostic 不消费为保守权限。

N06 明确 tcell_only 呈递区、已核验的 N07 20 aa 遮蔽证据和确认的膜拓扑按 S-27 处理。N06 E1 证据保留 SOFT；当前完整 OPEN 表达式的功能/核心/界面等操作数尚不齐，工程执行收紧为 RESTRICTED并记原因。全缺证据为 RESTRICTED；不把未知区域当 OPEN。N09 core_map=null 保持 null，不从组件回填 deep_core；结构推断二硫键/界面与 PTM 到 E2+ 边界的未决消费保持复核。具体原文差异与关闭证据见 [OI-001/002/006/007/008 收敛记录](<../project/OPEN_ITEMS.md#权限与负担工程剩余科学条件oi-001002006007008>)。

自动合成后应用显式用户区间。用户覆盖 HARD 为更宽权限时，保留 `constraint_override=true/non_standard=true`。同一位置相互冲突的用户权限/允许集不自行按列表顺序决定；保留自动结果、列出冲突位点并阻断整个掩码导出。未冲突 RESTRICTED 默认允许 `{WT}∪BLOSUM62正分替换`，C/G/P 允许 WT-only，绝不用 bias 代替硬排除。

`audit.n11_request_draft` 是显式工程请求草稿，来源 ID 绑定审计请求 hash；`mask_conversion` 使用已交付 N11 无损骨架投影和 fixed/omit 机制，保留作者号/iCode/工具位置。空 FIXED、用户冲突、缺结构或映射失败返回 `mask_conversion_error`，不导出可执行草稿。`n11_comparison` 回查既有工程序列是否满足本次约束，仅报告差异，不撤改原 N11 记录。本包实际只运行官方 parser/featurizer 掩码探针，模型加载和候选生成均为 0 次。

### 六维负担与空值

`audit.burden_records` 按原样本号保存变体 diff、六维工程 `values`、逐突变化学分量、突变配对/边界距离和原因；`n12_scoring_record` 回连原 ESM-IF1 相对分数/判定，未打分样本明确标记。原 R-35 结果整体保留，`n12_disposition_changed=false`；新增负担不能令原全排除样本重新通过。

[固定标度与工程档值](<../../src/t01_phase1_real/development/design_backend/scales.json>)绑定源文件大小/hash，来源为 AAindex `KYTJ820101`、[IMGT Volume 表](https://www.imgt.org/IMGTeducation/Aide-memoire/_UK/aminoacids/IMGTclasses.html)、Biopython 1.88 原始 BLOSUM62 文件，以及 SOP S-28 电荷/极性定义。登记脚本核验原数值行；运行时只读固定文件，不联网下载。电荷 K/R=+1、D/E=−1、H=+0.1（pH 7 近似），极性集 RKDENQHSTY，四分量均逐突变绝对差累加，极性翻转仅作审计。

几何使用同一 WT 的**原始完整原子账本**，不用 ProteinMPNN 的骨架投影计算侧链距离，也不生成变体侧链。WT Gly 使用 Cα，其他残基严格使用 Cβ；缺 Cβ 不替代为 Cα。聚集为距离严格 <10 Å 的突变对比例；严格 <5 Å 的对数 0/1/≥2 对应 LOW/MEDIUM/HIGH。无突变对时聚集为 0、风险 LOW；某对缺所需坐标时对应维度 null。

功能域/热点邻近取突变残基到区间端点残基的最小原子距离，≤5 Å 包含边界，位点在区间内按原件直接为 0 距离。原子不完整或端点/突变坐标缺失时不以剩余原子证明远离，结果 null。域来源未提供、失败、无确切命中/多命中或未评审置信处理未决时为 null；已完成且明确空区间才为 0。结构推断接触对不作为连续功能区间。当前 N06 正式抗原热点为 null，因此真实非零突变的表位邻近维保持 null，不借用呈递区替代。**零突变优先遵循原件：六维全 0 档、epistasis=LOW，即使域/热点未提供。**

工程档值按原件配置：general 的 count≤12、聚集≤0.5、功能/表位邻近≤0.3、epistasis≠HIGH；solubility 仅 count≤15，thermostability 仅功能邻近≤0.5。化学超档是任一单突变疏水差>4.5、体积差>100 Å³ 或电荷差>1，非累计和比较。`engineering_thresholds` 分别列已知超档和不可用维度；有已知超档时 aggregate=true，全部可算且未超档才为 false，有未算维度且无已知超档时为 null。该三态工程摘要不写入科学 Hard Filter。

外层 `design_permissions/mutation_burden/validation/formal_candidates` 均为 null，科学 Gate 未评估、不可科研消费/自动交接、`NOT_DEPLOYED`。完整 N11/N12/W5、结构复核和正式权限/负担继续按对应条件关闭。

### 权限与负担已验证调用

以下命令复用 r02 中已核验的历史 WT、24 条 N11 工程序列及 N12 记录，仅运行本地后端审计。相同 key/输入幂等，改变输入须换 key：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\design-backend-acceptance-r02 design-audit --input D:\work\蛋白智能体\discovery\t01-phase1-real\w5\design-backend-integration-20260908\acceptance-r02\requests\historical-24-burden.json --key w5-design-audit-local-example --run --wait 60
```

只读查询未用于篡改负例的已完成结果：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\design-backend-acceptance-r02 result --job-id t01p1r-job-a6e588d5a9a84d06914ecbe585190485
```

统一入口另支持 `get/events/execution/artifact/cancel/retry/recover/wait`。[实际调用](<../../discovery/t01-phase1-real/w5/design-backend-validation-20260908/local-example-r01.json>)状态 succeeded、结果 `design_audit_unreviewed`；[只读查询](<../../discovery/t01-phase1-real/w5/design-backend-validation-20260908/local-query-r01.json>)通过。这两份补充记录不计入下面的 1037 份文件。验收中的 combined/documented 来源或结果随后用于篡改负例，正常重用请用上面的历史请求；完整验收须使用全新根与批次，命令见 [RUNBOOK](<RUNBOOK.md#w5-n12-esm-if1-独立工程接入>)。


## W6 N13–N15 变体复评、稳定性与排序

## 稳定性工具本机接口

当前完成口径为 **ThermoMPNN 与 FoldX 双引擎稳定性工具工程接入完成**；这只关闭本包工具开发与本机生命周期验收，不等于完整 N14/N17/W6、科学签收、目标复现或部署完成。

ThermoMPNN 固定官方 commit `2b04fd370e399911b1fa5848112cc9013f084110`、`thermoMPNN_default.pt` 和镜像 `sha256:3cbd3c12b792a8b344347e6e9171d03deb7c5a115a6c4b8af27b84847dfdd847`；源码、模型、ProteinMPNN 权重、依赖环境和镜像均登记 hash。该 commit 没有 C43 所写的 `v2_ssm.py --threshold 100` 接口，因此未伪造该参数：适配器原样调用官方 `analysis/custom_inference.py`，随后强制验证单体每个残基恰有 AA20 全集（含 WT 自身零值），缺行、重复、身份、符号、非有限值或 hash 异常整组隔离。

请求只接受以下精确字段：`protein_sequence`、`user_sequence_id`、同一运行根已成功登记的 `structure_artifact`、有来源的 `scan_positions`、`excluded_positions`、`scope_source` 和 `timeout_seconds`。原生工具仍计算完整单体 SSM；显式范围与排除只决定本次工程比较集合，不裁结构、不减少完整输出。结果保留原始 `ddg_thermompnn`、`kcal/mol`、作者 chain/resseq/iCode、0-based 原生位置和引擎内 rank；WT 自身行不排名，不与 FoldX 绝对值求平均，也不执行未签收共识筛选。

在同一绝对运行根中已登记结构后，一条调用与查询命令为：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\t01_runtime.py --root D:\absolute\runtime thermompnn --input D:\absolute\thermompnn-request.json --key thermompnn-explicit-scan-r01 --run --wait 300
.\.venv\Scripts\python.exe -X utf8 scripts\t01_runtime.py --root D:\absolute\runtime result --job-id <job_id>
```

R-39 按原件硬守卫：结构含多个蛋白链时返回 `R39_THERMOMPNN_MONOMER_ONLY`，保留来源与映射，但不裁链、不调用模型。发布结果固定 `DEVELOPMENT_UNREVIEWED / review_required / usable_for_pipeline=false / NOT_DEPLOYED`；不完成 N14、N17 或科学 Gate。

FoldX 使用同一入口，输入文件必须提供已登记的结构 ArtifactRef 与显式工程范围：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\t01_runtime.py --root D:\absolute\runtime foldx --input D:\absolute\foldx-positionscan-request.json --key foldx-positionscan-r01 --run --wait 300
.\.venv\Scripts\python.exe -X utf8 scripts\t01_runtime.py --root D:\absolute\runtime result --job-id <job_id>
```

请求 `mode=positionscan` 时只允许 `scan_positions`，请求 `mode=buildmodel` 时只允许显式 `variants`；两者均强制 RepairPDB，固定位置不可扫描/突变。PositionScan 结果保留有符号 `ddg_foldx`、`candidate_disposition`、引擎内 rank，confidence 固定为 `null`；BuildModel 结果保留 5 次运行均值、std 和 high/medium/low 参考分档。两种模式的原始 `.fxout`、修复结构、mapping、命令和运行清单均随任务追踪，科学消费与自动交接继续关闭。

[最终验收 r05](<../../discovery/t01-phase1-real/w6/thermompnn-integration-20260908/acceptance-r05/index.json>)包含 13 个任务场景和 12 项守卫；452 份索引文件、347 项发布产物及 28 份源码/配置快照经[独立只读复核](<../../discovery/t01-phase1-real/w6/thermompnn-validation-20260908/evidence-audit-r03.json>)一致。现有 9 aa 本地结构真实输出 180 行；明确排除 2、8 位后发布 140 行，其中 133 个非 WT 突变只做引擎内排名。覆盖真实重试、取消、超时、崩溃恢复、多链跳过、来源及发布产物篡改；r01–r03 为验收汇总断言修正前、r04 为补齐官方 README 所引 SVG 资产前的未完成工程记录，不计现行完成批次。

FoldX 用户包确认包含 5.0 ELF、`RepairPDB`、`BuildModel`、`PositionScan` 及伴随分子文件；压缩包 SHA-256 为 `841a33ed680ac195ef8f6ccee26620fba64dd5e92891bf49c359170aee1e81d2`，可执行文件 SHA-256 为 `5309d81c3f08b8405d172153aaf9792a244c06f98387c9d57a104302a9cef2cf`。依据用户声明登记为 `USER_ATTESTED_ACADEMIC_VERSION`，不把它等同于机器许可证明；[包盘点](<../../discovery/t01-phase1-real/w6/stability-assets-20260908/foldx-user-package-probe-r02.json>)与[资产收据](<../../var/t01-phase1-real/tool-assets/foldx-20270131/assets.json>)保留该边界。Docker Desktop Linux engine 已恢复为 29.5.3，WSL2 kernel 为 `6.18.33.1-microsoft-standard-WSL2`；无缓存离线重建镜像固定为 `sha256:66539e081922ce4c4fb504c9906feb64044ce668033e63fdc9299d020af8c851`，镜像标签绑定的基镜像 ID 为 `sha256:68d914ec641a0b69267ce65184d000a2bc3a9ee2590ab702b82250ab2385735a`。


### N14/N15 逐变体报告本机接口

统一入口新增 `variant-report`（`t01.real.variant_report / N15`）和只读 `variant-record`。请求严格限定 `protein_sequence`、`user_sequence_id`、`upstream`、`variant_source`、`foldx_bindings`、`timeout_seconds`，不接受调用方自行提供的分数、科学资格或筛选结论。

`upstream` 必须显式包含 `design_audit`、`foldx` 两个槽；每槽为 `null` 或 `{job_id, artifact}`，引用同运行根登记的精确结果／诊断 ArtifactRef。`variant_source=N11_DESIGN_AUDIT` 使用设计审计既定样本集合，递归核验原 N11、ESM-IF1 与权限／负担来源；有适用 FoldX 时用 `foldx_bindings=[{sample_number, variant_id}]` 显式连接，核验同 WT、同结构 ArtifactRef、目标链、作者编号/iCode、原生映射、序列 diff 和所有 hash。未绑定的分数不自动分配，重复链接、错序列/错结构/错产物拒绝。PositionScan 或 ThermoMPNN 单点分数不能充当多突变 BuildModel。

`variant_source=FOLDX_EXPLICIT_ENGINEERING` 专门审计已登记 FoldX 请求中的工程突变，要求 `design_audit=null`、`foldx_bindings=[]`；由真实请求重建变体序列并绑定五次原始 ΔΔG、均值/std、修复及突变结构。该路径明确不是 N11 候选，不据此宣称已有合格设计。来源失败仍保留请求中已知的变体及不可用原因。

后端逐条返回序列/hash、精确突变、原始样本身份、ESM-IF1 及原淘汰原因、权限违反、六维负担、BuildModel 原值与来源、工程 Hard Filter 和缺少的具体科学条件。已知工程排除成立时保留排除，即使其他字段缺失；无已知排除但输入未齐时为 `UNDETERMINED`，不变成科学通过。`constraint_override` 按实际突变位置单列 `non_standard_ids`，不提升资格；WT 审计总体 override 不扩散到未触及覆盖位置的变体。

| 计算字段 | 生产者／规则 | 本包消费边界 |
|---|---|---|
| ESM-IF1 / R-35 | N12 原生逐位 loss、同 WT 基线和原复评记录 | 重新核验，保留原 20% 后排除及其原因，不重新放宽 |
| 权限 / burden | N11 权限审计、S-28 六维与工程档值 | 计算有明确数值的工程排除；空维度与未签收单列，正式 Hard Filter 为 null |
| stability | C35 BuildModel 5 次、T-01 step19b | 精确连接并复算均值/std；有值时计算 `sigmoid(-ddg/2)` 工程归一值；不可用原因明确，不平均双引擎 |
| epitope / safety | N13、S-23 及变体 safety 生产者 | N13 未执行、适用变体安全结果缺失，禁止当作 false／通过 |
| devability.overall_score | 变体 S-40 六维重算 | N10 缺项和变体重算未完成，保持缺失 |
| Pareto / objective score | SOP v10.5 T-01 step20 四维方向、三档权重及扣分 | 仅独立 `SYNTHETIC_CONTRACT_FIXTURE` 验证；真实报告因输入未齐关闭。允许的无结构表位中性值与“未执行 N13”严格区分 |
| 前20/40池、并列、SC-10、正式交付 | OI-009/010/011/022 与完整科学依赖 | 不计算最佳候选、不发明池或并列规则、不触发正式 WT／Agent C |

完整报告通过 `result --job-id` 查询；单条通过 `variant-record --job-id <报告任务ID> --id sample-1` 查询，返回报告 binding 和该条完整记录，发布 hash 异常拒绝回读。提交与执行命令：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\absolute\runtime variant-report --input D:\absolute\variant-report-request.json --key w6-report-new --run --wait 60
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\absolute\runtime result --job-id <报告任务ID>
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\absolute\runtime variant-record --job-id <报告任务ID> --id sample-1
```

### N13 表位保护本机接口

新增 `epitope-protection`，登记 `t01.real.epitope_protection / N13`。输入是已登记的基准逐变体报告与逐条明确的两侧来源，不接收调用方自报的科学保护结论、RSA 数组、热点或几何分数。基准报告必须尚未回连 N13，避免报告循环依赖；可选择其中部分或全部变体。请求格式：

```json
{
  "protein_sequence": "原始WT序列",
  "user_sequence_id": "工程配对说明",
  "upstream": {"base_report": {"job_id": "原报告任务ID", "artifact": "原报告完整ArtifactRef对象"}},
  "pairs": [{
    "variant_id": "sample-1",
    "wt": {"structure": null, "epitope_map": null, "domains": null},
    "variant": {"structure": null, "epitope_map": null, "domains": null}
  }],
  "timeout_seconds": 60
}
```

示意中的 `artifact` 须替换为完整 ArtifactRef 对象。每个非 null 侧来源同样为 `{job_id, artifact}`，可引用已成功结果或失败诊断；缺失和失败分别披露。WT 序列与变体序列从基准报告及原 N11/FoldX 输入递归验证，不要求两侧序列相同。WT 结构若提供，必须是原设计基座的精确 ArtifactRef；变体侧分别验证自己的序列、结构、映射、质量和 RSA。两侧目标链不同且没有已登记重命名契约时拒绝。`pair_id` 绑定基准报告、变体 ID、变体序列 hash 和两侧全部来源，避免仅按标签连接。

每侧结构会回放既有原生输出校验并从绝对 SASA 重新验证 RSA 归一化，保留作者编号/iCode、结构和映射 hash、逐位缺失及质量条件；N06 回放原生 observation 并递归核验其预测器所有发布产物；N09 验证原注释快照、计算结果及绑定来源。同一次检查复用相同 WT 来源，执行后仍重新核验来源，不能隐藏晚期替换。

| 层 | 工程值与限制 | 正式结论 |
|---|---|---|
| L1 | 真实非空 WT 热点区间并集上的逐位同一性、同一比例；无热点数据／空区间明确未计算 | 始终 null，不以全相同替代科学签收 |
| L2 | 两侧质量条件可用且每个验证位置 RSA 合法时，保留逐位差、WT/变体均值及均值差，原件参考边界严格 `>-0.15`；缺位、不可靠或出域不算空均值 | 工程阈值观察单列，正式保护为 null |
| L3 | 对匹配序列位置的 Cα 计算两两距离变化及其均方根，保留逐对明细；功能域仅比较双方明确同类型同区间的来源，错配逐域披露。该距离变化不需要叠合、不称 RMSD、不套2Å阈值；超过10000个距离对时整项未计算并列出工程输出限制，不截断点集 | 局部/功能域 RMSD、shape_similarity 保持 null；待明确拟合范围、缺位、最小点数/退化构型及点云算法 |
| L4 | 两侧 N06 同规则 profile、同一区间集合且加权分数均已存在时，计算区间绝对差均值，参考边界严格 `<0.2`；峰漂移/拆分/合并缺唯一对齐规则时未计算 | 不从 BepiPred 原始分数制造热点，正式预测保护为 null |

数值参考与科学条件的具体分工集中见 [N13 开放项](<../project/OPEN_ITEMS.md#n13-四层工程比较的具体科学缺项oi-007015022026028>)。低质量、无结构、未提供、失败、未签收、热点尚未生成、已计算空热点与空验证区间均不记科学通过。IEDB已移除，不生成E3/E4；正式 `structural_preservation / prediction_preservation / epitope_violation / epitope_soft_penalty` 保持 null。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\absolute\runtime epitope-protection --input D:\absolute\n13-request.json --key n13-paired-new --run --wait 60
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\absolute\runtime result --job-id <N13任务ID>
```

回连已有报告时，在原 `variant-report` 请求上增加可选 `n13_source={job_id, artifact}`。后端核验 N13 绑定的原报告具有完全相同的 WT、上游集合、变体来源类型及 FoldX 显式链接，再逐条核验序列hash；无配对记录的变体注明未进入 N13 配对集。新报告每条增加 `n13` 四层记录和 `n13_state`，报告原有淘汰依据不变。调用同一个 `variant-record --job-id <新报告任务ID> --id sample-1` 即可查询新增层级，不修改原报告或历史资格。失败N13仅接回状态/原因，不暴露成功保护值。


## W7 N16–N18 条件密码子、WT 扫描与交付

## N16 本机接口与实施回填

2026-09-09：`t01.real.optimize_codons / N16` 已接入现有 SQLite 任务、幂等、事件、ArtifactRef、查询和重试。主验收 [acceptance-r01 索引](<../../discovery/t01-phase1-real/w7/codon-integration-20260909/acceptance-r01/index.json>)记录 23 个任务案例、7 项守卫、197 份文件及 113 项发布产物；独立审计核验 6 次真实成功优化、1 次真实不可满足约束回退。成功次数包括故障后的新任务重试，不是六个科学候选。原24条排除记录未读取、未优化、未修改资格。

### 固定宿主与计算边界

- 仅开放精确 `expression_host="E.coli"` 配合 `host_profile="ecoli-k12-w3110-kazusa-316407-v1"`。调用方必须明确选择表 profile，不将属种或别名自动替换为株系。表来自 `python-codon-tables==0.1.18` 的 Kazusa 派生本地 CSV，原始字节 SHA-256 为 `b7eb52a39dce8c4ed4475f4a6032333dc2eff47eb2b1f756209c14569ffc4ace`。[Kazusa 原站](https://www.kazusa.or.jp/codon/cgi-bin/showcodon.cgi?aa=1&style=N&species=316407)标明 W3110 与标准遗传密码表；该在线核对仅为资料核验，运行时不访问网站。
- [资产清单](<../../src/t01_phase1_real/development/codon/assets/manifest.json>)固定 DNA Chisel 3.2.16、Biopython 1.88、NumPy 2.4.6、python-codon-tables 0.1.18、docopt 0.6.2、flametree 0.2.1、proglog 0.1.12、tqdm 4.70.0、colorama 0.4.6 的版本与安装文件 hash；[精确依赖](<../../src/t01_phase1_real/development/codon/assets/requirements.txt>)用于重建。代码固定 manifest hash；执行前后复核表和依赖内容。禁止以运行时重新生成清单的方式接受漂移。
- 请求仅接受 `INDEPENDENT_ENGINEERING_SEQUENCE`；1–1000 个 AA20 大写残基，无空白、X 或 `*`。`coding_policy="standard_fragment_no_added_start_or_stop"` 显式选择标准表1的编码片段，不添加起止密码子、载体、接头或信号肽。此为本包工程输入边界，未据此定义完整生产 CDS。
- 初始 DNA 逐残基选最高使用频率密码子，并列按字典序。CSV 保留 Kazusa 两位小数原值；传入工具前仅按同义组总和归一化，不改相对比例。64个密码子覆盖、唯一性、标准翻译和频率数值均校验。
- DNA Chisel 使用 `CodonOptimize(method="use_best_codon", codon_usage_table=本地表)`、显式翻译保持、全片段 GC 40%–60%（含边界）、BsaI/BpiI 双链识别位点规避。固定 NumPy seed 1601、`max_random_iters=1000`；优化目标采用该工具的默认方法并在 profile 披露，工程通过不表示全局最优。[官方规格说明](https://edinburgh-genome-foundry.github.io/DnaChisel/ref/builtin_specifications.html)为 API 核对依据。独立后验不调用 DNA Chisel 约束评估器，重新翻译、整数比较 GC 上下界并扫描完整正反向识别串，包含末端位点。
- 当前库实际实现把 `start_codon=False` 也视为已指定起始策略；本包按已核对源码使用 `None` 表达无新增起始要求。未将文档示例照抄为生产语义。
- `cai_score=null`，原因 `OI_004_CAI_METHOD_REFERENCE_AND_BOUNDARIES_UNAPPROVED`。工具内目标分数不是已签收项目 CAI；不另造合格阈值。额外限制位点、完整 CDS 起止/遗传表例外、生产目标和 CAI 仍由 OI-004 具名签收。

## N17 与 N18 本机接口

实施：2026-09-10。`t01.real.wt_reference / N17` 与 `t01.real.local_delivery / N18` 在现有 registry、SQLite、生命周期、查询和 ArtifactRef 中增量登记；不改冻结 W1 Schema，也不建立第二套运行系统。

N17 请求包含 `protein_sequence/user_sequence_id/timeout_seconds` 和显式 upstream 五槽：`structure/foldx/thermompnn/design_audit/topology`；缺项为 null，已提交但未完成任务用精确 job_id 和 null artifact，已终态用原登记 result/diagnostic 引用。对所有来源验证工具、请求、WT 序列、尝试/规则/执行 profile、资格和全部已发布文件 hash。FoldX 仅接受 PositionScan；两引擎输入必须与显式结构 ArtifactRef 完全相同，不能仅靠序列相同或复制分数配对。原生输出按既有解析器重新核验，保留请求扫描集合、排除位置、实际有效位置、原生引擎排名和扫描来源；不会调用新扫描。

N17 返回 `reference.engines`，各引擎包含原始 records、来源、范围和缺项；保留同义 WT 自身记录，排名仍是原引擎比较集合内的工程排名。`common_observed_mutations` 仅列已匹配键，`same_comparison_set` 明示集合是否相同；`combined_ddg/consensus_ranking/scientific_pass=null`。现有实测两引擎对应不同登记结构分析批次，分别形成参考，不强行生成“双引擎共识”。权限资料可回连时列出 FIXED∪RESTRICTED 与历史有效扫描的交集，只作违规范围复核，不重新授予权限或启动扫描。缺权限/拓扑、结构质量和未执行/失败/多链跳过状态保留；膜蛋白、低质量等门控未定分支不被参考回连绕过。

N18 请求包含 `protein_sequence/user_sequence_id/host_species/expression_host/timeout_seconds`、upstream 三槽 `wt_draft/variant_report/wt_reference` 及 `dna_bindings`。逐层回放 WT 草稿、N13 所在变体报告与 N17 原始来源，要求提供过的 WT 结构引用一致。DNA 绑定字段为 `subject`（WT 或报告内精确变体 ID）与 `source`；校验该对象序列和表达宿主后，再判断用途适用性。现有 N16 只有独立工程序列 profile，因此即使序列/宿主相同也登记 `INDEPENDENT_ENGINEERING_DNA_NOT_BUSINESS_APPLICABLE`，不附到 WT 或候选 DNA；不匹配序列/宿主、未知变体和损坏引用直接拒绝。缺 DNA 明记 `DNA_NOT_PROVIDED`。

N18 输出 `delivery` 和原始 `output/package.zip / report.md / package-manifest.json`。ZIP 包含机器数据、可读报告、已登记上游请求/结果和文件清单；每个文件有大小/SHA-256，清单不自包含，其本身由 ZIP 的已登记 ArtifactRef hash 覆盖。原始工具文件、模型、服务器资产和受许可限制的工具只保留来源引用，不复制工具、密钥或凭据；这不是可脱离原资产重跑模型的离线环境包。ZIP 内链接采用固定相对路径，可离线阅读。

结果明确区分 `WT_ROUTE_REVIEW_REQUIRED / DESIGN_ELIGIBLE_RELEASE_CLOSED / DESIGN_INPUTS_UNAVAILABLE / DESIGN_NOT_EXECUTED / UPSTREAM_FAILED / ALL_EXCLUDED / ENGINEERING_RECORDS_REVIEW_REQUIRED`，并回连 `business_route` 与完整 `design_applicability_gate`。`ALL_EXCLUDED` 保留每条原淘汰原因、null 最佳候选和原报告，不转成已通过 Gate 的 WT；`WT_ROUTE_REVIEW_REQUIRED` 也只是 R-57 本地业务分流。`formal_candidate_id/agent_c_payload/scientific_pass=null`，`formal_wt_delivery/candidate_record_complete/automatic_handoff=false`，生产仍为 `NOT_DEPLOYED`。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <同来源运行根> wt-reference --input <精确N17请求.json> --key <唯一键> --run
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <同来源运行根> local-delivery --input <精确N18请求.json> --key <唯一键> --run
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <同来源运行根> result --job-id <任务ID>
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <同来源运行根> artifact --job-id <任务ID> --artifact-id <ZIP或报告产物ID> --output <新文件路径>
```

同一入口支持 `get/events/execution/cancel/retry/recover/wait`。单个来源、报告或 ZIP 文件通过 artifact 查询，单变体继续使用其来源报告的 `variant-record` 查询。本地有界计算复用已有停止发布栅栏：取消/超时后不发布可消费报告，失联登记 INTERRUPTED，显式 retry 新建任务；未提供的来源不伪造已执行状态。
