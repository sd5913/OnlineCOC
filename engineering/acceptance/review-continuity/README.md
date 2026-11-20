# 审核连续性、引用扩展与通知批次验收

- 文档类型：验收记录
- 日期：2026-11-20
- 关联：[会话与批次](../../../docs/current/engineering/ai-session-access.md)、[引用嵌入](../../../docs/current/engineering/ai-pack-embedding.md)、[引擎通知](../../../docs/current/engineering/notifications.md)
- 机器结果：[results.json](results.json)，含逐例结果、旧测试更名映射、每轮分母、失败及生产源码 SHA-256。

## 当前结果

本目录最新去重 **187/187 通过（100%）**，这是确定性与真实 Host/Edge 的代码验收成功率，不是大模型成功率。本责任者未调用真实服务商；配置包侧统一记录 DeepSeek flash/pro 的调用、用量及生成成功率，不与本计数相加。

| 范围 | 证据与结果 |
| --- | --- |
| 大范围回归 | [regression-first.xml](regression-first.xml)：149/150，唯一纯读取约定差异在下轮修复 |
| 受影响复验 | [final.xml](final.xml)：49/49，含配置精确编辑、历史和通知 |
| 真实联测发现的状态缺陷复验 | [status-final.xml](status-final.xml)：69/69；生成中状态、新候选、撤权与旧回答同时验证 |
| 最终历史安全与重启 | [security-final.xml](security-final.xml)：19/19 |
| 引用、历史提示、通知候选与顶部调试 | [ui.xml](ui.xml)：7/7；最终引用界面 [reference-final.xml](reference-final.xml)：4/4 |
| 短确认完整纠错链 | [model-repair.xml](model-repair.xml)：1/1；拒绝无新读取的候选，读取目标后生成待批次，批准后仅通知 player1 一次 |

重复用例按最后结果计数；旧会话测试重命名通过 testAliases 对齐，不直接相加各轮总数。隔离宿主位于 engineering/ai/.test-output/，没有修改正式存档或持久服务配置。

## 行为覆盖

- 管理员旧回答在普通版本变化后可读并有过期提示；短确认携带历史意图，不携带旧事实作为新执行证明。
- 旧 sourceRefs、read 参数兼容；新搜索保留身份；旧搜索摘要变化且无身份记录时明确拒绝恢复。
- 删除对象、改变可见类别、授权代际变化、外发关闭、服务切换、会话删除、跨 scope 均不能恢复正文；生成期间持续复验。只读取其他角色不能授权修改目标角色。
- 旧上下文不能直接批准执行；严格玩家知识撤回及同目录重启继续回归。
- renderReference 接收完整授权 DTO 副本；宽/窄界面、输入预览、默认回退、异常、只读参数、技术详情、失权和迟到结果清理均检查。
- notification.send 独立审核，只绑定同批此前支持的宿主修改；不能伪造源命令，PL 不能审批，失败/拒绝不通知，目标隔离，重复批准不多发，响应丢失只按原回执对账。

## 首轮失败及处理

| 原始证据 | 失败与修复 |
| --- | --- |
| [history-initial.xml](history-initial.xml) | 2/2 原始复现失败：界面及下一轮模型均失去旧回答；修复只读历史与意图分离 |
| [reference-renderer-interrupted.json](reference-renderer-interrupted.json) | 浏览器测试脚本等待未完成函数；保留已观察的两项通过，第三项未完成；修正脚本后 [3/3](reference-renderer-core.xml) |
| [history-first-fix.xml](history-first-fix.xml) | 18/19；补丁路径错误使旧“应丢弃回答”断言未更新；修正路径及行为预期后通过 |
| [notification-first.xml](notification-first.xml) | 11/12；测试误读 source 嵌套字段；按真实 DTO 修正 |
| [core.xml](core.xml) | 26/27；测试复用已关闭协调器超时；按实际运行时方式重建后通过 |
| [regression-first.xml](regression-first.xml) | 149/150；新增凭据修改了配置纯读取函数的输入；移到协调器附加，49项复验通过 |

