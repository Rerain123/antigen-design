# T-01 决策与计划文档清理审计清单

> **后续状态：已获用户授权并执行。** 实际移动、唯一删除项和验证结果见[清理执行记录](DOCUMENT_CLEANUP_EXECUTION_20260903.md)；本文继续保留为执行前只读快照。

> 审计日期：2026-09-03  
> 状态：`READ_ONLY_AUDIT / NO_CLEANUP_ACTION_AUTHORIZED`  
> 审计目标：以最新一期范围和最新开发路线图为当前计划基线，识别会误导开发者或 AI 的过时、重复、混合及错误引用资料。  
> 本轮边界：只新增本审计清单；未移动、删除、重命名或改写任何被审计文件。

## 1. 审计结论

需要清理，而且应在继续 P0 实施前完成第一轮。当前主要风险不是“历史文件存在”，而是：

1. 历史计划与当前计划仍位于同一目录、同一索引和同一搜索结果层级；
2. `STATUS.md`、`ROADMAP.md`、项目索引等当前入口仍复制大量 S-07、v0.5、v0.6 过程；
3. 一些历史文档仍使用“当前”“下一步”等时态，且链接已指向同名的现行 v0.7 文件；
4. 当前 P0 依据表和工具说明把当前四步骤与已排除的 S-07/S-06 混在同一正文；
5. 专家目录新增一期图后，物理文件数与旧清单不一致，且同一图有两个完全相同的副本；
6. 文档检查器仍把两个 S-07 历史文档列为项目必需入口，技术上固化了旧导航。

建议采用“当前控制面尽量少，历史证据完整但默认不可见”的清理策略。正式清理前先形成单一
当前基线清单，再按迁移依赖分批处理，不能直接批量删除。

## 2. 本次判断基线

| 信息类型 | 当前判断依据 | 在清理中的作用 |
|---|---|---|
| 一期范围、优先级、裁剪 | 专家目录内的[最新一期图](<../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>)及后续节点 01 用户决定 | 决定什么属于当前一期；被排除内容不得继续占据当前计划入口 |
| 项目开发顺序 | [最新路线图](ROADMAP_P0_P7_20260903.md) | 决定当前及后续实施次序；历史执行链不应混入“近期计划” |
| P0-P7 门禁 | [顺序交付计划](P0_P7_STAGE_DELIVERY_PLAN_20260903.md) | 决定各阶段 G0～G6、范围和冻结条件 |
| 当前事实 | [当前状态](../../../docs/project/STATUS.md) | 只应回答现在完成什么、卡在哪里、下一步是什么 |
| 当前 P0 | [P0 v0.7](../p0-v07-plan/P0_IMPLEMENTATION_PLAN.md)与[V07-M1](../p0-v07-plan/P0_V07_M1_BACKLOG.md) | 当前唯一 P0 实施计划与任务台账 |
| 科学与业务规则 | [权威资料索引](../../../工作流设计/01-业务依据/README.md)及当前专家原件 | 防止把历史工程决定当作专家规则 |

本审计不判断专家科学内容是否正确，也不授权代码、Dify、G0 或部署变更。

## 3. 盘点范围与量化结果

- 当前文档检查器纳入 71 份 Markdown；本审计文件新增后应为 72 份。
- `docs/project/stages/p0/` 共有 24 份 Markdown，其中 17 份是明确的旧版本、V06 分批材料或
  S-07 历史资料，占 71%。
- 在 13 份仍处于默认控制面的入口、状态、计划、治理、P0 说明、数据契约和运行手册中，
  有 263 行命中 `S-07`、`S07_`、`P0-M1B`、`v0.5`、`v0.6` 或 `V06`。这是污染指示量，
  不是对每行是否应删除的最终裁决。
- 发现 1 组完全重复 Markdown：两份一期 18 节点图 SHA-256 均为
  `EE4A3E5DFA85F9E19EDA60EDB46BFD6735A2233CBD4D94038D6100A7C66E3F87`。
- 当前专家目录物理上有 22 个文件；旧差异清单只记录原二次交付的 21 个文件。新增的一期图
  来源于用户，不应被误写成博士原始交付的一部分。
- 发现至少 4 组把“v0.6”标签链接到当前 `P0_IMPLEMENTATION_PLAN.md`（现为 v0.7）的高风险引用。
- `scripts/check_docs.py` 仍强制要求 `S07_DECISION_REPORT.md` 和 `S07_CONTRACT_REVIEW.md` 位于
  当前 P0 路径，后续归档前必须解除该耦合。

