# 历次工具验证与操作命令参考

仅在复核对应工具、执行批次或排查故障时查阅相应章节。日常入口见 [运行手册](RUNBOOK.md)。
下文保留 2026-09-06 整理前的操作说明；其中阶段顺序由 [现行交付计划](../project/PHASE1_DELIVERY_PLAN.md)覆盖。
历史采集、seal、freeze、build 和实例写入命令不自动重跑；原批次与 manifest 不覆盖。

---
# T-01 当前一期开发运行手册

适用范围：严格一期 N01-N18，包含冻结 Mock 的只读验证和独立真实阶段开发入口；
实际阶段、生产状态和下一任务见 [STATUS](../project/STATUS.md)。

## 按变更选择验证

| 变更 | 必须执行 |
|---|---|
| 纯文档文字或导航 | 文档检查 |
| 文档检查器或其规则 | 文档检查、tests/test_docs.py |
| 路径、契约、生成、绑定或冻结引用 | 文档检查、受影响测试、对应只读资产校验 |
| 跨当前/历史分区的路径或隔离变更 | 上述检查、当前根测试、旧完整 Mock 和 S07 回归 |
| 阶段冻结 | 任务包规定的全部门禁、四分区检查及冻结证据核验 |

当前根、旧完整 Mock 和 S07 的结果分别报告。纯文档修改不自动重跑科学工具或目标 Dify；
任务包明确要求的额外检查仍须完成。

文档检查覆盖必需文件、本地链接、当前文档的标题锚点、关键导航、STATUS 当前任务入口和已知
过时入口表述；后续任务入口应随 STATUS 更新。它不证明任意自然语言状态一致、科学正确性、
工具可用性或冻结资产哈希完整，后者需运行专用 verify。
已登记的 B2 Markdown 源码快照只有与来源条目、产物条目的字节数和 SHA-256 同时一致时才按证据处理；
原位置的现行文档和快照旁的其他导航仍检查链接。清单缺失、损坏或字节不一致会报错，不能借快照路径跳过检查。

## W1-08B2 DeepTMHMM 评审复核

[限定评审](../project/phase1/PHASE1_REAL_W1_B2_REVIEW.md)与
[专用草案](../../工作流设计/02-数据契约/phase1-real-v0.1/b2-review/README.md)定义输入、标签/区段、P/B/null 和放行条件。
下列命令只重读现有 Academic 原始证据、人工案例和来源/hash，不启动 Docker 或模型：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/check_w1_b2_review.py verify
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_w1_b2_review.py
```

使用项目 Python 3.11/jsonschema；旧包的 Python 3.8/PyTorch 等只作为被核对运行证据，不导入模型模块。
首次 prepare_w1_b2_review.py 构造草案和预声明材料，check_w1_b2_review.py execute 回读后 seal；
它们均拒绝已有目录/结果，日常只用 verify。源码或契约变更须另建版本和批次，不能重封旧 manifest 消除差异。
后续实际模型试跑仍遵循下方 Academic 的新目录运行条件，并在 B2 自身适用 G0/G1 下补充具名证据。

PASS_REVIEW_PREPARATION 表示工程材料核对通过；参考训练独立性、科学阈值、接收域和目标环境签收尚未获批。
不得据此启用运行层 t01.real.deeptmhmm，或将手工 timeout/cancel/不可用示例登记为实际进程故障。
B1 科学确认与 FoldX/ProteinMPNN 后续波次实际验证不作为本只读检查的前置依赖。

## B2 原包执行与复验

[补证说明](../project/phase1/PHASE1_REAL_W1_B2_BOUNDARIES.md)对应独立的 Academic 原包执行批次。
日常只读复核不会运行模型：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/check_b2_boundaries.py verify
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_b2_boundaries.py
```

