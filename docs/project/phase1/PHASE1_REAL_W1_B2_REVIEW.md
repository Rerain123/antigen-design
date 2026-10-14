# W1-08B2：DeepTMHMM 限定评审准备

> 前序设计/评审参考：下文保留原时点的准备范围和结论；当前开发顺序由 [W1 交付任务](PHASE1_REAL_W1_BACKLOG.md)与 [现行计划](../PHASE1_DELIVERY_PLAN.md)覆盖。原科学未签收事实和机器证据保持原义，接手不必通读本页。

本评审承接 [B2 任务包](PHASE1_REAL_W1_B2_REVIEW_BACKLOG.md)及 [Academic 1.0 禁网实测](PHASE1_REAL_W1_DEEPTMHMM_OFFLINE.md)。
当前状态和下一步见 [STATUS](../STATUS.md)，机器结论见 [评审记录](PHASE1_REAL_W1_B2_REVIEW.json)，
维护检查见 [验证记录](PHASE1_REAL_W1_B2_VERIFICATION.json)。AI 工程自审不代替算法负责人或甲方签收。

## 1. 评审边界

B2-01～04 提供输入/失败支持域、请求结果 Schema、原始输出回读与正反例、参考独立性登记和正式适配器放行清单。
本次只校验已有输出和草案，不调用 predict.py，不改包/权重，也不注册科学 Worker。
DeepTMHMM 是序列级工具，A5 §2 明确不要求结构或 R-58 坐标映射，因此 B1 科学确认不是 B2 准备的前置条件。
B1 与 B2 分别满足自己的 G0/G1，不能互相借用资格。

总任务包 W1 只承接 N01–N02。FoldX、ProteinMPNN 的接口、编号约定和资产可提前准备，
实际工具验证及实现按 W5–W7 等所属波次开展；本次按用户决定修正 STATUS，未改变一期范围或后续门禁。

## 2. 原始事实与候选身份

权威依据为 A5 ToolSpec §1–7、SKILL R-05/R-48/R-58、SOP S-04/S-16/S-19/S-27 与 T-01、
Schema topology/in_outside_region、一期图和环境清单。完整来源及 hash 见
[source_manifest](../../../工作流设计/02-数据契约/phase1-real-v0.1/b2-review/source_manifest.json)。

软件候选仍为用户提供的 **DeepTMHMM 1.0 - Academic Version**，不是专家文档 v10.5，也不等同此前网页应用 1.0.57。
原 ZIP、41 个包文件、8 个模型资产和固定镜像已有本地登记；学术自用已确认，不重问用途。
开发 [profile](../../../工作流设计/02-数据契约/phase1-real-v0.1/b2-review/profile.json)从原 method_summary 引用版本、
参数及 hash：CPU、5 个 CV 模型、原科学默认参数，原 8 CPU/10 GiB/900 秒仅为既有运行配置。
目标服务器、实际资源和性能验收仍须登记；原源码线程策略不因本次准备而修改。

## 3. 输入支持域与失败行为

| 范围 | 已有证据或草案约定 | 验收边界 |
|---|---|---|
| 请求输入 | 每请求一条序列；由上游提供无空白的大写字符串和精确 SHA-256；B2 不重新规范化或截断 | 不接结构、任意命令或用户路径；宿主由上游保留，不作为 A5 模型参数 |
| AA20 | 官方示例和本地实际输入涵盖 50、51、96、97、173、307、375、471、991 aa | 这些离散样本不证明整个 50–991 区间，更不证明任意蛋白的准确率；AA20 为工程候选，完整生产生物学支持域仍须签收 |
| 非 AA20 | 一条 51 aa 人工 X 样本实际成功，X 原样保留 | 原始输出可保留，候选项目结果为输入复核；不把一次 X 成功推广到 B/J/O/U/Z 或所有 X 序列 |
| 空、非法或未规范化 | 空 FASTA 已实际退出 1、模型加载前拒绝；空记录/重复 ID/危险文件名问题另有源码依据与工程负测 | 草案拒绝空串、小写/空白、符号/非 ASCII，不默改输入；非法输入走 R-48 的 unreliable 与 failure WARNING |
| 短输入 | T-01 默认 <9 aa 在上游拦截；9/29/30 边界有人工契约检查 | 这是默认流程守卫，不是 DeepTMHMM 实测最短长度；短序列科学表现待验，不新增“9 aa 可准确预测”承诺 |
| 长输入 | 最大已测 991 aa；源码以 token 数切片，1022 与 300 为内部常量 | **1022 token 不是已验证的 1022 aa 上限**。>991 仅标为超出现有实测样本的复核提示；批准最大长度仍为 null。需实际记录 tokenizer 的端点与 token 数，并测 1020/1021/1022/1023 aa 等边界 |
| 安全 ID | 原包从 ID 生成概率文件名并使用 ID 字典；既有 `|` 文件名在 Windows 出现字符转换 | 正式单条封装使用 `t01seq_` 加完整序列 hash，原用户 ID 只作元数据；此策略已静态检查，尚未通过正式适配器执行验收 |
| 资源与执行 | 开发 CPU 原始推理和空输入已有证据；重复短样本两次标签一致 | GPU、长序列分块、并发、OOM/超时/取消/恢复和干净目标机安装均未由这批资料验收 |

