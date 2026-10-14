# PH1-MOCK-M1-06 命名、目录、生成、绑定与回归隔离

> 状态：`COMPLETED`  
> 日期：2026-09-04  
> 资产注册表版本：`T01-PHASE1-MOCK-ASSET-REGISTRY-v0.1`  
> 规范根命名空间：`t01_phase1_mock_v01`  
> 交付边界：只冻结未来一期 Mock 的资产身份、计划路径、单一生成源、绑定链和回归隔离；
> 不创建 Mock 实现、运行入口、Dify DSL、fixture 或 bound 产物。

## 1. 冻结结论

1. 一期 Mock v0.1 的所有运行时资产都从唯一根键 `t01_phase1_mock_v01` 派生；文件系统根目录使用
   `t01-phase1-mock-v0.1`。两种写法分别服务机器身份和可读路径，不能互换或另建别名。
2. 初始 Workflow 集严格为主 Workflow 与 Debug Workflow 两项；两者都表达同一套 N01-N18
   业务拓扑，不拆成或映射为 P0-P7。
3. Mock MCP 的稳定 provider 名为 `t01-phase1-mock-mcp-v01`，未来 Dify 调用面固定为 26 个
   namespaced 工具：1 个运行初始化、18 个节点 stub、6 个场景字面量控制读取、1 个结果归并。
4. M1-05 的 21 个 `scenario_key` 不改名；物理 `scenario_ref` 一律为
   ``t01_phase1_mock_v01.scenario.{scenario_key}``，并在机器注册表中逐项一一绑定。
5. `run_id` 由一期 Mock 后端签发，格式为 ``t01-phase1-mock-v01-run-{uuid4}``。Dify
   `sys.workflow_run_id` 只能写入外部关联/审计字段，不能成为规范 `run_id`。
6. 一期 Python 包、测试、脚本、Dify 资产、运行状态和回归证据均使用本任务冻结的独立根目录。
   本任务仅登记这些未来路径，不提前创建其中的代码或 DSL 文件。
7. Dify 模板只能由单一生成源 `src/t01_phase1_mock/dify/generator.py` 生成；bound 只能由模板与
   目标实例绑定清单派生。模板、bound 和回归结果都不是手工维护的源。
8. 旧 `legacy/full-t01-mock-v0.1/` 与 `legacy/s07/` 保持只读历史边界；新代码不得导入旧包、
   新命令不得写入旧目录，新旧测试与回归 campaign 必须分开运行。

机器真值见[资产注册表](../../../工作流设计/03-Dify实现/T01_PHASE1_MOCK_ASSET_REGISTRY_v0.1.json)，
结构约束见[注册表 JSON Schema](../../../工作流设计/03-Dify实现/T01_PHASE1_MOCK_ASSET_REGISTRY_SCHEMA_v0.1.json)。

## 2. 六类资产的规范身份

| 资产 | 稳定身份/格式 | 说明 |
|---|---|---|
| 根命名空间 | `t01_phase1_mock_v01` | 所有一期 Mock 逻辑身份的唯一前缀 |
| Workflow | `t01_phase1_mock_v01.workflow.main`、`t01_phase1_mock_v01.workflow.debug` | 初始集合恰为两项；增拆子 Workflow 必须升级注册表 |
| Tool provider | `t01-phase1-mock-mcp-v01` | Dify 实例内显示/逻辑 provider 名；实例生成的 provider ID 通过绑定清单注入 |
| Tool | `t01_phase1_mock_v01.tool.*` | 26 个精确工具名见第 4 节及机器注册表 |
| Scenario | `t01_phase1_mock_v01.scenario.{scenario_key}` | `{scenario_key}` 必须精确来自 M1-05 的 21 项目录 |
| Run | `t01-phase1-mock-v01-run-{uuid4}` | 仅后端签发；重放复用，恢复运行新建并回指原 run |
| Template | `t01_phase1_mock_v01.template.main/debug` | 未绑定、可复现的生成物 |
| Bound | `t01_phase1_mock_v01.bound.{binding_profile}.main/debug` | 模板与一个具名环境绑定清单的派生物 |

