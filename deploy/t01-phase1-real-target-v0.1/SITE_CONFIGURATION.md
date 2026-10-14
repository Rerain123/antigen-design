# T-01 现场配置表

本表只用于同事可参与后的目标环境采集。本地发布候选不填写、不推测这些值；任何 `REPLACE_AT_SITE` 存在时均不得部署。

| 类别 | 字段 | 现场值 | 验证证据 |
|---|---|---|---|
| Kubernetes | 版本、集群名、namespace | 待填 | `kubectl version` 与 namespace UID |
| GPU | 型号、数量、驱动、device plugin、扩展资源键 | 待填 | 节点 capacity/allocatable 与最小 GPU Job |
| 存储 | StorageClass、RWO/RWX、容量、快照能力 | 待填 | PVC/PV 绑定和快照恢复记录 |
| Harbor | 地址、项目、CA、拉取 Secret、保留策略 | 待填 | 镜像 push/pull 与 manifest digest |
| 域名 | FQDN、IngressClass、TLS Secret、证书责任人 | 待填 | DNS、TLS 链及 `/healthz` |
| 备份 | 对象存储或快照目标、加密、保留期、RPO/RTO | 待填 | 一次备份与异卷恢复 |
| 科学资产 | 各工具 PVC、只读挂载、资产 manifest/hash | 待填 | 逐工具预检收据 |
| 权限 | 部署人、运维人、ServiceAccount、审计保留 | 待填 | `auth can-i` 最小权限检查 |

填写后应另生成现场渲染件；不得直接修改本地候选的哈希索引。
