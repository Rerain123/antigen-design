# T-01 Dify工作流搭建与导入指南

> 当前角色：`FROZEN_LEGACY_FULL_T01_MOCK`；本文不适用于新一期 18 节点 Mock。  
> 当前一期入口：[PH1-MOCK-M1 backlog](../../../../docs/project/phase1/PHASE1_MOCK_V01_BACKLOG.md)  
> 文档状态：DRAFT v0.1（Mock调试骨架）  
> 编制日期：2026-08-31  
> 当前阶段：本地Mock + Dify画布调试；不进行正式服务器部署  
> 业务流程依据：[T01_算法图_v10_20260821.md](../../../../工作流设计/01-业务依据/T01_算法图_v10_20260821.md)  
> 历史工具手册与其他项目工程指南：只作接口、工程和部署方法参考，不代表本项目已有工具或服务器配置

## 1. 本轮结果

仓库中已生成 9 个 Dify Workflow DSL 0.7.0 模板：

| 顺序 | Workflow | 作用 |
|---:|---|---|
| 0 | `T01_P0_Structure` | 结构获取、预测、质量、拓扑、RSA、细菌定位 |
| 1 | `T01_P1_EpitopeSafety` | 表位、安全与糖基化 |
| 2 | `T01_P2_ConservationDomain` | 保守性、R-11、功能域；支持0b只补跑S-16 |
| 3 | `T01_P3_WTDevelopability` | WT可开发性、R-57与分支4稳定性补救 |
| 4 | `T01_P4_Design` | S-27/S-28/S-29及32→48→64两次重试 |
| 5 | `T01_P5_VariantEvaluation` | step19、19b、step20 |
| 6 | `T01_P6_CodonStabilityMD` | S-30、WT S-31与MD门控 |
| 7 | `T01_P7_OutputHandoff` | S-42、C29/C30、step26、S-43/S-44 |
| 主流程 | `T01_Master_v10` | 输入、长度、0b路由、step11、step15/16和八阶段编排 |

模板目录为 `dify/templates/`。命令入口为 `dify/scripts/build_dify_workflows.py`，实现为 `src/t01_dify_workflows/generator.py`。

## 2. 不变的职责边界

工作流中只允许以下节点类型：

- Start：接收已经收集好的字段或JSON字符串。
- Tool：调用MCP科学/后端工具或已发布的阶段工作流。
- IF/ELSE：只比较后端返回的固定枚举或布尔值。
- Variable Aggregator：汇合互斥分支，不合成科学结论。
- End：返回后端结果。

模板中不存在 LLM、Code、HTTP Request、Question Classifier 或自由文本科学判断节点。科学阈值、数据处理、过滤、排序、重试语义和报告组装均在后端工具内完成。C30也只是 `output.prepare_explanation` 返回后端事实摘要；LLM最多在工作流外根据该摘要进行语言解释。

## 3. 为什么模板需要绑定

Dify注册MCP服务后，会为当前Dify实例保存一个provider ID。阶段Workflow发布为工具后，也会产生各自的provider ID和tool name。这些值属于当前Dify实例，换实例、重建空间或重新发布后可能改变，不能写死在仓库模板中。

模板因此使用以下占位符：

- `__T01_MCP_PROVIDER_ID__`
- 每个阶段的 `__T01_P*_PROVIDER_ID__`
- 每个阶段的 `__T01_P*_TOOL_NAME__`

导入必须分两轮完成。

## 4. 第一轮：绑定并导入八个阶段Workflow

### 4.1 启动本地Mock MCP

```powershell
.\.venv\Scripts\t01-mock-mcp.exe `
  --transport streamable-http `
  --host 0.0.0.0 `
  --port 8101 `
  --path /mcp
```

Dify与服务在同一Windows宿主机进程中时可使用 `http://127.0.0.1:8101/mcp`。Dify运行在Docker Desktop容器中时，通常使用 `http://host.docker.internal:8101/mcp`。这只是开发连接，不是正式部署地址。

### 4.2 在Dify中注册MCP

在Dify工作区注册上述Streamable HTTP MCP，确认工具列表为63项、`mock.list_scenarios`返回25个场景。当前Mock不使用生产密钥，且只接受 `execution_mode=mock`。

从Dify导出的任一含该MCP工具节点的DSL中读取工具节点的 `provider_id`。不要猜测该值，也不要复用其他Dify实例的值。

### 4.3 绑定阶段模板

```powershell
.\.venv\Scripts\python.exe .\dify\scripts\build_dify_workflows.py bind-stages `
  --mcp-provider-id "<当前Dify实例的MCP provider_id>" `
  --output .\dify\bound\stages
```

该命令只生成8个阶段文件，不需要主流程的工作流工具ID。随后按00至07顺序导入Dify，逐个运行最小Mock测试，再把每个阶段发布为Workflow Tool。

## 5. 第二轮：绑定并导入主Workflow

复制 `dify/config/provider-bindings.example.json` 为 `dify/config/provider-bindings.local.json`，填写：

