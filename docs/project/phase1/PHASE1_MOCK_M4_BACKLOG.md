# PH1-MOCK-M4 独立回归 Campaign 与 Mock v0.1 冻结 Backlog

> 实施状态：`COMPLETED / ZERO_BLOCKER / MOCK_V0.1_FROZEN`  
> 输入基线：`T01-PHASE1-MOCK-M1-BASELINE-v0.1` + `PH1-MOCK-M2 PASS` + `PH1-MOCK-M3 PASS`  
> 当前生产状态：`NOT_DEPLOYED`  
> 正式 campaign：`t01p1m-v01-reg-20260904-release-freeze-03`  
> 放行结果：`PH1-MOCK-M4 COMPLETED / MOCK_V0.1_FROZEN / PH1-REAL-W1_READY`

## 1. 目标

`PH1-MOCK-M4` 不新增业务节点、场景或科学规则，而是在一个全新的、独立的回归 campaign 中，
重新证明以下整条链路仍然闭合：

```text
M1 冻结规格
  -> M2 确定性 Mock 后端与 fixture
  -> M3 单一 generator
  -> main/debug template
  -> local_dify_1_17 binding
  -> main/debug bound
  -> Dify 1.17.0 精确 ID 导入与回读
  -> main/debug 全场景重新执行
  -> 21 组规范化 parity
  -> 四分区隔离回归
  -> Mock v0.1 冻结清单
```

M4 只有在全部阻断门禁通过后，才把严格一期 18 节点 Mock v0.1 标记为 `FROZEN`，并将
`PH1-REAL-W1` 放行为 `READY`。M4 PASS 只代表 Mock 的流程、契约、路由和工程资产已冻结，
不代表任何真实科学工具、科研结果或生产 Workflow 已部署。

## 2. 不在本工作包内

- 不实现或调用 AlphaFold3、ESMFold2、DeepTMHMM、FreeSASA 或其他真实科学工具；
- 不访问科学公网、HiMat 后端、RCSB、AlphaFold DB、UniProt 或其他生产数据源；
- 不冻结科学 payload、科学阈值、Hard Filter、Gate 判据或 Pareto 规则；
- 不关闭 OI-004、OI-010、OI-013/014、OI-015、OI-020～022；
- 不修改 M1-05 场景真值、M1-07 acceptance Catalog 或 fixture manifest 来迎合实现；
- 不修改、导入或复用旧 P0-P7 Mock、旧 generator、旧 provider、旧 25 场景或 S07；
- 不创建真实一期 Dify Workflow，不宣称 `PRODUCTION_DEPLOYED`；
- 不启动 `PH1-REAL-W1` 的生产适配器实现。M4 冻结后只放行 W1，不代替 W1。

## 3. 权威输入

执行人必须按下列顺序读取并锁定输入，不得从旧 P0-P7 反推一期行为：

1. [当前状态](../STATUS.md)与[一期交付计划](../PHASE1_DELIVERY_PLAN.md)；
2. [M1-06 命名、目录、生成、绑定与隔离](PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md)；
3. [M1-07 验收断言与 fixture manifest](PHASE1_MOCK_M1_07_ACCEPTANCE_ASSERTIONS_FIXTURE_MANIFEST.md)；
4. [M2 实现评审](PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md)及其机器结果；
5. [M3 Backlog](PHASE1_MOCK_M3_BACKLOG.md)、[M3 实现评审](PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md)
   及 M3 target/binding/import/execution 证据；
6. [当前架构](../ARCHITECTURE.md)、[决定登记](../DECISIONS.md)与[开放项](../OPEN_ITEMS.md)。

以下冻结机器资产继续分别承担唯一真值，不因 M4 运行而改写：

