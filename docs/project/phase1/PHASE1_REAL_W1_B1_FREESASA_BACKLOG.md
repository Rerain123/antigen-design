# B1 消费者验证：FreeSASA

本任务由用户在 B1 E01–E04 完成后明确指定，承接 [输入事实工程评审](PHASE1_REAL_W1_B1_ENGINEERING_REVIEW.md)。
当前状态统一见 [STATUS](../STATUS.md)。范围是开发环境中的输入事实消费、地址/原子核验和原始面积回连，
不将 B1 或 FreeSASA 的完整科学 G1 提前放行。

| 子项 | 要求与验收 |
|---|---|
| F01 消费入口与来源绑定 | 消费已验证的 B1 事实配对，重新核对请求、原结构及三份事实的字节/hash；MODEL、上下文链和使用路径显式声明 |
| F02 工具地址与原子身份 | PDB 路径核对定宽转换和再解析；原子 API 路径单独验证字符编号。保留 label/auth/iCode，不截短、不重编号，工具 token 碰撞在计算前拒绝 |
| F03 原始工具实测 | 沿用既有固定镜像、ProtOr/LR200/1.4 Å/1 thread，实际禁网执行；逐原子核对工具读入身份、坐标、半径，再将面积按原始身份回连 |
| F04 限定评审与回归 | 预先声明正反例、两路径对照、乱序与篡改；记录实际调用/拒绝及工具未启动的边界，维护接口差异、原件/旧资产只读校验和当前根回归 |

依据先读 C34 ToolSpec §2/2b/4、SKILL R-58、SOP S-11、[已采用 FreeSASA 方案](PHASE1_REAL_W1_FREESASA_S09_DECISION.md)
及其 profile/用户记录；已有数值和地址证据见 [R-58/FreeSASA 边界专项](PHASE1_REAL_W1_R58_SASA_BOUNDARIES.md)。
原件、既有 profile、B1 原始事实和旧探针均保留原字节，新代码及实际运行使用独立批次。

本次不把未知 iCode `?` 自动改为空串，不用改写输入/改名绕过字段限制。
原子 API 是独立开发路径，需验证实际安装版本是否保持作者 token；不能只凭文档推定成功。
原生 API 通过也不表示旧整数 mapping Schema 已支持字符编号。
水和 H/D 按既有候选上下文排除并记账；非标准/非蛋白、altloc、占有率等未批准上下文明确拒绝或复核。
输入事实与原子面积回连不构成 R-58 科学映射批准；来源、缺原子比例、正常 RSA、buried_fraction、S-09 和生产 Worker 保持原门禁。

实现及接口差异见 [工程评审](PHASE1_REAL_W1_B1_FREESASA_REVIEW.md)，精确命令见 [运行手册](../../development/RUNBOOK.md)。
进度与下一步只在 STATUS 维护。
