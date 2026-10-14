# PH1-REAL-W1：N01–N02 输入、结构与基础分析

> 2026-09-25 管理归类：本页保留阶段接口和历史验收细节；以下旧排期按原时点解释。唯一当前执行包为[总计划](../PHASE1_DELIVERY_PLAN.md)的 PH1-REAL-GAP-1，当前进度见 STATUS。

> 2026-09-21 历史排期：当时执行 M1/P1–P4，仅验有限工程路径。该阶段的简化和暂定处理不适用于当前功能完成判定；当前须按[总计划的原文落实原则](../PHASE1_DELIVERY_PLAN.md#按原件补齐的执行原则)执行，不能以阶段页遗漏或旧停止条件省略专家条款。

> 更新：2026-09-21。本页维护阶段目标和完成标准；当前状态只见 [STATUS](../STATUS.md)，跨阶段顺序见 [总计划](../PHASE1_DELIVERY_PLAN.md)。

## 专家依据与阶段目标

依据 [专家权威索引](../../../工作流设计/01-业务依据/README.md)：结构链 ToolSpec S-08/S-09、A5 DeepTMHMM、C34 FreeSASA；SKILL R-58、SOP 对应步骤。本页是派生交付安排，范围及获准修订见 [一期范围](../PHASE1_SCOPE_REBASELINE.md)。

交付本阶段保留节点的真实可追溯业务能力；独立工程、目标环境、科学消费和完整节点完成分别判断。

## 已有成果

运行层、本地结构摄取/映射、DeepTMHMM 与条件 FreeSASA 已有独立工程成果；ESMFold2 统一任务、N01 与 N12 工程来源链已有证据。

历史批次、接口形成过程及原验收边界见 [整理前完整记录](../history/deployment/before-20260921/docs/project/phase1/PHASE1_REAL_W1_BACKLOG.md)；成果统一归入 [历史索引](../history/README.md)。不因本页精简而重新启动已完成任务。

## 剩余交付与完成标准

AF3 新批标准接入及 N01/S-09 验收；保持 ESMFold2 已验支持域；补齐各结构消费域、来源/缺原子口径和 RSA 资格。

- 保留具体输入、支持域、版本/profile、原始产物与 ArtifactRef/hash；跨节点同 run、同序列及 WT 来源校验通过。
- 成功、缺项、跳过、失败、取消/超时/恢复等适用路径有真实或明确标识的工程证据；未运行不写成通过。
- 已有科学规则直接落实，独立参考与适用签收齐备后才开放消费；满足适用 G0–G6 后才能宣布完整阶段发布。

## 依赖与当前边界

OI-015/023/024/027；AF3 当前工程验收不以全部科学签收先行作为开发阻塞。

问题、主责与关闭证据单点维护在 [OPEN_ITEMS](../OPEN_ITEMS.md)，不在阶段页复制第二套问题清单。科学 Gate CLOSED、usable_for_pipeline=false 与生产 NOT_DEPLOYED 不因独立工具成功而解除。

## 实施与验收入口

- [统一工具接口参考](../../development/TOOL_INTERFACES.md)：既有调用和字段说明；精确接口以固定源码/profile 为准。
- [运行手册](../../development/RUNBOOK.md)：按本次影响范围选检查，旧批次不可覆盖。
- [当前部署包](PHASE1_REAL_TARGET_DEPLOY_PLAN.md)：目标环境、AF3 接入和受影响 GPU 回归。