新执行必须用新的项目目录，先 prepare 预声明，再 run；--case 可选择已声明的一条，各条目录只能运行一次。
runner 固定现有镜像、专用空 Docker 配置 `.tmp/b2-boundaries-docker-client/config.json` 和本地 Docker Linux 管道，
禁网/CPU 8/10 GiB/900 秒且串行，不读取账号凭证或下载依赖。Docker 管道可能需要宿主执行权限。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/run_b2_boundaries.py prepare --batch .tmp/b2-boundaries-new
.\.venv\Scripts\python.exe -X utf8 scripts/run_b2_boundaries.py run --batch .tmp/b2-boundaries-new
.\.venv\Scripts\python.exe -X utf8 scripts/check_b2_boundaries.py assess --batch .tmp/b2-boundaries-new
.\.venv\Scripts\python.exe -X utf8 scripts/check_b2_boundaries.py seal --batch .tmp/b2-boundaries-new
.\.venv\Scripts\python.exe -X utf8 scripts/check_b2_boundaries.py verify --batch .tmp/b2-boundaries-new
```

assess 只在独立副本构造缺失/损坏产物，保留原包失败和事后故障的区别，不改原成功目录。
seal 在全部预声明条件通过后保存源码/产物清单，禁止覆盖旧 manifest。验证脚本拒绝完整旧文件掩盖执行失败。
<9 aa 原包输入仅用于开发探测，正常 T-01 的上游守卫保持不变；实际成功不授予科学或生产消费资格。

## B1 → FreeSASA 消费者验证

[工程评审](../project/phase1/PHASE1_REAL_W1_B1_FREESASA_REVIEW.md)与
[开发文件接口](../../工作流设计/02-数据契约/phase1-real-v0.1/b1-freesasa/README.md)限定支持域和结果用途。
以下只读校验原始输入、B1 事实、工具读回/面积、先声明的预期和首轮失败证据，不重新运行 FreeSASA：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/check_b1_freesasa_consumer.py verify --reparse
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_b1_freesasa_consumer.py
```

消费一个已验证的 B1 bundle 时，显式指定路径、模型和上下文；下面只生成新的准备目录，不调用工具：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/prepare_b1_freesasa.py --bundle discovery/t01-phase1-real/w1/b1-freesasa-consumer-20260906-r02/b1_bundles/F-char-native --output-dir .tmp/b1-freesasa-new --route native_atoms --model-index 0 --context-chain A
```

重复 --context-chain 指定多条遮挡链。成功准备返回 0，预检/消费者边界拒绝返回 1，请求/文件失败返回 20。
原作者 token 和 iCode 分别保留，native 不进行 PDB 回退；PDB 路径坐标精度按三位小数单独记录。
本开发入口严格拒绝未知 iCode、非完整占有率、altloc 和未批准非蛋白上下文。

需要实际整批重跑时，使用新的 --batch 目录依次执行 check_b1_freesasa_consumer.py 的 prepare、prepare-inputs；
再执行下面的固定镜像入口，之后 assess、seal、verify --reparse。
seal 要求 protected_before.json；复跑相同源码可先复制已验证批次的保护清单，源码/预期变更须先登记新的修改前快照和保护依据。
每阶段拒绝覆盖已有证据；工具输出放在新 batch 的 execution 子目录，检查器从该固定相对位置回读。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/run_b1_freesasa_consumer.py --batch .tmp/b1-freesasa-campaign-new --output-dir .tmp/b1-freesasa-campaign-new/execution --docker-config .tmp/b1-freesasa-docker-client
```

Docker Desktop Linux 引擎须已运行，镜像必须已本地存在。--docker-config 是可选的客户端配置目录；
本次使用仅含空 JSON 的项目临时目录，未读取/复制账号凭证。入口使用已登记的 Docker 管道，
固定 image ID、--pull never、--network none、只读输入/根文件系统、资源限制及唯一容器名，超时只清理自己的容器。
上面命令的 batch 必须先完成 prepare-inputs；不接受任意 Worker 代码、下载模型或联网回退。
工具成功状态是 SUCCESS_RAW_ONLY，始终不可用于 pipeline，不授予 R-58/G1 或正常 RSA 资格。