禁止把显示名、文件名、Dify 实例 ID、MCP URL 或旧 P0-P7 名称当作上述稳定身份。版本 `v01`
属于命名空间；未来不兼容版本必须使用新根键，不能就地改写 v0.1 身份。

## 3. Workflow 与模板注册

| workflow_id | Dify app 名 | template_id | 计划模板路径 | 职责 |
|---|---|---|---|---|
| `t01_phase1_mock_v01.workflow.main` | `T01_Phase1_Mock_v0.1` | `t01_phase1_mock_v01.template.main` | `dify/t01-phase1-mock-v0.1/templates/T01_Phase1_Mock_v0.1.template.dify.yml` | 一期 Mock 规范入口 |
| `t01_phase1_mock_v01.workflow.debug` | `T01_Phase1_Mock_v0.1_Debug` | `t01_phase1_mock_v01.template.debug` | `dify/t01-phase1-mock-v0.1/templates/T01_Phase1_Mock_v0.1_Debug.template.dify.yml` | 人工调试入口；不改变业务拓扑、场景或控制语义 |

约束：

- 两个 Workflow 都必须可还原 M1-03 的 N01-N18、E001-E027、Gate、N12 受控重算、N16/N17
  分支及 N18 汇合；Debug 不是第三套流程。
- 画布节点仍以 M1-02 `node_id` 为业务身份。Workflow、tool、S 步骤或 Dify 内部节点 UUID
  都不能替代 `N01-N18`。
- 本版本不注册子 Workflow。若 M3 因 Dify 工程限制必须拆分，须先升级本注册表并冻结新的
  workflow/template/bound 三方关系，不得临时使用旧 P0-P7 Workflow Tool。
- 此处冻结的是未来名称和路径，不代表两个模板文件或可导入应用当前存在。

## 4. Tool namespace 与绑定集合

### 4.1 Provider

| 项 | 冻结值 |
|---|---|
| 逻辑 provider ID | `t01_phase1_mock_v01.provider.mcp` |
| MCP server name | `t01-phase1-mock-v01` |
| Dify provider name | `t01-phase1-mock-mcp-v01` |
| 模板绑定 token | `__T01_PHASE1_MOCK_V01_MCP_PROVIDER_ID__` |
| 实例 provider ID | 只能从目标 Dify 实例读取并写入环境绑定清单；不得猜测或写死在生成源 |

### 4.2 26 个稳定工具

| 类别 | 数量 | 精确工具身份 | 责任边界 |
|---|---:|---|---|
| 运行初始化 | 1 | `t01_phase1_mock_v01.tool.run.initialize` | 校验 M1-04 request、解析 scenario_ref、处理幂等并签发/复用 run_id；不产生科学或控制结论 |
| 节点 stub | 18 | `t01_phase1_mock_v01.tool.node.n01` ～ `.n18` | 一一投影 M1-05 对应节点的 stub 事实；工具名尾号必须等于 `node_id` |
| 控制字面量 | 6 | `.tool.control.design_suitability`、`.n12_validation`、`.n15_delivery_recommendation`、`.n16_applicability`、`.n17_applicability`、`.n18_entry` | 只读取已绑定场景同名 `control_plan` 字面量；不是业务节点，也不计算规则 |
| 运行归并 | 1 | `t01_phase1_mock_v01.tool.run.finalize` | 按 M1-04 envelope 汇总已存在的节点、边、控制和终态事实；N18 仍是业务交付节点 |

两个 Workflow 使用同一冻结 toolset `t01_phase1_mock_v01.toolset.workflow_v01`。M2/M3 不得：

- 暴露无命名空间的 `structure.*`、`design.*`、`t01.*` 或 `mock.*` 工具；
- 让节点 stub 工具返回 Gate/N12/N15/N16/N17/N18 入口控制决定；
- 把 initializer/finalizer 或六个控制工具注册为 N19+；
- 将 M1-01 的生产候选工具名直接当作当前 Mock 的 MCP 工具名；
- 从旧 provider `t01-mock-mcp` 绑定任何一期画布节点。

本任务只冻结工具身份与类别，不定义工具参数 Schema、传输协议细节或实现代码。M1-04 envelope、
M1-05 场景字面量与后续 M1-07 fixture/断言共同决定实现验收。

