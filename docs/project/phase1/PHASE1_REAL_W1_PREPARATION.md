# W1-01/02 环境与样本登记

本页承接 [W1 backlog](PHASE1_REAL_W1_BACKLOG.md)的环境、资产和样本准备，供主开发直接推进。
当前进度、分工时点与下一步统一见 [STATUS](../STATUS.md)；逐项事实来自下列具名批次。

## 环境与资产

[2026-09-05 本地采集记录](../../../discovery/t01-phase1-real/w1/w1-preparation-20260905/README.md)
只检查当前开发进程、Python 包元数据和 PATH。开发机不自动等同于甲方目标服务器。
“未找到”只对检查范围成立；容器、WSL、其他 Python 环境及独立“工具部署”项目均未盘点。
这是首批采集范围；后续 Docker/WSL/GPU 的限定核验另见 [DeepTMHMM 专项](PHASE1_REAL_W1_DEEPTMHMM_G0.md)和
[结构预测准备](PHASE1_REAL_W1_STRUCTURE_PREDICTION_G0.md)，不回写首批记录。

| 登记项 | 事实或待补信息 | 依据与完成条件 |
|---|---|---|
| 本地开发 profile | `w1-local-development-windows`；Windows、Python 3.11.15、Biopython 1.88、NumPy 2.4.6、jsonschema 4.26.0 | [环境记录](../../../discovery/t01-phase1-real/w1/w1-preparation-20260905/facts/environment.json)；版本查到不等于全部功能可运行，解析执行另见 R-58 证据 |
| 甲方目标 profile / D01 | 用户确认服务器容量可满足 AF3/ESMFold2；开发继续在本机。主机、OS/GPU/驱动、存储与访问范围仍待具名登记 | [用户记录](../sources/PHASE1_W1_SERVER_CAPACITY_20260905.json)；目标 G0 前提供可核验 profile，不在仓库保存凭据 |
| 本地解析 / D04 | 当前开发环境已有严格解析和重解析产物 | [R-58 专项](PHASE1_REAL_W1_R58_MAPPING.md)；目标环境仍须复跑 |
| FreeSASA / D04 | 首批本机 Python/PATH 未找到；后续已在独立本地 Docker 镜像中探测 2.2.1 | [原始工具验证](PHASE1_REAL_W1_FREESASA_G0.md)记录真实产物、默认参数和禁网运行；甲方目标版本/配置/许可与生产可用性仍待核实 |
| AF3、ESMFold2 / D02 | 官方仓库、许可文本、源码候选及 ESMFold2 五月 checkpoint 已定位；权重尚未提供，服务器容量已有用户确认 | [结构预测准备](PHASE1_REAL_W1_STRUCTURE_PREDICTION_G0.md)；仍需具体目标 profile、AF3 使用适用性、本地资产 hash、依赖和禁网输出；容量确认不等于模型已安装 |
| DeepTMHMM / D02、D04 | 用户提供 Academic 1.0 学术包；原依赖 Docker 镜像、8 个模型资产 hash 和原代码 CPU 禁网输出已登记；网页应用 1.0.57 保持单独身份 | [学术包实测](PHASE1_REAL_W1_DEEPTMHMM_OFFLINE.md)；目标环境、科学参考与签收仍须补齐；GPU 与长序列分块未验证 |
| AF3 数据 / D03 | 用户回复暂无；官方全套数据下载约 252 GB、解压约 630 GB，本机磁盘缺充足余量 | 登记本地数据库/索引，或实测版本支持的真实预计算 MSA/模板；记录来源、hash、路径，不用空数据或联网回退充数 |
| 负责人 / D08 | 用户担任主开发；本地工程采集由本任务执行；甲方环境接口人、目标工具实际执行人、科学验收人待具名 | 主开发统一推进；取消工具分工不代替目标环境职责登记或科学签收 |

`nvidia-smi`、Docker、WSL 在首批仅检查命令路径；后续用户启动 Docker，实际引擎与 FreeSASA 独立记录在上述专项。
首批环境 JSON 保留当时事实；不据此声明 GPU 或其他模型可用。
工具就绪判断还需要真实输入输出、运行资源和离线证据。
后续结构预测批次已确认 Docker 可见 12 GB 级 GPU；宿主约 31.2 GiB RAM、Docker 约 15.2 GiB。
这只证明资源事实与 GPU 可见性，未验证 AF3/ESMFold2 的框架内核或模型；详细容量计算留在专项证据。

## G0 输入与分支清单

