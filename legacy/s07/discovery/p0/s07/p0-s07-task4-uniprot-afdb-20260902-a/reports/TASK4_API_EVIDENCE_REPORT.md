# S-07 任务 4：UniProt accession 与 AlphaFold DB API 回退取证

> 批次：`p0-s07-task4-uniprot-afdb-20260902-a`  
> 日期：2026-09-03  
> 状态：`EVIDENCE_COMPLETE / PROVISIONAL_RULES_ADOPTED / EXPERT_CONFIRMATION_PENDING`  
> 边界：`api_discovery / NOT_DEPLOYED / scientific_acceptance=NOT_RUN`

> 2026-09-03 用户决定：本报告第 5 节的三项建议均先作为暂行工程方案采用，并与任务 3 的
> 两项问题合并到 [S-07 五项专家确认问题总表]。专家书面确认前不得标记为正式科学规则。

## 1. 本任务完成了什么

本轮按 S-07 原文验证了以下回退链：

```text
无可用实验结构
  → 有 UniProt accession：查 AlphaFold DB API
  → 无 UniProt accession：在线 BLAST 查 UniProt accession
       → UniProt REST 回读条目和序列
       → AlphaFold DB API 取模型元数据和小型文件
  → 全部正常查询但无模型：返回 null，转 S-08
```

机器可读结果中 9/9 项证据检查通过；覆盖了已有合法编号、BLAST 找到
编号、BLAST 正常无命中、合法编号无模型、不支持的编号、编号与输入序列不同、
多个精确 accession 以及基础 accession 返回多个非匹配 isoform 模型。

依据：[Agent A SOP] S-07 L216–234；[结构链规格] §2a、§5、§6；[一期实施环境清单]
L57–67、L96–104；[S-07 任务安排] 任务 4。

## 2. 当前实施边界

2026-09-03 用户明确：当前 P0 先按文档走 API 查询；最终本地数据库如需启用，
由对方部署人员在目标服务器执行。因此本轮边界为：

| 范围 | 本轮处理 |
|---|---|
| RCSB/UniProt/AlphaFold DB 数据取得 | 官方 API，保存原始响应、响应头和小型文件 |
| 缺 accession 的 BLAST 回退 | 用 EMBL-EBI Job Dispatcher NCBI BLAST REST API 完成业务链取证 |
| 目标服务器上的本地 BLAST/数据镜像 | 部署交接项；本轮不执行，不要求用户部署 |
| 全量 AFDB 坐标包 | 不下载；任务 4 不需要 |

结构链规格将 C6 BLAST 的最终部署形态写为“本地”；这与当前 API 取证不是
同一个交付阶段。当前官方 API 取证锁定输入、输出、异步状态和错误语义；
目标服务器如改用本地 BLAST，必须保持同一契约并由部署人员另行完成版本和数据验收。

## 3. API 实测档案

| 服务 | 实测档案 | 从原始响应取得的版本事实 |
|---|---|---|
| EMBL-EBI NCBI BLAST REST | `blastp` + `uniprotkb_swissprot` + BLOSUM62；`expect=10`；最多 100 条 | BLASTP 2.16.0+；库创建时间 2026-09-01；575,748 条 |
| UniProt REST | `GET /uniprotkb/{accession}.json/.fasta` | `X-UniProt-Release=2026_03`；release date 2026-09-02 |
| AlphaFold DB | `GET /api/prediction/{accession}` + 响应中的 CIF/confidence/PAE URL | O15116 返回 `AF-O15116-F1`，v6 |

BLAST 中的 BLOSUM62、`expect=10`和返回上限只是为了完整观察原始输出的 discovery
档案，不是项目已确认的科学接受阈值。

## 4. 验收场景结果

