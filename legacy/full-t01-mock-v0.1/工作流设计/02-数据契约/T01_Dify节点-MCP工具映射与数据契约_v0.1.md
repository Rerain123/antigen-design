# T-01 Dify 节点—MCP 工具映射与数据契约

> 文档状态：DRAFT v0.1，等待业务与算法评审  
> 编制日期：2026-08-31  
> 当前角色：已冻结 Dify/Mock v0.1 的工程契约与历史映射；不再直接定义生产一期范围  
> 生产一期范围：以[一期 18 节点范围基线](../../../../docs/project/PHASE1_SCOPE_REBASELINE.md)为准  
> 适用范围：现有 T-01 v10 Mock 编排、Mock MCP 与回归测试；生产契约须在对应阶段门禁后另行升版  
> 本文不实现科学算法，不改变源工作流，不代表任何工具已经在本项目服务器部署完成

> [!IMPORTANT]
> 用户于 2026-09-03 确认新 18 节点图替换旧一期范围。S-23、S-06/PSORTb、S-32/MD、
> `context_scores` 注入、分支 4 稳定性救援、DiscoTope、IEDB Immunogenicity、SolubleMPNN
> 和 C29/C30 等明确排除能力即使仍出现在本文、现有生成器或 Mock 场景中，也只属于冻结的
> v0.1 回归资产，不构成生产一期授权。阶段 G4 迁移前不删除这些基线资产，也不据此修改生产实现。
> 后续节点 01 内网决定又明确删除 S-07、RCSB PDB、AlphaFold DB 及 BLAST→UniProt→AFDB
> 回退；生产节点 01 只保留 AlphaFold3/ESMFold2。内网只限制外部数据库查询，不影响部署在
> 甲方服务器上的模型；输入为必填目标蛋白序列、宿主物种和可选结构。下文冲突行只作 Mock/历史。

## 1. 依据、优先级与边界

### 1.1 权威业务依据与历史参考

当前权威原件及冲突处理规则统一见[权威业务资料索引](../../../../工作流设计/01-业务依据/README.md)。
[一期 18 节点图](<../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>)决定一期
范围、优先级、裁剪顺序和明确排除项；T-01 旧算法图、一期边界 PDF 与博士提供的 Agent A
v10.5 原始包继续定义保留节点的科学细节与历史依据。本文是派生工程契约，不能反向覆盖这些原件。

| 依据 | 用途 | SHA-256 |
|---|---|---|
| [一期裁剪算法图](<../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>) | 决定生产一期范围、落地优先级、裁剪顺序和明确排除项 | EE4A3E5DFA85F9E19EDA60EDB46BFD6735A2233CBD4D94038D6100A7C66E3F87 |
| [节点 01 内网裁剪会议截图](../../../../工作流设计/01-业务依据/一期节点01内网裁剪会议截图_20260903.png)及后续澄清 | 只删除外部数据库搜索；本地 AF3/ESMFold2 正常使用；输入=目标序列+宿主物种+可选结构 | C980D6CC5D1446278304AF49365850872403932CDCA9038D5B9624E72E4EBED4 |
| [T01_算法图_v10_20260821.md](../../../../工作流设计/01-业务依据/T01_算法图_v10_20260821.md) | 决定 T-01 步骤顺序、分支、门控、降级、重试、排序和交接逻辑 | 332FCAF2E1ACC272445A47F3EC001455F41BF960FFB66E51F4C36AD5ADC9163D |
| [已部署蛋白工具接口调用与测试手册.md](../../../../工具部署/已部署蛋白工具接口调用与测试手册.md) | 仅作为四个工具的历史版本、CLI 调用、目录隔离和验收方式参考 | 756B9FBD47F9CF770BEFB2490312B9A6B4F7454A5B379AB141F1A5051ED9F85E |

源文档的适用规则如下：

1. 先按一期 18 节点图判断能力是否属于一期，再对保留节点同时核对 T-01 旧算法图与 Agent A
   v10.5 对应 SOP/Schema/ToolSpec；科学细节冲突时按权威资料索引处理，不得静默选边。
2. 工具手册描述的是甲方服务器历史部署，不代表本项目当前能力。
3. 本项目所有科学工具当前统一视为 NOT_DEPLOYED，必须重新部署并验收。
4. 工具手册中的绝对路径不能直接写入本项目代码，只能作为历史参考。
5. 工具手册第 8 节 REST API 是建议而非已部署接口，本项目采用 MCP 契约重新设计。
6. HADDOCK3 不在 T-01 v10 主路径中，不得擅自加入 T-01；后续可用于其他对接工作流。
7. glyco_removal 已移出 T-01，应由 T-05 处理；T-01 仅保留 S-12 糖基化扫描。
8. epitope_fixed 已从 v10 输入删除，不得重新加入。

### 1.2 LLM、Dify 与后端职责

| 组件 | 允许职责 | 禁止职责 |
|---|---|---|
| LLM | 收集用户输入、抽取用户已明确提供的信息、询问缺失字段、发起 MCP 调用、解释后端报告 | 科学计算、阈值判断、权限合成、过滤、排序、填补缺失结果 |
| Dify | 可视化编排、调用 MCP、根据后端枚举路由、记录节点输入输出、Mock/Smoke/Production 调试 | 在 LLM 节点中实现科学规则；在 Code 节点中复制核心科学算法 |
| MCP 服务 | 参数校验、鉴权、任务提交、状态查询、结果返回、统一错误与 Artifact 契约 | 接受任意 Shell 命令或任意服务器绝对路径 |
| 后端科学服务 | 所有计算、数据处理、门控函数、重试规则、降级规则、Hard Filter、Pareto 和结果组装 | 根据 LLM 自由文本临时改变科学规则 |
| 科学工具 Worker | 在隔离环境中执行具体软件，保存原始输出与日志 | 直接面向 LLM 暴露非结构化命令接口 |

