# 高危配置发布与 KP 全房间读取

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-19
- 最后更新：2026-11-20
- 关联文档：[工程索引](README.md)、[房间 AI](ai-runtime.md)、[修改裁决](ai-rulings.md)、[数据查询](ai-data-query.md)、[宿主验收](../../../engineering/acceptance/high-risk-publication/README.md)

## 适用范围

本文记录宿主实现的审批、发布和读取契约。AI 生成、人工裁决界面、自动策略及包侧地图／物品同步由对应模块实现，见关联文档。宿主审批接口是已认证 KP 的管理接口；模型不持有该权限，AI 自动路径不能代填人工批准标记。

Room 仍为 schemaVersion=4。新增批准字段为可选，旧数据可加载；旧高危批准缺少明确批准摘要时不能继续发布。检查器摘要包含 `publication.py`、`room_read.py`，实现或契约更新后旧候选需要重新验证。

## 高危判定与候选

宿主 [publication.py](../../../engineering/backend/src/onlinecoc/publication.py) 独立根据完整候选判定高危，不接受模型自行声明为低风险。符合任一条件即为高危：

- 候选完整 Lua 源文件或数据文件集合与当前活动工件不同。
- 删除配置。
- 修改涉及 `item`、`weapon`、`bag` 类型的配置。
- 配置 ID 命中包契约 `highRisk.configurationIds` 或 `configurationPrefixes`。

地图等业务类型由包契约声明 ID／前缀；地图数据文件变化也满足文件变化条件。`highRisk.ruleFiles/dataFiles/allowRemove` 是包检查器可检查的扩展声明，不代替 KP 批准。A/B/C、包约束和依赖检查仍需通过。

`ChangeSet.configurations` 支持 `add`、`replace`、`remove`：

| 类型 | expectedRevision | value |
| --- | --- | --- |
| add | null，ID 尚不存在 | 完整 Configuration |
| replace | 当前配置修订字符串 | 完整 Configuration；修订必须变化、typeRef 保持一致 |
| remove | 当前配置修订的非空字符串 | null |

源文件／数据字段在受信 PreparedBundle 中是合并后的完整候选集合。配置 ID 不得重复。宿主在批准和发布前构造并验证整个最终配置图，再写入结果：

- 被任一实例引用的配置不能删除，归档实例也计入，不自动级联删除。
- 所有剩余配置的 `behaviors`、所有实例的 `rules` 均须指向候选工件中存在的规则。
- 候选规则声明依赖必须存在且无环。
- 已运行流程继续绑定原工件，旧工件保留；配置变更不自动重写旧实例数值。

## 宿主命令与明确批准

沿用普通 `POST /api/v1/commands` 的 commandId、authorityEpoch、账号认证和回执机制。`ai.proposal.approve` 参数：

```json
{
  "proposalId": "待审核提案 ID",
  "proposalRevision": 1,
  "explicitHighRiskDigest": "实际候选的64位小写十六进制摘要",
  "riskDecisions": {
    "high-risk": "已检查完整候选及影响并同意发布"
  }
}
```

该示例只展示高危字段，实际还必须填写包 `reviewPolicy` 的必填项；报告风险为 medium/high/unknown 时需填写 `gameplay-risk`。每条理由去空白后至少 3 字符。`explicitHighRiskDigest` 必须逐字等于本次 `candidateDigest`，不能填固定值或旧修订摘要。

批准只把完整候选、报告和证据复制到 Room 并暂存工件，不激活配置。返回 `approvalId`、`expiresAt`、`candidateDigest`。随后 `publication.apply` 接受 `{ "approvalId": "..." }`；只能由原批准者执行，且当前仍是 KP。

发布复验候选／证据摘要、明确高危批准、权限、作用域、authorityEpoch、提案修订、检查器版本、到期时间、世界基线和来源。配置变更、活动工件切换、批准消费标记、发布记录及命令回执在一个宿主存储提交中生效。提交前异常不产生部分配置修改。

