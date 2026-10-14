# PH1-MOCK-M3 新一期 Dify Workflow 构建、绑定与验收 Backlog

> 状态：`COMPLETED / ACCEPTANCE_PASS / ZERO_BLOCKER / M4_COMPLETED / MOCK_V0.1_FROZEN`  
> 建立日期：2026-09-04  
> 完成日期：2026-09-04  
> 上级计划：[一期 18 节点交付计划](../PHASE1_DELIVERY_PLAN.md)  
> 输入基线：`T01-PHASE1-MOCK-M1-BASELINE-v0.1` + 已通过[实现评审](PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md)的 M2 后端  
> 当前工作项：`PH1-REAL-W1 READY`  
> 本包只构建一期 Mock 的 Dify 编排、绑定与实例验收；其后的 M4 已独立执行回归冻结，真实科学能力仍属于 `PH1-REAL-W1～W7`。

## 1. 目标

在不改变 M1 规格和 M2 后端真值的前提下，建立严格一期 `N01-N18` 的两个 Dify Workflow：

- 由唯一新生成源确定性生成 main/debug 两个未绑定模板；
- 在画布上可还原 `E001-E027`、设计适用性 Gate、WT 直达、N12 受控重算、N16 条件执行及
  N16/N17→N18 汇合；
- 两个 Workflow 只调用 M1-06 登记的同一个 provider 和 26 个 Mock 工具，所有业务控制只读取
  M2 已固定的 `SCENARIO_LITERAL`；
- 从目标 Dify 实例读取真实 provider ID，经无秘密 binding manifest 生成 bound 派生物；
- 完成目标实例导入、回读、main/debug 各 21 案例/23 次提交和 21 组规范化一致性验证；
- 形成可追溯的模板、绑定、bound、导入与运行证据，只放行 M4，不提前冻结 Mock v0.1。

Dify 在本阶段只编排、等待、分支、汇合并返回后端事实。它不得计算科学值，不得从节点 stub 推导
Gate、Hard Filter、Pareto、重算、条件或 join 结论，也不得用 Dify system ID 替代规范 `run_id`。

## 2. 实施前起点与已闭合缺口

M3 建立时的事实基线如下：

- M2 已以 `COMPLETED / ACCEPTANCE_PASS / ZERO_BLOCKER / READY_FOR_M3` 放行；350 个 fixture、
  21 场景/23 提交、4 份/16 步 checkpoint、26-tool facade 和 M2 acceptance 均可离线复核；
- `src/t01_phase1_mock/dify/generator.py` 不存在，`templates/`、`config/`、`bound/` 均未创建；
- 仓库没有目标 Dify 实例版本、DSL 版本、同版本参考导出、实例 provider ID、导入方式或应用冲突
  检查证据；这些值不得从旧 Mock、公开示例或记忆猜测；
- 当前 `MockToolFacade` 是 transport-neutral 的 26-tool 调用面，仓库没有已证明可被目标 Dify
  访问的 MCP transport/server；M3-01 必须先确认目标协议与可达方式；
- M1-06 冻结了两个 Workflow、26 个工具、目录、token 和绑定链，但没有冻结目标 Dify 版本、
  DSL 结构、provider 实例 ID、API 地址或密钥。

这些是本 backlog 建立时的历史起点。M3-01 随后从用户本地 Docker Dify 取得 1.17.0、DSL 0.7.0、
同实例参考导出、专用 provider 和精确 26-tool 枚举；M3-02～10 已据此完成。闭合结果见
[目标预检](PHASE1_MOCK_M3_01_DIFY_TARGET_DSL_PREFLIGHT.md)和
[M3 实现评审](PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md)，不得把本节的实施前缺口误读为当前状态。

## 3. 权威输入与读取顺序