| 机器资产 | M4 用途 |
|---|---|
| `T01_PHASE1_MOCK_SCENARIO_CATALOG_v0.1.json` | 21 个场景的控制、节点、attempt、边和终态真值 |
| `T01_PHASE1_MOCK_ENVELOPE_SCHEMA_v0.1.json` | 请求与运行 envelope 校验 |
| `T01_PHASE1_MOCK_ASSET_REGISTRY_v0.1.json` | 2 Workflow、26 tools、provider 与路径身份 |
| `T01_PHASE1_MOCK_FIXTURE_MANIFEST_v0.1.json` | 21 案例、23 提交、22 请求变体和 checkpoint 计划 |
| `T01_PHASE1_MOCK_FIXTURE_MATERIALIZATION_v0.1.json` | 350 个 payload 的逐文件哈希闭集 |
| `T01_PHASE1_MOCK_ACCEPTANCE_CATALOG_v0.1.json` | M4 适用断言、operator、selector 与覆盖门 |
| `T01_PHASE1_MOCK_M2_ACCEPTANCE_RESULT_v0.1.json` | M2 独立通过证据，不替代 M4 实机回归 |
| `T01_PHASE1_MOCK_M3_ACCEPTANCE_RESULT_v0.1.json` | M3 放行证据，不得复制成 M4 结果 |

M1-07 `execution_matrix` 中的 `DECLARED_NOT_RUN` 是规格时点历史声明，必须保持冻结。M4 的实际
运行结论写入新的 M4 result，不能反向把 M1-07 文件改成 `PASS`。

## 4. 当前接管事实

M4 开始实施前应确认下列 M3 事实仍成立：

| 项目 | 接管基线 |
|---|---|
| Dify / DSL | 本地 Docker Dify `1.17.0` / DSL `0.7.0` |
| Workflow | main/debug 恰为 2 个，现有精确 app ID 只作实例关联 |
| 每个画布 | 59 个 Dify 节点、79 条物理边，可回读 `E001-E027` |
| Provider | `t01-phase1-mock-mcp-v01`，精确 26-tool 闭集 |
| M3 实例验收 | main/debug 各 21 案例、23 提交、4/16 checkpoint、9+44 断言、10 门禁 |
| M3 parity | 21 组全部 PASS，`global.016=PASS` |
| 隔离守卫 | 科学执行、公网科学请求、legacy 复用、HiMat 访问均为 0 |
| 当前分区回归 | 当前一期 164 项、旧 Mock 74 项、S07 41 项、113 个 Markdown 均 PASS |

上表是 M4 的接管基线，不是 M4 运行结果。实施时必须重新观测；当前一期测试和 Markdown 数量可因
M4 新增合法资产上升，应报告实际数量，不得为了保持旧数字而少收集测试或文档。旧 Mock 74 项和
S07 41 项是冻结分区，数量变化必须阻断并调查。

## 5. 实施前草稿处置

计划编写前曾误启动过实现编辑，因此工作区可能已经存在以下 M4 草稿：

- `src/t01_phase1_mock/dify/campaign.py`；
- `scripts/t01_phase1_mock/run_m4_campaign.py`；
- M4 result/freeze manifest Schema 草稿；
- `constants.py`、`paths.py`、`acceptance.py`、Dify target/import helper 中的 M4 草稿改动。

这些内容在计划时点统一标记为 `UNREVIEWED_DRAFT / NOT_ACCEPTED / NOT_EXECUTED`，未被直接用于
宣称完成。M4-01 已逐项审计并修正；正式执行、负测、四分区、冻结和放行证据见
[M4 实现与冻结评审](PHASE1_MOCK_M4_IMPLEMENTATION_REVIEW.md)。历史草稿标记不反向改写。

## 6. Campaign 身份、目录与不可覆盖规则

### 6.1 Campaign ID

M4 campaign 使用 M1-06 预留格式：

```text
t01p1m-v01-reg-YYYYMMDD-{slug}
```

约束：

- 只能使用小写字母、数字和短横线组成 slug；
- campaign ID 不是 canonical `request_id`、`run_id`、`envelope_id` 或 Dify workflow run ID；
- 一个 ID 只能创建一次。失败 campaign 必须保留原证据并换新 ID，禁止清空后重跑或覆盖；
- 不得接受旧 `master-reg-*`、`MOCK-*` 或任意 P0-P7 campaign 身份。

### 6.2 证据与运行状态分离

