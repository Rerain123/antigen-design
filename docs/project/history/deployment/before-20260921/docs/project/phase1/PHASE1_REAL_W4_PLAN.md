# PH1-REAL-W4 阶段计划：原蛋白可开发性与设计判断

> 更新：2026-09-08。实际进度与当前执行包只见 [STATUS](../STATUS.md)；总体依赖与放行条件见 [交付计划](../PHASE1_DELIVERY_PLAN.md)。

## 阶段交付表

**2026-09-19续行要求：** 按[专家流程校准计划](../PHASE1_DELIVERY_PLAN.md#专家流程校准与单卡执行计划2026-09-19)第2项补齐N10有效输入与真实Gate/WT路由。区分“适合设计”“不适合设计”“输入不足/尚未评估”；固定CLOSED及WT草稿组装均不等于业务判断已完成。沿用已有来源守卫和独立工具成果，具体科学歧义限定到OI-021等适用条款。

| 交付包 | 范围与完成标准 | 依赖 |
|---|---|---|
| N10 原蛋白可开发性基线（进行中） | 已统一提交/查询并完成 S-36a、S-37 结构路径、S-39、S-38 开发接入与 GUI 曲线工程对标及 S-40 部分汇总；S-36、S-37 序列路径/空间语义和 S-38 平坦曲线权重/科学签收未闭合，故 N10 不完整 | OI-025 CamSol 参数/符号、OI-032 序列聚集资产与空间簇签收、OI-033 平坦曲线权重、适用结构/RSA 资格 |
| 设计 Gate 与 WT 交付子路径 | 后端按确认规则判断是否进入设计；不适合时交付原蛋白评估与原因，并联调 N18 WT 输出 | OI-021、适用 N01–N10 真实输入与 N18 契约；不凭部分分数或未签收数据放行 |

两个包分别连续完成实现、测试和必要补证，不按每个公式新建任务页。提前开发 W4 不表示 W1–W3 完成或允许科学消费。

## N10 原蛋白可开发性基线

依据 [SOP S-36a～S-40](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)、[Schema](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md)与对应 ToolSpec；科学细节按 [权威索引](../../../工作流设计/01-业务依据/README.md)定位，具体缺口归 [OPEN_ITEMS](../OPEN_ITEMS.md)。

**包内推进顺序**：先做不依赖新模型的 S-36a 可表达性、S-39 标签暴露及 S-40 汇总接口与守卫，再按资产条件补 CamSol、聚集预测与 PROPKA，最后汇合 N10 的真实开发验收。已完成部分不因其他维度缺资产反复重开；只有部分完成时明确记录部分，不宣布整个 N10 完成。

- S-36a：固定 BioPython 版本，验证分子量单位、pI、GRAVY、不稳定指数、脂肪族指数和原件评分公式，保留可复核参考计算。未唯一确定的数学定义或输入边界不猜测。
- S-39：绑定实际结构质量/RSA 产物与同序列坐标，按原件计算两端暴露；低质量或 RSA 缺失时返回 unknown/原因。出域、未签收或映射不唯一不得转成可靠科学输入；工程夹具与真实产物分别记录。
- S-40：记录各维度值、可用性、缺失原因及来源，按原件处理归一化与权重。S-36 是必需输入；CamSol 缺失时只能查询已有维度，不能用其他分数平均冒充完整 overall。无可靠维度、未知权重或退化输入保持明确失败/复核；稳定性后续回填，不以 0 占位。
- S-36：按 C44 与 OI-025 完成参数来源核验、可重现制备及参考验证，不随意填写缺失参数。依照已授权模式实施，不扩大为尚未要求的结构修正或完整 pH 模型。
- S-37/S-38：固定真实工具与许可/运行资产，实测原生输出后接入。保留结构与序列路径差异、空间聚集定义、PROPKA 相对曲线及低质量守卫；不虚构绝对自由能或未定义分类。结构来源复用已接入后端，不联网获取。

**验收**：统一命令取得实际已执行维度、输入/工具/参数 hash、方法与复核原因；覆盖可靠/缺失/不可靠输入、同序列绑定、数值边界、失败隔离、产物篡改及适用生命周期，按共享代码影响回归。工具实跑、参考计算、契约夹具分别记证据。完整 N10 工程交付须覆盖全部保留步骤的适用执行/守卫，不能只交付可表达性就记 N10 完成；科学签收和目标部署分别判断。命令与批次索引回填本页。

### 当前工程结果与边界

- 已登记 `t01.real.developability / N10`，复用统一 SQLite 任务、幂等、事件、取消/恢复/重试、ArtifactRef 与发布校验。S-36a 固定 Biopython 1.88，分子量显式由 Da 转 kDa；S-39 只消费同序列、唯一映射且质量/RSA 可用的结构结果，未签收 RSA 仅返回 `computed_unreviewed`，不参与汇总。
- S-37 结构路径固定 `lcbio/a3d_server@sha256:c9e5a38b7d7f22c0b76678c5135ec4bf1af47cf77e8c9547a3bb4b9f7f2e938b`，容器内 AGGRESCAN3D 0.9.11 / Python 2.7.15，锁定默认 10 Å 距离。在禁网、只读根文件系统和受限资源容器中，对 PDB 或经 N02 原子账本校验的 mmCIF 只投影目标链后实跑，并发布 A3D CSV、统计、结构、FreeSASA、配置、stdout/stderr 及逐项 hash。正分残基按 Cα 距离图连通分量形成的空间簇是工程解释，保留精确位置而不按序列连续性合并；在算法签收与“非高风险”分类定义完成前结果为 `computed_unreviewed`，不参与 S-40。
- S-38 固定 PROPKA 3.5.1。本地 PDB 原字节直接运行；mmCIF 只在 N02 已验证原子账本能逐原子、坐标和地址往返时投影为 PDB，不能无损表示即拒绝该维。后端只解析 `.pka` 的逐基团 pKa/model-pKa，按 C24 在 pH 7.0 锚定并以梯形积分生成相对 ΔG_unfolding 曲线；不把 CLI 自带 folding-energy 表或任意常数当绝对 ΔG。
- C24 规定的 PROPKA GUI 曲线工程对标已完成：固定 VMD PROPKA GUI `propka.tcl` 的 git blob `c417a01fafd2da93a5abc59f957b22d3ff266dc1`、源码 SHA-256 `55cf9b44805e1697f0eb730223e5652f0caf7616af1fe729c3fe04b1d723548b` 和 3324–3352 行闭式公式，逐点比较现有 Tanford 梯形积分相对曲线。r14 的 41 点曲线均为 PASS，最大绝对差为 `0.000781108382120976 kcal/mol`，低于 `0.01 kcal/mol` 容差；逐点数值一致同时覆盖形状和符号。对标闭合不等于 S-38 科学签收：平坦曲线的“ΔG 加权平均 pH”在相对曲线可含负值时没有唯一非负权重定义，仍不猜测 optimal_ph；OI-015 的结构消费资格也继续独立约束可靠性和 S-40 纳入。
- S-40 固定输出六个维度及 `missing_dimensions/excluded_dimensions`。CamSol 是必需维度；它缺失时 `overall_score/classification` 始终为 null，`n10_complete=false`、`design_gate=NOT_EVALUATED`、`automatic_design_release=false`，显式权重也不得绕过。
- CamSol 原参数仍缺 `mu_random/sigma_random`，且 C44 的 Roseman H/P 阈值方向与公开 Roseman 数值及 C44 自身列出的疏水残基集合互相冲突，见 OI-025；必须由算法负责人明确“原表+改阈值”“取反+保留阈值”或项目变换表，后端才生成参数并实跑，不擅自选支。OI-032 的结构型 A3D 资产和命令已固定并实跑；对该镜像的禁网只读盘点确认其中 `aggrescan` 命令属于 AGGRESCAN3D 0.9.11，未发现可作为无结构备选的序列 AGGRESCAN 资产，且 A3D 包元数据只记录非商业用户许可，不能据此推导另一工具许可。剩余为官方序列 AGGRESCAN 离线资产/许可/命令及空间簇与非高风险分类签收；未采用明确声明为非官方的 Python 3 移植。

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

第二条使用尚不存在的运行根和 W4 批次，实际执行结构链、AGGRESCAN3D 结构路径及 PROPKA，并覆盖 PDB/mmCIF、无结构、低质量/RSA 异常、明确权重、故障、生命周期和来源篡改；不能覆盖完成批次，且要求 Docker Desktop Linux daemon 可用、上述固定 A3D digest 已在本机。当前完成证据为 [acceptance-r14](../../../discovery/t01-phase1-real/w4/developability-integration-20260908/acceptance-r14/index.json)：13 个 N10 场景、5 个真实结构上游、343 份索引前文件与 265 项发布产物核验，验收 profile 与现行实现一致，完整绑定 A3D 镜像/配置/原生输出及 PROPKA 源码、`propka.cfg`、依赖清单与 GUI 公式来源，对三条实际曲线完成 41 点逐点对标并全部 PASS；`propka_gui_benchmark_complete=true`、`propka_flat_curve_weighting_complete=false`，`N10_S36A_S37_STRUCTURE_S38_DEVELOPMENT_S39_S40_PARTIAL_ENGINEERING` 为 PASS。r11 因官方 A3D 0.9.11 的 `-C` 读取短 `END` 行触发 `IndexError` 中止，r12 因去掉 `END` 后工具重复末原子并令 FreeSASA 输出 `N/A` 中止；r13 闭合目标链投影和标准 `END`，r14 在相同 A3D 边界上新增 PROPKA GUI 对标，未放宽解析和来源守卫。r08、r09 因 Docker daemon 尚未可用在 normal-cif 前置阶段中止；更早未完成/前版证据继续保留，均不替代 r14。所有结果仍为开发未签收、不可科研消费、`NOT_DEPLOYED`。

## 设计 Gate 与 WT 子路径

在 OI-021 闭合前可验证输入契约、失败/复核路由和 WT 输出结构，不自行设“不适合设计”阈值。真实 Gate 必须由后端执行，未签收输入不得自动进入设计或交接。WT 路径保留原蛋白评估、未完成检查与原因，N18 不得将缺失检查记为通过。详细实施规则随本包推进在本节补齐，不预建空链接或另一套准备文档。


### 本包实施范围：Gate 与 WT 子路径工程包

2026-09-08 管理安排：N10 本轮可执行项与 N03→N06 回连已交付，主开发推进本节工程部分；N10 外部缺项保留原包，不要求等待两模型部署。

**交付目标**：通过统一入口绑定真实上游产物，返回可追溯的未评估/失败/需复核原因，并生成可查询的本地 WT 评估草稿。草稿明确列出已执行、未执行、缺失和未签收项目，不代表正式 WT 交付或“不适合设计”的科学结论。

1. 先按现有 S-42/S-44、Schema 归并 WT 字段及生产者，只落实有依据的字段；OI-013/014 未定字段保持明确缺项，不自造 Agent C 生产协议。
2. 复用统一任务层和 ArtifactRef，校验任务/尝试/哈希、同序列及资格；真实 N10 部分产物进入未评估/复核路由，不将 null 分数视为零或不适合设计。
3. 生成本地评估草稿、来源清单和机器可读原因，支持统一查询与适用生命周期。OI-021 未闭合时不计算新的科学阈值，不放行 N11；未签收结果不发送至 Agent C。
4. 验收真实部分 N10、缺失上游、失败上游、未签收、序列错配、哈希篡改及停止/重试等受影响场景，确认草稿与正式交付身份隔离。阳性科学放行仅可用明确标记的契约测试验证已有规则，不能冒充真实验收。

**工程完成标准**：真实输入→校验→明确阻断原因→本地草稿→查询与产物追踪可复现，必要回归通过。科学 Gate、完整 WT 交付、Agent C 生产接口及完整 W4 分别保持未完成；后续以对应外部条件和真实证据关闭。命令和证据在本节回填，不另建准备任务页。

### Gate 与 WT 草稿本机接口

已新增独立 `t01.real.wt_draft / N18` 工程 Worker，复用统一 SQLite、幂等、事件、取消、显式重试、恢复及 ArtifactRef；`N18` 登记只表示本地草稿组装，不表示完整 N18 已交付。执行不调用模型或网络。后端当前固定 `NOT_EVALUATED → LOCAL_WT_DRAFT_REVIEW`，`suitable_for_design/design_skip_reason` 为 null；N11、正式 WT 和 Agent C 放行均为 false。

请求字段为 `protein_sequence`、`user_sequence_id`、`host_species`、`organism`、`upstream`、`timeout_seconds`。序列为精确大写 AA20（1–20000 aa，工程容量边界）；物种可为明确输入字符串或 null，超时为 1–60 秒。`upstream` 必须显式列出 `structure/topology/blast/bepipred/netmhc/epitope_map/glycosylation/homology/domains/developability` 十个槽位，分别对应已登记 N01–N10 生产者。缺失槽为 null；提供时为 `{"job_id":"实际任务 ID","artifact":实际 result/diagnostic ArtifactRef 或 null}`。只有任务确无结果/诊断文件时 artifact 才能为 null，适用于排队、未启动取消或 preflight 失败。请求不接受自报状态、分数、签收、阈值或交接开关。

后端在准入、执行前及发布前复核同一运行根/授权 scope 内的任务与尝试、精确 ArtifactRef 登记、原请求序列、请求与结果 hash、结果 binding、历史执行 profile 和资格，以及上游全部发布原始产物的大小/hash。已提交后发生变化阻断执行或发布。历史产物按其记录的 profile 追溯，不要求它匹配修改后当前代码的 profile；不会重写旧结果。错误身份、错序列、哈希损坏返回明确 `FORBIDDEN/OUTPUT_INVALID/HASH_MISMATCH` 等错误，拒绝消费；合法缺失、失败、排队和未签收输入可以生成带阻断原因的草稿。

调用前将 `$runtimeRoot` 指向已有上游任务的本地运行根，`$n10JobId`、`$sequence` 取该任务的真实 ID 与原序列。CLI 自动解析其精确 ArtifactRef，其余槽位默认 null；也可通过其他 `--<槽位>-job-id` 参数绑定更多上游，或 `--input` 传完整严格 JSON：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root $runtimeRoot wt-draft --sequence $sequence --developability-job-id $n10JobId --key wt-local-example --run --wait 30
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root $runtimeRoot result --job-id $wtJobId
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root $runtimeRoot artifact --job-id $wtJobId --artifact-id $draftArtifactId --output D:\path\wt-draft.json
```

第一条返回 `job` 和 `result`，从中取 `$wtJobId`；`result.raw_artifacts` 中 `path=output/wt-draft.json` 对应 `$draftArtifactId`，第三条按该发布引用导出并校验。原请求、FASTA、上游请求/结果快照、source receipts、observation 与草稿均可通过统一 artifact 查询，不能用任意文件路径冒充上游来源。`get/events/execution/cancel/retry/recover` 沿用统一入口。

### 字段归并与阻断语义

来源版本：专家包 `v10.5 / 20260902` 的 SOP S-42/S-43/S-44、T-01 steps 24–28 与 Schema 1 CandidateRecord / Schema 2 AgentCHandoff；具体原文件与 hash 由规则 profile 绑定。本包工程外壳为 `t01/w4/local-wt-draft/0.1.0`、`document_kind=LOCAL_WT_ASSESSMENT_DRAFT`，不宣称满足 CandidateRecord 或 AgentCHandoff 完整 Schema。

| 本地草稿字段 | 生产者、现有依据与本包处理 |
|---|---|
| subject、protein_sequence、host_species、organism | 原请求事实；物种未提供保留 null，不把 user_sequence_id 当 accession 或病原体身份 |
| candidate_id、protein_id、evidence_level | S-42 / Schema 1；身份映射按 OI-014 待定、科学证据未签收，保持 null 与原因，不生成正式候选 ID |
| epitopes | N06 / S-19 → S-42 三图映射；原样保留开发字段及 null，失败时字段为 null、失败原因单列 |
| glycosylation | N07 / S-12；sequon 数量/位置保留。上游 `hotspot_assessment!=EVALUATED` 时草稿 shielding_risk 为 null；原始 false 与 NOT_PERFORMED 同存 observations，不能记成检查通过 |
| developability | N10 / S-36a～S-40；完整保留已执行维度、缺失/排除项、原分数/null、steps 与 risk_flags。部分 N10 增加 `N10_PARTIAL`，不重算 overall 或以 null 判 poor |
| N01–N10 其余 observations | 保留对应实际结果分量、上游警告与生产者路径；原始请求/结果另有 ArtifactRef 快照，不补正式交付字段 |
| dna_sequence、optimization_status、design_permissions、validation、stability_validation、delta_table、safety | 对应未执行生产者或无变体比较；值 null/`not_optimized` 并注明原因。实验安全恒为 NOT_ASSESSED |
| agent_c_payload、正式 WT/设计放行 | payload 为 null、放行为 false；S-43 可空摘要与 Schema 2 非空数值字段等生产映射仍归 OI-014，S-44 认证/幂等/确认仍归 OI-013；不构造或发送生产协议 |

`checks.executed` 仅表示存在上游 attempt，不等于成功或科学检查通过；`not_executed/missing/failed/pending/unsigned` 分别列明。`assessments` 保存任务执行状态与未签收身份，N10 steps 原样保留生产者的完成/未完声明，不能据本包回写其旧结果。科学检查是否全部通过为 null。

机器原因包括 `UPSTREAM_NOT_PROVIDED`、`UPSTREAM_NOT_TERMINAL`、`UPSTREAM_FAILED`（附实际 error）、`UPSTREAM_SCIENTIFIC_SIGNOFF_MISSING`、`N10_PARTIAL`、`HOTSPOT_SHIELDING_NOT_PERFORMED`，并固定列出 OI-013/014/021 对具体放行动作的阻断。草稿组装成功可使工程任务为 succeeded，草稿始终为 `local_wt_draft_review_required`；本地计算失败、停止或中断时 result.draft 为 null，已产生 raw 文件只作诊断证据。

### 本包工程验收

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_wt_draft_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_wt_draft_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\wt-draft-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w4\wt-draft-integration-new
```

验收必须使用未存在的运行根和 W4 批次。它实际执行无结构 N10 部分基线、两路预测均缺失时失败的 N06、独立 N07 sequon 扫描，复核上游绑定和草稿身份；不运行 AF3/ESMFold2 或补齐完整 N10。受控工具失败、停止和来源损坏分别标识，不冒充科学阳性。

2026-09-08 [工程验收 r02](../../../discovery/t01-phase1-real/w4/wt-draft-integration-20260908/acceptance-r02/index.json)为 PASS：23 个案例、5 个真实上游任务、324 份索引前文件、144 项发布产物核验。覆盖真实 N10 部分/未签收、N06 失败、合法缺失、排队/无结果取消、同序列与来源守卫、计算/输出失败、中断恢复/重试、幂等、统一 CLI 与产物查询、提交前后及原始产物篡改。r01 因验收脚本误将 N06 两路预测均缺失预期为成功而中止，原批次保留，不计 PASS。33 项 WT 单测覆盖额外资格/请求 binding 不一致、执行中取消、受控超时和计算期间来源变化，见 [专项日志](../../../discovery/t01-phase1-real/w4/wt-draft-validation-20260908/wt-tests-r01.txt)。根回归与文档检查结果见 STATUS 的本包验证摘要。

本包工程成果已完成；科学 Gate、完整 WT 交付、Agent C 生产接口和完整 W4 仍未完成。N10 原包部分身份及 OI-025/032/033 继续保留；本包未修改 r14/r06、专家原件、W1 冻结 Schema 或 Mock 资产。
