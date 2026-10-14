# P0-M1 S-07 能力缺口表

状态：`EVIDENCE_CAPTURE_COMPLETE / CONTRACT_REVIEW_REQUIRED`  
边界：以下结论只用于契约评审，不是生产科学规则，不代表 `structure.fetch` 已部署。

| ID | 实测事实 | 暴露的缺口 | P0-M2 前所需决定/实现 | 责任侧 | 阻塞 P0-M2 |
|---|---|---|---|---|---|
| S07-G01 | RCSB Search 返回 polymer entity，Data API 才提供 entry/entity/instance 事实，mmCIF 又是独立下载 | 单一“命中”对象不足以表达来源、链、实体和产物 | 冻结候选、链、实体、assembly/model 与 ArtifactRef 的层级 Schema | 开发评审 | 是 |
| S07-G02 | 6XRE entity 序列与目标 100% 相同，但 chain M 仅 314/393 个目标残基有坐标 | 序列 exact 不等于坐标完整或技术可用 | 算法负责人确认最低坐标覆盖、允许缺口位置及是否还要分辨率/方法门控 | 算法负责人 | 是 |
| S07-G03 | 5XZC 只覆盖目标 92-356，且 entity 201-233 无坐标 | `TARGET_DERIVED` 必须保存双层映射：target↔entity 与 entity↔coordinates | 冻结逐残基映射格式，以及 derived 是否可直接使用/何时必须进 S-08 | 算法负责人 + 开发 | 是 |
| S07-G04 | 6PPV 对 O15116 的局部 identity 为 62.5%，仅对齐目标 72/133；坐标映射为 69/133 | 有同源命中不等于有可用模板 | 确认 BLAST/MMseqs2 的用途、identity/coverage/e-value 规则和模板排序 | 算法负责人 | 是 |
| S07-G05 | O15116 的 RCSB target-level 查询（identity cutoff 0.9）为 HTTP 204，而 AFDB 以 O15116 返回 exact 133 aa v6 模型 | 实验结构和公共预测结构必须分来源表达，204 不能当故障 | 冻结来源优先级、AFDB 是否算“已有结构”、版本选择与序列回验规则 | 算法负责人 + 开发 | 是 |
| S07-G06 | AFDB 对 RefSeq `WP_505187596.1` 返回 HTTP 400，只接受 UniProt/支持的 AFDB ID | 权威输入只有序列时，不能直接保证找到 AFDB accession | 决定 sequence→UniProt 映射服务、物种约束、歧义处理和无映射降级 | 产品/算法负责人 | 是 |
| S07-G07 | RCSB sequence service 是 MMseqs2；独立 NCBI BLAST+ 对冻结 wwPDB FASTA 运行成功 | C6 “BLAST”不能由 RCSB Search 冒充，两套分数也不可混用 | 明确 C6 数据库、用途、输出字段与两类命中如何去重 | 算法负责人 | 是 |
| S07-G08 | 1UBQ RCSB exact 查询 total=1136、TP53 total=236；本次均只返回前 100 | 不分页/不去重会造成候选截断，排序可能随数据库更新变化 | 冻结分页上限、超量标志、去重键、排序与快照时间字段 | 开发评审 | 是 |
| S07-G09 | BLAST 前两类及同源样本均达到 `max_target_seqs=100`；P0-DISC-005 返回 42 个弱命中，首个 e-value=3.4 | discovery 参数不能充当生产阈值；“无可用结构”不能仅由有/无行决定 | 算法批准 production profile；输出 `capped` 与 `usability_undecided` | 算法负责人 | 是 |
| S07-G10 | wwPDB FASTA 含 B/O/U/X/Z；BLAST DB 需 taxdb 与正确 `BLASTDB` 才能完成元数据校验 | 输入字母、非标准残基和运行依赖未建模 | 冻结序列字符策略、DB/taxdb 版本清单、启动自检和失败码 | 开发 + 运维 | 是 |
| S07-G11 | AFDB 的 CIF/JSON 实际 Content-Type 均为 `application/octet-stream` | 不能仅凭 HTTP Content-Type 判定文件类型 | 按期望 artifact 类型做 magic/语法/维度/哈希校验，保留原始响应头 | 开发 | 是 |
| S07-G12 | 同一次活动中已观察 HTTP 0 连接故障、TLS revocation 故障、HTTP 204、HTTP 400 及 CLI 依赖故障 | “无命中”“无映射”“远端拒绝”“网络故障”必须分离 | 冻结 outcome/error 枚举、重试边界与可恢复性字段 | 开发评审 | 是 |
| S07-G13 | RCSB/AFDB/wwPDB 内容会更新；当前证据已有请求时间、来源 Last-Modified、版本和 SHA-256 | 线上重复调用不天然可复现 | 设计缓存/快照、source version、retrieved_at、request/profile hash 与过期策略 | 开发 + 运维 | 是 |
| S07-G14 | alternate location、assembly 选择、非标准残基与多 model 尚未形成代表性实测映射 | 当前 mapping 只覆盖本轮代表样本 | P0-M2 故障/边界测试中补 parser fixture；不擅自设科学选择规则 | 开发；科学规则待算法 | 否（需列入 M2 验收） |

## 本轮不能得出的结论

- 不能宣布 P0-DISC-005 已科学证明“无可用同源结构”；只能确认无 exact-target 证据，弱命中是否可用尚未决定。
- 不能因为 RCSB/AFDB 返回候选就自动路由“已有结构”。
- 不能把本轮 BLAST `evalue=10`、`max_target_seqs=100` 或 RCSB 查询 identity 参数升级为生产阈值。
- 不能把 AFDB `globalMetricValue` 直接映射为 S-09 high/medium/low。

## 建议的契约评审输入

下一步应基于 `candidate_structure_manifest.json` 与 `sequence_mapping_report.json` 逐字段评审：

1. 输入事实源与可选检索提示；
2. 检索 outcome 与标准 ToolError 的边界；
3. 候选/实体/链/model/assembly/ArtifactRef 层级；
4. 原始 sequence alignment 与 coordinate mapping；
5. 三类暂定命中语义及保守路由；
6. 分页、去重、排序、快照和证据版本。
