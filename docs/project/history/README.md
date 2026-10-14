# T-01 已完成成果与历史索引

本页是现行文档的历史入口。`STATUS.md` 只维护当前能力、阻塞和下一步；本页保留已完成工程包、被替代方案、冻结基线和整理前快照的查找关系。历史记录中的旧“下一步”不构成当前任务授权。

## M1 与 HiMat 合并归档

[合并历史记录](M1_HIMAT_CONSOLIDATED.md)集中保存整理前 M1 计划、HiMat/N03/N09/N11 实施与验证、原 STATUS 全文；历史阶段页面原位保留用于接口和证据追溯，停止作为并列当前排期。运行 JSON/ZIP、专家原件和冻结文档未移动或改写。

当前唯一执行包为[总计划](../PHASE1_DELIVERY_PLAN.md)中的 PH1-REAL-GAP-1；N08 等专家确认、N18/Agent C 延后。下面表格的完成边界按原批次理解，“当时缺失”不代表现在仍缺失，最新能力见 STATUS。

## 当前已完成工程包

| 主题 | 完成边界 | 证据入口 | 当前剩余工作 |
|---|---|---|---|
| PH1-REAL-ROUTE-1 线上工程路由纠偏 | 新目标 nr 设计 r18、WT r19、错误 r20 分别通过独立严格审计；设计路径 N12→N13→N14→唯一最终 N15、N16/N17 独立汇入 N18；部署哈希、原始 WT 五轮 FoldX、原生回执、成功路径报告/ZIP 回读均核验 | [部署哈希](../../../discovery/t01-phase1-real/m1-p4-20260922/route-deployment-verification-r01.json)、[r18](../../../discovery/t01-phase1-real/m1-p4-20260922/r18/route-audit-summary.json)、[r19](../../../discovery/t01-phase1-real/m1-p4-20260922/r19/route-audit-summary.json)、[r20](../../../discovery/t01-phase1-real/m1-p4-20260922/r20/route-audit-summary.json) | HiMat 用户入口尚未实跑；科学资格仍 CLOSED / false / NOT_DEPLOYED |
| M1 P4 目标库服务整链 | 设计 r16、WT r17、失败 r07 三条目标 nr 服务路径经独立审计；2227 文件全量 SHA-256，r16/r17 原生 N03 查询与报告/ZIP 回读；`P4_M1_MINIMAL_PASS` 仅为有限范围工程链通过，当前根 2289 passed / 15 skipped / 0 failed | [P4/M1 收口证据](../../../discovery/t01-phase1-real/m1-p4-20260922/p4-m1-acceptance-r01.json)、[r16 节点快照](../../../discovery/t01-phase1-real/m1-p4-20260922/r16/workflow-snapshot.json)、[r16 审计](../../../discovery/t01-phase1-real/m1-p4-20260922/r16/audit-summary.json)、[r17 审计](../../../discovery/t01-phase1-real/m1-p4-20260922/r17/audit-summary.json)、[r07 审计](../../../discovery/t01-phase1-real/m1-p4-20260922/r07/audit-summary.json) | r16 N14 先于 N13、另有两次中间 N15 的历史偏差保留；后置纠偏另以 r18/r19/r20 验收。目标库科学用途/上游校验和未签收，正式资格 CLOSED / false / NOT_DEPLOYED |
| M1 P3 WT 扫描与本地交付 | 原 P1/P2 run 下新执行 FoldX 位点 3 与 ThermoMPNN 原生 1520 条；N16 条件跳过，N18 报告/13 文件 ZIP 回读；1376 个 ArtifactRef 通过 | [独立审计](../../../discovery/t01-phase1-real/m1-p3-20260922/r01/audit-summary.json)、[N18 报告](../../../discovery/t01-phase1-real/m1-p3-20260922/r01/delivery/report.md)、[交付 ZIP](../../../discovery/t01-phase1-real/m1-p3-20260922/r01/delivery/package.zip) | 保留有限扫描范围和全淘汰事实；完整 WT 扫描及正式交接后补 |
| M1 P2 候选验证、复评与排序 | 24 条候选和 WT baseline 真实 ESM-IF1；3 条代表完成 N12–N15、各 5 次 FoldX；1705 个 ArtifactRef 通过，2228 passed / 15 skipped / 0 failed | [独立审计](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/audit-summary.json)、[最终变体报告](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/final-report.json)、[验证汇总](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/validation-summary.json) | 全部 EXCLUDED，仅调试排序；正式资格未开放 |
| M1 P1 上游到候选设计 | 显式 m1_test、同 run 上游与最小 BLAST 实跑、24 条非 WT 候选；229 个 ArtifactRef 校验通过；2211 passed / 15 skipped / 0 failed，部署代码 hash 与单卡入口守卫通过 | [实跑审计](../../../discovery/t01-phase1-real/m1-p1-20260921/r01/audit-summary.json)、[验证汇总](../../../discovery/t01-phase1-real/m1-p1-20260921/r01/validation-summary.json)、[部署核验](../../../discovery/t01-phase1-real/m1-p1-20260921/r01/deployment-verification.json) | N08/N09 unavailable、N10 缺项与正式资格原样保留；P4 工程最小验收不使其科学签收 |
| ESMFold2 工程接入 | 76 aa 标准结果、统一任务、N01/N12 同 run、取消/超时及单卡 Worker r03 | [Worker r03](../../../discovery/t01-phase1-real/unified-gpu-worker-20260920/r03/latest.json) | 长度扩展、Pod 崩溃恢复和科学签收仍关闭 |
| AF3 原生与标准适配 | 权重/数据库/环境核验、CPU 本地搜索、五样本原生推理、真实原件只读复放和标准适配；r14 完成 AF3→N01/S-09→N18 同 run，12 成功、8 明确跳过、0 失败 | [原生审计](../../../discovery/t01-phase1-real/af3-target-20260920/single-gpu-r01/audit-summary.json)、[r14 标准链审计](../../../discovery/t01-phase1-real/af3-target-20260920/workflow-r14/audit-summary.json) | 未知插入码的 FreeSASA 分支保持复核；业务数据、科学 Gate 与生产发布仍按后续计划推进 |
| 统一单卡 Worker | 唯一 A100-SXM-64GB、全局 FIFO、停止确认；AF3/ESMFold2/ProteinMPNN/ESM-IF1/ThermoMPNN 全部登记；后三项迁移回归严格串行通过，旧双 GPU/RBAC 入口封堵通过 | [单卡快照](../../../discovery/t01-phase1-real/unified-gpu-worker-20260920/r03/latest.json)、[三工具回归](../../../discovery/t01-phase1-real/unified-gpu-worker-20260920/regressions-r01/latest.json)、[入口守卫](../../../discovery/t01-phase1-real/unified-gpu-worker-20260920/entry-guard-r01/latest.json) | 仅在资源布局、GPU 型号/UUID 或执行入口变化时重验；长度扩展与 Pod 崩溃恢复仍后移 |
| 首条 N01–N18 工程链 | ESMFold2→N01→N17/N18，12 分支成功、8 分支明确跳过、0 失败 | [链路审计](../../../discovery/t01-phase1-real/workflow-first-chain-20260919/r03/audit-summary.json) | 不代表完整科学设计链或正式交付 |

