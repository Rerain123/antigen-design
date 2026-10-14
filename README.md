# T-01 单蛋白精修链智能体

> **GitHub公开版：** 本仓库包含完整项目交接范围内的代码、文档与归档资料，排除专家原件及凭据。部分历史压缩包/部署载荷已过滤专家成员，使用前请读 [公开范围与校验限制](docs/PUBLIC_SCOPE.md)。


T-01 面向单个目标蛋白，完成结构与基础分析、表位与保守性证据、设计、验证、排序和结果交付。
LLM/Dify 负责编排与解释，科学计算、门控和数据处理由 MCP/后端完成。

## 一期流程

```text
目标蛋白序列 + 宿主物种 + 可选结构
  -> N01 -> N02 -> N03（本地 BLAST）-> N04 ... N10 -> 设计适用性判断
                    ├─ 不适合：WT 评估 -----------------> N18 交付
                    └─ 适合：N11 -> N12 -> N13 -> N14 -> N15
                                                       ├-> N16 -> N18
                                                       └-> N17 -> N18
```

一期保留原 18 个节点及编号，N03 按最新用户决定采用 IEDB 本地镜像＋BLAST。节点 01 接收本地结构，或使用本地
AlphaFold3/ESMFold2；其余保留的数据库能力使用批准的本地数据包。具体范围见下方基线，业务范围不代表工具已部署。

## 从这里开始

**科学规则与验收要求以专家原件为准；以下计划和实现说明均为派生文件。**

- **同事接手：先读 [项目交接入口](docs/project/HANDOFF.md)**，其中说明仓库资料、外部资产、开发检查、发布方式及权限交接。
- [专家权威依据](工作流设计/01-业务依据/README.md)
- [当前状态与下一任务](docs/project/STATUS.md)
- [一期范围](docs/project/PHASE1_SCOPE_REBASELINE.md)
- [一期交付计划](docs/project/PHASE1_DELIVERY_PLAN.md)
- [一期任务与冻结基线索引](docs/project/phase1/README.md)
- [开发运行手册](docs/development/RUNBOOK.md)
- [已完成成果与历史](docs/project/history/README.md)
- [完整文档导航](docs/README.md)

AI 接手规则见 [AGENTS.md](AGENTS.md)。旧 P0-P7 Mock 与 S07 从
[历史工程资产](legacy/README.md)追溯，不参与一期范围、完成度或生产验收。
Mock 结果只能用于工程调试和回归。