## 5. Scenario 绑定

映射函数是纯字符串绑定：

```text
scenario_ref = "t01_phase1_mock_v01.scenario." + scenario_key
```

`scenario_key` 必须是 M1-05 Catalog 中的精确成员，大小写敏感、不做 trim 后别名、不接受旧
`MOCK-*` ID。21 项映射完整写入机器注册表；例如：

| scenario_key | scenario_ref |
|---|---|
| `happy_provided_structure` | `t01_phase1_mock_v01.scenario.happy_provided_structure` |
| `gate_wt_direct` | `t01_phase1_mock_v01.scenario.gate_wt_direct` |
| `n12_recalc_exhausted` | `t01_phase1_mock_v01.scenario.n12_recalc_exhausted` |
| `idempotent_replay` | `t01_phase1_mock_v01.scenario.idempotent_replay` |
| `n08_upstream_timed_out` | `t01_phase1_mock_v01.scenario.n08_upstream_timed_out` |

未知、重复、旧前缀或拼写不一致的引用在运行创建前失败；不得回落到 happy path。场景的控制、
节点、attempt、边和终态仍只以 M1-05 Catalog 为准，本任务不复制或改写其科学/流程语义。

## 6. 请求、envelope 与 run_id

| 身份 | 正则 | 签发者 |
|---|---|---|
| `request_id` | ``^t01-phase1-mock-v01-req-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`` | 调用方或受信入口；Dify 不改写 |
| `run_id` | ``^t01-phase1-mock-v01-run-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`` | 一期 Mock 后端 |
| `envelope_id` | ``^t01-phase1-mock-v01-env-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`` | 产生该 envelope 的组件 |

运行身份规则：

1. UUIDv4 的熵只用于生成不透明身份，绝不能成为场景选择、分支、重试、输出或时间控制输入。
2. 相同幂等键与相同规范请求重放时返回已有 `run_id`；幂等冲突不创建新运行。
3. 恢复是新运行，获得新 `run_id`，并在 `recovery_of_run_id` 中保存同命名空间的原 ID。
4. `idempotency_key` 仍是调用方提供的逻辑键，不当作文件名或目录段；所有索引都必须限定在
   一期 Mock 存储命名空间内。
5. Dify 的 `sys.workflow_run_id`、数据库自增 ID、campaign ID 和时间戳都只是关联数据，不能替代
   规范 `run_id`。
6. Windows 路径不得从未经校验的 ID 拼接；先通过完整正则，再解析并验证结果仍位于冻结根目录。

M1-04 Schema 与四个示例已同步采用这些 ID/场景规则；这只是物理身份约束，不改变 opaque 科学
payload 的未冻结状态。

## 7. 计划目录与所有权

以下是 M2/M3/M4 将按需创建的**计划路径**；M1-06 完成时它们不因此变成已实现资产。

| 路径 | 唯一职责 | 最早创建工作项 |
|---|---|---|
| `src/t01_phase1_mock/` | 一期 Mock Python 包；唯一 import root 为 `t01_phase1_mock` | M2 |
| `tests/t01_phase1_mock/` | 一期 Mock 单测/契约测试 | M2 |
| `scripts/t01_phase1_mock/` | 薄 CLI 包装；业务与生成逻辑不得只存在于脚本 | M2/M3 |
| `dify/t01-phase1-mock-v0.1/templates/` | 由生成源产生的未绑定模板 | M3 |
| `dify/t01-phase1-mock-v0.1/config/` | provider 绑定清单；不得含密钥 | M3 |
| `dify/t01-phase1-mock-v0.1/bound/{binding_profile}/` | 指定环境 bound 派生物 | M3 |
| `dify/t01-phase1-mock-v0.1/fixtures/` | M1-07 定义、M2/M3 使用的 fixture manifest 与数据 | M1-07/M2 |
| `dify/t01-phase1-mock-v0.1/regression/` | 当前一期预期、基线和回归说明 | M1-07/M4 |
| `dify/t01-phase1-mock-v0.1/regression/runs/{campaign_id}/` | 单次当前一期 Dify 回归证据 | M4 |
| `var/t01-phase1-mock-v0.1/` | 当前一期本地运行状态；不可提交 | M2 |
| `var/t01-phase1-mock-v0.1/runs/{run_id}/` | 单个运行的状态、日志与 Artifact 物理根 | M2 |

