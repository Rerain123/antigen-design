# PH1-MOCK-M4 独立回归、冻结与放行评审

> 评审结论：`PASS / ZERO_BLOCKER / M4_COMPLETED / MOCK_V0.1_FROZEN / PH1-REAL-W1_READY`  
> 评审日期：2026-09-04  
> 冻结候选 campaign：`t01p1m-v01-reg-20260904-release-freeze-03`  
> 机器结果：[M4 regression result](../../../dify/t01-phase1-mock-v0.1/regression/runs/t01p1m-v01-reg-20260904-release-freeze-03/T01_PHASE1_MOCK_M4_REGRESSION_RESULT_v0.1.json)  
> 冻结 manifest：[Mock v0.1 freeze manifest](../../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_FREEZE_MANIFEST_v0.1.json)

## 1. 当前候选结论

`PH1-MOCK-M4-01～10` 已全部完成。正式候选在本地 Dify 1.17.0 中对 M3 登记的两个
精确 app ID 做了独立重导入/回读，并使用互相独立的全新 main/debug runtime 完成全量执行。
M4 result 为 `PASS / blocker=0`；四个回归分区全部通过，457 个冻结资产已登记路径、字节数和
SHA-256，独立 Schema 与只读 `verify` 均通过。因此 `T01-PHASE1-MOCK-v0.1` 正式置为 `FROZEN`，
且只将 `PH1-REAL-W1` 放行为 `READY`。

## 2. Campaign 审计轨迹

| Campaign | 状态 | 处置 |
|---|---|---|
| `...release-freeze-01` | REJECTED | 23 次 Dify 调用成功；新增校验误把幂等重放的既有 run `request_id` 当作本次提交 ID，生命周期前阻断；证据原样保留 |
| `...release-freeze-02` | REJECTED | 23 次 Dify 调用成功；Windows 残留监听器导致写入旧 stable runtime，生命周期前阻断；证据原样保留 |
| `...release-freeze-03` | FREEZE_CANDIDATE | 禁止端口复用且确认单一监听器；main/debug 独立 runtime 全链通过 |

失败 campaign 未清空、改名、覆盖或充当通过证据。第二项发现促成 transport 禁止
`SO_REUSEADDR`；实机二次监听尝试以 `WinError 10048` 失败，关闭了跨 runtime 路由风险。

### M4-01～10 交接闭环

| 工作项 | 结果 | 机器证据 |
|---|---|---|
| M4-01 | PASS | campaign/Schema/CLI fail-closed 测试；非法 ID、链接、越界、legacy 与覆盖均拒绝 |
| M4-02 | PASS | `asset-chain.json`；21 来源、350 fixture 与六项 M3 接管哈希重算闭合 |
| M4-03 | PASS | `import-readback-evidence.json`；精确 2 app、59/79、E001-E027、26 tools、0 warning |
| M4-04 | PASS | `main/` 五份批次/capture；21/23/22、4 finalization、27 Dify run、4/16 checkpoint |
| M4-05 | PASS | `debug/` 五份批次/capture；同一完整矩阵且独立 runtime |
| M4-06 | PASS | M4 result；12 global、44×2 focus、10 coverage、21 parity，失败 0 |
| M4-07 | PASS | campaign/release-candidate 负测；身份、顺序、路径、篡改、科学与 freeze 失效关闭 |
| M4-08 | PASS | `checks/*.log` 与 `regression-partitions.json`；115 / 185 / 74 / 41 |
| M4-09 | PASS | freeze manifest；457 个资产，Schema 与只读 verify PASS |
| M4-10 | PASS | 本评审五项具名结论；Mock v0.1 FROZEN，W1 READY |

所有工作项剩余 blocker 均为 0。命令入口与复核方式见[当前运行手册](../../development/RUNBOOK.md)。

## 3. 候选机器结果

| 项目 | Main | Debug | 结论 |
|---|---:|---:|---|
| 具名场景 | 21 | 21 | PASS |
| canonical submission | 23 | 23 | PASS |
| 唯一请求变体 | 22 | 22 | PASS |
| 本次提交 request ID | 23 | 23 | PASS |
| finalization 观察 | 4 | 4 | PASS |
| Dify workflow run | 27 | 27 | PASS；角色内唯一且不等于 canonical run ID |
| checkpoint plan / step | 4 / 16 | 4 / 16 | PASS |
| 焦点断言 | 44 | 44 | PASS |
| blocker failure | 0 | 0 | PASS |

