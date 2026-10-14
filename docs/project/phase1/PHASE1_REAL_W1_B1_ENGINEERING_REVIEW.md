# B1 输入事实工程补强评审

本评审对应 [E01–E04 任务包](PHASE1_REAL_W1_B1_ENGINEERING_BACKLOG.md)。实际完成范围和后续排期见
[STATUS](../STATUS.md)，本轮验证命令与结果见 [维护验证记录](PHASE1_REAL_W1_B1_ENGINEERING_VERIFICATION.json)。

## 实现与交付

新增 [input_facts.py](../../../src/t01_structure_mapping/input_facts.py) 和
[CIF 原值读取器](../../../src/t01_structure_mapping/cif_facts.py)，通过
[独立 CLI](../../../scripts/probe_b1_input_facts.py) 使用；原 probe.py、候选生成及运行层 Worker 注册保持原字节。
新增 [工程结果扩展](../../../工作流设计/02-数据契约/phase1-real-v0.1/b1-engineering/README.md)，
直接验证原 B1 ingest 请求，返回绑定该请求的事实 Artifact，不改写原 B1 草案及其已登记 hash。

| 子项 | 行为与验收证据 |
|---|---|
| E01 输入预检 | 以内容识别 PDB/CIF，分别报告格式不符、损坏、不支持分支、MODEL/链不存在或非蛋白；记录全部 MODEL/链与 AUTO 候选；显式选择失败没有回退 |
| E02 原始元数据 | PDB EXPDTA/REMARK/SOURCE/COMPND 原行与可识别字段；mmCIF 方法、分辨率及来源类别；带原名/原值/位置、缺失/多值/差异/不可解析诊断 |
| E03 无损作者地址 | 每条原子保留字符作者编号、iCode、label/auth 链/位置/实体和出处；43A 与 43+iCode A 独立；整数/PDB/FoldX 格式逐项检测可表示性与碰撞 |
| E04 事实交接 | 精确请求及结构字节、三份独立事实 ArtifactRef/hash；本地实例的 run/request/job/attempt 和输入绑定；拒绝时仍保留诊断事实，字段来源可回读 |

[新批次](../../../discovery/t01-phase1-real/w1/b1-engineering-20260905/README.md)包含输入、独立预期、实测命令、
结果配对、修改前原件/旧证据指纹和新旧源码快照。原件与旧 R-58、B1、运行层证据均由只读校验复核。
首次调用前声明的预期使用具体文件编辑及前批独立计数，重解析只证明可重复性，不冒充科学金标准。

## 来源与工程处理

已复核当前一期图、SOP S-07b/c、SKILL R-58、Schema host_species/structure、结构获取 ToolSpec §2d、
FoldX §2a 及环境清单 §1a；后续节点 01 内网决定继续覆盖外部查询。
章节与公开格式依据保存在 [source_review.json](../../../discovery/t01-phase1-real/w1/b1-engineering-20260905/source_review.json)。
公开检索只访问格式说明，未上传结构/序列或调用结构数据库。

wwPDB 的 [auth_seq_id 定义](https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_atom_site.auth_seq_id.html)
允许非数值作者标识；[iCode](https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_atom_site.pdbx_PDB_ins_code.html)
为独立字段。因此本实现不将字符 `43A` 拆成数字和插入码，FoldX 原件的示例原义仍按 B1 限定评审定点确认。

PDB 地址列按 [wwPDB ATOM/MODEL 格式](https://www.wwpdb.org/documentation/file-format-content/format33/sect9.html)记录；
元数据对照 [PDB/mmCIF 字段关系](https://mmcif.wwpdb.org/docs/pdb_to_pdbx_correspondences.html)。
CIF 读取器限定为 [CIF 1.1](https://www.iucr.org/what-we-do/digital-standards/cif/cif1/file-syntax)单 data block、标量及平面 loop，
保留引号、分号文本与缺失标记。复杂方言不被误报为“用户文件必然损坏”。

以下为明确的工程选择，未扩张为科学规则：

- 原值位置按原 UTF-8 解码文本字符偏移及行列记录，BOM/CRLF 不归一化；原始字节另有 hash。
- 未知 iCode `?` 不能无损投影为空串；允许记录事实，但阻断该整数地址投影。旧探针的历史输出不回写。
- 不拼接 SOURCE/COMPND 的不完整续行，不挑选多方法或多分辨率的某个值；原行和诊断并存。
- 字符编号、前导零、过长链、iCode、数值范围和地址碰撞各有具体阻断原因；不会改名或重新编号以绕过消费者限制。
- PDB 非十进制编号、缺作者字段及数值不确定度写法属于当前未支持分支；原始文件始终保留。
- 缺少或损坏 CIF 语法时元数据标 extraction_status=unavailable，不能将提取失败当成正常的元数据缺失。

## 适用边界与剩余材料

该探针只提供可审查的文件事实，不是完整字典/科学有效性验证器，也不生成整数映射或候选序列比对。
AUTO/显式摄取链不是科学设计链；保留全部 altloc 和原子记录，不选择构象或计算缺原子比例。
来源声明与文件方法并列保留，source/plddt/missing_atom_fraction 仍为 null，host_species 始终沿用请求。

消费者字段 representable=true 仅表示保守格式投影可表达该地址。
它不验证完整 PDB 转换、工具原子身份、计算能力、映射正确性或消费者 G1；所有科学资格仍为 NOT_EVALUATED。
尤其 1UBQ 中的未知 iCode 在本事实层可见且受保守阻断，不改变原 R-58 候选的历史身份。

E01–E04 的工程准备闭环后，B1-E01 剩余的是具体消费者转换与适用工具验证；B1-A02 的原始元数据输入已具备，
来源判定及冲突处理仍由算法给出。B1-M01～M03、A01/A03 继续按
[B1 七项关闭条件](PHASE1_REAL_W1_B1_REVIEW.md#5-oi-015023-剩余项的定点关闭条件)准备。
没有签发 scientific signoff、verified、正常 RSA、正式 B1 Worker 或 W1 G1，也没有部署生产服务。

日常只读验证与新批次操作见 [运行手册](../../development/RUNBOOK.md#b1-输入事实工程补强)。