Artifact URI 前缀固定为 ``artifact://t01-phase1-mock-v0.1/{run_id}/``；URI 到本地/对象存储的
解析由后端负责，Dify 不拼接文件路径。`discovery/` 不属于 Mock 默认运行路径；没有单独批准的
取证任务时，M1-M4 不向其中写入结果。

## 8. 单一生成源与绑定链

```text
M1-02/03/04/05 + M1-06 registry
  -> src/t01_phase1_mock/dify/generator.py
  -> templates/*.template.dify.yml
  + config/provider-bindings.{binding_profile}.json
  -> bound/{binding_profile}/*.bound.dify.yml
  -> 校验/哈希/导入证据
```

冻结规则：

- `src/t01_phase1_mock/dify/generator.py` 是两个模板的唯一生成源；计划 CLI
  `scripts/t01_phase1_mock/build_dify_workflows.py` 只能调用它，不能包含第二份图定义。
- 模板必须可由干净工作区确定性重建；除明确的 provider 绑定 token 外不得含实例 ID、URL、
  API Key、JWT、OAuth secret 或本机绝对路径。
- 绑定清单路径为
  ``dify/t01-phase1-mock-v0.1/config/provider-bindings.{binding_profile}.json``；
  `binding_profile` 匹配 ``^[a-z][a-z0-9_-]{0,31}$``，且不能使用 `legacy`。
- 绑定值只能从目标 Dify 实例读取。未解析 token、未知工具、额外 provider、模板哈希不匹配、
  注册表版本不匹配或秘密字段出现时，绑定必须失败且不得写出 bound 文件。
- bound 路径分别为
  ``bound/{binding_profile}/T01_Phase1_Mock_v0.1.bound.dify.yml`` 与
  ``bound/{binding_profile}/T01_Phase1_Mock_v0.1_Debug.bound.dify.yml``。
- 每个 bound 证据须记录 registry version、workflow/template ID、模板 SHA-256、绑定清单 SHA-256
  与 bound SHA-256；不得手工修补 bound 后继续使用旧哈希。
- 模板和 bound 的 DSL 内容、画布坐标及 Dify 导入行为由 M3 实现与验证；M1-06 不创建任何 YAML。

## 9. 新旧回归隔离

### 9.1 冻结旧边界

| 旧对象 | 保留位置/身份 | 新一期禁止行为 |
|---|---|---|
| 旧包 | `legacy/full-t01-mock-v0.1/` | 不修改、不导入、不写入 |
| 旧生成源 | `legacy/full-t01-mock-v0.1/src/t01_dify_workflows/generator.py` | 不追加 N01-N18，不作为 import 依赖 |
| 旧 Python 包 | `t01_mock_mcp`、`t01_dify_workflows` | 当前 `src/` 与测试禁止导入 |
| 旧 Workflow | `T01_Master_v10`、`T01_P0_*`～`T01_P7_*` | 不发布/绑定为一期应用或 Workflow Tool |
| 旧 provider | `t01-mock-mcp` | 不绑定到一期模板 |
| 旧场景 | 25 个 `MOCK-*` ID | 不接受为一期 scenario_ref，不复制为别名 |
| 旧模板/bound | 旧包内 `dify/templates/`、`dify/bound/`、`dify/debug/` | 不覆盖、不作为新生成输出目录 |
| 旧回归 | 旧包内 `dify/regression/` | 不共享 campaign、run_id、预期或报告 |
| S07 备用包 | `legacy/s07/` | 不进入 N01 工具候选、import 或当前回归 |

### 9.2 回归命令与证据

三套测试必须从各自边界独立运行：

```powershell
# 当前一期；根 pyproject.toml 只收集 tests/
.\.venv\Scripts\python.exe -m pytest -q

# 冻结旧完整 Mock
Push-Location .\legacy\full-t01-mock-v0.1
..\..\.venv\Scripts\python.exe -m pytest -q
Pop-Location

# S07 备用包
Push-Location .\legacy\s07
..\..\.venv\Scripts\python.exe -m pytest -q
Pop-Location
```

