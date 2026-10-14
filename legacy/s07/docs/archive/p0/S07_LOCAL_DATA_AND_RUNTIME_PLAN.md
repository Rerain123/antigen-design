# S-07 API 运行与目标服务器本地数据部署交接

> 状态：`HISTORICAL_EVIDENCE / DEFERRED_OUT_OF_PHASE1`；版本：v0.3；日期：2026-09-03。  
> 范围：保存 S-07 旧 API/本地化方案；节点 01 内网决定后不再进入一期部署或交接。  
> 边界：当前 P0 不要求在用户工作站下载或部署完整数据库；目标 Linux 的本地化部署由对方部署
> 团队执行。该旧安排已被“甲方提供输入、删除数据库搜索”覆盖；所有真实生产能力仍为 `NOT_DEPLOYED`。

本历史任务曾按专家已经明确的 `PDB → AlphaFold DB；缺 UniProt 编号时 BLAST → UniProt →
AlphaFold DB` 路径工作。当时的 P0 依据一期环境清单采用官方 API 查询，并保存请求、响应、版本和
小型结构产物；本地数据库方案只作为对方目标服务器的后续部署交接清单。没有在本任务中增加
identity、coverage、BLAST 命中选择或结构质量阈值。

2026-09-03 的范围澄清如下：

- **旧建设路径**：RCSB Search/Data API、UniProt/BLAST API、AlphaFold DB API。
- **最终本地化路径**：如果交付环境要求本地库，由对方部署团队在目标服务器执行并验收。
- **用户工作站**：不承担全量 UniProt、AlphaFold DB 或 PDB 数据下载，也不作为生产服务器。
- **关系**：API 与本地 profile 必须保持同一业务结果、错误分类和追溯字段；本地部署不是当前
  API 取证和任务 5 契约整理的前置条件；任务 5 的[内部契约与离线验证](S07_TASK5_RESULT_CONTRACT.md)已完成。

## 1. 历史任务完成到哪里

| 项目 | 当前事实 | 本任务结论 |
|---|---|---|
| API 查询链 | 任务 4 已实跑 BLAST→UniProt REST→AlphaFold DB API，9/9 项证据检查通过 | 当时 P0 按 API 继续；见任务 4 报告 |
| 隔离关系样本 | 1 条 UniProtKB/Swiss-Prot 序列已建立 BLAST DB v5；输入、数据库回读和 AlphaFold DB v6 元数据序列一致 | `PASS_FIXTURE_ONLY` |
| NCBI BLAST+ | 本地已固定 2.17.0+，`makeblastdb`、`blastdbcheck`、`blastp`、`blastdbcmd` 均已实跑 | 可作为任务 4 的工程工具候选；生产科学参数未定 |
| wwPDB 序列数据 | 2026-08-29 序列与 entry 索引已冻结，并建立 MMseqs2 18-8cc5c DB/index；2026-08-22 BLAST 快照继续保留 | 本地 discovery 已通过；目标服务器发布仍未验收 |
| PDB 元数据和结构 | 2026-08-29 `entries.idx` 已完整连接严格候选；只保存本轮 6Q00、9R2Q mmCIF，没有完整坐标 archive | 候选轻量元数据已取证，生产坐标发布未就绪 |
| MMseqs2 | 官方 Windows 包 18-8cc5c 已校验并实跑；完整索引和 4 输入搜索成功 | 只证明 discovery 口径；目标 Linux 二进制和索引仍须重验 |
| UniProt 数据 | API 取证保存 7 个 accession 的 JSON/FASTA；本地仅有隔离样本 | API 证据已完成；不等于本地完整发布 |
| AlphaFold DB | API 取证覆盖模型存在、404 无模型、400 非法标识和多 isoform；本地仅有隔离样本 | API 证据已完成；不等于本地完整发布 |
| 目标服务器 | 本轮没有服务器部署会话；CPU、内存、磁盘、文件系统和运行账户尚未实测 | 由对方部署团队在交付阶段盘点和验收 |

隔离证据位于
[p0-s07-task2-fixture-20260902-a](../../../discovery/p0/s07/p0-s07-task2-fixture-20260902-a/README.md)，
机器可读结果见其 [fixture manifest](../../../discovery/p0/s07/p0-s07-task2-fixture-20260902-a/reports/fixture_manifest.json)。
任务 4 API 证据见
[p0-s07-task4-uniprot-afdb-20260902-a](../../../discovery/p0/s07/p0-s07-task4-uniprot-afdb-20260902-a/reports/TASK4_API_EVIDENCE_REPORT.md)。