| 顺序 | 输入 | M3 使用方式 |
|---:|---|---|
| 1 | [M2 实现评审](PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md)与 M2 机器结果 | 确认唯一后端真值、可调用面、已知限制和 M3 放行状态 |
| 2 | [M1-06 命名、目录、生成、绑定与隔离](PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md)及[资产注册表](../../../工作流设计/03-Dify实现/T01_PHASE1_MOCK_ASSET_REGISTRY_v0.1.json) | 固定 2 Workflow、26 tools、provider/token、路径和 template→binding→bound 链 |
| 3 | [M1-02 节点注册表](PHASE1_MOCK_M1_02_NODE_REGISTRY.md)与[M1-03 控制流](PHASE1_MOCK_M1_03_CONTROL_FLOW_STATE_GRAPH.md) | 固定业务节点身份、27 条边、状态、Gate/WT/recalc/condition/join 语义 |
| 4 | [M1-04 envelope 契约](PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md)及[Schema](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_ENVELOPE_SCHEMA_v0.1.json) | 固定 Workflow 输入、输出与规范 ID/引用外壳 |
| 5 | [M1-05 场景模型](PHASE1_MOCK_M1_05_DETERMINISTIC_SCENARIO_MODEL.md)及[场景 Catalog](../../../工作流设计/02-数据契约/T01_PHASE1_MOCK_SCENARIO_CATALOG_v0.1.json) | 固定 21 个场景及所有路由字面量；禁止 Dify 重算 |
| 6 | [M1-07 验收规格](PHASE1_MOCK_M1_07_ACCEPTANCE_ASSERTIONS_FIXTURE_MANIFEST.md)、[fixture manifest](../../../dify/t01-phase1-mock-v0.1/fixtures/T01_PHASE1_MOCK_FIXTURE_MANIFEST_v0.1.json)和[acceptance Catalog](../../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_ACCEPTANCE_CATALOG_v0.1.json) | 固定 M3 main/debug/parity 执行矩阵、selector/operator 和 10 个覆盖门 |
| 7 | M3-01 从目标 Dify 取得的版本、同版本最小导出、provider/tool 枚举与可达性证据 | 唯一决定实例相关 DSL 结构、绑定值和导入方法；不得反向覆盖前六层业务语义 |

前六层均为冻结或已放行输入。若 M3 发现真正的语义矛盾，必须登记 finding 并停止受影响工作项；
不得静默修改 M1 v0.1 或 M2 结果以适配 Dify。若只是目标 Dify 的工程限制，应在 M3 内选择等价
编排方式；若必须新增子 Workflow、工具或改变已登记身份，则先升级注册表和受影响基线再继续。

## 4. 范围边界

### 4.1 M3 包含

- 目标 Dify 版本、DSL、provider、26-tool 可达性和应用冲突的只读预检；
- Dify 调用包装、checkpoint/recovery 观察方式、业务画布映射和 main/debug 差异契约；
- 必要时对现有 `MockToolFacade` 增加不含业务逻辑的薄 transport adapter；
- `src/t01_phase1_mock/dify/generator.py` 唯一生成源及薄 CLI；
- 两个未绑定模板、静态 DSL/拓扑/变量/秘密/隔离校验；
- provider binding Schema/manifest、fail-closed binder、两个 bound 派生物和四级哈希链；
- 经授权的目标实例导入、回读/重导出、路由 smoke、main/debug 全量执行和 parity；
- M3 机器证据、实现评审及 M4 放行决定。

### 4.2 M3 不包含

- 修改 M2 场景、fixture、控制字面量、运行状态机或 26 个稳定工具身份；
- 让 LLM、Dify Code 节点、模板表达式或条件节点执行科学计算、Hard Filter 或 Pareto；
- 增加 P0-P7 子 Workflow、旧 `t01-mock-mcp` provider、旧 `MOCK-*` 场景或 S07 能力；
- 把旧生成器、旧模板、旧 bound 或旧画布结构复制成一期实现；
- 在模板、binding、bound、证据、日志或文档中保存 API key、token、密码、Cookie、JWT、OAuth
  secret 或其他凭据；
- 自动覆盖、删除或重命名目标实例已有应用；发现同名应用时必须停止并取得明确处置授权；
- 向 M4 的 `regression/runs/{campaign_id}/` 写入证据或冻结 Mock v0.1；
- 调用真实科学工具、访问科学公网数据库或声称真实 Workflow/Agent C 已部署。

## 5. 工作项与依赖