## 4. 风险分级

| 级别 | 含义 | 清理原则 |
|---|---|---|
| P0 | 会直接让当前开发或 AI 走错计划、读错权威文件 | 先修引用和当前入口，再做其他整理 |
| P1 | 当前文档混入大量历史，容易在搜索、摘要或上下文压缩时造成误判 | 第一轮归档同步瘦身 |
| P2 | 已有历史标记，但目录或索引仍显得杂乱 | 在迁移依赖解除后归档 |
| P3 | 纯证据、冻结基线或独立项目，默认导航隔离即可 | 不因“看起来旧”而删除 |

## 5. 主要问题清单

| ID | 级别 | 对象 | 审计发现 | 建议动作（均未执行） |
|---|---|---|---|---|
| `AUD-001` | P0 | `docs/project/README.md` L100–101 | 仍指导接手者读取 v0.6/S-07，并写“生产实施须满足 v0.6 门禁”，与当前 v0.7 冲突 | 改为只指向 P0 当前索引、v0.7 和 V07-M1；历史只留一个入口 |
| `AUD-002` | P0 | v0.6 评审、`OPEN_ITEMS.md` L423、`P0_TOOL_GUIDE.md` L337 及多份 S-07 文档 | 链接文字写 v0.6，目标却是当前 v0.7 文件 | 归档前统一改指 `P0_IMPLEMENTATION_PLAN_v0.6_ARCHIVE.md`，禁止历史文档链接漂移 |
| `AUD-003` | P0 | `STATUS.md` | 236 行中包含完整 S-07 任务 2～6、旧 P0-M1/M1B 与 v0.5/v0.6 过程；“当前状态”实际兼任变更日志 | 保留约 50～80 行当前快照；历史完成过程迁入只读 changelog |
| `AUD-004` | P0 | `ROADMAP.md` L98 起 | “近期执行顺序”先列出二十余个已完成历史步骤，再到当前 V07-M1 | 仅保留当前点向前的路线；已完成里程碑移入 changelog/历史路线图 |
| `AUD-005` | P1 | `OPEN_ITEMS.md` | 507 行同时保存开放项、已决定项、延期项、S-07 任务史、v0.6 评审史和范围决定全文 | 拆为当前开放项、当前有效决定、历史决策日志；保留 OI ID，不重编号 |
| `AUD-006` | P1 | P0 目录 | 24 份 Markdown 中 17 份历史文件与当前 7 份资料平铺/近似平铺 | 建立 `history/`，当前目录只保留索引、范围、v0.7、当前 backlog、当前依据与说明 |
| `AUD-007` | P1 | `P0_EXPERT_EVIDENCE_MATRIX.md` | 标题为当前 v0.7，但正文仍含完整 S-07 历史段和旧问题迁移；来源 JSON 仍是 2026-09-02 快照 | 生成纯四步骤当前矩阵；S-07 段归档；为 v0.7 另建当前来源清单，旧 JSON 原样保留 |
| `AUD-008` | P1 | `P0_TOOL_GUIDE.md` | 当前工具说明中有整章 S-07、整章 S-06 和三组历史比较 | 当前版只说明 S-08/S-09/S-04/S-11；排除能力移入历史说明或单独附录 |
| `AUD-009` | P1 | 根 `README.md`、`docs/README.md`、`docs/project/README.md`、P0 `README.md` | 默认导航逐项列举 S-07 任务、契约、决策和验收，历史材料反而比当前计划更显眼 | 四个入口都只保留一个“历史证据入口”，不再逐文件展开 |
| `AUD-010` | P1 | 两份一期图 | 内容与哈希完全相同；当前链接一部分指业务依据根目录，一部分指专家目录 | 先决定专家目录版本为导航正本；迁移约 15 处外层引用后，再单独批准删除或保留指针 |
| `AUD-011` | P1 | 专家索引与旧 manifest | 索引仍写“当前包 21 个文件”，实际目录 22 个；旧 manifest 的 21 个是当时专家交付快照 | 不改旧 manifest；新建当前目录清单，明确“21 个专家交付原件 + 1 个用户范围原件” |
| `AUD-012` | P1 | `工作流设计/02-数据契约/...v0.1.md` | 冻结 Mock v0.1、旧全链映射与当前生产迁移口径在同一文档 | 保留为 Mock 基线；M1/M6 另建生产契约，默认生产导航不再进入旧 Mock 全表 |
| `AUD-013` | P1 | `scripts/check_docs.py` | `REQUIRED_DOCUMENTS` 把两个 S-07 历史文件固化为必需当前文档 | 归档时改为要求当前 SSOT 和一个 history 索引；链接仍全量检查 |
| `AUD-014` | P1 | `AGENTS.md` 与 `工具部署/` | AGENTS 把 `工具部署/` 放进 T-01 默认真实工具路线，但该目录自己的 README 明确声明它是独立部署项目 | 从默认 T-01 路由移除；只在用户明确切换部署项目时进入，不混用其服务器决策 |
| `AUD-015` | P2 | `P0_IMPLEMENTATION_PLAN.md` | 当前计划仍保留整章 v0.6 迁移表和大量历史防误用说明 | 当前入口稳定后压缩为一个历史指针；保留必要的排除项，不复制迁移过程 |
| `AUD-016` | P2 | `P0_IMPLEMENTATION_PLAN_V0_7_REVIEW.md` | 是有效的 M0 评审证据，但不应长期与当前实施入口并列 | 保留不可变评审证据，迁入 `reviews/` 或由当前计划单向引用 |
| `AUD-017` | P2 | `EXPERT_V10_5_REVISION_REVIEW_20260902.md` + manifest | 是 21 个专家文件的历史差异快照，正文仍含当时 P0 五步骤/OI 状态 | 未决事项映射到当前 OI 后移入治理历史；manifest 原样保留 |
| `AUD-018` | P3 | `discovery/p0/s07/`、Mock 回归资产 | 已退出当前生产路线，但属于可复核原始证据和冻结回归 | 保留原路径或统一历史入口；不删除、不作为当前计划输入 |

