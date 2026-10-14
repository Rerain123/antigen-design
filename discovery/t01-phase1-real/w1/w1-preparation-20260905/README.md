# W1 环境与样本准备记录

本批用于 W1-01/02 的本地事实登记；任务说明见
[环境与样本登记](../../../../docs/project/phase1/PHASE1_REAL_W1_PREPARATION.md)。
项目状态见 [STATUS](../../../../docs/project/STATUS.md)。

| 文件 | 内容 |
|---|---|
| [environment.json](facts/environment.json) | 当前开发进程的 OS、Python 包元数据、PATH 与检查范围 |
| [sample_audit.json](facts/sample_audit.json) | 1UBQ 实体/编号/坐标对照及两个样本的原始原子事实 |
| [result.json](facts/result.json) | 实际命令、输入/采集脚本与产物的字节/hash、局部执行结论 |
| [verification.json](verification.json) | 本批输入/产物 hash 复核及与前批结构解析器的原子总数交叉核对 |
| [collect_facts.py](collect_facts.py) | 本批固定样本的可重放采集程序，不是生产工具或通用映射算法 |

采集只读当前样本副本和旧 R-58 产物，不读取冻结历史实现，不修改映射，不运行科学工具、不安装依赖。
未联网获取结构；未检查甲方目标环境、容器、WSL 或独立部署项目。

复跑命令统一见 [运行手册](../../../../docs/development/RUNBOOK.md#w1-环境与样本准备)，每次使用新输出目录。
PASS 只表示该批采集、来源 hash 和编号对照完成；目标 G0、科学 G1 与生产部署仍未执行。
