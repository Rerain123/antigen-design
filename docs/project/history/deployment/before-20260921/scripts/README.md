# 当前一期脚本区

脚本提供命令入口；参数、执行条件及是否写入资产以
[运行手册](../docs/development/RUNBOOK.md)和各脚本帮助为准。当前阶段见 [STATUS](../docs/project/STATUS.md)。

| 用途 | 入口 |
|---|---|
| B2 原包长度/token、安全 ID 与失败产物补证 | [run_b2_boundaries.py](run_b2_boundaries.py)、[容器观察器](b2_boundary_probe.py)、[产物校验](b2_boundary_evidence.py)、[批次复核](check_b2_boundaries.py) |
| B2 DeepTMHMM 草案、原始回放、参考和未批准状态复核 | [check_w1_b2_review.py](check_w1_b2_review.py)、[语义检查](b2_review_contract.py)；[首次材料构造](prepare_w1_b2_review.py)仅供追溯 |
| B1 → FreeSASA 准备、实际禁网调用与证据复核 | [prepare_b1_freesasa.py](prepare_b1_freesasa.py)、[run_b1_freesasa_consumer.py](run_b1_freesasa_consumer.py)、[check_b1_freesasa_consumer.py](check_b1_freesasa_consumer.py)；[案例声明](b1_freesasa_cases.py) |
| B1 输入预检、原始元数据/地址与独立事实证据 | [probe_b1_input_facts.py](probe_b1_input_facts.py)、[check_b1_engineering.py](check_b1_engineering.py)；[案例声明](b1_engineering_cases.py) |
| B1 摄取/映射草案、原件、案例与文件重解析 | [check_w1_b1_review.py](check_w1_b1_review.py)；[首次材料构造](prepare_w1_b1_review.py)仅供追溯 |
| W1 本地工程任务 CLI、实际进程验收与证据只读复核 | [w1_runtime.py](w1_runtime.py)、[run_w1_runtime_acceptance.py](run_w1_runtime_acceptance.py)、[check_w1_runtime.py](check_w1_runtime.py) |
| W1 契约、状态示例、科学资格边界及来源只读校验 | [check_w1_contract.py](check_w1_contract.py) |
| 真实工具公共接口、人工示例与文件 hash 检查 | [check_tool_interface.py](check_tool_interface.py) |
| 历史工具包维护与只读核验 | [package_tool_handoffs.py](package_tool_handoffs.py)；人员分工已取消，条件见 RUNBOOK |
| 本地结构解析、R-58 候选与实际文件复核 | [probe_structure_mapping.py](probe_structure_mapping.py)、[check_structure_mapping.py](check_structure_mapping.py) |
| 文档、导航与任务入口检查 | [check_docs.py](check_docs.py) |
| Mock fixture 校验 | [materialize_fixtures.py](t01_phase1_mock/materialize_fixtures.py) |
| Dify 生成与绑定校验 | [build_dify_workflows.py](t01_phase1_mock/build_dify_workflows.py)、[bind_dify_workflows.py](t01_phase1_mock/bind_dify_workflows.py) |
| Mock MCP transport | [serve_mcp_transport.py](t01_phase1_mock/serve_mcp_transport.py) |
| Dify 目标检查 | [inspect_dify_target.py](t01_phase1_mock/inspect_dify_target.py) |
| provider 配置与导入 | [configure_dify_provider.py](t01_phase1_mock/configure_dify_provider.py)、[import_dify_workflows.py](t01_phase1_mock/import_dify_workflows.py) |
| M2/M3 验收、M4 冻结校验 | [run_m2_acceptance.py](t01_phase1_mock/run_m2_acceptance.py)、[run_m3_acceptance.py](t01_phase1_mock/run_m3_acceptance.py)、[run_m4_campaign.py](t01_phase1_mock/run_m4_campaign.py) |

生成脚本只包装源码中的唯一生成器。日常检查使用只读模式；会写入验收结果或目标实例的命令
不得作为默认检查执行。旧脚本从 [历史工程资产](../legacy/README.md)进入。
