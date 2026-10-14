# M1-03 批次 B：S-09 分档与低置信掩码

> 提交顺序：B（第 2 批）  
> 覆盖索引：`P0-Q08`、`P0-Q09`  
> 当前状态：`EXPERT_DECISION_REQUIRED / M4_BLOCKED`  
> 重要说明：本批“暂行建议”是待专家评审的提案，尚未获用户或专家批准，不是当前科学规则

## 1. 给专家的一页摘要

S-09 是后端确定性判定，不调用外部科学工具。现有原文足以固定常规样例，但在边界、缺值和掩码
顺序上不能形成唯一输出；这些差异会决定 S-11 是否执行，也会影响后续结构可信度与掩码消费。

| ID | 待决定内容 | 已明确、无需再答 | 当前阻塞 |
|---|---|---|---|
| P0-Q08 | 实验结构 method/resolution/source 的完整分档 | X-ray 2.5 Å=high；cryo-EM 3.8 Å=medium；topology_reliable 与 confidence 独立 | X-ray 4.0 Å、null、NMR 未覆盖段、其他方法 |
| P0-Q09 | 预测结构 0.50/0.70 边界、缺值优先级和掩码算法顺序 | pTM≥0.50=true；实验结构 mask=null；低分阈值/最小段长/合并间隔已有规范值 | 0.70 重叠、数组异常、4+4 合并顺序、empty/null/partial |

答复必须形成无重叠、覆盖全部输入的决策表或伪代码。无法唯一判断的分支可以明确返回复核，但
不能要求后端自行“保守默认”。

## 2. P0-Q08：实验结构分档决策表

### 原文出处与冲突

- [Agent A SOP](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)
  S-09 L291–309：
  - X-ray：`<3.0 high`、`3.0–4.0 medium`、`>4.0 or null low`；
  - NMR：非 null 且 `<3.0 high`、null medium，未覆盖非 null 且 `>=3.0`；
  - cryo-EM：`<3.5 high`、`3.5<=r<=4.0 medium`、`>4.0 or null low`；
  - L307 又写“X-ray 4.0 Å=low”；L309 又写任何 `resolution=null` 默认 medium。
- [结构链 ToolSpec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md)
  L44 概括同一分档，L87 将 S-09 `resolution=null` 统一写为 medium+WARNING。
- SOP L306–308 明确 `topology_reliable=(resolution!=null AND resolution<=4.0)`，并说明它与
  confidence 独立；但其他实验方法和非法 resolution 没有完整输出。

### 现有实测/验证状态与影响

S-09 尚未完成锁定规则后的 G0/金标准验证。现有 ToolSpec 只给三个无歧义抽象用例：X-ray
2.5 Å→high、cryo-EM 3.8 Å→medium 且 topology_reliable=true。将当前原文直接编码时，下列同一
输入可得到不同输出：

| 输入 | 原文路径 1 | 原文路径 2 | 下游影响 |
|---|---|---|---|
| X-ray 4.0 Å | `3.0–4.0`→medium | L307 注释→low | medium 会执行 S-11；low 会跳过 S-11 |
| X-ray/cryo-EM null | 方法分支→low | L309/ToolSpec L87→medium | 是否执行 S-11 相反 |
| NMR 3.0 Å 或更高 | 无分支 | 可能被泛化为实验规则 | 无法形成确定输出 |
| OTHER method + 正值/null | 无方法分支 | ELSE 只写“未知 source”而非未知 method | confidence/topology 无权威结果 |

这里的“影响”是对同一权威文本的确定性分支比较，不是生产工具实测；M4 只能在专家决定后冻结
预期。

### 建议提交专家的暂行规则（尚未采用）

1. 以方法专属分支优先：X-ray `<3 high`、`3<=r<=4 medium`、`>4 low`；cryo-EM
   `<3.5 high`、`3.5<=r<=4 medium`、`>4 low`。
2. X-ray/cryo-EM 的 null 按各自方法分支为 low；NMR null 按 NMR 专属条款为 medium。
3. NMR 非 null 且 `<3` 为 high；`>=3`、OTHER/未知方法进入 `requires_review`，在获得进一步规则
   前不自动执行 S-11。复核状态应独立于 high/medium/low，不能伪装成某一置信档。
4. 对所有受支持实验方法，合法正 resolution 按现有公式计算 topology_reliable；null/非法值为
   false。confidence 与 topology_reliable 保持独立。

建议理由：优先采用最具体的 method 分支；对原文完全未覆盖的输入显式复核，不新造科学档位。

### 可选替代规则

1. 以 SOP L309/ToolSpec L87 为准：所有实验方法 resolution=null 都为 medium+WARNING。
2. 以方法分支为准：X-ray/cryo-EM null=low，NMR null=medium；OTHER 另给固定档。
3. X-ray 4.0=low，并把 X-ray medium 改为 `3.0<=r<4.0`；需正式修订区间文本。
4. 无法覆盖的 NMR/OTHER 始终指定 low 或 medium；须解释对 S-11 门控的科学依据。
5. 引入独立 `UNDETERMINED/REVIEW_REQUIRED` 分类；须确认与现有 Schema 和路由的兼容方式。

### 必须覆盖的边界案例

- X-ray：2.999、3.0、3.999、4.0、4.001 Å；null、0、负值、NaN；
- cryo-EM：3.499、3.5、4.0、4.001 Å；null；
- NMR：null、2.999、3.0、>3.0 Å；
- OTHER/Integrative/未知 method，source 仍为 experimental；
- 未知 source 与已知 experimental source + 未知 method 的区别；
- confidence=low 但 topology_reliable=true 是否允许，以及 S-11 是否只看 confidence。

