# W1-05：DeepTMHMM 离线准备与原始资料验证

本页记录开发机上的来源核对、客户端禁网检查和公开资料解析。当前任务进度见 [STATUS](../STATUS.md)，
任务依赖见 [W1 backlog](PHASE1_REAL_W1_BACKLOG.md)。本批证据见
[DeepTMHMM 记录](../../../discovery/t01-phase1-real/w1/deeptmhmm-20260905/README.md)。

本页以下保留收到学术包之前的准备事实。收到包后的版本核对、真实推理与原始产物见
[Academic 1.0 禁网专项](PHASE1_REAL_W1_DEEPTMHMM_OFFLINE.md)，不能将本页 NOT_RUN 延伸为后续批次状态。

## 1. 这次确认了什么

用户已说明“学术自用”，[原话记录](../sources/PHASE1_W1_DEEPTMHMM_USAGE_20260905.json)保留使用范围。
官方当前要求学术非商业用户申请本地软件包。用途已明确，下一项缺的是软件包和模型资产。

| 对象 | 实际证据 | 能得出的结论 |
|---|---|---|
| 开发机 | Docker Linux 引擎；RTX 5070 Ti Laptop、约 12 GiB 显存；Docker 分配约 15.2 GiB 内存 | 可用于后续环境尝试；尚未验证模型或 GPU 容器兼容性，不是甲方目标 profile |
| 本地已查范围 | 当前项目 Python/PATH、Docker 镜像清单、WSL Ubuntu Python 包元数据/命令 | 未发现 DeepTMHMM 包或对应镜像；未全盘扫描，也未将独立“工具部署”项目纳入验收 |
| SDK | PyPI 官方 `pybiolib 1.4.457`，wheel SHA-256 与 PyPI 一致 | 只是客户端版本，不是模型版本 |
| 应用元数据 | 官方匿名 API 返回 `DTU/DeepTMHMM:1.0.57`；页面提供本地包申请入口 | 是当日公开应用标识；未取得本地包，不能填写为已部署版本/权重 hash |
| 禁网执行 | 固定 Python 镜像中安装公开 wheel；`--network none`；仅 `lo` 网卡；`biolib run --local DTU/DeepTMHMM:1.0.57` 退出 1 | 明确报本地模式不再支持；这是 SDK 负向检查，不是 DeepTMHMM 模型失败或推理结果 |
| 公开资料 | 官方页面的 4 条 FASTA；官方应用直链的 3,576 条标注与 3,574 条历史交叉验证输出 | 原始字节、长度、标签与样本来源已可追踪；不能替代新安装模型的实际输出或科学验收 |

完整日志、时间、镜像 ID 和命令见
[SDK execution.json](../../../discovery/t01-phase1-real/w1/deeptmhmm-20260905/sdk-offline/execution.json)。
本次使用临时专用容器，执行后已移除；没有修改已有 Dify 容器或项目依赖。

## 2. 官方入口与专家原件的差异

依据 [A5 ToolSpec §1/2/4/7](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_A5_DeepTMHMM_v10.5.md)，
A5 是不可削减的 N02 能力，序列直接输入，不依赖 R-58；版本须在实际部署时锁定。
原件写的 `pip pybiolib` 本地调用不能直接作为现行部署操作：

- 官方 SDK 的 CLI 明确拒绝 `--local`，Python `machine='local'` 同样报错；默认路径启动云端任务。
- 官方应用说明改为申请非商业本地软件包；元数据中的 `allow_client_side_execution=true` 不能证明当前 SDK 可用。
- 本项目不以云端运行代替离线验证，不以 DeepTMHMM2 或第三方重打包镜像代替 A5。

