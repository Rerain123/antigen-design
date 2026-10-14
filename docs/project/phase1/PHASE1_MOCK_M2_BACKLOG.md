# PH1-MOCK-M2 确定性 Mock 后端与场景引擎实现 Backlog

> 状态：`COMPLETED / ACCEPTANCE_PASS / M3_M4_COMPLETED / MOCK_V0.1_FROZEN`  
> 建立日期：2026-09-04  
> 上级计划：[一期 18 节点交付计划](../PHASE1_DELIVERY_PLAN.md)  
> 冻结输入：`T01-PHASE1-MOCK-M1-BASELINE-v0.1`  
> 当前工作项：`PH1-REAL-W1 READY`  
> 本包只实现离线确定性 Mock 后端；Dify DSL 属于 M3，真实科学能力属于 `PH1-REAL-W1～W7`。

## 1. 目标

把已冻结的 M1 规格落实为一套可运行、可复核、可被 M3 复用的一期 Mock 后端：

- 严格覆盖 `N01-N18`、`E001-E027`、Gate、WT 分支、N12 重算、N16 条件执行及
  N16/N17→N18 汇合；
- 用同一个场景 Catalog 精确投影 21 个案例、23 次提交、334 个 attempts 与全部运行终态；
- 物化 synthetic fixture，并以 Schema、路径和 SHA-256 建立闭集追踪；
- 提供 M1-06 登记的 26 个 Mock 工具及离线可调用入口；
- 执行 `M2_BACKEND` 适用的 9 条全局断言和 44 条焦点断言，10 个覆盖门禁全部闭合；
- 为 M3 提供唯一后端真值，但不创建、绑定或导入 Dify Workflow。

“确定性”指相同场景产生相同控制、节点、attempt、边、错误和规范化结果；UUIDv4 只作不透明身份，
不得参与场景选择或路由。Mock 只验证工程契约，不验证任何科学结论。

## 2. 当前起点与接管规则

M1 已完成且冻结。M2 建立时出现的候选源码、测试、fixture payload 和机器结果已按本 backlog
逐项接管；`M2-01～09` 均通过自身测试、机器结果和最终评审，不再以文件存在或自报状态推断完成度。

计划建立时发现 materialization Schema 已要求顶层 `source_sha256`、旧索引却未同步，曾导致
**107 项收集、7 PASS、100 ERROR**。M2-01 已保留该接管轨迹并闭环：重新从冻结 M1 来源生成
21 项 SHA-256 锁，重建索引和 payload 后 `--check`、全量测试与机器验收均通过。详细证据见
[M2 实现评审](PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md)。

冻结 M1 资产为只读输入。若实现发现 M1 语义矛盾，必须停止受影响工作项、登记 finding，并按
M1-08 规则重新打开和升版；不得静默修改 v0.1 Catalog、manifest、Schema 或示例来迎合代码。

## 3. 冻结输入与读取顺序

M2 实现者必须按 M1-08 放行顺序读取并校验以下资产：

