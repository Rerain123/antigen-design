# 2026-09-06 文档整理前的进度记录

本页保存整理前的状态与历次验证记录，仅供追溯。当前进度和下一项只见 [STATUS](STATUS.md)。
下文 READY、停止线和“下一步”均为当时口径；开发顺序已由 [用户新决定](sources/PHASE1_DELIVERY_SIMPLIFICATION_20260906.json)更新。

---
# T-01 当前状态

> 更新时间：2026-09-06  
> 状态基线：`PHASE1_18NODE / MOCK_M1-M4_COMPLETED / MOCK_V0.1_FROZEN / PH1-REAL-W1_READY / PRODUCTION_NOT_DEPLOYED`

## 当前任务入口

当前任务：[PH1-REAL-W1](phase1/PHASE1_REAL_W1_BACKLOG.md)

W1 专项 backlog 已建立，W1-00 文档准备完成；波次仍为 READY，甲方目标环境 G0 尚未执行。
主开发已推进 [本地结构解析与 R-58 专项](phase1/PHASE1_REAL_W1_R58_MAPPING.md)：开发机解析、候选生成与本地样本核验独立记录；
不能将本地开发事实算作完整 W1 G0/G1 或生产部署。
后续 [R-58/FreeSASA 边界补强](phase1/PHASE1_REAL_W1_R58_SASA_BOUNDARIES.md)已打通到按输入位置核对原始面积，
新增实体位置路径、转换身份检查和缺失/多链实测；映射仍为 unverified/unreliable。
先开展 W1-01 目标环境/资产登记和 W1-02 参考样本准备，再按依赖进入逐工具 G0。
已启动 [W1-01/02 登记](phase1/PHASE1_REAL_W1_PREPARATION.md)：开发环境与现有样本补充核对已记录；
目标 profile、完整工具样本集及科学验收依据尚未齐备，未将局部准备记为两项全部完成。
W1-06 的 [FreeSASA 本地原始验证](phase1/PHASE1_REAL_W1_FREESASA_G0.md)已在独立 Docker 中执行；
[参数、独立参考与 S-09 先行决定](phase1/PHASE1_REAL_W1_FREESASA_S09_DECISION.md)已形成，用户已明确先采用方案，
仍待算法负责人确认；G1 未放行。FreeSASA 数值差检查通过，但 1UBQ G76 归一化出域，按方案报错复核。
W1-05 已推进到 [DeepTMHMM 学术包禁网实测](phase1/PHASE1_REAL_W1_DEEPTMHMM_OFFLINE.md)：用户提供 Academic 1.0 包，
原版依赖镜像和模型 hash 已登记；3 次 CPU 禁网调用成功、1 次空输入拒绝，原始标签/区段核对通过。
专家未指定软件版本，要求实测锁定版本和参数；Academic 1.0 作为开发候选，不能等同网页应用 1.0.57。
甲方目标环境、G1 科学参考和生产适配器仍未放行；前序 SDK 负测保持独立历史证据。
W1-04 的 [AF3/ESMFold2 身份、资源与验证准备](phase1/PHASE1_REAL_W1_STRUCTURE_PREDICTION_G0.md)已形成：
官方来源、ESMFold2 五月 checkpoint、完整资产规模、实际 wrapper 默认参数和 5 组待执行输入已登记。
权重和本地 MSA 尚未提供；用户后续[确认服务器容量可满足两模型](sources/PHASE1_W1_SERVER_CAPACITY_20260905.json)，
开发继续在本机。具体服务器 profile、访问方式和资产仍待登记，模型均未执行。
W1-07 的 [工程契约与科学草案](phase1/PHASE1_REAL_W1_CONTRACT_DESIGN.md)已形成，包含模块依赖、
提交/控制/任务 Schema、8 种任务状态、受控文件引用及既有原始事实归并。
按用户采用的分模块方案，W1-08A 只评审通用工程，B/C 仍按工具/引擎完成自身 G0/G1；
[W1-09A 通用运行层](phase1/PHASE1_REAL_W1_RUNTIME_IMPLEMENTATION.md)已完成本地工程实现和进程级验证：
SQLite 任务/幂等、受控 Worker、进程树停止、重启对账、显式重试及文件发布均有实测证据。
[W1-08B1 本地结构与映射评审准备](phase1/PHASE1_REAL_W1_B1_REVIEW.md)已完成：输入支持域、请求/结果草案、
23 组文件实测和摄取/映射分别评审齐备；科学签收未授予，两个正式 Worker 仍关闭。
前序 B1 评审全量回归发现的 [Windows SQLite 临时文件误判](phase1/PHASE1_REAL_W1_RUNTIME_FILE_FIX.md)已修复并重新验收，原执行证据保留。
[B1 前置工程补强](phase1/PHASE1_REAL_W1_B1_ENGINEERING_REVIEW.md)的 E01–E04 已完成本机实现：
输入格式/MODEL/链预检、原始元数据出处、字符作者地址及消费者可表示性分别落为独立事实 Artifact；
40 组正式 CLI 案例符合预期，原探针和旧证据保持原字节。全量维护检查见本页当前验证。
[B1 → FreeSASA 消费者工程验证](phase1/PHASE1_REAL_W1_B1_FREESASA_REVIEW.md)的 F01–F04 已完成本机实现和实际禁网调用：
45 组正式案例全部符合预期，18 组完成原始面积回连、26 组准备拒绝、1 组未知半径计算前拒绝；
字符作者号的 native 路径与可表达地址的 PDB 路径分别核对，4 组等坐标面积对照精确一致。
按用户最新[顺序决定](sources/PHASE1_W1_B2_PRIORITY_20260906.json)，[W1-08B2 DeepTMHMM 评审准备](phase1/PHASE1_REAL_W1_B2_REVIEW_BACKLOG.md)
的 B2-01～04 材料已形成，[限定评审](phase1/PHASE1_REAL_W1_B2_REVIEW.md)包含输入/失败支持域、专用 Schema、标签/PB/null 与放行条件；
20 组人工契约案例及 11 条旧真实输出回读符合预期，四份公开标注独立于新解析器但未获科学留出集签收。
用户核对后已明确推进 [B2 原包边界与执行补证](phase1/PHASE1_REAL_W1_B2_BOUNDARIES.md)：
本机按原资源限制逐条实测短/长输入、真实 token 与切片、安全 ID/原产物，并验证原包失败和缺失/损坏副本。
本机 13 次原包调用已完成：10 份完整原始结果、2 次原包退出 1；含 `*` 的一次意外退出 0，被后置 token 回拼检查拒绝。
17 类真实产物故障副本均被拦截；短输入及 1020～1023 aa 的 token/切片、安全 ID 回连已有实际证据。
本次仍为 W1-08B2 补证，原包拒绝预期未满足项 B2-E01 已保留，W1-09B2 正式适配器未放行。
B1 适用科学 G1 独立按 [定点关闭条件](phase1/PHASE1_REAL_W1_B1_REVIEW.md#5-oi-015023-剩余项的定点关闭条件)跟进，不阻断 B2 准备；
FoldX/ProteinMPNN 等只保留接口准备，实际验证按所属后续波次开展。
W1-08A/A 实施只覆盖工程；W1-07 科学 payload 仍为草案，B/C、W1 总评与生产未放行。
任务入口建立或变化时只更新本节，各级导航链接到本页。

按用户最新 [取消分工决定](DECISIONS.md#取消同事工具分工)，取消向同事分配工具的安排，由主开发按原计划统一推进。
[原 FreeSASA 与 BepiPred 交接资料](phase1/handoffs/README.md)作为历史参考保留，未发送；发包、回传及后续分配退出当前排期。
首批 [工具公共接口 v0.1](../../工作流设计/02-数据契约/tool-interface-v0.1/README.md)的工程约定、Schema、人工示例与校验器已形成，
两包直接在 v0.1 内同步。此项是 W1-07 的公共准备子项；完整真实契约、科学适配器及 G1 仍未放行。

## 结论

当前只推进严格一期 18 节点。旧 `Master + P0-P7` Mock v0.1 已重新定性为
`FROZEN_LEGACY_REFERENCE`，只供未来完整 T-01 开发参考，不参与一期范围、排期、验收或发布。

已冻结工作包是[PH1-MOCK-M1 新一期 Mock 规格与验收基线](phase1/PHASE1_MOCK_V01_BACKLOG.md)。
[M1-01 来源—节点—S 步骤—工具—优先级矩阵](phase1/PHASE1_MOCK_M1_01_SOURCE_NODE_STEP_TOOL_PRIORITY_MATRIX.md)、
[M1-02 节点注册表与责任边界](phase1/PHASE1_MOCK_M1_02_NODE_REGISTRY.md)和
[M1-03 逐边控制流与状态图](phase1/PHASE1_MOCK_M1_03_CONTROL_FLOW_STATE_GRAPH.md)、
[M1-04 一期 Mock envelope 契约](phase1/PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md)和
[M1-05 确定性场景模型](phase1/PHASE1_MOCK_M1_05_DETERMINISTIC_SCENARIO_MODEL.md)、
[M1-06 命名、目录、生成、绑定与回归隔离](phase1/PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md)、
[M1-07 验收场景与机器断言](phase1/PHASE1_MOCK_M1_07_ACCEPTANCE_ASSERTIONS_FIXTURE_MANIFEST.md)和
[M1-08 一致性评审](phase1/PHASE1_MOCK_M1_08_CONSISTENCY_REVIEW.md)均已完成。M1 基线已放行
`PH1-MOCK-M2`；新一期 Mock v0.1 冻结前，不开始一期真实工具生产实现。

[PH1-MOCK-M2 实施 Backlog](phase1/PHASE1_MOCK_M2_BACKLOG.md)的 `M2-01～M2-09` 已全部完成，
[实现评审](phase1/PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md)以 `ZERO_BLOCKER / READY_FOR_M3`
放行。后端已执行 21 个案例、23 次提交和 4 份/16 步 checkpoint；M2 适用的 53 条 blocker 与
10 个覆盖门禁全部通过。

[PH1-MOCK-M3 实施 Backlog](phase1/PHASE1_MOCK_M3_BACKLOG.md)的 `M3-01～M3-10` 也已全部完成。
本地 Docker Dify 1.17.0（DSL 0.7.0）中的 main/debug 两个应用均已生成、绑定、导入、回读并
实际验收；每阶段 21 个案例/23 次提交、4 份/16 步 checkpoint、9 条适用全局断言、44 条焦点
断言和 10 个覆盖门全部 PASS，21 组 parity 及 global.016 全部 PASS。M3 blocker、科学执行、
科学公网请求、legacy 复用和 HiMat 后端访问均为 0。[M3 实现评审](phase1/PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md)
此前仅将 `PH1-MOCK-M4` 放行为 `READY`；该工作现已完成。

[PH1-MOCK-M4 Backlog](phase1/PHASE1_MOCK_M4_BACKLOG.md)的 `M4-01～M4-10` 已全部完成。正式
campaign `t01p1m-v01-reg-20260904-release-freeze-03` 在独立 main/debug runtime 上完成本地 Dify
全量回归：每角色 21 案例、23 提交、22 请求变体、4 次终态观察、27 个唯一 Dify run 和 4/16
checkpoint；双份 44 条焦点断言、12 条全局断言、10 门禁、21 parity 全部通过。M4 blocker、
科学执行、科学公网请求、legacy 复用、HiMat 访问和秘密发现均为 0。457 个资产已写入
[freeze manifest](../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_FREEZE_MANIFEST_v0.1.json)
并通过只读验证；一期 Mock v0.1 已冻结，只放行 `PH1-REAL-W1 READY`。

## 已完成

- 最新一期 18 节点图已确认为唯一一期业务拓扑。
- 节点 01 已按内网决定删除 S-07、RCSB PDB、AlphaFold DB 和联网回退，保留本地 AF3/ESMFold2。
- 旧 P0-P7 Mock、63 个 Mock 工具入口和 25 个确定性场景保持冻结且完成隔离定性。
- 根目录工程区已清出旧计划源码；旧完整 Mock 集中到 `legacy/full-t01-mock-v0.1/`，S07 的
  代码、脚本、测试、文档、取证及约 10.9 GiB 本地资产集中到 `legacy/s07/`。
- 原 `docs/archive/` 的 34 个旧 P0/P0-P7 计划、评审和历史文件已整体移入
  `legacy/project-history/`；`docs/` 现只保留当前一期控制面与运行入口。
- 新一期范围、架构、交付路线和 Mock M1 backlog 已建立。
- `PH1-MOCK-M1-01` 已完成：N01-N18 全覆盖，已归并 S/T 步骤、工具、本地数据边界、优先级、
  削减顺序和排除项；未写 Mock 代码或 Dify DSL。
- `PH1-MOCK-M1-02` 已完成：N01-N18 的稳定 ID、唯一机器键、规范显示名、语义输入输出责任和
  单一生产者边界已冻结；未提前定义完整 Schema、状态机或实现。
- `PH1-MOCK-M1-03` 已完成：`E001-E027` 逐边流程、九个节点状态、Gate/WT 路由、N12
  三轮上限、N16/N17 条件及汇合语义已冻结；OI-010/OI-021 的生产判据继续保持未决。
- `PH1-MOCK-M1-04` 已完成：请求、运行、节点、ArtifactRef、错误与审计通用 envelope 及
  Draft 2020-12 Schema 已冻结；1 个请求和 3 个终态示例可解析，完整科学 payload 未被提前定义。
- `PH1-MOCK-M1-05` 已完成：21 个确定性场景、18 项节点 Mock 输出责任和 378 个节点终态指令
  已冻结；Gate/N12/N15/N16/N17/N18 入口全部只复制 `SCENARIO_LITERAL`，无科学计算。
- `PH1-MOCK-M1-06` 已完成：统一根键 `t01_phase1_mock_v01`、2 个 Workflow、26 个编排工具、
  21 个 namespaced scenario_ref、request/run/envelope ID、计划目录、单一生成源、绑定链与新旧
  回归隔离已冻结；同步收紧 M1-04 Schema/示例与 M1-05 场景绑定，未创建 Mock 代码或 Dify DSL。
- `PH1-MOCK-M1-07` 已完成：21 个验收案例、23 次提交、22 个请求变体、4 份/16 步异步
  checkpoint、18 条全局断言、44 条焦点断言和 10 个覆盖门禁已冻结；payload 与 DSL 未物化。
- `PH1-MOCK-M1-08` 已完成：工程、算法边界与产品范围一致性评审通过，5 组 finding 已修复，
  M1 blocker 与无主缺口均为 0；基线固定为 `T01-PHASE1-MOCK-M1-BASELINE-v0.1`。
- `PH1-MOCK-M2-01～09` 已完成：严格规格 preflight 锁定 21 份 M1 来源；350 个 synthetic
  payload 已物化；21 场景/23 提交、378 节点终态、334 attempts、4/16 checkpoint、26-tool
  facade、九根 selector 和 28 operator 已实现；53 条 M2 blocker 与 10 个门禁均 PASS。
- M2 接管时发现的旧索引缺 `source_sha256`、第 351 个未声明支撑文件、结果 Schema/门禁缺失及
  selector/operator 证据不足均已闭环，详见[M2 实现评审](phase1/PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md)。
- `PH1-MOCK-M3-01～10` 已完成：目标事实固定为 Dify 1.17.0/DSL 0.7.0；薄 MCP transport 精确
  暴露 26 tools；单一 generator 生成 main/debug；`local_dify_1_17` binding/bound 哈希链闭合；
  两应用均以 59 个 Dify 节点、79 条物理边回读 E001-E027，导入 warning 为 0。
- M3 main/debug 各完成 21 场景/23 canonical submission、4/16 checkpoint、9+44 条适用断言和
  10 个覆盖门；21 组规范化 parity 与 global.016 全部通过，M3 机器 blocker 为 0。
- Dify workflow run ID 与 canonical request/run/envelope ID 已分离记录；M3 结果仍统一标记
  `MOCK_DATA`、`scientific_compute=false` 和 `NOT_DEPLOYED`。
- `PH1-MOCK-M4-01～10` 已完成：草稿审计、输入与派生链复算、精确 app ID 重导入/回读、
  main/debug 全量执行、断言/parity、隔离负测、四分区与冻结 manifest 全部 PASS。
- 正式 M4 result 为 `PASS / blocker=0`；四分区分别为 Markdown 115、当前一期 185、旧 Mock 74、
  S07 41；457 个冻结资产的路径、字节和 SHA-256 可只读复算。
- `T01-PHASE1-MOCK-v0.1` 已置为 `FROZEN`；[M4 实现与冻结评审](phase1/PHASE1_MOCK_M4_IMPLEMENTATION_REVIEW.md)
  的工程、算法边界、产品、Dify 和发布五项结论均为 PASS。

- W1 专项 backlog 已形成，包含 W1-00～13、G0–G6、八项前置依赖、来源归并及验收证据要求；
  OI-015/023 已按 W1 适用子项收窄，新登记 OI-024 的 S-09 冲突和 OI-025 的 CamSol 参数准备。
  后续数据/许可、N18 WT 子契约和排序接口准备已明确主责与最迟时点；此项仅为文档完成。
- 两份独立工具交接 ZIP 已形成：开始说明、详细实现要求、验收清单、教学示例、回传模板和专家原件副本齐备；
  所有示例均标注用途，真实样本、模型、适配器及目标执行证据未伪造为已交付。
- 首批工具公共接口工程部分已统一：请求/结果 Schema、运行/可消费/复核状态、文件与 hash、
  错误码/退出码、版本追踪、离线校验入口；两包共用同一来源。R-58 和 OI-026 的科学细节仍待适用评审。

- 本地结构解析与 R-58 工程实现已形成：独立源码/依赖、严格 PDB/mmCIF 解析、全结构清单、逐位候选映射、
  便携格式/身份校验及实际坐标重解析核验。历史样本经过来源/hash 核对后独立复制，无 S07 代码或查询回流。
  本轮生成的映射仅为 unverified/unreliable，未把候选方法当成已批准科学比对器。
- W1-01/02 局部准备已落盘：本地开发 profile、工具资产待核实项、G0 输入分支与 G1 参考要求；
  对 1UBQ 新增实体序列—编号表—坐标的 76 位对照，并登记水分子、占有率及原子上下文。
  当时曾延后同事交接；后续已取消分工，现按本页当前任务入口执行。
- FreeSASA 开发候选环境已建立：独立 Docker/Python 模块 2.2.1，原始科学运行禁网。
  1UBQ 转 PDB 后返回 602 个原子、76 个残基的绝对 SASA，重复结果一致；原生和桥接路径均通过人工编号 42/42A 身份核对。
  mmCIF 原生入口错误、非法 PDB 及旧人工坐标 NaN 均已记录；没有生成项目 RSA 或签发 verified 映射。
- S-09 初次核对形成 27 个来源派生案例和 6 个待裁决案例，五份专家来源有 hash；清单保留当时状态，
  后续六项采用状态见下条及用户记录，案例未记为已执行。
- FreeSASA 后续数值专项完成：记录官方发表值、Biopython 独立积分算法与四组解析几何参考，执行参数扫描及参考加密。
  ProtOr/1.4 Å/200 slices/1 thread 的候选参数、显式结构上下文及数值容差方案已落盘。
- 用户已先行采用 FreeSASA 方案和 S-09 六项定点规则，[采用记录](sources/PHASE1_W1_FREESASA_S09_ADOPTION_20260905.json)
  保留原话、日期、适用范围和方案 hash；算法确认仍待完成。OI-024 从无采用决定收敛为六项具名算法确认。
- 1UBQ A:76 GLY 的原始归一化比值约 1.413，两套算法均出现；已登记 OI-027，先行按 OUTPUT_INVALID/不可消费/强制复核处理，未截断为 1。
- W1-05 开发准备形成独立证据：官方 pybiolib 1.4.457 在禁网容器中明确拒绝 --local，未启动预测任务；
  核验 3,576 条官方标注、3,574 条历史四行输出，备好 4 条官方 FASTA 和 4 条标注覆盖案例。
  用户“学术自用”已留来源记录；本地包获取方式与原件安装描述的差异归入 D02/D04，不修改科学原件。
- W1-05 后续收到用户学术包，41 个包文件及 8 个模型资产已登记，原代码和权重完整性保持一致。
  Academic 1.0 原始 CPU 推理实际禁网完成，9 条覆盖输入包含四标签及 2 条 P/B 输出；另有短输入重复和人工 X 输入成功。
  三行、区段、计数、概率文件与输入对应核对通过；空输入加载前拒绝。没有把公开标注用作独立准确率验收。
- R-58/FreeSASA 边界补强形成 12 个声明案例：完整实体序列与 label 位置核对解决重复末端的缺失定位；
  6 次实际 FreeSASA 计算验证负编号、42/42A、null 位置和多链上下文，2 次边界拒绝拦截 token 冲突与未知半径。
  派生 PDB 和工具内原子均检查身份与坐标；编号变化后的逐位面积完全相同，多目标链保持不可对齐。
  公共格式继续在 v0.1 内补充方法标识，没有生成正常 RSA 或批准映射。
- W1-04 开发准备完成官方版本追溯、许可来源与资产清单：AF3 源码候选固定，ESMFold2 标准/Fast 的五月权重元数据可核对，
  软件包、checkpoint 和嵌套 ESMC/CCD 依赖分别登记。没有下载或执行模型。
  本机限定范围硬件/环境盘点及 Docker GPU 可见性检查完成；备好 76 aa 官方输入、AF3 JSON 和人工长度边界，5 组计划均为 DECLARED_NOT_RUN。
- W1-07 工程设计与科学 payload 草案已落盘：任务/尝试/文件身份、提交/查询/取消/重试、8 状态及停止确认、恢复对账、
  服务端资格与证据隔离、旧工具协议桥接均有明确约定；登记 15 个运行层和 8 个科学/集成待执行案例。
  原 W1-08/09 拆为 A/B/C 分项并保留总评与集成；设计时点未实现运行层，后续 A 实测见下条。
- W1-09A A01–A06 本地工程实现完成：独立 SQLite 运行层、统一 Python/CLI 接口、固定工程 Worker、Windows 进程树控制、
  取消/超时确认、恢复对账、显式 retry、不可变文件及 hash 校验；51 项运行测试覆盖 RT01–RT15，5 组 CLI 场景实际执行。
  AF3/ESMFold2 及其他科学入口在启动前拒绝，全部结果为 ENGINEERING_FIXTURE 且不可供科研流程消费。
- W1-08B1 的 B1-01～04 评审准备完成：22 份专家原件检索与后续决定归并、两工具请求/结果草案及人工配对示例、
  23 组预先声明的本地文件实测和限定评审。OI-015/023 已收敛为 7 个具名子项及关闭材料；两个工具的完整 G1 仍未通过。
  摄取 AUTO、设计链、MODEL、partial/null、iCode、替换/插入、元数据和缺原子口径分别记录；没有修改原件、既有探针或生产注册。
- B1 前置 E01–E04 工程补强完成：新增独立输入事实探针，保留原请求/结构字节，分别发布预检、原始元数据和原始地址三份事实 Artifact。
  40 组正式 CLI 案例逐项符合预期，涵盖两份已有真实文件及人工格式/选择/元数据/地址边界；字符 43A 与 43+iCode A 分开记录，
  未知插入码、前导零、长链与消费者碰撞明确阻断相应字段投影；来源、缺原子比例、pLDDT 和科学映射资格仍未评估。
  [工程评审及接口差异](phase1/PHASE1_REAL_W1_B1_ENGINEERING_REVIEW.md)与 [独立证据](../../discovery/t01-phase1-real/w1/b1-engineering-20260905/README.md)可复核。
- B1 → FreeSASA 的 F01–F04 开发消费者完成：原始事实配对与显式 MODEL/链/路径形成绑定，PDB/native 分别核对实际原子身份、坐标和 ProtOr 半径，面积回连完整原始地址。
  正式批次 45 组案例全部符合预期，4 组等坐标路径对照精确一致；字符作者号不重编号，碰撞和未批准上下文明确拒绝。
  原始 1UBQ 的未知 iCode 与旧派生 PDB 的非完整占有率仍未获批；[独立证据](../../discovery/t01-phase1-real/w1/b1-freesasa-consumer-20260906-r02/README.md)保留首轮夹具精度问题及完整复跑结果。
- W1-08B2 评审准备 B2-01～04 完成材料构造：单序列、安全 ID、精确绑定、三行与区段、P/B/null/失败及下游责任均有独立草案和负测。
  既有 11 条输出回读为 8 条四标签未批准结果、2 条 P/B 空值、1 条 X 输入复核；没有新模型执行。
  四条公开标注保留原始来源行/hash 和训练独立性未确立状态；[B2 评审](phase1/PHASE1_REAL_W1_B2_REVIEW.md)将正式适配器要求分为四项 G1 签收与后续 G2–G6。

## 尚未完成

- 冻结 M1-07 execution matrix 保持不可改写，其中 M2/M3/M4 的规格时点声明仍是
  `DECLARED_NOT_RUN`；M2/M3/M4 的实际 PASS 只记录在各自新增机器结果和实现评审中。
- 一期真实科学工具的生产部署、生产适配器、离线发布包和真实 Workflow 均为 `NOT_DEPLOYED`；FreeSASA、DeepTMHMM 已有独立开发镜像和本地原始运行证据。
- W1 目标环境、各工具适用资产与许可、真实样本及实际执行/科学验收人仍须逐项补齐；
  本地解析、FreeSASA 与 DeepTMHMM 的已知开发事实保留，不能把这些已具备项重新写成未知。
  甲方目标环境实测、科学验收及 W1 G1 放行仍无证据。
- W1-07 的逐工具科学 payload 尚未冻结；通用运行层仅验证 Windows 本地 Python/CLI，服务器 Worker 和认证传输尚未接入。
  A 工程通过不代表 B/C 科学放行或 W1 总评通过。
- B1 已有可复核草案、输入选择预检、原始元数据出处及字符型作者地址的无损事实；完整摄取仍缺生产输入支持域、来源判定与缺原子比例。
  映射仍缺比对/构象选择、真实科学验收及消费者资格；B1-E01 已有 FreeSASA 开发消费子域证据，其余消费者和科学资格继续按具体工具完成。
- AF3/ESMFold2 的模型资产和本地 MSA 数据尚未提供；服务器容量已获用户确认，具体配置、访问与实际运行仍待验证。
  本机为 12 GB 级 GPU，宿主约 31.2 GiB RAM、Docker 约 15.2 GiB；AF3 完整数据缺充足内存/磁盘余量，
  ESMFold2 默认参数同时驻留的估计已超过总显存。实际框架兼容、两引擎原始输出和目标禁网复现尚未验证；W1-04 未完成。
- 用户确认暂无甲方真实测试用例；已从历史只读复用 1UBQ、5XZC 结构和独立序列，来源/hash 核对后进入当前测试目录。
  这些仅为本地开发参考；重复/替换/插入、非整数作者编号、模型/构象选择及后续工具消费仍需收敛，未签发 verified 映射。
  重复区的完整实体位置路径已有开发证据；一般替换/插入、非整数作者编号的无损消费、altloc 与完整性模板仍未全部解决。
- OI-015 的 W1 映射子项、OI-023 的生产输入子项、OI-024 先行规则的算法确认及 OI-027 出域科学核验须在 W1 适用 G1 前闭合；
  OI-023 的 Mock 请求与追踪部分保持关闭。
- FreeSASA 目前只有一份适用完整坐标的真实参考输入；还需留出、多链/partial/未知原子及边界样本。
  多链/partial/未知原子已有人工边界运行，仍缺独立真实留出与对应科学参考；人工派生不增加真实参考样本数。
  用户先行采用参数和候选容差，不等于科学签收；1UBQ 的正常项目 RSA 验收仍未通过。
- DeepTMHMM 本地包、模型资产、开发候选版本/参数和 CPU 禁网输出已具备；仍缺甲方目标环境复现、独立科学参考、
  G1 签收与生产输入/下游守卫实现。本机 1020～1023 aa 切片已有证据；GPU、更长序列、并发/恢复、实际超时/OOM 和目标离线安装未验证，不能将开发实测记为 W1-05 全部完成。
  B2 已有专用草案和回读材料，剩余明确为 B2-G1-INPUT/REFERENCE/RUNTIME/CONTRACT；当前独立科学留出签收为 0，正式适配器未放行。
- OI-004、OI-013/014、OI-020～022、OI-025 等按 [开放项](OPEN_ITEMS.md)的对应节点时点收敛；
  后续准备项不整体阻断 W1 G0。
- BepiPred 新登记 OI-026：原始分数列/平滑、Top20% 消费及峰合并细节待定点确认；
  不阻断原工具 G0，适用 G1 前须闭合。BepiPred 按 W2 主线推进；原交接验收清单仅作参考。

## 下一步

**下一项是按 [B2 定点放行条件](phase1/PHASE1_REAL_W1_B2_REVIEW.md#6-正式适配器的放行要求)收敛输入/参考/目标运行/契约签收材料。**
[W1-08B2 准备](phase1/PHASE1_REAL_W1_B2_REVIEW_BACKLOG.md)及本机原包边界补证已形成：短长/token、安全 ID、执行失败和损坏产物均有独立证据；
后续将 B2-E01 的 `*`→`<unk>` 事实纳入输入域与契约签收，保持预检和 token 回拼守卫，继续独立参考接收及具名目标复现；
算法侧确认输入域、训练独立性与科学指标，部署侧补目标复现；B2 自身适用 G0/G1 后才放行 W1-09B2 正式适配器。
FoldX/ProteinMPNN 的接口和资产可准备，实际验证/实现按 W5–W7 等所属波次及门禁开展，不列为 W1 当前执行项。
输入事实 E01–E04 与 [FreeSASA 消费者 F01–F04](phase1/PHASE1_REAL_W1_B1_FREESASA_REVIEW.md)已交接；
B1 的比对接受域、构象、映射签收、来源/缺原子规则及 FreeSASA 复杂上下文继续独立跟进，不阻断序列级 B2。
完整 W1-09B1 和 W1-09B2 分别要求自身适用 G0/G1，不互相借用工程通过或科学资格。

主开发按 [W1-01/02 环境与样本登记](phase1/PHASE1_REAL_W1_PREPARATION.md)核实目标 profile、工具资产、
实际执行人与验收人；继续利用已有本地解析和样本证据，补充 OI-015/023/024 的定点案例。
按 [先行决定](phase1/PHASE1_REAL_W1_FREESASA_S09_DECISION.md)继续准备，用户向算法负责人确认参数/上下文、
候选容差与 S-09 六项规则；工程侧补足适用样本、目标环境及 OI-015/023 输入证据。
OI-027 已有报错复核处置，算法需核验出域原因及正常科学消费口径；不通过放宽误差预算或截断 RSA 解决。
R-58 的候选映射经适用评审后才能登记 verified；原始探针不直接改作生产适配器。

DeepTMHMM 依据 [本地实测结果](phase1/PHASE1_REAL_W1_DEEPTMHMM_OFFLINE.md)准备目标复现与科学签收，
W1-07 已列清安全 ID、四标签/PB、空值及下游守卫，B2 实施前完成自身规则/样本与资格评审；不重问已明确的学术用途。
W1-04 按 [结构预测准备结论](phase1/PHASE1_REAL_W1_STRUCTURE_PREDICTION_G0.md#6-已准备的验证与后续顺序)
补齐具名服务器、AF3 使用适用性及全部本地资产后，再做 76 aa 禁网原始试跑；不在当前配置上启动完整模型/数据库安装。
已有工具按 W1-08B 分别评审，AF3/ESMFold2 按 W1-08C 分别评审；缺口仅约束相关模块。
AF3/ESMFold2 的源码/教程输出不当真实产物，科学契约冻结仍需适用 G0/G1 事实。

各工具的环境和样本就绪后，依次开展适用的本地解析、AlphaFold3/ESMFold2、DeepTMHMM、FreeSASA G0，
并核对 S-09 规则。某个工具的资源未就绪时继续其他可独立完成的 W1 工作。
W1-08A/B/C 分别放行 W1-09A/B/C；完整 W1 总评、集成与 W1-10～13 仍要求全部适用能力齐备。
部分工程通过不替代科学验收，全部工具按原波次和适用门禁统一推进。

## 当前停止线

1. `T01-PHASE1-MOCK-v0.1` 已冻结；Dify DSL 只能由当前单一 generator 重建，不得手改模板、bound
   或冻结 manifest 中登记的任何资产。
2. `PH1-REAL-W1` 仅为 `READY`；未完成各项真实门禁前不得声明真实能力或生产部署。
3. Mock、smoke、discovery 或工程评审 PASS 均不等于科学验收或生产部署。
4. 未经用户明确授权，不修改旧 P0-P7 Mock 的行为、模板或 25 场景基线。
5. 一期计划不得重新使用 P0-P7 作为阶段、任务编号或完成度。

## 当前验证

- M1-08 全链机器审计：`PASS`；18 节点、27 边、9 状态、4 个 envelope 示例、21 场景、2 个
  Workflow、26 个工具、23 次提交、22 个请求变体、378 个节点指令、334 个 attempts、326/8 个
  fixture key、4/16 checkpoint、18+44 条断言与 10 个门禁全部重算闭合。
- fixture 闭集：`CHECK_PASS`，2 个输入、22 个请求、326 个 attempt payload，共 350 个文件；
  重复构建物化索引 SHA-256 一致。
- M2 机器验收：`PASS`，21 案例、23 提交、16 checkpoint、53 blocker、10 覆盖门，failure 为 0。
- M3 机器验收：`PASS`；main/debug 各 21 案例、23 提交、16 checkpoint、9+44 条断言与 10 覆盖门；
  21 组 parity 全部通过，科学执行、科学公网请求、legacy 复用、HiMat 访问和 blocker 均为 0。
- M4 机器验收：`PASS`；正式 campaign 每角色 21 案例、23 提交、22 请求变体、4 次 finalization、
  27 个 Dify run、4/16 checkpoint、44 focus；12 global、10 coverage、21 parity 均 PASS，blocker 为 0。
- Mock v0.1 冻结校验：`PASS`；457 个资产，freeze manifest 可只读复算。
- 2026-09-05 文档整理阶段验证：文档检查 `PASS`（115 个 Markdown 文件）；当前根测试 `PASS`，207 项。
- 其中 [文档检查器测试](../../tests/test_docs.py) 23 项通过，覆盖关键导航、当前任务、锚点和过时入口负测；
  已精简 AGENTS.md 与各级 README，验证选择统一见 [运行手册](../development/RUNBOOK.md)。
- 文档整理阶段专家包 22 个文件与修改前哈希一致；M4 冻结 campaign 中的 185 项根测试数继续保留为历史证据，
  不以当前维护测试数改写冻结资产。
- 冻结旧完整 Mock：`PASS`，74 项；S07 备用包：`PASS`，41 项。
- 2026-09-05 W1 专项计划验证：文档检查 `PASS`（116 个 Markdown 文件），文档检查器测试 23 项通过；
  M4 只读 verify `PASS`，457 个冻结资产保持一致。本次仅新增/同步八份计划与入口文档，未执行 G0 或生产部署。
- 2026-09-05 首批同事交接包验证：文档检查 `PASS`（129 个 Markdown 文件）、文档检查器测试 23 项通过；
  两个 ZIP 的文件清单、SHA-256、独立本地链接、JSON 及教学数据一致性检查通过，原件副本与来源相符；
  专家包 22 个原文件保持修改前 hash，457 项 Mock 冻结资产只读 verify 通过。
  [打包验证记录](phase1/handoffs/releases/PACKAGE_VERIFICATION.json)可追溯；未执行 FreeSASA/BepiPred 或科学验收。
- 2026-09-05 公共工具接口维护验证：文档检查 `PASS`（135 个 Markdown 文件）；当前根测试
  271 项通过、1 项跳过，其中新增接口/包测试 64 项通过、1 项因 Windows 账户不能创建符号链接而跳过。
  路径穿越、重复身份、非法状态、请求/产物指纹、数组与区间及独立解压校验均有测试。
  两包共同包含 8 组人工请求/结果示例；ZIP、接口副本与来源字节/哈希一致，重复构建结果一致。
  用户要求直接更新 v0.1，现行 [发布清单](phase1/handoffs/releases/RELEASES.json)与
  [打包验证记录](phase1/handoffs/releases/PACKAGE_VERIFICATION.json)已重算为本次内容，不另留旧 ZIP。
  专家包 22 个原文件与本次修改前 hash 一致，M4 只读 verify 通过、457 个资产保持冻结；
  未跨历史分区改动，本轮未重跑旧 Mock/S07，前述历史结果不作为本轮执行记录。
  真实工具、科学验收与生产部署均未执行，W1 及 G0/G1 状态保持原结论。
- 当前根、旧 Mock 和 S07 必须继续分区报告，不把测试数相加后当作一期功能或生产验收。
- 2026-09-05 R-58 本地结构专项验证：文档检查 `PASS`（142 个 Markdown 文件）；当前根测试
  307 项通过、1 项因 Windows 符号链接权限跳过，其中 R-58 新增 36 项通过。
  旧完整 Mock 单独回归 74 项通过，S07 单独回归 41 项通过。
  [本地探测记录](../../discovery/t01-phase1-real/w1/r58-local-20260905/campaign_result.json)包含 2 组历史真实文件
  与 2 组人工格式输入，全部完成严格解析与实际文件重解析核对；9 项程序/输入清单 hash 与 16 项运行产物 hash 复核一致。
  1UBQ 的 A 链形成 76 位完整候选，仍为 unverified；5XZC 的 B/C/D/E 链与位置存在多个候选且仅含 Cα，
  保持 unreliable，不产生自动交接结果。测试覆盖插入码、null、作者/label 编号、多链/MODEL、altloc、
  非标准残基、损坏文件、篡改编号/指纹与输出目录重复。
  FreeSASA 包新增符合公共格式的人工结构/映射配对，公共 --check-files 可核对映射内容与请求；
  两份 v0.1 ZIP 已同步，包内链接、Schema、源码副本与 hash 检查通过。
  专家原件 22 项与本次修改前一致，历史来源 7 项保持原字节，Mock freeze verify 457 项通过。
  [本次维护检查记录](../../discovery/t01-phase1-real/w1/r58-local-20260905/maintenance_verification.json)列明各分区范围；
  未签发 verified 映射，甲方环境验收、科学验收及生产放行仍未执行。
- 2026-09-05 主线恢复与 W1-01/02 准备验证：文档检查 `PASS`（144 个 Markdown 文件）；
  [新批次核验](../../discovery/t01-phase1-real/w1/w1-preparation-20260905/verification.json)确认 8 项输入/程序与
  2 项采集产物 hash 一致，两个样本的原子总数与前批解析器一致。交接包只读检查通过，未重新打包；
  Mock freeze verify 457 项通过。此次仅调整计划、登记事实及新增批次采集程序，未改生产源码/契约，未重跑全量或历史测试。
  目标环境 G0、科学 G1 和生产部署未执行；W1-01/02 保持部分准备，波次仍为 READY。
- 2026-09-05 FreeSASA/S-09 专项维护验证：文档检查 `PASS`（147 个 Markdown 文件），当前根测试
  312 项通过、1 项因 Windows 符号链接权限跳过；新增证据与转换回归 5 项通过。
  [本批核验](../../discovery/t01-phase1-real/w1/freesasa-s09-20260905/maintenance_verification.json)复核首轮 48 项文件及
  补充 9 项文件 hash、原始重复结果、残基地址、插入码和 S-09 未决状态。
  两份交接 ZIP 只读检查通过且未改包，专家原件 22 项保持本次修改前 hash，Mock freeze verify 457 项通过。
  本轮没有跨历史分区变更，未重跑旧 Mock/S07；历史结果不作为本轮执行记录。
  科学运行仅发生在独立本地 FreeSASA 探测容器，未执行 S-09 生产判定、科学验收或甲方目标环境放行。
- 2026-09-05 FreeSASA 独立参考与规则采用维护验证：文档检查 `PASS`（149 个 Markdown 文件）；当前根测试
  318 项通过、1 项因 Windows 符号链接权限跳过，其中新增数值证据/科学边界回归 6 项通过。
  [本轮检查](../../discovery/t01-phase1-real/w1/freesasa-reference-20260905/maintenance_verification.json)记录命令和结果；
  新批 30 项程序/输入/产物/草案 hash 与 22 项专家原件一致，前批 48+9 项证据仍可只读复算。
  两份交接包只读核验通过且未改包；Mock freeze verify 457 项通过。本轮未跨历史分区，未重跑旧 Mock/S07。
  独立参考收敛、数值误差预算及解析几何检查通过；G76 出域使正常项目 RSA 仍不可接受。
  用户先行采用记录的 2 份来源 hash 与 6 个案例 ID 核验通过；算法确认仍待补齐，未执行 S-09 生产判定或甲方目标验收。
- 2026-09-05 DeepTMHMM 准备维护验证：文档检查 `PASS`（151 个 Markdown 文件）；当前根测试
  338 项通过、1 项跳过，含新增原始格式/证据回归 20 项。[本轮检查记录](phase1/PHASE1_REAL_W1_DEEPTMHMM_VERIFICATION.json)
  区分 SDK 预期拒绝、公开资料审核和未执行的模型推理；本批 169 项文件 hash 通过，22 份专家原件未变，
  Mock 冻结 457 项只读校验通过。本轮未跨历史分区，未重跑旧 Mock/S07；未提交外部申请或预测任务。
- 2026-09-05 R-58/FreeSASA 边界维护验证：当前根测试 381 项通过、1 项跳过，含新增边界回归 43 项；
  文档检查 `PASS`（154 个 Markdown 文件）。[本轮检查记录](phase1/PHASE1_REAL_W1_R58_SASA_VERIFICATION.json)
  记录 6 次真实面积计算、2 次工具边界拒绝及验证范围；新批 212 项文件、22 份专家原件和原 R-58 的 16 项输出只读校验通过。
  两份备用同事包已在 v0.1 内同步并重打包，尚未发送；Mock 冻结 457 项校验通过。
  本轮未跨历史实现分区，未重跑旧 Mock/S07；映射批准、甲方目标验收及科学 G1 仍未执行。
- 2026-09-05 DeepTMHMM 学术包实测维护验证：当前根测试 410 项通过、1 项跳过，含新增原始证据测试 28 项和导航检查回归 1 项；
  文档检查通过（156 个 Markdown 文件）。[本轮验证记录](phase1/PHASE1_REAL_W1_DEEPTMHMM_ACADEMIC_VERIFICATION.json)
  记录旧 Mock 74 项、S07 41 项回归全部通过；新批 122 项文件、41 个包资产及 22 份专家原件 hash 通过。
  Mock 冻结 457 项、fixture/DSL/binding 和两份交接包只读检查通过；真实推理为 EXECUTED_OFFLINE_CPU，生产仍未放行。
- 2026-09-05 AF3/ESMFold2 准备维护验证：当前根测试 428 项通过、1 项跳过，含新增准备证据测试 18 项；
  文档检查通过（158 个 Markdown 文件）。[本轮验证记录](phase1/PHASE1_REAL_W1_STRUCTURE_PREDICTION_VERIFICATION.json)
  区分公开资料、GPU 可见性和模型执行；84 个新批文件、58 份成功获取的官方资料、22 份专家原件及 457 个 Mock 冻结资产核验通过。
  本轮未跨历史实现分区或进行阶段冻结，未重跑旧 Mock/S07；没有下载权重/数据库或执行 AF3/ESMFold2，5 组验证计划仍未运行。
- 2026-09-05 取消工具分工维护验证：文档检查通过（158 个 Markdown 文件），两份历史工具包只读核验通过，
  ZIP、接口副本与来源 hash 保持一致；未重打包或发送。本轮仅同步分工决定、计划与导航，未改实现或运行科学工具，未重跑测试。
- 2026-09-05 W1-07 分模块契约维护验证：当前根测试 472 项通过、1 项跳过，含新增契约负测 44 项；
  文档检查通过（161 个 Markdown 文件）。[限定评审与本轮检查](phase1/PHASE1_REAL_W1_CONTRACT_REVIEW.json)
  记录 32 份来源（含 22 份专家原件）、8 份 job 示例、1 份提交与 4 类控制请求的静态校验通过；
  15 个运行层与 8 个科学/集成案例仍为 DECLARED_NOT_RUN。457 个 Mock 冻结资产及两份历史 ZIP 只读核验通过。
  W1-08A 仅放行通用工程实现，未启动 Worker/模型/Dify，未跨历史实现分区或进行阶段冻结，未重跑旧 Mock/S07。
- 全部工具的生产资格及完整 W1 发布门禁保持关闭；通用工程开发放行与生产放行分开记录。

- 2026-09-05 W1-09A 实施维护验证：当前根测试 525 项通过、1 项因 Windows 符号链接权限跳过；新增运行层测试 51 项、证据检查 2 项。
  [本轮检查记录](phase1/PHASE1_REAL_W1_RUNTIME_VERIFICATION.json)记录 15 类运行验收、16 次 CLI 调用和 5 组终态场景，
  16 项源码/测试/来源与 62 项输出 hash 一致；文档检查通过（164 个 Markdown 文件）。
  W1-07 的 32 份来源（含 22 份专家原件）、457 个 Mock 冻结资产及两份历史 ZIP 只读核验通过。
  本轮只改当前工程分区且未进行阶段冻结，未重跑旧 Mock/S07；没有运行科学模型、远程服务器或真实 Dify。
  W1-09A 工程验收适用 Windows 本地；服务器容量已登记为用户确认，具体配置/模型资产/目标验收仍待补齐。

- 2026-09-05 W1-08B1 评审准备维护验证：当前根测试 566 项通过、1 项因既有 Windows 符号链接权限跳过；
  新增 B1 契约/证据测试 37 项、运行层修复回归 4 项。[本轮检查记录](phase1/PHASE1_REAL_W1_B1_VERIFICATION.json)
  记录 23 组重新解析与候选核对、2 组请求/结果配对、14 项源文件和 93 项输出 hash；35 份依据含 22 份专家原件。
  首次全量回归的 2 项运行层失败已定位为 SQLite WAL/SHM 消失时零链接计数误判，修复后 51 项运行验收、15 类案例和 5 组 CLI 场景通过。
  原运行证据按 16 份修改前源码快照复验；当前修复代码使用独立新批次验收，原失败和前后源码均保留。
  文档检查通过（170 个 Markdown 文件），457 个 Mock 冻结资产及两份历史 ZIP 只读核验通过。
  本轮只改当前工程分区且未进行阶段冻结，未重跑旧 Mock/S07；科学签收、正式 B1 Worker、服务器和生产均未放行。

- 2026-09-06 B1 前置工程补强验证：当前根测试 638 项通过、1 项因既有 Windows 符号链接权限跳过，其中新增输入事实回归 72 项。
  [本轮检查记录](phase1/PHASE1_REAL_W1_B1_ENGINEERING_VERIFICATION.json)记录 40 组实际 CLI 案例：19 组事实记录、21 组按预期拒绝，全部通过。
  378 项新批文件、315 项受保护原件/旧证据/源码（含 22 份专家原件）只读 hash 与事实重解析通过；原 B1 的 23 组案例/2 组配对仍通过。
  R-58 边界旧证据、原运行层及当前修复批次均只读核验通过；457 个 Mock 冻结资产和两份历史 ZIP 未变。
  首轮全量检查发现新评审链接的验证记录尚未落盘，补齐后文档检查通过（173 个 Markdown 文件），完整根测试重跑通过，初次失败保留在独立维护证据。
  本轮只改当前工程分区且未进行阶段冻结，未重跑旧 Mock/S07；科学签收、正式 B1 Worker、目标服务器及生产均未放行。

- 2026-09-06 B1 → FreeSASA 消费者验证：当前根测试 723 项通过、1 项因既有 Windows 符号链接权限跳过，其中新增消费者回归 85 项全部通过。
  [本轮检查记录](phase1/PHASE1_REAL_W1_B1_FREESASA_VERIFICATION.json)记录 45 组正式案例：18 组原始面积成功、26 组准备拒绝、1 组分类器未知半径计算前拒绝；4 组路径精确对照和成功案例乱序回连全部通过。
  固定 FreeSASA 2.2.1 镜像实际禁网执行，工具 stderr 为空；965 个正式批次文件、1,616 个保护文件（含 22 份专家原件与 970 个首轮试验文件）只读校验通过。
  原 B1 的 40 组输入事实、23 组评审案例/2 组配对、R-58 原始证据、两版运行层、457 个 Mock 冻结资产及两份历史工具包均核验通过；文档检查通过（177 个 Markdown 文件）。
  首轮夹具长小数造成两路径坐标不同的比较失败已保留，r02 仅修正人工坐标字面量后独立复跑；未放宽消费规则或科学容差。
  本轮只改当前工程分区且未进行阶段冻结，未重跑旧 Mock/S07；科学 G1、正式 Worker、正常 RSA 与生产资格均未放行。

- 2026-09-06 W1-08B2 评审准备验证：当前根测试 802 项通过、1 项因既有 Windows 符号链接权限跳过；新增 B2 回归 71 项、快照导航回归 8 项均通过，文档检查器共 32 项通过。
  [本轮检查记录](phase1/PHASE1_REAL_W1_B2_VERIFICATION.json)记录 20 组人工契约案例、11 条既有原始输出回读和四份公开标注来源核对；独立科学留出集已签收数量仍为 0。
  新批 86 项文件、329 项保护文件（含 22 份专家原件）、旧 Academic 122 项证据和 41 个本地包资产均只读核验通过；本轮新增模型执行为 0。
  首轮全量检查发现封存 README 副本的相对链接被当作现行导航；限定清单与字节/hash 识别修复后文档检查通过（181 个 Markdown 文件），初次失败及修复前后源码另存维护证据，旧快照与 manifest 未改。
  原 B1 消费者、输入事实、评审配对、当前运行层、公共契约、457 个 Mock 冻结资产及两份历史工具包均只读核验通过。
  本轮只改当前工程分区且未进行阶段冻结，未重跑旧 Mock/S07；B2 科学签收、正式适配器、甲方目标环境和生产资格均未放行。

- 2026-09-06 B2 原包边界与执行补证：当前根测试 843 项通过、1 项因既有 Windows 符号链接权限跳过，新增补证回归 41 项全部通过；文档检查通过（183 个 Markdown 文件）。
  [本轮检查记录](phase1/PHASE1_REAL_W1_B2_BOUNDARIES_VERIFICATION.json)记录 13 次固定镜像禁网调用：10 份完整原始结果、2 次原包退出 1、1 次含 `*` 输入意外退出 0 后被校验拒绝；17 类产物故障副本全部拒绝。
  1/8/9/29/30 aa 与 1020～1023 aa 均成功，后者实际 1022～1025 个 token、分别切为 722 加 300～303 个 token，序列/标签/区段/概率/embedding/hash 全链回连通过；不扩大科学输入域或取消 <9 aa 上游守卫。
  B2-E01 原包将 `*` 编成 `<unk>` 的行为与初次评估失败保留；预声明拒绝预期未满足，未改计划、原输出或放宽守卫。后置 token 回拼与既有输入预检分别拒绝此结果/输入。
  新批 517 项文件、481 项受保护原件/旧证据/源码、旧 Academic 122 项证据及 41 个本地资产、B2 原评审、B1 消费者、通用契约/运行层、457 个 Mock 冻结资产及两份历史工具包均核验通过。
  本轮仅改当前工程分区且未进行阶段冻结，未重跑旧 Mock/S07；无 OOM/超时，不把资源保护配置当作故障实测。阶段保持 W1-08B2，输入/参考/目标/契约签收及 W1-09B2 正式适配器未放行。

详细向前顺序见[路线图](ROADMAP.md)，历史状态见[变更记录](../../legacy/project-history/project/CHANGELOG.md)。


## 整理前决定登记

以下表述也是整理前口径；现行决定见 [DECISIONS](DECISIONS.md)。

# T-01 当前决定登记

> 更新时间：2026-09-05  
> 本页只登记仍然生效的高层决定；科学细节仍以专家原件和版本化契约为准。

| 决定 | 当前口径 | 权威依据 |
|---|---|---|
| 一期业务拓扑 | 当前一期只以输入、N01-N18、设计 Gate、WT 分支和最终交付为业务骨架 | [最新一期图](<../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>)、[范围记录](sources/PHASE1_SCOPE_SOURCE_20260903.json) |
| P0-P7 定性 | P0-P7 是旧完整 T-01 Mock 工程分区，不是当前一期阶段或任务体系 | [一期 Mock 决定](sources/PHASE1_MOCK_BASELINE_DECISION_20260904.json) |
| 旧 Mock | 保留并冻结，未来开发完整 T-01 时可作参考；不得驱动当前一期计划、验收或发布 | [一期 Mock 决定](sources/PHASE1_MOCK_BASELINE_DECISION_20260904.json) |
| 新一期 Mock | 当前须新建严格匹配 18 节点图的独立 Mock；冻结后才开始真实工具生产实现 | [一期交付计划](PHASE1_DELIVERY_PLAN.md) |
| 节点 01 离线边界 | 删除 S-07/RCSB/AFDB 及联网回退；保留甲方服务器上的 AlphaFold3/ESMFold2 | [会议决定记录](sources/PHASE1_NODE01_OFFLINE_SOURCE_20260903.json) |
| 当前输入基线 | `protein_sequence`、`host_species` 必填，`structure` 可选；其余字段先从专家资料定点归并 | [一期范围](PHASE1_SCOPE_REBASELINE.md) |
| 一期 Mock envelope | 固定 `MOCK_DATA`、`scientific_compute=false`、完整 profile 和 18 个节点快照；请求/运行/节点/ArtifactRef/错误/审计采用 v0.1，科学 payload 保持 opaque | [M1-04 契约](phase1/PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md)、[JSON Schema](../../工作流设计/02-数据契约/T01_PHASE1_MOCK_ENVELOPE_SCHEMA_v0.1.json) |
| Mock 场景控制 | Gate、N12、N15、N16、N17 和 N18 入口只复制具名场景的 `SCENARIO_LITERAL`；21 个场景显式给出 N01-N18 终态与边，节点仅产生无科学值 stub | [M1-05 场景模型](phase1/PHASE1_MOCK_M1_05_DETERMINISTIC_SCENARIO_MODEL.md)、[机器目录](../../工作流设计/02-数据契约/T01_PHASE1_MOCK_SCENARIO_CATALOG_v0.1.json) |
| 一期 Mock 资产身份 | 根键固定为 `t01_phase1_mock_v01`；2 个 Workflow、26 个 namespaced 工具、21 个 scenario_ref、后端 run_id、计划目录、单一生成源、环境绑定与新旧回归严格隔离 | [M1-06 隔离规范](phase1/PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md)、[机器注册表](../../工作流设计/03-Dify实现/T01_PHASE1_MOCK_ASSET_REGISTRY_v0.1.json) |
| 一期 Mock fixture 与验收 | 21 个场景一一映射 21 个案例；23 次提交、22 个请求变体、4/16 异步 checkpoint、18+44 阻断断言与 10 个覆盖门禁形成闭集；运行型断言未执行前不得报 PASS | [M1-07 验收规格](phase1/PHASE1_MOCK_M1_07_ACCEPTANCE_ASSERTIONS_FIXTURE_MANIFEST.md)、[fixture manifest](../../dify/t01-phase1-mock-v0.1/fixtures/T01_PHASE1_MOCK_FIXTURE_MANIFEST_v0.1.json)、[acceptance Catalog](../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_ACCEPTANCE_CATALOG_v0.1.json) |
| M1 一致性与 M2 放行 | M1-01～08 规格基线冻结为 `T01-PHASE1-MOCK-M1-BASELINE-v0.1`；工程、算法边界和产品范围评审通过，M2 可实现确定性 Mock，但不得进入 Dify DSL 或生产能力 | [M1-08 一致性评审](phase1/PHASE1_MOCK_M1_08_CONSISTENCY_REVIEW.md) |
| M2 实现与 M3 放行 | M2-01～09 已完成；350 个 synthetic payload、21 场景/23 提交、4/16 checkpoint、26-tool facade、53 条适用 blocker 与 10 门禁通过；只放行 M3 构建 Dify Workflow | [M2 实现评审](phase1/PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md) |
| M3 实现与 M4 放行 | M3-01～10 已完成；本地 Dify 1.17.0/DSL 0.7.0 的 main/debug 已生成、绑定、导入回读并各执行 21 场景/23 提交，21 组 parity 通过；只放行 M4，未冻结 Mock 或部署真实能力 | [M3 实现评审](phase1/PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md) |
| M4 冻结与 W1 放行 | M4-01～10 已完成；独立 campaign 的 main/debug 全量回归、12 global、44×2 focus、10 coverage、21 parity、四分区和 457 资产只读验证全部通过；Mock v0.1 冻结，只放行 W1 READY，不代表真实能力部署 | [M4 实现与冻结评审](phase1/PHASE1_MOCK_M4_IMPLEMENTATION_REVIEW.md)、[freeze manifest](../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_FREEZE_MANIFEST_v0.1.json) |
| W1 专项准备 | 先形成 N01–N02 专项 backlog，同步收敛开放项与前置依赖；来源已有规则归并，真实冲突保留定点裁决；本次完成计划不代表 G0/G1 或生产部署 | 2026-09-05 当前会话用户明确决定（原话见下）；[W1 backlog](phase1/PHASE1_REAL_W1_BACKLOG.md)、[开放项](OPEN_ITEMS.md)、[交付计划](PHASE1_DELIVERY_PLAN.md) |
| 取消同事工具分工 | 取消工具分配、发包和回传安排，由主开发按原 W1–W7 计划统一推进。已有接口、说明和验收材料仍可复用；两份未发送工具包保留为历史参考，不再列为待分配任务 | 2026-09-05 [用户原话](#取消同事工具分工)；[历史交接资料](phase1/handoffs/README.md)、[W1 backlog](phase1/PHASE1_REAL_W1_BACKLOG.md) |
| W1 分模块开发 | 通用工程、已有工具、预测引擎分别按自身条件评审和实施，A 不等待 AF3/ESMFold2 资产；B/C 不跳过自身 G0/G1。完整 W1 集成、验收及发布仍等全部能力齐备 | [用户接受方案记录](sources/PHASE1_W1_MODULAR_DEVELOPMENT_20260905.json)、[W1-07 设计](phase1/PHASE1_REAL_W1_CONTRACT_DESIGN.md) |
| 服务器与开发位置 | 用户确认服务器容量可满足 AF3/ESMFold2；项目继续本机开发并完成 W1-09A。具体服务器配置、模型/MSA 资产和实际部署仍分别登记验证 | [用户原话](sources/PHASE1_W1_SERVER_CAPACITY_20260905.json)、[W1 环境登记](phase1/PHASE1_REAL_W1_PREPARATION.md) |
| 首批工具公共接口 | 两包共用协议 0.1.0、请求/结果 Schema、文件与错误/状态约定；工程符合性不替代 G0/G1。按用户决定直接更新 v0.1 交接资料并重算清单，不另保留旧包 | 2026-09-05 当前会话原话见下；[公共接口](../../工作流设计/02-数据契约/tool-interface-v0.1/README.md) |
| 本地结构与映射专项 | 主开发独立落实 PDB/mmCIF 解析、R-58 候选与核验工具。按用户要求只读检查历史样本，记录来源后复制为本地开发输入；历史状态/代码不回流，当前工具不联网检索 | 2026-09-05 用户原话见下；[R-58 专项](phase1/PHASE1_REAL_W1_R58_MAPPING.md) |
| FreeSASA 与 S-09 先行规则 | 用户先采用明确的参数/上下文、候选容差及 S-09 六项规则，仍向算法负责人确认；RSA 出域保留原值并报错复核。开发准备有确定基线，算法确认和 G1/G2 门禁不被替代 | [先行决定](phase1/PHASE1_REAL_W1_FREESASA_S09_DECISION.md)、[用户原话与来源 hash](sources/PHASE1_W1_FREESASA_S09_ADOPTION_20260905.json) |
| 一期入口与表达宿主 | 规范化序列与宿主物种必填，本地 PDB/CIF/mmCIF ArtifactRef 可选；`expression_host` 独立，缺失令 N16 条件跳过，明确但不支持的值令 N16 失败，不从 `host_species` 推断 | [M1-04 请求契约](phase1/PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md) |
| 一期排除/裁剪 | 默认完整一期；削减顺序为 N16→N07→N02/S-11；N10/N14/N17 受保护 | [一期范围](PHASE1_SCOPE_REBASELINE.md) |
| 数据网络 | 数据库型能力使用批准的本地数据包，运行时不得以公网查询 fallback | [一期交付计划](PHASE1_DELIVERY_PLAN.md) |
| 异步执行 | 真实长任务采用后端提交/轮询/超时/取消/恢复，不由 LLM 等待或推断 | OI-017；形成过程见[历史快照](../../legacy/project-history/project/OPEN_ITEMS_HISTORY_20260903.md) |
| Mock 证据 | 新旧 Mock 都只验证工程拓扑、契约和路由，不代表科学计算或生产部署 | [当前架构](ARCHITECTURE.md) |

2026-09-05 当前会话用户原话：“好的 先形成 W1 专项 backlog，并同步收敛相关开放项和前置依赖。”
本次据此调整工程准备与依赖时点；18 节点、内网边界、科学原件及已冻结 Mock 均不变。
OI-024 后续已获用户先行采用，适用上表及后续来源记录；算法负责人确认仍待补齐，不属于已完成科学签收。

2026-09-05 当前会话用户确认上一轮 FreeSASA/BepiPred 首批方案，原话：
“你这个觉得是对的。我们先每个同事分一个任务，看看他们的完成的效果，不一下子全分出去。
那你先把这个两个任务分别打个包吧。然后就是文档在描述的时候，写的简单明白一点，
然后再需要实现功能或工具的地方写的详细一点，因为他们是第一次做”。
首轮仅形成交接资料。当前接口按下述后续决定收敛为公共工程约定；科学未决项不因打包而关闭，目标工具未因此部署。

2026-09-05 当前会话后续用户原话：“先统一工具接口吧”；版本处理原话：
“不留v0.1 直接在0.1的基础上修改”。据此直接修订两份 v0.1 包，不另留旧版，更新 SHA-256、
文件清单与验证记录。授权范围为工程接口及交接资料，不修改专家原件或冻结 Mock。

2026-09-05 用户原话：“做‘本地结构解析与 R-58 映射专项’”；随后说明：
“就是目前的话，我们开发阶段是没有对方给的真实的测试用例。你可以找找冻结的历史里看看有没有，如果没有的话，那就是暂无”。
据此仅复用可追溯本地结构/序列作为开发输入；没有要求联网获取，也不将历史样本视为甲方金标准。

2026-09-05 用户随后调整交接时点，原话：
“这样，我们现在先不管同事那边，因为我要过几天才能给他们。我们现在就按照原来的计划进行，之后再给同事分任务”。
当时据此暂缓交接，由主开发继续原 W1 顺序；该安排已被下方取消分工决定覆盖。
原话保留用于追溯，已有公共接口、结构解析和工具资料仍可复用。

2026-09-05 用户针对已具备参数、容差和六项具体 S-09 结论的方案回复：
“先采用上述方案，但我还是要向算法负责人确认”。据此登记先行采用，不虚构算法负责人签名，
不把有条件采用升级成生产或 G1 放行；精确采用范围由上方 JSON 的来源 hash 固定。

## 取消同事工具分工

2026-09-05 用户最新原话：“这样 ，先取消给同事分工具这个事，我们就正常完成任务。下一步该干嘛”。
据此取消此前每人先分一个工具及延后交接的安排，由主开发按原计划统一完成任务。
已有工具包不删除、不发送，作为历史资料保留；公共接口、工具要求与验证证据继续服务主线。
这只调整执行分工，不改变一期范围、W1–W7 顺序或 G0–G6 门禁。

## W1 优先推进 B2 与后续工具波次边界

2026-09-06 用户明确要求优先推进 W1-08B2 DeepTMHMM 评审准备，包括输入/失败支持域、请求结果、
标签/区段/PB/null、独立参考和正式适配器放行条件；[完整原话](sources/PHASE1_W1_B2_PRIORITY_20260906.json)已独立保留。
据此修正 STATUS 将其他消费者实测列为下一项的安排：FoldX/ProteinMPNN 保留接口准备，
实际验证按所属波次开展，不在 W1 提前实现。B1 科学确认独立跟进，不阻断 B2 准备。
本决定调整执行顺序并重申既有波次边界，不改变一期完整范围或 G0–G6，也不授予 B2 科学资格。

2026-09-06 用户核对评审后，进一步明确开展 [本机原包边界与执行补证](sources/PHASE1_W1_B2_BOUNDARY_EXECUTION_20260906.json)：
实测短/长输入及真实 token、安全 ID/产物回连、执行失败与损坏产物拒绝。沿用现有本机资源限制，
阶段保持 W1-08B2，不依赖 B1 或 AF3/ESMFold2；自身输入域、独立参考、目标环境和契约适用签收后才进入 W1-09B2。

决定被更新时，应保留原始证据并替换本页当前口径；旧口径转入历史说明，不在当前入口并列展示。
