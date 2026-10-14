# PH1-REAL-W1：N01–N02 交付任务

> 现行执行任务页；更新：2026-09-06。进度、下一项和实际验证只在 [STATUS](../STATUS.md)维护。
> 依据：[用户认可的调整](../sources/PHASE1_DELIVERY_SIMPLIFICATION_20260906.json)、[三类放行与 G0–G6](../PHASE1_DELIVERY_PLAN.md#4-每个真实波次的门禁)。

## 任务拆分

| 交付包 | 范围 | 完成标准 |
|---|---|---|
| 通用运行底座 | 任务持久化、幂等、停止/恢复、受控文件 | 复用已有实现与验收，接工具时只补真实集成缺口；不再另起通用框架准备 |
| DeepTMHMM 接入 | 原包执行、标签/区段/计数、P/B/null、运行层桥接 | 统一入口完成真实提交→执行→解析→查询，失败与取消/恢复可验证；开发结果与科学资格隔离 |
| 本地结构分析链 | 输入、解析、R-58、S-09、FreeSASA | 本地结构经过同一调用链得到可追溯结果；未定映射/来源/RSA 分支明确复核，科学消费另签收 |
| 预测结构链与 W1 发布 | AF3/ESMFold2、降级链、离线包、Dify、全 W1 | 两引擎实际离线运行和正确后处理/降级，汇合全部必需工具，经目标及科学验收后冻结 |

每包包含实现、测试、必要评审和补证，不再为它们另开阶段。旧 W1-00～13、A/B/C、E/F 编号仅作证据定位。

## 预测结构链服务器分工

按 2026-09-10 最新用户安排，AF3/ESMFold2 同事部署分工取消，改由用户亲自操作、助手逐步指导；主开发负责统一任务层和下游结构链接入。接口、输入输出与验收集中在 [服务器部署与接口说明](AF3_ESMFOLD2_SERVER_HANDOFF.md)。两模型服务器工程、项目接入、科学签收分别验收，不因说明文档完成而宣布 W1 完成。

## DeepTMHMM 开发接入

本包对应原 W1-09B2，交付一个实际可调用的开发适配器。现有 Academic 1.0 本地实测和解析资料作为起点。
独立科学留出签收、目标服务器复现不再整体阻止本机封装；科学消费和目标发布仍按适用条件关闭。

1. 从 [统一运行层](../../../src/t01_phase1_real/runtime.py)和 [B2 解析逻辑](../../../scripts/b2_review_contract.py)开始；将可复用逻辑纳入新开发实现，保留旧探针、Schema 和执行证据的时点身份。
2. 明确并实现开发请求/结果与 Worker 登记。沿用既有 run/job/attempt、ArtifactRef、幂等和资源控制；工具准入由代码与回归验证，不能仅修改文档或打开 production_enabled。
3. 使用登记的 Academic 包/模型/镜像、安全 ID、禁网与既有资源限额执行；单条单容器，保留原科学参数、原始输出、退出码和停止事实。
4. 校验序列/标签长度、ID/hash、区段/计数、产物完整性；P/B 输出 topology=null、unreliable、WARNING、禁止交接。非法符号 `*` 保留上游预检与后置回拼拦截，不把原包退出 0 当成成功依据。
5. 开发测试输入选已有可追溯样本与已声明边界；AA20 只是开发候选域，<9 aa 的一期守卫保留，X 等非常规输入不自动扩大为科学支持域。长度/token 限制按事实显式配置，不能把旧 991 aa 观察当模型上限。
6. 通过统一入口执行成功、P/B、非法输入、工具失败/损坏结果、取消/超时、重复提交和恢复场景。受控故障注入单列，不声称自然 OOM 或真实模型准确率已通过。

**开发完成的交付物**：可执行源码与入口、必要契约、针对性测试、一条可复现调用命令及一份本批执行结果索引。
真实调用与故障测试可有多个案例，但不另写一套准备评审文档。更新本页的用法和 STATUS 的结果即可。
输出保留明确的开发/未签收身份，usable_for_pipeline=false；不进入科研决策或自动交接。
若发现必须先裁决的具体规则，仅关闭该分支并登记影响；完成其余可独立验收项。

### 本机调用与接口

当前统一入口为 [t01_runtime.py](../../../scripts/t01_runtime.py)，登记 engineering_probe、DeepTMHMM 和下节本地结构分析 Worker。
[development.Runtime](../../../src/t01_phase1_real/development/runtime.py) 在原 SQLite 运行层上扩展固定 Worker，沿用相同任务表、事务、幂等、状态和 ArtifactRef；旧工程入口及封存源码保留原字节。
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

针对性回归为 [test_deeptmhmm_development.py](../../../tests/test_deeptmhmm_development.py)。实际批次由 [run_deeptmhmm_acceptance.py](../../../scripts/run_deeptmhmm_acceptance.py)生成，用新 `--root` 和新 `--batch` 运行；执行结果索引见 STATUS 的当前验证。

## 本地结构分析链接入

**交付目标**：从统一任务入口提交序列、宿主和本地结构，经输入事实、解析/候选映射、S-09 与条件 FreeSASA，取得可追溯的开发结果。范围为现有能力串联及其集成缺口，AF3/ESMFold2 留在预测结构包。

1. 按下方结构链资料定位已有实现与适用原件，复用统一运行层的任务、幂等、停止/恢复和产物机制；不另建一套任务系统。
2. 串联本地输入与解析/候选映射，保留原结构身份、序列/文件 hash、映射歧义和失败原因。必要请求/结果字段在实现时按现有依据明确，不把候选映射登记成已批准映射。
3. S-09 与 FreeSASA 按已记录的先行采用方案和适用守卫接入，区分实际执行、条件跳过、错误和需复核；未定科学分支关闭，RSA 出域不截断。
4. 通过统一入口验证已有可追溯样本的正常调用、非法/缺失输入、映射歧义、质量条件及 RSA 出域；验证新增链影响的失败、取消/超时、恢复、幂等和产物绑定。真实计算与夹具/故障注入分列证据。

**开发完成标准**：一条可复现命令串起本包能力；结果能回连输入、各步执行事实和原始产物；适用守卫及受影响回归通过。调用用法回填本节，实际验证与下一项回填 STATUS，执行证据集中在一个批次索引。
结果继续保留开发未签收资格并禁止自动交接。具体科学待确认项仍在 OPEN_ITEMS 单点维护；只约束受影响分支，不把整个包重新拆成准备、评审、补证阶段。

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
| `--input` 元数据 JSON | 严格八字段：protein_sequence、host_species、structure_name、declared_format、selection、context_chain_ids、source_declaration、timeout_seconds；具体类型及验证见 [policy.py](../../../src/t01_phase1_real/development/structure/policy.py) |
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
宿主在发布前校验原始清单 hash、运行隔离、输入/步骤身份和逐位 RSA 回连；停止确认先于终态，缺失/损坏输出不产生有效分析。具体源码见 [structure](../../../src/t01_phase1_real/development/structure/worker.py)，针对性测试见 [test_structure_development.py](../../../tests/test_structure_development.py)。
完整开发验收可用 [run_structure_acceptance.py](../../../scripts/run_structure_acceptance.py) 的 `--root <新的绝对运行目录> --batch <W1 discovery 下的新批次目录>` 复跑；受控故障只在内部验收使用。实际结果与本批统一索引见 STATUS。

## 前置依赖

| 依赖 | 影响的动作 | 主责与关闭证据 |
|---|---|---|
| 本地包/镜像/模型与样本 | 对应原工具实际调用 | 主开发核验既有来源/hash、资源和禁网入口；缺资产时不假跑 |
| 输入域、独立科学参考与契约签收 | 对应结果进入科研流程 | 算法验收 + 后端确定适用样本、训练重叠、指标与签收；不阻断不依赖未定结论的开发 |
| R-58 比对/构象/映射批准、结构来源/缺原子口径 | 本地结构链的对应科学分支 | 算法定点确认，后端按原件保留歧义/空值与复核守卫；不阻断序列级 DeepTMHMM |
| S-09 六项规则与 RSA 出域 | 正常质量判定及 RSA 科学消费 | 按先行采用方案开发；算法确认 OI-024/027，出域不截断、不放宽容差 |
| 服务器 profile、访问、许可、AF3/ESMFold2 权重与 MSA | 两模型实跑及目标发布 | 环境接口人 + 主开发登记并实测；容量已获用户确认，不重复询问容量 |

实际缺项和最新状态见 [STATUS](../STATUS.md)，精确科学问题见 [OPEN_ITEMS](../OPEN_ITEMS.md)。
原 D01–D08 对应事实仍在 [环境登记](PHASE1_REAL_W1_PREPARATION.md)与 [前序依赖表](PHASE1_REAL_W1_REFERENCE.md#前置依赖)，只在需要细节时打开。

## 验收与证据

开发验收必须证明统一入口真实调用、结果绑定、守卫和生命周期；不能只统计文档、测试或 hash 数。
科学验收另检适用原件、参考、指标/容差、真实映射和具名签收；完整 W1 发布要求全部必需能力与 G0–G6 齐备。
命令按 [运行手册](../../development/RUNBOOK.md)选择；新执行使用新批次，历史原件、结果和 manifest 不改写。
已通过且未受影响的检查沿用证据；仅在新变更、失败或剩余风险需要时追加测试。

## 后续波次准备

W2 可推进 BepiPred/NetMHC 等具备自身条件的独立开发、包/数据准备，成果归 W2，不等待完整 W1 冻结。
W3 的同源/注释本地数据、W4 的 CamSol 参数与 Gate、N18 WT/Candidate/Failure 接口同步消除外部依赖。
W5 N12 契约冻结前确认前 20 池与排序关系；FoldX/ProteinMPNN 不并入 W1 交付。
原 P01–P06 仅按需追溯 [前序准备表](PHASE1_REAL_W1_REFERENCE.md#后续波次准备)，其中 IEDB 检索已由 [最新用户决定](../DECISIONS.md#移除-iedb-检索链)取消，但 N03 BLAST 及其本地目标库/索引仍须落实；保留任务和使用前条件以现行计划、开放项为准。
目标环境未齐时先完成当前可执行包；转到后续独立工具时更新 STATUS，不新增“下一阶段准备”的循环。

## 原文归并

必要科学规则先从 [权威索引](../../../工作流设计/01-业务依据/README.md)定位对应原件。
来源 SRC-01～12、已归并的序列/结构/R-58/S-09/拓扑/RSA 规则，查 [前序规则表](PHASE1_REAL_W1_REFERENCE.md#原文归并)。
开发放行调整不改科学原意。遇到具体字段或边界才读取对应 ToolSpec/SOP/Schema，不要求每次遍历整包。

## 剩余开放项

W1 科学使用前需处理 OI-015/023/024/027 和 B2 参考/输入/契约签收。问题定义、负责人和关闭证据统一在 [OPEN_ITEMS](../OPEN_ITEMS.md)。
未决项按影响约束具体功能、科学消费或发布，不阻断无依赖的整个交付包；真实阻塞到来时写清缺什么、由谁提供。

<details>
<summary>只在追溯或查实现细节时展开</summary>

- 通用运行层：[接口与实现](PHASE1_REAL_W1_RUNTIME_IMPLEMENTATION.md)、[契约设计](PHASE1_REAL_W1_CONTRACT_DESIGN.md)。
- DeepTMHMM：[原包实测](PHASE1_REAL_W1_DEEPTMHMM_OFFLINE.md)、[B2 接口/参考](PHASE1_REAL_W1_B2_REVIEW.md)、[边界补证](PHASE1_REAL_W1_B2_BOUNDARIES.md)。
- 结构链：[映射条件](PHASE1_REAL_W1_B1_REVIEW.md)、[输入事实](PHASE1_REAL_W1_B1_ENGINEERING_REVIEW.md)、[FreeSASA 消费](PHASE1_REAL_W1_B1_FREESASA_REVIEW.md)、[S-09/参数采用](PHASE1_REAL_W1_FREESASA_S09_DECISION.md)。
- 预测：[身份、资产与验证输入](PHASE1_REAL_W1_STRUCTURE_PREDICTION_G0.md)。
- [原计划完整记录](PHASE1_REAL_W1_REFERENCE.md)与 [历史索引](README.md)保留旧编号、评审和检查记录；其中旧开发停止条件由本页覆盖。

</details>