## M1 P1/P2 归并记录（2026-09-22）

以下保留交付时的执行事实、原任务要求和验证；其中“停止本包/后续安排”仅表示当时边界，当前下一项以 STATUS 和总计划为准。

**P1 已核对归并，P2 已完成真实接续并通过独立审计。** 在原 P1 run 下追加独立子任务，P1 父任务及全部原证据未改写。24 条候选和同 WT 骨架 baseline 均真实执行 ESM-IF1；sample-22、sample-4、sample-16 完成 ESMFold2、结构质量/FreeSASA、BepiPred、NetMHC I/II、表位地图、糖基化、可开发性及相对原始 WT 的 FoldX 五次 BuildModel，N13 配对评估与 N15 简化测试排序均成功。24 条仍全部 EXCLUDED，三条代表仅为调试复评，其余 21 条明确未选中、未执行后续重算；空热点保护指标保持 null/未评估，未恢复正式资格。

[P2 独立审计](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/audit-summary.json)为 `M1_P2_N12_N15_PASS`：三条非 WT 候选完成 N12–N15、1705 个 ArtifactRef 通过、五次 GPU 调用严格串行且停止确认、原生离线回执通过。最终使用修复执行器后新执行的 N12 评分（WT baseline −0.06536121744858592）；旧 N12 证据仍保留，未改写运行版本或复制为新计算。原 900/7200 秒 FoldX 超时及停止证据保留，14400 秒预算的独立子任务真实完成全部 15 组；启动前底层预算阻断已修复，按原 job/attempt 恢复。大结果回读采用压缩并校验哈希；未发布报告。

