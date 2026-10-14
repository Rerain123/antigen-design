# T-01 当前状态

> 更新：2026-09-20。现行一期保留N01–N18，N03仅保留BLAST；真实开发IN_PROGRESS。ESMFold2首条工程链及统一常驻单卡Worker回归已通过；AF3资产、环境、本地搜索、单张64GB设备/JAX验证和5样本原生推理独立审计已完成。AF3标准适配器已完成本地导入、合成夹具、真实原始五样本只读复放和相关回归验证；原生26文件/25302596字节与独立审计一致，标准化选择与结构/置信度绑定通过。线上统一Worker已登记AF3第五命令并修正为独立`/var/lib/t01/resident/af3` spool；控制面AF3源码投影和注册表已部署，最新统一配置/代码为r07/r09，单卡守卫仍为唯一A100-SXM-64GB。科学Gate CLOSED，生产NOT_DEPLOYED。

## 当前任务入口

当前任务：[PH1-REAL-TARGET-DEPLOY](PHASE1_DELIVERY_PLAN.md#服务器部署与真实运行验收)

**AF3线上适配最新回填（2026-09-20）：** 已将AF3 policy/workflow、registry/runtime、`development/__init__.py`及适配器源码以只读ConfigMap投影到service和统一GPU Worker；service部署已滚动到generation 30，统一Worker随后更新为独立AF3 spool，避免AF3执行目录被遗漏。AF3命令解释器已固定为`/alphafold3_venv/bin/python`，标准化器在最小AF3环境中使用内置三字母残基映射回退，不依赖未安装的Biopython。线上失败批次完整保留：r02因旧service仅登记ESMFold2，r03因旧Worker缺少AF3 spool，r04因`/usr/local/bin/python`不存在，r05因旧`development/__init__.py`/Biopython依赖；这些失败均未覆盖。r05新工作流曾到达父任务`STATE succeeded`但prediction为`TOOL_FAILED`，报告仍明确`usable_for_pipeline=false`；该报告不作成功证据。最新r09代码配置已完成server-side dry-run、apply和滚动就绪，尚未用修复后的配置完成新一批AF3成功验收。下一步必须新建独立r06批次，确认五个native sample、标准ArtifactRef/hash/source binding、AF3→N01回连和父任务N18结果；不得重用上述失败批次。科学Gate CLOSED，生产NOT_DEPLOYED。

**统一常驻单卡Worker已上线并完成ESMFold2真实回归（2026-09-20）：** 用户选定“不创建Role/RoleBinding、一个常驻GPU Worker只申请一张A100 64GB、内部串行启动不同工具进程”的方案。现行Pod `antigen-design-7887db7f57-5t55g`在`k8s-a100-02`为10/10 Ready、0重启；仅`worker-unified-gpu`申请`nvidia.com/gpu=1`、`gpumem-percentage=100`、`gpucores=100`，启动守卫实测唯一设备为`NVIDIA A100-SXM-64GB`、UUID `GPU-f098e2d4-4cf3-a2c2-3503-6cca5bedde31`、65536 MiB。固定镜像为`antigen-unified-gpu@sha256:ef4586e2849a54a82c97648691b248521b87042123ef624700dc4136d79898fe`，四个登记命令为ProteinMPNN、ESM-IF1、ThermoMPNN和ESMFold2；`unified_gpu_worker.py`在两个既有spool上维护一个全局owner/FIFO，未确认停止会阻断后续工具，不调用Kubernetes API。

不可变配置`antigen-unified-gpu-config-r03`/`code-r03`修复ESMFold2的任务私有`slot/tmp`及“由原生Worker自行创建native目录”兼容点。r01卡住任务通过正式cancel/reconcile收敛为cancelled且停止确认；r02按原始失败回执保留`FileExistsError`；均未覆盖。r03真实76 aa任务`t01p1r-job-d263f828aa564e3cb1cecc2e0676340f`成功，resident回执`exit_code=0`、`stopped_confirmed=true`，严格加载及结构/逐残基confidence/manifest全部发布；父任务`t01p1r-job-bbc5bd5aab92478785545eb358f53802`到达N18并成功。原生pTM为0.7356957793、mean pLDDT为0.7986941934，单链标准ipTM仍为null；[验收快照](../../discovery/t01-phase1-real/unified-gpu-worker-20260920/r03/latest.json)保持`usable_for_pipeline=false`。选定GPU/Resident/ESMFold2相关回归全部通过；其余三种GPU工具保留原独立真实证据并完成新镜像基础依赖检查，后续只做统一镜像影响范围内的代表性实跑，不重做科学验收。

**AF3标准接入本地验证完成（2026-09-20，未部署）：** 已新增`development/af3`第一版policy/profile/native worker/standard/result/source模块，并接入registry、runtime、workflow prediction及N01/S-09来源链。模块导入、AF3审计/单卡/资产/准备脚本及原生格式回归均通过；从只读runtime PVC取回的26个原始文件、25302596字节在本地独立审计复放通过，标准适配器真实生成12个派生产物，五个样本全部保留，单链按最高pTM选择。sample 1/4同为0.86时保留全部并暂用“最低seed、再最低sample序号”作可复现工程选择，明确不使用官方`ranking_score`替代项目pTM规则，也不声称同分模型存在科学优劣。适配器已兼容真实原生CIF缺失`auth_comp_id`及`has_clash=0.0`格式，同时继续拒绝不一致/非二值输入。尚未改动线上r03 Deployment、未登记第五个resident命令、未启动新GPU任务。下一步生成受保护部署增量并进行单卡真实任务验收。

**AF3第五命令部署增量已生成（2026-09-20，未apply）：** `scripts/prepare_unified_gpu_deploy.py`已生成不可变`antigen-unified-gpu-config-r04`/`antigen-unified-gpu-code-r04`及`.tmp/unified-gpu-worker-r04/patch.json`、`deploy/single-gpu/unified-worker.r04.yaml`。AF3进入统一Worker的第二spool/FIFO，resident注册固定`/var/lib/t01/resident/af3`与AF3源镜像；Deployment新增`antigen-af3-models`和`antigen-af3-databases`只读PVC挂载及AF3/辅助源码投影，仍只有一个`nvidia.com/gpu=1`的64GB Worker。ConfigMap和Deployment patch均通过server-side dry-run，patch带当前resourceVersion/UID/spec保护；尚未apply、未重启或启动AF3线上任务。

**已停止的RBAC动态调度候选（2026-09-20，历史）：** 曾实现`gpu_dispatch.py`持久排队/单执行者切换与`gpu_once.py`单请求执行器，复用resident请求、取消和终态收据；释放旧Pod后才启动下一请求，状态恢复不重复派发，未确认停止阻断切换。该候选因需要当前账号无权创建的Role/RoleBinding而未上线，已由上述无需Kubernetes API/RBAC的统一常驻Worker方案取代；候选代码、29项测试和dry-run清单只保留历史，不再作为当前部署前置。AF3仍待标准适配器，未伪登记可调用。详细设计见[交接](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md#自动单卡调度器准备2026-09-20)。

**单卡恢复最终核验（2026-09-20）：** generation 25已应用，Pod `antigen-design-7744db5bc9-48kpc`在`k8s-a100-02`为10/10 Ready、0重启；仅`worker-esmfold2`申请GPU，HAMi唯一UUID为`GPU-f098e2d4-4cf3-a2c2-3503-6cca5bedde31`、65536 MiB/100核心。日志`ESMFOLD2_SINGLE_GPU_GUARD_PASS`及`resident_worker_ready`通过；这是启动与调度验证，未重跑ESMFold2模型。原推理Job Failed和独立审计成功分别保留。当前常驻ESMFold2已恢复，其他三工具GPU Worker暂未恢复，不能宣称完整业务链可用。13项相关测试通过。

**最新实施回填：单卡验证与AF3原生推理通过（2026-09-20）。** 常驻部署先以受保护补丁进入generation 24 CPU维护模式，旧两张40GB分配随旧Pod退出释放，CPU服务9/9恢复。随后64GB验证Job和AF3推理串行使用`k8s-a100-02`上同一UUID `GPU-f098e2d4-4cf3-a2c2-3503-6cca5bedde31`，HAMi回执为65536 MiB/100核心；运行时精确型号及JAX单设备计算通过。AF3完成1UBQ 76 aa、seed 1的5个样本，原生模型推理63.83秒。封装脚本误用不带前缀的输出文件名导致原Job Failed；原日志及failure.json保留，无GPU重跑。独立只读审计Job成功核验5条完整A链、各602原子、序列/主链/有限坐标/CIF与JSON置信度一致；pTM 0.85–0.86、Cα平均pLDDT 0.94640–0.95289。26份原文件共25302596字节已建立hash清单，[审计证据](../../discovery/t01-phase1-real/af3-target-20260920/single-gpu-r01/audit-summary.json)。已提交generation 25单卡ESMFold2恢复补丁；最终就绪状态见下方续行核验。OPS-002剩余自动模式切换、旧部署入口守卫及受影响工具回归，不能据本次串行验证宣称自动编排完成。下方暂停/阻塞及未推理段落保留历史时点，当前以本段为准。

**单卡纠偏续行预检（2026-09-20）：** 用户已要求恢复推进，当前由主动暂停转为具体外部信息阻塞。已只读复核Deployment generation 23仍分配两张40GB卡；6个相关PV均Bound且无节点亲和性限制。目标`k8s-a100-02`节点读取被集群RBAC拒绝，相关HAMi系统配置也无读取权限；历史64GB作业只有32GiB显存申请，不能据此生成完整64GB调度配置。下一项需要运维提供获准单卡的节点/标签/UUID、实际显存及HAMi资源/设备选择配置，或对应只读权限；具体证据及字段见[单卡预检](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md#单张a100-64gb资源修正2026-09-19)。尚未切换部署或启动推理，OPS-002继续开放。

**专家流程校准及GPU纠偏计划已更新（2026-09-20）：** 用户要求按专家文档调整计划，并限定全项目一张A100 64GB。[现行执行顺序](PHASE1_DELIVERY_PLAN.md#专家流程校准与单卡执行计划2026-09-19)为：AF3 r03无GPU解压、独立只读复核、固定环境构建/检查、权重解压和CPU本地数据搜索均已完成；当前暂停在新GPU任务前的单卡资源纠正；随后才进行AF3权重加载/5样本推理、N01–N10有效输入/Gate/WT、N11–N12验证与科学重算、N13完整复评、N14–N15评分排序、N16/N17/N18汇合及HiMat验收。已有工具工程证据保留，不重做独立验收。N15残留S-23必需阻塞须按一期裁剪修正，不能恢复安全三联筛。

本轮只读核实当前Pod `antigen-design-9f86d7f66-xsqqn`在`k8s-a100-01`，`worker-gpu`和`worker-esmfold2`实际均为`NVIDIA A100-SXM4-40GB`且UUID不同，确为两张40GB卡的分配。具体身份及互斥GPU实施/验收要求见[资源修正](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md#单张a100-64gb资源修正2026-09-19)。本轮只调整计划，尚未生成/应用部署补丁或重启；线上资源未修复，OPS-002继续开放，下一次GPU实跑受阻。AF3 r03解压为无GPU任务且已成功产生回执，不受影响。科学Gate CLOSED、生产NOT_DEPLOYED保持。

**AF3当前暂停点（2026-09-20）：** 9份数据库归档已完成安全解压并独立复核，共195867个文件、672.44GB（626.25GiB）；数据库卷总量1081.10GB、已用914.74GB、可用166.35GB（154.92GiB）。AF3权重已下载、校验并解压（压缩约1.02GB，解压约1.15GB）；固定AF3 v3.0.2环境r06已构建、推送并以不可变digest检查通过，环境检查无GPU完成。真实1UBQ/76 aa单链已在本地数据库上完成CPU数据搜索，MSA/模板输出约12.28MB（11.71MiB），结果已由独立只读Job复核，可作为AF3推理输入；该阶段未申请GPU、无OOM。当前没有活动的AF3/ESMFold2 Job，已完成Job/PVC/日志/产物保留。由于常驻Deployment仍是两个`A100-SXM4-40GB`分配，尚未生成或应用资源补丁；在单张经确认的`A100-SXM-64GB`互斥配置完成前，不加载权重、不启动AF3推理。状态为`AF3_LOCAL_DATA_SEARCH_VERIFIED_NOT_INFERRED`，科学Gate仍CLOSED、生产仍NOT_DEPLOYED。

**首条N01–N18工程链r03独立审计通过，转入AF3（2026-09-19）：** 固定1UBQ/人泛素76 aa序列，SHA-256 `233b4b0b8c4616095bc3249f9375fc345d32af7deaef07117d0383c51d6f19aa`；不上传或复用结构，显式使用ESMFold2 seed 1。父任务`t01p1r-job-850250a8eeef47fc84ea534198effeca`、run`t01p1r-run-9fdc66d3850640e698560d5c2570b26e`到达N18并生成报告：12个分支真实成功、8个按差距表原因透明跳过、0失败；206个ArtifactRef全部唯一且同run。ESMFold2→N01来源、76个逐残基置信度、结构hash及N17/N18消费闭环；报告ZIP 207338字节，SHA-256 `0fbd839ce2d211423e9810af33123dfdc63a13fe85c157afc075b96c16398e71`，外/内层manifest、hash及CRC均通过。[独立审计](../../discovery/t01-phase1-real/workflow-first-chain-20260919/r03/audit-summary.json)保留实际结果；N03/N08/N09为`DATABASE_NOT_PROVIDED`，N11–N14为`SCIENTIFIC_GATE_CLOSED`，N16为`NO_ELIGIBLE_SEQUENCE`，交付结果`DESIGN_INPUTS_UNAVAILABLE`，不解释为科学或生产放行。

调用`workflow.report`还自动把本次新的`report.md`和`report.zip`发布到RustFS `data/`路径，匿名HEAD均为200；该r03未继承旧两份报告的单次公开授权。未擅自删除对象或改桶策略，现需用户决定保留公开或授权精确撤回；后续报告发布代码也须改成显式授权，不能继续默认公开。此发布边界不推翻工程链审计结果。

AF3只读资产检查r01已创建但因权重PVC挂载根路径多写一层`weights/`而终态Failed/BackoffLimitExceeded；数据库侧检查已先执行到权重读取点，失败不是资产损坏，且所有PVC均为只读挂载、无数据变更。保留r01 Job/Pod/日志，不重建同名任务。修正后的[r02检查清单](../../deploy/alphafold3/assets-inspect.r02.rancher.yaml)已由用户运行并成功：9份归档共238784443666字节，数据库卷总量1081101176832、可用842299772928字节；按约630000000000字节展开量+68719476736字节余量，规划需求698719476736，`provisionally_sufficient=true`。权重为1020545840字节、SHA-256 `74d0258616917cd122f5eab6d076afe4a8930e96823851e65e4f777dfb1f33ff`，权重卷可用19920080896字节。以上为资产盘点时点记录；权重随后已解压并独立校验，科学Gate仍CLOSED、生产NOT_DEPLOYED。

AF3安全解压r01在首个FASTA文件遇到流式libzstd EOF边界bug后终态Failed，r02处理到第3个归档时因2GiB内存上限被`OOMKilled`/退出137；原归档及两次partial、Job/Pod/日志均保留且未覆盖。r03改用1MiB可复用解码缓冲、256KiB tar缓冲和周期性flush/fsync/fadvise后，用户回传Job `Complete 1/1`、实际运行3h8m，并回传终标记`AF3_DATABASES_EXTRACTED_VERIFIED 195867 672435030513`及一致JSON回执。2026-09-20独立只读Job `antigen-af3-extraction-inspect-r01`终态`Complete 1/1`，耗时约1小时49分；全量重算195867个文件SHA-256全部通过，其中195859个`mmcif_files/`文件及8个根级数据库文件，总计672435030513字节（672.44GB/626.25GiB）。数据库卷总量1081.10GB、已用914.74GB、可用166.35GB（154.92GiB）。状态为`AF3_DATABASES_EXTRACTION_INDEPENDENTLY_VERIFIED_NOT_DEPLOYED`；解压独立复核已关闭，随后固定环境和CPU本地数据搜索也已完成；AF3权重加载/推理仍未开始，科学Gate仍CLOSED、生产仍NOT_DEPLOYED。

**N12同次运行r02工程验收及独立审计通过（2026-09-18）：** r05已将现场`NVIDIA A100-SXM4-40GB`与既有`NVIDIA A100-SXM-64GB`登记为两个精确环境元组，并把`esmfold2/standard.py`同时覆盖Worker与service。新run`t01p1r-run-9d7e6460a37942f6a27c95bb0047e883`内，N01结构、ProteinMPNN、ESM-IF1和ESMFold2四个新任务全部succeeded；线上终态快照与保存内容一致，任务库60条且活动任务0，新Pod 11/11 Ready、0重启。

[独立审计](../../discovery/t01-phase1-real/esmfold2-target-20260917/n12-same-run-20260918-r02/audit-summary.json)重新核验135个ArtifactRef、127个按SHA去重的落盘文件及9829564引用字节，大小/hash/本地字节均一致；ProteinMPNN 24条和ESM-IF1原sample_number 1–24完整，显式选择sample 1的序列、33个突变、分数及来源闭环一致。ESMFold2严格加载折叠权重及802个ESMC参数，76残基/592原子结构序列一致、主链完整、坐标有限；mean pLDDT 0.8082659841、pTM 0.7371199727，精确环境为Python 3.12.14、PyTorch 2.7.1+cu126、CUDA 12.6、A100-SXM4-40GB。sample 1原R-35仍为`R35_DETERIORATION_EXCEEDED`，只按`EXPLICIT_ENGINEERING_ONLY_NOT_R04`绑定预测；`validation`/正式候选为null，科学Gate、自动交接和生产状态保持关闭。此前r01的GPU身份失败完整保留，不重写或拼接。本项工程验收已关闭，无需重跑。

**GPU资源口径需在下一次GPU实跑前修复（2026-09-19）：** 用户明确只允许使用一张`NVIDIA A100-SXM-64GB`，不能同时占用两张GPU。当前常驻Deployment generation 23仍有两个GPU容器：`worker-gpu`申请`nvidia.com/gpumem=10240`、`worker-esmfold2`申请约`30000`，Pod无`nodeSelector`/`nodeAffinity`；现场HAMi注解出现两个分配设备，不能把共享锁当成物理GPU拓扑保证。历史N12同次运行实际为40GB，独立ESMFold2 r03验证实际为64GB；两者均为真实工程证据，但不改变用户新的资源约束。AF3当前数据库解压为无GPU Job，不受此项影响；在下一次AF3/ESMFold2 GPU任务前，必须选择统一单GPU Worker或互斥GPU模式，绑定经确认的64GB节点/资源，加入精确GPU名称启动守卫，并用Pod/HAMi/运行时三层证据证明只有一张64GB卡被使用。尚未修改或重启现有Deployment。

**ESMFold2独立393残基容量审计通过（2026-09-18）：** 用户capacity393-r01原生完成，助手只读取回Job/Pod/源码配置/日志和原生产物，Job Complete、容器退出0，严格加载及manifest/hash、请求/profile、进程禁网探针核验通过。TP53全长393残基、3059原子，序列一致、主链完整、坐标有限；mean pLDDT=0.8781784773、pTM=0.5601621270；79.03秒含校验/加载/推理，PyTorch峰值allocated显存15.34GiB，非总GPU占用。固定环境采用PyTorch替代kernel，未证明与融合kernel数值等价；不现场补装依赖或改变本次环境。证据`capacity393-20260918-r01/audit-summary.json`；审计/收集及配置相关22项检查通过。本项只覆盖一条393残基案例，常驻后端仍76上限；1000–1500及>1500为NOT_RUN。下一项按现有包准备N12真实预测来源工程接入/验收；扩展后端长度须另行回归，Pod崩溃恢复仍未覆盖。科学Gate CLOSED、生产NOT_DEPLOYED保持不变。

**ESMFold2独立393残基容量验证待用户启动（2026-09-18）：** 用户选择项目已有较长真实序列；使用已登记本地TP53/P04637全长393残基，FASTA及序列hash按SOURCE_MANIFEST核对，仅登记为新的工程输入，不使用历史结构或继承S07验收。`scripts/prepare_esmfold2_capacity.py`生成`deploy/esmfold2-standard/capacity393.r01.json`，本地隔离/源码检查及三资源服务器dry-run通过。独立Job维持固定严格加载源码、原模型、3 loops/50 steps、32GiB显存限额、只读模型卷；进程seccomp探针+独立禁网NetworkPolicy，主运行卷共享GPU锁，与常驻Pod同节点亲和，30分钟截止且不重试。服务现11/11 Ready，任务42 succeeded/7 failed/2 timed_out/1 cancelled，无活动任务；运行卷剩余20849737728字节。无nodes查询权限，实际GPU可调度性待提交确认；旧Pod异常记录未删除。本轮未apply，科学Gate关闭、常驻76残基上限不变；结果审计前不宣称393支持通过。

**ESMFold2真实执行超时验收通过（2026-09-18）：** 用户任务`367ad5abcf20463e88d3763b6e01b9e7`按30秒期限终态timed_out/TIMEOUT。助手独立核对10份产物大小/SHA-256/落盘字节、停止收据和进程检查通过：native-request已生成、未进入推理、无取消文件，登记PID366/birth3301310一致且active=0，stop_confirmed=true、prediction=null、usable_for_pipeline=false。证据位于timeout-20260918-r01。本项覆盖真实原生执行在推理前的自动超时停止，不声称GPU推理阶段超时或自然性能超限。当前进程禁网、显式控制器恢复、推理中取消、推理前超时均有目标证据；Pod重启/崩溃恢复、较长序列容量及N12仍未完成。下一项准备独立较长序列容量验证配置，已验收后端9..76残基限制暂不改变；科学Gate CLOSED、生产NOT_DEPLOYED。

**ESMFold2真实超时验收已准备，待用户运行（2026-09-18）：** 新增`scripts/run_esmfold2_timeout_acceptance.py`，独立scope/幂等键和timeout-20260918-r01目录，真实76残基模型命令设置30秒期限，由常驻监控器自动停止，无sleep故障注入或人工cancel。要求真实native-request已生成、禁网执行观察存在、任务与收据均timed_out/TIMEOUT、停止确认、登记PID/birth匹配且active=0、prediction=null；自然成功或仅等待GPU锁不记超时通过。复用取消验收的修复后登记目录检查；19项受影响测试及payload语法通过。尚未启动服务器任务，不需镜像/部署变更。预计在资产校验/加载阶段触发，不能声称GPU推理阶段超时或自然性能超限；推理取消已有独立通过证据。科学Gate关闭。

**ESMFold2运行中恢复及推理取消通过（2026-09-18）：** 用户任务`2ecea4688bbd43aa9dbd3137760dff3e`在INFERENCE_START后取消并终态cancelled。初次末端检查误读/tmp默认登记目录；已修复为导入posix前选择Worker持久目录`/var/lib/t01/resident/esmfold2/.processes`，保留缺文件拒绝，并核对登记leader与收据PID/birth一致。助手只读检查原任务，active=0，11份产物大小/hash/落盘一致，恢复前后attempt/target/进程身份不变，停止确认且prediction=null、科学资格false；9项脚本检查通过。证据`lifecycle-20260918-r01/latest.json`和`process-check.json`，无需用户重跑或部署。通过范围为显式控制器恢复与真实推理中取消，不含Pod重启/崩溃恢复。下一项真实超时；较长输入独立容量配置仍待准备，科学Gate关闭。

**ESMFold2进程禁网证据已复核，恢复/取消验收待用户启动（2026-09-18）：** backend-r03成功预测的runtime.json记录INET_INET6_DENIED，executor-observation.json记录seccomp-local-sockets-only-v1；已核验源码先实际尝试IPv4/IPv6 socket并要求PermissionError，再加载模型预测，证明该真实预测进程禁网，不宣称整个Pod网络隔离。新增`scripts/run_esmfold2_cancel_acceptance.py`使用独立scope/幂等键，运行中显式recover后核对attempt/target/进程身份不变，见到INFERENCE_START才取消，终态核对停止收据、进程组活动数0、prediction=null及科学资格false；8项证据守卫测试及payload语法通过。仅准备，未启动服务器任务；回执保存lifecycle-20260918-r01。该恢复验证不包含Pod重启/故障恢复；超时仍待单独验证。当前后端上限76残基，较长序列必须先准备独立容量配置，不能直接扩大已验收支持范围。Gate关闭。

**ESMFold2 r03预测→N01工程验收通过（2026-09-17）：** 用户新父任务`8ed6478a144e4ae8b987562c7a40338a`完成，prediction `220ca37308da497da1499aa60f14c01e`及structure `72c4cff76e7c42158a836e185b83b19a`均succeeded。助手独立复核backend-r03/latest.json内109份产物的大小、SHA-256及本地文件字节全部一致，所有任务usable_for_pipeline=false。原始CIF保留，601原子工具副本及转换双hash绑定通过；76残基mean pLDDT=0.7989875060633609、pTM=0.7357823848724365，S-09为high/topology_reliable=true、无满足长度规则的低置信区域。FreeSASA执行成功；G76 RSA=1.257736509468096出域，保留OUTPUT_INVALID及normal_rsa_result=null，不截断，故本次PASS仅表示预测到N01工程链路通过。epitope_map无预测输入按S-19失败，非本次修复回归。下一项推进实际禁网、取消/超时/恢复及较长序列工程验证，N12和完整科学消费仍未验收；科学Gate CLOSED、生产NOT_DEPLOYED不变。

**ESMFold2 r03部署已核验，待用户新任务验收（2026-09-17）：** 用户apply及rollout成功；助手只读核实generation/observed=17，Pod `antigen-design-5df4d6f8d-fnp6k`为11/11 Ready、0重启。控制面平台digest正确，控制面22份、ESMFold2 Worker 11份及结构Worker 1份源码/profile hash均与已审查本地版本一致。验收脚本已切换独立r03 scope、幂等键、输出backend-r03，并增加结构Worker挂载及部署就绪守卫；payload语法检查通过，尚未启动任务。下一步用户运行`scripts/run_esmfold2_backend_acceptance.py`，断线重跑同命令接回同一任务。须独立审查N01质量及RSA出域结果，父任务成功不等于科学资格通过；Gate仍CLOSED。

**ESMFold2 r03已上传，部署增量待用户应用（2026-09-17）：** 本地发布回执与用户日志均为VERIFIED，平台摘要`sha256:0e572b386fd2ad45d3d9b844910b3ff6fb01ce0ad5d42a1be27e183fb76bdb2b`。当前generation/observed=16、Ready副本1；只读任务库34 succeeded、6 failed、1 timed_out，无活动任务。`.tmp/esmfold2-backend-deploy-r03`保存更新前快照、源码hash、不可变代码ConfigMap及resourceVersion保护补丁；服务器dry-run与5项补丁守卫测试通过。控制面及所有投影源码与本地hash一致；已现场确认结构Worker路径，新增单文件只读挂载，不更换原生FreeSASA镜像。增量同步更新ESMFold2 source/standard、新增quality及结构Worker；配置/PVC保留。尚未apply，用户部署后再准备独立r03新任务；本地重放RSA出域边界和科学Gate关闭保持不变。

**ESMFold2 r03镜像已构建核验，待用户上传（2026-09-17）：** 用户构建索引摘要`sha256:3b3f4b19285467d841b627cb6e17bdd763e17e602f2b0aafdc17180488cc748b`，Linux/amd64平台摘要`sha256:0e572b386fd2ad45d3d9b844910b3ff6fb01ce0ad5d42a1be27e183fb76bdb2b`。助手禁网只读核验镜像内14份相关源码/profile与本地一致。上传脚本已锁定r03镜像身份、独立回执目录及中转Pod，5项身份守卫测试通过。下一步用户运行上传脚本；随后准备同时更新控制面、ESMFold2代码与结构Worker的受保护部署增量，再启动新任务。集群尚未应用r03，科学Gate关闭。

**ESMFold2预测质量→N01本地接入完成，待r03构建发布（2026-09-17）：** 后端重新核验预测全部原始/派生产物后，以内部prediction-evidence.json绑定N01 attempt，传递原件/工具副本/质量ArtifactRef和转换记录；结构Worker仅在G0预测分支消费证据，控制面再次独立复算S-09并比对，普通上传文件不获得此资格。113项结构/预测回归通过，补充来源断言及常驻桥回归33项通过。使用真实backend-r02原件在固定离线FreeSASA镜像CPU重放，预检、A链映射、S-09、FreeSASA均执行；G76 RSA原值1.2570753471758602出域，按现有规则保留OUTPUT_INVALID，不截断、不宣称正常RSA或科学通过。重放证据`.tmp/esmfold2-s09-replay-9d1kf1xj`，不是新GPU任务。下一步由用户构建控制面r03，随后同步发布ESMFold2源码及结构Worker更新，再做目标新任务；科学Gate关闭。

**用户授权occupancy适配已实现，尚未部署（2026-09-17）：** 仅对已严格验证的ESMFold2单模型A链、无替代构象、occupancy整列缺失结果生成tool-structure.cif，新增1.0为工程约定；已有occupancy拒绝覆盖。逐字段重解析确认其他内容不变，保留原始CIF并记录原件/副本双hash及授权。N01来源校验改为绑定派生ArtifactRef，继续独立重算所有预测产物。基于专家SOP S-09新增独立prediction-quality.json，参数默认0.70/0.50、pTM0.50及低置信5残基/间隔3，双写掩码并保留科学关闭。实际backend-r02产物在本地派生后通过N01预检，quality为high/topology_reliable true/掩码空；旧结构Worker尚未消费该新质量产物，FreeSASA/RSA仍不自动放行。修复待构建发布及新任务验证，不能把本地原件复算称为新的GPU任务。

**N01专家依据已复核，缺失occupancy不得直接补值（2026-09-17）：** 结构链ToolSpec要求保留原件；实际预测CIF的601行原子均无替代构象，但occupancy整列缺失。现有结构Worker另有预测来源未核验分支，尚未接通已登记ESMFold2的S-09置信度，不能仅补列宣告N01完成。专家包未定义缺失occupancy补1约定；若需要工具专用派生副本，该处理须取得明确口径。SOP S-19明确两类预测输入均为空时失败，故本次epitope_map失败正确，撤回将其改为跳过的方向。下一步为登记预测证据直连S-09及独立下游兼容处理，具体依据和精确待决问题见模型交接文档；本轮未改原件、科学规则或部署。

**ESMFold2 backend-r02预测通过，N01结构输入兼容仍阻塞（2026-09-17）：** 用户运行新父任务`00c69ed5facd4cbaa912ebe70d6c9c13`，prediction `061a7652dff8470783d5368d2539c5b2`成功，浮点均值修复经新任务验证通过。助手从本地latest.json独立复核94份产物大小/SHA-256全部一致；N01失败诊断为`Missing coordinate field: occupancy`，不是预测失败，预测原生CIF与N01严格输入要求尚未兼容。epitope_map失败原因为`S-19 has no available epitope predictor input`，此次未请求BepiPred/NetMHC；需单独处理无上游路由。父任务succeeded仅代表工程汇总完成，验收标记正确为ESMFOLD2_BACKEND_N01_NOT_PASSED。下一项核对预测CIF occupancy来源及受控结构适配依据，保留原生结果、现有严格检查和旧终态；无需用户重复运行当前脚本。科学Gate保持CLOSED。

**ESMFold2 r02部署已核验，待用户启动新验收（2026-09-17）：** 用户已应用r02增量，助手只读确认generation/observed=16，Pod `antigen-design-b7d56b9cf-v2csl`为11/11 Ready、0重启，平台镜像digest正确；控制面及Worker各10份ESMFold2源码/profile hash与本地修复版本一致。验收脚本已切换独立r02 scope/幂等键/输出目录并锁定r02镜像与代码ConfigMap，本地payload语法检查通过，助手尚未启动新任务。下一步用户执行`scripts/run_esmfold2_backend_acceptance.py`，结果保存backend-r02；断线可重跑同一命令。旧r01失败及产物保留，科学Gate保持CLOSED。

**ESMFold2 r02已上传，正式增量待用户应用（2026-09-17）：** 本地发布回执VERIFIED与用户日志一致，平台digest `sha256:e31d68cd2ba1fd5199f86732c77abc3137ff3f342186b0a26645c562b75f2e5d`。助手只读确认11/11 Ready、0重启，32项任务全部终态；生成`.tmp/esmfold2-backend-deploy-r02`，新不可变ConfigMap及Deployment patch服务器dry-run通过，2项补丁守卫测试通过。补丁仅更新控制面镜像与Worker源码清单引用，清单源码差异仅standard.py；新镜像10份ESMFold2源码hash与挂载字节一致，更新前快照已保存。尚未应用，等待用户部署后准备新任务验收；旧r01失败保留，科学Gate关闭。

**ESMFold2 r02修复镜像已构建核验，待用户上传（2026-09-17）：** 用户构建索引摘要`sha256:1859176f294b5953bb2a5f132667adca93674509aac856c1f32de459da9446c2`，Linux/amd64平台摘要`sha256:e31d68cd2ba1fd5199f86732c77abc3137ff3f342186b0a26645c562b75f2e5d`。助手禁网只读启动镜像，10份ESMFold2源码/profile与本地修复版本hash一致。现有上传脚本已锁定r02身份并使用独立r02回执目录及中转Pod，5项上传身份守卫通过。下一步由用户执行上传，随后同时更新控制面镜像及Worker不可变代码清单，再准备新任务验收；尚未发布修复到集群。

**ESMFold2后端r01失败已定位，跨Python均值修复待发布（2026-09-17）：** 断线后只读核验Pod仍11/11 Ready、0重启；原生执行成功且exit 0，但prediction任务`c0309371…`因标准结果字节比对被判OUTPUT_INVALID，N01验收未通过。控制面重算mean pLDDT为0.7987064140721369，Python3.12 Worker为0.7987064140721372；其余标准字段一致，confidence hash差异传递至result引用。已将新后端派生均值改为math.fsum，保留原生指标和严格字节/hash检查。19项受影响回归通过，实际Python3.11.16/3.12.14禁网只读对照的四份标准文件hash完全一致。修复尚未发布；下一步由用户构建`antigen-design:esmfold2-backend-r02`，再准备上传和Worker不可变源码清单更新，最后以新任务验证。旧r01终态和原生结果保留，不重写为成功；科学Gate保持CLOSED。

**ESMFold2常驻部署启动通过，待新任务验收（2026-09-17）：** 用户应用配置单文件挂载修复后，助手只读确认Pod `antigen-design-d667fcf98-ngmf5`为11/11 Ready、0重启；ESMFold2及原GPU Worker均输出resident_worker_ready。控制面与模型Worker各10份ESMFold2源码/profile逐文件hash均与本地一致。已准备`scripts/run_esmfold2_backend_acceptance.py`，本地payload语法检查通过，尚未启动模型；由用户运行新76残基预测→N01验收。固定专用scope/幂等键支持断线后重新运行接回同一任务，终态收集原始产物并核验大小/hash，失败不报PASS，不发布RustFS报告。科学Gate继续CLOSED。

**ESMFold2部署后启动修复待应用（2026-09-17）：** 用户已应用正式增量并收到rollout成功；助手随后只读复核generation/observed=14、控制面digest正确，但Pod `antigen-design-86b9db4bc-g48wz`为10/11 Ready，ESMFold2 Worker因`Worker configuration/root symlink`重启。ConfigMap目录投影使配置路径成为符号链接，与既有安全检查冲突。已修复部署生成器为只读单文件subPath挂载，保留原安全检查，5项部署测试通过。最小修复补丁`.tmp/esmfold2-backend-mount-fix-r01/deployment.patch.json`及更新前快照已保存，服务器dry-run通过；待用户应用。不需重建镜像或重新上传，尚未启动新预测任务，科学Gate保持CLOSED。

**ESMFold2控制面已上传，待用户应用正式增量（2026-09-17）：** 上传回执VERIFIED，平台digest `sha256:1c8b3f7c233580acd616d7e5b62a2c135fb9283d035399ead6dfde06420a2677`，中转Pod已清理。助手只读核对现有服务10/10 Ready、0重启；任务库21 succeeded、2 failed、1 timed_out，活动任务0。正式目录`.tmp/esmfold2-backend-deploy-r01`包含两ConfigMap及受resourceVersion保护的Deployment patch，服务器dry-run通过，`deployment.before.json`已保存。尚未应用；下一步由用户应用增量，再验收新预测→N01及生命周期。科学Gate保持CLOSED。下方较早构建/上传指引已完成，无需重做。

**ESMFold2统一任务/N01本地接入已实现，待构建发布（2026-09-17）：** 新增`development/esmfold2`，按新job/attempt执行严格加载、原生校验与标准结果生成；workflow可显式指定ESMFold2，成功后以原始G0结果ArtifactRef回连N01，失败不回退或伪装上传。复用现有幂等、取消、恢复、收据与SQLite任务库，科学资格关闭。13项新增任务/来源测试、4项部署渲染测试及既有工作流/常驻桥/API35项通过。完整当前根首轮1993通过、15跳过、5失败：4项因本轮改动冻结common.py触发，现已精确恢复原hash并重验全部通过；另1项为旧报告两处既有断链。独立Linux实际导入、INET/INET6拒绝与跨执行根GPU文件锁通过，未运行新模型。两ConfigMap与Deployment patch服务器dry-run通过，使用旧控制面digest仅检查清单，不能用于上线。下一步由用户本地构建新控制面镜像，随后发布、重新生成正式增量并启动新目标任务；集群未修改，N01目标整链与真实取消/超时尚未验收。[实现与用户命令](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md#统一任务与n01接入准备2026-09-17)。

**ESMFold2标准封装已完成（2026-09-17）：** [封装脚本](../../scripts/package_esmfold2_result.py)通过37项受影响测试。用户已生成正式派生目录`standard-r01`并执行verify，助手再次只读复核通过：25文件、76残基，manifest SHA-256 `b5e0d7ca19af8c53aabd0640ca06a48c35084ca97839d30c195852d12f8c0797`与验证包一致。[标准结构索引](../../discovery/t01-phase1-real/esmfold2-target-20260917/standard-r01/result.json)、逐残基置信度、参数、来源hash、执行记录与源码快照已落盘；8份原始产物逐字节保留，单链ipTM规范为null、原生0保留，科学Gate关闭。本项标准封装完成，未重跑推理或操作集群。当前下一项为新任务来源登记、统一任务层与N01接入；适配器仍明确绑定已登记r03布局与来源，尚未接通统一任务/N01/N12。详见[完成回执](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md#esmfold2标准封装2026-09-17)。下方r03说明保留本次封装起点及后续范围，下一项以上述完成回执为准。

**当前进度（2026-09-17）：** ThermoMPNN新A100任务180行原生结果全部解析、140行入选；N16独立Linux依赖与colorama修复后，新E.coli案例60nt DNA翻译一致且约束通过，证据见[r02摘要](../../discovery/t01-phase1-real/target-science-20260916/r02/summary.json)。RustFS新控制面已发布至generation/observed=13，10容器Ready、0重启；用户当轮明确批准这次1UBQ的两份报告公开只读后，后端workflow.report发布ZIP/Markdown成功，匿名下载大小/hash、ZIP CRC及重复发布同对象核验通过，未重算科学任务，见[入桶证据](../../discovery/t01-phase1-real/rustfs-report-20260917/r01/summary.json)。本轮36项受影响测试通过；未提交/推送Git，镜像来自当前工作区，发布细节见[本包回填](PHASE1_DELIVERY_PLAN.md#rustfs报告入桶与模型配置续行2026-09-17)。

**当前下一项：ESMFold2标准结果封装与后端接入。** 用户已取回r03的8份原始产物（67351字节），助手独立核验大小/hash、固定请求/profile/Job配置、严格权重加载、结构序列/坐标和置信度通过，见[审计结果](../../discovery/t01-phase1-real/esmfold2-target-20260917/r03/audit-summary.json)。A链76残基、601原子，主链齐全、坐标有限；平均pLDDT=0.798614、pTM=0.735635。目标A100执行记录164.97秒（含校验/加载/推理）、PyTorch峰值已分配显存13.06GiB、进程峰值RSS29.02GiB；仅证明本次3 loops/50 steps、seed 1的短序列工程运行。20项产物审计/收集守卫测试通过；旧r02失败及r03原始文件未改。下一步补齐标准结果/逐残基置信度接口与统一任务层接入，再验证禁网实际效果、取消/超时/恢复及较长输入；独立Job成功不等于完整部署验收或N01/N12已接通。临时读取Pod已由用户删除，无需重复清理；具体下一项及完成标准见[模型接入续行计划](PHASE1_DELIVERY_PLAN.md#模型接入续行计划2026-09-17)。HiMat继续后移，科学Gate保持CLOSED。

**AF3权重及数据库归档已下载校验（历史准备记录，2026-09-17）：** 权重r02已Complete，1020545840字节、官方CRC32C通过，SHA-256 `74d0258616917cd122f5eab6d076afe4a8930e96823851e65e4f777dfb1f33ff`；当时独立20Gi卷内保存、尚未解压/加载/推理，随后已完成权重解压校验。用户最新回传数据库Job `antigen-af3-databases-download-r01`为Complete 1/1、耗时3h37m，终标记`AF3_DATABASES_ARCHIVES_VERIFIED 9 238784443666`；9份归档约238.78GB全部通过下载器官方MD5及本地SHA-256校验，保存于独立1Ti PVC。该段保留下载时点事实；后续安全解压、独立复核、固定环境和CPU本地数据搜索已完成，当前仍未进行AF3 GPU推理。保留下载Job、PVC及归档，不重新下载。科学Gate保持CLOSED。[操作步骤与完成记录](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md#af3数据库下载2026-09-17)。

**临时结果Pod已清理：** 用户回传`antigen-esmfold2-results-r03`删除成功；上方清理指引已执行，模型卷、运行卷及本地r03证据保留，无需再次删除。


以下较早记录中的“下一项”“待发布”和阻塞描述均保留其时点事实，现行进度以上述最新回填为准。

**已部署科学工具集中实跑（2026-09-16）：** 已直接通过测试服后端执行新批次，16个任务全部终态：10成功、4失败、2取消；469份产物大小/SHA-256及后端报告ZIP CRC通过。ProteinMPNN新生成1条、ESM-IF1回评分1条及WT基线、FoldX RepairPDB/PositionScan与3个变体各5次BuildModel、N10→A3D/PROPKA均取得目标结果；成功数不等于业务节点完成数。FoldX初次缺`assets.json`，17份现有资产逐项核验后补入原登记文件，新任务成功、两次旧失败保留。剩余两项部署阻塞：ThermoMPNN原生输出180行但结果校验仍绑定本机GPU型号而拒绝A100；独立N16被Windows依赖清单与Linux环境差异及缺colorama阻止，未生成DNA。运行中FoldX取消及同attempt控制恢复通过；工程报告保留ThermoMPNN失败。结束时generation/observed=11、10容器Ready/0重启。详见[本批回填](PHASE1_DELIVERY_PLAN.md#已部署科学工具集中实跑回填2026-09-16)及[证据索引](../../discovery/t01-phase1-real/target-science-20260916/r01/index.json)。未发布新镜像、未提交/推送；科学Gate及生产资格不变。

**全项目复核与部署续行安排（2026-09-16）：** 本轮只读回查测试服仍为generation/observed=11、10容器Ready/0重启，运行与工具资产PVC各20Gi；service尚无RustFS环境，GPU为10GiB小样本配额。r02报告ZIP大小/hash/CRC重新核验通过；它覆盖19个内部条目、11成功/8跳过，不能换算为11/18业务节点完成。流程代码仍固定关闭N11–N14、未接入无结构预测，N15/N17/N18成功仅为相应工程汇总。ESMFold2完整清单已生成，本轮23份文件、26791863243字节逐项大小/hash均通过，状态应为“已下载、未部署”。新的[部署续行计划](PHASE1_DELIVERY_PLAN.md#部署续行计划2026-09-16)在原包内安排HiMat闭环、剩余工具目标实跑、双模型/三类数据库、完整业务编排及生产验收，不重做已完成镜像与资产迁移。没有提交、推送或修改集群。

**发布修复及新批次通过（2026-09-16）：** 提交`3ecb280`已按用户授权推送Codeup `test`，新控制面与DeepTMHMM Worker已部署，10容器Ready、0重启，线上20份冻结来源及BepiPred 104项资产核验通过。线程根因是原包按192个可见CPU设置192/194线程，超过容器4核配额；常驻适配按登记预算限制为2/2，原包及600秒期限不变，独立服务器新任务13.32秒完成。另补齐BepiPred遗漏的4份来源文件与文档换行。232项受影响回归通过。新批次r02 `b5c8b65e…`逐节点确认11项成功、8项明确跳过、0失败/超时，结构/拓扑/BepiPred/NetMHC均成功，报告下载大小/hash/ZIP CRC通过；旧r01失败身份与报告保留。详细镜像、回执与边界见[当前部署包](PHASE1_DELIVERY_PLAN.md#codeup发布通道现场补充2026-09-15)。

**当前下一项：关闭本批两项部署适配阻塞，HiMat联调后移。** 依据[最新用户决定](DECISIONS.md#科学工具优先与-himat-联调后移)，[部署续行计划](PHASE1_DELIVERY_PLAN.md#部署续行计划2026-09-16)批次1已取得上述真实执行证据；在原包内修复并发布ThermoMPNN目标GPU结果适配、独立N16 Linux依赖profile，再以新任务关闭对应失败，不改旧任务或跳过校验。随后继续双模型、数据库与流程接入。报告真实写入RustFS的`antigen-design`桶并核验大小/hash作为批次2独立补齐，本轮后端报告下载及既有小对象探针均不代替报告入桶；RustFS代码/环境仍待发布。HiMat文件接收、异步交互、卡片及附件显示后续集中调试，不阻断当前工具部署；工程实跑不代表科学签收或生产放行。

**RustFS存储实测通过、报告接入待发布（2026-09-16）：** 用户完成`him-ws/antigen-design-rustfs`凭据录入。助手从运行中控制面进行随机小对象PUT、HEAD大小/hash校验、匿名GET全文hash核验、精确DELETE及删除回读，结果全部通过，回执`.tmp/rustfs-verification/probe.json`。密钥仅在进程内存和exec stdin传递，未输出或落盘；未读取/复制OligoSmith凭据。本地新增报告发布模块并接入MCP workflow.report，开启后返回Markdown/ZIP附件URL，失败可重试且不返回已完成附件；21项受影响测试通过。Secret引用与环境补丁服务器dry-run通过；本轮未提交/推送、未更新正式Deployment，因此线上报告仍为旧接口。下一项发布新控制面、应用RustFS配置，再验证真实报告及HiMat卡片。详情见[Codeup现场补充](PHASE1_DELIVERY_PLAN.md#codeup发布通道现场补充2026-09-15)。

**批量Worker已启动（2026-09-16）：** 用户执行[scripts/deploy_resident_cluster.py](../../scripts/deploy_resident_cluster.py)的apply后，助手只读确认Deployment generation/observed均为8，新Pod `antigen-design-75cf69d8c8-mmlvt`位于`k8s-a100-02`，控制面和9个Worker全部Ready、0次重启。9组日志均出现`resident_worker_ready`；控制面安全读取11项命令注册成功，9个共享执行目录存在且可写，8个资产目录可见。从HiMat api容器访问healthz返回ok。GPU为10GiB小样本测试配置，数据库摘要仍为空；当前完成启动和挂载检查，未执行本轮科学任务或HiMat业务提交。下一项集中小样本真实计算与报告链验收。原部署快照、应用回执及挂载检查在`.tmp/antigen-resident-deploy-r01`，详情见[Codeup现场补充](PHASE1_DELIVERY_PLAN.md#codeup发布通道现场补充2026-09-15)。

**HAMi GPU轻量验证通过（2026-09-16）：** 用户应用`.tmp/antigen-gpu-probe.yaml`后watch连接中断；助手另行只读查询确认Pod已Completed、0次重启，正常调度至`k8s-a100-02`，镜像拉取耗时约2分13秒。日志为PyTorch `2.7.1+cu128`、CUDA `12.8`、`NVIDIA A100-SXM-64GB`、容器可见显存10240MiB及`GPU_COMPUTE_PASS`。已证明发布GPU镜像在本集群申请10GiB配额后能执行微小CUDA计算；未加载科学模型，未验证超额分配隔离或64GB配额可申请。下一项批量装配常驻Worker并进行真实任务验收；正式显存配置不直接沿用演示值。详情见[Codeup现场补充](PHASE1_DELIVERY_PLAN.md#codeup发布通道现场补充2026-09-15)。

**ESMFold2标准版下载准备（2026-09-16）：** 用户授权先推进标准版下载及部署准备。已核实既有标准版权重revision仍可公开访问、依赖ESMC-6B（约25GiB合计模型资产），Biohub源码要求独立Python3.12。服务器Hugging Face DNS解析失败、本机访问成功；已启动D盘独立后台续传下载，逐文件按官方LFS SHA-256或Git blob校验，未下载Fast版、未运行模型。源码/模型版本和日志入口见[部署说明](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md#esmfold2标准版准备回填2026-09-16)。已准备60Gi独立模型PVC清单，尚未应用；3项下载器测试通过。用户的GPU Worker上传仍由用户掌管，本次未干预。完整资产校验、环境安装、GPU挂载与真实推理仍待完成。

**Worker镜像发布完成（2026-09-16）：** 用户通过`.tmp/resume_resident_publish.py`完成GPU续传，返回`VERIFIED_REMOTE gpu`、`ALL_PUBLISHED 9`及`TEMP_RELAY_REMOVED`。助手读取本地`publish-receipts.json`，确认9项均为VERIFIED，GPU摘要与用户日志一致。9个Worker镜像已发布到Harbor，标签`integration-20260916-r01`；本次仅核对日志和回执，未重新连接仓库或集群。下一项为GPU资源配置、资产卷挂载、批量启动Worker及真实任务验收，尚未更新正式Deployment或触发Jenkins。详情见[Codeup现场补充](PHASE1_DELIVERY_PLAN.md#codeup发布通道现场补充2026-09-15)。

**Harbor现有账号核实（2026-09-16）：** 用户指出`him-ws/harbor`镜像仓库Secret。助手从上传Pod确认内部Harbor认证入口，再以内存中的现有凭据请求本项目9个`qcyz/antigen-design-resident-*`仓库的令牌；服务器返回的授权均包含pull/push。未输出或落盘凭据、未推镜像；此前“推送权限待确认”已关闭。下一项准备通过现有集群连接的内网镜像传输/发布通道，无需申请新账号或公网Harbor入口；端到端推送及digest回读尚未验证。

**公共流水线源码核对（2026-09-16）：** 用户提供`qcyz`完整Pipeline脚本。现有配置支持`imageName`和目标`containerName`，但Build固定仓库根context/Dockerfile且仅构建一个镜像，`targets`只选一个匹配目标，不是多镜像构建列表。添加Worker后可在本项目Jenkinsfile显式指定`containerName: 'service'`，无需依赖容器排序；本次未改代码或公共流水线。首次Worker发布建议批量推送本地已验证的`integration-r01`镜像；待落实现有Harbor可达入口及qcyz推送权限，或获准在已有内网构建节点批量导入。当前kubeconfig和Jenkins查询权限不能证明镜像推送权限；不以修改共享任务或申请公网开放为前置。

**资产卷迁移完成（2026-09-16）：** 用户创建`antigen-design-assets`（20Gi ceph-rbd，Bound）及临时上传Pod，将7,562,240,000字节资产包上传并解压到卷根。用户回传归档SHA-256与本地清单一致；助手通过本机kubectl只读核对解压后230/230个文件的大小、SHA-256及文件权限，全部PASS，无错误，卷剩余5,815,529,472字节。原归档仍保留在`.incoming`，上传Pod暂留；正式服务尚未挂载资产卷，9个Worker镜像发布和GPU配置仍待落实。后续挂载RWO卷前须停止临时上传Pod，保留PVC。详情见[Codeup现场补充](PHASE1_DELIVERY_PLAN.md#codeup发布通道现场补充2026-09-15)。

**本机集群连接（2026-09-15）：** 用户提供的kubeconfig已保存到Git忽略的`.tmp/himat.kubeconfig`并核对副本完整性；助手已使用本机kubectl只读连接`him-ws`，确认`antigen-design`为Ready 1、单个`service`容器、Recreate及Always拉取策略。账号允许创建Pod、pods/exec、pods/portforward、PVC和ConfigMap，以及patch Deployment、读取Pod和日志。现有20Gi运行卷Bound，独立资产卷尚未创建。下一步准备独立资产PVC和文件传输，继续落实9个Worker镜像发布与GPU配置；此次未修改集群。详情见[Codeup现场补充](PHASE1_DELIVERY_PLAN.md#codeup发布通道现场补充2026-09-15)。

**试发布回读（2026-09-15）：** `c5f5200`首次推送后曾仍为旧镜像；按用户要求用`07ee0b9`新增构建标签重触发后，用户已返回新控制面实际镜像摘要`1601b336…d8c9592`、Pod Ready true、rollout成功及HiMat api访问healthz为ok。随后用户提供Jenkins实际构建日志，确认完整提交`07ee0b9fa4507fe350bdfcd353683a9e064aba8f`构建并推送的镜像摘要与运行Pod一致，控制面源码→构建→部署证据已对应；科学Worker、权重及数据库仍待传入/装配，Gate保持关闭。完整摘要及下一项见[Codeup现场补充](PHASE1_DELIVERY_PLAN.md#codeup发布通道现场补充2026-09-15)。

**发布通道补充（2026-09-15）：** 用户现已取得Jenkins查询账号，并选择自行操作浏览器、提供日志。此前授权的Codeup `test`推送已完成；实际流水线使用BuildKit构建根Dockerfile，推送单个`antigen-design:latest`镜像，选取Deployment首个容器名（本次为`service`）更新镜像、重启并等待rollout。本批源码包含常驻适配，但不包含本机镜像、权重、临时数据和增量ZIP；多Worker发布与资产传输仍待落实，不能由源码推送推定完成。详情见[Codeup现场补充](PHASE1_DELIVERY_PLAN.md#codeup发布通道现场补充2026-09-15)。

**最新执行方式（2026-09-15）：常驻 Worker 内启动工具进程。** 暂停共享Job RBAC申请。第1步[环境装配](PHASE1_DELIVERY_PLAN.md#常驻环境批量装配回填2026-09-15)和第2步[镜像/资产打包](PHASE1_DELIVERY_PLAN.md#常驻镜像与资产打包回填2026-09-15)已完成，Docker已迁至D盘。**第3步本地业务接通与集中实跑完成**：11类原生工具及PROPKA取得新结果，本地认证MCP上传→提交→查询→报告下载通过；21个新任务、452份产物核对通过，受影响测试183项及Linux进程/装配测试26项通过。已修复A3D嵌套调用、BepiPred导入路径和ThermoMPNN配置定位，构建新控制面及9个Worker镜像，生成约522KiB增量包。旧大包保持原字节，尚不包含本轮修复。详细边界见[集中联调回填](PHASE1_DELIVERY_PLAN.md#常驻业务集中联调回填2026-09-15)。下一项为镜像上传、资产卷/GPU挂载和HiMat现场验收；本轮未更新服务器，未开放完整科研流程。

**当前安排（2026-09-15）：测试服流程优先，批量接入、集中联调。** 用户确认当前已部署的是 `antigen-design` 控制面，科学 Worker 尚未完成集群实跑，数据库根未配置；动态Job授权申请已暂停。上述为用户提供的现场事实，本轮未连接集群。HiMat 为实际使用入口，参考引物项目的集群内 MCP 和 RustFS 附件链路；Dify 历史局部联调不能替代 HiMat 验收。在同一个部署包内统一配置执行目录、资产和工具映射，批量补齐目标结果适配与 HiMat 文件/报告接口，以固定小样本集中打通提交→真实执行→结果汇合→下载；不再要求一个工具完成整套验收后才接入下一个。首轮允许明确缺项的工程报告，完整设计链仍继续补齐；生产运维、完整容量与逐工具故障矩阵后移，必要校验和真实失败状态保留。完成标准及后移事项单点见[现行测试服安排](PHASE1_DELIVERY_PLAN.md#测试服流程优先安排2026-09-15)，用户依据见[决定](DECISIONS.md#测试服流程优先与-himat-入口)。

**现场回填（2026-09-15）：** 用户返回 `antigen-design` Deployment 为 Ready 1，Service 为 80/TCP，独立 20Gi 运行卷已 Bound；Deployment 未显式指定 SA，仅挂载运行卷、服务认证 Secret 和临时目录，未挂载工具资产/launcher 配置。用户从 HiMat `api` 调用 `/healthz` 已得到 `status=ok`；带认证 MCP 调用尚待验证。资源、健康结果和本机资产盘点见[测试服资源快照](PHASE1_DELIVERY_PLAN.md#测试服资源快照2026-09-15)。此前准备的共享 Job SA/RBAC 管理员清单保留作历史资料，当前常驻路线不再要求应用该清单。

以下为各批次历史回填；其中“下一动作”“未部署”和旧部署名称仅代表原时点，当前安排以上段及现行测试服计划为准。

**源码与镜像入口（2026-09-14）：** 同事已建立 Codeup 仓库 `agent/antigen-design`（`https://codeup.aliyun.com/6549a8ea3aaed849b035cf92/agent/antigen-design.git`），本次完成项目代码的 `main` 分支初始导入。该地址是 Git 源码仓库，不是 Harbor 镜像地址。现场已确认共享 Harbor 项目路径格式 `harbor-core.base.svc.cluster.local/qcyz/*` 及拉取 Secret `harbor`；本项目的 `qcyz/antigen-design` 实际推送结果和 platform manifest digest 仍待 Jenkins 首次构建后登记。

**CI 接入批（2026-09-14）：** 用户提供旧项目的公共 Jenkins 配置并确认该流水线只更新已存在 Deployment 的镜像，不创建首次 Kubernetes 资源。本批新增根目录 `Dockerfile`/有界 `.dockerignore` 和指向 `him-ws/t01-control-plane` 的 `Jenkinsfile`，并将既有验证过的17份 Linux wheel作为有界CI输入；根目录镜像以禁网依赖安装成功构建，断网/只读/非特权容器 UID 10001 及核心导入通过，新增回归通过。本批以 Codeup `test` 分支为发布入口，用户已授权提交/推送；Git 推送不等于部署完成，公共 Jenkins 的实际触发、Harbor 推送和集群更新仍待执行回执。新 CI 构建不复用旧 rc3 digest，现场仍须登记实际 platform manifest digest。

**修复实施（2026-09-12）：本轮本地部署缺陷修复与新候选校验完成，目标仍未部署。** NetworkPolicy回读、结构挂载、现场配置/资产/RBAC渲染、A3D嵌套Job、发布格式校验和快照误报已修复；另修复真实容器暴露的CLI配置错位与Linux同端口重启失败。最终全仓1782通过/1跳过，新离线包50份索引及11类Job通过独立校验；结构/A3D原生禁网容器与rc3控制面认证/取消/重启/恢复/报告通过；结构/A3D目标结果校验已实现但现场证据未取得，其余通用工具结果profile、容量及完整科学流程仍未完成。09-14新现场事实已确认 `him-ws` 内部 Harbor 域名为 `harbor-core.base.svc.cluster.local`、`harbor` 是可作 `imagePullSecrets` 的 `kubernetes.io/dockerconfigjson`，已有工作负载使用 `qcyz/*`；专用 `t01-control-plane` SA 明确不存在，当前账号不能读取 Role/RoleBinding。已备管理员清单，未应用集群。当前成果、测试批次与下一动作单点见[部署修复回填](PHASE1_DELIVERY_PLAN.md#部署修复实施回填2026-09-12)，新候选0.2.0-rc3不覆盖旧0.1.0。以下09-12复核及09-10回填保留各自时点事实。

**全项目复核（2026-09-12）：尚未达到真实工具全链部署验收条件，继续当前部署包内修复。** 本次全仓为 **1730通过/1失败/1跳过**；失败是检查器误检封存文档快照产生180条断链，不能沿用历史全绿口径。21份专家原件与457份当前一期Mock冻结资产只读核验通过，旧离线候选完整性通过但未含当前修复。新增确认 NetworkPolicy 回读比较、结构worker目录挂载、A3D仍走Windows Docker、新生成器与旧校验器不兼容等工程缺陷；目标结果profile、预测模型与完整自动设计/交付仍未闭合。解决方案、逐节点差距及证据见[部署就绪复核](PHASE1_DELIVERY_PLAN.md#全项目部署就绪复核2026-09-12)。下一项是在本包关闭工程缺陷并重建新候选，从一个CPU工具完成目标实跑到报告；现场资源落实与定点科学确认并行，不重新运行或开放原24条淘汰候选。本轮未连接集群、未修改实现、未改专家/冻结资产，生产仍NOT_DEPLOYED。

**最新现场进度（2026-09-10）：** 用户已返回第一轮只读查询，详见[目标环境盘点](PHASE1_DELIVERY_PLAN.md#目标环境只读盘点2026-09-10)。him-ws 中可创建主要部署资源与管理 Job，但不能创建 Role/RoleBinding；专用服务账号授权待管理员协助。现有应用运行正常，正式名称已确认，见[项目命名决定](DECISIONS.md#项目命名)；新项目仓库尚未建立。下一步取得仓库实际地址、准备实际最小授权与现场配置，再构建含修复的新候选；不重复要求已返回的查询，不将原离线包视作已含新修复。以下实施回填保留各批次当时的验证事实。

服务器部署与真实运行验收：进行部署前缺陷修复与 Kubernetes 执行闭环；目标集群尚未验证。用户亲自操作服务器，助手逐步指导；AF3/ESMFold2 同事部署任务取消，模型部署和项目接入目标保留。本地发布候选已完成，4份验收索引文件及离线ZIP大小/hash管理复核一致；候选资产保持只读。

**实施范围校准（2026-09-10，依据用户部署前复核）：** 本地发布候选为已完成历史基线，不再作为当前实施包。当前统一修复停止归属、发布目录安全、网络/期限/工具模板、服务容量/权限/输入校验，并接通 Kubernetes Job 生命周期；不再拆出准备阶段。候选原件保持只读，目标仍`NOT_DEPLOYED`。本机当前没有 Kubernetes context；CNI禁网、卷调度和真实工具到报告闭环待现场验证，科学签收不能由单测替代。

**实施回填（2026-09-10）：部署前缺陷已完成本地修复，Kubernetes闭环继续实施。** 全仓回归1730通过/1跳过；末次加强Job终态确认后，最终专项48通过（新增一项回归），Linux隔离容器真实停止探针通过。13份源码/测试快照逐字节一致，原候选40份索引文件只读复核通过。新证据见[修复索引](../../discovery/t01-phase1-real/deployment-hardening-20260910/fix-r01/index.json)；全仓批次在末次加强前已加载，最终专项覆盖其变更，不把两者写成一次最终全仓运行。当前仅接通目标Job生命周期和原始诊断回连，独立目标结果profile、真实CNI隔离/存储/取消恢复仍未完成；未重建发布镜像、未应用集群。下一动作由用户按[运行手册](../development/RUNBOOK.md#按变更选择验证)返回服务器只读预检结果，本包内继续工程；原24条淘汰、科学Gate和Agent C不变。

**目标资源估算（2026-09-10）：** 用户确认项目可使用 1 张 A100、可用显存 64 GB。首轮按串行 GPU 任务规划 32 vCPU、192 GiB 内存和 2 TiB 持久存储；控制面 2 vCPU/8 GiB，AF3 16 vCPU/160 GiB/1 GPU，ESMFold2 8 vCPU/64 GiB/1 GPU。该数值用于生成候选配置，不代表集群已授予配额；GPU 分配方式、资源名、存储和最大输入长度仍在目标预检及实跑后冻结。

**实施回填（2026-09-10）：本地 Linux / Kubernetes 发布候选已完成，目标未验证。** 服务r02基线以大小/hash固定；Linux/amd64控制面镜像、离线tar/ZIP、17份wheel、SPDX SBOM、源码/文件索引和安装/升级/回滚/备份说明已生成。Windows冻结运行源码保持原字节，Linux以独立POSIX入口完成进程组停止、PID出生标记、文件锁/原子发布及重启接续；容器内真实超时得到`TIMEOUT`且确认进程树停止。Kubernetes输出含Namespace、ServiceAccount、Secret、ConfigMap、2 TiB PVC、最小RBAC、单副本Recreate Deployment、Service和10份仅生成未提交的科学Job模板；现场配置表预填1张A100/64 GiB与32 CPU/192 GiB估算。隔离Linux容器已实测认证、上传/越界拒绝、提交/查询、取消/恢复/重试、幂等/越权、报告递归hash、无资产`ASSET_MISSING`、升级/回滚和新卷备份恢复；最终rc1中断重启观察`recovered=1`。机器收据见[验收r01](../../discovery/t01-phase1-real/target-linux-kubernetes-20260910/acceptance-r01/index.json)，操作入口见[运行手册](../development/RUNBOOK.md#本地-linux--kubernetes-发布候选检查)。未连接服务器、未应用Kubernetes、未推Harbor；目标仍`NOT_DEPLOYED`，科学Gate/可消费资格及原24条排除不变。

**管理复核（2026-09-10）：** 真实服务 r02 的36份索引文件已逐份复核大小与SHA-256，全部一致；独立审计和测试汇总状态均为PASS。r02、独立审计与测试汇总固定为下一包输入，r01仅保留未完成历史，不作为有效部署基线。下一包范围与完成标准见当前任务入口；目标现场证据、科学Gate和正式发布继续分别判断。

**实施回填（2026-09-10）：真实服务接口与 Dify 局部联调已完成。** REST 与 Streamable HTTP MCP 共用认证服务，复用原 Runtime/SQLite/Artifact 状态，支持受控结构上传、提交、流程/节点查询、取消、恢复、重试和报告下载；调用者隔离、幂等、断线继续执行、服务重启接续、配置漂移失败关闭均已实测。独立真实 Dify provider 认证枚举8个工具，9节点/9边应用完成导入回读；一次新任务成功取得20,154字节报告，一次失败任务准确返回`PROFILE_NOT_APPROVED`。最终r02含36份索引文件、9个服务案例、2次Dify运行；独立审计核对14份快照、6个任务、4层ZIP/28个成员及0条凭据泄漏命中。当前根1690通过/1项既有跳过，专项7通过，457份Mock冻结资产只读通过。r01保留启动登记竞态的未完成事实。详细见[总计划实施回填](PHASE1_DELIVERY_PLAN.md#真实服务接口与-dify-实施回填)。验收后开发服务已停止；科学Gate、原24条淘汰、正式候选、Agent C、目标Linux与生产发布不变，下一包由管理任务据实安排。

**管理复核（2026-09-10）：** 本地真实流程集成r02的610份索引文件大小与hash全部一致；归档测试汇总为当前根1683通过/1跳过、专项85通过，本轮未重跑工具或根测试。该包本机工程完成，下一包范围与完成标准见当前任务入口；科学消费与生产仍关闭。

**实施回填（2026-09-10）：本地真实流程集成已完成。** 一次提交由后端自动调度并绑定同源子任务，统一查询/取消/超时/中断恢复/幂等与本地ZIP导出可用。最终r02新执行结构、DeepTMHMM、BepiPred及N06/N07到N18报告链；缺库、缺allele及上游失败保留明确状态，原24条历史回连仍全淘汰。r02的610份文件、329项发布产物、26个父/子任务通过独立hash及嵌套ZIP校验；r01另行保留。接口、证据及测试见[总计划实施回填](PHASE1_DELIVERY_PLAN.md#本地真实流程接口与实施回填)。该包交付时HTTP/MCP与Dify尚未实施，现行状态见上方服务包回填；未开放科学Gate、正式候选或Agent C，本包不代表一期完成。

**管理安排（2026-09-10）：** N17/N18 主批与四批补充/最终导出共629份索引文件大小与hash复核一致。下一包完成一次本地提交、后端依赖调度、统一查询/停止恢复与报告导出，复用已验收工具；详细范围和完成标准见上方任务入口。科学 Gate 不放宽，不自动恢复原24条候选。服务器部署和科学裁决继续按原责任跟进；W7盘点误列的MD已依据一期范围纠正。

**实施回填（2026-09-10）：N17 WT 参考回连与 N18 本地工程交付组装已完成。** 稳定性扫描绑定正确 WT/结构/范围，分别保留 FoldX 40条与 ThermoMPNN 140条有效记录；原76aa批次24条仍全淘汰，无最佳候选。统一查询可获取机器报告、可读摘要和带hash清单的本地ZIP；独立N16片段不冒充WT/候选DNA，不自动交接。主批333份文件/197项发布产物，最终当前代码导出41份文件/18项发布产物及补充场景均独立核验。接口、证据与[全项目剩余工程/外部依赖盘点](phase1/PHASE1_REAL_W7_PLAN.md#全项目剩余工程与外部依赖盘点)已回填；下一轮安排见本页当前任务入口。末端组装不等于完整科学N17/N18/W7或一期完成，生产仍NOT_DEPLOYED。N16 r01的197份文件管理复核结论保留。

**实施回填（2026-09-09）：N16 条件密码子优化工程已完成。** 明确 E.coli/W3110 本地表 profile，固定 DNA Chisel/Biopython 及依赖 hash；真实反向翻译、优化、独立翻译/GC/限制位点校验与统一任务查询、取消/超时、恢复/重试已实现。主批197份文件、113项发布产物独立核验一致；包括真实 GC 修复及不可满足约束回退。完整接口、支持范围与验证见 [W7 N16 回填](phase1/PHASE1_REAL_W7_PLAN.md#n16-本机接口与实施回填)。CAI、其他宿主和生产参数未签收，完整科学 N16/W7 与正式交付仍关闭；原24条淘汰结果保持，后续包由管理任务安排。N13 主批1086份、补充241份文件的管理复核结论保留。

**实施回填（2026-09-09）：N13 表位保护工程与报告回连包已完成。** 统一入口已实现 WT/变体来源配对、四层明确工程观察与缺项、N14/N15报告回连；两侧真实 BepiPred/N06 确认热点未生成，FoldX变体结构按未知来源/低质量隔离，不授予RSA或保护资格。原24条淘汰及其原因保持。主批次1086份文件、992项发布产物独立核验通过；补充241份文件、228项发布产物核验通过。接口、证据及具体科学缺项见 [W6 N13接口](phase1/PHASE1_REAL_W6_PLAN.md#n13-表位保护本机接口)；完整科学保护、科学排序与正式交付未开放，后续包由管理任务安排。N14/N15 r03的554份文件管理复核结论保留。

**实施回填（2026-09-09）：N14 稳定性回连与 N15 筛选排序工程包已完成。** 统一入口可提交并查询逐变体来源、筛选与复核报告；真实 24 条保留原 R-35 排除，输出 `ALL_EXCLUDED`，最佳候选与正式排名为 null。另一 WT/结构批次的 FoldX 三条工程突变完成五次结果回连、31 份修复/突变/WT PDB 语义核验，不嫁接到原24条。详细接口与新验收见 [W6 报告接口](phase1/PHASE1_REAL_W6_PLAN.md#n14n15-逐变体报告本机接口)。N13、N10 缺项及科学签收未闭合，完整 N14/N15/W6 和正式交付仍关闭；后续包由管理任务按现行计划安排。

**管理安排：W6 FoldX / ThermoMPNN 稳定性工具工程包已完成。** ThermoMPNN 已完成真实单体预测与完整 SSM 核验；FoldX 已恢复 Docker/WSL、固定内容镜像，并真实完成 RepairPDB、PositionScan 和每变体 5 次 BuildModel。两者统一任务、查询、取消/超时、恢复/重试和产物追踪均经新批次验收。具体接口和逐引擎状态见 [W6 计划](phase1/PHASE1_REAL_W6_PLAN.md#稳定性工具本机接口)。不等待 AF3/ESMFold2；完整 N14/N17/W6、跨引擎科学筛选与发布仍未放行。

**实施回填（2026-09-09）：FoldX 真实工程接入完成。** 用户确认附件为其申请的学术版本；本地保留压缩包/ELF/伴随文件哈希，登记 `USER_ATTESTED_ACADEMIC_VERSION`，同时明确包内没有单独许可回执，不将声明写成机器证明。Docker Desktop Linux engine 29.5.3 / WSL2 已恢复，无缓存离线重建的固定镜像为 `sha256:66539e081922ce4c4fb504c9906feb64044ce668033e63fdc9299d020af8c851`。真实两位点 PositionScan 得到 42 行原生记录并严格归一为 40 个唯一 AA20 结果；三个明确变体（单/多突变）各完成 BuildModel 5 次，15 行原始差值与均值/std 复算一致。失败重试、取消、超时、两类恢复、来源/输出/发布篡改和统一查询通过；结果固定 `DEVELOPMENT_UNREVIEWED / usable_for_pipeline=false / NOT_DEPLOYED`。[最终索引](../../discovery/t01-phase1-real/w6/foldx-integration-20260909/acceptance-r05/index.json)与[独立复核](../../discovery/t01-phase1-real/w6/foldx-validation-20260909/evidence-audit-r02.json)。

**实施回填（2026-09-08）：ThermoMPNN 单体稳定性工程接入完成。** 固定官方 commit、模型、依赖和 GPU 镜像，复核同根真实结构 ArtifactRef、序列、目标链、作者编号/iCode 与所有 hash；原样调用官方完整 SSM 入口，强制验证 AA20×L 覆盖、WT 自身零值及原始有符号 ΔΔG。9 aa 现有本地结构实得 180 行，显式排除 2、8 位后保留 140 行、133 个非 WT 突变仅作引擎内排名。取消/超时/失败重试/崩溃恢复、多链 R-39 不裁链跳过、来源与发布篡改隔离均通过。结果固定不可科研消费、不可自动交接、`NOT_DEPLOYED`；原 24 条 R-35 全排除结果不变。

**实施回填（2026-09-08）：N11 权限合成与 N12 mutation_burden 后端工程包已完成，管理复核 1037 份文件大小/hash 全部一致。** 真实上游身份/序列/hash 与资格校验、逐残基权限及原生掩码转换、六维负担和既有 N11/N12 回连、统一查询与生命周期均已验收；[本机接口与证据](phase1/PHASE1_REAL_W5_PLAN.md#权限与负担本机接口)已回填。r02 独立复核确认 1037 份文件、885 项发布产物大小/hash 一致。未决科学分支继续隔离，正式设计及 Agent C 关闭；本包未生成新候选，原 24 条在 R-35 20% 后全排除的记录不变。此前 ESM-IF1 r01 的 993 份文件管理复核结论保留。

**实施回填（2026-09-08）：N12 ESM-IF1 独立工程包已完成。** 固定官方模型/权重/环境，禁网完成同 WT 基线、真实 N11 工程序列打分、跨调用基线复用、相对公式和有限 R-35 复评，统一查询及生命周期通过；[W5 接口与验收](phase1/PHASE1_REAL_W5_PLAN.md#n12-本机调用与接口)记录命令与证据。r01 的 993 份文件、853 项发布产物独立复核一致。完整 N12/W5、结构复核、burden、科学权限/正式设计与 Agent C 继续关闭；后续包由管理任务据实安排。N11 r02 已获管理复核的 946 份文件及原完成口径保留。

**实施回填（2026-09-08）：W5 N11 独立工程包完成。** 官方 commit/权重与 GPU 镜像固定，真实 24 条生成、固定/受限位置、坐标与多链转换、原生张量/分数验证，以及取消/超时/恢复/重试、幂等和产物守卫均已实测。r02 的 946 份文件、773 项发布产物独立复核一致。科学权限合成、正式设计 Gate、正式候选、Agent C 与完整 N11/W5 仍未完成；N10 不因本包而改变部分完成口径。

**实施回填（2026-09-08）：W4「设计 Gate 与 WT 子路径」工程包已完成。** 统一入口已实现真实上游身份/序列/hash/资格校验、缺失/失败/未签收路由和可查询的本地 WT 草稿；[W4 接口与验收](phase1/PHASE1_REAL_W4_PLAN.md#gate-与-wt-草稿本机接口)记录具体成果。科学 Gate、正式 WT、Agent C 生产交接和完整 W4 仍未完成，不启用设计。用户确认服务器为 A100、AF3/ESMFold2 尚未部署；同事按已完善的 [服务器交接文档](phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md)从零部署，具体配额/资产和真实禁网执行待核验。

N10 保持部分完成：PROPKA GUI 公式曲线工程对标与 N03→N06 工程回连已完成；CamSol、序列聚集资产、A3D 空间语义和 PROPKA 平坦曲线权重/结构消费签收仍未闭合。overall 保持 null，正式 Gate 未评估。管理任务已复核 r14 的 343 份文件、r06 的 304 份文件大小/hash 全部一致；本包保留其原证据，未重开或回写。

阶段范围、交付包与完成标准：[W2 阶段计划表](phase1/PHASE1_REAL_W2_PLAN.md)、[W3 阶段计划表](phase1/PHASE1_REAL_W3_PLAN.md)。提前开发独立 N07 不代表 W2 已完成。

按 [最新用户澄清](DECISIONS.md)，N03 保留本地 BLAST，只移除 IEDB 检索。W2 为 BepiPred、NetMHC、BLAST 本地检索、表位地图与联调四个包；前次“删除整个 N03、保留 17 节点”的管理误解已纠正。

**W2 BepiPred 3.0 本机开发接入已完成。** 原包/依赖/权重已固定，统一入口打通序列提交→任务→禁网原包执行→双分数列解析/查询及产物追踪，生命周期与完整性验收通过。[一条调用命令与接口](phase1/PHASE1_REAL_W2_PLAN.md)。
DeepTMHMM 与本地结构链保持开发完成，共享运行层回归通过。**W2 NetMHC 本机开发接入已完成。** 两份用户提供的 DTU academic Linux x86_64 原包、包内版本/allele、固定禁网镜像和真实双通道输出均已核验；统一入口、解析、查询、部分/全部不可用、取消/超时/恢复/重试/幂等验收通过。明确 allele 的结果仍为开发未签收，OI-003 默认宿主面板、科学消费、目标复现和生产许可/部署均未完成。W1 预测结构链、科学签收与目标复现独立跟进，完整 W1 尚未完成。BepiPred 项目后处理保持 null/复核，未宣称 N04 科学验收或完整 W2 完成。
**W2 N03 BLAST 引擎工程接入及 N03→N06 工程回连已完成，整个 N03 包仍在进行。** NCBI BLAST+ 2.17.0 Linux amd64 固定镜像、本机工程 FASTA 建库、环境配置库根 + 登记 ID + manifest hash 绑定、禁网 `blastp`、原始/阈值合格 HSP、统一查询与生命周期/完整性守卫均已实测；N06 现复核真实 N03 任务/尝试/ArtifactRef、同序列、库 ID/manifest 和 hash，区分命中、无命中与上游不可用。工程库不代表目标库，普通命中不产生 IEDB 文献/E3/E4；服务器目标库核验和目标实跑仍按 OI-028 跟进。[一条调用命令与接口](phase1/PHASE1_REAL_W2_PLAN.md)。
**W3 N07 糖基化扫描本机开发接入已完成。** 统一入口可执行重叠 N-X-S/T 扫描、返回 1-based N 位点/数量/表达提示和可追溯原始 observation；0 位点为合法成功。热点状态严格区分未提供、上游不可用与已计算列表；20 aa 契约夹具与真实 N06 ArtifactRef 来源校验均已通过。当前 N06 热点因 OI-007/026 保持 null，任意跨度到 20 aa 的换算仍为 OI-029，因此不宣称热点科学全链或科学验收。[一条调用命令与接口](phase1/PHASE1_REAL_W3_PLAN.md)。
开发、科学消费、目标发布按 [现行计划](PHASE1_DELIVERY_PLAN.md)分别判断。
日常读本页和当前任务章节即可；详细规则、命令和证据按需查，不重读全部旧评审。

**W3 N08 本机工程接入已完成。** 固定 MMseqs2/MAFFT/BLAST 镜像禁网运行，以工程序列集验证一次全局 MSA 复用、疫苗株分离、cluster/注释回连、逐位熵/保守性及查询坐标、区域三档和生命周期。全同序列真实参考得到分数 1 与 1–120 位标准区段；未知分型、短段桥接、补充命中准入等按 OI-030 保持复核。19 个真实场景及来源/发布哈希守卫已通过；工程身份、不可科研消费与 `NOT_DEPLOYED` 保持。[本机调用与接口](phase1/PHASE1_REAL_W3_PLAN.md)。

**W3 N09 本机工程接入已完成。** 统一入口已接通工程注释包、12 类 feature/3 类关键词/5 类独立 motif、用户标注、Chain/parent 坐标处理与真实 DeepTMHMM 产物回连；结构链实测正常 RSA、缺失 RSA、RSA 出域及双链 Cys/界面几何。正式 core_map 保持 null，开发分量和明确三态规则不取得科学资格。[本机调用与接口](phase1/PHASE1_REAL_W3_PLAN.md)。

**W4 N10 基线部分工程接入已完成，整个 N10 仍在进行。** 统一入口已实现 Biopython 1.88 可表达性、真实结构/RSA 标签暴露、固定 digest 的 AGGRESCAN3D 0.9.11 结构路径、PROPKA 3.5.1 PDB/mmCIF 路径与 C24 相对 ΔG 后处理，并固定六维缺失/排除/汇总守卫。PROPKA 已按固定 VMD GUI 公式完成 41 点形状/符号/数值对标，最大差低于 0.01 kcal/mol；平坦曲线权重仍待算法裁决。结构型 A3D 的原生结果和工程空间簇因科学语义未签收保持不可靠；固定 A3D 镜像内没有序列 AGGRESCAN 资产，无结构备选仍缺官方资产/许可/命令；CamSol 参数与 Roseman 方向冲突未裁决。overall/null、N10/Gate/自动交接继续关闭。[接口与验收](phase1/PHASE1_REAL_W4_PLAN.md#n10-本机调用与接口)。

## 已完成与当前能力

| 交付 | 现有成果 | 距离可用交付还差什么 |
|---|---|---|
| 一期 Mock | M1–M4 按删除 IEDB 前的 18 节点范围完成并冻结，有 Dify 验收 | 仅为原范围工程参考，不代表修订后的真实链或科学验收 |
| 通用运行底座 | SQLite任务/幂等/事件/产物层及常驻进程执行已接通；测试服控制面和9个Worker运行，11项原生命令完成登记，r02局部分析链通过 | 其余目标工具实跑、目标生命周期代表案例、完整自动编排与生产容量/运维验收 |
| 真实服务 / 用户入口 | 本机认证REST/MCP、生命周期与Dify局部联调已实测；目标认证MCP提交/查询/重复提交/直接报告下载通过；RustFS存储实测与本地发布实现完成 | RustFS代码/环境发布、HiMat实际文件/异步状态/卡片及附件验收；生产边界和正式交付仍未放行，Dify历史入口不替代HiMat |
| DeepTMHMM | Academic 1.0原生输出与本地生命周期已验；目标线程适配后独立新任务13.32秒通过，r02拓扑通过 | 科学参考/输入域/契约签收、适用支持域及完整生产验收 |
| 本地结构分析链 | 输入/映射/S-09/条件FreeSASA/RSA与本地守卫已验；构建来源修复后r02目标结构链通过 | 映射/来源/缺原子/S-09/RSA的科学签收及适用目标边界；不将工程RSA改为科学批准 |
| AF3/ESMFold2 | ESMFold2在76残基工程支持域内的标准输出、统一任务、N01、显式N12同次运行、进程禁网、适用生命周期及统一单卡Worker回归已完成；393残基独立容量案例通过。AF3权重/数据库、195867文件独立复核、固定环境、本地CPU数据搜索、单张64GB五样本原生推理/审计及真实原件只读复放均完成；AF3标准适配器、pTM并列规则、统一任务/N01/S-09接入和第五命令登记已完成，r02–r05线上失败批次均保留 | AF3修复后独立r06尚未启动，需完成一条统一Worker真实成功任务及ArtifactRef/source binding/报告审计；ESMFold2长度扩展和Pod崩溃恢复后移，科学资格与双模型科学路由仍关闭 |
| BepiPred / W2 N04 | 固定CLI/五折模型/ESM-2与原始双列实测；线上104项资产核验和r02真实预测通过 | OI-026模型/分数消费与后处理签收、独立科学参考及适用许可；项目正式峰/热点仍未开放 |
| NetMHC / W2 N05 | 固定4.2e/4.3k原包、明确allele和本地生命周期已验，r02目标双通道预测通过 | OI-003宿主默认面板与映射、科学签收和适用生产许可；明确allele工程实跑不授予科研资格 |
| BLAST / W2 N03 | NCBI BLAST+ 2.17.0 固定 `amd64/linux` 镜像；工程 FASTA 真实建库，库根/ID/manifest/hash 绑定、禁网查询、原始及 70% identity/80% query coverage 合格 HSP、命中/未命中/不可用和生命周期已实测；真实工程产物已回连 N06 | OI-028 服务器既有目标库的适用性、名称/路径/来源/版本/许可/索引登记与目标实跑；科学消费和部署未完成 |
| 表位地图 / W2 N06 | N03/N04/N05精确来源、序列/hash、库身份与普通BLAST回连已本地实测；r02目标B/T结果汇总通过，未启用目标BLAST库 | OI-007/026的B峰/热点/权重、OI-028目标库与无IEDB科学语义、OI-029窗口；局部工程汇总不等于完整科学地图 |
| 糖基化 / W3 N07 | Biopython 1.88重叠sequon扫描、来源回连及本地生命周期已实测；r02目标扫描与N06工程回连通过 | OI-029非20aa热点窗口换算和科学签收；当前N06无可消费热点，N07不执行遮蔽判定 |
| 同源保守性 / W3 N08 | 本机工程序列集真实收集、MMseqs2 0.99 去冗余、MAFFT 单次全局比对及组内复用、保守性/坐标映射、明确区域规则、生命周期与数据/产物守卫已验证 | OI-030 对应科学消费；服务器批准的 N08 同源/补充库、大库适配及目标整链实跑、科学签收与部署未完成 |
| 功能域 / W3 N09 | 本机注释包真实查询、feature/关键词/motif、用户标注、坐标审计、真实拓扑/结构 ArtifactRef 回连、可用几何分量及本地生命周期通过 | 服务器真实注释库/大库适配与目标实跑；OI-006/031 置信度、合并/几何及 core_map 科学签收，科研消费与部署未完成 |
| 可开发性 / W4 N10 | S-36a、S-37 结构型 A3D、S-39、S-38 PROPKA 开发路径和 S-40 部分汇总已统一接入；真实 PDB/mmCIF、A3D 原生输出、相对 ΔG、GUI 41 点曲线对标、来源/产物 hash、生命周期与降级守卫通过 | OI-025 CamSol、OI-032 序列聚集资产/空间语义、OI-033 平坦权重及适用结构/科学签收；N10 未完成、无 overall、Gate 未评估 |
| W4 Gate / WT 草稿工程 | 独立 wt_draft Worker 绑定 N01–N10 已登记生产者，核验任务/尝试/请求/结果与原始产物 hash；真实 N10 部分与 N06 失败、N07 未执行遮蔽均明确披露；本地 JSON 草稿、统一查询与生命周期通过 | OI-013/014/021、适用真实输入科学签收；科学 Gate、正式 WT、Agent C 接口与完整 W4 未完成 |
| W5 N11 ProteinMPNN 独立工程 | 固定官方代码/权重与 GPU 环境禁网生成，真实结构身份/序列/hash 回连，逐位硬约束、原生坐标/全链样本/分数校验及统一生命周期通过 | OI-001/002/006/007/015 等适用科学权限/结构签收、其他目标路径、完整 N12 与目标复现；正式候选/Gate/自动交接未放行 |
| W5 N12 ESM-IF1 独立工程 | 固定模型/环境禁网打分，真实 N11→N12 回连、同 WT 基线一次计算与跨调用复用、全目标链 loss 均值、相对公式/R-35、查询及生命周期通过 | OI-008/015/022、完整结构复核、正式 burden、前 20 池/重算与科学签收、目标复现；完整 N12/W5 与正式 Gate 未放行 |
| W5 N11 权限 / N12 负担工程 | 真实上游逐位来源追踪、缺失/失败/未签收隔离、显式用户约束、原生固定/受限掩码转换、六维数值与空值、既有 N11/N12 回连及统一生命周期通过 | OI-001/002/006/007/008 等科学条件、完整结构复核与候选池；正式权限/负担/设计、Agent C 与完整 N11/N12/W5 未放行 |
| W6 ThermoMPNN / FoldX 稳定性工程 | ThermoMPNN 真实完整 SSM 与生命周期通过；FoldX 用户学术版固定镜像真实完成 RepairPDB、PositionScan、BuildModel 5 次，以及来源/原生输出/生命周期/产物核验 | 跨引擎科学共识、完整 N14/N17/W6、目标复现与部署仍未完成；两引擎工程结果均不可科研消费或自动交接 |
| W6 N14 回连 / N15 筛选排序工程 | 原 N11/N12/权限/负担递归校验、FoldX 精确变体与31份 PDB 回连、逐条工程淘汰/缺项、24条全淘汰报告、整批/单条查询；有依据的 Pareto/加权数值以独立夹具验证 | N13、变体重算、N10 缺项、科学权限/负担及 OI-009/010/011/022；不输出正式排名或候选，不开放完整 N14/N15/W6、Agent C 与正式交付 |
| W6 N13 表位保护工程 | 基准报告与两侧序列/结构/质量/RSA/N06/N09递归核验；L1同一性、L2均值差、L3明确Cα距离变化、L4完全匹配区间画像差及未决方法守卫；真实预测、缺失/失败/错链/生命周期与报告回连通过 | 局部RMSD叠合范围/最小点数/缺位策略、shape方法、非同一区间画像对齐、真实热点及科学签收仍未完成；没有真实阳性科学保护样本，不完成科学四层保护或正式交付 |
| N16–N18 / W7 | E.coli/W3110明确profile的独立密码子优化、WT扫描来源回连、本地报告/ZIP工程完成；r02目标N17/N18缺项汇总与直接下载通过 | 目标N16独立实跑及业务DNA绑定、N17新扫描、批准宿主/CAI、正式Candidate/WT/Failure与Agent C回执；不把缺项汇总成功记为全节点完成 |
| W2–W7整体 | 各节点已有程度不同的独立工程模块和局部链；测试服当前贯通分析及缺项报告 | 完整双模型/三类目标库/N10、科学权限、真实自动设计/重算/保护/排序及最终交接仍需完成；只移除IEDB检索 |

## 当前阻塞

| 缺项 | 主责 | 阻断范围 |
|---|---|---|
| B2 输入域、独立参考/训练重叠/指标与专用契约签收 | 算法验收 + 后端 | DeepTMHMM 科学消费；不整体阻止开发接入 |
| OI-015/023：映射接受域/构象/批准、来源/缺原子与非常规输入处置 | 算法 + 后端 | 对应结构或输入科学分支；不阻断序列级 B2 |
| OI-024/027：S-09 先行规则确认及 RSA 出域科学口径 | 算法负责人 | 对应质量/RSA 正常科学消费；先行方案与拒绝/复核守卫保留 |
| AF3修复后统一Worker真实r06验收尚未完成；ProteinMPNN、ESM-IF1、ThermoMPNN尚缺新统一镜像代表性回归；ESMFold2科学签收与扩展支持域未开放 | 主开发接入与回归；算法确认并列/科学路由 | 不阻断已完成的AF3本地适配器与原件核验或ESMFold2 76残基工程调用；阻断AF3线上工程验收、完整GPU资源回归、双模型完整W1及相应科学消费 |
| OI-026：BepiPred 原始分数消费、Top20% 与峰后处理口径 | 主开发归并事实 + 算法确认 | 相应后处理科学分支；不阻断原工具实跑和原始分数开发接入 |
| OI-003：MHC I/II 宿主面板、默认值与映射 | 算法 + 业务；主开发归并工具支持列表 | 相应宿主面板科学消费；不阻断原包实测与明确 allele 的开发验证 |
| OI-028：服务器既有数据库的 N03 适用性、名称/路径/索引与无 IEDB 时的证据消费边界 | 数据接口人提供服务器库信息；后端核验；算法裁决剩余科学语义 | N03→N06 工程回连已完成；本项只继续约束服务器真实目标库检索与相应科学消费 |
| OI-029：N06 热点到 R-25 20 aa 窗口的换算 | 算法确认 + N06/N07 后端 | 真实 N06 产物身份/哈希/序列绑定已完成；非 20 aa 换算仍阻断遮蔽科学消费与热点全链，不阻断独立 sequon 扫描 |
| OI-025：CamSol μ/σ 未生成，公开 Roseman 标度与 C44 H/P 方向冲突 | 后端归并 + 算法裁决 | 阻断 S-36、N10 完整 overall 和完整 N10；不阻断其他维度 |
| OI-032：结构型 AGGRESCAN3D 已固定并实跑；官方序列备选离线资产/许可/命令及 A3D 空间簇与非高风险分类语义未闭合 | 环境接口人 + 后端 + 算法 | 结构工程结果保持不可靠、无结构时聚集维度缺失；阻断完整 S-37/N10，非官方 Python 3 移植不替代 |
| OI-033：PROPKA 平坦曲线非负权重与结构消费签收 | 算法 + 结构映射签收；后端已完成 GUI 曲线对标 | GUI 形状/符号/数值工程对标已 PASS；剩余项阻断 S-38 科学消费和完整 N10 |
| OI-021：明显不适合设计与 WT 交接规则 | 产品 + 算法 + 后端 | 阻断设计 Gate/WT 放行；N10 部分结果不会触发 Gate |

N08 具体剩余条件见 [OI-030](OPEN_ITEMS.md#n08-同源保守性的具体待确认项oi-030)：服务器目标/补充库由数据接口人提供，后端完成大库适配和目标实跑；未知分型归组、跨标签去冗余、短段桥接、不可靠位点及区间分级由算法确认。只阻断对应科学分支/目标验收，不重开已完成工程链。

现有样本属于可追溯开发参考，暂无已签收的甲方测试集。B1/FreeSASA 映射仍未获科学批准；1UBQ G76 RSA 出域按错误复核，不截断。
B2 原包将 `*` 编成 `<unk>` 并退出 0 的事实保留，开发接入必须继续拒绝该输入/结果。
N09 剩余条件按 OI-006/031：服务器注释库由数据接口人提供，后端完成目标适配与实跑；科学负责人签收 TrEMBL/复用拓扑置信度、重叠冲突、几何计数及 core_map。只阻断对应科学消费与目标验收，不重开已完成工程接入。

具体来源与关闭证据只在 [开放项](OPEN_ITEMS.md)维护，不另开笼统准备问卷。

## 下一步

1. 使用独立批次`r06`完成修复后AF3统一Worker真实任务；核对prediction成功、resident退出确认、五个native sample、标准ArtifactRef/hash/source binding、AF3→N01回连、父任务N18及报告内外层完整性。
2. 对新统一镜像下的ProteinMPNN、ESM-IF1、ThermoMPNN各做一条代表性受影响回归，证明五个登记命令在同一张A100-SXM-64GB上全局串行且不会并发；历史独立科学工具验收不重跑。
3. AF3数据库、权重、固定环境、CPU本地数据搜索、原生推理产物及r02–r05失败Job/PVC/日志全部保留，不重新下载、解压、删除或复用；常驻长度扩展和Pod崩溃恢复继续后移。
4. 继续保持科学Gate `CLOSED`、`usable_for_pipeline=false`和生产`NOT_DEPLOYED`；AF3遗传/模板库不自动登记为N03/N08/N09业务库，HiMat、Agent C及正式科学交付按现行开放项推进。

## 当前验证

- 2026-09-20 AF3线上接入增量：service AF3 overlay r01/r02及统一Worker配置r07、代码r09均完成server-side dry-run和受保护apply；最新Deployment滚动成功，Worker日志通过唯一`NVIDIA A100-SXM-64GB`守卫并登记`af3`。真实统一工作流批次r02–r05的失败任务、原始resident收据和报告均保留，失败原因分别为旧service注册、spool遗漏、解释器路径和最小环境依赖；尚未形成修复后AF3成功任务。`tests/test_cluster_workflow_probe.py`、`tests/test_af3_standard.py`和`tests/test_unified_gpu_worker.py`共25项通过，仅有既有pytest缓存目录权限警告。

- 2026-09-20统一常驻单GPU Worker：服务器dry-run与三次受保护Recreate更新完成，最终Pod 10/10 Ready、0重启；64GB唯一设备启动守卫和四工具登记通过。ESMFold2 r03真实推理及父工作流成功，resident终态确认且GPU回到空闲；[r03验收快照](../../discovery/t01-phase1-real/unified-gpu-worker-20260920/r03/latest.json)已保存。统一Worker、resident、ESMFold2、GPU切换和AF3单卡相关选定回归通过；Windows上的Linux进程专项按标记跳过，不用本地跳过替代本次服务器真实执行。

- 2026-09-16本轮项目复核：当前根 **1873通过、15跳过、0失败**，2条既有解析字符串告警；本轮Windows结果不替代Linux进程专项。文档292份检查通过，29处历史断链单列；ESMFold2的23份资产大小/hash及r02报告ZIP大小/hash/CRC重新核验通过。首轮沙箱临时目录setup错误及重跑边界详见[复核依据](PHASE1_DELIVERY_PLAN.md#完成情况复核依据)。旧完整Mock/S07未重跑；以下测试数字均保留原批次时点。

- 2026-09-10 [本地 Linux/Kubernetes 候选验收r01](../../discovery/t01-phase1-real/target-linux-kubernetes-20260910/acceptance-r01/index.json)：离线Linux/amd64镜像、17份wheel、187项SPDX包记录、9项控制面资源和10份科学Job模板完成索引；认证、上传、取消、超时、恢复、幂等/越权、`ASSET_MISSING`、报告递归hash、升级/回滚及新卷备份恢复通过。当前根1707通过/1项既有跳过，457份Mock冻结资产只读通过；286份Markdown检查通过，29条历史问题仍单列。服务器未连接、清单未应用、Harbor未推送，目标保持`NOT_DEPLOYED`。

- 2026-09-10 [真实服务验收r02](../../discovery/t01-phase1-real/service-integration-20260910/acceptance-r02/index.json)：36份索引文件、9个服务案例、2次真实Dify运行；断线后的真实BepiPred执行、服务重启、幂等冲突、取消/恢复/重试、权限隔离和报告完整性均通过。[独立复核](../../discovery/t01-phase1-real/service-validation-20260910/evidence-audit-r01.json)核对14份快照、6个关联任务、4层ZIP/28个成员及0条凭据泄漏命中。当前根1690通过/1项既有跳过，服务专项7通过，457份Mock冻结资产只读通过；现行284份Markdown检查通过，29条历史问题仍单列。目标部署与科学消费未放行。

- 2026-09-09 [W6 FoldX 工程索引 r05](../../discovery/t01-phase1-real/w6/foldx-integration-20260909/acceptance-r05/index.json)：12 个任务场景、11 项请求/完整性守卫和 553 份索引文件；[独立复核](../../discovery/t01-phase1-real/w6/foldx-validation-20260909/evidence-audit-r02.json)确认全部大小/hash、456 项发布产物、无缓存固定镜像、实际隔离和原生数值一致。真实 RepairPDB 前置；两位点 PositionScan 42 个原生行归一为 40 个唯一 AA20 结果；三个单/多突变变体各 BuildModel 5 次，15 行 Dif 与 Average 均值/总体 std 复算一致。失败重试、取消、1 秒超时、两类崩溃恢复、来源/输出/发布篡改及 CLI 查询通过。r01–r03 分别保留镜像标签所有权、原生 `e/o` 组氨酸代码和 BuildModel 地址前缀问题的未完成事实；r04 虽通过功能验收，但镜像命中旧缓存层、缺现行 Dockerfile 声明的基镜像身份标签，故不作最终固定镜像批次。[最终测试摘要](../../discovery/t01-phase1-real/w6/foldx-validation-20260909/test-summary-r02.json)记录双引擎专项 36 项通过、当前根 1553 项通过及 1 项既有跳过，现行 199 份 Markdown 检查通过；29 条历史归档链接问题保持原状。结果仍不可科研消费，完整 N14/N17/W6 与部署未完成。

- 2026-09-08 [W6 ThermoMPNN 工程索引 r05](../../discovery/t01-phase1-real/w6/thermompnn-integration-20260908/acceptance-r05/index.json)：13 个任务场景、12 项守卫；[独立复核](../../discovery/t01-phase1-real/w6/thermompnn-validation-20260908/evidence-audit-r03.json)确认 452 份索引文件、347 项发布产物及 28 份源码/配置快照大小/hash 一致，执行/规则 profile 与现行实现一致。真实 9 aa 单体完整输出 180 行，显式范围减排除后 140 行、133 个非 WT 引擎内排名；真实失败重试、取消、超时、崩溃恢复、多链不裁链跳过、来源/发布篡改通过。24 项定向单测通过。本轮[完整当前根回归](../../discovery/t01-phase1-real/w6/thermompnn-validation-20260908/root-tests-r02.txt)为 **1541 通过、1 项既有跳过**；457 项 Mock 冻结资产[只读核验](../../discovery/t01-phase1-real/w6/thermompnn-validation-20260908/mock-freeze-verify-r01.txt)通过。r01–r03 为验收汇总断言修正前、r04 为补齐官方 README 所引 SVG 资产前的工程批次，保留原身份，不计现行完成。

本轮最终口径见上方 W6 r05：完整当前根 **1541 通过、1 项既有跳过**；199 份 Markdown 现行文档检查通过，29 条历史旧引用单列；457 项 Mock 冻结资产只读核验通过。未跨历史分区，旧完整 Mock/S07 未重跑。W5 的 1517 通过、1 项跳过保留其验证时点；W6 前轮中断/诊断记录不计作现行完成。

- 2026-09-08 [W5 权限与负担工程索引 r02](../../discovery/t01-phase1-real/w5/design-backend-integration-20260908/acceptance-r02/index.json)：24 个任务场景、7 项守卫；[独立复核](../../discovery/t01-phase1-real/w5/design-backend-validation-20260908/evidence-audit-r01.json)确认 1037 份文件、885 项发布产物、19 份源码/配置快照与现行 profile 一致，12 份工程结果和 7 组数值夹具复算一致。真实来源合成结果为 7 FIXED / 68 RESTRICTED / 1 显式 OPEN，官方 parser/featurizer 掩码核验通过；用户冲突阻断导出。原 N11/N12 归档只读复用，旧运行根的篡改负例仅在新副本按原归档恢复；本包新候选生成 0 次，原 R-35 全排除结果不变。正式权限/负担/设计、科学 Gate 和 Agent C 均未放行。r01 为最后两处来源/回连修正前的工程记录，保留原身份，最终验收以 r02 为准。

- 2026-09-08 [W5 N12 工程索引 r01](../../discovery/t01-phase1-real/w5/esm-if1-integration-20260908/acceptance-r01/index.json)：20 个任务场景、10 项守卫；[独立复核](../../discovery/t01-phase1-real/w5/esm-if1-validation-20260908/evidence-audit-r01.json)确认 993 份文件、853 项发布产物大小/hash 一致，28 份源码/配置快照与执行/规则 profile 一致。真实 N11 24 条序列逐条打分、WT 基线仅 1 次，合法跨调用复用不重算基线；多链 WT 同序列、来源/产物篡改、部分/全部失败、空输入、停止/恢复/重试及 CLI 通过。该批 24 条在 R-35 的 20% 后仍全排除，记录工程失败报告，不构成科研淘汰结论或完整验证通过。完整 N12/W5、结构复核、burden、科学 Gate 与 Agent C 均未放行。

- 2026-09-08 [W5 N11 工程索引 r02](../../discovery/t01-phase1-real/w5/proteinmpnn-integration-20260908/acceptance-r02/index.json)：25 个任务场景、12 项守卫、8 个真实结构上游，九次成功 ProteinMPNN 生成各 24 条，另一次全固定明确不生成。[独立复核](../../discovery/t01-phase1-real/w5/proteinmpnn-validation-20260908/evidence-audit-r01.json)确认 946 份文件、773 项发布产物大小/hash 一致，23 份源码/配置快照无差异，执行/规则 profile 与现行实现一致；重新解析全部成功 N11 结果。43 项 N11 单测通过；最终[完整根回归](../../discovery/t01-phase1-real/w5/proteinmpnn-validation-20260908/root-tests-r03.txt) **1376 通过、1 项既有跳过**，457 项 Mock 冻结资产只读核验通过。197 份 Markdown 现行文档检查通过，29 条历史原文旧引用继续单独报告；未跨历史分区，旧完整 Mock / S07 未重跑。r01 因验收取消幂等键重复而中止、保留未完成；r02 完成修复后验收。明确工程掩码不代替科学权限；完整 N11/W5、N10、科学 Gate、正式候选、Agent C 与目标部署均未放行。

- 2026-09-08 [W4 Gate / WT 草稿工程索引 r02](../../discovery/t01-phase1-real/w4/wt-draft-integration-20260908/acceptance-r02/index.json)：23 个案例、5 个真实上游任务、324 份索引前文件和 144 项发布产物校验；[独立复核](../../discovery/t01-phase1-real/w4/wt-draft-validation-20260908/evidence-audit-r01.json)确认全部大小/hash 一致、源码快照无差异、执行/规则 profile 与当前实现一致。实际运行无结构 N10 部分基线、缺少双路预测而失败的 N06、独立 N07；覆盖缺失/失败/排队/无结果取消/未签收输入、身份/序列/哈希拒绝、幂等、计算/输出故障、停止/恢复/重试及 CLI 查询。33 项 WT 单测通过；本次[完整根回归](../../discovery/t01-phase1-real/w4/wt-draft-validation-20260908/root-tests-r01.txt)为 **1333 通过、1 项既有跳过**，457 项 Mock 冻结资产只读核验通过。195 份现行 Markdown 检查与 51 项文档测试通过；29 条历史原文旧链接按既有状态保留。r01 因验收脚本误把 N06 全缺失输入预期为成功而中止，保留未完成身份；r02 按实际失败状态验证。草稿为独立本地工程身份，科学 Gate、N10 完整性、正式 WT、Agent C 交接和部署全部未放行。未跨历史分区，旧完整 Mock / S07 未重跑。

- 2026-09-08 [N10 部分工程验收索引](../../discovery/t01-phase1-real/w4/developability-integration-20260908/acceptance-r14/index.json)：13 个 N10 场景、5 个真实结构上游、343 份索引前文件和 265 项发布产物核验，验收 profile 与现行实现一致，并完整绑定固定 digest 的 AGGRESCAN3D 0.9.11 镜像/配置/原生输出，以及 PROPKA 源码、`propka.cfg`、依赖清单和固定 GUI 公式来源。三条实际曲线各 41 点逐点对标均 PASS，最大绝对差 `0.000781108382120976 kcal/mol`（容差 `0.01`）；平坦曲线权重保持未完成。覆盖无结构、PDB、经逐原子往返校验的 mmCIF→PDB 投影、低质量、RSA 出域、明确权重、计算/输出故障、取消、中断/恢复/重试、文档单命令及来源篡改；相同合成 PDB/mmCIF 的 A3D total score 均为 -2.2966，仅作开发执行一致性事实。30 项 N10 单测、436 项 N01–N10 受影响开发回归通过；195 份现行 Markdown 检查通过（29 条仅存于历史原文的旧链接），51 项文档测试通过。N10 完整性、overall、设计 Gate、科学消费和生产部署均为 false/空。r13 闭合目标链物理投影与标准 `END`；r14 新增 GUI 对标且保留相同守卫，现行证据为 r14。更早失败/前版批次继续保留。

- 2026-09-07 [N09 最终工程索引](../../discovery/t01-phase1-real/w3/domains-integration-20260907/acceptance-r04/index.json)：28 个场景（含真实 DeepTMHMM 与 4 个结构上游任务）、402 份索引前文件、262 项发布产物校验；大小/hash 及当前 profile 与快照独立复核一致。覆盖注释命中/无命中/多命中/unreviewed、motif/用户标注、parent 裁剪与 Chain 不重复偏移、真实拓扑回连、正常/缺失/出域 RSA、双链 Cys/界面、库/计算/输出失败、幂等、取消、中断恢复/重试、单命令和来源/数据库篡改。Cys 1–2 的 Cβ 距离 4.5 Å、界面位置 1–9 为合成几何工程参考。r01 因结构格式字段解析错误中止；r02 完成一轮验收；r03 新增同序列双链被既有映射不唯一守卫关闭；r04 用异序列第二链验证明确映射阳性，不放宽守卫。44 项 N09 测试通过（含新增受控计时超时/取消测试）；当前实现完整根回归 1267 通过、1 项既有跳过，最后新增测试单独通过，未冒称整根已运行 1268 项。457 项 Mock 冻结资产只读验证通过；现行文档检查通过，29 条既有历史链接问题保持，未跨历史分区、旧完整 Mock/S07 未重跑。工程结果不可科研消费或自动交接。

- 2026-09-07 [N08 最终工程验收索引](../../discovery/t01-phase1-real/w3/homology-integration-20260907/acceptance-r05/index.json)：19 个真实工程场景、516 份索引前文件、406 项发布产物校验；独立复核大小/hash 全部一致，当前执行 profile 与验收快照一致。现行文档检查通过（29 条既有历史链接问题），457 项 Mock 冻结资产只读验证通过；未跨历史分区，旧完整 Mock/S07 未重跑。包括真实全链、全同参考、区间查询、稀疏缺注释、独立分组、9 aa 原生拒绝、零收集、库缺失/manifest 不符、工具/输出失败、取消/超时、崩溃停止/收据恢复、重试、文档单命令和数据/发布篡改守卫。r01 临时目录 noexec 阻断 MMseqs 脚本、r02 标准区段断言未考虑短段复核、r03 未预期 9 aa 原生拒绝，均保留未完成；r04 已通过 18 场景，r05 在此基础上关闭未定义的 query_range class 并追加实测。工程数据不可科研消费，目标库未验收。新增 26 项测试；最后调整后 90 项针对性测试通过，完整根回归数字见下文。

- 2026-09-07 [N03 BLAST 引擎完成索引](../../discovery/t01-phase1-real/w2/blast-integration-20260907/acceptance-r03/index.json)：固定 NCBI BLAST+ 2.17.0 Linux amd64 镜像，真实 `makeblastdb` 构建 3 条工程蛋白的 v5 库并在禁网只读环境执行 `blastp`。18 个场景、368 份索引前文件、227 项发布产物校验覆盖命中、合法未命中、原始 HSP/阈值合格 HSP 分离、非法输入、库缺失、manifest 不符、索引损坏、工具/输出失败、重试、排队/运行取消、超时、崩溃恢复、幂等及产物篡改；索引独立复核无坏项。r01/r02 分别因官方镜像自带标签和 BLAST coverage 整数取整未纳入验收预期而在完成前停止，不计 PASS。工程结果 `usable_for_pipeline=false`、无 IEDB/E3/E4、目标库未验证，整个 N03 仍为 `IN_PROGRESS`。
- 2026-09-08 [N03→N06 工程回连及 N06 现行索引](../../discovery/t01-phase1-real/w2/epitope-map-integration-20260907/acceptance-r06/index.json)：24 个案例、304 份索引前文件和 161 项发布产物校验；固定 BLAST+ 2.17.0 在同一运行根真实建立命中/无命中工程库，N06 复核 N03 任务/尝试/ArtifactRef、同序列、库 ID/manifest 和 hash，并覆盖上游不可用、序列错配及 BLAST 来源篡改。普通 HSP 原样保留，但 IEDB/E3/E4/表位区/接触残基继续为空；同时真实运行 BepiPred/NetMHC，保持 102 个残基记录、644 个 MHC-I 命中、60 个有效 MHC-II 命中及 N06→N07 来源回连。10 项 N06 单测和包含 N03/N07 的 66 项直接回归通过。r05 因沙箱 Docker 管道权限在镜像检查阶段中止，不计 PASS；r04 是回连前的前版 PASS，r01–r03 既有未完成批次继续保留。结果仍为工程未签收、不可自动交接、`NOT_DEPLOYED`；服务器目标库未验收。
- 2026-09-07 最新管理复核：N08 r05 的 19 个案例、516 份文件大小与 SHA-256 一致，目标库未验收、不可科研消费；下一包安排为 N09。1224 项根回归与最终调整后的 90 项针对性测试分别保留验证时点，不宣称最终修改后重跑完整根回归。本次只读复核，不重跑科学工具。
- 2026-09-07 [N07 统一交付索引](../../discovery/t01-phase1-real/w3/glycosylation-integration-20260907/acceptance-r01/index.json)：16 个开发案例、139 份索引前文件；8,000 个 AA20 三肽穷举按独立谓词应命中 38 个且实得 38 个，另验证重叠/1-based 边界、合法空结果、≥3 表达提示、热点三状态/20 aa 计数、非法请求、幂等、取消、失败/恢复/重试及产物篡改检测。独立扫描和热点契约夹具身份分开，`hotspot_full_chain_validated=false`、`usable_for_pipeline=false`、`NOT_DEPLOYED`。计入本次 NetMHC 新增检查后，N07 加现有四工具共 299 项针对性测试通过。
- 2026-09-07 文档导航修复：W2/W3 独立阶段计划已建立，当前任务及阶段入口直接打开文件；扫描 193 份项目 Markdown，现行导航检查与 51 项文档回归通过。6 份历史原文中的 29 条旧引用路径单独报告，24 个现存目标已在 [历史入口](../../legacy/README.md)提供有效链接；未改写历史执行证据，未新增工具开发成果。
- 2026-09-07 [NetMHC 统一交付索引](../../discovery/t01-phase1-real/w2/netmhc-integration-20260907/acceptance-r03/index.json)：用户提供的 NetMHCpan 4.2e / NetMHCIIpan 4.3k Linux x86_64 academic archives 逐包 hash 核验并固化为固定断网镜像；真实样本产生 MHC-I 644 行和 MHC-II 88 行，分别完整解析 644 hits 与 60 个非 inverted hits（28 行 inverted 跳过）。12 个场景、251 份索引前文件、167 项发布产物校验覆盖包内 allele、原生展示名/Identity、1-based 坐标、双/单/零通道、损坏、失败、取消、超时、恢复、重试与幂等。r01/r02 是保留的未完成验收编排运行，不计 PASS；结果仍为本地开发未签收、不可科研消费、`NOT_DEPLOYED`。
- 2026-09-07 范围纠正：按用户图示恢复 N03 BLAST 和完整 18 节点，同步 W2 四包及现行入口，保留附图原字节，文档检查通过。457 项 Mock 冻结资产、21 份专家原件及 34 份交付快照于 09-06 已核验。本次仅改现行文档、保存用户附件，下列完整测试与真实执行数字沿用原交付证据。
- 2026-09-06 [BepiPred 统一交付索引](../../discovery/t01-phase1-real/w2/bepipred-integration-20260906/index.json)：104 项原包/权重/来源资产核验，17 个验收场景、14 次真实禁网容器执行、297 项发布产物核验；另有 3 次原包实测及文档单命令实跑。包内示例、9 aa/1022 aa 工程边界、异常与故障注入分别记证据，不作为独立科学准确率验收。
- 原包 `*` 输入退出 1；8 aa 输入退出 0 但平滑数组有 9 位，项目准入及后置等长校验均阻止消费。原始概率/平滑两列和三份原包分类 FASTA 保留，项目 linear_scores/peaks/map 仍为 null/需复核。监督进程中断、显式重试、缺失分数文件、损坏输出和损坏收据按预期隔离；一次验收客户端中断的原执行与诊断未覆盖。
- 共享运行层的 [结构链回归](../../discovery/t01-phase1-real/w1/bepipred-shared-regression-20260906/structure/index.json)完成 32 场景、29 次禁网执行、825 项产物核验；[DeepTMHMM 回归](../../discovery/t01-phase1-real/w1/bepipred-shared-regression-20260906/deeptmhmm/index.json)完成 13 场景、10 次禁网执行、207 项产物核验。前次 W1 交付与原始科学守卫保持。
- N09 时点根回归为 **1267 通过、1 项既有 Windows 符号链接权限跳过**（[N09 根回归](../../discovery/t01-phase1-real/w3/domains-validation-20260907/root-tests-r01.txt)）；随后仅追加验收案例与一项计时/取消测试，[44 项 N09 测试](../../discovery/t01-phase1-real/w3/domains-validation-20260907/n09-tests-r02.txt)通过。N08 前批根回归为 1224 通过、1 项跳过（[N08 根回归日志](../../discovery/t01-phase1-real/w3/homology-assets-20260907/root-tests-r01.txt)）；最后两处 N08 守卫调整后另有 [90 项针对性回归](../../discovery/t01-phase1-real/w3/homology-assets-20260907/targeted-tests-r02.txt)通过；前次 BepiPred 完整测试日志仍见[原批次日志](../../discovery/t01-phase1-real/w2/bepipred-integration-20260906/root-tests.txt)，不同批次不互相冒充冻结证据。使用 `-X utf8`，现行文档检查另行通过。
- [2110 项受保护文件](../../discovery/t01-phase1-real/w2/bepipred-integration-20260906/protected-after.json)逐项 hash 不变，覆盖前次结构链交付、原运行底座及 W1 Schema；当前实现另有源码快照。未跨旧分区改动，旧完整 Mock 与 S07 未重跑，不并入当前测试数字。
- 逐工具运行事实见 [按主题证据索引](phase1/README.md)。完整历次数字保留在 [整理前记录](STATUS_HISTORY_20260906.md)，不作为日常阅读内容。

## 当前停止线

未签收开发结果保持不可科研消费、禁止自动交接；无部署证据保持 NOT_DEPLOYED。
修订后一期保留范围、离线边界及适用 G0–G6 发布要求继续适用；冻结 Mock、专家原件和原始证据不回写。
