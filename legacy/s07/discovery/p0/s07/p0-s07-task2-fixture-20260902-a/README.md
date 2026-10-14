# S-07 任务 2 隔离关系验证：p0-s07-task2-fixture-20260902-a

状态：`PASS_FIXTURE_ONLY / NOT_DEPLOYED`

本批次只验证一条小型离线关系链能否被机器复核：UniProt FASTA 生成 BLAST 数据库，
序列检索返回 UniProt accession，再由该 accession 对应到已保存的 AlphaFold DB v6
元数据、模型和置信度文件。样本库只有 1 条序列，不代表生产数据覆盖，也不决定
BLAST 的科学阈值或多命中选择规则。

## 已执行内容

1. 从已核验的 P0-DISC-004 原始证据复制 `O15116.fasta`，原件保持不变。
2. 使用 NCBI BLAST+ 2.17.0+ `makeblastdb -dbtype prot -parse_seqids` 建立 BLAST DB v5。
3. 使用完整模式运行 `blastdbcheck`，并显式加载已冻结的 NCBI taxdb。
4. 使用同一 FASTA 做工程连通性查询，得到 133/133、100% identity、100% query coverage。
5. 使用 `blastdbcmd` 重新读取 accession，并核对输入序列、数据库序列和 AlphaFold DB
   元数据序列三者完全一致。

结构、置信度和 PAE 文件不在本批次重复复制；`reports/fixture_manifest.json` 保存它们的
原始路径、大小和 SHA-256。这样可以验证关系，又不会产生第二份大文件事实源。

## Windows 运行说明

当前工作区路径含非 ASCII 字符，Windows 版 BLAST 的 LMDB 数据库不能直接稳定读取该路径。
本批次沿用已有 discovery 的做法，运行期间临时用 `subst` 映射为 `P:`，结束后立即解除。
这是本地开发约束；目标 Linux 服务器仍须在自己的文件系统上重新验收。

## 严格边界

- `scientific_acceptance=NOT_RUN`。
- `production_deployment_status=NOT_DEPLOYED`。
- 本批次没有安装或验证 MMseqs2，没有验证完整 PDB、UniProtKB 或 AlphaFold DB 发布。
- BLAST 参数只用于确认文件和编号可联通，不能作为任务 4 的生产匹配参数。
- 生产数据覆盖、BLAST 多命中选择及 accession 缺少模型时的处理仍须在任务 2、4 中收敛。

机器可读证据见 [fixture manifest](reports/fixture_manifest.json)。
