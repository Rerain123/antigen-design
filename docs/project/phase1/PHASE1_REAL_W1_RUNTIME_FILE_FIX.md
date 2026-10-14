# B1 回归发现的运行层临时文件误判修复

本轮 [B1 评审准备](PHASE1_REAL_W1_B1_REVIEW.md)的全量回归暴露 W1-09A 的偶发工程问题，
实际检查与最终结果见 [维护记录](PHASE1_REAL_W1_B1_VERIFICATION.json)。科学规则、工具注册与接口 Schema 未改变。

## 问题与修复

原 no_links 把普通文件 st_nlink 不等于 1 全部视为硬链接。Windows 上 SQLite 连接开闭时，
WAL/SHM 正在消失的目录项会短暂返回 st_nlink=0；因此正常查询/恢复也可能报 FORBIDDEN。
首次全量回归出现 2 项失败；独立 SQLite 侧文件开闭探测观察到 411 次零链接计数，没有创建任何硬链接。
原始命令、失败、JUnit 和探测程序/观察保存在
[runtime-fix](../../../discovery/t01-phase1-real/w1/b1-review-20260905/runtime-fix)。

修复将路径预检的“多链接”条件改为 st_nlink>1；对于读取的输入/产物文件，
再在已打开、禁止并发改写/删除的句柄上用 fstat 要求链接数恰为 1，之后才读取字节。
这既处理临时目录项，也保持实际硬链接、重解析点、跨路径和字节/hash 校验；不放宽科学执行或文件消费资格。

新增回归覆盖零链接元数据、路径元数据不完整时实际句柄仍拒绝硬链接、普通硬链接预检，
以及历史源码登记不能越出证据根。原有并发、取消、超时、恢复和产物负测继续执行。
修复后实际 CLI 验收记录在 [新批次](../../../discovery/t01-phase1-real/w1/runtime-file-fix-20260905/README.md)。

## 原证据如何保持可复验

修改前先逐一比对原 W1-09A manifest 的全部 16 份源码/测试/来源，按原路径归档到 runtime-fix/before。
原 manifest、CLI、输入输出和原验证结论保持不变。
[历史源码索引](../../../discovery/t01-phase1-real/w1/runtime-source-history.json)以证据 manifest 的 SHA-256 精确选择旧执行源码；
检查器输出 ARCHIVED_EXECUTED_SOURCES，表示核验历史执行版本。未登记历史快照的新证据继续核验当前仓库源码。

旧证据核验通过只证明旧执行记录完整，不能当作当前修复版本的通过；当前版本使用新 CLI 批次和本轮根测试。
execution_profile 的源码 hash 随修复变化；任务必须按匹配的 profile 提交，不篡改旧任务档案来复用新代码。
