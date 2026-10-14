# S-07 任务 5 契约验证报告

> 日期：2026-09-03；批次：`p0-s07-task5-contract-20260903-b`。  
> 契约版本：`s07.task5.v1-review`；结论：`PASS_OFFLINE_CONTRACT_ONLY`。  
> 专家问题：原有 **5 项**，均为暂行采用、待专家确认。  
> 科学验收：`NOT_RUN`；部署状态：`NOT_DEPLOYED`；本批次新增网络调用：0。

任务 5 的内部结果契约、文件保存、错误与恢复说明及验证记录已完成。原始批次于
`2026-09-03T01:45:04.151303+00:00` 形成 46 项通过记录；本次文档收尾对该批次只读复核，
并补存测试和文档校验记录。任务 3/4 的真实来源证据、受控组合以及来源组件探针分别标注；
本报告不把它们计作新的完整在线 S-07 验收。

## 1. 交付与统计

| 项目 | 结果 | 证据 |
|---|---|---|
| 路由/错误结果场景 | 19/19 PASS | [机器证据](task5_contract_evidence.json) `route_cases` |
| 非法结果拒绝检查 | 20/20 PASS | 同文件 `rejection_checks`；PASS 表示错误载荷被拒绝 |
| 文件与恢复检查 | 7/7 PASS | 同文件 `storage_checks` |
| 三类检查合计 | **46/46 PASS** | 同文件 `total_checks` |
| 冻结来源文件 | 136 个、3,458,076 字节 | [来源索引](source_evidence_index.json)，全部登记过旧 manifest 校验 |
| 已保存结果 | 19 份 | [结果目录](../results)；包括同一运行的失败/重试两次尝试 |
| 正常内容对象 | 252 个 | [文件索引](../artifact_index.json)，逐对象大小与 SHA-256 复核 |
| 项目自动化测试 | **111/111 PASS** | [JUnit](pytest_results.xml)、[测试输出](pytest_output.txt)；其中任务 5 为 25 项 |
| 文档检查 | PASS | [检查输出](documentation_check.txt) |
| 收尾一致性复核 | PASS | [收尾记录](closeout_verification.json)，含命令、版本、哈希和逐项检查 |

46 项是本批次的场景/守卫计数，25 项是 pytest 对同一契约的测试计数，两者存在覆盖重合，
不相加为独立验收样本数。其余 86 项测试沿用既有工程基线。

契约正文见 [S07_TASK5_RESULT_CONTRACT.md][契约]，机器字段见
[冻结 JSON Schema](../schema/S07_TASK5_RESULT_CONTRACT.schema.json)。Schema 结构检查、Python
跨字段校验和文件内容校验均参与验证；单独使用 JSON Schema 不能覆盖全部不变量。

## 2. 路由与异常场景

下表的 S-08/S-09 均为结果中的 `next_step`，未实际调用下游工具。所有场景 PASS 表示符合其
预期结果，其中预期失败或待复核并不等于查询成功。

