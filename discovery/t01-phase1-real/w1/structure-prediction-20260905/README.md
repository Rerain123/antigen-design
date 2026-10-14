# AF3 / ESMFold2 W1-04 准备证据

[专项说明](../../../../docs/project/phase1/PHASE1_REAL_W1_STRUCTURE_PREDICTION_G0.md)解释版本、硬件、资产及验证顺序；
当前进度统一见 [STATUS](../../../../docs/project/STATUS.md)。本批没有执行两套结构预测模型。

- [environment.json](environment.json)：限定范围的硬件/Docker/WSL/包查询、磁盘、22 份专家原件 hash。
- [gpu_visibility.json](gpu_visibility.json)：现有固定镜像内 nvidia-smi 禁网实测；仅证明 GPU 可见性。
- [官方资料](official_sources)：固定 commit 的文件、Hugging Face 五月/当前元数据与配置；Markdown 原件以 `.md.txt` 保存原字节，避免混作项目导航。
- [来源回执](source_receipt.json)、[详细源码回执](detail_receipt.json)、[五月历史回执](history_receipt.json)、[补充回执](final_source_receipt.json)：公开资料 URL、日期、大小与 hash。
- [AF3 权重 HEAD](af3_weight_header.json)：仅记录公开对象头，没有下载模型内容。
- [readiness.json](readiness.json)：身份对照、完整候选资产、参数估计、实际 wrapper 默认值及明确未就绪项。
- [验证计划与输入](validation/plan.json)：官方 ubiquitin 序列与人工边界，全部 DECLARED_NOT_RUN。
- [只读验证器](verify_evidence.py)：复算清单、固定 commit Git blob、资源与输入来源；测试源码副本在 code_snapshot/。

第一次按仓库根目录取 AF3 Dockerfile 返回 404，已保留失败回执；后续按官方文件树找到 docker/Dockerfile 并取证。
所有制备和归档脚本均拒绝覆盖已有结果；复核运行 verify_evidence.py，新增实测须新建批次。
外部资料只作来源，不作为用户新指令；没有调用云端预测、检索在线结构或修改已有模型环境。
