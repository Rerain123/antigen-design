# W1-08B2：DeepTMHMM 原包边界与执行补证

本项承接 [B2 限定评审](PHASE1_REAL_W1_B2_REVIEW.md)和
[用户本机执行决定](../sources/PHASE1_W1_B2_BOUNDARY_EXECUTION_20260906.json)。
当前进度与下一步见 [STATUS](../STATUS.md)；本轮检查见 [验证记录](PHASE1_REAL_W1_B2_BOUNDARIES_VERIFICATION.json)。

## 1. 范围与执行约束

阶段保持 W1-08B2。独立脚本调用用户原 Academic 1.0 的 predict.py，不注册通用运行层的科学 Worker，
不写入 Dify 或正式项目 topology。B1 的结构/映射签收和 AF3/ESMFold2 不作为本项依赖。
本机开发事实不代替目标环境复现、输入域、独立科学参考及契约的适用签收；W1-09B2 尚未放行。

使用前批固定 image ID，CPU quota 8、affinity 0–7、10 GiB 内存及同额 memory-swap、900 秒单条上限、
512 个进程限制、禁网、只读根文件系统和只读包/输入/观察脚本；同时最多一个模型容器。
原包科学默认参数、线程策略和权重字节保留。命令、输入 hash、前后 41 项资产 hash 校验、
容器 inspect、stdout/stderr、实际退出/OOM/停止确认、运行资源和全部产物 hash 分别留存。

证据批次为 [deeptmhmm-academic-boundaries-20260906](../../../discovery/t01-phase1-real/w1/deeptmhmm-academic-boundaries-20260906/README.md)，
与前序 Academic 实测和 B2 只读评审批次分开；旧 plan、profile、判断和 manifest 不回写。
来源以 A5 ToolSpec §2/3/5/7、SOP S-04/T-01 和原包 utils.generate_esm_embeddings 为准；
此前收集的完整专家/包源码 hash 通过本批 protected_before 和前批 verify 复核。

## 2. 预声明输入与真实 token 观察

[计划](../../../discovery/t01-phase1-real/w1/deeptmhmm-academic-boundaries-20260906/plan.json)
在调用前登记输入字节/hash、来源与预期类别。安全 ID 控制使用原 Q8K459 的同一条 51 aa 输入；
短/长样本由该序列重复并截取为明确长度，全部标记人工边界夹具，不当作独立生物学金标准。
短输入包含 1、8、9、29、30 aa；长输入包含 1020、1021、1022、1023 aa。
1/8 aa 仅用于探测原包，T-01 正常流程的 <9 aa 上游守卫保持不变。

观察器通过 sys.settrace 读取原 utils.py 指定行上的真实局部变量，不替换 tokenizer、模型前向函数、
张量或源码。每条记录真实 token IDs、解码字符串、起止标志、每次成功前向的切片位置/长度、
表示张量形状与有限值、最终 embedding 长度。事件立即写入 token_trace.jsonl，原包异常时仍保留已完成观察。
校验器用观测到的 token 回拼原序列，要求切片不重叠、不遗漏，embedding 与原 aa 长度相等。
1022 是原代码的 token 常量；是否触发切片以实际事件为据，不声明为 aa 输入上限。

## 3. 安全 ID、原产物与失败拦截

每条 FASTA ID 使用 `t01seq_` 加原序列 UTF-8 SHA-256。原用户 ID 保留在计划元数据中，
不参与输出路径；安全 ID 控制的元数据特意包含空白、路径/分隔符和中文。
实际输出需满足以下独立条件：

- FASTA、执行记录和 SHA-256 一致；三行输出的 ID、原序列及标签长度逐一对应。
- 八列原区段格式、完整连续覆盖、类型与标签和 TMR 数一致；P/B 仍按 A5 §7 保留原值并禁止正常交付。
- 单条概率文件名必须与安全 ID 精确一致，头部 ID、0-based 位置、AA 和六列有限概率值一致。
- Markdown 原报告、PNG 与 embedding 文件齐备，完整目录清单及每份字节/hash 可回读。
- 成功执行必须已停止且退出 0，不能把进程失败、超时、OOM 或未确认停止解释为产物成功。

预声明的原包失败探测包括空 FASTA 记录、含 `*` 的非法字符输入，以及预先复制成功结果后触发“输出目录已存在”。
后者专门检验：即使失败目录里存在一套旧拓扑，执行失败也必须先行拒绝，不能被旧文件掩盖。