## 6. 当前控制面：保留但需要瘦身或校正

| 文件 | 建议分类 | 后续处理重点 |
|---|---|---|
| `AGENTS.md` | `KEEP_CURRENT / CORRECT_ROUTE` | 保留全局导航；解除默认进入独立 `工具部署/` 项目的路由 |
| `README.md` | `KEEP_CURRENT / TRIM` | 只保留产品、成熟度和当前方向；移除 S-07 任务 5/6 细节 |
| `docs/README.md` | `KEEP_CURRENT / TRIM` | 单一事实来源表不再逐项列 S-07 历史文件 |
| `docs/project/README.md` | `KEEP_CURRENT / REWRITE` | 目录树只展示当前资料和一个 history 入口；修复 v0.6 指令 |
| `工作流设计/01-业务依据/README.md` | `KEEP_CURRENT / REPAIR_PROVENANCE` | 默认链接专家目录内一期图；区分 21 个专家原件和用户新增范围原件 |
| `docs/project/overview/STATUS.md` | `KEEP_CURRENT / SPLIT_HISTORY` | 改为真正的当前快照；历史过程进入 changelog |
| `docs/project/overview/ARCHITECTURE.md` | `KEEP_CURRENT` | 未发现需因本次历史清理而归档的理由 |
| `docs/project/planning/PHASE1_SCOPE_REBASELINE.md` | `KEEP_CURRENT` | 一期范围派生 SSOT；只保留必要来源与影响，不展开历史实施过程 |
| `docs/project/planning/ROADMAP.md` | `KEEP_CURRENT / FORWARD_ONLY` | 以 V07-M1 为当前起点，只描述后续路线和少量完成摘要 |
| `docs/project/planning/STAGE_DELIVERY_PLAN.md` | `KEEP_CURRENT / TRIM` | 保留 P0-P7 范围和门禁；S-07 历史压成一行排除说明 |
| `docs/project/governance/OPEN_ITEMS.md` | `KEEP_CURRENT / SPLIT` | 默认只展示仍需动作的 OI；DECIDED/DEFERRED 进入专门视图 |
| `docs/project/stages/README.md` | `KEEP_CURRENT` | 只列已启动阶段；不预建空阶段目录 |
| `docs/project/stages/p0/README.md` | `KEEP_CURRENT / REWRITE` | 当前文件逐项列出；历史只指向一个 P0 history 索引 |
| `P0_SCOPE_REBASELINE.md` | `KEEP_CURRENT` | 当前 P0 范围入口 |
| `P0_IMPLEMENTATION_PLAN.md` | `KEEP_CURRENT / TRIM` | 当前 v0.7 实施计划；压缩旧版迁移章节 |
| `P0_IMPLEMENTATION_PLAN_V0_7_REVIEW.md` | `KEEP_EVIDENCE` | M0 评审证据，不作为日常计划入口 |
| `P0_V07_M1_BACKLOG.md` | `KEEP_CURRENT` | 当前唯一任务台账 |
| `P0_EXPERT_EVIDENCE_MATRIX.md` | `KEEP_CURRENT / SPLIT` | 只保留四步骤当前依据；S-07 历史另存 |
| `P0_EXPERT_EVIDENCE_SOURCES_20260902.json` | `PRESERVE_SNAPSHOT / REGENERATE_CURRENT` | 原文件不覆盖；另建匹配 v0.7 的当前来源清单 |
| `P0_TOOL_GUIDE.md` | `KEEP_CURRENT / TRIM` | 当前版只讲四步骤；删除默认阅读中的 S-07/S-06 长章 |
| 数据契约 v0.1 | `KEEP_FROZEN_MOCK / REPLACE_FOR_PRODUCTION` | 不破坏 Mock 基线；生产契约另升版 |
| `docs/development/RUNBOOK.md` | `KEEP_CURRENT / EXTRACT_LEGACY_COMMANDS` | S-07 历史命令移到历史运行说明，主手册只留当前操作 |

