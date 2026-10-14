# S-07 需要专家确认的问题总表

> 当前问题总数：**5 项**  
> 状态：`DEFERRED_OUT_OF_PHASE1 / HISTORICAL_PROVISIONAL_DECISIONS`  
> 统计日期：2026-09-03  
> 覆盖范围：S-07 任务 3 的 2 项 + 任务 4 的 3 项  
> 历史用户决定：五项曾先采用本文建议作为暂行工程方案，原计划后续集中提交专家确认。

> 后续范围覆盖：节点 01 内网决定已将 S-07 和数据库检索移出一期，五项停止作为当前专家外发
> 任务并随 OI-018 延后；若未来恢复 S-07，再按届时数据源和范围重新确认。

M1-03 曾形成可直接外发的[批次 A 材料](P0_V06_M1_BATCH_A_S07.md)，补齐替代规则、边界案例和
逐题填写栏；本文仅作为五项问题的历史来源总表，状态为延后而非当前待外发。

这是 S-07 历史范围内唯一的专家确认问题清单。任务 1～4 已经完成资料复核和工具/API 取证；专家原文
已经写清楚的规则不再重复提问。原先的 P0-Q01～Q17 是阶段审阅索引，并不等于当前有 17 个问题
要专家作答。任务 5 的[内部契约与离线验证](S07_TASK5_RESULT_CONTRACT.md)也已完成，未新增
专家问题。任务 6 的[非生产独立验收](S07_TASK6_ACCEPTANCE_AND_HANDOFF.md)进一步验证了完整候选、
当时的 API、O15116 回退和交接形状；8ZZ4/9A1L 的 Integrative 方法属于 S07-EQ-02 已声明的
不可比方法范围，同样没有新增问题。到 2026-09-03 为止，实际证据仍只收敛出以下 **5 项**会改变结构选择的问题。

五项暂行方案可以用于继续整理契约和验收用例，但在专家书面确认前均不得标记为 `VERIFIED`、
`FROZEN` 或正式生产科学规则。若专家结论不同，应更新规则版本并重算相应预期结果。

## 1. 一页总览

| 编号 | 需要确认的问题 | 当前暂行方案 | 不采用暂行方案的主要风险 | 专家状态 |
|---|---|---|---|---|
| S07-EQ-01 | PDB 检索的 coverage 用哪一边作分母 | 用输入序列的 query coverage；target coverage 只记录 | 候选池会随分母变化，同一输入可能得到不同结构 | `PENDING` |
| S07-EQ-02 | NMR 与 X-ray/cryo-EM 怎样排优先级 | 有合格 X-ray/cryo-EM 时取其中最小正 Å；无可比候选时才回退 NMR | NMR 没有可比 Å 数值，直接混排或忽略都会引入未写明的规则 | `PENDING` |
| S07-EQ-03 | BLAST 找到的相似 UniProt 编号何时能用于 AFDB | 只有输入、UniProt 和 AFDB 模型全长序列完全一致时自动使用 | 相似但不相同的模型可能替代用户目标序列，改变 S-08/S-09 路由 | `PENDING` |
| S07-EQ-04 | 多个合格 accession/model 怎样选择 | 先验证序列，再用精确 organism_name 缩小；仍有多个则返回歧义 | 按 API 顺序或编号文本选取会使结果不稳定且缺少科学依据 | `PENDING` |
| S07-EQ-05 | BLAST 查 Swiss-Prot 还是完整 UniProtKB | 当前 profile 使用 Swiss-Prot，并显式记录数据库及版本 | 搜索范围不同会改变命中、审阅状态和 AFDB 模型覆盖 | `PENDING` |

## 2. S07-EQ-01：coverage 到底覆盖哪一边

### 问题

S-07 原文只写 PDB 候选需满足 `coverage>90%`，没有说明分母。检索工具同时提供：

- query coverage：输入目标序列中有多少残基被命中覆盖；
- target coverage：PDB chain 序列中有多少残基被输入覆盖。

### 实际影响

同一条 ubiquitin 输入、同一个 wwPDB 快照和同一个 identity 门槛下：

