# AI 操作性能与大历史验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-22
- 最后更新：2026-11-22
- 关联文档：[AI 运行说明](../../../docs/current/engineering/ai-runtime.md)、[裁决接口](../../../docs/current/engineering/ai-rulings.md)

## 交付范围

AI v3 在[冻结目录](../ai-performance-interface-snapshot/v3/source.json)保留 223 个文件及 SHA256，清单摘要为 `3130b6d4175d0082ee5988dec1fc7b2167e76e92e804507297cfcbb90b10b239`。包侧和引擎侧分别联测，不修改它们施工中的源码。最终回归依赖 engine-performance-interface-snapshot/v2；早期对照依赖在各 `*-source.json` 中注明。

已实现：活动/归档紧凑分页和单项详情；同 generation 只读快照与请求归属索引；有界、按内容摘要复用的成功 Schema 校验；事务少一次中间复制；同一次配置三检共享 A 结果；任务终态和当时轨迹同次提交；有版本历史分片；交付证明明确写集合快路。过程 timeline 原来已在内存聚合，不把既有行为算作本轮新增。

紧凑卡片保留高危标识/riskTags、审核会话、归档关系及经授权复验的成功凭证；加载详情后才可批准。Python、HTTP、Web SDK 的参数与权限边界统一见上方裁决文档。无参数旧列表保留兼容。

## 实测方法与边界

[benchmark.py](benchmark.py) 使用相同合成设计、独立源码树及进程，100 / 1000 / 10000 条合法运行批次，每项一次初始调用加 30 次后续调用。批次共享一个请求/上下文，不能代表一万名用户、一万会话或所有配置大小。原文、基线及 digest 正常构造，未使用游玩存档，外部模型调用 **0 次**。

基线列表返回全部记录，优化列表返回 20 张紧凑卡片；详情基线先取全列表，优化只投影目标项。这是实际读取方式改变，不是相同完整响应序列化的纯函数竞速。时延为本机 Python 服务调用，不含 HTTP、浏览器或模型推理。并行回归和机器负载存在波动，P95 使用 30 样本第 29 小值；初始调用单列，不混入 P95。`readSnapshot` 只测显式只读缓存访问，不能当作完整历史复制耗时。

下表来自 [comparison.json](comparison.json) 和 [v2 原始样本](v2-benchmark.json)，单位毫秒。最终 v3 的交付证明路径另测，避免混用版本。

| 数量 / 操作 | 基线 P50 / P95 | v2 P50 / P95 |
| --- | ---: | ---: |
| 100 / 列表 | 20.67 / 25.15 | 4.81 / 7.47 |
| 1000 / 列表 | 192.98 / 356.23 | 4.67 / 6.16 |
| 1000 / 详情 | 188.22 / 200.72 | 2.16 / 3.13 |
| 1000 / verify | 893.57 / 1038.28 | 143.13 / 151.28 |
| 1000 / 三次任意 update 的事务 | 1612.32 / 2082.72 | 394.55 / 429.54 |
| 10000 / 列表 | 8 MiB 限制，无法写入 | 7.34 / 10.17 |
| 10000 / 详情 | 同上 | 3.10 / 3.44 |
| 10000 / verify | 同上 | 1417.91 / 1712.23 |
| 10000 / 三次任意 update 的事务 | 同上 | 5278.54 / 6526.25 |

10000 条逻辑状态约 19.2 MB。基线容量三档为 2/3，v2 为 3/3；容量拒绝不伪记为查询成功。1000 条列表响应从约 1.35 MB 降至 20.8 KB。初次构建索引/复制只读视图仍有成本，v2 万条列表初始调用为 275 ms。

## 交付证明窄写与万条验证

v2 的首次 `delivered=True` 虽只保存 30 条摘要证明，仍全量复制/验证 19 MB，曾测得活动 6.06 秒、归档 4.25 秒。记录保留在 [large-history.json](large-history.json)，这里的“首次”指首次保存该页交付证明，之前已加载历史。

v3 用 `update_delivery_receipts` 合并 `rulingDeliveries` / `messageDeliveries`；两个集合可共享一次原子提交。原 generation 必须已通过全验证，新 JSON 检查实际聚合深度与体积，未变历史保留引用。一般业务更新、旧发布时间迁移和任意事务仍全验证；在已有事务内调用会退回原事务。不能把此前三次任意 update 的 6.53 秒宣称为已优化到毫秒。

已加载历史的 v3 首次交付测得活动 34.13 ms、归档 21.21 ms，后续 30 次 P95 为 14.74 / 15.08 ms，见 [delivery-large-history.json](delivery-large-history.json)。另外在同一最终引擎上清空 Repository 读缓存和裁决索引，分别测活动/归档首次交付和 30 次后续读取，原始证据为 `delivery-cold-v2.json` / `delivery-cold-v3.json`，对照由 summarize.py 重算。v3 活动首次 **320.12 ms**、后续 P50/P95 **10.67/14.98 ms**；归档首次 **368.56 ms**、后续 **12.86/16.73 ms**。v2 同口径为 17889.43 / 14824.94 ms，采样期间负载高且之后发生运行中断；保留原始结果，不把比例视为严格空机器 A/B。它测服务已打开后的空读缓存，不含启动时完整磁盘审计。

