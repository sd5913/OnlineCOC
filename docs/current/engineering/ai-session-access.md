# AI 会话权限与执行批次

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-16
- 最后更新：2026-11-20
- 关联文档：[管理面板](ai-manager.md)、[嵌入组件](ai-pack-embedding.md)、[资料查询](ai-data-query.md)、[剩余包侧与发布边界](../../plans/Issues/issue-010-ai-package-mutations.md)

## 会话边界

权限由房间宿主验证，不接受客户端或模型指定账号。会话创建时保存 `owner` 与 `accessLevel`，两者不可经更新接口改写；KP 默认创建 `administrator`，也可选择 `player`；PL 只能创建 `player`。旧会话首次加载时按创建者当前房间角色补齐等级，旧回答没有玩家权限证据时不会转给玩家或带入玩家历史。

| 身份／会话 | 目录与历史 | 模型资料与操作 |
| --- | --- | --- |
| KP | 本房间全部未删除会话，可筛选本人；可管理他人标题、设置、归档与删除 | 管理员会话使用 KP 授权资料；可查询房间管理资料及所有会话、提出执行批次 |
| PL | 仅绑定本人且为玩家级的会话 | 只选择、查看本人授权知识证据；向 KP 提交需求；不取得审批和执行权限 |
| KP 创建的玩家会话 | 创建者仍是 KP，不可冒充其他玩家 | 使用创建者的玩家视角投影，不能通过 KP 实际角色读取管理员资料 |

只有创建者可在会话中发送新需求。KP 查看其他玩家会话不代表代替玩家发言。成员退出、撤权、策略更新和会话删除会使相关生成／历史授权失效；来源只发生版本变化时，管理员仍可能按下述只读历史规则查看旧回答。普通聊天接口仍按参与者授权。管理员 AI 默认可通过受信 kp-room 查询读取全房间游戏资料，包括其他频道和历史工件；可由 allowAdminRoomRead 关闭，外发仍受三类开关约束；本机凭据不属于房间资料。KP 可读其他管理员提案和报告，已有配置提案的修订／检查／发布仍绑定原审核人。

房间策略保存在独立 AI 仓库 `settings.accessPolicy`。`allowPlayerChat`、`autoApproveBatches`、`autoApproveConfigurations` 均默认 false。KP 在“服务与权限”保存策略时，服务端记录本次 KP 为授权执行人，客户端不能传入执行人字段。更新带 `revision` 防止覆盖。

- 关闭玩家对话：PL 不能创建、读取、更新、提交会话，不能绕过会话入口调用需求／资料查询；用量和本人原回执仍可核对。
- 开启玩家对话：提交直接使用所记录的有效 KP 执行人排队，模型始终受绑定玩家的数据权限上限约束。KP 可查看队列及会话；KP 自建玩家会话直接以本人执行、沿用玩家上限；PL 可读取通过当前来源复验的回答，不能读取诊断、完整提案报告或其他会话。
- AI 调用开关、服务配置和外发范围仍须有效。自动转交失败保留原需求，提交结果带 `dispatchError`；不自动重复提交，可由 KP 在原需求上重试转交。

## 数据与记忆

玩家会话使用按需查询，不把完整房间实体、源码或 KP 记忆预先送入模型。查询证据保存服务端选定的玩家身份并在每次调用、生成完成、历史复用和发布校验时复验；身份不是模型可传参数。引用与资料查询共用投影，KP 在玩家会话中也不能绕过。

严格 PL 使用宿主个人知识服务，公开、本人拥有或旧 adapter 的 `entities/known_configurations` 均不能代替披露记录。包必须安装并绑定知识策略，提供固定分面和明确的持续告知来源；缺失或故障时拒绝。完整包契约、作者指南、原始聊天和共享记忆不进入 PL 模型上下文；模型自由生成正文不能作为已知事实展示。具体契约见[AI 玩家已知资料](ai-player-knowledge.md)。

