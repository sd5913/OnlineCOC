# AI 修改裁决与配置包扩展

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-16
- 最后更新：2026-11-16
- 关联文档：[会话权限](ai-session-access.md)、[回答与修正](ai-responses.md)、[嵌入组件](ai-pack-embedding.md)、[实验用例](../../plans/ai-rulings-experiments.md)

## 一次提交，一次裁决

AI 的 `batch` 和 `draft` 分别表示运行时动作批次与配置候选。两者都出现在 **AI 修改裁决** 队列中；KP 查看整批内容后批准或拒绝。模型返回文字不能批准或执行修改。

| 类型 | 待裁决条件 | 批准后的行为 |
| --- | --- | --- |
| runtime | 最多 8 个白名单动作，固定参数、来源、权限与房间基线 | 按顺序执行；失败即停，保留逐项回执，已执行项不自动回滚 |
| configuration | 同一 ChangeSet 的 A/B/C 全部通过，且来源允许发布 | 保存风险决定后，在宿主事务中加载整批配置与规则；原实例数值不迁移 |

“整批裁决”不把运行时多命令变成数据库原子事务，也不把模板发布与之后创建实体合成一个事务。新增模板须先发布，再提交使用该模板的实例批次。权限、来源、版本或基线变化仍可使执行停止。

管理员会话中的明确短句“批准”“批准执行”“确认执行”“同意执行”“approve”，只绑定该会话最新需求对应的唯一裁决，不另发模型请求。重复批准已完成项返回原结果；多项待处理、目标不明确、基线失效或需填写配置风险决定时，转到裁决队列。没有对应裁决时保留正常对话，用于确认尚在设计中的方案。PL 的回复不取得裁决权。

模型上下文携带本会话最近裁决的 ID、类型和状态，要求避免重复生成已待审／已完成修改。该摘要仅在管理员会话且允许外发 KP 信息时提供，不附带历史动作明细。队列资料读取仍复验来源权限；失效时清除正文与敏感详情，保留状态供核对。

## 策略与接口

`allowPlayerChat`、`autoApproveBatches`、`autoApproveConfigurations` 分别控制玩家使用、运行时自动批准、配置自动批准，默认均为 false。KP 保存策略时绑定执行人；配置自动批准仅由该执行人负责的提案触发。配置仍须通过 A/B/C，自动为必填风险项记录“KP 已开启通过三检后的配置自动批准”。开启即接受检查报告中的风险与覆盖限制，不能跳过失败检查。

| 入口 | 参数／返回 |
| --- | --- |
| `GET /api/v1/ai/rulings` | KP 队列；rulingId、kind、status、digest、sessionId、summary、risks、动作或 ChangeSet／报告、回执 |
| `ai.ruling.decide` | `{rulingId,digest,decision:"approve"|"reject",riskDecisions?:{风险ID:理由}}` |
| `AiClient.aiRulings()` | 同一队列的 SDK 读取 |
| `createAITools(client).rulings` | `list()`、`decide(value,commandId?)` |
| `mountRulings(container,client,{onChange})` | 可独立嵌入；`refresh()`、`destroy()`；身份变化清除内容 |

命令使用现有 AI 封套、Origin/CSRF 与登录身份。配置裁决绑定原审核人、提案修订、候选摘要及必填风险项；批准时不能修改内容。完整底层提案／宿主发布接口继续保留，自定义接入可使用。

配置执行使用固定宿主命令 ID `ai-ruling:<proposalId>:<revision>:approve/apply`，在动作前保存执行意图。网络异常先用原 AI requestId 查询回执；宿主原命令回执可继续核对。未知／执行中状态不会自动重放。运行时队列提供“核对原执行回执”，只查询、不继续剩余动作；配置是否完成以宿主 publication 为准。批准成功而加载未完成的配置保留原 approval，可由开发接口核对或撤销，不能把未知结果当作新批准重新执行。

引用包侧聊天／事件等 `consultationOnly` 证据的版本只可咨询，即使三检通过也不进入可批准状态。队列显示来源限制；需要基于可发布的宿主证据重新生成，或后续完善包侧来源发布契约。此限制同样约束自动批准。

## Stumpsville 当前扩展范围

作者材料由 `tools/ai_extensions.py` 随 companion 生成并计入摘要。两个游戏数据文件仍使用固定值 Schema，核心规则与流程不在扩展范围。

| 对象 | 当前支持与限制 |
| --- | --- |
| NPC 模板 | 替换 `sv.npc` 的 defaults；新增／替换 `sv.ext.npc.*` actor 模板，替换只允许 defaults。扩展模板必须有 `isNpc=1` |
| 默认字段 | hp 0—40、maxHp 1—40；三属性及其上限 1—20；armor 0—3、location 1—10、incapacitated 0—1、lastRoll 0—20；最多 32 个数值字段，额外数字范围 -100—100 |
| 规则 | 每个独立 Lua 文件 return 一个 `sv.ext.*` 规则；只允许 action/calculation、一个 actor 输入、public=true、kp=true；不支持生成 flow |
| 效果 | 探测中只接受绑定 NPC 的数值效果，出现其他实体／关系效果或越界数字则拒绝；有限探测不能证明任意输入路径都安全，运行时仍受宿主权限约束 |
| 游戏性检查 | 作者提供 B 正反例、士气与权限 C 场景及指标；新增／修改规则对模板和现有 NPC 探测 d20=1、10、20，并比较旧规则。最多 8 个规则、32 个 NPC 模板、64 个探测对象 |

探测不是穷尽概率证明；未覆盖玩家角色、自动剧情联动及全部随机组合。报告明确记录覆盖边界，交 KP 决定。NPC 敌友立场、剧情风格等不可从数据推导的偏好交用户选择；字段或 Lua 基础错误走自动修正。

发布后，包侧按宿主当前工件同步活动规则修订和导出内容；扩展 NPC 纳入 KP 名册与同样的玩家发现过滤。公开实体不等于玩家已发现。`actor.reveal`、独立剧情、场景队列和聊天互动仍走包侧业务操作，尚未注册为 AI package 目标。

更新需重启后台以生成新 companion，刷新管理器／嵌入页；网页模式重新导出资源。已有房间的活动核心规则不会因重启自动替换：KP 应在规则管理导入当前包规则，使伤害与士气支持 `isNpc`；导入前检查其自定义规则，保留需继续使用的扩展文件。不要重置正式房间。

## 后续配置包的默认建议

建议作者默认提供明确的模板命名空间、允许替换范围、字段 Schema、B 正反例、C 场景／指标／未覆盖范围、语义名称、KP 队列和回执恢复。运行时与配置自动批准分别设置，默认关闭。不要以空扩展点表达“什么都能改”，也不要把前端隐藏当作玩家权限。

NPC 家族可显式使用 `contextMapping.extensionValidation` 约定，其定义包含 namespace、baseConfiguration、defaultsSchema、rulePrefix、fixtureRef；材料本地读取并计入包摘要。非 NPC 模型沿用通用 A/B/C 与作者场景，不应套用此特定探测器。配置删除与包侧跨账本事务仍待实现，见 [ISSUE-010](../../plans/Issues/issue-010-ai-package-mutations.md)。

## 验收

本轮离线工程与真实浏览器验收、包侧公开 HTTP 和真实模型实验分别记账，避免重复计数。用例、实际用量、通过与未通过项见[实验文档](../../plans/ai-rulings-experiments.md)；正式游戏存档不参与实验。
