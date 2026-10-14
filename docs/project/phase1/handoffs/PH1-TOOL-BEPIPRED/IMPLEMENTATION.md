# BepiPred 实现说明

本文件按“先跑原工具，再确认规则和接口，最后封装”组织。
JSON、run_tool.py、状态与错误统一使用 [公共接口 v0.1](interface/README.md)。工程约定已统一；完整生产 G1 及 OI-026 科学规则仍需评审。
科学依据和官方资料见 [原件索引](references/README.md)。

## 1. 获取代码，建立隔离环境

工具使用 BepiPred 3.0。从 [作者仓库](https://github.com/UberClifford/BepiPred-3.0)取得代码，
记录具体 commit/版本、来源和代码包 hash；工具名相同不表示不同提交的输出格式相同。

主开发确认目标 OS、Python、CPU/GPU 与安装位置后，在独立环境按选定提交的 README 和
requirements.txt 安装。选定环境要能复现，不能靠修改主项目环境解决依赖冲突。

准备记录至少包括代码 commit、Python、torch、fair-esm、依赖清单、推理设备及相关驱动信息。
软件和模型使用条件先交主开发核对，仓库中保留非秘密的来源记录，不写凭据。

作者仓库说明初次运行可能下载 ESM-2 权重，原始输出同时包含概率分数、滚动平均分数及不同候选文件。
因此有网准备期要把所需权重、模型文件和缓存逐项记清，运行期验证完整断网可用；不能只复制 Python 源码。
本段工具行为来源：[作者 README](https://github.com/UberClifford/BepiPred-3.0)。

## 2. 第一次用原工具运行

先保存选定版本的 help：

```bash
python bepipred3_CLI.py -h
```

下面是原工具的调用示例，应在工具源码目录、依赖和权重准备后执行。
把 input.fasta 换成已获准的样本路径：

```bash
python bepipred3_CLI.py -i input.fasta -o output -pred vt_pred -t 0.1512 -top 20
```

命令依据作者 README；执行前与本次选定 commit 的 help 核对。它只是原工具 G0 实测入口，
不代表项目已经决定所有分数列、Top20% 或峰合并语义。
本地权重参数/加载方法以所选版本代码和 help 为准，不猜不存在的参数名。

第一次回传应包含：

- 输入 FASTA 原件与 hash、代码/依赖/模型身份、命令、退出码、耗时和资源。
- 原始 CSV 的完整表头与样例行；原始 FASTA 与其他生成文件。
- 实际输出的序列 ID、残基字母、位置基址、概率分数和滚动平均分数的列映射表。
- 权重来源、文件 hash、缓存位置及离线加载办法；缺任何模型文件时的真实行为。

离线验证时，使用独立受限进程/容器或测试环境，不关闭共享服务器的网络。
记录断网方式和外联观察；运行成功本身不能证明没有网络依赖。

## 3. 输入和参数

本次适配器先支持单条序列。精确格式见 [请求 Schema](interface/request.schema.json)和
[公共字段说明](interface/README.md#3-请求怎么填)，不再另设一套接口草案。

输入放 inputs.sequence；parameters 含 threshold（默认 0.1512、范围 0.10–0.20）、
top_percent=20、min_peak_length=6、gap_tolerance=2、relaxation_metadata（默认 null，调整阈值时必填）。
rule_profile 在规则未确认时为 null；确认后由主开发提供 id、version、sha256。
输出目录只由 --output-dir 指定，不再放入请求 JSON。

其他可调参数按来源及评审结果处理，不自行扩大支持范围。
非标准字母、超长/超短输入的支持与错误行为先实测记录，再由主开发落实生产输入规则。
本次不是整个 T-01 入口，不要求你增加宿主选择、结构预测或全链短肽门控。

一期只做线性 B 细胞预测，本工具请求不接收 structure 字段。
按原文记录“仅线性B细胞表位预测”，不产生构象预测或 bcell E2 共识结果。

## 4. 解析逐残基结果

按所选版本的真实列名编写解析器，避免按固定列序号读取。

1. 对照输入序列 ID，确保读到本次输入的结果；不能混入另一个样本或上次运行文件。
2. 保存原始位置与残基字母，显式转换为项目的 1-based 位置。
3. 校验每个位置只有一个结果，范围为 1 到序列长度；残基字母与输入逐位相符。
4. 保留原始概率和滚动平均等实际存在的分数列；禁止把 FASTA 大小写标签当作数值分数。
5. 检查缺行、重复行、非法数字、NaN/Infinity、长度不符和字段缺失；不补 0、不复制相邻值。
6. 主开发确认 BP-D02 后，将指定列按序放入 linear_scores；数组第 0 项对应位置 1。
7. 分数的值域、容差和解析兼容版本以实际输出与验收约定记录；不凭观察随意缩放。

S-19 的跨来源合成、min-max 归一化、E 级与 IEDB 区间关联由主开发处理。
同事交回本步骤的原始分数和峰，避免在这里重复归一化或推断实验表位类型。

## 5. 峰提取：已有规则和待确认细节

原件已明确：

- 默认阈值是 0.1512，峰判定写的是 score > 0.1512，等于阈值不算超过。
- min_peak_length=6，gap_tolerance=2，可桥接不超过 2 个非表位残基。
- linear_peaks 的每项包含 start、end、mean_score。
- 另有“阈值 + Top20%”要求，必须保留它的来源和工具输出。

在 BP-D02 确认前，不把这几句话自行拼成一个最终算法。给主开发提交下表中的具体案例，
由其协调算法负责人形成可执行的规则表：

| BP-D02 子项 | 已有事实 | 需要确定的唯一问题 |
|---|---|---|
| 输入分数列 | 官方输出提供概率和滚动平均；项目原文写 linear_scores | 哪一列进入 linear_scores 和峰提取，是否使用平滑及其参数 |
| Top20% | 官方有独立 Top 候选输出；项目写阈值+Top20% | 项目如何消费两个结果；并列/取整按哪个已核验工具行为或明确规则处理 |
| 合并顺序 | 峰长度默认 6，桥接间隔默认 2 | 先过滤短段再合并，还是先合并再过滤；间隔是否计入有效长度 |
| 区间均值 | 输出要求 mean_score | 桥接位置是否计入均值；使用何种已确认分数列 |

例如“3 个高分 + 2 个低分 + 3 个高分”在不同合并顺序下会得到不同结果；
这是需交回的定点问题，不能偷偷选一种让测试通过。
案例文件见 [待确认用例](examples/rule_questions.json)，全局跟踪为 OI-026。

可先写原始解析和通用计算测试；规则确认后把判定表固化为测试。
未经确认时，工具运行结果可保留，linear_peaks 不得用空数组伪装“没有峰”，
也不能设置为可供主流程消费。工程输出应区分“原工具成功”和“项目后处理尚未完成”。

## 6. 输出、异常与可追溯性

适配器输出使用 [结果 Schema](interface/result.schema.json)与
[状态/错误/退出码表](interface/README.md#5-状态错误和退出码)。工具专用 result 只含 linear_scores、linear_peaks。
可对照 [规则待确认](interface/examples/bepipred-rules-pending/output/result.json)、
[人工成功形状](interface/examples/bepipred-success-shape/output/result.json)、
[错误终态](interface/examples/bepipred-failed/output/result.json)。这些示例均非真实模型结果。

原始 CSV/FASTA 和已解析的诊断数据留在 raw/，即使 result=null 也不丢证据。
不输出伪造的 conf_scores、conf_peaks 或实验表位类型。
确认后确实没有峰才返回 linear_peaks=[]；“没有峰”本身不是工具失败。

| 情况 | 要求 |
|---|---|
| BepiPred 不可用、模型缺失、命令失败 | failed，明确终止本次预测；上层按 S-17 halt 处理，不伪装空结果继续 |
| CSV 缺失/损坏、长度或坐标不符 | failed，指出差异；保留原始输出 |
| BP-D02 或其他适用规则未确认 | 可保留成功的原工具事实，result=null、usable_for_pipeline=false、review_required=true |
| 无峰但预测与后处理正常 | 成功，空峰数组；保留分数、参数与常态线性预测说明 |
| 超时/取消 | 停止实际子进程并记录原因；不重用旧目录结果、不静默联网回退 |

生产队列、幂等和重启恢复由主开发集成；你提供可以被控制、不会孤留进程的独立调用入口。

## 7. 评审后需要交付的入口

适用 G1 放行后实现：

```bash
python run_tool.py --input request.json --output-dir results/run-001
```

这是待开发的入口，本包不含 run_tool.py。示例请求见 [request.example.json](examples/request.example.json)。
先交原工具事实、列映射和规则问题；主开发完成适用 G1 后，再提交可复现的完整适配器。
源码建议分为调用、解析、峰提取、命令行四部分，测试可以分别运行。

离线交付应说明依赖包、代码、模型和缓存怎样转移到相同目标环境，如何在空结果目录重跑；
不要只写“在我电脑上能跑”。完成标准见 [验收清单](ACCEPTANCE.md)。