另有 12 条 M4 全局断言、10 个覆盖门和 21 组 main/debug parity 全部通过。`global.015` 使用目标
回读事实，`global.016=PASS`，`global.018=[21,23,0]`。

## 4. 输入、派生链和目标回读

| 项目 | 结果 |
|---|---|
| M1 冻结来源 | 21 份 SHA-256 与 M2 source lock 一致 |
| fixture 闭集 | `2 + 22 + 326 = 350`，逐文件验证通过 |
| M2 / M3 输入 | 均为 `PASS / blocker=0`，只作输入放行证据 |
| registry | `ea851f97cacb304a2927d45ef85363d7c44b49f792b10172bfe7792f960672a2` |
| main / debug template | `d14037d…e61` / `09162ff7…2f3` |
| binding manifest | `025d5859…55a` |
| main / debug bound | `c1bcbb1f…fa6` / `d7883fbc…d1b` |
| Dify / DSL | `1.17.0` / `0.7.0` |
| 目标结构 | 2 apps；每个 59 节点、79 物理边、`E001-E027`；26 tools；0 warning |

generator 与 binder 的只读 check 均通过；模板规范化业务图一致，bound 无未解析 token、秘密、本机
绝对绑定或科学远程地址。

## 5. 隔离和算法边界

| 守卫 | 候选结果 |
|---|---:|
| 数据分类 | `MOCK_DATA` |
| `scientific_compute` | `false` |
| 科学执行 / 科学公网请求 | 0 / 0 |
| legacy 实现复用 | 0 |
| HiMat 后端访问 | 0 |
| secret finding | 0 |
| 生产交付 | `NOT_DEPLOYED` |

控制结果只来自 `SCENARIO_LITERAL`。Dify 未执行科学计算、Hard Filter、Gate 推断或 Pareto；N01
没有 RCSB/AFDB/外部结构 ID 或远程 fallback。旧 P0-P7 与 S07 只在独立回归分区运行。

## 6. 五项具名评审结论

1. **工程一致性 PASS**：单一生成源、派生链、实例回读、运行证据与 457 个冻结资产哈希闭合；
   manifest 的只读复核通过。
2. **算法边界 PASS**：控制仅来自 `SCENARIO_LITERAL`，无科学计算、Hard Filter、Gate 推断或
   Pareto，相关执行计数均为 0。
3. **产品范围 PASS**：只含 N01-N18/E001-E027、默认完整 profile 与冻结排除项；旧 P0-P7/S07
   未进入当前实现或冻结资产。
4. **Dify 完整性 PASS**：两个精确应用、26 tools、main/debug 全量运行与 21 parity 全部通过。
5. **发布边界 PASS**：冻结对象仅为 Mock v0.1；真实科学工具、生产适配器和真实 Workflow 仍为
   `NOT_DEPLOYED`，M4 不代替 W1 的 G0/G1。

## 7. 四分区与冻结证据

| 分区 | 结果 |
|---|---|
| 文档 | PASS；115 个 Markdown |
| 当前一期 | PASS；185 项 |
| 冻结旧完整 Mock | PASS；74 项 |
| S07 备用包 | PASS；41 项 |

四份日志分别记录命令、相对工作目录、退出码、实际通过数和输出 SHA-256，未把分区测试数相加为
功能数量。关键冻结证据如下：

| 资产 | SHA-256 |
|---|---|
| M4 result | `e7730722034c9f8c15bf11394b3062744450e315f10012a7cd783c4b21701f6f` |
| asset chain | `1a1a027d705aef8aa4b44323128258a3542d484a84a0707109e425ff6df45fd4` |
| import/readback | `a6bfa8934beb921bf2f43ff198ae14fdfd87c88f5e93543ed20d7c0f59ac5823` |
| four partitions | `d7ce3f5cc965b8a479d95b080e9f90ad5f57ea61cb8c440dcc22fecae08b3268` |
| freeze manifest | `33dd4e041c51ecae755fe438d87dc40cc7c361c42edf1393bbf9825d020b572a` |

冻结时间为 `2026-09-04T14:18:00.001308Z`。正式只读命令
`run_m4_campaign.py verify` 返回 `PASS / FROZEN / 457 assets`。

## 8. 放行边界

`PH1-MOCK-M4` 已完成，下一项仅为 `PH1-REAL-W1 READY`。W1 从 N01-N02 的 G0 事实摸底开始；
在真实工具版本、输入输出、资源、许可证、原始产物、错误和断网行为完成 G0/G1 前，不得把 Mock
stub 直接替换为生产调用，也不得宣称真实科学能力已经部署。