输入字符串 Schema 允许携带坏输入以构造完整拒绝结果；语义检查决定对应复核/拒绝状态。
`input_findings` 是评审观察，>991 的提示不是科学阈值，也不会被写回专家输入域。

| 情况 | 结果/警告 | 保留与后续行为 |
|---|---|---|
| 四标签完整且输入位于候选语法域 | topology 为四枚举；parsed_unverified | 本评审仍固定不可消费、需评审，未授予生产资格 |
| 任意 P 或 B | topology=null、unreliable、PB_OUT_OF_DOMAIN、failure WARNING | 原始六标签串与区段等长完整保留；禁止自动交接，不映射成 inside/outside |
| A5 不可用 | topology=null、unreliable、TOOL_UNAVAILABLE，WARNING 命中“拓扑预测不可用” | 不直接 halt；各下游执行既有 null 守卫，R-48 的复核/交接限制仍保留 |
| 非法输入/未批准输入域 | topology=null、INVALID_INPUT 或 INPUT_REVIEW_REQUIRED | 不启动正式模型；历史 X 观察按回放证据保留，不能作为正式支持依据 |
| 空/部分/损坏输出、ID/序列/长度不符 | topology=null、INVALID_OUTPUT、unreliable、failure WARNING | 原文件和诊断保留，不补标签或仅发布幸存片段 |
| 工具失败/超时/取消 | topology=null，保留具体原因 | 生命周期仍由 A 管理；未确认进程停止不能发布 timed_out/cancelled，不从中复用“成功”拓扑 |

本次失败示例均明确标记 ENGINEERING_FIXTURE，只有原空 FASTA 拒绝是既有真实 G0 失败证据；
没有把超时/取消/不可用示例写成新模型实测。

## 4. 标签、区段、类型与空值契约

[请求/结果草案](../../../工作流设计/02-数据契约/phase1-real-v0.1/b2-review/README.md)绑定原请求字节、序列、profile、
run/job/attempt；回放结果额外绑定原输入、三行文件、区段表、执行记录和 method_summary。
历史 ID 原样配对，独立标为 HISTORICAL_ORIGINAL_ID，不伪称旧调用已经使用新的安全 ID。

原包 predicted_topologies.3line 为 `>ID | TYPE`、序列、标签三行；五类 TYPE 为 TM/SP+TM/SP/GLOB/BETA。
TMRs.gff3 实际是四个有效字段加四个尾空字段，并有长度/TMR 元数据，不能用通用九列 GFF3 猜列。
标签原生域 I/O/M/S/P/B，区段 1-based 闭区间、连续同标签完整聚合；概率 CSV 索引从 0 开始，不能混用坐标。
项目 has_signal 取 S 是否出现，tm_count 只数连续 M 段，outside_length 只数 O 残基；
原包 raw_tmr_count 同时计 M 和 B，另字段保留，不直接赋给项目 tm_count。

源码 tm_util.get_predicted_type_from_labels 只在出现 B 时选 BETA；仅含 P 的输出可显示为 GLOB。
所以 P/B 守卫直接检查逐位串，不能依赖 TYPE==BETA。与源码分类顺序不一致的类型/标签组合视为损坏输出。
所有原始概率文件与报告由原 manifest 保留；单条生成概率/图，旧批量不生成。
后续适配器须收集完整产物；现有概率检查只证明索引/AA/有限值/值域，不擅自批准概率和容差。