## B1 输入事实工程补强

[工程评审](../project/phase1/PHASE1_REAL_W1_B1_ENGINEERING_REVIEW.md)与
[结果扩展](../../工作流设计/02-数据契约/phase1-real-v0.1/b1-engineering/README.md)说明支持域和原值语义。
只读检查会验证原件/旧证据与新批次 hash；--reparse 重新读取文件核对事实，不改写旧产物：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/check_b1_engineering.py verify --reparse
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_b1_input_facts.py tests/test_w1_b1_review.py tests/test_structure_mapping.py
```

需要新的单文件证据时，使用 B1 ingest 草案请求及其 ArtifactRef 对应的原结构：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/probe_b1_input_facts.py record --request discovery/t01-phase1-real/w1/b1-engineering-20260905/inputs/E-character-versus-icode.request.json --structure discovery/t01-phase1-real/w1/b1-engineering-20260905/inputs/E-character-versus-icode.structure --output-dir .tmp/b1-input-facts-new
.\.venv\Scripts\python.exe -X utf8 scripts/probe_b1_input_facts.py verify --output-dir .tmp/b1-input-facts-new --reparse
```

目录必须尚不存在。record 返回 0 表示事实可评审、1 表示输入预检拒绝且诊断已留存、20 表示请求/文件绑定或操作失败。
verify 返回 0 也可能是成功核验“拒绝案例”，不表示输入通过。
请求和结构按原字节复制，三份事实分别有 ArtifactRef/hash；本地探针身份不属于 A 服务签发任务。
不需 Docker、服务器或模型，沿用本地 Python 3.11/Biopython 1.88/jsonschema；不联网查询结构。

整批重跑时依次对新的 --batch 目录执行 check_b1_engineering.py prepare、execute、seal、verify --reparse。
prepare 拒绝已有输入，execute 拒绝已有结果，seal 拒绝已有 manifest。
已有批次包含修改前保护清单与 before/after 快照；源码或预期变化须另建批次，不能重封旧证据消除 hash 漂移。

## W1-08B1 评审准备复核

[B1 限定评审](../project/phase1/PHASE1_REAL_W1_B1_REVIEW.md)与
[请求/结果草案](../../工作流设计/02-数据契约/phase1-real-v0.1/b1-review/README.md)均不构成科学 G1。
以下命令只读核验草案、专家原件及本批文件；--reparse 会重新解析本地案例并核对映射候选，不写回原批次：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/check_w1_b1_review.py --reparse
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_w1_b1_review.py
```

使用已登记 Biopython 1.88 及项目开发环境；不需 Docker/模型/服务器，不调用科学工具或 Dify。
prepare_w1_b1_review.py 是首次材料构造入口，会拒绝已存在的目录与 Schema，不作为默认复跑命令。
案例预期在实测前声明，人工短序列/坐标的工程通过不表示有效业务输入或科学参考签收。
若后续修改探针或草案，先按任务包记录前后来源，在新批次验证；不能改旧证据后沿用旧 hash。

## W1-07 契约设计检查

[设计说明](../project/phase1/PHASE1_REAL_W1_CONTRACT_DESIGN.md)区分工程契约、逐工具科学 payload 和运行实现。
以下只读检查不启动 Worker、模型或 Dify：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/check_w1_contract.py
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_w1_contract_design.py
```

检查来源原件/hash、注册名、提交/控制/任务 Schema、状态示例、文件身份和明确未执行的验收案例。
测试包含伪造成功、未确认停止、终态重开、恢复改身份、跨任务文件、工程结果冒充生产和来源篡改。
PASS 是设计静态符合性；真正的进程竞争、崩溃恢复、超时取消与不可变存储由
[W1-09A](../project/phase1/PHASE1_REAL_W1_RUNTIME_BACKLOG.md)实现后验证。科学资格不由此检查器签发。
W1-07 修改源文件清单中的原件/旧证据时应先查明来源变化，不通过重算 hash 掩盖意外漂移。

