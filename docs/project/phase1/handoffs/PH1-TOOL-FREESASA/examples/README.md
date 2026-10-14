# FreeSASA 示例说明

request.example.json 使用公共接口 0.1.0，run_mode=engineering_example，引用本目录人工 mapping_input.pdb 与 mapping.example.json，附实际文件 hash；config=null。映射已符合 R-58 公共格式，状态为 unverified，不能移除教学标记就当成真实核验。可运行公共 --check-files 检查输入与映射绑定；它没有执行 FreeSASA。
三残基例子只为容易看清对应关系，不是完整 T-01 的合法输入样本；所附 PDB 是不具科学意义的人工坐标，仅用于映射测试。

conversion_cases.json 是原工具运行后的转换函数测试；面积是人工指定的。
它能检查单位、参考表、null、分母和错误处理，不能证明 FreeSASA 部署成功或科学结果正确。

真实结构、序列、已核验映射和参考结果需要另外登记来源、hash 及使用范围。
完整的人工请求/结果配对见 [公共接口示例](../interface/examples/README.md)，均非真实运行记录。回传时把人工用例与真实结构验收分开。