```text
dify/t01-phase1-mock-v0.1/regression/runs/{campaign_id}/
  campaign.json
  asset-chain.json
  import-readback-evidence.json
  main/
    submissions.batch.json
    submissions.capture.json
    lifecycle.capture.json
    finalizations.batch.json
    finalizations.capture.json
  debug/
    submissions.batch.json
    submissions.capture.json
    lifecycle.capture.json
    finalizations.batch.json
    finalizations.capture.json
  checks/
    documentation.log
    current_phase1.log
    legacy_full_mock.log
    legacy_s07.log
  regression-partitions.json
  T01_PHASE1_MOCK_M4_REGRESSION_RESULT_v0.1.json

var/t01-phase1-mock-v0.1/m4-campaigns/{campaign_id}/
  main/runtime/
  debug/runtime/
```

证据目录保存可复核运行记录；`var/` 只保存可丢弃运行状态。main/debug 必须使用不同的新 runtime
root，不能因幂等键相同而共享状态。严禁读取或改名复用
`var/t01-phase1-mock-v0.1/m3-execution/` 作为 M4 运行输入。

## 7. 工作项拆分

| ID | 任务 | 主责角色 | 依赖 | 初始状态 |
|---|---|---|---|---|
| `PH1-MOCK-M4-01` | 审计草稿并冻结 campaign 协议、路径、Schema 与 fail-closed CLI | 工程 + QA | M3 PASS | `COMPLETED` |
| `PH1-MOCK-M4-02` | 重算 M1/M2/M3 输入与 generator→template→binding→bound 哈希链 | 工程 + QA | M4-01 | `COMPLETED` |
| `PH1-MOCK-M4-03` | 对精确现有 app ID 执行受控重导入并生成独立 import/readback 证据 | Dify 工程 | M4-02 | `COMPLETED` |
| `PH1-MOCK-M4-04` | 在全新 main runtime 执行 21 案例、23 提交和 4/16 checkpoint | Dify + 后端 | M4-03 | `COMPLETED` |
| `PH1-MOCK-M4-05` | 在全新 debug runtime 执行同一完整矩阵 | Dify + 后端 | M4-04 | `COMPLETED` |
| `PH1-MOCK-M4-06` | 执行 M4 的 12 条全局断言、双份 44 条焦点断言、10 门禁及 21 parity | QA + 后端 | M4-04/05 | `COMPLETED` |
| `PH1-MOCK-M4-07` | 执行隔离、安全、篡改、重复、跨 campaign 与科学边界负测 | 安全 + QA | M4-06 | `COMPLETED` |
| `PH1-MOCK-M4-08` | 运行文档、当前一期、旧 Mock、S07 四个独立回归分区并留证 | QA | M4-07 | `COMPLETED` |
| `PH1-MOCK-M4-09` | 生成冻结候选 manifest、逐文件哈希与可重复验证入口 | 发布 + QA | M4-06/07/08 | `COMPLETED` |
| `PH1-MOCK-M4-10` | 工程/算法边界/产品/Dify/发布一致性评审，冻结 v0.1 并放行 W1 | 五方评审 | M4-09 | `COMPLETED` |

M4-04 与 M4-05 逻辑上可独立，但目标 provider 复用本机端口和 Dify 实例，默认顺序执行。除非执行人
能证明 transport、runtime root 和证据写入完全隔离，否则不得并发运行 main/debug。

## 8. 各任务完成定义

### 8.1 PH1-MOCK-M4-01：Campaign 协议与执行入口

必须完成：

1. 对第 5 节列出的草稿逐文件评审；未评审代码不得进入后续执行。
2. campaign ID、证据根、runtime root、文件命名及不可覆盖策略均实现 fail closed。
3. M4 result Schema 和 freeze manifest Schema 通过 Draft 2020-12 自校验。
4. CLI 至少区分 `prepare`、生命周期驱动、结果组装、四分区回归、freeze 和只读 verify。
5. 未知 role、非法 campaign ID、既有 campaign 根、越界路径、symlink/junction 和 legacy 路径均拒绝。
6. `prepare` 只建立新 campaign 与请求批次，不得把任务状态直接改为 PASS/FROZEN。

验收：协议单测与负测通过；没有 Dify 调用、科学执行或 M4 完成声明。

### 8.2 PH1-MOCK-M4-02：输入与派生链复核

必须重新计算并记录：