核心原则：Dify 管理流程拓扑，后端管理科学语义，LLM 不参与内部计算。

## 2. Dify 工作流分层

### 2.1 主工作流

以下名称和分层固定用于已冻结的 Dify/Mock v0.1 回归基线；它们不是新一期生产拓扑的授权。
生产阶段工作流须在对应阶段达到 G4 后按一期 18 节点基线迁移、升版并重新回归。

Mock 主工作流名称固定为 T01_Master_v10，包含以下阶段子工作流：

| 顺序 | 子工作流 | 对应算法阶段 |
|---:|---|---|
| 0 | T01_P0_Structure | 阶段0：结构获取与基础分析 |
| 1 | T01_P1_EpitopeSafety | 阶段1：表位、安全与糖基化 |
| 2 | T01_P2_ConservationDomain | 阶段2：保守性与功能域 |
| 3 | T01_P3_WTDevelopability | 阶段3：WT 可开发性基线 |
| 4 | T01_P4_Design | 阶段4：序列设计 |
| 5 | T01_P5_VariantEvaluation | 阶段5：设计后变体重评与排序 |
| 6 | T01_P6_CodonStabilityMD | 阶段6：密码子、WT 稳定性与 MD |
| 7 | T01_P7_OutputHandoff | 阶段7：输出与交接 |

现有 T01_Master_v10 还包含阶段外的纯逻辑节点：长度守卫、0b 上下文注入路由、step11 权限输入准备、R-57、step15/16 evidence_bundle、step19、step20、MD 门控和 step26 交接分叉。其中被新一期基线排除的路径只保留作 Mock 回归，不得复制进生产一期工作流。

### 2.2 节点粒度

1. 一个 S 步骤原则上对应一个可观察的 Dify 工具节点。
2. 同一 S 步骤在不同调用点重用时，使用不同 Dify node_id，但 MCP tool_name 保持一致，并通过 scope 区分。
3. 四层表位验证、Hard Filter、Pareto 等 T 层逻辑必须对应后端确定性工具节点，不能交给 LLM。
4. 逐变体计算由后端批量完成；不得在 Dify 画布展开为数千个候选节点。
5. v0.1 严格保持源文档顺序，不自行把串行步骤改为并行；性能优化必须单独评审。

## 3. T-01 请求契约

### 3.0 当前一期迁移口径

一期用户输入基线已经明确为：`protein_sequence`、`host_species` 必填，`structure` 可选。
结构文件按专家 S-07c/结构链 ToolSpec 接受 PDB、CIF、mmCIF，保留原格式；chain 可选，解析失败
进入 `failure_report`，结构工具消费前执行 R-58。设计目标和表达宿主按一期图为可选，且不改变
已确认的入口必填集合；其精确关系由 OI-004 定点归并。

下面 3.1 表是冻结 Mock v0.1 的历史请求映射，不再作为要求甲方填写全部字段的现行清单。
新一期 Mock 请求规格由 [PH1-MOCK-M1](../../../../docs/project/phase1/PHASE1_MOCK_V01_BACKLOG.md)根据专家原文归并；
一致条款直接采用，只有具体科学冲突或真实缺口才定点复核。

### 3.1 Mock v0.1 源输入映射（历史）

| 字段 | 类型 | 必填 | 源文档语义 |
|---|---|:---:|---|
| protein_sequence | string | 是 | 输入蛋白氨基酸序列 |
| host | string | 是 | 宿主；也参与安全筛查的宿主相似性分析 |
| pathogen_type | string | 是 | 当值为 bacteria 时触发 S-06 |
| objective | string | 是 | 设计目标；thermostability 会触发 MD 条件之一 |
| epitope_mode | enum | 是 | both、bcell_only、tcell_only |
| epitope_policy | string/object | 是 | v10 输入字段；允许值和内部结构源文档未展开，待 SOP 补充 |
| regions_permissions | array | 否 | v10 新增输入；用于 user_regions 逐 region 覆盖 |
| md_validation | boolean | 是 | 用户显式要求 MD 的开关 |
| membrane_design_confirm | boolean | 是 | R-57 膜蛋白设计确认 |
| low_conf_design_confirm | boolean | 是 | R-57 低置信结构设计确认 |
| context_scores | object/null | 否 | 来自 T-02 auto_refine 的上下文注入 |

### 3.2 为执行所需但源文档未完整定义的字段

以下字段是工程契约候选，不是对源文档科学规则的修改。在评审通过前不得设置隐式默认值。

| 字段 | 原因 | v0.1 处理 |
|---|---|---|
| mhc_alleles | S-18 的 NetMHCpan/NetMHCIIpan/MHCflurry 均需要等位基因语义 | 可选；当 epitope_mode 包含 T 细胞且没有服务端已批准面板时返回 INPUT_REQUIRED |
| expression_host | S-30 仅在用户提供表达宿主时执行，不能与安全筛查 host 自动视为同一概念 | 可选；缺失时跳过 S-30 |
| request_visualization | C29/C30 仅在用户要求时执行 | 可选 boolean，默认 false 属于展示层默认，不影响科学流程 |
| execution_mode | 调试需要 mock、smoke、production | 工程枚举，不进入科学计算 |
| client_request_id | 幂等提交和审计 | 工程字段，不进入科学计算 |