用户已说明暂无甲方真实测试用例，并授权从冻结历史寻找开发输入。
已复用文件的来源、原始字节及规范化序列 hash 见
[样本来源清单](../../../tests/fixtures/structure_mapping/real/SOURCE_MANIFEST.json)。
其用途为本地开发参考；目标环境使用范围和完整请求中的 `host_species` 仍须明确，不由蛋白名猜宿主。

| 样本或分支 | 可用于什么 | 投入后续验证前需补什么 |
|---|---|---|
| 1UBQ mmCIF + 独立 FASTA | 本地解析、完整序列/编号对照；FreeSASA 原始结果摸底的候选输入 | 确认运行环境及 MODEL/链/水分子/参数上下文；科学消费前完成适用映射评审 |
| 5XZC mmCIF + TP53 FASTA | 多条候选链、重复位置和仅 Cα 输入的限制案例 | 固定其歧义与禁止自动交接预期；不用于正常全原子 SASA 验收 |
| 人工 PDB/mmCIF + ARG FASTA | partial、插入码、auth/label 编号、null 的格式边界 | 保持人工证据身份；不能替代真实结构上的科学数值参考 |
| 其他 R-58 工程边界 | 多 MODEL、altloc、非标准残基、损坏文件、篡改地址的单测 | 现有测试见样本索引；G0 正式运行需要把适用输入单独落盘并登记 hash |
| N01 完整请求 | 宿主、序列支持域、8/9/29/30aa 和异常输入 | 补齐具名案例；已有短肽规则按 backlog 归并，支持域缺口按 OI-023 处理 |
| AF3/ESMFold2 | 已备官方 76 aa ubiquitin、AF3 全管线 JSON 和人工长度边界；5 组计划均未执行 | [原始验证计划](../../../discovery/t01-phase1-real/w1/structure-prediction-20260905/validation/plan.json)；补齐资源/资产后执行；成功、故障注入与科学参考分开登记 |
| DeepTMHMM | 包内示例、4 条官方 FASTA、4 条标注输入已实际预测；另有重复短输入、人工 X 和空输入检查 | [原始输出核对](PHASE1_REAL_W1_DEEPTMHMM_OFFLINE.md#3-实际执行结果)；仍须独立科学参考和目标复现，历史标注不充当当前运行结果或独立留出 |
| S-09、FreeSASA | 实验来源/边界、预测置信度/null、SASA→RSA 与条件跳过 | 参数、独立参考及候选容差见 [先行决定](PHASE1_REAL_W1_FREESASA_S09_DECISION.md)；算法确认、留出/映射/null 样本及 G76 出域核验仍须补齐 |

详细人工样本与测试入口见 [样本索引](../../../tests/fixtures/structure_mapping/README.md)，
W1 全覆盖要求见 [backlog 验收表](PHASE1_REAL_W1_BACKLOG.md)。

## 本批样本核对与使用限制

[原始字段核对记录](../../../discovery/t01-phase1-real/w1/w1-preparation-20260905/facts/sample_audit.json)
直接读取 mmCIF 的实体序列、编号表和原子列，没有调用新映射生成算法来充当自己的预期结果。
它仍使用同一沉积文件及 Biopython 词法解析，属于补充工程对照，不是独立科学金标准。

- 1UBQ：实体序列与 FASTA 一致；76 个位置在编号表、实际坐标和已有候选映射之间一致。
  文件含 602 个聚合物原子、58 个水原子；76 个残基均有 N/CA/C/O，另有侧链原子。
  部分聚合物原子占有率低于 1；“有侧链”不等于全原子完整性已验收，缺原子比例未计算。
- 5XZC：1547 个原子全部为 Cα；作者链 A 有 619 个残基，B/C/D/E 各 232 个。
  该事实支持其限制案例用途，不解决设计链和序列位置的科学歧义。

本批没有修改映射状态或签发 verified，没有计算 RSA、S-09 质量档位或新的接受阈值。
后续 [FreeSASA 探测](PHASE1_REAL_W1_FREESASA_G0.md)补充原始面积、格式和非有限值事实；
[S-09 案例](PHASE1_REAL_W1_S09_CASES.json)承接已有规则与待裁决输入，不把草案记为已执行。

## G1 验收依据补齐要求

每个正式用例记录：输入与 hash、来源/使用范围、工具和参数版本、适用规则、原始预期与独立来源、
断言/科学容差、实际结果、执行人和科学验收人。离散地址对照采用明确一致性断言；数值容差不由工程猜测。
同一新实现的输出不能直接成为唯一金标准。

本批完成环境和样本的局部事实采集。目标 profile、完整 G0 样本集、数值参考、科学容差及具名签收
仍按 W1-01/02 完成标准补齐；部分准备结果不代表 W1-01/02 全部完成或 G0/G1 放行。
