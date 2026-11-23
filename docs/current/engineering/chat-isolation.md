# 聊天与 AI 状态依赖隔离

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-21
- 最后更新：2026-11-22
- 关联文档：[工程索引](README.md)、[首测引擎](first-test.md)、[高风险发布](high-risk-publication.md)、[AI 数据查询](ai-data-query.md)

## 轻量频道读取

`GET /api/v1/chat/channels` 使用当前登录身份，返回 `roomId`、`authorityEpoch`、`authorizationEpoch`、`accountId`、`channels`。`channels` 与该账号 `/api/v1/view` 的 `chatChannels` 结构和可见范围一致，包含当前发送权限、已读位置、未读数和频道序号，不构造实体、规则目录或知识投影。

该接口仍读取房间快照、检查成员有效性和每个频道的读取权限。KP 不因此获得其他成员私聊的访问权；包专用频道的额外场景、队伍限制仍由包适配层处理。

## 状态查询与完整记录查询

宿主 `data_queries.query` 在 `read_scope='kp-room'` 的 `search` 中支持 `roomMode`：

| 模式 | 范围 | 引用 sourceId |
| --- | --- | --- |
| `records`（宿主默认） | 当前完整持久化房间，包括聊天、命令、审计、outbox 和 AI 审批/发布记录 | `host-room` |
| `state`（显式选择） | 排除 `chat`、`commands`、`audit`、`outbox`；`aiControl` 仅保留 schemaVersion、scopeId、packBinding、settings、memoryFacts；其余房间字段保留 | `host-room-state` |

`roomMode` 仅用于包含 `room` 类型的全房间查询。`read` 会按引用的 `sourceId` 自动选择对应模式，同一请求不接受混合的 `host-room` 和 `host-room-state` 引用。直接调用 `rows` 的内部使用者需要传入 `room_mode='state'` 才能生成稳定状态引用。

查询证明仍绑定授权范围、当前外发策略、包适配器摘要、查询参数及其完整结果。实体、成员、配置、规则、知识、确认记忆和设置变化仍可能使旧证明失效。普通聊天不改变状态查询的宿主结果；明确读取的聊天记录仍保留原有消息版本和摘要依赖。包适配器返回的数据仍参与查询证明，适配器必须自行避免把无关聊天或作业总版本绑定到业务状态。

宿主 `world_digest` 本来就不包含聊天，本次没有放宽世界基线校验。发布仍验证当前权限、作用域、候选摘要、审批期限、引用及世界/配置/规则依据。

## 提交与投影开销

- 没有流程和等待项时，聊天提交直接从刚提交的状态形成回执，避免重复 tick 和回执快照；仍执行房间事务及持久化提交。
- 空闲 tick 按存储 generation 跳过重复快照；发生提交后重新判断。
- 账号投影按房间 generation、账号和来源版本缓存，最多保留 128 个键，返回独立深拷贝。任何提交使旧缓存失效。有知识策略时，仅当全部受信提供者显式实现 `projection_revision()`，且构造前后版本一致才缓存；未实现、异常或来源不明则逐次读取。提供者注册更替也使旧键失效，详见[引擎性能与来源失效](engine-performance.md)。
- WebSocket 在发送结束前仍检查当前认证；没有外部知识依赖且 generation 未变时，使用 generation 判断同一快照，避免再次构造投影。generation 或知识条件变化时保留重算校验及 reset 行为。
- 审批 schema 使用完整字节作为有界缓存键，仅复用已经通过结构验证且内容完全相同的记录。缓存上限 16 MiB、1000 条，单条上限 2 MiB；非 JSON 类型、循环和超大树不进入缓存。修改后的记录重新验证。跨记录引用、制品摘要和发布时的当前权限/依据校验不缓存。

## 验证证据

专项及浏览器对照位于 [chat-isolation 验收目录](../../../engineering/acceptance/chat-isolation/)。测试使用独立合成房间和账号，不读写正式存档，不调用外部模型 API。

三浏览器测试使用 KP、PL1、PL2 独立会话，房间预置 1200 条历史消息并增加 120 个实体；轮流发送 30 条消息，同时提交 4 次真实宿主 AI 审批。依赖隔离实验和审批均成功的性能对照分别记录，避免把旧版审批失败形成的轻负载当作性能优势。具体样本、分位数、失败率和首轮失败以该目录的 JSON/XML 为准；结果限于同机合成负载，包界面和公网延迟由对应联测单独确认。
