# 本地结构映射测试输入

synthetic/ 中的 PDB、mmCIF 和短序列是人工工程夹具，坐标没有真实蛋白科学意义。
它们用于验证 42/42A、缺失位置、作者与 label 编号等处理，不能跑出科学结论。
后续 [FreeSASA 原始探测](../../../docs/project/phase1/PHASE1_REAL_W1_FREESASA_G0.md)实际观察到该人工坐标产生 NaN；
继续保留为格式/非法数值案例，正常插入码计算验证使用另行标识的真实坐标人工编号副本。

real/ 中的 [1UBQ](real/1UBQ.cif)、[5XZC](real/5XZC.cif) 与对应 FASTA 是用户授权从历史资料只读复用的本地文件。
[来源清单](real/SOURCE_MANIFEST.json)记录原路径、字节 hash、采集记录和独立序列来源。
当前测试只读这些独立副本，不依赖历史实现模块，不使用网络。

这些是公开样本复用，不是甲方提供的测试用例，也没有获得本项目科学金标准身份。
5XZC 为多链且仅 Cα，专用于验证受限/歧义处置，不能替代正常全原子 FreeSASA 验收。
历史原件和它们的既有记录保持不变。

实体位置、重复区缺失、多链和转换消费的人工派生输入见
[R-58/FreeSASA 边界批次](../../../discovery/t01-phase1-real/w1/r58-freesasa-boundaries-20260905/README.md)。
新增测试只读该批 `prepared/` 输入；最初构造错误另留原文件，不能当作已通过样本。
