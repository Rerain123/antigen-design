# T-01 项目交接入口

交接日期：2026-10-14。接收仓库为 [Codeup antigen-design](https://codeup.aliyun.com/6549a8ea3aaed849b035cf92/agent/antigen-design)，交接分支为 `main`。本页说明接手方式；功能状态、剩余工作和科学限制仍以 [STATUS](STATUS.md) 为唯一入口。

## 阅读顺序

1. [当前状态](STATUS.md)：先看最新部署摘要和统一 8 项进度，区分工程实现、真实运行和科学签收。
2. [工作约定](../../AGENTS.md)和[交付计划](PHASE1_DELIVERY_PLAN.md)：确认修改权限、执行范围及放行条件。
3. [专家原件索引](../../工作流设计/01-业务依据/README.md)：按实际问题读取适用版本，原件优先于派生说明。
4. [架构](ARCHITECTURE.md)、[开发运行手册](../development/RUNBOOK.md)和[文档导航](../README.md)：定位组件、检查命令及历史依据。

## 仓库资料

| 目录 | 接手用途 |
|---|---|
| `src/`、`tests/`、`scripts/`、`requirements/` | 当前实现、回归、运维和取证脚本、固定构建输入 |
| `工作流设计/` | 专家原件、版本化契约和编排设计 |
| `docs/` | 范围、计划、决定、开放项、架构、运行手册和历史导航 |
| `deploy/` | 构建定义、部署配置及各次发布/回滚证据；日期化补丁不是可直接重放的最新指令 |
| `dify/` | 编排资产、冻结清单和回归证据；本机凭据和实例绑定不公开 |
| `discovery/`、`reports/` | 已归档取证、原始结果包、来源索引和核验收据，保留原路径及原始字节 |
| `legacy/` | 旧完整 Mock、S07 与旧计划，保留身份，不并入当前一期运行 |

此次交接补齐此前未纳入 Git 的可入库资料。模型权重、离线镜像、大型数据库及本地运行状态保留在现有存储，以[外部资产清单](../../reports/handoff-20261014/external-assets.json)和[交接核验收据](../../reports/handoff-20261014/verification.json)说明实际范围。清单中的本机路径只是现有副本位置，不是同事可直接访问的下载地址；接收人需从原工作站或有权限的集群存储复制，并核对清单。

本地虚拟环境、下载/测试缓存、凭据和个人配置不入库。根目录 `工具部署/` 是独立项目，仅原样纳入旧文档引用的《已部署蛋白工具接口调用与测试手册》作为历史依赖，其余不并入 T-01；完整独立项目的现有位置列入资产清单。少量直接引用的 `var/` 资产元数据随仓库保留，模型和运行状态仍在外部。用户、专家原件和冻结资料不因整理而删除或修改。历史文档中的旧路径保留原时点说明，恢复入口见 [legacy](../../legacy/README.md)。

## 开发与核验

Windows Git 克隆时启用长路径支持；证据目录较深，建议使用较短的本地目录：

```powershell
git clone -c core.longpaths=true --branch main https://codeup.aliyun.com/6549a8ea3aaed849b035cf92/agent/antigen-design.git antigen-design
cd antigen-design
```

使用 Python 3.11。从仓库根创建独立虚拟环境，基础开发依赖可按仓库固定要求安装：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install 'jsonschema>=4.23,<5' 'PyYAML>=6.0,<7' pytest -r requirements/structure-mapping.txt -r requirements/developability.txt -r requirements/glycosylation.txt
```

控制面离线构建依赖已随仓库保留的固定 Linux wheel；科学模型环境是独立镜像/资产，不能用上述基础开发依赖代替。完整测试涉及的其他工具按[运行手册](../development/RUNBOOK.md)及相应环境清单准备。

Windows 本地已有环境时可执行以下只读核验；首次接手应先恢复具体证据测试依赖的外部资产，再运行对应科学工具测试。

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
.\.venv\Scripts\python.exe -X utf8 scripts/check_docs.py
.\.venv\Scripts\python.exe -X utf8 scripts/t01_phase1_mock/run_m4_campaign.py verify
.\.venv\Scripts\python.exe -X utf8 -m pytest -p no:cacheprovider -o addopts='' -q tests/test_docs.py
```

当前根完整回归命令和历史分区命令见[运行手册](../development/RUNBOOK.md)。Windows 上跳过的 Linux 进程/取消测试不能当作已通过。测试收据明确区分本次执行与历史结果；克隆仓库不等于模型、数据库和目标集群已经可用。

## 线上运行与发布

线上最后核验的源码、镜像、工作负载和报告交付以 [10-14 上线收据](../../reports/report-fix-20261014/deployment-r02/closeout.json)为准。架构为 1 个 API、8 个 CPU Worker 和 1 个常驻独占 GPU Worker；各工具的解释器和科学环境仍隔离。主要存储引用如下，均位于现有 `him-ws` 命名空间：

| 资源 | 用途 |
|---|---|
| `antigen-design-runtime` PVC | 任务库、运行目录、执行记录、结果及部分已登记数据库 |
| `antigen-design-assets` PVC | 固定原生工具包与模型资产 |
| `antigen-esmfold2-models` PVC | ESMFold2 / ESMC 模型 |
| `antigen-af3-models`、`antigen-af3-databases` PVC | AF3 模型和数据库 |
| `antigen-n03-nr` PVC | 已有 N03 数据挂载；实际启用数据包以业务配置和 manifest 为准 |
| RustFS `antigen-design` 桶 | 已核验报告附件，任务主记录仍在运行卷 |

`test` 是现有 Jenkins 自动发布通道；`main` 用于本次完整交接。公共流水线目前仅构建并更新 API 镜像，9 个 Worker 和十服务源码挂载仍需按现有发布过程同步并逐容器验证。不能把一次 Git 推送当作十服务完整发布。最新完整快照和回滚资料见 [report-facts/r02](../../deploy/report-facts/r02/templates.json)及[逐容器核验](../../reports/report-fix-20261014/deployment-r02/deployment-verification.json)。旧补丁带 UID/resourceVersion 守卫，部署前需重新读取目标状态，不能删除守卫强行套用。

接收人需取得 Codeup 仓库、现有 Jenkins/镜像仓库、`him-ws` 相关工作负载及 PVC、HiMat/MCP 和 RustFS 的适用权限。通过受控渠道交接 kubeconfig、服务令牌、签名密钥和对象存储凭据；仓库只保留 Secret 引用及配置字段，不存密钥值。集群命令使用项目本地 kubeconfig，不切换或依赖全局默认上下文。

## 接手边界

本次整理和上传不改变科学规则、冻结结论或线上运行，也不授权新的科学任务。N08 和 N18/Agent C 的边界、待校准参数及其他科学缺口继续按 STATUS、开放项及最新明确决定处理。运行成功、报告下载成功与完整科学验收是不同结论。
