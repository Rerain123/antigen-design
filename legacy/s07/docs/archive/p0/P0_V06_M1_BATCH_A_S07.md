# M1-03 批次 A：S-07 五项专家确认

> 提交顺序：A（第 1 批）  
> 覆盖索引：`S07-EQ-01～05`；分别承接 P0-Q02、Q03、Q04  
> 当前状态：`DEFERRED_OUT_OF_PHASE1 / DO_NOT_SUBMIT`  
> 使用限制：节点 01 内网决定已将 S-07 移出一期；本批只作历史准备材料，未来恢复时重新评审

## 1. 给专家的一页摘要

S-07 已完成固定 wwPDB/MMseqs2 的 PDB 检索/结构读取，以及 BLAST→UniProt→AlphaFold DB 官方
API 取证。原文已经明确的严格 PDB 门槛、正 Å 比较、partial/null 和正常无命中不再提问。实测只
留下以下五项会改变候选池或最终结构来源的决定：

| ID | 唯一问题 | 当前暂行建议 | 若无答复的生产边界 |
|---|---|---|---|
| S07-EQ-01 | coverage 用哪一边作分母 | query coverage；target coverage 只审计 | 不冻结自动 eligibility |
| S07-EQ-02 | NMR 与 X-ray/cryo-EM 如何排序 | 先比较 X-ray/cryo-EM 正 Å；无可比候选时进入 NMR | 多方法无法唯一时人工复核 |
| S07-EQ-03 | BLAST-derived accession 何时可自动采用 | 输入/UniProt/AFDB 模型全长序列完全一致才自动采用 | 非精确候选不自动选 |
| S07-EQ-04 | 多 accession/model 如何排序 | 先验序列，再精确 organism；仍并列则返回歧义 | 不按 API 顺序选 |
| S07-EQ-05 | UniProt 查询范围 | 当前 profile 只用 Swiss-Prot 并记录版本 | 不宣称覆盖完整 UniProtKB |

五项暂行建议均已由用户批准作为工程临时边界，但仍需专家书面确认。专家若选择其他规则，应同时
给出边界、并列/缺值处置和回测样本要求。

## 2. S07-EQ-01：PDB coverage 分母

### 原文出处

- [Agent A SOP](../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)
  S-07 L223：候选要求 `identity>95% AND coverage>90%`，未定义 coverage 分母。
- [结构链 ToolSpec](../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md)
  L25 重复该门槛，仍未区分 query/target coverage。
- 已明确边界：`>90%` 是严格大于，等于 90% 不通过；序列检索 coverage 与实际坐标 coverage
  分开，后者仍可形成 partial。

### 现有实测影响

[任务 3 报告](../../../discovery/p0/s07/p0-s07-task3-mmseqs-20260902-a/reports/TASK3_EVIDENCE_REPORT.md)
在同一 ubiquitin 输入、同一 wwPDB 快照和同一 identity 门槛下得到：

| 规则 | 合格 PDB entry |
|---|---:|
| query coverage >90% | 1,333 |
| target coverage >90% | 792 |
| query 与 target 均 >90% | 792 |

分母改变使候选池减少 541 个 entry；PDB chain 比输入更长但完整覆盖输入时，target coverage 会将
其排除，因此这不是字段命名差异，而会改变候选和最终结构。

### 暂行建议

```text
coverage = 输入 query 中被比对覆盖的残基数 / 输入 query 全长
通过条件：coverage > 0.90
target coverage：只保存为审计事实，不新增第二个通过门槛
```

### 可选替代规则

1. 只用 target coverage；需说明为何长 chain 对目标完整覆盖仍应排除。
2. query 与 target coverage 都必须 >0.90；需说明双门槛的科学目的。
3. 按结构类型或长度差使用不同分母；需给出完整决策表。
4. 自定义规则；须定义分母、严格/含等号边界、多片段 coverage 合并方式。

### 必须覆盖的边界案例

- query 被完整覆盖，但 target 含额外长区段；
- target 被完整覆盖，但 query 只覆盖一部分；
- query coverage 恰好 0.90 与刚高于 0.90；
- 多个不连续 HSP/片段有重叠时 coverage 如何去重；
- 序列 coverage=1，但坐标 coverage<1 的 partial 结构。

### 请专家填写

| 字段 | 答复 |
|---|---|
| 采用建议/替代项/自定义 | 待填写 |
| 完整规则与等号边界 | 待填写 |
| 多片段合并规则 | 待填写 |
| 确认人、角色、日期 | 待填写 |
| 规则版本/补充样本 | 待填写 |

## 3. S07-EQ-02：NMR 与可比分辨率方法的优先级

### 原文出处

- Agent A SOP S-07 L225–227 要求取得 method/resolution/deposited_date 并选最清晰结构，但未给
  NMR 与正 Å 方法的比较规则。
- 结构链 ToolSpec L26 明确 X-ray 与 cryo-EM 的正 Å 可比较并取最小值；NMR
  `resolution=null` 与其他不可比方法需“单列优先级+WARNING”，但没有给出优先级。