这是当前官方分发方式与原件安装描述的差异，归入 D02/D04 工程资产依赖；保留原件，不新造科学裁决项。
主要依据：[DTU 服务说明](https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/)、
[BioLib 官方应用](https://dtu.biolib.com/DeepTMHMM/)、
[已保存的应用元数据](../../../discovery/t01-phase1-real/w1/deeptmhmm-20260905/public_sources/app-metadata.json)、
[客户端本地模式代码](../../../discovery/t01-phase1-real/w1/deeptmhmm-20260905/public_sources/sdk_sources/biolib/cli/run.py)。

## 3. 已备好哪些输入和原始资料

全部输入只用于本地开发。没有甲方真实用例，没有上传序列或提交预测任务。

| 输入或资料 | 用途与限制 |
|---|---|
| DTU 官方 FASTA：GLR1_DROME 991aa、CLV3_ARATH 96aa、NAB2_SCHPO 307aa、Q9ALY0_KLEAE 375aa | 收到本地包后的第一组真实输入；未根据名称猜测逐位标签或判为已通过 |
| 官方 `DeepTMHMM.3line` | 3,576 条标注；每条 header/sequence/labels 三行；不能当作本次模型预测 |
| 官方 `DeepTMHMM.crossval.top` | 3,574 条历史记录；实际是 header/sequence/两行 labels 四行，两个标签行独立保留 |
| 选出的 4 条短标注案例 | Q8K459：inside；P01499：signal；P07471：单 TM 且 outside=60；Q9HVD1：P/B。这些类别来自公开标注，不承诺新模型一定预测一致 |
| 人工异常测试 | 长度不符、未知标签、空值、截断、重复 ID、错误记录宽度、P/B 保留及证据篡改；只证明检查器识别对应错误 |

核验记录见 [audit.json](../../../discovery/t01-phase1-real/w1/deeptmhmm-20260905/source-audit/audit.json)，
输入在 [inputs 目录](../../../discovery/t01-phase1-real/w1/deeptmhmm-20260905/source-audit/inputs)。
两份公开资料的全部记录均满足序列与各标签行等长，标签属于 S/O/M/I/P/B。

有两处必须保留的限制：

1. 两份资料都含 4 条带 X 的序列。当前 DTU 网页只列 20 个标准氨基酸；历史资料出现 X 不等于现行离线版本接收 X。
   此事实补充 OI-023。首批正常试跑选 AA20 输入；非常规残基保留为待实测输入支持域，不能静默替换。
2. 历史四行资料与三行标注不是完全相同的集合：少 2 个 ID，第一标签行有 3 个 ID 不一致，第二标签行也不能当成标注。
   目前只按 `label_row_1/2` 记录；行角色未获得独立确认，不计算模型准确率，也不把它当作 1.0.57 的预期文件。

## 4. 收到本地包后的执行清单

按顺序执行，每一步保留原始事实；新运行建新批次，不覆盖本批。

1. **登记资产。** 记录官方获取方式、许可文件、包版本/commit、镜像 digest、代码与每个模型权重 hash、依赖和默认参数。
   核实包与 DeepTMHMM 2022 模型的对应关系；公开应用 1.0.57 只作为对照线索。
2. **准备隔离运行。** 根据包内真实说明确定命令，不猜命令或输出文件名。准备阶段把依赖和模型全部放本地，
   运行阶段 `--network none`；输入只读、输出独立可写；限制资源并设置超时，超时只回收本次作业。
3. **执行真实预测。** 先运行短输入，再跑 4 条官方输入和适用覆盖案例；记录命令、CPU/GPU 模式、耗时、峰值资源、退出码、stdout/stderr。
   包缺权重或需要联网时原样记录，不能触发在线回退。将真实失败与人为故障分开标识。
4. **核对原始格式。** 原样保存全部输出，包括逐残基标签、区段表及包实际输出的其他文件。确认 ID/输入序列/长度对应、
   标签集和列语义，逐段比较 1-based 闭区间，检查覆盖与连续性；`tm_count` 是连续 M 区段数，`outside_length` 是 O 残基数。
5. **检查科学守卫。** P/B 依原件要求 `topology=null + unreliable + failure级WARNING + 禁止自动交接`；原始六标签完整保留。
   A5 不可用时为 `topology=null + WARNING("拓扑预测不可用")`，不能补成全 outside。非法输入按 R-48。
   这些生产守卫及下游 S-16/S-19/S-27/膜蛋白门控联动尚未在本批实现或验证。
6. **准备 G1。** 由算法验收人确认独立参考、覆盖与离散标签验收口径；公开训练/交叉验证数据不能充当独立留出验收集。
   工具能运行不等于科学签收；W1-08 放行后才进入生产适配器与真实工作流实现。

## 5. 本地包申请说明

打开官方页面给出的
[学术非商业本地包申请入口](https://forms.cloud.microsoft/Pages/ResponsePage.aspx?id=rURVGECW5U69G3ew50KVeHoV9Bi7sdNBnLmAyRfuhiJUM1lRRVY0MExIMEU1V0UxN1ZDVkFFUzlVQi4u)。
由申请人填写真实身份、联系方式和机构信息；本任务没有代填或提交。以下是可复制的用途说明草稿：

> I would like to request the DeepTMHMM local package for academic personal, non-commercial research.
> I need to run inference locally without network access after installation. Please provide the package,
> model weights, license terms, version information and installation/inference instructions for the
> DeepTMHMM model described in the 2022 paper. The public BioLib application currently advertises version
> 1.0.57; please confirm the corresponding local package version. My development environment is Linux
> containers on Windows/WSL2. Please also specify whether CPU inference is supported and the recommended
> GPU/CUDA requirements.

申请回执、个人信息和下载凭据不要写入项目文档。收到后提供本地包所在目录即可继续资产核验。
等待期间可推进 W1-04 的 AF3/ESMFold2 身份和资产准备，或补充 R-58/FreeSASA 样本，不以此阻断整个 W1。

## 6. 校验与结论边界

复核命令统一见 [运行手册](../../development/RUNBOOK.md#deeptmhmm-离线准备与公开资料校验)。
本批检查器只审核来源、原始格式、标签统计和客户端负向证据，没有产生生产 CandidateRecord。
保留 `model_execution=NOT_RUN`、`production_status=NOT_DEPLOYED`；W1-05 的真实离线推理和当前包原始输出验收尚待执行。