Stumpsville 的进入／再次进入或 KP 定向揭示保存当时场景分面。本人角色表通过 KP 显式持续告知授权；场景不订阅未来变化。旧地点集合不自动转成知识，需 KP 选择“现在揭示”。AI 查询不会写入知识记录，玩家配置需求供 KP 查看，严格回答不直接代写可执行配置；KP 可在管理员会话中编写并走原裁决流程。

会话 `historyTurns` 为 0—4（默认 4），长期记忆需 KP 确认。有效回答沿用原查询证据；过期但仍可查看的管理员回答只保留历史意图，规则见下文。生成前后持续复验权限，撤回的包资料不作为历史恢复。会话归档不会改变权限或加载配置；删除会取消关联任务并从目录／聊天读取中移除，保留墓碑、执行回执、需求及用量审计，防止重复执行和历史账目丢失。上限为 200 个未删除会话、每会话 100 请求；含删除审计的会话记录最多 5000。

## 执行批次

管理员模型额外获得 `room_manage_catalog`、`room_read_management`、`room_read_sessions`。通用操作名称／Schema 可在 KP 外发关闭时读取；动态行动目录及另外两类管理正文仍要求 KP 外发许可。管理员身份不能绕过房间外发开关。管理资料按 section/offset/limit 分页，会话查询同样分页。工具只读；真正变更以以下输出提交，不设动作条数上限、参数总量不超过 32 KiB：

```json
{"kind":"batch","text":"修改理由与预期影响","actions":[{"target":"host","op":"entity.patch","args":{"id":"对象ID","name":"新名称"}}]}
```

操作白名单及精确参数来自宿主／AI 模块的现有机器 Schema。已接入实体、关系、进度、资源关联、流程、成员、房间状态、公开行动、可授权聊天操作，以及会话增改删除和记忆管理。实体删除沿用引擎归档语义；包内独立状态不是任意可写数据库。

批次固定动作、参数、会话、创建者、上下文、宿主 epoch 和房间基线摘要；审核不能顺便修改参数。KP 查看完整动作后“批准并执行”或拒绝。房间／会话基线变化返回 `BATCH_STALE`，需重新生成；不得拿旧批准套用新参数。自动批准开启时使用已记录 KP 执行相同校验，但不绕过宿主权限和数据契约。

每项使用固定命令 ID 保存执行意图与回执，顺序执行、失败即停止；已完成项不自动回滚。状态为 pending / executing / completed / rejected / partial / unknown。旧 batch.approve 接口拒绝重复批准；统一裁决接口对已完成项返回原结果；网络或存储结果未知、重启中断时，只能查询原执行回执，不重放整批。`reconcile` 不执行剩余动作；剩余工作需重新生成并审核新批次。

配置与规则修改通过三检后进入同一 KP 裁决队列，一次批准记录风险决定并加载整批；自动批准分为运行时与配置两个开关。确认绑定、接口、恢复及 Stumpsville 扩展范围统一见[修改裁决](ai-rulings.md)。配置删除使用高危候选与引用完整性校验；包侧独立事务仍未接入。

## 批次中的定向通知

`notification.send` 是同一待审核批次中的独立宿主动作。AI 参数为 `{recipientAccountIds,text,sourceActionIndex}`；索引从 0 开始，只能指向此前的受支持宿主修改动作。候选和摘要不意味着已送达，界面显示接收人、消息及绑定步骤。原申请人由 reviewSource.requestedBy 解释；当前 KP 不自动成为受影响玩家。

执行器只在原动作有 committed 回执后填入真实 sourceCommandId/sourceOp；模型不能指定这两个字段。宿主还验证原动作归属和支持范围；带 flowId 的流程启动回执不能证明动作完成，后续结束也不会自动升级这张启动回执，见[定向通知](notifications.md)。前序失败/unknown 停止批次；通知失败保留 partial/unknown 与原回执，不回滚已成功动作。对账不补发剩余通知，也不重放原动作；确认实际结果后另行安排后续工作。配置发布仍走独立 draft，不宣称已接入同批发布通知。

