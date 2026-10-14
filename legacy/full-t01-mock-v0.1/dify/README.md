# 冻结旧 T-01 Dify 资产

> 本目录属于旧 `Master + P0-P7` Mock v0.1，不是当前一期 N01-N18 Dify 入口。

本目录集中保存Dify侧的全部交付资产：

- `templates/`：含实例级provider占位符的9个受版本控制DSL模板。
- `config/`：当前Dify实例的MCP与Workflow Tool绑定配置示例。
- `fixtures/`：Dify调试表单和MCP节点示例输入。
- `scripts/`：DSL生成、绑定和静态校验入口。
- `bound/`：本地生成的可导入文件目录；按实例重新生成且不纳入版本控制。
- `debug/`：独立的一键Mock调试工作流；与供Master调用的阶段工作流隔离。
- `regression/`：Master 25 场景的预期矩阵、批量执行和本地追踪取证说明。

工作流设计文档是重要依据，按业务依据、数据契约和 Dify 实现整理在
[`工作流设计/`](../../../工作流设计/README.md)。允许移动整理但不得删除、清空或覆盖原始文件。
Python 实现和自动化测试分别位于 `src/t01_dify_workflows/` 与
`tests/test_dify_workflows.py`。

从 `legacy/full-t01-mock-v0.1/` 目录执行：

```powershell
..\..\.venv\Scripts\python.exe .\dify\scripts\build_dify_workflows.py validate `
  --path .\dify\templates `
  --allow-placeholders
```

完整流程见
[T01 Dify 工作流搭建与导入指南](../工作流设计/03-Dify实现/T01_Dify工作流搭建与导入指南_v0.1.md)。

## 八阶段一键调试版

一键调试版自动用 Dify 的 `sys.workflow_run_id` 创建唯一运行，并在进入对应阶段
前调用 `mock.configure_run` 绑定下拉框选中的固定场景。它不要求手工添加初始化
节点或粘贴 T-01 JSON，也不会改变供 Master 调用的正式阶段工作流。P2 额外保留
`entry_mode`，用于分别验证完整路径和 `context_only` 恢复入口。

```powershell
..\..\.venv\Scripts\python.exe .\dify\scripts\build_dify_workflows.py generate-debug
..\..\.venv\Scripts\python.exe .\dify\scripts\build_dify_workflows.py bind-debug `
  --mcp-provider-id t01-mock-mcp
```

可直接导入的 8 个本地文件按 00 至 07 生成到 `dify/debug/bound/`。