| 用例 | 场景与证据性质 | 预期且实际状态 | 下一步 | 保存结果 |
|---|---|---|---|---|
| R01 | 真实 6Q00 文件＋受控单候选池，完整实验结构 | `SUCCEEDED` | S-09 | [结果](../results/task5-R01/attempt-001.json) |
| R02 | 6Q00 派生 partial，输入 71–76 共 6 位 null | `DEGRADED` | S-09 | [结果](../results/task5-R02/attempt-001.json) |
| R03 | 已有 O15116 accession，冻结 UniProt/AFDB 文件回验 | `SUCCEEDED` | S-09 | [结果](../results/task5-R03/attempt-001.json) |
| R04 | 受控完整 BLAST 候选集＋冻结 UniProt/AFDB 证据 | `SUCCEEDED` | S-09 | [结果](../results/task5-R04/attempt-001.json) |
| R05 | 受控 PDB 空结果＋真实 BLAST 零命中回放，AFDB 未执行 | `SUCCEEDED` | S-08 | [结果](../results/task5-R05/attempt-001.json) |
| R06 | 合法 accession 无 AFDB 模型的 404 来源组件探针 | `SUCCEEDED` | S-08 | [结果](../results/task5-R06/attempt-001.json) |
| R07 | 非法编号 400 来源组件探针 | `FAILED` | null | [结果](../results/task5-R07/attempt-001.json) |
| R08 | 输入与 AFDB 非精确匹配，保留候选待复核 | `WAITING_USER` | null | [结果](../results/task5-R08/attempt-001.json) |
| R09 | 三个全长精确 accession，禁止按返回顺序选取 | `WAITING_USER` | null | [结果](../results/task5-R09/attempt-001.json) |
| R10 | 基础 accession 返回四个不匹配 isoform，组件探针 | `WAITING_USER` | null | [结果](../results/task5-R10/attempt-001.json) |
| R11 | 受控 PDB 元数据全部失败，AFDB 成功；保留不可靠与复核标志 | `DEGRADED` | S-09 | [结果](../results/task5-R11/attempt-001.json) |
| R12 | 受控 PDB 元数据失败＋AFDB 无模型，组件探针 | `FAILED` | null | [结果](../results/task5-R12/attempt-001.json) |
| R13 | 受控查询超时，保存第一次失败 | `FAILED` | null | [结果](../results/task5-retry/attempt-001.json) |
| R14 | 相同 run/输入/profile 重试成功，保留 R13 | `SUCCEEDED` | S-09 | [结果](../results/task5-retry/attempt-002.json) |
| R15 | 受控取消，后续来源保持未执行 | `CANCELLED` | null | [结果](../results/task5-R15/attempt-001.json) |
| R16 | 真实 BLAST 100 条上限回放，候选集合未证实完整 | `FAILED` | null | [结果](../results/task5-R16/attempt-001.json) |
| R17 | 真实 9R2Q 的 K/L/M/N 四条匹配链，按 R-58 保留歧义 | `WAITING_USER` | null | [结果](../results/task5-R17/attempt-001.json) |
| R18 | 受控损坏 mmCIF，保存原字节并报错 | `FAILED` | null | [结果](../results/task5-R18/attempt-001.json) |
| R19 | 受控 PDB 元数据部分失败，不以余下候选宣称最优 | `FAILED` | null | [结果](../results/task5-R19/attempt-001.json) |

R01–R05、R08/R09、R11、R13–R19 的批次范围为 `CONTROLLED_COMPOSITION`；R06/R07/R10/R12
为 `COMPONENT_PROBE`。每个来源操作还独立标注 `FROZEN_REPLAY`、`CONTROLLED` 或 `NOT_RUN`，
可以从保存结果回到原始文件，避免以整个场景的标签掩盖其中的受控部分。

## 3. 非法结果拒绝检查

| 检查 | 故意构造的错误 | 结果 |
|---|---|---|
| N01/N02 | identity=95% 或 query coverage=90% 却宣称合格 | 均拒绝；严格不等号守卫生效 |
| N03/N04 | `source=none` 候选或提前写入 S-09 confidence | 均拒绝 |
| N05/N06 | 非全长精确 AFDB 自动选择，或未通过 UniProt 序列回验 | 均拒绝 |
| N07 | 未执行来源伪造响应时间 | 拒绝 |
| N08 | partial 结果漏掉警告 | 拒绝 |
| N09/N10 | 取消或 PDB 元数据失败后伪装正常无结构并进入 S-08 | 均拒绝 |
| N11/N12 | BLAST 达到上限后自动选结构或声明正常均无 | 均拒绝 |
| N13 | 未执行的必要来源被当作正常均无 | 拒绝 |
| N14 | 结果引用的文件未列入 ArtifactRef | 拒绝 |
| N15 | 多链歧义被改成自动选择 | 拒绝 |
| N16 | 同一来源操作重复登记 | 拒绝 |
| N17 | 缺失坐标区段与覆盖计数不一致 | 拒绝 |
| N18 | 来源被绑定到另一条输入序列 | 拒绝 |
| N19 | 部分元数据失败却写 `complete=true` | 拒绝 |
| N20 | 重试没有引用上一次结果 | 拒绝 |

拒绝原因保存于[原始检查 JSON](task5_contract_evidence.json)。这些检查约束已知结果形态，
不是完整的生产对抗测试或全部科学规则验收。

## 4. 文件与恢复检查

