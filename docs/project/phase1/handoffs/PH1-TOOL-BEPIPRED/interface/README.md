# 两个工具共用的接口 v0.1

先照本页准备输入和输出，再按各自实现说明处理科学数据。
FreeSASA、BepiPred 共用调用方式、状态、错误、文件引用和版本记录；工具内部计算各自实现。

本版是主开发确定的**工程接口约定**，协议字段 `contract_version=0.1.0`。
它完成首批同事对接所需的公共部分，完整生产 G1、结构映射实现和科学规则仍按项目任务评审。
包内示例全是人工数据，没有执行科学工具，也没有已批准的生产规则 profile。

## 1. 同事先做这三步

1. 运行 `python validate.py --examples`，确认能看到 PASS。这只校验格式与人工文件哈希。
2. 找到自己工具的 [请求与结果示例](examples/README.md)，按字段填写请求。不要再使用旧的顶层 sequence、output_dir 等草案字段。
3. 适用 G1 放行后，实现下面的 `run_tool.py`；它需要调用真实工具，本资料包只提供校验器。

校验器需要 Python 3.11 和 jsonschema 4.x；项目根环境已有依赖。
独立环境可在获准的准备环境安装 `jsonschema>=4.23,<5` 并锁定版本；目标内网用本地依赖包安装。
校验器不安装依赖、不下载 schema、不调用科学工具。

## 2. 固定调用与文件位置

```bash
python run_tool.py --input request.json --output-dir results/attempt-001
python validate.py --request request.json --result results/attempt-001/result.json --check-files
```

- `--input`、`--output-dir` 是包装器命令行参数；输出目录只由命令行提供，请求中不再重复。
- 一次调用只处理一条规范化序列。`request_id` 由调用方提供，重试相同逻辑请求保留此 ID；每次实际调用由适配器生成新的 `attempt_id`。
- `request_id`、`attempt_id` 只作标识，不直接拼成不受检查的路径。同一个 request_id 内容变更必须由主开发的调度层拒绝。
- 输出目录必须全新创建；已存在就拒绝，不能覆盖、清空或读取旧结果。退出码不能代替 result.json 内的状态检查。
- 输入文件路径相对 request.json 所在目录；产物路径相对 result.json 所在的输出目录。统一用 `/`，不接收绝对路径、URL、`..`、反斜杠或冒号。输入由调用方事先落盘到本批目录。
- 包装器先把完整结果写临时文件，再原子改名为 result.json。raw/ 保存原始输出，日志去除凭据；result.json 不引用自己的哈希。
- 超时或取消须停止实际子进程并收集证据。单次包装器只返回终态；队列、运行中状态、幂等存储、跨进程取消和重启恢复属于主开发后续 W1-07/G2。

## 3. 请求怎么填

精确机器字段见 [request.schema.json](request.schema.json)。对象不接受未声明字段，JSON 禁止重复键、NaN、Infinity。

| 字段 | 谁填、怎么填 |
|---|---|
| contract_version | 固定 `0.1.0`；不支持的版本拒绝，不按相近版本猜解析 |
| tool_id | FreeSASA 为 `t01.real.freesasa`；BepiPred 为 `t01.real.bepipred`；与冻结 Mock 命名独立 |
| request_id | 调用方提供，1–128 个字母、数字、点、下划线或连字符，首位是字母/数字 |
| run_mode | `engineering_example` 人工接口测试；`g0_probe` 原工具事实记录；`pipeline` 已获适用放行的正式调用。前两类永远不能设置 usable_for_pipeline=true |
| node_id | FreeSASA：N02 或 N13；BepiPred：N04。N02 的 low 跳过条件不能自动移植到 N13 |
| inputs.sequence | 上游已规范化的大写 A–Z，无空格/换行且非空；这是传输语法，生物学支持集和长短边界仍按各工具与 OI-023 验收 |
| rule_profile | 未确认填 null；确认后填 `{id, version, sha256}`，引用主开发登记的规则文件。仅填这些字段不构成算法批准证据 |
| inputs / parameters | 下表的工具专用字段；不能把未确认规则塞进任意扩展字典 |

FreeSASA：