## 运行时写入目标与树桩镇限制

以下是管理员 AI 批次的白名单，不是任意数据库写权限；还须通过命令 Schema、宿主权限、当前状态及批次基线复验。

| 目标 | 当前允许的命令 | 边界 |
| --- | --- | --- |
| 实体实例 | entity.create / patch / update / archive | 使用现有模板；名称、数值、可见性等依命令 Schema；删除是归档 |
| 关系、进度、资源关联 | relation.set/remove、progress.set、asset.attach/remove | 修改宿主公开数据模型，不写任意文件 |
| 流程、公开行动 | flow.respond/retry/cancel、action.invoke、behavior.invoke | 只能调用目录中真实入口；遵循原裁决／执行规则 |
| 房间和成员 | room.status、member.add/update | 仍受宿主身份、状态与参数约束 |
| 宿主聊天 | chat.direct.open、chat.channel.create/update、chat.message.send/share/edit/retract | 不绕过频道参与者和消息操作权限；不等同于包侧 scopedChat |
| 定向通知 | notification.send | 独立审核动作，绑定同批此前成功且流程完成的宿主修改；模型只指定 sourceActionIndex |
| AI 会话与记忆 | ai.session.create/update/delete、ai.memory.create/confirm/revoke | 留审计与回执；不能借此修改密钥或房间 AI 权限开关 |
| 配置模板与规则 | 独立 kind=draft 路径 | 模板 add/replace/remove 经三检发布；规则源以完整 Lua 新增/替换，未提供源文件删除操作；模板删除高危且拒绝仍被引用的目标 |
| 包侧独立状态 | 尚无 package 批次目标 | 用已有包界面处理；新增 AI 适配见 ISSUE-010 |

树桩镇沿用 `sv.npc` 创建 NPC，只是增加实体及其名称、位置、属性、可见性，不需要配置扩展点。新 NPC 即使设为 public，也不会自动写逐玩家 `actorDiscoveries`，不能保证出现在玩家联系人／AI 已知人物中；KP 可使用包操作 `actor.reveal` 向指定玩家生成身份固定观察；撤回会撤销对应 identity 授权。旧联系人标记不再作为 AI 读取依据。该操作目前不在 AI 批次目录内。

“剧情标记没有写入适配器”需按存储归属理解：`sv.scene` 实体的 `numbers`（如 villagersFreed、ernieAwake）可通过宿主实体／行动命令修改；`package.json` 的发现、地点公开、个人线索、申请、队列、反馈、回执等独立状态不能直接由 AI 批次修改。包的场景流程还会在宿主数值和包内 sceneState／库存／门状态间同步；直接 patch 一个字段不会完成这些业务副作用，某些字段还会被后续同步覆盖。应优先走既有包场景流程；没有完整适配时只提交独立安全的实体修改，说明需 KP 处理的后续一步。

NPC 对话提示目前是给 KP 的设计文本；创建实例不会注册新的对话分支、互动按钮或自动剧情规则。新增行为由包作者实现，通用包事务注册／版本／幂等回执契约则需 AI／引擎基础支持。以上是当前代码核查，不代表已经为某个正式房间执行了操作。

## 接口与界面

| 接口 | 内容 |
| --- | --- |
| `GET ai/access` | 当前角色、canChat、defaultLevel、策略 revision 和下文列出的权限／自动审批开关；不返回授权执行人 |
| `GET ai/batches` | KP 的本房间执行批次列表、动作与逐项回执 |
| `ai.access.update` | `{revision,allowPlayerChat,autoApproveBatches,...}`；可选字段包含配置自动审批及下文五个权限开关，仅 KP |
| `ai.session.create` | `{title,accessLevel?}`；创建者从真实登录绑定 |
| `ai.session.delete` | `{sessionId,revision}`；本人或 KP；幂等回执 |
| `ai.batch.approve/reject/reconcile` | `{batchId,digest}`；仅 KP，原摘要绑定 |

