# AI 修改裁决与配置包扩展

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-16
- 最后更新：2026-11-21
- 关联文档：[会话权限](ai-session-access.md)、[回答约定](ai-responses.md)、[嵌入组件](ai-pack-embedding.md)、[数据查询](ai-data-query.md)

## 一次提交，一次裁决

模型的 `batch` 与 `draft` 分别提交运行时动作和配置候选，均进入 KP 队列。模型文字不能授权执行；批准不可顺便修改候选。

| 类型 | 校验与执行 |
| --- | --- |
| runtime | 白名单 `actions:[{target,op,args}]`，固定来源、会话、权限与基线；生成前预检，批准后在受支持范围内整批提交，失败不提交暂存业务修改 |
| configuration | 完整 ChangeSet 经 A/B 硬校验和 C 评估后，满足人工采纳条件才在宿主事务发布；保留旧工件供在途流程，原实例数值不迁移 |
| player_request | KP 接收玩家原需求，在自己的私有管理员会话准备方案；不写游戏状态、不授予新知识，后续修改另行人工裁决 |
| knowledge_request | 玩家明确点击申请，KP 选择真实可披露分面；执行 `knowledge.observe` 成功才标记已披露，申请本身不扩大权限 |

运行时单批动作数量及存量批次数量不设业务上限；配置变更数组也不设数量上限。仍有明确的传输和存储容量约束：运行时动作参数总量 32 KiB、初始组装 2 MiB、累计传输最多 768 KiB（模型窗口可能进一步降低）、模型输出预算、JSON 文档 8 MiB。超限明确拒绝，不截断动作、不另设隐藏的条数上限。宿主批次、AI 单库事务及单条记忆转换有不同边界，见下节；模板发布与随后创建实例仍是两次裁决。

管理员短句“批准／批准执行／确认执行／同意执行／approve”只绑定当前会话最新需求的唯一裁决，不另发模型请求。高危或有风险项时转到队列填写决定，不能凭一句确认省略风险审核。重复完成项返回原结果。

## 运行时预检与原子边界

新候选携带 `preflight`，逐项给出 passed / blocked / unsupported / runtime_required、错误码及路径。确定性预检不写状态、不消费正式骰子。生成器将可修复的技术失败反馈模型，最多两次；失败或不支持的候选保留为 blocked，不能批准。权限、目标、代价和效果的真实分歧不能靠重试替用户决定。

| 执行范围 | 当前行为 |
| --- | --- |
| 全部为受支持 host 操作 | 使用[宿主原子批次](atomic-batches.md)，21种操作共享最终提交；不另设动作条数上限 |
| AI 会话创建／更新／删除、记忆草稿创建 | 同一 AI 仓库事务；业务记录、子回执和批次终态一起提交。删除会话的真实生成取消在提交后发生 |
| 单条记忆确认／撤销 | 权威事实与宿主回执一起提交，AI 镜像按原回执恢复；旧确认回执不能覆盖后续撤销 |
| 混合宿主与 AI、多条记忆跨库、flow.*、member.add、非公开 action 或其他不支持组合 | 预检阻止整批，不拆批绕过；目录中可识别的名称不等于支持原子执行 |

执行总状态为 completed / failed / rolled_back / unknown，逐项 `execution.items` 为 committed / failed / rolled_back / not_executed / unknown，附原 commandId、可见 result 和安全诊断。零成功失败不显示为部分完成；撤销表示丢弃未提交的暂存状态。父 ID 固定为 `ai-atomic:<batchId>`，宿主子 ID 由引擎生成；AI 单库子 ID 仍为 `ai-batch:<batchId>:<index>`。

旧 partial 记录按真实回执保留，不补造回滚；缺少原子版本的旧 pending 候选返回 `BATCH_REGENERATE_REQUIRED`。异常先查原回执，`ai.batch.reconcile` 不换 ID 或重放业务。记忆转换的原 AI 请求处于 unknown 时，仅在宿主已有 committed 事实后恢复镜像。

`committed` 表示事务提交。`passed=false`、`public.outcome=failure/blocked` 是实际游戏结果，不能自动重试、重掷或据此认定目标完成。裁决详情分别显示指令状态和业务结果。

## 关联、替代与归档

