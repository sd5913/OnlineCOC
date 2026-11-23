# AI 数据查询与聊天裁决资料

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-15
- 最后更新：2026-11-23
- 关联文档：[AI 运行时](ai-runtime.md)、[嵌入组件](ai-pack-embedding.md)、[房间格式](room-format.md)、[剩余计划](../../plans/ai-data-query-adjudication.md)、[通用请求与决定规划](../../plans/interaction-records.md)

## 当前能力

当前依赖后端 0.3.0 / Room v4。宿主已提供持久个人知识账本及显式离线格式转换，未实现通用 InteractionRequest / DecisionRecord 持久集合。下述原始房间、聊天及裁决工具用于 KP 管理员通路；严格 PL 通路只开放个人知识。

房间 AI Runtime 使用按需上下文；需求、包契约、允许外发的作者条款、确认记忆、有限历史和显式引用先进入输入。明确配置编辑可预读有界模板页，其他详情经工具读取。`Context(proposals)` 与 `demand=True` 都不自动收集普通聊天室消息；旧非按需模式只保留实体／配置预加载。默认模型工具不提供 room_read_chat 或 channel/chat 搜索；当前显式转交或选择聊天来源时才开放对应能力。

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

管理员生成中的 `room_read_data` 若仅因 `fields` 无效而失败，且未附加新证明，可在共用技术纠错额度内去掉该字段过滤，按相同 refs、权限与外发范围重读；成功证明记录实际重读参数。模型批次误用 ref.id 时，只凭本轮已授权 host-state 实体详情中的 instanceId 精确替换 entity.patch/update/archive 的 id 或类型匹配的 action.invoke 输入；不从名称、序号、未读引用或包材料猜 ID。冲突映射、未匹配值继续走正常校验，审批时仍复验来源。

AI Runtime 给模型的列表结果另附 `pageSummary`：`returnedItems`、`countsByType`、`hasMore`、`isFirstPage`，只统计当前已授权返回页，不提供隐藏数据总数。请求的 `limit` 是数量上限，不是实际条数；只有第一页且无下一页时可据此报告该查询的完整数量，否则须分页去重。该摘要只用于模型阅读，不改变 HTTP EvidencePage、原始查询摘要或来源复验证据。读取聊天前应先读取频道引用，取详情的 `data.channelId`；猜测 ID 后得到 NOT_VISIBLE 不能推导为需要扩大权限。

