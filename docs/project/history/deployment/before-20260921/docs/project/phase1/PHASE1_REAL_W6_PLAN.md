# PH1-REAL-W6：表位保护、稳定性与综合排序

更新：2026-09-09。实际进度见 [STATUS](../STATUS.md)，阶段依赖与三类放行见 [总计划](../PHASE1_DELIVERY_PLAN.md)。W5 已交付生成器、逆折叠打分、权限/负担工程，不等于完整 W5 完成；稳定性双引擎工程包已完成，科学消费与节点完成仍分别判断。

## 阶段交付表

**2026-09-19续行要求：** 按[专家流程校准计划](../PHASE1_DELIVERY_PLAN.md#专家流程校准与单卡执行计划2026-09-19)第4–5项完成变体上游重跑、L1–L4、五维前40池/FoldX/六维终评和真实排序。当前比较/报告组装及排序夹具不等于业务完成；L4前20池与最终top20的关系按OI-022定点闭合。修正`variant_report/compute.py`将S-23/宿主同源缺失列作必需排序阻塞的残留，按一期图不执行并披露“一期未评估”；下方历史验收中的安全缺项保留原时点，不构成现行恢复要求。

| 包 | 交付目标 | 具体依赖 |
|---|---|---|
| 稳定性工具工程接入（完成） | ThermoMPNN 单体预测与完整 SSM，以及 FoldX 5.0 RepairPDB、BuildModel 5 次和 PositionScan，均已完成真实禁网执行、统一查询、来源/生命周期及产物核验 | 两引擎均使用可追溯本地结构独立验收，不要求先有科学通过候选；结果仍未科学签收、未部署，不能自动交接 |
| N13 表位保护 | 原/变体预测与结构证据比较、保护结论及缺失/失败处理 | 已签收适用表位规则，变体结构所需模型、OI-007/026/029 及候选池规则 |
| N14 稳定性评分与 N15 综合排序 | 稳定性结果回连、Hard Filter、适用 Pareto/综合排序与全部淘汰处置 | 工具实测、OI-009/010/011/022 与适用科学输入；不以工程结果放行 |

每包包含实现、测试与必要证据，不再拆准备/评审阶段。后两包随实际资料细化，不先建空接口。完整阶段保留所有现行能力，先做稳定性不削减 N13。

## FoldX / ThermoMPNN 稳定性工具工程（已完成）

依据 [C35 FoldX ToolSpec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C35_FoldX_v10.5.md)、[C43 ThermoMPNN 口径卡](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C43_ThermoMPNN_v10.5.md)、[SOP S-31](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)。本包共享引擎供 W6 N14 与 W7 N17 复用，不提前宣布 N17 完成。

**目标**：真实本地结构与明确工程突变/扫描范围→原工具禁网执行→有符号 ΔΔG 与原始输出→身份、单位、坐标和产物校验→统一查询。范围参数仅限定工程验收成本，不削减正式扫描能力。

1. 分别核实资产。FoldX 按现行原件固定 5.0；本轮已登记用户提供的学术版压缩包、可执行文件与伴随分子文件，并保留“用户声明授权、包内无单独许可回执”的事实。ThermoMPNN 固定官方代码/模型/依赖和实际参数。不得假定机器已有原包或用其他版本静默替代。缺项只记录具体资产及影响；可用引擎连续完成实跑与接入，双引擎包保持部分。
2. FoldX 必须实际 RepairPDB，再执行 BuildModel 的明确单/多突变评分及 PositionScan 的明确位置扫描。缓存绑定原结构、修复参数、工具资产和修复结果 hash；保留原/修复结构及映射，不将修复结果直接赋予科学资格。调用次数/重复次数、输出聚合及单位按固定工具和适用原件核验，不猜平均规则。
3. ThermoMPNN 仅用于原件允许的单体；多链按 R-39 明确跳过，不通过偷偷裁链伪装单体。扫描按 C43 获取全量预测，不能沿用默认稳定化子集；真实核验输出覆盖，不能仅凭传入高 threshold 就宣称完整。
4. 绑定序列、结构与工程突变/范围来源。核验唯一目标链、作者编号/插入码与工具编号，无法唯一映射明确失败/复核；partial 仅扫描原件允许覆盖区。FIXED/RESTRICTED 约束及资格沿用已实现来源守卫，不把工程权限当科学允许设计。
5. 保留每个引擎原始 ΔΔG、单位、工具版本和参数。依原件负值稳定方向做工程核验，若原工具事实冲突不得静默取反。双引擎不能平均原始 ΔΔG；排名交集仅在同一合法完整比较集合和明确规则下计算，未签收共识不作为正式筛选。
6. 接入统一任务、幂等、查询、取消/超时、恢复/重试与发布 hash；分别记录原包真实执行、故障注入与数值夹具。无需重建运行框架，不依赖 AF3/ESMFold2 部署。

**验收**：可追溯结构修复及复用、真实单/多突变与明确范围扫描、覆盖检查、坐标/iCode/多链与缺失结构守卫、缺资产、工具/输出失败、部分引擎不可用、来源/产物篡改及适用生命周期。两引擎分别有真实批次与完成状态；真实运行失败不得用夹具补成通过。按共享代码影响回归。

**完成标准**：两引擎适用能力禁网实跑与统一查询可复现，固定资产、来源/原始产物与必要守卫通过；单引擎先完成则回填部分，不等待另一引擎才保留成果。命令、支持域、实际限制和证据回填本节。

既有 24 条 R-35 全排除结果保持。工程验证使用明确标记的测试突变或已有工程记录，不能恢复其正式候选资格。N10、W5 目标分支/受控重算、OI-011 科学签收、完整 N14/N17、正式设计与 Agent C 交接仍按各自条件完成，不因本包工具可用而放行。

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

[最终验收 r05](../../../discovery/t01-phase1-real/w6/thermompnn-integration-20260908/acceptance-r05/index.json)包含 13 个任务场景和 12 项守卫；452 份索引文件、347 项发布产物及 28 份源码/配置快照经[独立只读复核](../../../discovery/t01-phase1-real/w6/thermompnn-validation-20260908/evidence-audit-r03.json)一致。现有 9 aa 本地结构真实输出 180 行；明确排除 2、8 位后发布 140 行，其中 133 个非 WT 突变只做引擎内排名。覆盖真实重试、取消、超时、崩溃恢复、多链跳过、来源及发布产物篡改；r01–r03 为验收汇总断言修正前、r04 为补齐官方 README 所引 SVG 资产前的未完成工程记录，不计现行完成批次。

FoldX 用户包确认包含 5.0 ELF、`RepairPDB`、`BuildModel`、`PositionScan` 及伴随分子文件；压缩包 SHA-256 为 `841a33ed680ac195ef8f6ccee26620fba64dd5e92891bf49c359170aee1e81d2`，可执行文件 SHA-256 为 `5309d81c3f08b8405d172153aaf9792a244c06f98387c9d57a104302a9cef2cf`。依据用户声明登记为 `USER_ATTESTED_ACADEMIC_VERSION`，不把它等同于机器许可证明；[包盘点](../../../discovery/t01-phase1-real/w6/stability-assets-20260908/foldx-user-package-probe-r02.json)与[资产收据](../../../var/t01-phase1-real/tool-assets/foldx-20270131/assets.json)保留该边界。Docker Desktop Linux engine 已恢复为 29.5.3，WSL2 kernel 为 `6.18.33.1-microsoft-standard-WSL2`；无缓存离线重建镜像固定为 `sha256:66539e081922ce4c4fb504c9906feb64044ce668033e63fdc9299d020af8c851`，镜像标签绑定的基镜像 ID 为 `sha256:68d914ec641a0b69267ce65184d000a2bc3a9ee2590ab702b82250ab2385735a`。


### FoldX 环境恢复与真实验收（已完成）

[最终验收 r05](../../../discovery/t01-phase1-real/w6/foldx-integration-20260909/acceptance-r05/index.json)包含 12 个任务场景、11 项请求/完整性守卫和 553 份索引文件；[独立复核](../../../discovery/t01-phase1-real/w6/foldx-validation-20260909/evidence-audit-r02.json)重新核验全部大小/SHA-256、456 项发布产物、无缓存固定镜像、实际容器隔离及数值明细，结果 PASS。[最终测试摘要](../../../discovery/t01-phase1-real/w6/foldx-validation-20260909/test-summary-r02.json)记录双引擎专项 36 项通过、当前根 1553 项通过及 1 项既有跳过；199 份现行 Markdown 检查通过，29 条历史归档链接问题保持原状。主要实测事实如下：

1. 每个成功模式均先真实执行 RepairPDB，并保留原结构、`target_Repair.pdb`、能量文件、命令、日志及完整输出 hash。
2. 两个明确扫描位点产生 42 行 FoldX 原生 PositionScan 记录；原工具每位点含 1 行相同 WT 重复和 1 个小写 `e`/`o` 组氨酸互变异构体代码。适配器只在完整结构与原生行核验后将 `e/o` 显式归一为 H，得到 40 个唯一 AA20 结果、40 份突变 PDB 和 2 份逐位能量文件；不伪造 PositionScan std，confidence 保持 null。
3. 三个明确变体（含单突变与双突变）各真实执行 BuildModel 5 次；15 行 `Dif` 与 `Average` 的均值/总体标准差重新复算一致，30 份 mutant/WT PDB 齐全。结果保留五次原值、均值、std 与参考 confidence，不做跨引擎绝对值比较。
4. 工具失败后真实重试、排队/运行中取消、1 秒超时、启动后监督进程中断恢复、停止收据后恢复、损坏输出、晚期来源替换和发布产物篡改均按预期停止、隔离或拒绝；统一 CLI 查询回读一致。

r01 因固定镜像标签尚未纳入严格容器所有权集合而在容器启动前停止；r02 保留首次真实 PositionScan 及未识别 `e/o` 时的隔离事实；r03 在 PositionScan 通过后暴露 BuildModel 地址前缀未处理空目标残基并停止。三者均不计 PASS；r04 功能与生命周期虽 PASS，但镜像命中旧缓存层，缺少现行 Dockerfile 声明的基镜像身份标签，故以无缓存离线重建后的 r05 为最终批次。许可继续按已有用户声明及适用使用范围登记，不重复要求已提供资产。正式科研消费、自动交接与原 24 条排除结果保持原状态。


## N14 稳定性回连与 N15 筛选排序工程（已完成）

2026-09-09 管理安排：双引擎原工具工程完成后，推进本页已有 N14/N15 业务包，不重复做原工具接入。目标是将真实 N11/N12、权限/负担和 FoldX 产物组合成逐变体可审计的工程筛选记录、适用排序及全部淘汰报告。

1. 核验 WT/结构、变体 diff、样本 ID、任务/尝试及 ArtifactRef/hash，以明确身份连接 FoldX BuildModel 与对应变体。缺失/失败/未签收单列；PositionScan 单点值或 ThermoMPNN 单突变值不得相加冒充多突变 BuildModel，也不得平均两引擎原始 ΔΔG。
2. 按 SOP T-01 step19b/20 和现行范围逐项归并筛选、评分字段及生产者。复用真实 ESM-IF1 排除与工程 burden，保留原有淘汰原因；资格、Hard Filter、Pareto/评分分别处理。OI-009/010/011/022 未定或输入不齐的计算关闭，输出缺少的具体条件，不能发明权重、前20/40池或并列规则。
3. N13 未完成、N10 overall=null、未签收结果不得包装为科学通过或默认最优。已有原件明确的缺值处理仅作标记工程规则，不赋予科学资格；不把未执行 N13 当无热点验证通过。字段充分且规则唯一的排序可用显式工程输入验证，其余返回未计算及原因。
4. 本批原24条已全部被R-35排除，应真实走“无可用变体→排除清单/复核报告”路径，不重生成、不额外放宽阈值、不挑一个强行交付。阳性排序使用明确标记的数值/契约夹具，与真实业务样本隔离，不能宣称已获得合格候选。
5. 统一入口完成提交、查询与可追溯报告，继承适用生命周期和产物守卫；不发送 Agent C，不回写旧证据或升级历史候选资格。

**工程完成标准**：真实历史批次与稳定性产物身份回连可验证；每条保留/排除/未判定均有来源与原因；全淘汰形成可查询报告；有依据的排序规则经过可手算夹具和边界验证，缺失规则保持阻断；受影响回归通过。实现命令和新验收证据回填本节。

本包完成不等于完整 N14/N15/W6。N13 表位保护、变体重新计算、N10 缺项、候选池及科学签收继续按真实依赖推进；未决字段先查原件，只有具体冲突才归并到现有开放项，不新增笼统准备任务。

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

### 本包真实验收与边界

[最终批次 r03](../../../discovery/t01-phase1-real/w6/variant-report-integration-20260909/acceptance-r03/index.json)记录 11 个任务场景、8 项请求／哈希守卫；[只读独立算术与证据审计](../../../discovery/t01-phase1-real/w6/variant-report-validation-20260909/evidence-audit-r01.json)核验 554 份索引文件、483 项发布产物、24 条原 R-35 排除、3 条 FoldX 变体及15个原生差值一致。验收使用历史真实产物副本，不计作新模型运行，原运行根、归档和资格均未改写。

- [24 条全部淘汰报告](../../../discovery/t01-phase1-real/w6/variant-report-integration-20260909/acceptance-r03/cases/real-24-all-excluded/report.md)：任务成功表示报告构建完成；业务结果为 `ALL_EXCLUDED / NO_AVAILABLE_VARIANTS`，不是筛选通过。每条保留 `R35_DETERIORATION_EXCEEDED`（ESM-IF1 相对 WT 恶化超过已用20%容忍）、逐位工程权限违反和已知负担超档。缺少的 FoldX、N13/安全和完整科学输入另列；不生成、不放宽、不强选。稳定性工具的9 aa批次与该76 aa WT不同，因此不能回填其分数。
- [FoldX 三条工程变体回连报告](../../../discovery/t01-phase1-real/w6/variant-report-integration-20260909/acceptance-r03/cases/real-foldx-three-bound/report.md)：从原始请求而非变体标签推断突变，按目标链和完整 canonical mapping 核验1份修复PDB、15份 mutant PDB、15份 WT 对照的残基、编号、主链原子与有限坐标；五次 ΔΔG、均值、总体 std 和 hash 逐条回连。原生 variant_id 只是身份标签，其文字不替代 WT/diff 核验。无 N11/N12/N13 输入，三条均为 `UNDETERMINED`，不是候选通过。
- 阳性 [排序算术夹具](../../../discovery/t01-phase1-real/w6/variant-report-integration-20260909/acceptance-r03/ranking-fixture.json)按 SOP 四维支配关系与 general 权重得到手算0.89；同分仅成组展示，不规定组内选择，不产出前20/40池。专项另覆盖三档分母、两种扣分、合法中性缺值、非法/非有限值、极端 sigmoid、五项硬筛选和未执行 N13 拒绝中性化。
- 真来源失败、未提供来源、错误 WT、跨根引用、PositionScan 冒充 BuildModel、伪造 ArtifactRef、错误变体连接、幂等冲突、计算失败/输出损坏/中断及其重试、计算后晚期来源替换和报告发布篡改均隔离；单测另验证排队／运行中取消、实际超时判断及终态不发布报告。整批与单条 CLI 回读已保存为 queries 证据。

r01 在重试阶段遇到复制运行根中已有幂等键，不计完成；r02 已通过当时功能与生命周期，r03 为补上逐份 PDB 语义核验、失败来源的已知变体和晚期来源替换后的最终批次。两种历史产物均保留原资格；`usable_for_pipeline=false / DEVELOPMENT_UNREVIEWED / NOT_DEPLOYED` 不变。

[最终检查摘要](../../../discovery/t01-phase1-real/w6/variant-report-validation-20260909/test-summary-r01.json)：当前根1580项通过、1项既有 Windows 符号链接权限跳过；报告与审计专项31项通过，文档测试56项通过。217份 Markdown 现行链接通过，29条原历史引用问题保持；457项冻结一期 Mock 资产只读验证通过。未跨历史分区修改，旧完整 Mock/S07 未重跑、不混入当前根数字。

可直接查询本批首条淘汰记录：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\variant-report-acceptance-20260909-r03\design variant-record --job-id t01p1r-job-cc48d78e2e2e4b31bc8a4cdcdfdcd4de --id sample-1
```


## N13 表位保护工程与报告回连（工程已完成）

2026-09-09 管理安排：N14/N15 报告工程已经交付，下一包补 N13，完成原/变体证据比较与逐层结果回连。依据现行范围、SOP T-01 step19、SKILL R-56/R-58、Schema 及 OPEN_ITEMS 中 OI-007/026/028/029；原件入口见本页前文。不新增逐项准备或评审任务。

**交付目标**：可信 WT/变体序列及适用结构、RSA、N06/N09 产物→四层工程观察/明确未执行原因→统一查询→既有 N14/N15 报告回连。工程观察和正式保护结论分离，不能把无可验证证据当作已证明保护。

1. 复用统一任务层与 ArtifactRef，绑定 WT、变体 diff、每侧结构/映射/质量/RSA、各自预测图及功能域来源。两侧序列应分别与各自产物一致，不能要求 WT 与变体序列相同；用稳定配对身份连接两侧，拒绝跨批次错配和来源篡改。FoldX 修复/变体结构不可冒充 AF3/ESMFold2 预测或自动获得 S-09/RSA 资格。
2. L1 按真实可用验证区间计算残基同一性；L2 在配对坐标及可用 RSA 上保留逐位差和均值；L3 对明确匹配的局部 Cα/功能域计算适用几何。先核对原件关于叠合范围、缺残基、最小点数等定义，未唯一明确时保留工程观测和具体待裁决项，不暗设算法。shape_similarity 无唯一方法/阈值时保持未计算，不自行补评分。
3. L4 绑定原/变体各自的 N06 预测画像，按有依据的区间对齐规则比较。依赖 BepiPred 后处理或热点尚未闭合时保持 null/复核，不从原始分数临时制造热点。若包内触发真实预测，必须显式工程请求且身份/资产可追溯，不自动启动正式候选流程。
4. 严格区分未提供、上游失败、未签收、已计算空热点、空验证区间、无结构、低质量和正常可计算。移除 IEDB 后不虚构 E3/E4；空区间不得计算空均值或直接产出科学 PASS。正式保护布尔值和降级语义按 OI-028 等待对应裁决，未决项只阻断具体分支。
5. N13 产物接入 N14/N15 逐变体报告：展示各层是否执行、值/缺项/原因及来源，不能把 NOT_EXECUTED 变成中性科学通过。原24条全淘汰状态保持，不重生成、不因新增报告字段恢复资格。

**验收**：真实上游来源回连（包含当前 N06 热点未生成的实际情况）、配对身份与哈希、空/缺失/失败状态、明确区间的同一性和 RSA 差、可手算几何及阈值边界、错链/缺坐标/跨批次拒绝、报告回连与适用取消/超时/恢复/重试。几何/数值夹具与真实科学工具产物分别记录；没有真实阳性科学样本时明确披露，不能用夹具签收完整保护链。

**工程完成标准**：四层已有依据的可执行部分和未决分支守卫均有实现/验证，真实来源→逐层结果→统一查询→报告回连可复现，受影响回归通过。命令、支持域和新验收索引在本节回填。若具体外部缺项影响部分能力，逐项注明，不将已有接口或守卫完成等同于全部四层科学验收。

本包不等待两模型部署才实现本地配对分析；依赖新预测的动作仍等待同事交付。N10、W5 未闭合分支、完整 W6 和科学/正式交付资格保持独立状态。

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

数值参考与科学条件的具体分工集中见 [N13 开放项](../OPEN_ITEMS.md#n13-四层工程比较的具体科学缺项oi-007015022026028)。低质量、无结构、未提供、失败、未签收、热点尚未生成、已计算空热点与空验证区间均不记科学通过。IEDB已移除，不生成E3/E4；正式 `structural_preservation / prediction_preservation / epitope_violation / epitope_soft_penalty` 保持 null。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\absolute\runtime epitope-protection --input D:\absolute\n13-request.json --key n13-paired-new --run --wait 60
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\absolute\runtime result --job-id <N13任务ID>
```

回连已有报告时，在原 `variant-report` 请求上增加可选 `n13_source={job_id, artifact}`。后端核验 N13 绑定的原报告具有完全相同的 WT、上游集合、变体来源类型及 FoldX 显式链接，再逐条核验序列hash；无配对记录的变体注明未进入 N13 配对集。新报告每条增加 `n13` 四层记录和 `n13_state`，报告原有淘汰依据不变。调用同一个 `variant-record --job-id <新报告任务ID> --id sample-1` 即可查询新增层级，不修改原报告或历史资格。失败N13仅接回状态/原因，不暴露成功保护值。

### N13 本轮验收与完成边界

[主批次 r05](../../../discovery/t01-phase1-real/w6/n13-integration-20260909/acceptance-r05/index.json)包含19个场景、8项请求/来源守卫；[独立审计](../../../discovery/t01-phase1-real/w6/n13-validation-20260909/evidence-audit-r01.json)核验1086份索引文件、992项发布产物一致，并复核29条配对记录（含重试）、2次真实预测与24条原淘汰保留。[补充批次](../../../discovery/t01-phase1-real/w6/n13-integration-20260909/supplement-r01/index.json)包含5个场景和错链守卫；[补充只读复核](../../../discovery/t01-phase1-real/w6/n13-validation-20260909/supplement-audit-r01.json)确认241份文件、228项发布产物一致。两批不合并冒充独立科学样本数量。

1. 原76 aa WT与24条真实N11变体从已验收报告回连；全24条可查询各侧缺项，逐条R-35、权限/负担工程排除完全保留。另选sample-1作明确工程预测请求，WT与该变体分别真实运行BepiPred，再分别运行N06；两侧序列/hash不同且各自预测来源正确。N06实际热点均为null/review_required，L1/L4不假装通过。查询与原报告的比较记录在主批次中。
2. 9 aa FoldX工程变体作为另一批独立验证结构配对，真实运行本地结构分析，保留FoldX来源说明，质量为low、RSA未执行。补充链B结构也是明确标记的工程派生输入；不同目标链被拒绝，不静默重命名，不冒充AF3/ESMFold2或科学结构。
3. 补充真实N06无预测器失败任务回连，明确upstream failed；真实N09原注释/功能域快照及来源验证通过。缺失、失败、未签收、空热点/空区间及低质量分别表达。没有真实已签收热点、配对正常RSA或阳性科学保护样本；L1/L2/L3/L4阳性数值用独立 `SYNTHETIC_CONTRACT_FIXTURE` 验证，不能据此签收科学全链。
4. 生命周期覆盖真实配对上的计算失败、输出损坏、中断及重试、运行中取消/超时停止；专项另验证排队取消、实际计时超限与诊断回连。来源错侧序列、原WT错结构、缺少变体ID、重复配对、跨根、循环报告、原生N06产物篡改、错链和计算后结构替换均隔离。统一单条查询返回完整N13观察和来源。
5. 工程几何保留可手算的匹配Cα距离变化，阈值测试验证RSA在-0.15、画像差在0.2的严格边界；缺Cα、单点、空集合、不同画像区间/规则profile、出域及非有限数不产出正常科学指标。RMSD/shape和非同一区间对齐的具体方法缺项单点维护于OPEN_ITEMS，未发明算法或权重。

r01因同一WT产物重复验证耗时被停止，随后改为单次来源缓存并保持执行后复核；r02保留沙箱Docker管道权限失败；r03/r04分别暴露9 aa数据不适用NetMHC/N06既定请求域的验收安排问题。没有改动工具准入范围，r05改用76 aa真实WT/变体作预测来源、9 aa批次独立作结构配对。前批未计完成，原件、旧证据及旧资格不回写。

[可读逐变体报告](../../../discovery/t01-phase1-real/w6/n13-validation-20260909/report.md)展示sample-1实际预测配对及所有24条原淘汰；其余23条在该单样本预测配对报告中明确未进入配对集，全24条缺项配对报告另行保留。直接查询本轮sample-1：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\n13-acceptance-20260909-r05\design variant-record --job-id t01p1r-job-5105a94bf8884020a0fc5bc8a233d176 --id sample-1
```

当前根回归1611项通过、1项既有Windows符号链接权限跳过；受影响专项177项通过，不与根数字相加。457项冻结一期Mock资产只读核验通过；未跨历史分区，旧完整Mock/S07未重跑。检查日志见 [根回归](../../../discovery/t01-phase1-real/w6/n13-validation-20260909/root-tests-r01.txt)及[专项](../../../discovery/t01-phase1-real/w6/n13-validation-20260909/targeted-tests-r01.txt)。工程完成不等于完整N13科学验收或W6完成，`DEVELOPMENT_UNREVIEWED / usable_for_pipeline=false / NOT_DEPLOYED` 保持。

[最终检查摘要](../../../discovery/t01-phase1-real/w6/n13-validation-20260909/test-summary-r01.json)同时记录56项文档测试通过、218份Markdown现行导航通过、29条既有历史引用问题保持；最终执行profile及18份源码快照与验收一致。