同一原请求反复生成相同 batch 或配置候选复用原记录；内容冲突返回 `REQUEST_CANDIDATE_CONFLICT`，配置修改继续使用原提案的修订接口。业务关系来自显式回复或来源关联，不能仅凭同会话、相似文字合并。新批次有效或新配置校验达到可裁决状态后，才将同事件未执行的旧待审项标为 superseded；失败的新尝试不会抢走旧候选。旧摘要、状态、回执和前后继定位仍可追溯。

KP 的任务和裁决 DTO 增加 queueTargetId、queueDigest、correlationId、queueStatus（active/history/superseded/archived）、supersededBy、supersedes、canArchive、canRestore、archived、archiveReason。自绘待办使用 queueStatus 分流，执行状态仍读 status；这些字段不返回 PL 任务。旧记录没有可信关系时不自动合并，可人工整理。

`ai.queue.archive {targetId,digest,archived,reason?}` 使用 **queueDigest** 做版本检查；targetId 为 request/batch/proposal/player/knowledge 加原 ID。归档必须填写 1—500 字符理由，恢复不清除已建立的 supersededBy。组织信息保存在独立元数据中，不删除正文、不取消业务、不改执行回执。`QUEUE_VERSION_CONFLICT` 要求刷新；`QUEUE_ITEM_PROTECTED` 表示不可整理；归档或被替代项的派发、批准被 `QUEUE_ITEM_INACTIVE` 拒绝。

生成中、排队中、校验中、执行中、结果未知、部分完成、已执行／已发布、已接收申请、有执行回执或宿主批准记录的项均受保护。只有人工恢复可恢复的记录才能回到可处理状态；已被后继替代的旧裁决恢复后仍不能批准。

## 高危与普通自动批准

服务端从完整候选和活动基线计算 `highRisk/riskTags/diff`：规则源码、地图或游戏数据的实际变化、物品／武器／容器模板、配置删除，以及包声明的关键配置 ID／前缀均为高危。模型不能自报低风险以绕过判断。

高危**始终人工确认**。`ai.ruling.decide` 除 `{rulingId,digest,decision,riskDecisions}` 外，批准须传 `explicitHighRiskDigest:digest`，并记录 `riskDecisions['high-risk']`。宿主 `ai.proposal.approve` 独立重算风险，将指纹纳入批准记录；`publication.apply` 再次复核。指纹不符返回 `HIGH_RISK_REVIEW_REQUIRED`，风险理由缺失返回 `RISK_REVIEW_REQUIRED`。旧批准、重复自然语言确认、普通自动审批都不能绕过。

`autoApproveBatches` 和 `autoApproveConfigurations` 默认关闭，只控制允许范围内的普通变更，执行人为保存策略的 KP。配置自动批准仍需 A/B/C 全部 pass、可发布来源且不需 C 人工采纳。来自 player_request 的审核会话始终人工批准，普通修改也不适用自动策略。`allowRuntimeChanges`、`allowConfigurationChanges` 可关闭对应写入，待执行内容同样受校验。

配置删除使用 `{kind:'remove',id,expectedRevision,value:null}`。所有活动或归档实例都不能仍引用目标；拒绝时返回 `REFERENCE_CONFLICT`，不自动级联。`Publication.configurationRevisions[id]=null` 表示已删除。规则替换仍校验现存行为引用、接口与工件完整性。模板删除不等于规则源删除：ChangeSet.sources 只接受文件名到完整 Lua 字符串的映射，未提供删除源文件操作，不能以 null 或空文件冒充已支持的删除。

## C 类评估与可变依据

A/B 的结构、作者许可、引用和执行检查是发布硬条件。C 原始报告及状态始终保留；只有 `unknown` 的全部 error 都属于 `EXTENSION_FORBIDDEN`、`LIVE_SCENARIO_COVERAGE_MISSING`、`EXISTING_INSTANCE_COVERAGE_MISSING` 时，才可交 KP 评估采纳。同名错误若来自 A/B 仍拒绝；沙箱执行失败、缺失规则、随机覆盖未知及其他 C error 不可采纳。

配置 DTO 的 `cAssessment` 给出 adoptable、requiresAcceptance、basisRevision、basisDigest、reportDigest、stale、findings 和 limitations。共享卡片保留三种处理动作及一处可选备注；“采纳评估并发布”将此次明确点击记为 riskDecisions，附 `cReview:{basisRevision,basisDigest,reportDigest}`，不编造人工理由。模型、普通自动审批和自然语言确认不能代替此次采纳。宿主批准与发布均重算并验证绑定；缺证明返回 `C_REVIEW_REQUIRED`。

