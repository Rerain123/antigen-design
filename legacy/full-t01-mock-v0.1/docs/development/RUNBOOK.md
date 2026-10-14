# T-01 开发与调试运行手册

> 当前适用性：本文现有命令操作的是冻结的旧 `Master + P0-P7` Mock v0.1，仅用于历史回归。  
> 新一期 18 节点 Mock 尚未实现；其开发入口见[当前 backlog](../../../../docs/project/phase1/PHASE1_MOCK_V01_BACKLOG.md)。

本手册面向旧包的历史开发、Dify 联调和回归取证。业务流程与数据字段不在这里重复定义；需要时
分别查看[当前一期范围](../../../../docs/project/PHASE1_SCOPE_REBASELINE.md)。旧 Mock 回归才读取
[T-01 v10 算法图](../../../../工作流设计/01-业务依据/T01_算法图_v10_20260821.md)和
[旧 Mock 数据契约](../../工作流设计/02-数据契约/T01_Dify节点-MCP工具映射与数据契约_v0.1.md)。

## 1. 基线检查

从本归档包根目录 `legacy/full-t01-mock-v0.1/` 执行：

```powershell
..\..\.venv\Scripts\python.exe -m pytest -q
..\..\.venv\Scripts\python.exe ..\..\scripts\check_docs.py
```

本包基线应为 74 项旧完整 Mock 测试通过；另有 41 项 S07 和 1 项当前文档测试，必须在各自
目录独立运行。若只修改历史文档，仍需运行全项目文档检查。已移出一期的 S-07
证据命令统一保存在[历史运行说明](../../../s07/docs/archive/p0/S07_LEGACY_RUNBOOK.md)，不属于当前实施路径。

## 2. 启动旧完整 T-01 Mock MCP

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
..\..\.venv\Scripts\python.exe -m t01_mock_mcp.server `
  --transport streamable-http `
  --host 0.0.0.0 `
  --port 8101 `
  --path /mcp
```

保持该终端运行。在另一个终端执行：

```powershell
..\..\.venv\Scripts\python.exe .\scripts\smoke_mcp_http.py `
  --url http://127.0.0.1:8101/mcp
```

期望：协议握手通过、`tool_count=63`、`scenario_count=25`、`status=PASS`。

普通浏览器 GET 返回 406 不代表服务故障；MCP 端点需要正确协议和 Accept 头。

## 3. Dify 连接

- 本地 Dify：Docker Compose，版本 1.17.0。
- 宿主机 MCP：`http://127.0.0.1:8101/mcp`。
- Dify 容器使用：`http://host.docker.internal:8101/mcp`。
- provider 标识：`t01-mock-mcp`。
- 不启用动态客户端注册；本地 Mock 当前不需要 OAuth 客户端密钥。

详细界面操作见
[Mock MCP 接入说明](../../工作流设计/03-Dify实现/T01_Mock_MCP服务与Dify接入说明_v0.1.md)。

## 4. 生成与校验 Dify DSL

生成正式模板和一键 Debug 模板：

```powershell
..\..\.venv\Scripts\python.exe .\dify\scripts\build_dify_workflows.py generate
..\..\.venv\Scripts\python.exe .\dify\scripts\build_dify_workflows.py generate-debug
```

静态校验模板：

```powershell
..\..\.venv\Scripts\python.exe .\dify\scripts\build_dify_workflows.py validate `
  --path .\dify\templates `
  --allow-placeholders
```

绑定当前实例的 MCP provider：

```powershell
..\..\.venv\Scripts\python.exe .\dify\scripts\build_dify_workflows.py bind-stages `
  --mcp-provider-id t01-mock-mcp

..\..\.venv\Scripts\python.exe .\dify\scripts\build_dify_workflows.py bind-debug `
  --mcp-provider-id t01-mock-mcp
```

阶段 Workflow 发布为工具并填写 `dify/config/provider-bindings.local.json` 后绑定 Master：

```powershell
..\..\.venv\Scripts\python.exe .\dify\scripts\build_dify_workflows.py bind-master `
  --bindings .\dify\config\provider-bindings.local.json `
  --output .\dify\bound\master
```

规则：

- 只修改 `src/t01_dify_workflows/generator.py` 和测试，再重新生成。
- 不批量手工修改 `dify/templates/`、`dify/bound/` 或 `dify/debug/bound/`。
- `provider-bindings.local.json` 不得包含 JWT、API Key 或其他密钥。
- provider ID 与 Workflow Tool name 必须从当前 Dify 实例读取，不能猜测。

## 5. 旧 P0-P7 Mock 的 Dify 导入与发布顺序

