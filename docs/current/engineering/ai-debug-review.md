# AI 来源审核、调试导出与模型标识

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-19
- 最后更新：2026-11-20
- 关联文档：[会话权限](ai-session-access.md)、[裁决](ai-rulings.md)、[嵌入接入](ai-pack-embedding.md)、[管理器](ai-manager.md)

## 来源审核

KP 接收玩家申请时，新建本人名下的 administrator 会话。新请求使用“请协助处理所引用的申请或裁决……”；玩家原话、原申请人、原会话和裁决定位独立保存在 `settings.reviews`，以 `reviewSource` 来源卡展示。原玩家会话不被改写，KP 的回复不回灌给 PL。旧会话不批量迁移；既有 accepted 玩家申请会按原记录补出“历史来源”卡。其旧首条在展示、首次外发和历史中投影为通用 KP 审核文案，存档原文保留；private 外发关闭时旧首条模型回答也不进入后续历史。调试正文注明 legacy 来源。

`ai.review.create` 是 KP 命令，参数为 `{source,instruction?}`。支持三类 source：

| kind | 输入 | 服务端处理 |
| --- | --- | --- |
| ruling | rulingId、可选 digest | 从当前授权裁决投影取概要、修改与回执快照；有 digest 时检查当前版本 |
| request | requestId | 从当前授权任务投影反查原申请人、原会话和可见回答 |
| package | sourceId、category、id、revision、title、summary；可选 requestedBy、context | 标为 provided-snapshot；包必须在服务端从当前状态组装，不能把客户端材料冒充宿主 DataRef |

包 source 总量不超过 32 KiB；定位字段及 requestedBy 不超过 200 字符，title 120、summary 8000，instruction 4000。context 为 JSON object。模块裁决来源快照上限 64 KiB。返回 `{sessionId,requestId,taskId?,generationError?}`；生成未启动时仍保留可打开的审核会话。

相同 KP、来源定位与版本、补充指令会复用未删除的审核会话。原命令信封保留既有幂等回执；重复点击不重复派发已创建的任务。转交不改变原裁决结果，也不能重放已完成动作。玩家申请“接收”仍只表示接收需求；所有来源审核会话产生的运行时批次和普通配置，即使房间开启自动批准，也须另行人工批准。高危规则保持原有人工审批要求。

来源材料是历史快照和需求，不是当前事实或执行授权。模型 payload 的 `currentActor` 是当前 KP；来源 `requestedBy` 只解释“我的角色”等原话，不能改变权限主体。模型必须查询活动角色、实际物品定义、规则与配置；数值背包槽位和通用模板不等于实际物品定义。

来源正文按外发范围处理：玩家创作申请使用 private，其他裁决/包材料使用 kp；关闭时 payload 只给出 omitted 与所需范围，不发送正文。玩家引用仍按原玩家及当前外发政策转为文字标签，不能解释成 KP 知识句柄。当前 KP 在本地查看原材料和允许模型外发是两个不同权限。

## 引用与调试

`GET /api/v1/ai/debug` 为只读端点。至少提供 sessionId、requestId、rulingId 之一，均为非空、最多 200 字符；`includeContent` 默认 false，HTTP 仅接受字面 true/false。未知或重复参数拒绝。响应带 `Cache-Control: no-store`，不调用 command，不保存导出副本或正文回执。

默认包含房间与任务定位、状态、错误码、调用模型标识；KP 可见脱敏诊断。显式 `includeContent=true` 才加入本次授权投影中的文本、回答、来源或裁决详情。PL 只能导出自己的玩家会话，不能借 requestId 或 rulingId 获取 KP 内容；关闭玩家 AI、删除会话和来源失效后重新检查，不能借旧导出请求读取撤权内容。不返回本机凭据、系统提示、原始服务商消息、HTTP 头或完整隐藏上下文。显式正文导出仍可能含私密游戏和对话资料，界面对此标明，常见凭据格式另做脱敏。

入口：`Application.debug(account, options)`；AI 组件 `AiClient.aiDebug(options)` / `createAITools(client).debug(options)`；引擎 SDK `Client.aiDebug(options)`。管理器代理和 LAN 仅新增只读路径。网页与 P2P 沿用配置包桥；包桥须独立校验参数和实际会话身份，不能开放管理员命令给 PL。

聊天顶部“引用与调试”按钮位于 KP 审核与设置之前，点击打开子窗口，可选择整个会话或某条消息；对话正文不再重复放置调试折叠栏。裁决详情仍有自己的入口。提供复制定位、默认无正文的 JSON 导出和显式正文勾选。关闭后清空窗口，重新打开恢复默认不含正文；切换会话、身份、折叠或销毁组件时清理窗口及迟到响应。复制定位不调用模型；局域网 HTTP 没有 Clipboard API 时显示只读定位文本并自动选中，不能自动复制时可按 Ctrl+C。组件销毁或身份切换后丢弃迟到的私密响应。