### 3.3 长度守卫

1. 当序列长度小于 9 aa 且流程需要 MHC 分析时，必须 HALT。
2. 当序列长度小于 30 aa 时，必须产生 WARNING。
3. 何谓“需要 MHC”由 epitope_mode 是否包含 T 细胞路径确定；不得由 LLM猜测。

### 3.4 context_scores 最小契约

context_scores 必须包含显式路由置信字段，由 T-02 或后端产生，T-01 不负责重新推断该置信度。

| 字段 | 类型 | 说明 |
|---|---|---|
| injection_confidence | enum | HIGH 或 NON_HIGH；对应高置信/非高置信路由 |
| sequence_level.conservation | ArtifactRef/null | 序列级保守性数据 |
| sequence_level.bcell | ArtifactRef/null | B 细胞表位数据 |
| sequence_level.tcell | ArtifactRef/null | T 细胞表位数据 |
| sequence_level.epitope_maps | ArtifactRef/null | 表位三图数据 |
| sequence_level.safety | ArtifactRef/null | 安全筛查数据 |
| sequence_level.glyco | ArtifactRef/null | 糖基化数据 |
| structure_level.structure | ArtifactRef/null | 结构数据 |
| structure_level.quality | ArtifactRef/null | 结构质量数据 |
| structure_level.topology | ArtifactRef/null | 拓扑数据 |
| structure_level.rsa | ArtifactRef/null | RSA 数据 |

两条注入路径都必须补跑 S-16、解包 core_map、初始化 evidence_bundle 六键并判定 is_membrane。HIGH 路由到 step15；NON_HIGH 路由到 step12。未提供 context_scores 时走完整独立路径。

## 4. MCP 通用数据契约

### 4.1 StepRequest

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| schema_version | string | 是 | 数据契约版本，例如 0.1.0 |
| workflow_version | string | 是 | 固定记录 T01-v10 |
| run_id | string | 是 | 一次 T-01 运行的全局 ID |
| step_id | string | 是 | 源步骤或 T 层节点 ID |
| node_id | string | 是 | Dify 节点 ID |
| attempt | integer | 是 | 从 1 开始 |
| scope | string | 是 | wt、variant、rescue、context_injection 等调用范围 |
| execution_mode | enum | 是 | mock、smoke、production |
| parameters | object | 是 | 该步骤的白名单参数 |
| input_artifacts | array[ArtifactRef] | 是 | 可以为空数组，不接受任意服务器路径 |
| context | object | 是 | 经过 Schema 校验的最小上游上下文 |
| idempotency_key | string | 是 | 防止重复提交 |

### 4.2 StepResult

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| schema_version | string | 是 | 与 StepRequest 兼容的数据契约版本 |
| workflow_version | string | 是 | T01-v10 |
| run_id | string | 是 | 原样返回 |
| step_id | string | 是 | 原样返回 |
| node_id | string | 是 | 原样返回 |
| attempt | integer | 是 | 当前尝试次数 |
| job_id | string/null | 是 | 异步任务 ID；无需异步时为 null |
| status | enum | 是 | QUEUED、RUNNING、SUCCEEDED、SKIPPED、DEGRADED、WAITING_USER、FAILED、CANCELLED |
| progress | object/null | 是 | QUEUED/RUNNING 时的 current、total、message；其他状态可为 null |
| data | object/null | 是 | 小型结构化业务结果；无结果时为 null |
| artifacts | array[ArtifactRef] | 是 | 原始和完整结果文件引用 |
| quality_flags | array[string] | 是 | 可以为空数组 |
| warnings | array[Warning] | 是 | 可以为空数组 |
| error | ToolError/null | 是 | 成功时为 null |
| provenance | Provenance | 是 | 工具、模型、参数和时间信息 |
| metrics | ExecutionMetrics | 是 | 耗时和资源摘要 |

### 4.3 ArtifactRef

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| artifact_id | string | 是 | 对外唯一引用 |
| logical_name | string | 是 | 业务文件名，不是服务器绝对路径 |
| artifact_type | string | 是 | fasta、pdb、csv、json、report 等 |
| media_type | string | 是 | MIME 类型 |
| sha256 | string | 是 | 内容哈希 |
| size_bytes | integer | 是 | 文件大小 |
| producer_step_id | string | 是 | 产出步骤 |
| created_at | datetime | 是 | ISO 8601 |
| resource_uri | string/null | 是 | 授权后的 MCP Resource URI 或下载引用 |

不得在 Dify变量或 LLM上下文中返回 /data/... 等服务器绝对路径。

### 4.4 ToolError

| 字段 | 类型 | 说明 |
|---|---|---|
| code | string | 稳定、可测试的错误码 |
| category | enum | INPUT_VALIDATION、TOOL_UNAVAILABLE、TIMEOUT、EXECUTION、OUTPUT_MISSING、OUTPUT_INVALID、SCIENTIFIC_GATE、CANCELLED、INTERNAL |
| retryable | boolean | 后端是否允许自动重试 |
| message | string | 面向开发者的简明信息 |
| user_message | string | 可直接向用户展示的信息 |
| details | object | 经过脱敏的结构化细节 |

### 4.5 Provenance

至少记录：adapter_name、adapter_version、tool_name、tool_version、model_name、model_version、parameter_profile、parameters、random_seed、input_hashes、started_at、finished_at、exit_code、compute_profile。命令行可以写入受限日志，但不能返回给 LLM。

### 4.6 工具调用的通用安全约束

这些约束来自工具手册的通用调用规则，并适用于所有后续工具：

