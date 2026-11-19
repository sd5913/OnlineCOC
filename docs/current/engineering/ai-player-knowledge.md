# AI 玩家已知资料

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-17
- 最后更新：2026-11-18
- 关联文档：[设计与 D01—D16](../design/ai-player-knowledge.md)、[实施记录](../../history/2026-11-17-ai-player-knowledge.md)、[引擎知识服务](player-knowledge.md)、[会话权限](ai-session-access.md)、[Stumpsville 操作](../../../rulepacks/stumpsville/docs/current/player-knowledge.md)

## 当前通路

依赖后端 **0.3.0 / Room v4**。PL 会话绑定创建账号，只从宿主知识服务取得已披露内容。KP 创建玩家级会话也受相同上限约束，不能借实际 KP 身份读完整房间。未安装或绑定知识提供方、提供方故障、`egress.ai=denied` 均拒绝，不回退到 public／owner 或旧 adapter。

初始模型输入只包含本人请求、已复验的引用与历史、会话权限和查询说明。完整包契约、作者指南、原始房间、聊天与共享记忆不进入严格 PL 上下文。玩家自报内容不创建知识，也不使猜测成为已确认事实。

| 环节 | 当前实现 |
| --- | --- |
| 模型工具 | `room_search_knowledge`、`room_read_knowledge`，主体固定为服务端会话 owner，`player=True` |
| 查询／引用 | PL HTTP 资料只接受 knowledge；`/knowledge` 补全不列未知对象；详情读取完整 `KnowledgeRef` |
| 输出 | 仅接受 kind=known、evidence=本轮已签发详情ID数组、next=none或ask_kp；不接受其他字段 |
| 排版 | 服务端固定顺序渲染授权数据，转义 Markdown／HTML／嵌套引用；不显示模型自由事实、猜测或自定义选项 |
| 知识不足 | 固定提示和“请 KP 说明／仅整理已知资料”选项；发送前者进入 KP 可见的待处理需求，不再次自动调用模型 |
| 修改 | 严格 PL 回答不能创建执行批次；KP 在管理员会话处理需求，沿用三检和裁决流程 |

个人知识属于 **private 外发范围**，即使原实体标记 public。启用需同时满足：KP 允许玩家对话、启用服务配置／AI 调用、允许 private 外发、包知识能力就绪。

2026-11-18 已修复玩家提示词与服务商 JSON 模式的兼容问题，并在发送层增加格式指令兜底；严格 evidence 输出、知识授权和 KP 代建玩家会话的权限上限保持一致。HTTP 参数错误不会作为模型正文错误反复重试，见[服务商错误](ai-responses.md#json-请求与服务商错误)。

## 版本、历史和撤回

`observed_snapshot` 保存当时分面；名称、正文、标签和详情都固定到同一版本。原资料改名或更新不会刷新旧观察，也不会仅因无关世界变化阻断只读回答。`live_scope` 只用于明确持续告知的来源；Stumpsville 用于本人角色表和公共回合状态，场景不订阅未来变化。

引用格式为 `[[knowledge:<base64url完整KnowledgeRef>@1]]`。`@1` 是编码版本，内容修订在句柄内；不透明句柄不是访问凭据，复制给他人仍需重新授权。组件整体插入／删除引用，标签按当前授权复验，撤权后清空详情和标签，不能转读当前实体。

只读上下文 `facts.strictPlayer=true`，`reviewPrincipal=sessionAccess.owner`，`knowledgeProofs` 保存宿主证明。发送、工具查询、返回及历史展示时检查身份、恢复作用域、外发策略和来源。AI 调用 `require_egress("ai")` 与 `recheck_many`，同批证据共享一次来源捕获；引擎批准／发布不接受严格只读上下文。

旧回答缺少严格证明时不进入 PL 历史。格式错误默认沿用配置的 5 次修复上限，修复请求不回灌被拒绝的模型正文。撤权后阻止后续发送、在途回答和旧答案供给；无法收回已经交付给用户或服务商的内容。

## 分阶段验收

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
