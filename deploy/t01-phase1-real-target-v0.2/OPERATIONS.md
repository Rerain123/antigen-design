# 目标 Linux 候选 0.2.0-rc3

此目录为新的本地候选。生产 NOT_DEPLOYED，scientific_gate CLOSED。
原0.1.0候选、专家原件和历史成果保持只读。

实际构建/运行验收以本目录metadata及项目当前交付包为准。
Kubernetes资源模板带占位值，不可直接应用；现场使用项目scripts/render_target_site.py输入实际配置，输出application.yaml及administrator.yaml。

包内已包含scripts/render_target_site.py及只依赖标准库/PyYAML的最小源码集；在安装了PyYAML的Python3.11环境运行。site-config.template.json只能复制到新的现场文件后填写，渲染器会拒绝其占位值。源码完整版本已在镜像内，metadata/source-index.json登记精确构建输入，后续项目状态文档变更不冒充已烘焙进镜像。

用户2026-09-12确认Harbor及专用SA尚未建立。管理员可审阅kubernetes/administrator-bootstrap-him-ws.yaml：在现有him-ws创建t01-control-plane服务账号并绑定命名空间内Job/Pod只读观察与Job创建/删除、NetworkPolicy读取权限，不含Secret读取或集群级权限。先建立antigen-design镜像仓库并返回实际地址，再推入已核验镜像、取得平台manifest digest和创建项目专用PVC/凭据引用。上述文件均未应用。
现有命名空间不重建/重标，不改动已有应用；认证Secret预先由操作者创建，工具镜像/资产独立准备。

本包增加配置/资产装配、结构worker挂载、独立A3D Job、版本化校验和目标结构结果验证。
目标结构/A3D结果需要固定的现场工程验收收据；其他通用工具结果profile尚未完成。
AF3/ESMFold2、完整自动设计/交付、科学规则与目标集群实跑仍是未完成项。

离线安装：先核验index与外层ZIP，docker image load导入images中的tar，核对metadata/image.json中的镜像身份；注册表推送后以实际平台manifest digest渲染现场清单。
升级/回滚：停止接受新任务，等待执行结束或按工具协议取消并确认Pod停止；一致备份运行卷和SQLite后替换Deployment digest。旧镜像与卷备份保留；回滚使用兼容的旧镜像及升级前卷快照，不能让两个版本同时写同一运行根。
所有阶段重新验证认证、持久化、幂等、取消/恢复、禁网与报告hash。需要现场权限/数据的检查不得用本地容器记录代替。

依赖清单由禁网容器内的dpkg-query和Python importlib.metadata采集为SPDX，覆盖已安装OS/Python包；未进行漏洞库或完整文件/许可证扫描，不能把125条安装包清单与旧Scout的187条发现结果作同口径比较。镜像构建显式传入RELEASE_VERSION=0.2.0-rc3，固定基础镜像及本地wheel，build network=none。