KP 在设置中更新 `ai.c_basis.update {revision,metricOverrides,liveScenarios,notes}`。revision 必须等于当前版本；保存后递增并保留修改人、时间和原摘要。metricOverrides 只可调整作者已声明指标的 absoluteDelta 与 risk；补充场景实际运行于基线和候选，不能删除作者场景、改变 A/B 或任意声明通过。单次依据最多 32 KiB、64 指标、32 场景，notes 最多 2000 字符。版本冲突返回 `C_BASIS_VERSION_CONFLICT`。

检查时保存完整依据和摘要；依据变化后旧候选／批准返回 `C_BASIS_STALE`，按 `canRevalidate` 提供“按当前依据重新检测”，再人工裁决。补充场景只能调用基线与候选都存在的规则，三点随机探针不是穷尽玩法证明。模型在 KP 外发开启时可读发送时的 gameplayReview，但没有修改依据或自我批准工具。

AI 服务关闭后，宿主依据和权限回调重新读取持久化仓库，继续核验原批准；不缓存旧依据。依据仓库不可读时返回 `C_BASIS_UNAVAILABLE`，其他来源仓库不可读时返回 `AI_SERVICE_UNAVAILABLE`，均不跳过检查。重新启动的服务替换旧回调。

真实 C 报告、网页采纳、发布消费、依据变化拒绝与配置增删改结果集中在[本轮验收](../../../engineering/acceptance/ai-defaults-c-review/README.md)，不在当前文档复制实验流水。

## 接口和回执

