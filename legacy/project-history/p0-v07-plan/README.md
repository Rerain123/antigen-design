# P0 v0.7 已替换计划索引

> `SUPERSEDED / ARCHIVED 2026-09-04`：本目录曾尝试把一期按旧 P0-P7 工程分区实施，现已由
> 一期 18 节点计划替换。内容只作迁移证据，不得作为当前任务、范围或验收依据。

> 当前版本：v0.7  
> 当前里程碑：`P0-V07-M0 COMPLETED`  
> 下一包：`P0-V07-M1 READY_NEXT`，尚未启动  
> 生产状态：`NOT_DEPLOYED`

## 当前范围

```text
序列 + 宿主物种 + 可选结构
  -> 合法结构直接 S-09；否则本地 S-08（AF3/ESMFold2）后进入 S-09
  -> S-04 DeepTMHMM
  -> 质量/R-58 门禁后的 S-11 FreeSASA
  -> P0EvidenceBundle
```

RCSB PDB、AlphaFold DB、BLAST/UniProt 回退、S-07 与 S-06 已移出一期。当前未触发削减，S-11 仍在完整 P0 profile 中。

## 阅读顺序

| 需要回答的问题 | 当前文档 |
|---|---|
| P0 包含什么 | [P0 范围重基线](P0_SCOPE_REBASELINE.md) |
| 怎么实施、有哪些门禁 | [P0 v0.7 实施方案](P0_IMPLEMENTATION_PLAN.md) |
| 下一步具体做什么 | [P0-V07-M1 backlog](P0_V07_M1_BACKLOG.md) |
| 专家原文支持什么 | [当前专家依据矩阵](P0_EXPERT_EVIDENCE_MATRIX.md)与[来源快照](P0_EXPERT_EVIDENCE_SOURCES_20260903.json) |
| 向非专业成员解释工具 | [P0 工具说明](P0_TOOL_GUIDE.md) |
| 当前版本是否评审 | [v0.7 工程评审](P0_V07_M0_REVIEW.md) |
| 后续 M3/M5/M6 如何承接旧规则 | [计划承接材料](P0_FUTURE_MILESTONES.md) |

## 当前阻塞

- OI-023：M1 输入契约归并，`IN_REVIEW`。
- S-09 Q08/Q09：M3 决定材料。
- OI-015/R-58：M5 与 FreeSASA 的阻塞门禁。
- OI-017：原则已决定，M7 尚未实现。
- AF3/ESMFold2、DeepTMHMM、FreeSASA 的 G0 均未开始。

字段、格式、阈值或失败语义先查专家包；已有原文直接归并，只有真实冲突或缺口才定点上报。

## 历史入口

旧 v0.5/v0.6、S-07、旧 M1 与被替换的混合说明统一从[P0 历史资料索引](../README.md)进入。历史证据不得恢复为当前一期范围，也不得据此宣称部署或科学验收。