| 错误码 | 含义与处理 |
| --- | --- |
| HIGH_RISK_REVIEW_REQUIRED | 高危候选缺少或不匹配明确批准摘要；显示该候选供 KP 重新审核 |
| RISK_REVIEW_REQUIRED | 缺少必填理由、含未知审核项或理由过短 |
| DIGEST_MISMATCH | 候选／证据被改动；低风险候选提交了错误的显式摘要也使用此码 |
| REFERENCE_CONFLICT | 删除仍被引用的配置、改变配置类型或产生无效规则绑定 |
| VERSION_CONFLICT | 配置已变化、ID 冲突或替换未更新修订 |
| RULE_CYCLE_OR_MISSING | 候选规则依赖缺失或成环 |
| BASELINE_STALE / SOURCE_STALE | 游戏基线或证据变化，需要重新验证审核 |
| VALIDATOR_STALE | 包绑定或检查器版本变化，需要重新验证 |
| PERMISSION_DENIED | 账号、会话读取范围或当前授权不满足条件 |

## 历史上下文的只读复验

引擎提供 `publication.check_history_context(host, state, account, context)`，用于持久 AI 历史的授权读取。调用方在宿主锁内取得当前 `state` 后调用；成功返回 `None`，失败抛出现有 `DomainError`。它先验证完整 `ContextSnapshot`，不修改传入上下文、不提交房间，也不把旧证据升级为新批准。

普通同目录重启保留 scope，但更换 `authorityEpoch`。历史只读入口不要求旧上下文的 epoch 等于本次进程，也不要求执行检查器指纹不变；读取不需要重新证明旧候选可执行。当前账号、授权版本、scope、包契约、来源／记忆、查询证明、外发策略、服务配置及已安装会话访问回调仍全部复验。管理员上下文继续检查活动规则、配置和世界基线；严格玩家上下文继续按原 owner 复验知识证明、提供方及当前授权，不能用 KP 身份替换原玩家知识范围。

因此，仅宿主重启不会使仍有效的历史失去读取资格；成员停用／撤权、资料变化、知识撤回、提供方失效、外发策略变化、恢复为新 scope 等仍会拒绝。该入口保留原基线检查，不把历史输出声明为当前世界事实。

`publication.check_context` 仍供生成中的执行校验、批准与发布使用，继续要求当前 `authorityEpoch` 和执行检查器版本。历史复验通过不允许重用旧批准或旧运行时命令；重新提交修改须重新捕获上下文、检查并审核。已提交命令的同 ID 回执查询规则保持不变。AI 消费侧必须区分历史读取和执行路径，不能把全部 `check_context` 调用替换为历史入口。

引擎专项及回归见[历史上下文验收](../../../engineering/acceptance/history-context/README.md)；AI 会话展示、连续对话和界面接线由 AI 模块另行验收。

## 发布回执与包侧同步

成功命令的 `result` 是 Publication，包含 `publicationId`、`approvalId`、`scopeId`、`commandId`、`accountId`、`candidateDigest`、`previousRuleset`、`ruleset`、`configurationRevisions`、`createdAt`。配置删除表示为 `configurationRevisions[configurationId] = null`；新增／替换为新修订字符串。

同一 commandId 重试返回原回执；同一已消费 approvalId 再次发布返回原 Publication，不重复生效。客户端结果未知时查询 `GET /api/v1/receipts/{commandId}`，保留原 commandId；回执按当前账号隔离。KP 可通过 `GET /api/v1/admin/artifacts/{ruleset}` 读取实际发布工件；传输桥是否开放该管理路由以对应联网模块为准。

包侧独立文件不属于宿主这次原子提交。包应在审核前检查稳定索引、实例及地图等约束，并使用 `scopeId + publicationId` 对发布后的确定性同步去重。同步失败必须保留“宿主已提交、包侧待同步／冲突”状态；不能把已提交回执改成失败或默默回滚游戏世界。此处仅定义对接边界，具体同步实现见包侧文档。

## 显式 KP 全房间读取

