# W1-06 FreeSASA 本地原始工具验证

本项核实 FreeSASA 的执行位置、版本、格式与原始产物，属于开发机 G0 探测。
当前阶段与剩余依赖见 [STATUS](../STATUS.md)；[本批证据](../../../discovery/t01-phase1-real/w1/freesasa-s09-20260905/README.md)
与甲方目标验收分开记录。S-09 配套规则见 [定点核对](PHASE1_REAL_W1_S09_RULE_REVIEW.md)。
后续参数、独立算法对照、候选容差及用户先行采用记录见 [FreeSASA/S-09 决定](PHASE1_REAL_W1_FREESASA_S09_DECISION.md)。
下文保留首批原始探测事实，不将后来 200 slices 的结果写回本批默认参数记录。
后续地址、实体定位与缺失/多链输入的开发消费验证见 [R-58/FreeSASA 边界补强](PHASE1_REAL_W1_R58_SASA_BOUNDARIES.md)。

## 环境与来源

用户确认本地没有 FreeSASA 命令或系统包，并在本轮启动 Docker。
已核实 Docker Desktop Linux 引擎可用；在已有 Python 基础镜像上新建独立开发镜像，
以 pip 安装候选版本 FreeSASA 2.2.1、Biopython 1.88、NumPy 2.4.6。
原件未锁定 FreeSASA 版本，因此本轮按 ToolSpec §1 记录候选版本，尚未将其冻结为生产版本。

- 本地镜像标签：`t01-freesasa-g0:2.2.1-20260905`；执行按 [image ID](../../../discovery/t01-phase1-real/w1/freesasa-s09-20260905/environment/docker.json) 固定。
- [构建定义](../../../discovery/t01-phase1-real/w1/freesasa-s09-20260905/environment/Dockerfile)、
  [pip 来源和包 hash](../../../discovery/t01-phase1-real/w1/freesasa-s09-20260905/environment/pip-install-report.json)、
  [Python 版本清单](../../../discovery/t01-phase1-real/w1/freesasa-s09-20260905/environment/python-freeze.txt)及
  [系统包清单](../../../discovery/t01-phase1-real/w1/freesasa-s09-20260905/environment/os-packages.txt)保留。
- 软件包元数据声明 MIT；甲方环境的软件使用、版本和资产接收仍须按 W1-01 登记。
- 构建阶段下载公开软件依赖；运行阶段使用 `--network none`，每个案例仅观察到 loopback 网络接口。
  输入挂载只读，结果写入本批独立目录；容器执行后移除，开发镜像保留供复跑。

本次读取当前样本副本，没有查询 RCSB/AFDB、下载新结构或改动 Dify 应用。

## 本批实际探测

| 案例 | 观察到的事实 | 使用边界 |
|---|---|---|
| Python 原生 Structure 直接读 1UBQ mmCIF | 解析失败，stderr 保留坐标行读取错误 | 此次测试的 Python 文件入口不能直接读 mmCIF；不泛化为所有 FreeSASA 入口都不支持 |
| Biopython 转 PDB，再由原生入口读取 | 转换前后 660 个原子的身份及 PDB 三位坐标核对一致；FreeSASA 纳入 602 个原子、76 个残基 | 58 个水原子按包默认 HETATM=false 排除；未确认生产计算上下文 |
| 相同原生路径重复运行 | 原始 JSON 字节与数值一致 | 重复性工程证据，不是独立科学金标准 |
| Biopython mmCIF 对象桥接 | 返回 602 原子、76 残基；stderr 有元素推断提示 | 与原生路径总面积存在约 0.000146 Å² 差异，只记录，不据此批准科学容差 |
| 非法 PDB 文本 | 返回解析异常，无正常结果 | 错误路径事实 |
| 原人工 partial/iCode 坐标，经原生和桥接两条路径 | 原始计算含 NaN，首轮严格 JSON 序列化拒绝输出；补查保留非有限原值 | 仅作格式/非法数值案例；不能当正常 SASA 样本，也不改成零或缺失残基 null |
| 从 1UBQ 派生的人工编号案例（A43 改为 A42A） | 两条路径均保留 A42 与 A42A，仍有 76 个独立残基地址，绝对面积有限 | 只证明本案例的插入码身份处理，不自动签发 R-58 verified |

原生 PDB 路径的本次总绝对 SASA 为 4804.055641141745 Å²；逐原子、逐残基加总与工具总值一致。
数值仅用于记录本次参数和结构上下文，不作为项目科学结论或 RSA 参考答案。

## 适配器应吸收的事实

1. 优先准备“保留 mmCIF 原件→工具边界派生 PDB→核对编号/原子→调用”的工程路径。
   本案例转换成功；多字符作者链等超出 PDB 能力的输入仍须显式报错或设计可追溯映射，不能截断。
2. 只取绝对 SASA，项目 RSA 按专家锁定的 Tien Theoretical 表处理。库自带相对面积保留为原始事实，
   不直接当项目 RSA；本轮没有生成归一化数组或 buried_fraction。
3. 实测默认参数为 LeeRichards、probe radius=1.4 Å、20 slices、1 thread；HETATM/hydrogen/join-models 均为 false。
   这些是候选版本的默认事实。生产 MODEL、链、非蛋白组分、缺原子和未知原子处置仍需明确，不能隐式继承。
4. 检查逐原子/逐残基值是否有限，再做项目后处理。原工具返回对象不等于合法数值；NaN 要保留原始诊断，
   对应公共接口 OUTPUT_INVALID 或既定数值失败语义，不静默填零、裁剪或编造可用结果。
5. 原始工具探针与公共协议适配器分别验收；本批直接调用原始 API，没有声称已实现 `run_tool.py` 或生产接口。

接口行为交叉依据：[FreeSASA 官方类文档](https://freesasa.github.io/python/classes.html)、
[函数文档](https://freesasa.github.io/python/functions.html)、[2.2.1 发布资料](https://pypi.org/project/freesasa/2.2.1/)。
官网页面标示 Python 文档 2.2.0；本轮具体结论以实际 2.2.1 模块及原始记录为准。
项目科学规则仍来自 [C34 ToolSpec](../../../工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C34_FreeSASA_v10.5.md)。

## 完整 G0/G1 前还缺什么

独立数值参考、参数与候选容差已在后续批次形成，用户先行采用；仍需算法确认。
完整 G0/G1 还需要甲方目标 profile 与实际执行人、R-58 映射评审、结构上下文/原子完整性确认、
partial/未知残基/缺原子和留出样本，以及 S-09 六项规则的算法确认。新发现的 G76 出域见 OI-027，
当前按已采纳的报错复核方案处理，不能将该样本算作正常 RSA 验收通过。
本次为本地原始工具成功提供证据，未完成完整 W1 G0/G1、生产适配器、离线交付包或 Dify 接入。

复跑与只读核验命令见 [运行手册](../../development/RUNBOOK.md#freesasa-本地原始工具探测)。
