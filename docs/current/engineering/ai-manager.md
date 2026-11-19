# AI 管理器、嵌入组件与开发接口

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-13
- 最后更新：2026-11-17
- 关联文档：[AI 运行时](ai-runtime.md)、[会话权限与执行批次](ai-session-access.md)、[模块入口](../../../engineering/ai/README.md)、[Stumpsville 接入计划](../../plans/stumpsville-ai-integration.md)、[工程索引](README.md)

## 使用入口

在 Windows 上运行 [start-manager.cmd](../../../engineering/ai/start-manager.cmd)，使用项目现有 `engineering/.venv` 启动本机管理服务并打开浏览器，默认地址 `http://127.0.0.1:8776`。管理器独立于房间运行；关闭管理器不关闭游戏宿主。当前交付为本机 Web 面板，没有额外 Electron 安装包。

需要更换端口、配置文件或保存房间连接的目录时，从项目根目录执行：

```powershell
engineering/.venv/Scripts/python -B engineering/ai/scripts/manager.py --port 8776 --config engineering/ai/config/ai-providers.json
```

`--data-dir` 默认 `engineering/ai/.manager`；`--no-browser` 在本机终端输出一次性入口。启动先占用回环端口，成功后才打开入口。入口片段 5 分钟有效、仅可交换一次管理会话；页面立即移除片段，会话最长 8 小时。锁定后需关闭启动命令窗口，再重新启动。不要把含一次性片段的入口作为房间邀请地址。

1. **服务商**：编辑已有 DeepSeek 配置，或添加 DeepSeek / Chat Completions 兼容服务；设置地址、模型、凭据引用、启停、超时与可选额度；“启用每日用量限制”默认不勾选。完整参数保留在高级 JSON 中。保存密钥后可主动点击“测试连接”，这一步会产生实际服务用量。
2. **房间与会话**：添加已运行的本机宿主地址，使用该房间真实 KP 或 PL 账号登录。宿主必须已通过 `serve --ai-config … --ai-pack …` 组合 AI；启动示例见[模块入口](../../../engineering/ai/README.md)。管理器不另开同一存档、不代替宿主加载包。
3. **使用 AI**：左侧每个房间连接呈现为一个文件夹，KP 可列出房间全部会话，PL 仅授权会话；支持搜索、新建、改名、归档/恢复、删除；顶栏“会话管理”提供置顶、排序及会话设置。中间显示格式化回答，底部输入，切换会话分别保留页面内草稿。KP 在“KP 审核与设置”中选择服务商、开启调用及外发范围后，自己点击“发送”会提交并转交 AI；允许 PL 对话后，玩家需求直接转交，按绑定玩家权限生成回答；默认不开启。管理员运行时修改以执行批次提审，可显式开启自动批准。生成配置提案后查看 A/B/C、差异及风险，通过统一裁决“批准并执行”加载整批。
4. **引用与原型**：输入 `/config`、`/entity` 或 `/data` 调出补全，选择后可“查看引用”。左下角“配置包交互原型”打开 `/prototype.html`，可体验 KP／PL 的对象引用及审核流程；使用固定演示数据，不连接游戏。设计和后续接线见[原型计划](../../plans/ai-pack-interaction.md)。