- 21 份 M1 冻结来源 SHA-256 与 M2 机器结果中的来源锁一致；
- fixture `2 + 22 + 326 = 350`，逐文件路径、字节数和 SHA-256 不漂移；
- M2、M3 机器结果均为 `PASS / blocker=0`，但只作为输入放行证据；
- registry→generator→main/debug template→binding manifest→main/debug bound 全链；
- generator `--check` 和 binder `--check` 均只读通过；
- main/debug 模板的规范化业务图一致；
- 模板只含登记 provider token，bound 不含未解析 token、秘密、本机绝对路径或科学远程地址。

M3 接管哈希如下，M4 必须重算后比较，不得直接复制文本：

| 资产 | M3 SHA-256 |
|---|---|
| 资产注册表 | `ea851f97cacb304a2927d45ef85363d7c44b49f792b10172bfe7792f960672a2` |
| main template | `d14037d202b8cb715560ed9fd1302867796ab7db2d54e3d2d673f8d9626a7e61` |
| debug template | `09162ff71fad27340ce08e1b73dd4a2caa3b0cdba8a013830c541e6d2a6332f3` |
| binding manifest | `025d5859b01befbc77540a4d32a0ef01479c34484af481a615cf8b126395855a` |
| main bound | `c1bcbb1f2a156d79ac3fcd592c08e5415ca5b671c2e47c339672c11567b48fa6` |
| debug bound | `d7883fbc19ff6aa66a875e7fb60f88be2ce46945c4b919c4057332f71752ad1b` |

任一差异都必须停止并定位来源；不得在 M4 内静默重写模板、bound 或冻结规格。

### 8.3 PH1-MOCK-M4-03：目标重导入与回读

执行前必须再次确认：

- transport 健康检查为 `status=ok`、`tool_count=26`、`mock_only=true`、
  `scientific_compute=false`；
- Dify 版本仍为 1.17.0，DSL 为 0.7.0；
- provider 精确为 `t01-phase1-mock-mcp-v01` 且 26 tools 全集一致；
- main/debug 现有应用各只有一个，app ID 与 M3 证据完全一致。

只允许对 M3 已登记的精确 app ID 做显式授权更新。名称碰撞、ID 变化、重复应用或 provider 漂移时
立即停止；不得自动创建第三个同名应用、覆盖未知应用、删除应用或修改 provider 凭据。

独立 M4 import/readback 证据必须记录：bound 哈希、app/workflow ID、无秘密 export 哈希、source/
readback semantic graph 哈希、59/79 数量、`E001-E027`、26 tools、warning 数和导入状态。M3 的
`import-evidence.json` 只能提供预期身份，不能复制为本任务结果。

### 8.4 PH1-MOCK-M4-04：Main 全量回归

在新的 main runtime root 中执行：

- 21 个具名场景；
- 23 次 canonical submission；
- 22 个唯一请求变体；
- 4 份 checkpoint plan、16 个固定步骤；
- 4 次仅用于观察终态的 finalization，不计入 canonical submission；
- 每次 Dify workflow run ID 与 canonical request/run/envelope ID 分离记录。

必须保留幂等重放、幂等冲突、取消、恢复和超时的原始执行顺序。传输层短暂失败如需重试，必须
保存原失败 capture、重试 capture、合并依据和重试次数；重试不得增加 canonical submission，
也不得删除失败证据后伪装成一次成功。

### 8.5 PH1-MOCK-M4-05：Debug 全量回归

使用全新的 debug runtime root，重复 M4-04 的完整矩阵。不得读取 main runtime 的 idempotency
索引、run record 或 Artifact。debug 只允许增加已冻结的可观察信息，不得改变业务控制、节点终态、
边、错误或最终 envelope。

M4-04 与 M4-05 都必须有各自 23 个 submission Dify run 和 4 个 finalization Dify run；同一角色
内部 Dify run ID 必须唯一，且不得等于 canonical run ID。

### 8.6 PH1-MOCK-M4-06：M4 断言、门禁与 parity

M4 必须从冻结 Catalog 执行以下 12 条全局断言，不允许硬编码 `PASS` 或使用 `prechecked` 旁路：

```text
global.004
global.008
global.009
global.010
global.011
global.012
global.013
global.014
global.015
global.016
global.017
global.018
```

每条断言都必须实际走 `selector → expected/source_selector → operator → result`。其中：

