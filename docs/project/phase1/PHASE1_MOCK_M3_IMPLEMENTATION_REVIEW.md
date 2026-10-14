# PH1-MOCK-M3 Dify Workflow 构建、绑定与实例验收评审

> 评审结论：`PASS / ZERO_BLOCKER / M3_COMPLETED / M4_READY`  
> 评审日期：2026-09-04  
> 目标档案：`local_dify_1_17`  
> 机器结果：[M3 acceptance result](../../../dify/t01-phase1-mock-v0.1/evidence/m3/local_dify_1_17/T01_PHASE1_MOCK_M3_ACCEPTANCE_RESULT_v0.1.json)  
> 结果 Schema：[M3 acceptance result Schema](../../../dify/t01-phase1-mock-v0.1/evidence/m3/local_dify_1_17/T01_PHASE1_MOCK_M3_ACCEPTANCE_RESULT_SCHEMA_v0.1.json)

## 1. 放行结论

`PH1-MOCK-M3-01～10` 已全部完成。两个严格一期 `N01-N18` Dify Workflow 已从单一生成源构建，
以 `local_dify_1_17` 档案完成 provider 绑定，导入本地 Dify 1.17.0，回读结构一致，并在目标实例
完成 main/debug 双阶段全量执行和 21 组 parity。机器结果为 `PASS`，blocker 为 0。

本评审只将 `PH1-MOCK-M4` 放行为 `READY`。尚未创建 M4 campaign，尚未冻结一期 Mock v0.1；
真实科学工具、生产适配器和真实 Dify Workflow 均保持 `NOT_DEPLOYED`。

## 2. 验收摘要

| 项目 | Main | Debug | 结论 |
|---|---:|---:|---|
| 场景 | 21 | 21 | PASS |
| canonical submission | 23 | 23 | PASS |
| checkpoint plan / step | 4 / 16 | 4 / 16 | PASS |
| 适用全局断言 | 9 | 9 | PASS |
| 焦点断言 | 44 | 44 | PASS |
| 覆盖门 | 10 | 10 | PASS |
| blocker failure | 0 | 0 | PASS |

`M3_MAIN_DEBUG_PARITY` 比较 21 组规范化 canonical 结果，21 组全部相等，
`t01_phase1_mock_v01.acceptance.global.016` 为 `PASS`，差异失败数为 0。

## 3. 目标、应用与回读事实

| 项目 | 结果 |
|---|---|
| Dify / DSL | `1.17.0` / `0.7.0` |
| provider | `t01-phase1-mock-mcp-v01`，精确 26 tools |
| main app / draft workflow | `a5fa1d0e-45a9-469e-aef9-4c55639f9eba` / `181b59ac-a9f6-427a-a261-8a690c9c6409` |
| debug app / draft workflow | `52dd71b0-9b76-4c85-b50c-e5aead4b293b` / `63b89ec7-51f0-4472-a1b4-045efaddb5c3` |
| 每个画布 | 59 Dify 节点、79 物理边、E001-E027 全部可回读 |
| provider/tool 回读 | 同一稳定 provider，精确 26-tool 闭集 |
| 结构回读 | main/debug 的 source 与 readback semantic graph SHA-256 分别相等 |
| 导入警告 | 0 |

上述 Dify system ID 只作实例关联。每次实例调用的 workflow run ID 已与 canonical
`request_id`/`run_id` 分离记录；它们没有进入或替代 M1-04 规范身份。

## 4. 可追溯生成与绑定链

| 资产 | SHA-256 |
|---|---|
| M1 资产注册表 | `ea851f97cacb304a2927d45ef85363d7c44b49f792b10172bfe7792f960672a2` |
| main template | `d14037d202b8cb715560ed9fd1302867796ab7db2d54e3d2d673f8d9626a7e61` |
| debug template | `09162ff71fad27340ce08e1b73dd4a2caa3b0cdba8a013830c541e6d2a6332f3` |
| binding manifest | `025d5859b01befbc77540a4d32a0ef01479c34484af481a615cf8b126395855a` |
| main bound | `c1bcbb1f2a156d79ac3fcd592c08e5415ca5b671c2e47c339672c11567b48fa6` |
| debug bound | `d7883fbc19ff6aa66a875e7fb60f88be2ce46945c4b919c4057332f71752ad1b` |

generator 的 `--check` 可只读证明两个模板字节级可重建；binder 的 `--check` 可证明
registry→template→manifest→bound 哈希闭合。模板只含登记 provider token，bound 已无未解析 token；
binding、bound 和证据中的 secret finding 均为 0。

M1 资产注册表中的 `implementation_state=SPEC_ONLY` 是 M1-06 冻结时的历史声明，未被反向改写；
实际 M3 物化状态由本评审、绑定证据、导入证据和 acceptance result 共同记录。

## 5. M3-01～10 完成证据

