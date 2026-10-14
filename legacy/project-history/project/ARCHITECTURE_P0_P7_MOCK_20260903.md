# T-01 P0-P7 Mock 架构（已归档）

> `LEGACY_REFERENCE 2026-09-04`：本文描述冻结旧 Mock 拓扑，不是当前一期目标架构。
> 现行架构见[一期 18 节点架构](../../../docs/project/ARCHITECTURE.md)。

## 目标

T-01 实现单蛋白精修链的可审计智能体。系统通过 Dify 展示完整流程，通过 MCP 调用
后端能力，并将每个科学步骤的输入、状态、产物、错误和来源结构化保存。

架构的关键目的不是让 LLM 计算，而是让复杂科学流程可编排、可追踪、可复现和可替换。

一期生产能力范围以[一期 18 节点范围重基线](PHASE1_SCOPE_WITH_P0_MAPPING_20260903.md)为准。
本文保留的旧 Master/P0-P7 名称描述的是已冻结 Dify/Mock v0.1 拓扑，不表示名称中的
Safety、MD 或其他已排除能力仍属于生产一期。P0 v0.7 的生产入口为必填目标蛋白序列、宿主物种
和可选结构；有合法结构时直接质量评估，无结构时运行部署在甲方服务器上的 AlphaFold3/ESMFold2。
内网只排除 S-07、RCSB PDB、AlphaFold DB 和相关外部查询，不限制本地科学工具运行。

## 目标拓扑

```text
用户 / 上层 Agent
  -> Dify T01_Master_v10
  -> 8 个阶段 Workflow Tool（P0-P7）
  -> T-01 MCP 服务
  -> Schema、门控、状态、队列和数据处理层
  -> 隔离的科学工具 Worker
  -> 对象存储、日志、产物和审计信息
```

本文只定义智能体、Dify、MCP、后端和 Worker 之间的逻辑服务边界。

## 组件职责

### LLM / 上层 Agent

- 收集用户目标和输入。
- 询问缺失字段。
- 选择并调用已定义工具。
- 等待任务完成并解释后端返回的事实。

不得执行科学计算、阈值判断、Hard Filter、Pareto、权限合成、排序或结果补猜。

### Dify

- 可视化编排 Master 和阶段工作流。
- 根据后端返回的固定枚举或布尔值路由。
- 展示运行节点、耗时、输入输出和错误。
- 为调试与回归保留父子 Workflow 追踪。

Dify 不承担科学计算或内部数据加工。Variable Aggregator 只汇合互斥分支，不合成科学结论。
科学工具与后端契约先独立设计、实现和验收；Dify 在阶段工具包完成后进行集成验证与编排。若
Dify 存在字段形态、大小或版本兼容问题，应在 MCP facade/Dify binding 增加专用 projection 或
adapter，不得反向改变后端权威结果和科学产物。

### MCP / 后端

- 校验 Schema 和输入范围。
- 实现门控、重试、超时、取消、过滤、排序和数据处理。
- 管理幂等键、运行状态、作业状态和错误分类。
- 校验产物完整性并记录 Provenance。
- 将科学工作交给隔离 Worker。

### 科学工具 Worker

- 在固定版本和资源配置下运行具体软件。
- 保存原始输入、标准输出、错误日志和原始产物。
- 返回机器可验证的状态与产物引用，不让 LLM解释为计算结果。

## Dify 工作流

已冻结 Dify/Mock v0.1 阶段名称：

1. `T01_P0_Structure`
2. `T01_P1_EpitopeSafety`
3. `T01_P2_ConservationDomain`
4. `T01_P3_WTDevelopability`
5. `T01_P4_Design`
6. `T01_P5_VariantEvaluation`
7. `T01_P6_CodonStabilityMD`
8. `T01_P7_OutputHandoff`

`T01_Master_v10` 是总控工作流。另有 8 个 `_Debug` 工作流用于独立初始化 Mock 场景，
正式阶段不包含该初始化节点，供 Master 作为 Workflow Tool 调用。

生产迁移仍按 P0→P7 的依赖分区推进，但每个阶段的实际节点以最新一期范围为准；S-23、
S-32/MD 等明确排除路径只留在旧 Mock 回归中。对应阶段达到 G4 时再为生产 DSL 升版、改名或
删除旧节点，并建立新的回归基线，不直接覆盖现有 v0.1 资产。

允许的画布节点类型为 Start、Tool、IF/ELSE、Variable Aggregator 和 End。当前模板不含
LLM、Code、HTTP Request 或 Question Classifier。

## 数据契约原则

- 所有工具使用统一的 `StepRequest` / `StepResult`。
- 产物使用 `ArtifactRef`，不得泄漏服务器绝对路径。
- 错误使用稳定的 `ToolError` 类别，不以异常文本驱动路由。
- 每个结果记录适配器、工具、模型、参数、哈希、时间与退出码等 Provenance。
- 长任务使用 `QUEUED/RUNNING` 和独立 `job_id`；终态不得伪装为运行中。
- Mock 结果必须标记 `MOCK_DATA` 和 `scientific_compute=false`。
- 通用后端结果保持调用方中立；Dify 跑通只证明编排与集成可用，不代替后端单测、科学验收和
  artifact 复现证据。

完整字段定义见 [数据契约](../../full-t01-mock-v0.1/工作流设计/02-数据契约/T01_Dify节点-MCP工具映射与数据契约_v0.1.md)。

## 代码与资产边界

- `src/t01_mock_mcp/`：契约、工具目录、场景引擎、SQLite 状态和 MCP 服务。
- `src/t01_dify_workflows/generator.py`：Dify DSL 的唯一生成源。
- `src/t01_dify_workflows/regression.py`：Master 回归、取证和报告逻辑。
- `dify/templates/`：带实例占位符的版本化模板。
- `dify/bound/`：当前实例绑定后的本地导入文件，不是通用源文件。
- `tests/`：契约、流程结构、场景、状态和回归校验。

## 当前非目标

- 不在 Mock 阶段给出科学结论。
- 不绕过未确认 SOP 提供默认阈值。
