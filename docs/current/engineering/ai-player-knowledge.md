# AI 玩家已知资料

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-17
- 最后更新：2026-11-19
- 关联文档：[设计与 D01—D16](../design/ai-player-knowledge.md)、[实施记录](../../history/2026-11-17-ai-player-knowledge.md)、[引擎知识服务](player-knowledge.md)、[会话权限](ai-session-access.md)、[Stumpsville 操作](../../../rulepacks/stumpsville/docs/current/player-knowledge.md)

## 当前通路

依赖后端 **0.3.0 / Room v4**。PL 会话绑定创建账号，只从宿主知识服务取得已披露内容。KP 创建玩家级会话也受相同上限约束，不能借实际 KP 身份读完整房间。未安装或绑定知识提供方、提供方故障、`egress.ai=denied` 均拒绝，不回退到 public／owner 或旧 adapter。

初始模型输入包含本人请求、已复验的引用与历史、会话权限、查询说明及 `knownIndex`：生成前自动用空 query 读取本人已授权目录（最多 50 项，含后续游标）。目录仅是标签，模型仍须 `room_read_knowledge` 读取详情后才能选择证据。完整包契约、作者指南、原始房间、聊天与共享记忆不进入严格 PL 上下文。玩家自报内容不创建知识，也不使猜测成为已确认事实。

