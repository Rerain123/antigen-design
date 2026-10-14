# W1-09A 通用运行层实现说明

本任务提供本地开发可用的任务运行层：保存任务、避免重复提交、执行受控进程、查询与停止任务、重启对账，
并校验输入输出文件。当前进度见 [STATUS](../STATUS.md)，实施范围来自 [W1-09A 任务包](PHASE1_REAL_W1_RUNTIME_BACKLOG.md)。
源码位于 [t01_phase1_real](../../../src/t01_phase1_real)，本轮只启用无科学意义的 engineering_probe。

## 可以怎么用

使用项目现有 Python 环境，在项目根打开 PowerShell：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/w1_runtime.py --root D:/work/蛋白智能体/.tmp/w1-my-runtime demo
```

这条命令创建 run、登记输入、提交并执行一个工程任务，返回任务 JSON。返回的 job_id 可用于后续
get、cancel、recover、wait；显式 retry 会建立关联到原任务的新 job。详细命令见
[运行手册](../../development/RUNBOOK.md#w1-09a-本地通用运行层)。
CLI 退出 0 表示请求被正确处理；任务是否成功必须读 state。请求被拒绝时退出 20，返回固定错误 envelope。
本地存储或进程操作异常退出 21。wait 最多等待 15 秒，未终止时返回实际活动状态，不伪造完成。

## 实现与约定

| 部分 | 实现行为 |
|---|---|
| 持久化 | 本地 SQLite，WAL、FULL 同步、版本 1 migration；run/job/event/artifact/idempotency/execution 事务存储 |
| 身份与幂等 | 服务签发 run/job/attempt/artifact；调用范围、操作、key 构成索引，同 key 同 UTF-8 字节返回原对象，改字节拒绝 |
| 调用范围 | Python scope 由可信调用层提供，CLI 固定 local-owner；该版本是本地操作者接口，没有 HTTP/MCP 登录认证服务 |
| 输入 | ArtifactRef 由运行层登记；提交前及启动前复核所属 run、字节数和 SHA-256，保存原始提交字节与独立 attempt 输入 |
| Worker | 唯一允许 t01.real.engineering_probe；固定命令、源码/入口/Schema/Python 指纹，输入不接受 shell、任意命令、模型或脚本路径 |
| 资源 | Windows Job Object：最多 4 个进程、256 MiB 作业内存、2 秒 Worker 墙钟限时；这些是工程夹具限额，不是科学工具配置 |
| 停止 | 先提交 stop_reason，再终止整个所属进程组，确认 active=0 才写 cancelled/timed_out；取消与成功在事务内排序，终态不可改 |
| 恢复 | 调度器与 supervisor 分离；PID 加进程创建时间识别执行，recover 增加 lease_epoch；保留同一个 attempt，拒绝旧 epoch 回调 |
| 发布 | 同目录临时文件写入、flush/fsync 后原子重命名，拒绝覆盖；收集时核验 receipt、退出码、身份、大小和 hash，再登记结果 |
| 错误与重试 | 非零退出、缺失/损坏/错身份输出分别记录失败；仅确认失败、取消、超时后允许显式 retry，新 job/attempt 保留原输入与 profile |

运行根必须是独立本地目录。专家、源码、测试、文档、证据、冻结 Mock、legacy 和独立部署项目路径禁止作为运行根。
路径穿越、绝对路径注入、ADS、符号链接、junction、硬链接及跨 run 引用均拒绝；读取使用禁止并发改写/删除的文件句柄。
文件系统和 SQLite 由可信本地操作者管理；scope 和路径检查不等于对同一 OS 账户恶意改写数据库的隔离，后续服务须接认证与目录 ACL。
Job Object 用于生命周期和资源管理，不是网络沙箱；工程 Worker 源码没有网络操作，科学工具仍需要自己的禁网执行环境。

## 崩溃窗口如何处理

| 中断位置 | 对账结果 |
|---|---|
| 提交事务未提交 | 任务和幂等索引一起回滚；可能留下未登记的不可消费临时/快照文件，首版不自动清理 |
| 已认领，尚未登记启动意图 | 对账事务封住旧认领，确认没有启动，记录 INTERRUPTED；原调度器随后不能继续启动 |
| 已登记启动意图，尚无 supervisor 回执 | 无法确认是否启动，保持 reconciling；禁止自动 retry 或第二次启动，不能按等待时长推断停止 |
| supervisor 已登记且存活 | 重新关联同一执行身份；supervisor 继续处理持久化的取消/超时意图 |
| supervisor 崩溃 | Job Object 的最后句柄关闭会终止其所属进程；对账须再检查进程组，确认结束后才记录中断或收集已写回执 |
| 输出和 receipt 已写，终态未提交 | 核验身份/hash/真实退出记录，事务内发布；已有停止意图时保持取消/超时，不改成成功 |

未确认的启动窗口可能需要本地执行环境人工对账。当前没有“强制成功”或“忽略进程重试”入口。
已经确认的终态可重复查询和重复提交原请求，不会重新执行。代码/profile 改动后旧输入只能在匹配档案下运行或建立明确的新请求。

这里细化 W1-07 的工程实现方式，不增加公开状态或改变 Schema。此前
[设计评审](PHASE1_REAL_W1_CONTRACT_REVIEW.json)及 acceptance.json 的 DECLARED_NOT_RUN 保留当时事实，
实际执行以本轮独立证据为准。Windows 进程管理依据
[Microsoft Job Objects 文档](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)。

## 验证证据与适用边界

[工程证据批次](../../../discovery/t01-phase1-real/w1/runtime-engineering-20260905/README.md)包含 CLI 原始命令与输出、
job/event/execution、输入输出和 receipt、环境、源码清单、JUnit 实测及 RT01–RT15 对应关系。
[本轮维护验证](PHASE1_REAL_W1_RUNTIME_VERIFICATION.json)分别记录当前根回归、文档、契约和只读冻结校验。
测试直接运行无害进程及其子进程，覆盖并发提交/认领、真实进程中断、停止竞争、epoch、未知执行、文件篡改和生产调用拒绝。

本轮资格仅为 Windows 本地开发工程运行层。Linux/远程服务器 Worker、科学适配器、网络传输、Dify 真实编排和全 W1 发布仍按各自任务验收。
所有工程结果都为 ENGINEERING_FIXTURE、scientific_disposition=not_evaluated、usable_for_pipeline=false。

用户已[确认服务器容量可满足 AF3/ESMFold2](../sources/PHASE1_W1_SERVER_CAPACITY_20260905.json)，开发继续在本机。
该决定使模型后续运行位置有了明确方向；具体 OS/GPU/驱动/存储、访问方式、模型和本地 MSA 资产仍需登记与实际验证。
没有把“容量满足”写成“权重已安装”或“科学工具已部署”。