1. 每次调用创建独立任务目录，逻辑结构为 input、output、logs。
2. 工具运行环境、源码和模型目录只读；任务目录可写。
3. 使用参数数组启动子进程，不拼接 Shell 字符串。
4. exit_code 为 0 后仍必须检查预期输出存在、非空且可解析。
5. 所有用户参数使用白名单和 Schema 校验。
6. 每个任务记录工具版本、模型版本、参数、种子、时间和退出码。
7. 长任务必须异步执行，提供提交、状态、取消和结果读取能力。

### 4.7 异步任务 MCP 契约

每个科学工具可以立即返回终态 StepResult，也可以返回带 job_id 的 QUEUED/RUNNING StepResult。所有异步工具共享以下 MCP 工具：

| MCP tool_name | 输入 | 输出 | 说明 |
|---|---|---|---|
| jobs.get_status | run_id、job_id | StepResult | 查询进度和当前状态 |
| jobs.get_result | run_id、job_id | StepResult | 仅终态可读取完整 data/artifacts |
| jobs.cancel | run_id、job_id、reason | StepResult | 尝试取消；终态任务不得重复取消 |

Dify 在 mock 模式可以同步得到结果；smoke/production 不得为等待长计算而长期占用单个工具调用。整体 T-01 状态由后端 run_id 持久化，Dify 执行记录用于观察与调试，但不是唯一状态源。

### 4.8 运行状态

| RunStatus | 说明 |
|---|---|
| DRAFT | 用户输入尚未完整 |
| VALIDATING | 后端正在校验输入 |
| QUEUED | 已创建但尚未开始 |
| RUNNING | 至少一个步骤正在执行 |
| WAITING_USER | 等待 R-57 等明确确认 |
| SUCCEEDED | 已按 step26 任一路径完成交接组装 |
| DEGRADED | 允许的降级路径完成，必须携带 quality_flags |
| FAILED | 不可恢复的工具、数据或系统失败；设计全淘汰但已完成 WT+failure_report 交接不自动等同于执行失败 |
| CANCELLED | 用户或系统取消 |

最终 outcome 与 RunStatus 分离，仅允许：VARIANT_HANDOFF、WT_DESIGN_SKIPPED、WT_FAILURE_REPORT，分别对应 step26 的 best 存在、设计未执行、设计全淘汰三路。

## 5. T-01 核心中间数据契约

### 5.1 evidence_bundle 六键

六个键始终存在；缺少数据时使用经 Schema 允许的空值，不允许缺键。

| 键 | 来源 | 语义 |
|---|---|---|
| fixed_input | S-15/step11 | conserved.fixed_positions |
| domains_input | S-16 | 功能域输入 |
| core_map | S-16 | 四分量 core_map；四分量名称需从 v10 SOP 补充，本文不猜测 |
| epitope_evidence | S-19 | 三图及 E0-E4 证据 |
| degraded_regions | S-13/S-15/step11 | conservation_confidence 为 LOW 时的降级区域 |
| user_regions | regions_permissions | 用户逐 region 覆盖 |

### 5.2 epitope_evidence

必须包含：b_cell_epitope_map、t_cell_presentation_map、b_cell_antigenic_hotspot_map。证据等级为 E0 至 E4；文档列出权重 1.0、0.8、0.5、0.2，但未在算法图中完整写明每一级与权重的逐项映射，因此具体映射必须从 v10 SOP 固化后再实现。

### 5.3 design_permissions

每个位点至少包含：position_1based、permission、allowed_residues、evidence_refs、rule_refs、user_override。permission 仅允许 FIXED、RESTRICTED、OPEN。

后端必须实现源文档规则：

- HARD = E4 接触 ∪ 验证功能残基 ∪ 二硫键 ∪ 用户固定 ∪ 深核心 ∪ 高保守与机制交集。
- RESTRICTED = 高保守减 HARD ∪ 普通核心 ∪ 寡聚界面 ∪ E3 ∪ E2 ∪ 关键 PTM ∪ 关键 glyco。
- SOFT = E1 ∪ 浅埋藏。
- HARD、RESTRICTED、SOFT 映射到 FIXED、RESTRICTED、OPEN。
- E3 不自动升级、高保守不自动 HARD、无 MSA 不自动 OPEN、E1 走 SOFT 到 OPEN。
- user_regions 逐 region 覆盖。

### 5.4 最终 Candidate JSON

S-42 输出至少包含：best_candidate、top20_variants、delta_table、design_permissions、evidence_provenance、quality_flags、warnings、design_skipped、failure_report、artifacts。膜蛋白设计跳过时 dna 为 null。具体 Candidate 内部字段需要 v10 SOP/Pydantic模型补充，本文不自行定义科学字段。

## 6. Dify 节点—MCP 工具映射

所有实际部署状态均为 NOT_DEPLOYED；pure_backend 表示需要编写确定性后端代码，而不是调用 LLM。

### 6.1 启动、长度与上下文

| Dify node_id | 源节点 | 类型 | MCP tool_name | 关键输出/路由 |
|---|---|---|---|---|
| T01_START | START | User Input/LLM收集 | t01.validate_request | 只收集与校验，不计算 |
| T01_G00_LENGTH | 长度守卫 | pure_backend | t01.evaluate_length_guard | HALT、WARNING、PASS |
| T01_G01_CONTEXT | G0B | IF/ELSE | t01.route_context_scores | NONE、HIGH、NON_HIGH |
| T01_0B_INJECT | 0b | pure_backend | t01.inject_context_scores | 注入序列级/结构级数据，随后必须进入 S-16 |
| T01_T11_PREPARE | step11 | pure_backend | t01.prepare_permission_inputs | fixed_input、fixed、degraded_regions、epitope_evidence |
| T01_T15_GUARD | step15 | pure_backend | t01.evaluate_mutable_length | mutable_length 结果 |
| T01_T16_BUNDLE | step16 | pure_backend | t01.build_evidence_bundle | 六键完整 evidence_bundle |

