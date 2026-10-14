# W1：R-58 与 FreeSASA 边界补强

本轮把“本地结构解析 → 待核验映射 → 派生 PDB → FreeSASA 原始面积 → 按输入位置对照”串起来，
用于开发验证。当前阶段和下一任务见 [STATUS](../STATUS.md)，
原始产物见 [本批记录](../../../discovery/t01-phase1-real/w1/r58-freesasa-boundaries-20260905/README.md)。
没有签发 verified 映射，没有产生可供科学流程消费的正常 RSA 或 buried_fraction。

## 修复与实现

### 用明确的实体位置解决重复区缺失

原方法只看有坐标的残基序列。若输入末端为 GG、结构仅保留其中一个 G，就可能无法判断缺失位置。
新路径在 mmCIF 提供完整实体序列时，核对完整序列与输入逐字一致，再利用实体位置找到原始作者地址。

- 先核对 `_struct_asym`、`label_asym_id`、`label_entity_id` 的对应关系，拒绝重复实例 ID 或相互矛盾的声明。
- `_entity_poly_seq` 必须为连续 1…N、每位唯一的标准氨基酸序列；完整序列须与输入一致。
- 每个坐标残基的 `label_seq_id` 必须唯一、在范围内，且残基身份与该位置一致。
- label 编号只用来定位输入位置；交给工具核对的地址仍是作者 `chain_id/res_seq/insertion_code`，不更换编号体系。
- 实体表缺失时仍可产生原有顺序子序列候选。有实体但字段不完整、微异质性、未知残基或位置冲突时，不绕过错误改报唯一成功。
  完整实体与输入不同的片段仍需适用比对方法，保留差异/歧义诊断，不新增替换评分或接受阈值。

依据：专家 [SKILL R-58](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md)、
[C34 §2/2b](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C34_FreeSASA_v10.5.md)，以及
wwPDB 对 [label_seq_id](https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_atom_site.label_seq_id.html)、
[label_entity_id](https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_atom_site.label_entity_id.html)和
[实体序列表](https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Categories/entity_poly_seq.html)的定义。
这是有明确字段来源的工程候选方法；完整科学映射审批仍独立进行。

### 转换前后核对原子与地址

[开发桥接模块](../../../src/t01_structure_mapping/sasa_probe.py)要求显式 MODEL 与计算上下文链集合。
原件只读；派生 PDB 写入新文件，记录原件/派生文件 hash、选择、排除项和占有率问题。
重解析后核对原子数量、作者地址、插入码、原子名、元素及 PDB 三位坐标精度。
FreeSASA 读取后再核对一次原子身份和坐标，最后按完整地址归并面积，不按两个数组的行顺序配对。

采用 [既有 FreeSASA 方案](PHASE1_REAL_W1_FREESASA_S09_DECISION.md)中的 ProtOr、1.4 Å、200 slices、1 thread。
水和 H/D 的排除留有记录；多字符链、超出 PDB 字段范围、未选择 altloc、未知非蛋白上下文不静默转换。
部分占有率保留原值并记复核问题；本轮原始计算不代表上下文已获科学批准。

公共格式仍在 **v0.1 / 0.1.0** 内维护，新增 `entity_label_or_exact_subsequence` 方法标识；
原 `exact_ordered_subsequence` 示例仍有效。重解析检查增加方法身份核对，两份备用同事包按同一 canonical 来源同步。

## 实际验证结果

先声明案例，再执行。除原始 1UBQ 外，以下均为本地 1UBQ 派生的人工边界，不能当作独立生物学留出样本。

| 案例 | 结果 |
|---|---|
| 原始 1UBQ | 602 个原子、76 个残基；总面积复现已有 200 slices 结果；G76 出域继续保留 |
| 删除重复末端第 75 位坐标 | 实体位置路径生成待核验候选；FreeSASA 返回 75 个残基；对照数组仍长 76，第 75 位 null、第 76 位有值 |
| A43 改为 A42A | 保持 A42/A42A 两个地址；映射回输入后的每一位绝对面积与原始结果完全相同 |
| A1 改为 A−1 | 负编号完整保留；逐位绝对面积与原始结果完全相同 |
| 唯一目标链 + 人工 B 链上下文 | A 链唯一候选，B 链 fixed；两链都参与原始计算，只将 A 链对齐输入。A 链 53 个位置面积减少，说明遮挡上下文被实际纳入 |
| 两条相同目标序列链 | 可以记录整结构原始面积；映射保持 unreliable，没有目标链对齐数组 |
| 坐标残基替换、label 位置越界 | 保留具体冲突，映射 unreliable；没有安排原始面积计算来掩盖输入问题 |
| `auth_seq_id=42A` | 解析明确拒绝，不猜成 42 + iCode A；原始输入保留 |
| 多字符作者链 AUTH | 可以解析并形成候选；PDB 转换明确拒绝，不截成 A |
| 数字插入码使 4+“2” 与 42+空码产生同一工具 token | 工具边界预检拒绝，防止地址合并；未计算面积 |
| 未知原子名 ZZZ | 保留 ProtOr 分类器返回的负半径值，明确拒绝；不猜半径或跳过原子 |

共 12 个案例，6 次真实 FreeSASA 计算、2 次工具边界拒绝；其余为解析/映射/转换检查。
完整判定见 [assessment.json](../../../discovery/t01-phase1-real/w1/r58-freesasa-boundaries-20260905/assessment.json)。
全部工具运行禁网，原始 stdout/stderr、版本、镜像、参数、原子半径和地址可追踪。
编号变化的比较采用精确数组一致性；多链只验证遮挡关系，不提出新科学误差阈值。

首次人工多链构造误用了 1UBQ 已属于水的 label B。本轮发现后新增实例声明冲突检查，
修正后的新准备目录使用作者链 B / label C。首次输入与结果保留为准备阶段错误证据，
未投入 FreeSASA 运行；实际执行只使用 `prepared/` 中修正后的输入。

## 接手和剩余边界

命令与执行条件统一见 [运行手册](../../development/RUNBOOK.md#r-58-与-freesasa-边界开发验证)。
修改前源码留在新批次 `before/`，实际运行源码留在 `after/`；原 R-58 批次的源码 hash 表示旧时点，
不回写为当前版本。只读检查用实际运行快照复核，旧原始证据保持原字节。

本轮减少了已知工程缺口，但仍需要：非整数作者 ID 的无损工具消费方案、一般替换/插入的适用比对方法、
altloc 选择与完整性模板、独立真实留出样本，以及算法验收和甲方目标环境实测。
S-09 六项先行规则的算法确认、G76 出域的 OI-027 核验没有因此关闭。
所有结果仍是 unverified/unreliable 和不可自动消费，W1 整体 G1/G2 未放行。
