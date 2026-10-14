# AlphaFold3 / ESMFold2 模型技术要求与接口

> 本页只维护模型边界及标准结果要求。当前执行见 [部署验收任务](PHASE1_REAL_TARGET_DEPLOY_PLAN.md)，现场事实见 [STATUS](../STATUS.md)。历次资源纠偏、下载、环境和批次回填见 [历史记录](../history/deployment/before-20260921/docs/project/phase1/AF3_ESMFOLD2_SERVER_HANDOFF.md)。

## 权威依据

科学要求来自 [结构链 ToolSpec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_结构预测获取链_v10.5.md)、专家 SOP/SKILL 及 [权威索引](../../../工作流设计/01-业务依据/README.md)。N01 离线与单卡范围按 [用户决定](../DECISIONS.md)执行。

## 执行与资产边界

- 统一 Worker 是唯一指定 A100 64GB 资源持有者，各固定环境的工具按全局 FIFO 串行；停止未确认不启动下一项，不需要 Kubernetes API/RBAC 动态切换。
- 控制面通过固定 registry/resident 命令提交；实际源码见 [AF3](../../../src/t01_phase1_real/development/af3)、[ESMFold2](../../../src/t01_phase1_real/development/esmfold2)、[统一 Worker](../../../src/t01_phase1_real/unified_gpu_worker.py)。旧交接中拟定的 run_structure.py 只是原接口提案，不作为当前现存 CLI。
- 环境、模型、数据库分别固定来源、版本与 hash，运行中禁止联网补取或外部结构查询。AF3 数据不自动成为 N03/N08/N09 业务库。
- 请求不得提供任意 shell/镜像/模型绝对路径；每次新 attempt、独立输出目录，原生结果与失败不覆盖。统一运行层负责幂等、停止与恢复。
- ESMFold2 常驻已验支持域仍为 76 aa；393 aa 独立容量案例不自动扩展生产上限。长序列及 Pod 崩溃恢复未覆盖部分继续明确标记。
- AF3 保留五样本及原生 ranking_score；单链按最高 pTM 选择，同分全保留并按最低 seed/sample 作确定性工程选择，不能声称科学优劣。
- r14 已完成 AF3 标准任务及 N01/S-09→N18 同 run 工程验收；其 mmCIF 未知插入码 `?` 保持原字节，映射与 FreeSASA 分支继续 `unverified / review_required`，不得由部署成功推导为 RSA 科学可用。

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


## 验收与调用入口

具体命令见 [RUNBOOK](../../development/RUNBOOK.md)及脚本帮助；AF3 部署顺序 1 的完成证据和后续边界在 [部署任务页](PHASE1_REAL_TARGET_DEPLOY_PLAN.md)维护。原有下载、解压、原生推理审计保留，不重新执行无关独立验收。

执行成功、结构质量、下游科学消费与正式发布分别判断。原生单链 ipTM=0 可保留，标准接口 null 加不适用原因；不据工程成功宣称科学合格。