### 6.2 阶段0：结构获取与基础分析

> P0 第七版当前生产范围为必填目标序列/宿主物种和可选结构；有合法结构时直接进入 S-09，
> 无结构时执行 S-08，再进入 S-09→S-04→条件 S-11，详见
> [P0 范围重基线](../../../project-history/p0-v07-plan/P0_SCOPE_REBASELINE.md)。下表完整描述的是冻结的
> Mock 基线版：`P0_S07_FETCH`、`P0_G_EXISTING`、`P0_G_BACTERIA`、`P0_S06_LOCALIZE` 均不得进入
> 生产第七版原样复用；生产版需新建仅基于甲方可选结构的确定性分支。G4 前不删除旧 Mock 节点。

| Dify node_id | S步骤 | MCP tool_name | 工具/实现 | 关键条件与输出 |
|---|---|---|---|---|
| P0_S07_FETCH | 旧 Mock S-07 | structure.fetch | RCSB PDB、AlphaFold DB、BLAST | `EXCLUDED_FROM_PHASE1`；只保留冻结回归 |
| P0_G_EXISTING | 旧 Mock 路由 | t01.route_existing_structure | pure_backend | 旧节点不可原样复用；生产版只判断甲方是否提供且通过校验的结构，不消费 S-07 结果 |
| P0_S08_PREDICT | S-08 | structure.predict | AlphaFold3、ESMFold2 | 旧 Mock 行；生产版仅在没有合法输入结构时执行，本地模型不受外部数据库限制 |
| P0_S09_QUALITY | S-09 | structure.assess_quality | pure_backend | 消费甲方提供结构或 S-08 预测结构；confidence 为 high、medium、low |
| P0_S04_TOPOLOGY | S-04 | topology.predict | DeepTMHMM | tm_count、is_membrane |
| P0_G_RSA | 结构低置信门控 | t01.route_rsa | pure_backend | low 跳过 S-11 并设 rsa=null |
| P0_S11_RSA | S-11 | structure.compute_rsa | FreeSASA | 必须含 R-58 序列比对校验 |
| P0_G_BACTERIA | 旧 Mock 细菌分支 | t01.route_pathogen_type | legacy_mock_only | 仅保持冻结基线回归兼容，不属于当前生产 P0 |
| P0_S06_LOCALIZE | 旧 Mock S-06 | localization.predict_bacteria | legacy_mock_only | OI-019 已决定移出一期；仅保留冻结 Mock 回归，不得生产化 |

### 6.3 阶段1：表位、安全与糖基化

| Dify node_id | S步骤 | MCP tool_name | 工具/实现 | 关键条件与输出 |
|---|---|---|---|---|
| P1_S03_IEDB | S-03 | epitope.query_iedb_prior | IEDB镜像、BLAST | 已发表表位证据 |
| P1_S17_BCELL | S-17 | epitope.predict_bcell | BepiPred 3.0；DiscoTope-3.0条件激活 | epitope_mode 为 both/bcell_only；DiscoTope 仅实验结构或 pTM≥0.5，预测结构须标注 medium confidence caveat |
| P1_S18_TCELL | S-18 | epitope.predict_tcell | NetMHCpan 4.2、NetMHCIIpan 4.3、IEDB Immunogenicity可选 | epitope_mode 为 both/tcell_only；IEDB Immunogenicity仅限9-mer |
| P1_S19_MAPS | S-19 | epitope.synthesize_maps | pure_backend | 三图、E0-E4、合成分大于0.5热点 |
| P1_S12_GLYCO | S-12 | glyco.scan | BioPython正则 | 按三图热点重算遮蔽 |
| P1_S23_SAFETY | S-23 | safety.assess_triple | IApred、AlgPred 2.0、ToxinPred2、宿主库BLAST | host_similarity_flag 四维合成 |

MHCflurry 2.2.1 仅作为手册中的 MHC-I 工具参考。它不在 T-01 v10 S-18 的必备工具行中，不能替代 NetMHCpan/NetMHCIIpan。若后续作为辅助引擎加入，必须单独评审并保留其 cartesian 与 genotype 语义差异。

### 6.4 阶段2：保守性与功能域

| Dify node_id | S步骤/T层 | MCP tool_name | 工具/实现 | 关键输出 |
|---|---|---|---|---|
| P2_S13_HOMOLOGS | S-13 | conservation.collect_homologs | 病原数据库、BioPython、MMseqs2、BLAST | conservation_confidence HIGH/MEDIUM/LOW |
| P2_S14_CONSERVATION | S-14 | conservation.compute | MAFFT | 位点保守性 |
| P2_S15_REGIONS | S-15 | conservation.extract_regions | pure_backend | standard/relaxed/minimal/failed |
| P2_R11_TYPING | R-11 | conservation.analyze_within_type | pure_backend/复用同源工具 | LOW 时设置 conserved_confidence_degraded |
| P2_S16_DOMAINS | S-16 | domain.identify | UniProt、BioPython、DeepTMHMM复用、结构坐标计算 | 功能域、二硫键、寡聚界面、core_map |

S-16 的结构规则必须保留：二硫键 Cβ-Cβ 小于 6.0 Å；寡聚界面小于 4.5 Å。

### 6.5 阶段3：WT 可开发性基线