| 检查 | 实际操作 | 结果 |
|---|---|---|
| F01 | 将受控对象 `abc` 改为等长 `abd`，重新读取 | SHA-256 不符，拒绝；仅检查长度不足以通过 |
| F02 | 读取不存在的对象 | 文件缺失错误被捕获 |
| F03 | 尝试以不同字节覆盖已存文件 | 拒绝，旧字节仍为原值 |
| F04 | 重读并重复保存同一结果 | 结果字节和 SHA-256 不变，无新来源调用 |
| F05 | 同一 run 尝试更换输入快照中的物种 | 不可变绑定拒绝新值 |
| F06 | 读取 R14 并校验其引用的 R13 | 上次失败的哈希一致，尝试编号与输入/profile 连续 |
| F07 | 用真实 mmCIF 解析器读取受控坏文件 | 解析失败，保留格式错误事实 |

故障注入只作用于本批次的 `controlled/storage-probes/` 和明确标记的派生文件；任务 3/4
原件不被修改。正常 artifact 索引包含 252 个可完整读取的内容对象；故意损坏的 storage probe
不混入该索引。

文件完整性与格式有效性分开：R18 的损坏文件可按其原始坏字节留档，但不能作为有效结构供
下游使用。错误结果保留其文件引用，便于重现失败；后续尝试另存，禁止覆盖第一次失败。

## 5. 本次收尾复核

本次使用既有 b 批次的 `--verify` 模式，核验 19 份结果、252 个索引对象及其输入、profile、
来源/候选 manifest、MethodSummary 和重试关系。随后比对 136 个来源文件与任务 3/4 的
原始 manifest，核对当前模型生成 Schema、文档 Schema 与批次 Schema 一致，并复核当前
21 个专家原件哈希。

收尾命令、执行时间、运行环境版本和证据摘要记录在
[closeout_verification.json](closeout_verification.json)。项目全套测试运行使用独立测试临时目录，
结果为 111 项通过、无失败；任务 5 的 25 项测试会重新构造其受控场景，既有 b 批次保持原字节。
文档链接和入口检查也通过。

复核方法见[运行手册][运行手册]。若需要产生新的证据批次，构建器必须接收全新的 `--campaign`
目录；不能用重跑覆盖本批次，或者把读取旧结果算成一次新的在线工具执行。

## 6. 限制与任务 6 输入

- R01 的真实结构来自冻结 6Q00 文件，但候选池只有受控的一条，未证明新的全库最优。
- R02 是派生 partial；真实 9R2Q 的四链歧义仍在 R17 阻止自动交接。
- R04 使用受控完整 BLAST 候选集；任务 4 真实正命中达到 100 条上限的事实单独由 R16 保留。
  后续完整链验收需解决候选收集闭合问题。
- R06/R12 的 12 aa 输入仅用于来源组件探针，完整 T-01 会在更早的长度守卫处停止。
- AFDB confidence/PAE 原件与原生指标已保存；未生成 S-09 的质量分档、掩码或最终 CandidateRecord。
- 当前证明的是冻结结果可重复读取。新在线请求可能观察到变化的数据发布，须另记来源版本与结果。
- 真实 S-07 连续运行、耗时资源、部署、S-08/S-09 对接、生产并发/崩溃恢复及 OI-017 长任务
  状态机尚未完成，不能由本报告替代。

本次没有新增专家问题；[五项清单][专家问题]保持 `PROVISIONAL_USER_APPROVED /
EXPERT_CONFIRMATION_PENDING`。OI-018 仍为 `IN_REVIEW`，OI-015/019 的既有状态不变。
任务 5 可交付审阅，任务 6 和生产实现仍按 [S-07 任务安排][任务安排]及 P0 v0.6 门禁推进。

[契约]: ../../../../../docs/project/stages/p0/S07_TASK5_RESULT_CONTRACT.md
[运行手册]: ../../../../../docs/development/RUNBOOK.md#11-s-07-任务-5-离线契约验证
[专家问题]: ../../../../../docs/project/stages/p0/S07_EXPERT_CONFIRMATIONS.md
[任务安排]: ../../../../../docs/project/stages/p0/S07_IMPLEMENTATION_TASKS.md