[选择记录](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/selection.json)保留未追加 ProteinMPNN 的事实：固定 N11 profile 不支持原件追加轮配置，未将未执行写成重试成功。最终仍按计划允许的全淘汰调试路径输出。当前包停止，不自动进入 P3/P4；由计划管理任务据本页事实安排后续。

### P2 原任务要求（已完成，非当前执行授权）

**目标：把 P1 已生成的真实候选接入验证、重评、稳定性打分和测试排序。** 复用已验收的 N11 入口，不重做 P1 部署；不等待正式 BLAST 库、N08/N09 数据或 N10 全维度齐备。工具接口与原件按 W5/W6 对应章节查阅，已有暂定处理继续适用。

1. **来源与接续。** 先核验 P1 run 中的候选、WT、结构和约束 ArtifactRef。运行层若支持原 run 下追加独立子任务，则在同 run 新执行 N12–N15 并记录 P1 来源；不得改写已完成父任务、原审计或把 P1 产物声称为 P2 新生成。若不支持可靠接续，用同一样例和配置创建新 run，真实重跑上游及 N11 后串联 P2；不复制旧 ArtifactRef 冒充新 run。
2. **N12 验证。** 对 24 条真实候选执行 ESM-IF1，并在同 WT 骨架上取得可核验 WT baseline，保留原始分数、相对变化和排除原因。按真实分数降序、稳定候选 ID 处理平分，选最多 3 条代表候选；优先未被排除者，全淘汰时按既定 A06 最多追加一轮，仍淘汰可选被排除候选进行明确标记的调试复评。用一个已部署且支持该输入的 ESMFold2/AlphaFold3 路径做真实结构复核，不将调试复评视作恢复候选资格。
3. **N13 变体复评。** 对代表候选实际重跑适用 BepiPred、NetMHCpan/NetMHCIIpan、表位地图、糖基化及可开发性计算；结构质量与 FreeSASA 按新结构检查，执行已有可用计算，缺失维度留 null/原因。WT 与变体使用同一版本/参数和可比较的来源；空热点保护指标记不适用或未评估，不因空集直接判保护通过。不得只复用 WT 分数或跑比较夹具充当变体重评。
4. **N14/N15 打分与排序。** 对同一代表候选实际调用 FoldX，按已固定工具路径相对原始 WT 计算并保留原始输出，不将不同 WT/骨架的历史分数拼接。N15 按 A07 的 ESM-IF1 分数形成简化测试排序，并关联结构复核、表位/可开发性复评、FoldX 结果和缺项；完整 Pareto/权重优化留待 M2。所有候选的未选中、未计算、被排除状态分别保留。
5. **测试服验收。** 完成受影响测试、部署代码核验和真实串行调用；共享运行层/契约变化按运行手册扩大回归。新具名批次至少有 1 条非 WT 候选完整经历 N12→N13→N14→N15，证据包含 candidate_id、序列 hash、WT/结构来源、run_id、配置、原始回执及 GPU 停止确认。只提交任务或父任务 succeeded 不算达标。

