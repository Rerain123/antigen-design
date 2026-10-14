# P0-M1：S-07 真实输出发现实验总结

状态：`EVIDENCE_CAPTURE_COMPLETE / CONTRACT_REVIEW_REQUIRED`  
Campaign：`p0-s07-discovery-20260901-a`  
部署状态：`NOT_DEPLOYED`

## 完成范围

- 冻结 5 个公开 discovery case，并保留输入序列、来源、日期与哈希。
- 捕获 RCSB Search/Data/mmCIF、AlphaFold DB metadata/mmCIF/confidence/PAE 的原始交换。
- 固定 NCBI BLAST+ 2.17.0 与 2026-08-22 wwPDB protein FASTA，构建并全量校验 BLAST DB。
- 对 4 个输入保存 BLAST archive、tabular 与 JSON 输出。
- 形成 5 个代表候选的 manifest 与逐候选序列—坐标映射。
- 保留成功、HTTP 204、HTTP 400、连接/TLS 故障与 CLI 依赖故障等不同输出形态。

## 关键发现

1. “序列完全一致”与“目标坐标完整”是两个字段：6XRE 为 exact entity，但 chain M 坐标覆盖仅 314/393。
2. 目标片段必须显式映射：5XZC 对齐目标 92-356，实际有坐标的目标残基为 232/393。
3. 同源命中必须与目标命中分离：6PPV 对 O15116 为 62.5% 局部 identity，坐标映射 69/133。
4. AlphaFold DB 的 O15116 v6 模型与输入 133 aa 精确一致，但 API 不能直接接受 RefSeq accession。
5. P0-DISC-005 只能报告“无 exact-target 证据且同源可用性未决”，不能在缺少阈值时宣称科学无结构。
6. HTTP 204 是成功空结果；HTTP 400/HTTP 0/CLI 非零退出应进入不同 outcome/error 分支。

## 退出产物

- `candidate_structure_manifest.json`
- `sequence_mapping_report.json`
- `capability_gap_table.md`
- `blast_dependency_and_results_manifest.json`
- `evidence_inventory.json`

## 停止线与下一步

P0-M1 的原始取证目标已经完成，但 S-07 契约尚未批准。下一步是 **S-07 契约评审**，不是直接开始
P0-M2 编码。只有命中语义、科学阈值/路由、chain/assembly 选择、AFDB accession 映射以及
outcome/error 枚举得到相应负责人确认后，才能实现生产检索适配器。

本报告及全部候选均为 discovery evidence；未接入 MCP/Dify，不用于科研结论或生产候选选择。
