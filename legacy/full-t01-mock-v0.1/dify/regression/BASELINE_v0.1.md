# T01 Dify/Mock v0.1 工程基线

> 冻结日期：2026-09-01  
> 基线范围：Dify 编排、MCP 数据契约、确定性 Mock 场景和自动化取证。  
> 本基线不代表真实科学工具已经部署，也不代表科研结果或生产候选已经通过验收。

## 冻结结论

- 本地 Dify：`1.17.0`。
- Master：`T01_Master_v10`。
- 阶段 Workflow Tool：P0-P7，共 8 个。
- Mock MCP：63 个工具、25 个确定性场景，仅允许 `execution_mode=mock`。
- Master 回归批次：`master-reg-20260831-a`。
- 回归结果：25/25 PASS，0 FAIL。
- Dify PostgreSQL 取证记录：2496 条父子 Workflow/节点记录。
- Python 自动化测试：75/75 PASS（含文档结构与链接校验）。

回归报告位于本地忽略目录：

- `dify/regression/runs/master-reg-20260831-a/report.md`
- `dify/regression/runs/master-reg-20260831-a/report.json`
- `dify/regression/runs/master-reg-20260831-a/results.jsonl`
- `dify/regression/runs/master-reg-20260831-a/traces.json`

这些文件含本地实例运行证据，不纳入版本控制。其 SHA-256 记录在
`baseline_v0.1.sha256`，可用于确认本次证据是否被改写。

## 冻结内容

1. `StepRequest`、`StepResult`、`ArtifactRef`、`ToolError` 和 Provenance 契约。
2. 56 个 T-01 工具、3 个作业工具、4 个 Mock 控制工具的名称与 Mock 接口。
3. P0-P7 与 `T01_Master_v10` 的节点顺序、分支、门控和交接结构。
4. 25 个 Mock 场景的预期路径、禁止路径、关键枚举和标准错误类别。
5. Dify 1.17 的兼容处理，包括 MCP `json` 数组输出和跨 Workflow 标量 `stage_route`。
6. 不含 LLM、Code、HTTP Request 或 Question Classifier 节点的编排边界。

## 尚未冻结/仍待确认

- `QUEUED/RUNNING` 长任务的通用轮询、超时和取消子流程。
- `context_scores=NON_HIGH` 从内部 step12 恢复的业务映射。
- 数据契约第 11 节中的 `SOP_PENDING` 字段与阈值。
- Agent C 的真实接口、认证和交付确认契约。
- 所有真实科学工具、smoke/production 模式与我方服务器生产拓扑。
- 算法、业务、后端、Dify 和运维负责人的正式签字确认。

## 变更控制

冻结后如修改工具名、Schema、门控、节点连接、错误类别或场景预期，应：

1. 先修改生成源/后端源代码和测试，不直接批量修改生成后的 DSL。
2. 将基线版本提升为 `v0.2` 或更高，不覆盖本文件的 v0.1 结论。
3. 重新生成和导入 Dify DSL，发布受影响的阶段 Workflow Tool 并刷新版本。
4. 使用全新 campaign/run_id 重跑全部 25 个 Master 场景。
5. 重新执行全量 Python 测试并生成新的证据哈希。