P2 完成后停止本包并回填 STATUS，供管理任务安排 P3；本包不要求 N17 全扫描、N16 扩域、报告公开、HiMat 或 Agent C 联调。科学 Gate、正式管线资格与生产状态保持原义。实施 AI 只能写 STATUS，不修改本计划或其他项目文档。

### 归并时的实跑验证

- [P2 最终结果](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/final-report.json)：按最新真实 ESM-IF1 分数排序为 sample-22（−2.29667824193051）、sample-4（−2.325000762939453）、sample-16（−2.3328445836117395）；对应 FoldX ΔΔG 为 **3.4968882、−2.628056、−8.550728 kcal/mol**，各保留五次原始值、标准差、WT 和变体 PDB。三条均 EXCLUDED，正式 ranked_candidates/Pareto/best_candidate 仍为空；N10 的旧 stability_ddg 缺项未被覆盖，N14 实际结果独立关联。
- [P2 原生证据包](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/native-evidence.zip)含 510 份输出/回执及 ArtifactRef 索引，10,472,175 bytes；ZIP 回读与逐项 size/SHA-256 核验通过，[包哈希清单](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/native-evidence-manifest.json)保留身份。正式 BLAST 未接入、未搜索服务器库；N08/N09 不可用，空热点不判保护通过，CamSol、部分 RSA/标签暴露及正式加权缺项保持原原因。
- [P2 受影响测试](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/validation-summary.json)：**278 passed / 0 skipped / 0 failed**。Docker 恢复后，同 run 来源测试通过；覆盖代表选择、淘汰/缺失保留、N13 来源、FoldX 五次与预算上界、ESM-IF1/ESMFold2、部署文件字节保持及原生串行/离线审计守卫。[P2 测试服代码核验](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/deployment-verification.json)为 `M1_P2_DEPLOYED_CODE_HASHES_PASS`，r08 控制面覆盖与 ESMFold2 worker 完整目录一致；[单卡守卫](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/gpu-entry-guard.json)通过。r08 底层预算/轮询修复后，完整当前根 **2228 passed / 15 skipped / 0 failed**（[JUnit](../../../discovery/t01-phase1-real/m1-p2-20260921/r01/full-tests.junit.xml)）；457 份冻结 Mock 资产只读复核 PASS，未跨历史分区，旧完整 Mock/S07 未重跑。Linux 进程行为的平台跳过不充当原生执行通过，真实 Linux 同 attempt 启动另有回执。收尾脚本/审计/压缩回读专项另有 7 项通过，最终真实运行独立审计亦已通过。
- [P1 实跑审计](../../../discovery/t01-phase1-real/m1-p1-20260921/r01/audit-summary.json)：`M1_P1_UPSTREAM_TO_N11_PASS`；run `t01p1r-run-37b2e9f985b2405e82890262f81c71c4`；229 个 ArtifactRef 通过，24 条候选均不同于 WT 且互不相同。固定 1/76 位点、位置 2 的 A/Q 允许集及突变记录逐条复核通过；原生 ProteinMPNN 约 5.68 秒，整父任务约 63.84 秒。全部为本轮新执行，无旧候选回放；[N11 结果及执行回执](../../../discovery/t01-phase1-real/m1-p1-20260921/r01/design.json)保留原生 seccomp 离线限制、A100 身份和停止确认。
- [AF3 r14 独立审计](../../../discovery/t01-phase1-real/af3-target-20260920/workflow-r14/audit-summary.json)：`AF3_FIRST_N01_N18_ENGINEERING_AUDIT_PASS`；run `t01p1r-run-7943e908347d4f24ba08bbbd23d1afeb`；194 个 ArtifactRef 复核通过；五个样本最高 pTM 0.86，sample 1 与 4 同分，按已登记的确定性工程规则选择 sample 1；未使用官方 ranking score。
- [统一 GPU 三工具回归](../../../discovery/t01-phase1-real/unified-gpu-worker-20260920/regressions-r01/latest.json)：`UNIFIED_GPU_THREE_TOOL_SERIAL_REGRESSION_PASS`；同一 run 内 ProteinMPNN→ESM-IF1→ThermoMPNN 严格串行，分别生成 24 条、评分 1 条、原生预测 1520 条/筛得 1480 条；全部为 A100-SXM-64GB、CUDA 12.8，且停止确认后才启动下一项。
- [本轮单卡入口守卫](../../../discovery/t01-phase1-real/m1-p1-20260921/r01/gpu-entry-guard.json)：`UNIFIED_GPU_OLD_ENTRY_GUARD_PASS`；Deployment generation 48，只有 `worker-unified-gpu` 持有一张完整 A100 64GB，五个 GPU 工具仍统一登记，队列 idle，无旧 GPU Deployment，无 ServiceAccount token 挂载。
- [测试服代码核验](../../../discovery/t01-phase1-real/m1-p1-20260921/r01/deployment-verification.json)：`M1_P1_DEPLOYED_CODE_HASHES_PASS`，13 个实际挂载文件与不可变 `antigen-m1-p1-code-r01` 逐字节一致，单副本就绪；原有统一 GPU r11/r13 与 AF3 service r07 保留。本轮只加 P1 代码覆盖与最小测试库只读挂载，部署配置见[本轮清单](../../../deploy/m1-p1/r01/configmap.yaml)，不改变 GPU 调度或凭据。
- [P1 最终验证](../../../discovery/t01-phase1-real/m1-p1-20260921/r01/validation-summary.json)：完整当前根 **2211 passed / 15 skipped / 0 failed**；[JUnit 原始结果](../../../discovery/t01-phase1-real/m1-p1-20260921/r01/tests.junit.xml)保留平台跳过原因。覆盖默认入口关闭、显式配置/掩码、业务 Gate 隔离、同 run/错序列/hash 篡改、幂等冲突、缺库语义与部署补丁。一个 Docker 来源测试在受限环境报 ASSET_MISSING，具备本机 Docker 权限后复跑及完整回归均通过。457 份冻结 Mock 资产只读验证 PASS；无跨历史分区变更，旧完整 Mock 与 S07 未重跑。
- 受影响结构、AF3 审计、统一 Worker、串行回归与入口守卫测试均通过。文档检查为 `PASS_WITH_HISTORICAL_LINK_ISSUES`：现行导航零错误，29 条旧历史引用与冻结报告中 2 条已验证 ZIP 包内链接单列；未修改冻结原件。

