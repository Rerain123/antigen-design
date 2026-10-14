# BepiPred 示例说明

input.fasta 是人工工程序列，可用于原工具 smoke；没有科学参考含义，也没有附带预测值。
request.example.json 使用公共接口 0.1.0，run_mode=engineering_example；rule_profile=null 表示尚未具备正式后处理规则。完整的人工请求/结果配对见 [公共接口示例](../interface/examples/README.md)。

scores.fixture.json 是人工解析/比较练习，只验证位置和阈值比较；它不是原生 CSV，不能拿它验证原始列解析。
rule_questions.json 用于向主开发说明具体歧义，expected=null 是“待裁决”，不是“没有峰”。

真实参考样本、原始 CSV/FASTA、科学预期和容差另行登记。人工测试通过不能替代模型运行与科学验收。