| 工作项 | 结论 | 主要证据 |
|---|---|---|
| M3-01 | PASS | [目标预检](PHASE1_MOCK_M3_01_DIFY_TARGET_DSL_PREFLIGHT.md)与 `target-preflight.json` |
| M3-02 | FROZEN/PASS | [调用与画布契约](PHASE1_MOCK_M3_02_WORKFLOW_INVOCATION_GRAPH_CONTRACT.md) |
| M3-03 | PASS | 薄 MCP Streamable HTTP transport；目标枚举与调用精确 26 tools |
| M3-04 | PASS | 单一 generator 确定性生成 main/debug 两个模板 |
| M3-05 | PASS | DSL、拓扑、变量、秘密、隔离和负向静态测试 |
| M3-06 | PASS | 严格 binding Schema/manifest、两个 bound 与完整哈希链 |
| M3-07 | PASS | 两应用无碰撞导入、精确 ID 重导入、回读语义图一致 |
| M3-08 | PASS | main/debug 各 21 场景、23 提交、9+44 断言、10 覆盖门 |
| M3-09 | PASS | 21 组 parity 与 global.016 全部通过 |
| M3-10 | PASS | 本评审五项结论通过，M4 仅置为 READY |

## 6. 五项具名评审结论

1. **工程一致性 PASS**：source→template→binding→bound→import→readback→run 全链均由稳定 ID、
   版本和 SHA-256 追溯；模板与 bound 没有手工补丁源。
2. **算法边界 PASS**：Dify 未计算科学值、Gate、Hard Filter、Pareto、重算、条件或 join 结论；
   业务控制全部来自 M2 `SCENARIO_LITERAL`，`scientific_execution_count=0`。
3. **产品范围 PASS**：只实现 N01-N18、E001-E027；旧 P0-P7/S07 实现复用计数为 0，未引入生产
   能力或科学远程回退。
4. **Dify 完整性 PASS**：两个应用使用同一 26-tool provider，导入回读一致，main/debug 双执行与
   21 组 parity 全部通过。
5. **发布边界 PASS**：M3 仅完成一期 Mock 的 Dify 编排和实例验收；M4 campaign、Mock 冻结、真实
   工具和生产发布均未提前发生。

## 7. 实施中闭合的工程发现

- 本地 Dify 容器通过 Docker host gateway 高频创建短连接时曾出现一次瞬态 503。transport 固定为
  HTTP/1.1、扩大连接队列并关闭阻塞式 server close 后，全量双阶段运行未再失败。
- 初始化工具的目标 Dify 输出 Schema 最初没有暴露完整 `result`，导致幂等冲突的拒绝 envelope
  无法从拒绝 end 返回。Schema 增加 `result` 并让结构化输出同时保留完整结果后，冲突提交在同一
  canonical 状态上重放验证通过，没有新增 canonical submission。
- 23 次 submission 与 4 次 checkpoint 最终化观察分别留存；每条记录都保存 Dify workflow run ID
  和 canonical ID 映射，避免把观察调用误计为业务提交。

这些修正都在 Dify-facing 工程层，没有改变 M1 场景、M2 后端真值、26 个工具稳定身份或科学规则。

## 8. 隔离与安全结果

| 守卫 | 结果 |
|---|---:|
| 科学执行 | 0 |
| 科学公网请求 | 0 |
| legacy 实现复用 | 0 |
| HiMat 后端访问 | 0 |
| secret finding | 0 |
| M4 campaign 写入 | 0 |
| blocker failure | 0 |

M3 运行证据保存在 `dify/t01-phase1-mock-v0.1/evidence/m3/local_dify_1_17/`，运行时状态保存在
`var/t01-phase1-mock-v0.1/m3-execution/`；没有写入 M4 的 `regression/runs/{campaign_id}/`。

## 9. 回归结论

最终收口结果如下；四个分区保持独立陈述，不相加冒充一期功能数量：

| 分区 | 结果 |
|---|---|
| generator `--check` / binder `--check` | PASS；两个 template/bound 哈希与本评审一致 |
| 文档检查 | PASS；113 个 Markdown 文件 |
| 当前根测试 | PASS；164 项 |
| 冻结旧完整 Mock | PASS；74 项 |
| S07 备用包 | PASS；41 项 |

命令见[当前开发运行手册](../../development/RUNBOOK.md)。任一分区后续失败都会阻断 M4 冻结，不能
用本次历史 PASS 绕过。

## 10. M4 放行边界

下一项为 `PH1-MOCK-M4`：建立独立 campaign，执行正常、分支、重算、条件、失败、取消/恢复、
幂等和排除项的冻结回归。M4 必须重新验证 M3 产物与目标实例证据，不能把本次 M3 execution root
改名冒充 M4 campaign，也不能因 M3 PASS 而声称 Mock v0.1 已冻结。
