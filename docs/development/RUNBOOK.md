# T-01 开发运行手册

先按 [STATUS](../project/STATUS.md)进入当前交付包；只查本次变更涉及的命令。
开发、科学消费、目标发布采用 [现行计划](../project/PHASE1_DELIVERY_PLAN.md)，旧命令参考不决定阶段顺序。

## 按变更选择验证

常驻执行专项：`python -X utf8 -m pytest -p no:cacheprovider -o addopts='' -q tests/test_resident_process.py tests/test_resident_runtime_bridge.py tests/test_resident_result.py`。实际进程/取消恢复/常驻CLI案例只在Linux运行；Windows跳过不能替代Linux测试。控制面设置`T01_RESIDENT_CONFIG_FILE`为可信绝对JSON路径，格式为`version=0.1.0`、`runtime_volume_root`、`tools`；每个工具注册`root`、`source_image_id`和`command`（tool/argv/environment/memory_bytes）。配置不从业务请求接收。常驻入口为`python -B -m t01_phase1_real.resident_worker --root <绝对执行目录> --config <可信命令JSON>`，Worker配置为`version=0.1.0`和`commands`，必须与控制面登记的命令逐字段相同。每个Worker只管理自己的执行根，输入、原生输出、监督日志分目录，`.processes`需持久化；取消通过同一execution目录的cancel标记，终态必须有归属匹配的停止回执。常驻配置启用后不回退创建Job。

