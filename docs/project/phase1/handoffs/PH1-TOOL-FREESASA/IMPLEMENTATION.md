# FreeSASA 实现说明

本文件把任务分成“先跑原工具”和“评审后做适配器”两步。
请求、结果、错误和入口统一按 [公共接口 v0.1](interface/README.md)实现。工程约定已统一；完整生产 G1 仍需真实工具、映射及规则证据。
科学规则来自包内专家原件，来源定位见 [索引](references/README.md)。

## 1. 先跑原工具，记录实际环境

使用独立环境，不改动现有项目的 Python 环境。目标系统按主开发提供的环境档案执行。
以下为有网准备环境的安装示例；具体 Python/FreeSASA 版本在试运行后锁定。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install freesasa
python -m pip show freesasa
python -m pip freeze > requirements.lock.txt
```

安装失败时记录完整命令、退出码及关键错误。需要编译依赖时，先核对官方说明和允许的安装范围。
不要反复更换版本却不记录。安装命令依据 [官方 Python 模块说明](https://github.com/freesasa/freesasa-python/blob/master/README.md)。

用主开发提供的真实结构或获准使用的官方样本调用原工具。至少记录：

- OS、Python、FreeSASA Python 包及所用 C 库版本（能取得时）、安装包来源。
- 输入文件原始字节 SHA-256、序列、运行命令、耗时和资源使用。
- 实际使用的算法、探针半径、精度、原子半径分类器、线程数，以及氢原子/HETATM/MODEL 处理选项。
- 原始逐残基绝对 SASA、错误与警告。主链和侧链都计入，不把只含 Cα 的结构当正常完整样本。

Python API 可从 Structure、calc、Result.residueAreas 入手；读取 ResidueArea.total 的绝对面积，
再执行项目自己的 RSA 归一化。API 与插入码行为见 [官方类文档](https://freesasa.github.io/python/classes.html)。
具体调用形式以选定版本的 help 和真实产物为准。

有网准备完成后，应能在目标环境断网运行。依赖应在与目标系统兼容的准备环境构建为本地安装包，
记录 requirements.lock.txt 和文件 hash；离线安装必须使用本地包，不能失败后联网补依赖。

## 2. 输入需要哪些内容

先支持一次处理一条输入序列及其指定结构。公共字段不再另列一套草案；精确格式见
[请求 Schema](interface/request.schema.json)与 [公共字段说明](interface/README.md#3-请求怎么填)。

本工具的 inputs 含 sequence、structure、mapping、mapping_status、quality_confidence；
parameters.config 引用实际参数文件，rule_profile 引用主开发确认的科学规则版本。
structure/mapping/config 采用 `{path, sha256}`，路径相对 request.json；output_dir 只通过命令行传入。
pipeline 计算必须使用有 hash 的资产和 verified 映射；准备期未知资产填 null 并回报依赖。

结构无法由选定接口直接读取时，使用主开发提供或评审的解析/转换路径，并保存原件、派生文件和映射。
转换必须保留链、残基、插入码的对应关系。首份 G0 可以先使用 PDB；其他格式不能因此被声明为已经支持，
完整格式处理由主开发在 W1 分工中明确并验收。

样例见 [请求说明数据](examples/request.example.json)和 [映射说明数据](examples/mapping.example.json)。
请求已引用包内人工结构和符合公共格式的 unverified 映射；config 仍为 null。格式/文件检查可执行，但真实工具运行仍需核验样本和参数，人工坐标不能用于科学计算。

## 3. 正确使用结构映射

输入序列第 1 个位置不一定是 PDB 编号 1。应使用主开发提供的对应表：

- 每个序列位置使用 1-based 编号；数组第 0 个元素对应序列位置 1。
- 结构残基用 chain_id、res_seq、insertion_code 联合定位；42 与 42A 不能合并。
- 映射中缺失的结构残基保留 null，后面的数组元素不能向前移动。
- 映射表必须覆盖整个输入序列，并说明哪些位置缺失；不凭结构文件的行号或排序猜位置。
- 检查映射版本、输入 hash、位置范围和重复映射。映射未核验/失败/链有歧义时，返回需复核结果，
  禁止供后续自动计算或交接，不能自行选第一条链。
- 多 MODEL、其他链参与计算的上下文、altloc 和转换后的链标识先由主开发确定。
  不擅自删掉其他链来计算表面积；你只把指定目标序列的结果写回输出。

主开发已提供映射格式与便携检查器，见 [R-58 说明](interface/structure_mapping/README.md)。本包有人工结构/映射配对供校验练习；真实映射验收仍依赖主开发，不要求你重写 R-58。

## 4. SASA 转成 RSA

规则来自 FreeSASA ToolSpec §2/2b：

```text
RSA[i] = 该残基的绝对 SASA / 该残基类型的参考面积
buried_fraction = 满足 RSA < 0.20 的残基数 / 输入序列长度
```

参考面积使用 Tien 2013 Gly-X-Gly 的 Theoretical 列，单位 Å²：

| 残基 | 面积 | 残基 | 面积 | 残基 | 面积 | 残基 | 面积 |
|---|---|---|---|---|---|---|---|
| A | 129 | R | 274 | N | 195 | D | 193 |
| C | 167 | E | 223 | Q | 225 | G | 104 |
| H | 224 | I | 197 | L | 201 | K | 236 |
| M | 224 | F | 240 | P | 159 | S | 155 |
| T | 172 | W | 285 | Y | 263 | V | 174 |

不得直接使用工具内置 relativeTotal 代替本表计算，也不得混入另一套参考面积。
表面积使用主链与侧链总面积；不要把绝对面积、百分数和 RSA 混在一起。

处理要求：

1. 先创建与 sequence 等长的 null 数组，再按映射填入可计算值。
2. 缺失结构残基或原子缺失导致不可计算：该位置保持 null，并记录警告。
3. 未知/非标准残基：RSA=null，记录具体位置并交主开发协调裁决；不替换为 G，也不静默删掉。
4. null 不参与埋藏数计数，分母仍是输入序列全长；RSA 正好等于 0.20 不算埋藏。
5. 保留完整精度参与计算，展示时再格式化。科学比较容差由参考验收确定。
6. 若按本表所得 RSA 超出规定范围，保留原始值及证据并标记需复核；未经裁决不截断成 1，
   不将出域值悄悄当作可交付正常结果。工具自身的相对面积也可能出域，原始事实见官方类文档；
   本项目的处置须结合 G0 与原件确认。

[人工转换用例](examples/conversion_cases.json)用于验证单位、null 和分母。
这些数值是单元测试输入，不是 FreeSASA 预测，也不代表真实结构。

## 5. 输出与错误

结果统一写入 result.json，原始产物放在同次输出目录。使用
[结果 Schema](interface/result.schema.json)与 [状态/错误/退出码表](interface/README.md#5-状态错误和退出码)。
result 的工具专用部分为 per_residue 与 buried_fraction；完整示例见
[人工正常形状](interface/examples/freesasa-success/output/result.json)、
[缺失位置](interface/examples/freesasa-partial/output/result.json)、
[质量跳过](interface/examples/freesasa-skipped/output/result.json)。

只在适用规则、映射和接口都已经确认并校验通过时设置 usable_for_pipeline=true。
部分位置缺失且映射可靠时按原文保留 null；是否同时触发复核遵循问题类型及确认的处置表。
RSA 在项目中是内部步骤变量，本包的调试 JSON 不意味着给最终 CandidateRecord 新增顶层字段。

| 情况 | 要求 |
|---|---|
| quality_confidence=low | 当前 N02 调用应跳过：execution_status=skipped、result=null，说明上游质量条件；不得输出全零数组 |
| 空序列、损坏结构、版本不匹配或程序报错 | failed，保留原始原因和退出码；不伪造科学结果 |
| 缺映射、映射失败或链歧义 | usable_for_pipeline=false、review_required=true；不得继续自动消费 |
| 非标准残基、未确定的数值处置 | 保存原始证据并标记需复核；不能将待确认项写为通过 |
| 文件缺失、非法 JSON 或 hash 不一致 | 输入校验失败；不联网检索结构、不自动替换文件 |

错误码及包装器退出码已在公共接口固定。映射未核验/失败、规则未确认或 RSA 出域时，result=null，原始证据进入 artifacts；禁止用“成功”掩盖不可自动消费。

## 6. 评审后实现的调用入口

适用 G1 放行后实现 run_tool.py，统一接受 JSON 文件和结果目录：

```bash
python run_tool.py --input request.json --output-dir results/run-001
```

这是你需要交付的入口，本包没有提供 run_tool.py。入口应返回明确退出码；
对超时/取消停止实际子进程并收集错误证据。全项目的队列、幂等和恢复由主开发实现，本包配合其接口。

源码建议分开组织调用、映射校验、结果转换和命令行，便于单独测试。
先提交 G0 事实和本公共接口的符合性结果；主开发完成适用 G1 评审后，再交付完整适配器、测试和离线包。
检查要求见 [验收清单](ACCEPTANCE.md)。