| Dify node_id | S步骤 | MCP tool_name | 工具/实现 | 关键输出 |
|---|---|---|---|---|
| P3_S36_SOLUBILITY | S-36 | developability.predict_solubility | CamSol-reimpl | 溶解度 |
| P3_S36A_EXPRESSION | S-36a | developability.compute_expressibility | BioPython ProtParam | 表达量特征 |
| P3_S37_AGGREGATION | S-37 | developability.predict_aggregation | AGGRESCAN3D结构版/序列版 | 聚集倾向；R-58详细校验条款待SOP补充 |
| P3_S38_PH | S-38 | developability.predict_ph_stability | PROPKA | pH稳定性；R-58详细校验条款待SOP补充 |
| P3_S39_TAG | S-39 | developability.assess_tag_exposure | pure_backend，复用 RSA | 标签暴露 |
| P3_S40_BASELINE | S-40 | developability.assess | pure_backend | 六维归一化与 classification |
| P3_R57_GATE | R-57 | t01.evaluate_design_applicability | pure_backend | CONTINUE 或 DESIGN_SKIPPED |

R-57：is_membrane 且未确认，或 confidence=low 且未确认，均跳过 S-27，走 WT 交接并记录对应 quality_flags；膜蛋白跳过时提示转入 T-11；显式确认后才允许继续。

### 6.6 分支4：稳定性补救

| Dify node_id | 源节点 | MCP tool_name | 工具/实现 | 条件/输出 |
|---|---|---|---|---|
| B4_GATE | 分支4 | t01.route_stability_rescue | pure_backend | classification=poor 且非膜触发 |
| B4_S31_SCAN | S-31 | stability.scan_mutations | FoldX PositionScan、ThermoMPNN | fixed=保守∪功能域；epitope_peaks=三图热点 |
| B4_TOP3_SCREEN | Top3粗筛 | stability.screen_rescue_top3 | S-36、S-37、S-36a、S-40序列版 | 补救成功/失败 |
| B4_S08_PREDICT | S-08复用 | structure.predict | AlphaFold3/ESMFold2 | 突变体结构 |
| B4_S11_RSA | S-11复用 | structure.compute_rsa | FreeSASA | 重算 RSA |
| B4_S09_QUALITY | S-09复用 | structure.assess_quality | pure_backend | 重评结构质量 |

### 6.7 阶段4：序列设计

| Dify node_id | S步骤 | MCP tool_name | 工具/实现 | 关键规则 |
|---|---|---|---|---|
| P4_S27_DESIGN | S-27 | design.generate_mutations | ProteinMPNN；SolubleMPNN可选；ThermoMPNN预测器 | 后端内部执行 v10 双变量权限合成；SolubleMPNN仅 objective=solubility 且表达宿主为大肠杆菌 |
| P4_S28_VALIDATE | S-28 | design.validate | ESM-IF1、ESMFold2、AlphaFold3 | 输出通过变体及 mutation_burden 六维；R-58详细校验条款待SOP补充 |
| P4_RETRY_GATE | S-28重试 | t01.evaluate_design_retry | pure_backend | 首轮全淘汰后依次 48、64 设计，最多重试2轮 |
| P4_S29_CONSERVATIVE | S-29 | design.check_conservative_mutations | pure_backend | 保守区非空时执行；违规变体排除 |

历史手册中的 ProteinMPNN 提交 8907e6671bfbfc92303b5f79c4b5e6ce47cdef57 仅为参考基线。本项目必须重新部署，并验证固定位置、允许残基和 v10 design_permissions 的准确映射；历史最小示例不足以证明该能力已满足。

### 6.8 阶段5：变体重评与排序

| Dify node_id | 源步骤 | MCP tool_name | 工具/实现 | 关键规则 |
|---|---|---|---|---|
| P5_VARIANT_REASSESS | step19批量重评 | variant.reassess_developability | 复用 S-36/36a/09/37/38/39 | 逐变体，后端批量处理 |
| P5_S23_SAFETY | S-23复用 | safety.assess_triple | scope=variant | 非 PASS 设置 safety_excluded |
| P5_S12_GLYCO | S-12复用 | glyco.scan | scope=variant | 逐变体复扫 |
| P5_EPITOPE_L1_L4 | step19四层验证 | epitope.validate_presentation | pure_backend及结构数据 | L1恒可查；无结构时L2-L4为null |
| P5_S40_COARSE | S-40粗评 | developability.assess | 五维 | 产生 overall |
| P5_SCORE_POOL | step19b成本保护 | t01.select_stability_score_pool | pure_backend | overall前40，典型不超过24全打 |
| P5_S31_VARIANT_DDG | S-31变体打分 | stability.score_variants | FoldX BuildModel五轮平均 | 基座非low、非膜、score_pool非空才执行 |
| P5_S40_FINAL | S-40终评 | developability.assess | 六维，含 stability_ddg | 终评结果 |
| P5_STEP20_RANK | step20 | ranking.rank_variants | pure_backend | Hard Filter→Pareto→目标档案→双层多样性→SC-10 |

四层验证固定条件：L1 热点残基同一性；L2 RSA 差大于 -0.15；L3 热点 Cα 加功能域 RMSD 小于 2.0 Å，并记录 shape_similarity 但 evidence 不设硬阈；L4 画像差小于 0.2。structural 未过设置 epitope_violation 并硬排除，prediction 未过设置 soft_penalty。无结构时 L2-L4 不可计算，structural 与 prediction 两个字段均置 null。

step20 固定顺序：

