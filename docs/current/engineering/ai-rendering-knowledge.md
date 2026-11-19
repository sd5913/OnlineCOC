# AI 嵌入渲染与玩家知识排查

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-16
- 最后更新：2026-11-17
- 关联文档：[会话权限](ai-session-access.md)、[嵌入接入](ai-pack-embedding.md)、[会话管理交互原型](../../plans/ai-session-management-prototype.md)

## 间歇性格式失效

Stumpsville 的 `renderPage` 在游戏状态更新时重建外层 DOM，随后把原 AI 组件挂到新容器。组件原先在 Shadow DOM 中使用外部 stylesheet link；节点离开文档再挂回时，样式的重新应用可能晚于内容显示。这条路径与“短暂失去格式，随后正常”的现象一致；未取得用户当时的浏览器性能记录，不能认定它是所有闪动的唯一原因。

组件现在通过 `components/styles.js` 按 URL 共享加载并建立 `CSSStyleSheet`，采用 `adoptedStyleSheets`，样式随 Shadow Root 保留。首次加载完成前隐藏组件；失败时显示可重试按钮，不把无样式正文当成加载成功。Stumpsville 网页构建器同时把 CSS 传为内联文本，不要求沙箱向本机下载样式。不改宿主轮询频率或用户的聊天／AI 标签布局。

回归覆盖样式下载失败／恢复、30 次移除后重新挂载、实际嵌入组件和本地 WebRTC 打包加载。聊天内容更新、异步查询和宿主整体 DOM 重建仍可能造成其他位置变化；本项没有宣称完成宿主全页面增量渲染。

## 聊天刷新与滚动稳定性

2026-11-17 的聊天模板优化保留未变化的消息正文、引用标签和会话目录节点；状态变化仅更新相关消息。引用名称解析完成后，只有用户仍处于原会话且没有主动滚动，才跟随到底部。上翻后显示“回到最新”，轮询不覆盖输入区的处理结果提示。

发送回执按原 sessionId 处理，用户切换会话后不会被旧提交切回，另一会话草稿也不会被清除。停止生成后清除对应的加载占位文案。样式继续使用前述共享 adoptedStyleSheets；容器查询处理宽页面里的窄嵌入栏，未改动宿主 DOM 重建方式。

## 场景越界读取

2026-11-17 已以宿主个人知识服务取代原包侧地点集合过滤。本人进入过或被定向揭示产生固定观察；原资料之后变化不灌入该观察。原 `/view` 受管场景不再暴露名称和详情，个人角色表须明确持续告知授权。AI 初始上下文不接收任何包指南或完整契约。

有效权限、引用、模型证据选择及分阶段验收统一见 [AI 玩家已知资料](ai-player-knowledge.md)。Stumpsville 的 KP 房间页管理授权与旧地点待处理记录，地点页定向揭示；旧 `locationKnowledge` 只是“现在揭示”的候选，查询和启动均不补造记录。已显示给人的内容不能从人的记忆中收回。

## 应用与证据

需要更新并重启宿主、包服务，网页分发重新构建。当前宿主要求 Room v4；Room v3 必须在停止旧进程后按[房间格式](room-format.md)显式转换，不能直接按旧版重启步骤加载。此次验收只操作隔离目录，没有修改正在使用的正式存档。

样式证据沿用[原专项](../../../engineering/acceptance/ai-runtime/rendering-knowledge-results.json)；新知识组件见[浏览器验收](../../../engineering/acceptance/ai-runtime/known-a2.xml)，Stumpsville 完整已知信息试点见[10组验收](../../../rulepacks/stumpsville/tests/strict-known-results.json)。
聊天模板的三轮调整、27 项最终通过及两项定位修正复测见[逐轮记录](../../../engineering/acceptance/ai-runtime/chat-polish-results.json)；包括长历史阅读锚定、异步引用、发送期间切换会话、停止生成与 390 px 容器。此次未重跑包侧 WebRTC 分发验收；已有网页包需重建以获得新资源。
