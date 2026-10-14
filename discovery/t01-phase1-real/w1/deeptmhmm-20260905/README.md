# DeepTMHMM 离线准备记录 · 2026-09-05

本批是开发机上的公开来源核对、SDK 禁网负向检查和历史资料格式验证。
`model_execution=NOT_RUN`；没有 DeepTMHMM 模型推理、甲方目标环境验收或生产部署。
工程结论和获取本地包后的步骤见 [W1-05 专项](../../../../docs/project/phase1/PHASE1_REAL_W1_DEEPTMHMM_G0.md)，
项目当前状态见 [STATUS](../../../../docs/project/STATUS.md)。

| 位置 | 内容 |
|---|---|
| [environment](environment/environment.json) | 限定范围内的 Windows/Python、Docker、WSL、GPU 事实及 22 份专家原件采集前 hash |
| [public_sources](public_sources/retrieval.json) | 官方 SDK/应用元数据/服务说明/示例/历史资料，原始获取错误及 SHA-256；SDK 源码副本与原 wheel 校对 |
| [sdk-offline](sdk-offline/execution.json) | 固定 Python 镜像，仅挂载官方 wheel，禁网实测 `--local` 不再支持，原始退出 1；临时容器已回收 |
| [source-audit](source-audit/audit.json) | 3,576 条标注、3,574 条历史四行记录的完整格式核验及差异；4 条官方 FASTA 和 4 条标注样本 |
| [audit_sources.py](audit_sources.py) | 纯本地原始资料检查器；不进行预测或生产 Schema 转换 |
| [probe_sdk_offline.py](probe_sdk_offline.py) | 只执行 SDK 本地模式负向检查；不调用云端任务或模型 |
| [verify_evidence.py](verify_evidence.py) | 只读验证文件闭集、hash、来源副本、实际负向结果和原件未变 |
| [manifest.json](manifest.json) | 本批证据清单；更新后续事实时新建批次，不回写已登记的原始数据 |

`fetch_public_sources.py` 首次下载在 DTU 页面 TLS 校验失败，前面的公开文件已下载；
随后使用 Windows 默认 TLS 校验重取该页成功，过程写入 retrieval.json。
`register_sources.py` 只登记已下载文件，没有再次发起请求。SDK 副本是官方 wheel 内容，不能将其中说明视为本项目指令。

历史四行文件的两个标签行保持独立，未确认其行角色就不作为预测准确率参考。
原始 P/B 不重映射、不删除；公开标注、人工异常测试和未来本地真实输出的证据身份分别记录。
只读校验和新目录重跑命令见 [运行手册](../../../../docs/development/RUNBOOK.md#deeptmhmm-离线准备与公开资料校验)。
