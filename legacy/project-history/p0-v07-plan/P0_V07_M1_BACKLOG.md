# P0-V07-M1 甲方输入契约归并 Backlog

> 状态：`READY_NEXT / NOT_STARTED`  
> 日期：2026-09-03  
> 上级计划：[P0 实施方案 v0.7](P0_IMPLEMENTATION_PLAN.md)  
> 核心开放项：OI-023=`IN_REVIEW`  
> 生产状态：`NOT_DEPLOYED`

## 1. 目标

把最新用户决定与专家 SOP、Schema、ToolSpec 中已经给出的输入规则归并成一个可评审、可校验、
可追溯的 `P0InputBundle`。M1 不向用户发送宽泛字段问卷，不实现生产代码、不修改 Dify、
不运行科学工具。

## 2. 已确认边界

- 内网限制只影响外部数据库查询，不影响部署在甲方服务器上的 AlphaFold3/ESMFold2 正常使用；
- 节点 01 不查询 RCSB PDB 或 AlphaFold DB，S-07 及 BLAST→UniProt→AFDB 回退不进入一期；
- 必填输入：`protein_sequence`（目标蛋白序列）、`host_species`（宿主物种）；
- 可选输入：`structure`（甲方本地提供的结构）；
- 有合法结构时解析后进入 S-09；无结构时执行 S-08 AlphaFold3/ESMFold2，再进入 S-09；
- accession、PDB ID、URL、名称或自由文本不得触发外部数据库补齐；
- 字段、格式和科学校验先读取专家原文；只有真实冲突或缺口才提交对应专家，不重复询问用户。

## 3. 已定位的专家依据

| 主题 | 专家依据 | 可直接采用的结论 |
|---|---|---|
| 顶层输入 | [一期 18 节点图](<../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期裁剪算法图（一期 18 节点 + 落地优先级）.md>) L9；[Agent A SOP](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md) L1785–1805 | 目标蛋白序列、宿主为主输入；设计目标、表达宿主等按图/SOP 为可选 |
| 字段名 | [Agent A Schema](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md) L21–32 | 使用 `protein_sequence`、`host_species`；二者为 string |
| 结构可选 | 用户最新决定；[S-07c SOP](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md) L361–379 | 结构可选；本地文件解析不等于恢复 S-07 数据库检索 |
| 结构格式 | S-07c SOP L363–375；[结构链 ToolSpec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md) L48–51 | 接受 PDB/CIF/mmCIF；保留原格式；下游确需时另行转换 |
| chain | S-07c SOP L363/371 及 S-07b L349–354 | chain 可选、默认 auto；取第一条 protein chain，排除 DNA/RNA/ligand；多蛋白链告警 |
| 结构异常 | S-07c SOP L376–378 | 原子缺失比例 >20%→WARNING；格式无法解析→`failure_report` |
| 映射 | [Agent A SKILL](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md) R-58 | 结构工具前执行序列比对、选链、缺失残基与 insertion code 映射；歧义禁止自动交接 |
| S-08 输入/路由 | Agent A SOP L238–280；结构链 ToolSpec L31–38 | `seq` 输入；AF3 默认，ESMFold2 按明确路由/失败条件使用；长序列规则已有原文 |

## 4. 工作项

| 工作项 | 交付物 | 负责人角色 | 状态 | 完成证据 |
|---|---|---|---|---|
| `V07-M1-01` 来源归并 | 最新决定、流程图、SOP、Schema、ToolSpec 的字段/规则/优先级矩阵 | 文档工程 + 后端 | `READY` | 每条契约可回溯到原文位置 |
| `V07-M1-02` 请求 Schema | `P0InputBundle` review schema：必填序列/宿主、可选结构及工程身份字段 | 后端 | `NOT_STARTED` | Schema review draft 与示例通过结构校验 |
| `V07-M1-03` 序列校验 | string/FASTA 载体、规范化、长度、非法输入、hash 和稳定错误码 | 后端 + 算法复核 | `NOT_STARTED` | 决策表、正常/边界/失败 fixtures |
| `V07-M1-04` 可选结构 | PDB/CIF/mmCIF、chain、原格式、ArtifactRef、解析、缺失原子、R-58 前置 | 后端 + 算法复核 | `NOT_STARTED` | 文件契约及单链/多链/损坏/不一致用例 |
| `V07-M1-05` 字段映射 | `host`→`host_species` 迁移、`structure`→`file_path`→`pdb_path` 层级、`organism` 下游边界 | 文档工程 + 后端 | `NOT_STARTED` | 无双事实源的映射表与兼容策略 |
| `V07-M1-06` 工程接收与追溯 | ArtifactRef、内网接收、权限、大小、hash、provider/time/version、替换、attempt、幂等 | 后端 + 运维 | `NOT_STARTED` | 状态转移表、审计样例、不可覆盖检查 |
| `V07-M1-07` 验收与复核 | fixture manifest、机器预期、专家原文一致性审阅、真实冲突/缺口清单 | 测试 + 后端 + 算法复核 | `BLOCKED_BY_M1_01_TO_06` | 测试结果、具名评审与 OI-023 关闭记录 |