| 字段 | 约定 |
|---|---|
| inputs.structure / inputs.mapping | null 或 `{path, sha256}`。sha256 是文件原始字节的 64 位小写十六进制指纹；准备阶段尚未取得文件/指纹允许 null，不能冒充已校验 |
| inputs.mapping_status | `unverified` 尚未核验、`verified` 已按 R-58 核验、`unreliable` 失败/歧义；调用方负责真实性，工具仍需验证映射与文件、序列的绑定 |
| inputs.quality_confidence | 上游 S-09 给出的 high/medium/low，工具不重新分档 |
| parameters.config | null 或 `{path, sha256}`，引用具体算法、探针/半径表、精度、线程和链/MODEL/原子选项配置；参数文件内容需 G0/G1 确认，本版不猜默认值 |

FreeSASA 的 pipeline 计算要求结构、映射、配置都有 hash，映射为 verified，并有规则 profile。
N02 quality=low 只返回跳过记录，可不提供上述计算资产；这不表示整个 N02 已完成。
映射文件字段与校验器见 [R-58 映射规范](structure_mapping/README.md)。FreeSASA 包内 mapping.example.json 已符合此格式，但仍为人工 unverified 示例；真实映射的结构核验与适用评审由主开发完成。

BepiPred：

| 字段 | 约定 |
|---|---|
| parameters.threshold | 默认 0.1512，允许 0.10–0.20；原文比较是严格大于，具体峰算法等 OI-026 |
| parameters.top_percent | 本版固定 20；如何消费 Top 输出待 OI-026，不据此实现新的筛选组合 |
| parameters.min_peak_length / gap_tolerance | 本版分别为 6、2；合并顺序及区间均值仍待确认 |
| parameters.relaxation_metadata | 默认 null；改变 threshold 时必须填写 `{reason, decision_ref}`，其批准依据由主开发核验 |

## 4. 结果怎么填

精确机器字段见 [result.schema.json](result.schema.json)。必填字段不能省略；缺科学结果写 null，不能用 0 或 [] 代替未完成。

| 字段 | 约定 |
|---|---|
| contract_version / tool_id / request_id / run_mode | 原样对应本次请求 |
| attempt_id | 本次执行的唯一标识，重试必须新建 |
| execution_status | succeeded 原工具与本次已执行步骤完成；failed 本次失败；skipped 仅限 FreeSASA N02 quality=low |
| usable_for_pipeline | 只有 pipeline、成功、有已确认结果、无待复核项且实际通过输入/映射/规则检查时才可为 true |
| review_required | 科学规则待确认、映射不可靠、未知残基或数值待处置时为 true，同时 usable_for_pipeline=false |
| result | 正常结构见下表；失败、跳过、后处理规则未确认或映射未核验时为 null；原始数据进 artifacts |
| issues | 每条含 code、severity、message；涉及位置时加 positions（1-based、唯一、不超序列长度） |
| artifacts | 原始文件、诊断、日志、环境记录的引用，包含 artifact_id、role、path、media_type、sha256、size_bytes |
| provenance | 适配器/原工具版本、请求与参数指纹、规则版本、UTC 时间、实际命令与原工具退出码、环境产物引用 |

| 工具 result | 结构约束 |
|---|---|
| FreeSASA | `{per_residue: [number 或 null], buried_fraction: number}`；数组与序列等长，数值范围 [0,1]。每个 null 必须有带位置的 MISSING_RESIDUE 或 UNSUPPORTED_RESIDUE；出域原值存诊断，result=null 并复核，不裁剪 |
| BepiPred | `{linear_scores: [number], linear_peaks: [{start, end, mean_score}]}`；分数等长且有限，区间为 1-based 闭区间、递增、不重叠、不超界。Schema 不自设分数归一化、峰长度算法或桥接均值 |

只有后处理完成且确实没有峰时才返回 `linear_peaks=[]`。本版人工成功形状示例也不是 OI-026 的裁决。
FreeSASA 数组是内部步骤输出，不给最终 CandidateRecord 新增顶层 RSA 字段；BepiPred 不增加构象结果。

## 5. 状态、错误和退出码

| 情况 | result.json 状态及处理 | 包装器退出码 |
|---|---|---|
| 已成功计算；或仅原工具成功但规则待确认 | succeeded；后者 result=null、review_required=true，并写 RULES_PENDING | 0 |
| FreeSASA N02 quality=low | skipped、QUALITY_LOW（info）、result=null；未调用原工具 | 2 |
| 输入字段/格式不合法 | failed、INVALID_INPUT（error） | 10 |
| 文件/模型缺失，或输入 hash 不符 | failed、ASSET_MISSING / HASH_MISMATCH（error） | 11 |
| 原工具失败 | failed、TOOL_FAILED（error），provenance.tool_exit_code 记原退出码 | 12 |
| 输出解析、坐标或数值不合法 | failed、OUTPUT_INVALID（error） | 13 |
| 超时 / 取消 | failed、TIMEOUT / CANCELLED（error）；回收子进程 | 14 / 15 |
| 结果目录已存在或无法落盘 | 拒绝执行或停止；stderr 说明，无完整 result.json 就视为失败 | 20 |