1. Hard Filter：epitope_violation、safety_excluded、constraint_override、host HIGH、mutation burden 超档。
2. Pareto front：developability、stability、epitope_preservation、burden。
3. front 内按 objective_profile 排序。
4. 双层多样性：家族配额5；序列聚类 identity 大于95%。
5. SC-10：best.overall 小于0.30时 WARNING，并降级 WT 交接或 failure_report；两者选择规则待 SOP 补充。

### 6.9 阶段6：密码子、WT 稳定性与 MD

| Dify node_id | S步骤/门控 | MCP tool_name | 工具/实现 | 条件/输出 |
|---|---|---|---|---|
| P6_S30_CODON | S-30 | sequence.optimize_codons | DNA Chisel、BioPython | 仅提供表达宿主时；膜跳过场景 dna=null |
| P6_S31_WT_SCAN | S-31 | stability.scan_mutations | FoldX PositionScan、ThermoMPNN | 非膜且结构非low；tm_count=1限大胞外域 |
| P6_MD_GATE | MD门控 | t01.evaluate_md_gate | pure_backend | objective=thermostability或md_validation，且非膜且ddg非空 |
| P6_S32_MD | S-32 | dynamics.run_md_validation | AmberTools、AMBER默认/Gromacs、MD分析 | top3按consensus顺序 |

历史手册中的 ThermoMPNN 提交 2b04fd370e399911b1fa5848112cc9013f084110 仅为参考基线。本项目必须重新部署，并在实现任何阈值前统一 ddG_pred 的生物学符号定义；源手册明确要求先统一该规则。

### 6.10 阶段7：输出与交接

| Dify node_id | S步骤/门控 | MCP tool_name | 工具/实现 | 条件/输出 |
|---|---|---|---|---|
| P7_S42_ASSEMBLE | S-42 | output.assemble_candidate_json | pure_backend + Pydantic | Candidate JSON |
| P7_VIS_GATE | VIS | t01.route_visualization | pure_backend | 用户要求时进入 C29/C30 |
| P7_C29_VISUAL | C29 | output.render_comparison_report | 展示层 | 用户要求时生成可视化对比报告 |
| P7_C30_EXPLAIN | C30 | output.prepare_explanation | 展示层 | 用户要求时生成后端事实摘要；LLM只能据此解读 |
| P7_STEP26_HANDOFF | step26 | t01.route_handoff | pure_backend | best、design_skipped、failure_report三路 |
| P7_S43_PACKAGE | S-43 | handoff.assemble_agent_c | pure_backend | 变体或WT交接包 |
| P7_S44_DELIVER | S-44 | handoff.deliver_agent_c | 交付动作 | 目标接口尚未定义，先Mock |

## 7. 关键门控与分支矩阵

| gate_id | 输入条件 | 路由/动作 | 必须记录 |
|---|---|---|---|
| G-LENGTH-HALT | 长度小于9且需MHC | HALT | 输入错误/停止原因 |
| G-LENGTH-WARN | 长度小于30 | 继续并WARNING | quality_flags/warnings |
| G-CONTEXT-HIGH | context_scores=HIGH | 补S-16后到step15 | 注入来源和哈希 |
| G-CONTEXT-NONHIGH | context_scores=NON_HIGH | 补S-16后到step12 | 注入来源和哈希 |
| G-CONTEXT-NONE | 无context_scores | S-07完整路径 | 无 |
| G-BACTERIA | pathogen_type=bacteria | 执行S-06 | psortb_flag |
| G-STRUCTURE-LOW | confidence=low | S-11跳过，rsa=null | 降级原因 |
| G-R57-MEMBRANE | is_membrane且未确认 | 跳过S-27，WT交接 | membrane_expected_poor |
| G-R57-LOW | confidence=low且未确认 | 跳过S-27，WT交接 | skipped_low_confidence |
| G-BRANCH4 | classification=poor且非膜 | 稳定性补救 | 触发原因 |
| G-S28-RETRY | 当前轮全淘汰 | 48后64，最多2轮 | attempt与设计数量 |
| G-19B | 基座非low、非膜、score_pool非空 | FoldX BuildModel | score_pool来源 |
| G-WT-SCAN | 非膜且结构非low | WT饱和扫描 | tm_count区域限制 |
| G-MD | 热稳定目标或md_validation，且非膜且ddg非空 | top3 MD | 触发原因 |
| G-STEP26-BEST | best存在 | 变体交接 | best_candidate |
| G-STEP26-SKIP | 设计未执行 | WT+design_skipped | 门控原因 |
| G-STEP26-FAILED | 设计全淘汰 | WT+failure_report | 淘汰统计 |

## 8. Mock 场景与分支验收

Mock MCP 必须使用与真实 MCP 完全相同的 tool_name、输入 Schema 和输出 Schema。

