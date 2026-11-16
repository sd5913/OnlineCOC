# 房间 AI 接入与运行时配置设计

- 文档类型：计划
- 状态：进行中
- 创建日期：2026-11-12
- 最后更新：2026-11-13
- 关联文档：[实施与验收计划](ai-runtime-construction-plan.md)、[计划索引](README.md)、[项目概况](../current/design/project-overview.md)

2026-11-12：用户确认 A/B/C 的责任分工与交付方式，并要求精简和深化设计。本文保留已确认方向和首版方案。用户现已授权逐阶段实施：AI-0—AI-2 的契约、检查工具、共同执行器、人工提案、审批/发布与迁移恢复已完成，AI-3 服务商与编排已通过模拟及真实 DeepSeek 联调，AI-4 上下文/记忆与 AI-5 HTTP/SDK/KP 界面已验收，AI-6 实际 demo 工程试点与回归已完成；真实 KP 试玩反馈待补；实际能力见[工程说明](../current/engineering/ai-runtime.md)，任务及验收在实施计划维护。

2026-11-13：用户明确要求立即实现独立管理器和嵌入组件，Stumpsville 仅计划。新增交付与 AM-0—AM-4 验收见[当前管理器文档](../current/engineering/ai-manager.md)；树桩镇的具体依赖、阶段与门槛统一见[接入计划](stumpsville-ai-integration.md)。本文件保留原 AI-0—AI-6 的范围与人工试玩待办，不将包侧适配标记为已完成。

## 1. 目标、范围与建议结论

房间 AI 面向 KP，接收 KP 输入、转发的玩家需求或已开启的自动需求，参考授权上下文、配置包规则和宿主能力，生成方案及 Lua/JSON 变更，经 A/B/C 检查与 KP 审核后加载。

首版支持 DeepSeek 和自定义 Chat Completions 兼容端点；新增配置、允许字段修改及 Lua action/calculation。优先复用已有动作，发布房间扩展版本，不回写原包、不自动执行或发放实例。自动化止于生成和检查，发布始终需要 KP 批准。

暂缓 flow 自动生成、配置删除、实例迁移、修改 Python/前端/启动脚本、跨包侧存档写入和向量数据库。已有 flow 继续固定旧工件；若配置修改影响它且无法验证，阻止该修改。无机器可读包契约的旧包只开放咨询和草稿。

## 2. 已核查的工程基础与缺口

2026-11-12 初次核查形成下列工程决定；随后 AI-1 的检查工具和宿主回归已验收，结果及实际限制以工程说明为准：

| 现有依据 | 工程决定 |
| --- | --- |
| [Host](../../engineering/backend/src/onlinecoc/host.py)：单数据目录 demo、房间写锁、命令幂等 | 同主机组合独立 AI 服务；网络调用、沙箱和评估在锁外运行 |
| [registry](../../engineering/backend/src/onlinecoc/registry.py)：完整规则组、不可变工件；stage/activate/configuration.put 分开 | 合并完整工件；新增审批及单事务发布命令 |
| [模型](../../engineering/backend/src/onlinecoc/model.py)、[契约](../../engineering/contracts/models.json)：Room schemaVersion=1，拒绝未知字段；配置不会迁移旧实例 | 显式迁移 Room；AI 元数据不塞入 Configuration |
| [server](../../engineering/backend/src/onlinecoc/server.py)：预览只支持非 flow、固定骰面；普通请求体上限 64 KiB | 单独提供对照评估；普通 AI 命令传 ID，较大人工草稿走限额上传 |
| [Lua 运行器](../../engineering/backend/src/onlinecoc/lua_runtime.py)：inspect 执行顶层；已有进程/资源限制 | 在检查和正式执行两条路径补齐同一受限环境，不把现有隔离视为恶意代码托管保证 |
| [聊天领域](../../engineering/backend/src/onlinecoc/chat.py)：按频道授权、修订/撤回 | 不直接导出完整存档；来源变更使上下文和派生记忆失效 |
| [文件存储](../../engineering/data-management/onlinecoc_data/store.py)、[备份恢复](../../engineering/backend/src/onlinecoc/assets.py) | 复用单写入者和 CAS；AI 仓库与 Room 不声称具有跨仓库事务 |

配置包可能另有独立状态，不能假定 Host 已持有全部剧情事实。首版发布只覆盖主机事务内的扩展点；包侧可变状态须先变为主机版本化事实，否则只供咨询，不用于可发布提案。