## 2. 数据之间必须怎样关联

```text
目标序列
  ├─ PDB 序列索引
  │    └─ PDB entry + polymer entity + chain
  │          ├─ 实验方法、分辨率、发布日期等轻量元数据
  │          └─ 选中候选的 mmCIF 坐标文件
  └─ 已有 UniProt accession，或 BLAST 产生的 accession 候选
       └─ UniProt accession + 序列版本
            └─ AlphaFold DB model id + model version
                 ├─ model mmCIF
                 ├─ residue confidence
                 └─ predicted aligned error
```

后端关系索引至少保存以下事实，不由 LLM 拼接：

| 关系 | 必存字段 | 校验 |
|---|---|---|
| PDB 序列记录 → 实体 | PDB ID、entity ID、链 ID、序列哈希、数据快照 | 索引记录能定位同一快照的实体元数据 |
| 实体 → 坐标 | 文件路径、文件哈希、格式、发布日期或修订标识 | 文件存在、哈希一致、能解析对应实体/链 |
| UniProt 序列 → accession | accession、reviewed 状态、序列版本、序列哈希、UniProt 发布 | BLAST subject 可回读；返回序列可与输入重新比对 |
| accession → AlphaFold DB | accession、model ID、model version、序列哈希、模型/置信度/PAE 路径 | accession、模型元数据和文件序列一致；缺文件显式报错 |

序列索引、元数据和结构文件必须写入同一个不可修改的发布 manifest。运行时不得把不同日期的
PDB 索引、UniProt FASTA 和 AlphaFold DB 模型临时拼成一个未声明版本。

## 3. 当前工程证据与本地化交接候选

### 3.1 可直接复用的工程资产

| 资产 | 当前版本或快照 | 大小/记录 | 完整性证据 | 限制 |
|---|---|---:|---|---|
| NCBI BLAST+ | 2.17.0+ | 官方归档 143,400,333 B | 官方 MD5 已核对；本地归档 SHA-256 `ccde8788641e8f4137536aaadedfeac2f3599dbbc6166e701b5d89d19fa79038` | 未冻结任务 4 的科学参数 |
| wwPDB 原始序列压缩包 | 2026-08-22 | 66,543,638 B | SHA-256 `e58353521f49336892fa583f0b0efb598e5b1cb482e5b6f33a9cb1f3e373c294` | 不是完整结构发布 |
| 蛋白序列 FASTA | 从上述快照过滤 | 1,090,949 条；318,599,298 residues | 386,955,714 B；SHA-256 `6da00091dd5e498ad0251dd49d09bf889ab8da649a681e398399bb75eb7ae5c6` | 旧 discovery 使用 BLAST，不是待建 MMseqs2 索引 |
| wwPDB BLAST DB | v5 | 12 个数据库文件 | P0-M1 已全量检查 | 仅作旧证据和对照输入 |
| NCBI taxdb | 2026-08-31 | 64,988,443 B | SHA-256 `1ec18441f502859e073ed955c42c7cc5a56ebda67be035fda9a467c5d0d58eb4` | 必须与引用 taxid 的数据库一起装载 |
| wwPDB 原始序列压缩包 | 2026-08-29 | 66,761,281 B | SHA-256 `3ce3bf140288f133e0fbf1185186ca50a24cd9bd58f9116b032347101760eeb0` | 当前任务 3 冻结快照 |
| wwPDB 蛋白序列 FASTA | 2026-08-29 过滤产物 | 1,093,472 条；319,328,548 residues | 387,841,581 B；SHA-256 `f4dc11e5ddcca509d536c501011759e177f15ec3f9dc145f14f1c5f167004201` | discovery 数据源，未部署服务器 |
| wwPDB entry 索引 | 2026-08-29 | 57,316,966 B | SHA-256 `9f9709b11302bc1414ea19b5be6b5e92104804c19fcbcec013010ce0a772fc86` | 有 entry 级方法/分辨率/日期；不能代替 entity/chain 与完整坐标库 |
| MMseqs2 Windows 包 | 18-8cc5c | 22,129,914 B | 官方 asset SHA-256 与本地值均为 `9752087ca4e25e93b830775832a75044dc94ae348d66d4681f9ff0355eecfcbf` | Windows beta/Cygwin，只用于 discovery |
| PDB MMseqs2 索引 | wwPDB 2026-08-29 + MMseqs2 18-8cc5c | 主序列库 321,515,492 B；`.idx` 3,483,500,544 B | 版本、文件哈希及检索输出见任务 3 artifact manifest | 目标 Linux 必须重建或验证兼容性 |
| O15116 UniProt FASTA | 单条隔离样本 | 133 aa | 原件和复制件 SHA-256 均为 `878637930baf89eb3716a0085d9b4b8a84b0705ee50a865fab6cd9133bb9e8e8` | 不代表 UniProt 覆盖 |
| AF-O15116-F1 | AlphaFold DB v6 | model 135,937 B；confidence 1,797 B；PAE 39,746 B | 三个文件 SHA-256 见 fixture manifest | 仅用于关系和解析验证 |

