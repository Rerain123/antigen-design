# 文档中度扁平化执行记录

> 执行日期：2026-09-03  
> 授权：用户确认“继续优化”  
> 性质：当前资料迁移、导航归并与历史归档；不改变业务范围、科学结论或生产门禁。

## 1. 执行结果

- `docs/` 最大文件深度由 6 层降为 3 层；原先位于第 5～6 层的 29 个文件已全部消除深层路径。
- 当前项目控制资料集中到 `docs/project/`，当前 P0 集中到 `docs/project/p0/`，历史资料集中到 `docs/archive/`。
- 当前入口不再串联 `project/overview/planning/governance/stages` 等中间导航层。
- 核心导航收敛为[文档总入口](../../../docs/README.md)、[当前 P0](../p0-v07-plan/README.md)和[统一归档索引](../README.md)。

## 2. 迁移与链接

- 逐项校验并迁移 47 个文件；没有使用递归移动。
- 49 个 Markdown 文件中的 444 个本地链接按新位置重写。
- 两支仍可执行的 S-07 证据脚本改为读取 `docs/archive/p0/`；discovery 中记录形成时路径的 JSON/报告仍作为历史快照保留。
- 文档检查器的必需文件表已切换到扁平结构。

## 3. 归并后删除的 11 个来源页

下列文件在内容有明确承接位置后删除：

- 3 个重复总入口：`docs/project/CURRENT_BASELINE.md`、`docs/project/README.md`、`docs/project/stages/README.md`，由 `docs/README.md` 承接。
- 5 个目录型索引：planned、reviews、P0 history、M1 history、governance history 的 `README.md`，分别由当前 P0、评审文档或统一归档索引承接。
- 3 个未来里程碑草案：M3/S-09、M5/R-58+FreeSASA、M6/契约迁移，完整要点归并到[P0 后续里程碑承接](../p0-v07-plan/P0_FUTURE_MILESTONES.md)。

随后逐个确认并删除 11 个空目录；没有递归删除内容。仓库当前没有 Git 元数据可提供文件级回退点，但上述 11 页的有效内容及历史来源均已保留在承接文档中。

## 4. 未改变的边界

- 当前专家包及其最新一期 18 节点图未移动、未改写。
- 冻结 Mock、真实工具 discovery 证据语义、代码行为与测试基线未因本次目录整理改变。
- 当前阶段仍是 `P0_V0_7 / M1_READY_NEXT / PRODUCTION_NOT_DEPLOYED`。
- RCSB PDB、AlphaFold DB、联网回退和 S-07 仍不属于一期当前范围。

## 5. 验证

- 文档链接与必需文件检查：`PASS`，80 个 Markdown 文件。
- 全量自动化测试：`PASS`，116 项。
- 当前 3 个 JSON 资料文件可解析；最新一期图哈希保持不变，外层重复副本不存在。