| 口径 | 保留的 PDB entry 数 |
|---|---:|
| query coverage >90% | 1,333 |
| target coverage >90% | 792 |
| query 和 target 均 >90% | 792 |

若 PDB chain 比输入更长，但已完整覆盖输入，target coverage 会把它排除。不同分母会产生不同
候选池，进而可能选出不同结构。

### 当前暂行方案

```text
coverage = 输入序列中被比对覆盖的残基数 / 输入序列全长
通过条件：coverage > 0.90
```

target coverage 作为审计事实保留，不增加“两边都必须 >90%”的新门槛。

### 请专家确认

S-07 的 `coverage>90%` 是否应定义为 query coverage，并且不额外要求 target coverage>90%？

## 3. S07-EQ-02：NMR 与 X-ray/cryo-EM 的优先级

### 问题

原文规定 X-ray 与 cryo-EM 的正 Å 分辨率可比较并取最小值，但 NMR 的
`resolution=null`，只写了需要“单列优先级+WARNING”，没有给出排序规则。

### 实际影响

任务 3 的严格候选池实际包含 537 个 X-ray、694 个 cryo-EM、99 个 solution NMR 和 3 个
solid-state NMR entry。X-ray/cryo-EM 可以按 Å 排序，102 个 NMR 候选无法参加该排序。直接忽略
NMR 或把它们混在一起，都等于工程自行增加规则。

### 当前暂行方案

1. 有合格 X-ray/cryo-EM 时，在两类可比候选中选择最小正 Å；NMR 作为备选并记录 WARNING。
2. 没有合格 X-ray/cryo-EM 时，再进入 NMR 候选选择。
3. 多个 NMR 无法唯一选择时停止自动选择，不按数据库顺序、PDB ID 或日期自行决胜。

### 请专家确认

当严格候选同时包含 NMR 与具有正 Å 分辨率的 X-ray/cryo-EM 时，是否按上述顺序处理？若只有
多个 NMR，正式的选择或人工复核规则是什么？

## 4. S07-EQ-03：BLAST 相似 accession 的使用门槛

### 问题

S-07 写明缺少 UniProt 编号时，用 BLAST 查询 UniProt，再去 AlphaFold DB 取模型，但没有规定
BLAST 命中的 identity、coverage 或 E-value 门槛。PDB 检索的 `identity>95% 且 coverage>90%`
明确属于 C3，不能自行复制给 C6。

### 实际影响

任务 4 中，一条只改动 1 个残基的输入仍将 O15116 排在第一，identity 为 99.2%，但输入第 43 位
与 UniProt/AFDB 模型不同。接受该编号会使用现成 AFDB 模型并进入 S-09；不接受则可能进入 S-08
重新预测。这个决定会直接改变结构来源。

### 当前暂行方案

只有“输入序列、UniProt 序列和 AFDB 模型序列全长完全一致”时才自动选用。非精确候选保留完整
比对和 R-58 映射事实，不自动选择，也不伪装成无命中。

### 请专家确认

请给出 BLAST-derived accession 的正式合格条件，包括 identity、query coverage、target coverage、
E-value、长度差异、替换/插入/缺失、物种条件，以及各边界是否包含等号。

## 5. S07-EQ-04：多个 accession 或模型怎样选择

### 问题

同一条序列可能对应多个 UniProt accession，一个基础 accession 也可能返回多个 isoform 模型。
S-07 接收 `organism_name`，但没有规定序列关系、物种、reviewed 状态、isoform 或模型质量之间的
排序顺序。

### 实际影响

任务 4 的 76 aa ubiquitin 样本得到 3 个同分、100% 全长精确 accession，分别来自不同物种，
三者均有 AFDB 模型。Q86UQ4 基础编号又返回 4 个与 5058 aa 输入均不相同的 isoform 模型。按
API 返回顺序选择会使结果依赖服务排序，而不是已批准的科学规则。

### 当前暂行方案

1. 逐条验证输入、UniProt 记录和每个 AFDB 模型的序列关系。
2. 只在序列合格后使用精确 `organism_name` 缩小范围。
3. 仍有多个合格结果时返回明确歧义并停止自动选择；不按 API 顺序、accession 文本或未经批准的
   AFDB 质量值决胜。