[large_history.py](large_history.py) 的每轮验证包含 8 个场景：超 8 MiB 写入；100 页无遗漏/重复；活动/归档各 5000 且计数正确；实际交付与玩家拒绝；逻辑备份逐内容相等恢复；宿主配对备份、新 scope 及原文附件；同目录重启后保留失效原文并拒绝旧审批；撤权后隐藏原文和动作。已完成轮次均为 8/8，最终计数见 [verification.json](verification.json)。

## 回归与失败处理

全量与每轮失败均保留 XML 和源码哈希，禁止相加当作独立覆盖。v2 全量 **740/740** 通过（[release-core.xml](release-core.xml)）；v3 新写集合与历史专项分别 **54/54、46/46、27/27**，最后一轮包含实际 `os._exit` 强退。最终 **AI v3 + engine v2 全量 753/753（100%）通过**，耗时约 375 秒，见 [release-v3-recovered.xml](release-v3-recovered.xml)、[完整日志](release-v3-recovered.log) 与 [冻结来源](release-v3-recovered-source.json)。仅有已存在的 Starlette/httpx 弃用提示，无跳过或失败。

| 发现 | 当时证据 | 修复与复验 |
| --- | --- | --- |
| 两次驱动引用不存在的测试文件 | first.xml、segments-optimized.xml（0 用例） | 核对实际文件名后重跑，不计为产品失败或通过 |
| 旧最小 Context 请求缺 sourceId，索引触发 KeyError | core.xml 723/725、memory-check.xml 7/8 | 恢复无来源请求的兼容分支；memory-fixed 14/14，后续全量通过 |
| 万条超过原 8 MiB 聚合限制 | baseline/adapted-benchmark.json | 分片格式 2、128 MiB 内部聚合；旧档、配额、备份、故障和万条实测 |
| 单条内容变短导致后续分片边界全部移动 | segments-verified 120/121、segment-analysis.xml、core-v2 738/739 | 改为按键稳定分桶；segments-partitioned 20/20，v2 全量通过 |
| compact 缺高危标识、审核会话和成功凭证 | 包侧审查反馈，原 v1 冻结保留 | 与详情共用风险分类，保留字段；compact-metadata 55/55 |
| 最终两项运行中断，没有产生 XML/最终样本 | release-v3-core-source.json、原进程在会话恢复后已不存在 | 不报通过；保持冻结源码，另建 recovered 标签补跑全量与空缓存冷读，日志一并保留 |
| 首次交付 30 条证明触发整库写入 | large-history.json | 明确写集合快路；保留通用全验证，差分校验、非法写集合、未知 generation、故障和恢复专项通过 |

运行中的失败按错误码反馈，不用“通过”覆盖拒绝：来源变化重新查询后建新候选；撤权禁止回退读取；无效游标重新取第一页；格式/摘要/引用损坏停止打开并核对完整备份；配额拒绝保持旧代。提交后丢失应答先读取原 generation/回执，不能换请求 ID 重放业务动作。测试中发现的问题保存原 XML/source，修复后另起标签复验；未完成或失败的轮次不改写为成功。

## 存储和验收限制

- 聚合上限 128 MiB，单文档/分片仍 8 MiB，默认目录总配额 512 MiB；旧代和故障遗留完整分片不自动清理。普通业务事务仍随总状态增长。
- 小版本 2 清单布局兼容：新 reader 可读完整旧档和旧分段布局；旧程序不能理解分段清单。目录备份必须包含 objects-v2 与所有 generations；推荐逻辑导出或宿主配对备份。
- 打开存储仍校验代链并重建/校验当前引用数据；不是磁盘按页查询，也没有证明所有历史代的对象内容都已逐个重读。真实强退不等于断电故障测试。
- 未落盘过程事件在硬退出后可能缺失；终态提交和最终事件保存有明确边界，不伪造轨迹。模型成功率、网络稳定性和包侧 UI 由各自验收记录支持。

## 复现

项目根目录运行；输出在本目录，work/ 为忽略的隔离目录，不含正式存档：

```powershell
engineering/.venv/Scripts/python -X utf8 -B engineering/acceptance/ai-operation-performance/run_tests.py --label 自定义唯一标签 --engine engineering/acceptance/engine-performance-interface-snapshot/v2 --ai-source engineering/acceptance/ai-performance-interface-snapshot/v3 --core
engineering/.venv/Scripts/python -X utf8 -B engineering/acceptance/ai-operation-performance/summarize.py
node engineering/acceptance/ai-operation-performance/verify-client.mjs
```

benchmark.py / large_history.py 的 `--tree` 指向 run_tests.py 创建并记录在 source.json 的隔离树。保留每轮原始样本、失败及冻结来源；不复用正式房间做性能实验。
