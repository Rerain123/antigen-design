# W1-09A 本地工程运行证据

任务范围和实现方式见 [说明](../../../../docs/project/phase1/PHASE1_REAL_W1_RUNTIME_IMPLEMENTATION.md)，
当前阶段见 [STATUS](../../../../docs/project/STATUS.md)。

- [acceptance.json](acceptance.json)：CLI 案例、RT01–RT15 实测映射与工程适用范围。
- [manifest.json](manifest.json)：本批源码、测试、命令和产物的字节/hash 清单。
- [environment.json](environment.json)：Windows、Python、SQLite、jsonschema 开发环境。
- [runtime-tests.xml](runtime-tests.xml)：实际工程测试结果；[执行命令](runtime-tests-command.json)保留标准输出。
- [最终维护检查](../../../../docs/project/phase1/PHASE1_REAL_W1_RUNTIME_VERIFICATION.json)：根回归、文档、原件及冻结资产检查；maintenance 子目录保存本轮根测试原始 JUnit。
- commands 和 jobs 子目录：CLI 原始记录、任务事件、执行身份、文件与进程停止回执。

运行数据库与进程目录单独放在 .tmp；本目录只放可复核证据。首版不自动清理运行数据。
本批不包含科学工具运行或服务器部署；故障测试中断的均为本批创建的无害进程。
复核使用 [check_w1_runtime.py](../../../../scripts/check_w1_runtime.py)，复跑使用
[run_w1_runtime_acceptance.py](../../../../scripts/run_w1_runtime_acceptance.py)并指定新的证据目录，不能覆盖本批。