## 7. 文件级历史处置候选

以下均只是建议，不表示已获移动或删除授权。

| 文件/组 | 建议分类 | 归档前置条件 |
|---|---|---|
| `P0_IMPLEMENTATION_PLAN_v0.5_ARCHIVE.md` | `ARCHIVE_P0_VERSION` | 修复入链；保留原文与哈希 |
| `P0_IMPLEMENTATION_PLAN_v0.6_ARCHIVE.md` | `ARCHIVE_P0_VERSION` | 增加外层归档索引说明其已被 v0.7 替代，不改原文 |
| `P0_IMPLEMENTATION_PLAN_V0_6_REVIEW.md` | `ARCHIVE_P0_VERSION` | 把错误目标链接改到 v0.6 archive |
| `P0_V06_M1_BACKLOG.md` | `ARCHIVE_AFTER_MIGRATION` | 确认仍有效的 Q08/Q09、OI-015/Q12/Q13 已进入 V07-M3/M5 |
| `m1/README.md` | `ARCHIVE_AFTER_MIGRATION` | 与四个旧批次一并迁移 |
| `m1/M1_03_BATCH_A_S07.md` | `ARCHIVE_S07` | 无当前依赖；未来恢复 S-07 时从历史入口读取 |
| `m1/M1_03_BATCH_B_S09.md` | `ARCHIVE_AFTER_MIGRATION` | 先建立 V07-M3 当前材料，不能只在旧批次中保留规则冲突 |
| `m1/M1_03_BATCH_C_S11.md` | `ARCHIVE_AFTER_MIGRATION` | 先建立 V07-M5 当前材料，保留 OI-015/R-58 追溯 |
| `m1/M1_03_BATCH_D_SCOPE.md` | `ARCHIVE_SCOPE_HISTORY` | 范围决定已进入当前基线和 OI-019 决定记录 |
| `S07_IMPLEMENTATION_TASKS.md` | `ARCHIVE_S07` | 由单一 S-07 history 索引承接 |
| `S07_LOCAL_DATA_AND_RUNTIME_PLAN.md` | `ARCHIVE_S07` | 解除与当前部署计划的交叉引用 |
| `S07_EXPERT_CONFIRMATIONS.md` | `ARCHIVE_S07` | OI-018 保留重启条件，不在当前开放问题中展开五题 |
| `S07_DECISION_REPORT.md` | `ARCHIVE_S07` | 修复检查器硬依赖；历史链接改为归档内相对路径 |
| `S07_CONTRACT_REVIEW.md` | `ARCHIVE_S07` | 修复检查器硬依赖；可复用通用契约先迁入当前 M6/OI-017 材料 |
| `S07_M1B_RUN_RECORD.md` | `ARCHIVE_S07` | discovery 原始证据继续留存 |
| `S07_TASK5_RESULT_CONTRACT.md` + Schema | `ARCHIVE_AFTER_MIGRATION` | 通用状态、错误、ArtifactRef、重试语义先迁入当前生产契约 |
| `S07_TASK6_ACCEPTANCE_AND_HANDOFF.md` | `ARCHIVE_S07` | 最终 c 批次证据入口保持可达 |
| `S07_EVIDENCE_REUSE_20260902.json` | `RETAIN_S07_EVIDENCE` | 与 S-07 历史索引和 discovery 一起保留 |
| 专家二次交付 review + manifest | `ARCHIVE_GOVERNANCE_HISTORY` | 当前未决事项和当前包清单另有落点；旧 21 文件快照不可覆盖 |
| 旧 `T01_算法图_v10_20260821.md` | `RETAIN_AUTHORITY_HISTORY` | 仍用于新图未覆盖的科学细节，不能作为一期成员关系依据 |
| 旧一期边界 PDF | `RETAIN_AUTHORITY_HISTORY` | 保留原始交付承诺证据，默认范围导航不进入 |
| 业务依据根目录的一期图副本 | `DELETE_DUPLICATE_CANDIDATE` | 用户单独批准；先迁移全部引用并更新来源记录，专家目录副本哈希复核一致 |
| `discovery/p0/s07/` 全部批次 | `RETAIN_IMMUTABLE_EVIDENCE` | 不进入默认导航，不删除原始取证和失败批次 |
| Dify/Mock v0.1 基线及回归资产 | `RETAIN_FROZEN_BASELINE` | 与生产一期计划明确隔离 |

