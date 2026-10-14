# 历史工具交接资料

这里保留原 FreeSASA、BepiPred 工具分工方案的说明与 ZIP；该安排已由 [取消分工决定](../../DECISIONS.md#取消同事工具分工)覆盖。
包内“同事 A/B”、发包与回传要求均属于原方案，不能作为当前任务指派。主线执行入口见 [STATUS](../../STATUS.md)。
两包的接口来源是 [公共接口 v0.1](../../../../工作流设计/02-数据契约/tool-interface-v0.1/README.md)，包内 interface 保留对应副本；工程约定仍可供主线复用。

| 任务 | 原拟接收角色 | 先读 | 交接快照 |
|---|---|---|---|
| PH1-TOOL-FREESASA | 同事 A | [FreeSASA 开始说明](PH1-TOOL-FREESASA/README.md) | [FreeSASA 任务包 v0.1](releases/PH1-TOOL-FREESASA-v0.1.zip) |
| PH1-TOOL-BEPIPRED | 同事 B | [BepiPred 开始说明](PH1-TOOL-BEPIPRED/README.md) | [BepiPred 任务包 v0.1](releases/PH1-TOOL-BEPIPRED-v0.1.zip) |

两包可独立解压阅读，包含必要的专家原件副本、教学示例、验收清单和回传模板。
它们是原开发任务资料，不含已实现适配器、模型权重或真实科学验收样本；后续实现按主线任务包安排。

## 正式交接前核对什么

以下仅保留当时的交接检查项，用于追溯，不是当前发包或人员分配步骤：

1. 核对当时剩余任务，再告知每位同事目标环境、可用访问、安装位置与数据使用范围；凭据用受控渠道提供。
2. 为 FreeSASA 提供真实结构样本、输入序列和已核验映射；明确 MODEL/多链计算上下文及格式转换方式。
3. 为 BepiPred 提供可用来源的真实样本，确认软件/模型使用条件；牵头处理 BP-D02 的分数列、Top20% 和峰合并细节。
4. 按每包的回传模板评审第一次结果。主开发评审工程接口，科学预期和容差由算法验收人确认。
5. G0 工具事实与 G1 规则/接口就绪后放行对应适配器实现；正式主流程仍按 W1–W7 集成和验收。

FreeSASA 对应 [W1](../PHASE1_REAL_W1_BACKLOG.md)的 W1-03/06/07 子任务；
BepiPred 是 W2 N04 的提前独立准备。相关工具成果分别回填对应波次，不能把它们的单工具通过
记作 W1 或 W2 整体完成，也不改动已冻结 Mock。

## 如何交接与维护

历史阅读顺序为各包 README、实现说明和原件索引。包目录及 ZIP 保留原字节，不因取消分工而重新打包。
原维护流程使用 [打包脚本](../../../../scripts/package_tool_handoffs.py)同步公共接口副本、生成 ZIP、清单与 SHA-256；日常只读核验条件见 [运行手册](../../../development/RUNBOOK.md#真实工具公共接口与交接包)。
[发布清单](releases/RELEASES.json)记录压缩包身份与哈希，包内 PACKAGE_MANIFEST.json 记录文件哈希。
[打包验证记录](releases/PACKAGE_VERIFICATION.json)记录 ZIP 内容一致性、包内链接、JSON 示例和原件副本校验；它不属于工具实测或科学验收。
原件副本与来源哈希保持一致；后续裁决写派生说明，不改写副本。当时按用户决定直接更新两个 v0.1 包，不另保留旧版；历史包身份以发布清单的 SHA-256 为准。

相关规则缺口见 [开放项](../../OPEN_ITEMS.md)，分工决定见 [决定登记](../../DECISIONS.md)。
