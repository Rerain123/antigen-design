# PH1-MOCK-M2 确定性 Mock 后端实现评审

> 评审日期：2026-09-04  
> 评审状态：`PASS / ZERO_BLOCKER / READY_FOR_M3`  
> 冻结输入：`T01-PHASE1-MOCK-M1-BASELINE-v0.1`  
> 实现里程碑：`PH1-MOCK-M2`  
> 生产状态：`NOT_DEPLOYED`

## 1. 放行结论

`PH1-MOCK-M2-01～09` 已完成。一期确定性 Mock 后端现可从 21 份冻结 M1 来源进行 fail-closed
预检，物化 350 个 synthetic payload，执行 21 个具名场景和 23 次提交，并输出符合 M1-04 的
18 节点 request/run envelope。

[M2 机器结果](../../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_M2_ACCEPTANCE_RESULT_v0.1.json)
通过其独立[结果 Schema](../../../dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_M2_ACCEPTANCE_RESULT_SCHEMA_v0.1.json)：
9 条适用全局断言、44 条焦点断言和 10 个覆盖门禁全部 PASS，blocker failure 为 0。因此仅将
`PH1-MOCK-M3` 放行为 `READY`；M4、真实科学工具和生产部署没有被提前放行。

## 2. 冻结输入与可追溯链

预检从 M1-01～08、envelope Schema 与四个示例、场景 Catalog、资产注册表、fixture manifest、
acceptance Catalog 及各自 Schema 重算 21 项 SHA-256。相同哈希同时写入
[fixture 物化索引](../../../dify/t01-phase1-mock-v0.1/fixtures/T01_PHASE1_MOCK_FIXTURE_MATERIALIZATION_v0.1.json)
和 M2 机器结果；任一冻结文件缺失、重复 JSON key、Schema 失败、版本/数量/引用不符或哈希漂移，
都会在生成或运行前失败。

M1 的声明状态保持不变：fixture manifest 仍记录 `SPEC_ONLY_PAYLOADS_NOT_MATERIALIZED`，acceptance
Catalog 的 M2 execution matrix 仍记录 `DECLARED_NOT_RUN`。实际 M2 执行事实只写入新增的物化索引、
机器结果和本评审，没有反向改写冻结规格。

## 3. 工作项验收

| 工作项 | 实际交付与证据 | 结论 |
|---|---|---|
| `M2-01` | `catalog.py/jsonio.py/paths.py` 严格加载五组机器契约、四个 envelope 示例和 21 项来源哈希；重复 key、非法路径和 Schema 变异负测通过 | `PASS` |
| `M2-02` | `fixtures.py` 与薄 CLI 生成 2 input + 22 request + 326 attempt，共 350 个 payload；8 个 null fixture 不生成文件；索引逐文件记录数据分类、路径、字节数和 SHA-256 | `PASS` |
| `M2-03` | `projection.py` 对 21 场景精确投影 378 个节点终态、334 个 attempts、控制字面量、实际边及 expected run | `PASS` |
| `M2-04` | `engine.py/storage.py` 实现提交、幂等、4 份/16 步离散 checkpoint、两阶段取消、超时注入、恢复新 run 和持久化本地入口；重启、重复事件、非法转换与损坏记录拒绝 | `PASS` |
| `M2-05` | 请求、checkpoint、终态均经 M1-04 Schema 校验；attempt、ArtifactRef、error、control、edge、audit 引用闭合；后端可把 run-scoped URI 解析为经哈希验证的 fixture 字节 | `PASS` |
| `M2-06` | `tools.py` 从资产注册表精确枚举并本地调用 1 initialize + 18 node + 6 control + 1 finalize；未知/旧工具身份及跨场景 run 绑定拒绝 | `PASS` |
| `M2-07` | `acceptance.py` 提供九根只读 selector view、28 个闭集 operator 和断言 harness；9 条全局断言逐案例、44 条焦点断言逐条执行 Catalog 的 selector→expected→operator 链，另叠加全局闭集不变量；各类变异均 fail closed | `PASS` |
| `M2-08` | 21 案例/23 提交、9+44 条 blocker 与 10 门禁执行完成；机器结果通过独立 Schema；三分区回归分别通过 | `PASS` |
| `M2-09` | 本评审完成工程、算法边界、产品范围与 M3 可接入性四项结论；状态、架构、索引和运行手册同步 | `PASS` |

## 4. 定量结果

| 项目 | 结果 |
|---|---:|
| 场景 / 案例 / 提交 / 唯一 request_id | `21 / 21 / 23 / 23` |
| 输入 / 请求变体 / 非 null attempt payload / null fixture | `2 / 22 / 326 / 8` |
| payload 文件总数 | `350` |
| 节点终态指令 / attempts | `378 / 334` |
| checkpoint plans / steps | `4 / 16` |
| 工具 / assertion operators | `26 / 28` |
| M2 全局 / 焦点 / blocker failure | `9 / 44 / 0` |
| 覆盖门禁 / failure | `10 / 0` |
| 科学执行 / 网络请求 / legacy 复用 / Dify DSL | `0 / 0 / 0 / 0` |