旧资产的来源、完整候选和 `NOT_DEPLOYED` 边界继续以
[P0-M1 总结](../../../discovery/p0/s07/p0-s07-discovery-20260901-a/reports/P0_M1_SUMMARY.md)
及 [S-07 证据复用清单](S07_EVIDENCE_REUSE_20260902.json)为准。

### 3.2 目标服务器本地化时仍须补齐的资产

以下项目只在对方最终选择本地数据 profile 时执行，不要求在用户工作站准备：

1. 目标 Linux 上与指定 PDB 快照绑定的 MMseqs2 二进制、序列数据库和索引。
2. PDB entity/chain 轻量元数据快照，以及可按候选读取的完整 mmCIF 文件库；本地
   `entries.idx` 与两个文件验证候选不能替代该发布。
3. 与批准覆盖范围一致的 UniProt FASTA、accession/序列版本信息和 BLAST 数据库。
4. 与上述 accession 覆盖一致的 AlphaFold DB 模型、置信度、PAE 和本地关系索引。
5. 目标 Linux 服务器的工具二进制、依赖、CPU/内存/磁盘基线和健康检查结果。

## 4. 目标服务器发布候选与容量依据

以下数字只用于对方部署团队评估目标服务器容量，**不是当前工作站的下载清单**。正式本地化
发布时仍要保存实际响应头、文件大小和校验值：

| 数据/工具 | 当前可见发布 | 规划事实 | 许可 |
|---|---|---|---|
| wwPDB | 每周更新的 archive/mirror | 可通过官方 rsync 镜像冻结 divided mmCIF 和派生序列；本地 2026-08-22 快照已落后于当前镜像，属于正常的版本差异 | PDB archive 数据为 CC0 1.0 |
| UniProtKB | 2026_02，2026-06-10 | Swiss-Prot FASTA 93,706,469 B；TrEMBL FASTA 40,542,998,911 B；完整 idmapping 压缩包 14,058,076,092 B | 可版权部分为 CC BY 4.0 |
| AlphaFold DB | v6 bulk download | Swiss-Prot CIF 包 40,062,921,728 B；human proteome v6 包 5,177,506,304 B；当前 bulk 目录还包含其他完整蛋白组 | CC BY 4.0，发布物须保留归属信息 |
| NCBI BLAST+ | 2.17.0+ | 当前本地版本与官方 `LATEST` 一致 | 二进制与第三方组件许可随官方包保存 |
| MMseqs2 | 18-8cc5c | 固定 release/commit；索引必须记录生成它的 MMseqs2 版本，升级后重新验收 | MIT；保留 LICENSE 和版本信息 |

正式容量不能只按压缩包相加。部署前还要实测解压后文件、MMseqs2/BLAST 索引、临时构建空间、
双版本切换空间和日志空间；没有目标服务器盘点前不在方案里猜一个磁盘数值。

官方依据：[wwPDB 镜像说明]、[wwPDB 使用政策]、[UniProt 当前发布目录]、[UniProt 下载说明]、
[UniProt 许可]、[AlphaFold DB bulk 目录]、[AlphaFold DB FAQ]、[AlphaFold DB 许可]、
[NCBI BLAST+ LATEST]、[NCBI BLAST 手册]、[MMseqs2 releases]。

## 5. 版本化目录与 manifest

目标 Linux 服务器建议采用下列物理布局；实际根目录由服务器盘点决定：

```text
<t01-data>/s07/releases/<release_id>/
├── manifest.json
├── pdb/<pdb_snapshot>/
│   ├── source/
│   ├── sequence-mmseqs/
│   ├── metadata/
│   └── coordinates/
├── uniprot/<uniprot_release>/<coverage_profile>/
│   ├── source/
│   ├── blastdb/
│   └── accession-sequence-index/
├── alphafold-db/v6/<coverage_profile>/
│   ├── source/
│   ├── models/
│   ├── confidence/
│   ├── pae/
│   └── accession-model-index/
├── relationships/
└── health/

<t01-tools>/
├── ncbi-blast/2.17.0+/
└── mmseqs2/18-8cc5c/
```