`GET ai/rulings` / `AiClient.aiRulings()` 返回 KP 队列，包括来源、会话、概要、状态、digest、风险、完整动作或 ChangeSet、diff、报告和回执。`createAITools(client).rulings` 提供 list/decide。`mountRulings(...,{compact:true,onOpenSession,onKnowledgeRequest})` 支持紧凑摘要、详情浮窗和宿主披露选择器。知识申请的批准由选择器一次提交；未装选择器不能直接批准。创作申请按钮为“接收并生成方案”，接收后返回 KP 专用 reviewSessionId，onOpenSession 优先打开该审核会话；accepted 仅表示接收。接口和取消规则见[玩家创作申请](ai-session-access.md#玩家创作与配置申请)。

配置宿主命令 ID 固定为 `ai-ruling:<proposalId>:<revision>:approve/apply`。运行时与披露操作同样先保存执行意图再执行。未知结果只核对原回执，不自动换 ID 或重放：运行时用 `ai.batch.reconcile`，知识申请用 `ai.knowledge.reconcile {rulingId,digest}`。部分完成不等于全批成功。已批准未加载的配置保留原 approval，由公开接口核对或撤销。

配置裁决意图在执行前保存 `proposalRevision`；队列同时匹配修订号与候选摘要，再应用其状态和回执。`candidateDigest` 不包含宿主 epoch 或提案修订号，同内容重新修订、检查后摘要可能保持不变，不能据此把旧修订的拒绝套给新修订。读取不会删除或改写原决定，旧宿主回执与原 AI 命令回执仍可核对。

旧决定缺少 `proposalRevision` 时，只有全部回执 commandId 都完整符合上述格式、绑定同一 proposalId 且修订号一致，才推断修订归属；不会只取第一条或做前缀匹配。没有可靠归属的同摘要决定继续保留；其中 unknown／executing 即使摘要改变也继续阻止重试，不能将未知执行视为未执行。

重启前的待批准上下文仍会被宿主以 `STALE_AUTHORITY` 拒绝。明确拒绝且没有发布的候选，可通过公开 `ai.proposal.revise` 建立新修订并 `ai.proposal.validate` 重新三检；新修订通过后恢复 pending，必须再次人工批准高危完整候选和风险理由。修订仍复验当前权限、基线与保留的来源证据；调用方应先核对当前配置与原 diff.before，不能以重检为由覆盖期间变更。已有 publication 的完成事实仍优先显示，避免重复发布。

引擎隔离回归与旧记录兼容证据见[裁决修订验收](../../../engineering/acceptance/ruling-revisions/README.md)；配置包浏览器恢复入口由包侧独立联测。

执行会改变此前读取的实体修订。裁决状态与来源状态分开：

| sourceState | 原文和详情 | 执行 |
| --- | --- | --- |
| fresh | 当前来源有效，按权限返回摘要与详情 | 仍须通过批准时的实时校验 |
| stale | 来源变旧但仍可读取时保留详情；来源删除后仅凭绑定当前受众的交付证明保留原 summary，动作、候选、报告和差异隐藏，并标记 sourceDetailsUnavailable | 不可重新批准旧候选 |
| denied | 无法证明交付、真实授权撤销或会话失效，不恢复旧正文和详情 | 拒绝 |

公开 GET rulings 仅对 fresh 摘要记录 rulingDeliveries；内部查询不伪造交付。也可使用同请求已验证的 messagePublication 恢复原摘要。凭证绑定 scope、账号授权 epoch、上下文及原文摘要；不恢复执行权。completed、partial、unknown／executing 保留实际业务状态，重复批准已完成项不重新执行。

独立包参考来源须经下节风险评估，不能自动批准；宿主 `host-room` 来源继续使用宿主可信基线及权限复验。

## 包作者声明

以下材料必须来自本机管理员选择的不可变包快照，不能来自模型命令。引用文件加入 `sources`（KP 可见）以纳入摘要。

| 声明 | 格式与作用 |
| --- | --- |
| `PackContract.highRisk` | `{configurationIds,configurationPrefixes,ruleFiles,dataFiles,allowRemove}`；显式高危扩展目标，不免除结构、引用或三检。普通扩展仍用 extensionPoints |
| `contextMapping.gameTerms` | JSON 文件路径；仅 KP 在允许外发 KP 信息时加载到模型 gameTerms，解释复活等术语、前提与歧义。不是执行授权，不进入 PL 隐藏资料 |
| `contextMapping.stableArrays` | JSON 数组 `[{dataRef:'game.json',pointer:'/items',idKey:'id',appendOnly:true}]`；B 对比当时活动基线逐位 ID，禁止删减、重排和重复，覆盖后续已发布项 |
| `contextMapping.dataReferences` | `[{dataRef:'game.json',pointer:'/locations',idKey:'index',referencesKey:'exits',contiguousFrom:1,allowSelf:false}]`；最后两项可选，检查候选引用完整、连续编号及自引用 |
| `contextMapping.liveScenarios` | `[{configurationId,rule,actorInput,input,coversData:[],coversRules:[],expectedErrors:[],randomSides:20}]`；expectedErrors 与 randomSides 可选，C 自动用匹配的真实活动实体 ID 跑基线／候选，不硬编码存档 ID |

存量场景仅运行与实际 changed_data/changed_rules 相交的声明，其他记录 skipped-unaffected；相关声明的每个匹配实体都运行所声明骰面数的低／中／高三点探针（randomSides 默认 20，范围 2—10000）。声明覆盖的数据和变更文件导出的规则必须完整；`coversRules` 只可覆盖本条实际调用的 rule。两侧同一错误且在 expectedErrors 中才记录 blocked-compatible，不冒充执行成功；一侧成功、不同错误或未声明错误均失败。零匹配明确记录零样本。仍需包 fixture、必需指标及 A/B 校验，不代表剧情平衡的穷尽证明。

NPC 专项 `contextMapping.extensionValidation` 保留；其已完整验证的 NPC 规则不会再要求静态核心场景重复覆盖。核心或地图变更转用通用及存量场景。B 已允许但不属于 NPC 家族的配置修改，在 C 记录 EXTENSION_FORBIDDEN 覆盖边界，不能用 NPC 探针冒充覆盖。模板、规则、探测对象不再设置 32/8/64 条业务上限。

Stumpsville 的实际材料、发布后的包状态同步及限制由[包侧集成文档](../../../rulepacks/stumpsville/docs/current/integrations.md)维护，避免在模块文档复制过期清单。配置包默认应提供结构 Schema、稳定 ID、引用约束、B 正反例、C 场景与未覆盖范围、高危名单及回执恢复；空扩展点不表示任意修改获准。

作者 fixture/live/B 场景可经 `sandbox.run_scenario(...,private_rule_ids=())` 的精确名单验收私有计算；名单仅从不可变作者场景及规则 metadata 提取，私有调用的 scenario.account 必须为真实模拟 KP。默认无名单、PL account、未列规则仍拒绝；全部在 worker 的隔离副本运行，不提供任何线上私有规则调用权限。

删除配置还须开启包契约 highRisk.allowRemove；目标可以是 highRisk 显式名单，或原 extensionPoints 允许的类型和命名空间／既有 ID。删除始终按高危审核，普通 NPC 数值替换不会仅因允许删除而成为高危；仍被实体引用的模板不能删除。


## 来源审核与调试

所有原生裁决详情可“转 AI 处理”；未生成裁决的请求和包裁决也有统一来源入口，原裁决状态不因此改变。来源审核会话保持人工批准，见[统一审核接口](ai-debug-review.md#来源审核)。

模型 dataEdits 会先展开为完整候选再进入当前裁决流程；增量不是运行时执行命令，也不能绕过数据/核心规则的高危人工批准。修改摘要、diff 和批准指纹绑定完整结果，见[精确增量](ai-data-query.md#活动配置数据的精确增量)。

历史保留、来源幂等、关联替代、归档保护和紧凑引用的本轮成功率与失败处理见[专项验收](../../../engineering/acceptance/review-followup/README.md)。

阶段验收、初跑与复验关系见[开发记录](../../history/2026-11-20-ai-development-records.md)。

## 成功回执与关联闭环

运行批次仅在全部动作完成、固定命令 ID 逐条向实际宿主／AI 回执确认 committed 且与已存回执一致，并且没有明确的 false／failure／blocked 业务结果时记录 resolution。该只读字段包含 targetId、correlationId、goalDigest（完整执行计划摘要）、receiptRefs[{target,account,commandId}] 和 completedAt（UNIX 秒；旧记录缺失为 null）。resolution 展示前独立复验成功批次的历史来源权限；详情已隐藏或原来源不可访问时省略该字段，避免从普通前驱任务重新暴露回执命令 ID。只将同显式 correlation 且 supersededBy 前驱链可达成功批次的未执行项自动归档，附完成理由及凭证，不改写原状态或删除原文；自动闭环项不能恢复执行。

同角色、目标名称或相似文本不建立关系。执行中、unknown、partial、有已发批准／回执的记录保持保护；接收玩家申请 accepted 只是接收，不代表目的达成。当前闭环限 AI 运行批次；包 job 和配置发布不能仅声明 success 冒充该凭证。崩溃恢复时按实际回执补全整理，不重放动作。

## 生成快照与执行过程

生成期间资料变化不会自动丢弃已经形成的候选；任务返回具体依赖检查与明确重新生成入口，详见[发送快照](ai-session-access.md#发送快照与执行校验)。这不续用旧批准，也不保证候选能通过当前执行校验。裁决详情按序显示动作、参数、预检和执行 DTO。原任务 events 展示实际阶段、操作名和失败码；原子批次的暂存项可被标为 rolled_back，这不改写旧顺序批次已经提交的事实。

## 独立来源风险评估

配置和运行批次返回 `consultationAssessment={requiresAcceptance,sourceCount,sourceDigest,notice}`。摘要绑定完整当前 Context；资料标记为 consultationOnly 或已读引用来自独立包时，显示 `consultation-source` 风险。草稿必须先读当前宿主模板或活动工件，运行批次必须读取实际目标；历史建议和来源接受不能替代技术可执行性。

KP 点击“采纳评估并发布／执行”，传 `consultationReview:{sourceDigest}`，裁决接口另要求 `riskDecisions["consultation-source"]` 的明确理由。缺失或错误证明返回 `CONSULTATION_REVIEW_REQUIRED`；真实来源变化仍返回 `SOURCE_STALE`。宿主重新计算评估并将证明纳入批准摘要，发布时再检查；拒绝候选无需接受风险。配置与运行时自动批准均跳过这种候选，聊天中的普通“批准”不能伪造来源接受。

严格 PL 会话保持 CONSULTATION_ONLY 写入拒绝，不能使用 KP 证明越权。A/B 失败、过期目标、无权限及不支持的跨事务组合仍不可执行。来源接受是人工风险决定，不是提供了宿主与包存储的原子保证。