| 顺序 | 冻结输入 | M2 使用方式 |
|---:|---|---|
| 1 | [M1-02 节点注册表](PHASE1_MOCK_M1_02_NODE_REGISTRY.md)与[M1-03 控制流](PHASE1_MOCK_M1_03_CONTROL_FLOW_STATE_GRAPH.md) | 固定 18 节点、27 条边、9 个节点状态及责任边界 |
| 2 | [M1-04 envelope 契约](PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md)与[机器 Schema](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_ENVELOPE_SCHEMA_v0.1.json) | 校验请求、运行、节点、ArtifactRef、错误、审计和追踪外壳 |
| 3 | [M1-05 场景模型](PHASE1_MOCK_M1_05_DETERMINISTIC_SCENARIO_MODEL.md)、[Catalog](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_SCENARIO_CATALOG_v0.1.json)及其[Schema](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_SCENARIO_CATALOG_SCHEMA_v0.1.json) | 作为控制、节点、attempt、边和终态的唯一 expected source |
| 4 | [M1-06 资产隔离规范](PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md)、[注册表](../../../工作流设计/03-Dify实现/T01_PHASE1_MOCK_ASSET_REGISTRY_v0.1.json)及其[Schema](../../../工作流设计/03-Dify实现/T01_PHASE1_MOCK_ASSET_REGISTRY_SCHEMA_v0.1.json) | 固定 namespace、2 个 Workflow 身份、26 个工具、21 个 scenario_ref 和路径边界 |
| 5 | [M1-07 fixture 规格](PHASE1_MOCK_M1_07_ACCEPTANCE_ASSERTIONS_FIXTURE_MANIFEST.md)、[manifest](../../../dify/t01-phase1-mock-v0.1/fixtures/T01_PHASE1_MOCK_FIXTURE_MANIFEST_v0.1.json)及其[Schema](../../../dify/t01-phase1-mock-v0.1/fixtures/T01_PHASE1_MOCK_FIXTURE_MANIFEST_SCHEMA_v0.1.json) | 冻结 2/22/23/378/334/326/8 与 4/16 的物化和提交闭集 |
| 6 | [acceptance Catalog](../../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_ACCEPTANCE_CATALOG_v0.1.json)及其[Schema](../../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_ACCEPTANCE_CATALOG_SCHEMA_v0.1.json) | 冻结 selector、28 个 operator、断言、案例、门禁及执行矩阵 |
| 7 | [M1-08 一致性评审](PHASE1_MOCK_M1_08_CONSISTENCY_REVIEW.md) | 继承映射、已解决 finding、未决项隔离和 M2 停止线 |

M2-01 应记录上述文件的 SHA-256 与版本链，后续每次验收先做 preflight；任一文件缺失、版本错配、
重复 JSON key、Schema 失败或冻结哈希意外变化时立即失败，不继续生成 payload 或运行场景。

## 4. 范围边界

### 4.1 M2 包含

- `t01_phase1_mock` Python 包、严格规格加载器、fixture materializer/repository；
- Catalog 精确投影器、运行生命周期、幂等、取消、超时、恢复和本地状态存储；
- M1-04 envelope、ArtifactRef、错误、审计和逐边追踪实现；
- 26 个登记工具的 transport-neutral facade，以及供 M3 对接前验证的离线本地调用面；
- selector 规范化适配器、28 个 operator、M2 acceptance harness 和负向门禁；
- synthetic payload、物化索引、M2 机器结果及实现评审记录。

### 4.2 M2 不包含

- `src/t01_phase1_mock/dify/generator.py`、Dify YAML、template、binding、bound 或导入证据；这些属于 M3；
- `regression/runs/{campaign_id}/`、main/debug parity 或 Mock v0.1 冻结；这些属于 M4；
- 任何真实科学程序、模型、数据库、远程请求、生产 Worker、真实 Agent C 或科研候选；
- 对 Gate、Hard Filter、Pareto、N12/N15/N16/N17/N18 决策的计算或从 fixture 内容反推；
- 对 `legacy/full-t01-mock-v0.1/`、`legacy/s07/` 或旧 `MOCK-*` 场景的导入、复制或写入；
- 对未决科学字段、阈值、字母表、生产失败策略或 Agent C 契约的猜测补齐。

## 5. 工作项与依赖

