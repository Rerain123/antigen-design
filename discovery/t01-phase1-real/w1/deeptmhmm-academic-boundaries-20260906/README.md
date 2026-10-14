# DeepTMHMM Academic：B2 原包边界与执行补证

本批限定范围见 [补证说明](../../../../docs/project/phase1/PHASE1_REAL_W1_B2_BOUNDARIES.md)，
进度只见 [STATUS](../../../../docs/project/STATUS.md)。
[plan.json](plan.json) 是调用前登记的输入、预期和资源限制；[method_summary](method_summary.json)
引用前批原始版本/参数身份，不回写前批科学结论。

inputs 保存精确原始 FASTA；runs 下的真实调用保留命令、输入、运行日志、inspect、token trace 和完整输出。
fault-* 是真实结果的故障副本，fault.json 区分事后产物注入与实际模型执行。
protected_before 记录旧证据/原件/源码保护，封存后仅用专用 verify 复核，不重跑旧输出目录。
执行与复验命令见 [运行手册](../../../../docs/development/RUNBOOK.md)。

所有结果保持 NOT_DEPLOYED；输入/参考/目标环境/契约签收是正式适配器的独立前提。

[执行评估](assessment.json)、[实际方法与 token 汇总](method_summary.executed.json)、
[原包非法字符发现](source_finding.json)分别记录实测结果、原始出处和未满足的原包拒绝预期。