结构完整链验证脚本为[resident_native_structure_probe.py](../../tests/resident_native_structure_probe.py)，在派生结构镜像中运行两个新任务，查询完整结果并核对重复计算值；只读取归档案例的原始输入，不读取旧计算结果作为输出。离线构建、容器挂载和运行参数见[r02汇总](../../discovery/t01-phase1-real/resident-worker-20260915/engineering-r02/summary.json)。`Dockerfile.resident`保留为结构专用入口；其余环境使用下方[批量装配](#常驻环境批量装配)。

### 常驻环境批量装配

本机原镜像与模型包已存在时，在仓库根目录执行以下命令。构建器先核对全部原镜像ID，再以禁网模式构建9个镜像；不下载、推送或更新服务器。每轮使用新的输出目录，保留实际`images.json`，不要将可变开发标签当作目标部署digest。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/assemble_resident_workers.py --docker "C:/Program Files/Docker/Docker/resources/bin/docker.exe" --output .tmp/resident-assembly-next
.\.venv\Scripts\python.exe -X utf8 scripts/verify_resident_environments.py --docker "C:/Program Files/Docker/Docker/resources/bin/docker.exe" --output .tmp/resident-environment-check-next
.\.venv\Scripts\python.exe -X utf8 -m pytest -p no:cacheprovider -o addopts='' -q tests/test_resident_assembly.py tests/test_resident_process.py tests/test_resident_runtime_bridge.py tests/test_resident_result.py
```

两脚本支持`--groups structure homology gpu`等指定组。全量验证使用本机第0张GPU，无GPU会明确失败；它验证原解释器/依赖、工具启动、CUDA和临时目录隔离，不代表模型完整推理或整链验收。Linux专属进程案例必须在Linux容器中执行。本批完整命令和日志见[装配索引](../../discovery/t01-phase1-real/resident-worker-20260915/assembly-r01/index.json)。

可复用输出为[控制面注册表](../../discovery/t01-phase1-real/resident-worker-20260915/assembly-r01/controller.json)、[镜像ID](../../discovery/t01-phase1-real/resident-worker-20260915/assembly-r01/images.json)和各组`configuration/<group>.worker.json`。后续部署必须让控制面与对应Worker以相同绝对路径看到同一执行目录，并保持两侧命令配置一致；当前文件是本机装配产物，尚未应用服务器。

| 容器路径 | 后续装配要求 |
|---|---|
| `/var/lib/t01/resident/<group>` | 对应Worker执行根可写，UID/GID 10001；任务和`.processes`持久化；GPU三个工具共享`gpu`根 |
| `/run/t01-slot` | 每个容器独立可写临时目录，UID/GID 10001；不得跨Worker共享 |
| `/t01/assets` | 原包与权重只读；沿用已校验目录名，资产须另行迁移 |
| `/t01/databases/blast`、`/t01/databases/homology` | 登记数据库ID的父目录，只读；当前未完成服务器数据库登记 |
| `/tmp` | 镜像已设置为每个任务临时目录的别名，不另外覆盖挂载 |

Worker默认入口使用镜像内可信配置，无需Docker socket或Kubernetes API凭据。GPU组只分配一张卡、一个Worker，并串行执行；配置里的256 GiB是CUDA虚拟地址空间上限，不是申请256 GiB物理内存，实际容器内存/GPU/存储配置仍须按目标资源确定。A3D环境已经可启动，N10业务嵌套派发与HiMat集中联调在后续步骤完成。

### 目标单卡与 AF3 顺序 1 复核

当前目标部署只有 `worker-unified-gpu` 申请指定 A100 64GB，并串行登记 AF3、ESMFold2、ProteinMPNN、ESM-IF1、ThermoMPNN。以下两个审计只读取集群业务状态和现行清单，但会刷新仓库内对应 `latest.json`/`audit-summary.json`；均不会调用 `workflow.report`。已有 r14 和 r01 证据不需要因普通文档修改重复执行。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/audit_af3_workflow_target.py --batch r14
.\.venv\Scripts\python.exe -X utf8 scripts/audit_unified_gpu_entry_guard.py
```

三工具迁移回归脚本的 `--check` 只校验本地远程载荷；省略 `--check` 会在服务器提交或恢复固定幂等范围内的真实 ProteinMPNN→ESM-IF1→ThermoMPNN 任务，因此仅在需要新验收证据时运行，不作为日常状态查询。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/run_unified_gpu_tool_regressions.py --check
```

现行完成证据为 [AF3 r14 审计](../../discovery/t01-phase1-real/af3-target-20260920/workflow-r14/audit-summary.json)、[三工具串行回归](../../discovery/t01-phase1-real/unified-gpu-worker-20260920/regressions-r01/latest.json)和[旧入口守卫](../../discovery/t01-phase1-real/unified-gpu-worker-20260920/entry-guard-r01/latest.json)。AF3 mmCIF 的未知插入码必须保留原字节；`ICODE_UNKNOWN` 继续输出 `review_required` 和 null RSA，不可由操作命令归一化为通过。

### 常驻业务集中联调

第3步成果及边界见[集中联调回填](../project/PHASE1_DELIVERY_PLAN.md)。[探针](../../scripts/run_resident_batch_probe.py)在Linux控制面运行，通过`T01_RESIDENT_CONFIG_FILE`连接同卷Worker；`--root`与`--output`必须是新目录。支持`n10`、`workflow`、`gpu-foldx`、`databases`案例。`workflow`通过本地认证HTTP MCP提交和下载，临时认证值仅在内存中，不连接HiMat；GPU案例仅生成一个新工程样本；数据库仅为工程库。

新镜像为`antigen-design-control:integration-r01`及9个`antigen-design-resident-<group>:integration-r01`。部署时使用匹配的控制面、Worker和注册表；本地ID不当作Harbor推送digest。增量包`deploy/antigen-design-resident-integration-20260915-r01.zip`包含源码、配置、10份Dockerfile、镜像基线/新ID和逐文件索引，不含权重、大镜像层、数据库或Secret。按`images.json`核对基础镜像后可在解压的新目录执行例如`docker build --network none --pull=false -f bepipred.Dockerfile -t antigen-design-resident-bepipred:integration-r01 .`。控制面Dockerfile依赖`antigen-design-control:ci-root-smoke`，它不在第2步Worker大包中；现场也可从本项目根Dockerfile构建当前控制面。增量ZIP不能单独作为完整离线部署包。

受影响回归：

```powershell
.\.venv\Scripts\python.exe -B -m pytest -o addopts= -q -p no:cacheprovider tests/test_resident_a3d.py tests/test_resident_runtime_bridge.py tests/test_resident_result.py tests/test_resident_assembly.py tests/test_developability_development.py tests/test_a3d_target.py tests/test_bepipred_development.py tests/test_thermompnn_development.py tests/test_real_service_api.py tests/test_local_workflow.py
```

Linux另运行`tests/test_resident_process.py`及`tests/test_resident_assembly.py`。完整命令及复现脚本随[本轮证据](../../discovery/t01-phase1-real/resident-worker-20260915/integration-r01/index.json)封存。服务器上传、挂载和HiMat/RustFS现场验收待执行。

### 常驻镜像与资产批量迁移包

**清理后状态（2026-09-27，用户授权同步）：** 旧包 `deploy/antigen-design-resident-20260915-r01/images/workers-linux-amd64.tar` 已删除；该目录保留原索引、配置、资产包和验证器，但已不是完整交付包，不能再直接执行下方旧路径的整包验证或用于恢复部署。较新的镜像导出保留于 `deploy/antigen-resident-publish-20260916-r01/workers-linux-amd64.tar`（交接时不入Git，其位置与hash见[外部资产清单](../../reports/handoff-20261014/external-assets.json)），对应[发布回执](../../deploy/antigen-resident-publish-20260916-r01/publish-receipts.json)保留。当前线上项目源码使用[归一快照及回滚清单](../../deploy/version-unification/r01/preflight.json)，实际版本见 [STATUS](../project/STATUS.md)；上述镜像导出不能单独恢复当前完整版本。清理范围见[清单](../../reports/version-unification-20260927/cleanup-manifest.json)和[完成回执](../../reports/version-unification-20260927/cleanup-receipt.json)。

本节以下命令、包内文件表及“待落实/尚未应用”描述保留为原打包阶段的历史参考，不代表当前部署状态。重新打包须使用新的输出路径和匹配的完整索引，不向已清理的旧目录补入不同版本文件后沿用原哈希。

本机Docker已迁到`D:\DockerData\DockerDesktopWSL`，`CustomWslDistroDir`设置经回读确认。大包输出使用D盘，禁止默认落入C盘临时目录。已完成环境装配后，以其索引为输入运行[打包器](../../scripts/resident_bundle.py)；每次使用新的输出目录，旧包不覆盖。该命令只导出现有镜像、只读打包已登记资产，不重新构建、不推送镜像、不连接集群。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/resident_bundle.py build --assembly discovery/t01-phase1-real/resident-worker-20260915/assembly-r01 --output deploy/antigen-design-resident-20260915-r01 --docker "C:/Program Files/Docker/Docker/resources/bin/docker.exe"
```

| 包内文件 | 用途 |
|---|---|
| `images/workers-linux-amd64.tar` | 一次`docker image save`导出的9个镜像，共用文件层不按镜像另打9份包 |
| `assets/tool-assets.tar` | 230份已登记原包/权重/许可相关文件，按原相对路径打包；FoldX可执行权限保留 |
| `metadata/images.json`、`metadata/assets.json` | 原本地索引ID、单独回读的linux/amd64平台摘要，以及每份资产大小/hash/权限；不是Harbor推送回执 |
| `configuration/controller.json`、各组`*.worker.json` | 匹配的控制面/Worker注册命令 |
| `configuration/mount-plan.json` | 针对现有`him-ws/antigen-design`的挂载方案，明确`apply_ready=false`及现场待定项 |
| `bundle.json`、`SHA256SUMS`、`verify_bundle.py` | 整包索引、校验和及可在另一台机器离线使用的验证器 |

完整复制交付目录后，使用Python3.11或以上校验。独立验证器只用标准库，无需本项目虚拟环境、Docker或联网；校验整包文件、镜像配置ID/标签/内容blob及资产成员hash/权限，不解压或执行工具。

```powershell
.\.venv\Scripts\python.exe -X utf8 deploy/antigen-design-resident-20260915-r01/verify_bundle.py verify deploy/antigen-design-resident-20260915-r01
```

Linux接收机在包目录运行`python3 verify_bundle.py verify .`。只有接收机具备Docker引擎时才使用`docker image load --input images/workers-linux-amd64.tar`；HiMat/Rancher的kubectl终端不等于Docker主机终端。镜像上传通道及Harbor推送digest待后续落实，不能直接把本地image ID填成仓库digest。

若本次导出已生成`.partial`镜像包、但后续校验未结束，可以在原构建命令追加`--resume`；它重新核对原装配索引、本地镜像和平台身份，并验证已有归档，验证通过才改名完成，不重复导出大包。已存在`bundle.json`的完成包拒绝续写。单平台导出的OCI摘要不同于本地顶层索引ID，验证器同时校验包内Docker/OCI清单、配置与层的绑定，不能直接把配置hash与本地索引ID相比。

挂载方案：控制面与9个Worker放在同一Pod以复用现有RWO运行卷，GPU组只申请一次GPU；每个Worker独享`/run/t01-slot`临时卷。拟新建20Gi `antigen-design-assets`资产卷，资产包解到该卷根目录，控制面只读挂载到`/app/var/t01-phase1-real/tool-assets`，Worker只读挂载到`/t01/assets`。不要解到现有任务目录；不要对原包原地写入生成配置。资产卷尚未创建，GPU资源名和实际容量仍待现场确认；最终部署使用单副本Recreate，避免新旧Pod跨节点同时占用RWO卷。该布局依据[Kubernetes卷访问模式](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#access-modes)，属于测试服实施方案，尚未应用。

本包不包含数据库、AF3/ESMFold2、Secret、业务运行数据或更新后的控制面镜像。资产迁移完成后仍须接通N10/A3D业务路径、集中真实计算/HiMat联调，再构建与本轮代码匹配的控制面并更新服务器。不能仅凭打包成功开放科学Gate。

部署前修复及Job桥接专项：`python -X utf8 -m pytest -o addopts='' -q tests/test_deployment_hardening.py tests/test_kubernetes_launcher.py tests/test_kubernetes_runtime_bridge.py tests/test_target_linux_candidate.py tests/test_real_service_api.py`。Linux真实停止探针为`scripts/probe_posix_stop_safety.py`，只在隔离Linux容器中新建测试进程，不对主机既有进程发信号。完整范围及未闭合的目标验证见[部署前修复](../project/PHASE1_DELIVERY_PLAN.md)。

首轮现场只读查询已由用户返回，结果单点维护在[目标环境盘点](../project/PHASE1_DELIVERY_PLAN.md)。节点及 kube-system DaemonSet 查询无权限，不重复执行来等待权限变化。以下保留为具备权限后补查或换环境时的参考；不导出kubeconfig、Secret或token。项目名称已按[命名决定](../project/DECISIONS.md#项目命名)确认；下一步确定仓库实际地址、专用服务账号授权和真实镜像/资产卷映射，再验证禁网、同节点挂载和Job取消/恢复。当前占位模板不能直接作为发布清单。

```bash
kubectl config current-context
kubectl get nodes -o wide
kubectl get nodes -o custom-columns=NAME:.metadata.name,CPU:.status.allocatable.cpu,MEMORY:.status.allocatable.memory,GPU:.status.allocatable.nvidia\\.com/gpu
kubectl get daemonsets -n kube-system
kubectl get storageclasses
```

本包调用方式见[本地真实流程接口](../project/PHASE1_DELIVERY_PLAN.md)，检查命令见下方对应章节。

| 变更 | 必须执行 |
|---|---|
| 纯文档文字/导航 | 文档检查 |
| 文档检查器/规则 | 文档检查、tests/test_docs.py |
| 路径、契约、生成、绑定、冻结引用 | 文档检查、受影响测试、对应只读资产校验 |
| 跨当前/历史分区路径或隔离 | 上述检查、当前根测试、旧完整 Mock 与 S07 分别回归 |
| 阶段冻结 | 适用全部门禁、四分区检查、冻结证据 |

普通功能改动运行能覆盖实际行为与风险的测试；完整检查通过后，不因整理文字重复运行科学工具。

## 本地真实流程集成检查

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_local_workflow.py tests/test_local_workflow_evidence.py tests/test_docs.py
.\.venv\Scripts\python.exe -X utf8 scripts/audit_local_workflow_evidence.py discovery/t01-phase1-real/integration-20260910/acceptance-r02
.\.venv\Scripts\python.exe -X utf8 scripts/check_docs.py
```

新批次实跑入口为`scripts/run_local_workflow_acceptance.py --batch <新名称>`，需要本机Docker及已固定工具资产；禁止复用已存在的批次目录。脚本新执行本地1UBQ结构/DeepTMHMM/BepiPred和后端报告，另在新运行副本保持历史24条淘汰身份；旧索引与原生输出不回写。独立auditor检查归档/发布hash、父子身份、嵌套ZIP清单及新执行/历史复用标识。单测覆盖取消栅栏、总期限、控制器中断续接、并发控制器、显式新尝试、CLI导出及篡改；这些测试不构成科学签收。
当前根、旧 Mock、S07 结果分别报告，不能相加作为一期功能完成度。具体执行事实保留在本批记录，STATUS 只记摘要。

## 真实服务与 Dify 局部联调检查

服务凭据使用严格 JSON 文档，由进程环境`T01_REAL_SERVICE_CREDENTIALS_JSON`注入；每项包含不少于32字符的`token`、唯一`principal`和明确`scopes`。安全配置文件不得放入仓库、证据或命令日志。示例启动只引用受控文件，不展示其内容：

```powershell
$env:T01_REAL_SERVICE_CREDENTIALS_JSON = Get-Content -Raw -LiteralPath D:\secure\t01-real-service-credentials.json
.\.venv\Scripts\python.exe -X utf8 -m t01_phase1_real.service_api --host 127.0.0.1 --port 18083 --runtime-root D:\work\蛋白智能体\var\t01-phase1-real\service-local
```

默认仅监听回环；Dify 容器联调才按受控主机边界监听`0.0.0.0`并使用`http://host.docker.internal:18083/mcp`。数据库根、并发和运行根只由服务启动参数固定，不进入调用请求。验收结束停止进程；生产监听、TLS/反向代理、持久密钥和目标 Linux systemd/容器部署另包验证。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_real_service_api.py
.\.venv\Scripts\python.exe -X utf8 scripts/build_real_service_dify.py --check
.\.venv\Scripts\python.exe -X utf8 scripts/audit_real_service_evidence.py discovery/t01-phase1-real/service-integration-20260910/acceptance-r02 --runtime-root var/t01-phase1-real-service-acceptance-r02 --output discovery/t01-phase1-real/service-validation-20260910/evidence-audit-new.json
.\.venv\Scripts\python.exe -X utf8 scripts/check_docs.py
```

审计输出必须是新路径；复核现有r02时直接读取已归档的[独立审计](../../discovery/t01-phase1-real/service-validation-20260910/evidence-audit-r01.json)，不要覆盖。新的完整实跑使用`scripts/run_real_service_acceptance.py`和从未存在的 runtime/evidence/secret/continue 四个路径；脚本在 Dify 停点保持服务，只有容器内 provider配置、DSL导入及成功/失败执行证据齐备后才创建继续标记。现有 provider/app 更新必须分别提供精确 record/app ID及显式更新参数；不得按名称误改其他应用。传入 provider helper 的明文凭据文件读取后立即删除，导出的 DSL 和证据不得包含 header 值。`acceptance-r01`为失败批次，只以`acceptance-r02`作为当前 PASS 证据。

服务实现或 Dify 生成/绑定变化运行服务专项、完整当前根和冻结 Mock 只读核验；没有跨历史分区时不重跑旧完整 Mock/S07。真实运行成功不开放科学消费，报告仍须显示`CLOSED / false / NOT_DEPLOYED`。

## 本地 Linux / Kubernetes 发布候选检查

发布目录为 [t01-phase1-real-target-v0.1](../../deploy/t01-phase1-real-target-v0.1)，单文件离线包为 `deploy/t01-phase1-real-target-v0.1-offline.zip`。候选只可在本地构建、导入和校验；本节命令没有 `kubectl apply`、Harbor push 或服务器访问。凭据只以仓库外临时文件只读挂载，不能写入命令日志、镜像、清单实值或证据。

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_target_linux_candidate.py tests/test_real_service_api.py tests/test_w1_runtime.py tests/test_codon_lifecycle.py
.\.venv\Scripts\python.exe -X utf8 scripts/build_target_linux_candidate.py stage --target .tmp/target-linux-build
docker --config .tmp/docker-config build --network none --pull=false --platform linux/amd64 --build-arg RELEASE_VERSION=0.1.0-rc1 --tag t01-phase1-real-control:0.1.0-rc1 .tmp/target-linux-build
.\.venv\Scripts\python.exe -X utf8 scripts/verify_target_linux_candidate.py deploy/t01-phase1-real-target-v0.1 --archive deploy/t01-phase1-real-target-v0.1-offline.zip
.\.venv\Scripts\python.exe -X utf8 scripts/check_docs.py
```

`wheelhouse` 只在联网准备阶段生成；候选镜像构建必须使用固定 base digest、`--network none` 与本地 wheel。最终镜像以 `metadata/image.json` 为准，离线 tar 必须实际执行一次 `docker image load`；SPDX、源码清单、扩展包 `index.json` 和 ZIP 均逐字节复核。验收容器必须为 UID/GID 10001、只读根、drop ALL、no-new-privileges、专用持久卷和 internal-only 网络；覆盖认证、上传及越界路径拒绝、提交/查询、取消/恢复/重试、报告递归 hash、进程中断自动接续、升级/回滚及新卷备份恢复。

Kubernetes `control-plane.yaml`只含 Namespace、ServiceAccount、Secret、ConfigMap、PVC、Role/RoleBinding、单副本 Recreate Deployment 和 ClusterIP Service；`scientific-jobs`共10份，只作现场渲染输入。任何 `REPLACE_AT_SITE`、零 digest、未登记 PVC/GPU 资源名或 Secret 占位存在时不得应用。现场先填写 [配置表](../../deploy/t01-phase1-real-target-v0.1/SITE_CONFIGURATION.md)，推入 Harbor 后用实际 manifest digest 重渲染，并另做 `kubectl --dry-run`、`auth can-i`和真实 Job 验收。本地候选 PASS 不能更新目标部署状态。

N08 的一条调用命令、数据登记格式及新批次验收入口见 [W3 N08 本机接口](../project/phase1/PHASE1_REAL_W3_PLAN.md)。工程运行采用独立 homology 数据根和固定禁网镜像；服务器大库适配与目标验收另行记录。

N10 的严格请求、部分结果语义、PROPKA 输入转换及新批次验收入口见 [W4 N10 本机接口](../project/phase1/PHASE1_REAL_W4_PLAN.md)。当前没有完整 overall 或设计 Gate 资格。

## 2026-09-12 目标部署修复与现场渲染

新候选使用 `deploy/t01-phase1-real-target-v0.2`，索引格式0.2.0要求10类控制面资源（含NetworkPolicy）和11份科学Job（新增A3D）；旧0.1.0候选维持原9类/10份只读校验。现场不得直接应用候选的占位模板。新构建必须使用新的staging/候选路径；各批实际验收结果见当前交付包，生成模板不等于目标可运行。

受影响检查：`tests/test_docs.py`、`tests/test_target_linux_candidate.py`、`tests/test_target_site.py`、`tests/test_target_structure_result.py`、`tests/test_a3d_target.py`、`tests/test_kubernetes_launcher.py`、`tests/test_kubernetes_runtime_bridge.py`、结构/N10/流程回归，随后当前根全量与457份Mock冻结只读核验。封存文档快照仅在原index大小/hash核验通过时免于按现行路径解析，缺失或篡改仍失败。

现场渲染命令：`.venv/Scripts/python.exe scripts/render_target_site.py --config <现场JSON路径> --output <新的输出目录>`。JSON精确字段由[渲染实现](../../src/t01_phase1_real/deployment/site.py)限定：schema_version=0.1.0、namespace、api_server、control_image、runtime_claim、storage_class、storage_size、source_assets_claim、credentials_secret、image_pull_secrets、tools、database_claims。所有镜像必须是实际registry digest，禁止零digest/占位域名；只填写凭据引用名称，不填写token/password。输出application.yaml不含Namespace/Secret/Role/RoleBinding；administrator.yaml交有权限者落实最小Role/RoleBinding，不修改him-ws现有应用或命名空间标签。

source_assets_claim只读挂载到`/app/var/t01-phase1-real/tool-assets`，卷根是原登记的各工具目录，保持原相对路径/hash；工具各自asset_claim卷布局仍按Job的package/models/database子目录。BLAST/同源库在`database/<database_id>`，控制面与科学Job须使用同一数据claim；domains同样在database子目录下放登记包。清单会绑定launcher JSON、服务账号token/CA路径、运行卷、数据库CLI参数及imagePullSecrets。实际SA授权、资产存在/可读与hash、存储权限需在现场验证。

结构与A3D目标结果放行还要求操作者提供独立现场工程验收收据。现场JSON可追加qualification={claim,sha256}，只读卷根放qualification.json及引用证据文件；launcher固定收据路径/hash。收据精确字段见[target_result.py](../../src/t01_phase1_real/deployment/target_result.py)：schema_version、server、namespace、control_image、network_policy_uid、node_names、tools、approved_by、approved_at、evidence；tools记录实际image到固定source_image_id的来源关系。evidence包含cni_dns_denied、cni_tcp_denied、effective_network_policies、image_provenance、storage、cancel_recovery六类独立文件的相对路径与hash。必须由实际现场测试产生并确认；这是可审计的操作者工程批准，不是代码自动证明CNI、镜像来源或科学资格。未提供时可收集原始运行诊断，不得把contract fixture登记为现场证据。

A3D失联/取消的父任务在原Pod停止确认前保持非终态；恢复不重新POST旧Job，清理后按中断处理，需显式retry创建新尝试。结构结果复用原生身份/产物hash、package、RSA归一化校验，目标分支另检实际Job/Pod、零重启、镜像digest、节点和现场收据；Docker分支保留原禁网/CPU守卫。目标结果、现场部署与科学签收分别记录，原24条排除不变。

### Codeup / Jenkins 构建入口（2026-09-14）

2026-10-14交接补充：`main`保存完整交接资料，`test`保留现有自动发布通道。十服务已拆成独立Deployment，但现有公共流水线仅更新API镜像；完整发布还需同步固定源码快照和9个Worker并逐容器核验。接手权限、存储位置与最新发布/回滚入口见[交接说明](../project/HANDOFF.md)。以下构建命令仍只验证控制面，不能替代十服务发布验收。

公共 Jenkins 默认从仓库根目录读取 `Dockerfile` 和 `Jenkinsfile`。根 Dockerfile 直接从当前源码树组装与本地 Linux 候选相同的 `/app` 布局，只使用 `deploy/t01-phase1-real-target-v0.2/wheelhouse` 的17份已验证 Linux wheel；这些 wheel 须与 CI 文件一并进入 Codeup，不得换成联网 `pip install`。本地验证命令：

```powershell
docker build --network none --pull=false --platform linux/amd64 --build-arg RELEASE_VERSION=0.2.0-rc3-ci --tag antigen-design-control:ci-root-smoke .
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp:rw,noexec,nosuid,size=64m --entrypoint python antigen-design-control:ci-root-smoke -B -c "import os,t01_phase1_real,jsonschema,yaml,Bio,numpy; print({'uid':os.getuid(),'release':os.environ['T01_RELEASE_VERSION'],'imports':'PASS'})"
```

当前`Jenkinsfile`的`latest`目标为已存在的`him-ws/antigen-design` Deployment；用户确认通过Codeup `test`分支自动部署。公共流水线原有职责为构建、推送及更新已存在工作负载，不创建首次所需资源。根Dockerfile目前只构建控制面，本机Worker镜像和权重不在该构建上下文中。接入9个常驻Worker前需核对公共脚本的多镜像构建及容器更新方式，以及基础镜像/资产的传入通道；不要求用户先申请公网Harbor或Nodes读取权限。现场补充及下一项见[Codeup通道回填](../project/PHASE1_DELIVERY_PLAN.md)。推送回执须记录实际仓库digest，不以本机image ID或浮动latest代替。

## 日常只读检查

N09 的本地注释包、真实上游 ArtifactRef 和新批次运行命令集中见 [N09 本机接口](../project/phase1/PHASE1_REAL_W3_PLAN.md)。工程执行及服务器目标验收分别记录；不要复制旧任务的引用作为新运行根内的已登记产物。

从项目根执行文档检查：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/check_docs.py
```

检查普通及引用式本地链接、现行章节和阶段文件入口。`PASS_WITH_HISTORICAL_LINK_ISSUES` 表示现行导航通过，但历史原文仍有旧路径；逐条清单由检查器输出，现存目标见 [历史入口](../../legacy/README.md)。这不是编辑器点击跳转的验证结果。

需要核验冻结引用时运行，只读不重冻：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/t01_phase1_mock/run_m4_campaign.py verify
```

## N17 WT参考与N18本地工程包

来源必须为同运行根内已登记任务，序列相同不能代替精确WT结构/变体/表达宿主匹配；[W7接口与证据](../project/phase1/PHASE1_REAL_W7_PLAN.md)维护请求、导出、剩余依赖及状态语义。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_local_delivery_development.py tests/test_local_delivery_evidence_audit.py tests/test_docs.py
.\.venv\Scripts\python.exe -X utf8 scripts/audit_local_delivery_evidence.py discovery/t01-phase1-real/w7/local-delivery-integration-20260910/export-check-r01
.\.venv\Scripts\python.exe -X utf8 scripts/run_local_delivery_acceptance.py --batch acceptance-new
```

复核已封存产物用第二条；第三条必须是新批次，复制并核验历史来源后组装，不启动稳定性/设计模型、不自动交接Agent C。完整包查询用result，单个ZIP/报告用artifact，具体变体用来源报告的variant-record。共享运行层改动回归当前根及冻结Mock只读验证；历史分区未改则不重跑旧完整Mock/S07。

## N16 条件密码子优化

精确请求、支持表、结果语义与生命周期见 [W7 N16 接口](../project/phase1/PHASE1_REAL_W7_PLAN.md)。采用固定本地依赖，不需 Docker；新验收只使用独立工程序列，不处理旧24条排除记录。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_codon_development.py tests/test_codon_evidence_audit.py tests/test_codon_lifecycle.py
.\.venv\Scripts\python.exe -X utf8 scripts/audit_codon_evidence.py discovery/t01-phase1-real/w7/codon-integration-20260909/acceptance-r01
.\.venv\Scripts\python.exe -X utf8 scripts/run_codon_acceptance.py --batch acceptance-new
```

第三条必须使用新批次，复核已封存结果只执行第二条。共享 registry/runtime/契约变化增加当前根回归及冻结 Mock 只读验证；未跨历史分区，不重跑旧完整 Mock/S07。依赖漂移需要重新核验并建立新版本 profile，不能覆盖旧清单。

## DeepTMHMM 当前统一入口

提交、执行、查询、取消、恢复和重试的命令及开发请求边界单点维护在 [当前交付包](../project/phase1/PHASE1_REAL_W1_BACKLOG.md)。
固定本地 Academic 资产及 Docker Linux Engine 可用后运行；本机结果仍不可科研消费。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_deeptmhmm_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_deeptmhmm_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\deeptmhmm-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w1\deeptmhmm-acceptance-new
```

第二条会实际执行一组串行模型及明确标记的故障案例，需要使用尚不存在的证据目录；普通只读复核不重复运行模型。

## 本地结构分析当前统一入口

一条命令、输入元数据和结果语义见 [W1 本地结构调用](../project/phase1/PHASE1_REAL_W1_BACKLOG.md)。需本机已登记的 FreeSASA 镜像，使用同一任务层，计算禁网且保持开发资格。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_structure_development.py tests/test_deeptmhmm_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_structure_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\structure-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w1\structure-acceptance-new
```

第二条需要全新的运行目录与批次目录，实际执行原件、工程夹具及明确标记的故障场景，生成本批 index.json。`--receipt-damage-only` 与 `--stop-only` 可补跑对应工程场景；默认已包含二者。完整性测试只改动新验收任务的指定文件，并先保存原字节。

## 测试与历史回归

BepiPred 的命令与结果契约单点维护在 [W2 本机调用](../project/phase1/PHASE1_REAL_W2_PLAN.md)。运行以下针对性测试；需要新实测时使用新的运行根和 W2 批次：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_bepipred_development.py tests/test_deeptmhmm_development.py tests/test_structure_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_bepipred_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\bepipred-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w2\bepipred-acceptance-new
```

第二条实际运行固定模型及有标记的故障案例。`--resume-tail` 仅适用于验收客户端在已记录 crash-after-start 后中断的补完；要求 profile 和旧证据字节保持一致，不重写完成批次。

按变更范围选择，不默认同时执行所有行：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_docs.py
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```

旧分区的独立命令和操作条件见 [历史回归命令](REFERENCE_COMMANDS.md#测试与历史回归)。

## BLAST N03 本机引擎接入

请求、数据库 manifest 约束、一条真实调用命令及相似性/文献证据边界见 [W2 N03 本机调用](../project/phase1/PHASE1_REAL_W2_PLAN.md)。普通复核运行针对性测试；需要重跑真实工程建库和生命周期证据时必须使用全新的运行根与 W2 批次：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_blast_development.py tests/test_netmhc_development.py tests/test_bepipred_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_blast_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\blast-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w2\blast-integration-new
```

第二条命令会创建并登记一个全新小型工程 FASTA 库，使用固定 NCBI BLAST+ 2.17.0 镜像在 `network=none` 下执行真实 `makeblastdb/blastp`，再验证命中、未命中、库不可用/损坏、生命周期与完整性。不得覆盖完成批次，也不得把工程库或其命中作为目标库、IEDB 文献、E3/E4 或科学签收证据。服务器目标库接入复用同一 ID + manifest + 只读库根接口，先按 OI-028 核实来源、版本、许可、路径和索引。

## NetMHC N05 本机开发接入

NetMHCpan 4.2e 与 NetMHCIIpan 4.3k 的用户提供 Linux x86_64 包、包内 allele 清单和固定镜像已登记。普通复核运行测试；需要新的真实生命周期证据时必须使用全新的运行根和 W2 批次：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_netmhc_development.py tests/test_bepipred_development.py tests/test_deeptmhmm_development.py tests/test_structure_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_netmhc_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\netmhc-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w2\netmhc-acceptance-new
```

请求字段、一条真实调用命令、镜像和结果语义见 [W2 NetMHC 本机调用](../project/phase1/PHASE1_REAL_W2_PLAN.md)。验收脚本核验原包完整 hash，并真实运行正常、单/双通道不可用、解析损坏、取消、超时、恢复、重试和幂等场景；不得对已有完成批次复跑或覆盖。公开 Web 快照仍不能代替 stand-alone 包，本地开发 PASS 也不授予科学消费、商业或生产资格。

## N06 表位地图与局部联调

请求、真实 N04/N05 ArtifactRef 绑定、已计算/关闭分支、N07 来源回连和一条调用命令见 [W2 N06 本机调用](../project/phase1/PHASE1_REAL_W2_PLAN.md)。普通复核运行针对性测试；需要重跑真实 BepiPred/NetMHC 与局部故障链时必须使用全新的运行根和 W2 批次：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_epitope_map_development.py tests/test_glycosylation_development.py tests/test_netmhc_development.py tests/test_bepipred_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_epitope_map_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real-n06-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w2\epitope-map-integration-new
```

第二条真实执行 N04/N05 各一次，再验证 N06 正常/部分/上游失败、幂等、取消/重试、计算/输出失败、中断恢复、序列/来源替换及提交后哈希损坏，并以实际 N06 结果验证 N07 来源。它不执行未确认的 BepiPred 峰、证据权重、热点合成、非 20 aa 窗口换算或 N03 BLAST，也不授予科学消费资格。

## N07 糖基化扫描

请求、热点状态、结果语义和一条调用命令见 [W3 N07 接口](../project/phase1/PHASE1_REAL_W3_PLAN.md)。这是可信本地后端的有界规则计算，不需要 Docker 或网络；结果保持开发未签收资格。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_glycosylation_development.py tests/test_netmhc_development.py tests/test_bepipred_development.py tests/test_deeptmhmm_development.py tests/test_structure_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_glycosylation_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\glycosylation-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w3\glycosylation-acceptance-new
```

验收命令必须使用尚不存在的新运行根和 W3 批次；它穷举三肽规则并执行独立扫描、热点契约与生命周期/完整性案例，不单独验证真实 N06 ArtifactRef。真实来源校验现由上述 N06 联调批次覆盖；非 20 aa 热点换算和热点科学全链仍未验证，也不授予科学消费资格。

## W4 Gate 与 WT 本地草稿

请求、字段生产者与来源校验、阻断原因和统一查询命令集中见 [W4 本机接口](../project/phase1/PHASE1_REAL_W4_PLAN.md)。新增 `wt-draft` 工程 Worker，不运行模型或网络，不开启 N11、正式 WT 或 Agent C。完整验收使用新的运行根和批次，真实执行无结构部分 N10、失败 N06 与独立 N07，不重跑历史批次：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_wt_draft_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_wt_draft_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\wt-draft-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w4\wt-draft-integration-new
```

共享 runtime/registry/增量契约变化需回归受影响开发 Worker；草稿来源必须是同一运行根中已登记的真实任务，不复制旧运行的引用冒充新任务。停止或草稿组装失败时仅返回诊断与原始证据，不把 raw 草稿当成功交付。

## W5 N12 ESM-IF1 独立工程接入

权限合成与 mutation_burden 的独立入口、空值和掩码草稿见 [合并后端接口](../project/phase1/PHASE1_REAL_W5_PLAN.md)。其验收不重复生成候选，使用新根中保留原身份的 N11/N12 历史副本；原根与归档只读。全新合并验收：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_design_backend_development.py tests/test_design_backend_sources.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_design_backend_acceptance.py --root var/t01-phase1-real/design-backend-acceptance-NEW --batch discovery/t01-phase1-real/w5/design-backend-integration-NEW/acceptance-r01
.\.venv\Scripts\python.exe -X utf8 scripts/audit_design_backend_evidence.py --batch discovery/t01-phase1-real/w5/design-backend-integration-NEW/acceptance-r01 --output discovery/t01-phase1-real/w5/design-backend-integration-NEW/audit.json
```

NEW 必须为未存在的新批次。脚本核验旧索引后复制历史运行根，仅在新副本恢复原验收故意损坏的两份产物并记录修复前/后 hash；其旧任务不计为本轮模型执行。新增 N06/N07/N08/N09 是实际后端/禁网工具执行，本机原生掩码探针仅 parser/featurizer，`generation_invocations=0`。末尾篡改也只作用新运行根副本，归档留破坏前产物。独立审计复算权限/负担及数值夹具，并核验官方掩码、来源标度、源码/规则 profile 和发布文件。共享调度/契约变更执行完整当前根回归，既有冻结资产只读复核。

请求、同 WT 基线签名、N11 来源与数值/科学边界见 [N12 本机接口](../project/phase1/PHASE1_REAL_W5_PLAN.md)。需要登记的 ESM-IF1 和 N11 官方资产、固定 GPU 镜像及本机 Docker Linux daemon。实际模型运行禁网；完整验收真实生成 N11 工程序列，旧批次只读：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_esm_if1_development.py tests/test_esm_if1_evidence_audit.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_esm_if1_acceptance.py --root var/t01-phase1-real/esm-if1-acceptance-NEW --batch discovery/t01-phase1-real/w5/esm-if1-integration-NEW/acceptance-r01
.\.venv\Scripts\python.exe -X utf8 scripts/audit_esm_if1_evidence.py --batch discovery/t01-phase1-real/w5/esm-if1-integration-NEW/acceptance-r01 --output discovery/t01-phase1-real/w5/esm-if1-integration-NEW/audit.json
```

把 NEW 换为未存在的批次名；不得覆盖索引/审计输出。只读审计重新核验全部大小/hash、源码快照、当前执行/规则 profile、原生逐位 loss 与基线源；后续实现改动后须用新验收，不能把旧 profile 写成当前。脚本末尾只破坏新运行根中的指定副本做守卫，归档批次保留破坏前发布字节，正常查询使用文档指定的多链任务。共享调度/契约/隔离变更运行完整当前根回归及适用只读冻结校验。

## W5 N11 ProteinMPNN 独立工程接入

请求、固定版本、结构支持域、工程掩码及结果资格见 [W5 本机接口](../project/phase1/PHASE1_REAL_W5_PLAN.md)。需要本机 Docker Linux daemon、固定 GPU 镜像和官方权重；每次实际生成禁网。新验收必须使用尚不存在的运行根和 W5 批次：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_proteinmpnn_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_proteinmpnn_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\proteinmpnn-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w5\proteinmpnn-integration-new
```

第一条复核约束、坐标、资产守卫与已记录原生输出的语义检查，不启动模型；第二条真实执行本地结构及 ProteinMPNN，再单独运行受控故障、取消/超时/恢复和仅新验收副本的篡改检测。上游必须来自同一运行根；不能把旧 ArtifactRef 复制到新根冒充已登记来源。共享运行层变化回归适用开发 Worker；普通文字整理无需重跑 GPU。科学权限、Gate、ESM-IF1、正式候选和 Agent C 不在本包完成口径内。

## W6 ThermoMPNN 与 FoldX 稳定性工具

ThermoMPNN 的精确请求、完整 SSM、R-39 与结果资格见 [W6 本机接口](../project/phase1/PHASE1_REAL_W6_PLAN.md)。普通复核只运行单测；新鲜验收会实际使用固定 GPU 镜像并必须给出尚不存在的运行根和批次：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_thermompnn_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_thermompnn_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\acceptance\w6-thermompnn-integration-NEW --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w6\thermompnn-integration-NEW\acceptance-r01
.\.venv\Scripts\python.exe -X utf8 scripts/audit_thermompnn_evidence.py --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w6\thermompnn-integration-NEW\acceptance-r01 --output D:\work\蛋白智能体\discovery\t01-phase1-real\w6\thermompnn-validation-NEW\evidence-audit-r01.json
```

ThermoMPNN 验收会创建同根结构任务，真实运行完整单体 SSM 和失败后的重试，并验证幂等、请求守卫、取消、超时、崩溃恢复、多链不裁链跳过、来源/产物篡改。原生全量输出与显式比较范围分开；不得只保存筛选子集、取反原分数或与另一引擎求平均。

FoldX 使用用户声明的 5.0 学术包和固定 CPU 镜像；新鲜验收必须给出尚不存在的运行根、批次和审计输出：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_foldx_development.py tests/test_thermompnn_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_foldx_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\foldx-acceptance-NEW --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w6\foldx-integration-NEW\acceptance-r01
.\.venv\Scripts\python.exe -X utf8 scripts/audit_foldx_acceptance.py --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w6\foldx-integration-NEW\acceptance-r01 --output D:\work\蛋白智能体\discovery\t01-phase1-real\w6\foldx-validation-NEW\evidence-audit-r01.json
```

FoldX 验收真实执行 RepairPDB、明确 PositionScan 和每变体 5 次 BuildModel，并覆盖失败重试、取消、超时、崩溃恢复、来源/发布篡改和统一查询。原生 `e/o` 组氨酸互变异构体代码只能在同时核验 HIS PDB、AA20 覆盖和原始行数后归一为 H；原始文件保持不变。用户学术版声明是使用依据，不改写为包内许可回执。结果继续 `DEVELOPMENT_UNREVIEWED / NOT_DEPLOYED`，不得据此完成 N14/N17 或恢复原 24 条候选资格。

## W6 N14/N15 逐变体工程报告

接口、逐变体来源与缺项规则见 [W6 报告接口](../project/phase1/PHASE1_REAL_W6_PLAN.md)。新验收复核归档索引，在新根复制并保留历史任务身份，仅修复新副本中原验收故意损坏的产物；原运行根及归档只读，不重新生成候选或运行模型。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_variant_report_development.py tests/test_design_backend_development.py tests/test_design_backend_sources.py tests/test_foldx_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_variant_report_acceptance.py --root var/t01-phase1-real/variant-report-acceptance-NEW --batch discovery/t01-phase1-real/w6/variant-report-integration-NEW/acceptance-r01
.\.venv\Scripts\python.exe -X utf8 scripts/audit_variant_report_evidence.py --batch discovery/t01-phase1-real/w6/variant-report-integration-NEW/acceptance-r01 --output discovery/t01-phase1-real/w6/variant-report-integration-NEW/audit.json
```

NEW 必须尚不存在。24 条原排除与三条 FoldX 工程突变属于不同 WT/结构，分别验证，不相互赋予稳定性分数；阳性排序为独立数值夹具。末尾篡改探针只修改新根副本并恢复原字节，文档命令仍可查询。共享登记/契约变化执行当前根回归与适用只读冻结校验；未跨历史分区不要求重跑旧完整 Mock/S07。

## W6 N13 表位保护与报告回连

请求、配对身份、计算边界见 [N13 本机接口](../project/phase1/PHASE1_REAL_W6_PLAN.md)。专项不依赖 Docker；真实验收须可访问本机 Docker 固定结构/BepiPred镜像，复制历史报告运行根且保留原身份，分别执行76 aa WT/变体预测与9 aa FoldX工程结构分析，不修改工具长度准入域或原结构来源声明。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -o addopts='' -q tests/test_epitope_protection_development.py tests/test_epitope_protection_evidence_audit.py tests/test_variant_report_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_epitope_protection_acceptance.py --root var/t01-phase1-real/n13-acceptance-NEW --batch discovery/t01-phase1-real/w6/n13-integration-NEW/acceptance-r01
.\.venv\Scripts\python.exe -X utf8 scripts/audit_epitope_protection_evidence.py --batch discovery/t01-phase1-real/w6/n13-integration-NEW/acceptance-r01 --output discovery/t01-phase1-real/w6/n13-integration-NEW/audit.json
.\.venv\Scripts\python.exe -X utf8 scripts/run_epitope_protection_supplement.py --batch discovery/t01-phase1-real/w6/n13-integration-NEW/acceptance-r01 --output discovery/t01-phase1-real/w6/n13-integration-NEW/supplement-r01
```

NEW 与审计／补充目录必须不存在。补充脚本仅在该新验收根追加实际 N06 失败、N09 来源与错链/晚期篡改场景，篡改后恢复源字节。原24条淘汰、已管理复核的N14/N15 r03及历史工具结果只读保留；数字夹具不计真实科学工具证据。共享登记/契约变更须跑当前根回归及适用冻结只读校验；旧完整Mock/S07按是否跨分区分别报告。

## N10 原蛋白可开发性部分基线

请求与结果边界见 [W4 N10 接口](../project/phase1/PHASE1_REAL_W4_PLAN.md)。Biopython 规则在可信本地后端执行；结构型聚集预测固定 `lcbio/a3d_server@sha256:c9e5a38b7d7f22c0b76678c5135ec4bf1af47cf77e8c9547a3bb4b9f7f2e938b`（AGGRESCAN3D 0.9.11），PROPKA 3.5.1 以本地子进程读取已验证结构，二者始终禁网。PDB 保留原字节，mmCIF 只通过 N02 原子账本的可往返固定列投影；A3D 再使用目标链 ATOM-only 投影与标准 `END`，不可改用 `-C` 规避。A3D 原生文件、原始 `.pka`、命令参数、stdout/stderr、派生输入和 observation 均发布并核验。普通复核不重复运行结构链：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_developability_development.py tests/test_domains_development.py tests/test_glycosylation_development.py tests/test_epitope_map_development.py tests/test_deeptmhmm_development.py tests/test_structure_development.py
.\.venv\Scripts\python.exe -X utf8 scripts/run_developability_acceptance.py --root D:\work\蛋白智能体\var\t01-phase1-real\developability-acceptance-new --batch D:\work\蛋白智能体\discovery\t01-phase1-real\w4\developability-integration-new
```

第二条会真实运行结构 FreeSASA、AGGRESCAN3D 结构路径与 PROPKA，必须使用尚不存在的新运行根和 W4 批次，并要求 Docker Desktop Linux daemon 可用且固定 A3D digest 已存在。它不补齐 CamSol 或官方序列聚集备选，也不完成 A3D 空间语义/分类签收和 PROPKA 科学对标；成功只表示当前部分工程链、失败隔离和哈希守卫通过。不得据此填 overall、宣布 N10 完成、触发设计 Gate 或授予科研消费资格。

<details>
<summary>工具实测、历史证据复核和实例操作（按需查）</summary>

## W1-08B2 DeepTMHMM 评审复核

[命令、参数与执行条件](REFERENCE_COMMANDS.md#w1-08b2-deeptmhmm-评审复核)。

## B2 原包执行与复验

[命令、参数与执行条件](REFERENCE_COMMANDS.md#b2-原包执行与复验)。

## B1 → FreeSASA 消费者验证

[命令、参数与执行条件](REFERENCE_COMMANDS.md#b1--freesasa-消费者验证)。

## B1 输入事实工程补强

[命令、参数与执行条件](REFERENCE_COMMANDS.md#b1-输入事实工程补强)。

## W1-08B1 评审准备复核

[命令、参数与执行条件](REFERENCE_COMMANDS.md#w1-08b1-评审准备复核)。

## W1-07 契约设计检查

[命令、参数与执行条件](REFERENCE_COMMANDS.md#w1-07-契约设计检查)。

## 结构预测准备证据复核

[命令、参数与执行条件](REFERENCE_COMMANDS.md#结构预测准备证据复核)。

## R-58 与 FreeSASA 边界开发验证

[命令、参数与执行条件](REFERENCE_COMMANDS.md#r-58-与-freesasa-边界开发验证)。

## DeepTMHMM 学术包禁网证据复核

[命令、参数与执行条件](REFERENCE_COMMANDS.md#deeptmhmm-学术包禁网证据复核)。

## DeepTMHMM 离线准备与公开资料校验

[命令、参数与执行条件](REFERENCE_COMMANDS.md#deeptmhmm-离线准备与公开资料校验)。

## 真实工具公共接口与交接包

[命令、参数与执行条件](REFERENCE_COMMANDS.md#真实工具公共接口与交接包)。

## 本地结构解析与 R-58 映射

[命令、参数与执行条件](REFERENCE_COMMANDS.md#本地结构解析与-r-58-映射)。

## W1 环境与样本准备

[命令、参数与执行条件](REFERENCE_COMMANDS.md#w1-环境与样本准备)。

## FreeSASA 本地原始工具探测

[命令、参数与执行条件](REFERENCE_COMMANDS.md#freesasa-本地原始工具探测)。

## FreeSASA 独立数值参考

[命令、参数与执行条件](REFERENCE_COMMANDS.md#freesasa-独立数值参考)。

## W1-09A 本地通用运行层

[命令、参数与执行条件](REFERENCE_COMMANDS.md#w1-09a-本地通用运行层)。

## 本地 Dify Mock transport

[命令、参数与执行条件](REFERENCE_COMMANDS.md#本地-dify-mock-transport)。

## 会写入状态的验收操作

[命令、参数与执行条件](REFERENCE_COMMANDS.md#会写入状态的验收操作)。

## 开发与资料维护

[命令、参数与执行条件](REFERENCE_COMMANDS.md#开发与资料维护)。


</details>

原始采集/seal/freeze 和 Dify 实例写入入口不作为默认检查。新实测用新批次；不覆盖冻结资产、旧输入输出或 manifest。
模型输出、工程夹具、故障注入分别标识；密钥不进源码、日志、DSL 或文档。