当前聊天模板采用居中正文、底部圆角输入区、空白会话建议和紧凑会话目录；默认 Enter 发送、Shift+Enter 换行，也可在输入区切换 Ctrl+Enter。生成中提供停止按钮，阅读历史时提供“回到最新”，复制回答使用已显示的语义名称。输入失败、延迟回执和切换会话均保留对应草稿；完整交互和嵌入约束见[对话交互](ai-pack-embedding.md#对话交互)。这些前端改动没有缩短模型推理时间，也没有增加流式协议。

另有独立的[会话管理原型](../../plans/ai-session-management-prototype.md)，侧栏“会话管理原型”可打开 `/session-prototype.html`，提供三栏／窄屏交互和演示数据；不修改正式会话。

服务商模板默认关闭；已有配置以管理器保存状态为准。更改配置会自动递增修订，房间在读取设置和下一次调用前刷新同一配置文件；已开始任务仍使用原快照，不能静默换模型。停用只阻止后续调用；要中止正在生成的请求，应在房间取消该请求。

## 功能及权限

| 面板 | 已有功能 | 权限与持久化 |
| --- | --- | --- |
| 服务商 | 新增、编辑、启停、停用后删除；JSON 导入预览、逐项保存、导出全部配置；连接探测 | 本机管理会话；Profile 修订 CAS 和文件锁防止并发覆盖 |
| 密钥 | 输入新密钥、加密保存、移除、显示配置状态 | 不提供明文读取；配置导出只有 credentialRef |
| 房间连接 | 登记名称与本机地址、登录、切换、断开和移除 | 保存名称/地址；密码不持久化，宿主 Cookie 仅在管理器内存中按管理会话及房间隔离 |
| 房间文件夹与会话 | 当前房间下新建、改名、归档/恢复、查看历史、继续需求；搜索房间名和已加载会话标题 | 按 Room.scopeId 隔离；KP 管理本房间全部会话，PL 仅本人玩家级会话；等级与创建者固定绑定 |
| 用量统计 | 日期、服务配置/模型、当前会话筛选；输入/输出、确认消耗、预留及分页调用明细 | KP 可查房间汇总，PL 仅本人需求；按当前房间 AI 仓库计数 |
| 房间助手 | 需求队列、人工草稿、三检、编辑修订、风险审核、批准/加载、取消、回执、外发范围、确认记忆 | 全部沿用宿主鉴权；本机管理员身份不赋予 KP 权限 |

管理服务只绑定回环；房间地址限 `http://127.0.0.1:<port>` / `localhost`，拒绝远程地址、用户信息、路径及重定向。页面与接口检查 Host、Origin、管理 Cookie 和写请求 CSRF。房间代理是有限路由表，不开放 host-control 或任意转发。此版不支持管理远程房主，也不向 LAN 暴露服务商管理。

Windows 密钥经 DPAPI CurrentUser 加密存入 `%LOCALAPPDATA%/OnlineCOC/AI/credentials.json`，由当前 Windows 用户解密。`credentialRef` 继续使用 `env:变量名`：先查本机保险库的同名条目，再查进程/Windows 用户环境变量。移除保险库条目后可能回退环境变量；共享同一引用的配置共享密钥，删除 Profile 不自动删密钥。非 Windows 仅支持环境变量，尚无原生保险库验收。相同 Windows 用户运行的宿主才可读取该保险库。

## 会话与记忆语义

房间文件夹是管理器的连接分组，不额外复制存档或创建任意磁盘目录。会话仍存于对应宿主的独立 AI 仓库 `settings.sessions`，不写入游戏实体；目录按房间 scope 与会话权限隔离，规则见[会话权限](ai-session-access.md)。重启宿主保留 scope 时可继续历史；更换存档或恢复为新 scope 不会沿用旧会话。最多每房间 200 个未删除会话、每会话 100 个请求；归档保留历史及审批证据。会话提交与请求创建在同一 AI 仓库提交中完成，失败不产生孤立请求；改名/归档带 revision，重复 command ID 返回原回执。新建/更新/提交会话的业务变更和幂等回执在一次 AI 仓库事务中校验、落盘；失败不留下半成品。幂等重放不重复提交。仓库加载及最终提交仍完整验证结构、账号归属和引用；批准/发布等跨仓库操作不使用此合并事务。

生成时按该会话 `historyTurns` 携带此前 0—4 个请求，默认 4，设为 0 不携带会话历史；原始记录仍保留。已取消请求跳过；历史玩家输入标记为非权威陈述。历史 AI 回答只在原审核者、当前授权、外发策略、房间基线及来源仍有效时加入，并标记为未批准回答；过期项列入遗漏清单，不作为事实。上下文仍受 96 KiB 总上限约束。这是有限轮次会话连续性，没有自动压缩或跨房间记忆。

长期事实继续使用原有 `Memory` 创建、KP 确认及撤销流程。会话归档不撤销已确认记忆或已加载配置；取消请求不回滚游戏。恢复分叉时旧 AI 历史作为待复核附件，不自动成为新房间会话。当前没有硬删除审计链的接口。

## 每日限额与用量统计

新服务配置和示例模板的 `limits.dailyTokenBudget` 默认为 `null`，表示不限制每日累计 Token；记账始终开启。正整数（1—10,000,000）表示显式启用日限额，已有正数配置仍按原额度执行。关闭/重新开启限额不会删除历史或重置当日用量。本次已将当前本机 `deepseek-main` 改为不限额；其他部署通过管理器的额度开关保存。输出长度、上下文大小、超时、工具轮数等仍独立受限。

管理器连接房间后，左侧“用量统计”打开该房间面板；三种嵌入对话顶栏也有同名入口。支持今天/最近7天/最近30天/自定义日期、服务配置筛选，以及选中会话后的“仅当前会话”。KP 默认查看整个房间，可切换“我的需求”；PL 只查本人发起的需求，KP 转交调用也归到原玩家。API 默认 `scope=mine`，房间汇总仅真实 KP 可请求；会话筛选允许 KP 查询他人会话，PL 仅本人。统计不包含需求/回答正文、工具参数、密钥或他人的会话标题。

| 指标 | 含义 |
| --- | --- |
| `confirmedTokens` | 服务商成功响应中的 `usage.total_tokens`；并非货币金额 |
| `promptTokens` / `completionTokens` | 已确认的输入/输出 Token；旧记录缺少细分时以 `missingBreakdownCalls` 提示，已知总量仍保留 |
| `pendingReservedTokens` | 仍在调用中的保守预留，尚未确认实际消耗 |
| `uncertainReservedTokens` | 失败、取消、重启或旧记录缺乏状态时保留的预留，标为“待核实”，不能当成实际消耗或零消耗 |
| `accountedTokens` | 确认消耗＋上述两类预留；启用限额后用于本地额度判断 |
| `calls` / `settledCalls` / `pendingCalls` / `uncertainCalls` | 调用次数及用量状态；多轮工具/重试分别记账，调用前被拒绝的不计为一次模型调用 |

预留量为输入 JSON 的 UTF-8 字节数加最大输出 Token，是保守估算。每次尝试按开始调用时的 UTC 日期记入对应服务配置，跨日完成仍归原调用日；北京时间每天 08:00 进入新日。重启保留账本，历史只读查询不改写旧记录。无效响应或中断可能无法取得服务商 usage，因此保留“待核实”预留，不自动清零。

当前统计限于所连接房间的独立 AI 仓库，不汇总其他房间、管理器连接探测或服务商账户上的其他应用；不查询服务商余额或估算费用。设置中的今日额度另标当前 UTC 日期，不与历史日期筛选结果混算。额度开关只有本机服务商管理器/管理员 CLI 可修改，玩家用量接口仅只读。

更新此版本须重启房间 AI 宿主和本机管理器、刷新页面；旧进程的配置 Schema 不支持 `dailyTokenBudget:null`。加载新版后，后续额度调整沿用配置热刷新，无需再次重启。

## 嵌入方式

配置包完整接入说明、三种对话页面、独立会话管理、同源 iframe、底层工具和资源清单统一见[配置包 AI 工具与三种嵌入视图](ai-pack-embedding.md)。

配置包专用入口是 [pack.js](../../../engineering/ai/web/components/pack.js)，附 [类型声明](../../../engineering/ai/web/components/pack.d.ts)和[资源/路由清单](../../../engineering/ai/web/components/pack-manifest.json)；原 [index.js](../../../engineering/ai/web/components/index.js) 保留兼容入口和本机管理员组件。启用 AI 的宿主通过 `/ai-ui/` 提供这些静态模块；独立管理器通过 `/components/` 提供同一源码。组件为原生 ES module，无前端框架依赖。

```javascript
import { AiClient, mountAI, mountChat } from '/ai-ui/pack.js';

// 页面已有同源房间登录；也可用 client.login(loginName, password)。
const client = new AiClient();
await client.resume();
const review = mountAI(client, { target: document.querySelector('#review') });
const chat = mountChat(document.querySelector('#chat'), client, {
  listTarget: document.querySelector('#conversation-list'),
  onReview: id => review.review(id)
});

// 宿主页面退出/换房/卸载时调用；共享登录场景不要擅自 logout 其他组件。
function dispose() {
  chat.destroy();
  review.destroy();
  client.destroy();
}
```

| 接口 | 契约 |
| --- | --- |
| `mountAIPage` / `mountAIConversation` / `mountAICollapsible` | 单独页面、紧凑对话页、折叠面板；均可嵌入，可暂停/恢复和预填引用；详见[配置包接入](ai-pack-embedding.md) |
| `mountUsage(target,client,{sessionId?,scope?})` | 可独立嵌入用量查询/统计；返回 refresh/setSession/suspend/resume/destroy，不销毁共享客户端 |
| `mountSessionManager(target,client,options?)` | 独立会话管理/设置；本机管理器与三种对话视图均已接入，详情见[嵌入指南](ai-pack-embedding.md#独立会话管理与显示组件) |
| `mountMarkdown` / `renderMarkdown` | 安全格式渲染；支持标题、表格、列表、代码等子集，保留正文语义引用 |
| `createAITools(client)` | 无界面会话/需求/引用/审核/设置/回执分组工具；返回原始回执，不自动批准或加载 |
| `mountAI(client,{target,onReceipt?})` | 返回 `refresh/review/showBatches/reloadSettings/destroy`；包含需求、审核、配置设置及长期记忆 |
| `mountChat(target,client,{listTarget?,onReview?,onChange?})` | 对话区和可选外部会话列表；返回 `refresh/select/newChat/showArchived/applySessionChange/setDraft/insertReference/suspend/resume/destroy`；KP 明确发送后转交生成，允许后 PL 直接转交并读取玩家范围回答 |
| `bindReferenceInput(input,container,client,{editor?})` | 两级指令/数据补全，返回 `reset/destroy`；传入 ReferenceEditor 时插入语义标签，旧 textarea 接法仍插入文本标记 |
| `createReferenceEditor(element,{resolveReferences?})` | 创建语义引用编辑器；value 是底层标记文本，displayText 是可读名称；提供 setValue/insertReference/replace/cursor/destroy |
| `renderReferenceText` / `hydrateReferences` | 将已提交文本呈现为标签；按当前授权解析名称，过期或不可访问时显示提示，不缓存跨身份私密名称 |
| `mountSessions(target,client,{onReview?,onError?,t?})` | 返回 `refresh/destroy`；会话目录与连续需求；t 当前只覆盖标题，完整多语言文案尚未抽取 |
| `mountProviders(target,adminApi,{onChange?})` | 本机管理嵌入组件；adminApi.request(path,body?) 对接下列管理 API，不能传房间客户端代替 |
| `AiClient` | 无界面客户端；login/resume/sync/logout、subscribe、AI 命令/回执/会话/任务/设置/机器契约、aiReferences/aiResolve；普通 command/receipt 用于批准和加载 |
| 自定义 `Transport.request(path,{method,body,csrf})` | 返回解析后的 JSON，非成功抛出带 code 的错误；接入方负责真实会话、CSRF、路由白名单及传输，不接受浏览器传来的账号字段作为授权 |

默认 HttpTransport 只允许同源 `/api/v1/`；跨服务需受控代理或自定义 Transport。对话/审核/服务商组件用 Shadow DOM 隔离样式/ID；补全绑定复用调用方容器，独立使用时需提供候选列表样式。`mountChat` 的 listTarget 由组件管理，卸载会清空，不与其他列表共用。CSS 变量 `--ai-accent`、`--ai-surface`、`--ai-text`、`--ai-input`、`--ai-border` 用于外观调整。销毁释放订阅/轮询；退出、身份变化或权限重置清除正文，迟到的私密响应丢弃。组件不把模型文本作为 HTML 插入。

既有测试操作台的 `engineering/test-console/ai.js` 现转用同一审核组件；通用 `engineering/client-sdk/client.js` 保留兼容接口。会话集成和新的 headless API 使用本模块 AiClient。显示成 PL 的 UI 不是权限凭证，服务端始终读取真实账号。

## 数据引用与短指令

PL 补全仅提供 `/knowledge`，语义标签及详情固定到本人已授权观察；管理页和开发者底层引用接口保持同一权限。新增细则见 [AI 玩家已知资料](ai-player-knowledge.md)。下面的原始配置／实体／聊天指令用于 KP。

新增 `/chat /event /ruling` 语义引用、资料预览和四类只读查询；具体权限、HTTP、底层工具和包侧边界统一见[数据查询](ai-data-query.md)。


| 输入 | 数据来源 | 权限 |
| --- | --- | --- |
| `/config 关键词` | 当前房间 Configuration 及其修订 | 仅 KP；PL 使用已披露的 knowledge 分面，不能直接读取模板 |
| `/entity 关键词` | 当前活动实体：角色、物品等 | 仅 KP 原始实体；PL 使用 knowledge 引用，外发需 private |
| `/data 关键词` | 当前活动工件的 JSON 数据文件 | 仅 KP；外发需 kp；不读取安装目录、包侧私有文件或任意路径 |

补全分两级：输入 `/` 显示可用指令，输入 `/en` 等前缀筛选指令名称；用方向键、Enter/Tab 或鼠标选中后，继续补全该类数据对象。指令列表即时显示，数据查询等待输入稳定 180 ms；Escape 关闭。补全使用当前光标位置，在句子中间插入时保留后文。PL 不显示 `/data`，实际权限继续由服务端验证。

输入框和已发送消息中的引用显示为有底色、加粗的语义标签，例如“旅行提灯”；新会话的自动标题也使用可读名称。标签整体插入，点击 ×、Backspace/Delete、选区删除/替换或剪切均以完整引用处理；支持撤销/重做及相邻引用。IME 组合输入期间不确认候选或触发发送。复制到普通文本使用名称，在支持本组件剪贴板格式的输入框间粘贴时保留完整引用，跨房间后仍需重新授权解析。外来 HTML 按纯文本处理，不创建可执行内容。

存储和提交仍为 `[[config:demo.skill@1]]`、`[[entity:对象ID@修订]]`、`[[data:文件名@活动规则版本]]`，没有改变后端协议。名称是展示信息，实际对象由类型、ID、修订确定；过期名称无法验证时显示“已过期引用”或“不可用引用”，不静默升级版本。来源内容作为不可信数据，不能代替包规则或授予工具权限。

包侧可用 `chat.setDraft(text,references)` 预填一段草稿，或 `chat.insertReference(reference)` 在光标/选区处插入一个对象；references 使用授权查询返回的元数据。调用不会自动发送。独立使用 ReferenceEditor 时，退出/换房应清空内容并 reset 补全，卸载时 destroy 两者；候选及标签样式由挂载页面提供，通用对话组件已自带。包侧静态白名单应覆盖新增的 `reference-editor.js` 及其导入依赖。

- `GET /api/v1/ai/references?kind=config&q=skill`：需真实房间会话；q 最多 120 字符，返回 `{items:[{kind,id,label,revision,visibility,token}],hasMore}`，最多 20 条，不含完整值。
- `POST /api/v1/ai/references/resolve`：写路由同样验证 Origin/CSRF，正文只能是 `{tokens:[...]}`；返回 `{items:[{kind,id,label,revision,visibility,value}]}`，最多 12 个输入标记、32 KiB 解析结果。实际只读，不修改游戏。
- `AiClient.aiReferences(kind,q)` / `aiResolve(tokens)` 与上述 HTTP 对应；Python 使用 `References(host).search/resolve/from_text`，调用方负责可信身份。

提交需求先验证引用可见性和修订；生成时再检查发起者及审核者可见、外发策略和版本，加入 Context.selectedReferences，计入 96 KiB 总预算。配置/实体来源随既有来源清单复验；工件数据由活动规则版本和房间基线绑定。旧版本返回 `REFERENCE_STALE`，不可见返回 `REFERENCE_NOT_VISIBLE`，外发关闭返回 `EXTERNAL_SCOPE_DISABLED`，格式及数量/体积超限明确失败，不偷偷替换版本。

预览有权限不等于获准外发。引用只读；修改数据仍需候选配置、A/B/C、KP 批准与宿主发布。包侧场景、笔记和独立 package.json 暂无自动引用映射。包代理/网页服务桥须显式新增所需路由和组件资源白名单，不能由通用 API 已实现推导为包已接通。

## HTTP 与 Python 接口

房间写入仍是 `POST /api/v1/ai/commands`，封套 `{requestId,authorityEpoch,op,args}`。新增操作参数的机器来源为 [ai-operations.json](../../../engineering/contracts/ai-operations.json)：

| op / 读取路径 | 参数或返回 |
| --- | --- |
| `ai.session.create` | `{title,accessLevel?}`，1—120 字符；返回 sessionId、owner、accessLevel、title、revision、archived、createdAt、updatedAt |
| `ai.session.update` | `{sessionId,revision,title?,archived?,pinned?,historyTurns?,renderMode?,showDiagnostics?}`；historyTurns 为 0—4，renderMode 为 formatted/plain，其余新增字段为布尔；owner 由真实会话限定，不能转移 |
| `ai.session.submit` | `{sessionId,text}`，1—8000 字符；返回 requestId/sessionId；玩家级会话直接排队成功时另含 taskId，失败含 dispatchError |
| `GET /api/v1/ai/sessions?archived=false` | `{items:[Session & {requestCount}],access}`；KP 全部／PL 本人 |
| `GET /api/v1/ai/sessions/{id}` | `{session:Session,items:Task[]}`；PL 可见自己提交的需求及通过玩家来源复验的回答 |
| `GET /api/v1/ai/usage` | 授权用量汇总、按日/服务配置分组与分页调用明细；参数见下文 |
| `GET /api/v1/ai/contracts` | `{version:1,operations,$defs}`；需房间登录，供自建表单/生成器读取实际 JSON Schema |

用量查询参数：`from` / `to` 为 UTC 日期 `YYYY-MM-DD`（含两端，最长366天，默认最近7天）；`scope=mine|room`（默认mine）；可选 `profileId`、授权 `sessionId`、`before`（上页nextBefore）、`limit`（1—100，默认50）。未知/重复参数和非法范围被拒绝。返回 `scopeId/scope/timezone/from/to`、`totals`、`byDay`、`byProfile`、`budgetsToday`、`items/nextBefore`；分页只影响调用明细，汇总仍覆盖整个筛选范围。历史未知模型/时间返回 null，不推测补齐。

JS 使用 `client.aiUsage(options)` 或 `createAITools(client).usage(options)`；Python 使用 `Application.usage(account, options)`，参数按 HTTP 字符串形式提供。接口通过原房间 Cookie 鉴权，管理器及树桩镇网页桥只转发明确用量路由，不能传入账号伪造查询范围。

Session 时间为 Unix 秒数。返回 `committed` 才算命令成功；网络超时用原请求 ID 查询 aiReceipt，批准/发布查询主机 receipt，不自动换 ID 重做。跨线程/进程不直接修改 AI 文件仓库。

管理器 API 前缀为 `/manager/api/`：

| 路径 | 方法及输入 |
| --- | --- |
| `unlock` / `session` / `lock` | POST `{key}` 换 HttpOnly Cookie + csrf；GET 当前 csrf；POST `{}` 锁定并断开全部房间 |
| `providers` | GET 脱敏 Profiles、credentialStatus/storage/configPath；POST `{profile,expectedRevision}`，新建 expectedRevision=0（Profile.revision 保留合法初值 1） |
| `providers/{id}/delete` | POST `{revision}`，必须停用 |
| `providers/{id}/credential` | POST `{secret:string\|null}`；设置/移除，无 GET |
| `providers/{id}/probe` | POST `{}`；JSON 与工具能力探测，显式计费操作，不记入某个房间的日预算 |
| `rooms` | GET 名称/地址/当前连接状态；POST `{name,url}` |
| `rooms/{id}/login` | POST `{loginName,password}`，使用房间鉴权 |
| `rooms/{id}/request` | POST `{path,method?,body?}`，path 为白名单内 `/api/v1/` 后缀 |
| `rooms/{id}/delete` | POST `{}`，需先断开 |

Python 直接集成使用 `Runtime` / `Application` / `Sessions` / `Proposals` / `References`；本机管理使用 `Manager` / `create_manager_app`、`profiles.save_profile`、`Vault`。这些是进程组合接口，调用方必须建立可信身份边界；网络服务优先用已有 HTTP 鉴权入口。自定义服务商协议通过 `providers.create_provider` 增加适配，当前 UI 只配置 DeepSeek 或 Chat Completions 兼容协议。

## 本地延迟与测量

此次定位到创建会话会为 pending、业务状态和回执重复校验/提交整个 AI 仓库；会话详情还会遍历无关请求及其提案。已将自包含会话命令合并为一次持久事务，并在任务查询前按本会话 requestIds 过滤。没有关闭最终校验或磁盘同步。

前端创建成功直接使用 committed 回执渲染，不串行重读列表和详情；服务商和 KP 审核按需挂载，关闭审核即销毁。只轮询选中会话，生成中约 0.9—1.2 秒、空闲约 12 秒，后台标签不查询；不为全部房间后台加载历史。搜索仅覆盖房间名称及已加载会话，不是跨账号全文搜索。

同机隔离存档，251 条请求（250 条无关历史＋1 条当前需求），每项 7 次样本：

| 服务层调用 | 优化前中位数 | 优化后中位数 |
| --- | --- | --- |
| 新建会话 | 158.58 ms | 57.53 ms |
| 当前会话详情 | 6.76 ms | 3.16 ms |
| 会话列表 | 1.08 ms | 1.14 ms |

创建约减少 64%，详情约减少 53%；列表没有明显改善。脚本新建 Host＋Runtime 为 724 ms，计时从 Python 导入后开始；它不代表整个服务启动。完整管理器进程到 HTTP 就绪的单样本为 1572.88 ms（约 1.57 秒），见[启动测量](../../../engineering/acceptance/ai-runtime/chat-startup.json)，包含解释器与导入，不含浏览器启动、旧存档和模型请求。没有充分证据宣称冷启动本身获得同等幅度优化。

最终真实 Edge 浏览器中的新建会话单样本 50.24 ms，包含点击、HTTP 代理、宿主提交与界面更新；该样本为空的隔离测试房间，不可与 250 条历史的服务层样本混为同一负载。生成采用离线确定性服务商。DeepSeek 网络推理、三检执行、历史规模扩大后的完整仓库校验仍可能耗时；本轮没有改变为流式输出，也没有宣称缩短真实模型生成时间。

证据：[优化前](../../../engineering/acceptance/ai-runtime/chat-performance-before.json)、[优化后](../../../engineering/acceptance/ai-runtime/chat-performance-after.json)、[浏览器](../../../engineering/acceptance/ai-runtime/chat-browser.json)。复测用 [benchmark_local.py](../../../engineering/ai/scripts/benchmark_local.py) 指向一个尚不存在的临时目录；不打开现有游戏存档、不调用模型。小样本是当前机器定位结果，不是高并发或长期负载保证。

## 验收与参考

2026-11-17 聊天模板完成三轮迭代：第一轮 12 项既有回归通过；第二轮 5 项新交互测试通过；第三轮补充发送切换竞态，最终按测试 ID 去重 **27 项通过（含 6 项新增交互测试）**。末轮初跑 25 项通过、2 项旧定位断言失败；限定补全候选定位后，两项复测通过。见[逐轮结果与源码摘要](../../../engineering/acceptance/ai-runtime/chat-polish-results.json)。覆盖本机管理器、三种嵌入形态、390 px 窄容器/移动视口、引用详情与原子编辑、权限和归档删除；使用真实 Edge、隔离宿主及离线模型，无真实 API 消耗。前端优化不代表推理延迟优化。

2026-11-16：日限额默认关闭、授权用量查询与可嵌入统计通过122项模块测试和9组树桩镇接入验收。证据见[用量验收](../../../engineering/acceptance/ai-runtime/usage-results.json)；覆盖额度重新启用、失败/取消/重启保留、旧记录、分页、原玩家归属、HTTP越权、真实Edge管理器及双网页玩家。全部为离线模型与隔离存档。

2026-11-15：格式化回答、独立会话管理与设置已完成；51 项模块回归和 7 组树桩镇接入验收通过，细节及当前入口见[嵌入指南](ai-pack-embedding.md#验收)。结果、复验范围与源码摘要见[本轮记录](../../../engineering/acceptance/ai-runtime/rendering-sessions.json)。以下性能样本和阶段数字仍保留其原测量日期。

2026-11-14 新增配置包专用入口、无界面工具和三种视图/HTML 入口，并对三条房间页面开放同源 iframe。生命周期、分发与验收见[嵌入说明](ai-pack-embedding.md)，证据见[嵌入阶段](../../../engineering/acceptance/ai-runtime/embeds.json)。

2026-11-14 追加指令名称补全与语义引用编辑。最终 9 项专项全部通过，结果见[引用交互验收](../../../engineering/acceptance/ai-runtime/reference-ui.json)及[原型截图](../../../engineering/acceptance/ai-runtime/reference-ui-semantic.png)；覆盖原子增删/替换、撤销重做、剪贴板、光标中段补全、IME 组合事件边界、名称安全渲染、过期/迟到响应及原管理器生成审核流程。本次没有改动后端存储协议，也没有重新执行全部宿主测试；下述 337 项属于前一轮回归。

2026-11-14 完整 AI＋宿主回归 335 项通过，末轮引用/事务/HTTP/会话/真实管理器浏览器专项 22 项通过；原操作台及真实启动复验 3 项通过；按测试 ID 去重共 337 项，无失败/跳过。按测试 ID 去重的最终结果见[本轮验收摘要](../../../engineering/acceptance/ai-runtime/chat.json)，各轮不相加当作新增测试。

本轮覆盖真实 Windows DPAPI、管理器 CLI、房间文件夹、快捷引用与预览、版本及外发边界、提交/回执单次落盘和失败回滚、KP 生成→三检→批准→加载、归档重开、PL 隔离、锁定及原型角色切换。界面截图见[管理器](../../../engineering/acceptance/ai-runtime/chat-room.png)和[配置包原型](../../../engineering/acceptance/ai-runtime/chat-pack-prototype.png)。

此前管理器 AM-0—AM-4 的 331 项去重验收及组件双挂载/迟到响应证据见[历史阶段记录](../../../engineering/acceptance/ai-runtime/manager.json)。此次浏览器使用离线确定性服务商，没有再次调用真实 DeepSeek；既有真实服务结果见 [deepseek-live.json](../../../engineering/acceptance/ai-runtime/deepseek-live.json)。配置包原型不写入树桩镇，真实 KP 试玩、完整本地化、非 Windows 保险库及跨设备完整配置发布未由此次测试证明。

管理功能组织参考 [CC Switch 官方项目](https://github.com/farion1231/cc-switch)，查阅于 2026-11-13；2026-11-14 对话与房间分组参考 [ChatGPT Projects 官方说明](https://help.openai.com/en/articles/10169521-projects-in-chatgpt)，借鉴侧栏分组和独立会话的组织思路，不复制其代码或资源，也不把 ChatGPT 项目的功能直接作为本模块承诺。

会话分级、玩家开关、批次动作／审批／原回执和删除语义统一维护于[会话权限与执行批次](ai-session-access.md)。本页不将配置删除、包侧独立状态或任意私聊读取描述为已支持。

2026-11-16 验收：模块按测试 ID 去重 323 项、树桩镇 32 组通过，覆盖分级权限、直接排队、批次审批／恢复、归档／删除、双网页玩家及原生 KP。均使用隔离存档和离线服务，未调用真实模型或修改正式存档；[验收汇总](../../../engineering/acceptance/ai-runtime/session-access-results.json)保存逐项结果、复测关系和源码摘要。

对话区现接入[语义引用与结构化选择](ai-responses.md)：精简正文，工具诊断单独展示，选择项填写输入框后再发送。

输出修正次数默认 5，可在服务商编辑的调用限制中设置。运行时与配置自动批准分别配置；KP 的 AI 修改裁决队列统一处理批次与通过三检的配置。详细规则以[修改裁决](ai-rulings.md)和[输出修正](ai-responses.md#基础错误修正与用户决策)为准。

2026-11-17 对话布局参照 [ChatGPT 网页入口](https://chatgpt.com/) 的清晰正文、底部输入区和新对话引导；本项目保留房间身份、数据引用和 KP 审核入口，使用自己的组件实现。
