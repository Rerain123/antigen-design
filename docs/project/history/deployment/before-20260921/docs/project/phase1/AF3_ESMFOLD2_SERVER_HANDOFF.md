# AlphaFold3 / ESMFold2 服务器部署与接口说明

建立：2026-09-10；现行状态更新：2026-09-20。对象：负责目标交付的用户与在已授权范围内直接实施、核验和工程接入的助手。原同事部署分工已取消；保留文件路径以兼容现有链接。技术步骤按现场环境逐项执行。

**现行状态：** ESMFold2已在76残基工程支持域内完成标准结果、统一任务、N01回连、显式N12同次运行、适用生命周期、首条N01–N18工程链及统一单卡Worker真实回归；393残基仍只是一条独立容量案例，科学Gate关闭。AF3权重/数据库已校验并解压，195867个文件独立复核、固定环境、本地CPU数据搜索、单张64GB设备/JAX验证和1UBQ五样本原生推理均已完成并审计。AF3标准适配器及统一任务/N01/S-09接入的第一版本地代码已开始落盘，但尚未完成本地回归、真实原件标准化、部署或第五命令登记。当前不再阻塞于GPU资源校正；实际进度以[STATUS](../STATUS.md#当前任务入口)为准。

**当前执行顺序：** 遵循[专家流程校准计划](../PHASE1_DELIVERY_PLAN.md#专家流程校准与单卡执行计划2026-09-19)：单卡资源基础层与AF3原生阶段已完成；当前先把已落盘的AF3适配器做成自包含模块，完成语法/导入、合成夹具与真实五样本只读标准化验证，再准备受保护部署增量、登记第五个命令并做真实单卡任务；最后执行受影响GPU工具代表性串行回归。已通过的资产盘点和独立科学工具验收不重做。

## 单张A100 64GB资源修正（2026-09-19）

### 现行统一常驻GPU Worker（2026-09-20）

用户最终选择：不创建Role/RoleBinding；Deployment中只保留一个`worker-unified-gpu`，完整申请一张A100 64GB，ProteinMPNN、ESM-IF1、ThermoMPNN和ESMFold2在该容器内按全局FIFO逐个启动。四套工具依赖仍放在独立固定前缀，任务继续使用原resident请求、attempt、进程组、取消/超时和ArtifactRef；资源统一不等于混用科学环境。Worker只读两个既有spool，在`/var/lib/t01/resident/unified-gpu`保存全局owner；任何未确认停止的执行都会阻断下一项。它不访问Kubernetes API、不需要ServiceAccount令牌或命名空间RBAC。

固定镜像为`harbor-core.base.svc.cluster.local/qcyz/antigen-unified-gpu@sha256:ef4586e2849a54a82c97648691b248521b87042123ef624700dc4136d79898fe`。现行不可变ConfigMap为`antigen-unified-gpu-config-r03`和`antigen-unified-gpu-code-r03`；Pod `antigen-design-7887db7f57-5t55g`在`k8s-a100-02`为10/10 Ready、0重启。仅统一Worker声明`gpu=1`、`gpumem-percentage=100`、`gpucores=100`，启动日志确认唯一设备`NVIDIA A100-SXM-64GB`、UUID `GPU-f098e2d4-4cf3-a2c2-3503-6cca5bedde31`、65536 MiB，并登记四个工具。

ESMFold2首次r01验收因统一镜像的`/tmp`别名缺少任务slot而卡住，已通过正式Runtime cancel/reconcile安全收敛，resident回执`stopped_confirmed=true`；r02补slot后暴露监督器预创建`output/native`与原生Worker `exist_ok=False`冲突，按失败回执保留。r03仅对ESMFold2关闭预创建并保留任务私有tmp，真实76 aa推理成功：子任务`t01p1r-job-d263f828aa564e3cb1cecc2e0676340f`、父任务`t01p1r-job-bbc5bd5aab92478785545eb358f53802`均成功，结构、confidence、严格加载与manifest完整，执行停止确认后槽位回到空闲。[r03验收快照](../../../discovery/t01-phase1-real/unified-gpu-worker-20260920/r03/latest.json)保存父任务与各节点状态。科学资格仍为`DEVELOPMENT_UNREVIEWED`、`usable_for_pipeline=false`。

AF3环境已包含在统一镜像基底；项目标准适配器第一版本地代码已经建立，并开始接入统一任务与N01/S-09，但尚未通过测试、部署或登记固定resident命令，因此不得把“代码已写”写成“AF3已进入线上统一任务”。sample 1/4原生pTM同为0.86，全部样本保留；专家原件未指定同分科学优先级，当前最低seed/最低sample序号只用于确定性工程主模型，不使用官方`ranking_score`替代项目pTM规则。验证完成后再把AF3作为第五个命令登记到同一全局FIFO；不得并行创建另一个GPU Job。ProteinMPNN/ESM-IF1/ThermoMPNN保留历史真实结果且新镜像基础依赖检查通过，仍需各一条代表性受影响回归来关闭OPS-002。

### 历史自动单卡调度器候选（2026-09-20，未上线）

以下方案在用户选定统一常驻Worker后停止推进；其代码、测试和清单仅保留历史，Role/RoleBinding不再是现行部署阻塞，也不得与统一Worker同时启用。

当前新增`src/t01_phase1_real/gpu_dispatch.py`和`gpu_once.py`：控制器只读取共享卷既有已提交resident请求，按提交文件时间排队；在共享卷持有进程生命周期锁并保存reserved/running/releasing/idle状态。持久化意图后才修改独立`antigen-design-gpu-slot`；比较Deployment UID/resourceVersion，保持Recreate及0/1副本。完成/失败/取消/超时均须原执行器确认stopped_confirmed，先降为0并等Pod彻底消失，再处理下一请求。控制器崩溃后接回原request hash与target；进程状态不明、Pod无确认收据退出、其他项目GPU占用、配置漂移均阻止新分配，不自动重跑科学任务。单请求Worker运行前核验64GB精确型号/UUID/显存，然后调用原resident执行器，结束后等待控制器释放Pod。

由`scripts/prepare_gpu_dispatcher.py`生成[部署候选](../../../deploy/single-gpu/dispatcher.r01.yaml)，包含两环境：`gpu`保留既定ProteinMPNN/ESM-IF1/ThermoMPNN镜像与命令，`esmfold2`保留独立镜像/模型PVC。共享RWO运行卷通过对CPU服务Pod的required podAffinity保持同节点；控制面不再因每次工具切换而重启。AF3尚无resident标准适配器，当前未登记该模式，待接入后才纳入同一队列。新控制器与GPU Deployment初始副本均为0，未部署。配置、代码、两个Deployment服务器dry-run通过；29项本地检查覆盖FIFO、停止确认、Pod释放、重复派发恢复、取消/失败/超时状态、资源/配置拒绝、现有单卡及AF3解析回归。未进行Linux候选容器运行或真实跨工具验收。

实际部署阻塞为当前账号`m-mcm7t`对Role/RoleBinding无读取/创建权限；SA创建预校验允许。[最小权限清单](../../../deploy/single-gpu/dispatcher-rbac.r01.yaml)仅授权命名空间Pod列表读取和专用`antigen-design-gpu-slot` Deployment的get/patch，不含节点、Secret或主服务Deployment权限。管理员可在项目目录使用既有kubeconfig执行`kubectl --kubeconfig .tmp/himat.kubeconfig apply -f deploy/single-gpu/dispatcher-rbac.r01.yaml`（必须使用具有相应RBAC管理权限的身份）；助手不能以当前账号越权完成。角色准备后，仍应先核验无活动任务，生成适用于generation 25的受保护CPU模式补丁（旧r01补丁不可重用），释放现有ESMFold2 GPU，部署并启用控制器，逐项验证后再开放工具派发。旧部署生成入口回退防护及AF3标准接入继续列为剩余工作，OPS-002未关闭。

**2026-09-20实施进展（覆盖下方旧阻塞结论）：** 用户授权部署后，按HAMi官方`use-gputype`、`gpumem-percentage=100`、`gpucores=100`准备清单并通过服务器dry-run；无需将node读取权限作为强制前置。先核对73个业务任务全部终态，再应用resourceVersion/UID/spec三重保护补丁，Recreate释放原两个40GB GPU容器；generation 24 CPU维护模式9/9就绪。独立探针在`k8s-a100-02`分配唯一`GPU-f098e2d4-4cf3-a2c2-3503-6cca5bedde31`，型号`NVIDIA A100-SXM-64GB`，HAMi分配65536 MiB/100核心，JAX 0.9.1单设备矩阵计算通过。随后同UUID五样本AF3推理完成，独立审计通过；详见[审计](../../../discovery/t01-phase1-real/af3-target-20260920/single-gpu-r01/audit-summary.json)。原推理Job因末端文件名前缀检查错误保持Failed，不改终态；26份原始文件及失败记录保留，独立只读审计另记成功。单链ipTM原生null；sample 1/4的原生pTM同为0.86，标准封装前不自行发明同分选择规则。

AF3结束后准备只恢复`worker-esmfold2`的generation 25补丁，精确型号/UUID/显存启动守卫通过才启动resident_worker，原`worker-gpu`不恢复。当前这套切换由助手顺序执行，尚无后端自动模式切换。ProteinMPNN/ESM-IF1/ThermoMPNN常驻GPU入口因此暂不可执行；恢复这些工具前须先释放ESMFold2分配。13项切换/设备拒绝/输出解析测试通过。原补丁和快照存于本地`.tmp/single-gpu-cpu-r01`与`.tmp/single-gpu-esmfold-r01`，可能含服务配置，不对外发布。源码入口为`scripts/prepare_single_gpu_cpu_mode.py`、`scripts/prepare_single_gpu_esmfold_mode.py`及`scripts/run_af3_inference.py`；OPS-002仍需自动互斥、旧入口守卫、失败恢复和工具迁移回归后关闭。

**续行预检（2026-09-20）：** 用户已要求继续执行，取消此前主动暂停；助手可执行的操作由助手继续承担。只读回查Deployment仍为generation 23、1个Ready副本、Recreate策略，快照resourceVersion为`46160507`（后续生成补丁必须重新读取，不复用该旧值）。Running Pod仍为`antigen-design-9f86d7f66-xsqqn`，HAMi分配下表两枚不同UUID；没有完成单卡切换。历史成功验证r03在`k8s-a100-02`分配`GPU-fc605496-6212-6a39-2e34-93403d832611`、393案例分配`GPU-b3031d22-ea79-a720-dbcd-77bd92cce593`，两者均仅申请32768 MiB；历史成功不能证明当前完整64GB可调度。

已核验AF3数据库/模型/运行卷及常驻运行/工具资产/ESMFold2模型共6个PV均为Bound、驱动`rbd.csi.ceph.com`、无nodeAffinity；未发现卷规格绑定旧节点，但RWO切换仍须等待原挂载释放。命名空间查询未返回ResourceQuota或LimitRange对象，这不构成64GB额度批准。账号`m-mcm7t`读取目标node返回Forbidden，读取`kube-system` ConfigMap权限检查为no；目前不能核实目标节点标签、可分配容量及实际HAMi配置。该限制来自集群RBAC，不是本地自动审批拒绝。

**当前精确阻塞及交接信息：** 运维需提供获准单卡的节点名称/选择标签、UUID、实际可用显存及当前HAMi设备选择注解和资源值（包括`nvidia.com/gpu`、显存单位/上限及是否要求独占核心）；或提供目标节点和相关HAMi配置的只读访问。无需开放节点写权限。拿到信息后才能生成有依据的64GB目标补丁，执行dry-run、暂停派发/等待任务终态、释放旧GPU分配和单卡验收。当前仅完成现场预检，未生成可应用的目标补丁、未执行切换或AF3推理；OPS-002仍开放。

用户硬约束：整个项目同时最多使用一张 `NVIDIA A100-SXM-64GB`，禁止40GB替代。该约束覆盖ProteinMPNN、ESM-IF1、ThermoMPNN、ESMFold2、AF3及临时GPU验收Job；不修改历史结果中的真实设备身份。

本次只读现场复核：常驻Pod `antigen-design-9f86d7f66-xsqqn`位于`k8s-a100-01`，两个GPU容器分别申请`nvidia.com/gpu=1`，HAMi显存限额10240/30000 MiB。两容器`nvidia-smi --query-gpu=name,uuid,memory.total --format=csv,noheader`返回：

| 容器 | 设备型号 | 物理UUID |
|---|---|---|
| worker-gpu | NVIDIA A100-SXM4-40GB | GPU-60efd96d-3f20-1057-4f62-ed24561b9f1e |
| worker-esmfold2 | NVIDIA A100-SXM4-40GB | GPU-53cfb869-cb43-8ac4-6a0c-b46b4d5202a8 |

这是两张不同40GB卡的资源分配，不符合单张64GB要求；显存列为容器切片额度，不能作为物理卡容量证明。历史64GB实跑位于`k8s-a100-02`，仅作定位线索，不能推断该节点所有卡均为64GB或直接写死未知标签。

**实施方案与验收：** 优先准备互斥GPU模式，复用各模型既有环境，避免为修正调度强行合并不兼容依赖。切换时暂停新GPU派发，等待已有任务终态，释放旧GPU容器/Pod资源并核实释放，再启用所选工具环境；仅停止计算进程不算释放Kubernetes GPU分配。CPU服务及无GPU解压保持独立。自动流程需要由后端负责排队和模式切换，不要求用户逐工具手工拼接任务。

1. 只读确认可调度64GB设备的节点标签、资源键、HAMi设备选择机制及UUID；缺权限时由运维提供已验证信息，不猜测标签/注解。检查PVC节点亲和及目标节点容量。
2. 准备带resourceVersion保护的新部署补丁和互斥执行控制；同一时点全项目仅一个GPU资源申请者，单卡数量为1，绑定获准64GB设备。常驻Worker、独立AF3/ESMFold2 Job及旧部署生成入口均纳入检查，不能只改一个清单。
3. 新任务启动前运行精确型号、可见设备数量和UUID守卫；不是指定64GB或可见多卡时拒绝执行，不回退40GB。历史standard/audit中40GB解析资格保留为历史事实，不能以删除旧环境元组来伪装修正调度。
4. 本地验证双GPU申请拒绝、40GB拒绝、模式切换/失败回退/取消及任务恢复不重复分配；准备服务器dry-run。用户应用后核对Pod资源与节点、HAMi唯一物理UUID、运行时CUDA设备三层证据，并做受影响工具最小回归。

**完成边界：** 本轮已完成现状核实和修正计划，尚未生成可应用补丁、未切换/重启Deployment，线上仍不合规；OPS-002未关闭。AF3 r03解压为无GPU任务且已成功产生回执，不受此项阻断。下一次GPU实跑前必须先完成本节实施与验收。

**原始起点（2026-09-10，历史）：** 项目可使用1张A100、可用显存64GB，当时服务器尚未部署AF3和ESMFold2，计划从零安装、备齐资产并实跑。首轮部署估算为32 vCPU、192 GiB内存和2 TiB持久存储，GPU工具串行运行；实际资源身份以后续现场证据为准。本段只保留最初部署背景，不表示当前仍未部署ESMFold2。

**交付目标：在目标服务器上部署两个本地结构预测引擎，提供统一的文件式命令接口，完成真实禁网预测，并交回源码、固定环境、调用示例与原始验收产物。** 本文可单独转交，无需先阅读整个项目。

本文最初定义需要实现的Worker交接接口`t01.structure-worker/0.1`。ESMFold2侧现已完成统一任务登记和目标工程验收；AF3侧仍以本文接口为待实现目标，尚不能通过现有统一任务层调用。下方历史示例只有在对应回填明确记录真实执行后才算完成，示例命令本身不构成部署证据。

## AF3权重下载准备（2026-09-17）

**权重下载完成：** 用户回传r02成功日志，助手只读回查`antigen-af3-weights-download-r02`为Complete、succeeded=1（完成时间2026-09-17T01:40:00Z），日志大小/hash一致。`af3.bin.zst`为1020545840字节，官方CRC32C `0h6mjg==`校验通过，SHA-256 `74d0258616917cd122f5eab6d076afe4a8930e96823851e65e4f777dfb1f33ff`。文件及`download-receipt.json`由下载器保存在PVC `antigen-af3-models`内的`/weights/alphafold3-official-r01`（目录沿用r01，任务为r02）；本轮只回查日志/Job，未另挂卷重新计算hash。权重尚未解压、加载或用于推理；数据库随后已完成归档下载，现行状态见下一节。以下记录保留先前准备与失败时点事实。

**r01实际失败与r02修复：** 用户已导入r01，20Gi卷`antigen-af3-models`为Bound；下载Job四次尝试均在HEAD校验阶段失败，最终`BackoffLimitExceeded`。官方实际对象为1020545840字节，ETag `"-COWBlqWv7ZQDEAQ="`，仅提供`x-goog-hash: crc32c=0h6mjg==`，没有MD5；原下载器强制MD5属于实现错误，未开始正文下载。已修复为核验官方提供的MD5和/或CRC32C，兼容重复校验响应头，仍强制至少一种官方校验及大小/ETag身份，保留续传守卫与本地SHA-256。标准CRC32C向量、真实头形态、损坏拒绝及原续传回归共11项通过。新[r02清单](../../../deploy/alphafold3/weights-download.r02.rancher.yaml)使用新不可变ConfigMap和Job，复用原卷与资产目录；服务器dry-run通过，交用户导入启动，旧r01失败记录保留，不删除PVC。以下6项测试与MD5描述保留r01准备时点事实。

用户使用Rancher Kubernetes Shell，已从service容器对官方权重地址执行HEAD并回传`HTTP: 200`。现已准备[可导入Rancher的清单](../../../deploy/alphafold3/weights-download.rancher.yaml)：在`him-ws`创建独立`antigen-af3-models` 20Gi ceph-rbd PVC、不可变脚本ConfigMap及`antigen-af3-weights-download-r01` Job；导入即开始下载，最多3次失败重试、48小时期限，不申请GPU。使用已发布控制面固定digest作为Python下载容器，不启动控制服务；不挂载ESMFold2卷。清单已通过服务器dry-run，尚未由助手实际应用，不能记为权重已下载或PVC已创建。

[下载器](../../../scripts/download_af3_weights.py)只访问官方`https://storage.googleapis.com/alphafold3/af3.bin.zst`，保存源URL、大小、ETag及官方MD5；断点续传检查206及精确Content-Range，使用If-Match防止对象变更混入，失败保留partial，完成后比对官方MD5并生成本地SHA-256。新下载、零字节中断恢复、续传/重复核验、拒绝忽略Range、拒绝损坏字节及源对象变化共6项测试通过。成功日志`AF3_WEIGHTS_VERIFIED`；资产与回执保留在卷内`/weights/alphafold3-official-r01`。本次不解压、不加载权重、不下载数据库，科学Gate继续CLOSED。

数据库的科学依据：[SOP S-08](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md)明确`AF3自带MSA搜索管线(jackhmmer→UniRef/BFD)`，[结构ToolSpec §2b](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md)保留WT MSA复用，不能默认改无MSA推理。此前“先盘点服务器已有AF3库”的安排已被用户本轮澄清覆盖，当前执行以下下载步骤。

## AF3数据库下载（2026-09-17）

**最新完成记录：** 用户回传Job `antigen-af3-databases-download-r01`为Complete 1/1、DURATION 3h37m；Pod `antigen-af3-databases-download-r01-hbcfr`为Succeeded，无法继续exec是正常终态。最终日志为`AF3_DATABASES_ARCHIVES_VERIFIED 9 238784443666`，9份归档全部通过下载器校验；最后一份`mgy_clusters_2022_05.fa.zst`大小69333008025字节、SHA-256 `584b0918d0d31a7284e38127f46e4a98544efa40c5ef8a609c7e17a547dc76ed`。依据为用户回传日志，助手未另挂卷复算。保留Job、独立1Ti PVC与归档；当前并行阶段只准备只读挂卷盘点、实际空间核算和安全解压清单/dry-run，首条N01–N18工程链闭环后再实际解压并核验所需目录和文件，随后执行AF3环境与管线验收。下载完成不等于数据库已解压可用。以下下载操作保留历史说明，不需重新启动。

**只读挂卷盘点r02已准备（2026-09-19）：** r01实际创建后终态Failed/BackoffLimitExceeded，日志定位为权重PVC根挂到`/models`却读取`/models/weights/alphafold3-official-r01`，多写一层目录；失败发生在数据库逐项检查之后、权重回执读取之前。两个PVC均以只读方式挂载，r01未修改任何资产；保留原Job/Pod/日志，不重建同名任务。[检查脚本](../../../scripts/inspect_af3_assets.py)不变，[r02清单](../../../deploy/alphafold3/assets-inspect.r02.rancher.yaml)改为把权重PVC根挂到`/weights`并读取`/weights/alphafold3-official-r01`。它复核固定manifest、9份归档/逐文件回执/大小、权重回执与实际文件系统总量/可用量；按官方约630GB展开估算另留64GiB规划余量，只作是否可进入解压的初筛，不把估算当实际展开大小。Job禁网、无SA token、无GPU、不写PVC、不解压；25项下载/盘点回归及Kubernetes服务器dry-run通过。该检查已由用户导入r02并成功，结果见下一节。

**r02盘点结果与安全解压准备（2026-09-19）：** 用户运行r02成功。数据库卷总量`1081101176832`字节、可用`842299772928`字节；9份归档合计`238784443666`字节，按约`630000000000`字节展开估算及`68719476736`字节规划余量，所需`698719476736`字节，`provisionally_sufficient=true`。权重卷可用`19920080896`字节，权重文件`1020545840`字节、SHA-256为`74d0258616917cd122f5eab6d076afe4a8930e96823851e65e4f777dfb1f33ff`；科学Gate仍CLOSED、生产NOT_DEPLOYED。

安全解压r01在首个FASTA文件遇到流式libzstd EOF边界bug后失败，r02在第3个归档因2GiB内存上限被`OOMKilled`/退出137；原归档、旧partial及Job/Pod/日志均保留。r03改用1MiB可复用解码缓冲、256KiB tar缓冲和周期性flush/fsync/fadvise，流式重算每份压缩源SHA-256；PDB tar逐成员拒绝绝对路径、`..`、重复项、符号/硬链接和设备文件。用户回传Job `Complete 1/1`、实际运行3h8m，终标记为`AF3_DATABASES_EXTRACTED_VERIFIED 195867 672435030513`且JSON回执一致：输出已从`unpacked-r03.partial`原子发布为`unpacked-r03`。2026-09-20独立只读复核Job `antigen-af3-extraction-inspect-r01`终态`Complete 1/1`，约1小时49分内全量重算195867个文件SHA-256并全部通过：195859个`mmcif_files/`文件、8个根级数据库文件，总计672435030513字节（672.44GB/626.25GiB）。数据库卷总量1081.10GB、已用914.74GB、可用166.35GB（154.92GiB）。复核状态为`AF3_DATABASES_EXTRACTION_INDEPENDENTLY_VERIFIED_NOT_DEPLOYED`；解压独立复核已关闭，但本地数据搜索、权重加载和推理仍未验证，科学Gate保持CLOSED、生产保持NOT_DEPLOYED。

用户确认当前应下载 AF3 数据库，见[决定登记](../DECISIONS.md#数据库位置澄清)。专家原件明确科学上需要本地 MSA；完整工程文件清单来自[官方 v3.0.2 下载脚本](https://github.com/google-deepmind/alphafold3/blob/v3.0.2/fetch_databases.sh)，数据集版本为 `alphafold-databases/v3.0`。[同版本启动程序](https://github.com/google-deepmind/alphafold3/blob/v3.0.2/run_alphafold.py)在构建数据管线配置时检查全部数据库路径，因此采用其9项标准包，未通过空文件或禁用MSA绕过检查；包含RNA数据不表示扩大一期蛋白单链业务范围。此处固定的是数据库下载依据，AF3运行环境commit仍待部署验证。

已逐对象HEAD确认9个压缩包HTTP成功、大小、ETag、generation及官方MD5/CRC32C，固定[下载清单](../../../deploy/alphafold3/database-manifest.v3.0.json)，总计238784443666字节（约238.8GB/222.4GiB）。其中蛋白MSA为Small BFD、MGnify、UniRef90、UniProt，模板为PDB mmCIF和PDB seqres，其余为NT-RNA、Rfam、RNAcentral。官方安装文档估计解压后约630GB；申请独立1Ti ceph-rbd卷，预留压缩包与解压数据空间，实际Ceph可分配容量须以PVC Bound和后续卷内空间检查为准，dry-run不证明容量已分配。

[Rancher导入文件](../../../deploy/alphafold3/databases-download.r01.rancher.yaml)包含`him-ws/antigen-af3-databases` PVC、不可变ConfigMap与`antigen-af3-databases-download-r01` Job。使用已发布固定digest的Python容器，UID/GID10001，不申请GPU；只挂载独立数据库卷和脚本，不触碰ESMFold2上传或AF3权重卷。按文件从小到大串行下载；7天期限、最多6次失败重试，网络失败保留partial并续传。对象变化、Range未兑现、空间不足或MD5不匹配会失败；不会把错误数据标为完成。每份归档验证官方MD5并记录本地SHA-256，保留官方CRC32C源值但本任务不重复计算CRC32C。

操作：在Rancher选择目标集群，Import YAML粘贴上述文件的完整内容并导入（资源已指定him-ws）；导入即开始服务器下载。随后在Kubernetes Shell执行：

```sh
kubectl -n him-ws get pvc antigen-af3-databases
kubectl -n him-ws get job antigen-af3-databases-download-r01
kubectl -n him-ws logs -f job/antigen-af3-databases-download-r01 --pod-running-timeout=180s
```

如果PVC持续Pending，执行`kubectl -n him-ws describe pvc antigen-af3-databases`查看Events；不要反复新建卷。若Job重试产生多个Pod，先执行`kubectl -n him-ws get pods -l job-name=antigen-af3-databases-download-r01 --sort-by=.metadata.creationTimestamp`，再对最新Running的具体Pod查看日志，避免`logs job/...`选到旧失败Pod。关闭Shell或日志连接中断不停止Job；重连只查看状态，不重复导入新任务。

压缩包与逐文件回执写入卷内`/databases/alphafold3-v3.0/archives`。全部下载成功标记为`AF3_DATABASES_ARCHIVES_VERIFIED 9 238784443666`，同时生成总回执`download-receipt.json`。这只表示归档下载和校验完成；后续还需安全解压、登记解压文件清单、配置本地数据路径并真实执行AF3管线，科学Gate保持CLOSED。

本轮22项权重/数据库下载器回归通过，三资源服务器dry-run通过；从现有service容器只读获取PDB seqres归档头部32字节，返回`206 bytes 0-31/26493534`，证明服务器当前可访问该源并支持Range。尚未由助手应用或启动下载。当前成果是可导入配置，不能登记为数据库已下载或部署通过。文档检查仅报旧实跑归档`backend-report.md`的`data.json`和`manifest.json`两条既有缺失链接，本轮未修改冻结报告。

**用户启动回填：** 用户随后报告数据库正在下载；助手只读确认`antigen-af3-databases-download-r01`为Running、0/1（查询时约7分钟）。本轮不干预该下载任务，完成/解压/管线验收仍待后续证据。

**日志连接中断排查：** 用户随后报告Rancher下载“断掉”；助手只读回查同一Job仍active=1/ready=1、Pod Running/0重启（运行约72分钟），UniRef90归档33271639594字节已验证，UniProt最新日志为11639193600/48688827585字节（23.9%）。未观察到下载进程中断，按日志连接中断处理，不创建重试任务或更换下载器。当前后台Job与网页/终端日志连接独立；可在Rancher Shell使用`kubectl -n him-ws logs job/antigen-af3-databases-download-r01 --tail=12`单次查进度，配合`kubectl -n him-ws get job antigen-af3-databases-download-r01`查终态。若后续Pod真实失败，现有Job最多6次重试、partial留在PVC并可续传；只有最终Failed才另查失败原因并准备新Job复用原卷，不能将重新打开日志视作重新开始下载。

## 环境构建与轻量部署进度（2026-09-17）

现行进度以本节为准，后文“未创建PVC”“尚未安装环境”等保留09-16早期时点事实。用户2026-09-17报告模型上传完成；助手通过现有`antigen-esmfold2-assets-upload` Pod只读重算全部23份文件，26791863243字节的大小/SHA-256全部一致；manifest SHA-256 `77ec2cdd4003e59a5c328ce99858be7e2ce42b8b2d7902971e74426f26a39a8f`与profile相符。模型PVC剩余36281724928字节。核验日志保留`.tmp/esmfold2-upload-verification-20260917.log`；未修改模型、上传进程或启动推理。用户最新要求可操作环节尽量自行操作，助手准备步骤与核验。

- **固定环境本地通过：** Python 3.12.14、Torch 2.7.1+cu126、Biohub esm 3.3.0固定源码及Transformers 4.57.6固定源码构建完成。完整环境镜像manifest为`sha256:34e2c26c1865740cb427e21d1df6e925e868454a7f1833563f54a639100b7157`；禁网、只读、UID10001导入通过，包含Triton所需gcc/libc6-dev。
- **目标存储阻塞及调整：** 完整Worker镜像`sha256:7f54308a9f00fe2d53b82f6a60bbc767cb14d8599aedf8894ca98ac3795d26c6`在A100节点拉取成功，随后因节点ephemeral-storage不足被驱逐（137），不能作为远端import或推理成功。为减小节点镜像占用，将Python依赖移入PVC目录，Worker仅保留解释器、编译器与包装器；最新轻量镜像已发布`qcyz/antigen-esmfold2:standard-worker-pvc-20260916-r04`，固定digest `sha256:372545ebe3469a3d32269c27033d19624d713d75ca162dbe6fff5dafed44f77f`。
- **依赖包已上卷，待解压：** 用户回传`ESMFOLD2_ENVIRONMENT_ARCHIVE_UPLOADED 4 3243028640`；4份远端SHA-256与固定清单一致，助手核对本地上传回执与日志一致。`site-packages.tar.gz`为3236572234字节，SHA-256 `c31cc6de03e21227e0be601e97d917b02aeeb6a878ef29a6c08214096ce1b4d9`；解压清单35514文件、6142561244字节。目标目录`/models/esmfold2-environment-20260916-r01`。外层manifest hash `c719aade5db1dacf747cf1f882061a132558ae359bc5a5dd58fc1f5c955bab39`已固定在[profile](../../../deploy/esmfold2-standard/profile.server.json)；Worker在导入前校验归档、依赖清单及全部解压文件。尚未执行目标解压、GPU导入或推理。
- **集群准备：** 模型PVC 60Gi、runtime PVC 10Gi已创建且Bound；独立ConfigMap `antigen-esmfold2-validation-r01`已更新当前profile/request；[Job清单](../../../deploy/esmfold2-standard/validation.job.yaml)固定轻量digest、只读挂载PVC根至`/models`、显式临时磁盘请求/限制，服务器dry-run通过。无出站NetworkPolicy已准备并应用；尚未创建推理Job，32GiB GPU配额尚未证明可完成标准模型预测。

最新回填：用户执行安装后回传`ESMFOLD2_ENVIRONMENT_READY 35514 6142561244`，助手只读回查`installation-receipt.json`状态为`PVC_ENVIRONMENT_EXTRACTED_VERIFIED_NOT_GPU_TESTED`，文件数、字节数及固定manifest hash一致。上述“待解压”保留准备时点事实，当前解压已通过。下一步按下文启动A100验证；现有已通过工具成果保留，AF3及科学签收仍待完成。

### 环境包上传操作（2026-09-17）

已准备独立[环境上传脚本](../../../scripts/upload_esmfold2_environment.py)，沿用模型上传成功的分块续传通道，使用不同端口18743与独立目标目录`/models/esmfold2-environment-20260916-r01`。通过现有上传Pod的exec和仅绑定127.0.0.1的port-forward传输；上传前逐项校验本地文件，服务端完成时重算SHA-256，重复运行复核已完成文件并续传partial，失败保留已传字节。完成后请求退出临时接收进程，关闭本机转发。此脚本只上传环境材料，不解压、不导入环境、不启动推理。

本机`--check-only`已确认4份文件共3243028640字节，包含环境外层manifest；外层manifest与Worker profile固定hash一致。回环服务实测续传、重复核验、远端损坏拒绝、本地损坏拒绝及Worker回归共14项通过。只读确认上传Pod仍为Running；未由助手启动环境上传。

由用户在**本机Windows PowerShell**执行，不能在Rancher Kubernetes Shell执行本机路径：

```powershell
Set-Location 'D:\work\蛋白智能体'
.\.venv\Scripts\python.exe -u -B -X utf8 scripts/upload_esmfold2_environment.py
```

完成标记为`ESMFOLD2_ENVIRONMENT_ARCHIVE_UPLOADED 4 3243028640`，回执保存在`.tmp/esmfold2-environment-upload-20260917-r01/receipts.json`。运行时保持本机联网、不休眠；网络中断退出后可重跑同一命令。保留`antigen-esmfold2-assets-upload` Pod供后续解压核验；待环境就绪再由用户按步骤释放上传Pod、启动GPU验证，不能同时任意新建另一份RWO卷挂载任务。

### 环境解压与核验操作（2026-09-17）

用户已完成上述环境上传，上传回执`.tmp/esmfold2-environment-upload-20260917-r01/receipts.json`的4项complete/hash/大小与用户日志一致。以下是下一步，由用户执行；助手本轮只准备脚本并本机测试，未改变目标卷。

[安装脚本](../../../scripts/install_esmfold2_environment.py)通过kubectl exec在现有上传Pod运行标准库代码，固定环境目录和外层manifest hash，逐项复核归档、清单及依赖锁；检查空间后解压到同卷暂存目录，只接受清单内普通文件，拒绝路径越界、链接、重复/缺失/损坏文件。35514份文件逐项大小/SHA-256及完整文件集合通过后，原子发布`site-packages`目录，生成独立`installation-receipt.json`，原归档保留。已有正式目录只核验，不覆盖；中断重跑可重建暂存目录中的文件。Linux文件锁阻止并发安装；不安装系统依赖、不修改模型、不申请GPU。

本机解压、重复核验、后续篡改拒绝、危险成员拒绝、源/内容损坏拒绝、中断暂存恢复、空缓存目录兼容与Worker回归共19项通过。真实归档完整扫描确认35514份文件及6142561244字节与清单一致；空目录不属于文件清单，解压仅按已接受文件创建父目录，不将空缓存目录误判成缺失资产。用户在**本机Windows PowerShell**执行：

```powershell
Set-Location 'D:\work\蛋白智能体'
.\.venv\Scripts\python.exe -u -B -X utf8 scripts/install_esmfold2_environment.py
```

预期最后出现`ESMFOLD2_ENVIRONMENT_READY 35514 6142561244`。中间打印`ENVIRONMENT_SOURCE_VERIFY`、`ENVIRONMENT_UNPACK_PROGRESS`、`ENVIRONMENT_VERIFY_PROGRESS`；保持终端连接，失败时保留日志及暂存字节。该标记只证明环境文件已解压并核验，不代表Python3.12/CUDA导入、权重加载或真实预测已通过。确认后再由用户按后续步骤释放上传Pod并启动固定GPU验证Job，科学Gate保持CLOSED。

### A100验证启动操作（2026-09-17）

**用户启动回填：** 用户删除临时上传Pod并应用r02成功，首次logs返回ContainerCreating。助手随后只读describe确认`antigen-esmfold2-validation-r02-ww927`已Running/Ready、0重启，调度至`k8s-a100-02`，HAMi分配32768MiB；模型/运行两卷Attach成功，固定轻量镜像约111.9MB、1.756秒拉取，容器2026-09-17 10:55:52 +0800启动。事件均为Normal，最初日志错误发生在容器创建期间，不构成模型失败；模型加载与预测结果仍待核验。以下“尚未创建”保留准备时点事实。

模型与环境卷就绪后，新建[r02验证清单](../../../deploy/esmfold2-standard/validation.r02.rancher.yaml)：沿用已发布轻量镜像digest，创建不可变`antigen-esmfold2-validation-r02` ConfigMap与同名Job，固定76残基ubiquitin工程序列，输出独立`/runs/engineering-r02`。旧r01配置和证据保留。该清单包含匹配验证Pod标签的无出站策略，模型/环境卷只读、输出卷可写；沿用HAMi调度、32GiB GPU显存、32Gi主机内存请求/64Gi限制及7200秒期限。实际可调度性、显存容量与网络阻断效果仍须目标实跑证明，不能由dry-run推定。

为保留失败日志，r02不设置自动TTL清理且不自动重试；仅包装启动/成功日志，原Worker异常退出照常传播。13项清单/Worker受影响测试通过，三资源服务器dry-run通过。集群只读检查时上传Pod仍Running，AF3数据库Job独立Running，未创建ESMFold2验证Job。上一轮自动审批先后遇到用量及登录令牌错误、没有执行生成操作；用户续行后已通过正常审批重试，本地清单生成与服务器预校验完成，无剩余审批阻塞。

用户在本机Windows PowerShell逐条执行。先释放临时上传Pod的卷挂载，保留模型PVC、模型和环境文件；等待命令成功后才启动验证任务：

```powershell
Set-Location 'D:\work\蛋白智能体'
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws delete pod antigen-esmfold2-assets-upload --wait=true --timeout=180s
kubectl --kubeconfig .tmp/himat.kubeconfig apply -f deploy/esmfold2-standard/validation.r02.rancher.yaml
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws logs -f job/antigen-esmfold2-validation-r02 --pod-running-timeout=300s
```

若任一步失败，保留输出并排查，不删除PVC、不覆盖旧输出，也不直接重建同一任务。仅日志等待超时时先用`kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws get pods -l job-name=antigen-esmfold2-validation-r02 -o wide`查看调度/拉取状态。启动日志为`ESMFOLD2_VALIDATION_START asset_verification_then_model_loading`，随后完整资产重验阶段可能暂时没有日志；最终成功日志为`ESMFOLD2_VALIDATION_COMPLETED engineering_result_requires_review`。仍须回查Job Complete、原生结构/置信度/执行回执及产物hash，才能确认这次工程预测成功。科学Gate继续CLOSED，不自动接入完整业务链。

### ESMC权重布局修复与r03启动（2026-09-17）

用户提供r02完整日志，助手只读确认Job Failed、Pod退出1，结束时间2026-09-17T02:58:18Z。6份权重分片读取后出现大量`newly initialized`编码器参数，随后在扩散结构头`torch.linalg.svd`报不收敛；旧结果不能用于工程预测验收或科学消费。现有哈希验收只证明传输完整，未证明代码与权重布局兼容，这是准备检查的缺口。缺少Transformer Engine/xformers/flash-attn的回退警告须保留，但本次已证明的加载错误是布局不匹配，不能仅安装加速库或重试SVD来掩盖它。

固定的ESMC-6B revision `7d0f99a8b716749ad1a0328181c1e0339691b0c2`使用`esmc.embed_tokens/layers.*`及分离q/k/v、gate/up；固定环境的Biohub Transformers `ef32577…`加载器期待`embed/transformer.blocks.*`和合并矩阵。[官方布局代码](https://github.com/Biohub/esm/blob/43b4548b86762edfa747b07d5f440aad3c33acee/esm/models/esmc/checkpoint_layout.py)明确两种布局按行拼接/拆分可逐值往返，不需转置或改变训练值。独立[严格加载器](../../../deploy/esmfold2-standard/esmc_strict_loader.py)按该固定依据实现：先核对所有原分片键及形状，逐参数读取有限fp32训练值并按原profile转bf16上GPU，完整加载802个编码器参数；1042份源编码器张量均被覆盖，独立masked-LM输出头6份明确不用于裸编码器，与官方加载裸编码器的边界一致。无缺失参数随机初始化或静默放行。原始模型文件和环境清单不写回。

独立[r03 Worker](../../../deploy/esmfold2-standard/run_structure.r03.py)另要求折叠模型`missing/unexpected/mismatched/error`全部为空，保存`checkpoint-loading.json`；使用原数值参数、SVD算法和32GiB GPU预算，不修改旧失败。修复文件嵌入不可变ConfigMap并在运行前核验SHA-256，使用既有轻量镜像及只读模型卷，输出`/runs/engineering-r03`。无需重新上传大文件或重建基础环境。

验证：本机原环境容器禁网/只读运行小型真实ESMC模型，与固定官方`native_to_published`产生的权重往返；全部参数及fp32前向输出逐值相等，缺键、多余键、错误形状、NaN拒绝通过。真实6B的1048份分片头映射及形状全部通过；这不代表在本机加载了完整6B数值。真实折叠模型约939MB权重在CPU加载，四类错误列表均为空；CPU审计进程单独禁用GPU专用Triton导入以完成加载检查，交付Worker不含此处理。主机20项受影响测试及服务器三资源dry-run通过。来源源码、测试脚本、用户日志与边界见[修复证据](../../../discovery/t01-phase1-real/esmfold2-layout-repair-20260917/r01/summary.json)。GPU完整严格加载与预测仍待用户启动r03，SVD错误是否随正确加载消失不预先保证。

用户在本机Windows PowerShell执行；r02已失败且无运行进程，保留原Job/Pod/输出，不需再次删除上传Pod：

```powershell
Set-Location 'D:\work\蛋白智能体'
kubectl --kubeconfig .tmp/himat.kubeconfig apply -f deploy/esmfold2-standard/validation.r03.rancher.yaml
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws wait --for=condition=Ready pod -l job-name=antigen-esmfold2-validation-r03 --timeout=300s
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws logs -f job/antigen-esmfold2-validation-r03
```

检查新日志中的`ESMFOLD2_PARAMETERS_STRICTLY_LOADED missing=0 unexpected=0`、`ESMC_KEY_MAPPING_VERIFIED 802 1042`和`ESMC_PARAMETERS_STRICTLY_LOADED 802 missing=0 unexpected=0`，再看推理与终态。若Ready等待超时或失败，先回查Pod/Job，不重复apply新批次；任何仍出现编码器`newly initialized`的结果均不能验收。科学Gate保持CLOSED。

### r03结果读取与核验（2026-09-17）

用户应用r03并wait Ready成功，随后`logs -f`返回HTTP/2 `INTERNAL_ERROR`。助手只读回查Job已Complete、succeeded=1，Pod `antigen-esmfold2-validation-r03-g5nzv`为Succeeded、退出0、0重启；容器从2026-09-17T03:13:25Z运行到03:16:13Z，Job于03:16:16Z完成。日志确认折叠模型零缺失、ESMC映射802/1042并严格加载全部802参数、进入推理后出现`ESMFOLD2_VALIDATION_COMPLETED`。此次SVD未再报错，原r02失败仍保留。缺少可选加速库的数值回退警告保留，不将本次工程完成解释为不同数值后端科学等价。

进程已结束，不能再向完成容器exec读取结果；[只读结果Pod](../../../deploy/esmfold2-standard/results-reader.r03.yaml)仅挂载既有runtime PVC至`/runs`，不申请GPU/不挂模型卷，使用匹配既有禁止出站策略的标签，2小时期限。[收集脚本](../../../scripts/collect_esmfold2_r03.py)要求r03 Job Complete，读取固定目录`/runs/engineering-r03`，在服务器与本机验证文件集合、大小/SHA-256、结果身份及关闭的科学资格；本地不同字节拒绝覆盖。用户已执行以下命令，8份原始产物共67351字节成功保存到`discovery/t01-phase1-real/esmfold2-target-20260917/r03`，另存Job与日志。以下为已执行的读取步骤，不需要重复创建Pod或重跑模型。

用户在本机PowerShell依次执行：

```powershell
kubectl --kubeconfig .tmp/himat.kubeconfig apply -f deploy/esmfold2-standard/results-reader.r03.yaml
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws wait --for=condition=Ready pod/antigen-esmfold2-results-r03 --timeout=300s
.\.venv\Scripts\python.exe -u -B -X utf8 scripts/collect_esmfold2_r03.py
```

**独立工程产物核验通过：** [审计脚本](../../../scripts/audit_esmfold2_r03.py)复核原始8份文件大小/hash、固定请求/profile与实际Job容器/卷配置、序列hash及结果引用、严格权重加载记录。mmCIF解析为一个模型、A链76残基、601原子；序列逐位一致，无重复原子身份，N/CA/C/O主链原子齐全，全部坐标有限。固定Biohub源码`esm@b6b0e8815dc3174a9fe9afd36b222aea57d536c5/esm/utils/structure/molecular_complex.py:858`将token pLDDT乘100写入B因子；按残基身份独立复算后，mean/min/max与原始指标在1e-6浮点误差内一致，未把全部原子均值当作逐残基均值。该容差只用于数值序列化核验，不是科学质量阈值。

| 本次事实 | 结果与边界 |
|---|---|
| 原始置信度 | mean 0.7986140847，min 0.4770510495，max 0.8796935678，pTM 0.7356354594 |
| ipTM | 原始输出为0；单链标准接口应记录null及不适用原因，同时保留原始0，不据此判结构失败 |
| 资源 | A100-SXM-64GB；PyTorch峰值已分配显存14027569152字节（13.06GiB），不是总GPU占用；进程RSS峰值30429460KiB（29.02GiB） |
| 耗时 | 164.97秒，包含资产/环境校验、加载及推理，不是单独推理计时 |
| 支持范围 | 76残基、单链、seed 1、3 loops/50 sampling steps、1样本；未外推到更长输入或默认高预算参数 |
| 未完成 | 标准候选/逐残基confidence输出、统一任务层及N01/N12接入、实际禁网效果、取消/超时/恢复、较长输入容量与科学签收 |

[审计摘要](../../../discovery/t01-phase1-real/esmfold2-target-20260917/r03/audit-summary.json)保存8份来源hash、76个逐残基置信度及执行记录，属于派生审计，不写回原生manifest或result。审计与收集测试共20项通过，包含重算hash后仍拒绝序列/坐标/主链/置信度/元数据篡改及未完成Job。旧r02失败保留；此次未重算模型、未改集群或正式Deployment。结果保持`predicted_engineering_unreviewed`、`usable_for_pipeline=false`，没有声称立体化学质量或科学精度合格。

本机可复核：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 scripts/audit_esmfold2_r03.py
```

取回与核验均已完成，用户可删除临时读取Pod（保留运行PVC、原始结果及验证Job）：

用户随后已执行并回传`pod "antigen-esmfold2-results-r03" deleted from him-ws namespace`；该清理已完成，以下命令无需重复执行。

```powershell
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws delete pod antigen-esmfold2-results-r03 --ignore-not-found --wait=true --timeout=180s
```

成功标记为`ESMFOLD2_R03_ARTIFACTS_VERIFIED`，随后输出METRICS和本地路径；完成收集/审阅后再清理此临时Pod，保留PVC及原失败/成功任务证据。无需重算或重新apply推理Job，科学Gate保持CLOSED。

## ESMFold2标准封装（2026-09-17）

**正式派生包已完成：** 用户已执行以下生成和verify命令，两次输出均为`ESMFOLD2_STANDARD_PACKAGE_VERIFIED`，25文件、76残基，manifest SHA-256 `b5e0d7ca19af8c53aabd0640ca06a48c35084ca97839d30c195852d12f8c0797`；助手再次只读执行verify得到相同结果。[正式结构索引](../../../discovery/t01-phase1-real/esmfold2-target-20260917/standard-r01/result.json)与[来源记录](../../../discovery/t01-phase1-real/esmfold2-target-20260917/standard-r01/provenance.json)已落盘。无需再次生成或上传。本次标准封装关闭，下一项为新任务来源登记、统一任务层与N01接入；本轮没有新推理或集群修改。下方命令保留用于复核。

[封装脚本](../../../scripts/package_esmfold2_result.py)仅在本地读取已取回的r03原件，先验证固定原生manifest、Job/日志hash、请求/profile及结构审计，再生成独立标准包。该阶段不运行预测、不修改服务器；仅支持已登记r03来源，不能拿未知新任务沿用r03身份。推理attempt_id沿用原Kubernetes Job UUID，来源注明`offline_derivation_from_completed_r03_not_new_inference`，不伪造新的预测尝试。

输出25个文件：`result.json`含标准候选结构索引，引用字节不变的`raw/structure.cif`；`confidence/esmfold2-seed-1-sample-0.json`含76条逐残基坐标身份与置信度；`parameters.json`记录seed/MSA/loops/steps/精度/样本数；`provenance.json`绑定输入、profile、资产/环境manifest、原生8文件、Job/日志及封装/审计/Worker源码hash；`execution.json`记录已知执行事实。`raw/`保留8份原生结果及Job，`logs/cluster.log`保留原日志，`sources/`保留7份实现/配置快照。包清单覆盖其余24份文件，自身hash由verify命令打印，避免自引用。

置信度原始字段取自mmCIF B因子，明确`raw_scale=0_100`并仅除100一次；依据固定导出源码，这是token pLDDT乘100的导出值。逐残基身份经审计与输入对齐后生成，不以原子行号推断序列位置。mean为76个规范值算术平均；原工具摘要在raw_scores与原件中完整保留。单链标准ipTM=null，附不适用原因；原始ipTM=0不改写。科学Gate=CLOSED、usable_for_pipeline=false、automatic_handoff=false。

未采集的GPU驱动、Pod退出码记录和分段耗时明确为null并注明原因；Job成功事实来自已归档Complete记录。仅有合并Kubernetes日志，不伪造stdout/stderr分流；NetworkPolicy存在不当作实际禁网探针通过。标准结构封装不等于完整执行生命周期接口已验收。

**本地验证：** 37项封装/审计/收集测试通过，覆盖原件不变、序列/坐标/量纲、参数来源、单链ipTM、重复目录拒绝、来源损坏先于写入拒绝、篡改后重新hash仍拒绝。CLI已在`.tmp/esmfold2-standard-package-validation-r01`生成并复核真实派生包：25文件、76残基，manifest SHA-256 `b5e0d7ca19af8c53aabd0640ca06a48c35084ca97839d30c195852d12f8c0797`。没有重跑模型或更新集群。

**用户下一步：在本地Windows PowerShell执行**（不是Rancher Shell）：

```powershell
Set-Location 'D:\work\蛋白智能体'
.\.venv\Scripts\python.exe -B -X utf8 scripts/package_esmfold2_result.py --output-dir discovery/t01-phase1-real/esmfold2-target-20260917/standard-r01
.\.venv\Scripts\python.exe -B -X utf8 scripts/package_esmfold2_result.py --verify discovery/t01-phase1-real/esmfold2-target-20260917/standard-r01
```

两次应输出`ESMFOLD2_STANDARD_PACKAGE_VERIFIED`、files=25、residues=76与上述manifest hash。生成目录已存在会拒绝覆盖；若已生成，直接执行第二条verify命令。原始r03目录不变，无需新建读取Pod或占用GPU。verify同时复核结构语义、引用与当前登记源码快照，不只核对manifest。未来修改封装实现需要新派生目录和新验收，不能覆盖旧包继续沿用旧hash。

## 统一任务与N01接入准备（2026-09-17）

**N12同次运行工程验收准备（2026-09-18）：** 专家SOP S-28与OI-015/022边界保持不变，R-04仍没有唯一全域决策表，因此`src/t01_phase1_real/development/n12_prediction_evidence.py`继续只做显式引擎的只读证据绑定。复核时发现已有来源校验仅验证任务/产物自身run_id一致，调用者未强制给出期望run_id，存在把另一run的合法结果接入当前链的工程风险；现已把`expected_run_id`贯穿runtime/supervisor以及ProteinMPNN、ESM-IF1、ThermoMPNN、FoldX和N12预测来源验证。适配器仍按原sample_number重验N11/WT、ESM-IF1原生分数、精确变体序列、host和ESMFold2 ArtifactRef，原R-35行原样保留，`validation=null`、`formal_candidates=null`、`scientific_gate=CLOSED`、`usable_for_pipeline=false`、`automatic_handoff=false`，`engine_selection=EXPLICIT_ENGINEERING_ONLY_NOT_R04`。同run提交辅助测试4/4、N12适配/来源测试9/9通过。

新增`scripts/run_n12_esmfold2_acceptance.py`作为唯一真实验收入口，固定使用一条新的同run 1UBQ工程链：N01结构→ProteinMPNN→ESM-IF1→按原sample_number显式选择变体→ESMFold2→`n12_prediction_evidence.inspect`。脚本只支持`--check`静态检查或直接运行；直接运行的证据目录固定为`discovery/t01-phase1-real/esmfold2-target-20260917/n12-same-run-20260918-r01`。真实运行前它会核对控制面镜像、不可变r04 ConfigMap挂载、必需源码路径以及服务容器中的8份源码SHA-256，任何漂移均拒绝启动。当前固定hash为：`runtime.py d9446ad1b3e575c2dd6f7b220af50f34a0de5e4fb43735a40645bf2df9e6ac28`；`proteinmpnn/source.py aeca91247a68958fe302845eb9ad5582b56b8dec7d43958eaf4dad571c612413`；`esm_if1/source.py aab2523a047581907f24b837ae66b8bbba525e0f321ef9a888633c476dd89e78`；`thermompnn/source.py c46f9c9b727a2a11f1b5d572587d489ef8f0e0520dc2cdbe975238ff16b3567b`；`foldx/source.py 69395898376935a24d259b8e03487170713d1c997e47b71910527976dea2c474`；`supervisor.py 10ec8f302fa5e6c118a75e25b2f14bba0beeee66487c486363e30e004c0f4767`；`n12_prediction_evidence.py 09e20dd7f61c437f30f365d63c0d7ffec869ce054f2e141fe67adff68a56fe5b`；`esmfold2/source.py a5a2d0ae3282bf85d85daf3e5a09585b70fc3b3046825fbc424625eb7e6830fe`。`--check`已输出`N12_SAME_RUN_PAYLOAD_CHECK_PASS`，验收静态守卫2/2通过。

准备r04部署增量时发现当前service容器没有`esmfold2-code`挂载，若只替换共享代码ConfigMap，控制面仍会运行镜像内旧来源验证代码。`scripts/prepare_n12_same_run_backend_r04.py`现创建不可变`antigen-n12-same-run-code-r04`，从r03代码清单继承并覆盖上述7份控制面/来源文件、要求原`esmfold2/source.py`存在；对service以逐文件只读`subPath`挂到`/opt/t01/src/...`，同时替换ESMFold2 worker共享`esmfold2-code`卷使其继续在`/backend`看到新代码。补丁固定控制面平台digest `sha256:0e572b386fd2ad45d3d9b844910b3ff6fb01ce0ad5d42a1be27e183fb76bdb2b`，并对Deployment resourceVersion、当前镜像、旧ConfigMap和挂载状态做守卫。准备脚本相关3项与N12 9项合计12/12通过；以模块方式执行服务器dry-run已输出`N12_SAME_RUN_R04_SERVER_DRY_RUN_PASS`，产物目录`.tmp/n12-same-run-backend-r04-20260918-r01`包含`worker-code.json`、`deployment.patch.json`、`deployment.before.json`和`source-hashes.json`。本轮未apply、未rollout、未重启Pod、未启动模型；完整N12只有在用户执行下面的r04应用和真实同run链、再由助手独立核验产物/hash/run_id后才能记工程验收通过，科学Gate与R-04自动路由继续关闭。

**r04现场回归修复（2026-09-18）：** 用户首次应用旧r04时 ConfigMap 已存在但 Deployment JSON patch 被服务器拒绝；随后验收在 service 源码 hash 检查阶段发现缺少`esmfold2/source.py`挂载，未启动任务。已修复生成器把该文件加入 service 的 immutable ConfigMap 与逐文件只读挂载，并将版本改为不可变`antigen-n12-same-run-code-r04b`；相关测试16项通过。旧r04目录仅保留为历史回执，不要重复应用。

首次真实链随后暴露导入根差异：控制面镜像的`PYTHONPATH`为`/app/src`，旧 r04b 文件挂在`/opt/t01/src`，导致`n12_prediction_evidence`无法导入；任务在创建 run 前失败。现保留旧挂载并增加`/app/src`逐文件只读挂载，验收探针同步检查`/app/src`。当前 r04b ConfigMap 已含8份源码，下一补丁只更新挂载列表，不重新创建 ConfigMap；相关测试19项通过。

随后发现`kubectl exec`启动的独立Python进程不会自动经过service的Linux入口，直接加载冻结Windows runtime；`scripts/run_n12_esmfold2_acceptance.py`现于远端payload开头显式调用`linux_service.install_platform_modules()`，再导入Runtime。该修复不需要重新部署，静态检查、payload编译和19项相关测试已通过；可直接重跑验收入口。

**r04b部署与首次真实链结果（2026-09-18）：** r04b生成、服务器dry-run、ConfigMap核对、Deployment补丁和rollout均已完成；`apply`返回unchanged、patch返回no change，说明generation 22已具有目标挂载。助手随后只读核验`/app/src`的8份源码hash、实际导入路径、Deployment就绪和活动任务0均通过。旧r04/r04b目录只保留回执，当前不得再执行。

首次真实run`t01p1r-run-7a5ae8c195da4e34a813e491552e0653`中，结构任务`t01p1r-job-af124b71e2164685920be07f00d50ce4`、ProteinMPNN任务`t01p1r-job-ded143d97c7a4b12b0122116b50d2260`及ESM-IF1任务`t01p1r-job-4efc674a9d9c4b8b9f306b13694f871d`均成功；ESMFold2任务`t01p1r-job-f404b3cbd0ae468ab339ebc3d3f715ff`完成严格加载和原生推理后在标准化阶段失败。原生A链76残基结构60954字节，mean pLDDT 0.8079411387443542、pTM 0.736737847328186；执行环境Python 3.12.14、PyTorch 2.7.1+cu126、CUDA 12.6、capability 8.0，GPU报告`NVIDIA A100-SXM4-40GB`。标准化器原先只接受已验证的`NVIDIA A100-SXM-64GB`，故拒绝为`Unregistered ESMFold2 target environment`。失败任务exit 1、tree_stopped和stopped_confirmed均为true，科学资格false；不得重写为成功。

只读集群复核确认当前Pod位于`k8s-a100-01`，HAMi annotation为`nvidia.com/use-gputype=A100-SXM4-40GB`并分配30000MiB；旧成功证据在`k8s-a100-02`报告`A100-SXM-64GB`。r05仅登记这两个精确环境元组，连同Python/PyTorch/CUDA/capability共同校验，不接受任意A100或其他GPU。将实际失败原生字节仅在内存替换为旧登记名称后，余下结构、序列、主链、置信度、来源和派生产物全部检查通过。相关直接测试37项及payload `--check`通过；另一个既有本机同run测试因固定结构Docker镜像当前不存在返回`ASSET_MISSING`，不计本修复通过，也不改变集群链结果。

r05使用新的不可变ConfigMap `antigen-n12-same-run-code-r05`，在原8份来源基础上增加`esmfold2/standard.py`，同时覆盖Worker `/backend`与service `/app/src`；验收脚本改用新scope/幂等键及证据目录`n12-same-run-20260918-r02`，不复用r01失败。服务器dry-run已输出`N12_SAME_RUN_R05_SERVER_DRY_RUN_PASS`，生成目录为`.tmp/n12-same-run-backend-r05-20260918-r01`。生成件绑定应用前线上`resourceVersion=46103872`；9份本地源码hash与清单一致，补丁只有resourceVersion/镜像/旧ConfigMap/挂载数4项守卫和代码卷、service新增`standard.py`挂载2项替换。

**r05上线回填：** 用户应用ConfigMap返回created、Deployment返回patched，rollout成功。助手只读核验generation/observed=23、Ready/Updated/Available=1；新Pod `antigen-design-9f86d7f66-xsqqn`为11/11 Running、0重启。service从`/app/src/t01_phase1_real/development/esmfold2/standard.py`导入，Worker从`/backend/t01_phase1_real/development/esmfold2/standard.py`导入；两侧9份源码hash逐项等于r05清单。任务库共56条且活动任务为空。旧Pod `antigen-design-5df4d6f8d-fnp6k`已为Failed、0/11且无Ready容器，保留现场，不删除。以下应用命令保留为已完成历史操作，不要重复执行：

```powershell
Set-Location 'D:\work\antigen.design'
$rel3 = '.tmp\n12-same-run-backend-r05-20260918-r01'
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws apply -f "$rel3\worker-code.json"
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws patch deployment antigen-design --type=json --patch-file "$rel3\deployment.patch.json"
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws rollout status deployment/antigen-design --timeout=300s
```

以下唯一验收入口已由用户成功运行，命令保留为历史复现记录，不要重复启动新run：

```powershell
Set-Location 'D:\work\antigen.design'
.\.venv\Scripts\python.exe -u -B -X utf8 scripts/run_n12_esmfold2_acceptance.py
```

**r02完成回填：** 用户得到`ARTIFACTS_VERIFIED 135`和`N12_ESMFOLD2_SAME_RUN_ENGINEERING_PASS`。新run`t01p1r-run-9d7e6460a37942f6a27c95bb0047e883`的结构、ProteinMPNN、ESM-IF1和ESMFold2四个任务全部succeeded；助手线上只读回查四个终态快照与本地保存逐字一致，任务库60条且活动任务0，新Pod 11/11 Ready、0重启。

[独立审计摘要](../../../discovery/t01-phase1-real/esmfold2-target-20260917/n12-same-run-20260918-r02/audit-summary.json)由新增的[审计脚本](../../../scripts/audit_n12_esmfold2_same_run.py)生成并重复运行一致：135个ArtifactRef对应127个按SHA去重的唯一落盘文件，9829564引用字节全部大小/hash/本地字节一致；9份源码身份一致。ProteinMPNN和ESM-IF1的24个原sample_number完整，sample 1的76残基序列、33个突变和分数闭环；原R-35仍失败。ESMFold2原生结构60954字节、592原子，mean pLDDT 0.8082659840583801、pTM 0.7371199727058411；严格权重加载、精确A100-SXM4-40GB环境、禁网标记、主链/坐标/序列及occupancy派生双hash均通过。结论仅为N12显式ESMFold2工程回连完成；R-04自动路由、正式候选、科学Gate、自动交接和生产状态不变。本项无需重跑。

**最新完成：393残基独立容量审计通过（2026-09-18）。** 用户运行完成后，助手通过现有service只读取回共享卷结果，保留原生8文件、输入来源、禁网探针、Job/Pod及日志；[审计摘要](../../../discovery/t01-phase1-real/esmfold2-target-20260917/capacity393-20260918-r01/audit-summary.json)。Job Complete、容器退出0；配置与提交清单一致，严格checkpoint加载、文件manifest/hash、序列/残基编号、主链、坐标及置信度一致性均通过。A链393残基3059原子；mean pLDDT=0.8781784772872925，pTM=0.5601621270179749；elapsed=79.02742552757263秒包含校验/加载/推理，peak_gpu_memory_bytes=16475138048（15.34GiB PyTorch allocated），peak_process_rss_kib=31115952。网络seccomp实际拒绝INET/INET6。固定环境使用PyTorch LayerNorm/attention/RoPE fallback，日志保留；没有融合kernel数值等价或科学质量签收，不为消除警告临时安装依赖。22项相关检查通过。常驻后端仍限制76aa；393只计本案例工程容量通过，1000–1500/>1500 NOT_RUN；后续N12真实来源工程验收、长度扩展回归及Pod故障恢复待完成。科学Gate关闭。收集脚本`scripts/collect_esmfold2_capacity.py`明确按独立request_id复用结构审计，默认r03身份检查不放宽，旧证据不覆盖。

**当前操作：独立393残基容量Job（2026-09-18）。** 用户明确选择已有真实序列。本地`tests/fixtures/structure_mapping/real/5XZC.fasta`登记为TP53/P04637全长393aa，文件SHA-256 `a5c70cd6ea90eedac06af5c41218f472405bd4024d6041595c1a0a95b210f341`，序列SHA-256 `e3ca60f18e3b6e98986ad6749215ee3b7a3abc09c191675213d1f243c035c9a3`。仅取核验后的序列登记为当前新工程输入，不使用旧结构、不执行S07、不继承旧验收。生成器及隔离检查通过，清单三资源server dry-run通过；尚未提交。沿用原生源码/权重/3 loops/50 steps及32GiB显存配额，独立实验profile长度393，常驻profile仍76。Job同节点亲和避免模型RWO卷跨节点冲突，共享`/shared/.gpu-execution.lock`防止与常驻GPU任务重叠；模型只读，独立NetworkPolicy无egress，加实际seccomp socket拒绝检查。30分钟总截止含排队/等待锁，backoffLimit=0；输出主运行PVC的`/var/lib/t01/capacity393-20260918-r01`，目录已存在则拒绝覆盖。运行卷余20.85GB、现有任务均终态；nodes权限不足未核对整机GPU剩余额度，Pending时先诊断不重建任务。

用户本地PowerShell执行：

```powershell
Set-Location 'D:\work\蛋白智能体'
kubectl --kubeconfig .tmp/himat.kubeconfig apply -f deploy/esmfold2-standard/capacity393.r01.json
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws get pods -l job-name=antigen-esmfold2-capacity393-r01 -o wide
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws logs -f job/antigen-esmfold2-capacity393-r01 --pod-running-timeout=300s
```

原生完成标记`ESMFOLD2_CAPACITY_NATIVE_COMPLETED_REQUIRES_AUDIT`，不是科学通过。若Pending/ContainerCreating等待超时或日志连接中断，保留Job，回传状态；不删除常驻Pod或模型卷，不重复创建另一Job。结束后通过现有service读取共享卷取回结果，核验393残基结构、置信度、完整性、耗时和峰值；1000–1500及>1500仍NOT_RUN。原生峰值为PyTorch allocated，不是总GPU占用。独立393结果成功也不自动放宽后端支持范围，科学Gate保持CLOSED。

**最新完成：真实原生执行超时（2026-09-18）。** 任务`367ad5abcf20463e88d3763b6e01b9e7`设置30秒期限，返回timed_out/TIMEOUT。独立复核[完整回执](../../../discovery/t01-phase1-real/esmfold2-target-20260917/timeout-20260918-r01/latest.json)及[进程检查](../../../discovery/t01-phase1-real/esmfold2-target-20260917/timeout-20260918-r01/process-check.json)，10份产物大小/hash/本地字节一致。真实native-request已生成，inference_started=false；无取消文件，任务与常驻收据均确认超时及停止，登记PID366/birth3301310一致，进程组active=0，prediction=null，科学消费false。结论仅为推理前真实执行自动超时通过；未测试GPU推理阶段超时，不称为模型自然性能超限。无需重跑。随后准备独立较长序列容量验证，保留当前后端76残基上限；Pod崩溃恢复与N12仍待验收，科学Gate关闭。

**当前操作：30秒真实执行超时验收（2026-09-18）。** [超时脚本](../../../scripts/run_esmfold2_timeout_acceptance.py)使用独立任务scope与幂等键，已准备，19项超时/取消脚本测试通过；用户执行下面命令。该案例真实启动模型命令，短时限覆盖资产校验/加载/推理的整个执行过程，预计加载前后触发，不把它记为推理阶段超时或自然性能超限。要求native-request已落盘（不能只在锁上等待）、禁网观察存在、原生超时收据及任务TIMEOUT、停止确认、登记进程组活动0且身份一致、prediction=null。脚本不调用cancel，不使用模拟sleep，不修改旧任务或部署。保存timeout-20260918-r01；断线重跑同命令接回同一任务。成功标记`ESMFOLD2_NATIVE_EXECUTION_TIMEOUT_PASS`。

```powershell
Set-Location 'D:\work\蛋白智能体'
.\.venv\Scripts\python.exe -u -B -X utf8 scripts/run_esmfold2_timeout_acceptance.py
```

**最新：运行中恢复及推理取消验收完成（2026-09-18）。** 任务`2ecea4688bbd43aa9dbd3137760dff3e`经过recovery、INFERENCE_START、stop_requested至cancelled。首次独立进程检查未继承Worker进程内部设置的T01_PROCESS_REGISTRY，错误查找/tmp；实际持久登记存在于`/var/lib/t01/resident/esmfold2/.processes`。脚本已修复导入顺序和目录并增加登记leader身份比对，9项测试通过。助手仅只读核验原任务、保存process-check.json，登记PID342/birth3249903与收据一致，active=0；11份产物独立校验通过，prediction=null、usable_for_pipeline=false，恢复未新建attempt/执行目录/进程。回执位于`discovery/t01-phase1-real/esmfold2-target-20260917/lifecycle-20260918-r01`，无需再次运行。停止检查没有将登记缺失当作进程清空；未重启Pod或重跑推理。下一项超时验收，崩溃恢复和较长输入仍未完成。

**下一项操作（2026-09-18）：真实推理中取消及显式控制器恢复。** 新脚本[run_esmfold2_cancel_acceptance.py](../../../scripts/run_esmfold2_cancel_acceptance.py)在独立scope内使用固定幂等键提交76残基任务，在运行中调用recover并保留原attempt/执行目录/进程身份，看到ESMFOLD2_INFERENCE_START后取消；终态检查停止收据、Worker命名空间中登记进程组active=0、prediction=null和科学Gate未开放。8项守卫测试通过，尚未运行目标任务。不重启Pod，不把此项称为崩溃恢复；超时与较长输入另行准备。若推理已自然结束而取消未发生，脚本必须不通过，不能将成功预测记为取消成功。断线重跑同命令接回原任务，不删除任何旧产物。

```powershell
Set-Location 'D:\work\蛋白智能体'
.\.venv\Scripts\python.exe -u -B -X utf8 scripts/run_esmfold2_cancel_acceptance.py
```

成功标记`ESMFOLD2_INFERENCE_CANCEL_AND_CONTROLLER_RECOVERY_PASS`；输出目录`discovery/t01-phase1-real/esmfold2-target-20260917/lifecycle-20260918-r01`。backend-r03已有真实进程禁网证据：runtime.json的INET_INET6_DENIED与executor-observation.json的seccomp-local-sockets-only-v1一致，源码实际尝试INET/INET6创建且仅PermissionError放行后才运行模型；本项按进程禁网通过，不扩大为Pod NetworkPolicy实际隔离或系统安全边界认证。专家结构ToolSpec长度风险分级与交接§6停止验收要求已复核；当前policy仍9..76残基，未测较长输入不承诺支持。

**最新完成：backend-r03预测→N01工程验收通过。** 用户父任务`8ed6478a144e4ae8b987562c7a40338a`、prediction `220ca37308da497da1499aa60f14c01e`、structure `72c4cff76e7c42158a836e185b83b19a`均成功。独立复核[本地完整回执](../../../discovery/t01-phase1-real/esmfold2-target-20260917/backend-r03/latest.json)中109份产物大小/SHA-256/落盘字节一致，所有任务科学消费资格false。原件SHA-256 `7297e1aad5a36febff9de319c1fcb941798d628ab49ec5ae0f4d8d054ff0fa6a`，工具副本`052a2e06d65c4978747a7cdfd8d6f78c3b187b7ddb00a8e7735c19d119609986`，转换仅601行occupancy工程补值，记录与来源绑定保留。76残基mean pLDDT=0.7989875060633609、pTM=0.7357823848724365；S-09 high、topology_reliable=true，未满足最小连续长度的低置信残基不形成区域。输入预检、映射、质量接入、FreeSASA均执行；总SASA=4811.968962635386Å²，G76绝对SASA=130.80459698468198Å²，RSA=1.257736509468096，按原规则output_invalid且normal_rsa_result=null。N01 succeeded为工程任务完成，不表示RSA有效或科学签收。S-19双空输入导致epitope_map失败为保留规则。本次占有率兼容与质量来源接入阻塞关闭；后续实际禁网、取消/超时/恢复、较长序列及N12验收仍待完成，不重跑已通过独立工具或开启科学Gate。

**当前操作：r03部署核验通过，用户启动新验收。** generation/observed=17，Pod `antigen-design-5df4d6f8d-fnp6k`11/11 Ready、0重启；控制面22份、ESMFold2 11份、结构Worker 1份源码/profile hash核对一致。验收脚本锁定r03镜像、代码ConfigMap、结构Worker挂载及就绪状态，使用独立scope/幂等键，结果写backend-r03；本地语法检查通过，助手未启动。断线重跑相同命令，避免创建额外任务。N01工程结果与科学资格、RSA可用性分开审查，S-19无预测输入失败规则保持不变。

```powershell
Set-Location 'D:\work\蛋白智能体'
.\.venv\Scripts\python.exe -u -B -X utf8 scripts/run_esmfold2_backend_acceptance.py
```

**当前操作：r03上传完成，部署待用户应用。** 发布回执VERIFIED；`scripts/prepare_esmfold2_backend_r03.py`生成`.tmp/esmfold2-backend-deploy-r03`，服务器dry-run及5项保护测试通过。控制面和投影源码hash已比对，结构Worker实际路径已只读核实为`/opt/t01/src/t01_phase1_real/development/structure/worker.py`，采用只读subPath覆盖修复代码。任务库41项均终态；保留部署前快照和source-hashes.json。以下命令在本地PowerShell运行；尚未实际部署或启动新任务。若resourceVersion test失败，先重新读取部署生成新补丁，不移除保护。

```powershell
Set-Location 'D:\work\蛋白智能体'
kubectl --kubeconfig .tmp/himat.kubeconfig apply -f .tmp/esmfold2-backend-deploy-r03/worker-code.json
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws patch deployment antigen-design --type=json --patch-file .tmp/esmfold2-backend-deploy-r03/deployment.patch.json
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws rollout status deployment/antigen-design --timeout=600s
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws logs deployment/antigen-design -c worker-esmfold2 --tail=20
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws logs deployment/antigen-design -c worker-structure --tail=20
```

**当前操作：r03构建完成，待上传。** 用户镜像索引`sha256:3b3f4b19285467d841b627cb6e17bdd763e17e602f2b0aafdc17180488cc748b`；目标Linux/amd64 manifest为`sha256:0e572b386fd2ad45d3d9b844910b3ff6fb01ce0ad5d42a1be27e183fb76bdb2b`。镜像内11份ESMFold2源码/profile及runtime、结构Worker/result共14份文件与本地一致。上传脚本已更新为r03并通过5项身份守卫；旧r02回执和镜像保留。用户执行下列命令，等待`VERIFIED_REMOTE control`匹配上述平台摘要及`ALL_PUBLISHED 1`、`TEMP_RELAY_REMOVED`。脚本只上传；后续部署必须同时更新两个Worker相关代码，尚未启动新验收。

```powershell
Set-Location 'D:\work\蛋白智能体'
.\.venv\Scripts\python.exe -u -B -X utf8 scripts/publish_esmfold2_backend_control.py
```

**最新：预测质量已接入结构Worker，本地CPU重放通过主要步骤。** runtime仅对已核验G0预测ArtifactRef写入内部prediction-evidence.json，绑定当前N01 attempt及原件/派生/质量ArtifactRef；Worker从实际input.json所在执行目录读取，核对绑定后消费专家S-09结果，结果适配器再次复算分档和掩码。上传结构的预测声明仍不自动获得信任。113项结构/预测回归及后续来源/常驻桥33项通过。`scripts/probe_esmfold2_structure_adapter.py`使用backend-r02真实归档字节在固定FreeSASA镜像禁网CPU重放，输入预检、A链映射、S-09和FreeSASA执行成功；G76原始绝对SASA=130.73583610628947Å²，除专家G参考104得到1.2570753471758602，现有出域守卫保持OUTPUT_INVALID。记录在`.tmp/esmfold2-s09-replay-9d1kf1xj`，不计作新GPU或服务器验收。用户先构建控制面r03；发布增量必须同时携带更新的ESMFold2源码及结构Worker，不能只换控制面。

```powershell
Set-Location 'D:\work\蛋白智能体'
docker build --platform linux/amd64 -t antigen-design:esmfold2-backend-r03 .
docker image inspect antigen-design:esmfold2-backend-r03 --format '{{.Id}}'
```

**用户已明确允许并要求修复occupancy（2026-09-17）：** 授权仅覆盖已验证ESMFold2单模型、无替代构象的工具专用副本，补occupancy=1.0，原件与转换记录保留。standard.py新增受限派生及每个原字段重新比对，生成tool-structure.cif/structure-conversion.json；source.py将新派生raw/G0 ArtifactRef交N01，原件仍为raw/structure.cif，result.json记录两者。不得覆盖原有occupancy，不得扩展实验输入。新增quality.py依据专家结构ToolSpec §2c及SOP S-09生成prediction-quality.json，保留可配置默认参数及双写掩码、E-06待回测身份，科学Gate关闭。用真实backend-r02产物重算，原件未改、派生通过原输入预检，质量high、topology_reliable=true、掩码为空。该质量文件目前是预测结果的独立产物，尚未进入旧structure Worker的质量放行分支；此边界须在后续接入中保持明确。N06按S-19两类输入为空返回失败规则保留。当前本地修复未部署。

**专家依据复核：N01接入不能以填充值消除报错（2026-09-17）。** 已查阅当前专家包《ToolSpec_结构预测获取链_v10.5》§2c/2d/3/4、《AgentA_SOP_v10.5_20260902》S-08/S-09/S-19及《ToolSpec_C34_FreeSASA_v10.5》§2/2b。结构获取链要求保留原始格式、按登记引擎解释置信度，工具转换失败只影响特定下游；未给出预测CIF缺失occupancy时可填1的规则。backend-r02实际原生CIF为601原子、全部altloc为`.`、occupancy列整体缺失，不是坐标缺失或模型未完成。现有通用结构Worker将occupancy列作为输入预检必填项，且quality.py对`predicted`一律返回PREDICTION_PROVENANCE_UNVERIFIED，尚未消费已登记ESMFold2置信度，因此仅补occupancy不能完成S-09接入。

后续应保持两层职责：N01取得已验证预测原件及逐残基置信度/来源，S-09消费登记的预测证据；FreeSASA等需要全占有率的步骤单独判断是否可执行，不把它们的输入限制反向当成预测失败。若采用补occupancy的工具专用派生结构，须先明确专家口径：是否允许对固定ESMFold2单链、单模型、无替代构象结果将缺失occupancy以工程约定1.0写入派生副本；必须原件只读保留、记录逐项转换与双hash，且不得扩展到实验结构。当前未采用该约定、未修改原件或预检。

N06无需更改失败路由：SOP S-19第765–767行明确规定，单通道缺失时重分配，**两者均None时failure_report（至少需要一种表位预测输入）**。本次验收关闭BepiPred/NetMHC，因此现有TOOL_FAILED符合专家规则，不能改为成功或空表位图。此前“处理无上游路由”的待办在本次专家复核后收敛为保留真实失败，不将其计入预测成功。

**最新backend-r02实跑结果：预测通过、N01未通过。** 父任务`00c69ed5facd4cbaa912ebe70d6c9c13`，prediction `061a7652dff8470783d5368d2539c5b2`成功；本地`backend-r02/latest.json`所含94份产物大小/hash已由助手独立复核。N01诊断INPUT_UNSUPPORTED，具体为`Missing coordinate field: occupancy`；标准预测结构尚不满足严格输入预检。epitope_map独立失败为`S-19 has no available epitope predictor input`，对应本次未提供表位预测分支。父任务成功不等于这些节点成功，验收脚本返回NOT_PASSED符合事实。下一步先检查模型导出字段及适配依据，保持原生结果和原终态不可改写，不直接将缺失occupancy静默置1。用户当前无需重跑或重新上传。

**最新：r02部署已完成，启动新验收。** generation/observed=16，Pod `antigen-design-b7d56b9cf-v2csl`为11/11 Ready、0重启；镜像digest正确，控制面与Worker各10份ESMFold2源码/profile hash一致。验收脚本现固定r02独立scope/幂等键，输出backend-r02，不再使用r01；要求r02镜像与代码ConfigMap，语法检查通过。助手未启动预测。用户执行：

```powershell
Set-Location 'D:\work\蛋白智能体'
.\.venv\Scripts\python.exe -u -B -X utf8 scripts/run_esmfold2_backend_acceptance.py
```

成功预期`ESMFOLD2_BACKEND_N01_PASS`，必须prediction与structure均成功且原始产物大小/hash通过；其他节点状态分别报告，不把父工作流成功当预测通过。断线或本地等待超时可重跑同一命令，接回同一r02任务。此时尚未取得r02新计算结果，科学Gate关闭。

**最新：r02上传已核验，正式增量待应用。** 回执为VERIFIED，平台digest `sha256:e31d68cd2ba1fd5199f86732c77abc3137ff3f342186b0a26645c562b75f2e5d`；更新前11/11 Ready、0重启、活动任务0。`scripts/prepare_esmfold2_backend_r02.py`生成新不可变源码清单`antigen-esmfold2-backend-code-r02`和受resourceVersion保护的两字段更新补丁，服务器dry-run及2项守卫测试通过。源码清单差异严格限定standard.py，镜像10份模块hash与Worker投影源一致。原Deployment快照位于`.tmp/esmfold2-backend-deploy-r02/deployment.before.json`；此补丁尚未应用。用户逐条执行，任一报错停止回传，若resourceVersion改变须重新生成，不去掉守卫：

```powershell
Set-Location 'D:\work\蛋白智能体'
kubectl --kubeconfig .tmp/himat.kubeconfig apply -f .tmp/esmfold2-backend-deploy-r02/worker-code.json
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws patch deployment antigen-design --type=json --patch-file .tmp/esmfold2-backend-deploy-r02/deployment.patch.json
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws rollout status deployment/antigen-design --timeout=600s
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws logs deployment/antigen-design -c worker-esmfold2 --tail=20
```

就绪后再核验双端源码并准备新任务；旧验收脚本仍绑定r01，不用它启动r02。科学Gate保持CLOSED。

**最新：r02镜像已构建核验，下一步上传。** 平台digest `sha256:e31d68cd2ba1fd5199f86732c77abc3137ff3f342186b0a26645c562b75f2e5d`，索引digest `sha256:1859176f294b5953bb2a5f132667adca93674509aac856c1f32de459da9446c2`；镜像中10份ESMFold2源码/profile与修复后的本地hash一致。上传脚本改为固定r02身份，5项身份守卫通过；r01上传回执和失败任务保留。用户运行下列命令，预期VERIFIED_REMOTE control的摘要等于上述平台digest，随后ALL_PUBLISHED 1及TEMP_RELAY_REMOVED。回执保存`.tmp/esmfold2-backend-publish-20260917-r02`。此次仅上传；新部署还须同步更新Worker代码ConfigMap，不能仅换控制面镜像。

```powershell
Set-Location 'D:\work\蛋白智能体'
.\.venv\Scripts\python.exe -u -B -X utf8 scripts/publish_esmfold2_backend_control.py
```

**最新修复待发布：** backend-r01父任务`92f16b079a144eaba0ab2e9bfc4b9898`已终态，prediction子任务`c0309371d84941d99abcd8a51f77a0b5`为OUTPUT_INVALID，原生execution `1f9598cb594bddddaa80c3df4740eece`成功exit 0。严格重算差异仅为mean pLDDT：Worker 0.7987064140721372、控制面0.7987064140721369，及其派生confidence hash引用。新后端standard.py改用math.fsum，19项回归及实际Python3.11.16/3.12.14四文件逐字节hash对照通过；原生结果、旧失败和科学关闭状态保留。旧验收脚本仍绑定r01，重跑不会修复终态，暂不启动。下一步先构建修复镜像，再同时更新控制面及Worker源码身份并准备新任务。

```powershell
Set-Location 'D:\work\蛋白智能体'
docker build --platform linux/amd64 -t antigen-design:esmfold2-backend-r02 .
docker image inspect antigen-design:esmfold2-backend-r02 --format '{{.Id}}'
```

**ESMFold2常驻部署启动通过，待新任务验收（2026-09-17）：** 用户应用配置单文件挂载修复后，助手只读确认Pod `antigen-design-d667fcf98-ngmf5`为11/11 Ready、0重启；ESMFold2及原GPU Worker均输出resident_worker_ready。控制面与模型Worker各10份ESMFold2源码/profile逐文件hash均与本地一致。已准备`scripts/run_esmfold2_backend_acceptance.py`，本地payload语法检查通过，尚未启动模型；由用户运行新76残基预测→N01验收。固定专用scope/幂等键支持断线后重新运行接回同一任务，终态收集原始产物并核验大小/hash，失败不报PASS，不发布RustFS报告。科学Gate继续CLOSED。

```powershell
Set-Location 'D:\work\蛋白智能体'
.\.venv\Scripts\python.exe -u -B -X utf8 scripts/run_esmfold2_backend_acceptance.py
```

产物保存在`discovery/t01-phase1-real/esmfold2-target-20260917/backend-r01`。预期终标记`ESMFOLD2_BACKEND_N01_PASS`；该标记要求新prediction和structure均成功并保持科学资格关闭，仍不代表生命周期或长序列验收。网络中断后重跑同一命令，不更换幂等键。

**ESMFold2部署后启动修复待应用（2026-09-17）：** 用户已应用正式增量并收到rollout成功；助手随后只读复核generation/observed=14、控制面digest正确，但Pod `antigen-design-86b9db4bc-g48wz`为10/11 Ready，ESMFold2 Worker因`Worker configuration/root symlink`重启。ConfigMap目录投影使配置路径成为符号链接，与既有安全检查冲突。已修复部署生成器为只读单文件subPath挂载，保留原安全检查，5项部署测试通过。最小修复补丁`.tmp/esmfold2-backend-mount-fix-r01/deployment.patch.json`及更新前快照已保存，服务器dry-run通过；待用户应用。不需重建镜像或重新上传，尚未启动新预测任务，科学Gate保持CLOSED。

```powershell
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws patch deployment antigen-design --type=json --patch-file .tmp/esmfold2-backend-mount-fix-r01/deployment.patch.json
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws rollout status deployment/antigen-design --timeout=600s
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws logs deployment/antigen-design -c worker-esmfold2 --tail=20
```

任一命令报错停止回传；rollout后仍须检查Worker日志和持续就绪。

**ESMFold2控制面已上传，待用户应用正式增量（2026-09-17）：** 上传回执VERIFIED，平台digest `sha256:1c8b3f7c233580acd616d7e5b62a2c135fb9283d035399ead6dfde06420a2677`，中转Pod已清理。助手只读核对现有服务10/10 Ready、0重启；任务库21 succeeded、2 failed、1 timed_out，活动任务0。正式目录`.tmp/esmfold2-backend-deploy-r01`包含两ConfigMap及受resourceVersion保护的Deployment patch，服务器dry-run通过，`deployment.before.json`已保存。尚未应用；下一步由用户应用增量，再验收新预测→N01及生命周期。科学Gate保持CLOSED。下方较早构建/上传指引已完成，无需重做。

用户本地PowerShell逐条执行，任一报错先停止回传；resourceVersion守卫失败应重新生成清单。Recreate会重建服务Pod，预期增加到11个容器，PVC保留。

```powershell
Set-Location 'D:\work\蛋白智能体'
kubectl --kubeconfig .tmp/himat.kubeconfig apply -f .tmp/esmfold2-backend-deploy-r01/resident-config.json
kubectl --kubeconfig .tmp/himat.kubeconfig apply -f .tmp/esmfold2-backend-deploy-r01/worker-code.json
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws patch deployment antigen-design --type=json --patch-file .tmp/esmfold2-backend-deploy-r01/deployment.patch.json
kubectl --kubeconfig .tmp/himat.kubeconfig -n him-ws rollout status deployment/antigen-design --timeout=600s
```

**构建完成，当前下一步上传：** 用户已构建`antigen-design:esmfold2-backend-r01`，索引摘要`sha256:9ecad40ff4ead9190c400d4a9624aaa94e8f3e7b62a1f40e5662e3e878f8573f`，Linux/amd64平台manifest摘要`sha256:1c8b3f7c233580acd616d7e5b62a2c135fb9283d035399ead6dfde06420a2677`，config摘要`sha256:528b2b3111b857b5aeb996abd553d709da6867645605b5b3b0e719a4b40ffa7c`。助手禁网/只读启动镜像验证18份后端及RustFS来源hash、ESMFold2注册导入通过，未加载模型。下方构建命令已执行，无需重复。

[上传脚本](../../../scripts/publish_esmfold2_backend_control.py)基于既有内网Harbor传输方式，固定索引/平台身份并校验`.tmp/publish_resident_images.py`的SHA-256后才加载，5项身份守卫测试通过。脚本导出并验证本地镜像，凭据只在内存中读取现有Harbor Secret，创建专用临时中转Pod`antigen-esmfold2-backend-relay-r01`，上传至`qcyz/antigen-design:esmfold2-backend-r01`并回读manifest及各层，最后删除该临时Pod。不会更新Deployment、模型卷或启动预测；已有中转Pod存在时拒绝复用。回执与续传状态保存在`.tmp/esmfold2-backend-publish-20260917-r01`。本轮仅准备脚本，助手未执行上传。

请用户在本地PowerShell执行：

```powershell
Set-Location 'D:\work\蛋白智能体'
.\.venv\Scripts\python.exe -u -B -X utf8 scripts/publish_esmfold2_backend_control.py
```

成功预期`VERIFIED_REMOTE control sha256:1c8b3f7c233580acd616d7e5b62a2c135fb9283d035399ead6dfde06420a2677`、`ALL_PUBLISHED 1`、`TEMP_RELAY_REMOVED`。收到回执后，再用实际仓库digest生成新正式部署增量，不应用旧控制面digest的dry-run文件。

新增[ESMFold2后端模块](../../../src/t01_phase1_real/development/esmfold2/policy.py)，登记`t01.real.esmfold2`/N01，沿用现有任务/attempt、ArtifactRef、幂等、常驻收据、停止与恢复。当前输入为9..76 AA20单链、显式seed=1、固定3 loops/50 sampling steps；76仅为工程上限。无resident登记时明确拒绝。新调用使用自己的身份，r03及standard-r01不冒充新请求结果。

workflow新增可选`prediction`对象（`engine=esmfold2, seed=1, timeout_seconds=600`），仅在无上传结构、无历史结构复用时接受；未指定保留原行为。执行prediction→structure→原分析链，预测失败明确跳过结构。原生manifest、精确请求/profile、源码/资产/环境、严格加载、结构序列/主链/坐标及置信度均校验后，再由`source.py`复核原任务与全部原始字节交给N01。结构保留`raw/G0_REAL_OUTPUT`身份；跨run、错序列/宿主、旧attempt及未成功结果拒绝，科学资格关闭。

模型Worker沿用已验证独立Python3.12环境与轻量镜像，源码/profile由不可变ConfigMap挂载；控制面需要新镜像。共同GPU文件锁位于共享卷，既有GPU Worker须同时挂载新监督代码和命令配置；等待锁受原超时/取消进程组管理。CUDA与seccomp组合、新模型任务、取消/超时/恢复仍须目标验证。

验证：13项新后端测试使用明确标识的归档字节契约夹具，覆盖新身份、幂等、恢复、停止收据、N01来源及损坏拒绝，不计新推理；4项部署渲染和既有流程/常驻桥/API35项通过。完整根首轮1993通过/15跳过/5失败，日志`.tmp/esmfold2-backend-root-tests.txt`：4项因common.py修改触发冻结源检查，已恢复原LF字节/hash并重验通过；依赖隔离移入新模块，新增17项重验通过。余1项文档失败为旧报告两处既有断链，不改冻结报告。固定Linux环境中的[进程探针](../../../tests/esmfold2_resident_linux_probe.py)实际通过模块导入、INET/INET6拒绝和跨执行根GPU锁互斥，未加载模型。

[增量准备脚本](../../../scripts/prepare_esmfold2_backend_deploy.py)只读当前Deployment/ConfigMap/PVC并服务器dry-run，保留服务env/Secret引用，用resourceVersion阻止覆盖并发变更。已用当前旧控制面digest验证两ConfigMap与patch可接受，输出`.tmp/esmfold2-backend-dry-run-only-r01`仅为验证，**禁止直接用于新代码上线**。新镜像发布后需以新digest、新目录重新生成正式清单，核对无活动任务后交用户应用。本轮未修改集群或提交/推送Git。

**用户下一步：仅在本地Windows PowerShell构建新控制面镜像。**

```powershell
Set-Location 'D:\work\蛋白智能体'
docker build --platform linux/amd64 -t antigen-design:esmfold2-backend-r01 .
docker image inspect antigen-design:esmfold2-backend-r01 --format '{{.Id}}'
```

回传构建末尾和image ID后，再准备内网发布、digest回读及正式增量。构建不等于上传/部署，模型与环境无需重传。新序列→预测→结构分析→报告、实际禁网、取消/超时/恢复仍待服务器验收。

## ESMFold2标准版准备回填（2026-09-16）

**下载完成复核（2026-09-16）：** 本轮项目复核发现最终`asset-manifest.json`已生成，状态为`ASSETS_DOWNLOADED_NOT_DEPLOYED`。独立重新读取23份文件并逐项比对大小/SHA-256，合计26791863243字节，全部通过；原后台PID已不在运行。当前进入固定环境、模型卷与预测适配阶段，无需重新下载。目标只读查询未见`antigen-esmfold2-models` PVC，现有GPU Worker仅申请10GiB；它不构成标准版模型容量通过。完整排期见[部署续行计划](../PHASE1_DELIVERY_PLAN.md#部署续行计划2026-09-16)。以下“下载已启动”及GPU上传描述保留准备时点事实。

用户授权先推进ESMFold2标准版下载和部署准备；现有ProteinMPNN/ESM-IF1/ThermoMPNN GPU镜像仍由用户上传，两项操作分离。本批已核实固定标准版`biohub/ESMFold2@e1e189d0f5fb70c2693da2332eca4443c0ccccd6`的`config.json`引用`biohub/ESMC-6B`，不能仅下载约939MB的折叠权重。后者固定为`7d0f99a8b716749ad1a0328181c1e0339691b0c2`（官方2026-09-14 revision），六份语言模型分片合计约25.4GB，另含约417MB CCD及配置；两个官方仓库API均返回gated=false。固定模型快照的许可元数据为MIT及第三方条款，不将单个标签视为所有依赖的完整许可记录。

代码沿用既有Biohub/esm候选`b6b0e8815dc3174a9fe9afd36b222aea57d536c5`，其pyproject要求Python>=3.12,<3.13并依赖Biohub Transformers分支；本次将该浮动依赖解析为固定提交`ef32577f55da19a4989cd7b22e004dc43a4998cb`，属于待环境验证的准备版本，不冒充已验收兼容组合。官方模型实现支持通过`load_esmc=False`先载入折叠模型，再调用`load_esmc(本地路径)`；后续包装器须使用完整本地资产、禁网环境，不能依赖运行时下载。尚未安装环境或进行import/权重加载/预测。

目标Pod访问Hugging Face出现DNS解析失败，访问GitHub raw成功；本机官方站点访问成功，故采用本机D盘下载。下载器为[scripts/prepare_esmfold2_assets.py](../../../scripts/prepare_esmfold2_assets.py)，只用Python标准库，固定revision、支持Range续传，逐份比对官方LFS SHA-256或小文件Git blob身份，并生成本地SHA-256清单。已有不同内容文件拒绝覆盖；未解包执行模型pickle或远程代码。断点续传、拒绝忽略Range响应、拒绝已存在损坏文件共3项测试通过；首轮沙箱测试因临时目录写权限失败，授权在D盘测试目录重跑通过，缓存写权限告警不影响断言。

资产目录为Git忽略的`var/t01-phase1-real/structure-models/esmfold2-standard-20260916-r01`；下载已启动为独立隐藏后台进程，日志与进程信息在`.tmp/esmfold2-download/current.json`，所有大文件和.partial均在D盘。`download-progress.json`仅列已验证文件，只有`asset-manifest.json`生成且status为`ASSETS_DOWNLOADED_NOT_DEPLOYED`才表示本批文件下载校验完成。后台运行不代表下载已完成，机器需保持联网、不休眠；不要同时启动第二个下载进程。

需要恢复且已确认没有同名下载进程时，在项目PowerShell执行：

```powershell
& '.\.venv\Scripts\python.exe' -u -B -X utf8 scripts/prepare_esmfold2_assets.py --output var/t01-phase1-real/structure-models/esmfold2-standard-20260916-r01
```

已准备[独立模型卷清单](../../../deploy/esmfold2-standard/assets.pvc.yaml)：`him-ws/antigen-esmfold2-models`、60Gi、ceph-rbd、RWO，尚未创建。60Gi用于模型原件及传输暂存余量，不是已申请配额；不占用剩余约5.4GiB的现有工具资产卷。后续确认完整资产、构建独立Python3.12环境和依赖锁、核实实际GPU资源名/可用显存，再进行固定单链工程输入的禁网预测与结构链接入。本批未改共享流水线、未使用Fast、未开放科学资格。

## 1. 工作范围与责任

T-01 分析单个目标蛋白。用户输入序列、宿主物种和可选本地结构；无结构时，需要本地 AlphaFold3 或 ESMFold2 预测结构，随后交给已有结构映射、质量检查和 FreeSASA/RSA 分析链。

| 负责人 | 本次负责的交付 |
|---|---|
| 用户操作、助手指导与实现 | 检查服务器；固定代码、权重、数据库和运行环境；实现本文 CLI 包装；真实禁网运行；输出规范化结果与原始文件；验证停止和资源边界 |
| 项目主开发 | 将交付的 Worker 接入现有任务层、ArtifactRef、幂等、查询、取消/恢复/重试及结构分析链；实现有依据的模型路由与结果选择 |
| 计划管理 | 维护分工、实际完成状态和具体阻塞，复核交付证据 |
| 算法负责人 | 科学输入域、模型使用与质量规则签收；工程部署成功不等于科学验收 |

先支持单条标准蛋白、单链、显式指定引擎。无需建设网站、HTTP 服务、MCP 服务、Dify 工作流或新任务数据库；服务器作业由 CLI 启动，后续由项目运行层管理。宿主信息原样记录，不自行转成模型科学参数。

推理期间禁止联网，不允许调用在线预测或 RCSB/AFDB，也不自动改用另一个模型。AF3 使用已登记的本地遗传/模板数据管线属于本次范围。暂不扩展配体、核酸、修饰残基或复合物。

## 2. 先检查服务器，再固定环境

请先运行以下只读 Linux 命令，将结果保存为交付中的环境记录。不存在的命令注明缺失即可；不要为检查擅自升级宿主驱动。

```bash
uname -a
cat /etc/os-release
lscpu
free -h
df -hT
nvidia-smi
nvidia-smi -L
nvidia-smi --query-gpu=name,uuid,memory.total,driver_version --format=csv
docker version
docker info
```

补充记录：实际分配的 GPU/显存、CPU/内存配额、可用磁盘与挂载点、Docker/Apptainer/调度器支持、GPU 容器可见性、运行账号及目录读写权限、安装阶段是否可联网、资产如何合规转入内网。共享服务器按实际配额安排，不能把机器总资源当可独占资源。

不要套用开发机资源作为服务器事实。若环境不足，给出“哪一引擎、哪个配置、缺什么资源、实测或估算依据”，继续另一引擎可执行部分。无需等待两者一起成功才回传已有成果。

### A100 部署检查重点

| 检查项 | 现场需要给出的结论 |
|---|---|
| GPU 分配 | A100 实际显存、卡数、可用 GPU UUID；是否仅分配 MIG 实例，以及实例可用显存。先按一个任务占用一张实际可分配 GPU 验证，两模型顺序运行，实测后再配置并发 |
| 驱动与框架 | 两个独立环境内分别验证 GPU 可见、模型加载和真实计算；固定 AF3 的 JAX/CUDA 与 ESMFold2 的 PyTorch/CUDA 组合，不强行共用 Python 环境；宿主 nvidia-smi 正常不等于模型环境已可用 |
| CPU / 内存 | 记录 AF3 本地数据搜索阶段实际配额与峰值，GPU 推理和 CPU 数据准备分别计时 |
| 存储 | 分清数据库、权重、安装暂存、解压/构建缓存、运行输出所在分区的可用空间和配额；不能只报磁盘总容量 |
| 运行容量 | 先完成短序列真实预测，再逐步测试较长序列；记录成功长度和峰值，不能把多卡显存相加当单任务可用显存 |

AF3 官方安装文档验证过 A100，并建议至少 64 GB 主机内存，完整遗传数据库安装可能需要最高约 1 TB 磁盘。这里只用作容量规划参考，仍需为两模型权重、暂存和结果额外留空间；具体支持长度以本次固定环境实测为准。[官方安装依据](https://github.com/google-deepmind/alphafold3/blob/main/docs/installation.md)

A100 是可推进部署的硬件条件；在未知显存版本、配额及数据管线资源时，不提前承诺所有长度或双模型并发。不得因为看到 A100 就跳过显存/内存/磁盘检查，也无需等待重新采购 GPU 才开始盘点和安装。

### 工具身份与资产

| 引擎 | 身份及固定要求 |
|---|---|
| AF3 | Google DeepMind 官方 AlphaFold3；固定代码 commit、依赖、权重 SHA-256、本地数据库版本/清单、实际参数；本次单链请求要求 5 个 diffusion 样本 |
| ESMFold2 | Biohub 官方 ESMFold2，按项目已有 2026-05 标准版候选起步；不能用旧 ESMFold v1、ESM3 或第三方同名项目替代；Fast 是不同 checkpoint，不能静默替换标准版 |

2026-09-08 核对的官方入口：[AF3](https://github.com/google-deepmind/alphafold3)、[ESMFold2 模型卡](https://huggingface.co/biohub/ESMFold2)、[Biohub 实现](https://github.com/Biohub/esm)。具体安装参数以最终固定 commit 的文档和 `--help` 为准，交付记录实际执行命令，不使用浮动 `latest`。

项目历史候选（尚非已部署资产）：AF3 commit `c0f97eda2f1f482fd94d3a38bece18c7069b4a5c`；ESMFold2 标准版模型 revision `e1e189d0f5fb70c2693da2332eca4443c0ccccd6`、Biohub 代码候选 `b6b0e8815dc3174a9fe9afd36b222aea57d536c5`。如固定版本与服务器不兼容，记录替代版本及原因，不把候选写成验收版本。

安装时一次备齐权重及传递依赖，包括实际使用的语言模型、配置、tokenizer、CCD 与数据文件。AF3 的 CPU 数据准备和 GPU 推理可分开执行，但两段均须使用本地资产并留下输入输出与 hash。许可记录分别覆盖代码、权重、数据和结果使用条件；不要把开源代码许可当作所有资产许可，也不要回传令牌或无权分发的权重。

运行环境优先固定容器镜像 digest，同时交付构建文件和依赖锁定。服务器不能使用 Docker 时可交付固定 Apptainer 或环境包，记录差异，不要求为此重装宿主。运行时断网、输入/模型/数据库只读，输出与缓存写入每次独立目录；显式限制 CPU、内存、GPU 和磁盘使用。设置库的 offline 选项还不够，需要验证进程实际处于禁网环境。

### 从零部署操作顺序

以下工作由用户在助手逐步指导下完成，接口字段继续使用第 3–5 节，不另起一套协议。

1. **确定安装位置与资源**：完成上述检查，建立独立代码、环境、模型、数据库、请求和运行目录；记录实际路径及账号权限。复用已有兼容的 GPU 运行时；如需变更共享驱动或重启，先按服务器维护流程安排，不能直接照搬官方全新机器安装脚本。
2. **准备离线安装材料**：按固定版本收集两模型源码、完整模型快照、依赖 wheel/环境包或容器镜像，以及 AF3 数据管线需要的本地数据。安装阶段允许联网与否由现场确认；内网不能下载时，在获准联网的准备环境下载并构建，再转入内网，转入前后核对 SHA-256。镜像包同时记录文件 hash 和导入后 image ID/digest。
3. **部署 AF3**：按固定 commit 的官方安装文档构建/导入环境，取得官方权重，配置模型目录和全部实际使用的本地数据库路径；用完整单链输入先跑本地数据准备，再跑 GPU 推理并生成 5 个样本。保留准备后的原生 JSON/MSA/模板来源与 hash。只跑模型加载或跳过缺失数据不算完成完整本地序列输入链。
4. **部署 ESMFold2 标准版**：按固定 Biohub 代码与模型 revision 安装，备齐语言模型等传递依赖，全部改为可定位的本地资产引用。按固定版本真实支持配置 MSA；验证日志与输出证明实际采用的标准版、MSA 模式和权重。不得临时联网加载缺失组件或偷偷切换 Fast。
5. **证明独立禁网可运行**：在新工作目录、明确禁网条件下分别真实运行，允许使用已登记只读模型/数据，但不依赖未登记的用户缓存。保存有效启动命令、资源与输出。资产不全时先补资产，不能用下载成功或 import 成功代替真实预测。
6. **封装并验收**：将上述真实命令纳入统一 CLI，完成输出规范化、停止/超时与完整性守卫，执行第 6 节案例并交回第 7 节材料。两套环境可分别完成、分别交回，不要求同一天一起完成。

建议目录布局（示意，不要求使用系统目录；按用户实际权限和容量选择部署根）：

```text
<deployment_root>/
  src/alphafold3/         # 固定源码
  src/esmfold2/
  images/                # 镜像导入包或离线环境
  models/alphafold3/      # 只读模型资产
  models/esmfold2/
  databases/alphafold3/   # 本地数据库；其他准备数据按实际登记
  wrapper/               # run_structure.py 和 profiles
  requests/              # 示例及准备输入
  runs/                  # 每个 attempt 独立目录
```

交付 README 中直接填写两引擎的安装路径、环境身份、权重/数据库清单、实际启动与停止命令、已测资源/长度、复现请求和剩余问题。服务器已有 BLAST 等业务数据库不能未经核验就当成 AF3 遗传/模板数据库；也不要求把大数据库传回开发机。

## 3. 需要实现的调用入口

交付入口文件名统一为 `run_structure.py`，由它读取 JSON 并调用固定的原工具。两引擎可以在不同容器内执行，由同一入口选择执行配置。

```bash
python run_structure.py --input requests/af3.json --output-dir runs/af3-001 --profile profiles/af3.json
python run_structure.py --input requests/esmfold2.json --output-dir runs/esmfold2-001 --profile profiles/esmfold2.json
```

`--profile` 是服务器管理员维护的执行配置：固定引擎/版本、资产 ID/manifest hash 与本地路径、容器 digest、资源配额、超时上限、支持长度范围。每次调用复制不含秘密的配置快照并记录 SHA-256。请求只引用 `asset_profile_id`，不得传入任意 shell、镜像或模型绝对路径。

`--output-dir` 必须不存在；重复目录拒绝，不能覆盖已有结果。同一 `request_id` 重试允许使用新目录和新 `attempt_id`，全局幂等由项目任务层处理。一次调用只执行一次明确引擎，不在包装器中自动重试、排队或切换模型。

### 输入示例

下面是接口示例，不是预测证据。序列为 76 aa 工程测试输入，不能据此声明科学精度。

```json
{
  "contract_version": "t01.structure-worker/0.1",
  "request_id": "af3-demo-001",
  "engine": "alphafold3",
  "asset_profile_id": "af3-server-v1",
  "inputs": {
    "sequence_id": "ubiquitin-demo",
    "sequence": "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG",
    "host_species": "Homo sapiens",
    "chain_id": "A"
  },
  "parameters": {
    "seed": 1,
    "num_samples": 5,
    "msa_mode": "local_pipeline",
    "prepared_input": null,
    "timeout_seconds": 7200
  }
}
```

| 字段 | 必须遵循的约定 |
|---|---|
| contract_version | 固定为上述版本；未知版本拒绝 |
| request_id / sequence_id | 非空安全 ID，允许字母、数字、点、下划线、连字符；拒绝路径分隔符；原样回传 |
| engine | `alphafold3` 或 `esmfold2`；必须匹配执行 profile |
| sequence | 非空大写 AA20 原始序列，无 FASTA 标头/空格/终止符；不静默裁剪、补残基或替换 X；长度限制按实测 profile 明示 |
| host_species | 必填非空字符串，作为项目输入身份保留，不自行推断模型参数 |
| chain_id | 本次固定 `A`；包装器保存实际输出链与输入链映射 |
| seed | 非负整数；记录原工具实际 seed 参数及确定性限制，不保证 GPU 输出逐字节相同 |
| num_samples | AF3 为 5；ESMFold2 首轮为 1；不支持的值明确拒绝 |
| msa_mode | `local_pipeline`：本地生成真实准备数据；`prepared`：读取已准备且校验过的输入；`none`：仅在固定引擎/profile 已验证支持且调用者明确指定时允许，不作为缺数据库的自动降级 |
| prepared_input | 非 prepared 模式必须为 null；prepared 模式为 `{ "path": "prepared/input.json", "sha256": "真实64位小写十六进制hash" }`，路径相对请求 JSON 所在目录；拒绝绝对路径、`..`、URL 和越界符号链接 |
| timeout_seconds | 正整数且不超过 profile 上限；示例 7200 是请求预算，不承诺所有序列可在两小时内完成 |

ESMFold2 示例由上例改为 `engine=esmfold2`、对应 profile 和 request_id、`num_samples=1`。MSA 模式必须按固定标准版的真实支持选择并随交付给出完整可运行 JSON；不能仅为快速跑通改用 Fast 或假装 MSA 已加载。

`prepared_input` 是包装器自身准备文件的入口，内含目标序列身份、原生输入及所有关联文件的相对路径/hash、数据库 manifest 和生成参数。包装器负责核对序列与引用资产。不同引擎的原生格式不混用；其他伴随文件也须进行同样的路径约束和哈希验证。首轮至少验证同序列准备数据复用；WT 到突变体的科学复用由项目侧另行明确，不能直接修改序列后声称复用正确。

## 4. 输出文件与数据约定

每次尝试至少输出下列文件。名称表示本次交付要求，当前仓库不预先创建空文件或伪造结果。

```text
result.json                  # 包装器终态及候选索引，最后原子写入
manifest.json                # 除自身外所有交付文件的相对路径、字节数、SHA-256
execution.json               # 实际命令、版本/资产身份、时间、资源、退出码
profile.json                 # 本次执行配置快照，不含秘密
logs/stdout.log
logs/stderr.log
raw/                         # 原生输入、MSA/模板准备引用与原生输出
models/<model_id>.cif         # 每个成功候选的 mmCIF
confidence/<model_id>.json   # 与候选绑定的逐残基置信度
```

所有结果路径相对输出目录，使用 `/`，禁止绝对路径、外部 URL 和越界链接。原生输出可以位于 `raw/` 并被候选直接引用，避免复制大文件；路径不必机械采用示例文件名。manifest 写完后，再在验收索引记录 manifest 自身 hash，避免自引用循环。

### result.json 必需字段

| 字段 | 类型与语义 |
|---|---|
| contract_version / request_id | 与请求一致 |
| attempt_id | 每次实际执行生成的独立 UUID |
| status | `succeeded` / `failed` / `cancelled` / `timed_out`；只表示此单次执行 |
| engine / engine_version / asset_profile_id | 实际引擎、代码 commit/版本、配置身份；同时绑定 profile 与资产 manifest hash |
| sequence_id / sequence / sequence_sha256 | 回传输入身份；hash 为大写序列 ASCII 字节 SHA-256，不含换行；包装器自行计算 |
| host_species | 原样回传 |
| models | 候选数组；失败也可保留部分原生候选，但不得标成完整成功 |
| errors / warnings | 数组，每项至少 `{code, message}`；成功 errors 为空 |
| usable_for_pipeline / automatic_handoff | 本次固定 false；工程成功不开放科学消费或自动交接 |

每个 `models` 元素必须包含：`model_id`、`seed`、`sample_index`（0-based）、`source`（`af3_predicted`/`esmfold2_predicted`）、`structure_path`、`structure_sha256`、`format=mmcif`、`confidence_path`、`confidence_sha256`、`ptm`（0–1 或 null）、`iptm`（单链不适用为 null）、原工具评分及其字段名（存在则保留）。无值使用 null，不填 0；NaN/Infinity 拒绝。

AF3 保留全部 5 个样本及原始排名，不能只交官方默认 top1。项目单链选择规则依据现有 ToolSpec 为最高 pTM，由主开发在接入时实现；部署端不自行用 ranking_score 替换规则。ESMFold2 保留实际生成的候选和原始置信度。不要把不同模型的排名分数直接等同。

### confidence 文件

顶层包含 `model_id`、`sequence_sha256`、`raw_scale`（`0_100` 或 `0_1`）、`normalization`、`mean_plddt`、`residues` 数组。每个输入残基一条记录：

- `sequence_position`：1-based，与输入序列一一对应；`amino_acid`：单字母。
- `chain_id`、`label_seq_id`、`auth_seq_id`、`insertion_code`：真实结构坐标身份；记录缺失原因，不能按文件行号推断序列位置。
- `plddt_raw` 与 `plddt`：原始值和规范化 0–1 值；缺失填 null 并记录原因。

AF3 从真实 per-atom 置信度按结构身份取每个残基 Cα，0–100 除以 100。ESMFold2 根据固定版本的原始定义和实测确认尺度；0–1 不再除以 100。不得仅凭本次最大值猜尺度，不取全部原子的均值冒充逐残基 pLDDT。完整输出时 `mean_plddt` 为逐残基规范化值的算术平均；存在缺失时设 null 并告警，不用缺失为 0 或静默忽略来制造完整均值。

验证 mmCIF 可解析、序列/链映射、残基覆盖、置信度范围与数量及 hash。mmCIF 为主交付格式，PDB 可选，转换失败保留 mmCIF 和告警。质量低仍可为执行成功，后续 S-09 判定由项目负责；包装器不宣称科学质量合格。

## 5. 失败、停止与资源记录

| 退出码 | 状态/错误码 | 要求 |
|---|---|---|
| 0 | succeeded | 完整候选与必需产物校验通过后才返回 |
| 10 | failed / INPUT_INVALID | 参数、序列、路径或契约不合法，不启动推理 |
| 11 | failed / ASSET_MISSING 或 ASSET_MISMATCH | 模型、数据、环境配置缺失或 hash 不符；不能在线补取 |
| 12 | failed / TOOL_FAILED 或 RESOURCE_EXHAUSTED | 保存原工具退出码、stderr；OOM 分类要有证据 |
| 13 | failed / OUTPUT_INVALID | 输出缺失、不可解析、身份/置信度/哈希不合法；不伪造成功 |
| 14 | timed_out / TIMEOUT | 超过实际预算，停止进程树/容器并保留日志 |
| 15 | cancelled / CANCELLED | 收到 SIGTERM/SIGINT，停止子进程/容器并保留日志 |
| 20 | failed / IO_ERROR | 明确不可写/磁盘满等错误；无法落盘时至少 stderr 非零退出 |

包装器可正常收尾时以临时文件 + rename 原子发布 `result.json`，记录真实退出码与最终状态。SIGKILL/断电无法保证写终态，留下的中间文件不得被视为成功；交付实际进程/容器身份供主开发恢复核对。停止验收需证明没有遗留 GPU 进程或容器。

`execution.json` 记录 UTC 开始/结束、CPU 数据准备与 GPU 推理分段耗时、实际 seed/样本数、GPU 型号/驱动、配置资源上限、峰值显存/内存（无法测量时 null 并注明原因）、容器/进程身份、禁网方式、完整脱敏命令及日志位置。不记录密钥或用户令牌。

## 6. 实施顺序与验收

按三个连续步骤完成，不为每个小项另建准备文档：

1. 盘点服务器与已有资产，固定可运行环境；缺项具体列在本次交付记录中。
2. 两引擎分别完成原工具真实禁网预测，再实现第 3–5 节包装和规范化输出。
3. 执行下列验收，打包交付；主开发随后完成统一任务层与结构链联调。

| 验收项 | 完成证据 |
|---|---|
| AF3 单链真实预测 | 固定本地数据准备 + 5 样本；原生输入输出、结构、置信度、资源/禁网记录齐全 |
| ESMFold2 标准版真实预测 | 固定标准版及传递依赖，明确 MSA 实际状态；原生输出和规范化结果一致 |
| 同序列准备数据复用 | 准备数据 hash/来源一致，日志证明跳过相应准备过程，真实推理成功 |
| 输入与路径拒绝 | 非法字符、空序列、超 profile 长度、未知引擎、路径越界被拒绝；未启动推理 |
| 资产与输出守卫 | 缺权重/数据、hash 不匹配、输出缺失/破损/置信度出域明确失败 |
| 超时与取消 | 在运行中触发，确认进程/容器结束、无遗留 GPU 占用，状态与日志正确 |
| 重复调用与失败后重跑 | 原目录拒绝覆盖，新目录有新 attempt_id，旧结果不变，无隐式重试 |
| 长度与资源边界 | 报告至少短序列与一个较长序列的真实长度、耗时、峰值；1000–1500 和 >1500 aa 未测则写 NOT_RUN，不承诺支持 |
| 可迁移复现 | 在干净工作目录用交付命令和已固定资产复跑，结果身份、格式、manifest 校验通过 |

模型真实执行、受控故障注入、解析夹具测试分别标记，故障注入不能算真实自然 OOM。无需运行整个项目测试库；主开发接入后负责受影响回归、幂等/恢复以及下游结构 ArtifactRef 验收。

## 7. 最终交回什么

交回一个目录或压缩包，包含以下内容即可，不另写多个重复报告：

1. `README.md`：服务器环境摘要、已部署引擎与明确未完成项、安装/禁网启动/复现命令、实际支持长度和资源限制、目录配置方法。
2. `run_structure.py` 及其源码依赖、接口机器校验 Schema、环境锁定文件、镜像构建文件/导入说明、脱敏执行 profiles。
3. AF3 与 ESMFold2 各一份可直接执行的完整请求 JSON；prepared 模式实际示例和准备命令。
4. 模型/数据库/依赖 manifest、SHA-256、官方来源和许可引用；大型资产留在服务器，给出可定位路径与权限，不要求搬回开发机。
5. 每项验收的请求、终态、原始日志与必要输出；一个 `acceptance/index.json` 汇总场景、执行类型、PASS/FAIL/NOT_RUN、相对证据路径及 hash；不得预填通过。

交付报告分别写明：AF3 服务器工程部署、ESMFold2 服务器工程部署、统一任务层接入、下游结构链联调、科学签收。前两项可分别完成，后三项未验证就保持未完成；任何一个工具跑通不代表完整 W1 或项目生产发布完成。

## 8. 项目侧参考入口（按需）

本文是本次服务器交付接口的唯一说明。工具科学要求仍以专家原件为依据；遇到冲突记录具体字段/原工具事实，不自行改科学规则。

- [W1 计划](PHASE1_REAL_W1_BACKLOG.md)：本次属于预测结构链包，不新增波次。
- [已有模型身份和资产调查](PHASE1_REAL_W1_STRUCTURE_PREDICTION_G0.md)：历史候选与开发机调查，不代表服务器现状。
- [结构链 ToolSpec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md)：只采用现行保留的本地预测与结构质量部分，S-07 在线检索已移除。
- [统一 Worker 登记](../../../src/t01_phase1_real/development/registry.py)：由主开发后续扩展，部署端不重建任务系统。
- [项目当前状态](../STATUS.md)：实际进度单点维护。