路径相对于 `/api/v1/`；命令使用已有 AI command 封套及 Origin/CSRF。`AiClient` 提供 `aiAccess/aiBatches`，`createAITools` 提供 `access`、`batches` 和 `sessions.delete`。会话 `owner/accessLevel/deleted` 类型、完整操作参数见模块 `index.d.ts` 和 `GET ai/contracts`。

可嵌入会话管理提供进行中／已归档／全部目录，KP 可筛选仅本人，创建时选择等级，显示固定创建者，删除前二次确认。归档后自动切换到已归档目录，恢复后切回进行中。打开管理弹窗暂停对话轮询；写入后作废旧响应，关闭后恢复。自装配 `mountChat` 可用 `applySessionChange(session)` 接收管理操作结果；删除时 `onSelect/onSession` 可能收到 null。

审核面板拆为“需求与审核／服务与权限／AI 修改裁决”，本机管理器侧栏可折叠，小屏改为覆盖式目录。树桩镇的现有设置面板同步提供完整权限开关和嵌入裁决队列；网页玩家桥按包声明开放本人会话、资料披露和创作申请，不开放审批或管理命令。

升级后重启房间宿主、本机管理器并刷新页面；树桩镇网页导出需重新生成，以包含同一版组件与 adapter。验证使用隔离测试存档和离线模型，无需真实密钥；验收入口为 `test_access_batches.py`、`test_access_ui.py` 与包内 `tests/verify_map_ai.py`。