### 现有实测影响

任务 3 的 ubiquitin 严格候选池包含 537 个 X-ray、694 个 cryo-EM、99 个 solution NMR 和
3 个 solid-state NMR entry。X-ray/cryo-EM 内可选出 0.85 Å 的 6Q00；102 个 NMR 候选没有可比
Å 值。任务 6 还观察到 Integrative 方法，已作为 `OTHER` 不可比候选保留。直接忽略、混排或按
数据库顺序选择都会增加原文没有规定的规则。

### 暂行建议

1. 存在合格 X-ray/cryo-EM 时，只在这两类中取最小正 Å；NMR/OTHER 作为备选并记 WARNING。
2. 没有合格正 Å 候选时，再进入 NMR/其他不可比候选组。
3. 不可比组内无法唯一选择时停止自动选择，进入人工复核。

### 可选替代规则

1. NMR 永远优先或按特定质量指标优先；须指定指标、来源、缺值和排序方向。
2. 所有方法先分组，各组返回一个最优候选并始终人工选择。
3. 只允许 X-ray/cryo-EM 自动选择，NMR/OTHER 永不自动选。
4. 使用 deposited_date、ensemble RMSD 等作为 tie-break；须给字段可信性和完整顺序。

### 必须覆盖的边界案例

- 同时存在正 Å X-ray、cryo-EM 与多个 NMR；
- 只有一个或多个 NMR，且都没有传统 resolution；
- 只有 Integrative/OTHER 方法；
- 两个可比候选分辨率相同；
- resolution 为 null、0、负值或明显异常；
- 首选候选已撤回或元数据部分失败；deposited_date 是否参与决胜。

### 请专家填写

| 字段 | 答复 |
|---|---|
| 方法组完整优先级 | 待填写 |
| 仅 NMR/OTHER 时的处理 | 待填写 |
| 同分与 deposited_date 规则 | 待填写 |
| 确认人、角色、日期 | 待填写 |
| 规则版本/补充样本 | 待填写 |

## 4. S07-EQ-03：BLAST-derived accession 自动采用门槛

### 原文出处

- Agent A SOP S-07 L228 和结构链 ToolSpec L28 规定“无 accession 时 BLAST vs UniProt 取
  accession，再查 AlphaFold DB”，但没有给该 BLAST 回退的 identity/coverage/E-value 门槛。
- PDB 的 `identity>95% AND coverage>90%` 明确属于 C3 搜索，不能自动复制给 C6/UniProt。

### 现有实测影响

[任务 4 报告](../../../discovery/p0/s07/p0-s07-task4-uniprot-afdb-20260902-a/reports/TASK4_API_EVIDENCE_REPORT.md)
显示：133 aa 的 O15116 精确输入可完成 UniProt→AFDB v6；只改第 43 位一个残基后，BLAST 首名
仍是 O15116，identity=99.2%，但输入为 A、UniProt/AFDB 为 L。接受该 accession 会直接使用现成
AFDB 模型并进入 S-09；不接受则可能进入 S-08 新预测。

### 暂行建议

只有输入序列、UniProt 序列和具体 AFDB model/isoform 序列全长完全一致时自动采用。非精确候选
保留 alignment/R-58 事实并进入复核，不伪装成“无命中”，也不自动替代用户目标。

### 可选替代规则

1. 允许相似序列自动采用；须完整给出 identity、query/target coverage、E-value、长度差、
   substitution/indel 和物种条件及等号边界。
2. 相似候选只作人工建议，任何 BLAST-derived accession 都不得自动采用。
3. 相似候选仅用于 S-08 模板/提示而不作为 S-07 已有结构；须定义下游 source 和质量语义。

### 必须覆盖的边界案例

- 全长精确匹配；单点替换（现有 99.2% 样本）；
- N/C 端截短或标签、内部 insertion/deletion；
- 高 identity 但 query/target coverage 不同；
- 同物种相似序列与异物种精确序列冲突；
- UniProt 精确但 AFDB isoform/model 序列不一致；
- 命中 accession 合法但 AFDB 无模型。

### 请专家填写

| 字段 | 答复 |
|---|---|
| 自动采用条件 | 待填写 |
| 所有阈值与等号边界 | 待填写 |
| 非精确候选的下游路由 | 待填写 |
| 确认人、角色、日期 | 待填写 |
| 规则版本/补充样本 | 待填写 |

## 5. S07-EQ-04：多个 accession/model 的排序与并列

### 原文出处

Agent A SOP S-07 接收 `organism_name` 并要求 BLAST→UniProt→AFDB，但没有规定 sequence、物种、
canonical/isoform、reviewed 状态和模型质量之间的排序，也没有规定仍并列时转人工、S-08 或失败。

### 现有实测影响

- 76 aa ubiquitin 输入得到 3 个同分、100% 全长精确 accession，来自不同物种，三者都有 AFDB
  模型；global metric 为 95.62/95.62/95.56。
