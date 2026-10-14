# P0-M1B：S-07 真实输出审计

> 审计批次：`p0-s07-m1b-20260901-b`  
> 生成时间：2026-09-01T09:32:52.028487Z  
> 性质：非生产取证；未部署；不包含结构分类、可用性判断、候选选择或流程路由。

## 1. 这次审计解决什么问题

此前无法确认 S07-D09，是因为还不知道候选工具一次真实运行会产生多少文件、文件有多大、
分页结果怎样展开，以及 entry、polymer entity、chain 和不同查询之间会出现哪些重复。
本批次只把这些事实保存下来，供下一轮讨论；它不替算法负责人决定任何科学规则。

## 2. 实际产生的文件

本批次共保存 **253 个文件**，合计 **10.4 MiB**，
识别出 **21 类文件**；其中空文件 7 个，
主要来自正常无 stderr/stdout 的调用记录。

| 文件类别 | 数量 | 合计大小 | 单文件中位数 | 最大文件 |
|---|---:|---:|---:|---:|
| afdb_confidence_json | 2 | 7.0 KiB | 3.5 KiB | 5.3 KiB |
| afdb_metadata_response | 3 | 20.5 KiB | 1.9 KiB | 18.5 KiB |
| afdb_model_cif | 2 | 487.7 KiB | 243.9 KiB | 355.0 KiB |
| afdb_pae_json | 2 | 451.2 KiB | 225.6 KiB | 412.4 KiB |
| audit_plan | 1 | 3.7 KiB | 3.7 KiB | 3.7 KiB |
| blast_archive | 4 | 984 B | 246 B | 246 B |
| campaign_metadata | 3 | 10.7 KiB | 4.0 KiB | 5.9 KiB |
| captured_http_request | 19 | 13.3 KiB | 655 B | 972 B |
| cli_stream | 10 | 475 B | 47 B | 95 B |
| exchange_record | 49 | 81.0 KiB | 1.7 KiB | 1.7 KiB |
| http_response_headers | 44 | 18.2 KiB | 340 B | 950 B |
| http_transport_stderr | 44 | 2.2 KiB | 52 B | 52 B |
| other_json | 7 | 8.9 KiB | 663 B | 4.2 KiB |
| protein_fasta | 4 | 957 B | 185 B | 460 B |
| rcsb_entry_metadata | 4 | 44.2 KiB | 11.0 KiB | 12.4 KiB |
| rcsb_mmcif | 4 | 7.6 MiB | 425.7 KiB | 6.6 MiB |
| rcsb_page_request | 19 | 13.3 KiB | 655 B | 972 B |
| rcsb_pagination_record | 5 | 5.1 KiB | 714 B | 2.5 KiB |
| rcsb_polymer_entity_metadata | 4 | 358.7 KiB | 90.2 KiB | 156.6 KiB |
| rcsb_polymer_instance_metadata | 4 | 53.3 KiB | 12.4 KiB | 21.6 KiB |
| rcsb_search_response | 19 | 1.3 MiB | 85.4 KiB | 118.5 KiB |

## 3. RCSB 分页事实

| 样本 | 报告总数 | 实收条目 | 页数 | 唯一 entity | 唯一 entry | 结束原因 |
|---|---:|---:|---:|---:|---:|---|
| P0-DISC-001 | 1136 | 1136 | 12 | 1136 | 1004 | REPORTED_RESULT_SET_EXHAUSTED |
| P0-DISC-002 | 236 | 236 | 3 | 236 | 235 | REPORTED_RESULT_SET_EXHAUSTED |
| P0-DISC-003 | 125 | 125 | 2 | 125 | 103 | REPORTED_RESULT_SET_EXHAUSTED |
| P0-DISC-004 | 0 | 0 | 1 | 0 | 0 | SUCCESSFUL_EMPTY_RESPONSE |
| P0-DISC-005 | 0 | 0 | 1 | 0 | 0 | SUCCESSFUL_EMPTY_RESPONSE |

跨样本重复出现的 polymer entity 有 0 个，
跨样本重复出现的 PDB entry 有 0 个。
这些数字说明“查询结果去重”不是简单删除重复文件：entity 和 entry 是不同层级，
同一 entry 还可能包含多个 entity。这里仅记录现象，没有确定正式去重键。

## 4. 文件重复事实

排除空文件后，共发现 23 组字节完全相同的文件，
对应 70 个重复副本。字节重复只说明内容相同，
不代表这些文件在业务上可以合并；请求来源、对象层级和运行批次仍需保留。

## 5. 结构与其他来源的输出组成

RCSB 的 4 个冻结观察对象共产生 16 个响应正文，合计 8.0 MiB。
AlphaFold DB 检查了 3 个明确给出的标识；
本地 BLAST 检查了 4 个样本，并同时保留原始归档、表格和 JSON（存在时）。
这些观察对象来自已冻结的 P0-M1 代表样本，只用于查看输出组成，不表示本次工具选中了它们。

## 6. 可追溯性现状与缺口

共检查 49 条 HTTP/CLI 调用记录，发现 0 个记录完整性问题。每个非报告文件都已进入
清单并计算 SHA-256。BLAST 使用的程序、数据库文件和 discovery profile 另有依赖清单。

目前仍有两个明确缺口：

- RCSB 与 AlphaFold DB 是在线可变数据源。本批次保存了请求、响应、时间和哈希，但没有冻结整个远端数据库版本。
- 只对 4 个预先冻结的代表对象下载了完整结构元数据与坐标文件，并未为每个搜索命中都下载结构文件。

## 7. 回到 S07-D09 时需要确认什么

现在已有证据可以逐项讨论以下问题：

1. 主结果中保留哪些轻量候选信息，哪些原始分页响应和大文件只通过产物引用提供。
2. entity、entry、chain/model/assembly 是否需要分别建立身份键，而不是使用一个全局去重键。
3. 一次查询快照至少保存哪些请求、分页、来源时间、数据库/工具版本和文件哈希。
4. 分页对调用方采用哪种机制，以及审计保护上限与正式生产上限如何分开管理。

在这些事项由 wing 评审确认前，本报告不把任何候选方案写成正式契约。D11-D17 仍等待
算法/产品负责人反馈，因此本批次也不能进入 P0-M2 生产编码。

## 8. 机器可读证据

- `artifact_inventory.json`：逐文件路径、类型、大小与 SHA-256。
- `output_audit.json`：分页、层级重复、来源输出、BLAST 和调用完整性摘要。
- 原始请求与响应位于本批次的 `requests/` 与 `evidence/` 目录。