## 结构预测准备证据复核

[W1-04 专项](../project/phase1/PHASE1_REAL_W1_STRUCTURE_PREDICTION_G0.md)记录 AF3/ESMFold2 的官方身份、
本机资源和待执行输入。以下命令只校验已有证据，不下载模型、不运行结构预测：

```powershell
.\.venv\Scripts\python.exe -X utf8 discovery/t01-phase1-real/w1/structure-prediction-20260905/verify_evidence.py
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_w1_structure_prediction_readiness.py
```

校验包含文件清单/hash、专家原件、固定源码 commit、五月模型元数据对照、完整资产预算、
实际 wrapper 默认参数和输入来源。PASS 只代表准备证据一致；模型状态仍为 NOT_RUN。
GPU 探针仅运行过 nvidia-smi，不是 JAX/PyTorch 或模型兼容性测试。
采集及封存脚本保留追溯用途，不能覆盖既有批次；新的安装、下载或推理应另建批次。
两模型环境须与当前项目及 DeepTMHMM 隔离，实际执行条件和顺序按专项说明核对。

## R-58 与 FreeSASA 边界开发验证

[专项说明](../project/phase1/PHASE1_REAL_W1_R58_SASA_BOUNDARIES.md)区分实体定位、PDB 转换、原始面积和科学签收。
日常只读复核：

```powershell
.\.venv\Scripts\python.exe discovery/t01-phase1-real/w1/r58-freesasa-boundaries-20260905/verify_evidence.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_r58_sasa_boundaries.py tests/test_structure_mapping.py tests/test_tool_interface.py
```

工具复跑需要既有固定 FreeSASA Docker 镜像、本机 Docker Linux 引擎及新输出目录：

```powershell
.\.venv\Scripts\python.exe discovery/t01-phase1-real/w1/r58-freesasa-boundaries-20260905/run_raw.py --output-dir .tmp/r58-sasa-new-run
```

本命令使用该批修正后的 `prepared/` 输入，禁网、只读挂载代码和输入，原始输出写入新目录。
容器退出 0 仅表示案例已记录，必须逐例检查 SUCCESS/REJECTED、映射、原始数值及未解决问题。
本批 6 次实际面积计算和 2 次工具边界拒绝分开登记；面积按地址归并，映射仍不可自动消费。
PDB 不可表达的字段明确拒绝；不通过修改作者编号、截短链 ID 或猜半径绕过错误。

重新生成同一套人工边界供检查时也必须使用新目录：

```powershell
.\.venv\Scripts\python.exe discovery/t01-phase1-real/w1/r58-freesasa-boundaries-20260905/prepare_cases.py --output-dir .tmp/r58-sasa-new-preparation
```

此命令不会改变 run_raw.py 固定使用的输入目录。新输入、源码或预期改变时新建实际执行批次并登记，
不覆盖已有输入或原始结果；seal_manifest.py 是一次性归档入口，不是日常检查。
原 R-58 批次中的源码 hash 属于旧时点，新批 before/ 和 after/ 保存前后源码，不能回写旧记录。

## DeepTMHMM 学术包禁网证据复核

用户提供包的身份、专家版本依据、真实输出与限制见 [学术包专项](../project/phase1/PHASE1_REAL_W1_DEEPTMHMM_OFFLINE.md)。
日常检查不需要 Docker，不会执行模型；资产检查另读取 var 中约 2.8 GB 文件：

```powershell
.\.venv\Scripts\python.exe discovery/t01-phase1-real/w1/deeptmhmm-academic-20260905/verify_evidence.py
.\.venv\Scripts\python.exe discovery/t01-phase1-real/w1/deeptmhmm-academic-20260905/verify_evidence.py --assets
.\.venv\Scripts\python.exe -m pytest -q tests/test_w1_deeptmhmm_academic.py tests/test_w1_deeptmhmm_evidence.py tests/test_docs.py
```

