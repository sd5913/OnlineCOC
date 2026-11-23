# AI 回答、语义引用与选择项

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-16
- 最后更新：2026-11-23
- 关联文档：[嵌入接口](ai-pack-embedding.md)、[数据查询](ai-data-query.md)、[权限与批次](ai-session-access.md)、[包侧写入责任](../../plans/Issues/issue-010-ai-package-mutations.md)

## 基础错误修正与用户决策

技术修复共用最多两次额度，实际值为 `min(limits.maxRepairAttempts, 2)`；旧 Profile 中大于 2 的值不会增加本次修复上限。修复轮次与 `maxToolRounds` 独立，仍受任务超时、用量和权限复验约束。格式、工具参数、批次预检、基础配置错误及未取证的否定查询回答共用该额度。

JSON 解析、非对象输出、缺失／错误字段、非法引用和选项会反馈错误代码与结构路径，要求模型返回完整正确对象。只接受完整 JSON 或唯一完整 JSON 围栏，不从任意解释文字中猜测提取。已生成配置的 A 检查若发现基础 Schema／Lua／引用错误，修订同一提案重检；不生成多份待批配置，不自动忽略 B/C 或风险决定。

系统提示统一列出 plan、clarification、draft、batch 四种顶层格式；仅 draft 使用 changeSet，管理员运行时批次必须使用 actions。修正反馈附 requiredFields／allowedFields／missingFields／unexpectedFields，批次另附实际输出 Schema 与已成功工具名。格式失败后的批次不能改为 plan 或 draft 来绕过修正，返回 MODEL_REPAIR_KIND_CHANGED 后继续使用剩余额度；真实缺失决策仍可返回 clarification。不会将 changeSet.suggestions 自动转换为可执行动作，也不据格式错误宣称工具未开放。

用户已委托的文案、氛围、装饰名称等低影响细节，提示要求选保守兼容方案并简述假设；涉及对象、公开或保密、不可逆范围或不同玩法效果的重大未决选择，模型返回一次合并的 `clarification`，任务进入 `needs_input` 等待用户。显式要求等选择时必须等待；用户选定后保留决定。兼容旧模型的 plan+choices 也进入 needs_input。技术失败不构成重新确认意图的理由。

