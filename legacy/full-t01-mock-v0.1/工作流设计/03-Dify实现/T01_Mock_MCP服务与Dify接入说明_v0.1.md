# T-01 Mock MCP 服务与 Dify 接入说明

> 当前角色：`FROZEN_LEGACY_FULL_T01_MOCK`；只用于旧 Master/P0-P7 回归，不属于当前一期 Mock。  
> 当前一期入口：[PH1-MOCK-M1 backlog](../../../../docs/project/phase1/PHASE1_MOCK_V01_BACKLOG.md)  
> 版本：0.1.0  
> 工作流：T01-v10  
> 用途：Dify 可视化串联、分支验收、故障定位和后续替换真实 MCP 工具  
> 明确限制：本服务不执行科学计算，结果不能用于科研结论或生产候选

## 1. 实现依据与职责边界

本服务严格依据以下两份用户提供文档及已评审的数据契约实现：

1. [T01_算法图_v10_20260821.md](../../../../工作流设计/01-业务依据/T01_算法图_v10_20260821.md)：定义 T-01 流程、门控、分支和科学步骤。
2. [已部署蛋白工具接口调用与测试手册.md](../../../../工具部署/已部署蛋白工具接口调用与测试手册.md)：只作为历史调用与工程安全规则参考；其中部署位于甲方服务器，本项目全部能力仍按从零部署处理。
3. [T01_Dify节点-MCP工具映射与数据契约_v0.1.md](../02-数据契约/T01_Dify节点-MCP工具映射与数据契约_v0.1.md)：定义 Dify 节点、MCP 名称和统一输入输出契约。

职责固定为：

| 层 | 负责 | 禁止 |
|---|---|---|
| LLM | 收集缺失输入、发起工具调用、等待结果、解释后端事实 | 计算科学指标、补猜阈值、改变门控、直接加工大结果 |
| Dify | 编排节点、根据后端枚举路由、查看输入输出、重放 Mock 场景 | 在 LLM/Code 节点复制科学算法 |
| 后端/MCP | Schema 校验、门控、状态、科学计算、产物校验、审计 | 把服务器绝对路径或未校验输出交给 LLM |
| 当前 Mock 服务 | 契约、状态、门控、固定场景、错误注入、异步状态模拟 | 调用或假装调用任何真实科学工具 |

## 2. 当前服务范围

MCP 工具共 63 个：

- 56 个 T-01 工具，名称与映射文档第 6 节完全一致。
- 3 个异步作业工具：`jobs.get_status`、`jobs.get_result`、`jobs.cancel`。
- 4 个调试控制工具：`mock.configure_run`、`mock.configure_run_from_json`、`mock.get_run`、`mock.list_scenarios`。

所有 T-01 工具均使用同一扁平 `StepRequest` 输入和 `StepResult` 输出。以后把某个 Mock 工具替换成真实 MCP 服务时，Dify 节点变量无需改变。

## 3. 安装与启动

当前工作区已创建 `.venv` 并安装服务。直接验证：

```powershell
.\.venv\Scripts\pytest.exe
.\.venv\Scripts\t01-mock-mcp.exe --help
```

启动 Streamable HTTP：

```powershell
.\.venv\Scripts\t01-mock-mcp.exe `
  --transport streamable-http `
  --host 0.0.0.0 `
  --port 8101 `
  --path /mcp
```

默认状态库位于 `var/t01-mock.sqlite3`。如需单独实例：

```powershell
$env:T01_MOCK_DB_PATH = "D:\work\蛋白智能体\var\t01-mock-dev.sqlite3"
.\.venv\Scripts\t01-mock-mcp.exe --host 0.0.0.0 --port 8101
```

在另一个终端执行真实 MCP 握手：

```powershell
.\.venv\Scripts\python.exe .\scripts\smoke_mcp_http.py `
  --url http://127.0.0.1:8101/mcp
