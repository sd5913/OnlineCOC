# AI 数据查询与聊天裁决资料

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-15
- 最后更新：2026-11-15
- 关联文档：[AI 运行时](ai-runtime.md)、[嵌入组件](ai-pack-embedding.md)、[房间格式](room-format.md)、[剩余计划](../../plans/ai-data-query-adjudication.md)、[通用请求与决定规划](../../plans/interaction-records.md)

## 当前能力

后端 0.2.0 / Room v3 上增加只读数据查询、聊天窗口、事件资料和语义引用。未改变 Room 格式，不转换旧存档，也未实现通用 InteractionRequest / DecisionRecord 持久集合。

房间启动的 AI Runtime 使用按需上下文：需求、包契约、允许外发的作者条款、确认记忆、有限会话历史和显式引用先进入输入，实体/配置/聊天详情通过工具读取；不再默认发送每频道最近 50 条聊天和全部运行源码。直接构造 `Context(proposals)` 仍保留旧模式，`Context(proposals, demand=True)` 使用新模式。

按需载荷明确提供 `dataAccess.initialFacts="not-loaded"`；空的roomFacts/rules不等于空数据库。系统提示要求先按类型搜索、再读取引用；query只匹配显示名称，空字符串枚举所选类型，不能用“entity/npc”关键词替代类型筛选。selectedReferences为空不妨碍搜索。

实现分为宿主的 [data_queries.py](../../../engineering/backend/src/onlinecoc/data_queries.py)（权限、读取及复验），AI 模块的 [DataQueryService](../../../engineering/ai/src/onlinecoc_ai/data_queries.py)（工具 Schema、配额、来源记录），以及配置包的只读适配器。模型不能修改数据、审批、执行裁决或选择本机路径。

## 工具与接口

所有 HTTP 接口以 `/api/v1/ai/data/` 为前缀，采用 POST JSON，要求房间登录、同源 Origin 和 CSRF。身份来自会话；未知参数、账号参数、任意路径和 SQL 均拒绝。

| 模型工具 | HTTP 后缀 | 参数与行为 |
| --- | --- | --- |
| `room_search_data` | `search` | `types? / query? / limit? / cursor?`；按名称检索，返回授权标签和版本化引用 |
| `room_read_data` | `read` | `refs`，可选 `fields`；读取精确引用，字段只能从已授权投影中选 |
| `room_read_chat` | `chat` | `channelId`，可选 `after / before / query / limit / cursor`；序号为排他边界，返回升序消息 |
| `room_read_case` | `case` | `refs`；读取 event/ruling 资料，可同时选择多项 |

类型为 entity、config、rule、memory、channel、chat、event、ruling。完整运行规则源码仅 KP 可读且模型外发需启用 kp；普通玩家不能借查询取得源码。公开作者条款仍走既有包契约。模型另保留 `room_read_context` 和 `pack_read_contract` 两个工具。

输入 JSON Schema 由 `/api/v1/ai/contracts` 的 `dataTools` 返回，与模型使用同一工具定义。返回形状：

```text
schemaVersion: 1
snapshotId: 授权结果与查询参数的摘要
items[]: { ref, label, visibility, authority, data? }
ref: { sourceId, kind, id, revision, digest, scopeId }
page: { nextCursor: string | null }
coverage: { status: complete | partial, within: requested-authorized-scope }
```

搜索不返回 data；详情返回已授权字段。ref.id 是稳定的来源键摘要，不是可直接代入游戏命令的实体/消息 ID。实际业务 ID 保留在授权详情中。旧引用、跨房间引用、来源变化返回 SOURCE_STALE；不可见频道返回 NOT_VISIBLE，不能据此区分未知与越权对象。

AI Runtime 给模型的列表结果另附 `pageSummary`：`returnedItems`、`countsByType`、`hasMore`、`isFirstPage`，只统计当前已授权返回页，不提供隐藏数据总数。请求的 `limit` 是数量上限，不是实际条数；只有第一页且无下一页时可据此报告该查询的完整数量，否则须分页去重。该摘要只用于模型阅读，不改变 HTTP EvidencePage、原始查询摘要或来源复验证据。读取聊天前应先读取频道引用，取详情的 `data.channelId`；猜测 ID 后得到 NOT_VISIBLE 不能推导为需要扩大权限。

每页默认 20、最多 50 项；详情最多 12 个引用；输入和单次结果各不超过 16 KiB；每次生成最多 24 次工具调用，并受 Profile 回合数、总期限及每日用量限制。完整模型消息历史不超过 96 KiB。超限明确失败，可缩小窗口/页数；不静默丢弃资料。分页游标绑定授权结果和筛选条件，数据变化后须从第一页重查。

模型工具执行中的 `INPUT_INVALID`、`QUERY_INPUT_LIMIT`、`QUERY_RESULT_LIMIT`、`SOURCE_STALE`、`NOT_VISIBLE` 在尚未附加新查询证明时，作为 `{error:{code},notice}` 返回，让模型按原额度缩小请求或重新搜索；并非成功的空列表。未知工具、权限/策略变化、查询次数超限及附加证明后复验失败仍终止任务。HTTP查询接口仍使用原错误响应，不改变其成功EvidencePage结构。拒绝的工具尝试计入配额与脱敏诊断，不伪造dataQueries成功证明。

## 来源、权限与发布

模型查询使用审核者与原发起者的共同可见投影，再取房间允许外发类别的交集。KP 不自动获得未参与私聊；包侧场景权限按当前位置计算。HTTP 预览可见不等于允许外发，生成时重新检查。搜索先授权再匹配和分页，不返回隐藏计数。

