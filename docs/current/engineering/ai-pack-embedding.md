# 配置包 AI 工具、嵌入视图与会话管理

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-14
- 最后更新：2026-11-16
- 关联文档：[管理器与 API](ai-manager.md)、[AI 运行时](ai-runtime.md)、[配置包开发指南](../../../rulepacks/README.md)、[包侧交互计划](../../plans/ai-pack-interaction.md)

## 入口与选择

配置包使用公开入口 [pack.js](../../../engineering/ai/web/components/pack.js)，类型声明为 [pack.d.ts](../../../engineering/ai/web/components/pack.d.ts)。启用 AI 的宿主在 `/ai-ui/` 提供这些文件。本入口不导出服务商/密钥面板；原 `index.js` 保留兼容入口及本机管理组件。

| 方式 | 公开入口 | 已提供内容 |
| --- | --- | --- |
| 自行装配 | `AiClient`、`createAITools`、引用编辑器及补全工具 | 自建会话列表、输入、对象选择器、审核布局和 Transport |
| 单独页面 | `mountAIPage` / `/ai-ui/page.html` | 本房间会话目录、对话、语义引用、按需打开的 KP 队列/审核/设置 |
| 对话页面 | `mountAIConversation` / `/ai-ui/conversation.html` | 紧凑会话选择器与对话区，适合游戏布局中的一栏或页签 |
| 用量统计 | `mountUsage`、`AiClient.aiUsage` / `createAITools.usage` | 可独立挂载，三种对话页内置入口；授权范围内的消费/预留统计 |
| 会话管理 | `mountSessionManager` / `/ai-ui/sessions.html` | 本人会话搜索、排序、置顶、归档恢复及会话设置；可独立挂载 |
| 可折叠页面 | `mountAICollapsible` / `/ai-ui/collapsible.html` | 默认收起，首次展开时挂载；收起保留草稿与选中会话，暂停面板自身轮询 |

三种对话视图均提供“会话管理”入口，与独立管理组件共用真实房间登录、会话存储、引用校验和 KP 审核流程；不会另外创建游戏宿主、存档或服务商配置。KP 明确发送后可转交 AI；PL 只提交需求，不能因为选用了某种视图而获得 KP 权限。配置包自己的布局、术语和翻译仍由包作者维护。

截图：[单独页面](../../../engineering/acceptance/ai-runtime/embed-page.png)、[对话页面](../../../engineering/acceptance/ai-runtime/embed-conversation.png)、[展开面板](../../../engineering/acceptance/ai-runtime/embed-collapsible.png)、[收起状态](../../../engineering/acceptance/ai-runtime/embed-collapsed.png)。

## 原生组件嵌入

已登录同源房间的页面可以复用登录 Cookie；已有 `AiClient` 时直接传入，不再创建第二个客户端。

```javascript
import { AiClient, mountAICollapsible } from '/ai-ui/pack.js';

const client = new AiClient();
await client.resume(); // 未登录时可由包侧登录流程调用 client.login()
const panel = mountAICollapsible(document.querySelector('#ai-panel'), client, {
  title: '房间助手',
  open: false
});

// 角色、物品或配置卡片的“带入讨论”动作：先取得当前授权的元数据。
const result = await client.aiReferences('entity', '提灯');
if (result.items[0]) panel.insertReference(result.items[0]);
// 只打开面板并插入整体标签，不自动发送。

// 页面卸载：组件只释放自己的节点、订阅和轮询。
panel.destroy();
client.destroy(); // 仅当这个客户端由本页面创建并独占时调用
```

替换挂载函数为 `mountAIPage` 或 `mountAIConversation` 即可切换形式。为普通页面/对话组件的容器设置明确高度，例如 `height: 700px`；可折叠组件展开高度由 CSS 变量 `--ai-panel-height` 控制，默认 640px。组件支持现有 `--ai-surface`、`--ai-text`、`--ai-border` 等主题变量，使用 Shadow DOM 隔离样式与内部 ID。

公共选项：`title`、`review`（默认 true）、`onReview(proposalId?)`、`onReceipt(commandId)`、`onSessions(items)`、`onSession(session)`。提供 `onReview` 时，将审核入口交给包侧自定义 UI；无提案 ID 表示打开房间审核/队列入口。`review:false` 隐藏该组件的审核入口，适合需求专用界面，但不构成服务端权限策略。折叠版另有 `open`、`onToggle(open)`。

