# 冻结旧完整 T01 Mock v0.1

本包保存旧 `T01_Master_v10 + P0-P7` 工程基线：63 个 Mock 工具入口、25 个确定性场景、
Dify 模板/绑定/回归、数据契约、运行手册和运行期数据库。它只供未来完整 T01 的历史参考，
不得驱动当前一期 `N01-N18` 的范围、排期、验收或发布。

## 目录

- `src/`：旧 Mock MCP 与 Dify 生成/回归代码。
- `tests/`：旧完整 Mock 的冻结回归。
- `dify/`：旧 Master + P0-P7 模板、绑定、fixture 和 25 场景证据。
- `工作流设计/`：旧数据契约及 Dify 接入/导入指南。
- `docs/development/RUNBOOK.md`：旧 Mock 专用运行手册。
- `scripts/`、`var/`：smoke 脚本和历史运行期文件。

## 冻结回归

从本目录运行：

```powershell
..\..\.venv\Scripts\python.exe -m pytest -q
```

需要启动或生成旧资产时先读[旧 Mock 运行手册](docs/development/RUNBOOK.md)。不得把本包的
`P0-P7` 名称、生成器或场景复制成一期实现。

