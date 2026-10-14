# M1-03 批次 C：OI-015、R-58 与 FreeSASA

> 提交顺序：C（第 3 批）  
> 覆盖索引：`OI-015 + P0-Q12/P0-Q13`  
> 唯一问题：C-01=OI-015/P0-Q12 映射；C-02=P0-Q13 数值参数  
> 当前状态：`OI-015 BLOCKED / S-11 G0_NOT_STARTED / EXPERT_DECISION_REQUIRED`  
> 重要说明：本批建议尚未成为科学规则；OI-015 未解除前不得实现生产 S-11 适配器

## 1. 给专家的一页摘要

权威资料已经明确：FreeSASA 前必须执行 R-58；partial 缺失位置保持等长 null；多链无法唯一
确定时禁止自动交接；SASA 用 Å²，RSA 用 Tien 2013 Gly-X-Gly `Theoretical` 表，埋藏阈值严格
为 `<0.20`，分母为输入序列全长。真正缺失的是两组不同决定：

| 唯一问题 | 已明确 | 待决定 |
|---|---|---|
| C-01 / OI-015 + P0-Q12 | 比对前置、多链/插入码必须映射、歧义阻止自动交接、partial=null | 比对算法/参数、允许替换/截短/标签、chain/model/assembly、覆盖阈值、目标位点与复核转移 |
| C-02 / P0-Q13 | 全原子绝对 SASA、参考面积表、`RSA<0.20`、全长分母、A/R/G 数值 | FreeSASA 算法/探针/半径、复合物范围、altloc/非标准原子、null/全空/NaN/RSA>1 |

OI-015 是 C-01 的父门禁，不另发一个重复“R-58 怎么做”的问题。映射规则通过不代表 FreeSASA
数值口径已冻结，反之亦然。

## 2. C-01：OI-015 / P0-Q12——R-58 可执行映射

### 原文出处与已明确事实

- [Agent A SKILL](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md)
  R-58 L173：所有结构类工具消费前进行结构序列↔输入序列比对；partial 缺失区域 null；多链用
  与输入一致的设计链，其他链 fixed；无法唯一确定、插入码无法解析或映射失败时 failure 级
  WARNING、强制复核并禁止自动交接。
- [Agent A SOP](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)
  S-11 L386–397：函数签名只写 `structure{pdb_path}`，但操作又依赖输入 seq、PDB 坐标映射和
  `len(seq)`；正式输入上下文尚未承载齐全。
- [FreeSASA ToolSpec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C34_FreeSASA_v10.5.md)
  L11/L17–18/L22 重述映射与 partial 规则，但没有给比对程序、参数或阈值。
- [一期边界 PDF](../../../工作流设计/01-业务依据/抗原智能体一阶段边界及核心能力说明.pdf)
  第 10 页要求多链结构或特殊残基编号先确认目标链及序列—结构对应关系。

### 现有实测影响

[S-07 任务 3](../../s07/discovery/p0/s07/p0-s07-task3-mmseqs-20260902-a/reports/TASK3_EVIDENCE_REPORT.md)
提供了可复用但不能替代 S-11 金标准的映射事实：

- 6Q00 A 链：输入 76/76，实际坐标也是 76/76，可形成完整映射；
- 9R2Q：K/L/M/N 四链对 TP53 输入都达到 identity=1、query coverage=1，但每链只有 200/393
  个输入位置有坐标（50.89%，位置 92–291），必须标 partial；四链同等匹配，按 R-58 阻止自动
  交接。

这证明“序列检索 coverage=100%”不能代替坐标 coverage，也证明只取第一条链会改变结果。现有
证据没有验证 FreeSASA、插入码或允许差异阈值，不能据此关闭 OI-015。

### 建议提交专家的暂行规则（尚未采用）

1. S-11 输入必须同时绑定规范输入序列、不可变结构 ArtifactRef、候选的 chain/model/assembly
   上下文和版本化 `alignment_profile_id`；不得只传 `pdb_path`。
