# AI 数据查询与聊天裁决资料

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-15
- 最后更新：2026-11-19
- 关联文档：[AI 运行时](ai-runtime.md)、[嵌入组件](ai-pack-embedding.md)、[房间格式](room-format.md)、[剩余计划](../../plans/ai-data-query-adjudication.md)、[通用请求与决定规划](../../plans/interaction-records.md)

## 当前能力

当前依赖后端 0.3.0 / Room v4。宿主已提供持久个人知识账本及显式离线格式转换，未实现通用 InteractionRequest / DecisionRecord 持久集合。下述原始房间、聊天及裁决工具用于 KP 管理员通路；严格 PL 通路只开放个人知识。

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

KP 类型为 entity、config、rule、memory、channel、chat、event、ruling，另可读取本人 knowledge。完整运行规则源码仅 KP 可读且外发需启用 kp；KP 模型保留 `room_read_context` 和 `pack_read_contract`。PL 的 HTTP search/read 只接受 knowledge 类型，chat/case 因缺少历史受众证明拒绝；PL 模型使用 `room_search_knowledge` / `room_read_knowledge`，直接消费 KnowledgeRef，详见[已知资料](ai-player-knowledge.md)。

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

每页默认 20、最多 50 项；详情最多 12 个引用；输入和单次结果各不超过 16 KiB；每次生成最多 24 次工具调用，并受 Profile 回合数、总期限及每日用量限制。初始资料快照不超过 96 KiB；累计消息与工具 Schema 共用现有传输请求的 256 KiB 预算，最终序列化请求仍须满足传输上限。超限明确失败，可缩小窗口/页数；不静默丢弃资料。分页游标绑定授权结果和筛选条件，数据变化后须从第一页重查。

模型工具执行中的 `INPUT_INVALID`、`QUERY_INPUT_LIMIT`、`QUERY_RESULT_LIMIT`、`SOURCE_STALE`、`NOT_VISIBLE` 在尚未附加新查询证明时，作为 `{error:{code},notice}` 返回，让模型按原额度缩小请求或重新搜索；并非成功的空列表。未知工具、权限/策略变化、查询次数超限及附加证明后复验失败仍终止任务。HTTP查询接口仍使用原错误响应，不改变其成功EvidencePage结构。拒绝的工具尝试计入配额与脱敏诊断，不伪造dataQueries成功证明。

## 来源、权限与发布

模型查询使用审核者与原发起者的共同可见投影，再取房间允许外发类别的交集。普通查询不扩大未参与私聊范围；管理员 AI 的受信 kp-room 通道及包侧 read_scoped 另行传递全读授权，见下节。HTTP 预览可见不等于允许外发，生成时重新检查。搜索先授权再匹配和分页，不返回隐藏计数。

每次查询的 operation、args、scopeId、initiator 和结果摘要保存在任务上下文 `facts.dataQueries`；上下文摘要随新增资料更新。发送前、响应后、读回、审批及发布复用宿主校验。消息编辑/撤回、引用变化、权限变化或恢复分叉使旧依据失效；查询权限不会通过缓存绕过。审批/发布时主机查询复验不依赖 AI 仓库开启。

使用包侧资料的任务标记 `consultationOnly`，宿主审批返回 CONSULTATION_ONLY。包文件与主机尚无跨存储原子快照；本轮明确保持包侧咨询边界，不能用它的输出绕过 A/B/C 或发布校验。撤回聊天不会回滚已经发生的游戏动作。

## 事件资料与树桩镇

EventBundle 是只读投影，包含 messages、actions、rulings、executions、links、coverage。决定内容与执行状态分开：否决是已确认决定、outcome=deny，叙事裁决无需执行；没有完整回执时执行状态为 unknown。未记录的决定者、时间或聊天关联保持缺失，不由 AI 推断补齐。

宿主已分享的行动结果卡可构成 event，附同频道有效 replyTo 消息；卡片不授予原始命令权限，也不虚构 KP 决定。树桩镇适配器读取本包场景/队伍聊天、原 requests 和逐玩家事件投影，使用真实 requestId 与命令回执关联。该 adapter 仅供 KP 管理员通路；严格 PL 因缺少聊天／裁决历史受众证明不读取此类事件。普通查询不直接返回原始命令参数和整个 package.json；显式 KP 全读例外见下文，PL 不使用该通道。

树桩镇发起业务行动时可在 args 中加入 `sourceMessages`，最多 12 条，每条为 `{channelId, messageId, revision, sequence}`。包服务通过既有授权历史接口核验，申请和后续裁决沿用这些引用；新裁决记录真实决定者和时间。历史无关联记录仍标为不完整。当前没有自动语义配对或历史回填；界面可手选多个聊天/事件标签共同咨询。

可信包开发者的适配器实现 `create_adapter(data_path)`，返回有 `read(room_snapshot, account)` 的对象，可用 `kinds` 声明支持类型。每项输出 `{sourceId,kind,id,revision,label,data,visibility}`，引用、筛选、分页和复验由宿主统一处理。适配器获得完整主机快照，必须由管理员审查和明确安装；它是本机可信程序，不是模型沙箱或从包文档自动加载的脚本。

