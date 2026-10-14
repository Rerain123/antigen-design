# S-07 任务 6：独立验收与 P0 交接

> 状态：`COMPLETE_HISTORICAL_NONPRODUCTION_ACCEPTANCE / DEFERRED_OUT_OF_PHASE1`  
> 版本：v0.1；日期：2026-09-03  
> 权威验收批次：`p0-s07-task6-acceptance-20260903-c`  
> 部署状态：`NOT_DEPLOYED`；科学验收：`NOT_RUN`

> 后续覆盖：节点 01 内网决定已将 S-07 和数据库检索移出一期；本验收不再构成 P0 v0.7
> 生产门禁或交接候选，仅作为历史证据保留。

## 1. 结论和边界

任务 6 的非生产独立验收与交接材料已经完成。新批次在固定 wwPDB 发布上重跑 MMseqs2，
同时读取当前 RCSB、UniProt 和 AlphaFold DB 官方 API，复核任务 5 的错误、恢复与 S-08/S-09
交接形状。10/10 项任务检查、全套 116 项 Python 测试和文档链接检查均通过。

本次形成可运行的验收后端、固定版本与资源记录、原始请求/响应、结构文件、机器报告、逐文件
哈希清单、运行依赖矩阵和 P0 S-07 组件候选清单。它们用于 P0 v0.6 设计与发布评审，不代表：

- 已发布生产 MCP、Dify Workflow 或真实科学工具；
- S-08/S-09 消费者已经部署；
- 五项暂行规则已经获得专家确认；
- 已完成 G1 科学验收或目标服务器本地数据库部署。

## 2. 本次交付

| 任务 6 交付要求 | 已形成的交付物 | 状态 |
|---|---|---|
| 可运行后端能力 | [验收后端](../../../src/t01_s07_acceptance/backend.py)、[运行器](../../../scripts/run_s07_task6_acceptance.py)与[Windows 包装脚本](../../../scripts/run-s07-task6-windows.ps1) | 非生产验收可运行 |
| 版本与运行记录 | [机器报告](../../../discovery/p0/s07/p0-s07-task6-acceptance-20260903-c/reports/task6_acceptance.json)和[运行依赖矩阵](../../../discovery/p0/s07/p0-s07-task6-acceptance-20260903-c/reports/runtime_dependency_matrix.json) | 完成 |
| 验收样例与报告 | [人读报告](../../../discovery/p0/s07/p0-s07-task6-acceptance-20260903-c/reports/TASK6_ACCEPTANCE_REPORT.md)、原始证据及[初始清单](../../../discovery/p0/s07/p0-s07-task6-acceptance-20260903-c/reports/artifact_manifest.json) | 10/10 PASS |
| 错误、恢复与交接 | 复用[任务 5 契约](S07_TASK5_RESULT_CONTRACT.md)，复核 19 份结果、20 项非法状态拒绝与 7 项存储/恢复检查 | PASS |
| 部署与恢复说明 | 本文 §6 和[本地数据与运行环境方案](S07_LOCAL_DATA_AND_RUNTIME_PLAN.md) | 完成；目标服务器待接收方实施 |
| P0 发布包组成候选 | [P0 S-07 组件候选清单](../../../discovery/p0/s07/p0-s07-task6-acceptance-20260903-c/reports/p0_s07_component_candidate.json) | `STAGED_ACCEPTANCE_EVIDENCE_ONLY` |
| 独立收尾复核 | [收尾目录](../../../discovery/p0/s07/p0-s07-task6-acceptance-20260903-c/reports)中的 `closeout_verification.json` 和 `closeout_manifest.json` | PASS |

组件候选明确写入 `deployable=false` 和 `production_mode_enabled=false`。P0 v0.6 工程评审完成后，
该清单仍只是证据候选，不能当成生产发布授权。

## 3. 验收结果

### 3.1 固定发布本地检索

固定 profile 为 wwPDB `2026-08-29`、MMseqs2 `18-8cc5c`，阈值仍为
`identity > 95%`、`query coverage > 90%`，每条 query 上限为 10,000。新运行得到 2,466 条
严格 query-chain 候选，未触及该上限。