| scenario_id | 场景 | 预期路径 |
|---|---|---|
| MOCK-HAPPY-PATH | 全部通过 | best候选交接 |
| MOCK-SHORT-MHC-HALT | 小于9aa且需MHC | 长度守卫停止 |
| MOCK-SHORT-WARNING | 9至29aa | WARNING后继续 |
| MOCK-CONTEXT-HIGH | 高置信注入 | S-16后step15 |
| MOCK-CONTEXT-NONHIGH | 非高置信注入 | S-16后step12 |
| MOCK-NO-STRUCTURE | S-07无结构 | 进入S-08 |
| MOCK-LOW-STRUCTURE | S-09 low | S-11跳过；R-57等待或跳过 |
| MOCK-BACTERIA | bacteria | 执行S-06并解析flag |
| MOCK-MEMBRANE-SKIP | 膜且未确认 | WT+design_skipped |
| MOCK-MEMBRANE-CONFIRMED | 膜且确认 | 继续设计，后续结构步骤按规则降级 |
| MOCK-POOR-RESCUE-SUCCESS | poor且非膜 | 分支4成功后继续 |
| MOCK-POOR-RESCUE-FAIL | poor且非膜 | 分支4失败但按原图继续到EBB |
| MOCK-DESIGN-RETRY-48 | 首轮全淘汰、48轮通过 | 一次重试后继续 |
| MOCK-DESIGN-RETRY-64 | 首轮与48全淘汰、64通过 | 两次重试后继续 |
| MOCK-DESIGN-ALL-REJECTED | 三轮全淘汰 | WT+failure_report |
| MOCK-EPITOPE-STRUCTURAL-FAIL | L2/L3 structural失败 | epitope_violation硬排除 |
| MOCK-EPITOPE-PREDICTION-FAIL | L4失败 | soft_penalty降权 |
| MOCK-VARIANT-SAFETY-FAIL | 变体安全非PASS | safety_excluded硬排除 |
| MOCK-19B-SKIPPED | low或膜或空池 | 不执行变体FoldX |
| MOCK-SC10-WARNING | best.overall小于0.30 | WARNING并按待确认规则降级 |
| MOCK-MD-RUN | MD门控全部满足 | top3执行S-32 |
| MOCK-MD-SKIP | 任一MD条件不满足 | 直接阶段7 |
| MOCK-TOOL-TIMEOUT | 任一工具超时 | 标准TIMEOUT错误与重试策略 |
| MOCK-OUTPUT-MISSING | exit_code=0但无输出 | OUTPUT_MISSING，不得视为成功 |
| MOCK-OUTPUT-INVALID | 文件存在但解析失败 | OUTPUT_INVALID |

## 9. 历史工具手册与本项目映射

| 工具 | 历史参考版本 | T-01关系 | 本项目当前状态 | 接入结论 |
|---|---|---|---|---|
| ProteinMPNN | commit 8907e6671bfbfc92303b5f79c4b5e6ce47cdef57 | S-27核心工具 | NOT_DEPLOYED | 重新部署；补齐固定位置/允许残基/权限映射验收 |
| ThermoMPNN | commit 2b04fd370e399911b1fa5848112cc9013f084110 | S-31及S-27预测器 | NOT_DEPLOYED | 重新部署；先统一ddG符号和区域过滤 |
| MHCflurry | 2.2.1 | 可作为S-18 MHC-I辅助候选 | NOT_DEPLOYED | 不替代NetMHCpan/NetMHCIIpan；调用模式必须显式 |
| HADDOCK3 | 2026.7.0 | 不在T-01主路径 | NOT_DEPLOYED | 从T-01排除，另建对接工作流 |

## 10. Dify 调试与追踪契约

每个 Dify 工具节点必须展示或可检索：run_id、workflow_version、dify_dsl_version、node_id、step_id、attempt、scope、status、branch_taken、input_artifact_hashes、output_artifact_ids、quality_flags、duration_ms、tool_version、error.code。

调试模式：

| mode | 行为 |
|---|---|
| mock | 不调用真实科学工具；由scenario_id返回固定契约数据 |
| smoke | 真实工具的小规模连通性测试，不代表科学生产结果 |
| production | 使用正式参数、正式模型和完整验收后的工具 |

禁止将 smoke 结果标记为生产候选。Mock和Smoke结果必须在最终输出中显式标注 execution_mode。

## 11. 尚待业务/SOP确认的问题

这些问题在两份依据文档中没有完整定义，v0.1 不作推断：

1. epitope_policy 的枚举和详细语义。
2. regions_permissions 的精确输入 Schema、重叠 region 冲突优先级。
3. MHC I/MHC II 等位基因面板来源、默认面板和宿主映射规则。
4. host 与 expression_host 是否为两个独立字段。
5. context_scores 的高置信判定由谁生成及其完整 Schema。
6. core_map 四分量的正式字段名和数据类型。
7. E0-E4 与 1.0/0.8/0.5/0.2 的逐级权重映射。
8. mutation_burden 六维字段、档位和超档阈值。
9. objective_profile 的允许目标和权重。
10. SC-10低于0.30时选择WT交接或failure_report的精确条件。
11. ThermoMPNN/FoldX ΔΔG符号、单位和阈值的统一规则。
12. S-23中 IApred 的警告含义及工具可用性/授权方案。
13. S-44 Agent C 的接收接口、认证和交付确认契约。
14. S-42现有Pydantic Candidate模型的完整字段定义。
15. S-28、S-37、S-38 的 R-58 详细校验条款；算法图自检记录提及这些条款，但未展开具体字段与判定方式。

上述项目未确认前，可以 Mock，但不能宣称完整科学验收通过。

## 12. v0.1 完成标准

- [ ] 算法负责人确认所有步骤顺序与条件未偏离 T-01 v10。
- [ ] 业务负责人确认请求字段和待确认问题。
- [ ] 后端负责人确认 StepRequest、StepResult、ArtifactRef 和 ToolError 可实现。
- [ ] Dify负责人确认主工作流与八个子工作流的节点粒度。
- [ ] 运维负责人确认所有工具均从 NOT_DEPLOYED 开始管理。
- [ ] Mock MCP 可以覆盖第8节全部场景。
- [ ] Dify DSL、数据契约和Mock fixtures纳入Git版本管理。

本文评审通过后，进入第二步：实现统一 Mock MCP Server，并用相同工具名搭建 T01_Master_v10 与八个阶段子工作流。