首轮真实模型联测发现：新任务把历史意图的旧资料过期误当成自身过期，公开状态提前变成 stale。两模型第一例均通过，第二例因此提前停止，不能判作模型语义失败；配置包保留调用记录并在源码再冻结后复测。本地 [status-initial.xml](status-initial.xml) 保存 3/3 修复前失败，69项关联复验通过。historyIntents 现只递归核对查看授权；只有 historyContexts 事实依赖传播过期。

## 失败流程与边界

历史恢复不改写原 context，也不恢复旧批准。HISTORY_REQUERY_REQUIRED 在原修复额度内要求读取目标；HISTORY_PROVENANCE_INCOMPLETE 显示兼容原因，由用户重新描述意图并查询当前资料。删除、撤权、跨 scope 保持隐藏。

旧 search/chat 没有身份且摘要改变时，无法证明原受众；严格玩家证据、复合事件、包投影和配置子树仍保守精确复验。不是旧存档全量迁移。

通知 sourceActionIndex 从 0 开始，源命令由真实回执派生。带 flowId 的启动回执不能证明业务完成。通知失败不回滚已成功修改；partial/unknown 先核对原回执，禁止重放原动作。AI 不能用独立新批次重绑上一批动作补发；需 KP 核对原结果，通过宿主通知接口使用原 commandId 处理。配置 draft 发布尚未接入同批运行时通知。

## 复验方式

项目根目录运行 engineering/.venv/Scripts/python.exe -X utf8 -B -m pytest，使用 -q -p no:cacheprovider，为 --basetemp 和 --junitxml 指定新路径。核心测试为 test_history_continuity.py、test_batch_notifications.py、test_reference_renderer_ui.py；关联回归逐例清单在 results.json。不得覆盖首轮失败证据。


## 配置包联合实测交付

下表依据配置包责任会话在全部测试进程结束后的交付，原始报告由包侧维护。本目录的 187 项不等同于下列模型成功率。

| 模型／轮次 | 端到端用例 | API 调用／tokens | 失败与处理 |
| --- | --- | --- | --- |
| Flash 首轮 | 1/2 | 7 / 102603 | 第二例被 API stale 状态提前终止；工程状态修复 |
| Pro 首轮 | 1/2 | 12 / 202140 | 同上，不能判作模型语义失败 |
| Flash 状态修复后 | 1/2 | 14 / 231725 | 第一例猜造 sv.world/addPips，被语义审核拦下，未执行；补包指南 |
| Pro 状态修复后 | 1/2 | 20 / 324478 | 第一例再次询问钱币字段，未执行；达到32次上限，不追加调用 |
| Flash 术语说明更新后 | **2/2** | 11 / 169882 | 原玩家申请和过期短确认均正确，通知及重复批准检查通过 |

合计 **64 次、1030828 tokens**。跨版本全部用例尝试为 6/10（含两次 API 状态中断），不作为同版本模型优劣比较。Flash 最新 2/2；Pro 最新 1/2，未使用最终包指南重新验证，不宣称全部模型通过。正式服务商配置字节未改变。

两模型都已通过过期短确认链：旧回答可读 → 短句确认 → 重新查询 player2 → 待审 +2 与独立通知 → 批准只影响目标 → 再批准不重放。包侧整包 UI 14/14、真实宿主通知6/6、原提示10/10、语义引用6/6；分组保留，不并入本目录去重计数。

原始交付：[Flash报告](../../../rulepacks/stumpsville/tests/review-identity-live-deepseek-flash-results.json)、[Pro报告](../../../rulepacks/stumpsville/tests/review-identity-live-deepseek-v4-pro-results.json)、[整包界面报告](../../../rulepacks/stumpsville/tests/ruling-workspace-results.json)。各轮失败及重试均保留，不能用最终成功覆盖先前调用。