## 3. 模块边界与运行路径

~~~mermaid
flowchart LR
  IN[KP/玩家需求] --> JOB[房间任务]
  CTX[授权上下文与记忆] --> JOB
  JOB <--> AI[服务商适配器]
  JOB --> P[不可变提案]
  P --> V[A/B/C 校验]
  V --> KP[KP 审核]
  KP --> H[主机复核与原子发布]
  H --> R[回执与确认记忆]
~~~

采用独立 Python 包 onlinecoc_ai，由主机启动器注入端口；业务模块不导入 FastAPI。每房间一个工作队列，服务随主机启停；AI 关闭/离线不影响普通游戏。

| 模块 | 固定职责/主要接口 |
| --- | --- |
| providers | validate_profile、probe、generate、cancel；统一模型响应与错误 |
| context / memory | capture、read_source、search、confirm、revoke；授权和来源版本检查 |
| pack / validation / sandbox | normalize_bundle、validate_base、validate_pack_rules、evaluate_gameplay；生成受信报告 |
| proposals / coordinator | 接收需求、状态转换、有限修复、生成 PreparedBundle；无批准/发布工具 |
| repository | AI 任务、草稿、报告、记忆与调用用量；独立文件存储 |
| 宿主 publication 端口 | approve、apply、revoke、receipt；Room 内审批与发布的唯一权威 |

只在短事务内持有各仓库锁；禁止持有 AI 仓库锁调用 Host，也禁止 Host 持锁等待 AI 仓库、模型或 worker。通过不可变快照传参，提交后异步对账。

<a id="41-配置与适配器"></a>

<a id="42-官方接口核查及本项目选择"></a>

## 4. 服务商接入与 DeepSeek 首版

ProviderProfile：profileId、revision、adapter、baseUrl、model、credentialRef、requestOptions、limits。首版主机管理员通过本机 CLI 配置，服务启停时加载；KP 只能选择允许的 profile。在线修改服务商配置后续再接本机管理授权入口。

默认 HTTPS；私网/本机端点需管理员明确允许，重定向重新校验目标，不允许玩家/包提交任意端点或请求头。密钥只在主机环境/秘密存储中解析，配置、日志、报告、包和备份只保存引用。AI 外发范围由房间设置明确选择，切换服务商或扩大范围须重新确认。

ProviderAdapter 输出 content、toolCalls、finishReason、usage、providerRequestId；能力快照绑定 profileRevision、model 和探测时间。首版非思考、非流式最终 JSON；空白、截断、未知字段、非法工具请求均在本地拒绝。strict/Beta 不是基础依赖；将来启用思考模式时，协议历史留在任务内，不作为长期记忆。

建议初值：每房间并发 1、排队 5、工具回合 6、格式修复 2、传输重试 2；连接超时 10 秒、单次请求总期限 120 秒、输出预算 4096 tokens。它们是可配初值，不是实测性能；另设每任务总期限和每日 Token 上限。永久认证/参数错误不重试，限流/暂时错误退避且不突破总预算；取消不保证服务商未计费，未知用量须保守预留。AI 重试与游戏发布幂等分开。