`manifest.json` 至少包含：

- `release_id`、创建时间、构建主机、覆盖 profile 和状态；
- 每个上游发布的名称、日期、原始 URL、大小、哈希和许可；
- 工具版本、二进制哈希、完整构建命令和参数；
- 原始文件、派生索引和关系索引的逐文件或分片 manifest；
- PDB、UniProt、AlphaFold DB 的覆盖范围和已知未覆盖范围；
- 健康检查用例、结果、耗时和资源峰值；
- `scientific_ruleset_version`，但不得在数据发布中偷偷写入未批准的科学阈值。

运行时只读一个明确的 `release_id`。新发布在独立目录构建和验收，通过后原子切换激活引用；
旧发布继续只读保留，正在执行的 run 不跨版本切换。

## 6. 对方目标服务器的本地化构建顺序

本节是交接验收顺序，责任人为对方部署团队；只有选用本地 profile 时执行。

| 顺序 | 工程动作 | 交付 | 通过条件 |
|---:|---|---|---|
| 1 | 对方盘点目标服务器 | OS/CPU/内存/磁盘/文件系统/账户/网络清单 | 能计算下载、解压、索引、双版本和临时空间 |
| 2 | 冻结工具 | BLAST+ 与 MMseqs2 二进制、许可、哈希和版本输出 | 在目标主机执行版本与最小样本成功 |
| 3 | 冻结数据 profile | PDB 快照、UniProt 发布与范围、AFDB v6 范围 | 三者的覆盖和不覆盖都写入 manifest |
| 4 | 下载原始发布 | 只读 source 目录和下载记录 | 大小、上游校验或本地 SHA-256 全部通过；失败不进入构建 |
| 5 | 建立派生索引 | PDB MMseqs2、UniProt BLAST、轻量元数据与关系索引 | 索引能回读记录，工具版本与源哈希绑定 |
| 6 | 执行关系审计 | 序列→PDB 实体/链/坐标；accession→AFDB 文件 | 缺关系和缺文件有计数与原因，不能静默忽略 |
| 7 | 离线验收 | 正常、空结果、损坏、缺文件、取消/恢复用例 | 断开公网仍能运行；损坏返回故障而非“无命中” |
| 8 | 冻结发布 | manifest、验收报告和只读权限 | 发布状态可从 `STAGED` 政策化切到 `FROZEN` |

## 7. 数据覆盖采用什么安排

| profile | 用途 | 当前状态 | 能说明什么 |
|---|---|---|---|
| `fixture-o15116-v1` | 单条关系与文件完整性验证 | 已通过 | 工程链能从序列找到 accession 并定位 AFDB v6 文件 |
| `api-p0-v1` | 当前 P0 API 取证与后续契约实现 | 任务 4 取证已完成 | API 请求、版本、正常空结果、无模型、非法标识和歧义形态可追溯 |
| `integration-swissprot-afdb-v6` | 对方服务器的首套本地化集成资料 | 交接建议，尚未部署 | UniProt Swiss-Prot 与 AFDB Swiss-Prot bulk 范围直接对齐，适合本地化验收 |
| `production-expanded` | 面向实际支持物种扩展 AFDB proteome 与 UniProt 数据 | 待任务 4 实测和业务覆盖确认 | 扩大真实输入覆盖，容量和 accession 选择问题随之增加 |
| `full-uniprotkb` | Swiss-Prot + TrEMBL 全库检索 | 不默认下载 | 仅扩大 UniProt 命中范围；不能保证命中 accession 在已装 AFDB 中有模型 |

当前 P0 使用 `api-p0-v1`。如果对方之后要求本地化，首套本地发布建议使用
`integration-swissprot-afdb-v6`，因为数据库与模型范围可以逐条核对。它只是一套可复现的集成
验收 profile，不能被表述为 T-01 已经支持全部 UniProtKB 或全部物种。

这里出现了一个**具体的原文缺口**，不是文档之间的冲突：专家资料只规定“BLAST 查询 UniProt
编号后再查 AlphaFold DB”，没有规定 UniProt 搜索库只含 Swiss-Prot 还是还含 TrEMBL，也没有
规定多个 accession 怎样选、最高命中没有本地 AFDB 模型时怎样继续。这会改变结构覆盖和最后
选到的模型。

