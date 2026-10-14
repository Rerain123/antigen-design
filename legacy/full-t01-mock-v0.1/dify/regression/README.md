# T01 Master 25 场景回归

本目录用于验证 `T01_Master_v10` 在 Dify 中的实际编排路径。回归仍由 Dify 执行，
脚本只负责生成输入、调用 Workflow Service API（或接收编辑器手工/自动测试结果）、
读取本地 Dify 追踪记录并对照预期；
它不参与任何科学计算。

## 固定资产

- `master_expected_25.json`：25 个 Mock 场景的预期路径、关键枚举、终态和禁止路径。
- `BASELINE_v0.1.md` / `baseline_v0.1.sha256`：已通过基线、开放项和证据哈希。
- `../fixtures/master_input.example.json`：所有场景共用的基础 T-01 输入。场景差异由 Mock 后端确定性注入。
- `../scripts/master_regression.py`：准备、执行、取证和报告入口。

每轮产生的输入、原始响应、追踪和报告保存到 `runs/<campaign>/`，该目录不纳入版本控制，
避免把本地实例日志或未来可能包含业务输入的证据误提交。

## 前置条件

1. 本地 Dify 和 Mock MCP 正常运行。
2. 编辑器运行模式不要求发布 Master，也不要求 API Key。
3. 仅在使用 Workflow Service API 模式时，发布 `T01_Master_v10` 当前版本，并在
   “访问点 / API 访问”中创建一个本地测试 API Key。
4. API 模式的 Key 只放进当前 PowerShell 会话的环境变量，不写入项目文件：

```powershell
$env:DIFY_API_KEY = "app-仅粘贴到当前终端"
```

## 一轮完整回归

以下示例使用批次名 `master-reg-20260831-a`；重新执行时必须换一个批次名，确保每个
`run_id` 唯一。

```powershell
$campaign = "master-reg-20260831-a"
$runDir = ".\dify\regression\runs\$campaign"

.\.venv\Scripts\python.exe .\dify\scripts\master_regression.py prepare `
  --campaign $campaign

.\.venv\Scripts\python.exe .\dify\scripts\master_regression.py run `
  --manifest "$runDir\manifest.json" `
  --results "$runDir\results.jsonl" `
  --base-url http://localhost

.\.venv\Scripts\python.exe .\dify\scripts\master_regression.py collect `
  --results "$runDir\results.jsonl" `
  --traces "$runDir\traces.json"

.\.venv\Scripts\python.exe .\dify\scripts\master_regression.py report `
  --manifest "$runDir\manifest.json" `
  --results "$runDir\results.jsonl" `
  --traces "$runDir\traces.json" `
  --report-json "$runDir\report.json" `
  --report-md "$runDir\report.md"
```

`run` 默认支持断点续跑：已有 `run_id` 的记录不会重复提交。API Key 不会写入输入、
响应、追踪或报告。

## 编辑器运行模式（无需 API Key）

如果 Master 尚未发布或暂时不创建 API Key，可按 `inputs.csv` 在 Dify 的“测试运行”
中执行场景。执行后用同一份 `manifest.json` 从本地 PostgreSQL 生成 API 形状的结果记录
和完整追踪：

```powershell
.\.venv\Scripts\python.exe .\dify\scripts\master_regression.py collect-editor `
  --manifest "$runDir\manifest.json" `
  --results "$runDir\results.jsonl" `
  --traces "$runDir\traces.json"
```

该命令只输出已经完成的 Master 运行；尚未执行的场景不会伪造记录，并会在报告中明确
显示为缺失。重复执行会用数据库中的最新已完成记录重建 `results.jsonl`。

## 生成文件

- `manifest.json`：本轮唯一 run_id、四个 Master 输入和展开后的预期规则。
- `inputs.csv`：UTF-8 BOM 的四列输入文件，可用于人工核对或兼容的 Dify 批量入口。
- `results.jsonl`：Dify Workflow API 原始响应，或由编辑器运行的顶层数据库记录转换而来；每场景一行。
- `traces.json`：从本地 Dify PostgreSQL 只读取出的父子 Workflow 与节点证据。
- `report.json` / `report.md`：自动比对结果。

判定为 PASS 至少要求：顶层状态正确、必经节点出现、禁止节点未出现、关键后端枚举或
错误类别与预期一致。Mock PASS 只表示契约和路由正确，不表示真实科学工具已部署。