1. 只有执行旧 Mock 回归时，才导入或覆盖 P0-P7 Workflow；不得将其发布为当前一期。
2. 阶段应用执行“发布更新”。
3. 进入“工作流作为工具”，执行配置/更新以刷新所引用的 Workflow 版本。
4. 记录实际 Workflow provider ID 与 tool name。
5. 重新绑定并覆盖导入 Master。
6. Master 只作为顶层编排时不必发布为 Workflow Tool。
7. 若要通过 Workflow Service API 调用 Master，必须发布 Master 并创建该应用专用 API Key。

只发布阶段应用、不刷新“工作流作为工具”，Master 仍可能调用旧版本。

## 6. 旧 Mock 独立阶段调试

名称以 `_Debug` 结尾的 8 个工作流会自动使用 `sys.workflow_run_id` 初始化所选 Mock 场景，
不需要人工添加 `mock.configure_run_from_json`。

- P0、P1、P3-P7：选择 Mock 场景后运行。
- P2：还需选择 `full` 或 `context_only`。
- Debug 工作流只用于独立测试；Master 调用的是不含初始化节点的正式阶段。

## 7. 旧 Master 25 场景回归

### 7.1 准备输入

```powershell
..\..\.venv\Scripts\python.exe .\dify\scripts\master_regression.py prepare `
  --campaign master-reg-YYYYMMDD-a
```

每轮必须使用新的 campaign/run_id。生成目录：
`dify/regression/runs/<campaign>/`。

### 7.2 编辑器运行模式

适用于 Master 尚未发布或不希望创建 API Key 的情况：

1. 按 manifest/CSV 的四个字段运行 Dify“测试运行”。
2. 所有场景结束后只读采集本地 PostgreSQL：

```powershell
$runDir = ".\dify\regression\runs\master-reg-YYYYMMDD-a"

..\..\.venv\Scripts\python.exe .\dify\scripts\master_regression.py collect-editor `
  --manifest "$runDir\manifest.json" `
  --results "$runDir\results.jsonl" `
  --traces "$runDir\traces.json"
```

该模式只记录真正完成的 Master 运行；未运行场景不会被伪造为成功。

### 7.3 Workflow Service API 模式

先发布 Master，并将 Key 只放入当前 PowerShell 会话：

```powershell
$env:DIFY_API_KEY = "app-仅粘贴到当前终端"

..\..\.venv\Scripts\python.exe .\dify\scripts\master_regression.py run `
  --manifest "$runDir\manifest.json" `
  --results "$runDir\results.jsonl" `
  --base-url http://localhost

..\..\.venv\Scripts\python.exe .\dify\scripts\master_regression.py collect `
  --results "$runDir\results.jsonl" `
  --traces "$runDir\traces.json"
```

### 7.4 生成报告

```powershell
..\..\.venv\Scripts\python.exe .\dify\scripts\master_regression.py report `
  --manifest "$runDir\manifest.json" `
  --results "$runDir\results.jsonl" `
  --traces "$runDir\traces.json" `
  --report-json "$runDir\report.json" `
  --report-md "$runDir\report.md"
```

完整规则见 [回归说明](../../dify/regression/README.md)。

## 8. Dify 1.17 兼容性

- MCP 对象/数组常量在 DSL 中保存为 JSON 文本，否则编辑器可能渲染失败。
- enum/select 参数的变量绑定可能在导入后被归一化为空值；当前工具调用固定为 `mock`。
- MCP `json` 输出在 Dify 中表现为数组，父 Workflow 不能用选择器读取数组下标。
- 跨阶段门控由阶段 Workflow 显式导出标量，例如 `stage_route`。
- Dify 显示 `0 Tokens` 正常，因为当前流程没有 LLM 节点。

## 9. 最小排错顺序

1. `docker info`：确认 Docker Engine 可用。
2. `docker ps`：确认 Dify API、Web、Worker、PostgreSQL、Redis、Sandbox 健康。
3. 运行 MCP smoke：确认 63 个工具和 25 个场景。
4. 在 Dify 集成页确认 provider 可看到工具数量。
5. 检查阶段 Workflow Tool 是否刷新到最新发布版本。
6. 查看失败节点的真实输入、输出与错误，不从上游界面提示猜原因。
7. 如为跨 Workflow 字段缺失，检查是否错误读取了 MCP `json` 数组内部字段。
8. 修复生成源并增加测试，然后重新生成、绑定、导入与发布。

## 10. 安全与停止条件

- 不把密钥写入项目文件。
- 不在已批准的 discovery/证据方案或对应生产门禁之外执行真实科学软件。
- 不把 smoke 结果描述为科学验收。

## 11. 历史证据命令

S-07/P0-M1B/任务 5/任务 6 的旧复核命令已移至[历史运行说明](../../../s07/docs/archive/p0/S07_LEGACY_RUNBOOK.md)。
除非用户明确要求追溯旧证据，当前开发与部署不读取或执行这些命令。