```

成功标准为 `tool_count=63`、`scenario_count=25` 和 `status=PASS`。

## 4. Dify 连接

项目部署边界已经明确：T-01 MCP、后端状态与科学计算服务部署在我方服务器。正式 Dify 工作流通过 HTTPS 和鉴权访问我方服务，不连接甲方历史工具服务器，也不直接访问内部科学工具端口。

目标链路为：

```text
Dify → HTTPS/JWT → 我方 OpenResty/1Panel → 回环绑定的 MCP Gateway → 后端/Worker/科学工具
```

当前工作流搭建直接使用开发环境中的 Mock MCP：Dify 与服务同机时使用其可达地址；Dify 在本机 Docker Desktop、Mock 服务运行在 Windows 宿主机时可测试 `http://host.docker.internal:8101/mcp`。此阶段不要求先部署到正式服务器。

等工作流和真实工具达到上线条件后，再切换为我方服务器的 HTTPS/JWT 地址。服务器公网域名、端口和路径尚未确认，不能复制其他项目的域名、`8020`/`8090` 端口或 `/opt/oligosmith` 路径。`127.0.0.1` 在 Dify 容器内表示容器自身，不表示 Windows 宿主机。

生产环境要求：

- 只暴露反向代理的 HTTPS 地址，容器端口不直接公开。
- Mock、smoke、production 使用独立入口、密钥、状态和产物命名空间。
- 生产 `tools/list` 不得出现 `mock.*` 调试工具。
- 长任务使用异步 `job_id` 查询，Dify 不保持长时间同步调用。
- TLS、JWT、Host/Origin 白名单、访问源、请求大小、超时和速率限制在部署阶段固化。

详细部署边界见 `工具部署/T01_自有服务器部署基线_v0.1.md`。

## 5. Dify 主流程的调用顺序

一次调试运行建议按以下顺序：

1. Dify 开始节点收集 T-01 输入和 `scenario_id`。
2. 生成全局唯一 `run_id` 和 `client_request_id`。
3. 调用 `mock.configure_run_from_json`，把 `run_id`、场景和完整 T-01 输入绑定；JSON解析与Schema校验在后端完成。
4. 调用 `t01.validate_request`。
5. 调用 `t01.evaluate_length_guard`；只依据后端返回的 `data.route` 路由。
6. 按映射文档连接 8 个阶段子工作流。
7. 每个工具返回 `QUEUED/RUNNING` 时，将 `job_id` 交给统一轮询子流程。
8. 终态后读取 `data` 和 `artifacts`，再进入下一节点。
9. 流程末尾调用 `mock.get_run` 查看持久化的节点轨迹，辅助定位 Dify 变量映射或分支问题。

示例请求文件：

- `dify/fixtures/configure_run.example.json`
- `dify/fixtures/step_request.example.json`

## 6. 每个科学工具节点的统一变量映射

| StepRequest 字段 | Dify 建议来源 |
|---|---|
| schema_version | 固定 `0.1.0` |
| workflow_version | 固定 `T01-v10` |
| run_id | 开始节点生成并全程透传 |
| step_id | 映射文档中的源步骤或 T 层 ID |
| node_id | Dify 节点唯一 ID |
| attempt | 初次为 1；S-28 重试依次为 2、3 |
| scope | `wt`、`variant`、`rescue`、`context_injection` 等显式值 |
| execution_mode | Mock 工作流固定 `mock` |
| parameters | 当前步骤白名单参数或紧邻上游的小型结构化输出；大型结果只传 ArtifactRef/后端状态引用 |
| input_artifacts | 上游 `ArtifactRef` 数组，可为空 |
| context | 仅保留当前门控需要的最小上下文 |
| idempotency_key | 推荐 `run_id:node_id:attempt:scope` |

每个 Dify 工具节点至少保留以下输出变量：

```text
status
job_id
data
artifacts
quality_flags
warnings
error
provenance
metrics
```

不要把 `data` 交给 LLM 节点重新计算。Dify 的 IF/ELSE 节点只比较后端明确枚举，例如 `HALT`、`RUN_S32`、`DESIGN_SKIPPED`。

## 7. Mock 场景使用方法

先调用：

```json
{
  "run_id": "dify-debug-0001",
  "scenario_id": "MOCK-NO-STRUCTURE",
  "input": { "...": "完整 T01Input" }
}
```

