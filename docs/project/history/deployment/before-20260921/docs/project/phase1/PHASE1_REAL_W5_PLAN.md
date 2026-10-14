# PH1-REAL-W5：候选设计、验证与受控重算

更新：2026-09-08。实际进度与当前实施包只在 [STATUS](../STATUS.md)维护；开发、科学消费与发布分别判断，依据 [交付计划](../PHASE1_DELIVERY_PLAN.md)。

## 阶段交付表

**2026-09-19续行要求：** 按[专家流程校准计划](../PHASE1_DELIVERY_PLAN.md#专家流程校准与单卡执行计划2026-09-19)第3项补齐自动设计、R-04双模型路由、S-29、负担消费及两层受控重算；现有工具独立验收保留。GPU新任务先满足单张A100 64GB约束，历史40GB结果不变。完成标准必须包含真实编排与全淘汰/停止分支，不能用工程任务retry或显式单样本预测替代。

| 交付包 | 交付目标与完成标准 | 具体依赖 |
|---|---|---|
| N11 ProteinMPNN 独立开发接入（本包工程已完成） | 固定原工具与权重，真实禁网生成工程序列，完成明确约束的坐标转换、输出校验、统一提交/查询及生命周期验收 | 可追溯本地结构、唯一设计链、工具资产和实际资源；不等待预测结构模型部署 |
| N11 权限合成与适用设计分支 | 明确规则的逐位权限工程及原生掩码转换已完成；适用目标分支继续按科学条件接入 | OI-001/002/006/007、结构/拓扑与其他适用科学依据；不得以工程明确掩码代替科学权限签收 |
| N12 验证与受控重算（ESM-IF1 独立工程接入已完成） | ESM-IF1 同 WT 结构基线、变体打分、适用 burden 与结构复核、按规则重试及停止 | 逆折叠原工具已固定并实跑；完整分支仍受 OI-008/015/022 与适用 AF3/ESMFold2 结构复核约束 |

包内连续完成原工具核验、实现、测试和证据，不另建逐项准备文档。后两个包随事实细化，不提前虚构接口或完成记录。完整 W5 保留所有现行适用分支；本次优先通用 ProteinMPNN 不代表删除其他目标路径。

## 实施包：ProteinMPNN 独立开发接入

依据专家包 v10.5（2026-09-02）的 [C15 ToolSpec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C15_ProteinMPNN_v10.5.md)、[SOP S-27](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)及现行用户范围决定。并列原文冲突按 AGENTS 处理，列出具体来源，不自行猜科学口径。

**本包目标**：从同序列、可追溯本地结构和明确工程位点约束出发，完成 ProteinMPNN 真实执行→原生序列/分数解析→约束核验→统一查询。结果为工程生成记录，不成为正式生产候选，不从未签收 Gate 自动触发。

1. 核对官方原工具代码、权重、许可、CLI 与资源；固定 commit、模型 hash、依赖和运行 profile，真实禁网运行。资产缺失只阻断对应实跑，不伪造输出。不要沿用其他模型的 GPU 资源估算。
2. 复用现有结构任务 ArtifactRef、原子/序列映射和唯一链校验；序列位置使用 1-based，显式保留链、作者编号、插入码与工具实际位置的转换证据。多链只设计唯一目标链，其余链保持固定；不能按作者残基号直接猜工具数组下标。
3. 工程调用显式传入固定位置和逐位点允许集，来源与工程用途可追溯；未提供的科学权限不能自动推断为全开放。探测固定版本的逐位点 omit 能力，按 ToolSpec 验证固定/受限位置；不能以软偏置替代硬限制。FIXED 转换失败中止该链；受限位置仅在能正确固定时按规范降级，否则中止。
4. 使用原件规定的工作流候选默认 24、采样温度 0.1，记录实际参数/seed与真实输出数量。核验序列长度、字符、固定位置不变和受限位置满足允许集；保留原生分数名称、重复及 WT 相同记录，不伪造去重后的数量或下游验证结果。
5. 接入现有任务层、事件、查询、取消/超时、恢复/幂等重试及产物 hash；不新建调度框架。工具真实生成、受控故障和契约夹具分别记证据。全部工程结果不可科研消费、不可自动交接。

**验收覆盖**：可追溯结构真实生成；明确固定/受限位置的原生执行与结果后校验；多链目标及编号转换；无可设计位置的明确处置；缺结构/链不唯一/序列错配/约束越界/转换失败；缺资产/非法输出/上游或产物篡改；统一 CLI 查询与适用生命周期。声明场景是否真实工具调用，不将夹具当真实约束能力证明。按共享代码影响选择回归。

**开发完成标准**：固定工具在本机或实际可用环境禁网执行成功，统一入口能提交、执行、查询并核验工程序列与原始产物，守卫和生命周期通过。已完成证据、命令、支持域和限制见下文；本包完成不代表完整 N11/W5 或科学放行。

## N11 本机调用与接口

统一入口新增 `proteinmpnn`，登记 `t01.real.proteinmpnn / N11`，复用现有 SQLite、ArtifactRef、事件、容器监督与恢复，不从 WT 草稿或未签收 Gate 自动触发。后端实现位于 [proteinmpnn](../../../src/t01_phase1_real/development/proteinmpnn/policy.py)。

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

工具固定为官方 commit `8907e6671bfbfc92303b5f79c4b5e6ce47cdef57`、`vanilla_model_weights/v_48_020.pt`、MIT 许可，原源码/权重逐项校验官方 Git blob 和 SHA-256；[资产登记](../../../src/t01_phase1_real/development/proteinmpnn/assets.json)保存九份文件及固定镜像身份。镜像为 `sha256:5b6baa8ebc5660bd3de9cf8b6d1694c7de35fadd23fea6cd7a8352a536e3f3af`，Python 3.10.21、PyTorch 2.7.1+cu128、CUDA 12.8、NumPy 1.26.4；[环境收据](../../../discovery/t01-phase1-real/w5/proteinmpnn-assets-20260908/environment.json)保留依赖安装来源/hash、完整 pip/dpkg 版本和禁网 GPU 张量实测。构建时下载依赖；实际生成固定 `network=none`，根文件系统/源码/权重/输入只读，输出独立可写，GPU device 0、2 CPU、4 GiB 主存、128 PID，无 CPU 或联网回退。资源上限是工程准入策略，不是最大长度性能保证。

固定版 `--help` 与实际 featurizer 均确认逐位点 `--omit_AA_jsonl` 硬排除；不使用 bias 参数。实际格式为 `{"target":{"A":[[[2],"禁止残基串"]]}}`，固定位置格式为 `{"target":{"A":[1]}}`；数字是解析后的链内位置。由于工程 PDB 的 resSeq 特意重编为 1..L，工具 resSeq 与数组位置相同，原作者编号则留在转换表中。C15 §4 的原编号/示例差异与后续科学签收见 [OI-002/015 对齐记录](../OPEN_ITEMS.md#n11-原工具坐标与权限边界oi-002015)，不修改专家原件。

成功结果为 `generated_unreviewed`，`generation.records` 保留真实样本数、原生 `score/global_score/seq_recovery`、1-based mutations、`is_wt` 和 `duplicate_of_sample`，不去重凑数。校验原生 FASTA 与全链采样张量一致、FIXED 不变、RESTRICTED 允许集及禁止残基概率为零、非目标链不变，并从保存的逐位 log probability 回算原生分数；任何不一致都隔离整组输出。没有可设计位置时只执行原生解析/掩码审计，返回 `not_generated_no_designable_positions`、0 条及明确原因，不声称调用生成器。

失败结果为 `unreliable`，`generation=null`，保留机器错误、复核原因与原始输出；取消/超时确认实际停止后发布。恢复核验原执行收据/清单，不重跑同一个 attempt；显式 retry 创建新尝试。所有结果固定 `design_permissions=null`、`formal_candidates=null`、`scientific_gate=NOT_EVALUATED`、`usable_for_pipeline=false`、`automatic_handoff=false`、`NOT_DEPLOYED`，原生 ProteinMPNN 分数不替代 ESM-IF1 或候选排序。

### 已验证调用

以下一条命令使用 r02 运行根中已登记的正常 PDB 结构上游，另建工程任务；请求文件显式包含 24、0.1、seed 17 与逐位掩码。相同 key、相同字节幂等；换输入须换 key。已验收 CLI 的原始参数与输出见 [调用记录](../../../discovery/t01-phase1-real/w5/proteinmpnn-integration-20260908/acceptance-r02/cli/documented.json)。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\proteinmpnn-acceptance-r02 proteinmpnn --input D:\work\蛋白智能体\discovery\t01-phase1-real\w5\proteinmpnn-integration-20260908\acceptance-r02\requests\normal-pdb.json --key w5-n11-local-example --run --wait 180
```

只读查询已完成、未用于篡改测试的正常 PDB 结果：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_runtime.py --root D:\work\蛋白智能体\var\t01-phase1-real\proteinmpnn-acceptance-r02 result --job-id t01p1r-job-8d4419d5da9b4b418680f154f734534b
```

同一入口支持 `get/events/execution/artifact/cancel/retry/recover/wait`；控制操作各用独立幂等 key。全新验收命令见 [RUNBOOK](../../development/RUNBOOK.md#w5-n11-proteinmpnn-独立工程接入)，不得覆盖 r02。

### 本包验收事实

[r02 完整索引](../../../discovery/t01-phase1-real/w5/proteinmpnn-integration-20260908/acceptance-r02/index.json)记录 **25 个任务场景、12 项守卫、8 个真实结构上游**；[独立复核](../../../discovery/t01-phase1-real/w5/proteinmpnn-validation-20260908/evidence-audit-r01.json)确认 **946 份索引前文件、773 项发布产物**大小/SHA-256 一致，23 份源码/配置快照无差异，执行/规则 profile 与当前实现一致，并重新解析全部 10 份成功 N11 结果。

9 次成功生成各保留 24 条，共 216 条工程采样记录；另一次全 FIXED 明确返回 0 条且未调用生成器。真实覆盖 1UBQ 坐标保持派生、同 seed 重复、PDB/mmCIF、WT-only 允许集、多链只设计 B、作者 100/100A/106 到 1/2/3 转换及非目标链不变。该 76 aa 样本 r02 容器内执行约 8.40 秒，GPU 峰值分配 63,094,784 bytes、保留 83,886,080 bytes；仅为当前样本/显卡事实，不外推大序列资源。

缺结构、序列错配、缺失残基、链不唯一、替代构象、约束越界/未覆盖及伪造来源均拒绝；原工具失败、输出损坏、排队/运行取消、硬期限、启动后监督崩溃和收据后恢复、失败重试、提交后来源篡改与已发布结果篡改均按预期隔离。缺资产/权重损坏及原生输出语义负例由 [43 项单测](../../../discovery/t01-phase1-real/w5/proteinmpnn-validation-20260908/n11-tests-r01.txt)验证，其中损坏输入为隔离夹具，未修改官方权重或冻结资产。全长形状、硬掩码、禁止残基概率、逐位分数与 WT 恢复率均由宿主验证。

最终共享代码的 [完整根回归 r03](../../../discovery/t01-phase1-real/w5/proteinmpnn-validation-20260908/root-tests-r03.txt)为 **1376 通过、1 项既有 Windows 符号链接权限跳过**；[457 项 Mock 冻结资产](../../../discovery/t01-phase1-real/w5/proteinmpnn-validation-20260908/mock-verify-r01.json)只读核验通过。现行文档检查通过；未跨历史分区，旧完整 Mock 与 S07 未重跑，不合并为本期科学完成度。

smoke-r01 是首轮成功原生输出，供语义回归只读使用；acceptance-r01 因验收脚本复用取消幂等 key 中止，未记整包 PASS，后续修复使用新 r02；镜像构建前两次分别在本地 digest 解析等待和旧 pip 元数据处理中未完成，成功构建为 r03。所有前次输出保留原身份。科学签收、正式权限合成、ESM-IF1、目标复现及生产部署不包含在上述数字中。

## 后续边界

N11 正式权限、目标分支、N12 科学消费与预测结构验证、burden、前 20 池与重算仍在本阶段跟进。ESM-IF1 独立工程打分已完成，依据 [C18 ToolSpec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C18_ESM-IF1_v10.5.md)，不能将 ProteinMPNN 原生分数替代 ESM-IF1 或正式候选排序。

W4 科学 Gate 未放行、N10 不完整和未签收的上游事实继续保持；只限制相应正式消费与自动设计，不阻止明确标记的独立工具工程实跑。AF3/ESMFold2 同事部署与 N10 外部缺项在原包推进，W1–W4 不因进入 W5 而标完成。


## 实施包：N12 ESM-IF1 独立验证接入

2026-09-08 管理安排：N11 ProteinMPNN 独立工程包已完成，下一包推进 ESM-IF1 真实打分与 N11→N12 工程回连。依据本页已链接的 C18 ToolSpec 和 SOP S-28；科学权限合成留在 N11 原包，不因外部确认未齐而阻断独立工具验证。

**交付目标**：固定 ESM-IF1 原工具与权重，在同一 WT 结构上计算 WT 基线、批量评价真实 ProteinMPNN 工程序列，返回原始分数、相对变化、工程规则结果及复核原因，并接入统一提交/查询与生命周期。不得用 ProteinMPNN 分数代替逆折叠实跑。

1. 固定官方实现、模型 `esm_if1_gvp4_t16_142M_UR50`、依赖、许可与执行 profile，核验实际 CLI/API 和分数平均范围，禁网真实运行；缺资产明确失败。ESM-IF1 与同事部署的 ESMFold2 是不同工具。
2. 绑定真实 WT 结构、WT 序列和 N11 工程序列 ArtifactRef，核验任务/尝试/hash、唯一设计链及坐标转换；变体序列与申报突变列表必须相符。变体仍使用同一 WT 骨架打分，不等待变体结构预测。
3. 首次计算 WT baseline，同批后续变体复用；跨调用复用只接受可校验的基线产物，绑定 WT 序列、结构字节/目标链/映射、模型和执行参数，不能直接信任用户提供的浮点数。任一绑定改变不得沿用旧基线。
4. 保留原始有符号分数，依 C18 计算 `(variant_score-baseline_score)/abs(baseline_score)`，delta_pct 存百分数。零分母、NaN/Infinity、缺原子/映射异常等按原工具事实和来源明确拒绝或复核，不能自行填值或截断。原工具与原件语义冲突时列明来源和影响。
5. 后端规则层与原工具打分层分开，按已明确的 R-35 条件验证 10% 判断以及全排除时 15%→20% 的有限复评与历史记录；不是重新生成候选或无限重跑模型。规则测试与真实模型结果分别记证据，不把工具执行成功写成完整验证通过。
6. 统一查询、取消/超时、恢复/幂等重试与文件防篡改沿用共享运行层；覆盖单变体失败隔离、全部失败、合法空输入的明确处置。保留工程数据身份，不能自动发送 Agent C 或触发正式设计。

**验收**：真实 WT 基线及真实 N11 工程序列打分；同批基线只计算一次和合法跨调用复用；错结构/错链/换模型/假基线拒绝；序列与突变不符；负值公式、阈值边界及有限复评；缺资产、无效输出、部分失败、来源与产物篡改，以及适用生命周期。报告实际调用数与案例类型，工程数值规则夹具不冒充模型自然产生的淘汰分布。

**完成标准**：统一入口完成真实 N11 产物→身份校验→WT 基线/变体打分→查询与产物追踪，固定资产及验收证据可复现，受影响回归通过。实现后将真实命令、支持域和索引回填本节，不预建空证据。

本包不宣称完整 N12/W5：mutation_burden 是独立后端计算，仍按 OI-008 跟进；结构复核等 AF3/ESMFold2 对应能力，候选池和受控重算按 OI-022 跟进。未执行结构复核明确记录，不伪装为预测失败以套用降级。工程规则结果与完整验证/科学资格分字段保存，正式 Gate、科学消费和自动交接保持关闭。

## N12 本机调用与接口

统一入口 `esm-if1` 登记 `t01.real.esm_if1 / N12`，复用任务库、ArtifactRef、事件与 GPU 容器监督。后端 [source](../../../src/t01_phase1_real/development/esm_if1/source.py)重新验证真实 N11 原生记录、硬约束、结构字节和坐标映射；[result](../../../src/t01_phase1_real/development/esm_if1/result.py)复核官方 parser 实际读入的 N/CA/C、逐残基 loss、平均范围、模型调用数和输出清单。

请求是字段全部显式提供的严格 JSON：

| 字段 | 工程接口 |
|---|---|
| `protein_sequence` / `user_sequence_id` | 精确 WT AA20 序列（1–1000 aa）及来源标签；与 N11 请求完全一致 |
| `structure_artifact` / `n11_artifact` | 同运行根内已登记成功结果的完整 ArtifactRef；核验任务、尝试、请求、大小/hash 和原生输入输出，结构引用须与 N11 一致 |
| `sample_numbers` | 明确选择原 N11 样本号，唯一整数 1–24，实际存在且保留请求顺序；`[]` 合法，明确不打分 |
| `baseline_artifact` | 首次为 `null`；复用仅接受当前执行 profile 下成功 N12 结果的完整 ArtifactRef，不接受浮点基线 |
| `timeout_seconds` | 整数 1–900；硬期限与宿主停止确认共同控制 |

结构支持域继承 N11 的完整标准骨架、唯一目标链、最多 8 链/总上下文 1000 aa 和可无损投影坐标。固定官方 `load_structure/extract_coords_from_complex` 解析全部蛋白链；目标链放首位，链间填充 10 个 NaN 坐标作为官方上下文分隔符。其他链参与骨架上下文，分数平均仅覆盖目标链全部残基；分隔符不进入分母。缺原子/映射异常不走补坐标旁路。

工具固定为 [官方 ESM 实现](https://github.com/facebookresearch/esm/tree/2b369911bb5b4b0dda914521b9475cad1656b2ac/examples/inverse_folding) commit `2b369911bb5b4b0dda914521b9475cad1656b2ac`、模型 `esm_if1_gvp4_t16_142M_UR50`；[资产登记](../../../src/t01_phase1_real/development/esm_if1/assets.json)保存 36 份原源码/许可文件和权重的大小/SHA-256，源码另核验官方 Git blob。权重为 1,700,450,121 bytes，SHA-256 `be4ba36edec22a9bfaa4946ff6b2815f1f19d8a3d7e0eada8b796d5a0eae9fd4`；源许可 MIT，保留原件。

固定镜像 `sha256:926d4619df9759cd2417dcc9056b7bd648dca1d2adf15631aaad2e84a88d39cc`，Python 3.10.21、PyTorch 2.7.1+cu128、CUDA 12.8、NumPy 1.26.4、Biotite 0.39.0、SciPy 1.15.3、torch-geometric 2.6.1；[环境收据](../../../discovery/t01-phase1-real/w5/esm-if1-assets-20260908/environment-r01.json)保存完整 pip/dpkg 版本、安装来源/hash、GPU 与原生 API 对标。构建依赖时联网，实际打分 `network=none`，GPU 0、2 CPU、6 GiB 主存、128 PID，只读源码/权重/输入和容器根，独立输出；无联网或 CPU 回退。实际模型参数 141,662,150，eval/float32、seed 17、禁用 TF32。官方本地 checkpoint 加载使用 PyTorch `safe_globals([argparse.Namespace])`，未修改官方源码或关闭受限加载器。

每条序列调用一次官方 `get_sequence_loss`，保留逐位负对数似然和 padding mask，按全目标链负均值回算原始有符号分数。与官方 `score_sequence` 的独立数值对标差为 `4.23855e-7`，工程容差 `1e-6`；探针的 2 次调用只作 API 对标，生产批次基线为 1 次。原件的“伪似然/越接近 WT”描述与原工具条件自回归似然的差异见 [OI-015/022 对齐](../OPEN_ITEMS.md#n12-原生分数与完整验证边界oi-015022)，不据此推断稳定性或完整验证资格。

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

统一入口另支持 `get/events/execution/artifact/cancel/retry/recover/wait`。原批 [CLI 打分与基线复用记录](../../../discovery/t01-phase1-real/w5/esm-if1-integration-20260908/acceptance-r01/cli/documented.json)及查询输出已归档；其中 documented 运行根结果随后作为篡改负例，不能作为正常查询示例。完整验收必须使用新根/批次，见 [RUNBOOK](../../development/RUNBOOK.md#w5-n12-esm-if1-独立工程接入)。

### N12 本包验收事实

[完整索引 r01](../../../discovery/t01-phase1-real/w5/esm-if1-integration-20260908/acceptance-r01/index.json)覆盖 20 个任务场景、10 项守卫；[独立复核](../../../discovery/t01-phase1-real/w5/esm-if1-validation-20260908/evidence-audit-r01.json)确认 993 份索引前文件、853 项发布产物大小/hash 一致，28 份源码/配置快照与现行实现一致，执行/规则 profile 一致。重新解析两份真实 N11 生成结果、九份 N12 scoring 输出（含空输入与局部失败记录），验证两个首次基线来源和六次跨调用复用。

真实 1UBQ 坐标保持派生样本的 WT 分数为 `-0.06536155625393517`，同批基线 1 次、24 条 N11 工程序列各 1 次。这批真实分数在 20% 后仍全部排除，未包装为通过样本或触发重新生成。多链工程样本目标 B，保留作者 100/100A/106 与投影 1/2/3 转换，WT-only 序列相对变化接近 0。R-35 的七组负值、精确阈值与有限复评夹具单独标记；不声称为模型自然分布。观察到 GPU 峰值分配 698,561,536 bytes，仅为本机样本事实。

排队/运行取消、超时、启动后崩溃、收据后恢复、失败重试、部分/全部失败、输出损坏、幂等冲突、换 WT/结构/模型/样本、假基线及来源/发布产物篡改均按预期隔离。原权重未作破坏测试，缺失与坏 hash 由隔离夹具验证。smoke-r01 因共享准入域遗漏 N12 中止，修复后 smoke-r02 原生链通过；两批均保留原身份，完整验收为 r01。

[65 项 N12 单测](../../../discovery/t01-phase1-real/w5/esm-if1-validation-20260908/n12-tests-r01.txt)、[5 项独立审计测试](../../../discovery/t01-phase1-real/w5/esm-if1-validation-20260908/audit-tests-r01.txt)通过；最终[完整当前根回归 r02](../../../discovery/t01-phase1-real/w5/esm-if1-validation-20260908/root-tests-r02.txt)为 **1451 通过、1 项既有跳过**。文档检查器只对两份精确路径且大小/hash 匹配登记的官方 README 排除上游相对链接扫描，邻近项目文档和损坏/未登记原件仍检查；[56 项文档测试](../../../discovery/t01-phase1-real/w5/esm-if1-validation-20260908/docs-tests-r01.txt)通过。此前根回归 r01 被中断、未取得完整摘要，诊断重跑定位官方 README 的链接误报；修复后 r02 为完整通过记录，不覆盖前版。

[457 项 Mock 冻结资产](../../../discovery/t01-phase1-real/w5/esm-if1-validation-20260908/mock-verify-r01.json)只读核验通过；现行 197 份 Markdown 检查通过，29 条历史原文旧引用独立保留。未跨历史分区，旧完整 Mock/S07 未重跑。本页新命令另有[实际调用输出](../../../discovery/t01-phase1-real/w5/esm-if1-validation-20260908/local-example-r01.json)和[正常只读查询](../../../discovery/t01-phase1-real/w5/esm-if1-validation-20260908/local-query-r01.json)，不计入原 r01 的 993 份文件。


## 实施包：N11 权限合成与 N12 mutation_burden 后端工程

管理安排：N11 生成器、N12 ESM-IF1 独立工程均已交付，接下来将两者之间及验证侧的确定性后端规则合为一个实施包。依照现行 S-27/S-28、C15/C18 ToolSpec 与 Schema 归并，原件链接见本页前文。进度只见 STATUS。

**交付目标**：真实上游事实→逐残基约束/权限工程结果→N11 约束转换验证，以及真实变体→六维 mutation_burden 工程计算→N12 来源回连与查询。工程结果不能取得科学签收资格，未签收输入不得触发正式设计。

1. 权限合成区分约束 HARD/RESTRICTED/SOFT 与执行权限 FIXED/RESTRICTED/OPEN，记录逐位来源、规则及原因；复用 N06/N07/N08/N09/结构的真实 ArtifactRef 校验。缺失、失败和未签收分开处理，全证据缺失不得默认 OPEN；core_map 等正式 null 不得从工程分量偷偷补成科学证据。
2. 实现有唯一依据的集合优先级、保守默认与明确用户约束；OI-001/002/006/007、窗口及来源资格仍未定的分支明确复核，不自行定义重叠覆盖或证据等级。来源未签收时输出工程审计结果，正式权限保持未放行。与 N11 原生掩码的联调必须是显式工程调用，保留数据身份；不自动启动新的候选生成。
3. mutation_burden 由后端计算，不能伪装为 ESM-IF1 输出。绑定 WT/变体 diff、同一结构和实际域/热点来源，按 C18 核验计数、化学变化、空间聚集、功能域邻近、表位邻近和 epistasis 风险；固定标度文件、坐标和规则版本。域/热点缺失按适用原件保留 null；零突变、单突变无配对分母等逐项查原件，未唯一明确处不猜值。
4. OI-008 的字段/档位和科学阈值未签收，已明确公式可作为标明用途的工程观察；未知定义不取任意默认，不能把未计算/不可靠维度当通过。工程值、工程档位与正式 burden/过滤资格分开；不输出虚假的完整 validation。
5. 接通统一提交、查询、来源/产物校验和适用生命周期，利用已交付 N11/N12 真实记录完成回连；不修改原验收批次。当前 24 条在 R-35 20% 后全排除的事实保留，新计算不得令它们重新获得通过资格。

**验收与完成标准**：来源可靠性/缺失/冲突、全部缺证据、固定与受限映射、零/单/多突变、化学/空间边界、缺坐标/域/热点、序列错配、来源与产物篡改等明确可复现；真实上游回连与人工可算的几何/数值夹具分开记录；统一查询和受影响回归通过。已明确分支连续实现并验收，具体科学冲突回填现有开放项，不新建笼统问卷或逐项准备任务。

**完成边界**：本包工程可独立交付；科学权限、正式 burden、候选池 OI-022、结构复核与正式设计/Agent C 交接继续按各自条件关闭。完整 N11/N12/W5 不因工程部分通过而完成。实际命令、实现限制和证据在本节回填，不预建空链接。

## 权限与负担本机接口

新增统一入口 `design-audit`，工具 `t01.real.design_audit / N12` 代表合并的 S-27/S-28 本地工程审计，不替换 N11 生成器或 N12 ESM-IF1。实现位于 [design_backend](../../../src/t01_phase1_real/development/design_backend/policy.py)，复用现有任务库、ArtifactRef、事件、幂等和本地计算停止/恢复机制。所有计算由后端执行；输出不自动提交 ProteinMPNN，不调用预测模型。

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

N06 明确 tcell_only 呈递区、已核验的 N07 20 aa 遮蔽证据和确认的膜拓扑按 S-27 处理。N06 E1 证据保留 SOFT；当前完整 OPEN 表达式的功能/核心/界面等操作数尚不齐，工程执行收紧为 RESTRICTED并记原因。全缺证据为 RESTRICTED；不把未知区域当 OPEN。N09 core_map=null 保持 null，不从组件回填 deep_core；结构推断二硫键/界面与 PTM 到 E2+ 边界的未决消费保持复核。具体原文差异与关闭证据见 [OI-001/002/006/007/008 收敛记录](../OPEN_ITEMS.md#权限与负担工程剩余科学条件oi-001002006007008)。

自动合成后应用显式用户区间。用户覆盖 HARD 为更宽权限时，保留 `constraint_override=true/non_standard=true`。同一位置相互冲突的用户权限/允许集不自行按列表顺序决定；保留自动结果、列出冲突位点并阻断整个掩码导出。未冲突 RESTRICTED 默认允许 `{WT}∪BLOSUM62正分替换`，C/G/P 允许 WT-only，绝不用 bias 代替硬排除。

`audit.n11_request_draft` 是显式工程请求草稿，来源 ID 绑定审计请求 hash；`mask_conversion` 使用已交付 N11 无损骨架投影和 fixed/omit 机制，保留作者号/iCode/工具位置。空 FIXED、用户冲突、缺结构或映射失败返回 `mask_conversion_error`，不导出可执行草稿。`n11_comparison` 回查既有工程序列是否满足本次约束，仅报告差异，不撤改原 N11 记录。本包实际只运行官方 parser/featurizer 掩码探针，模型加载和候选生成均为 0 次。

### 六维负担与空值

`audit.burden_records` 按原样本号保存变体 diff、六维工程 `values`、逐突变化学分量、突变配对/边界距离和原因；`n12_scoring_record` 回连原 ESM-IF1 相对分数/判定，未打分样本明确标记。原 R-35 结果整体保留，`n12_disposition_changed=false`；新增负担不能令原全排除样本重新通过。

[固定标度与工程档值](../../../src/t01_phase1_real/development/design_backend/scales.json)绑定源文件大小/hash，来源为 AAindex `KYTJ820101`、[IMGT Volume 表](https://www.imgt.org/IMGTeducation/Aide-memoire/_UK/aminoacids/IMGTclasses.html)、Biopython 1.88 原始 BLOSUM62 文件，以及 SOP S-28 电荷/极性定义。登记脚本核验原数值行；运行时只读固定文件，不联网下载。电荷 K/R=+1、D/E=−1、H=+0.1（pH 7 近似），极性集 RKDENQHSTY，四分量均逐突变绝对差累加，极性翻转仅作审计。

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

统一入口另支持 `get/events/execution/artifact/cancel/retry/recover/wait`。[实际调用](../../../discovery/t01-phase1-real/w5/design-backend-validation-20260908/local-example-r01.json)状态 succeeded、结果 `design_audit_unreviewed`；[只读查询](../../../discovery/t01-phase1-real/w5/design-backend-validation-20260908/local-query-r01.json)通过。这两份补充记录不计入下面的 1037 份文件。验收中的 combined/documented 来源或结果随后用于篡改负例，正常重用请用上面的历史请求；完整验收须使用全新根与批次，命令见 [RUNBOOK](../../development/RUNBOOK.md#w5-n12-esm-if1-独立工程接入)。

### 权限与负担本包验收事实

[最终索引 r02](../../../discovery/t01-phase1-real/w5/design-backend-integration-20260908/acceptance-r02/index.json)覆盖 24 个任务场景和 7 项守卫；[独立只读复核](../../../discovery/t01-phase1-real/w5/design-backend-validation-20260908/evidence-audit-r01.json)确认 **1037 份索引前文件、885 项发布产物**大小/hash 一致，19 份源码/配置快照及执行/规则 profile 与现行实现一致，12 份工程结果和 7 组数值夹具复算一致。

真实 N07/N08/N09 工程产物、明确失败 N06 与既有 WT/N11/N12 回连后，主样本得到 7 FIXED / 68 RESTRICTED / 1 显式用户 OPEN；原生 ProteinMPNN parser/featurizer 验证固定位、链及逐位 omit 张量。用户冲突保留自动结果并阻断掩码导出；全缺来源不默认 OPEN。历史 24 条逐一计算负担并回连原 N12 判定，另用两条真实 WT-only 记录验证零突变。域/热点缺失与明确空、缺侧链原子、精确 5/10 Å 边界、化学单突变边界和原始作者号/iCode 追踪分别保留证据。

任务失败、损坏输出、执行中断及重试，排队取消、运行取消、超时、幂等冲突、错 WT/结构/N11/N12/样本及来源/发布篡改通过验收或定向生命周期测试。旧 ESM 归档先逐文件校验，再复制运行根；只有新副本中此前刻意损坏的 N11/N12 文件按已核验原归档恢复，逐项记录恢复前后 hash。原运行根、原归档和旧时点声明不回写。r01 保留为域无命中语义和逐样本 N12 回连最后修正前的记录，最终验收为新 r02。

[66 项定向测试](../../../discovery/t01-phase1-real/w5/design-backend-validation-20260908/tests-r02.txt)全部通过；最终[完整当前根回归](../../../discovery/t01-phase1-real/w5/design-backend-validation-20260908/root-tests-r01.txt)为 **1517 通过、1 项既有跳过**。[457 项 Mock 冻结资产](../../../discovery/t01-phase1-real/w5/design-backend-validation-20260908/mock-verify-r01.json)只读核验通过，现行 197 份 Markdown 检查通过，29 条历史引用单列保留。未跨历史分区，旧完整 Mock/S07 未重跑。本包模型加载、候选生成均为 0 次；原 24 条 R-35 全排除状态不变，工程完成不等于完整 N11/N12/W5 或科学放行。
