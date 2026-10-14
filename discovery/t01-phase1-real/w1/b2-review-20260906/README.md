# W1-08B2 评审准备证据

现行进度见 [STATUS](../../../../docs/project/STATUS.md)，解释及放行条件见
[B2 限定评审](../../../../docs/project/phase1/PHASE1_REAL_W1_B2_REVIEW.md)。

- expected_cases.json：执行前的 20 组人工契约预期和 11 条旧输出回读计划；不冒充模型预测。
- execution：实际完成的离线配对与重解析、回放请求/结果、公开标注差异记录；新模型执行次数为 0。
- reference_inventory.json / references：四条公开标注的原片段、精确来源行和 hash，保留训练独立性未确立及科学未签收状态。
- protected_before.json / after / manifest.json：原件、旧 Academic/公开资料及当前实现的保护清单、评审源码/契约快照和字节 hash。

空输入的真实拒绝来自旧 Academic 批次；20 组人工异常/正常例和旧输出均按各自证据身份记录。
科学参考样本和验收阈值待具名接受，不能把格式一致或预测/标注一致当成科学放行。
精确只读复核命令见 [运行手册](../../../../docs/development/RUNBOOK.md)。
