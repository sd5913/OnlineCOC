# AI 修改裁决与配置包扩展

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-16
- 最后更新：2026-11-20
- 关联文档：[会话权限](ai-session-access.md)、[回答约定](ai-responses.md)、[嵌入组件](ai-pack-embedding.md)、[数据查询](ai-data-query.md)

## 一次提交，一次裁决

模型的 `batch` 与 `draft` 分别提交运行时动作和配置候选，均进入 KP 队列。模型文字不能授权执行；批准不可顺便修改候选。

| 类型 | 校验与执行 |
| --- | --- |
| runtime | 白名单 `actions:[{target,op,args}]`，固定来源、会话、权限与基线；逐项保存回执、顺序执行，失败即停，已成功项不自动回滚 |
| configuration | 完整 ChangeSet 通过 A/B/C 后，在宿主事务发布；保留旧工件供在途流程，原实例数值不迁移 |
| player_request | KP 接收玩家原需求，在自己的私有管理员会话准备方案；不写游戏状态、不授予新知识，后续修改另行人工裁决 |
| knowledge_request | 玩家明确点击申请，KP 选择真实可披露分面；执行 `knowledge.observe` 成功才标记已披露，申请本身不扩大权限 |

运行时单批动作数量及存量批次数量不设业务上限；配置变更数组也不设数量上限。仍有明确的传输和存储容量约束：运行时动作参数总量 32 KiB、初始上下文 96 KiB、累计请求 256 KiB、模型输出预算、JSON 文档 8 MiB。超限明确拒绝，不截断动作、不另设隐藏的条数上限。批次不是跨命令原子事务；模板发布与随后创建实例仍是两次裁决。

管理员短句“批准／批准执行／确认执行／同意执行／approve”只绑定当前会话最新需求的唯一裁决，不另发模型请求。高危或有风险项时转到队列填写决定，不能凭一句确认省略风险审核。重复完成项返回原结果。

## 高危与普通自动批准

服务端从完整候选和活动基线计算 `highRisk/riskTags/diff`：规则源码、地图或游戏数据的实际变化、物品／武器／容器模板、配置删除，以及包声明的关键配置 ID／前缀均为高危。模型不能自报低风险以绕过判断。

高危**始终人工确认**。`ai.ruling.decide` 除 `{rulingId,digest,decision,riskDecisions}` 外，批准须传 `explicitHighRiskDigest:digest`，并填写 `riskDecisions['high-risk']`。宿主 `ai.proposal.approve` 独立重算风险，将指纹纳入批准记录；`publication.apply` 再次复核。指纹不符返回 `HIGH_RISK_REVIEW_REQUIRED`，风险理由缺失返回 `RISK_REVIEW_REQUIRED`。旧批准、重复自然语言确认、普通自动审批都不能绕过。

`autoApproveBatches` 和 `autoApproveConfigurations` 默认关闭，只控制允许范围内的普通变更，执行人为保存策略的 KP。配置自动批准仍需 A/B/C 和可发布来源。来自 player_request 的审核会话始终人工批准，普通修改也不适用自动策略。`allowRuntimeChanges`、`allowConfigurationChanges` 可关闭对应写入，待执行内容同样受校验。

配置删除使用 `{kind:'remove',id,expectedRevision,value:null}`。所有活动或归档实例都不能仍引用目标；拒绝时返回 `REFERENCE_CONFLICT`，不自动级联。`Publication.configurationRevisions[id]=null` 表示已删除。规则替换仍校验现存行为引用、接口与工件完整性。模板删除不等于规则源删除：ChangeSet.sources 只接受文件名到完整 Lua 字符串的映射，未提供删除源文件操作，不能以 null 或空文件冒充已支持的删除。

## 接口和回执

