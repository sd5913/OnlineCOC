# 房间内原子指令批次

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 关联文档：[工程实现](first-test.md)、[机器可读契约](../../../engineering/contracts/atomic-batches.json)、[操作参数](../../../engineering/contracts/operations.json)、[专项验收](../../../engineering/acceptance/atomic-batches/README.md)、[可靠性计划](../../plans/ai-command-reliability.md)

## 1. 入口与支持范围

以下是可信 Python 组合入口，`account` 必须来自已认证主体。没有新增允许客户端自报身份的 HTTP 接口，`batch.execute` 不在普通管理操作白名单。

```python
preflight = host.preflight_batch(account, actions)
receipt = host.execute_batch(account, actions, command_id="stable-batch-id")
receipt = host.receipt(account, "stable-batch-id")
```

`actions` 是非空数组，不另设动作条数业务上限。每项严格为 `{"target":"host","op":"...","args":{...}}`，规范 UTF-8 JSON 总量上限 32 KiB。参数沿用普通操作契约。预检总预算 10 秒、正式执行总预算 30 秒、单个 Lua 工作进程最多 10 秒、整批最多 256 次随机抽取；规则进程的隔离与资源限制继续生效。

支持 21 种操作：

- `entity.create`、`entity.patch`、`entity.update`、`entity.archive`
- `relation.set`、`relation.remove`、`progress.set`
- `asset.attach`、`asset.remove`（仅房间素材引用与元数据）
- `room.status`、`member.update`（不能修改执行者自己）
- `notification.send`
- `action.invoke`、`behavior.invoke`（最终绑定必须是公开且有权限的 action 模式规则）
- `chat.direct.open`、`chat.channel.create`、`chat.channel.update`
- `chat.message.send`、`chat.message.share`、`chat.message.edit`、`chat.message.retract`

`flow.*`、flow/calculation 模式规则、`member.add`、规则或配置发布、素材上传、AI 存储操作及外部等待/副作用不在范围内。任一非 host 目标或不支持操作会在所有业务执行前阻止整批，不静默拆批。知识提供方继续遵守纯读取/派生约定，接收暂存状态，不得自行写存储或调用网络。

## 2. 预检

返回 `{"status", "checkedAt", "scope":"host.room.atomic.v1", "items":[...]}`。每项包含零起算 `index`、`target`、`op`、`status`，失败附安全 `code`、`reason`、`path`，可有 `ruleId`、`ruleCode`、`object`。

状态为 `passed`、`blocked`、`unsupported`、`runtime_required`。先核对所有项的结构、参数、范围与规则入口，再在分离的房间副本中顺序执行确定性部分。后项能看到前项暂存效果。整批准入失败时，其他项标 `runtime_required` 并说明尚未进行业务预检；业务前置失败后，余项显示依赖阻塞。

首次请求随机数时停止该规则的预检，将本项与依赖后项标为 `runtime_required`。预检不抽取、消费、保存或猜测正式随机数，不写房间、回执或通知。确定性项可附权限过滤后的 `result` 与 `preview:true`；生成对象 ID 等只是预览，不能用于正式指令引用。超预算也显示运行时需重检。

`passed` 只说明本次检查通过，不保证未来执行成功。正式执行重新检查当前权限与前置条件；AI 层仍需核对自己的来源依赖和已审批候选版本。

## 3. 回执与恢复

总回执保持 `unknown/pending/committed/rejected` 格式。终态 `receipt.result` 为执行 DTO：

```json
{
  "status":"rolled_back", "scope":"host.room.atomic.v1",
  "items":[
    {"index":0,"target":"host","op":"entity.patch","commandId":"batch-...","status":"rolled_back"},
    {"index":1,"target":"host","op":"action.invoke","commandId":"batch-...","status":"failed","code":"RULE_FAILED","ruleCode":"SV_EMPTY_SLOT","reason":"规则前置条件不满足。","path":"/actions/1/args"}
  ],
  "committedCount":0, "failedCount":1, "notExecutedCount":0, "rolledBackCount":1
}
```