## 8. 建议的目标结构（未创建）

```text
docs/project/
├── CURRENT_BASELINE.md              # 当前有效文档的短清单与替代关系
├── overview/
│   ├── STATUS.md                    # 只保留当前快照
│   └── CHANGELOG.md                 # 历史进展
├── planning/                        # 只放当前范围、路线图、总交付计划
├── governance/
│   ├── OPEN_ITEMS.md                # 只放仍需动作的事项
│   ├── DECISIONS.md                 # 当前仍有效的决定
│   └── history/                     # 历史审阅与被替代决定
└── stages/p0/
    ├── README.md                    # 只列当前文件和一个 history 链接
    ├── 当前范围、v0.7、当前 backlog、当前依据
    ├── reviews/                     # 当前版本的不可变评审证据
    └── history/
        ├── v05-v06/
        └── s07/
```

`discovery/`、专家原件和冻结 Mock 资产保持各自证据目录，不复制进 `docs/project/history/`。

## 9. 建议执行波次（未执行）

1. **波次 0：冻结当前控制面。** 新建 `CURRENT_BASELINE.md`，只列最新范围、路线图、阶段计划、
   当前状态、P0 v0.7、V07-M1 和专家入口；任何清理都以此为回归参照。
2. **波次 1：修正会走错路的内容。** 修复 v0.6→v0.7 漂移链接、项目导航旧指令、专家 21/22
   来源表述，以及 T-01 与独立部署项目的边界。
3. **波次 2：瘦身当前入口。** 重写 STATUS、ROADMAP、根 README、docs 两级导航和 P0 索引；
   每个当前入口最多保留一个历史链接。
4. **波次 3：迁移仍有价值的旧规则。** 先建立 V07-M3、V07-M5 和生产契约承接点，再归档
   V06 B/C、任务 5 通用契约及其来源。
5. **波次 4：归档 P0 历史。** 移动 v0.5/v0.6、V06、M1-03、S-07 文档并建立单一 history 索引；
   不改归档正文，只修复必要的相对链接或用外层 manifest 记录哈希。
6. **波次 5：拆分治理和契约。** OPEN_ITEMS 与决定/历史分离；Mock v0.1 契约与新生产契约分离。
7. **波次 6：处理唯一删除候选。** 用户确认后处理外层一期图完全重复副本；其余历史证据不删除。
8. **波次 7：更新检查器并全量验证。** 当前 SSOT、history 索引、所有链接和冻结回归均通过。

## 10. 删除与不可删除边界

### 只有单独批准后才可删除

- 与专家目录版本哈希完全一致的业务依据根目录一期图副本。
- 后续审计新发现且确认无独立来源、决定、证据或恢复价值的纯临时副本。

### 不因过时而删除

- 专家交付原件及参数/校验文件；
- 用户会议截图、来源 JSON 和正式决定证据；
- discovery 原始请求、响应、日志、失败批次和哈希清单；
- v0.5/v0.6 正式计划、评审和阶段验收证据；
- Dify/Mock 冻结基线和与其绑定的测试；
- 已被替代但用于说明“为何改变”的正式决策记录。

这些内容的正确处置是“移出默认控制面并明确历史身份”，不是抹除。

## 11. 本轮未执行事项

- 未修改任何现有 Markdown、JSON、Schema、Python、Dify 或专家原件；
- 未移动、重命名或删除任何文件或目录；
- 未改变任何当前状态、OI、里程碑或生产门禁；
- 未创建 history、decisions、reviews 或 current baseline 目录/文件；
- 未实施代码、G0、生产适配器、部署或 Dify 工作流。

下一步应先由用户确认本清单的分类原则及波次，再单独授权具体整理范围。
