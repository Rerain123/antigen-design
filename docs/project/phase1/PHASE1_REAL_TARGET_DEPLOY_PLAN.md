# PH1-REAL-TARGET-DEPLOY：服务器部署与真实运行验收

> 2026-09-25 管理归类：本页保留阶段接口、原完成标准及历史证据；旧“当前/下一步/停止”按原时点解释。唯一当前执行包为[总计划](../PHASE1_DELIVERY_PLAN.md)的 PH1-REAL-GAP-1；N03 恢复 IEDB＋BLAST，N08 等专家确认、N18/Agent C 暂缓。科学细节仍以专家原件与最新用户决定为准，不重复维护本页排期。


> 部署计划顺序 1 已于 2026-09-21 完成工程验收；本页保留完成标准、边界和后续目标。当前状态由 [STATUS](../STATUS.md)维护；完整路线见 [总计划](../PHASE1_DELIVERY_PLAN.md)。

## 目标与依据

在批准的离线资产和单张 A100 64GB 上完成真实工具统一任务、结构来源、业务编排与可追溯交付。工程接入、科学消费和正式发布分别验收，不以空候选报告或父任务 succeeded 代替科学完成。

依据：[一期范围](../PHASE1_SCOPE_REBASELINE.md)、[专家权威索引](../../../工作流设计/01-业务依据/README.md)中的结构链 ToolSpec、SOP T-01/S-08/S-09 及下游适用章节；[统一单卡与主线顺序的用户决定](../DECISIONS.md)。已有明确规则直接落实，真正科学歧义登记 [OPEN_ITEMS](../OPEN_ITEMS.md)。

## 已具备的输入

- ESMFold2 标准输出、统一任务→N01、N12 同 run 和首条 N01–N18 工程链已有独立证据；支持边界不因单例扩展。
- AF3 数据、权重、固定环境、CPU 本地搜索及单卡原生五样本通过；本地标准适配器已对原件复放验证，全部样本保留。
- 统一常驻 Worker 全局 FIFO、唯一设备与停止确认已实施；AF3、ESMFold2、ProteinMPNN、ESM-IF1、ThermoMPNN 五个 GPU 工具均已登记，ESMFold2 r03 和三个迁移影响工具的代表性实跑通过。
- 最新记录为统一配置 `config-r11/code-r13`、service overlay r07；AF3 使用 `/alphafold3_venv/bin/python`，显式传入五个 `/hmmer/bin/*` 路径，并单独采用 512 MiB 有界文件上限，其他工具保持 32 MiB 默认值。Deployment generation 47 的唯一 Worker 采用 request/limit 96/128 GiB、8/16 CPU 主机资源边界，GPU 为指定单张 A100 64GB；service 与 Worker 已从容器内复核实际配置。后续更新仍须读取实时 resourceVersion，不复用历史补丁。

## 当前执行与完成标准

新执行安排以[总计划](../PHASE1_DELIVERY_PLAN.md) M1/P1–P4 为准；本页基础层已完成证据保留。后续不等完整资格才开始测试整链。

| 次序 | 交付内容 | 状态与证据 |
|---|---|---|
| 1 | AF3 独立验收批次 | **完成。** r14 越过四库 HMMER，取得五个 native sample、最高 pTM 及同分保留、standard ArtifactRef/hash/source binding、AF3→N01/S-09→N18 同 run；prediction 和父流程均成功。r12 prediction 成功但旧 service 结构校验器误标来源，r13 暴露并定位该问题，均保留原身份、不冒充最终成功批次 |
| 2 | 三个受影响 GPU 工具代表性回归 | **完成。** ProteinMPNN→ESM-IF1→ThermoMPNN 在同一 run、同一 A100 64GB 上严格串行成功，每项均有 `stopped_confirmed=true` 后才启动下一项 |
| 3 | 旧执行入口守卫 | **完成。** 现行 Deployment 只有统一 Worker 持有 GPU，无旧动态 GPU Deployment、无并行旧侧车、无 ServiceAccount token；五个 GPU 工具共用三个 spool 和一个全局 owner，未知进程仍按实现阻断释放 |
| 4 | 报告发布边界 | OPS-001 当前两份对象由用户决定；后续公开发布显式授权，下载不自动扩大公开范围 |
| 5 | 候选设计至报告主线 | P1–P3 接通上游分析、ProteinMPNN 候选生成、结构与表位复评、稳定性评分、排序和报告，使用显式测试模式及暂定口径，正式资格另验收 |
| 6 | 端到端最小验收及后续 | P4 验证新候选设计任务、WT 分支、失败或取消及报告回读；完整覆盖和正式交付留待 M2/M3 |

