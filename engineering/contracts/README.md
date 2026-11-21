# 首测机器契约

- `models.json`：账号、成员、房间/场次、实体、关系、配置、容器、规则工件、流程/等待、资源及个人记录。
- `messages.json`：命令、登录、回执、错误和授权投影形状。
- `operations.json`：各管理/行动操作的独立输入。保护字段不通过普通玩家 patch 开放。
- `ai-operations.json`：AI 命令输入；队列整理及提交关联字段的严格边界见下文，业务权限与执行由 AI 模块检查。
- `notifications.json`：绑定已提交宿主动作的持久定向通知、收件箱分页及逐收件人确认；send/ack 输入也登记在 operations.json，详见[定向通知](../../docs/current/engineering/notifications.md)。
- `fixtures/`：实体正例、非法字符串数值反例、初始化房间。初始化 fixture 的 activeRuleset 为 null，必须由 Host 加载工件后才是可运行房间。

文件顶层是 schema 名称到 JSON Schema Draft 2020-12 的映射。宿主同时检查语义不变量（权限、引用、循环、数量等），通过形状校验不等于可提交。Lua 短输入声明生成动态动作 schema，客户端表单直接消费该目录。

完整接口与字段生命周期见[首测工程](../../docs/current/engineering/first-test.md)。后端0.3.0只支持Room v4；`knowledge.json`定义持久策略、观察、授权、分面引用、只读证据、4项命令与5项读取/预览入口。完整格式、显式v3复制转换与独立版本号见[房间格式说明](../../docs/current/engineering/room-format.md)，使用方式见[个人知识服务](../../docs/current/engineering/player-knowledge.md)。旧Schema仅作历史资料，运行时不加载。ExecutionSnapshot是规则/AI验证的精简投影，不能作为Room加载。

本机身份管理使用独立的 [host-control.json](host-control.json)，授权绑定启动实例的 Windows 用户，不属于普通房间命令或 KP 权限。操作说明见[主机账号维护](../../docs/current/engineering/host-accounts.md)。

## AI 队列整理与提交关联字段

`ai.queue.archive` 要求 `targetId`、`digest`、布尔 `archived`；targetId 为 `request/batch/proposal/player/knowledge` 之一加冒号及 32 位小写十六进制 ID，digest 为 DTO queueDigest 对应的 64 位小写十六进制摘要。`reason` 为 1—500 字符，archived=true 时必填，false 时可省略。整理不等于取消业务、删除正文或回执；实际状态与权限仍由 AI 服务核验，Schema 通过不构成执行授权。

`ai.session.submit` 可选 `submissionKey`（1—200 字符）、`replyToRequestId`（32 位小写十六进制 ID）。`ai.player.request` 仅文本创建分支可选 submissionKey；使用 requestId 转交已有请求的分支不接受它。`ai.review.create` 仅 package source 分支可选 `correlationKey`（1—200 字符）。旧调用可不传这些字段；既有参数边界及 additionalProperties=false 保持，未给明确关联键时不由 Schema 推断业务关系。

上述是输入契约。服务端幂等、关联归属、归档资格及页面行为需由 AI／包侧联合验收；本次契约验证结果见[队列 Schema 验收](../acceptance/queue-schema/README.md)。
