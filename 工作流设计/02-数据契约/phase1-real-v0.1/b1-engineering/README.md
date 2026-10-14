# B1 输入事实工程扩展

本目录承接 [B1 前置工程补强](../../../../docs/project/phase1/PHASE1_REAL_W1_B1_ENGINEERING_BACKLOG.md)。
这是独立 `0.1.0 / DRAFT_ENGINEERING_EXTENSION`，保留 [B1 原请求/结果草案](../b1-review/README.md)及其旧 hash。
它没有注册成正式 ingest_structure/map_structure 的 Worker，也没有变更 A 运行层协议。

输入直接校验 B1 原 ingest 请求 Schema；本地 CLI 显式接收该请求文件和结构文件，并核对结构 ArtifactRef 的字节与 hash。
请求中的序列、host_species、声明格式、MODEL/作者链选择及来源声明保持原值。
精确请求字节与原结构字节分别保存在新目录，文件名后缀不参与格式检测。

| 文件 | 语义 |
|---|---|
| request.json、input.structure | 原始输入字节；原请求中带规范化序列及独立序列 hash |
| preflight.json | 实际格式、声明/内容核对、所有 MODEL/链、AUTO 候选、选择诊断及摄取观察 |
| raw_metadata.json | 字段原名、原值、词法形式、来源位置、缺失/多值/差异/不可解析诊断 |
| raw_addresses.json | 每条原子记录的作者与 label 字段、完整残基身份、消费者字段可表示性 |
| result.json | [结果扩展 Schema](result.schema.json)，绑定请求/结构/序列及三份独立事实 ArtifactRef |
| artifacts.json | 本地 ArtifactRef 到固定文件名的清单、hash 和采集时间 |

配对实例与字节来源见 [独立批次](../../../../discovery/t01-phase1-real/w1/b1-engineering-20260905/README.md)。
文件身份声明为 LOCAL_PROBE_NOT_RUNTIME_ISSUED；所有事实产物标记 ENGINEERING_FIXTURE、不可科学消费。
这里的 job/attempt 仅用于开发证据配对，不是 A 服务签发的任务。

## 预检状态与错误

`ready_for_review` 只表示在本探针支持域内记录完成。`rejected` 保留三份诊断 Artifact，
但 ingestion_observation=null；它们不是旧 B1 result.output_artifact 的正常 inventory 或 mapping。

| error_code | 适用情况 |
|---|---|
| FORMAT_MISMATCH | 可检测内容与 PDB/CIF/MMCIF 声明不符；仍按实际格式保存可提取事实 |
| INPUT_UNSUPPORTED | 压缩/二进制、非 UTF-8、URL/不可识别内容、多 data block、save frame、CIF 2.0、缺作者字段或当前不支持的数值/编号方言 |
| PARSE_FAILED | 空文件、损坏 CIF 语法/loop、重复字段/原子、非法或非有限坐标、PDB 截断/损坏 MODEL 边界 |
| SELECTION_REQUIRED | 多 MODEL 未明确选择 0-based model_index |
| SELECTION_NOT_FOUND | 请求 MODEL 索引或作者链不存在；label 链不自动替代作者链 |
| SELECTION_NOT_PROTEIN | 所选 MODEL 没有蛋白链，或指定链为非蛋白 |

`error_code` 是首个主因，完整 diagnostics 保留其他发现。AUTO 按文件顺序选首个蛋白链并报告全部候选；
选择仅是摄取观察，不执行输入序列的设计链比对。显式链失败不回退 AUTO。
蛋白分类沿用既有探针 AA/is_aa/ATOM 非核酸观察，未知残基单字母为 null；这不是生产字母表批准。

## 原值与消费者边界

来源 location 使用原 UTF-8 解码文本的 0-based 字符区间 `[start,end)` 和 1-based line/column；
保留 BOM、CRLF 和字段引号，结构 SHA-256 始终基于原始字节。raw_value 可以直接从原文区间复核。
CIF 标记 `?`、`.`、字段缺失分别记 unknown/not_applicable/absent；带引号的问号和点仍是字面值。
PDB 定宽字段保留原切片，空白链保留一个空格，不被裁成空字符串。

作者身份保留 auth_seq_id 字符串和独立 iCode；完整清单还保留 MODEL、label/auth 链、label 位置/实体、
残基原名、记录类别及每条原子出处。`43A` 和 `43 + A` 是两条不同身份；不输出重编号结构。

integer_mapping_v0_1 检查当前整数地址的保守无损投影；pdb_fixed_columns 另检查链字符及 resSeq/iCode 列宽；
foldx_position_token 再阻断含 iCode 的地址。任一投影碰撞均显式阻断。
前导零、字符型编号、超出可互操作整数范围和未知 iCode 不做有损强制转换。
未知 `?` iCode 与无插入码的空串不同：本扩展保守阻断前者；旧探针对 `?` 的历史处理保持原样。
字段可表示只说明该局部格式检查通过，完整转换、原子身份、工具实测与科学 G1 仍分别验收。

PDB EXPDTA/REMARK/SOURCE/COMPND 完整行始终留存；解析出可识别字段，无法归并的续行明确标诊断。
mmCIF 保存 method、refine/reflns/EM resolution、自然/工程/合成来源和相关实体/模型上下文。
多实验/多实体字段值不同只提示待审差异，不挑值、不平均、不判断哪一个为真。
source_declaration 与这些字段同时可见，来源、pLDDT、缺原子比例仍为 null；不计算 S-09。

## 与原 B1 草案的差异

1. 请求不变；输出增加三份事实 Artifact 及独立开发身份，tool_id 为 t01.dev.structure_input_facts。
2. 拒绝时可以保存诊断事实，不改变原 B1 “失败无正常 output_artifact”的规定。
3. 新增 SELECTION_NOT_PROTEIN，尚未映射为 A 的任务错误或科学状态。
4. 字符地址事实不符合旧整数 inventory/mapping 的类型，不能传给 map_structure 冒充其 inventory_artifact。
5. 完整 B1 的科学来源、缺原子比例、比对/构象选择、verified 与消费者许可继续等待相应评审。

正式适配前需要按 B1 的 G1 决定收敛支持域和结果错误桥接，不能仅改 contract_status 消除资格守卫。
只读校验与新批次命令见 [运行手册](../../../../docs/development/RUNBOOK.md#b1-输入事实工程补强)。
