# P0 S-07 Discovery：p0-s07-discovery-20260901-a

状态：`EVIDENCE_CAPTURE_COMPLETE / CONTRACT_REVIEW_REQUIRED`

本批次用于观察 RCSB PDB Search/Data、AlphaFold DB 和 NCBI BLAST+ 的真实输入输出，
再据此评审 `structure.fetch` 契约。它不是生产运行、不是金标准，也不接入 Dify。

## 严格边界

1. `protein_sequence` 是序列事实源；accession 只能帮助检索，返回结果必须回验序列。
2. S-07 三类命中语义仅为 `PROVISIONAL_DISCOVERY_POLICY`。
3. 不在本批次设定 identity、coverage、缺失残基或链选择的生产阈值。
4. RCSB sequence service 的结果标记为 MMseqs2 证据，不冒充 BLAST。
5. 无命中与 HTTP/解析/下载故障分别记录。
6. 原始 evidence 只写一次；重复实验使用新的 exchange 或 campaign。

## 第一轮顺序

1. 以 PDB 1UBQ entity 1 的 76 aa ubiquitin 序列验证 RCSB exact-match 路径。
2. 获取搜索候选对应的 Data API 元数据、链元数据和原始 mmCIF。
3. 扩展到 target-derived、homolog-only、AlphaFold DB-only、no-hit 与故障样本。
4. 冻结结构序列 discovery 数据库后运行 BLAST+，同时保留 archive 与 tabular 输出。
5. 生成 `candidate_structure_manifest`、`sequence_mapping_report` 和能力缺口表。

## 完成结果

- 已捕获 RCSB Search/Data/mmCIF、AlphaFold DB metadata/mmCIF/confidence/PAE、
  NCBI BLAST+ archive/tabular/JSON 证据。
- 已固定 NCBI BLAST+ 2.17.0、2026-08-22 wwPDB protein FASTA 与 taxdb，并完成
  BLAST 数据库全量校验。
- 已形成 5 个代表候选和 5 份逐候选序列—坐标映射；没有候选被选为生产结构。
- P0-DISC-005 只证明“无 exact-target 证据且同源可用性未决”，未被误标为科学上的
  `NO_USABLE_STRUCTURE`。

退出报告见 [P0-M1 总结](reports/P0_M1_SUMMARY.md)、
[候选结构清单](reports/candidate_structure_manifest.json)、
[序列映射报告](reports/sequence_mapping_report.json)和
[能力缺口表](reports/capability_gap_table.md)。

报告可由以下命令从冻结证据重新生成并校验：

```powershell
.\.venv\Scripts\python.exe .\scripts\build_p0_s07_discovery_reports.py
```

下一步是 S-07 契约评审；评审通过前不得进入 P0-M2 生产适配器编码。