| 输入 | 严格 chain | entry | 处理结果 | 关键事实 |
|---|---:|---:|---|---|
| 1UBQ | 2,442 | 1,333 | `SELECTED_PROVISIONAL` | 暂选 6Q00/A，0.85 Å |
| TP53 | 24 | 8 | `REVIEW_REQUIRED` | 9R2Q 的 K/L/M/N 四条链按 R-58 阻止自动交接 |
| O15116 | 0 | 0 | `NO_STRICT_CANDIDATE` | 正常空结果，继续公共预测结构回退 |
| WP_505187596.1 | 0 | 0 | `NO_STRICT_CANDIDATE` | 正常空结果 |

6Q00/A 的序列与坐标均覆盖 76/76；9R2Q/K 的检索序列匹配与坐标覆盖继续分开记录，坐标为
200/393。这样可以直接检查 `partial`，不会用检索 coverage 代替实际坐标覆盖。

本地 MMseqs2 运行墙钟为 3.607989 秒，采样到的主进程峰值工作集为 9,949,184 B，工具日志给出的
最大估计内存为 3,221,225,472 B。验收机记录为 32 个逻辑 CPU、33,483,198,464 B 物理内存；
这些是本批次资源事实，不直接变成目标服务器容量承诺。

### 3.2 当前官方 API 连续读取

| 用例 | RCSB 返回总数 | 严格实体 | 候选 chain | GraphQL 批次 | 处理 |
|---|---:|---:|---:|---:|---|
| API-1UBQ | 1,623 | 1,588 | 2,422 | 16 | 暂选 6Q00/A |
| API-O15116 | 0 | 0 | 0 | 0 | 正常空结果，转 AFDB |

RCSB 检索使用 `return_all_hits=true`，并以 matching context 重新核对 query coverage。元数据读取采用
`rcsb_entry_info.experimental_method`；8ZZ4 和 9A1L 的 `Integrative` 方法被记录为 `OTHER`，作为
不可比方法候选保留，不参与可比 Å 值排序。这一情况已由现有 S07-EQ-02 覆盖，没有新增专家问题。

O15116 在 RCSB 严格候选为空后，从 UniProt `2026_03` 读取序列，再取得
`AF-O15116-F1` v6。输入、UniProt JSON、UniProt FASTA、AFDB 元数据和 CIF 序列逐层完全一致，
confidence 与 PAE 维度检查通过，形成 `source=alphafolddb` 的 S-09 交接候选。

本批次共记录 25 次 HTTP 往返，累计 HTTP 墙钟 24.705311 秒，下载 3,041,793 B。API 数据是
2026-09-03 的连续运行观察；将来重跑应比较契约、不变量和发布版本，不能假设返回数量永远不变。

### 3.3 结果、故障和下游交接

任务 5 的 19 份结果全部重新验证：11 份保持 `BLOCKED`，2 份形成 S-08 交接，6 份形成 S-09
交接。20 项非法状态拒绝和 7 项文件/恢复检查仍为 PASS，包括同长度内容损坏的哈希识别、只读
回放不变和重试保留旧失败记录。

缺 accession 的真实 BLAST 正命中路径仍返回 100 条，恰好达到 profile 的 100 条上限。因此本次
只确认 `candidate_collection_complete=false` 和 `automatic_selection_allowed=false`；不能从被截断的
候选集中自动挑选 accession。这是 P0 v0.6 的发布门禁，不把它伪装成任务执行故障或正常零命中。

## 4. 三个运行批次怎样解释

| 批次 | 结果 | 保留原因 |
|---|---|---|
| `...-a` | `FAILED_INCOMPLETE`；T6-C06 未通过 | 初次错误使用 `exptl.method`，8ZZ4/9A1L 的显式空值揭示 RCSB 方法字段取值不完整 |
| `...-b` | 10 项验收通过；初次打包清单失败，随后仅收尾 | MMseqs 工作目录含悬空 `latest` 链接；失败与恢复记录均保留。该批次又因后续元数据字段修正而被 c 取代 |
| `...-c` | `COMPLETE_NONPRODUCTION_ACCEPTANCE_WITH_RELEASE_GATES` | 使用正确实验方法字段，正常生成 151 文件、8,110,881 B 的初始哈希清单；作为权威批次 |