可复用开发锁文件中的 HTTPX，通过适配器隔离依赖；正式接入时纳入运行依赖与安装清单，不依赖开发环境。官方行为依据仍为 2026-11-12 查阅的[接入说明](https://api-docs.deepseek.com/)、[工具调用](https://api-docs.deepseek.com/guides/tool_calls/)、[JSON 输出](https://api-docs.deepseek.com/guides/json_mode/)和[思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)，实施时再探测账号实际能力，不固化模型别名。

<a id="5-配置包规则如何成为可用上下文"></a>

<a id="51-拟定-pack-ai-contract"></a>

<a id="52-权威顺序与依赖闭包"></a>

## 5. 配置包契约

ai/contract.json 是可选入口，引用 ai/schemas/*.schema.json、checks.json、fixtures/、scenarios/*.json、metrics.json 和 review-checklist.md；这些是拟新增包格式。缺失必需材料时返回 unknown，不能由模型自行补出“通过”标准。

| 契约字段 | 含义 |
| --- | --- |
| schemaVersion、packId、packVersion、hostProtocolRange | 身份及兼容范围 |
| sources、schemas、checks、scenarios、metrics、reviewChecklist | 引用文件、条款 ID、可见性；契约摘要覆盖全部引用内容 |
| extensionPoints | 可改配置 ID/命名空间、类型、JSON Pointer 路径、规则入口及禁止项 |
| contextMapping | 世界/角色/物品等字段映射及来源；必须能追溯到主机版本化事实 |
| requiredChecks、requiredMetrics、reviewPolicy | 必做项、风险确认项、准入条件；不随普通提案改写 |

宿主权限与不变量不可覆盖。包规则改变或 KP 房规须独立确认并形成契约修订，再重新检查提案。自然语言条文负责解释来源，机器约束负责检查；同一约束只维护一个权威定义。包内文件规范化为 stage 可接受文件名，拒绝路径逃逸、重解析点、同名/大小写冲突和摘要不符。

<a id="6-需求入口上下文与记忆"></a>

<a id="61-房间工作流"></a>

<a id="62-上下文预算"></a>

<a id="63-记忆分层与真实性"></a>

## 6. 上下文与记忆

ContextSnapshot 固定 scopeId、initiator、reviewPrincipal、authorityEpoch、authorizationEpoch、baseRuleset、configDigest、contractDigest、validatorSetDigest、worldDigest、sourceRefs、memoryRefs、included/omittedSources 和 createdAt。reviewPrincipal 由派发 KP 确定，自动模式绑定开启该模式的 KP，撤权即暂停。公开、KP、分组/私聊资料先按实际权限与外发设置取交集；KP 身份不自动赋予他人私聊读取权。其他 KP 只有当前有权读取提案全部来源，才能查看并批准。

worldDigest 首版保守覆盖所有游戏实体、关系、配置、成员权限、进度、活动流程/待办、room status/runId 及包契约。排除 AI 数据、审批、回执、审计、聊天已读等非游戏变化；被引用的消息/记忆独立记录版本。并发变化使评估过期，后续才考虑有证明的精确读集优化。客户端仅接收不透明令牌，不公开隐藏对象摘要或存储 generation。

上下文按平台边界→包规则/依赖→相关当前事实→已确认裁定→近期摘要排序，预留工具与输出预算；放不下硬约束时拆分任务或询问 KP，不静默截断。发送前、接受响应时、审批和发布前均复核权限及来源版本。

| 记忆类型 | 权威与生命周期 |
| --- | --- |
| 当前事实 | 从主机重新读取；玩家声称与摘要不能覆盖 |
| 事件索引 | 消息/回执/审批 ID 与修订，不复制未知事实 |
| KP 确认裁定/偏好 | KP 确认、修订、撤销及有效期；房规须同步契约 |
| 对话/情节摘要 | 模型辅助、附来源、继承最严格可见范围，不自动升级为事实 |
| 任务工作区 | 有限工具历史与备选方案，任务结束后按保留策略清理 |

MemoryEntry：memoryId、scopeId、kind、content、sourceRefs/revisions、visibility、status、validUntil、supersedes。首版结构化/关键词检索，不要求向量库；检索前过滤房间和权限。来源编辑、撤回、撤权与否决级联失效，包括摘要和缓存；玩家回复使用玩家投影重新组织或由 KP 明确编辑。停止检索不等于删除历史文件代、备份或服务商已收到的数据。

<a id="7-三类校验工具与评估证据"></a>

<a id="71-a基础格式与实际加载"></a>

<a id="72-b配置包规则与兼容性"></a>

<a id="73-c游戏性影响评估"></a>

<a id="74-统一报告"></a>

## 7. A/B/C 校验

### 7.5 开发主责与交付边界

保留原第 7.5—7.6 节入口，作为已确认分工与格式的唯一说明。

| 检查 | 主责及配合方 | 工具负责的结论 |
| --- | --- | --- |
| A 格式与加载 | 工程开发者主责；包作者补自定义数据 Schema/夹具 | 文件与 Schema 合法、引用可解析、真实 loader 可加载、最小场景可运行 |
| B 包规则符合性 | 包作者/规则维护者主责条款及正反例；工程提供检查器 | 变更属于扩展点，数值、依赖、代价、互斥、权限与旧实例/flow 兼容满足明确规则 |
| C 游戏性影响 | 包设计者定义场景/指标；工程实现对照；KP 接受或拒绝风险 | 收益/成本、概率、资源循环、选择替代和剧情影响，以及未覆盖项 |

A 的 Schema 描述数据表示；B 描述游戏允许的内容；C 比较合法内容的实际影响。AI 可解释、建议案例和修复提案，但不能改校验器、阈值或基准使自己过关。无密钥时三类已定义的确定性检查仍须可用。

### 7.6 提供格式与使用方式

| 材料 | 拟定最小字段/实现 |
| --- | --- |
| A | 平台及包 JSON Schema；valid/invalid JSON 夹具；真实 stage/模型校验共用受限 worker |
| B checks.json | checkId、sourceRef、selector、checkerId、parameters、required、caseRefs |
| C scenarios/*.json | scenarioId、fixtureRef、身份/权限、动作输入序列、randomPolicy、maxSteps、metricIds |
| C metrics.json | metricId、calculatorId、parameters、unit、比较方式、阈值及风险等级 |
| C review-checklist.md | 主观问题、适用条件、证据要求；由 KP 填结论与理由 |

首批受信 checkerId：core.numeric-range@1、core.reference-exists@1、core.unique@1、core.scenario-assert@1；计算器提供 success-rate、mean、maximum 的版本化实现。selector 只接受已声明集合/ID/typeRef 与字段路径，parameters 逐类校验，不支持 eval；必需检查零匹配为 unknown，必需字段缺失为 fail，不能按空集合自动通过。更复杂规则由包作者提出，再独立开发、审核注册插件，不能在运行提案中上传新的检查器。

例如“道具 bonus 取值 0—15”的 B 条目（仅格式候选）：

~~~json
{
  "checkId": "bonus-range",
  "sourceRef": "rules#item-bonus",
  "selector": {"collection": "configurations", "ids": ["demo.ext.lucky-token"]},
  "checkerId": "core.numeric-range@1",
  "parameters": {"pointer": "/defaults/bonus", "minimum": 0, "maximum": 15},
  "required": true,
  "caseRefs": ["fixtures/bonus-valid.json", "fixtures/bonus-invalid.json"]
}
~~~

A 先拒绝错误 JSON/重复键/非有限数/超限/越界路径，再运行受限 inspect 和候选世界烟测。B 检查合并后的完整工件，列出旧实例、行为绑定与旧 flow 影响；动态依赖无法确定时扩大验证或阻断。检查和正式执行生成源码均须使用通过验收的限权 worker（无凭据/真实存档写权/任意网络，限制 CPU、内存、墙钟、输出和进程树）；未完成只能交付模板/静态草稿演示，不能算完整首版。

C 在同一冻结世界的独立副本上执行基线与候选，使用场景声明的身份、动作和有界随机；绝不调用实时房间随机服务。可枚举则精确计算，否则记录算法版本、种子、样本数和不确定性。骰型/调用次数改变时不按序强行配对；基线为零不计算相对增幅。首版支持单动作与有界多步 action，缺少 flow 仿真证据的相关修改阻断。

三类共用 ValidationReport：reportId、level、status、candidateDigest、baselineDigest、contextDigest、contractDigest、validatorSetDigest、coverage、findings、evidence、createdAt。finding 包含 code、定位、条款、证据、建议；C 补充基线/候选/差值、单位、样本或精确枚举标记、风险及人工事项。

status=pass/fail/unknown/error。A/B 必需项须 pass；C 的 pass 仅表示必需评估已完成，风险等级独立保存，必需人工事项须由 KP 逐项处理。必需项 unknown/error 不得放行，非必需未覆盖项明确展示。CLI、KP 面板与 AI 工具调用同一核心；发布只接受主机受信服务登记的报告，客户端上传 pass 无效。

<a id="8-提案工具权限与-kp-审核"></a>

<a id="81-proposal-与-changeset"></a>

<a id="82-模型可调用工具"></a>

<a id="83-审核状态与界面"></a>

## 8. 提案与任务状态

| 对象 | 关键字段与不变量 |
| --- | --- |
| Request | requestId、scopeId、sourceKind、sourceId/revision、initiator、intent、dedupKey；聊天/手动/外部已确认文本统一归一化，不接原始音频 |
| Proposal | proposalId、revision、requestId、contextRef、profileRevision/model、summary、alternatives、changeSet、reportRefs；修改即新修订 |
| ChangeSet | configuration.add/replace 的完整载荷与 expectedRevision；完整 sources/data 候选；invocation.suggest 只作说明，不随发布执行 |
| PreparedBundle | 服务端组装的完整工件、配置变更、前置条件、报告与必需证据、摘要；不可由模型伪造身份或批准状态 |
| Approval | approvalId、proposalRevision、candidateDigest、baseline/contextDigest、contract/validatorSetDigest、reviewer、riskDecisions、expiresAt、status |
| Publication | publicationId、approvalId、commandId、旧/新工件及配置修订、审计时间、回执；一个批准最多对应一次发布 |

摘要复用现有 canonical JSON＋SHA-256。candidateDigest 覆盖 scopeId、完整规则/数据、配置变更及契约；不得仅 hash 显示差异。配置新 revision 由宿主按内容生成，同 ID 同修订不得对应不同内容；replace 不能改 typeRef，首版无删除/实例迁移。生成 ID、摘要、报告权威字段由服务端填写。

需求先保存为 received；仅 KP 派发或房间启用自动模式才进入 queued。后续主路径：queued → generating → validating → review_ready → approved → published。缺信息为 needs_input；检查不通过为 blocked；拒绝为 rejected；基线/来源/权限变化为 stale；取消为 cancelled。模型修复最多两轮并生成新提案修订。只在门禁满足时进入 review_ready，KP 手改也重跑。

发布中的 publishing/reconciling 是 AI 任务观察状态，不是成功证据；结果丢失只查主机回执。重启恢复生成任务为 interrupted，默认等待 KP 继续；已提交发布不重做。协调器用任务租约及 CAS 保证单一执行者，重试不得重复计费预算预留或消费批准。

模型工具只开放授权上下文/记忆、包条文读取、草稿提交与 A/B/C。没有 Shell、任意文件/网络、原始 Host.state、批准、发布或实体修改工具。所有工具参数验证任务绑定的 scope/权限；玩家文本、包文档和工具结果不能覆盖平台策略。

<a id="9-原子发布并发与恢复"></a>

<a id="91-首版必须新增的主机能力"></a>

<a id="92-恢复幂等与回退"></a>

## 9. 审批、原子发布与恢复

将原方案“批准后仍依赖独立草稿仓库”的边界进一步收敛为两步：

1. **approve**：锁外从受信 PreparedBundle 获取不可变副本；锁内验证当前 KP、摘要、报告、基线、来源、风险决定和期限。将候选工件登记到 Room.artifacts（仅暂存），配置变更及必要报告证据快照写入 Room.aiControl.approvals。批准不激活规则、不更新配置。
2. **publication.apply**：仅提交 approvalId、candidateDigest 与既有命令封套。锁内从 Room 读取已批准内容，复核身份、有效期、当前契约/检查器、全部前置条件；在同一拟状态更新配置、activeRuleset、批准 consumed、publication、审计及回执，验证最终模型后一次 commit。

publish 不访问 AI 仓库、不执行耗时 Lua/网络；审批与发布均使用主机权限。房间允许 active/paused，archived 拒绝。正式提交前世界变化返回 stale；KP 可主动暂停减少反复过期，但暂停不替代比较。中途更改 profile、来源或权限也须重新生成/验证适用部分并重新批准。

沿用 accountId＋commandId 幂等；再用 approvalId 防止换 commandId 重复发布。同 payload 返回原回执，不同 payload 冲突；跨重启按当前 epoch 重新发起未提交命令前先查原回执。故障后区分“已提交”“明确未提交”“未知待对账”，不得在不确定提交结果时写第二个拒绝事务覆盖证据。

旧 flow 固定旧工件但其后续阶段可读新配置，B 须明确兼容；新增 action 用新修订。回退是对旧工件/配置的新提案，检查现有引用后重新审批；不撤销真实骰点、伤害、库存和剧情进度。仅主机内的数据具有原子性，外部包文件不在事务内。

<a id="10-存储接口与工程落点"></a>

## 10. 存储、接口与迁移

### 存储归属

| 位置（拟定） | 数据及权威 |
| --- | --- |
| 主机数据目录 ai-providers.json | 管理员配置及 credentialRef；不随规则包或房间备份导出 |
| rooms/demo/ai/ | 独立 FileDataStore：requests、jobs、proposals、reports、memories、usage；任务层可重建 |
| Room.aiControl | scopeId、lineageId、contractBindings、settingsRevision、approvals、publications；审批与发布最终权威 |
| Room.artifacts | 原有及审批暂存/已发布工件；发布链无需独立 AI 仓库可用 |

采用 Room schemaVersion 1→2 显式迁移，文件存储格式仍为 1。先按旧模型验证，再增补 aiControl 并一次提交；已为 2 不重复迁移，未知版本拒绝。所有执行快照、模型校验、backup/restore 同步识别两代；旧程序不能打开新存档，应使用升级前备份回退。

scopeId 为存档内持久 UUID，避免多个 demo 串数据；正常重启沿用。恢复到新目录时创建新 scopeId，lineageId 保留来源；未消费批准撤销、运行中任务转 interrupted。记忆按来源重新校验，不能直接复用旧审批。

备份以 Room 中审批工件和必要报告快照为完整发布依据；AI 草稿/记忆为显式选项。需要 AI 快照时用维护屏障暂停任务写入、分别取快照并写最终 manifest，失败无有效 manifest，不声称两个 store 自动形成事务。未包含 AI 数据也可恢复已发布游戏。凭据永不导出；旧文件代保留历史，容量不足必须明确停止 AI 写入，清理不能删除已引用证据/工件。

### 应用契约

| 入口（实际实现以工程说明为准） | 权限、输入与输出 |
| --- | --- |
| GET /api/v1/capabilities | 追加 aiProtocolVersion、enabled、支持能力及限额；Room 数据迁移版本与 AI 接口版本分开，关闭 AI 时明确返回 disabled |
| POST /api/v1/ai/commands | 新 AI 封套：requestId、authorityEpoch、op、args；scope/账号由主机绑定；AI 仓库按账号/requestId 去重 |
| ai.request.create/cancel | 玩家管理自己的请求；KP 管理房间队列；返回任务 ID，不同步等待模型 |
| ai.proposal.revise/validate、ai.memory.confirm/revoke、ai.settings.update | KP；要求 expectedRevision；修改使相关审批过期 |
| GET /api/v1/ai/tasks/{id}、/proposals/{id} | 按权限分页/查询；玩家只有自己的脱敏进度；首版轮询，不塞进完整房间 WS |
| POST /api/v1/ai/drafts | KP 人工草稿上传，8 MiB 初始总限额，工件仍受真实 loader 限额；返回候选 ID |
| POST /api/v1/commands：ai.proposal.approve/revoke、publication.apply | 沿用主机命令封套和回执；批准入参为 proposalId/revision、candidateDigest、风险决定，服务端解析 PreparedBundle |
| 本机 ai-profile CLI | 配置、检查、探测；启服加载；在线探测只发送固定无房间内容的请求 |

HTTP 复用认证、Origin、CSRF，账号不能由载荷指定。AI 工具协议只暴露白名单子集；新增端点若经 LAN 使用须同步网关路由及权限验收，首版本机完成后再开放 LAN。大文件入口单独限额，不能全局放宽普通命令限制。

业务错误至少区分 INPUT_INVALID、NOT_VISIBLE、PERMISSION_DENIED、STALE_BASELINE、SOURCE_CHANGED、CHECKS_INCOMPLETE、APPROVAL_EXPIRED/CONSUMED、BUDGET_EXCEEDED、PROVIDER_UNAVAILABLE、STORAGE_UNAVAILABLE；task 记录可重试性与诊断，玩家错误不泄露秘密对象或路径。

## 11. 实施分期、试点与待确认项

实施顺序固定为：契约/最小包 → A/B/C 与共同沙箱 → 审批发布 → 服务商/任务 → 记忆/入口/KP 界面 → 真实包试点。先人工草稿完成“检查—审批—加载”，再接模型，详见[实施计划](ai-runtime-construction-plan.md)。

当前采用的工程默认：文件存储、宿主内组合服务、首版本机、非流式结果、自动接收默认关闭、明确需求按钮/前缀优先、无实例迁移；自动监听排除 AI 自己消息，以来源 ID＋修订去重，编辑/撤回取消未发布任务。外部输入须先转成可确认文本，不扩展本轮为语音模块。

实施前需决定的仅保留：真实试点包及维护者、房间预算/保留期、包的游戏性阈值。可先用 engineering/ai/tests/fixtures/pack/ 的最小技术包推进；它不代表任何现有包已适配。更换试点不改变协议，阈值不得由通用平台猜测。

机器契约与 AI-0 源码已创建；其余候选路径在相应实施任务施工前登记，真正创建时同步实际目录。既有主机权威、配置与实例分离、旧流程版本固定等决策保留，重复风险说明与逐条测试已集中到实施计划。