可信 AI 组合层为宿主安装 `host.ai_room_read_authorizer(account)` 回调。仅当账号及 initiator 均为当前有效 KP、回调返回布尔 True 时，`data_queries.query(..., read_scope='kp-room')` 才可读取完整房间范围。未安装回调默认拒绝。此范围不是模型参数；AI 服务依据当前管理员会话和策略选择它。传入 player 覆盖时拒绝；标记 strictPlayer 或玩家会话的上下文不能冒用该范围。

新增 DataQueryRef：`kind='room'`、`sourceId='host-room'`。查询 `search` 的 `types=['room']` 返回分片引用；`read` 读取引用对应的 `{path, value}`。普通查询不默认包含 room；未显式授权时直接请求该类型被拒绝。

[room_read.py](../../../engineering/backend/src/onlinecoc/room_read.py) 仅投影 Room 已定义字段，包括配置／原始工件源码与数据、活动及归档实例、成员／个人进度、完整房间聊天、流程／等待、命令记录／审计、素材元数据、AI 控制和知识账本。不读取主机 identity、密码、登录会话、API 密钥、独立 AI 仓库或任意本机文件；素材二进制不在 Room JSON 内。

房间记录按 JSON 路径拆分，单条数据目标上限 4096 字节。大字符串按 Unicode 字符分片，另有 `textOffset`、`textLength`；偏移不是 UTF-8 字节偏移。读取结果仍受 16 KiB 总限额约束，建议每次读取 1—2 个大分片，遇 `QUERY_RESULT_LIMIT` 缩小批量。引用绑定路径、分片偏移、内容摘要及房间 scope；数据变化后旧引用失效。分页只覆盖请求范围，不表示模型已经读完全部房间。

显式范围允许 KP 读取非参与者私聊；正常聊天权限接口保持原规则。模型外发仍受 `externalSources` 管理：混合 Room 分片要求 public/kp/private 三项均开启，未授权时不返回该类记录，不擅自扩大外发权限。

上下文用 `facts.aiReadScope='kp-room'` 标记范围，查询证明另保存 `readScope`；宿主在来源复验时重新执行回调和相同查询。AI 服务还绑定其策略修订。关闭读取授权、撤销 KP 身份、资料变化或外发策略变化会阻断旧上下文；只有完整证据复验后才可批准或发布。

包侧独立资料可实现可选端口 `adapter.read_scoped(state, account, *, read_scope=None)`。宿主仅在上述范围校验通过后传入 `'kp-room'`，普通调用传 None；旧适配器仍调用 `read(state, account)`。包侧应据此决定是否增加全包资料，不得仅凭 KP 角色绕过关闭的全读开关。投影仍经过共同接收者交集、可见性外发过滤和摘要复验；适配器异常按 `DATA_SOURCE_UNAVAILABLE` 拒绝，不回退到更宽读取范围。旧 read-only 适配器无需改签名。

## 验收

受信包作者的离线场景可在 worker `sequence` 请求中提供 `privateRuleIds`，AI 包装端口为 `run_scenario(..., private_rule_ids=())`。默认空列表；只接受已存在规则 ID 的无重复列表。实际模拟 principal 必须为 KP，且私有规则命中该名单，才可在场景副本中执行；玩家 principal 即使命中也拒绝。不自动提升玩家身份，公开场景的越权反例保留原账号。该端口不暴露在普通 Host 命令中；KP／PL 的在线 `action.invoke` 仍不能直接调用 private 规则。

名单只由可信包作者 fixture／live 声明生成；模型候选不能改写验证材料。执行仍使用真实 Lua、输入 Schema、规则前置条件和同一资源限制，每次 trial 从独立快照开始；模拟 effects 不提交正式房间。修改核心规则时无需为了通过 C 验证将内部规则设成公开。

隔离宿主专项和回归的原始 JUnit、运行命令、失败初跑说明及范围见[验收记录](../../../engineering/acceptance/high-risk-publication/README.md)。宿主事务专项使用受信合成 resolver；真实 AI A/B/C 联合回归单独记录，不把合成报告计作真实规则验证。测试不读取或修改正式房间，不部署服务。