配置包从 `pack.js` 导入：

```js
appendDebugTools(target, client, {requestId}, {valid: () => stillMounted});
appendReviewSource(target, source, {onOpenSource, onOpenSession});
```

`mountChat` 及三种视图支持 `options.onOpenSource(source)` 定位包原裁决；原生来源另有“查看原对话”。`mountRulings` 的“转 AI 处理”调用统一命令，成功后通过 onOpenSession 打开 KP 审核会话。新增资源 `debug.js` 随 pack-manifest 分发。

## 有效权限和模型版本

管理员全房间读、资料查询、提交运行时修改和配置修改默认 true；玩家聊天及两种自动批准默认 false。“允许调用 AI”仍独立控制服务，已有房间显式外发 false 不被自动改写。

`room_manage_catalog` 的通用操作名称/schema 不再被 KP 正文外发开关挡住；其中房间动态行动目录在 kp=false 时替换为明确的省略提示。`room_read_management`、`room_read_sessions` 和其他实际私密游戏资料仍需相应外发许可。权限页显示当前缺口，提供“选择全部游戏资料（保存后生效）”，只填写外发选项，仍需保存服务设置生效。

服务商 Profile 可选 `versionInfo:{label?,sourceUrl?,verifiedAt?}`，表示管理员人工核验备注。UI 分别显示 API 模型 ID/别名、版本备注/日期和探测响应。每次成功调用记录 requestedModel、API 原样返回的 returnedModel、systemFingerprint 和用量；缺失响应标识记为未知。别名或后端 fingerprint 均不证明固定模型版本，历史记录不回填猜测版本。


## 验收

阶段测试、失败复验和早期决策已移入[开发记录](../../history/2026-11-20-ai-development-records.md)。各阶段计数不相加为当前全量结果。 路由、SDK、LAN 及真实模型结果分别保留，不互相替代。

## 配置起草

把 game.json 的 items 分片作为整文件替换会在 A 层缺失 title 等字段。应使用[活动配置精确增量](ai-data-query.md#活动配置数据的精确增量)：模型只提交明确追加，服务端保留完整基线并继续三检/人工审批，避免重吐未触及字段。旧真实失败记录保留，不能用模块专项通过代替包侧真实模型闭环。


## 故障反馈与处理

| 情况 | 反馈与处理 | 可否直接重做 |
| --- | --- | --- |
| 明确参数／权限拒绝 | 保留错误码，修正参数或由 KP 调整合法授权；包桥清除已明确拒绝的挂起标记 | 以新请求重新提交修正内容 |
| 模型格式或基础结构错误 | 同一任务按配置额度自动修正，诊断保留每次错误和路径；耗尽后显示失败 | 编辑原需求后重试，不自动无限循环 |
| A/B/C 阻塞 | 查看配置裁决报告，修正候选／作者材料或补真实决策；阻塞候选不可发布 | 重新校验，不能跳过报告 |
| CONSULTATION_ONLY | 当前任务引用了独立包资料，只能咨询；新建需求并读取宿主 configurations 或活动工件数据后准备候选 | 不移除来源证明来强行发布 |
| STORAGE_UNAVAILABLE／STORE_FULL | 保留原 ID，先核对回执及磁盘；新版 AI 存储会无损压缩旧代，真正不足仍须备份恢复到新目录 | 不删除中间代、不盲目重放 |
| 来源／基线版本变化 | 有权限且可证明来源仍存在的管理员旧回答显示过期提示，只保留历史意图；修改前重新读取当前目标 | 旧批准不沿用 |
| HISTORY_PROVENANCE_INCOMPLETE | 旧搜索只留摘要，变化后无法证明原对象仍可查看；隐藏正文，重新描述需求并查询 | 不猜测补造来源 |
| 来源删除／撤权／跨 scope | 隐藏旧正文，不通过历史回退恢复 | 恢复访问需真实授权 |
| 已完成或部分完成后旧来源失效 | 保留执行状态；按原回执核对，正文仍可因撤权隐藏 | 不重放已成功动作 |
| 超时、断线、服务端异常、unknown | 保留原请求 ID，查询原回执；未知结果不当作失败或成功 | 未核清前不换 ID 重做 |

实验记录须区分模型生成、三检、批准、发布和实际消费的结果；计入失败尝试、修复及真实调用用量。审核连续性、引用扩展和通知批次见[专项记录](../../../engineering/acceptance/review-continuity/README.md)。重启、调试与失败恢复的首轮/复验见[本轮报告](../../../engineering/acceptance/ai-runtime/repair-20261120.md)。
