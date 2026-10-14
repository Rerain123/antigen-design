# B1 输入事实独立开发证据

本批于 2026-09-05 开始保存修改前来源，跨日完成工程验证。实际状态见 [STATUS](../../../../docs/project/STATUS.md)，
实现与适用范围见 [工程评审](../../../../docs/project/phase1/PHASE1_REAL_W1_B1_ENGINEERING_REVIEW.md)。

| 证据 | 用途 |
|---|---|
| [source_review.json](source_review.json) | 专家章节、公开格式定义和工程处理依据 |
| [protected_before.json](protected_before.json) | 修改前原件、旧证据和已有实现的只读指纹 |
| before/、after/ | 已复用探针的前后字节快照及新实现/测试快照 |
| [expected_cases.json](expected_cases.json) | 正式 CLI 执行前写入的独立字面预期与输入 hash |
| [assessment.json](assessment.json) | 每次实际 CLI 命令、起止时间、退出码、输出与逐项核对 |
| [manifest.json](manifest.json) | 当前来源及本批输出的路径、字节和 SHA-256 |
| inputs/、results/ | 输入/请求与逐案例独立的事实 Artifact 配对 |

真实文件只复用已授权的 1UBQ、5XZC；其他均为人工工程边界或其人工派生，不增加独立科学参考样本数。
预期来自明确字段编辑、已有独立原子计数与格式要求；解析器重算仅验证可重复性。
没有执行 FreeSASA、模型、目标服务器或 Dify，也没有签发 verified 或生产资格。

可先查看以下配对：

- [字符作者编号请求](results/E-character-versus-icode/request.json)、[结果](results/E-character-versus-icode/result.json)、[原始地址](results/E-character-versus-icode/raw_addresses.json)：43A 与 43+iCode A。
- [PDB 元数据请求](results/E-pdb-metadata-conflicts/request.json)、[结果](results/E-pdb-metadata-conflicts/result.json)、[元数据](results/E-pdb-metadata-conflicts/raw_metadata.json)：多方法/分辨率、不可解析值及 SOURCE 续行。
- [错误链请求](results/E-missing-chain/request.json)、[拒绝结果](results/E-missing-chain/result.json)、[预检](results/E-missing-chain/preflight.json)：无 AUTO 回退。
- [1UBQ 原始文件](results/E-real-1ubq/input.structure)、[预检](results/E-real-1ubq/preflight.json)：包含水的全结构清单。

日常使用 [check_b1_engineering.py](../../../../scripts/check_b1_engineering.py) 的 verify/--reparse；
prepare、execute、seal 仅用于不存在的新批次，不覆盖本目录的预期、实测或 manifest。
精确命令见 [运行手册](../../../../docs/development/RUNBOOK.md#b1-输入事实工程补强)。