公开 CLI 参数为 `serve --ai-config ... --ai-pack ... --ai-data-adapter <可信py文件> --ai-data-path <包存档>`；后两项成对且必须启用 AI。树桩镇可选 AI 启动已自动提供其 `tools/ai_data.py` 和本次运行目录的 package.json。适配器不创建/修改存档，读取文件最多 8 MiB，异常返回 DATA_SOURCE_UNAVAILABLE。代码摘要参与查询快照；未配置适配器的房间仅提供主机资料。

KP 任务诊断的 `errors[]` 现可附带 `httpStatus`（100—599 的整数），旧记录缺失时不推测补齐。只记录阶段、内部错误码、模块栈和 HTTP 状态；PL 不返回诊断字段。服务商 HTTP 错误分类与修复边界见[回答协议](ai-responses.md#json-请求与服务商错误)。

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

## 会话权限投影

玩家会话统一绑定 owner，使用知识查询、不可变引用与 knowledgeProofs；即使实际账号为 KP 也使用 player=True。HTTP／模型参数不能指定主体。PL 不复用原实体／模板 adapter，缺少知识提供方时不降级。管理员会话的资料管理及修改批次维持原权限与基线，严格只读证明不能用于批准或执行。

模型结果额外携带 citation.token/label，原 HTTP EvidencePage 和来源摘要不变。标记只从授权条目生成；正文引用按已提供标记校验，显示由真实权限解析。模板显示名可由包侧 reference_label 映射，见[回答与选择项](ai-responses.md)。


## KP 全房间查询

管理员上下文可带 `facts.aiReadScope='kp-room'` 与 `aiPolicyRevision`；查询传 `read_scope='kp-room'`，证据记录 readScope。宿主实际审核者和发起者均须为 KP、player 为空，且本机 AI 注册的 ai_room_read_authorizer 明确许可。PL／KP 的玩家级会话不使用此通道；普通聊天 API 不扩权。

新增 `room` 类别以 `sourceId=host-room` 返回按 JSON path 分片的宿主游戏状态，包含历史规则、关系、流程、知识记录等；长文本带 textOffset/textLength。按 ref 小批读取，结果预算仍生效。外发 room 混合分片要求 public/private/kp 三开关全部开启；不包含 Identity、本机配置、密钥或任意文件。关闭 allowAdminRoomRead 后旧上下文和新读取均拒绝。

包独立资料必须由包适配器投影；新增类别可使用已有 config/memory，但不能仅以 KP 角色判断已获得全读授权。包来源仍 consultationOnly，与 host-room 可发布来源不同。

受信包适配器可实现 `read_scoped(state,account,*,read_scope=None)`。宿主先完成账号、发起者与全读开关校验，才传入 kp-room；普通路径传 None，旧 read(state,account) 保持兼容。包侧必须再次确认实际 KP，并仅在 kp-room 时追加全包状态和全场景聊天；关闭开关后旧证据复验失败。

管理工具 `room_manage_catalog({})` 先返回操作名称索引；用 `{operations:["entity.patch"]}` 按需取精确参数 Schema。原库接口 `Batches.catalog()` 不变。模型应先取目标参数再提交批次，避免反复注入完整操作目录。KP 任务诊断的 `contextBudget` 只含累计字节、上限、工具 Schema 和工具消息字节数，不记录资料内容；容量失败会在聊天中显示可操作的缩小查询提示。

读取活动游戏配置时，先用 room_read_management 的 room 节取得 activeRuleset，再按 `/artifacts/<revision>/data/game.json` 搜索 room 标签并按原样 ref 分批读。小文件可能合在父片，精确路径无结果时按 `/artifacts/<revision>` 查父片。宽 room 查询的证明绑定全部匹配记录，无关业务记录变化也可能使其失效；不能把最后一次 read 的 SOURCE_STALE 自动判定为该分片改变。查询过的每份证明都会复验。

## 配置包提供实体检索标签

KP 的实体搜索可调用受信适配器 `reference_label('entity', key, fallback)`；先完成实体投影、接收者交集和外发可见性校验，且实际审核者与发起者均为 KP 才使用该钩子。返回去除首尾空白后非空、不超过 160 字符且能编码为 UTF-8 的字符串，否则回退实体原名；异常也回退。PL 仍走个人知识查询，KP 与 PL 混合接收场景不调用该扩展。

该钩子只用于检索展示，资料必须与实体处于同一可见范围，不能夹带未授权剧情。标签可能注明角色所属玩家，帮助定位随机角色名；标签本身不是授权或执行证据，修改前仍须读取实际实体的 owner、configurationId 和 lifecycle。正文引用继续使用角色原名。实体原文、六字段 ref、数据摘要和可见性不变；标签变化会使旧搜索快照及查询证明失效，调用方须重新查询。

2026-11-19 实体标签与相关查询回归共 76 项去重通过（包含 15 项新增专项），覆盖检索、回退、外发过滤、玩家隔离、引用不变和分页复验，另验既有高危读取、知识与 AI 引用。见[验收说明与证据](../../../engineering/acceptance/entity-search-label/README.md)。不与此前模块或引擎阶段数累加；真实模型效果由 Stumpsville 的独立实测记录维护。


PL 在生成前自动预载本人空 query 目录，计入 24 次查询；非空关键词无匹配明确回退个人目录。目录不是详情证据，模型仍须读取引用。错误分类、已知目录和证据边界见[玩家已知资料](ai-player-knowledge.md#查询未命中与服务阻断)。创作申请无需数据查询，不借申请扩大已知范围。