## 5. 归并原则

1. 专家原文一致且字段含义明确的内容直接进入 review contract，不再询问用户。
2. 上传、ArtifactRef、哈希、幂等、错误码和存储隔离属于工程契约，由后端/运维给出确定性方案。
3. 工具支持范围通过 M2 G0 验证；G0 只确认工具事实，不改写专家科学规则。
4. 只有多个权威原件给出互斥规则，或原文确实缺少会改变科学结果的条款时，才形成定点专家问题。
5. 定点问题必须带原文位置、冲突、影响、建议和边界案例，不能把整份字段表转交用户填写。

## 6. 当前已知的文档归并点

这些是 M1 内部任务，不是向用户提出的问题：

- 旧请求契约使用 `host`，专家 Schema 使用 `host_species`；当前规范字段按最新流程和 Schema
  采用 `host_species`，旧字段只做兼容映射。
- CandidateRecord 的 `organism` 是下游完整记录字段，但最新入口未把它列为 P0 必填；不得因输出
  Schema 的 required 误要求甲方在 P0 重复填报。
- 用户输入层称 `structure`，S-07c 解析参数称 `file_path`，内部结果称 `pdb_path`；M1 要明确三层
  映射并禁止把服务器绝对路径暴露给 Dify/LLM。
- 专家原文规定空/非法序列失败，但没有集中列出所有非标准氨基酸字符；先汇总各工具支持事实，
  若会改变科学接受范围，再提交算法专家定点复核。
- 内网传输形态不改变科学输入语义；先使用 ArtifactRef 抽象，具体 API/对象存储/共享目录由部署
  profile 决定，不作为用户字段问题。

## 7. 与旧 v0.6 backlog 的关系

| 旧项 | v0.7 处置 |
|---|---|
| P0-Q01 | 迁入 M1-01/M1-03，按专家原文收敛输入解析，不重新询问用户已有规则 |
| P0-Q02～Q05、S07-EQ-01～05 | S-07 移出一期，停止作为当前外发/阻塞项 |
| P0-Q10/Q14 | 迁入 M1-02/M1-06，负责输入失败、复核状态和 P0EvidenceBundle 边界 |
| P0-Q16/Q17 | 迁入 M1-07 和后续内网 G0/release 准备 |
| M1-03 B：Q08/Q09 | 迁入 `P0-V07-M3`，不在本 M1 决定 |
| M1-03 C：OI-015/Q12/Q13 | 迁入 `P0-V07-M5`，不在本 M1 决定 |
| `EXEC-S07-CANDIDATE-COMPLETE` | 取消一期门禁；BLAST 100 条触顶不再进入生产计划 |

[P0-V06-M1 backlog](../p0/P0_V06_M1_BACKLOG.md)继续保留为迁移证据，不再是当前任务台账。

## 8. 退出条件

M1 只有同时满足以下条件才可标记完成：

- OI-023 记录来源矩阵、归并结论、具名工程/算法复核、日期和适用版本；
- `P0InputBundle` 明确 `protein_sequence`、`host_species` 必填，`structure` 可选；
- PDB/CIF/mmCIF、chain、原格式、解析失败、缺失原子和 R-58 规则进入结构输入契约；
- 输入接收、校验、驳回、补交、替换和幂等状态无歧义；
- accession-only、PDB-ID-only、URL、缺序列和损坏文件均不能触发远程查询；
- fixture manifest 覆盖正常、边界和失败，并保存输入 hash；
- 文档检查和 116 项冻结测试通过；
- 未运行 G0、未修改生产代码/Dify、未宣称任何真实工具已部署。

不存在真实文档冲突时，M1 不需要额外用户答复即可完成工程评审。M1 退出后，下一包为
`P0-V07-M2` AlphaFold3/ESMFold2 内网 G0。
