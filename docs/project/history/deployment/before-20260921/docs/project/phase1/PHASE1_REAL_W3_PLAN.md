# PH1-REAL-W3 阶段计划：糖基化、同源保守性与功能域

> 更新：2026-09-07。范围、完成标准和工具用法在本页维护；实际进度与当前执行包只见 [STATUS](../STATUS.md)。总体依赖与放行条件见 [一期交付计划](../PHASE1_DELIVERY_PLAN.md)。

## W3 阶段计划表

**阶段目标**：完成 N07–N09 的糖基化扫描、同源保守性和功能域注释。工具开发可独立推进，完整链仍消费具备适用资格的上游结果；提前开发 W3 不代表 W2 完成。

| 交付包 | 节点 | 交付内容与完成标准 | 具体依赖 |
|---|---|---|---|
| [糖基化扫描开发接入](#w3-糖基化扫描开发接入) | N07 / S-12 | **本机开发接入已完成**：序列扫描、结果查询、坐标与真实 N06 来源回连、空值/异常及适用任务生命周期已验证 | 独立扫描不依赖 NetMHC 或数据库；非 20 aa 热点窗口换算及科学消费见 OI-029 |
| [同源收集与保守性](#w3-n08-同源收集与保守性开发接入) | N08 / S-13/14/15 | 本地收集→去冗余→比对→保守性计算→区域提取，可追溯至数据库、序列及比对产物 | 工程接入使用明确标识的本机工程序列集及真实 MMseqs2/BLAST/MAFFT 资产；服务器批准同源库另作目标验收，不自动当作 N03 目标库 |
| [本地功能域识别](#w3-n09-本地功能域识别开发接入) | N09 / S-16 | 本地注释查询与坐标映射，区分无命中、数据缺失和需复核；保留适用结构检测与 core_map | 本地 UniProt 注释数据、版本与输入映射；无联网回退；OI-006 及结构/RSA 资格按分支控制 |

### W3 N09 本地功能域识别开发接入

**交付目标**：统一提交序列及可选拓扑、用户标注、结构/RSA，通过本地注释和确定性后端计算返回可追溯的功能域、坐标、来源、置信度与复核原因。依据 [SOP S-16](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)、[Schema](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md)及 R-37，工程实现和验收在同一包完成，不另建准备任务。

本机用明确标识的工程注释包验证真实解析、查询与计算，不要求复制完整服务器数据库。服务器已有数据库不等于已具备适用 UniProt 注释；目标验收前核实序列/条目身份、feature 格式、版本/来源/许可及库索引。复用环境库根、库 ID、manifest 与产物绑定机制，不开放公网查询或隐式同源注释转移。

- 实现 S-16 已明确的 feature 类型、描述关键词和独立 motif 扫描，保留来源与置信度；工程条目即使声明 reviewed，也不能获得真实科学参考资格。用户标注按原件采纳并保留其身份，不伪装成数据库注释。
- 复用真实 DeepTMHMM 产物，校验任务/尝试/ArtifactRef、序列与 hash；区分拓扑未提供、不可用及合法无区段。多聚蛋白 offset 和注释坐标来源须显式可追溯，避免对成熟序列坐标重复偏移；裁剪、丢弃、重叠取舍保留原因，歧义分支不猜规则。
- 保留可选结构检测和 core_map 的完整范围。无结构时按原件保持 core_map=null；有结构时复用已有映射/RSA 守卫，核实二硫键、界面和四分量规则及 Schema。OI-006 或未签收结构/RSA 只约束相应分支；明确几何计算可作未签收开发验证，不能凭缺失 RSA 补值或生成设计放行结论。
- 验证注释命中/无命中/库不可用、序列不匹配、用户标注、motif/拓扑回连、坐标边界/来源冲突、产物篡改及适用生命周期；引用权威规则和可复核参考案例，按共享变更影响回归。未定义的输入匹配、reviewed/unreviewed、坐标或合并语义具体回填 OPEN_ITEMS，不扩大为整个包等待。

**工程完成标准**：一条命令可从登记的工程注释包与实际拓扑产物得到已明确分支的功能域计算结果、来源及未完成项，统一查询和上述守卫通过；仅返回占位值或缺库诊断不算接入完成。可选结构分支分别报告已执行/缺输入/需复核，不静默移除。**目标完成标准**：服务器批准的真实注释库适配与实跑、相应科学规则/输入资格及目标复现完成；工程接入完成后可推进独立包，整个 N09 在目标要求齐备前仍未完成。命令与单批次证据回填本节，进度只见 STATUS。

**工程交付证据（2026-09-07）**：[最终 r04 索引](../../../discovery/t01-phase1-real/w3/domains-integration-20260907/acceptance-r04/index.json)记录 28 个场景、402 份索引前文件、262 项发布产物校验；独立 hash 与执行 profile 复核通过。实际执行 DeepTMHMM 及 4 个结构上游任务，验证真实拓扑、正常/缺失/出域 RSA，以及双链 Cys/界面阳性。44 项 N09 测试通过；当前实现根回归 1267 通过、1 项既有跳过，后追加的计时/取消测试单独通过。本机工程完成，目标数据与科学签收不随之完成。

#### N09 本机调用与接口

[N09 实现](../../../src/t01_phase1_real/development/domains)、[参考测试](../../../tests/test_domains_development.py)与[工程验收脚本](../../../scripts/run_domains_acceptance.py)使用独立 `t01.real.domains / N09` 注册，复用同一 SQLite 任务、幂等、事件、ArtifactRef 与停止/恢复机制。N09 在可信本机 Python/Biopython 1.88 中计算，不联网；真实 DeepTMHMM 和结构上游沿用各自固定禁网镜像。工程注释中的 reviewed 标记仅用于测试规则路由，所有结果保留 `DEVELOPMENT_UNREVIEWED / usable_for_pipeline=false / automatic_handoff=false / NOT_DEPLOYED`。

从已完成批次的真实拓扑来源运行一条命令（引用 ArtifactRef 必须在同一个运行根内；新 key 创建新 N09 任务）：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\domains-acceptance-r04 --domains-database-root D:\work\蛋白智能体\discovery\t01-phase1-real\w3\domains-integration-20260907\acceptance-r04\databases domains --input D:\work\蛋白智能体\discovery\t01-phase1-real\w3\domains-integration-20260907\acceptance-r04\requests\documented.json --key documented --run
```

上述 `documented` key 回读已执行结果；验收末尾会受控篡改上游拓扑发布副本以验证守卫，因此该批次结束后不再用旧上游创建新任务，原始拓扑证据保存在批次中。需要全新可调用上游时运行下方完整新批次，或在新运行根实际提交 DeepTMHMM 后构造对应 ArtifactRef；不可只复制 JSON 到另一个任务库冒充已登记来源。

请求精确字段为 `protein_sequence/user_sequence_id/organism_name/database_id/database_manifest_sha256/entry_id/parent/topology_input/structure_input/user_annotations/timeout_seconds`。序列为严格 AA20 大写 1–20000 aa；上游另遵守各自输入域。`entry_id` 可为空或显式 accession；查询仅采用序列与 organism 精确匹配，多命中不自动择一，不作同源注释转移。`parent` 为空或 `{id,offset,sequence}`，必须验证成熟序列等于原序列的声明切片。用户标注使用成熟坐标 `{type,start,end,note}`，逐条保留 `user_annotation / user_high`。

`topology_input/structure_input` 均为 `{state,artifact,reason_code}`，区分 `not_provided/available/upstream_unavailable`。真实来源核对任务、尝试、登记、hash、同序列及成功/失败身份；结构进一步回连原文件字节及已验证映射/RSA，N09 不接受请求自报 RSA 数组。已在成熟序列上计算的拓扑和结构坐标不再次偏移。真实拓扑 TM/signal 保留为 source-verified observation；其 S-16 confidence 未定义时保持 null，不自行赋高置信功能域。

本机工程注释包以环境根 + 登记 ID + manifest hash 定位，固定 N09 用途、资格、来源/版本/日期/许可/引用及 payload hash。当前包包含 `manifest.json` 与 `entries.json`，后者最多 500 条 UniProt-shaped 条目（每条最多 500 features），不代表服务器大库适配已完成。原 feature 的 `type/description/location` 和每条 `coordinate_spaces` 一起保存。精确/不确定坐标分开；成熟 Chain 不减 offset；parent feature 依 ToolSpec 减 offset−1，并记录裁剪/丢弃。具体校验见 [policy.py](../../../src/t01_phase1_real/development/domains/policy.py)。

后端实现 12 类 L1、3 类 L2 关键词与 5 类独立重叠 motif 扫描。已明确重叠按 overlap/min(length)≥0.80 去重，原文全局/排序语义发生分歧时记录复核。TrEMBL 未定义降级档、不确定坐标、多类别冲突、拓扑缺省等均保留原始事实及原因，不变为无功能域科学结论。

结构分支回连现有映射与 FreeSASA 资格守卫；开发计算 Cys Cβ 距离 <6 Å、链间重原子距离 <4.5 Å、packing/contact 分量与接触图。Gly 无 Cβ 不补 CA，归一化零分母为 null。network 两种接触计数解释均记录，仅结果一致时输出开发布尔值；三态条件按 S-16 实现，操作数不足时不猜状态。无结构、无 RSA、RSA 出域和映射不唯一分别记录，缺失或出域 RSA 不生成 burial。正式 `core_map` 继续 null，开发分量仅在 `structure_assessment.components` 提供；OI-006 与 [OI-031](../OPEN_ITEMS.md#n09-注释与结构分支的具体待确认项oi-031) 控制相应科学消费。

复核及全新批次命令（root/batch 必须不存在，完成索引不可覆盖）：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_domains_development.py tests/test_homology_development.py tests/test_epitope_map_development.py tests/test_glycosylation_development.py tests/test_structure_development.py tests/test_deeptmhmm_development.py -q
.\.venv\Scripts\python.exe -X utf8 scripts/run_domains_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\domains-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w3\domains-acceptance-new
```

### W3 N08 同源收集与保守性开发接入

**交付目标**：在同一包内接通序列收集、去冗余、分组、MSA、逐位保守性与区域提取，统一提交/查询并回连数据和实际工具产物。依据 [SOP S-13/S-14/S-15](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)、其引用的 R-06～R-11 及 [Schema](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md)适用章节；不新建准备、实现或补证任务页。

**环境安排**：本机暂时无正式数据库，部署服务器已有数据库但其 N08 适用性尚未核实。本机使用明确标识的工程序列集与注释，真实执行 MMseqs2/MAFFT，按适用调用复用已完成的 BLAST 引擎；服务器核实同源库后再作真实目标库验收，不要求复制完整库到开发机。N03 与 N08 的数据用途分别登记，不自动共用目标库，不恢复旧 S07 或公网查询。

- 固定工具版本、来源/许可及离线执行资产；复用现有任务与库身份机制，核验输入序列、注释、索引和 manifest。保留来源、疫苗株分离及分型/宿主缺失事实，不虚构谱系或样本来源。S-13 要求的补充检索仅使用已批准的本地库；不足时披露，不联网补齐。
- 按原件落实去冗余、分组、置信度及 MSA 复用。S-13 已产生的全局比对交给 S-14 使用，不重复全局对齐；组内计算的比对作用域应有明确来源。先核对规则顺序与字段，原件不能唯一确定的分支登记具体问题，其余继续。
- 按 S-14 计算熵、保守分数/分级与不可靠位置，按 S-15 提取区域、固定位置及原件规定的逐级放宽历史。明确比对列与查询序列坐标回连；全 gap、缺失、零序列或退化情况无明确依据时保持复核，不猜分数，不把失败当空成功。
- 验证真实工具链、合法空结果、稀疏/缺注释、比对完整性、库或工具不可用、来源/产物篡改及适用生命周期；参考计算、工程夹具与服务器数据证据分别记录。共享代码按实际影响回归，保持未签收和禁止自动交接。

**工程完成标准**：一条命令从登记的工程序列集运行真实工具，得到可回连的 MSA、已明确分支的逐位保守性、区域及失败/复核原因；覆盖上述守卫并有可复核参考计算。只完成接口或模拟结果不算工程接入完成。**目标完成标准**：服务器批准同源库的检索与整链实际执行通过，来源/版本/索引可追溯；工程部分完成可转入下一独立包，但目标数据未验收时整个 N08 继续保持未完成。命令与一份批次索引回填本节，进度只见 STATUS。

**本机工程交付证据（2026-09-07）**：[最终 r05 索引](../../../discovery/t01-phase1-real/w3/homology-integration-20260907/acceptance-r05/index.json)记录 19 场景、516 份索引前文件与 406 项发布产物校验，独立 hash 复核通过。覆盖真实收集/去冗余/比对、全同参考、区间统计、缺注释/独立分组、短序列原生失败、零收集、库/工具/输出失败、幂等、取消/超时、两种崩溃恢复、重试、单命令及篡改守卫。26 项 N08 测试和受影响回归已通过。只计本机工程完成，目标数据验收和科学签收保持未完成。

#### N08 本机调用与接口

统一入口以 `t01.real.homology / N08` 接入原任务库；[实现](../../../src/t01_phase1_real/development/homology)、[验收脚本](../../../scripts/run_homology_acceptance.py)与[参考测试](../../../tests/test_homology_development.py)独立于旧 Mock/S07。固定镜像包含 MMseqs2 `14-7e284+ds-1+b2`、MAFFT `7.505`、原 NCBI BLAST+ `2.17.0+` 的二进制与共享库；镜像 ID、版本实测、来源与包内许可见 [资产收据](../../../src/t01_phase1_real/development/homology/assets.json)。构建安装工具时联网，序列执行一律 `network=none`、根只读、2 CPU/4 GiB、独立容器槽。MMseqs2 原生工作流要执行其生成的 shell 脚本，因此仅 N08 容器内 `/tmp` 允许执行；不授予宿主额外命令能力。

本机一条命令提交并取得真实结果（示例数据已标为工程用途，重复 key 返回原任务；新运行使用新 root/key）：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\homology-local --homology-database-root D:\work\蛋白智能体\discovery\t01-phase1-real\w3\homology-integration-20260907\acceptance-r05\databases homology --input D:\work\蛋白智能体\discovery\t01-phase1-real\w3\homology-integration-20260907\acceptance-r05\requests\documented.json --key n08-example-001 --run --wait 60
```

请求精确字段为 `protein_sequence/user_sequence_id/organism_name/protein_name/database_id/database_manifest_sha256/source_filter/group_by/sequence_weighting/query_range/timeout_seconds`。序列要求严格 AA20 大写、9–20000 aa；字符不替换。9 aa 工程集已观察到原生 MMseqs2 无法提取 k-mer 并失败，准入不保证所有长度可执行，失败不作空成功。`source_filter=wild_type`、`sequence_weighting=off`；`group_by=subtype|host_species|both`；`query_range=null` 或 1-based 闭区间；超时 1–900 秒。CLI 同时提供 `get/result/events/artifact/cancel/retry/recover`，使用同一 job/attempt/ArtifactRef 生命周期。

数据库通过操作者配置的绝对本地根、登记 ID 与 manifest SHA-256 解析，请求不能指定文件路径或命令。当前开发包每库最多 500 条，每条最多 20000 aa，包含 `sequences.fasta`、`annotations.json`、`manifest.json` 三个文件，适用于本机工程验收，尚非大库服务器适配。manifest 固定 N08 用途、`ENGINEERING_FIXTURE` 或 `TARGET_DATABASE_UNREVIEWED`、来源/版本/日期/许可/引用与逐文件大小/hash；注释精确字段及完整验证见 [policy.py](../../../src/t01_phase1_real/development/homology/policy.py)。前后两次核验、容器内复核、原数据副本和结果回读互相绑定；N03 数据库不能自动用于 N08。

收集按 organism/protein 原始注释精确匹配，分离疫苗株并保存 lab/unknown 排除事实，对 wild 输入全集一次 MMseqs2 `--min-seq-id 0.99 --alignment-mode 3` 去冗余，其余采用固定版默认参数；保留所有 cluster 成员及代表原注释，不生成虚构谱系。少于 20 条时真实本地建库/BLAST 补充检索，保留原始命中和索引 hash，因补充准入科学阈值未定义，`automatic_admission=false`，不冒充 NCBI nr 或联网补齐。

MAFFT 全局执行一次，查询序列作为单独坐标锚点，明确不计入 N_eff、熵、gap 或分组统计。S-14 与各组复用同一 MSA/原列；输出逐列熵、分数、分级、不可靠位置、MSA 列↔查询残基映射及查询逐位数组。组内结果分别保存；混合分型全局值仅为诊断，不代替目标分型选择。置信度不足独立分层证据时降档，工程标签不构成科学谱系。S-15 已明确连续段按三档提取，输出固定位置与逐档历史；无段为 `quality_flag=failed / regions=[] / fixed_positions=[]`。全 gap、不可靠位点、短段桥接及未知分型相关歧义分支保持 null/复核；区间查询返回 mean/min/max，未定义的整体 class 保持 null。具体冲突、主责和关闭证据集中在 [OI-030](../OPEN_ITEMS.md#n08-同源保守性的具体待确认项oi-030)。

所有输出为 `G0_REAL_OUTPUT / DEVELOPMENT_UNREVIEWED / usable_for_pipeline=false / automatic_handoff=false / NOT_DEPLOYED`。本机工程参考、原生失败、故障注入与服务器目标验收分别标识。整包 N08 的目标库适配/实跑和科学签收仍需完成，不因本机链通而关闭。

复核与新批次命令如下；新批次必须使用尚不存在的 root 和 batch，已完成索引不覆盖：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_homology_development.py tests/test_blast_development.py tests/test_epitope_map_development.py tests/test_glycosylation_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_homology_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\homology-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w3\homology-acceptance-new
```

### W3 糖基化扫描开发接入

**交付目标**：复用现有统一任务入口，让输入序列可执行 S-12 本地扫描并查询可追溯结果。设计、实现、测试与必要补证在本包内完成，不等待 NetMHC 原包，不新增准备包。依据 [SOP S-12](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)、[Schema glycosylation](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md)与 [R-25/R-26](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md)的适用条款。

- 实现 N-X-S/T（X≠P）扫描、1-based 位点与数量、原件规定的表达提示，以及输入/方法/产物来源；位点表示序列模式命中，不冒充实验糖基化证据。
- 热点为可选输入。按 SOP 保留空/None 时的字段语义，并披露未作热点遮蔽判定；不得把上游失败或未计算伪装成已完成的空热点。提供热点时核对坐标、计数与“峰值 20 aa”规则的明确依据；若原件不能唯一确定窗口或边界，仅该判定分支保持复核，具体问题归 OPEN_ITEMS，继续完成独立扫描。
- 无位点是合法结果；未执行、合法空结果、非法输入和计算失败分别表达。验证边界/重叠模式、坐标回连、热点缺省及适用的幂等/停止/恢复/产物完整性；按共享代码实际影响补已有工具回归。沿用后端计算与现有运行机制，不为纯计算验收强行增加容器调用。

**开发完成标准**：一条命令可从提交序列到取得真实计算结果与原始输入回连，有可复核的参考案例和上述守卫证据；适用已明确规则通过验证，未定分支明确披露并保持关闭。单批次索引记录独立扫描和热点契约夹具各自身份；未完成真实热点联调时不宣称 N06→N07 全链通过。用法回填本节、成果与剩余条件回填 STATUS，未签收开发结果继续禁止科研消费和自动交接。

**当前结果（2026-09-07）**：N07 独立扫描开发接入已完成。统一入口登记 `t01.real.glycosylation / N07`，绑定执行 profile 与 S-12/R-25/R-26 规则 profile；可信本地后端使用 Biopython 1.88 与支持重叠的正则前瞻扫描，不启动容器、不访问网络。请求、原始 FASTA、计算 observation、结果、事件及执行事实均进入现有 SQLite/ArtifactRef 生命周期，固定为 `G0_REAL_OUTPUT / DEVELOPMENT_UNREVIEWED / usable_for_pipeline=false / NOT_DEPLOYED`。

一条独立扫描命令如下；`--sequence` 路径会把热点状态显式记为 `not_provided`，同步计算结束后直接返回任务和结果：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\glycosylation-local glycosylation --sequence NNSTAAANPSAAANAT --user-id overlap-reference --key n07-example-001 --run
```

需提供热点或表达上游失败时可使用 `--n06-job-id <N06任务ID>` 自动构造请求，也可使用 `--input request.json`。请求固定字段为 `protein_sequence`、`user_sequence_id`、`hotspot_input`、`timeout_seconds`；`hotspot_input.state` 仅允许 `not_provided`、`upstream_unavailable`、`available`。前两种必须使用 `hotspots=null`，结果保持 Schema 要求的 `shielding_risk=false`，同时以 `hotspot_assessment.status=NOT_PERFORMED` 明示未判定；`available` 可用空列表表示已计算且无热点，非空区间必须是已排序、去重、1-based 闭区间且恰为 20 aa。真实来源使用完整 N06 结果 ArtifactRef，运行时核对任务/尝试、登记、大小、SHA-256、结果身份和同序列绑定；旧 `node_id/source_id/sha256` 形态仅保留合同夹具，并明确标记 `CONTRACT_FIXTURE_NOT_ARTIFACT_VERIFIED`。后端按 sequon 的 N 位点计数，单个窗口内 ≥2 个置 `shielding_risk=true`。

独立扫描支持 1–20000 aa 的严格大写 AA20；不做字符替换或归一化。0 个 sequon 返回成功且 `sites=[] / site_count=0 / expression_hint=null`，不是未执行；≥3 个 sequon 返回 `expression_hint="真核表达优先"`。输出同时保留命中三肽和 1-based N 坐标，并固定提示：sequon 命中只是序列模式，不是实验糖基化证据。

[W3 独立验收索引](../../../discovery/t01-phase1-real/w3/glycosylation-integration-20260907/acceptance-r01/index.json)记录 16 个案例和 139 份索引前文件：8,000 个 AA20 三肽穷举得到规则期望的 38 个命中，另覆盖重叠/边界、合法空结果、热点缺省/上游失败/已提供空列表/20 aa 风险、非法输入、幂等冲突、排队取消、失败恢复与重试、损坏 observation 和发布产物篡改检测。独立扫描案例与热点契约夹具分开标识。[N06 联调索引](../../../discovery/t01-phase1-real/w2/epitope-map-integration-20260907/acceptance-r04/index.json)另以实际 N06 结果验证 N07 来源 ArtifactRef、同序列和提交后哈希损坏；当前真实 N06 热点为 null，故来源校验完成但 `hotspot_full_chain_validated=false`。两批均无科学签收和自动交接。

针对性复核及新批次命令：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_glycosylation_development.py tests/test_netmhc_development.py tests/test_bepipred_development.py tests/test_deeptmhmm_development.py tests/test_structure_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_glycosylation_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\glycosylation-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w3\glycosylation-acceptance-new
```

第二条必须使用不存在的新运行根和 W3 批次目录；已完成索引不可覆盖。真实 N06 来源绑定已在 N06 批次完成；当前未完成项是非 20 aa 上游热点如何换算为 20 aa 判定窗口、N06 尚未产出的可消费 B 细胞热点及相应科学签收/目标发布，不反向否定本次独立 sequon 扫描开发完成。

