# 人工接口示例

这些文件用于学习 JSON 结构和测试校验器，所有 request.run_mode 都是 engineering_example，
所有 result.usable_for_pipeline 都是 false。成功状态也是人工构造，不是 FreeSASA/BepiPred 的实测。

| 目录 | 检查用途 |
|---|---|
| [freesasa-success](freesasa-success/request.json) | 完整数组与结果形状 |
| [freesasa-partial](freesasa-partial/request.json) | 缺失位置 null、带位置的警告、不缩短数组 |
| [freesasa-skipped](freesasa-skipped/request.json) | N02 quality=low、未调用原工具 |
| [freesasa-mapping-pending](freesasa-mapping-pending/request.json) | 映射待核验、保留原始证据、没有可交接结果 |
| [bepipred-rules-pending](bepipred-rules-pending/request.json) | OI-026 待定，禁止用空峰数组冒充完成 |
| [bepipred-success-shape](bepipred-success-shape/request.json) | 已完成且无峰的输出形状；不定义峰算法 |
| [bepipred-failed](bepipred-failed/request.json) | 资产缺失错误 |
| [bepipred-timeout](bepipred-timeout/request.json) | 超时错误终态 |

每个目录都有 request.json、output/result.json；有产物时，output 下保存真实的教学文件供 hash 检查。
三残基/十残基序列是短小的接口练习，不判断完整 T-01 输入合法性。
SYNTHETIC-NOT-APPROVED profile 只是形状占位，绝不能转成生产批准记录。
结构/映射/config 为 null 的请求不能实际计算；真实运行必须补齐获准资产。

从上一层执行 `python validate.py --examples`。不要编辑结果 hash 来掩盖文件变动；
新增测试时按修改后的教学文件重算 hash，并明确它仍是人工测试。