执行总状态是 `committed/rolled_back/failed`，逐项状态是 `committed/rolled_back/failed/not_executed`。第一个执行项失败为 `failed`；前面已有成功暂存项时为 `rolled_back`。两者业务提交数均为 0，没有 `partial`。“撤销”指丢弃未提交暂存状态，不回写旧房间快照。

宿主持有房间锁，先持久保存批次意图。正式随机数逐次写入该意图轨迹；业务变更、子命令回执、定向通知和父批次成功回执最后一次提交。相同账号与 `command_id` 配相同 actions 返回原回执；不同内容报 `COMMAND_ID_CONFLICT`。子 ID 为 `batch-` 加 `SHA256(canonical([command_id,index]))`，已有子 ID 会阻止准入。

进程中断后复用已保存随机轨迹。恢复核对排除自身意图记录后的完整房间摘要；房间已改变则拒绝恢复并保留他人的修改。最终提交还有存储代号 CAS。发布已成功但回复丢失时，以持久成功回执为准。

异常或断线后先查询原 ID。`unknown/pending` 不能表示成功、失败或撤销，不得换新 ID 盲目重放。已知 pending 可以用完全相同 ID 和 actions 调用原入口恢复，也会在宿主恢复时处理。存储不可写时可能保持 pending，恢复存储后再对账。

## 4. 业务结果、诊断与通知

成功项 `result` 重新经过当前回执权限投影；后来不可见的对象或频道不会通过父批次泄露。预检使用同样投影；PL 诊断进一步移除对象和内层规则码。

Lua 的首个宿主领域错误不会被内层包装或 `pcall` 覆盖。Lua 断言只保留同时出现在规则源码字符串字面量中的大写符号码，例如 `SV_EMPTY_SLOT`，不返回动态文本、堆栈、源码或隐藏实体内容。参数 Schema 错误含 JSON Pointer；一般业务断言定位到规则/动作参数整体，宿主不猜测包专属参数字段。

规则返回 `false`、`public.outcome: failure` 或 `public.outcome: blocked` 是有效业务结果，不自动变成技术错误或重掷理由。`committed` 仅表示事务提交，不能据此认定玩家目标已达成；包/AI 层根据安全结果判读，宿主不硬编码树桩镇 outcome。确定性预检也保留该业务返回值。

通知可沿用 `sourceCommandId/sourceOp`，或在批次中改用 `sourceActionIndex` 指向更早的一项，两种形式不能混用。宿主解析索引并核验成功来源。收件人、文本、来源与去重规则不变；暂存 outbox 仅在最终提交后对玩家可见，后项失败时一并丢弃。投递/确认沿用原通知 ID，不撤销已提交游戏状态。

## 5. 单条记忆确认/撤销

记忆确认/撤销涉及宿主权威事实与 AI 镜像，不能宣称六类 AI 操作均为单库原子事务。独立可信入口为：

```python
receipt = host.commit_memory_fact(
    account, fact,
    command_id="stable-memory-transition-id",
    expected_revision=current_host_revision_or_zero,
)
fact_to_mirror = receipt["result"]["memory"]
```

`fact` 是完整下一版 `MemoryEntry`，状态限 `confirmed/revoked`，属于当前宿主 scope，revision 大于当前宿主权威版本。`expected_revision` 是当前 `memoryFacts` revision，首次为 0，不是 AI 草案版本。调用者必须是 KP，可信 AI 服务须先核对自己的所有权、来源引用与决定权限。

权威事实和回执同一次宿主提交生效；丢回复和重复调用按相同标识对账。AI 模块使用回执中的精确事实恢复自己的镜像。此函数不写 AI 存储，也不加入 `execute_batch`；多项跨库组合仍在预检阶段阻止。