本批的接收、构建、执行和归档脚本为一次性取证入口，拒绝覆盖已有记录。复跑模型时新建证据批次，沿用
已固定镜像/资产与禁网资源限制，并另存命令、输入、输出和 manifest；不要直接运行接收脚本或重封旧 manifest。
原工具 Markdown 报告保留容器内链接，由专用 hash 检查覆盖；导航检查仅排除这类原报告，继续检查项目文档。

## DeepTMHMM 离线准备与公开资料校验

范围、当前官方获取方式与真实模型执行要求见 [W1-05 专项](../project/phase1/PHASE1_REAL_W1_DEEPTMHMM_G0.md)。
本批仅有 SDK 负向检查和公开资料核验，模型推理为 NOT_RUN。

```powershell
.\.venv\Scripts\python.exe discovery/t01-phase1-real/w1/deeptmhmm-20260905/verify_evidence.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_w1_deeptmhmm_evidence.py
```

重新检查公开资料时选择不存在的新目录：

```powershell
.\.venv\Scripts\python.exe discovery/t01-phase1-real/w1/deeptmhmm-20260905/audit_sources.py --output-dir .tmp/deeptmhmm-source-audit-new
```

仅在需要重验客户端行为且本地 Docker Linux 引擎可访问、固定 Python 镜像及公开 wheel 已存在时运行：

```powershell
.\.venv\Scripts\python.exe discovery/t01-phase1-real/w1/deeptmhmm-20260905/probe_sdk_offline.py --output-dir .tmp/deeptmhmm-sdk-check-new
```

脚本只创建本次专用容器，禁网、输入只读、限制 CPU/内存，超时回收该容器。脚本退出 0 表示观察到
SDK 的预期拒绝（容器退出 1），不表示模型可用。真实模型命令须以收到的官方本地包为准；
不要删除 `--local` 后重试，这会改变为在线任务。旧批次不覆盖，初次下载和来源登记脚本不是日常重跑入口。

## 日常只读检查

从项目根目录按变更范围选择：

```powershell
.\.venv\Scripts\python.exe .\scripts\check_docs.py
.\.venv\Scripts\python.exe .\scripts\t01_phase1_mock\materialize_fixtures.py --check
.\.venv\Scripts\python.exe .\scripts\t01_phase1_mock\build_dify_workflows.py --check
.\.venv\Scripts\python.exe .\scripts\t01_phase1_mock\bind_dify_workflows.py --check .\dify\t01-phase1-mock-v0.1\config\provider-bindings.local_dify_1_17.json
.\.venv\Scripts\python.exe .\scripts\t01_phase1_mock\run_m4_campaign.py verify
```

fixture 检查验证闭集、来源、字节和哈希；生成与绑定检查复算 generator→template→binding→bound
派生链；M4 verify 校验冻结清单、campaign/result/partition 关联和登记资产的字节及 SHA-256。
这些命令不重写资产、不调用科学程序、不更新目标 Dify。

冻结后不得去掉 --check 原地重建资产、覆盖 manifest 或删除后重冻。发现漂移时先定位原因，
按版本化变更流程处理；不能手改画布、模板或 bound 后继续沿用旧冻结结论。

## 真实工具公共接口与交接包

公共字段、路径基准、退出码与检查能力见 [接口规范](../../工作流设计/02-数据契约/tool-interface-v0.1/README.md)。
从项目根运行：

```powershell
.\.venv\Scripts\python.exe scripts/check_tool_interface.py --examples
.\.venv\Scripts\python.exe -m pytest -q tests/test_tool_interface.py
.\.venv\Scripts\python.exe scripts/package_tool_handoffs.py --check
```

原工具分工已取消，包内称谓与交接流程仅作历史参考；取消分工不触发重打包或发送。
历史包解压后可运行 `python interface/validate.py --examples`，依赖见接口规范。
实际交付用 `--request request.json --result output/result.json --check-files` 检查文件与双方一致性。
这些检查不会执行 FreeSASA/BepiPred，不改变真实门禁。