管理员模型若把单个合法 plan/clarification 放进同名工具调用的 arguments，服务端转为正常回答并占用一次共用纠错额度，随后继续校验选择项与引用；不执行伪工具。多工具、未知名称、批次或发布命令不走此兼容。实体引用与错误字段过滤的限定纠正见[数据查询](ai-data-query.md#工具与接口)。

提示要求逐项核对实际候选差异与用户目标，部分已完成时读取活动资料并只补缺项，尤其核对双向连接的两端。候选、已批准未发布工件及模型文字都不是成功凭证；结果以真实 publication/execution 回执为准。这些语义提示不等于任意自然语言目标的自动证明器，真实模型成功率须单独实验。

执行账本提供最近同会话裁决的原请求、授权动作和真实状态；新数值修改附原值，旧记录不补猜。已识别的简短“继续”若重新写最近意图已完成／待批／结果不明动作的相同目标，返回 `INTENT_EXECUTION_REPLAY` 并在共用额度内要求说明真实状态，不能再扣款、再发放或重复通知。明确追加是新的需求。该检查不覆盖任意自然语言，也不推断不同请求属于同一业务；权限撤回后账本详情仍隐藏。

明确“发一份”属于增量，不能用已有库存替代。已复现的“已经有，所以不需要再发”误拒绝触发 `REQUESTED_INCREMENT_OMITTED`；“确保有”仍可按现状满足。金额结算的支付／收取方向如确实不明，提示要求一次澄清该重大选择。确定性与真实模型结果分别见[本轮记录](../../../engineering/acceptance/ai-ambiguity-recovery/README.md)。

`MODEL_OUTPUT_INVALID` 表示基础输出修正次数耗尽；诊断展开可查看 `MODEL_JSON_INVALID`、`MODEL_FIELDS_INVALID`、`MODEL_CHOICES_INVALID`、`MODEL_REPAIR_KIND_CHANGED`、`REFERENCE_UNVERIFIED` 或 A 检查代码等具体原因及修正次数。只记录结构路径，不记录原异常文本。空响应、协议错误或输出截断也使用这项修正额度，但耗尽后保留对应 `PROVIDER_*` 原因；认证、连接、权限、基线或任务超时不包装成格式错误。

工具调用的坏 JSON 或参数 Schema 错误会返回具体字段与真实 Schema，再由模型修正；已计费用的响应保留实际 usage。批次参数与公开规则 input 也校验精确路径，随后运行无写入预检。模型须区分物品定义 ID 与库存槽位，根据授权记录修正唯一引用，不能让用户修 JSON 或猜测目标。`MODEL_TOOL_REPAIR_LIMIT` 表示工具修复耗尽；`BATCH_PREFLIGHT_BLOCKED` 和 `BATCH_UNSUPPORTED` 保留不可批准候选及逐项原因。

按需读取场景中，明确查询请求若未取得任何成功的房间查询证据，却回答“未找到／不存在／没有记录”，触发 `MODEL_EVIDENCE_REQUIRED`，在同一修复额度内要求实际查询。真实空查询可回答未找到；查询未完成须明确说明。此检查针对已识别的否定表达，不是任意自然语言事实的完整证明器。完整生产提示的首次失败、短反馈 API 复测和边界回归分别保留在[本轮验收](../../../engineering/acceptance/ai-defaults-c-review/README.md)。

实际出现的“只读 entity.patch 子集便断言不存在数值修改命令”会与完整操作名称索引核对；匹配该错误时返回 MODEL_CAPABILITY_UNPROVEN，在既有修复额度内纠正。此检查针对已复现模式，不宣称能自动判断任意自然语言的正确性。

## JSON 请求与服务商错误

玩家提示明确要求 JSON 对象；兼容发送层在 system/user 消息都没有 `json`（忽略大小写）时，增加一条格式指令，不修改调用方历史或玩家知识权限。依据 [DeepSeek JSON 模式说明](https://api-docs.deepseek.com/guides/json_mode)，仅提供对象示例不足以满足服务商的提示词检查。

HTTP 拒绝与模型回答格式错误分开处理：

| HTTP 状态 | 错误代码 | 处理 |
| --- | --- | --- |
| 400、422 | `PROVIDER_REQUEST_INVALID` | 检查请求参数，不使用模型格式修复次数 |
| 402 | `PROVIDER_BALANCE_INSUFFICIENT` | 检查服务商余额 |
| 404 | `PROVIDER_NOT_FOUND` | 检查接口地址或模型名 |
| 413 | `PROVIDER_REQUEST_TOO_LARGE` | 缩小发送资料 |
| 401、403 | `PROVIDER_AUTH_FAILED` | 检查凭据或服务商访问权限 |
| 408、429、5xx | `PROVIDER_TIMEOUT`、`PROVIDER_RATE_LIMITED`、`PROVIDER_UNAVAILABLE` | 按 `maxTransportRetries` 有界重试 |
| 3xx／其他非 200 | `PROVIDER_REDIRECT_REJECTED`／`PROVIDER_HTTP_ERROR` | 拒绝重定向或报告其他 HTTP 异常 |

`UNSUPPORTED_CAPABILITY` 保留给返回了不支持的思考内容、JSON／工具能力探测未通过等能力检查，不再笼统代表 HTTP 参数错误。已获得 HTTP 200 的正文仍可能格式无效，继续使用前述最多两次技术修复额度。历史失败记录不自动重跑或改写。

聊天区提供对应中文说明；KP 的诊断保留错误代码和可选 `httpStatus`，不保存服务商错误正文、响应头、密钥或请求内容。PL 仍不接收诊断详情。更新代码后需重启承载 AI 的房间宿主；刷新管理器和嵌入页面，已打包网页需重新构建资源。

## 回答与引用

系统提示与树桩镇指南默认要求：约 150—300 汉字（不计引用标记／选择项），先一句结论，设计或多项事实接 2—4 条 Markdown 列表，段间空行，每段至多两句，属性合为一行；用户要求详细方案时展开。正文使用生命、护甲、位置等语义名称，诊断独立展示；仅影响下一步的限制简短说明一次。已确认的创建方向直接生成可审核批次，不再反复确认。可查询的数据由模型查询，不转问用户。过期但仍有权查看的旧方案以 historical-intent-only 参与短句确认；修改前重新读取当前目标，不能沿用旧事实或批准。此处是生成约束，不保证任意模型固定字数，也不截断重要内容；旧回复不会被重写。

模型查询结果在不改变原 EvidencePage 与证据摘要的前提下，额外提供 `citation: {token,label}`。实体／配置 token 使用真实业务 ID 与修订，聊天／事件／裁决使用对应证据引用；不把 `ref.id` 当作业务 ID。无对应语义引用的规则、频道等类型仍使用可读名称。

模型在正文中原样使用收到的 `[[entity:真实ID@修订]]` 等 token。服务端只接受本次已提供的引用或经复验的历史引用，伪造／不完整标记进入修复流程，仍不合法则拒绝回答。前端通过现有授权解析接口呈现有底色的名称标签；引用过期或不可见时显示对应状态。模型不会自选显示名称冒充其他对象。行内代码中单独出现的合法引用也会渲染为标签；完整代码块保留原文。

旧回复中的普通 ID 不作猜测性替换；只有真实绑定的引用可转换。模板没有可读名称时使用原 ID。受信包适配器可提供 `reference_label(kind,key,fallback)` 返回 1—160 字符的显示名；当前用于配置模板，先完成可见性过滤，再调用映射，失败沿用原名。树桩镇为 NPC、角色、地点及场景模板提供语义名称。这个接口不增加可读权限。

## 引用详情与稳定渲染

对话历史和 `mountMarkdown` 的引用标签支持点击／Enter／空格打开二级详情面板；Escape、关闭按钮或点击遮罩关闭并恢复焦点。对象使用字段列表、数组使用分层条目，常见字段显示中文名，深层／长资料提示部分未展开，不再回退为 JSON。只构造文本 DOM，不执行数据中的 HTML。编辑器仍保持引用的整块插入、删除行为。

| 展示层级 | 内容 |
| --- | --- |
| 玩家（默认） | 已授权正文、名称、资料类型／观察时间；不展示技术标识、导航映射和原始 JSON 入口；未知字段用保守标签 |
| 管理员 | 同样的可读排版，加修订／可见性、管理字段和原字段名；“技术详情（原始数据）”默认折叠 |

对话自动按“真实 KP 且管理员会话”选择管理员展示；KP 查看玩家级会话仍使用玩家展示。输入区“查看引用”也按同样规则显示结构化数据。层级仅控制表现，不扩大服务端授权；不能靠字段隐藏补救源数据过度披露。严格 PL 正文只显示名称、短用途和引用入口，完整树形资料点击后查看；旧结构回复经来源复验后只读转换，详见[玩家已知资料](ai-player-knowledge.md#数据排版与角色差异)。

包可通过同步 `renderReference(item,{audience,readOnly:true})` 返回 Node 或 null 复用本包只读语义视图；完整 DTO、回退与生命周期见[嵌入接口](ai-pack-embedding.md#配置包引用详情渲染)。

每次打开及对话刷新时，通过 `aiResolve` 重新读取精确 token 的当前授权数据；过期显示“引用已过期”，失权／不可读清除旧详情，不静默跳到新版。只展示服务端投影，PL 不因此获得完整 NPC 属性。详情不缓存数据；身份切换、切换会话、暂停／删除／卸载时清空，乱序请求不得覆盖较新的面板。

轮询按 requestId 和展示内容保留未变化的消息 DOM，不再把所有标签反复变为“数据引用”后解析；即使任务状态或选项状态更新，也复用未变的用户文字和回答正文。首次出现仍需一次异步解析名称；正文或权限改变时按新数据重绘。`mountMarkdown.update` 的正文、模式和解析函数未变时也保留节点，支持先挂载组件再将目标节点插入页面。

低层接入可组合 `renderMarkdown`／`renderReferenceText`、`hydrateReferences` 和 `bindReferenceDetails`：

```js
const resolve = tokens => client.aiResolve(tokens);
renderMarkdown(body, task.response);
await hydrateReferences(body, resolve);
const details = bindReferenceDetails(body, resolve, {container, valid: () => stillAuthorized});
// 收到权限／来源变化时刷新；身份切换或卸载时立即销毁。
await details.refresh();
details.destroy();
```

`container` 默认为 body 的父节点，可传 HTMLElement／ShadowRoot；返回 open(token, anchor?)、close、refresh、destroy。`audience` 可为 `player`（默认）、`administrator` 或返回这两个值的函数；`mountMarkdown` 对应选项只接受字符串。管理员展示需接入方根据真实身份及会话权限决定，不能使用用户传入的 URL 参数。解析回调须返回与 token 相同 kind/id/revision 的授权对象及 value。刷新时展示层级变化会重建详情；自定义接入仍负责及时清理换身份后的内容，不使用不复验权限的全局数据缓存。资源清单和树桩镇构建图包含 `reference-details.js/css`。

## 结构化选择项

当前用户明确提交了某个选项的完整文本后，生成输入保留 resolvedChoices。若模型再次返回同一组选项，服务端以 REPEATED_RESOLVED_CHOICE 要求纠正，计入已有最多两次修复额度；新取舍仍可提问。该检查只识别当前明确匹配，用户重新选择或改变主意不会被旧选项锁住；不把模糊回复推断成授权，也不代替执行审批。较早需求保留与模板预读见[上下文机制](ai-session-access.md#上下文连续性与预算)。

`plan`、`clarification` 输出可额外携带以下字段；`draft`、`batch` 不接受它：

```json
{
  "kind": "clarification",
  "text": "建议设计一位在庭院照顾病鼠的医师。",
  "choices": {
    "prompt": "希望采用哪种风格？",
    "options": [
      {"id": "friendly", "label": "友好医师", "text": "采用友好医师方案，继续完善。"},
      {"id": "mysterious", "label": "神秘访客", "text": "采用神秘访客方案，继续完善。"}
    ]
  }
}
```

一组 2—6 项，prompt 最长 200 字符，唯一 id 最长 40、label 最长 60、text 最长 800；拒绝未知字段、空白选项及命令参数。实际定义为模块 `answers.py`；任务接口返回可选 `Task.choices`，来源复验失败或取消后不返回可操作选项。

三种对话视图及本地管理器共用 `mountChat`，直接展示选择卡片。只允许创建者选择当前最新回答的选项；归档、他人会话、旧轮次及暂停状态不可操作。普通选项点击后把完整 follow-up text 填入输入框，保留已有草稿，可修改后再发送；不会批准批次或写游戏状态。玩家的 ask_kp 选项直接提交资料披露申请，ask_kp_change 提交独立创作申请，均须用户明确点击并绑定原问题；不授权修改。正文不重复 A/B/C 文本列表。

## 自定义嵌入

`pack.js` / `index.js` 导出 `mountChoices`，`pack.d.ts` / `index.d.ts` 提供 `ResponseChoices`、`ResponseOption` 类型。组件不依赖房间客户端，只构造 DOM 和调用选择回调，支持单独装配：

```js
import {mountChoices} from './ai-ui/pack.js';
const options = {onSelect: option => chat.setDraft(option.text), disabled: false};
const panel = mountChoices(container, task.choices, options);
panel.update(nextTask.choices, options);
// 卸载视图或身份变化时：
panel.destroy();
```

接入方决定如何保存原草稿，并沿用真实身份和原会话提交接口；不能把回调当作执行授权。组件使用 Shadow DOM，标签按文字输出，不执行模型 HTML；不传 onSelect 时只读。分发包含 `choices.js` 与 `choices.css`，见公共资源清单；Stumpsville 的固定网页构建图已同步。

重启宿主以加载新提示及包指南快照，刷新管理器／嵌入页，树桩镇网页模式需重新导出资源。离线测试验证契约、权限及显示链路；真实模型的简洁程度仍需实际使用中核对。

## 验收

阶段测试、失败复验和早期决策已移入[开发记录](../../history/2026-11-20-ai-development-records.md)。各阶段计数不相加为当前全量结果。

## 玩法术语与玩家申请

2026-11-19：管理员提示消费包作者 gameTerms，区分复活中的生命值、失能／死亡、归档及场景副作用；术语材料不是权限或执行证据。已明确意图不反复确认；真正语义分歧才用简短选项提问。PL 的 ask_kp 由服务端生成中性选项，用户点击后提交独立知识申请；模型不能选择未知资料或自行披露，完成状态来自真实宿主观察回执。

通用 mountChoices 仍只通知 onSelect；可用 hintText 自定义说明。玩家聊天对服务端 ask_kp 选项明确说明“点击即提交申请”，其他选项继续只填入输入框；已有申请禁用重复选项。

游戏术语只在 gameTerms 注入一次，不在 sources 重复；玩家回答含 ask_kp 时不再另外重复展示同名申请按钮。


PL strict-known 增加固定 `next:ask_kp_change` 选项，不接受模型自由正文。查询空结果使用“暂未获得与问题匹配的本人已知资料”，不推断无权限；本人装备按已授权字段格式化，不输出 raw JSON。错误与 UI 提示见[已知查询](ai-player-knowledge.md#查询未命中与服务阻断)，申请流程见[会话权限](ai-session-access.md#玩家创作与配置申请)。

## 来源审核与调试

KP 审核会话明确区分当前 KP 指令与被引用玩家材料；前者显示为用户发言，后者为可展开来源卡。定位、调试正文和模型标识见[来源审核与调试](ai-debug-review.md)。

## 配置数据增量输出

模型 draft 现在可在 changeSet 之外附加 dataEdits，使用 pack_read_config_data 发出的 editRef 精确追加或修改节点。服务端展开完整候选并继续原三检；changeSet.data 仍是整文件替换，不能当作隐式合并。输入格式、前置条件和限制见[精确增量](ai-data-query.md#活动配置数据的精确增量)。

## 消息时间与连接错误

每条用户发言显示真实发送时间，每条已生成回复显示保存时间；旧回复未记录时明确标示，不推算。失效引用保留已交付标签并灰显禁用，原文与资料详情权限分离，见[消息留存](ai-session-access.md#消息留存与时间)。

通用 HttpTransport 将网络、HTTP、JSON 解析和本地断线错误分别归类。错误仅含安全 code、status（HTTP 数值或 null）、operation、可用的 requestId/commandId 及 errorKind，不展示原始响应体。非 JSON 502 等仍保留 HTTP 状态；HTTP 200 的 rejected/unknown 业务回执保持原义，不自动重放。

## 生成中的变化

本轮回答与工具使用发送时快照，后续无关聊天不触发 SOURCE_STALE。真正依赖变化保留正文和候选并展示检查项，由 KP 选择继续讨论或按最新资料重新生成；成员撤权、会话删除及外发关闭仍阻止新输出。冻结、重启和审批边界统一见[发送快照与执行校验](ai-session-access.md#发送快照与执行校验)。

技术反馈保留真实错误原因。Lua 基础错误附 DSL 构造器语法；草稿修复不能降级为 plan 后误报可审核。NPC 扩展缺少固定判别字段时返回 `EXTENSION_MARKER_REQUIRED` 和精确 `/configurations/<id>/defaults/isNpc`，可在同一两次额度内修正；数值范围、权限和作者场景覆盖失败不因此放宽。

配置 B 层 `DATA_REFERENCE_CONFLICT` 也可在该额度内修订同一提案，反馈实际 JSON 路径；自环另指出记录业务键及零基下标。修复后完整重跑 A/B/C，持续失败不可批准，不能通过人工接受 C 评估跳过 B。

批次纠错目录只附本次行动 Schema；KP 外发允许时另附发送快照中相关规则及声明依赖源码（最多16KiB）。技术反馈不含测试预期答案，不能保证模型语义或正文始终正确。真实失败及复核边界见[指令可靠性验收](../../../engineering/acceptance/ai-command-reliability/README.md)。

## 压缩与来源评估反馈

过程卡新增“压缩上下文并保留可追溯原文”。每个摘要分组的 COMPRESSION_INVALID、COMPRESSION_PROVENANCE_INVALID、COMPRESSION_RESULT_LIMIT 会尝试一次纠正；持续失败、COMPRESSION_NOT_REDUCED、COMPRESSION_LIMIT 或 CONTEXT_LIMIT_EXCEEDED 明确结束本次生成，保留原始会话与压缩档案，用户可缩小当前请求后重试。工具文本裁剪可能无需摘要调用；同一任务中的后续摘要替换单个检查点。KP 诊断另区分裁剪／摘要及其字节、调用、耗时和失败；正常 PL 输出不包含这些内部记录。仅明确的 PROVIDER_CONTEXT_OVERFLOW 可在实际缩小输入后自动恢复一次，普通参数错误与输出截断不会触发此恢复；持续失败提示缩小需求。完整策略见[语义压缩](ai-session-access.md#语义压缩与原文定位)。

独立包资料产生可审核候选时显示来源评估，并由 KP 明确接受后执行。`CONSULTATION_REVIEW_REQUIRED` 提示回到裁决卡核对本次来源风险；不要重新询问用户已经确认的创作参数，也不要把缺少批准描述为模型无法创建配置。协议和技术拒绝边界见[裁决说明](ai-rulings.md#独立来源风险评估)。