| 工作项 | 交付内容 | 依赖 | 当前状态 | 完成证据 |
|---|---|---|---|---|
| `PH1-MOCK-M3-01` | 目标 Dify、DSL、provider/transport 和导入能力预检 | M2 review | `COMPLETED` | [目标预检](PHASE1_MOCK_M3_01_DIFY_TARGET_DSL_PREFLIGHT.md)：1.17.0/0.7.0、26-tool、权限、零 blocker |
| `PH1-MOCK-M3-02` | 冻结 Workflow 调用包装、checkpoint/recovery 驱动和 18 节点画布映射 | M3-01 | `COMPLETED` | [调用与画布契约](PHASE1_MOCK_M3_02_WORKFLOW_INVOCATION_GRAPH_CONTRACT.md)已冻结并实现 |
| `PH1-MOCK-M3-03` | 建立或验证薄 Dify-facing transport，保持 26-tool 闭集 | M3-02 | `COMPLETED` | 目标 Dify 实际枚举并调用精确 26 tools；无新增业务逻辑或工具 ID |
| `PH1-MOCK-M3-04` | 实现唯一 generator 与 main/debug 未绑定模板 | M3-02、M3-03 | `COMPLETED` | 两模板可字节级重建，只有登记 provider token 未绑定 |
| `PH1-MOCK-M3-05` | 静态验证 DSL、拓扑、变量、工具、秘密和 main/debug 差异 | M3-04 | `COMPLETED` | N01-N18、E001-E027、26 tools、路由源、token、秘密与隔离测试通过 |
| `PH1-MOCK-M3-06` | 建立 binding 合同，从目标实例生成 manifest 与两个 bound | M3-05、目标 provider 事实 | `COMPLETED` | `local_dify_1_17` manifest 合法，token/secret 均为 0，哈希链闭合 |
| `PH1-MOCK-M3-07` | 经授权导入 main/debug，回读/重导出并验证绑定 | M3-06、导入授权 | `COMPLETED` | 两应用身份独立，59 节点/79 物理边回读一致，导入 warning 为 0 |
| `PH1-MOCK-M3-08` | 执行 main/debug 各 21 案例/23 提交及适用断言 | M3-07 | `COMPLETED` | 两阶段各 9 条全局 + 44 条焦点断言与 10 覆盖门均 0 failure |
| `PH1-MOCK-M3-09` | 21 组 main/debug 规范化 parity 与差异审计 | M3-08 | `COMPLETED` | 21 组及 global.016 全部 PASS，failure 为 0 |
| `PH1-MOCK-M3-10` | 工程/算法边界/产品/Dify 一致性评审并放行 M4 | M3-09 | `COMPLETED` | [M3 实现评审](PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md)五项通过；仅 M4 置为 READY |

主依赖链为：

```text
M3-01 -> M3-02 -> M3-03 -> M3-04 -> M3-05 -> M3-06 -> M3-07 -> M3-08 -> M3-09 -> M3-10
```

M3-03 若目标实例已经存在可达且精确匹配的 26-tool provider，可用具名验证证据完成而不新增代码；
不得为了填满交付树创建第二套 facade。M3-06/07 需要目标实例事实和授权，但这不允许跳过 M3-01～05
或用虚构值预生成 bound/import PASS。

## 6. 逐项实施说明

### 6.1 PH1-MOCK-M3-01：目标实例与 DSL 兼容性预检

只读收集并冻结：

1. 目标实例的非秘密环境标识、Dify 精确版本/build、部署形态和支持的 Workflow app/DSL 版本；
2. 从同一目标实例导出的最小 Workflow 样本，覆盖实际使用的 start、tool、if/else、iteration/loop、
   branch/join、variable aggregator、end 等节点类型；提交前须去除实例凭据和无关内容；
3. 目标实例内显示名为 `t01-phase1-mock-mcp-v01` 的 provider 是否存在，其实例 ID、协议、可达端点
   及工具枚举是否与注册表的 26 个 ID 精确相等；
4. `T01_Phase1_Mock_v0.1` 和 `T01_Phase1_Mock_v0.1_Debug` 是否已存在，以及导入新应用、更新应用、
   回读/重导出和执行所需权限；
5. Dify 可达 Mock 后端的网络方向、状态持久化位置和凭据注入方式；凭据只存在受控环境变量/秘密存储；
6. 目标能力是否能表达 N12 最多三轮、N16/N17 分支与 join、失败终态和 checkpoint/recovery 观察。