只在需要维护既有 v0.1 包时运行下面的写入命令；它从唯一接口源同步两包、重建 v0.1 ZIP、
清单和打包验证记录。当时按用户要求直接修订 v0.1，不另保留旧包；科学原件副本仅核验，不改写。

```powershell
.\.venv\Scripts\python.exe scripts/package_tool_handoffs.py --build
```

脚本默认也是只读检查。不要运行旧临时 assemble.py，它会恢复过时请求示例。
修改 canonical 接口后必须同步重打包；工程接口测试检查副本漂移，包验证检查 ZIP 与全部来源的 hash。

## 本地结构解析与 R-58 映射

专项范围与来源见 [任务说明](../project/phase1/PHASE1_REAL_W1_R58_MAPPING.md)。本机已核验的开发依赖
在 [structure-mapping.txt](../../requirements/structure-mapping.txt)，不修改冻结 Mock 的 pyproject.toml。
需要准备新环境时按获准方式安装本地依赖；下面的探测和校验均不联网。

```powershell
.\.venv\Scripts\python.exe scripts/probe_structure_mapping.py --structure tests/fixtures/structure_mapping/real/1UBQ.cif --sequence-file tests/fixtures/structure_mapping/real/1UBQ.fasta --output-dir .tmp/r58-my-new-run --evidence-kind local_input
.\.venv\Scripts\python.exe scripts/check_structure_mapping.py --mapping .tmp/r58-my-new-run/mapping.json --structure tests/fixtures/structure_mapping/real/1UBQ.cif --sequence-file tests/fixtures/structure_mapping/real/1UBQ.fasta
.\.venv\Scripts\python.exe -m pytest -q tests/test_structure_mapping.py tests/test_tool_interface.py
```

第一条会新建输出目录；每次改用未存在的目录，不覆盖旧证据。多 MODEL 用 --model-index 指定 0-based 索引，
--chain-id 只说明摄取链请求，不绕过设计链唯一性。结果为 structure_inventory.json、mapping.json、probe_result.json。
探测退出 0 只表示程序完成记录，仍要检查 mapping_status；unreliable 不可自动交接。解析失败退出 1，输出目录错误退出 20。
第二条只读重解析真实坐标，能检出 JSON 形状正确但残基编号被改动的情况。PASS 不是科学批准。
便携 mapping Schema 校验已集成到公共接口 --check-files；历史包维护条件见前节。

## W1 环境与样本准备

[采集程序](../../discovery/t01-phase1-real/w1/w1-preparation-20260905/collect_facts.py)仅重放本批开发环境盘点与
固定历史样本副本的原始字段核对；不会安装包或执行科学工具。依赖沿用本地解析环境。

```powershell
.\.venv\Scripts\python.exe discovery/t01-phase1-real/w1/w1-preparation-20260905/collect_facts.py --output-dir .tmp/w1-preparation-new-run
```

输出目录须在项目内且尚不存在；记录 environment.json、sample_audit.json 和 result.json。
此程序没有运行目标环境验收、完整原子完整性检查或科学批准，使用范围见 [登记说明](../project/phase1/PHASE1_REAL_W1_PREPARATION.md)。

## FreeSASA 本地原始工具探测

范围与事实见 [FreeSASA 专项](../project/phase1/PHASE1_REAL_W1_FREESASA_G0.md)。只读核验已有证据：

```powershell
.\.venv\Scripts\python.exe discovery/t01-phase1-real/w1/freesasa-s09-20260905/verify_evidence.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_w1_freesasa_evidence.py
```

下面会执行真实 FreeSASA 原始计算。仅在本地 Docker Desktop 已启动、登记的开发镜像仍存在时使用；
每次选择新的输出目录。不要重新执行原批次 run_local.py 覆盖证据，它也会拒绝已有结果目录。