| 环节 | 当前实现 |
| --- | --- |
| 模型工具 | `room_search_knowledge`、`room_read_knowledge`，主体固定为服务端会话 owner，`player=True` |
| 查询／引用 | PL HTTP 资料只接受 knowledge；`/knowledge` 补全不列未知对象；详情读取完整 `KnowledgeRef` |
| 输出 | 仅接受 kind=known、evidence=本轮已签发详情ID数组、next=none、ask_kp或ask_kp_change；不接受其他字段 |
| 排版 | 服务端按固定证据顺序、中文字段及分层列表渲染已授权结构；转义正文中的标记，不显示模型自由事实、猜测或自定义选项 |
| 知识不足 | 中性提示说明暂未匹配；ask_kp 提供主动披露申请按钮，不因空结果断言无权限或对象不存在 |
| 创作／修改 | ask_kp_change 提供独立创作申请按钮；输入区也可直接提交。KP 接收后创建私有管理员审核会话，修改另行人工裁决，见[申请规则](ai-session-access.md#玩家创作与配置申请) |

个人知识属于 **private 外发范围**，即使原实体标记 public。启用需同时满足：KP 允许玩家对话、启用服务配置／AI 调用、允许 private 外发、允许 AI 资料查询、包知识能力就绪且允许 AI 外发。

2026-11-18 已修复玩家提示词与服务商 JSON 模式的兼容问题，并在发送层增加格式指令兜底；严格 evidence 输出、知识授权和 KP 代建玩家会话的权限上限保持一致。HTTP 参数错误不会作为模型正文错误反复重试，见[服务商错误](ai-responses.md#json-请求与服务商错误)。

## 查询未命中与服务阻断

关键词 `query` 是字面过滤，不是语义检索。宽泛问题先读取个人目录，再选相关角色、场景或线索分面；名称可能位于角色表的装备字段内。非空 query 无匹配时，工具明确返回 `queryMatch:none / fallback:personal-index` 及同一玩家的目录，不伪装成关键词命中。继续使用目录的 nextCursor，最多 24 次查询（自动初始目录计 1 次），不会转读其他玩家或完整世界。

工具参数错误、旧引用等可恢复错误以安全工具结果返回，允许模型纠正后继续读取；外发策略、身份／知识撤销仍阻断。空结果只说明此次查询没有取得匹配资料；不返回“权限不足”作为通用兜底。

| 错误码 | 含义 |
| --- | --- |
| KNOWLEDGE_UNAVAILABLE | 包知识服务未安装、未绑定或不可用 |
| KNOWLEDGE_EGRESS_DISABLED | 包策略禁止个人知识外发 AI |
| EXTERNAL_SCOPE_DISABLED | 房间关闭 private 外发 |
| DATA_QUERIES_DISABLED | KP 关闭 AI 资料查询 |

`ai/access.knowledge` 返回 status、code 和可读说明；提交前置失败保留 requestErrors，任务/会话也返回安全 error。PL 界面显示处理提示，不接收堆栈、工具参数或 KP 诊断。关闭查询不等于关闭创作申请，后者独立受玩家对话和创作申请开关控制。

## 版本、历史和撤回

`observed_snapshot` 保存当时分面；名称、正文、标签和详情都固定到同一版本。原资料改名或更新不会刷新旧观察，也不会仅因无关世界变化阻断只读回答。`live_scope` 只用于明确持续告知的来源；Stumpsville 用于本人角色表和公共回合状态，场景不订阅未来变化。

引用格式为 `[[knowledge:<base64url完整KnowledgeRef>@1]]`。`@1` 是编码版本，内容修订在句柄内；不透明句柄不是访问凭据，复制给他人仍需重新授权。组件整体插入／删除引用，标签按当前授权复验，撤权后清空详情和标签，不能转读当前实体。

只读上下文 `facts.strictPlayer=true`，`reviewPrincipal=sessionAccess.owner`，`knowledgeProofs` 保存宿主证明。发送、工具查询、返回及历史展示时检查身份、恢复作用域、外发策略和来源。AI 调用 `require_egress("ai")` 与 `recheck_many`，同批证据共享一次来源捕获；引擎批准／发布不接受严格只读上下文。

旧回答缺少严格证明时不进入 PL 历史。格式错误默认沿用配置的 5 次修复上限，修复请求不回灌被拒绝的模型正文。撤权后阻止后续发送、在途回答和旧答案供给；无法收回已经交付给用户或服务商的内容。

## 数据排版与角色差异

结构化场景、线索、行动和角色数值由 `known_answers.format_data` 确定性展开，常用字段和已授权 `metadata.inventory` 的物品名称、说明、伤害、护甲、照明、用量与槽位使用中文名称，布尔值显示“是／否”。内部标识、导航映射、版本等技术字段不放进玩家正文；未知字段使用保守标签，不猜测其业务意义。长资料／深层嵌套有界展示，并提示打开引用详情。原证据、摘要和知识权限不因排版改变，观察记录也不被表述为当前可执行行动。

旧版严格回答中的已知 JSON 块，在历史来源复验成功后只读转换为同样格式，不改写持久记录，不调用模型或当前世界查询。普通 KP 自由正文、用户输入和配置代码不作猜测性转换；缺少授权证明的历史继续不显示。

引用详情和输入区“查看引用”同样提供结构排版。KP 的管理员会话保留管理字段，详情可主动展开技术原文；PL 及 KP 查看玩家级会话使用玩家展示。独立装配默认玩家视图。**展示差异不是权限过滤**：服务端先按真实身份和会话主体返回授权数据，包提供方须在创建知识前排除未披露事实，不能靠前端隐藏原文防止剧透。

包专有的字段单位、枚举及隐藏分支由包作者定义。Stumpsville 已在生成观察前按个人发现筛选行动，并分离 KP 机制、玩家措辞与显式披露；旧证据通过新版策略／guard 失效，操作与验收见[包侧现行规则](../../../rulepacks/stumpsville/docs/current/player-knowledge.md)。该修复使用现有引擎 API；通用展示契约仍是[引擎 ISSUE-012](../../plans/Issues/issue-012-authorized-data-presentation.md)评估项。

## 分阶段验收

2026-11-19 已知资料排版、旧回复只读转换及 KP／PL 显示分层通过 134 项相关测试，详见[显示验收](ai-responses.md#验收)。仅改变已授权数据的表现，不放宽严格 evidence 门槛；包侧内容投影缺口单列 ISSUE。

2026-11-18 玩家 JSON 模式兼容修复已通过实际 DeepSeek 请求及 215 项相关测试，见[本轮记录](../../../engineering/acceptance/ai-runtime/capability-fix-results.json)。下面的 384 项为此前个人知识阶段，不与本轮数字相加。

2026-11-17 按 A0—A3 与工程侧 K0—K5 对接。最终 **384 项 AI 测试去重全部通过**：全量原始记录为 383 通过、1 项测试操作遗漏；补齐 KP 转交步骤后 2 项操作台补验通过。原始失败保留，不重复累加。明细见[汇总](../../../engineering/acceptance/ai-runtime/known-results.json)、[全量](../../../engineering/acceptance/ai-runtime/known-full.xml)、[补验](../../../engineering/acceptance/ai-runtime/known-ui-retest.xml)。阶段专项如下：

| 阶段 | 交付及证据 |
| --- | --- |
| A0 | 严格输出、引用编码、能力／外发拒绝、批量复验；最初 18 项见 [A0](../../../engineering/acceptance/ai-runtime/known-a0.xml)，后续扩展纳入运行时专项 |
| A1 | 主体隔离、固定观察、无完整指南、在途撤权、旧回复复验、第二包证词及转交 KP；[85 项运行时专项](../../../engineering/acceptance/ai-runtime/known-runtime-final.xml)全部通过 |
| A2 | 单独／对话／折叠嵌入、原子引用、原观察详情、撤权清空、会话权限；初次 [5 项界面验收](../../../engineering/acceptance/ai-runtime/known-a2.xml)通过，扩展的 17 项组件／操作台浏览器测试均在最终全量及补验中通过 |
| A3 | [Stumpsville 12 组](../../../rulepacks/stumpsville/tests/strict-known-results.json)公开 HTTP／Edge 测试；原十地点／18 行动 [8 组回归](../../../rulepacks/stumpsville/tests/scene-results.json)通过；不同玩法[证词示例](../../../engineering/ai/examples/knowledge-investigation.py)不跟随未来改口 |

测试使用隔离存档、确定性模型及本机 HTTP。断言实际提供方输入和最终显示结果，包括模型夹带秘密的拒绝／重试，不以模型偶然未泄露代替权限验证。本轮未调用真实模型、修改正式房间或部署云端。

## 首版边界

按账号隔离；角色级主体、场景持续订阅、二进制知识资料、生成式事实摘要尚未开放。缺少历史受众／顺序证明的聊天和裁决不进入严格 PL AI。首次接入旧房间须显式转换 Room v4、绑定知识策略，并由 KP 选择现在揭示的旧地点；不能补造历史观察。开发者接线和源版本规则见[包侧说明](../../../rulepacks/stumpsville/docs/current/player-knowledge.md)。

2026-11-19 本轮查询与创作申请验收：按测试 ID 取最新结果去重 **190 项通过，0 失败、0 跳过**。覆盖真实宿主权限、私有审核、普通自动审批拦截、重启和 Edge 嵌入界面；初跑问题、复验关系与源码摘要见[本轮结果](../../../engineering/acceptance/ai-runtime/player-requests-results.json)。模块未调用付费 API、未修改正式房间；包侧隔离模型实测另行记录，不合并测试数。