### 请专家填写

| 字段 | 答复 |
|---|---|
| X-ray 完整区间 | 待填写 |
| cryo-EM 完整区间 | 待填写 |
| NMR 完整区间/缺值 | 待填写 |
| OTHER/未知 method/source | 待填写 |
| resolution 非法值处置 | 待填写 |
| topology_reliable 与 S-11 门控 | 待填写 |
| 确认人、角色、日期、规则版本 | 待填写 |

## 3. P0-Q09：预测分档、缺值与低置信掩码

### 原文出处与缺口

- Agent A SOP S-09 L310–321：`pLDDT>=0.70 high`、`0.50–0.70 medium`、`<0.50 low`，因此
  0.70 同时落入 high 与文字区间 medium；pTM `>=0.50` 为 topology_reliable。
- SOP L311 与结构链 ToolSpec L112：AlphaFold DB 无逐残基 pLDDT 时 medium+WARNING，mask=null；
  未说明已有合法 mean/global metric 时的优先级，也未覆盖其他预测 source 缺数组。
- SOP L317 与 ToolSpec L45：[低分连续段、长度>=5、间隔<=3 合并]，但没有说明先过滤短段还是
  先合并、gap 是否纳入区间、坐标制式、null 如何切段、无命中 `[]` 还是 null。
- [一期环境清单](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期实施环境清单_v10.5.md)
  L71/L79 将 0.50、5 aa、3 aa 明确列为 E-06 可配置规范值，仍待回测，不等于算法顺序已经定义。

### 现有实测/验证状态与影响

S-07 任务 4 已观察 AFDB O15116：元数据 global metric=89.69，逐残基 confidence 均值=89.706，
两者均保留；这说明“已有均值”和“逐残基计算均值”可能同时存在且不完全相同。S-09 消费者仍为
未部署，未执行 M4 回测。

掩码顺序对一个确定性夹具有直接影响：两个各 4 aa 的 `<0.50` 段相隔 2 aa，若先过滤 `<5 aa`
则结果为空；若先合并再检查长度则形成一个 10 aa 区间。两种实现都能从现有短句推导，因而不能
先写生产测试再让测试反向决定规则。

### 建议提交专家的暂行规则（尚未采用）

1. 分档采用无重叠区间：`pLDDT>=0.70 high`；`0.50<=pLDDT<0.70 medium`；`<0.50 low`。
2. 逐残基数组存在时，后端另算 `calculated_mean`，与原生 mean/global metric 分开保存；超过专家
   指定容差时进入复核，不用一个值覆盖另一个。
3. AlphaFold DB 且逐残基数组不可用时，沿用明确特例 medium+WARNING、mask=null；其他预测源
   缺数组/均值不自动套用 AFDB 特例，进入复核。
4. 掩码算法解释为：先找最大连续 `<0.50` 段→只保留长度>=5 的段→再将保留段间隔<=3 的相邻
   段合并；输出为规范输入的 1-based、两端包含区间，合并区间包含 gap。
5. 合法数组且没有合格段时输出 `[]`；数组不可用时输出 null。输入对齐的 null 位置切断连续段，
   同时产生 WARNING；partial 不删除位置。

### 可选替代规则

1. 0.70 归 medium，把 high 改为 `>0.70`；须同步修订 R-01 的 `>=0.70`。
2. 掩码先合并所有低分段再做 5 aa 过滤；4+4/gap2 将成为一个区间。
3. gap 不计入输出，只返回多个原始段但记录同一 group；须说明消费者如何处理。
4. null 位置可跨越合并、视为低分或使整个 mask 不可靠；须选择一种并给理由。
5. 所有预测源缺逐残基数组均用 medium+WARNING；须说明缺全局均值时为何仍可定 medium。

### 必须覆盖的边界案例

- mean pLDDT：0.4999、0.50、0.6999、0.70、1.0；越界、NaN、字符串；
- pTM：0.4999、0.50、null；
- 原生 mean 与逐残基 calculated mean 相同、微差、明显不一致；
- per-residue 缺失、空数组、不等长、部分 null、越界/NaN；
- 单段长度 4/5；两段间隔 2/3/4；4+4 gap2；5+5 gap3；
- pLDDT 恰为 0.50 的位置是否属于低分段；
- 数组有效但无低分段（`[]`）与数组不可用（null）；
- partial 映射中输入位置保留 null 后的分段与坐标。

### 请专家填写

| 字段 | 答复 |
|---|---|
| 0.50/0.70 无重叠区间 | 待填写 |
| mean/global/per-residue 优先级与容差 | 待填写 |
| AFDB 及其他预测源缺值 | 待填写 |
| 掩码筛选/合并顺序 | 待填写 |
| 坐标、gap、empty/null/partial 语义 | 待填写 |
| 确认人、角色、日期、规则版本 | 待填写 |

## 4. 批次 B 统一签收

| ID | 专家状态 | 规则版本 | 确认人/角色 | 日期 | 冻结后回测 |
|---|---|---|---|---|---|
| P0-Q08 | `PENDING` | 待填写 | 待填写 | 待填写 | method/resolution 全决策表 + S-11 门控 |
| P0-Q09 | `PENDING` | 待填写 | 待填写 | 待填写 | 分档/缺值/掩码 E-06 fixtures |

两题均答复并形成无重叠规则后，M4 才能冻结确定性验证预期。材料准备、抽象样例或工程建议本身
都不解除 M4/M6/M7 门禁。
