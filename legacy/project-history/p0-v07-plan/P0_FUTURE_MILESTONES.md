# P0 v0.7 后续里程碑承接

> 状态：`PLANNED / NOT_NEXT`  
> 当前仍只执行 [P0-V07-M1](P0_V07_M1_BACKLOG.md)。本文件承接 M3、M5、M6 已识别但尚未进入执行窗口的规则输入。

## M3：S-09 决定输入

历史来源：[旧 M1-03 B](../p0/P0_V06_M1_BATCH_B_S09.md)。S-09 是后端确定性质量评估，不是外部科学工具。

| ID | 已明确 | M3 必须收敛 |
|---|---|---|
| P0-Q08 | X-ray 2.5 Å=high；cryo-EM 3.8 Å=medium；`topology_reliable` 与 confidence 独立 | X-ray 4.0 Å、null、NMR 未覆盖区间、OTHER/非法 resolution 的无重叠决策表 |
| P0-Q09 | pTM `>=0.50`；实验结构 mask=null；低分阈值/最小段长/合并间隔已有值 | pLDDT 0.50/0.70 边界、global/mean/per-residue 优先级、异常数组、掩码顺序、坐标及 empty/null/partial 语义 |

退出条件：具名算法负责人确认完整决策表或伪代码；边界 fixtures 覆盖等号、缺值和异常；明确 S-11 门控消费；来源、版本与日期可审计。

## M5：R-58 与 FreeSASA 决定输入

历史来源：[旧 M1-03 C](../p0/P0_V06_M1_BATCH_C_S11.md)。已明确结构工具前执行序列—结构映射，partial 保持等长 null，多链无法唯一确定时禁止自动交接；SASA 单位为 Å²，RSA 使用 Tien 2013 `Theoretical`，埋藏阈值严格为 `<0.20`。

| 决定包 | M5 必须收敛 |
|---|---|
| OI-015 / P0-Q12 | 比对算法与参数、substitution/indel/tag/截短、sequence/coordinate coverage、chain/model/assembly 与并列、insertion code、目标位点不可映射和停止状态 |
| P0-Q13 | FreeSASA 版本、算法、probe radius、原子半径、复合物范围、altloc/occupancy/非标准原子、null/全空、NaN/越界与浮点容差 |

退出条件：形成版本化 mapping/parameter profile；完成完整、partial、多链、iCode 和 SASA/RSA 边界 fixtures；执行真实 G0 并保留原始输出、版本、资源和失败证据。

## M6：通用结果契约迁移

历史来源：[S-07 任务 5 契约](../../s07/docs/archive/p0/S07_TASK5_RESULT_CONTRACT.md)。只迁移通用工程不变量，不迁移 S-07 候选、来源状态或联网路由：

- 统一运行状态、稳定 `ToolError`、warning 与 `retryable` 语义；
- `ArtifactRef` 记录哈希、大小、类型、生成者、输入/profile 绑定和不可变引用；
- 重复提交、attempt、取消、恢复和幂等边界与 OI-017 状态机一致；
- 原生输出、派生结果和 `P0EvidenceBundle` 分层，所有缺失值带原因；
- 四步骤分别保存版本、参数、资源、原始输出、状态与审计证据。

M6 必须基于 M1～M5 当前输入、决定和 G0 证据重新建立 Schema 与测试，不得复制旧联网 fallback。

