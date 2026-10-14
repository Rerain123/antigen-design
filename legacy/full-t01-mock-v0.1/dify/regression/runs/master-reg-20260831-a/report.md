# T01 Master 回归报告：master-reg-20260831-a

- 工作流：`T01_Master_v10`
- 场景：25
- 通过：25
- 失败：0
- 生成时间：2026-09-01T00:31:38.204360+00:00

| # | 场景 | run_id | Dify 状态 | 追踪节点 | 判定 | 说明 |
|---:|---|---|---|---:|---|---|
| 1 | `MOCK-HAPPY-PATH` | `master-reg-20260831-a-01` | succeeded | 114 | PASS | P0-P7完整路径，BEST候选交接。 |
| 2 | `MOCK-SHORT-MHC-HALT` | `master-reg-20260831-a-02` | succeeded | 8 | PASS | 长度守卫以结构化FAILED/HALT终止，不进入P0。 |
| 3 | `MOCK-SHORT-WARNING` | `master-reg-20260831-a-03` | succeeded | 114 | PASS | 长度守卫WARNING后继续完整路径。 |
| 4 | `MOCK-CONTEXT-HIGH` | `master-reg-20260831-a-04` | succeeded | 66 | PASS | 注入上下文，P2仅补跑S-16，随后从step15进入设计。 |
| 5 | `MOCK-CONTEXT-NONHIGH` | `master-reg-20260831-a-05` | succeeded | 82 | PASS | 注入上下文，P2补跑S-16并经P3重算结构依赖维度。 |
| 6 | `MOCK-NO-STRUCTURE` | `master-reg-20260831-a-06` | succeeded | 115 | PASS | P0从S-07进入S-08预测分支。 |
| 7 | `MOCK-LOW-STRUCTURE` | `master-reg-20260831-a-07` | succeeded | 76 | PASS | S-11跳过，R-57跳过设计，以WT_DESIGN_SKIPPED交接。 |
| 8 | `MOCK-BACTERIA` | `master-reg-20260831-a-08` | succeeded | 115 | PASS | P0执行S-06并解析细菌定位flag。 |
| 9 | `MOCK-MEMBRANE-SKIP` | `master-reg-20260831-a-09` | succeeded | 77 | PASS | R-57跳过设计，以WT_DESIGN_SKIPPED交接。 |
| 10 | `MOCK-MEMBRANE-CONFIRMED` | `master-reg-20260831-a-10` | succeeded | 114 | PASS | 明确确认后继续设计，最终BEST交接。 |
| 11 | `MOCK-POOR-RESCUE-SUCCESS` | `master-reg-20260831-a-11` | succeeded | 120 | PASS | 分支4筛选成功，执行S-08/S-11/S-09后继续。 |
| 12 | `MOCK-POOR-RESCUE-FAIL` | `master-reg-20260831-a-12` | succeeded | 117 | PASS | 分支4筛选失败，不执行补救结构链，但继续到EBB。 |
| 13 | `MOCK-DESIGN-RETRY-48` | `master-reg-20260831-a-13` | succeeded | 118 | PASS | P4重试一次，在48设计轮通过。 |
| 14 | `MOCK-DESIGN-RETRY-64` | `master-reg-20260831-a-14` | succeeded | 122 | PASS | P4重试两次，在64设计轮通过。 |
| 15 | `MOCK-DESIGN-ALL-REJECTED` | `master-reg-20260831-a-15` | succeeded | 100 | PASS | 32/48/64三轮全淘汰，跳过P5/P6，以WT_FAILURE_REPORT交接。 |
| 16 | `MOCK-EPITOPE-STRUCTURAL-FAIL` | `master-reg-20260831-a-16` | succeeded | 114 | PASS | P5标记epitope_violation硬排除。 |
| 17 | `MOCK-EPITOPE-PREDICTION-FAIL` | `master-reg-20260831-a-17` | succeeded | 114 | PASS | P5标记soft_penalty降权。 |
| 18 | `MOCK-VARIANT-SAFETY-FAIL` | `master-reg-20260831-a-18` | succeeded | 114 | PASS | P5标记safety_excluded硬排除。 |
| 19 | `MOCK-19B-SKIPPED` | `master-reg-20260831-a-19` | succeeded | 113 | PASS | P5跳过变体FoldX，执行无ddG降级排序链。 |
| 20 | `MOCK-SC10-WARNING` | `master-reg-20260831-a-20` | succeeded | 114 | PASS | 排序返回DEGRADED并标记SC10规则待确认。 |
| 21 | `MOCK-MD-RUN` | `master-reg-20260831-a-21` | succeeded | 115 | PASS | P6对top3执行S-32。 |
| 22 | `MOCK-MD-SKIP` | `master-reg-20260831-a-22` | succeeded | 114 | PASS | P6跳过S-32，直接进入阶段7。 |
| 23 | `MOCK-TOOL-TIMEOUT` | `master-reg-20260831-a-23` | succeeded | 19 | PASS | P0结构化返回TIMEOUT并在Master终态汇合，不继续P1。 |
| 24 | `MOCK-OUTPUT-MISSING` | `master-reg-20260831-a-24` | succeeded | 19 | PASS | P0结构化返回OUTPUT_MISSING，不能视为计算成功。 |
| 25 | `MOCK-OUTPUT-INVALID` | `master-reg-20260831-a-25` | succeeded | 19 | PASS | P0结构化返回OUTPUT_INVALID并停止后续阶段。 |

> 本报告只验证 Mock 契约和 Dify 路由，不代表真实科学计算已部署或通过验收。