- `global.015` 从资产注册表和目标回读比较 2 Workflow、provider 与 26 tools；
- `global.016` 比较 21 组 main/debug 规范化 canonical envelope；
- `global.018` 以 `[21 executed cases, 23 executed submissions, 0 blocker failures]` 收口；
- 缺 selector、未知 operator、类型不符或预期源不可解析一律为 blocker failure。

同时执行 main/debug 各 44 条焦点断言和 10 个覆盖门。parity 只能删除 M3-02 明确允许的
`dify_observability` 字段；首个差异必须输出 JSON Pointer，不能扩大忽略列表来通过。

### 8.7 PH1-MOCK-M4-07：隔离、安全与负向门禁

至少覆盖：

1. 非法、旧前缀、大小写错误和越界 campaign ID 拒绝；
2. 已存在 campaign 目录拒绝覆盖；
3. capture 的 campaign、role、app、计数、顺序、Dify run ID 重复或失败状态篡改均拒绝；
4. asset-chain、binding、bound、readback 或结果哈希漂移均拒绝冻结；
5. main/debug runtime 互相引用、M3 runtime 复用、legacy/S07 路径或 import 出现时拒绝；
6. 未解析 token、秘密样式字段、凭据、Cookie、本机绝对绑定或科学远程 URL 为 0；
7. 所有结果保持 `MOCK_DATA`、`scientific_compute=false`、handoff `NOT_DEPLOYED`；
8. 科学执行、科学公网请求、legacy 实现复用、HiMat 后端访问均为 0；
9. N01 不产生 RCSB/AFDB/外部结构 ID 或远程 fallback；
10. freeze 前结果失败、分区缺失或 blocker 非零时，freeze 命令必须失败且不写出 FROZEN manifest。

### 8.8 PH1-MOCK-M4-08：四分区回归

最终代码和文档稳定后，从各自边界独立运行：

```powershell
.\.venv\Scripts\python.exe .\scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q

Push-Location .\legacy\full-t01-mock-v0.1
..\..\.venv\Scripts\python.exe -m pytest -q
Pop-Location

Push-Location .\legacy\s07
..\..\.venv\Scripts\python.exe -m pytest -q
Pop-Location
```

四个分区必须分别记录命令、相对工作目录、退出码、实际通过数和输出哈希。不得把测试数相加后
冒充一期功能数量。当前一期测试数和 Markdown 数应按最终实际值报告；旧 Mock 必须仍为 74 项，
S07 必须仍为 41 项。

### 8.9 PH1-MOCK-M4-09：冻结 Manifest

冻结候选至少包含：

- release ID、版本、campaign ID、binding profile 和冻结时间；
- M1 来源、M2/M3 输入、当前源码、脚本、测试、Schema、fixture、模板、binding、bound、M4
  campaign 证据的相对路径、字节数和 SHA-256；
- 21/23、4/16、12 条全局断言、双份 44 条焦点断言、10 门禁、21 parity 与 0 blocker；
- 四分区实际结果；
- `MOCK_DATA`、`scientific_compute=false`、科学/公网/legacy/HiMat/secret 计数为 0；
- `production_state=NOT_DEPLOYED` 和 `next_release_gate=PH1-REAL-W1_READY`。

运行状态、缓存、凭据、Dify 数据库、Docker volume 和本机绝对路径不得进入冻结资产。manifest
必须有独立 Schema 和只读 `verify` 入口；任一登记文件缺失或哈希变化都返回失败。

### 8.10 PH1-MOCK-M4-10：一致性评审与状态切换

必须给出五项具名结论：

1. **工程一致性**：单一生成源、派生链、实例回读、运行证据和冻结哈希闭合；
2. **算法边界**：控制仅来自 `SCENARIO_LITERAL`，无科学计算、Hard Filter、Gate 推断或 Pareto；
3. **产品范围**：只含 N01-N18/E001-E027、默认完整 profile 和已冻结排除项；
4. **Dify 完整性**：两个应用、26 tools、main/debug 全量运行和 parity 全部通过；
5. **发布边界**：冻结的是 Mock v0.1，不是生产工具或真实 Workflow。

仅当五项均 PASS、M4 机器 blocker 为 0、四分区全部通过且 freeze manifest 可只读复核时，才允许：

