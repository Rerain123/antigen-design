# S-07 任务 5：离线契约验证批次

> 批次：`p0-s07-task5-contract-20260903-b`；日期：2026-09-03。  
> 结论：`PASS_OFFLINE_CONTRACT_ONLY`；新增网络调用：0。  
> 科学验收：`NOT_RUN`；生产部署：`NOT_DEPLOYED`。

本批次复用任务 3/4 的冻结文件并组合受控场景，验证 S-07 结果、错误、文件与恢复契约。
19 个路由场景、20 个非法状态拒绝检查和 7 个文件/恢复检查全部通过。任务 5 文档收尾继续
使用这份既有证据，并只读复核；没有将旧批次描述为新在线检索。

- [任务 5 契约说明](../../../../docs/archive/p0/S07_TASK5_RESULT_CONTRACT.md)：字段、路由、保存、追溯与恢复边界。
- [验证报告](reports/TASK5_CONTRACT_VALIDATION_REPORT.md)：逐场景结果、限制和收尾检查。
- [机器证据](reports/task5_contract_evidence.json)：46 项原始检查。
- [来源文件索引](reports/source_evidence_index.json)：136 个导入文件与旧清单的对应关系。
- [文件索引](artifact_index.json)：252 个内容对象的大小、哈希与来源。
- [冻结 Schema](schema/S07_TASK5_RESULT_CONTRACT.schema.json)：对应 `s07.task5.v1-review`。

`objects/` 按内容哈希保存文件；`results/` 保存每个运行的各次尝试；`bindings/` 固定输入与
profile；`controlled/` 保存明确标记的受控派生文件和故障探针。`controlled/storage-probes/`
包含故意损坏的文件，不应当作真实来源损坏，也不属于正常 artifact 索引。

从项目根目录只读复核：

```powershell
.\.venv\Scripts\python.exe .\scripts\build_s07_task5_contract_evidence.py `
  --campaign discovery/p0/s07/p0-s07-task5-contract-20260903-b --verify
```

该命令不会重建批次或访问 API。需要重新构建时必须使用新的、尚无文件的批次目录；已保存的
结果、Schema 和来源证据不可覆盖。原有 a 批次保留，本文只以 b 批次作为任务 5 的交付证据。