交付建议为 `PHASE1_MOCK_M3_01_DIFY_TARGET_DSL_PREFLIGHT.md` 及 M3 evidence root 下的机器 JSON。
若无法取得同版本导出、provider/tool 不匹配、目标不可达或权限不足，应给出一个定点 blocker 和缺失
事实，不得转而读取旧 P0-P7 DSL 作为当前来源。

### 6.2 PH1-MOCK-M3-02：调用包装、生命周期与画布映射契约

在写 generator 前冻结以下工程契约：

1. canonical request 如何进入 Workflow，Dify-only orchestration context 如何与 M1-04 request 隔离，
   输出如何保持完整 envelope；
2. 正常提交、幂等重放、幂等冲突、poll、显式 timeout/cancel/recovery 如何由测试驱动器与 Workflow
   协同，尤其要明确 recovery 后新 `run_id` 的传递；
3. 四份 checkpoint plan/16 个步骤如何被 main/debug 观察，且不增加未登记业务工具、不由墙钟或
   Dify 重试次数隐式推进；
4. 18 个业务节点与 27 条边如何映射到 Dify 内部节点；Gate、recalc、condition、join 不是 N19+；
5. 26 个工具在两个画布中完整登记，每次运行只执行当前分支需要的调用；节点 stub 不输出控制真值；
6. debug 只可增加日志、trace、可见中间变量等 observability 字段，业务调用、路由和最终规范结果
   必须与 main 相同；
7. Dify system workflow/app/run/node ID 只写外部关联字段，不能进入规范 request/run/envelope ID。

交付为 `PHASE1_MOCK_M3_02_WORKFLOW_INVOCATION_GRAPH_CONTRACT.md`。它是生成器的评审映射，不另建
可手工维护的第二份图源；节点/边/工具清单仍从冻结规格和 M2 bundle 读取。

### 6.3 PH1-MOCK-M3-03：Dify-facing transport 与 26-tool 可达性

目标实例若尚无可达 provider，可在 M3 增加一个薄 adapter，但必须满足：

- 只代理当前 `MockToolFacade`，工具集合从资产注册表加载，不复制 26 项常量；
- 不实现 Gate、重算、条件、join、fixture 选择或科学计算；
- Dify 能获得稳定工具描述、参数 Schema 和结构化错误，未知工具/参数/scenario/run 全部 fail closed；
- lifecycle test driver 与业务 toolset 分离，不把 poll/inject/cancel/recover 偷注册成第 27+ 个业务工具；
- 仅监听明确批准的测试接口，认证材料不进仓库，日志屏蔽请求凭据；
- transport smoke 同时证明 provider 名、26 ID、一次 initialize/node/control/finalize 调用及错误路径。

若既有 provider 已满足这些要求，本项以只读枚举、调用和版本证据结束，不创建冗余 server。

### 6.4 PH1-MOCK-M3-04：唯一生成源与两个模板

实施内容：

1. 新建 `src/t01_phase1_mock/dify/generator.py`，从 `SpecificationBundle`、资产注册表和 M2 调用面
   构建 Workflow IR；业务节点、边、工具或场景列表不得只硬编码在脚本/YAML；
2. `scripts/t01_phase1_mock/build_dify_workflows.py` 只解析 CLI 参数并调用 generator；
3. 输出且只输出 M1-06 固定的两个模板：
   - `dify/t01-phase1-mock-v0.1/templates/T01_Phase1_Mock_v0.1.template.dify.yml`
   - `dify/t01-phase1-mock-v0.1/templates/T01_Phase1_Mock_v0.1_Debug.template.dify.yml`
4. Dify 内部节点 ID、画布坐标、字段顺序、换行和序列化规则确定化，连续两次干净生成字节一致；
5. 模板只允许出现登记 token `__T01_PHASE1_MOCK_V01_MCP_PROVIDER_ID__`，不得含实例 ID、URL、
   本机绝对路径、密钥或 bound 值；
6. main/debug 使用同一业务图和 toolset；debug 差异由 M3-02 的显式 allowlist 生成，不维护第二套图。

### 6.5 PH1-MOCK-M3-05：模板静态校验与负向门禁

validator 至少检查：