```powershell
$freeBatch = (Resolve-Path -LiteralPath discovery/t01-phase1-real/w1/freesasa-s09-20260905).Path
$freeImage = (Get-Content -Raw -LiteralPath "$freeBatch/environment/docker.json" | ConvertFrom-Json).image_id
$freeOutput = Join-Path (Get-Location) '.tmp/freesasa-new-run'
New-Item -ItemType Directory -Path $freeOutput -ErrorAction Stop | Out-Null
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --cpus 2 --memory 1g --pids-limit 64 --mount "type=bind,source=$freeBatch/inputs,target=/input,readonly" --mount "type=bind,source=$freeBatch/probe_raw.py,target=/probe_raw.py,readonly" --mount "type=bind,source=$freeOutput,target=/out" $freeImage python -B /probe_raw.py --input /input/1UBQ.cif --mode cif-to-pdb --output-dir /out/result
```

该入口输出原始面积和环境/诊断，不输出项目 RSA 或公共接口生产 result。
成功执行仍需检查 engineering_checks、stderr、映射及参数；人工坐标含 NaN 的诊断见本批 followup，
不能以正常包装器退出或 JSON 格式代替数值检查。镜像不存在时按本批 Dockerfile 在新的批次重建并重新核验，
不能把重新构建的标签当成旧 image ID。

## FreeSASA 独立数值参考

[本批说明](../../discovery/t01-phase1-real/w1/freesasa-reference-20260905/README.md)记录不同算法和采样密度，
[方案与采用记录](../project/phase1/PHASE1_REAL_W1_FREESASA_S09_DECISION.md)解释现行规则与剩余确认。
下面只读复算已有结果，不需要 Docker 或 Windows FreeSASA：

```powershell
.\.venv\Scripts\python.exe discovery/t01-phase1-real/w1/freesasa-reference-20260905/verify_reference.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_w1_freesasa_reference.py tests/test_w1_freesasa_evidence.py
```

需要真实复跑初轮参数扫描时，在登记的本地 Docker Desktop 和固定镜像上运行：

```powershell
.\.venv\Scripts\python.exe discovery/t01-phase1-real/w1/freesasa-reference-20260905/run_comparison.py --output-dir .tmp/freesasa-reference-new-run
```

该命令固定禁网、只读输入和资源限额，拒绝已有目录；不会改动原批次。输出是数值研究结果，
不产生可消费项目 RSA。原 run_refinement.py 仅是固定首轮的补充采集入口，已执行后不原地重跑；
新的加密研究须在新批次中明确输入、参考密度和证据路径。不要重写 assessment 或 manifest 来消除漂移。

## W1-09A 本地通用运行层

[实现说明](../project/phase1/PHASE1_REAL_W1_RUNTIME_IMPLEMENTATION.md)解释存储、停止/恢复和当前适用范围。
依赖沿用开发环境 Python 3.11 和 jsonschema；仅验证 Windows 单机，不要求 AF3/ESMFold2 或 Docker。
以下演示会在指定独立目录创建 SQLite 和工程文件。换一个目录即可建立新的开发实例：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/w1_runtime.py --root D:/work/蛋白智能体/.tmp/w1-my-runtime demo
.\.venv\Scripts\python.exe -X utf8 scripts/w1_runtime.py --root D:/work/蛋白智能体/.tmp/w1-my-runtime profile
.\.venv\Scripts\python.exe -X utf8 scripts/w1_runtime.py --help
```

完整调用顺序是 create-run --key → stage --run-id --input → submit --input → dispatch --job-id。
stage 读入独立 UTF-8 JSON 文件，字段为 mode、payload、delay_seconds；demo 自动完成这组操作。
submit 和 control 消费 W1-07 Schema 的原始 UTF-8 字节，profile 使用 profile 子命令返回的当前登记值。
get/events 查询；cancel --job-id --key 提交停止；recover --job-id 对账并更新 lease；wait --job-id 等待终态；
retry --job-id --key 在确认失败/取消/超时后新建关联任务，还需 dispatch。CLI 不接受任意命令或科学工具配置。

只读复核已留存证据；第二条会新建临时目录并运行无害进程与故障测试：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/check_w1_runtime.py
.\.venv\Scripts\python.exe -X utf8 scripts/check_w1_runtime.py --batch discovery/t01-phase1-real/w1/runtime-file-fix-20260905
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_w1_runtime.py tests/test_w1_runtime_evidence.py tests/test_w1_runtime_fix.py
```