| 工作项 | 交付内容 | 依赖 | 当前状态 | 完成证据 |
|---|---|---|---|---|
| `PH1-MOCK-M2-01` | 接管现有草稿、建立包/测试骨架和冻结规格 preflight | M1 baseline | `COMPLETED` | 21 份冻结来源 SHA-256、五组契约、四个示例、版本/数量/引用及负向读取测试通过 |
| `PH1-MOCK-M2-02` | 物化 2 个输入、22 个请求和 326 个 attempt payload，建立物化索引 | M2-01 | `COMPLETED` | 350 个 payload 闭集字节可复建；索引逐文件记录数据分类；synthetic 结构字节内嵌；8 个 null key 无文件 |
| `PH1-MOCK-M2-03` | 实现 21 场景 exact projection 核心 | M2-02 | `COMPLETED` | 378 个节点终态、334 个 attempts、边、控制和 expected run 逐项等于 Catalog |
| `PH1-MOCK-M2-04` | 实现提交、幂等、checkpoint、取消、超时、恢复与存储 | M2-03 | `COMPLETED` | 23 次提交和 4 份/16 步 checkpoint 按字面量推进；重启、损坏和非法转换测试通过 |
| `PH1-MOCK-M2-05` | 实现 envelope、ArtifactRef、错误、审计和引用闭合 | M2-04 | `COMPLETED` | 请求、checkpoint 与终态通过 M1-04 Schema；Artifact 字节/哈希和全部引用闭合 |
| `PH1-MOCK-M2-06` | 实现 26-tool facade 与离线本地调用入口 | M2-05 | `COMPLETED` | 1 initialize + 18 node + 6 control + 1 finalize 精确枚举并本地调用；未知工具和跨场景绑定拒绝 |
| `PH1-MOCK-M2-07` | 实现 selector adapter、28 operator 与 acceptance harness | M2-06 | `COMPLETED` | 九根 selector、28 operator、9 条全局与 44 条焦点断言均走 Catalog selector→expected→operator；变异测试 fail closed |
| `PH1-MOCK-M2-08` | 执行全案例、负向门禁与三分区回归，生成 M2 机器结果 | M2-07 | `COMPLETED` | 21 案例/23 提交、10 门禁、0 blocker；当前、旧 74、S07 41 分区通过 |
| `PH1-MOCK-M2-09` | 工程/算法边界/产品范围一致性评审并放行 M3 | M2-08 | `COMPLETED` | [M2 实现评审](PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md)四项结论通过；仅 M3 置为 READY |

依赖链固定为：

```text
M2-01 -> M2-02 -> M2-03 -> M2-04 -> M2-05 -> M2-06 -> M2-07 -> M2-08 -> M2-09
```

如果已有草稿一次覆盖多个工作项，仍须按此顺序补齐并记录各自证据；不得因为代码已经存在而跳过
前置规格校验、fixture 闭集、负向测试或独立评审。

## 6. 逐项实施说明

### 6.1 PH1-MOCK-M2-01：接管审计与规格 preflight

实施内容：

1. 盘点 `src/t01_phase1_mock/`、`tests/t01_phase1_mock/`、`scripts/t01_phase1_mock/` 和当前一期
   fixture/regression 根，区分 M1 冻结资产、M2 草稿与禁止的 M3/M4 资产；
2. 使 Python 包在干净环境中可导入，并在 `pyproject.toml` 明确声明实际运行/测试依赖；
3. 严格读取 JSON，拒绝重复 key、未知顶层版本、缺失 Schema 和不受控路径；
4. 校验五组机器契约、四个 M1-04 示例、版本链、18/27/9、2/26/21、21/23/22、
   378/334/326/8、4/16、18/44/10 等冻结不变量；
5. 为每个 preflight 条件增加正向与最小负向测试，不允许捕获异常后降级继续运行。

计划代码边界：`constants.py`、`jsonio.py`、`paths.py`、`catalog.py`；业务投影不得塞入这些模块。
本项结束时仍不要求场景执行通过，但必须为后续任务提供可信、只读的 `SpecificationBundle`。

### 6.2 PH1-MOCK-M2-02：fixture 物化与闭集索引

实施内容：

1. 仅从 manifest 的 planned path 和 Catalog source pointer 生成 2 个 input、22 个 request 与
   326 个非 null attempt payload；provided-structure 的 synthetic 本地结构字节内嵌在标准 input
   payload 的 ArtifactRef 对应字段内，不另创 manifest 外文件；8 个 null key 保持无文件、无 output 引用；
2. 物化索引对全部 payload 逐文件标记 `MOCK_DATA`、`scientific_compute=false`；input/request
   还按自身 Schema 携带相同字段，attempt stub 按冻结 M1 Schema 携带 `mock_only=true` 与
   `scientific_compute=false`；只允许 synthetic transport/state stub；
