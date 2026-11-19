# AI 会话权限与执行批次

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-16
- 最后更新：2026-11-17
- 关联文档：[管理面板](ai-manager.md)、[嵌入组件](ai-pack-embedding.md)、[资料查询](ai-data-query.md)、[剩余包侧与发布边界](../../plans/Issues/issue-010-ai-package-mutations.md)

## 会话边界

权限由房间宿主验证，不接受客户端或模型指定账号。会话创建时保存 `owner` 与 `accessLevel`，两者不可经更新接口改写；KP 默认创建 `administrator`，也可选择 `player`；PL 只能创建 `player`。旧会话首次加载时按创建者当前房间角色补齐等级，旧回答没有玩家权限证据时不会转给玩家或带入玩家历史。

| 身份／会话 | 目录与历史 | 模型资料与操作 |
| --- | --- | --- |
| KP | 本房间全部未删除会话，可筛选本人；可管理他人标题、设置、归档与删除 | 管理员会话使用 KP 授权资料；可查询房间管理资料及所有会话、提出执行批次 |
| PL | 仅绑定本人且为玩家级的会话 | 只选择、查看本人授权知识证据；向 KP 提交需求；不取得审批和执行权限 |
| KP 创建的玩家会话 | 创建者仍是 KP，不可冒充其他玩家 | 使用创建者的玩家视角投影，不能通过 KP 实际角色读取管理员资料 |

只有创建者可在会话中发送新需求。KP 查看其他玩家会话不代表代替玩家发言。成员退出、撤权、来源修改、策略更新和会话删除会使相关生成／历史依据失效；已有回答可能显示“依据已变化”。宿主原有私聊参与者边界仍有效，管理员会话不赋予读取未参与私聊或本机凭据的权限。KP 可读其他管理员提案和报告，已有配置提案的修订／检查／发布仍绑定原审核人。

房间策略保存在独立 AI 仓库 `settings.accessPolicy`。`allowPlayerChat`、`autoApproveBatches`、`autoApproveConfigurations` 均默认 false。KP 在“服务与权限”保存策略时，服务端记录本次 KP 为授权执行人，客户端不能传入执行人字段。更新带 `revision` 防止覆盖。

- 关闭玩家对话：PL 不能创建、读取、更新、提交会话，不能绕过会话入口调用需求／资料查询；用量和本人原回执仍可核对。
- 开启玩家对话：提交直接使用所记录的有效 KP 执行人排队，模型始终受绑定玩家的数据权限上限约束。KP 可查看队列及会话；KP 自建玩家会话直接以本人执行、沿用玩家上限；PL 可读取通过当前来源复验的回答，不能读取诊断、完整提案报告或其他会话。
- AI 调用开关、服务配置和外发范围仍须有效。自动转交失败保留原需求，提交结果带 `dispatchError`；不自动重复提交，可由 KP 在原需求上重试转交。

## 数据与记忆

玩家会话使用按需查询，不把完整房间实体、源码或 KP 记忆预先送入模型。查询证据保存服务端选定的玩家身份并在每次调用、生成完成、历史复用和发布校验时复验；身份不是模型可传参数。引用与资料查询共用投影，KP 在玩家会话中也不能绕过。

严格 PL 使用宿主个人知识服务，公开、本人拥有或旧 adapter 的 `entities/known_configurations` 均不能代替披露记录。包必须安装并绑定知识策略，提供固定分面和明确的持续告知来源；缺失或故障时拒绝。完整包契约、作者指南、原始聊天和共享记忆不进入 PL 模型上下文；模型自由生成正文不能作为已知事实展示。具体契约见[AI 玩家已知资料](ai-player-knowledge.md)。

Stumpsville 的进入／再次进入或 KP 定向揭示保存当时场景分面。本人角色表通过 KP 显式持续告知授权；场景不订阅未来变化。旧地点集合不自动转成知识，需 KP 选择“现在揭示”。AI 查询不会写入知识记录，玩家配置需求供 KP 查看，严格回答不直接代写可执行配置；KP 可在管理员会话中编写并走原裁决流程。