任务 4 已用 API 完成一对多、无模型、相近命中和多 isoform 取证，并形成
[5 项专家确认问题总表](S07_EXPERT_CONFIRMATIONS.md)。生产冻结前必须明确最终覆盖 profile、
相似 accession 门槛和多命中处理；对方本地化部署沿用确认后的同一规则。

## 8. 验收清单

### 8.1 已完成的隔离验收

- 原 UniProt FASTA 与隔离复制件哈希一致。
- BLAST DB v5 为 1 条、133 residues；`blastdbcheck -full` 成功。
- `blastdbcmd` 按 accession 回读的序列与输入相同。
- 工程连通性查询观察到 133/133、100% identity、100% query coverage。
- AlphaFold DB 元数据的 accession、model ID、v6 和 133 aa 序列均与输入一致。
- model mmCIF、confidence 和 PAE 文件存在且哈希与旧证据一致。
- `scientific_acceptance=NOT_RUN`、`production_deployment_status=NOT_DEPLOYED` 已写入 manifest。

第一次不带 taxdb 的完整性检查因 taxid 9606 无法解析而失败；将冻结 taxdb 加入 `BLASTDB` 后
完整检查通过。因此生产健康检查必须同时验证主数据库和 taxonomy 依赖，不能只看索引文件存在。

### 8.2 对方目标服务器本地化发布尚须通过

以下验收仅在交付选择本地 profile 时由对方部署团队执行：

1. 每个下载文件、索引、模型和元数据分片均能回到来源 URL、版本、大小与哈希。
2. MMseqs2 和 BLAST 的实际版本与 manifest 一致；换版本重建索引，不直接复用未验收索引。
3. 以 1UBQ 等冻结输入完成序列→PDB entity/chain→元数据→mmCIF 的离线往返。
4. 以 O15116 等冻结输入完成序列/accession→UniProt→AFDB model/confidence/PAE 的离线往返。
5. 对正常无记录、accession 无模型、元数据缺失、索引损坏和结构文件损坏分别得到不同状态。
6. 禁止网络后仍能完成声明范围内查询；任何在线访问都视为验收失败。
7. 输出携带 `release_id`、各上游版本、工具版本、参数和原始产物引用。
8. 运行账户对冻结发布只读；新旧发布并存时，已开始的运行仍固定原版本。

## 9. 当前结论和下一动作

任务 2 已完成数据关系验证和目标服务器本地化交接方案；任务 3 完成 PDB 检索/结构读取证据，
任务 4 完成官方 API 的 UniProt accession 与 AFDB 回退取证。当前不在用户工作站继续下载全量
数据库。任务 5 已统一 API 路径的内部结果、错误和追溯契约，完成 46 项离线检查及验证文档；
任务 6 已完成固定发布与当前 API 的非生产独立验收、资源记录和 P0 组件交接候选。
[P0 v0.6 方案](../../../../project-history/p0/P0_IMPLEMENTATION_PLAN_v0.6_ARCHIVE.md)已完成重写和工程评审；下一项为 `P0-V06-M1`，
五项暂行科学规则仍待专家确认。

目标 Linux 的盘点、索引构建和完整 PDB/UniProt/AFDB 发布属于后续交付给对方部署团队的任务。
只有对方选择并开始本地 profile 部署时，才按本文件第 5、6、8.2 节执行；完成前继续标记
`TARGET_SERVER_HANDOFF_PENDING / NOT_DEPLOYED`。

[wwPDB 镜像说明]: https://www.wwpdb.org/ftp/pdb-ftp-sites
[wwPDB 使用政策]: https://west.wwpdb.org/about/usage-policies
[UniProt 当前发布目录]: https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/
[UniProt 下载说明]: https://www.uniprot.org/help/download
[UniProt 许可]: https://www.uniprot.org/help/license/
[AlphaFold DB bulk 目录]: https://ftp.ebi.ac.uk/pub/databases/alphafold/latest/
[AlphaFold DB FAQ]: https://www.alphafold.ebi.ac.uk/faq
[AlphaFold DB 许可]: https://alphafold.ebi.ac.uk/assets/License-Disclaimer.pdf
[NCBI BLAST+ LATEST]: https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/
[NCBI BLAST 手册]: https://www.ncbi.nlm.nih.gov/books/NBK52640/
[MMseqs2 releases]: https://github.com/soedinglab/MMseqs2/releases
