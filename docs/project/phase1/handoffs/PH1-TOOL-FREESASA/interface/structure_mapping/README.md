# R-58 结构映射格式 v0.1

这份表回答一个问题：输入序列第几个位置，对应结构中的哪个残基。
例如输入 ARG，结构只保留 A 和 G，编号分别是 42 和 42A，映射中间位置必须为 null；
42 与 42A 是不同残基，不能合并，也不能把 G 向前移动。

机器格式见 [mapping.schema.json](mapping.schema.json)，独立检查器为 [validate_mapping.py](validate_mapping.py)。
它随公共接口复制到两个任务包，工程字段在此统一维护。

## 1. 文件内容

| 字段 | 含义 |
|---|---|
| mapping_version / artifact_type | `0.1.0` / `t01.real.structure_mapping` |
| evidence_kind | synthetic_fixture 为人工用例；local_input 为本地真实文件，不等于甲方样本或金标准 |
| sequence / sequence_sha256 | 规范化序列与 UTF-8 无换行 SHA-256 |
| structure_sha256 / format | 结构原始文件指纹；pdb 或 mmcif，不通过转换覆盖原件 |
| model_index / model_serial | 本次选择的 0-based MODEL 索引和原始 MODEL 编号；原文件未声明编号则 serial=null |
| selection | 原始请求中的 MODEL 索引与摄取链；未指定为 null，供原样重解析核验，不从最终结果倒推选择 |
| ingestion_chain_id | 摄取链；AUTO 取第一条蛋白链，只用于记录摄取事实 |
| target_chain_id / fixed_chain_ids | 已生成候选映射的目标链及其余保持不变的链。存在多个可能目标时，target=null，不能擅自把其他候选链标为 fixed |
| entries | 与序列等长，每项含 sequence_position（1-based）、sequence_residue、structure_residue、reason |
| structure_residue | null 或 `{chain_id,res_seq,insertion_code,hetero_flag,residue_name}`；编号允许负数，空插入码用空字符串，PDB 空白链保留一个空格 |
| reason | mapped / missing_structure_residue / unresolved_mapping。歧义未解决不能声称具体位置确定缺失 |
| chain_candidates | 每条蛋白链的观察序列、候选状态与位置；用于复核，不作为已批准的设计链 |
| parser / method / producer_version | 解析器及版本、编号体系、候选方法与程序版本；不借用 Mock 身份 |
| issues / review | 具体问题；未复核时 review=null，已复核需记录人员、时间、决定引用及 R58_MAPPING_ONLY 范围 |

mmCIF 使用 auth_asym_id、auth_seq_id 和独立 iCode，不把 label 编号当作者编号。
完整观察值、label/auth 对照、原子名、altloc、非蛋白组分和所有 MODEL 在主开发输出的 structure_inventory.json 中保留。
映射表自身不包含原子坐标或结构质量分档，原坐标由 structure_sha256 绑定原文件。

## 2. 三种状态

| 状态 | 含义与消费边界 |
|---|---|
| unverified | 已有可检查的候选对照表，仍需适用核验；review_required=true、usable_for_pipeline=false |
| unreliable | 尚无唯一/支持的映射，目标链为空、entries 地址均为 null，禁止自动交接 |
| verified | 完成独立结构/序列核验与所引用的适用评审后，由主开发登记；必须有 review，不能保留未解决的阻断项；人工用例不得使用此状态 |

当前探测程序只产生 unverified 或 unreliable，不能通过命令行参数签发 verified。
Schema 接受 verified 的格式，并不验证人员身份或评审内容；调用方仍须核实决定引用、G1 和具体工具条件。
映射通过也不证明原子完整或适合计算 SASA。FreeSASA 的 config、质量条件及科学验收独立检查。

## 3. 候选方法的范围

`entity_label_or_exact_subsequence` 在 mmCIF 提供实体序列时，先核对实例/实体声明，再要求完整
`_entity_poly_seq` 与输入逐字一致，通过 `label_seq_id` 定位输入位置，保留原始作者地址。
实体位置须连续且唯一，坐标残基身份也必须一致；缺失坐标位置为 null。这可以定位重复区内的缺失。
实体表有冲突、微异质性或不完整时不绕过问题；完整实体与输入不同的片段不自动作为唯一成功映射。
实体表不存在时才使用下述原候选方法。方法标识及格式仍在 v0.1 内维护。

`exact_ordered_subsequence` 是原有工程探测方法，不是专家指定的通用科学比对算法：

1. 保留每条结构链中观察到的残基顺序，对照输入序列逐字匹配，允许输入位置在结构中缺失。
2. 分别找最早和最晚的顺序嵌入。二者一致才是该方法下的唯一位置候选；不一致就报歧义。
3. 在全部蛋白链中检查候选唯一性。手动指定摄取链不能绕过多个可能设计链的复核。
4. 多 MODEL 未指定时先报告待选择；不默认第一个 MODEL 代表科学计算基座。

无替换评分、gap penalty、覆盖率或 identity 接受阈值。它不会把替换、插入或重复区勉强对齐，
也不能仅凭“唯一子序列”证明生物学正确。新增实体位置路径同样只生成待核验候选；一般替换/插入仍需经评审比对方法。
非标准残基原名保留，不自动变为标准残基；altloc 全部登记，不自动选择某个构象。
mmCIF 缺 author 编号或 author ID 非整数（如把 43A 写在 auth_seq_id 中）时，当前探测器明确失败并保留原始输入，
不能回退为 label 编号。该格式分支仍待工程转换约定与消费方验证，不能声称生产全格式已完成。

## 4. 同事如何检查

从任务包根执行：

```bash
python interface/structure_mapping/validate_mapping.py --mapping examples/mapping.example.json
python interface/validate.py --request request.json --result output/result.json --check-files
```

第一条检查表内格式、序列指纹、坐标完整性和状态一致性。FreeSASA 包提供对应人工文件，BepiPred 无此工具输入。
第二条在请求引用 mapping 时，同时核对映射内容与请求的 sequence、结构 hash、mapping_status。
输入 mapping 文件 hash 正确，但其中写的结构 hash/序列/状态不符，也会失败。

上述便携检查器无需 Biopython，不能证明地址确实存在于结构中。
主开发另用本地重解析检查器对比实际结构、候选链和每个作者编号；两层均不能代替科学批准。
不要把 unverified 改为 verified 来消除错误。拿到经核验样本后，再按 review 指向的决定填写。

依据：专家 SKILL R-58、SOP S-07c/S-11、FreeSASA ToolSpec §2/2b、ProteinMPNN ToolSpec §2、
FoldX ToolSpec §2a 的 chain/resSeq/iCode 要求。上述文件位于各任务包 references 原件索引；
公共字段、候选方法和检查层次是本次工程决定，未知科学接受标准仍未自行补齐。