需要新证据时运行下条，目录必须尚不存在。它实际执行 CLI 和工程测试，不启动科学模型：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/run_w1_runtime_acceptance.py --output-dir discovery/t01-phase1-real/w1/runtime-engineering-new-run
```

运行根限独立本地磁盘，不支持 UNC、网络共享数据库、多机竞争或服务端身份认证。
原 W1-09A 证据的源码通过历史索引核验执行时快照；当前文件检查修复采用独立批次，见
[修复说明](../project/phase1/PHASE1_REAL_W1_RUNTIME_FILE_FIX.md)。ARCHIVED_EXECUTED_SOURCES 不代表当前源码通过旧批次验收。
工程 Worker 有单任务资源限额；本轮不承诺科学性能、远程 Linux 执行或断电/磁盘故障恢复。
未知执行保留 reconciling，先对账，不能通过改数据库、删除回执或重新提交冒充已停止。
不会自动清理 SQLite、事件、幂等键或孤立文件；需要清理时先确认所有所属进程停止并按具体目录单独维护。

## 测试与历史回归

当前根测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

只验证文档检查器时：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_docs.py
```

旧包必须在各自目录运行：

```powershell
Push-Location .\legacy\full-t01-mock-v0.1
..\..\.venv\Scripts\python.exe -m pytest -q
Pop-Location

Push-Location .\legacy\s07
..\..\.venv\Scripts\python.exe -m pytest -q
Pop-Location
```

[旧完整 Mock 手册](../../legacy/full-t01-mock-v0.1/docs/development/RUNBOOK.md)与
[S07 备用包](../../legacy/s07/README.md)只服务各自历史资产，结果不计入一期功能或生产完成度。

## 本地 Dify Mock transport

本地 Mock 应用绑定专用 transport。Docker 或宿主机重启后，可在独立终端启动：

```powershell
.\.venv\Scripts\python.exe .\scripts\t01_phase1_mock\serve_mcp_transport.py `
  --host 0.0.0.0 `
  --port 18081 `
  --runtime-root .\var\t01-phase1-mock-v0.1\local-dify-runtime
```

只读健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:18081/healthz
```

应返回 status=ok、tool_count=26、mock_only=true、scientific_compute=false。
服务只消费 synthetic fixture 并写入具名 Mock 运行目录；不暴露到公网，不改绑真实科学服务、
HiMat 或旧 t01-mock-mcp provider。

## 会写入状态的验收操作

run_m2_acceptance.py 会写入 M2 机器结果，run_m3_acceptance.py 及目标执行、provider 配置和
导入脚本涉及验收证据或实例状态写入，均不是默认日常检查。冻结后不原地重跑覆盖既有证据；
需按对应任务包使用独立证据位置和明确目标。

M4 prepare/drive/assemble/partition/freeze 属于发布 campaign 协议，冻结完成后日常只运行 verify。
相关入口、参数和适用证据见 [脚本索引](../../scripts/README.md)、
[一期任务索引](../project/phase1/README.md)及各脚本 --help。

## 开发与资料维护

从 [STATUS 当前任务入口](../project/STATUS.md#当前任务入口)接手。
真实工具先完成 G0/G1，遵守 [交付计划](../project/PHASE1_DELIVERY_PLAN.md)的逐波门禁，
不原地替换冻结 Mock 源码。文档职责见 [文档总入口](../README.md)。

Mock、smoke 和 discovery 不能代替科学验收。密钥只放受控运行环境，不写入仓库、DSL、日志或文档。