- 将 M4 标记为 `COMPLETED`；
- 将 `T01-PHASE1-MOCK-v0.1` 标记为 `FROZEN`；
- 将 `PH1-REAL-W1` 标记为 `READY`；
- 更新 `STATUS.md`、`ARCHITECTURE.md`、`ROADMAP.md`、一期交付计划、一期索引和运行手册。

任何一项失败时保持 `M4_NOT_COMPLETED / MOCK_NOT_FROZEN / PH1-REAL-W1_BLOCKED`。

## 9. 机器验收总表

| 门禁 | 冻结要求 |
|---|---|
| Campaign 隔离 | 新 ID、新 evidence root、新 main/debug runtime；M3/legacy/S07 复用为 0 |
| 派生链 | M1→M2→generator→template→binding→bound 哈希闭合且无漂移 |
| 目标回读 | Dify 1.17.0/DSL 0.7.0；2 应用；每画布 59 节点/79 边；E001-E027；26 tools |
| Main | 21 案例、23 submission、4/16 checkpoint、44 focus，全 PASS |
| Debug | 21 案例、23 submission、4/16 checkpoint、44 focus，全 PASS |
| 全局断言 | M4 适用 12 条全部实际执行并 PASS |
| 覆盖门 | 10 个具名门禁全部 PASS |
| Parity | 21 组规范化结果全部一致；`global.016=PASS` |
| 收口计数 | `global.018=[21,23,0]` |
| 科学边界 | `MOCK_DATA`、`scientific_compute=false`、科学执行/公网请求为 0 |
| 隔离边界 | legacy 复用、HiMat 访问、秘密发现均为 0 |
| 分区回归 | 文档、当前一期、旧 74、S07 41 分别 PASS |
| 冻结验证 | manifest Schema PASS，全部登记文件路径/字节/SHA-256 可重算 |

以上全部为 blocker，不允许 warning-only 放行。

## 10. 计划交付物

| 交付物 | 计划路径 |
|---|---|
| M4 Backlog | `docs/project/phase1/PHASE1_MOCK_M4_BACKLOG.md` |
| M4 实现与冻结评审 | `docs/project/phase1/PHASE1_MOCK_M4_IMPLEMENTATION_REVIEW.md` |
| M4 result Schema | `dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_M4_REGRESSION_RESULT_SCHEMA_v0.1.json` |
| 单次 M4 result | `dify/t01-phase1-mock-v0.1/regression/runs/{campaign_id}/T01_PHASE1_MOCK_M4_REGRESSION_RESULT_v0.1.json` |
| 单次 campaign 全证据 | `dify/t01-phase1-mock-v0.1/regression/runs/{campaign_id}/` |
| freeze manifest Schema | `dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_FREEZE_MANIFEST_SCHEMA_v0.1.json` |
| Mock v0.1 freeze manifest | `dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_FREEZE_MANIFEST_v0.1.json` |
| M4 执行入口 | `scripts/t01_phase1_mock/run_m4_campaign.py` |
| M4 实现逻辑 | `src/t01_phase1_mock/dify/` 内当前一期独立模块 |
| M4 测试 | `tests/t01_phase1_mock/` 内 campaign、篡改、隔离、结果与冻结验证测试 |

方括号变量只在 M4 实施时物化。已有同名草稿不代表交付物已验收。

## 11. 执行顺序与交接规则

```text
M4-01 协议/草稿审计
  -> M4-02 哈希链
  -> M4-03 目标重导入/回读
  -> M4-04 main 全量执行
  -> M4-05 debug 全量执行
  -> M4-06 断言/门禁/parity
  -> M4-07 隔离与负测
  -> M4-08 四分区回归
  -> M4-09 冻结 manifest
  -> M4-10 五方评审与状态切换
```

每项交接必须提供：实际产物、机器可读结果、执行命令、计数、哈希、失败数和剩余 blocker。不得只用
自然语言“已完成”替代证据，也不得在 M4-10 前提前修改状态为 FROZEN。

## 12. M4 完成后的下一任务

M4 完成后只放行 `PH1-REAL-W1`。W1 从 N01-N02 的 G0 事实摸底开始：实测本地
AlphaFold3/ESMFold2、S-09 结构标准化、DeepTMHMM 和条件 FreeSASA 的版本、输入输出、资源、
许可证、原始产物、错误与断网行为。未完成 G0/G1 前，不得把 Mock stub 直接替换为生产调用。