其他已固定的 warning 码：RULES_PENDING、MAPPING_UNVERIFIED、MAPPING_UNRELIABLE、
MISSING_RESIDUE、UNSUPPORTED_RESIDUE、VALUE_OUT_OF_RANGE、REVIEW_REQUIRED。
MISSING_RESIDUE 不自动意味着映射不可靠；是否复核按已确认处置表。其余复核码必须 review_required=true。
failed 必须至少有一条 error；succeeded/skipped 不允许 error。详细原工具错误写 message 和日志，不自创公共错误码。

以上是待实现包装器的退出码。**校验器**退出码另为 0=检查通过、1=数据/文件不符合约定、2=命令参数错误。
对非法 JSON、缺 request_id 等无法关联的输入，包装器以 10 退出并保留诊断，不虚构正常请求身份；
拿到可关联请求后才生成标准失败 envelope。输入本身无效时，不能要求请求/结果成对校验通过。

## 6. 指纹与版本记录

- 请求指纹：request.json 原始 UTF-8 文件字节的 SHA-256。文件只改空格也会变化；发起后保持输入不可变。
- 参数指纹：`json.dumps(parameters, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)` 的 UTF-8 字节 SHA-256；校验器提供 parameters_hash。其他语言对接须先通过同一测试向量，不自行换规范化方式。
- 序列指纹（映射/样本记录使用）：规范化 sequence 的 UTF-8 字节，无 FASTA 头和换行。结构、配置、映射、产物均按各自原始文件字节计算。
- rule_profile 是规则文件的身份与 hash；provenance 必须与请求一致。适配器的输入检查还须对照主开发的已批准登记，文件 hash 相符本身不证明科学规则已批准。
- adapter_version 记本次实现版本/commit，tool_version 记真实工具版本/commit。不得填 latest 或把包装器版本当模型版本。
- environment_artifact_id 引用 role=environment 的本地 JSON/清单，记录 OS、Python、依赖锁文件、CPU/GPU/驱动、软件/模型/缓存/配置的来源版本和 hash、运行资源。模型清单的具体内容在逐工具 G0 锁定；公共校验器只核验文件身份，不替代环境验收。
- started_at/finished_at 使用 RFC3339 带时区时间，建议 UTC `Z`；后者不能早于前者。command 用参数数组，不能拼接含密钥的 shell 字符串。
- 工具成功必须有 raw 和 environment 产物；失败尽量保留已生成证据。artifact_id、产物路径不重复，大小和 hash 以最终文件为准。

协议版本、工具版本、规则版本、环境身份分别记录，不使用一个 v0.1 代替所有版本。
新增工具需要登记 tool_id、请求/结果子 Schema、对应来源和测试，不能把它当成现有工具的任意 payload。

## 7. 校验能证明什么

`--request` 检查请求；加 `--result` 检查双方身份、状态、数组长度、坐标和 provenance 一致性；
再加 `--check-files` 核验实际输入/产物的字节、大小、路径边界和 hash；FreeSASA 提供 mapping 时还核对其字段、序列、结构 hash 与映射状态。实际残基地址由主开发另行重解析核验。默认格式检查不会打开外部资产。
`--examples` 会检查本目录全部人工示例和实际教学文件，不使用网络。

PASS 仅表示本次检查范围符合工程约定，不能证明模型跑过、映射正确、科学结果可信或 G1 获批。
消费者还必须核验环境、已批准 profile、真实样本验收和适用门禁，不能仅相信 usable_for_pipeline 布尔值。
本版未实现科学适配器、R-58 比对器、Dify/MCP 服务或生产调度层。

来源定位：FreeSASA ToolSpec §2/2b/3/4、SOP S-11、SKILL R-58/R-48；BepiPred ToolSpec §2/3、
SOP S-17、SKILL R-16/R-48、最终 Schema 的 bcell 字段。科学细节见各任务包 references 原件索引。
工程字段/退出码由主开发在本次“统一工具接口”任务中确定；OI-015/023/024/026 不因接口检查通过而关闭。
