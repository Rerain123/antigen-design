# W1-04：AF3 / ESMFold2 身份、资源与原始验证准备

本专项处理 N01 无用户结构时的本地预测准备。任务进度见 [STATUS](../STATUS.md)，完整依赖见
[W1 backlog](PHASE1_REAL_W1_BACKLOG.md)。来源、机器事实和输入文件见
[独立证据批次](../../../discovery/t01-phase1-real/w1/structure-prediction-20260905/README.md)。

## 1. 本轮结论

用户已回复“暂无”，没有提供 AF3 权重、本地 MSA 数据、ESMFold2 权重或服务器资料；
[原话记录](../sources/PHASE1_W1_STRUCTURE_ASSET_AVAILABILITY_20260905.json)保留调查范围。
这不等于全盘扫描，也不推断甲方没有服务器。

两套工具的官方身份和本地执行入口已定位；本机 Docker GPU 可见性检查通过。
但当前开发机不适合作为两套工具完整默认配置的验收环境：AF3 缺权重和本地数据，内存/存储余量不足；
ESMFold2 默认同时加载折叠模型与 ESMC-6B，参数占用估计已超过本机显存。
本轮交付为**可行性结论、逐项资产清单、参数来源和待执行验证输入**；两模型均为 NOT_RUN，生产 NOT_DEPLOYED。

## 2. 专家要求与工具身份

依据 [结构链 ToolSpec §1/2b/3/7](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md)、
[SOP S-08](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)、
[SKILL R-03/04/05](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md)及
[环境清单 C11/C12](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/一期实施环境清单_v10.5.md)：

| 工具 | 原件要求 | 本轮定位 |
|---|---|---|
| C12 AlphaFold3 | 未锁具体软件版本；部署时固定版本/参数；WT 默认使用；5 个 diffusion 样本 | Google DeepMind 官方实现，源码候选固定到 `c0f97eda2f1f482fd94d3a38bece18c7069b4a5c`，未安装或部署 |
| C11 ESMFold2 | CZ Biohub 2026-05 版本；用于 R-04 场景及规定的长序列降级 | Biohub 官方 ESMFold2 家族已证实存在；标准版与 Fast 是两个不同 checkpoint，需分别记录 |

[2026-09-03 用户决定](../sources/PHASE1_NODE01_OFFLINE_SOURCE_20260903.json)仍优先：保留本地 AF3/ESMFold2，
不恢复 S-07、RCSB/AFDB 查询或在线预测回退。本地 AF3 的遗传数据库/模板管线是模型输入准备，
不等于重新启用 S-07 在线结构检索；数据资产需走 D03 登记。

### AF3 官方分发与许可

