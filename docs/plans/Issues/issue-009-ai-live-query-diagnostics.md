# ISSUE-009：真实 AI 查询失败与异常诊断缺口

- 文档类型：计划
- 状态：进行中
- 创建日期：2026-11-15
- 最后更新：2026-11-15
- 关联文档：[问题索引](README.md)、[AI查询契约](../../current/engineering/ai-data-query.md)、[树桩镇接入](../../../rulepacks/stumpsville/docs/current/integrations.md)、[真实验证记录](../../../rulepacks/stumpsville/tests/ai-demand-results.json)
- 问题状态：工程缺陷已修复，真实查询链路通过；完整答案的规则语义仍待验收
- 影响版本：树桩镇0.9.0、当前AI Runtime、deepseek-flash
- 优先级：高

## 现象与预期

2026-11-15用户明确授权一次真实服务隔离验证。使用全新样例房间、当前启用的DeepSeek服务配置和最新包指南，提问“查看所有房间信息并梳理”。已收到并结算一次服务商响应（3381输入、92输出、共3473 tokens），但任务终态为failed/AI_TASK_FAILED，无最终回答，未记录任何dataQueries。不能判为真实模型按需查询通过。

用户此前房间的空列表回复是另一份证据：外发全开、有30实体及13配置，但当次模型未实际查询，仅将按需模式的空roomFacts解释为无资料，后台仍载旧指南。包侧已更新指南并提示旧快照重启。此次隔离验证使用新快照后出现的AI_TASK_FAILED尚不能由旧指南问题解释，也不能断言两者根因相同。

预期：模型搜索和读取授权资料后给出有依据的回复；模型调用错误应保留足以定位的脱敏阶段/异常信息，而非只出现泛化错误。

## 复现与证据

1. 正常本机权限、已明确授权的真实服务调用；仅样例数据，未加载真实房间。
2. 执行包内 [verify_ai_demand.py](../../../rulepacks/stumpsville/tests/verify_ai_demand.py) 的显式 `--live` 模式。原服务商配置不改，隔离副本限制6次工具回合、无自动修复/传输重试、2200输出tokens、240秒任务期限。
3. 样例房间准备两名玩家，打开三类外发范围，发起一次上述自然语言咨询。
4. 检查[精选结果](../../../rulepacks/stumpsville/tests/ai-demand-results.json)。忽略目录 `rulepacks/stumpsville/tests/output/ai-demand-e86927a2/` 保存测试存档，AI任务已有responseDigest与用量，facts没有dataQueries。现有host.log未记录内部异常栈；原始模型响应未持久化，无法从摘要还原其工具名称或参数。

该次失败后的首轮排查没有追加真实调用。独立本地复验确认：HTTP空query搜索entity/config/channel/event/ruling/memory/rule正常，首批数量分别为12/12/1/9/2/0/12；entity/config存在后续页。回环模拟模型先搜索entity和config（query为空、limit=12），再回答，任务达到review_ready。证据目录分别为 `output/ai-demand-replay-682c19f0/` 和 `output/ai-demand-tools-*/`。这只证明对应本地链路可用，不代表复现了真实响应的未知参数。后续授权真实复验见下文。

## 原因与候选处理

原3473 tokens案例的内部异常仍无法还原。可确认服务商响应已被适配器接受并结算，随后任务失败；不能确定那次失败发生在权限复验、工具执行、输出处理还是关闭服务商连接。不能用“无dataQueries”断言模型没有尝试调用工具，失败的工具尚未形成证明记录。

原工程 [coordinator.py](../../../engineering/ai/src/onlinecoc_ai/coordinator.py) 的 `_loop` 将无code异常统一保存为AI_TASK_FAILED，缺少阶段和脱敏异常类型/栈。用户授权后已补足诊断；不修改数据权限或默认外发范围。离线已确认并修复两类处理缺陷：连接清理异常覆盖主错误/成功结果，以及可恢复的只读查询错误直接终止咨询。由于上次真实响应未保留，尚不能将这两类缺陷认定为那次调用的确切根因。

## 实施步骤与验收条件

首轮修复按当时授权仅使用离线回放。之后用户明确允许必要的 DeepSeek API 测试，追加隔离样例实测。目前实施状态如下：