3. 生成
   `dify/t01-phase1-mock-v0.1/fixtures/T01_PHASE1_MOCK_FIXTURE_MATERIALIZATION_v0.1.json`
   及对应 Schema，记录 logical key、相对路径、字节 SHA-256、来源指针和数据分类；
4. 重复构建必须字节一致；`--check` 只验证不写入，能发现缺失、多余、哈希漂移、路径逃逸、
   symlink/junction 和 matching-but-undeclared key；
5. 不修改冻结 manifest 内的 `DECLARED_NOT_MATERIALIZED` 历史状态；实际物化状态只写入 M2 新索引。

计划代码边界：`fixtures.py` 与薄脚本 `scripts/t01_phase1_mock/materialize_fixtures.py`。生成逻辑必须
在包内，脚本不能成为第二份真值。

### 6.3 PH1-MOCK-M2-03：场景精确投影核心

实施内容：

1. `scenario_ref` 只能精确映射到 21 个 Catalog key；未知、旧前缀、大小写变体和近似值均拒绝；
2. 对每个场景投影 18 个节点终态、完整 attempt 历史、实际边序列、运行终态及 Catalog 字面量；
3. 六个 `control_plan` key 只读复制；`n18_entry` 只在规范化断言视图中按 M1-07 定义呈现，
   不伪造为 M1-04 新 control decision；
4. Gate、N12、N15、N16、N17 和 N18 入口不得从 fixture、节点输出、LLM、环境或随机数计算；
5. N18 只组装已存在结果，不补算、提升或修复上游状态；失败、超时、跳过和未执行保持可区分。

计划代码边界：`projection.py`。21 个场景必须参数化测试，逐项比对 Catalog，而不是只做 happy-path
快照或抽样。

### 6.4 PH1-MOCK-M2-04：运行生命周期、幂等与离散检查点

实施内容：

1. 实现请求校验、run 创建、读取、显式事件注入、取消、恢复和终态读取；
2. 每次提交产生新 namespaced `request_id`；正常创建签发 UUIDv4 `run_id`，幂等重放复用原
   `run_id`，幂等冲突在创建新运行前拒绝且不改写原运行；
3. 四个异步场景只按 manifest 的 16 个离散步骤推进；禁止 `sleep`、墙钟到期、后台随机任务或
   轮询次数触发状态变化；
4. retry/recovery 历史只追加不覆盖，`recovery_of_run_id`、attempt 前驱、错误与原运行关系闭合；
5. 本地运行写入 `var/t01-phase1-mock-v0.1/`，测试写入临时目录；任何状态都不得写入 fixture、
   legacy、S07 或 M4 campaign 目录。

计划代码边界：`storage.py` 与 `engine.py`。进程重启后的读取、损坏记录、重复事件和非法状态转换均须
有负向测试。

### 6.5 PH1-MOCK-M2-05：envelope 与引用完整性

实施内容：

1. 在入口和终态出口执行 M1-04 Draft 2020-12 Schema 校验；内部对象不得绕过出口校验；
2. 建立节点结果、attempt、ArtifactRef、error、audit、control decision 和 edge trace 的唯一引用；
3. Artifact URI 只能使用
   `artifact://t01-phase1-mock-v0.1/{run_id}/`，后端解析物理路径，调用方不得拼本机路径；
4. Artifact 字节 SHA-256 必须对应物化 fixture；null fixture 不产生 ArtifactRef；partial/error 引用
   按 Catalog 精确保留；
5. `MOCK_DATA`、`scientific_compute=false`、`PHASE1_FULL` 与 `NOT_DEPLOYED` 标识在所有要求位置
   闭合，且没有生产可用性暗示。

计划代码边界：可由 `projection.py` 的 envelope builder 或独立 `envelopes.py` 承担，但只能有一个
规范序列化入口。

### 6.6 PH1-MOCK-M2-06：26-tool facade 与离线调用面

实施内容：

1. 从资产注册表注册且只注册 26 个工具：1 个运行初始化、18 个节点 stub、6 个控制字面量、
   1 个运行归并；
