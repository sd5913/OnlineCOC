# AI 回答、语义引用与选择项

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-16
- 最后更新：2026-11-18
- 关联文档：[嵌入接口](ai-pack-embedding.md)、[数据查询](ai-data-query.md)、[权限与批次](ai-session-access.md)、[包侧写入责任](../../plans/Issues/issue-010-ai-package-mutations.md)

## 基础错误修正与用户决策

新服务配置、示例和当前本机配置的 `limits.maxRepairAttempts` 默认 5（可设 0—10），指首次输出之外最多 5 次自动修正，全部错误时最多 6 份输出。管理面板提供独立设置；已有其他自定义 profile 保留其显式值。修正次数与 `maxToolRounds` 独立，仍受任务超时、取消、可选用量上限和权限复验约束。

JSON 解析、非对象输出、缺失／错误字段、非法引用和选项会反馈错误代码与结构路径，要求模型返回完整正确对象。只接受完整 JSON 或唯一完整 JSON 围栏，不从任意解释文字中猜测提取。已生成配置的 A 检查若发现基础 Schema／Lua／引用错误，修订同一提案重检；不生成多份待批配置，不自动忽略 B/C 或风险决定。

需要决定意图、风格、冲突目标或重大取舍时，模型返回 `clarification` 和简短问题，可附结构化选项；任务进入 `needs_input` 等待用户。兼容旧模型的 plan+choices 也进入 needs_input。未知偏好不能作为格式错误反复重试，已确认方向不能再次追问。

`MODEL_OUTPUT_INVALID` 表示基础输出修正次数耗尽；诊断展开可查看 `MODEL_JSON_INVALID`、`MODEL_FIELDS_INVALID`、`MODEL_CHOICES_INVALID`、`REFERENCE_UNVERIFIED` 或 A 检查代码等具体原因及修正次数。只记录结构路径，不记录原异常文本。空响应、协议错误或输出截断也使用这项修正额度，但耗尽后保留对应 `PROVIDER_*` 原因；认证、连接、权限、基线或任务超时不包装成格式错误。本次没有读取用户截图对应旧任务的原始诊断，因此不能据截图断定那次错误的唯一原因。

## JSON 请求与服务商错误

