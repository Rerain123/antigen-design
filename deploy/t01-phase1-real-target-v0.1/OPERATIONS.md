# T-01 本地 Linux / Kubernetes 发布候选操作说明

## 边界

本包是 Linux x86_64 本地发布候选，不是目标服务器部署结果。`production_status` 固定为 `NOT_DEPLOYED`，Scientific Gate 固定为 `CLOSED`，产物不得用于科学消费。Kubernetes 文件仅生成和校验，构建与验收脚本没有集群提交入口。

## 离线安装

1. 在受控主机核对顶层 `index.json` 的每个文件大小与 SHA-256。
2. 以 `docker load --input images/t01-phase1-real-control.tar` 或现场批准的容器运行时导入镜像。
3. 核对导入后的本地 image ID 与 `metadata/image.json`，并保留导入日志。
4. 复制 `site-profile.template.yaml` 形成现场配置；填写 GPU、存储、Harbor、域名和资产 PVC 后进行严格预检。
5. 将所有镜像推入 Harbor，记录 Harbor 返回的 manifest digest，以其渲染 Deployment/Job；不得用 tag 代替 digest。
6. 将 Secret 占位内容替换为现场凭据，使用批准的 Secret 管理流程创建。证据包中只能保存脱敏件。
7. 按 Namespace、Secret/PVC/RBAC、Deployment、Service 顺序应用。科学 Job 模板在资产与 GPU 预检完成前不得提交。

## 升级与回滚

- 升级前停止新提交，等待活动任务终态或明确取消；校验备份；记录旧 Deployment 镜像 digest、PVC UID 和数据库哈希。
- 镜像只按 digest 替换，Deployment 保持单副本 `Recreate`，避免 SQLite/PVC 双写。升级后复核认证、查询、恢复、报告下载及旧任务可读性。
- 回滚时恢复上一已验收镜像 digest；若数据库格式发生不兼容变更，先恢复与旧镜像同批次的备份，不允许旧程序直接打开新格式副本。
- 本候选的本地演练使用同一持久卷在两个不可变候选镜像间升级和回滚，并验证既有报告哈希不变。

## 备份与恢复

- 先暂停提交和调度，确认没有写事务，再对整个 runtime PVC 做一致性快照或只读归档；不得只复制 SQLite 主文件而遗漏 `-wal`/`-shm` 或产物目录。
- 备份清单至少包含数据库、上传、任务产物、发布报告、文件大小和 SHA-256；Bearer Secret 单独由现场 Secret 系统备份。
- 恢复到新 PVC 后先执行哈希复核和只读查询，再启动单副本服务；用已有成功任务下载报告并比对原 SHA-256。

## 故障与安全

- 断线不取消已持久化任务。重启时服务从 SQLite 恢复非终态任务；Linux 子进程由进程组、PID 出生标记和资源限制管理。
- Linux 控制面不接 Docker socket。科学工具走 Kubernetes Job；镜像/资产缺失只阻断对应引擎并返回明确事实状态。
- Pod 使用非 root、只读根文件系统、丢弃 capabilities、RuntimeDefault seccomp；运行数据只写 PVC，临时数据只写受限 `emptyDir`。
- Role 不允许读取 Secret，不允许创建任意 Pod/Deployment，也没有 cluster-wide 权限。