2. 节点工具只能返回对应 `node_id` 的已有投影，控制工具只返回场景字面量，finalize 只归并；
3. 未登记工具、旧 provider、旧包名、N19+、工具/节点尾号不一致和跨场景 run 均 fail closed；
4. 核心 facade 与传输解耦；提供 M3 接入前可枚举、可调用的离线本地 MCP 面或等价协议适配，
   但不执行 Dify provider 绑定、模板生成或导入；
5. 薄启动脚本只能调用包内 server/facade，不能复制工具表或场景逻辑。

计划代码边界：`tools.py`、可选 `mcp_server.py` 和
`scripts/t01_phase1_mock/serve_mock_mcp.py`。完成证据至少包含精确工具枚举和一次本地 transport smoke。

### 6.7 PH1-MOCK-M2-07：selector 与机器断言 harness

实施内容：

1. 把实现只读映射到 `catalog | fixture | acceptance | request | submission[n] | run | trace |
   workflow | original_run` 规范视图；
2. 实现 acceptance Catalog 闭集登记的 28 个 operator，不接受别名、未知 operator 或隐式类型转换；
3. 只执行 `applies_to` 包含 `M2_BACKEND` 的 9 条全局断言和全部 44 条焦点断言；18 条全局断言
   的其余阶段项不得在 M2 伪报为已运行；
4. selector 缺失、fixture 缺失、expected source 无法解析、operator 未知或 projection 不等时，
   必须形成 `BLOCKER FAIL`，不能 skip、warning 或回落默认值；
5. 断言引擎本身须有变异测试，证明它能抓住一处状态、边、哈希、身份、控制或路径偏差。

计划代码边界：`acceptance.py` 与对应测试；harness 只读取运行结果，不反向修改引擎输出。

### 6.8 PH1-MOCK-M2-08：全量执行与机器结果

实施内容：

1. 按 acceptance Catalog 顺序执行 21 个案例/23 次提交，不抽样、不并案、不替换具名场景；
2. 验证 10 个覆盖门禁、9+44 条 M2 断言、fixture/Artifact/hash 闭集和所有负向隔离规则；
3. 生成独立的
   `dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_M2_ACCEPTANCE_RESULT_v0.1.json`
   及其 Schema，记录输入版本/哈希、每案例结果、失败详情、汇总和执行环境；
4. 不修改冻结 acceptance Catalog 中的 `DECLARED_NOT_RUN` 历史声明；M2 实际执行事实只记录在
   新结果文件和 M2 评审中；
5. 分别运行当前一期、冻结旧完整 Mock 74 项和 S07 41 项回归，任何一套失败都阻断 M2 放行。

M2 机器结果不是 M4 campaign，不写入 `regression/runs/`，也不得声称 main/debug Workflow 或
main/debug parity 已通过。

### 6.9 PH1-MOCK-M2-09：一致性评审与 M3 放行

评审至少给出四项具名结论：

1. 工程一致性：规格、payload、代码、测试、机器结果和目录/哈希可追溯；
2. 算法边界：科学计算为 0，所有控制只来自 `SCENARIO_LITERAL_ONLY`；
3. 产品范围：严格 N01-N18，无旧 P0-P7/S07 回流，无生产部署暗示；
4. 后续可接入性：26-tool 调用面足以供 M3 生成两个 Workflow，且没有把 DSL 责任提前塞入 M2。

交付文档为 `PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md`。只有 blocker 为 0、M2 机器结果 PASS、
三分区回归分别通过后，才能把 M2 标记 `COMPLETED` 并将 M3 改为 `READY`；M4 与真实工具仍保持
未开始。

## 7. 最终物理交付

下列是 M2-01～09 审计后保留的实际责任边界：

