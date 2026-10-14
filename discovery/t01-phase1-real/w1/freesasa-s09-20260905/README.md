# FreeSASA 原始输出与 S-09 准备记录

本批范围为开发机 Docker 内的原始 FreeSASA 验证；任务解读见
[FreeSASA 专项](../../../../docs/project/phase1/PHASE1_REAL_W1_FREESASA_G0.md)，
规则准备见 [S-09 核对](../../../../docs/project/phase1/PHASE1_REAL_W1_S09_RULE_REVIEW.md)。
项目状态见 [STATUS](../../../../docs/project/STATUS.md)。

| 入口 | 内容 |
|---|---|
| [环境](environment/docker.json) | 本机引擎与实际镜像 ID；同目录记录构建和包来源 |
| [输入来源](inputs/SOURCE_MANIFEST.json) | 当前样本副本、映射候选及人工格式错误输入 |
| [首轮 campaign](campaign_result.json) | 七次实际 Docker 命令、退出码、耗时、stdout/stderr 及产物 hash |
| [原生 PDB 原始结果](runs/converted-pdb/result/raw.json) | 逐原子、逐残基绝对 SASA、半径及库自带相对值；不等于项目 RSA |
| [插入码及 NaN 补查](followup/inspection.json) | 四次 API 诊断；人工编号的真实坐标副本与旧人工坐标明确区分 |
| [只读核验程序](verify_evidence.py) | 来源/hash、残基身份、重复性、原子加总及 S-09 草案状态检查 |
| [补充清单](supplement_manifest.json) / [维护验证](maintenance_verification.json) | 后续诊断和 S-09 草案 hash；本次检查范围及结果 |

[原始探针](probe_raw.py)与[首轮执行器](run_local.py)按已执行时点保留；
[后续诊断](inspect_insertion.py)单独记录，未改写首轮序列化失败事实。
首轮非法 PDB/mmCIF 入口失败属于原始解析异常；两个旧人工坐标案例属于含 NaN 后的序列化拒绝，不能统称工具没有运行。

构建需要公开依赖下载；科学运行时禁用容器网络。当前资料不是可离线重建的完整 G3 软件交付包。
复跑命令见 [运行手册](../../../../docs/development/RUNBOOK.md#freesasa-本地原始工具探测)，使用新目录，勿覆盖本批。
所有核验只声明工程事实；映射保持 unverified，S-09 案例未执行，科学验收与生产部署未放行。
