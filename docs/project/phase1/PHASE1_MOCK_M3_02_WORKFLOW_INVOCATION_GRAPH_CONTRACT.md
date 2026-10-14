# PH1-MOCK-M3-02 Workflow 调用、生命周期与画布映射契约

> 状态：`FROZEN / IMPLEMENTED / VERIFIED`  
> 冻结日期：2026-09-04  
> 依赖：[M3-01 目标预检](PHASE1_MOCK_M3_01_DIFY_TARGET_DSL_PREFLIGHT.md)、
> [M1-03 控制流](PHASE1_MOCK_M1_03_CONTROL_FLOW_STATE_GRAPH.md)、
> [M1-04 envelope](PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md)和
> [M2 实现评审](PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md)

## 1. 冻结结论

main/debug 共用一个业务图生成源、一个 provider 和同一 26-tool 闭集。Dify 只传递 canonical
request、读取后端已经给出的节点/控制事实、按固定字面量选择边并返回完整 envelope。业务真值、
运行状态、幂等、取消、恢复和 checkpoint 推进仍由 M2 后端及显式验收驱动器负责。

画布使用 59 个 Dify 节点和 79 条物理边表达 N01-N18 与 E001-E027。额外 Dify 节点只是 start、
条件判断、上下文聚合、明确 skip、汇合、最终化和 end 等编排结构，不引入 N19+ 业务身份。

## 2. Workflow 输入与输出

Workflow start 只接受下列编排输入：

| 字段 | 责任 |
|---|---|
| `operation` | `SUBMIT` 或 `FINALIZE_EXISTING`；选择新提交/重放与既有运行最终化观察 |
| `request_json` | `SUBMIT` 时携带完整 M1-04 canonical request JSON；Dify 不改写其规范 ID |
| `run_id_override` | `FINALIZE_EXISTING` 时携带后端已有规范 `run_id`；不得填写 Dify workflow run ID |

正常结束输出 `envelope`、`submission_action` 和 `canonical_run_id`。幂等冲突在专用拒绝 end 输出
初始化工具的结构化 `submission`、`submission_action=REJECT_REQUEST` 和 `error_code`。输出中的
canonical envelope 仍须符合 M1-04 Schema；Dify system ID 只保留在外部运行映射证据中。

## 3. 两种调用模式

```text
SUBMIT
  -> run.initialize(request_json)
  -> REJECT_REQUEST ? rejected end : canonical run context
  -> 当前场景所需节点/控制路径
  -> run.finalize(run_id)
  -> canonical envelope

FINALIZE_EXISTING
  -> canonical run context(run_id_override)
  -> 当前运行所需节点/控制路径
  -> run.finalize(run_id)
  -> canonical envelope
```

`RETURN_EXISTING_RUN` 是后端幂等重放事实；Dify 仍观察同一个 canonical run。`REJECT_REQUEST`
不会创建新 run。目标实例每次调用产生的 Dify workflow run ID 与 canonical run ID 分开记录。

## 4. Checkpoint、取消与恢复

4 份 checkpoint plan 的 16 个步骤由验收驱动器按 M1-07 明确序列推进：`POLL`、场景事件注入、
`CANCEL` 或 `RECOVER`。推进依据只来自计划中的 `checkpoint_fact`，不用墙钟、Dify 重试次数或 LLM
推断。恢复时 M2 后端创建新的 canonical `run_id` 并保留 `recovery_of_run_id`；之后用
`FINALIZE_EXISTING` 观察新 run 的最终 envelope。

因此 Dify Workflow 不注册 poll/inject/cancel/recover 业务工具，也不自行伪造异步过程。每个阶段
的 23 次 canonical submission 与 4 次最终化观察分别计数，后者不是额外 submission。

## 5. 业务图映射

| 业务结构 | Dify 映射 | 控制来源 |
|---|---|---|
| E001-E010 | N01-N10 tool 与逐节点成功检查串联 | 节点 envelope 的固定状态 |
| E011 | N10 成功后调用设计适用性控制工具 | `SCENARIO_LITERAL` |
| E012-E013 | `DESIGN_NOT_SUITABLE` → 明确 WT settled → N18 入口 | `design_suitability.decision` |
| E014 | 适合设计 → N11/N12 路径 | 同上 |
| E015-E018 | N11/N12 最多三轮物理展开；通过、重算或耗尽 | `n12_validation.decision_1..3` |
| E019-E021 | N13→N14→N15 及交付建议 | 节点状态与 `n15_delivery_recommendation` |
| E022-E025 | N16/N17 两支分别执行或明确 skip | `n16_applicability`、`n17_applicability` |
| E026 | 两支 settled 后汇合到 N18 入口控制 | aggregator 只聚合状态，不判定业务结果 |
| E027 | N18 后调用最终化工具并返回 envelope | 后端运行事实 |

所有节点失败检查和 N12 耗尽都 fail closed 到最终化工具，由后端返回相应失败 envelope。画布不从
节点 payload 数值推导 Gate、Hard Filter、Pareto、重算、条件或 join 结论。

## 6. N12 有界重算责任

N11/N12 在画布上展开为 C1、C2、C3 三组物理 tool 节点，但每组分别携带稳定业务身份 `N11`、
`N12` 和显式 cycle。是否进入下一轮只读取 N12 控制工具返回的 `decision_1..3`：

- `RECALC_REQUIRED` 才进入下一轮；
- 非重算结果进入 N13；
- 第三轮 `RECALC_EXHAUSTED` 进入失败最终化；
- 不存在第四轮、隐式回边或 Dify 自主重试。

## 7. N16/N17 与 N18 汇合责任

N15 后同时取得 N16、N17 适用性字面量。每支只在 `EXECUTE` 时调用对应节点工具；否则通过固定
`NOT_EXECUTED` 结构进入汇合。aggregator 仅证明两支都已 settled，N18 是否可进入仍由
`n18_entry` 控制工具给出。失败、超时、部分交付和跳过语义均来自场景/后端，不由模板计算。

## 8. Main/debug 唯一差异

两个模板的规范化业务图必须完全相等。允许的模板展示差异只有 app 名称、图标背景、稳定
workflow/template ID 与 role 描述；运行结果只允许以下外部观测指针不同：

```text
/dify_observability/app_id
/dify_observability/workflow_id
/dify_observability/workflow_run_id
/dify_observability/role
```

归一化不得移除 request、canonical ID、节点状态、attempt、控制、边、错误、ArtifactRef、审计、
handoff 或最终状态。任一其他差异均阻断 parity。

## 9. 实现与验证映射

- 唯一图生成源：`src/t01_phase1_mock/dify/generator.py`；
- 静态合同：`src/t01_phase1_mock/dify/validator.py`；
- 生命周期与证据组装：`src/t01_phase1_mock/dify/runner.py`；
- 观测差异归一化：`src/t01_phase1_mock/dify/normalization.py`；
- transport 只代理 M2 `MockToolFacade`，不含业务判断；
- 模板、bound、导入回读和实例运行最终以
  [M3 实现评审](PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md)及机器证据判定。

本契约冻结的是 Dify 工程映射，不修改 M1-03/M1-04/M1-05，也不提前定义真实科学 Workflow。
