# 旧操作台裁决 SDK 接口验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 关联文档：[SDK](../../client-sdk/client.js)、[通用审核面板](../../ai/web/components/room-panel.js)、[裁决组件](../../ai/web/components/rulings.js)

## 修复内容

宿主 `/sdk/client.js` 对应的 `Client` 新增 `aiRulings()`，调用既有 `GET /api/v1/ai/rulings`，让旧操作台审核入口取得裁决及高危候选摘要。裁决列表还使用两个此前缺失的接口，本轮一并补齐：

- `aiResolve(tokens)`：携带当前 CSRF，通过既有 `POST /api/v1/ai/references/resolve` 解析授权资料引用。
- `subscribe(listener)`：返回取消订阅函数；完整快照、服务端 reset、身份重置和断线时通知组件清空或更新内容。原 `onChange` 继续工作。

两个读取接口复用 SDK 的 `request` 会话代号保护，切换身份后的迟到结果以 `SESSION_CHANGED` 拒绝。裁决响应不被改写，读取不触发批准或执行。审核面板仍由 KP 填写理由，并在高危批准中传入原 `explicitHighRiskDigest`；宿主审核和发布规则未改。

## 验证与边界

[test_client.mjs](test_client.mjs) 读取真实 SDK 和组件源码，用独立 Node 运行时及合成 Transport 验证以下 8 项，全部通过：

1. 审核面板、裁决列表和调试组件直接调用的 Client 方法均存在。
2. 裁决读取保留高危摘要，且不提交决定或创建待执行命令。
3. 引用解析保留 tokens，使用 POST 和当前 CSRF。
4. 裁决读取拒绝身份重置后返回的旧响应。
5. 引用解析拒绝身份重置后返回的旧响应。
6. 权限错误继续抛出，不伪装成空列表。
7. 原 onChange 与新订阅均在完整快照、reset 和断线时通知，取消订阅有效。
8. 身份重置通知清空，旧 WebSocket 消息不能恢复私密视图。

原始 JUnit 见 [core.xml](core.xml)，结果和源码摘要见 [results.json](results.json)。本次未运行真实 HTTP、浏览器审核发布或付费模型；旧操作台完整浏览器复验由 AI 责任者执行。本轮只修改 SDK 文件，未修改 AI 组件、宿主或高危审核规则。

## 复验

先登记 SDK、AI 组件源码的使用及本目录输出改动，再从项目根目录执行：

```powershell
node --test --test-reporter=spec --test-reporter-destination=stdout --test-reporter=junit --test-reporter-destination=engineering/acceptance/rulings-sdk/core.xml engineering/acceptance/rulings-sdk/test_client.mjs
```
