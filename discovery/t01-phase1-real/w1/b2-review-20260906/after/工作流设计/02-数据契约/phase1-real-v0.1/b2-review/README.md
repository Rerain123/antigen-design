# B2 DeepTMHMM 请求/结果评审草案

本目录补充 W1-07 的专用科学 payload 草案，工具名沿用 t01.real.deeptmhmm。
适用 [W1-08B2 评审](../../../../docs/project/phase1/PHASE1_REAL_W1_B2_REVIEW.md)，进度见 [STATUS](../../../../docs/project/STATUS.md)。
不修改原 CandidateRecord Schema，不注册运行层 Worker；DRAFT_REVIEW_ONLY 不能直接当生产契约。

## 文件责任

| 文件 | 用途 |
|---|---|
| [request.schema.json](request.schema.json) | 单序列、原 ID/安全内部 ID、精确输入与候选 profile 引用 |
| [result.schema.json](result.schema.json) | 运行观察、原始六标签事实、四标签 topology 或 null、失败原因、复核与执行绑定 |
| [profile.json](profile.json) | Academic 原包/模型/镜像/参数、已测离散长度、候选输入政策和未批准范围 |
| [source_manifest.json](source_manifest.json) | 专家、用户决定、原始源码和执行证据的只读 hash |
| [example_pairs.json](example_pairs.json) | 手工请求/结果案例及文件 hash；不是实际模型任务 |
| [acceptance.json](acceptance.json) | 工程断言、参考和正式适配器的分项放行条件 |
| [reference_receipt.template.json](reference_receipt.template.json) | 独立科学参考接收模板；空字段表示尚无签收 |

## 请求

protein_sequence 由上游完成规范化；本检查器不转大写、删空白、删非法位点、替换残基或静默截短。
字段允许传递坏输入以核验拒绝语义，不表示模型接受任意字符串。
protein_sequence_sha256 是精确 UTF-8 序列 hash；internal_sequence_id 必须等于 `t01seq_` 加该完整 hash，
user_sequence_id 仅为展示/追溯文本，不能拼文件路径或命令。每请求单条、每 attempt 独立目录，原包批量覆盖能力不扩大生产接口。
profile_id 与 profile_sha256 绑定本目录候选；无用户可覆盖科学参数、源码命令、结构或远程 URL 参数。

<9 aa 对应 T-01 默认上游守卫；AA20 是工程候选，X 的单例成功仍进入输入复核。
>991 提示超出现有样本，**不是工具最大长度**；approved_minimum_aa/approved_maximum_aa 均未批准。

## 结果与空值

结果分别描述 execution_observation 和 interpretation_status。
completed 仅是原始进程有完整可核验输出，不代表科学批准；parsed_unverified 也不使 usable_for_pipeline 为 true。
运行层 queued/running/stop_requested/reconciling 等仍由通用 A 协议承接，正式 timed_out/cancelled 要在实际停止确认后发布。

raw_record 保存完整序列、原 ID、五类 TYPE、六类标签串、原始区段及 raw_tmr_count。
项目 topology.labels 仅 inside/outside/TMhelix/signal；segments 为 1-based 闭区间连续段。
has_signal 依据 S，tm_count 只计连续 M 段，outside_length 只数 O；原包 M+B 的 raw_tmr_count 独立保留。
任何 P/B 都使 topology=null、PB_OUT_OF_DOMAIN、unreliable、failure WARNING 并禁止自动交接。
仅含 P 也可能显示 GLOB；不能只检查 TYPE。原值保留在 raw_record，不塞入四枚举字段或缩短数组。

null_reason 明确区分 INVALID_INPUT、INPUT_REVIEW_REQUIRED、PB_OUT_OF_DOMAIN、TOOL_UNAVAILABLE、
INVALID_OUTPUT、TOOL_FAILED、TIMED_OUT、CANCELLED。不可用警告含“拓扑预测不可用”；
各消费点继续其 null 守卫，不用全 outside/inside 或零计数伪造正常对象。
所有草案固定 requires_review=true、automatic_handoff=false、usable_for_pipeline=false、scientific_signoff=null。
完整生产批准后的正常可消费状态需另经 B2 G1/G2 建立，不通过删除这些常量直接升级本草案。

binding 含 run/request/job/attempt 及请求字节、序列、profile hash。此处身份均为 LOCAL_REVIEW_NOT_RUNTIME_ISSUED。
G0_RAW_REPLAY 额外引用原 FASTA、三行输出、区段表、执行记录和 method_summary 的精确路径/hash/大小，
并用 HISTORICAL_ORIGINAL_ID 配对；原始旧 ID 不被重写成新安全 ID，也不冒称已验证安全 ID 的实际调用。
ENGINEERING_FIXTURE 保持人工案例身份。原概率 CSV/图/报告由旧产物 manifest 保护，后续正式封装须完整收集；
草案未生成“项目概率”或设置概率和的科学容差。

## 校验

[b2_review_contract.py](../../../../scripts/b2_review_contract.py)检查 Schema 之外的序列、区段、计数、P/B/null 和输入绑定；
[check_w1_b2_review.py](../../../../scripts/check_w1_b2_review.py)校验预声明案例、实际输出回读和参考来源。
仅能重读本地资料；不执行模型、不改原包、不联网回退。精确命令集中在 [运行手册](../../../../docs/development/RUNBOOK.md)。