当前固定 commit 的 [官方 README](https://github.com/google-deepmind/alphafold3/blob/c0f97eda2f1f482fd94d3a38bece18c7069b4a5c/README.md)
已提供 Google 直接下载模型参数的链接，不应沿用旧的“必须先填申请表”描述。
本轮只对该对象发出 HEAD 请求，返回 200、压缩大小约 1.02 GB；**没有下载权重**，HEAD/ETag 也不是本地 SHA-256 验证。

源码使用 Apache-2.0；权重与输出另受
[模型条款](https://github.com/google-deepmind/alphafold3/blob/c0f97eda2f1f482fd94d3a38bece18c7069b4a5c/WEIGHTS_TERMS_OF_USE.md)
约束，包括非商业机构及其用途要求、须直接从 Google 获取等。
已明确的学术自用保留为用户用途事实；AF3 的机构/项目适用性尚无单独记录，不从下载链接公开推断授权就绪。
本轮未代填表、提交申请、接受协议或向外发送序列。

### ESMFold2 五月发布身份

[Biohub 官方模型卡](https://huggingface.co/biohub/ESMFold2)及 [官方代码](https://github.com/Biohub/esm)
提供本地推理和 MIT 许可来源；没有使用旧 fair-esm/ESMFold v1、ESM3 或第三方同名项目充数。

| 对象 | 五月候选 revision | 与当前公开记录的比较 |
|---|---|---|
| 标准 ESMFold2 | `e1e189d0f5fb70c2693da2332eca4443c0ccccd6` | 折叠权重 SHA-256、配置相同；MSA 编码器启用 |
| ESMFold2-Fast | `0438ea0d932a314950665e0b4d0af4322ae88250` | 折叠权重 SHA-256、配置相同；MSA 编码器未启用 |
| CCD 字典 | 标准版同一五月快照 | 与当前记录的大小、SHA-256 相同；Fast 也需要单独准备该资产 |

这是远端元数据对照，不是已下载权重校验，也不证明新旧运行时数值等价。标准版与 Fast 的权重互不相同；
官方教程提醒 Fast 可能直接忽略提供的 MSA，不能仅因名字或速度把两者互换。
验证计划先列**标准版为待试候选**，Fast 保留为单独比较选项，不冻结生产选择。

五月代码快照 `b6b0e8815dc3174a9fe9afd36b222aea57d536c5` 为 esm 3.3.0，依赖 Biohub transformers 分支；
当前候选代码 `bf343ba264b650dff7a073643725f9aaa1fdbe8d` 为 esm 3.4.1，要求 Python ≥3.12、
PyTorch ≥2.11/<2.12、transformers ≥4.57.6/<5，并含 Linux CUDA 13 相关依赖。
这些与项目 Python 3.11、DeepTMHMM Python 3.8 环境不同，须独立安装；不得把软件包版本当作模型版本。

## 3. 本机能承担什么

只读盘点覆盖项目当前 Python/PATH、WSL Ubuntu 包元数据、Docker 镜像清单和具名硬件命令。
未查独立“工具部署”项目、无关容器内部或整块磁盘。相关包/命令在这些检查范围内未发现；用户资产回复另行记录。

| 项目 | 本机实测 | 对验证的影响 |
|---|---|---|
| GPU | RTX 5070 Ti Laptop，12,227 MiB，驱动 591.74，Compute Capability 12.0 | 禁网临时容器能运行 nvidia-smi；不证明 JAX/PyTorch 内核及科学数值兼容 |
| CPU / 内存 | 16 核/32 线程，宿主可见内存约 31.2 GiB，Docker 约 15.2 GiB | 不能照搬 AF3 官方至少 64 GB RAM 的完整管线配置 |
| 存储 | D 盘剩余约 643 GB（十进制），C 盘剩余约 96 GB | AF3 全套数据解压约 630 GB，D 盘仅余约 13 GB，缺工作区、镜像和安全余量 |
| ESMFold2 参数估计 | 标准版约 12.71 GiB，Fast 约 12.53 GiB；尚不含激活、缓存和分配器 | 已超过本机约 11.94 GiB 总显存；标准同时驻留配置不适用 |

ESMFold2 估计由官方参数数目按源码默认 ESMC bf16、折叠模型 float32 计算；它是容量估算，**不是实际 OOM 记录**。
offload/分阶段或其他精度可以另做专项验证，但没有因此承诺本机能跑，更不静默降低精度或换模型。

AF3 的 [安装说明](https://github.com/google-deepmind/alphafold3/blob/c0f97eda2f1f482fd94d3a38bece18c7069b4a5c/docs/installation.md)
以 Linux、A100/H100 80 GB 的大输入实测为依据；80 GB 并非所有短序列的强制最低显存。
其 [两阶段入口](https://github.com/google-deepmind/alphafold3/blob/c0f97eda2f1f482fd94d3a38bece18c7069b4a5c/README.md)
允许本地 CPU 准备 MSA/模板，再由 GPU 推理；已有真实预计算输入时，推理机可不存完整数据库。
不能用空 MSA 和空模板替代既定管线，并宣称完整能力已验证。

建议优先盘点已有 Linux 服务器。若能统一使用 A100/H100 80 GB，可直接接近 AF3 官方验证环境；
系统内存与 SSD 应在官方 64 GB/约 1 TB 基础上留余量，例如 128 GB RAM、2 TB SSD 可作为工程容量草案，
不是新增科学硬门槛或采购决定。实际容量仍按序列长度、并发和是否拆分数据管线确定。

## 4. 需要准备的资产

| 资产 | 数量/规模与来源 | 当前缺口 |
|---|---|---|
| AF3 源码及依赖镜像 | 固定官方 commit，Dockerfile/uv.lock 已保存供审阅 | 尚未构建 AF3 镜像；目标 GPU 内核兼容未验证 |
| AF3 模型权重 | Google 官方压缩对象约 1.02 GB | 使用适用性记录、下载、解压与本地 hash 尚缺 |
| AF3 MSA/模板数据 | 官方脚本含 MGnify、BFD、UniRef90、UniProt、PDB seqres/mmCIF，以及 RNA 数据 | 全套下载约 252 GB、解压约 630 GB；也可登记真实本地预计算 MSA/模板；本轮均暂无 |
| ESMFold2 标准版 | 折叠权重约 0.94 GB + config | 只有远端身份/大小/hash，未下载 |
| ESMFold2-Fast | 独立折叠权重约 0.76 GB + config | 仅作另一候选，不默认替代标准版 |
| ESMC-6B | 6 个权重分片合计约 25.41 GB，另需索引/config | 两个折叠变体共同依赖，不能遗漏 |
| CCD 字典 | `ccd.pkl` 约 0.417 GB | 准备为批准的本地资产；运行时显式路径和 hash |
| ESMFold2 完整候选环境 | 固定代码、Python/torch/依赖、折叠权重/ESMC/CCD 组合 | 标准版主要资产约 26.76 GB；Fast 组合约 26.58 GB，均不含环境和工作区 |

所有远端 hash、revision 和字节数在 [readiness.json](../../../discovery/t01-phase1-real/w1/structure-prediction-20260905/readiness.json)，
`local_bytes_verified=false` 明确表示还没有对应本地文件校验。没有启动大型权重/数据库下载。
后续准备必须覆盖嵌套下载：ESMFold2 会继续加载 config.esmc_id 指向的语言模型，CCD 默认也可能访问 Hugging Face。
部署时使用本地 checkpoint、显式 `ESMCFOLD_CCD_PATH`、固定缓存及离线开关，实际推理加 `--network none`。

## 5. 原始输出与参数核验要点

AF3 应保存每个 seed/sample 的 mmCIF、confidences、summary_confidences、排名表和实际数据管线输入。
官方顶层样本按 ranking_score 排序，项目单体按 pTM 选择；两者要比对，并确认项目入选样本无碰撞。
项目按 Cα 提取逐残基 pLDDT，再由 0–100 归一化；不能直接取全原子平均。
输出定义见 [官方输出说明](https://github.com/google-deepmind/alphafold3/blob/c0f97eda2f1f482fd94d3a38bece18c7069b4a5c/docs/output.md)。

ESMFold2 当前源码的原始 pLDDT 位于 [0,1]，返回对象含 pTM，官方教程可以输出 mmCIF。
导出结构的 B-factor 是另一个载体，必须分别核验缩放；不得根据一批数值恰好小于 1 就猜原生标度，或重复除以 100。
这些是源码/教程事实，真正的版本能力确认仍要有实际输出。

当前 wrapper 的默认参数为 **20 loops、200 sampling steps、1 diffusion sample、lm_dropout=0.3**，
与 README 示例 20/100、教程 10/100、checkpoint 配置中的其他默认值不相同。
后续候选试跑按实际 wrapper 明确所有参数，并记录固定种子；这些工程试跑参数尚未得到 G1 科学签收。
不得把另一个入口的配置默认值写成实际调用参数。

## 6. 已准备的验证与后续顺序

[validation/plan.json](../../../discovery/t01-phase1-real/w1/structure-prediction-20260905/validation/plan.json)
包含 5 组明确标为 DECLARED_NOT_RUN 的案例：AF3 短序列、ESMFold2 短序列、真实 MSA 两阶段复用、错误产物、长序列边界。
正常输入为 Biohub 官方教程中的 76 aa ubiquitin，与已登记 1UBQ 序列逐字相同，保存了来源和 hash。
AF3 JSON 保持 MSA/模板字段未设置，以便真实本地管线准备；没有伪造预计算 MSA 或预测结构。
999/1000/1500/1501 aa 是人工长度边界输入，只用于未来分支测试，不是科学性能参考。

执行顺序：

1. 登记具名服务器 profile、运行目录、资源和使用范围；确认 AF3 许可适用性。
2. 固定两引擎代码/变体/依赖及全部本地资产；准备 AF3 数据或真实预计算输入。
3. 先在独立禁网环境运行 76 aa 输入，记录全部结果、耗时、峰值资源和失败原因。
4. 用真实原始输出确认标度、逐位映射、样本选择及错误守卫，再扩展长输入与独立科学参考。
5. 将 W1-03～06 的事实汇入 W1-07，完成 W1-08 评审后才实现生产适配器。

开发超时不能被冒充为原件规定的 >2h 超时；测试失败路由不必主动耗尽显存或等待两小时。
资源未就绪期间，主开发可继续 W1-07 已有结构/DeepTMHMM/FreeSASA 的契约草案及定点规则收敛。
本轮不把 W1-04 标为完成，也不以服务器缺口阻断整个 W1。

只读复核命令见 [运行手册](../../development/RUNBOOK.md#结构预测准备证据复核)；项目级检查见
[本轮验证记录](PHASE1_REAL_W1_STRUCTURE_PREDICTION_VERIFICATION.json)。