当前一期 campaign 格式预留为 ``t01p1m-v01-reg-YYYYMMDD-{slug}``，证据只能进入当前
`dify/t01-phase1-mock-v0.1/regression/runs/`。旧 `master-reg-*` 不能被新 runner 接受；当前
run_id 也不能写入旧 SQLite、旧 regression 目录或 S07 证据目录。

任何共享工具若未来确有必要，必须先提取到新的中性包并同时证明两套基线不变；直接 import、复制
生成器、目录 junction/symlink 或以相对路径穿越 `legacy/` 均不允许。

## 10. 机器验收不变量

M1-07/M2/M3 至少实现以下 fail-closed 检查：

1. 注册表严格通过 Draft 2020-12 Schema，workflow 恰为 2、tool 恰为 26、scenario 映射恰为 21。
2. 18 个 `NODE_STUB` 工具与 N01-N18 一一对应；6 个控制工具与 M1-05 `control_plan` 六键一一对应。
3. 场景映射 key 集合与 M1-05 Catalog 完全相等，且每个 ref 等于固定前缀加 key。
4. request/run/envelope ID 与恢复引用通过冻结正则；Dify system ID 不出现在规范 `run_id` 字段。
5. 归一化后的生成输出、绑定输出、运行目录和回归目录全部位于当前冻结根目录，且不是 symlink/
   junction 跨界目标。
6. 当前运行时资产不含 `T01_Master_v10`、`T01_P0_`～`T01_P7_`、`t01-mock-mcp`、`MOCK-*`、
   `t01_mock_mcp` 或 `t01_dify_workflows` 身份。
7. template 只能含登记 token；bound 不含 token或秘密，并能由登记 source/template/binding 哈希追溯。
8. 当前回归、旧 74 项回归和 S07 41 项回归分别通过；历史测试数不计入一期功能完成度。

## 11. 与后续任务的边界

| 工作项 | 继承本任务 | 仍需产出 |
|---|---|---|
| `M1-07` | 所有稳定 ID、21 个 scenario_ref、fixture/回归计划路径 | 验收场景、机器断言、fixture manifest 内容与预期 |
| `M1-08` | 注册表、隔离规则、验证结果 | 工程/算法/产品一致性评审与具名缺口 |
| `M2` | Python/tool/run/storage 身份和路径 | Mock 后端、场景引擎、状态与契约实现 |
| `M3` | Workflow/template/bound 身份、生成源和绑定链 | 生成器、Dify DSL、绑定校验与导入证据 |
| `M4` | 回归目录、campaign 与新旧门禁 | 实际全场景回归、基线哈希和 v0.1 冻结 |

本任务没有冻结生产科学工具接口、完整科学 payload、Dify DSL 版本、目标实例 provider ID、API
地址或密钥，也没有关闭 OI-013/014 等生产接口缺口。

## 12. 验收记录

| 检查 | 结果 | 证据 |
|---|---|---|
| 六类命名空间 | `PASS` | workflow/tool/scenario/run/template/bound 均有唯一前缀、格式与机器登记 |
| Workflow/Tool 集 | `PASS` | 2 个 Workflow、26 个工具；N01-N18 与 6 个控制键均一一覆盖 |
| Scenario 绑定 | `PASS` | 21 个 M1-05 key 与 21 个 namespaced ref 双向唯一 |
| ID 隔离 | `PASS` | request/run/envelope 使用一期前缀 UUIDv4；旧 campaign 与 Dify system ID 不可替代 |
| 目录与生成源 | `PASS` | 当前/旧路径无交叉；模板单一生成源和只读派生链已冻结 |
| 绑定与秘密边界 | `PASS` | 实例 ID 仅经清单注入；模板/bound 禁止秘密和手工改写 |
| 回归隔离 | `PASS` | 根、旧完整 Mock、S07 的命令、路径与通过数独立 |
| 实现停止线 | `PASS` | 未创建 Mock 源码、fixture、Dify YAML 或 bound 产物 |

下一项为 `PH1-MOCK-M1-07`：在本注册表上冻结验收场景、机器断言和 fixture manifest；仍不开始
Mock 代码或 Dify DSL。