### 请专家确认

请给出 accession/model 的完整排序和并列处理，说明物种匹配、canonical/isoform、reviewed 状态
及 AFDB 质量值是否参与选择；无法唯一选择时，应停止、人工复核，还是进入 S-08？

## 6. S07-EQ-05：UniProt 搜索范围

### 问题

官方 API 同时提供 `uniprotkb_swissprot`、`uniprotkb_trembl`、`uniprotkb` 和 `afdb` 数据集，
专家原文只写“UniProt”，没有指定搜索范围。

### 实际影响

只查 Swiss-Prot 范围清楚且记录经过审阅，但会漏掉仅在 TrEMBL 中的记录。查完整 UniProtKB 会
增加候选和一对多裁决压力，也不能保证每个命中都有 AFDB 模型。不同范围会改变最终是否能找到
公共预测结构。

### 当前暂行方案

当前 P0 profile 使用 `uniprotkb_swissprot`，数据库名和发布版本必须写入执行档案。专家确认前，
只声明覆盖该 profile，不声称已经覆盖完整 UniProtKB。

### 请专家确认

正式 profile 应使用 Swiss-Prot、完整 UniProtKB，还是分层查询？若分层，请同时规定查询顺序、
停止条件、候选合并方式，以及当前层命中没有 AFDB 模型时是否继续下一层。

## 7. 已明确、无需重复确认的内容

- PDB 搜索门槛严格为 `identity>95%` 且 `coverage>90%`；等于边界不通过。
- X-ray/cryo-EM 的正 Å 分辨率取最小值。
- 序列检索 coverage 与实际坐标 coverage 分开；坐标缺失的结构保留 `partial` 和 WARNING。
- 多链无法唯一确定时按 R-58 禁止自动交接。
- PDB 无可用结构后查 AlphaFold DB；缺 UniProt accession 时先 BLAST UniProt。
- 正常零命中、合法 accession 无 AFDB 模型、非法标识和服务故障必须使用不同状态。
- accession、UniProt 序列、AFDB model/isoform 与模型内序列必须逐层回验。
- 当前 P0 按文档使用 API；最终本地数据库由对方部署团队在目标服务器部署，不要求用户执行。

## 8. 专家统一反馈表

专家可直接在“专家结论”一栏填写；若不同意暂行方案，请写明替代规则和边界案例。

| 编号 | 当前状态 | 专家结论 | 确认人 | 确认日期 | 规则版本/边界案例 |
|---|---|---|---|---|---|
| S07-EQ-01 coverage 分母 | `PENDING` | 待填写 | 待填写 | 待填写 | 待填写 |
| S07-EQ-02 NMR 优先级 | `PENDING` | 待填写 | 待填写 | 待填写 | 待填写 |
| S07-EQ-03 BLAST accession 门槛 | `PENDING` | 待填写 | 待填写 | 待填写 | 待填写 |
| S07-EQ-04 多 accession/model 选择 | `PENDING` | 待填写 | 待填写 | 待填写 | 待填写 |
| S07-EQ-05 UniProt 搜索范围 | `PENDING` | 待填写 | 待填写 | 待填写 | 待填写 |

## 9. 原文和实测出处

- 原文：[Agent A SOP] S-07 L216–234、R-58 L391–393。
- 原文：[结构链规格] §2a、§5、§6。
- 原文：[一期环境清单] L57–67、L96–104。
- 任务 3：[PDB 检索与结构读取证据报告] §2–§4。
- 任务 4：[UniProt/AFDB API 回退证据报告] §3–§5。

[Agent A SOP]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md
[结构链规格]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md
[一期环境清单]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期实施环境清单_v10.5.md
[PDB 检索与结构读取证据报告]: ../../../../../discovery/p0/s07/p0-s07-task3-mmseqs-20260902-a/reports/TASK3_EVIDENCE_REPORT.md
[UniProt/AFDB API 回退证据报告]: ../../../../../discovery/p0/s07/p0-s07-task4-uniprot-afdb-20260902-a/reports/TASK4_API_EVIDENCE_REPORT.md