r02（service 注册）、r03（AF3 spool）、r04（解释器）、r05（初始化模块/依赖）、r06（Biopython 缺失）、r07（HMMER 路径缺失）均保留失败记录，不复用原批次。r05 父任务曾成功但 prediction=TOOL_FAILED，不计入 AF3 成功证据。r08 是时限校准的受控取消批次；r09 是 64 GiB cgroup 封顶后的失败批次；r10 是 96 GiB 封顶后的预防性受控取消批次；r11 在 128 GiB、无 OOM 情况下暴露 HMMER 子进程 32 MiB hard `RLIMIT_FSIZE`，随后受控取消并确认停止。各批次均保留原始执行目录且不计入成功证据。

完成快照：r14 父任务 `t01p1r-job-4e2773eae1cb494fa7d04b2c657537d8`、prediction 子任务 `t01p1r-job-57eb7c19dc9f4e59a7556907a8ac00fd`、run `t01p1r-run-7943e908347d4f24ba08bbbd23d1afeb`。194 个 ArtifactRef 经只读审计；12 个节点成功、8 个因数据库未提供/科学 Gate 关闭/无合格序列而明确跳过、0 失败。报告发布接口未调用，科学 Gate 仍为 CLOSED。

AF3 单链按最高 pTM 选样；并列保留全部，以最低 seed、再最低 sample 序号作确定性工程选择，不宣称科学优劣，不用 ranking_score 偷换项目规则。单链 ipTM 标准接口为 null 并保留不适用原因。

## 依赖与边界

- 全项目唯一指定 A100 64GB；无需新建 Role/RoleBinding。运维只在资源配置变化或权限不足时介入。
- N03/N08/N09 各自需要批准的业务数据包，AF3 遗传/模板数据库不能自动登记为业务库。
- r14 AF3 mmCIF 的未知插入码 `?` 按原字节保留；映射为 `unverified`，FreeSASA 为 `review_required / ICODE_UNKNOWN` 且 RSA 为 null。该边界不推翻 AF3 部署工程验收，也不得被改写成科学可消费结果。
- 本包内处理普通修复与补证；已通过独立工具不重做无关验收。HiMat、ESMFold2 长度扩展与 Pod 崩溃恢复按现有优先级后移。
- CLOSED/false/NOT_DEPLOYED 保持，直至对应资格有明确证据。报告公开授权不得从旧对象继承到新对象。

## 操作与证据入口

- [模型技术要求与接口](AF3_ESMFOLD2_SERVER_HANDOFF.md)、[运行手册](../../development/RUNBOOK.md)、[统一接口参考](../../development/TOOL_INTERFACES.md)。
- [单卡 Worker r03](../../../discovery/t01-phase1-real/unified-gpu-worker-20260920/r03/latest.json)。
- [AF3 原生五样本独立审计](../../../discovery/t01-phase1-real/af3-target-20260920/single-gpu-r01/audit-summary.json)。
- [AF3 r14 标准链独立审计](../../../discovery/t01-phase1-real/af3-target-20260920/workflow-r14/audit-summary.json)。
- [统一 GPU 三工具串行回归](../../../discovery/t01-phase1-real/unified-gpu-worker-20260920/regressions-r01/latest.json)。
- [旧执行入口守卫](../../../discovery/t01-phase1-real/unified-gpu-worker-20260920/entry-guard-r01/latest.json)。
- [ESMFold2 首条工程链 r03](../../../discovery/t01-phase1-real/workflow-first-chain-20260919/r03/audit-summary.json)。
- [AF3 原根目录增量迁移清单](../history/root-artifacts-migration.json)记录原路径、归档位置和 hash；旧 patch 只作历史证据。
- [已完成成果与历史](../history/README.md)承接所有历次数字、执行过程和失败证据。

实施 AI 每次完成只更新 STATUS 的现有摘要，保留实际运行证据链接；本页对应条目及其他文档由计划管理任务核对后维护。实施 AI 不得直接回填本页或改动计划，完整分工见 [AGENTS](../../../AGENTS.md#2-推进任务)。
