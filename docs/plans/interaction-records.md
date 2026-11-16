# 通用请求与决定：工程评估及分期方案

- 文档类型：计划
- 状态：草案
- 创建日期：2026-11-14
- 最后更新：2026-11-14
- 关联文档：[ISSUE-008](Issues/issue-008-generic-request-decision.md)、[AI 读取资料设计](ai-data-query-adjudication.md)、[当前房间格式](../current/engineering/room-format.md)、[既有包侧协作](Issues/issue-003-rulepack-cooperative-ruling.md)

## 评估结论与范围

建议采用 **InteractionRequest＋DecisionRecord 两个关联模型**，归通用业务层，独立于 AI。方向适合项目；本轮完成工程取舍、权限与事务边界说明，尚未新增宿主集合、命令、查询 API 或 SDK。以下结构和接口均为设计稿，不能直接提交当前宿主。

| 方式 | 评估 |
| --- | --- |
| 单一记录族 | 共用头部简单，但申请人、决定者和状态语义不同，会形成大量条件字段；不选为首版写入模型 |
| 请求＋决定 | 能表达主动裁定、一请求多决定和改判；通过共同引用格式复用 UI/查询，推荐作为目标 |
| 仅标准读取适配 | 改动小，适合先验证跨包映射；不能补齐缺失历史、保证事务或把包数据升级成宿主权威，作为第一阶段 |

不新增 Entity 类型来规避权限，不扩展 AI 的生成任务 Request。Flow/Wait 保留推进、等待和恢复，命令回执保留真实执行结果；两个新模型负责“谁提出什么、谁决定什么、依据何在”。创建请求与允许行动均不等于执行成功。

## 推荐最小语义

公共头部为 schemaVersion、稳定 ID、roomId、scopeId、revision、包命名空间 type、typeVersion、时间和 audience。请求另含 initiator、authorizedDeciders、subjectRefs、payload、reason、sourceRefs、deadline；决定另含可空 requestRef、actor、outcome、reason、sourceRefs、supersedes、executionRefs。typeVersion 绑定包声明的输入／输出 Schema 与摘要；不接受客户端任意 schema 或可执行脚本。

首版正式请求只提供 open→closed/cancelled/expired，草稿留在客户端。确认决定形成不可变内容；改判新增决定并引用旧 ID/版本，原记录只允许宿主追加 superseded/revoked 状态变更及审计，不能覆盖原 outcome/reason。闭合或过期的请求不能再次消费；改判必须显式使用专门操作，不能重复走首次确认。

outcome 是包规则定义的结构化答复，例如 allow/deny/narrative，不是通用生命周期枚举。executionRefs 只关联宿主已验证的 command/flow/wait 及不可变决定版本；无执行需求显式标记 none，有执行需求通过回执派生 pending/completed/failed/unknown。暂不承诺多方投票或多阶段部分完成的统一调度。

引用建议采用 `{sourceId, kind, id, revision, digest, scopeId}`：sourceId 标识引擎或包适配器命名空间，revision 是字符串，digest 由受信来源生成。引用本身不带权限，当前读取时逐项复验。旧数据不知道的字段明确为 null 并附 completeness=partial，不伪造 KP 身份、时间或来源版本；不完整映射只能展示，不能作为发布依据。

scope 是房间通用概念。正式持久化时拟引入 Room 顶层 scopeId，AI 控制改为绑定它，避免非 AI 请求依赖 AI 私有字段；这是后续不兼容格式变更，需要另发版本说明。**本次 Room v3 不新增该字段，也不预先增加空 requests/decisions 集合。**

## 权限和一致性

| 操作 | 推荐约束 |
| --- | --- |
| 发起 | 活跃成员，只能提交包契约允许的类型和对象；发起身份、时间由宿主写入 |
| 撤回 | 发起者且请求仍 open；KP 管理取消需独立权限和理由 |
| 决定 | 活跃且在 authorizedDeciders 中的主体；仅有 KP 标签不能越过来源私聊权限；自动规则主体仅由宿主执行器创建 |
| 改判／撤销 | 原决定契约允许的裁决者；必须提交期望修订、理由及旧决定引用，不回滚既有消耗或重新掷骰 |
| 查询 | 先按 audience 授权再检索分页；关联来源再次授权，不返回隐藏计数；决定可读不意味着来源全文可读 |
| AI | 受权只读或提供建议；模型生成的 actor、confirmed 状态与执行结果均不接受为事实 |

决定记录、请求闭合、审计及对应命令回执应在同一 Room 事务提交。复用现有 commandId 幂等；另以请求 revision 和唯一首次消费约束处理不同 commandId 的重复决定和两名 KP 竞争。

能在单一行动中执行时，同事务记录决定与效果；必须等待的行动由现有 Flow 承接，保存决定版本与流程 ID。恢复或响应未知先查原回执，不自动重复行动。新决定不能替旧决定悄悄结算；持续房规变更仍走规则暂存/激活或正式配置发布。

创建/确认时验证来源、对象、规则版本及 audience；来源权限无法覆盖目标受众时拒绝扩大共享，允许操作者删除该来源后提交独立叙事说明，但不得冒称该说明已验证原私聊。读取时权限变化可隐藏来源内容。恢复到新 scope 后保留原历史引用并标识旧作用域，不把旧未执行决定自动重新执行。

## 三个表达样例

以下是业务摘要，不是完整 API 封套：

| 场景 | 请求 | 决定 | 执行关联 |
| --- | --- | --- | --- |
| 尝试开锁 | 玩家发起 stumpsville.action，payload 指向门和角色 | KP confirmed，outcome=allow | 引用实际检定回执；检定失败仍表示“获准尝试但失败” |
| 拒绝行动 | 玩家申请跨场景取物 | KP confirmed，outcome=deny，reason=距离不足 | none；不是决定记录 rejected，也没有伪造成功回执 |
| 主动叙事及改判 | requestRef=null | KP confirmed，outcome=narrative；后续新决定 supersedes 前条 | none；旧说明保留，原规则与消耗不自动变化 |

另用 ISSUE-003 的多人协助／结构化问答验证多主体引用与回答表达，不重做已完成包玩法。对树桩镇现有 requests/receipts/events 做读取试点时保留原 ID，仅映射实际存在字段。

## 实施顺序与验收门槛

1. **I0 读取契约与样例**：下一步交付 Draft 2020-12 Schema、版本化类型注册约定、上述三类正反例和来源完整性标记。状态转换表与权限表不得只写成自由文本；机器验证通过不等于来源可信。
2. **I1 受信读取试点**：树桩镇及 ISSUE-003 各一适配器，提供 describe/search/read/recheck；与包作者核对原始语义和权限。私聊、隐藏实体、他人回执、改判及缺失来源均有负例。通过前不接入 AI 正式发布证据链。
3. **I2 宿主接线**：确定包类型注册的生效/锁版方式，新增持久集合、命令、HTTP/SDK 及通用 scope；另升 Room 格式。验收并发、跨 commandId 重复、事务失败、结果未知、恢复分叉、改判和授权变化。
4. **I3 AI 与 UI**：AI EventBundle 读取正式记录，不成为第二事实库；引用接入当前 A/B/C 证据及发布前复验；默认只读，不赋予模型审批权。

完成 I1 前不建议同时推进全套宿主写入：两种包侧资料尚无统一可验证来源，过早持久化会把不确定映射固化成权威事实。后续需确认类型注册权限、来源撤回的保留政策和跨阶段执行补偿范围。复杂审批、所有配置包迁移与自动修正历史不作为本轮前提。
