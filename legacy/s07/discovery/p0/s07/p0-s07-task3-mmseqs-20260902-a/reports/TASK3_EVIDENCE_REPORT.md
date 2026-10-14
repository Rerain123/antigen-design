# S-07 任务 3 本地检索与结构读取证据

> 状态：`PASS_WITH_TARGETED_RULE_GAPS / NOT_DEPLOYED`  
> 批次：`p0-s07-task3-mmseqs-20260902-a`  
> 数据：wwPDB 2026-08-29 序列与 entry 索引；MMseqs2 18-8cc5c。  
> 边界：这是隔离 discovery，不是生产结构选择，也没有接入 MCP/Dify。

## 1. 实际完成的链路

```text
4 条冻结输入
  → 本地 MMseqs2 搜索 1,093,472 条 PDB protein chain 序列
  → 严格后筛 fident > 0.95 AND proposed qcov > 0.90
  → chain 聚合为 PDB entry
  → 连接同快照 entries.idx 的方法、分辨率和 accession date
  → 对可比的 X-ray/cryo-EM 候选取最小正 Å 值
  → 下载本轮文件验证候选 mmCIF
  → 独立计算序列覆盖与实际坐标覆盖
```

宽松候选集后筛得到 2466 个 query-chain 候选。再以 MMseqs2
`--min-seq-id 0.95 -c 0.90 --cov-mode 2` 重跑，候选键与后筛结果完全一致。

## 2. 四个输入的结果

| 输入 | 严格 chain | PDB entry | 方法分布 | 可比最小分辨率 | 当前处理 |
|---|---:|---:|---|---|---|
| 1UBQ ubiquitin 序列 | 2442 | 1333 | X-ray 537；cryo-EM 694；solution NMR 99；solid-state NMR 3 | 6Q00，0.85 Å，chain A | mmCIF 验证通过；跨 NMR 方法优先级未定义，不能标生产入选 |
| P04637 TP53 序列 | 24 | 8 | cryo-EM 8 | 9R2Q，3.2 Å，chains K/L/M/N | 四条链同等匹配，按 R-58 禁止自动交接 |
| O15116 LSM1 序列 | 0 | 0 | 无 | 无 | 在该冻结快照中进入 AlphaFold DB fallback 测试路径 |
| WP_505187596.1 序列 | 0 | 0 | 无 | 无 | 在该冻结快照中进入 AlphaFold DB/accession fallback 测试路径 |

“无”只表示这次完整本地快照和记录参数没有候选，不表示其他版本或更宽阈值下绝对没有同源结构。

## 3. 结构文件读取结论

- 6Q00：X-ray，0.85 Å，A 链目标序列 76/76，实际坐标映射也是 76/76；文件 SHA-256
  `14b9d334cb8b7277bf452c38ac61f31618d338aa93b5feff3aba8f869b9a0d87`。
- 9R2Q：cryo-EM，3.2 Å，K/L/M/N 四条链都对目标序列达到 identity=1、query coverage=1；
  每条链实际只有 200/393 个目标位置有坐标，
  即 50.89%，映射区间为目标位置 92–291。因此它必须
  标注 `partial`，不能因为序列检索 coverage=100% 就声称坐标完整。

9R2Q 的四条匹配链属于同一目标实体，但空间位置不同。专家已有 R-58 多链规则规定“无法唯一
确定设计链→failure 级 WARNING + 禁止自动交接”，所以这里直接执行现有规则，不新增一个让用户
决定“随便选哪条链”的问题。

## 4. 边界和选择规则验证

受控夹具共 10 个，全部符合预期：

- identity=0.95 不通过；coverage=0.90 不通过；两者都严格大于阈值才通过。
- X-ray 2.0 Å 与 cryo-EM 3.5 Å 可比时选 2.0 Å。
- 相同分辨率不按返回顺序选第一条，保留为未决 tie。
- 0、负值和 null 不参与正 Å 最小值。
- NMR 与有分辨率的 X-ray/cryo-EM 不强行比较。
- 多条同等匹配链按 R-58 阻止自动交接。

夹具见 [strict-filter-and-selection-cases.json](../inputs/controlled/strict-filter-and-selection-cases.json)，
逐候选事实见 [strict_candidate_metadata.tsv](strict_candidate_metadata.tsv)，机器报告见
[task3_evidence.json](task3_evidence.json)。

## 5. 现在真正需要定点确认的两件事

### S07-T3-G01：coverage 的分母

S-07 原文只写 `coverage>90%`，没有像 C20 ToolSpec 那样明确写 query coverage。本次实测中，
ubiquitin 若使用 query coverage 保留 1333 个 entry；若使用 target
coverage，或要求两侧都超过 90%，只保留 792 个。候选集合会改变，
所以这不是字段命名问题。

**建议**：S-07 将 coverage 明确为输入/query 序列覆盖率，因为它直接回答“目标序列有多少被实验
结构序列覆盖”；target coverage 同时保留作审计事实，但不加入现有 Hard Filter。生产契约冻结前
需要专家确认这一句。

### S07-T3-G02：NMR 和有正分辨率结构怎样排优先级

ubiquitin 的严格候选实际同时出现 X-ray、cryo-EM、solution NMR 和 solid-state NMR。原文能在
X-ray/cryo-EM 内按最小正 Å 选择 6Q00，但 NMR 没有可比的 Å 数值；ToolSpec 只写“NMR 单列
优先级+WARNING”，没有给出优先级。

**建议**：按方法组保留候选；当存在合格 X-ray/cryo-EM 时，先取其中最小正 Å，NMR 作为备选并
警告；只有无可比候选时再进入 NMR 选择。若专家不同意，应返回各方法组最优项供明确选择，不能
使用数据库返回顺序。

## 6. 尚未完成的生产工作

- 当前只保存 6Q00、9R2Q 两个文件验证候选，没有部署完整本地 mmCIF archive。
- Windows MMseqs2 包只证明检索口径可执行；目标 Linux 二进制、索引、资源和离线健康检查仍待验收。
- 两项规则确认、完整结构文件发布和最终契约完成前，不实现生产适配器，不把任何候选写成生产选择。
