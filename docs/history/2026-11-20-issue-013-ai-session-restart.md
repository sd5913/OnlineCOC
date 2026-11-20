# ISSUE-013：AI 会话重启后的历史读取与继续对话

- 文档类型：历史
- 状态：已归档
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 原路径：docs/plans/Issues/issue-013-ai-session-restart.md
- 原状态：进行中
- 归档日期：2026-11-20
- 归档原因：引擎只读历史接口和 AI 消费接线已实现并完成联合验收
- 替代文档：[会话与重启](../current/engineering/ai-session-access.md#同房间重启与历史)
- 关联文档：[AI 会话](../current/engineering/ai-session-access.md)、[问题索引](../plans/Issues/README.md)

## 已复现

同一隔离宿主、同一目录、同一包连续生成两轮 kind=plan，关闭 Coordinator、Proposals、Host，再从原目录创建 Host/Proposals/Application。会话和请求仍在，第二轮回答被标 stale；新需求构造历史时旧回答被遗漏。首次自动化失败见 engineering/acceptance/ai-runtime/restart-initial.xml，复现测试 engineering/ai/tests/test_session_restart.py。

源码链：Application.tasks → Host.validate_ai_sources → AI access.validate_context → 对 historyContexts 调用 publication.check_context。该发布校验要求 context.authorityEpoch 等于本次进程 host.epoch，重启后必变。因此多轮历史在资料、授权、scope 未变化时仍不可读取。Context.history 同样复用发布校验。截图另有 SOURCE_STALE，需包侧继续排除包快照/资料摘要变化，不能据此断言所有旧来源都可恢复。

## 预期与安全边界

同一房间重启可继续读取仍获授权且来源未变的历史；不要伪造新 epoch 或改写持久旧上下文。旧批准和旧运行时批次不得因历史恢复而重新可执行。scope 分叉、身份/权限撤销、知识撤回、资料或包契约变化仍须阻止历史复用。模型历史也须使用同一受限读取验证，不能将旧建议升级为事实或执行授权。

## 分工与验收

请引擎责任者评估并实现独立的只读历史上下文复验入口，保留现有发布/执行校验严格性；AI 侧改接显示与历史消费调用，补重启、撤权、跨 scope、旧批准拒绝测试。工程侧需验证：无变化重启通过；身份、外发、来源撤销仍失败；重启前未消费批准和批次仍不能重放；不能依靠前端隐藏修复权限。

所有测试使用隔离数据；用户已授权 DeepSeek 场景实测，但该根因无需真实模型。未改正式房间。
## 完成记录

2026-11-20 引擎新增 `publication.check_history_context(host,state,account,context)`，只读检查不依赖旧进程 epoch 和执行检查器指纹，保留完整主体、scope、包、基线、来源、知识与外发验证，不修改旧上下文。AI 的 historyContexts 和 Context.history 已接入；当前生成、批准、发布和批次执行仍使用严格校验。

引擎 110 项回归通过（含 29 项新专项），AI 重启／会话／知识／调试联合 33 项通过。测试实际关闭后从同一目录重建宿主，并验证两轮 KP／PL 历史、撤回与旧批次拒绝。首次缺陷复现、引擎夹具错误和复验均保留；证据：[引擎汇总](../../engineering/acceptance/history-context/results.json)、[AI 初次复现](../../engineering/acceptance/ai-runtime/restart-initial.xml)、[联合回归](../../engineering/acceptance/ai-runtime/restart-integrated.xml)。

该修复不恢复真实变更或撤权导致失效的旧来源，也不延长旧批准；截图中的所有 SOURCE_STALE 不能一概按进程重启处理。