- YAML/DSL 可解析且符合 M3-01 已确认的目标版本结构；应用名、workflow/template ID 与路径精确；
- 两个模板可还原 N01-N18、E001-E027、Gate/WT、N12 最多三轮、N16 条件和 N16/N17 join；
- provider/tool 集与注册表精确相等，既无缺失也无额外工具，且所有控制源都是场景字面量；
- canonical request/envelope 变量不被 Dify system ID、空值回退或字符串拼接改写；
- template token 集闭合，不含 bound 值、凭据、远程科学 URL、本机路径或 legacy 标记；
- main/debug 归一化图相同，只有 M3-02 allowlist 内的观测字段不同；
- 手工修改模板、未知节点类型、悬空边、循环越界、错误 join、token 漂移和秘密注入均被负测阻断；
- `--check` 只读验证当前模板等于 generator 重建结果，不静默重写漂移文件。

### 6.6 PH1-MOCK-M3-06：绑定合同、bound 与哈希链

实施内容：

1. 为 `provider-bindings.{binding_profile}.json` 建立严格 Schema；profile 必须匹配
   `^[a-z][a-z0-9_-]{0,31}$` 且不能为 `legacy`；
2. binding manifest 只记录从目标实例读取的 `mcp_provider_id`、非秘密目标档案引用、registry/
   template 版本与 SHA-256；不得记录 API endpoint 或凭据；
3. binder 验证模板哈希、注册表版本、provider 显示名与 26-tool 枚举后，才替换全部登记 token；
4. 任一 token 未解析、出现未知 token/额外 provider、绑定值为空、源哈希漂移、秘密字段命中或路径
   越界时，失败且不写出任何 bound 文件；
5. 输出路径严格为：
   - `dify/t01-phase1-mock-v0.1/bound/{binding_profile}/T01_Phase1_Mock_v0.1.bound.dify.yml`
   - `dify/t01-phase1-mock-v0.1/bound/{binding_profile}/T01_Phase1_Mock_v0.1_Debug.bound.dify.yml`
6. 证据记录 registry、两个 template、binding manifest 和两个 bound 的 SHA-256；bound 不含 token
   或秘密，且只能由 source→template→binding 派生，禁止手工补丁。

### 6.7 PH1-MOCK-M3-07：目标实例导入与回读

导入属于外部状态变更，只能在目标、profile 和授权明确后执行：

1. 先做同名应用碰撞检查；不存在时创建两个新应用，存在时停止并请求用户决定，不自动覆盖；
2. 导入两个 bound，记录导入时间、目标 Dify build、binding profile、源哈希和实例返回的 app/
   workflow ID；实例 ID 仅作外部关联；
3. 在实例内复核 provider、26 个工具、输入变量、分支、循环、join 和输出变量均已解析；
4. 回读或重导出两个应用，去除目标生成的非语义字段后与 bound/生成 IR 做结构比对；
5. 禁止把原始凭据、Cookie、授权头或含秘密的原始响应写入证据；
6. 任一应用导入失败或结构漂移时，两者整体不得标为 PASS，也不得靠 UI 手工修改后绕过 generator。

### 6.8 PH1-MOCK-M3-08：main/debug 全量实例执行

按 acceptance Catalog 原顺序分别执行：

- `M3_DIFY_MAIN`：21 个案例、23 次 canonical submission、4 份/16 步 checkpoint plan；
- `M3_DIFY_DEBUG`：相同的 21/23 与 4/16；
- 每个阶段执行其适用的 9 条全局断言和 44 条焦点断言，并证明 10 个覆盖门均被具名案例命中；
- 幂等重放/冲突、recovery 新 run、取消、超时与恢复由 M3-02 定义的驱动器显式推进；辅助观察调用
  不得伪装成新的 canonical submission；
- 每个 Dify 运行保留 instance workflow run ID 与规范 request/run/envelope ID 的分离映射；
- 结果统一为 `MOCK_DATA`、`scientific_compute=false`、`NOT_DEPLOYED`，科学执行与公网科学请求为 0。

M3 机器结果写入 M3 evidence root，不写入 M4 的 `regression/runs/`，也不修改冻结 acceptance
Catalog 中的 `DECLARED_NOT_RUN` 历史声明。