```text
src/t01_phase1_mock/
  __init__.py
  constants.py
  jsonio.py
  paths.py
  catalog.py
  fixtures.py
  projection.py
  storage.py
  engine.py
  tools.py
  acceptance.py
  [mcp_server.py]

tests/t01_phase1_mock/
  conftest.py
  test_catalog_and_fixtures.py
  test_projection.py
  test_engine.py
  test_acceptance.py
  test_isolation.py
  test_operators_and_selectors.py

scripts/t01_phase1_mock/
  materialize_fixtures.py
  run_m2_acceptance.py
  [serve_mock_mcp.py]

dify/t01-phase1-mock-v0.1/fixtures/
  T01_PHASE1_MOCK_FIXTURE_MATERIALIZATION_SCHEMA_v0.1.json
  T01_PHASE1_MOCK_FIXTURE_MATERIALIZATION_v0.1.json
  inputs/                                      # 2 JSON payloads；标准输入内嵌 synthetic 结构字节
  requests/                                    # 22 payloads
  node-results/                                # 326 payloads

dify/t01-phase1-mock-v0.1/regression/
  T01_PHASE1_MOCK_M2_ACCEPTANCE_RESULT_SCHEMA_v0.1.json
  T01_PHASE1_MOCK_M2_ACCEPTANCE_RESULT_v0.1.json

docs/project/phase1/
  PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md
```

方括号文件只在对应调用面确有需要时创建；Dify generator、YAML、binding、bound 与 M4 `runs/`
明确不在本清单。

## 8. 验收门禁

| 门禁 | 必须满足 |
|---|---|
| 规格门禁 | 五组冻结机器契约及 Schema、四个 envelope 示例、版本/哈希/数量/引用链全部通过 |
| fixture 门禁 | 2 输入 + 22 请求 + 326 attempt payload，共 350 个文件；synthetic 结构内嵌；8 null 无文件；闭集无缺失、多余或漂移 |
| 投影门禁 | 21 场景、378 节点终态、334 attempts、控制、边和 expected run 与 Catalog 精确一致 |
| 生命周期门禁 | 23 提交、4/16 checkpoint、幂等、取消、超时、恢复和追加历史全部通过 |
| envelope 门禁 | 请求/运行 Schema、Artifact/error/audit/trace 引用及哈希全部闭合 |
| 工具门禁 | 26 个工具精确可枚举/调用，未知或旧身份 fail closed |
| 断言门禁 | M2 适用 9 条全局 + 44 条焦点断言、10 个覆盖门禁，0 blocker failure |
| 隔离门禁 | 无网络、科学程序、旧 import/写入、Dify DSL、M4 run 或秘密字段 |
| 回归门禁 | 当前一期全测、旧完整 Mock 74 项、S07 41 项分别 PASS |
| 评审门禁 | M2-09 四项结论通过，M1 未被静默改写，M3 才可 READY |

## 9. 退出条件

`PH1-MOCK-M2` 只有同时满足以下条件才完成：

- `M2_BACKEND` 的 21 个案例/23 次提交已真实执行，而不是继续引用 `DECLARED_NOT_RUN`；
- 9 条适用全局断言、44 条焦点断言和 10 个覆盖门禁全部 PASS，blocker 为 0；
- synthetic payload、物化索引、运行结果、测试和评审可从冻结 M1 版本与 SHA-256 追溯；
- 26 个 Mock 工具共享同一后端真值，且没有从 stub 内容推导业务控制；
- 当前一期测试、旧 74 项和 S07 41 项各自通过，旧资产没有被修改或写入；
- 没有 Dify DSL/bound/M4 campaign、真实科学调用、网络访问、生产候选或部署声明；
- [当前状态](../STATUS.md)、[一期资料索引](README.md)和[开发运行手册](../../development/RUNBOOK.md)
  已同步，M3 只在 M2-09 通过后变为 `READY`。

`PH1-MOCK-M2-01～09` 已全部完成并通过
[M2 实现评审](PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md)。其后
[M3 实施 Backlog](PHASE1_MOCK_M3_BACKLOG.md)已从本包唯一后端真值生成并验证两个 Dify Workflow，
[M3 实现评审](PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md)已通过；M4 又以独立 campaign 完成回归与
Mock v0.1 冻结，见[M4 实现与冻结评审](PHASE1_MOCK_M4_IMPLEMENTATION_REVIEW.md)。下一任务为
`PH1-REAL-W1 READY`，真实工具仍保持未开始。
