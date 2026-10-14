# 当前一期测试区

根配置只收集当前 tests 目录，历史包在各自目录单独运行。

| 范围 | 入口 |
|---|---|
| B2 原包 token/切片、真实产物损坏、失败退出与完整性拒绝 | [test_b2_boundaries.py](test_b2_boundaries.py)；只读已有执行，不运行容器 |
| B2 DeepTMHMM 请求/结果绑定、PB/null、连续区段/计数、输入支持与参考独立性 | [test_w1_b2_review.py](test_w1_b2_review.py) |
| B1 → FreeSASA 字符地址、身份/坐标/半径守卫、乱序回连与证据防篡改 | [test_b1_freesasa_consumer.py](test_b1_freesasa_consumer.py) |
| B1 输入选择、原始字段/位置、无损地址与独立 Artifact 绑定 | [test_b1_input_facts.py](test_b1_input_facts.py) |
| B1 草案、跨请求/文件身份、未批准状态与案例重解析 | [test_w1_b1_review.py](test_w1_b1_review.py) |
| W1 本地运行层并发、进程树、停止恢复、文件隔离与独立证据 | [test_w1_runtime.py](test_w1_runtime.py)、[test_w1_runtime_evidence.py](test_w1_runtime_evidence.py) |
| Windows SQLite 临时目录项、打开句柄与历史源码根守卫 | [test_w1_runtime_fix.py](test_w1_runtime_fix.py) |
| W1 真实运行设计：状态、身份、文件、工程/科学边界与来源 | [test_w1_contract_design.py](test_w1_contract_design.py)；静态设计检查，进程级运行实现另验 |
| 真实工具公共接口状态、文件、身份与交接包一致性 | [test_tool_interface.py](test_tool_interface.py) |
| 本地 PDB/mmCIF、R-58 映射、历史样本复用与错误守卫 | [test_structure_mapping.py](test_structure_mapping.py)、[样本说明](fixtures/structure_mapping/README.md) |
| FreeSASA 本地证据、S-09 待决状态及 PDB 转换身份 | [test_w1_freesasa_evidence.py](test_w1_freesasa_evidence.py)；只读检查，不在根测试中运行容器 |
| FreeSASA 独立数值参考、容差预算、出域值及裁决快照保护 | [test_w1_freesasa_reference.py](test_w1_freesasa_reference.py)；历史待决快照的后续采用状态见用户决定记录 |
| 文档路径、关键导航、当前任务入口及过时入口负测 | [test_docs.py](test_docs.py) |
| 一期 Mock 规格、fixture、场景、生命周期和工具契约 | [t01_phase1_mock](t01_phase1_mock) |
| Dify 生成、绑定、实例证据、parity、隔离及冻结协议 | 同一 Mock 测试目录中的 test_dify_*、test_m4_* |

如何选择检查和执行分区回归见 [运行手册](../docs/development/RUNBOOK.md)；
规格、执行结果及冻结证据见 [一期任务索引](../docs/project/phase1/README.md)；
最新验证结果见 [STATUS](../docs/project/STATUS.md)。

冻结 Catalog 中 DECLARED_NOT_RUN 等是规格时点声明，不能用当前测试结果反向改写。
当前测试不得导入旧包或跨目录收集 legacy 测试；三套结果分别报告，不累计为一期功能完成度。