## 被替代方案与失败批次

统一常驻 Worker 已替代旧双 GPU、动态 RBAC 调度和并行 Job 候选；旧方案只作历史参考，不得恢复为当前入口。AF3 工作流 `r02`–`r07` 的失败任务、r08–r11 的校准/受控取消、r12 的旧 wire-format 兼容暴露和 r13 的旧结构校验器来源误标均保留原身份，不能覆盖或复用；只有 r14 计作本轮标准业务链成功证据。具体边界见 [AF3 部署任务页](../phase1/PHASE1_REAL_TARGET_DEPLOY_PLAN.md)。

## 冻结基线与原位资料

一期 Mock 冻结清单锁定的 8 份 M1 文档、专家权威原件、历史交接包、来源 manifest 和既有 `legacy/` 分区保持原路径和原字节。本页只提供入口，不复制或重写这些文件。

## 整理前快照与根目录迁移

- [整理前部署文档快照](deployment/before-20260921/index.json)记录整理前原字节与路径。
- [AF3 根目录产物迁移清单](root-artifacts-migration.json)记录具名增量、现场快照和工作流探针的原路径、新路径、文件数、大小及 SHA-256。
- `deployment/before-20260921/` 内的旧链接按快照时点解释；历史报告中的既有断链单独保留，不修改冻结报告正文。

## 查找规则

先从 [当前状态](../STATUS.md)进入当前任务，再按本页证据入口追溯原始批次。历史文件不能反向覆盖当前状态；科学规则始终回到 [权威索引](../../../工作流设计/01-业务依据/README.md)。