2. 完整一一映射且设计链唯一时可自动继续；缺坐标但序列位置可唯一映射时保留输入等长数组并在
   对应位置置 null+WARNING。
3. 在专家明确允许的差异表形成前，替换、indel、N/C 端标签/截短、多个同等最佳链、model 或
   assembly 歧义一律进入 `requires_review`，不自动把 FreeSASA 结果用于验证/交付。
4. 映射键同时保存输入 1-based position、chain_id、author resSeq+iCode、标准编号和 model；iCode
   不能解析时沿用 R-58 阻断。
5. 映射报告必须分别给 sequence identity/query coverage、coordinate coverage、缺失/替换/插入、
   多链候选、选择理由和目标位点可映射性，不能用一个 coverage 代表全部事实。

该建议只定义安全停止边界；具体 alignment 算法、参数与允许差异仍必须由专家确认后写入 profile。

### 可选替代规则

1. 只允许全长、完全相同且坐标完整的结构自动计算；任何 partial/差异都转 S-08 或人工复核。
2. 允许达到指定 identity/coverage 的替换、截短或 indel；须给算法、gap/末端处理、阈值及等号。
3. 允许 partial 自动计算可映射区；须定义最小 coordinate coverage、关键位点不可映射时的处置和
   buried_fraction 分母。
4. 多条同等匹配链按 assembly、chain ID、occupancy 或其他指标自动选；须给权威排序和并列规则。
5. 不唯一时对所有候选链分别计算并返回人工比较；须说明是否可进入后续自动消费。

### 必须覆盖的边界案例

- 6Q00 式全长完整一链；9R2Q 式序列完整但坐标 partial 且多链同等匹配；
- 两条完全相同链、只有一条坐标更完整、或不同 assembly 中链重复；
- 内部缺失残基、N/C 端截短、表达标签、信号肽切除；
- 单点替换、未知残基 X、selenomet/非标准残基和 insertion/deletion；
- author resSeq+iCode（如 100、100A、100B）及 mmCIF label/auth 编号差异；
- 多 model/NMR ensemble；目标位点恰位于缺失或歧义位置；
- identity/coverage 恰好等于允许阈值；alignment 多个同分解。

### 请专家填写

| 字段 | 答复 |
|---|---|
| 比对算法、版本、参数 | 待填写 |
| 允许 substitution/indel/tag/截短 | 待填写 |
| sequence/coordinate coverage 阈值与等号 | 待填写 |
| chain/model/assembly 选择与并列 | 待填写 |
| 目标位点不可映射时的处置 | 待填写 |
| 自动继续/强制复核/失败状态 | 待填写 |
| 确认人、角色、日期、规则版本 | 待填写 |

## 3. C-02：P0-Q13——FreeSASA 数值和参数口径

### 原文出处与已明确事实

- Agent A SOP S-11 L394–397：per-residue 绝对 SASA（Å²）→Tien 2013 参考面积归一化，
  `buried_fraction=count(RSA<0.20)/len(seq)`。
- FreeSASA ToolSpec L19–22/L26–56：全原子主链+侧链 SASA；锁定 Tien 2013 Gly-X-Gly
  `Theoretical` 列；A/R/G 为 129.0/274.0/104.0 Å²；partial/不可算位置为 null+WARNING；
  非标准残基不按 G 兜底。
- Agent A SKILL R-24 L111：`RSA<0.20` 不优先，因此 0.20 本身不属于 buried。
- FreeSASA ToolSpec L8 和一期环境清单 C34 行：版本尚未锁定，当前只写 pip/削减池。

### 现有实测/验证状态与影响

当前没有锁定 FreeSASA 版本、算法、探针、原子半径或结构范围的 S-11 G0；也没有真实
FreeSASA 金标准。现有 A/R/G 数值只是参考表检查点，不是工具运行结果。