### 6.9 PH1-MOCK-M3-09：main/debug parity

对 21 个场景逐一比较 main/debug 规范化结果：

1. 只移除 M3-02 冻结 allowlist 中的日志、调试 trace、Dify system ID 等观测字段；
2. request、规范 run/envelope ID 关系、节点状态、attempt、控制、边、错误、ArtifactRef、审计、
   handoff 和最终状态均不得被归一化器删除或改写；
3. 执行 acceptance global.016 `NORMALIZED_EQUALS`，21 组必须全部相等；
4. 正常、WT、N12 两/三轮与耗尽、N16/N17 skip/fail/timeout、上游失败、取消、恢复、幂等和 N18
   失败都必须进入 parity，不得只比较 happy path；
5. parity 失败必须输出最小 JSON pointer 差异并阻断 M3，不允许扩大 allowlist 来吞掉业务差异。

### 6.10 PH1-MOCK-M3-10：实现评审与 M4 放行

最终评审至少给出五项具名结论：

1. 工程一致性：source→template→binding→bound→import→run 全链可由版本和 SHA-256 追溯；
2. 算法边界：Dify 未计算科学结果或控制，全部路由来自后端 `SCENARIO_LITERAL`；
3. 产品范围：严格 N01-N18，无 P0-P7/S07/生产能力回流；
4. Dify 完整性：两个应用、同一 26-tool provider、21/23 双执行和 21 parity 均通过；
5. 发布边界：M3 只放行 M4，未创建 M4 campaign、未冻结 Mock v0.1、未放行真实工具。

交付文档为 `PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md`。只有 M3 全部机器断言和三分区回归通过、
blocker 为 0，才能把 M3 标记 `COMPLETED` 并将 M4 改为 `READY`。

## 7. 计划物理交付

```text
src/t01_phase1_mock/dify/
  __init__.py
  generator.py                    # 唯一 Workflow/模板生成源
  validator.py                    # 只读 DSL/图/秘密/隔离校验
  binding.py                      # template + manifest -> bound
  normalization.py                # main/debug 观测差异归一化
  runner.py                       # 目标实例 M3 执行与证据组装
  [transport.py]                  # 仅当目标需要；薄代理现有 26-tool facade

scripts/t01_phase1_mock/
  inspect_dify_target.py          # 只读预检
  build_dify_workflows.py         # 薄生成/--check 入口
  bind_dify_workflows.py          # 薄绑定/--check 入口
  import_dify_workflows.py        # 显式目标与授权保护
  run_m3_acceptance.py            # main/debug/parity 执行入口

tests/t01_phase1_mock/
  test_dify_target_contract.py
  test_dify_generation.py
  test_dify_template_validation.py
  test_dify_binding.py
  test_dify_import_evidence.py
  test_dify_execution.py
  test_dify_parity.py
  test_dify_isolation.py

dify/t01-phase1-mock-v0.1/
  templates/
    T01_Phase1_Mock_v0.1.template.dify.yml
    T01_Phase1_Mock_v0.1_Debug.template.dify.yml
  config/
    T01_PHASE1_MOCK_PROVIDER_BINDING_SCHEMA_v0.1.json
    provider-bindings.{binding_profile}.json
  bound/{binding_profile}/
    T01_Phase1_Mock_v0.1.bound.dify.yml
    T01_Phase1_Mock_v0.1_Debug.bound.dify.yml
  evidence/m3/{binding_profile}/
    target-preflight.json
    binding-evidence.json
    import-evidence.json
    T01_PHASE1_MOCK_M3_ACCEPTANCE_RESULT_SCHEMA_v0.1.json
    T01_PHASE1_MOCK_M3_ACCEPTANCE_RESULT_v0.1.json

docs/project/phase1/
  PHASE1_MOCK_M3_01_DIFY_TARGET_DSL_PREFLIGHT.md
  PHASE1_MOCK_M3_02_WORKFLOW_INVOCATION_GRAPH_CONTRACT.md
  PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md
```

`{binding_profile}` 不是字面目录，必须在 M3-01/06 用目标实例的具名非秘密 profile 替换。M3 evidence
root 是当前一期 M3 的导入/运行证据，不是 M4 campaign；若实施时需要调整该计划树，必须在 M3
评审中说明依据和迁移，不得把新路径静默写进冻结 M1 注册表。