1. 已实现 `TaskTrace`：记录阶段、回合、已知工具名、参数键白名单及摘要、完成/拒绝/失败状态、异常类型和模块代码位置。日志不记录异常消息、绝对路径、密钥、对话或参数正文；正常任务也保留工具执行摘要。诊断仅向KP返回，原生对话可展开查看。
2. 已明确按需 `initialFacts=not-loaded` 与系统工具使用指引。允许模型在原额度内修正 `INPUT_INVALID/QUERY_INPUT_LIMIT/QUERY_RESULT_LIMIT/SOURCE_STALE/NOT_VISIBLE`，仅在未新附加查询证明时恢复；权限变化、未知工具及复验失败仍拒绝。未开放任意工具或发布权限。
3. 已修复清理异常覆盖主错误、成功回答或取消状态的问题。98项引擎/界面回归通过，另通过树桩镇查询范围5组与双网页地图/AI5组。离线使用实际DeepSeek适配器和MockTransport跑通搜索→读取→样例事实回复，覆盖参数修正、脱敏和KP/PL诊断隔离。见[验收摘要](../../../engineering/acceptance/ai-runtime/issue-009-results.json)。
4. 追加修复：模型列表结果增加当前授权页的实际数量，避免将 limit 当作条数；明确 ref.id 是证明引用，读取频道详情后才使用 data.channelId。原始查询摘要、权限与 HTTP 契约不变。
5. 工具轮次用完后的原有最后一次模型请求不再提供工具，要求汇总现有证据并声明未读范围，不增加请求上限。只读梳理使用 plan 回答，不应生成配置草稿。
6. 新真实复验定位到 `proposal_validate → check_base` 的 KeyError：合法配置省略可选 behaviors 时，校验器仍按必填字段读取。现按空引用集合处理；替换配置和未改动配置均有回归，缺失规则引用仍拒绝。此次新故障有具体诊断，不等于已还原最初那次失败的根因。

## 追加真实复验与结论（2026-11-15）

全部使用新生成的样例房间和隔离 Profile，原服务商、模型和凭据引用沿用现有配置。每次咨询最多6轮工具及7次模型请求，240秒，无传输重试或格式修复。预算与输出调整仅写隔离副本。此前3473 tokens失败记录保留不覆盖。

| 记录 | 实测结果 |
| --- | --- |
| [初次复验](../../../rulepacks/stumpsville/tests/ai-demand-retest-20261115.json) | 查询成功；保守预算预留超过10万上限，未生成回答 |
| [20万预算复验](../../../rulepacks/stumpsville/tests/ai-demand-retest-budget200k-20261115.json) | 2200输出上限触发截断；其中一次响应未结算实际用量 |
| [8192输出复验](../../../rulepacks/stumpsville/tests/ai-demand-retest-output8192-20261115.json) | 自动链路检查通过，但人工发现50/14错误计数及误用频道引用，不算答案验收通过 |
| [计数及引用修复复验](../../../rulepacks/stumpsville/tests/ai-demand-retest-final-20261115.json) | 查询成功，但模型继续查询直到工具轮次超限 |
| [收尾机制复验](../../../rulepacks/stumpsville/tests/ai-demand-retest-bounded-20261115.json) | 查询成功，模型返回草稿时诊断定位到上述可选字段 KeyError |
| [校验修复后复验](../../../rulepacks/stumpsville/tests/ai-demand-retest-validated-20261115.json) | 7次请求、91819 tokens，11次资料查询成功；一次 SOURCE_STALE 拒绝后仍完成回答，无草稿、无异常 |

最终样例的29个实体、13项配置与1个频道及业务ID general核对一致，回答说明了未读内容；最后一轮收尾生效。但“地图是单链”“零标记意味着玩家未获知线索”等解释没有读取相应规则作为依据，不能视为完整事实审核通过。原始资料查询能力已验证，完整答案质量仍需改进，本问题保留进行中。不得把脚本 passed（仅检查链路、详情读取和角色名）当作所有叙述准确。

[本轮汇总](../../../engineering/acceptance/ai-runtime/issue-009-live-results.json)和[JUnit](../../../engineering/acceptance/ai-runtime/issue-009-live-regression.xml)记录87项回归全部通过，另4项CLI限制检查通过；与前阶段98项测试存在重叠，不累加。6次隔离咨询共33次服务请求，已确认393620 tokens，另有1次截断响应实际用量未知；保留的37296预算预留量不是服务商实际账单。原始3473 tokens另计。未修改真实存档、正式服务配置或云端服务；本轮停止追加API调用。

剩余验收：梳理答案应区分原始数值、已读取规则确认的含义和待验证建议；未读规则时不得将字段名称或零值断言为地图拓扑、剧情或个人认知。后续改进以这些具体反例验证，不以扩大工具配额代替质量检查。

不在范围内：修改真实存档、扩大外发权限、发布游戏配置、改云端服务。

## 处理记录

- 2026-11-15：一次授权真实调用未通过；本地查询与模拟工具流程成功。保留失败记录，不宣称重启即可保证修复，不追加真实调用。
- 2026-11-15：用户授权工程AI模块修复；完成上述脱敏诊断与错误处理，98项工程测试和10组配置包回归通过。真实结果仍保留失败状态，问题保持进行中。
- 2026-11-15：用户允许必要的DeepSeek实测；完成6次隔离咨询和新增修复，87项回归通过。真实查询链路及实际计数通过，发现并保留答案语义限制，原失败记录不改写。
