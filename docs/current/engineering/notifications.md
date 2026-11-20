# 持久定向操作通知

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 关联文档：[运行入口](first-test.md)、[房间格式](room-format.md)、[机器契约](../../../engineering/contracts/notifications.json)、[专项验收](../../../engineering/acceptance/notifications/README.md)

## 动作与通知

`notification.send` 是显式宿主命令，复用 `/api/v1/commands`、当前身份、epoch、Origin/CSRF 和持久回执。仅当前有效 KP 可发送，且 sourceCommandId 必须指向该 KP 自己已 committed 的宿主命令，sourceOp 必须相符。客户端不能上传“原操作成功”来代替宿主回执；失败、pending、unknown 或缺失来源均拒绝。流程启动回执只确认进入流程，即使有 flowId 也不能据此通知动作完成。

通知须作为提交指令包中的独立操作，与原动作、接收账号及文字一起供人审核。引擎不会根据前端快照变化自动推送；AI 批次或包侧 Job 负责按已批准的顺序提交原动作及通知，并保存每步回执。通知失败不撤销已提交原动作；恢复时查询原回执，只恢复尚未确认的通知步骤，不重做装备或属性操作。sourceCommandId 可定位部分完成的具体动作，不代表整批成功。

```json
{
  "op": "notification.send",
  "args": {
    "recipientAccountIds": ["player1"],
    "text": "生命值已调整为 8",
    "sourceCommandId": "原宿主动作ID",
    "sourceOp": "entity.update"
  }
}
```

以上为命令 payload 的 op/args，外层仍须完整宿主命令封套。成功回执的 `result` 是 `{notificationId,sequence}`。通知 ID 由发送者与原动作 ID 确定；同一原动作最多一条通知，可指定多个受众。即使换发送命令 ID，相同受众和文字仍返回原通知；受众或文字改变返回 `NOTIFICATION_CONFLICT`，不会重发或重置已确认状态。多接收者共用同一段文字，不能包含只应向其中一人披露的细节。

允许的来源操作为 `entity.create/update/patch/archive`、`relation.set/remove`、`progress.set`、`asset.attach/remove`、`action.invoke`、`behavior.invoke`、`publication.apply`。通知、确认、批准意图或成员管理本身不能作为成功业务动作来源。仅写包侧文件的操作不在此宿主回执验证范围，不能用伪造 commandId 接入。

## 收件箱与确认

| 接口 | 行为 |
| --- | --- |
| `GET /api/v1/notifications?after=0&limit=50` | 当前已登录账号的未确认通知，按 sequence 升序，只读，不接收 accountId |
| `notification.ack {notificationId}` | 当前收件人确认；与确认回执一并持久提交，返回 `{notificationId,acknowledgedAt}` |
| `Host.notifications(account,after=0,limit=50)` | 受信进程内入口；调用者必须绑定真实身份 |
| `InProcessTransport.notifications(after=0,limit=50)` | 使用 transport 固定账号读取 |
| `Client.notifications({after,limit})`、`Client.ackNotification(notificationId,commandId?)` | JavaScript SDK；沿用登录代际隔离、CSRF 和命令重试封套 |

```json
{
  "items": [{
    "notificationId": "64位十六进制ID",
    "sequence": 1,
    "senderAccountId": "kp",
    "text": "生命值已调整为 8",
    "createdAt": 1795140000,
    "source": {"commandId": "原宿主动作ID", "op": "entity.update", "status": "committed"}
  }],
  "nextAfter": 1,
  "hasMore": false
}
```

`nextAfter` 为本页最后一项序号，空页保持请求 after。hasMore=true 时继续翻页。序号允许有间隔；不以间隔推断其他人的消息数量。列表不返回其他受众、原操作参数或完整回执。时间为 Unix 秒，允许小数。文字按纯文本显示，不作为 HTML 执行。

投递持续到该收件人确认；读取本身不消费。离线成员只要仍有效就可成为受众，同目录重启、断线或重新登录后从 after=0 补取。展示方用 notificationId 去重，并持久记录本浏览器已展示 ID，再提交 ack；确认失败仅重试 ack。成功确认后不再返回，换确认命令 ID 也保留第一次 acknowledgedAt。多个收件人分别确认，KP 不能代他人确认。

网络展示与宿主确认不是一个原子事务，展示后确认前断线时未确认项可能再返回，接口不保证所有设备上的弹窗严格只出现一次。当前没有独立 WebSocket 推送帧；客户端通过读取接口轮询或在重连时补取。

受众绑定发送时的 memberId 和 authorizationEpoch；成员撤权、退出或身份授权版本改变后，旧项不可读、不可确认，重新激活不自动复活旧通知。内容属于 KP 显式定向告知，不将被引用实体、秘密字段或知识账本自动附送给收件人。

## 持久化、限制与故障

Room v4 现有 outbox 保存 `kind:notification,schemaVersion:1` 的记录，包括受众授权版本、原动作摘要及每人确认时间。旧 outbox 动作提示仍兼容且不进入通知收件箱；不增加必需顶层字段，不在打开时迁移存档。新通知校验形状、ID、序号唯一性、原动作 committed 回执、op 和签名关联。备份恢复保留原动作与通知事实、确认状态；不会因此重新执行原动作。

通知记录与发送回执在同一房间提交；确认记录与确认回执同样原子提交。发布前进程退出不产生半条通知或虚假确认；发布后退出可查询原回执，按同 ID 重试。原动作和后续通知是两个提交，跨步骤状态由包侧 Job 或 AI 批次回执管理。未知结果不能改报成功。物理断电下目录元数据持久性未验证。

每条文字最多 2000 字符、受众 1—100 个且不得重复；每页 1—100 项。通知记录最多 10000 条，含已确认记录；目前不自动清理审计、回执或历史通知。另受既有命令大小、文件存储和房间配额限制，达到上限明确失败。

| 错误 | 含义 |
| --- | --- |
| `NOTIFICATION_SOURCE_NOT_COMMITTED` | 当前发送者没有该原动作的 committed 回执 |
| `NOTIFICATION_SOURCE_INVALID` | 来源 op 不匹配或不在允许范围 |
| `NOTIFICATION_SOURCE_INCOMPLETE` | 来源为流程启动／节点，不能表示整体完成 |
| `NOTIFICATION_CONFLICT` | 同一原动作已有不同受众或文字的通知 |
| `NOTIFICATION_STATE_INVALID` | 持久通知形状或来源关联损坏，拒绝加载／提交 |
| `PERMISSION_DENIED` / `NOT_VISIBLE` | 发送者、受众或确认权限不满足 |

客户端也须处理既有 `INPUT_INVALID`、`LIMIT_EXCEEDED`、`COMMAND_ID_CONFLICT` 和存储错误，不把通知投递失败当作原动作未执行。