| 下游 | 正常消费 | topology=null 的接口责任 |
|---|---|---|
| S-16 / W3 | TMhelix/signal 复用为域；单 TM 大胞外域交叉核验 | 仅本地批准 UniProt 注释与正则，加 WARNING；不造拓扑域 |
| S-19 / W2 | 热点内任意 outside/signal → in_outside_region=true | 不传 topology_labels；未评估标为 null（Schema 可空），不把未知写成 false；完整三图流程由 W2 验证 |
| S-27 / W5 | 按原 topology_allowed 表达式 | 缺失拓扑本身不限制权限；不能因此清除 unreliable 或禁止自动交接标记 |
| 膜蛋白 Gate / W4、扫描 / W7 | 按 tm_count/outside_length 与 S-16 证据消费；单 TM 且 outside_length>50 是既有严格边界 | 不解引用 null，不把“无拓扑”解释为生物学上“非膜蛋白”；保留原 Gate 规则和复核状态，按所属波次联调 |
| S-05 | T-02 场景参考 | 默认保留/topology_exempted 不回流到当前 T-01 的 W1 节点 |

S-09 的 topology_reliable 是结构质量字段，不是 A5 的预测资格；两者分开。

## 5. 参考样本与验收条件

[参考登记](../../../discovery/t01-phase1-real/w1/b2-review-20260906/reference_inventory.json)将以下三类分开：

- **公开标注参考**：Q8K459、P01499、P07471、Q9HVD1 的原始三行片段、完整文件 hash、精确来源行、序列/标签 hash。
  覆盖 inside、signal、单 TM 大胞外域和 P/B，独立于本次解析代码；原始标注未被模型输出覆盖。
- **原模型回归资料**：9 条覆盖输入、重复短输入、人工 X；只用于包/解析/回连复核。官方示例未附独立预期标签，
  包内示例和相同实现的新输出也不构成金标准。
- **独立科学留出集**：当前尚无已签收样本。公开 3,576 条标注及历史 3,574 条四行交叉验证资料与训练的独立性未确定，
  不能用一致率给新安装版本签发准确率资格；四行资料的行角色也不能冒充运行时三行格式。

本次对四条公开标注和既有实际预测做逐位差异登记，结果为诊断性比较，没有设置科学通过阈值。
新增 [参考接收模板](../../../工作流设计/02-数据契约/phase1-real-v0.1/b2-review/reference_receipt.template.json)
要求来源/许可、原始序列与注释证据、坐标/版本、训练重叠核查、预声明指标/阈值、验收人及签收时间。
待补参考覆盖真实普通/信号/单跨膜/多跨膜、P/B、短序列、长度/token 边界和适用非常规残基。

工程验收要求精确一致：输入与标签等长、每位置恰覆盖一次、类型/区段/计数无矛盾、ID/hash 绑定、
P/B/null/失败不丢位置或冒充成功。科学验收另需具名负责人接受独立参考、训练泄漏评估、
逐残基/区段/类型指标及与下游边界相关的验收标准；数值阈值和样本数量不得由本校验器臆定。

## 6. 正式适配器的放行要求

机器清单见 [acceptance.json](../../../工作流设计/02-数据契约/phase1-real-v0.1/b2-review/acceptance.json)。

| 定点项 | 正式放行所需证据 | 主责 |
|---|---|---|
| B2-G1-INPUT | 批准 AA 字母表、实际接收域、短/长/token 边界及资源限制；区分源程序可接受与科学有效 | 算法 + 后端 |
| B2-G1-REFERENCE | 独立科学样本、来源/训练重叠核查、预声明指标与阈值、具名签收 | 算法验收 |
| B2-G1-RUNTIME | 具名目标环境、实际许可/包/模型 hash、候选版本参数、目标禁网复现 | 部署 |
| B2-G1-CONTRACT | 专用接口、P/B/null/部分失败、method_summary、下游交接责任签收 | 后端 + 算法 |
| B2-G2-ADAPTER | 前述适用评审放行后，实现安全单条封装、进程执行、原始产物校验、停止/恢复与不可变发布 | 后端 |
| B2-G3–G6 | 干净离线打包、N02 实际接入、适用波次验收与冻结 | 部署/测试/算法验收 |

本次工程通过允许继续定点准备和补证据，不放行 W1-09B2 的正式科学适配器。
B1 未完成的科学确认、C 类预测模型资产和后续 FoldX/ProteinMPNN 验证均不作为 B2 准备阻塞项。

## 7. 工程验证记录

[本轮维护检查](PHASE1_REAL_W1_B2_VERIFICATION.json)单独记录首次失败与修复后回归。
首次全量检查将封存的契约 README 副本按快照位置解析相对链接，产生三项导航误报；
现行检查器只对明确登记且与来源/产物两份清单字节数、SHA-256 一致的该副本按证据处理，
现行原文及邻近文档继续检查。旧 manifest 和快照均保持原字节，修复前后源码另存维护证据。
