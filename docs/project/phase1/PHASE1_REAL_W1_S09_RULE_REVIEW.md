# W1 S-09 规则核对与定点裁决

本页服务 W1-06/07，保留原文核对与初始案例；不冒充算法确认或生产判定。
六项具体方案已由用户先行采用，现行口径见 [先行决定](PHASE1_REAL_W1_FREESASA_S09_DECISION.md#5-s-09-六项先行裁决)
及 [用户记录](../sources/PHASE1_W1_FREESASA_S09_ADOPTION_20260905.json)。算法确认仍待补齐。
执行状态见 [STATUS](../STATUS.md)，案例及来源 hash 见 [案例清单](PHASE1_REAL_W1_S09_CASES.json)。
清单包含字段级预期，部分案例仅覆盖掩码或指定分支，不是可直接提交的完整 N01 请求。

## 原件定位

| 来源 | 适用内容 |
|---|---|
| [SKILL §2.1 R-01/R-02、R-48](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md) | pLDDT / pTM 门槛与异常复核通则 |
| [SOP S-09、T-01 step2](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md) | 来源分流、方法分档、掩码及 S-11 非 low 执行条件 |
| [结构 ToolSpec §2c/3/4/5/6](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md) | 掩码默认参数、双写、null 守卫与抽象验收用例 |
| [Schema structure](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md) | 实验 pLDDT / pTM 为 null；低置信区位于 structure；source 枚举 |
| [环境清单 §参数台账](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期实施环境清单_v10.5.md) | 掩码阈值、最短长度与合并间隔 |

已复核本表及后续用户决定。内网决定去掉 AFDB 查询与 fallback；不因 S-09 原文仍列 alphafolddb 而恢复该入口。

## 可直接归并的部分

| 输入条件 | confidence | topology_reliable | 附加规则 |
|---|---|---|---|
| X-ray：0 < resolution < 3.0 Å | high | true | 实验掩码为 null |
| X-ray：3.0 ≤ resolution < 4.0 Å | medium | true | 4.0 单列裁决 |
| X-ray：resolution > 4.0 Å | low | false | S-11 条件跳过 |
| cryo-EM：0 < resolution < 3.5 Å | high | true | 实验掩码为 null |
| cryo-EM：3.5 ≤ resolution ≤ 4.0 Å | medium | true | 4.0 明确包含 |
| cryo-EM：resolution > 4.0 Å | low | false | S-11 条件跳过 |
| NMR：0 < resolution < 3.0 Å | high | true | 仅归并原文列明分支 |
| NMR：resolution=null | medium | false | 通用无法获取分辨率的 WARNING；掩码为 null |
| AF3/ESMFold2：mean_plddt ≥ 0.70 | high | 由 pTM 决定 | 使用已核实标度的 [0,1] 数值 |
| AF3/ESMFold2：0.50 ≤ mean_plddt < 0.70 | medium | 由 pTM 决定 | 0.70 依 R-01 明确归 high |
| AF3/ESMFold2：mean_plddt < 0.50 | low | 由 pTM 决定 | confidence 与 topology 分开计算 |
| 预测 pTM ≥ 0.50 / <0.50 或 null | 不改变 confidence | true / false | 不从置信度反推 pTM |

上述数值分档仅适用于合法输入；负分辨率、NaN、未归一化 pLDDT 等不直接套表。
缺少必需元数据先暴露明确错误/待核实项，不按零值填充，也不把 B-factor 自动当作预测置信度。
未知 source 的 confidence=low+WARNING 已有原文；其 topology_reliable 的赋值未写明，不能冒充完整就绪分支。

掩码按原文先识别 pLDDT<0.50 的连续段（至少 5 位），再合并间隔不超过 3 位的相邻合格段。
位置为 1-based 闭区间，间隔为两个端点之间的残基数。阈值、长度、间隔作为显式默认参数登记，
回测校准前不擅自改变；短段先拼接再筛选不作为本轮默认解释。实验结构或逐残基数组为 null 时返回 null，
可用数组中没有合格段时返回空数组。最终实现同时写 structure 和 quality；只写一处不能通过验收。

## OI-024：三组问题、逐例裁决

| ID / 输入 | 原文差异或缺口 | 原文确定部分 | 用户先行采用的处置（算法仍待确认） |
|---|---|---|---|
| S09-D01：X-ray 4.0 Å | SOP 分档正文写 3.0–4.0→medium，topology 注释写 4.0=low | topology=true，掩码=null | confidence=medium，采用正文闭区间；澄清注释，待算法确认 |
| S09-D02a/b：X-ray / cryo-EM，resolution=null | 各方法分支写 low；随后通用行及 ToolSpec §5 写 medium+WARNING | topology=false，掩码=null | 两者适用通用 medium+WARNING，通用 null 条款优先；待算法确认 |
| S09-D03a/b：NMR 3.0 / 4.1 Å | SOP 只覆盖非空 <3.0 与 null | topology 公式诊断值分别为 true / false，实验掩码=null | 不输出正常 quality，强制复核并禁止自动交接；不借用 X-ray 档值，待算法确认 |
| S09-D03c：未识别实验方法、resolution=2.0 Å | 已知是实验来源，但方法分档未覆盖 | topology 公式诊断值为 true，实验掩码=null | 不输出正常 quality，强制复核并禁止自动交接；保留实验来源，待算法确认 |

最终算法确认需要：具名负责人、日期、来源与章节、适用输入、最终规则、边界/null 预期及影响。
用户已对六项具体内容作出先行采用决定；历史案例清单保留当时的 null 待定字段，当前准备须同时
读取后续采用记录，不能把旧快照误当成仍无项目决定，也不能把先行采用当作科学确认。

## 与其他开放项和 FreeSASA 的衔接

- OI-023 负责本地结构来源/方法/分辨率的证据字段及别名归一化；AF3/ESMFold2 缺失均值、数组不符、
  非有限值及非法范围按生产输入规则处理，不能套用仅写给 AFDB 的缺失值回退。
- 未知来源的 topology 缺省和异常输入完整返回形态仍须在 W1-07 明确；这不改变已有的 unknown→low 规则。
- S-09 只决定质量及条件分支。FreeSASA 还需要 R-58 映射、原子/链/MODEL 上下文与参数；quality 非 low
  不自动证明这些前提满足。本地原始工具探测只记录事实，不通过未决规则放行 pipeline。
- 初始案例是带来源的验收草案；六项后续方案按用户决定先行采用，算法确认后再冻结最终规则。
  OI-024 保持 IN_REVIEW，G1/G2 不因先行采用或本地工具运行通过而放行。