2026-11-18 修复严格玩家提示词遗漏 `JSON` 关键词导致 DeepSeek 拒绝请求的问题。玩家提示明确要求 JSON 对象；兼容发送层在 system/user 消息都没有 `json`（忽略大小写）时，增加一条格式指令，不修改调用方历史或玩家知识权限。依据 [DeepSeek JSON 模式说明](https://api-docs.deepseek.com/guides/json_mode)，仅提供对象示例不足以满足服务商的提示词检查。

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

`UNSUPPORTED_CAPABILITY` 保留给返回了不支持的思考内容、JSON／工具能力探测未通过等能力检查，不再笼统代表 HTTP 参数错误。已获得 HTTP 200 的正文仍可能格式无效，继续沿用前述默认 5 次修复流程。历史失败记录不自动重跑或改写。

聊天区提供对应中文说明；KP 的诊断保留错误代码和可选 `httpStatus`，不保存服务商错误正文、响应头、密钥或请求内容。PL 仍不接收诊断详情。更新代码后需重启承载 AI 的房间宿主；刷新管理器和嵌入页面，已打包网页需重新构建资源。

## 回答与引用

系统提示与树桩镇指南默认要求：约 150—300 汉字（不计引用标记／选择项），先一句结论，设计或多项事实接 2—4 条 Markdown 列表，段间空行，每段至多两句，属性合为一行；用户要求详细方案时展开。正文使用生命、护甲、位置等语义名称，诊断独立展示；仅影响下一步的限制简短说明一次。已确认的创建方向直接生成可审核批次，不再反复确认。可查询的数据由模型查询，不转问用户。此处是生成约束，不保证任意模型固定字数，也不截断重要内容；旧回复不会被重写。

模型查询结果在不改变原 EvidencePage 与证据摘要的前提下，额外提供 `citation: {token,label}`。实体／配置 token 使用真实业务 ID 与修订，聊天／事件／裁决使用对应证据引用；不把 `ref.id` 当作业务 ID。无对应语义引用的规则、频道等类型仍使用可读名称。

模型在正文中原样使用收到的 `[[entity:真实ID@修订]]` 等 token。服务端只接受本次已提供的引用或经复验的历史引用，伪造／不完整标记进入修复流程，仍不合法则拒绝回答。前端通过现有授权解析接口呈现有底色的名称标签；引用过期或不可见时显示对应状态。模型不会自选显示名称冒充其他对象。行内代码中单独出现的合法引用也会渲染为标签；完整代码块保留原文。

旧回复中的普通 ID 不作猜测性替换；只有真实绑定的引用可转换。模板没有可读名称时使用原 ID。受信包适配器可提供 `reference_label(kind,key,fallback)` 返回 1—160 字符的显示名；当前用于配置模板，先完成可见性过滤，再调用映射，失败沿用原名。树桩镇为 NPC、角色、地点及场景模板提供语义名称。这个接口不增加可读权限。

## 引用详情与稳定渲染

对话历史和 `mountMarkdown` 的引用标签支持点击／Enter／空格打开二级详情面板；Escape、关闭按钮或点击遮罩关闭并恢复焦点。面板显示授权名称、类型、修订、可见性及数据字段，生命／力量等常见字段有中文名称，其余保留真实字段名；原始数据默认折叠。只构造文本 DOM，不执行数据中的 HTML。编辑器仍保持引用的整块插入、删除行为。

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

`container` 默认为 body 的父节点，可传 HTMLElement／ShadowRoot；返回 open(token, anchor?)、close、refresh、destroy。解析回调须返回与 token 相同 kind/id/revision 的授权对象及 value。自定义接入负责及时通知身份变化；不要使用不复验权限的全局数据缓存。资源清单和树桩镇构建图包含 `reference-details.js/css`。

## 结构化选择项

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

三种对话视图及本地管理器共用 `mountChat`，直接展示选择卡片。只允许创建者选择当前最新回答的选项；归档、他人会话、旧轮次及暂停状态不可操作。点击把完整 follow-up text 填入输入框，保留已有草稿，可修改后再发送；不会提交请求、批准批次或写游戏状态。正文不重复 A/B/C 文本列表。

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

2026-11-18 服务商兼容修复：**215 项离线测试通过**（核心 66 项、相关回归 149 项），包含严格 PL 的真实 HTTP 适配层模拟、知识查询／读取／回答、400 错误不重试、状态脱敏及 KP／PL 浏览器显示。真实 DeepSeek 共 4 次合成请求：玩家主路径和旧提示词兜底均通过；额外通用探针返回过 1 次无效 JSON，1 次纠正后通过。已确认用量合计 1704 tokens，另一次失败探针的用量未保留，不将其计作零。见[逐项验收](../../../engineering/acceptance/ai-runtime/capability-fix-results.json)与[真实 API 记录](../../../engineering/acceptance/ai-runtime/capability-fix-live.json)。未发送房间数据或修改正式存档；未重新构建 Stumpsville 分发包。

2026-11-16：按测试 ID 去重 86 项模块测试、10 组树桩镇验收通过。覆盖服务端引用／选项约束、权限撤销、三种视图、独立装配、真实引用解析、草稿保留、无自动提交、CSP 样式及两名 WebRTC 玩家。均为隔离存档／离线服务；[结果和源码摘要](../../../engineering/acceptance/ai-runtime/ai-responses-results.json)，[界面截图](../../../engineering/acceptance/ai-runtime/answer-choices.png)。

同日引用详情补验：65 项去重模块测试、11 组树桩镇验收通过，覆盖精确修订、失权清空、异步乱序、键盘／移动端、轮询及状态更新无标签闪回、先构造后插入节点、三种嵌入和打包网页双玩家。见[本轮结果及源码摘要](../../../engineering/acceptance/ai-runtime/reference-details-results.json)、[详情面板截图](../../../engineering/acceptance/ai-runtime/reference-details.png)。仍为隔离存档与离线模型，生成篇幅是提示约束，未宣称真实模型稳定达标。
