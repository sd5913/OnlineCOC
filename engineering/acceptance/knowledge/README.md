# ISSUE-011 首版验收记录

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-17
- 最后更新：2026-11-17
- 关联文档：[现行接口与边界](../../../docs/current/engineering/player-knowledge.md)、[施工记录](../../../docs/history/2026-11-17-player-knowledge-construction-plan.md)、[机器汇总](results.json)

首版 K0—K5 已完成。宿主、文件存储、HTTP/WS、SDK及联网边界共176项去重测试通过；AI模块384项去重测试通过；Stumpsville另有12组严格知识验收及8组场景回归，覆盖18个预设行动。上述组数、性能循环和阶段复跑不累加为测试数。机器汇总保存用例标识、原始失败、复验关系及源码摘要。

测试只使用独立合成存档、临时目录、回环网络和确定性模型。没有修改正式房间、调用付费模型或部署云端。P2P覆盖本机真实WebRTC与宿主代理，web覆盖受限路由及包静态导出；本轮没有重新验证真人异地网络或公网基础设施。

文档收口检查覆盖项目文档、AI入口、包侧现行说明和本验收报告，共100篇，相对文件链接无断链。工程/AI计划和ISSUE-011已归档，目录清单已登记全部新增知识服务文件与验收产物。

## 阶段结果

| 范围 | 最终证据 | 结果 |
| --- | --- | --- |
| 宿主、聊天、Lua/Flow、文件恢复、格式、知识 | [backend-release.xml](backend-release.xml) | 129通过 |
| AI宿主批准、发布、恢复、备份 | [ai-host-regression.xml](ai-host-regression.xml) | 28通过 |
| 联网、web限制和资源边界 | [network-retest.xml](network-retest.xml)、[network-paths.xml](network-paths.xml) | 17项去重通过；前者2项环境失败由后者复验覆盖 |
| SDK账号切换及WebRTC原流程 | [sdk-sessions.xml](sdk-sessions.xml) | 2通过，其中WebRTC用例与上行重复 |
| WS最终end排队后撤权 | [ws-enqueue.xml](ws-enqueue.xml) | 1通过；排队前撤权已包含在129项 |
| AI消费与组件 | [AI汇总](../ai-runtime/known-results.json) | 384项去重通过 |
| 配置包及第二示例 | [严格知识](../../../rulepacks/stumpsville/tests/strict-known-results.json)、[场景](../../../rulepacks/stumpsville/tests/scene-results.json)、[证词示例](../../ai/examples/knowledge-investigation.py) | 12组、8组通过；证词示例在AI运行时测试中验证 |

初次后端备份比较只归一化AI scope，新增知识scope后预期过期；修正为同时验证并归一化独立知识scope，最终129项通过。初次浏览器缺少捆绑Chromium，改用已安装Edge；新联网夹具子进程缺少aiohttp导入路径，补齐后3项通过。初次AI全量383/384，剩余操作台测试遗漏KP“转交AI”，修正后两项通过。原始XML保留，不将失败记录改写为通过。Starlette的httpx弃用提示仍存在，不影响本轮结果。

## K-01—K-27覆盖

此表对应计划验收义务，不等于函数数量。`core`指[宿主知识测试](../../backend/tests/test_knowledge.py)，`network`指[HTTP/WS/迁移测试](../../backend/tests/test_knowledge_network.py)，`edges`指[补充负例](test_edges.py)。AI详细对应见[AI现行验收说明](../../../docs/current/engineering/ai-player-knowledge.md)。