| 用例 | 实际结果 | 结论 |
|---|---|---|
| 已有合法 accession | O15116 的输入、UniProt、AFDB 元数据及 CIF 序列均为 133 aa 且完全一致 | 可返回 `source=alphafolddb`，转 S-09 |
| BLAST 找到 accession | O15116 在线 BLAST 第 1 名为 O15116，identity=100%，query/target coverage=100% | BLAST→UniProt→AFDB 整段通过 |
| 无 accession | 80 aa 受控样本任务正常 `FINISHED`，返回 0 条 | 正常空结果；不写成工具故障 |
| 合法 accession 无模型 | C0HLM8 与 P80438 的 UniProt REST 均为 HTTP 200，AFDB 均为 HTTP 404 | 正常无模型；转 S-08 |
| 不支持的编号 | RefSeq `NP_055277.1` 被 AFDB 以 HTTP 400 拒绝并返回明确错误 | 与 HTTP 404 无模型分开 |
| 编号与序列不符 | 单点改动样本仍以 O15116 排第 1，identity=99.2%；回读后检出第 43 位 A/L 不同 | 必须保存不一致和映射事实；不写成相同序列 |
| 一对多 accession | 76 aa ubiquitin 有 3 个同分、100% 全长精确 accession，三者均有 AFDB 模型 | 不得按 API 顺序默认选第 1 条 |
| accession 返回多模型 | Q86UQ4 基础编号返回 4 个 isoform 模型，长度为 2292/2217/2323/317，均不等于 5058 aa 输入 | 必须逐模型回验；本用例不选中任何模型 |

O15116 的 CIF、逐残基 confidence 和 PAE 文件均已解析：序列、confidence 与 PAE
维度均为 133，且 PAE 为 133×133。AFDB 元数据的 global metric 为 89.69，由逐残基
confidence 直接计算的平均值为 89.706；两个原始量同时保留，不用其中一个覆盖另一个。

详细数值见 [task4_api_evidence.json](task4_api_evidence.json)，用例索引见
[api_case_matrix.tsv](api_case_matrix.tsv)，原始文件校验见 [artifact_manifest.json](artifact_manifest.json)。

## 5. 现有原文还不能唯一决定的三点

### S07-T4-Q01：BLAST 找到的相似 accession 什么时候可以用

S-07 只规定了“BLAST vs UniProt 取 accession”，没有写这条回退的 identity/coverage
门槛。`identity>95% AND coverage>90%` 在原文中明确挂在 C3/PDB 序列搜索下，
不能自动认定它也约束 C6。本轮的单点变化样本会产生 99.2% 的同物种首命中；
是使用它的 AFDB 模型，还是直接转 S-08，会改变实际结构来源。

**建议的暂行边界**：只有输入与 UniProt/AFDB 全长序列精确一致时才自动选用；
非精确候选保留比对和 R-58 映射事实，待专家确认门槛前不自动选择。

### S07-T4-Q02：多个合格 accession/模型怎样选

ubiquitin 样本实际返回 3 个同分、全长精确序列；它们分别来自不同物种，
AFDB global metric 为 95.62/95.62/95.56。S-07 虽然接收 `organism_name`，却没有给出
“序列关系、物种、编号审阅状态、模型质量”的排序规则。

**建议的暂行边界**：先判断序列是否合格，再用精确 `organism_name` 缩小范围；
仍有多个时返回歧义，不用 API 顺序、accession 文本或未经批准的质量值自行决胜。

### S07-T4-Q03：BLAST 查 Swiss-Prot 还是整个 UniProtKB

官方 API 同时提供 `uniprotkb_swissprot`、`uniprotkb_trembl`、`uniprotkb` 和 `afdb`
数据集。原文只写“UniProt”，没有指定范围。搜索范围会改变命中量、审阅状态
及后续能否找到 AFDB 模型。

**建议的暂行边界**：P0 取证档暂用已审阅的 Swiss-Prot；数据库名必须是显式、
可追溯的 execution-profile 字段。专家未确认前，不声称已覆盖全部 UniProtKB。

这三点不影响当前完成 API 连通、数据回验和错误分类；用户已批准按上述建议暂行。它们会影响
最终选中哪个模型，所以在 P0 v0.6 科学契约冻结前仍需专家定点确认。全部 5 项集中见
[S-07 五项专家确认问题总表]。

## 6. 任务 4 验收结论

- 任务 4 所要求的 API 业务链和五类基本场景已完成真实取证。
- 正常无命中、有 UniProt 但无 AFDB 模型、以及非法编号已得到不同机器状态。
- 序列、accession、AFDB model/isoform 和原始质量数据已可逐层回验。
- 任务 4 可进入契约整理，状态为“取证完成，3 项科学选择规则待确认”。
- 本结论不表示已部署生产适配器、已完成目标服务器部署或已通过科研有效性验收。

[Agent A SOP]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md
[结构链规格]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md
[一期实施环境清单]: ../../../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期实施环境清单_v10.5.md
[S-07 任务安排]: ../../../../../docs/project/stages/p0/S07_IMPLEMENTATION_TASKS.md
[S-07 五项专家确认问题总表]: ../../../../../docs/project/stages/p0/S07_EXPERT_CONFIRMATIONS.md