## 8. 验收门禁

| 门禁 | 必须满足 |
|---|---|
| 目标事实 | 精确 Dify build、同版本参考导出、provider/tool 枚举、可达性和权限均有非秘密证据 |
| 调用契约 | canonical request 与 Dify-only context 分域；checkpoint/recovery/run_id 传递唯一且可测 |
| 生成 | 单一 generator；两个模板干净重建字节稳定；无手工维护第二图源 |
| 图与路由 | N01-N18、E001-E027、Gate/WT/N12/N16/join 可还原；控制只来自后端字面量 |
| 工具 | 两个模板只使用登记 provider 和 26 tools；无缺失、额外、旧身份或跨场景绑定 |
| 模板安全 | 仅登记 token 未解析；无实例 ID、URL、本机路径、密钥、科学远程调用或 legacy 标记 |
| 绑定 | profile 合法，真实 provider ID 来自目标；bound 无 token/秘密，四级哈希链闭合 |
| 导入 | 两个应用无误覆盖地导入，回读结构一致，目标 system ID 与规范 ID 分离 |
| main/debug | 每个阶段 21 案例/23 提交、9+44 断言与 10 覆盖门全部 PASS |
| parity | 21 组规范化结果全部相等，差异仅在冻结 observability allowlist |
| 隔离回归 | 当前一期、旧完整 Mock 74 项和 S07 41 项分别 PASS，旧资产无写入 |
| 发布边界 | M4 仅变为 READY；M4 campaign、Mock v0.1 冻结和真实工具仍未开始 |

## 9. 已闭合的外部依赖与停止条件

以下事实是 M3 建立时要求从实际目标取得的外部依赖，现均已闭合：

- 目标 Dify 为本地 Docker 1.17.0，DSL 0.7.0；
- 同实例 Workflow 导出已读取并净化记录；
- `t01-phase1-mock-mcp-v01` 的实例记录、协议、精确 26-tool 枚举和可达性已验证；
- binding profile 固定为 `local_dify_1_17`；
- 导入、回读/重导出和 Workflow 执行均已实际完成。

机器事实见 [M3-01 预检](PHASE1_MOCK_M3_01_DIFY_TARGET_DSL_PREFLIGHT.md)。首次导入前两个目标应用
均不存在；后续重导入只使用已记录的精确 app ID。原停止条件继续有效：目标未明确、同名应用
归属不清或权限边界变化时必须停止，不得默认覆盖。

## 10. 退出条件

`PH1-MOCK-M3` 只有同时满足以下条件才完成：

- 目标 Dify 与 provider 事实真实可复核，不是占位符、旧实例值或手工猜测；
- 两个模板可从唯一 generator 确定性重建，两个 bound 可从模板和具名 manifest 确定性派生；
- main/debug 已导入并回读验证，画布业务拓扑和工具集合与冻结资产一致；
- `M3_DIFY_MAIN` 与 `M3_DIFY_DEBUG` 各 21 案例/23 提交真实执行，适用 9+44 条断言和 10 门禁
  全部 PASS；
- `M3_MAIN_DEBUG_PARITY` 的 21 组结果及 global.016 全部 PASS；
- 科学执行、科学公网请求、legacy 复用、秘密泄漏、手工模板/bound 修补和 blocker failure 均为 0；
- 当前一期测试、旧完整 Mock 74 项和 S07 41 项分别通过；
- [当前状态](../STATUS.md)、[一期资料索引](README.md)、[Dify 实现入口](../../../工作流设计/03-Dify实现/README.md)
  和[开发运行手册](../../development/RUNBOOK.md)已同步；
- M3 实现评审只将 `PH1-MOCK-M4` 放行为 `READY`，不把 M3 PASS 写成 Mock 冻结或生产部署。

上述退出条件在 M3 时点已满足，详见 [M3 实现评审](PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md)。
其后的 `PH1-MOCK-M4` 现已完成独立 campaign、冻结回归与 Mock v0.1 冻结，详见
[M4 实现与冻结评审](PHASE1_MOCK_M4_IMPLEMENTATION_REVIEW.md)；下一任务为 `PH1-REAL-W1 READY`。