缺失/损坏案例只改真实成功结果的独立副本，标记 `POST_EXECUTION_ARTIFACT_FAULT_COPY`，
不声称为模型自然产生的故障。分别移除预测/区段/概率/PNG/报告/trace，截断标签，改错序列/ID/区段，
注入 NaN 或错误概率位置，改坏 PNG/报告 ID/token，另测 hash 篡改与未登记文件。
语义故障副本登记自身清单，使测试触达格式/绑定检查；hash 故障保留原清单，以验证完整性拒绝。
每个故障保留来源执行、原清单、变更声明及具体诊断；拒绝结果的 raw_record/topology 为空、不可消费、需复核。

## 4. 验收与适用边界

安全 ID 控制要求完整原产物且与前批同序列的标签/类型/区段精确一致。
边界输入允许原包成功或有具体诊断的失败；成功必须通过全部位置/token/产物一致性检查，
失败必须保留 stdout/stderr 和终止证据。预声明负例须被拒绝，不能通过删案例或放宽条件消除失败。

完整原始结果标记 COMPLETE_RAW_ONLY；这只表示开发文件完整，不给出生产 topology、科学准确率或消费资格。
本批不会扩大旧 B2 profile 的已批准域，不补造独立参考、性能 SLA、概率和容差或科学验收阈值。
GPU、并发/恢复、目标干净机复现和未覆盖的更长长度仍需按自身适用条件验证；900 秒保护存在不等于已实测超时场景。
后续以 B2-G1-INPUT/REFERENCE/RUNTIME/CONTRACT 的具名签收为入口进入正式适配器实施。

## 5. 实测结果与原包发现

[实际方法记录](../../../discovery/t01-phase1-real/w1/deeptmhmm-academic-boundaries-20260906/method_summary.executed.json)
从每次 runtime/token_trace 回读；原 method_summary 是调用前声明，PENDING_EXECUTION 保留其时点含义。

| 输入长度 aa | 实际 token 数 | 实际前向切片 token 数 | 结果 |
|---|---|---|---|
| 1 / 8 / 9 / 29 / 30 | 3 / 10 / 11 / 31 / 32 | 分别为同数单片 | 原包成功、完整回连 |
| 51（安全 ID 控制） | 53 | 53 | 原包成功，与前批同序列标签/类型/区段一致 |
| 1020 | 1022 | 722 + 300 | 原包成功、完整回连 |
| 1021 | 1023 | 722 + 301 | 原包成功、完整回连 |
| 1022 | 1024 | 722 + 302 | 原包成功、完整回连 |
| 1023 | 1025 | 722 + 303 | 原包成功、完整回连 |

这些输入的 tokenizer 均增加 `<cls>` 和 `<eos>`；观测的长输入切片按 0-based 半开区间首尾相接，
最终 token 与序列回拼完整。此前方法文案中的“overlap”不替代实际切片证据：本批未观测到重叠 token。
长输入单条墙钟约 96 秒，最高进程峰值 RSS 为 5,695,096 KiB；这是本机资源观察，含追踪开销，不是性能 SLA。

实际调用共 13 次：10 份完整原始成功结果，2 次原包退出 1，另 1 次原包退出 0 但被后置校验拒绝。
空记录在模型加载前拒绝；“输出目录已存在”保留了成功产物副本，仍因执行失败拒绝消费。
17 类独立产物故障全部被拒绝并保留具体诊断；没有 OOM 或超时，不声称验证了这两类实际故障。

**B2-E01：`*` 被静默转成 `<unk>`。** 输入 `ACDEFGHIK*` 的真实 tokenizer 输出 12 个 token，
其中 `*` 对应 ID 3 / `<unk>`，原包最终退出 0。原计划预期“原包拒绝”未满足，
[初次评估失败与来源发现](../../../discovery/t01-phase1-real/w1/deeptmhmm-academic-boundaries-20260906/source_finding.json)
保留计划、原输出、初次检查器与失败记录，未改预期或放宽消费检查。
后置检查报 TOKEN_RECONSTRUCTION_MISMATCH；已有 B2 输入预检报 INVALID_SEQUENCE_SYMBOL，
因此不能依赖原包退出码代替项目输入域检查。本次专用回归同时核实两处拒绝。

限定结论为 PASS_DEVELOPMENT_EVIDENCE_WITH_ORIGINAL_TOOL_FINDING：工程补证完成，
原包拒绝预期有一项未满足且明确记录；不是“全部原包行为均符合预期”，不扩大输入域或放行正式适配器。