| 编号 | 证据与结果 |
| --- | --- |
| K-01 | core `test_k01_empty_and_k24_no_ai`；无策略沿用legacy行为 |
| K-02 | core `test_k02_k03_subject_and_legacy_exit`；Stumpsville未揭示地点及原始view负例 |
| K-03 | core主体隔离、network HTTP跨玩家ref、edges跨账号cursor、AI运行时复制引用 |
| K-04 | core `test_k04_fixed_versions_and_k20_archive`；包侧改正文后旧资料与UI不变 |
| K-05 | core `test_k05_live_revisions_and_eligibility`；本人表与公共回合显式订阅 |
| K-06 | core `test_k06_equivalent_grant_and_k14_unrelated_change`；等价grant逐一撤回 |
| K-07 | core `test_k07_forgery_and_k08_dedupe`；PL命令与伪造来源拒绝 |
| K-08 | 同上；命令幂等、参数碰撞、来源/策略修订及事件去重 |
| K-09 | core提交前/后故障、原生动作与管理操作自动观察同事务；既有文件故障恢复 |
| K-10 | core持久策略、提供方缺失/异常；AI能力故障拒绝与旧引用复验 |
| K-11 | core未来匹配对象、策略冲突；edges重绑定使旧引用/cursor失效 |
| K-12 | core成员重建与scope；network登录权限；SDK账号切换/退出负例 |
| K-13 | AI会话绑定owner与KP查看PL会话测试；宿主聊天室参与者回归 |
| K-14 | core无关变化保持固定资料；AI上下文只读依赖与原批准基线28项回归 |
| K-15 | core `test_explicit_live_entity_compatibility_and_revoke`、操作/旧回执负例；撤权后viewToken与完整实体资格失效 |
| K-16 | AI运行时发送前、工具后、在途返回与历史复用撤权；实际模型payload断言 |
| K-17 | network排队前撤权发reset；[排队后屏障](test_ws_boundary.py)证明无法收回已排队end、随后新视图删除资料；[SDK竞态](test_sdk_sessions.py)验证旧连接/临时块/旧异步结果不跨账号 |
| K-18 | core规则输入/结果/旧回执和显式denied优先；strict关系/进度/wait/目录过滤；合法主机计算保留 |
| K-19 | core受控素材URL、edges旧聊天卡/角色名；联网资源边界、Stumpsville原始静态导出与AI指南不分发 |
| K-20 | core原对象归档与来源硬约束；快照不可读时拒绝而不回填最新正文 |
| K-21 | core容量、分面/观察大小，edges查询64KiB与原子拒绝，机器schema未知字段/布尔revision拒绝 |
| K-22 | core成员/恢复作用域、network完整备份恢复；包重启且AI关闭后知识保持 |
| K-23 | network三种v3转换保留源字节；包旧地点记录不授权，KP确认后“现在揭示” |
| K-24 | core独立知识服务；包AI关闭重启/查询；本轮真实模型调用0次 |
| K-25 | 非地点证词示例固定版本，AI `test_known_runtime.py`第二包测试 |
| K-26 | AI严格证据输出/伪造引用/跨主体/旧历史/自由文本拒绝；组件详情标签同版本 |
| K-27 | 129项宿主、28项AI宿主、17项联网、384项AI模块及场景8组回归均通过 |

## 复现入口

从项目根目录运行，使用已安装的工程与联网独立虚拟环境。测试自动创建临时房间，不传入正式数据目录。

```powershell
engineering/.venv/Scripts/python.exe -B -m pytest engineering/backend/tests/test_host.py engineering/backend/tests/test_foundation.py engineering/backend/tests/test_faults.py engineering/backend/tests/test_model_contracts.py engineering/backend/tests/test_adapters.py engineering/backend/tests/test_chat.py engineering/backend/tests/test_chat_network.py engineering/backend/tests/test_network.py engineering/backend/tests/test_room_versions.py engineering/backend/tests/test_knowledge.py engineering/backend/tests/test_knowledge_network.py engineering/acceptance/knowledge/test_edges.py -q -p no:cacheprovider
engineering/.venv/Scripts/python.exe -B -m pytest engineering/backend/tests/test_ai_approval.py engineering/backend/tests/test_ai_publication.py engineering/backend/tests/test_ai_recovery.py engineering/backend/tests/test_ai_backup.py -q -p no:cacheprovider
engineering/.venv/Scripts/python.exe -B -m pytest engineering/acceptance/knowledge/test_ws_boundary.py -q -p no:cacheprovider
$env:PYTHONPATH="$PWD/engineering/network-p2p/src;$PWD/engineering/network-web/src"
$env:P2P_REAL_HOST_TEST='1'
$env:PLAYWRIGHT_CHANNEL='msedge'
engineering/network-p2p/.venv/Scripts/python.exe -B -m pytest engineering/acceptance/knowledge/test_network_paths.py engineering/acceptance/knowledge/test_sdk_sessions.py engineering/network-p2p/tests/test_sdk.py -q -p no:cacheprovider -o asyncio_mode=auto
engineering/.venv/Scripts/python.exe -B engineering/acceptance/knowledge/benchmark.py
```

上述最终执行均退出0；历史失败详情见XML和[机器汇总](results.json)。AI与包的复现入口见各自验收文档。性能脚本会重建隔离中样例并更新本目录performance.json；`--cold-only`补充独立新进程冷开和一次完整观察提交测量。

## 性能及交付边界

[performance.json](performance.json)记录Windows、CPython 3.14.2、20主体/1,000资源/5,000授权、知识3,009,599字节、Room提交3,378,223字节、WS投影23,337字节。每项100次：warm search/read/recheck p95约71.5/68.9/70.4 ms；legacy同机基线67.4 ms，门槛154.8 ms，全部通过。每请求捕获一次存储快照；批量proof复验专门断言一次来源捕获，结构缓存不缓存权限。

新进程冷开约2.06秒；同规模新增一次观察命令约1.44秒，其中文件提交约443 ms。首版继续使用全量文件代，未引入数据库，不承诺大型高频房间的低写延迟。

后端为0.3.0/Room v4。旧v3必须显式转换到新副本，再绑定提供方并由KP选择现在揭示；没有查询时自动升级。受控二进制资料、角色级知识、自由生成事实摘要和场景未来信息订阅未开放。已发送给用户/服务商的内容不能追回；撤回约束后续供给。正式升级操作见[房间格式](../../../docs/current/engineering/room-format.md)，本轮不执行正式部署。
