# PH1-MOCK-M3-01 目标 Dify、DSL、Provider 与导入能力预检

> 状态：`COMPLETED / PASS / ZERO_BLOCKER`  
> 取证日期：2026-09-04  
> 绑定档案：`local_dify_1_17`  
> 机器证据：[target-preflight.json](../../../dify/t01-phase1-mock-v0.1/evidence/m3/local_dify_1_17/target-preflight.json)

## 1. 结论

目标是用户已启动的本地 Docker Dify，精确版本为 `1.17.0`，可导入 DSL 版本为 `0.7.0`。
同一实例已经提供可复核的 Workflow 导出结构；专用 provider
`t01-phase1-mock-mcp-v01` 可从 Dify API 容器访问，并精确枚举 M1-06 登记的 26 个工具。
新建、回读和调试运行所需能力均已验证，两个目标应用在首次导入前均无同名碰撞。因此
`PH1-MOCK-M3-01` 无 blocker，放行 M3-02。

预检仅访问本地 Dify 控制面和本项目一期 Mock transport。未进入 HiMat 后端，未调用真实科学
工具，未发起科学公网请求。

## 2. 目标实例事实

| 项目 | 冻结事实 |
|---|---|
| 环境 | `LOCAL_DIFY_DOCKER` |
| Dify 版本 | `1.17.0` |
| DSL 版本 | `0.7.0` |
| 部署形态 | Docker Compose，本机范围 |
| 绑定档案 | `local_dify_1_17` |
| provider 稳定 ID/显示名 | `t01-phase1-mock-mcp-v01` |
| provider 实例记录 ID | `94a0a63c-d085-4684-a481-956f01ba41bf` |
| 协议 | MCP Streamable HTTP，协议版本 `2025-06-18` |
| 网络方向 | Dify API 容器 → Docker host gateway → 本地一期 Mock transport |
| 认证方式 | `NONE`；无凭据写入仓库或 DSL |
| 状态存储 | 宿主机一期 M3 专用运行目录 |

provider 实例记录 ID 只用于目标实例关联；Workflow 中的稳定 provider ID 仍由 M1-06 命名空间
决定。Dify app/workflow/run/node system ID 同样不得替代规范 `request_id`、`run_id` 或 envelope ID。

## 3. 同实例 DSL 参照

从同一 Dify 实例读取的参考应用为 `T01_Master_v10`，净化后的导出 SHA-256 为
`27c9dc3e9c12b8184c65d52a58d85280772d716f72e436b6770b15fcbea74c35`。参照确认了当前实例实际接受
的 `start`、`tool`、`if-else`、`variable-aggregator` 和 `end` 节点结构，以及 MCP tool 节点的
provider/tool 字段形态。参照不作为一期业务图源，也没有复制旧 P0-P7 业务拓扑。

一期所需的有限重算和条件汇合采用目标版本可表达的确定性展开：N12 最多三轮在画布上有界展开，
N16/N17 通过后端控制字面量选择执行或明确跳过，再由 variable aggregator 汇合。这是 Dify
工程映射，不改变 M1-03 的业务语义。

## 4. Provider 与工具闭集

目标 provider 可达且 `authed=true`，工具数为 26。工具闭集由资产注册表读取，构成为：

- 1 个运行初始化工具；
- N01-N18 共 18 个节点事实工具；
- 6 个控制字面量工具：设计适用性、N12 验证、N15 交付建议、N16/N17 适用性和 N18 入口；
- 1 个运行最终化工具。

未知工具、未知参数、未知场景和未知运行均由 transport fail closed。生命周期驱动器中的 poll、
事件注入、取消和恢复不是第 27 个业务工具，也不出现在 Dify provider 工具集合中。

## 5. 权限、碰撞与能力

| 检查 | 结果 |
|---|---|
| 导入新 Workflow 应用 | `PASS` |
| 回读/导出草稿 Workflow | `PASS` |
| 调试运行 | `PASS` |
| `T01_Phase1_Mock_v0.1` 首次导入前碰撞 | 无 |
| `T01_Phase1_Mock_v0.1_Debug` 首次导入前碰撞 | 无 |
| N12 三轮有界重算 | 可表达 |
| N16/N17 条件分支与汇合 | 可表达 |
| 失败终态 | 可表达 |
| checkpoint/recovery 观察 | 可由显式测试驱动器与 Workflow 最终化入口协同完成 |

后续重导入采用精确 app ID，不以同名模糊查找覆盖其他应用。导入响应、provider 配置和证据中均不
保存 Cookie、授权头、API key、密码或远程科学地址。

## 6. 范围守卫

| 计数 | 值 |
|---|---:|
| 真实科学执行 | 0 |
| 科学公网请求 | 0 |
| 旧 P0-P7/S07 实现复用 | 0 |
| HiMat 后端访问 | 0 |
| blocker | 0 |

本预检只放行 M3 的 Workflow 工程工作，不代表 Mock v0.1 已冻结，也不代表真实科学能力或生产
Workflow 已部署。