| 方法 | 行为 |
| --- | --- |
| `refresh()` / `select(sessionId)` / `newChat()` | 刷新、选择本人会话、新建会话 |
| `setDraft(text,references?)` | 预填草稿；references 为授权查询返回的名称、类型、ID、修订等元数据 |
| `insertReference(reference)` | 在输入框光标或选区整体插入语义标签；折叠版自动展开 |
| `showUsage()` | 打开用量统计；折叠版自动展开，选中会话后可选择仅当前会话 |
| `manageSessions()` | 打开本人会话管理；折叠版自动展开 |
| `review(proposalId?)` | 打开默认或自定义审核入口，仍要求真实 KP |
| `suspend()` / `resume()` | 暂停/恢复组件轮询；普通视图可用于游戏页签显隐 |
| `destroy()` | 清空组件私密内容，释放订阅、轮询及节点；不调用共享客户端的 logout/destroy |
| 折叠版 `open()` / `close()` / `toggle()` / `isOpen` | 控制展开状态；关闭会暂停对话并卸载审核面板 |

折叠不会取消已提交任务，也不撤销批准或回滚游戏。切换会话会分别保留未发送草稿；草稿只保留在当前页面内存中，换身份、退出、销毁或刷新页面会清理；关闭审核区会丢弃尚未提交的审核表单输入。折叠暂停的是本组件的会话/审核轮询，宿主共用 `AiClient` 的身份同步仍由其拥有者管理。

## 独立 HTML 与 iframe

四个 HTML 入口可直接在**运行房间的站点**打开，不是管理器 8776 端口的房间代理入口。它们提供登录表单，已有同源登录时直接恢复；没有 AI 组合的宿主不会提供这些入口。

同源配置包页面可使用：

```html
<iframe
  src="/ai-ui/conversation.html"
  title="房间 AI 对话"
  style="width:100%;height:700px;border:0">
</iframe>
```

将地址替换为 `page.html` 或 `collapsible.html` 可切换对话版本；`sessions.html` 提供会话管理，点击“打开对话”进入同源 `conversation.html`。可选 `?session=<会话ID>` 定位本人会话，ID 必须符合格式，最终仍由服务端检查归属。URL 不接受密码、密钥或角色授权参数。

宿主只对这四个 HTML 路径设置 `frame-ancestors 'self'`，允许同源嵌入；宿主其他页面和本机管理器继续禁止被嵌入。跨域 iframe 不受支持。跨服务或 P2P/网页桥应采用原生组件＋受控 `Transport`，或由包作者提供自己的同源页面，不能通过放宽角色字段替代授权。

同源 iframe 与父页面共享房间 Cookie；iframe 内显式退出会影响同源其他页面的登录。删除 iframe 仅停止该页面客户端，不向宿主发送退出命令。需要由父页面精细控制草稿、引用与关闭行为时，优先使用原生组件 API；当前没有跨域 postMessage 控制协议。

## 底层工具与自定义装配

`createAITools(client)` 不创建 UI、不登录、不轮询，不自动转交、批准或加载。它在已有 `AiClient` 上提供分组方法，并丢弃销毁/身份变化后迟到的结果。

| 分组 | 方法 |
| --- | --- |
| `sessions` | `list(archived?)`、`get(id)`、`create(title,id?)`、`update(sessionId,revision,changes,id?)`、`submit(sessionId,text,id?)` |
| `requests` | `list(options?)`、`submit(text,id?)`、`dispatch(requestId,id?)`、`cancel(requestId,id?)` |
| `references` | `commands()`、`token(reference)`、`search(kind,q?)`、`resolve(tokens)` |
| `review` | `get(id)`、`validate(proposalId,revision,id?)`、`approve(proposalId,proposalRevision,riskDecisions,id?)`、`apply(approvalId,id?)`、`revoke(approvalId,id?)` |
| `usage(options?)` | 只读用量汇总与分页明细；from/to/scope/profileId/sessionId/before/limit |
| `settings` | `get()`、`update(settings,id?)` |
| `receipts` | `ai(commandId)`、`host(commandId)` |
| 工具本体 | `contracts()` 读取实际机器契约；`destroy()` 释放本工具包装，不销毁共享客户端 |

