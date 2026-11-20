# ISSUE-014：旧操作台缺少 AI 裁决客户端方法

- 文档类型：历史
- 状态：已归档
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 原路径：`docs/plans/Issues/issue-014-ai-console-rulings-client.md`
- 原状态：待引擎责任者处理
- 归档日期：2026-11-20
- 归档原因：SDK 补齐并通过独立与真实浏览器复验
- 替代文档：[当前嵌入说明](../current/engineering/ai-pack-embedding.md)
- 关联文档：[问题索引](../plans/Issues/README.md)、[AI 嵌入](../current/engineering/ai-pack-embedding.md)

## 现象与复现

AI 全量回归首轮 519 项中，`test_ui.py::test_browser_requests_review_revision_publish_and_cache_clear` 在点击“审核方案”时失败：页面状态为 `client.aiRulings is not a function`，方案摘要未显示。原始证据为 [full-20261120.xml](../../engineering/acceptance/ai-runtime/full-20261120.xml)。

`engineering/backend/src/onlinecoc/server.py` 的 `/sdk` 静态挂载使用 `engineering/client-sdk/client.js`；该 Client 提供 aiTasks/aiProposal/aiAccess/aiBatches，但没有 aiRulings。`engineering/test-console/ai.js` 复用通用 room-panel，而该组件的 review() 会读取 aiRulings 取得完整高危摘要。

## 影响与边界

旧首测操作台无法打开 AI 配置审核。不能用跳过裁决查询或取消高危摘要检查绕过。新嵌入客户端属于独立实现，本问题不推断为所有界面均失败。

## 处理与验收

由引擎责任者补齐旧客户端对当前只读裁决接口的必要适配，并核对裁决详情涉及的方法。保持代际校验、鉴权和高危批准边界；不新增自动审批。

先做客户端隔离验证；再由 AI 责任者运行上述真实浏览器用例，验证生成、审核、拒绝、导入、修订、批准、加载、重连和退出清理全链路。初验失败、修复与复验分开保存。完成后同步有效说明并归档本问题。

## 完成记录

引擎补齐 `aiRulings()`、`aiResolve(tokens)` 与可取消的 `subscribe(listener)`；继续使用会话代号保护与 CSRF，不改审批和发布规则。[独立 8 项](../../engineering/acceptance/rulings-sdk/results.json)通过；AI 责任者的旧操作台全链路、设置与紧凑裁决浏览器复验 [5/5 通过](../../engineering/acceptance/ai-runtime/full-retest-20261120.xml)。首轮四项全量失败保留；其中另外三项是过时文案或过宽选择器，另行修正。统一统计见[本轮报告](../../engineering/acceptance/ai-runtime/repair-20261120.md)。
