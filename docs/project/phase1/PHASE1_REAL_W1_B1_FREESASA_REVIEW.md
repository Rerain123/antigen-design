# B1 → FreeSASA 消费者工程评审

本评审承接 [专项任务](PHASE1_REAL_W1_B1_FREESASA_BACKLOG.md)及 B1 原始输入事实，范围为本机开发消费者。
现行状态和下一步见 [STATUS](../STATUS.md)，维护检查见 [验证记录](PHASE1_REAL_W1_B1_FREESASA_VERIFICATION.json)。
这是 AI 工程自审记录，不代替算法负责人或甲方的科学签收。

## 1. 结果与适用范围

F01–F04 已形成独立源码、文件接口、实际工具调用和可复核证据。
正式 r02 批次的 45 组预声明案例全部符合预期：18 组完成原始面积回连、26 组准备阶段拒绝，
另 1 组调用 ProtOr 分类器后因未知半径拒绝，未开始面积计算。
固定 FreeSASA 2.2.1 镜像只见 lo 网卡；Python/Biopython/numpy 实际版本与既有 profile 一致，
参数沿用 ProtOr / Lee–Richards / 200 slices / 1.4 Å / 1 thread。

| 验证事项 | 结果及边界 |
|---|---|
| 原始事实消费 | B1 请求、结构、三份事实、ArtifactRef、执行身份及用户声明完整复制；工具进程再次核对 hash 与重解析 |
| PDB 路径 | 定宽地址及坐标转换后重解析，再核对 FreeSASA 实际读入；字符号/前导零拒绝，不截短或重编号 |
| native 原子路径 | 实测保留 43A、44B、043、43、长作者号和带正负号编号；旧整数 mapping Schema 未被扩大 |
| 碰撞检查 | 字符 43A 与 43+iCode A、4+iCode 2 与 42、不同 label 身份共享 author token 均明确拒绝 |
| 逐原子回连 | 工具身份、数量、坐标、ProtOr 半径核实后，以工具原子索引回连完整 raw_address；乱序不改变结果 |
| 两路径对照 | 整数、iCode、负编号、多链共 4 组，等坐标下逐原子/逐残基面积精确一致；只移除固定宽度字段的填充空白作语义比较 |
| 上下文与精度 | 显式模型/链、水和 H/D 记账；链 A 单独与 A+B 的遮挡方向检查通过。PDB 三位小数和 native double 分别记录 |
| 拒绝与防篡改 | 未知 iCode、长链、模型/上下文错误、altloc、占有率、元素/名称冲突、非蛋白和未知半径，以及绑定/产物篡改均有回归 |

## 2. 消费接口变化

新增 [freesasa_consumer.py](../../../src/t01_structure_mapping/freesasa_consumer.py)，
通过 [准备 CLI](../../../scripts/prepare_b1_freesasa.py)消费上游 bundle；
[容器入口](../../../scripts/run_b1_freesasa_consumer.py)执行固定的开发探针。
完整字段、状态、错误与产物责任见 [开发文件接口](../../../工作流设计/02-数据契约/phase1-real-v0.1/b1-freesasa/README.md)。

preparation.json 保留原始 MODEL、label/auth 地址、作者 token 与独立 iCode、原始和工具坐标及排除清单。
原生路径仍受 FreeSASA 单字符链和组合 token 唯一性约束；API 能保存字符串不意味着所有原始身份都能表达。
未知 iCode `?` 不转换为空串，作者号中的字符也不被自动拆成 iCode。
ProtOr 半径来自明确分类器，未知半径不使用元素猜测回退；四列原子名使用已经声明的重元素，实际工具半径再次核对。

raw_residue_areas.json 按完整原始残基地址给出绝对 SASA，绑定上游、准备产物与原子面积 hash。
未生成输入序列位置数组、正常 RSA、buried_fraction 或 scientific mapping；旧事实探针、旧映射 Schema、
旧 sasa_probe 和既有 profile/专家原件均保持原字节，未注册运行层 Worker。

## 3. 原始样本与失败记录

本次正向夹具是明确标记的人工重原子几何。它们验证工具调用与地址回连，不能增加真实参考样本数。
原始 1UBQ CIF 因未知 iCode 被拒绝；历史已派生 PDB 中有 28 个非完整占有率原子，
在当前严格消费支持域仍被拒绝。保留旧原始数值证据，不据此补签新的科学资格或修改输入绕过边界。

首轮工具调用的身份检查通过，但夹具生成器将一处坐标写成 6.4399999999999995，
PDB 转换为 6.440 后与 native 接收到的 double 不同，因此四组精确路径比较未通过。
[首轮失败记录](../../../discovery/t01-phase1-real/w1/b1-freesasa-consumer-20260906/initial_assessment.json)
及执行源码、输入、日志和面积已完整保留。仅修正人工夹具的字面量生成后，在新的 r02 批次独立复跑；
未放宽消费者、科学阈值或比较标准。

正式证据见 [r02 索引](../../../discovery/t01-phase1-real/w1/b1-freesasa-consumer-20260906-r02/README.md)，
其来源与保护清单同时覆盖专家原件、旧 B1/R-58/运行层以及首轮试验。

## 4. 限定放行与后续接口责任

本评审只支持 B1-E01 的 FreeSASA 开发消费子域：完整原始身份到原始面积的工程回连。
映射状态保持 NOT_EVALUATED，结果固定不可用于 pipeline；B1-M01/M02/M03、A01/A02/A03，
复杂上下文、缺原子模板、科学参考、OI-024/027 和目标机 G0/G1 仍按既有关闭条件评审。
FoldX、DSSP 及其他 R-58 消费者的编号/格式适配须各自验证，本批不会将它们一并标为完成。