上述写方法的最后一个可选 `id` 是幂等命令 ID。返回完整回执，调用方必须确认 `status === 'committed'` 才使用 result。网络结果未知时，查原 ID 的回执，不换 ID 自动重试。审核和加载使用宿主命令，查 `receipts.host`；会话和需求使用独立 AI 命令，查 `receipts.ai`。

```javascript
import { createAITools, requestId } from '/ai-ui/pack.js';

const ai = createAITools(client);
const createId = requestId();
const created = await ai.sessions.create('道具讨论', createId);
if (created.status !== 'committed') throw new Error(created.code || created.status);

const found = await ai.references.search('entity', '提灯');
const reference = found.items[0];
if (reference) {
  const receipt = await ai.sessions.submit(
    created.result.sessionId,
    '我想改良 ' + ai.references.token(reference),
    requestId()
  );
  // 这里仅提交需求。是否转交由 KP 的显式操作决定。
  console.log(receipt.status);
}
ai.destroy();
```

更低层仍可直接用 `AiClient.aiCommand/aiReceipt/command/receipt`、HTTP 和自定义 `Transport.request(path,{method,body,csrf})`。全部操作 Schema、字段和配额以 [API 文档](ai-manager.md#http-与-python-接口)与 `GET /api/v1/ai/contracts` 为准。

输入层可独立组合：`createReferenceEditor(element,{resolveReferences})`＋`bindReferenceInput(element,candidates,client,{editor})`；提交读取 `editor.value`，显示摘要读取 `editor.displayText`。`REFERENCE_COMMANDS` / `referenceCommands(role)` 提供指令元数据，`referenceToken` 生成底层标记，`renderReferenceText` / `hydrateReferences` 渲染授权名称。自行装配时，必须在退出/换房时清理编辑器、候选与异步结果；不能把对象名称或剪贴板元数据当作授权凭证。

## 独立会话管理与显示组件

```javascript
import { mountSessionManager, mountMarkdown } from '/ai-ui/pack.js';

const sessions = mountSessionManager(container, client, {
  title: '本房间会话',
  onOpen: id => conversation.select(id),
  onChange: session => conversation.refresh().catch(showError)
});
// 可调用 refresh / select(id) / suspend / resume / destroy；不销毁共享 client。
const answer = mountMarkdown(answerContainer, modelText, {
  resolveReferences: tokens => client.aiResolve(tokens)
});
// answer.update(nextText); answer.destroy(); sessions.destroy();
```

管理组件支持标题搜索、使用中/已归档/全部过滤、按最近更新/名称排序及置顶优先。`onOpen` 未传时隐藏“打开对话”；`onChange` 在确认写入后通知宿主。首次连接、手动刷新、筛选和写入后加载目录，不新增定时轮询。所有操作限定当前房间的本人会话，KP 也不能编辑他人的目录。

会话设置由 `ai.session.update` 保存：`title`、`pinned`（默认 false）、`historyTurns`（整数 0—4，默认 4）、`renderMode`（formatted/plain，默认 formatted）、`showDiagnostics`（默认 true，仅 KP 界面显示）。归档通过 `archived` 控制，不删除记录。旧记录缺少新字段时读取默认值，不需迁移。历史轮数只控制后续生成携带的既有请求，不清除已确认记忆，来源复验及总上下文上限继续生效。更新携带 `revision`；冲突需重新选择后修改。写入响应丢失时暂停重复写入，点击“查询操作结果”查询原命令回执，不重新创建。

回答支持 Markdown 子集：标题、粗体/斜体/删除线、列表、引用块、链接、行内/围栏代码和管道表格；表格与代码在窄容器内独立滚动，围栏代码可复制。原始文本模式保留标记；用户输入保持文本及语义标签。采用 DOM 构建，不执行模型 HTML，也不自动请求远端图片；链接仅允许 http/https/mailto。此实现不承诺完整 CommonMark、数学公式或语法高亮。

`mountMarkdown` 自带隔离样式，可传授权解析器；`renderMarkdown(element,text,options)` 是低层渲染函数，自行装配时加载 `markdown.css` 并按需调用 `hydrateReferences`。正文中的引用仍按授权显示“提灯”等完整标签，代码中的引用标记保持字面文本。切换身份或卸载时由宿主销毁显示组件，避免保留私密内容。

## 可嵌入用量统计

```javascript
import { mountUsage, createAITools } from '/ai-ui/pack.js';
const usage = mountUsage(usageContainer, client, { sessionId: selectedSessionId });
// 有选中会话时显示“仅当前会话”；UI默认KP看房间，PL看本人。
const report = await createAITools(client).usage({ scope: 'mine', limit: 30 });
// usage.setSession(id) 会直接查询本人该会话；refresh / suspend / resume / destroy 可用于页签生命周期。
```

`mountUsage` 在打开和手动查询时读取，不额外定时轮询；共享客户端的身份同步仍由宿主管理。退出/换身份/销毁后清除统计，丢弃迟到响应。包的静态分发需含 `usage.js/usage.css`，服务桥需允许 `GET ai/usage` 及明确筛选字段。统计与权限定义统一见[管理器文档](ai-manager.md#每日限额与用量统计)，不把预留量当作账单金额。

## 资源和服务桥接

机器清单为 [pack-manifest.json](../../../engineering/ai/web/components/pack-manifest.json)：列出运行文件、类型文件、四个页面、读取/提交路由和审核所需的宿主操作。包作者可以据此准备自己的静态分发及精确路由白名单。清单不含管理器路由或服务商密钥接口，也不是宿主授权策略的替代品。

保留清单内模块/CSS 的相对目录，不能只复制 HTML 或入口 JS。`pack.d.ts` 依赖声明文件 `index.d.ts`；运行入口 `pack.js` 不依赖管理员组件。iframe 入口需在包自己的同源服务中保留正确的 Content-Type、Origin/CSRF、身份 Cookie 及 CSP；跨服务 Native Transport 由包作者按现有会话桥实现。

Stumpsville 的本地 KP、PL 与网页玩家已接入原生对话和会话管理；旧咨询队列也使用相同格式渲染。包侧按清单分发资源，网页构建内联新增模块与样式，并以 composedPath 转发 Shadow DOM 表单事件；响应丢失恢复与包桥共用原命令回执。PL 仍只看自己的需求和状态，模型回复由 KP 审阅；配置生成发布仍见[后续计划](../../plans/stumpsville-ai-integration.md)。

## 验收

2026-11-16 的不限额与用量统计新增验收为122项模块测试及9组树桩镇接入，详见[用量结果](../../../engineering/acceptance/ai-runtime/usage-results.json)及[界面截图](../../../engineering/acceptance/ai-runtime/usage-panel.png)。以下为此前格式/会话阶段结果，不重复累加。

三种页面已在真实 Edge＋隔离宿主中验证；包括 KP 生成、A/B/C、批准/加载，PL 仅提交，同源 iframe 与响应头范围，折叠暂停/恢复、草稿保留、窄屏、组件共用客户端及迟到响应清理。底层工具覆盖会话幂等、只提交不自动转交、PL 越权拒绝和销毁后不再发送请求；资源清单验证模块依赖闭合。

2026-11-15 格式与会话管理更新通过 **51 项模块回归、7 组树桩镇接入验收**；防重复提交的 4 项复验包含在 51 项内。证据见[结果与源码摘要](../../../engineering/acceptance/ai-runtime/rendering-sessions.json)，截图见[格式渲染](../../../engineering/acceptance/ai-runtime/markdown-embedded.png)、[会话管理](../../../engineering/acceptance/ai-runtime/session-management.png)。覆盖真实 Edge、本地 KP、两名 WebRTC 网页玩家、旧咨询队列和沙箱表单；全部使用隔离存档/模拟服务，没有调用真实 DeepSeek、修改正式存档或新增云端部署。此前三种视图 26 项验收保留于[原记录](../../../engineering/acceptance/ai-runtime/embeds.json)。

## 数据查询与事件资料

三种视图共用新增 `/chat /event /ruling` 补全及资料预览，仍使用整块语义标签。开发者可调用 `AiClient.aiData` 或 `createAITools(client).data.search/read/chat/case`，路由已列入 pack-manifest.json。参数、来源复验与可信包适配要求见[数据查询](ai-data-query.md)，不需复制查询或权限实现。