失败批次不删除、不覆盖。a 证明元数据字段错误能使验收失败；b 证明验收通过后的打包失败可在不
重跑科学请求的情况下独立收尾；c 是最终用于文档、测试和 P0 v0.6 的证据来源。

## 5. 验收检查与发布门禁

| 项目 | 结论 | 对后续的约束 |
|---|---|---|
| 新固定发布 MMseqs2 检索与完整候选收集 | PASS | 本批次候选未触顶；生产 profile 仍须在 v0.6 定义 |
| 当前 RCSB 完整命中、元数据与结构读取 | PASS | API 数量是运行时事实，需保留请求和响应 |
| O15116 UniProt→AFDB 连续回退 | PASS | S-09 仅验证交接形状，消费者未部署 |
| 严格阈值、多链、不可比方法与 partial | PASS | 依赖的五项暂行规则继续附带专家待确认状态 |
| 任务 5 故障、不可变回放与重试 | PASS | OI-017 生产等待/取消/恢复入口仍未实现 |
| 缺 accession 的 BLAST 正命中候选完整性 | BLOCKED | 100 条触顶结果禁止自动选择 |
| P0 S-07 非生产独立验收 | PASS | 已进入并支撑 v0.6 方案重写与工程评审 |
| 科学验收 G1 | `NOT_RUN` | 专家规则和真实科学验收方案未冻结 |
| MCP、Dify、S-08、S-09 | `NOT_DEPLOYED` | 阶段发布包完成后统一接入 |
| 目标服务器本地数据库 | `HANDOFF_PENDING_RECEIVING_TEAM` | 接收方按 17 组索引/资源清单部署和校验 |

五项待确认问题仍为 [S07-EQ-01～05](S07_EXPERT_CONFIRMATIONS.md)，状态均为 `PENDING`。本次发现的
Integrative 方法属于 S07-EQ-02 已声明的不可比方法范围，没有扩大问题清单。

## 6. 重跑、故障和恢复

每次验收必须使用新的 `campaign_id`；运行器拒绝覆盖已有目录。在 Windows 非 ASCII 工作区中，
包装脚本会临时映射 ASCII 盘符供 MMseqs2 使用，并在结束后解除映射：

```powershell
.\scripts\run-s07-task6-windows.ps1 -CampaignId p0-s07-task6-acceptance-YYYYMMDD-a
```

普通运行失败后保留原批次，并使用新编号重试。只有“10 项验收已经写入不可变报告、随后仅在
manifest 打包阶段失败”时，才允许对原批次运行 `--finalize-existing`；它不重新发送 API 请求，
并追加失败与恢复记录。证据检查可独立执行：

```powershell
.\.venv\Scripts\python.exe .\scripts\verify_s07_task6_closeout.py `
  --campaign-id p0-s07-task6-acceptance-20260903-c
```

收尾脚本同样拒绝覆盖已存在的收尾文件。需要重新验证时应只读检查现有 JSON/哈希，或复制规则到
新的验收批次，不删除历史结果。网络中断、HTTP 非预期状态、候选收集触顶和文件损坏都必须保留为
不同的事实，不能改写成正常空结果。

目标服务器上的本地数据库、索引、权限、容量和离线运行由接收方按
[任务 2 交接方案](S07_LOCAL_DATA_AND_RUNTIME_PLAN.md)执行。工作站批次没有宣称目标服务器已部署。

## 7. 下一项任务

S-07 的任务 1～6 现已完成到“非生产验收与交接证据”层级。[P0 实施方案 v0.6](../../../../project-history/p0/P0_IMPLEMENTATION_PLAN_v0.6_ARCHIVE.md)
已纳入任务 3～6 事实并通过[工程评审](../../../../project-history/p0/P0_IMPLEMENTATION_PLAN_V0_6_REVIEW.md)。下一项执行
`P0-V06-M1` 决定与契约工作包；对应门禁通过后才实施生产适配器、OI-017 状态机以及
S-08/S-09 的真实接入，在此之前保持 `NOT_DEPLOYED`。
