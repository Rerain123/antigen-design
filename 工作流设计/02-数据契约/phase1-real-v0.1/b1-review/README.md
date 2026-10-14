# B1 摄取与映射请求/结果草案

本目录服务 [B1 限定评审](../../../../docs/project/phase1/PHASE1_REAL_W1_B1_REVIEW.md)，
使用 0.1.0，状态为 DRAFT_REVIEW_ONLY。当前阶段见 [STATUS](../../../../docs/project/STATUS.md)。

| 文件 | 用途 |
|---|---|
| [request.schema.json](request.schema.json) | 两工具共享输入字段，映射额外需要前序 inventory_artifact |
| [result.schema.json](result.schema.json) | parsed/candidate/rejected、不可消费状态、文件及请求字节绑定 |
| [摄取请求](examples/ingest-request.json)、[摄取结果](examples/ingest-result.json) | 结构文件到全结构清单的人工配对示例 |
| [映射请求](examples/map-request.json)、[映射结果](examples/map-result.json) | 前序清单到候选映射文件的人工配对示例 |
| [example_artifacts.json](example_artifacts.json) | 人工身份指向实际工程夹具文件及其 hash；不是 runtime 已签发的任务 |
| [source_manifest.json](source_manifest.json) | 专家、用户决定、旧格式和已有输入证据来源 |

ArtifactRef 字段沿用父级 job Schema；映射文件沿用公共 mapping Schema，不改历史包。
这两种输出都是中间记录，不直接填专家最终 CandidateRecord.structure；其 source/confidence 仍须适用来源及 S-09 评审。
request 格式不能表达空结构预测分支：无结构由 N01 分给后续 AF3/ESMFold2，不能隐式检索。
host_species 不由结构头部覆盖；source_declaration 是待核对用户声明。

Schema 形状检查之外，还须校验序列/hash、run/job/attempt、原始请求字节、输入输出分离、声明/检测格式、
清单对应的结构、映射的模型/链/逐位数组以及实际文件字节。对应检查入口为
[check_w1_b1_review.py](../../../../scripts/check_w1_b1_review.py)。
检查通过仅说明评审材料一致；生产运行层仍拒绝两个科学工具，不能将示例拿去消除资格守卫。