支持独立挂载的 KP 服务／权限设置页和紧凑裁决详情弹窗；任务列表直接返回会话定位，恢复会话减少串行读取。接口、分发、iframe 限制与性能证据统一见[嵌入指南](ai-pack-embedding.md#独立设置与紧凑裁决)。


## 查询、写入与玩家申请开关

`allowAdminRoomRead`、`allowDataQueries`、`allowRuntimeChanges`、`allowConfigurationChanges`、`allowKnowledgeRequests`、`allowPlayerRequests` 默认 true；分别控制管理员全房间读取、模型查询工具、运行时修改、配置修改、资料披露申请、创作申请。旧存档缺失的新字段按默认值加载，不要求重建房间。`allowPlayerChat` 和两类普通自动批准仍默认 false。新旧设置面板均显式提供这些开关；高危必须人工确认是不可关闭的策略。权限版本进入新生成上下文，变更后旧依据须重新校验。

玩家点击“向 KP 申请披露”调用 `ai.knowledge.request {sessionId,requestId}`，绑定本人玩家会话和原问题；只有用户明确点击才提交，不能替其他玩家申请。同一问题去重。任务与会话 DTO 的 `knowledgeRequest` 返回 pending/completed/rejected/partial/unknown/executing 等状态，不包含 KP 未授权目标或拒绝细节。

KP 从 `kind:knowledge_request` 队列选择真实资源和分面，先使用宿主知识 preview 取得当前 sourceRevision，再提交 `ai.ruling.decide {rulingId,digest,decision:'approve',disclosures:[{op:'knowledge.observe',args:{...}}]}`。subjectMemberId 必须对应申请人；不能通过申请给其他人披露。只有真实观察命令全部成功才标 completed；拒绝不写知识，未知结果用 ai.knowledge.reconcile 核对，不能盲目重做。跨账本新线索写入不在本接口范围。

## 玩家创作与配置申请

`ai.player.request` 是主动提交业务意图的独立入口，与 `ai.knowledge.request` 的资料披露分开。需 `allowPlayerChat` 与 `allowPlayerRequests` 开启、本人未归档的玩家级会话。两种互斥参数：

- `{sessionId,text}`：直接记录原需求并申请；纯文本无需启动模型、知识服务或 private 外发。显式引用仍须通过当前引用校验，过期引用可改为普通文字或转交已有 requestId。
- `{sessionId,requestId}`：转交同一会话已有原问题；按原 requestId 去重，不采用模型生成的替代文字。

模型仅可返回 `next:ask_kp_change` 建议提交，不能自动创建申请。`Task.playerRequest` 仅含 rulingId/sessionId/requestId/status/createdAt/digest；pending、accepted、rejected、cancelled 不等同于修改已执行。玩家看不到 KP 审核会话、草稿、秘密材料或生成错误细节。

KP 队列 `kind:player_request` 显示原需求。批准的含义是**接收并生成方案**：在当前 KP 名下创建私有 administrator 会话。KP 请求使用通用审核指令，原玩家发言、原申请人和裁决定位独立保存为 `reviewSource`，不会冒充 KP 发言。原文只表达需求，生成的修改始终另行人工批准；重复接收复用审核会话。外发、引用、来源跳转和统一转交接口见[来源审核](ai-debug-review.md#来源审核)。

该审核会话的运行时批次和普通配置也必须另行人工批准，`autoApproveBatches/autoApproveConfigurations` 不会自动处理它们；高危指纹和三检保持原要求。接收时生成失败会保存 KP 可见 generationError，原审核会话仍可打开并由 KP 重试转交；重启不自动创建第二个会话或重发模型。实际执行按既有批次／配置回执核对。

未接收前取消原问题或删除会话会取消申请；归档后不能新增申请。已接收的审核会话是 KP 独立工作，删除 PL 原会话不撤销已接收的方案，也不授予 PL 取消 KP 工作的权限。历史误分类的资料申请保留，不自动改写正式房间。

## 同房间重启与历史

会话记录保存在原房间 AI 仓库；同目录重启不重建 scope，旧进程标识不单独使历史失效。管理员历史区分两种情况：依据仍有效时保留原证明；只有版本或基线变化、且原对象仍存在并可查看时，保留旧回答并标记过期。账号撤权、来源删除、会话删除、外发策略改变、跨 scope、无法证明的包投影变化仍隐藏正文。严格玩家知识继续精确复验，不使用管理员回退。

任务 DTO 为 `sourceState:"stale"`、`sourceError`、`sourceNotice`、`historicalReadOnly:true`，同时保留 `text/response/initiator`。已有待审/待补充回答可以显示 stale；queued/generating/validating、失败/取消以及 published/completed/rejected/partial/unknown 保留真实工作状态。自绘队列应显示 sourceNotice，不把“可读”解释为“旧候选可执行”。

后续短句确认可携带 `authority:"historical-intent-only"` 的旧回答；`facts.historyIntents` 保存原任务与上下文定位，持续复验查看权限。historyIntents 的旧资料过期不传播到新任务；historyContexts 仍作为事实依赖复验。不会把旧 sourceRefs、dataQueries、historyContexts 当作新执行证明。修改候选必须重新读取当前目标。服务端对直接实体目标按标识检查新读取，对配置候选检查模板/规则/配置节点读取；其他动作至少要求本轮当前读取，并继续通过宿主基线、权限和人工审核。缺少读取返回 `HISTORY_REQUERY_REQUIRED`，进入原模型修复额度，要求查询而不是重复追问已确定的方案。

旧存档不强制要求新字段：原 sourceRefs 或 read/case 参数中的对象标识可用于存在性与权限复验。旧 search/chat 仅有摘要且结果已变化时，无法证明原返回对象是否已删除，返回 `HISTORY_PROVENANCE_INCOMPLETE` 并隐藏旧正文；重新描述需求、查询当前资料后继续，不伪造来源。新查询保存 readRefs，管理查询保存实际返回键；复合事件、独立包投影及配置子树仍使用更保守的来源检查。

生成中的当前任务、未消费批准和待执行批次继续绑定运行标识；重启后不自动重发模型、批准或重放动作。需要新方案时重新读取、生成、校验和审批，未知执行按原回执对账。变更恢复为新 scope 的房间不能沿用旧历史授权。

阶段验收、初跑与复验关系见[开发记录](../../history/2026-11-20-ai-development-records.md)。