后续科学工具输入中不携带 `scenario_id`；服务按 `run_id` 读取已绑定场景，因此科学工具 Schema 与未来真实工具保持一致。

已执行过步骤的 `run_id` 不允许改绑其他场景或输入。要测试另一条路径，创建新的 `run_id`，避免旧幂等结果污染调试。

25 个场景可通过 `mock.list_scenarios` 动态获取，具体预期路径与数据契约文档第 8 节一致。

## 8. 异步节点调试

Mock 默认同步返回。要测试 Dify 的轮询子流程，可在任一允许终态的工具 `parameters` 中临时加入：

```json
{
  "_mock_async": true
}
```

行为固定为：

1. 原工具返回 `QUEUED`、`job_id` 和 0/2 进度，不返回完整 artifacts。
2. 第一次 `jobs.get_status` 返回 `RUNNING` 和 1/2。
3. `jobs.get_result` 在未完成时仍只返回当前状态，不泄漏完整结果。
4. 第二次 `jobs.get_status` 返回原工具终态和完整 data/artifacts。
5. `jobs.cancel` 只允许取消 QUEUED/RUNNING；终态重复取消返回 `JOB_ALREADY_TERMINAL`。

`_mock_async` 只是 Mock 调试保留参数，未来真实适配器不得把它传给科学软件。

## 9. 定位问题的最小检查顺序

出现错误分支时按以下顺序查看：

1. `run_id`、`node_id`、`step_id`、`attempt`、`scope` 是否与当前节点一致。
2. `status` 是否为 Dify 当前分支允许的状态。
3. `data.route` 或 `data.outcome` 是否使用后端枚举原值。
4. `error.code`、`error.category`、`error.retryable` 是否被 Dify 正确分流。
5. `input_artifacts[].sha256` 与 `provenance.input_hashes` 是否能追溯。
6. `quality_flags` 是否包含 `MOCK_DATA`，防止 Mock 结果误入生产。
7. 用 `mock.get_run(run_id)` 对照持久化轨迹与 Dify 节点日志。

三类强制错误场景固定注入到 `structure.fetch`：

| 场景 | error.category | exit_code | 期望处理 |
|---|---|---:|---|
| MOCK-TOOL-TIMEOUT | TIMEOUT | null | 按 retryable=true 的策略重试 |
| MOCK-OUTPUT-MISSING | OUTPUT_MISSING | 0 | 即使退出码为 0 也不得判成功 |
| MOCK-OUTPUT-INVALID | OUTPUT_INVALID | 0 | 阻止无效结果进入下游 |

## 10. 当前有意保留的未实现项

以下内容继续标记为 `SOP_PENDING`，不能由 Dify、LLM 或 Mock 代码自行补齐：

- `epitope_policy` 的批准枚举或内部结构。
- E0-E4 与 1.0、0.8、0.5、0.2 权重的完整逐项映射。
- S-16 `core_map` 四个分量的正式名称。
- mutable_length 的完整路由阈值。
- R-58 对 S-11、S-28、S-37、S-38 的详细校验条款。
- SC-10 触发后选择 WT 交接或 failure_report 的确定规则。
- Candidate 内部完整科学字段模型。
- S-44 Agent-C 目标接口、鉴权和交付确认语义。
- 所有科学工具的本项目部署、版本冻结、模型文件、参数白名单和金标准验收。

## 11. 本阶段验收标准

- `pytest` 全部通过。
- HTTP 冒烟输出 63 个工具、25 个场景和 PASS。
- T-01 工具目录与映射文档第 6 节逐项一致。
- 所有 Mock 结果显式标记 `MOCK_DATA`，且只接受 `execution_mode=mock`。
- 三类错误、三路交接、R-57、S-28 重试、19b 和 MD 门控均有自动化测试。

当前已进入下一阶段：仓库内已生成 `T01_Master_v10` 和 8 个阶段工作流的 Dify DSL 模板。模板绑定与导入步骤见 [T01_Dify工作流搭建与导入指南_v0.1.md](T01_Dify工作流搭建与导入指南_v0.1.md)。
