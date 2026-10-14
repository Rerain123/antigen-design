# P0 S-07 任务 4 API 取证批次

本批次用官方在线 BLAST、UniProt REST 和 AlphaFold DB API 验证
`sequence → UniProt accession → AFDB model` 回退链。详细结论见
[TASK4_API_EVIDENCE_REPORT.md](reports/TASK4_API_EVIDENCE_REPORT.md)。
任务 3/4 合计 5 项待专家确认问题统一见
[S-07 专家确认问题总表](../../../../docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md)。

边界：

- 执行模式为 `api_discovery`，不用于科研结论。
- 生产部署仍为 `NOT_DEPLOYED`。
- 不需要、也没有下载 37 GB AlphaFold DB 坐标包。
- 目标服务器上的本地数据库或缓存由对方部署人员后续实施与验收。
- 早先的工作站本地 Swiss-Prot 实验不纳入本批 API 验收 manifest。
- 已停止的 Swiss-Prot 2025_03 下载保留为 `.partial` 文件，不会被任何脚本当作完整数据库；
  当前任务不会恢复该下载。

重建机器报告：

```powershell
.\.venv\Scripts\python.exe .\scripts\build_s07_task4_api_evidence.py
```

主要产物：

- `reports/task4_api_evidence.json`：完整的机器可读事实、检查和待确认规则。
- `reports/api_case_matrix.tsv`：验收场景索引。
- `reports/artifact_manifest.json`：纳入 API 验收的原始证据哈希。
- `evidence/blast-api/ebi/`：在线 BLAST 任务状态和原始结果。
- `evidence/uniprot-api/`：UniProt JSON/FASTA 及响应头。
- `evidence/afdb/`：AFDB 元数据、响应头与 O15116 小型模型/置信度/PAE 文件。