下列选择会直接改变数值：在设计链单独计算或在复合物中计算会改变界面 SASA；altloc、非标准
原子和缺原子会改变残基绝对 SASA；`[0.10, null, 0.30]` 若用全长分母得到 1/3，若只用有效值
分母得到 1/2；全 null 若机械计算 count/len 会得到 0，可能被误解为“没有埋藏残基”；RSA>1
若裁剪会掩盖原始计算/参考表差异。因为尚未 G0，本批只请求参数决定，不宣称已观察到某个生产值。

### 建议提交专家的暂行规则（尚未采用）

1. 生产前必须建立显式、版本化 FreeSASA parameter profile；记录精确版本、算法、探针半径、
   原子半径集、chain/model/assembly 范围、altloc 和非标准原子策略，不依赖未记录的库默认值。
2. 保留原始绝对 SASA 与未裁剪的计算 RSA；RSA>1/NaN/负值进入 WARNING/复核，不在专家确认前
   静默 clamp、置 0 或删除。
3. partial/null 不计入 `<0.20` 的 numerator，denominator 仍按原文 `len(input_sequence)`；全 null
   时建议 `buried_fraction=null + unreliable/requires_review`，避免把不可算写成 0。
4. 非标准/未知残基继续 null+WARNING，不按 Gly 或其他残基替代；是否允许 MSE→MET 等等价映射
   由专家明确列白名单。
5. 设计链单独计算还是在完整生物学 assembly/复合物环境中计算必须由 profile 指定；在决定前不
   选择默认范围。

### 可选替代规则

1. 接受某个锁定 FreeSASA 版本的全部默认参数；仍须把实际解析出的默认值写入 profile 和证据。
2. 指定自定义算法/探针/半径；须给精确数值和来源。
3. buried_fraction 只用非 null 有效残基作分母；这会改变 SOP 的 `len(seq)`，需正式修订。
4. 全 null 返回 0、failure 或 null；须选择一种并说明下游语义。
5. RSA>1 clamp 到 1、保留原值、置 null 或失败；须说明浮点容差。
6. 只算设计链、算整个文件、或算指定 biological assembly；须说明界面残基的预期。

### 必须覆盖的边界案例

- A/R/G 参考面积 129.0/274.0/104.0；RSA 恰好 0.20 与略小/略大；
- 完整数组、部分 null、全 null、空序列（应由输入守卫拒绝）；
- SASA=0、RSA<0、RSA=1、略高于 1、NaN/Infinity 与浮点容差；
- 缺原子、altloc 多构象、occupancy 并列、HETATM/水/配体；
- MSE 等非标准残基、未知残基 X；
- 单链与多链复合物、界面残基、多个 model/assembly；
- FreeSASA 运行失败、部分输出和输出长度不等于规范序列。

### 请专家填写

| 字段 | 答复 |
|---|---|
| FreeSASA 版本/算法 | 待填写 |
| probe radius/原子半径集 | 待填写 |
| chain/model/assembly/复合物范围 | 待填写 |
| altloc/occupancy/非标准原子 | 待填写 |
| null 与全空 buried_fraction | 待填写 |
| RSA 越界/NaN/浮点容差 | 待填写 |
| 确认人、角色、日期、规则版本 | 待填写 |

## 4. 批次 C 统一签收

| 项 | 专家状态 | 规则版本 | 确认人/角色 | 日期 | 后续证据 |
|---|---|---|---|---|---|
| OI-015/P0-Q12 R-58 | `PENDING` | 待填写 | 待填写 | 待填写 | mapping profile + 完整/partial/多链/iCode 金标准 |
| P0-Q13 FreeSASA | `PENDING` | 待填写 | 待填写 | 待填写 | parameter profile + 原始 SASA/RSA/资源/失败 G0 |

两题答复只是解除 M6 的规则输入；仍需锁定工具版本并完成 S-11 G0、Schema/状态契约和验收资产。
这些证据齐全前，OI-015 不得标记 VERIFIED，M6/M7 不得通过。