每页默认 20、最多 50 项；详情最多 12 个引用；普通查询输入和单次结果各不超过 16 KiB；每次生成最多 24 次工具调用，并受 Profile 回合数、期限及每日用量限制。初始组装、累计输入、模型窗口与语义压缩统一见[上下文预算](ai-session-access.md#上下文连续性与预算)。分页游标绑定授权结果和筛选条件，数据变化后须从第一页重查。

管理员模板修改应先用 `room_read_management({section:"configurations",offset:0,limit:...})` 分页读取宿主权威模板、当前修订和默认值；结果摘要纳入管理读取证明，变化后 SOURCE_STALE。`room_manage_catalog` 只列运行时/会话操作，操作名 Schema 为枚举，不提供 `config.create` 或 `configuration.create`；模板增删改通过 draft 的 configurations 提交。管理查询的参数/输入/结果预算错误会返回有界反馈供模型修正，尝试继续计入原额度；权限与外发拒绝仍终止任务。失败读取不会附加虚假成功证明。

模型工具执行中的 `INPUT_INVALID`、`QUERY_INPUT_LIMIT`、`QUERY_RESULT_LIMIT`、`SOURCE_STALE`、`NOT_VISIBLE` 在尚未附加新查询证明时，作为 `{error:{code},notice}` 返回，让模型按原额度缩小请求或重新搜索；并非成功的空列表。未知工具、权限/策略变化、查询次数超限及附加证明后复验失败仍终止任务。HTTP查询接口仍使用原错误响应，不改变其成功EvidencePage结构。拒绝的工具尝试计入配额与脱敏诊断，不伪造dataQueries成功证明。

## 来源、权限与发布

模型查询使用审核者与原发起者的共同可见投影，再取房间允许外发类别的交集。普通查询不扩大未参与私聊范围；管理员 AI 的受信 kp-room 通道及包侧 read_scoped 另行传递全读授权，见下节。HTTP 预览可见不等于允许外发，生成时重新检查。搜索先授权再匹配和分页，不返回隐藏计数。

每次查询的 operation、args、scopeId、initiator、结果摘要及返回对象的 readRefs 保存在任务上下文 `facts.dataQueries`；上下文摘要随新增资料更新。发送前、响应后、读回、审批及发布复用宿主校验。被明确引用的消息编辑／撤回、引用变化、权限变化或恢复分叉使旧依据失效；无关新聊天不影响 state 查询或单条消息引用；查询权限不会通过缓存绕过。审批/发布时主机查询复验不依赖 AI 仓库开启。readRefs 仅补充只读历史的对象身份，不能替换查询摘要或放宽当前审批；过期历史与旧存档边界见[会话权限](ai-session-access.md#同房间重启与历史)。

独立包资料仍保留 `consultationOnly` 来源标记，现表示须 KP 明确接受的来源风险。模型结果 `sourcePolicy.publication=requires-kp-source-review`：应先读取宿主当前模板或活动工件目标，再生成可校验候选；不能把参考材料当作当前宿主事实。包文件与宿主没有跨存储原子保证，来源接受也不跳过 A/B、权限、版本、实际执行和来源复验。批准协议见[来源风险评估](ai-rulings.md#独立来源风险评估)。撤回聊天不会回滚已发生动作。

## 事件资料与树桩镇

EventBundle 是只读投影，包含 messages、actions、rulings、executions、links、coverage。决定内容与执行状态分开：否决是已确认决定、outcome=deny，叙事裁决无需执行；没有完整回执时执行状态为 unknown。未记录的决定者、时间或聊天关联保持缺失，不由 AI 推断补齐。

宿主已分享的行动结果卡可构成 event，附同频道有效 replyTo 消息；卡片不授予原始命令权限，也不虚构 KP 决定。树桩镇适配器读取本包场景/队伍聊天、原 requests 和逐玩家事件投影，使用真实 requestId 与命令回执关联。该 adapter 仅供 KP 管理员通路；严格 PL 因缺少聊天／裁决历史受众证明不读取此类事件。普通查询不直接返回原始命令参数和整个 package.json；显式 KP 全读例外见下文，PL 不使用该通道。

树桩镇发起业务行动时可在 args 中加入 `sourceMessages`，最多 12 条，每条为 `{channelId, messageId, revision, sequence}`。包服务通过既有授权历史接口核验，申请和后续裁决沿用这些引用；新裁决记录真实决定者和时间。历史无关联记录仍标为不完整。当前没有自动语义配对或历史回填；界面可手选多个聊天/事件标签共同咨询。

可信包开发者的适配器实现 `create_adapter(data_path)`，返回有 `read(room_snapshot, account)` 的对象，可用 `kinds` 声明支持类型。每项输出 `{sourceId,kind,id,revision,label,data,visibility}`，引用、筛选、分页和复验由宿主统一处理。适配器获得完整主机快照，必须由管理员审查和明确安装；它是本机可信程序，不是模型沙箱或从包文档自动加载的脚本。

公开 CLI 参数为 `serve --ai-config ... --ai-pack ... --ai-data-adapter <可信py文件> --ai-data-path <包存档>`；后两项成对且必须启用 AI。树桩镇启用 AI 启动时自动提供其 `tools/ai_data.py` 和本次运行目录的 package.json。适配器不创建/修改存档，读取文件最多 8 MiB，异常返回 DATA_SOURCE_UNAVAILABLE。代码摘要参与查询快照；未配置适配器的房间仅提供主机资料。

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

## 会话权限投影

玩家会话统一绑定 owner，使用知识查询、不可变引用与 knowledgeProofs；即使实际账号为 KP 也使用 player=True。HTTP／模型参数不能指定主体。PL 不复用原实体／模板 adapter，缺少知识提供方时不降级。管理员会话的资料管理及修改批次维持原权限与基线，严格只读证明不能用于批准或执行。

模型结果额外携带 citation.token/label，原 HTTP EvidencePage 和来源摘要不变。标记只从授权条目生成；正文引用按已提供标记校验，显示由真实权限解析。模板显示名可由包侧 reference_label 映射，见[回答与选择项](ai-responses.md)。


## KP 全房间查询

管理员上下文可带 `facts.aiReadScope='kp-room'` 与 `aiPolicyRevision`；查询传 `read_scope='kp-room'`，证据记录 readScope。宿主实际审核者和发起者均须为 KP、player 为空，且本机 AI 注册的 ai_room_read_authorizer 明确许可。PL／KP 的玩家级会话不使用此通道；普通聊天 API 不扩权。

`room` 查询按 JSON path 分片返回宿主状态，长文本带 textOffset/textLength。AI 生成侧强制 `roomMode=state`，返回 `sourceId=host-room-state`，排除 chat、commands、audit、outbox 和 AI 审批／发布流水。显式记录读取仍可使用引擎 records 模式；两类引用不能混用。按 ref 小批读取，结果预算仍生效。外发 room 混合分片要求 public/private/kp 三开关全部开启；不包含 Identity、本机配置、密钥或任意文件。关闭 allowAdminRoomRead 后旧上下文和新读取均拒绝。

state 投影只保留活动与执行中依赖的工件，标签标明 `[active]`／`[in-flight]`，详情附 `artifactUsage`。批准新候选产生的纯暂存工件不作为当前活动资料，也不改变此前 state 查询的证明；实际活动数据、执行中依赖、权限和外发变化继续失效。records 模式仍可显式查询原始暂存记录，不能作为已发布依据。

包独立资料必须由包适配器投影；新增类别可使用已有 config/memory，但不能仅凭 KP 角色推断获得全读授权。独立来源保留 consultationOnly 标记，执行候选须读取当前目标并由 KP 明确接受来源评估。

受信包适配器可实现 `read_scoped(state,account,*,read_scope=None)`。宿主先完成账号、发起者与全读开关校验，才传入 kp-room；普通路径传 None，旧 read(state,account) 保持兼容。包侧必须再次确认实际 KP，并仅在 kp-room 时追加全包状态和全场景聊天；关闭开关后旧证据复验失败。

管理工具 `room_manage_catalog({})` 先返回操作名称索引；用 `{operations:["entity.patch"]}` 按需取精确参数 Schema。原库接口 `Batches.catalog()` 不变。模型应先取目标参数再提交批次，避免反复注入完整操作目录。KP 任务诊断的 `contextBudget` 只含累计字节、上限、工具 Schema 和工具消息字节数，不记录资料内容；容量失败会在聊天中显示可操作的缩小查询提示。

读取活动游戏配置时，先用 room_read_management 的 room 节取得 activeRuleset，再按 `/artifacts/<revision>/data/game.json` 搜索 room 标签并按原样 ref 分批读。小文件可能合在父片，精确路径无结果时按 `/artifacts/<revision>` 查父片。宽 room 查询的证明绑定全部匹配记录，无关业务记录变化也可能使其失效；不能把最后一次 read 的 SOURCE_STALE 自动判定为该分片改变。查询过的每份证明都会复验。

## 配置包提供实体检索标签

KP 的实体搜索可调用受信适配器 `reference_label('entity', key, fallback)`；先完成实体投影、接收者交集和外发可见性校验，且实际审核者与发起者均为 KP 才使用该钩子。返回去除首尾空白后非空、不超过 160 字符且能编码为 UTF-8 的字符串，否则回退实体原名；异常也回退。PL 仍走个人知识查询，KP 与 PL 混合接收场景不调用该扩展。

该钩子只用于检索展示，资料必须与实体处于同一可见范围，不能夹带未授权剧情。标签可能注明角色所属玩家，帮助定位随机角色名；标签本身不是授权或执行证据，修改前仍须读取实际实体的 owner、configurationId 和 lifecycle。正文引用继续使用角色原名。实体原文、六字段 ref、数据摘要和可见性不变；标签变化会使旧搜索快照及查询证明失效，调用方须重新查询。

PL 在生成前自动预载本人空 query 目录，计入 24 次查询；非空关键词无匹配明确回退个人目录。目录不是详情证据，模型仍须读取引用。错误分类、已知目录和证据边界见[玩家已知资料](ai-player-knowledge.md#查询未命中与服务阻断)。创作申请无需数据查询，不借申请扩大已知范围。

## 2026-11-19 来源审核与调试

通用 room_manage_catalog 的公共操作 schema 不依赖 KP 正文外发；动态行动目录及私密查询仍受外发限制。模型必须继续读取实际物品/规则，不能把数值槽位当作无定义。详见[有效权限](ai-debug-review.md#有效权限和模型版本)。


## 活动配置数据的精确增量

2026-11-19 新增管理员只读工具 `pack_read_config_data`，解决模型把 `game.json` 的 items 分片当成整文件提交的问题。它只读当前任务绑定的活动工件，不读任意磁盘路径，也不修改房间。实际 KP、administrator 会话、allowDataQueries 和 KP 资料外发均须满足；PL 工具集合不包含它。

参数 `{file,path?,offset?,limit?}`：file 是活动工件中已有的数据文件键；path 是从文件根开始的字段名/非负整数索引数组，最多 32 段。limit 默认 12、最多 20；数组可分页，大对象返回子键目录后继续指定 path。普通查询仍用原四种数据工具；配置写作无需为保留未触及字段重拼整文件。

返回 editRef、revision、fileDigest、path、targetDigest、type 和读取内容/目录；complete 表示是否一次完整返回目标值。单次返回最多 28 KiB。editRef 只在本次生成中有效，不是客户端可自造的修改凭据，也不授予发布权限。

数组页另给出与 value 一一对应的 `positions:[{zeroBasedIndex,path}]`，包含分页偏移后的真实 JSON 路径。它不是运行时物品序号或实体 ID；业务命令仍按包作者声明的映射与实际定义取值。

模型 draft 可在 changeSet 之外附加 dataEdits：

```json
{
  "kind": "draft",
  "text": "追加物品定义，等待 KP 审批。",
  "changeSet": {
    "schemaVersion": 1,
    "configurations": [], "sources": {}, "data": {}, "suggestions": []
  },
  "dataEdits": [{
    "op": "append",
    "ref": "这里填写 pack_read_config_data 返回的 64 位 editRef",
    "keyField": "id",
    "value": {"id": "new-item", "name": "示例物品"}
  }]
}
```

先调用工具 `{file:"game.json",path:["items"]}`。示例 value 仅解释结构；实际必须提供配置包 Schema 要求的完整物品字段。未改动文件省略，不向 changeSet.data 填入半份 JSON。

| op | 目标和附加字段 | 前置条件 |
| --- | --- | --- |
| append | 对象数组；keyField、value | 整个基线数组的业务键类型一致且唯一，新键未存在；可用部分页取得 ref，不要求读取未触及的其他物品 |
| append | 非根字符串；字符串 value，不带 keyField | 已完整读取该字符串；直接拼接，原有文字保留 |
| append_value | 普通数组；任意 JSON value | 在末尾追加一个值，不假定元素或业务编号唯一；仍须通过作者 Schema 与引用校验 |
| add | 对象；key、value | 对象中该键不存在；只新增此键 |
| replace | 非根节点；value | 对应节点曾被完整返回；替换该节点，保留其余字段 |
| remove | 非根对象属性 | 对应节点曾被完整返回；不支持删除数组元素，避免隐式索引位移 |

只接受工具本次发出的 ref，并复核工件修订、完整文件及目标摘要。拒绝猜引用、版本变化、同文件同时完整替换和增量、真正重叠的修改。数组追加按原长度及本批已追加数计算实际末尾写位置，因此可与旧元素的独立字段修改共存，次序不限；整数组替换仍冲突。带 keyField 的追加在合并完成后再次校验唯一键，不能用后续字段修改制造重复键。缺失路径不会隐式创建；超大节点不能未经完整读取就替换。单批增量输入最多 64 KiB。

编译器在副本上展开完整文件：未触及字段取自权威基线，不能由模型猜测；任何编译错误都不产生部分候选。格式修复每次从同一基线重新展开，不能把上次追加重复累积。结构错误进入最多两次的共用技术修复流程；真正缺少玩法决策时仍询问用户。

增量最终形成完整 ChangeSet，沿用 A/B 硬校验、C 评估、差异及指纹；C 人工采纳的附加证明见[裁决](ai-rulings.md#c-类评估与可变依据)。完整候选会继续经过包 Schema、稳定数组/引用规则与游戏性检查，数据变更仍按高危人工审批。任务上下文分别保留 configDataReads 的原节点读取证明与 configDataEdits 的操作、路径和基线摘要；同一任务修复候选时保存本轮实际读取依据。历史只读显示允许仍存续节点的值更新，不放宽 editRef、批准或发布校验，具体边界见[历史授权](ai-session-access.md#同房间重启与历史)。该机制目前用于模型工具/输出编排；人工 HTTP ai.draft.create 仍提交原完整 ChangeSet，不接受顶层 dataEdits。

专项覆盖字段保留、分页外重复键、猜引用、过期基线、重叠编辑、数组删除限制、PL/外发/查询禁用以及真实三检后高危人工批准；该阶段首次失败和复验关系见[验收记录](../../../engineering/acceptance/ai-runtime/data-edits-results.json)。包侧真实模型复验独立记录。

阶段验收、初跑与复验关系见[开发记录](../../history/2026-11-20-ai-development-records.md)。