每次查询的 operation、args、scopeId、initiator 和结果摘要保存在任务上下文 `facts.dataQueries`；上下文摘要随新增资料更新。发送前、响应后、读回、审批及发布复用宿主校验。消息编辑/撤回、引用变化、权限变化或恢复分叉使旧依据失效；查询权限不会通过缓存绕过。审批/发布时主机查询复验不依赖 AI 仓库开启。

使用包侧资料的任务标记 `consultationOnly`，宿主审批返回 CONSULTATION_ONLY。包文件与主机尚无跨存储原子快照；本轮明确保持包侧咨询边界，不能用它的输出绕过 A/B/C 或发布校验。撤回聊天不会回滚已经发生的游戏动作。

## 事件资料与树桩镇

EventBundle 是只读投影，包含 messages、actions、rulings、executions、links、coverage。决定内容与执行状态分开：否决是已确认决定、outcome=deny，叙事裁决无需执行；没有完整回执时执行状态为 unknown。未记录的决定者、时间或聊天关联保持缺失，不由 AI 推断补齐。

宿主已分享的行动结果卡可构成 event，附同频道有效 replyTo 消息；卡片不授予原始命令权限，也不虚构 KP 决定。树桩镇适配器读取本包场景/队伍聊天、原 requests 和逐玩家事件投影，使用真实 requestId 与命令回执关联。KP 读取包侧允许的事件，PL 只读取本人事件；渠道与来源进一步过滤。原始命令参数和整个 package.json 均不直接发送给模型。

树桩镇发起业务行动时可在 args 中加入 `sourceMessages`，最多 12 条，每条为 `{channelId, messageId, revision, sequence}`。包服务通过既有授权历史接口核验，申请和后续裁决沿用这些引用；新裁决记录真实决定者和时间。历史无关联记录仍标为不完整。当前没有自动语义配对或历史回填；界面可手选多个聊天/事件标签共同咨询。

可信包开发者的适配器实现 `create_adapter(data_path)`，返回有 `read(room_snapshot, account)` 的对象，可用 `kinds` 声明支持类型。每项输出 `{sourceId,kind,id,revision,label,data,visibility}`，引用、筛选、分页和复验由宿主统一处理。适配器获得完整主机快照，必须由管理员审查和明确安装；它是本机可信程序，不是模型沙箱或从包文档自动加载的脚本。

公开 CLI 参数为 `serve --ai-config ... --ai-pack ... --ai-data-adapter <可信py文件> --ai-data-path <包存档>`；后两项成对且必须启用 AI。树桩镇可选 AI 启动已自动提供其 `tools/ai_data.py` 和本次运行目录的 package.json。适配器不创建/修改存档，读取文件最多 8 MiB，异常返回 DATA_SOURCE_UNAVAILABLE。代码摘要参与查询快照；未配置适配器的房间仅提供主机资料。

## 开发者与界面

`AiClient.aiData(operation,args)` 或 `createAITools(client).data.search/read/chat/case(args)` 可独立使用。管理器房间代理和树桩镇个人咨询桥已放行四个固定路径，真实登录与 CSRF 继续由房间校验。

三种嵌入视图共用 `/chat /event /ruling` 指令和候选补全；输入和历史消息显示语义标签，整块增加/删除。`查看引用` 显示所选聊天、决定理由、执行状态和资料缺口。配置包可用现有 `insertReference` 或 `setDraft` 自行装配资料选择器，不会自动发送。

```javascript
const found = await client.aiData('search', {types: ['event'], query: '检定'});
if (found.items.length) {
  const details = await client.aiData('case', {refs: [found.items[0].ref]});
  // 在本包界面展示 details；展示不等于批准或执行。
}
```

## 验收与边界

专项覆盖 HTTP 登录/CSRF、严格输入、外发开关、KP/PL 交集、跨房间引用、分页变化、消息撤回、宿主发布复验及多工具调用额度；真实 Edge 覆盖单独、对话和折叠视图。树桩镇使用独立测试存档与离线模型，验证消息→申请→叙事裁决→模型咨询、其他玩家隔离和旧资料失效。证据分别见 [查询专项](../../../engineering/acceptance/ai-runtime/data-query.xml)、[浏览器专项](../../../engineering/acceptance/ai-runtime/data-ui.xml)、[包侧结果](../../../rulepacks/stumpsville/tests/ai-data-results.json)。

当前为类型过滤后的内存检索和本机包文件读取，没有持久全文索引、向量库或跨任务查询缓存；大聊天窗口仍有线性扫描成本。按需查询减少初始资料量，但增加模型往返，不承诺缩短真实推理时间。通用请求/决定持久化、自动语义关联、包资料参与配置发布继续见计划。

2026-11-15经授权追加真实DeepSeek隔离验证，分页枚举、详情读取、实际数量与最终回答链路通过；同时保留未读规则却推断游戏含义的答案质量缺口。见[实测与87项回归汇总](../../../engineering/acceptance/ai-runtime/issue-009-live-results.json)。未修改用户存档或部署公网，不能将链路通过等同于完整事实审核。

2026-11-15 验收汇总：全量运行后修正一项旧指令列表断言，最终受影响路径 67 项通过；按测试名称取最新结果去重，共 387 项通过、0 失败、0 跳过。另通过树桩镇资料链路 4 组及既有自动裁决/恢复 6 组验收。[汇总及源码摘要](../../../engineering/acceptance/ai-runtime/data-results.json)保留了全量运行与复验的关系。
