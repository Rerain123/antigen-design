# S-07 历史证据命令

> **非当前实施手册。** S-07 已移出一期；这些命令只用于复核既有非生产证据，不得接入 MCP/Dify、创建生产能力或覆盖已有批次。

## P0-M1B 输出审计

```powershell
.\scripts\run-p0-s07-m1b-windows.ps1 -CampaignId p0-s07-m1b-<new-id>

..\..\.venv\Scripts\python.exe .\scripts\build_p0_s07_m1b_audit.py `
  --campaign-root .\discovery\p0\s07\p0-s07-m1b-<id>
```

每次使用新 campaign ID。已验证批次见[P0-M1B 运行记录](S07_M1B_RUN_RECORD.md)。

## 任务 5 离线契约复核

```powershell
..\..\.venv\Scripts\python.exe .\scripts\build_s07_task5_contract_evidence.py `
  --campaign discovery/p0/s07/p0-s07-task5-contract-20260903-b --verify
..\..\.venv\Scripts\python.exe -m pytest -o addopts='' -q tests/test_s07_task5_contract.py
```

历史契约和边界见[任务 5 结果契约](S07_TASK5_RESULT_CONTRACT.md)。已有 a/b 批次不得覆盖。

## 任务 6 非生产验收复核

```powershell
.\scripts\run-s07-task6-windows.ps1 -CampaignId p0-s07-task6-acceptance-YYYYMMDD-a
..\..\.venv\Scripts\python.exe -m pytest -o addopts='' -q .\tests\test_s07_task6_acceptance.py
..\..\.venv\Scripts\python.exe .\scripts\verify_s07_task6_closeout.py `
  --campaign-id p0-s07-task6-acceptance-20260903-c
```

新运行需要访问外部官方 API，不符合当前甲方内网一期实施边界；除非另有明确授权，只做已有批次的只读复核。详细记录见[任务 6 历史验收](S07_TASK6_ACCEPTANCE_AND_HANDOFF.md)。