会话 `historyTurns` 仍为 0—4（默认 4），长期记忆仍需 KP 确认。复用回答时保留原查询及历史上下文证据，并在生成前后持续复验；包侧资料撤回后不会继续返回基于旧经历的结论。会话归档不会改变权限或加载配置；删除会取消关联任务并从目录／聊天读取中移除，保留墓碑、执行回执、需求及用量审计，防止重复执行和历史账目丢失。上限为 200 个未删除会话、每会话 100 请求；含删除审计的会话记录最多 5000。

## 执行批次

管理员模型额外获得 `room_manage_catalog`、`room_read_management`、`room_read_sessions`。三个管理工具还要求允许外发 KP 信息；管理员身份不能绕过房间外发开关。管理资料按 section/offset/limit 分页，会话查询同样分页。工具只读；真正变更以以下输出提交，最多 8 项、参数总量不超过 32 KiB：

```json
{"kind":"batch","text":"修改理由与预期影响","actions":[{"target":"host","op":"entity.patch","args":{"id":"对象ID","name":"新名称"}}]}
```

操作白名单及精确参数来自宿主／AI 模块的现有机器 Schema。已接入实体、关系、进度、资源关联、流程、成员、房间状态、公开行动、可授权聊天操作，以及会话增改删除和记忆管理。实体删除沿用引擎归档语义；包内独立状态不是任意可写数据库。

批次固定动作、参数、会话、创建者、上下文、宿主 epoch 和房间基线摘要；审核不能顺便修改参数。KP 查看完整动作后“批准并执行”或拒绝。房间／会话基线变化返回 `BATCH_STALE`，需重新生成；不得拿旧批准套用新参数。自动批准开启时使用已记录 KP 执行相同校验，但不绕过宿主权限和数据契约。

每项使用固定命令 ID 保存执行意图与回执，顺序执行、失败即停止；已完成项不自动回滚。状态为 pending / executing / completed / rejected / partial / unknown。旧 batch.approve 接口拒绝重复批准；统一裁决接口对已完成项返回原结果；网络或存储结果未知、重启中断时，只能查询原执行回执，不重放整批。`reconcile` 不执行剩余动作；剩余工作需重新生成并审核新批次。

配置与规则修改通过三检后进入同一 KP 裁决队列，一次批准记录风险决定并加载整批；自动批准分为运行时与配置两个开关。确认绑定、接口、恢复及 Stumpsville 扩展范围统一见[修改裁决](ai-rulings.md)。配置删除和包侧独立事务仍未接入。

## 运行时写入目标与树桩镇限制

以下是管理员 AI 批次的白名单，不是任意数据库写权限；还须通过命令 Schema、宿主权限、当前状态及批次基线复验。

| 目标 | 当前允许的命令 | 边界 |
| --- | --- | --- |
| 实体实例 | entity.create / patch / update / archive | 使用现有模板；名称、数值、可见性等依命令 Schema；删除是归档 |
| 关系、进度、资源关联 | relation.set/remove、progress.set、asset.attach/remove | 修改宿主公开数据模型，不写任意文件 |
| 流程、公开行动 | flow.respond/retry/cancel、action.invoke、behavior.invoke | 只能调用目录中真实入口；遵循原裁决／执行规则 |
| 房间和成员 | room.status、member.add/update | 仍受宿主身份、状态与参数约束 |
| 宿主聊天 | chat.direct.open、chat.channel.create/update、chat.message.send/share/edit/retract | 不绕过频道参与者和消息操作权限；不等同于包侧 scopedChat |
| AI 会话与记忆 | ai.session.create/update/delete、ai.memory.create/confirm/revoke | 留审计与回执；不能借此修改密钥或房间 AI 权限开关 |
| 配置模板与规则 | 独立 kind=draft 路径 | add/replace 经 A/B/C、审核、发布；批次不直接发布，删除未接入 |
| 包侧独立状态 | 尚无 package 批次目标 | 用已有包界面处理；新增 AI 适配见 ISSUE-010 |

