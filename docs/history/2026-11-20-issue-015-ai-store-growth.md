# ISSUE-015：AI 累计快照配额故障与全历史无损压缩

- 文档类型：历史
- 状态：已修复并验证，已归档
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 归档日期：2026-11-20
- 替代关系：当前行为以[存储工程说明](../current/engineering/first-test.md#5-管理和恢复)和[压缩验收](../../engineering/acceptance/store-compaction/README.md)为准。
- 关联文档：[问题索引](../plans/Issues/README.md)、[本轮总报告](../../engineering/acceptance/ai-runtime/repair-20261120.md)

## 原始故障

树桩镇隔离单房间连续配置矩阵在 158 代 AI 快照后返回 STORE_FULL，HTTP 对外为 STORAGE_UNAVAILABLE。累计 527106299 字节，最新一代 7019617 字节，默认配额 536870912 字节。单独分批通过不能证明累计缺陷已解决。原始失败与配置案例保留在[首轮结果](../../rulepacks/stumpsville/tests/ai-config-matrix-results.json)及隔离目录 `rulepacks/stumpsville/tests/output/ai-config-matrix-dbe1cfea/`。

## 协调与实现

先登记 ISSUE 并唤起引擎会话。引擎曾考虑检查点截断旧代；自动审批拒绝不可逆历史删除，未执行该方案。原授权协调会话接手并改为无损压缩：逐代核验完整摘要链，在单写锁内发布 gzip 副本、同步和回读原字节，再移除冗余原文件；所有历史代、原始字节、head 与 CAS 都保留。最近两代默认不压缩，AI Repository 仅在下一提交将超过配额时自动触发；其他 FileDataStore 调用者默认关闭。

不裁剪业务历史、不改正式存档、不用调高配额掩盖问题。原 JSON 链可直接读取；压缩后的混合链需新版读取器，旧程序回退须使用兼容版本导出并恢复到独立目录。真正空间不足或损坏仍明确失败。

## 验收结果

- 压缩专项 15/15：原始字节、锁、CAS、备份恢复、累计写入、7 个故障点、损坏和真实配额。
- 管理查询专项 8/8；追加 AI 与引擎联合回归 226/226，其中 AI 158、引擎 68。见[初验](../../engineering/acceptance/ai-runtime/query-storage-initial-20261120.xml)、[回归](../../engineering/acceptance/ai-runtime/query-storage-regression-20261120.xml)。
- 对原失败目录的隔离副本验证：158 代全部原始字节保留，占用从 527106299 降至 143448602 字节；再提交 12 代后关闭重开成功，审计/回执等非实验数据不变，原目录每代摘要未变。见[机器结果](../../engineering/acceptance/store-compaction/large-fixture-results.json)。

## 有效限制

完整历史和当前业务状态继续增长，压缩需要临时空间；这不是无限容量保证。加载仍校验完整链，大仓库加载/首次压缩可能较慢。未做断电硬件实验。保留外部备份，后续容量治理依据实际数据增长另行设计；禁止手工删链中间代。
