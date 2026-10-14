# DeepTMHMM Academic 1.0 开发禁网证据

说明与限制见 [专项](../../../../docs/project/phase1/PHASE1_REAL_W1_DEEPTMHMM_OFFLINE.md)，当前进度见
[STATUS](../../../../docs/project/STATUS.md)。本批记录用户提供学术包的实际运行，不覆盖前序 SDK 负测。

- [包接收记录](package_receipt.json)：用户提供 ZIP 的身份、41 个包文件及 22 份专家原件 hash；NOT_RUN_AT_RECEIPT 是接收时点。
- [候选版本与参数](method_summary.json)：Academic 1.0、8 个模型资产 hash、固定镜像、依赖和原代码参数。
- [环境构建](environment/build.json)：固定 Python 基础镜像、原 requirements、安装报告与实际镜像 ID。
- [执行目录](runs)：short/coverage/x-residue 为真实成功推理；empty 是加载前输入拒绝。完整 stdout/stderr、容器检查、资源与原始文件均保留。
- [原始核对](raw_audit.json)：三行、区段、概率、P/B 守卫预期及重复输入一致性；不包含科学准确率或生产适配器验收。
- [只读检查器](verify_evidence.py)：校验 manifest、原件、执行环境和重新解析结果；加 `--assets` 复算 var 内完整包文件。

`package_sources/` 为软件原件副本，包括许可；大模型保存在接收记录指明的 var 目录。
`code_snapshot/` 保存本次新增测试及文档检查器。`receive_package.py`、`build_environment.py`、`run_offline.py`、
`audit_raw.py`、`seal_manifest.py` 是本批一次性制备/执行入口，均不覆盖既有接收、执行或审计结果。
原始 Markdown 报告中的容器内链接按工具实际输出保留。权重与推理原程序未修改；生产为 NOT_DEPLOYED。