provided-structure 的 70 字节 synthetic PDB transport stub 内嵌在
`input.synthetic.standard.json`，其 ArtifactRef 保存字节数与 SHA-256；它明确声明不含科学坐标。
这样严格保持 M1-07 冻结的 `2 + 22 + 326 = 350` payload 闭集，不创建 manifest 未声明的第 351
个文件。

## 5. 四项具名评审结论

### 5.1 工程一致性：PASS

规格、payload、源码、测试、机器结果、版本和哈希形成单向追溯链。fixture 重复构建得到相同物化
索引 SHA-256；`--check` 只读验证能发现缺失、多余、路径逃逸、链接、字节数或哈希漂移。运行存储
使用独立 namespace，进程重启后 checkpoint 与幂等关系可恢复。

### 5.2 算法边界：PASS

科学执行计数为 0。Gate、N12、N15、N16、N17 和 N18 入口全部从具名场景复制
`SCENARIO_LITERAL`；fixture 内容、节点 stub、随机数、墙钟、环境与 LLM 均不参与控制。输出不含
科学评分、阈值、候选排序、DNA/密码子序列或真实结构结论。

### 5.3 产品范围：PASS

实现严格使用 N01-N18、E001-E027 与完整一期 profile；WT 直达、N12 最多三轮、N16 条件、
N16/N17→N18 汇合、上游失败/超时、取消、恢复和幂等均有具名场景。源码无旧 P0-P7/S07 import
或写入，结果统一标记 `MOCK_DATA`、`scientific_compute=false` 与 `NOT_DEPLOYED`。

### 5.4 后续可接入性：PASS

26-tool transport-neutral facade 共享同一后端与场景真值，足以供 M3 生成 main/debug 两个
Workflow 并验证路由。M2 未创建 generator、YAML、template、binding 或 bound，也未伪报 Dify
导入、main/debug parity 或 M4 campaign。

## 6. 接管 finding 闭环

| Finding | 处置 | 状态 |
|---|---|---|
| 旧物化索引缺少 Schema 已要求的 `source_sha256`，曾造成 100 个 setup error | 从冻结来源重算 21 项 SHA-256，重建全部 payload/索引并执行只读 `--check` | `RESOLVED` |
| M2 计划草稿一度把 synthetic structure 理解为独立第 351 文件，与 M1-07 的可物化数量不一致 | 将无科学坐标的 transport 字节内嵌到标准 input payload，保持 ArtifactRef/hash 与 350 文件闭集 | `RESOLVED` |
| 候选结果原先没有独立 M2 result Schema、覆盖门结果和完整执行环境 | 新增 Draft 2020-12 Schema；结果记录 21 来源哈希、10 门禁、关键冻结计数和离线环境 | `RESOLVED` |
| 候选断言实现未证明所有 selector/operator 都可执行 | 实现九根 selector adapter、28 operator 闭集及变异测试；53 条 M2 blocker 均实际调度 | `RESOLVED` |
| 候选断言曾先由布尔函数预判，再以 `prechecked` 绕过 operator 语义，形成第二份断言真值 | 删除硬编码焦点评估器及 `prechecked` 通道；9 条全局断言逐案例、44 条焦点断言逐条解析 Catalog selector、literal/source expected 与原生 operator；测试锁定 `9×21+44=233` 次原生调度 | `RESOLVED` |
| 物化索引、离线本地持久化入口及工具 run—scenario 绑定的负向证据不够直接 | 索引逐文件加入数据分类；增加 `MockBackend.local()`、重复事件/版本/闭集/哈希漂移、跨场景工具调用和秘密字段隔离测试 | `RESOLVED` |

未发现需要重新打开 M1 v0.1 的规格矛盾；未决科学问题继续留在现有 OI，不影响纯字面量 M2。

## 7. 最终验证记录

从项目根目录分别执行：

```powershell
.\.venv\Scripts\python.exe .\scripts\t01_phase1_mock\materialize_fixtures.py --check
.\.venv\Scripts\python.exe .\scripts\t01_phase1_mock\run_m2_acceptance.py
.\.venv\Scripts\python.exe .\scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest
Push-Location .\legacy\full-t01-mock-v0.1
..\..\.venv\Scripts\python.exe -m pytest
Pop-Location
Push-Location .\legacy\s07
..\..\.venv\Scripts\python.exe -m pytest
Pop-Location
```

结果分别为：fixture `CHECK_PASS`（350）、M2 acceptance `PASS`（21/23/16、53 blocker、0 failure）、
当前根 `136 passed`、冻结旧完整 Mock `74 passed`、S07 备用包 `41 passed`。三套 pytest 结果保持
分区陈述，不相加冒充一期功能数量。

## 8. 后续停止线

下一任务见[PH1-MOCK-M3 实施 Backlog](PHASE1_MOCK_M3_BACKLOG.md)：只从当前后端真值与 M1-06
注册表建立新的 Dify generator、main/debug 模板、绑定检查和导入证据。M3 不得复制旧生成器或
改变 M2 场景控制；`PH1-MOCK-M4` 仍受 M3 阻断，真实科学能力仍须等待 Mock v0.1 冻结。