- `mcp_provider_id`；
- 8个已发布阶段Workflow Tool的 `provider_id`；
- 8个已发布阶段Workflow Tool的 `tool_name`。

然后执行：

```powershell
.\.venv\Scripts\python.exe .\dify\scripts\build_dify_workflows.py bind-master `
  --bindings .\dify\config\provider-bindings.local.json `
  --output .\dify\bound\master
```

导入生成的 `99_T01_Master_v10.dify.yml`。主流程通过Workflow Tool调用8个阶段，不通过LLM决定工具或计算结果。

本地bindings文件不得包含鉴权密钥；如以后需要MCP Header/JWT，应保存在Dify凭据或部署环境变量中，而不是DSL或Git。

## 6. 主流程恢复点与分支

主流程严格保留算法图中的三种入口：

1. `context_scores=NONE`：P0→P1→P2→step11→P3/R-57/分支4→step15/16。
2. `context_scores=HIGH`：注入→补跑S-16→从内部step15恢复，跳过步骤1至14。
3. `context_scores=NON_HIGH`：注入→补跑S-16→从内部step12恢复，重算结构依赖维度后进入R-57/分支4。

这里的“step12”是算法图的内部流程步骤，不是S-12糖基化扫描。DSL将非高置信恢复点映射到阶段3的结构依赖可开发性重算；在获得更完整的v10 SOP或业务评审确认后，需要把这一映射作为重点复核项，但不得把它误接到S-12。

后续主要分支为：

- R-57设计跳过：直接进入P7，交付WT与`design_skipped`。
- R-57继续：分支4按后端`RUN_BRANCH4/SKIP_BRANCH4`执行，再进入step15/16。
- P4三轮全淘汰：跳过P5/P6，进入P7并交付`failure_report`。
- 设计通过：P5→P6→P7。

## 7. 首次调试输入

主Workflow Start需要：

| 字段 | 值 |
|---|---|
| `run_id` | 与JSON外层`run_id`一致，例如`dify-debug-0001` |
| `scenario_id` | 与JSON外层`scenario_id`一致，例如`MOCK-HAPPY-PATH` |
| `t01_input_json` | 可直接粘贴 `dify/fixtures/configure_run.example.json` 全文 |
| `execution_mode` | 固定`mock` |

`mock.configure_run_from_json`在后端解析JSON、校验T01Input并持久化运行状态。Dify和LLM不解析或重算其中的科学字段。

建议先测试：

1. `MOCK-HAPPY-PATH`；
2. `MOCK-SHORT-MHC-HALT`；
3. `MOCK-CONTEXT-HIGH`；
4. `MOCK-CONTEXT-NONHIGH`；
5. `MOCK-NO-STRUCTURE`；
6. `MOCK-LOW-STRUCTURE`；
7. `MOCK-MEMBRANE-SKIP`；
8. `MOCK-DESIGN-RETRY-64`；
9. `MOCK-DESIGN-ALL-REJECTED`；
10. `MOCK-MD-RUN`；
11. 三个工具错误场景。

每次运行后用 `mock.get_run`按`run_id`查看持久化轨迹。不要仅依据Dify节点显示“执行完成”判断科学步骤成功，必须检查StepResult的`status`和`error`。

## 8. 当前静态验收

生成器和测试已经验证：

- 9个Workflow均只有一个Start和一个End；
- 所有节点可从Start到达，并可到达End；
- 所有IF/ELSE均同时具有true和false出口；
- 图为DAG，S-28重试已显式展开为32、48、64三轮；
- 56个T-01 MCP工具名全部被画布覆盖；
- 无未登记科学工具；
- 无LLM、Code或HTTP节点；
- 模板绑定后不得残留provider占位符。

运行命令：

```powershell
.\.venv\Scripts\python.exe .\dify\scripts\build_dify_workflows.py validate `
  --path .\dify\templates `
  --allow-placeholders
```

## 9. 尚未完成的Dify联调项

当前DSL是可绑定的第一版Mock调试骨架，以下内容必须在实际Dify实例中继续验证，不能标记为完成：

1. 真实导入后MCP自定义输出Schema是否完整暴露`status/data/error/json`。
2. Workflow Tool发布后的对象子字段能否在主流程条件节点中直接选择。
3. 变量聚合器对未执行分支的行为是否与当前Dify版本一致。
4. `QUEUED/RUNNING`长任务的通用轮询/取消子流程；当前主DSL只覆盖同步终态Mock路径。
5. 25个Mock场景的Dify画布逐项运行证据与截图。
6. 非高置信0b的内部step12恢复点业务复核。

这些联调通过后，再开始逐工具实现真实后端；正式服务器部署仍在上线阶段执行。

## 10. Dify版本依据

本模板按2026-08-31核对的Dify主线格式生成：DSL版本`0.7.0`、Tool Node版本`2`、MCP provider类型`mcp`、阶段调用provider类型`workflow`。实际Dify部署版本必须在首次导入前记录；如果导出格式不同，应优先以该实例导出的最小Workflow为基准调整生成器，不手工批量修改9个文件。
