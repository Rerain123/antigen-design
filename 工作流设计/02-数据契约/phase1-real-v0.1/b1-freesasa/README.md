# B1 → FreeSASA 开发消费者文件接口

本扩展消费 [B1 原始输入事实](../b1-engineering/README.md)，用于本机开发验证。
它不新增运行层 tool_id、生产 Worker 或科学资格，不能作为 N02 的已批准结果使用。
适用范围与证据见 [专项任务](../../../../docs/project/phase1/PHASE1_REAL_W1_B1_FREESASA_BACKLOG.md)。

## 输入及绑定

入口是 [prepare_b1_freesasa.py](../../../../scripts/prepare_b1_freesasa.py) 的 `run(bundle, output_dir, *, route, model_index, context_chain_ids)`。
bundle 必须含原始 request.json、input.structure、result.json、artifacts.json 和 preflight/raw_metadata/raw_addresses 三份 JSON。
先校验原 B1 Schema、ArtifactRef、请求/执行身份及原值出处，再重解析原结构；拒绝的 B1 预检不能进入工具。
新目录内 b1_input 保存上游完整原字节副本，旧事实及旧整数映射 Schema 不变。

consumer_selection.json 的三个必填字段为：

| 字段 | 类型及约束 |
|---|---|
| route | `pdb_file` 或 `native_atoms`；显式选定，不进行失败回退 |
| model_index | 从 0 开始的整数；必须与上游 B1 实际选择一致，原 MODEL serial 另存 |
| context_chain_ids | 非空、唯一的作者链字符串列表；链必须存在且含 B1 摄取链 |

binding 保留 b1_binding、b1_result_sha256、b1_structure_artifact、b1_fact_artifacts，
并绑定消费选择文件与既有 FreeSASA profile 的 SHA-256。工具进程在调用前重新核对这些字节及语义，
包括请求序列 hash、事实所属 attempt、原结构、宿主声明和未批准状态。
这些 ID 的身份范围始终是 `LOCAL_PROBE_NOT_RUNTIME_ISSUED`。

## 准备及工具产物

consumer_result.json 返回 `READY_FOR_TOOL_PROBE` 或 `REJECTED_BEFORE_TOOL`，有固定 error_code、错误详情、
准备文件 hash 和完整 binding。准备命令从不调用 FreeSASA；CLI 返回码依次为 0、1，文件/请求级异常为 20。
Python API 的空上下文也明确拒绝；CLI 本身要求至少一个 `--context-chain` 参数。

成功准备产生 preparation.json；仅 PDB 路径另产 prepared.pdb。逐原子记录包含：

| 字段组 | 责任 |
|---|---|
| raw_row_index / raw_residue_id / raw_address | 回连 B1 原始行和完整残基身份，包括 MODEL、label/auth 名称空间与缺失标记 |
| author_seq_id / insertion_code / chain_id | 作者 token 原样保存；不重编号、截短或建立链别名 |
| tool_residue_token / tool_atom_name | FreeSASA 实际接收的编号及四列原子名；编号为作者 token 加明确 iCode，合并碰撞提前拒绝 |
| coordinate_source / coordinate_tool | 原数值与实际传入坐标；PDB 三位小数精度显式记录，native 保留解析 double |
| element / element_evidence | 从原 CIF type_symbol 或 PDB element 列补读并保留出处；不得猜测缺失元素 |
| excluded_atoms | 每一被排除原子的原始行及原因；未选模型、显式上下文外链、水、H/D 分别记录 |

本开发支持域限标准蛋白重原子、明确 iCode、单字符链、无 altloc 且 occupancy=1 的上下文。
未知/缺失 iCode 不等同空串；字符作者编号可走 native，但仍须实际工具读回验证。
字符编号、前导零和超出定宽范围的编号在 PDB 路径明确拒绝。
非标准/非蛋白上下文、部分/零占有率和替代构象保留复核边界，不用修改输入绕过。
四列原子名按已声明单字母重元素形成，要求与原子名首字符相符；不支持的名称/元素组合拒绝。

工具结果按顺序保存 classifier.json、tool_atoms.json、verified_atoms.json、raw_areas.json 和 raw_residue_areas.json。
先核对 ProtOr 分类器半径，再核对实际原子数、身份、坐标和工具半径；面积按核实的工具原子索引回连完整原地址。
不使用 residueAreas 的简化键，不按数组位置 zip，也不借作者号推断输入序列位置。
tools 读回原始 token/原子名的空白填充也保留在 tool_atoms 中，语义核验另处理固定宽度填充。
未知 ProtOr 半径返回 `UNKNOWN_PROTOR_RADIUS`，可有分类器调用证据，但 `calculation_started=false`。

工具终态仅为 `SUCCESS_RAW_ONLY` 或 `REJECTED`。前者表示原始面积完成身份回连，
同时固定 `usable_for_pipeline=false`、`normal_rsa_result=null`、`buried_fraction=null`、
`scientific_approval=null`、`production_status=NOT_DEPLOYED`；mapping_status 为 NOT_EVALUATED。
raw_residue_areas 绑定上游、准备文件及原子面积文件 hash，整批 manifest 另绑定工具读回和日志。

## 运行边界

[独立容器入口](../../../../scripts/run_b1_freesasa_consumer.py)只执行既有固定 FreeSASA 2.2.1 镜像，
显式禁网、只读根文件系统与只读源码/输入，结果写入新的项目目录；不会拉取镜像或安装依赖。
精确命令和复核入口集中在 [运行手册](../../../../docs/development/RUNBOOK.md)。
科学映射、完整性比例、项目 RSA 和下游 S-09 等仍须各自适用的 G1；本接口不颁发这些资格。
