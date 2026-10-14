# W1 真实运行契约 v0.1

本目录是 W1-07 的独立工程契约源。用途与科学边界见
[设计说明](../../../docs/project/phase1/PHASE1_REAL_W1_CONTRACT_DESIGN.md)，进度见 [STATUS](../../../docs/project/STATUS.md)。

| 文件 | 用途 |
|---|---|
| [contract.json](contract.json) | 命名、模块资格、工具登记、生命周期和操作语义 |
| [submit.schema.json](submit.schema.json) | 调度请求；科学请求通过不可变文件引用，不用任意科学 payload |
| [control.schema.json](control.schema.json) | 创建运行、查询、取消、显式重试的传输无关请求 |
| [job.schema.json](job.schema.json) | 任务状态与受控 ArtifactRef；科学资格另行验证 |
| [acceptance.json](acceptance.json) | 静态示例、运行层/科学待执行案例；不冒充实际运行 |
| [source_manifest.json](source_manifest.json) | 规则原件、用户决定、接口和既有原始证据的 hash |
| [B1 摄取与映射草案](b1-review/README.md) | 逐工具请求/结果配对、文件绑定与限定评审；不启用运行层科学资格 |
| [B1 输入事实扩展](b1-engineering/README.md) | 独立预检、原始元数据和作者地址；保持原摄取/映射草案 |
| [B1 → FreeSASA 开发消费者](b1-freesasa/README.md) | 显式工具路径、原始事实绑定、逐原子核实和面积回连；不授予科学资格 |
| [B2 DeepTMHMM 评审草案](b2-review/README.md) | 单序列/安全 ID、六类原始标签与四类交付、PB/null、参考与适配器放行条件 |

校验器为 [check_w1_contract.py](../../../scripts/check_w1_contract.py)。它离线读 JSON、来源和状态示例，不启动任务或科学工具。
版本 0.1.0 不代表已冻结完整生产接口；科学 payload 在逐工具 G1 后独立登记。
原 [单工具协议](../tool-interface-v0.1/README.md)继续有效，桥接关系见设计说明，不因本次取消分工重打包历史 ZIP。