`GET ai/rulings` / `AiClient.aiRulings()` 返回 KP 队列，包括来源、会话、概要、状态、digest、风险、完整动作或 ChangeSet、diff、报告和回执。`createAITools(client).rulings` 提供 list/decide。`mountRulings(...,{compact:true,onOpenSession,onKnowledgeRequest})` 支持紧凑摘要、详情浮窗和宿主披露选择器。知识申请的批准由选择器一次提交；未装选择器不能直接批准。创作申请按钮为“接收并生成方案”，接收后返回 KP 专用 reviewSessionId，onOpenSession 优先打开该审核会话；accepted 仅表示接收。接口和取消规则见[玩家创作申请](ai-session-access.md#玩家创作与配置申请)。

配置宿主命令 ID 固定为 `ai-ruling:<proposalId>:<revision>:approve/apply`。运行时与披露操作同样先保存执行意图再执行。未知结果只核对原回执，不自动换 ID 或重放：运行时用 `ai.batch.reconcile`，知识申请用 `ai.knowledge.reconcile {rulingId,digest}`。部分完成不等于全批成功。已批准未加载的配置保留原 approval，由公开接口核对或撤销。

配置裁决意图在执行前保存 `proposalRevision`；队列同时匹配修订号与候选摘要，再应用其状态和回执。`candidateDigest` 不包含宿主 epoch 或提案修订号，同内容重新修订、检查后摘要可能保持不变，不能据此把旧修订的拒绝套给新修订。读取不会删除或改写原决定，旧宿主回执与原 AI 命令回执仍可核对。

旧决定缺少 `proposalRevision` 时，只有全部回执 commandId 都完整符合上述格式、绑定同一 proposalId 且修订号一致，才推断修订归属；不会只取第一条或做前缀匹配。没有可靠归属的同摘要决定继续保留；其中 unknown／executing 即使摘要改变也继续阻止重试，不能将未知执行视为未执行。

重启前的待批准上下文仍会被宿主以 `STALE_AUTHORITY` 拒绝。明确拒绝且没有发布的候选，可通过公开 `ai.proposal.revise` 建立新修订并 `ai.proposal.validate` 重新三检；新修订通过后恢复 pending，必须再次人工批准高危完整候选和风险理由。修订仍复验当前权限、基线与保留的来源证据；调用方应先核对当前配置与原 diff.before，不能以重检为由覆盖期间变更。已有 publication 的完成事实仍优先显示，避免重复发布。

引擎隔离回归与旧记录兼容证据见[裁决修订验收](../../../engineering/acceptance/ruling-revisions/README.md)；配置包浏览器恢复入口由包侧独立联测。

执行会改变此前读取的实体修订。来源复验失败时，completed 仍显示“已执行完成，请勿重复执行”，partial 显示“部分操作已执行，请核对原回执”，unknown／executing 提示核对结果；仅待执行内容提示重新读取并生成方案。权限撤销时仍隐藏原摘要、动作、候选、报告、差异和回执内容，只保留裁决状态及脱敏 receipt.status，不输出命令 ID、参数或结果。重复批准已完成项返回完成状态，不重新执行。

包侧独立状态等 `consultationOnly` 来源仍只供咨询；宿主与包文件尚无跨存储原子快照。读取这些来源不能据此执行配置发布。宿主 `host-room` 查询属于宿主可信基线，保持来源与权限复验。

## 包作者声明

以下材料必须来自本机管理员选择的不可变包快照，不能来自模型命令。引用文件加入 `sources`（KP 可见）以纳入摘要。

| 声明 | 格式与作用 |
| --- | --- |
| `PackContract.highRisk` | `{configurationIds,configurationPrefixes,ruleFiles,dataFiles,allowRemove}`；显式高危扩展目标，不免除结构、引用或三检。普通扩展仍用 extensionPoints |
| `contextMapping.gameTerms` | JSON 文件路径；仅 KP 在允许外发 KP 信息时加载到模型 gameTerms，解释复活等术语、前提与歧义。不是执行授权，不进入 PL 隐藏资料 |
| `contextMapping.stableArrays` | JSON 数组 `[{dataRef:'game.json',pointer:'/items',idKey:'id',appendOnly:true}]`；B 对比当时活动基线逐位 ID，禁止删减、重排和重复，覆盖后续已发布项 |
| `contextMapping.dataReferences` | `[{dataRef:'game.json',pointer:'/locations',idKey:'index',referencesKey:'exits',contiguousFrom:1,allowSelf:false}]`；最后两项可选，检查候选引用完整、连续编号及自引用 |
| `contextMapping.liveScenarios` | `[{configurationId,rule,actorInput,input,coversData:[],coversRules:[],expectedErrors:[]}]`；expectedErrors 可选，C 自动用匹配的真实活动实体 ID 跑基线／候选，不硬编码存档 ID |

存量场景仅运行与实际 changed_data/changed_rules 相交的声明，其他记录 skipped-unaffected；相关声明的每个匹配实体都运行 d20=1/10/20 探针。声明覆盖的数据和变更文件导出的规则必须完整；`coversRules` 只可覆盖本条实际调用的 rule。两侧同一错误且在 expectedErrors 中才记录 blocked-compatible，不冒充执行成功；一侧成功、不同错误或未声明错误均失败。零匹配明确记录零样本。仍需包 fixture、必需指标及 A/B 校验，不代表剧情平衡的穷尽证明。

NPC 专项 `contextMapping.extensionValidation` 保留；其已完整验证的 NPC 规则不会再要求静态核心场景重复覆盖。核心或地图变更转用通用及存量场景，不以 NPC 探测冒充覆盖。模板、规则、探测对象不再设置 32/8/64 条业务上限。

Stumpsville 的实际材料、发布后的包状态同步及限制由[包侧集成文档](../../../rulepacks/stumpsville/docs/current/integrations.md)维护，避免在模块文档复制过期清单。配置包默认应提供结构 Schema、稳定 ID、引用约束、B 正反例、C 场景与未覆盖范围、高危名单及回执恢复；空扩展点不表示任意修改获准。

作者 fixture/live/B 场景可经 `sandbox.run_scenario(...,private_rule_ids=())` 的精确名单验收私有计算；名单仅从不可变作者场景及规则 metadata 提取，私有调用的 scenario.account 必须为真实模拟 KP。默认无名单、PL account、未列规则仍拒绝；全部在 worker 的隔离副本运行，不提供任何线上私有规则调用权限。

删除配置还须开启包契约 highRisk.allowRemove；目标可以是 highRisk 显式名单，或原 extensionPoints 允许的类型和命名空间／既有 ID。删除始终按高危审核，普通 NPC 数值替换不会仅因允许删除而成为高危；仍被实体引用的模板不能删除。


## 来源审核与调试

所有原生裁决详情可“转 AI 处理”；未生成裁决的请求和包裁决也有统一来源入口，原裁决状态不因此改变。来源审核会话保持人工批准，见[统一审核接口](ai-debug-review.md#来源审核)。

模型 dataEdits 会先展开为完整候选再进入当前裁决流程；增量不是运行时执行命令，也不能绕过数据/核心规则的高危人工批准。修改摘要、diff 和批准指纹绑定完整结果，见[精确增量](ai-data-query.md#活动配置数据的精确增量)。

阶段验收、初跑与复验关系见[开发记录](../../history/2026-11-20-ai-development-records.md)。
