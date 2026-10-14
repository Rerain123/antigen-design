# NetMHC 接入批次

本目录保存 2026-09-07 的 W2 N05 接入事实。前序 `official/` 与 `preflight.json` 是原包到齐前的公开格式参考和阻塞事实；随后用户提供 NetMHCpan 4.2e 与 NetMHCIIpan 4.3k Linux x86_64 academic archives，并明确要求接入。原始压缩包、包内版本/allele/说明文件和镜像收据现固定在项目运行资产中。

[environment/build.json](environment/build.json)记录断网构建与镜像身份；[acceptance-r03/index.json](acceptance-r03/index.json) 是完成索引：校验两份原包 SHA-256、`amd64/linux` 固定镜像、断网/只读/资源约束、全长 FASTA 自动切片、1-based `Pos`、包内 allele 与原生展示名映射、Identity 截断、`%Rank_EL`、原生 `BindLevel`、MHC-II core/inverted，并完成统一任务生命周期。12 个场景覆盖正常双通道、单通道/解析部分失败、双通道不可用、整工具失败、非法 allele、幂等冲突、排队/运行中取消、超时、监督中断恢复及显式重试。

`acceptance-r01/` 与 `acceptance-r02/` 是验收脚本编排问题导致的未完成运行，均无完成 `index.json`；它们没有被覆盖或冒充通过。`official/` 仍只作为 DTU 公开页面/Web 服务参考，不代替 stand-alone package 或本地执行证据。

本批资格限定为 `LOCAL_DEVELOPMENT_ONLY`：显式 allele 原始预测仍为 `DEVELOPMENT_UNREVIEWED`、`usable_for_pipeline=false`、`NOT_DEPLOYED`。包内学术条款按用户提供的原件登记；不由本次接入推断商业、生产、宿主默认面板或科学签收权限。OI-003 继续约束默认宿主面板与科学消费。