树桩镇沿用 `sv.npc` 创建 NPC，只是增加实体及其名称、位置、属性、可见性，不需要配置扩展点。新 NPC 即使设为 public，也不会自动写逐玩家 `actorDiscoveries`，不能保证出现在玩家联系人／AI 已知人物中；KP 可使用包操作 `actor.reveal` 向指定玩家生成身份固定观察；撤回会撤销对应 identity 授权。旧联系人标记不再作为 AI 读取依据。该操作目前不在 AI 批次目录内。

“剧情标记没有写入适配器”需按存储归属理解：`sv.scene` 实体的 `numbers`（如 villagersFreed、ernieAwake）可通过宿主实体／行动命令修改；`package.json` 的发现、地点公开、个人线索、申请、队列、反馈、回执等独立状态不能直接由 AI 批次修改。包的场景流程还会在宿主数值和包内 sceneState／库存／门状态间同步；直接 patch 一个字段不会完成这些业务副作用，某些字段还会被后续同步覆盖。应优先走既有包场景流程；没有完整适配时只提交独立安全的实体修改，说明需 KP 处理的后续一步。

NPC 对话提示目前是给 KP 的设计文本；创建实例不会注册新的对话分支、互动按钮或自动剧情规则。新增行为由包作者实现，通用包事务注册／版本／幂等回执契约则需 AI／引擎基础支持。以上是当前代码核查，不代表已经为某个正式房间执行了操作。

## 接口与界面

| 接口 | 内容 |
| --- | --- |
| `GET ai/access` | 当前角色、canChat、defaultLevel、策略 revision 和三个开关；不返回授权执行人 |
| `GET ai/batches` | KP 的本房间执行批次列表、动作与逐项回执 |
| `ai.access.update` | `{revision,allowPlayerChat,autoApproveBatches,autoApproveConfigurations?}`；仅 KP |
| `ai.session.create` | `{title,accessLevel?}`；创建者从真实登录绑定 |
| `ai.session.delete` | `{sessionId,revision}`；本人或 KP；幂等回执 |
| `ai.batch.approve/reject/reconcile` | `{batchId,digest}`；仅 KP，原摘要绑定 |

路径相对于 `/api/v1/`；命令使用已有 AI command 封套及 Origin/CSRF。`AiClient` 提供 `aiAccess/aiBatches`，`createAITools` 提供 `access`、`batches` 和 `sessions.delete`。会话 `owner/accessLevel/deleted` 类型、完整操作参数见模块 `index.d.ts` 和 `GET ai/contracts`。

可嵌入会话管理提供进行中／已归档／全部目录，KP 可筛选仅本人，创建时选择等级，显示固定创建者，删除前二次确认。归档后自动切换到已归档目录，恢复后切回进行中。打开管理弹窗暂停对话轮询；写入后作废旧响应，关闭后恢复。自装配 `mountChat` 可用 `applySessionChange(session)` 接收管理操作结果；删除时 `onSelect/onSession` 可能收到 null。

审核面板拆为“需求与审核／服务与权限／AI 修改裁决”，本机管理器侧栏可折叠，小屏改为覆盖式目录。树桩镇的现有设置面板同步提供三个策略开关和嵌入裁决队列；网页玩家桥仅增加 access 读取和本人会话删除，不开放管理命令。

升级后重启房间宿主、本机管理器并刷新页面；树桩镇网页导出需重新生成，以包含同一版组件与 adapter。验证使用隔离测试存档和离线模型，无需真实密钥；验收入口为 `test_access_batches.py`、`test_access_ui.py` 与包内 `tests/verify_map_ai.py`。

2026-11-16 验收：模块按测试 ID 去重 323 项、树桩镇 32 组通过，覆盖分级权限、直接排队、批次审批／恢复、归档／删除、双网页玩家及原生 KP。均使用隔离存档和离线服务，未调用真实模型或修改正式存档；[验收汇总](../../../engineering/acceptance/ai-runtime/session-access-results.json)保存逐项结果、复测关系和源码摘要。
