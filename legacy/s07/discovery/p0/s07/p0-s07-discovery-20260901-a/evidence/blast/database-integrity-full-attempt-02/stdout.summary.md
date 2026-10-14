# BLAST 数据库完整性校验 attempt 02 摘要

- 命令退出码：`1`。
- 全量逐 OID 校验运行至最后一个 OID `1090948`，逐条状态均为 `PASS`。
- 唯一报告错误来自元数据检查：缺少 taxonomy 数据库时无法解析 `Taxid 9606`。
- 原始标准输出为 121,076,114 字节，SHA-256 为
  `f1b747de3571253544e94c35b947f9daf8652c399cc335e0e9c9ed1bf3e9c06b`。
- 原始标准输出已移入仓库内被忽略的受控制品区，位置记录在同目录 `exchange.json`。
- 补齐 NCBI `taxdb` 并设置 `BLASTDB` 后，`database-integrity-full-attempt-04`
  退出码为 `0`，完整性校验通过。

本次失败属于运行依赖缺口，不应解释为序列数据库内容损坏。
