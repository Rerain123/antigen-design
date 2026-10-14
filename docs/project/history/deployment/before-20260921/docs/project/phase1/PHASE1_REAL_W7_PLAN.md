# PH1-REAL-W7：条件密码子优化、WT 稳定性参考与交付

更新：2026-09-10。实际进度与下一项见 [STATUS](../STATUS.md)，总体范围与放行见 [总计划](../PHASE1_DELIVERY_PLAN.md)。进入 W7 是独立工程推进，不表示 W1–W6 或科学验收已完成。

## 阶段交付表

**2026-09-19续行要求：** 按[专家流程校准计划](../PHASE1_DELIVERY_PLAN.md#专家流程校准与单卡执行计划2026-09-19)第6–7项补齐真实候选DNA绑定、适用WT扫描触发与条件汇合。N17历史参考组装`scan_invocations=0`不作为新扫描验收；N18必须区分候选、WT和失败结果，禁止以空设计报告代表科学全链。新GPU扫描遵守单张A100 64GB约束，已通过独立工具验收不重开。

| 包 | 完成目标 | 具体依赖 |
|---|---|---|
| N16 条件密码子优化工程（已实施） | 显式表达宿主、固定本地密码子表、真实优化、翻译及约束校验、统一任务与产物查询 | E.coli 明确表 profile 工程完成；OI-004 未定宿主/参数分支关闭，验收见下文 |
| N17 WT 稳定性参考业务回连（工程已实施） | 复用双引擎形成适用扫描范围、排除位置、参考结果与限制说明 | 历史扫描来源回连完成；权限、结构与 OI-011 适用签收仍缺，引擎参考不等于完整科学节点 |
| N18 本地交付组装及外部交接（本地工程已实施） | 汇合 WT/候选/失败产物与来源、缺项及方法记录，适用条件满足后交接 | 本地ZIP/报告完成；OI-013/014、正式资格与目标接口仍缺，不自动发送 |

每包连续完成实现、测试和必要证据，不拆成准备/评审任务。后两包在实施时按原件细化，不预建接口或空证据。

## N16 条件密码子优化工程

依据 [现行范围](../PHASE1_SCOPE_REBASELINE.md)、[SOP S-30](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)、[SKILL R-36](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md)及 [OI-004](../OPEN_ITEMS.md)。目标是明确工程蛋白输入→本地反向翻译/优化→逐项校验→可查询的工程 DNA 产物，不开展实验或正式表达方案设计。

1. `expression_host` 与蛋白来源 `host_species` 分离。缺少表达宿主按现行 N16 条件路由跳过，不猜宿主；明确但未支持的值失败。原始 S-30 未指定宿主 halt 不能覆盖后续一期条件路由决定。
2. 固定 DNA Chisel、Biopython 及实际依赖/表资产，记录来源、版本、hash 和离线运行方式。只开放有明确依据且资产齐备的宿主 profile，不把原件列出的全部宿主宣称为已支持。BHK-21 近似映射、VERO 缺项和其他别名按 OI-004 核对，不自行套用其他物种。缺表阻断相应宿主，不阻断已有完整 profile 的真实工程验证。
3. 核验反向翻译与实际优化；保持编码蛋白序列一致。按 S-30 的明确约束实现翻译保持、GC 与指定限制性位点检查；“等”所代表的额外位点、起止密码子、遗传密码表及优化目标等未定细节先查原件，不自行扩大需求。所有实际参数在 profile 记录。
4. CAI 为后端计算而非 DNA Chisel 原生输出，方法/参考表与边界须有明确依据和独立参考；未定义时保持 null/复核，不发明合格阈值。优化失败按原件区分返回未优化 DNA 与执行失败，标明未满足的约束，不把回退产物称为优化成功。
5. 接入统一提交、查询、幂等、取消/超时、恢复/重试和来源/发布 hash。允许明确标记的独立工程序列实跑，但不得自动将原24条已淘汰变体送入正式优化或恢复其资格；无合格候选的业务链保持跳过/失败报告。

**验收与完成标准**：至少一个有来源的本地宿主 profile 真实完成优化与独立翻译回验，约束逐项可复算；验证宿主缺失/不支持、缺表/hash 错误、非法序列、不可满足约束或优化失败的明确回退、来源/产物篡改和适用生命周期。明确原件要求的其他宿主尚未覆盖范围，不能以一个 profile 通过宣称全部宿主交付。真实调用、故障注入和数值夹具分开记录，受影响回归通过；命令与真实索引回填本节。

工程产物保持未签收、不可科研消费、不可自动交接。完整 N16、W7 与正式部署仍需适用支持目录、科学规则和目标验收；N10、真实热点、结构预测和 W5/W6 未决分支继续在原包跟进。

## N16 本机接口与实施回填

2026-09-09：`t01.real.optimize_codons / N16` 已接入现有 SQLite 任务、幂等、事件、ArtifactRef、查询和重试。主验收 [acceptance-r01 索引](../../../discovery/t01-phase1-real/w7/codon-integration-20260909/acceptance-r01/index.json)记录 23 个任务案例、7 项守卫、197 份文件及 113 项发布产物；独立审计核验 6 次真实成功优化、1 次真实不可满足约束回退。成功次数包括故障后的新任务重试，不是六个科学候选。原24条排除记录未读取、未优化、未修改资格。

### 固定宿主与计算边界

- 仅开放精确 `expression_host="E.coli"` 配合 `host_profile="ecoli-k12-w3110-kazusa-316407-v1"`。调用方必须明确选择表 profile，不将属种或别名自动替换为株系。表来自 `python-codon-tables==0.1.18` 的 Kazusa 派生本地 CSV，原始字节 SHA-256 为 `b7eb52a39dce8c4ed4475f4a6032333dc2eff47eb2b1f756209c14569ffc4ace`。[Kazusa 原站](https://www.kazusa.or.jp/codon/cgi-bin/showcodon.cgi?aa=1&style=N&species=316407)标明 W3110 与标准遗传密码表；该在线核对仅为资料核验，运行时不访问网站。
- [资产清单](../../../src/t01_phase1_real/development/codon/assets/manifest.json)固定 DNA Chisel 3.2.16、Biopython 1.88、NumPy 2.4.6、python-codon-tables 0.1.18、docopt 0.6.2、flametree 0.2.1、proglog 0.1.12、tqdm 4.70.0、colorama 0.4.6 的版本与安装文件 hash；[精确依赖](../../../src/t01_phase1_real/development/codon/assets/requirements.txt)用于重建。代码固定 manifest hash；执行前后复核表和依赖内容。禁止以运行时重新生成清单的方式接受漂移。
- 请求仅接受 `INDEPENDENT_ENGINEERING_SEQUENCE`；1–1000 个 AA20 大写残基，无空白、X 或 `*`。`coding_policy="standard_fragment_no_added_start_or_stop"` 显式选择标准表1的编码片段，不添加起止密码子、载体、接头或信号肽。此为本包工程输入边界，未据此定义完整生产 CDS。
- 初始 DNA 逐残基选最高使用频率密码子，并列按字典序。CSV 保留 Kazusa 两位小数原值；传入工具前仅按同义组总和归一化，不改相对比例。64个密码子覆盖、唯一性、标准翻译和频率数值均校验。
- DNA Chisel 使用 `CodonOptimize(method="use_best_codon", codon_usage_table=本地表)`、显式翻译保持、全片段 GC 40%–60%（含边界）、BsaI/BpiI 双链识别位点规避。固定 NumPy seed 1601、`max_random_iters=1000`；优化目标采用该工具的默认方法并在 profile 披露，工程通过不表示全局最优。[官方规格说明](https://edinburgh-genome-foundry.github.io/DnaChisel/ref/builtin_specifications.html)为 API 核对依据。独立后验不调用 DNA Chisel 约束评估器，重新翻译、整数比较 GC 上下界并扫描完整正反向识别串，包含末端位点。
- 当前库实际实现把 `start_codon=False` 也视为已指定起始策略；本包按已核对源码使用 `None` 表达无新增起始要求。未将文档示例照抄为生产语义。
- `cai_score=null`，原因 `OI_004_CAI_METHOD_REFERENCE_AND_BOUNDARIES_UNAPPROVED`。工具内目标分数不是已签收项目 CAI；不另造合格阈值。额外限制位点、完整 CDS 起止/遗传表例外、生产目标和 CAI 仍由 OI-004 具名签收。

### 请求与查询

下面命令实际使用主批次保存的独立20残基请求；新运行根不会接触原候选。输入 JSON 的完整字段可直接查看[真实请求](../../../discovery/t01-phase1-real/w7/codon-integration-20260909/acceptance-r01/cases/aa20-real/request.json)。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root var/t01-phase1-real/n16-local-new optimize-codons --input discovery/t01-phase1-real/w7/codon-integration-20260909/acceptance-r01/cases/aa20-real/request.json --key n16-engineering-001 --run
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root var/t01-phase1-real/n16-local-new result --job-id <返回的job_id>
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root var/t01-phase1-real/n16-local-new artifact --job-id <返回的job_id> --artifact-id <返回的artifact_id> --output <新的本地文件路径>
```

统一 `get/events/execution/cancel/recover/retry/wait` 同样可用。原始产物含请求、表、依赖清单、来源 receipt、attempt 绑定、工具观察及 initial/optimized FASTA；回退只提供 initial FASTA。统一结果含 `dna.initial_dna/optimized_dna/returned_dna`、返回类别、逐项校验、失败原因和参数。请求字节、序列、job/attempt/execution、表来源和全部发布产物均可回查 hash。

| 条件 | 任务及结果 | DNA 语义 |
|---|---|---|
| 宿主及 profile 均为 null | `succeeded / skipped_missing_expression_host`，不启动工具 | null；这是条件跳过，不是优化或科学通过 |
| 不支持宿主（含尚未支持的别名） | `failed / UNSUPPORTED_EXPRESSION_HOST` | null；要求批准的表/profile，不猜替代物种 |
| E.coli 未明确选择已登记表 | `failed / HOST_PROFILE_REQUIRED` | null |
| 缺表、hash 不符、依赖漂移 | 明确 `CODON_TABLE_MISSING / HASH_MISMATCH / DEPENDENCY_*` | null |
| 工具正常优化且后验一致 | `succeeded / optimized_engineering` | 优化后 DNA，仅工程未签收 |
| 原生 `NoSolutionError` | `succeeded / optimization_incomplete`，WARNING | 原始未优化 DNA；列出原生失败及未满足约束 |
| 执行异常或输出后验错误 | `failed / TOOL_FAILED` 或 `OUTPUT_INVALID` | null，不伪装成优化回退 |
| 取消、超时或进程中断 | `cancelled / timed_out / failed(INTERRUPTED)` | null；确认停止后终态，新任务重试 |

`host_species` 不属于本请求字段，不能代替 `expression_host`。CHO、HEK293、Sf9、BHK-21、VERO、MDCK、CEF 均未开放；不声称原件宿主目录已全部覆盖，不启用 BHK-21→小鼠近似映射。完整科学 N16、候选接入、N18 自动交接和正式部署继续关闭。

### 执行与验收

优化进程由 Windows Job Object 管理，1 GiB 内存、最多4个进程（包括 Windows venv 启动器），kill-on-close；Python audit hook 拒绝 socket 和子进程接口。它是可信本地固定代码的离线执行边界，不宣称已提供远程多租户 OS 网络沙箱。取消/超时终止所属进程树；调度进程失联先确认 Job Object 停止，再登记 INTERRUPTED，恢复不重跑原 attempt。

真实 `AAAAAKKK` 工程片段初始 GC 62.5%，优化后 58.33% 且翻译完全一致；`WWWWWW` 只有 TGG，GC 2/3，触发真实不可满足约束及未优化回退。任务验收区分真实工具、故障注入和守卫；没有以 Mock 或空数据代表科学结果。独立审计命令如下：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/audit_codon_evidence.py discovery/t01-phase1-real/w7/codon-integration-20260909/acceptance-r01
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_codon_development.py tests/test_codon_evidence_audit.py tests/test_codon_lifecycle.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_codon_acceptance.py --batch acceptance-new
```

第三条仅用于需要重跑时，必须使用尚不存在的新批次。主验收之外，生命周期测试还实际终止已登记调度进程、核验所属子树停止、恢复并新任务重试，以及 CLI 真正提交/查询。测试覆盖来源提交后篡改、执行后来源变化、发布篡改、禁止网络调用和归档审计器的坏 hash/缺文件/额外文件拒绝。验证记录见本包的 [验证摘要](../../../discovery/t01-phase1-real/w7/codon-validation-20260909/summary.json)。工程完成，后续包由管理任务安排。

受影响验证：当前根回归 1643 passed / 1 skipped；随后新增的审计器及真实崩溃/CLI测试纳入最终专项检查，N16 39项与文档56项共95项通过。现行文档检查通过，历史29处失效引用不变；冻结 Mock 457项只读核验一致。未跨历史分区，旧完整 Mock/S07 未重跑。主验收源码快照和 execution/rule profile 与当前实现复核一致；完整生产 `NOT_DEPLOYED`。


## N17 WT 参考回连与 N18 本地交付组装

管理安排：N16 独立工程已完成，下一包合并完成末端业务组装，复用稳定性双引擎、WT 草稿和逐变体报告，不重复搭建工具。依据 SOP T-01 step22/24–28、S-31/S-42/S-44、Schema 与现行范围；OID 及科学未决项仍在 OPEN_ITEMS 单点维护。

**目标**：同一 WT 的可追溯分析/稳定性参考、候选排除和适用 DNA 记录，汇合成一个本地工程交付包，具备机器索引、可读报告、文件校验与统一查询。包内身份明确为开发未签收，不能冒充正式 CandidateRecord/AgentCHandoff 已通过。

1. N17 复用真实 FoldX PositionScan/ThermoMPNN 记录，绑定同一 WT、结构、扫描范围、排除位置和工具身份；不把不同序列/结构批次合成双引擎共识，不把 BuildModel 候选打分替代 WT 扫描。只有匹配的实际比较集合和明确规则才能作工程排名；跨引擎不平均 ΔΔG。缺结构/权限、未执行、跳过和失败分别保留。
2. 扫描触发依照现行门控，膜蛋白与低质量等原件冲突或未定分支保留复核，不新增扫描旁路。独立工程参考不授予科学资格。已有数据不能同 WT 回连时留缺项，不能为了报告完整嫁接9 aa与76 aa批次。
3. N18 按现有生产者映射汇总 WT 草稿、N13/逐变体报告、适用 N16 DNA 与 N17 参考；核验各层 ArtifactRef、hash、序列、变体及表达宿主身份。独立密码子测试片段不可当作 WT 或候选的 DNA；缺失则明确未提供。
4. 区分设计未执行、设计后全淘汰、上游计算失败和可供复核的工程记录。原24条全淘汰保持无最佳候选，可生成本地 WT/失败说明，但不能未经适用 Gate 把它变成正式 WT 交付。不生成正式候选 ID、伪造已签收字段或自动发送 Agent C。
5. 交付包至少包含可读摘要、机器数据、来源/方法与缺项清单、实际文件清单及hash。保持原批次不变，明确哪些资产留在服务器或因许可仅提供引用；导出仅限登记产物，不复制凭据。复用统一查询、导出和适用生命周期，不新建第二套任务系统。

**验收标准**：原24条全淘汰真实批次得到一致的本地说明；独立稳定性批次形成正确WT参考且不跨批嫁接；N16配对/未配对、上游缺失/失败/未签收、错误WT/变体/宿主、损坏引用及发布篡改均正确处理。包内链接和hash可验证，整包与单项查询可复现；阳性正式交接只能作为有标记契约测试，不冒充生产实跑。按改动影响回归，命令和新索引回填本节。

**完成边界**：本地工程组装成功不代表科研可用或正式发布。OI-013/014、各节点科学资格、目标部署与真实完整流程仍需独立完成；科学条件未齐时输出具体差距，不以空值补成全链PASS。包完成后由管理任务统一核对全项目工程缺口与外部依赖，再确定下一轮，不自动宣布一期完成。

## N17 与 N18 本机接口

实施：2026-09-10。`t01.real.wt_reference / N17` 与 `t01.real.local_delivery / N18` 在现有 registry、SQLite、生命周期、查询和 ArtifactRef 中增量登记；不改冻结 W1 Schema，也不建立第二套运行系统。

N17 请求包含 `protein_sequence/user_sequence_id/timeout_seconds` 和显式 upstream 五槽：`structure/foldx/thermompnn/design_audit/topology`；缺项为 null，已提交但未完成任务用精确 job_id 和 null artifact，已终态用原登记 result/diagnostic 引用。对所有来源验证工具、请求、WT 序列、尝试/规则/执行 profile、资格和全部已发布文件 hash。FoldX 仅接受 PositionScan；两引擎输入必须与显式结构 ArtifactRef 完全相同，不能仅靠序列相同或复制分数配对。原生输出按既有解析器重新核验，保留请求扫描集合、排除位置、实际有效位置、原生引擎排名和扫描来源；不会调用新扫描。

N17 返回 `reference.engines`，各引擎包含原始 records、来源、范围和缺项；保留同义 WT 自身记录，排名仍是原引擎比较集合内的工程排名。`common_observed_mutations` 仅列已匹配键，`same_comparison_set` 明示集合是否相同；`combined_ddg/consensus_ranking/scientific_pass=null`。现有实测两引擎对应不同登记结构分析批次，分别形成参考，不强行生成“双引擎共识”。权限资料可回连时列出 FIXED∪RESTRICTED 与历史有效扫描的交集，只作违规范围复核，不重新授予权限或启动扫描。缺权限/拓扑、结构质量和未执行/失败/多链跳过状态保留；膜蛋白、低质量等门控未定分支不被参考回连绕过。

N18 请求包含 `protein_sequence/user_sequence_id/host_species/expression_host/timeout_seconds`、upstream 三槽 `wt_draft/variant_report/wt_reference` 及 `dna_bindings`。逐层回放 WT 草稿、N13 所在变体报告与 N17 原始来源，要求提供过的 WT 结构引用一致。DNA 绑定字段为 `subject`（WT 或报告内精确变体 ID）与 `source`；校验该对象序列和表达宿主后，再判断用途适用性。现有 N16 只有独立工程序列 profile，因此即使序列/宿主相同也登记 `INDEPENDENT_ENGINEERING_DNA_NOT_BUSINESS_APPLICABLE`，不附到 WT 或候选 DNA；不匹配序列/宿主、未知变体和损坏引用直接拒绝。缺 DNA 明记 `DNA_NOT_PROVIDED`。

N18 输出 `delivery` 和原始 `output/package.zip / report.md / package-manifest.json`。ZIP 包含机器数据、可读报告、已登记上游请求/结果和文件清单；每个文件有大小/SHA-256，清单不自包含，其本身由 ZIP 的已登记 ArtifactRef hash 覆盖。原始工具文件、模型、服务器资产和受许可限制的工具只保留来源引用，不复制工具、密钥或凭据；这不是可脱离原资产重跑模型的离线环境包。ZIP 内链接采用固定相对路径，可离线阅读。

结果明确区分 `DESIGN_NOT_EXECUTED / DESIGN_INPUTS_UNAVAILABLE / UPSTREAM_FAILED / ALL_EXCLUDED / ENGINEERING_RECORDS_REVIEW_REQUIRED`。`ALL_EXCLUDED` 保留每条原淘汰原因、null 最佳候选和原报告，不转成已通过 Gate 的 WT。`formal_candidate_id/agent_c_payload/scientific_pass=null`，`formal_wt_delivery/candidate_record_complete/automatic_handoff=false`，生产仍为 `NOT_DEPLOYED`。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <同来源运行根> wt-reference --input <精确N17请求.json> --key <唯一键> --run
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <同来源运行根> local-delivery --input <精确N18请求.json> --key <唯一键> --run
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <同来源运行根> result --job-id <任务ID>
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root <同来源运行根> artifact --job-id <任务ID> --artifact-id <ZIP或报告产物ID> --output <新文件路径>
```

同一入口支持 `get/events/execution/cancel/retry/recover/wait`。单个来源、报告或 ZIP 文件通过 artifact 查询，单变体继续使用其来源报告的 `variant-record` 查询。本地有界计算复用已有停止发布栅栏：取消/超时后不发布可消费报告，失联登记 INTERRUPTED，显式 retry 新建任务；未提供的来源不伪造已执行状态。

### N17 与 N18 实测和证据

最终可直接查看[原24条全淘汰可读报告](../../../discovery/t01-phase1-real/w7/local-delivery-integration-20260910/export-check-r01/cases/real24-all-excluded-delivery/report.md)、[机器数据](../../../discovery/t01-phase1-real/w7/local-delivery-integration-20260910/export-check-r01/cases/real24-all-excluded-delivery/data.json)或[本地交付ZIP](../../../discovery/t01-phase1-real/w7/local-delivery-integration-20260910/export-check-r01/cases/real24-all-excluded-delivery/package.zip)。其中原报告、WT草稿和扫描缺项保留；没有把另一9aa结构的稳定性结果或独立DNA测试接入该76aa批次。

| 批次 | 文件 / 发布产物 | 验证内容 |
|---|---|---|
| [acceptance-r01](../../../discovery/t01-phase1-real/w7/local-delivery-integration-20260910/acceptance-r01/index.json) | 333 / 197 | 16任务、8守卫；原24全淘汰、WT草稿、各自结构的FoldX40条/ThermoMPNN140条、多链跳过、BuildModel拒绝、错误WT/跨根/损坏引用、失败/恢复/重试及发布篡改；8个ZIP核验 |
| [supplement-r01](../../../discovery/t01-phase1-real/w7/local-delivery-integration-20260910/supplement-r01/index.json) | 115 / 84 | 10任务、4守卫；真实独立DNA配对后不适用、错误序列/宿主/变体、失败/等待中上游、取消/受控超时/执行后来源变化 |
| [supplement-r02](../../../discovery/t01-phase1-real/w7/local-delivery-integration-20260910/supplement-r02/index.json) | 127 / 96 | 导出配套文件修复后重跑上述场景，data/manifest/report均作为登记产物发布，4个ZIP核验 |
| [source-state-r01](../../../discovery/t01-phase1-real/w7/local-delivery-integration-20260910/source-state-r01/index.json) | 13 / 10 | 真实失败ThermoMPNN扫描保留failed状态，同运行根错误结构引用拒绝 |
| [export-check-r01](../../../discovery/t01-phase1-real/w7/local-delivery-integration-20260910/export-check-r01/index.json) | 41 / 18 | 当前代码再次完整组装24全淘汰包，10个ZIP内文件核验；源码及execution/rule profile与现行实现一致 |

修复记录：首轮ZIP内部链接正确，但单独保存的Markdown缺配套data/manifest文件，文档检查失败。本包修复为同时发布两份配套文件；r01封存前已补齐验收报告同目录文件并与实际ZIP逐字节比对。旧运行目录仅新增从原ZIP提取的只读阅读配套，未修改既有请求、产物字节或封存清单；新增记录及全部独立审计见[验证目录](../../../discovery/t01-phase1-real/w7/local-delivery-validation-20260910)。历史r01代码不冒充最终代码，最终profile以export-check-r01为准。

受影响回归首轮1660项通过、1项跳过，唯一失败为上述文档链接；修复后开发/文档67项和新增审计器4项通过，冻结Mock457项只读核验通过。旧完整Mock/S07未跨分区，未重跑。每个真实回放保留原模型工具执行身份，不宣称本包重新运行ProteinMPNN/FoldX/ThermoMPNN；新增N16调用仅使用20残基独立测试片段。终态失败与时间注入分别标记，未伪造科学阳性或生产交接。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/audit_local_delivery_evidence.py discovery/t01-phase1-real/w7/local-delivery-integration-20260910/acceptance-r01
.\.venv\Scripts\python.exe -X utf8 scripts/audit_local_delivery_evidence.py discovery/t01-phase1-real/w7/local-delivery-integration-20260910/export-check-r01
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_local_delivery_development.py tests/test_local_delivery_evidence_audit.py tests/test_docs.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_local_delivery_acceptance.py --batch acceptance-new
```

第四条仅在确需重跑时使用新批次，复制并验证历史来源后执行本地组装，不修改原批次。当前根源码、验证日志及manifest见验证目录；本包工程完成，完整科学节点和一期发布未完成。

## 全项目剩余工程与外部依赖盘点

本节是按用户要求在末端包之后汇总的实施盘点，不替代各包或 [OPEN_ITEMS](../OPEN_ITEMS.md) 的唯一问题定义，也不自行安排下一轮。判定依据为现行 W1–W7 文档、当前 registry/后端实现和实际证据；独立工具完成不等于业务节点、科学消费或生产完成。

| 范围 | 已有工程基础 | 仍缺工程动作／外部条件 | 主责与关闭证据 |
|---|---|---|---|
| N01–N02 结构与拓扑 | 本地结构、质量、映射、DeepTMHMM 和条件 RSA 有真实工程证据 | AF3/ESMFold2 目标部署、统一任务适配和下游接线仍缺；结构比对接受域、来源/缺原子口径、RSA出域等科学签收未齐 | 服务器同事按交接文档部署；后端接入/离线实跑；算法关闭 OI-015/023/024/027；证据归 W1 |
| N03 / N08 / N09 本地数据库 | BLAST、同源收集/比对/保守性、功能域注释与来源回连已有工程路径 | 目标序列库/同源库/注释包的用途、来源、版本、许可、索引与目标实跑仍需实际资产；正式 core_map 几何/空值口径待签收 | 数据接口人提供目标资产；后端校验/hash/复现；算法 OI-006/028/031；W2/W3 |
| N04–N07 表位与糖基化 | BepiPred、明确 allele 的 NetMHC、N06 来源汇总、N07 sequon 与精确20aa窗口工程已做 | 峰后处理、模型/分数列、宿主 allele 面板、热点赋级/权重及窗口转换未齐；不能以空热点或移除 IEDB 为科学通过 | 算法/业务 OI-003/007/026/028/029；后端在裁决后补处理及真实参考；W2/W3 |
| N10 可开发性 | 可表达性、标签暴露、A3D结构路径、PROPKA曲线、部分 S-40 有实测 | CamSol Roseman符号冲突与 μ/σ 制备；官方序列聚集资产/许可/命令；空间簇和非高风险分类、平坦曲线权重；完整 overall 未生成 | 算法裁决 OI-025/032/033；资产接口人落实序列工具；后端完成参数/适配与独立验证；W4 |
| Gate / N11 权限设计 | 本地 WT 草稿、ProteinMPNN、权限/负担工程回连有实测 | 完整自动权限分支、冲突规则与设计 Gate 科学释放仍缺；不能以显式工程 mask 代替科学权限 | 产品/算法 OI-001/002/006/007/021，后端补已裁决分支与全链校验；W4/W5 |
| N12 完整验证与重算 | ESM-IF1 同 WT 基线、变体分数、burden 与历史 R-35 已做 | 变体结构复核依赖预测结构；完整验证、前20池/缺值/并列与受控重算业务闭环未完成。任务执行失败 retry 不等于科学重算闭环 | 后端+算法 OI-008/015/022，预测环境接口人；W5 |
| N13 科学保护 | WT/变体序列、结构、RSA、N06/N09 来源与四层工程观察已做 | 真实热点路径、结构 RMSD 原子/对齐及阈值、画像漂移/拆合比较规则、空/未执行正式语义及独立科学参考未齐 | 算法/产品按 OI-007/022/026/028 和 N13 表位缺项表关闭；后端补规则/参考；W6 |
| N14 / N15 科学筛选排序 | FoldX真实变体分数回连、ESM/权限/负担汇总及24条全淘汰已做 | 依赖完整 N10/N13/验证资格；目标权重、前20池、排序缺值/并列及稳定性科学消费未签收，不能强选最佳 | 算法/业务 OI-008/009/011/022；后端补适用排序路径与全链证据；W6 |
| N16 | 一个明确 E.coli/W3110 本地表 profile 与真实优化工程完成 | 原件其余宿主目录/别名及表资产、生产 CDS 参数、CAI 方法与参考、正式 WT/候选来源绑定未开放 | 算法/业务 OI-004；后端实现批准 profile 和业务接线，数据接口人提供表；W7 |
| N17 | WT稳定性工具与本包历史参考回连完成 | 科学扫描触发、权限/覆盖/区域优先级完整业务闭环及匹配比较集合的共识方法/签收仍需关闭；S-32/MD 已按一期范围排除，不列入待办 | 算法 OI-011及适用门控裁决；后端补一期保留分支；W6/W7 |
| N18 | WT/全淘汰/缺失/失败本地工程组装与查询完成 | 正式 CandidateRecord/WT/Failure 映射、SC-10分叉及 Agent C 生产接口/认证/幂等/确认未完成；正式阳性链无验收 | 业务/后端/Agent C接口人关闭 OI-010/013/014/021，再做具名真实联调；W7 |
| 跨节点交付与运维 | Windows可信本地 CLI/SQLite及认证 REST/Streamable HTTP MCP 已完成；独立真实 Dify provider/DSL 在本机完成绑定、回读和成功/失败实跑 | Linux/远端 Worker、目标持久密钥和网络边界、离线环境与数据打包、目标 Dify endpoint、全链条件/失败/重算路由、目标断网端到端和 G0–G6 汇合冻结未完成 | 后端/工作流/部署负责人按[目标 Linux 部署候选包](../PHASE1_DELIVERY_PLAN.md#目标-linux-部署候选包)落实；不以 Mock冻结、本机服务或本地ZIP代替目标证据 |

不重新要求 IEDB/RCSB/AFDB 或线上回退；N03 仍只保留批准本地 BLAST。工程可独立推进的项与必须等待科学裁决/资产/目标接口的项分别列明，后续安排由管理任务统一作出，当前一期仍 `IN_PROGRESS / NOT_DEPLOYED`。