- Q86UQ4 基础 accession 返回 4 个 isoform 模型，长度 2292/2217/2323/317，均不等于 5058 aa
  输入。按基础 accession 或 API 首条选取都会得到错误目标。

### 暂行建议

1. 逐 accession、UniProt record 和每个 AFDB model/isoform 回验序列。
2. 只在序列合格后使用精确 `organism_name` 缩小候选。
3. 仍有多个合格项时返回明确歧义并停止自动选择；不按 API 顺序、accession 文本或未批准质量值
   决胜。

### 可选替代规则

1. 依次使用物种、reviewed、canonical、AFDB 质量值排序；须给完整优先级和并列规则。
2. 忽略物种，只选择全长精确序列中的最高质量模型；须说明质量字段及缺值。
3. 多个精确结果始终人工复核；不进行任何自动 tie-break。
4. 无法唯一时转 S-08；须说明为何已有精确公共模型仍重算，以及如何记录 source。

### 必须覆盖的边界案例

- 多个全长精确 accession，物种不同或 `organism_name` 缺失；
- 同物种 canonical 与 isoform 均精确；reviewed 与 unreviewed 冲突；
- 一个 accession 返回多个模型，只有一个序列精确；
- 多个精确模型质量相同或质量缺失；
- organism 名称同义词、菌株/亚种差异；
- 全部候选不精确或无 AFDB 模型。

### 请专家填写

| 字段 | 答复 |
|---|---|
| 完整排序键及顺序 | 待填写 |
| organism/canonical/reviewed/质量的作用 | 待填写 |
| 最终并列路由 | 待填写 |
| 确认人、角色、日期 | 待填写 |
| 规则版本/补充样本 | 待填写 |

## 6. S07-EQ-05：UniProt 搜索范围与分层停止条件

### 原文出处

Agent A SOP S-07 L228 只写“BLAST vs UniProt”；一期环境清单 L66 也只写无 accession 时 BLAST
UniProt。官方 API 提供 `uniprotkb_swissprot`、`uniprotkb_trembl`、`uniprotkb` 和 `afdb` 等
数据集，原文没有指定生产范围、顺序或层间停止条件。

### 现有实测影响

任务 4 的 discovery profile 使用 `uniprotkb_swissprot`，BLASTP 2.16.0+，当时库创建时间
2026-09-01、575,748 条；该 profile 已验证 9/9 API 场景，但没有比较 TrEMBL 或完整 UniProtKB。
扩大范围可能增加仅 TrEMBL 命中和候选歧义，也不保证命中项都有 AFDB 模型。因此现有实测只
证明 Swiss-Prot profile 的形态，不证明它是完整生产范围。

### 暂行建议

当前 P0 首个 profile 只使用 `uniprotkb_swissprot`，显式记录数据库名、创建/发布版本和查询参数；
专家确认前不声称覆盖完整 UniProtKB。

### 可选替代规则

1. 直接查询完整 UniProtKB；须说明 reviewed 状态是否参与选择。
2. 分层 Swiss-Prot→TrEMBL；须定义当前层何时停止、候选是否跨层合并、命中无 AFDB 模型时
   是否继续下一层。
3. 直接查询 AFDB 数据集；须说明与 UniProt 回读、序列/物种验证的关系。
4. 不允许 BLAST-derived accession 自动路由，只接受用户 accession 或转 S-08。

### 必须覆盖的边界案例

- Swiss-Prot 精确命中并有模型；精确命中但无模型；
- Swiss-Prot 无命中、TrEMBL 有精确命中；
- 两层均有精确但不同 accession/物种；
- 当前层有非精确命中，下一层可能有精确命中；
- 多库重复 accession、版本更新和候选去重；
- 全部查询正常但无合格模型，与服务故障分开。

### 请专家填写

| 字段 | 答复 |
|---|---|
| 数据集及查询顺序 | 待填写 |
| 每层停止/继续条件 | 待填写 |
| 跨层合并与去重 | 待填写 |
| 确认人、角色、日期 | 待填写 |
| 规则版本/补充样本 | 待填写 |

## 7. 批次 A 统一签收

| ID | 专家状态 | 规则版本 | 确认人/角色 | 日期 | 需要重算的用例 |
|---|---|---|---|---|---|
| S07-EQ-01 | `PENDING` | 待填写 | 待填写 | 待填写 | coverage 候选池/partial |
| S07-EQ-02 | `PENDING` | 待填写 | 待填写 | 待填写 | 混合方法/NMR/OTHER |
| S07-EQ-03 | `PENDING` | 待填写 | 待填写 | 待填写 | 精确/替换/indel |
| S07-EQ-04 | `PENDING` | 待填写 | 待填写 | 待填写 | 多 accession/isoform/歧义 |
| S07-EQ-05 | `PENDING` | 待填写 | 待填写 | 待填写 | 分层库/无模型/零命中 |

批次 A 全部确认后，仍需 M2 解除 BLAST 100 条触顶并验证完整候选，才能评审 S-07 G1；专家答复
本身不等于 OI-018 已关闭或生产适配器可以实现。
