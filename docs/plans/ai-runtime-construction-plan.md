# 房间 AI 模块实施与验收计划

- 文档类型：计划
- 状态：进行中
- 创建日期：2026-11-12
- 最后更新：2026-11-13
- 关联文档：[设计正文](ai-runtime-design.md)、[计划索引](README.md)、[文档维护标准](../standards/document-maintenance.md)

2026-11-13：用户明确要求立即实现独立管理器和嵌入组件，Stumpsville 仅计划。新增交付与 AM-0—AM-4 验收见[当前管理器文档](../current/engineering/ai-manager.md)；树桩镇的具体依赖、阶段与门槛统一见[接入计划](stumpsville-ai-integration.md)。本文件保留原 AI-0—AI-6 的范围与人工试玩待办，不将包侧适配标记为已完成。

## 1. 交付目标与本次状态

用户已确认按阶段实施。AI-0—AI-2 已完成；T01—T09 连同既有宿主共 229 项通过；AI-3 的 173 项模拟及受影响回归通过，并已在用户提供测试凭据后完成真实 DeepSeek 联调；AI-4 的 46 项和 AI-5 的 8 项 HTTP/真实 Edge 验收已通过；AI-6 工程试点及最终回归已完成，真实 KP 试玩反馈待补。实际能力见[工程说明](../current/engineering/ai-runtime.md)。真实服务、模拟服务与人工试玩分别记录，不互相替代。

首版完整交付为 DeepSeek/自定义兼容服务、独立 A/B/C 工具、房间上下文与记忆、手动/自动需求、KP 审批及原子加载。flow 生成、实例迁移、跨包侧存档发布、向量检索和其他协议适配器不进入首版。规范与默认值以[设计正文](ai-runtime-design.md)为唯一来源，本文件只维护施工和验收。

## 2. 工作包、依赖与退出条件

工程侧负责执行器、接口和存储；包作者负责 Schema、条款约束、场景/指标；AI 接入开发负责调用与编排；KP/规则设计者参与风险与体验验收。具体分工见[设计第 7.5 节](ai-runtime-design.md#75-开发主责与交付边界)。

以下路径均为实施目标；新增路径尚不存在，不提前写入实际目录。路径缩写仅用于本计划：

| 缩写 | 路径及实施影响 |
| --- | --- |
| AI | engineering/ai/src/onlinecoc_ai/：新增独立 Python 包 |
| AT | engineering/ai/tests/：新增测试及 fixtures/pack/ 技术试点包 |
| HOST | engineering/backend/src/onlinecoc/：宿主接口、模型、执行与恢复 |
| CT | engineering/contracts/：新增 ai.json，修改 models.json/operations.json/messages.json |
| UI/SDK | engineering/test-console/、engineering/client-sdk/client.js |
| 启动/依赖 | engineering/backend/scripts/run.py、engineering/backend/pyproject.toml、requirements-runtime.lock、dependency-manifest.json；补齐安装入口的运行依赖 |
| 验收产物 | engineering/acceptance/ai-runtime/：拟新增可重放结果；临时存档放隔离输出目录，不用真实游玩存档 |

### AI-0：契约与最小试点

- [x] **AI-0.1｜工程＋包作者**：在 CT/ai.json 定义 Profile、PackContract、ContextSnapshot、Request、Proposal、ChangeSet、Report、PreparedBundle、Approval、Publication；未知字段拒绝、版本显式、工具权限与错误码有定义。
- [x] **AI-0.2｜工程**：AI/contracts.py 实现加载/校验和规范化摘要；定义合法/非法模型夹具及摘要向量。同内容摘要稳定，改变任一审核相关字段必须改变相应摘要。
- [x] **AI-0.3｜包作者**：AT/fixtures/pack/ 提供最小道具加成规则、A Schema/样例、B 正反例、C 对照场景/指标及人工清单；清楚声明试验规则，不冒充已有包规则。

**已验收（2026-11-12）**：三个工具输入输出及材料责任边界已落入契约；T01 的 64 项测试通过，见[AI-0 机器结果](../../engineering/acceptance/ai-runtime/ai-0.json)。本阶段未请求模型、未加载到游戏。

### AI-1：A/B/C 与共同沙箱

依赖 AI-0；各工作项可独立开发，但共用契约。

- [x] **AI-1.1｜工程**：AI/pack.py、validation/base.py 实现文件映射、路径/配额检查、完整包合并和真实 stage/模型加载，保留未修改规则。
- [x] **AI-1.2｜工程**：AI/sandbox.py 与 HOST/lua_runtime.py 共用受限 worker。检查与正式运行都执行相同权限/资源策略；生成源码在 inspect 前即进入隔离。
- [x] **AI-1.3｜工程＋包作者**：validation/rules.py 实现首批 checker 注册表、参数 Schema、条款定位、约束/旧实例/旧 flow 影响检查。未知 checker 和缺必需材料不放行。
- [x] **AI-1.4｜工程＋规则设计者**：validation/gameplay.py 实现场景执行、可枚举概率和可重放采样、基线/候选比较与覆盖报告；场景主体包括实际玩家身份和负权限案例。
- [x] **AI-1.5｜工程**：AI/cli.py 提供 check-base/check-rules/assess；JSON 输出与面板/模型共用报告，不额外维护一套 CLI 算法。

**退出条件**：T02—T05 通过；无模型时完成有效人工变更的 A/B/C。受限执行未验收只能交付静态/受信模板演示，不能据此开放任意 AI Lua。

**已验收（2026-11-12）**：T01—T05 共 128 项通过；宿主 74 项回归通过。见[AI-1 机器结果](../../engineering/acceptance/ai-runtime/ai-1.json)、[宿主回归](../../engineering/acceptance/ai-runtime/ai-1-host.json)及[精确概率/权限/资源耗尽报告](../../engineering/acceptance/ai-runtime/ai-1-gameplay.json)。正式运行与检查已共用受限 worker；当前交付为离线工具，尚未开放模型生成或发布。非 Windows 执行限制和真实玩法体验未验收。

### AI-2：提案、审批与主机发布

依赖 AI-0/1；这是接入模型之前必须完成的人工闭环。

- [x] **AI-2.1｜工程**：AI/repository.py、proposals.py 实现独立 FileDataStore、任务/提案修订、PreparedBundle 与不可伪造的受信服务登记；服务端生成权威 ID、摘要和版本。
- [x] **AI-2.2｜工程**：HOST 新增 publication.py、room_migrations.py；修改 model.py、contracts.py、host.py 及 CT。实现 Room 1→2、aiControl、approve/revoke/apply；检查执行快照同样兼容 schemaVersion=2。
- [x] **AI-2.3｜工程**：批准时将工件仅暂存到 Room.artifacts，并复制配置变更、基线与必要报告证据到审批记录；发布只读取 Room，不依赖 AI 仓库。批准和发布各自是一个独立原子命令。
- [x] **AI-2.4｜工程**：实现 commandId 幂等、approvalId 单次消费、stale 检查和提交结果对账；处理提交后抛错，不错误写入“未提交”记录。
- [x] **AI-2.5｜工程**：HOST/assets.py、启动/恢复路径更新升级前备份、旧格式读取、新格式导出、恢复 scope 分叉/撤销旧批准、可选 AI 快照及引用完整性校验。

**退出条件**：T06—T09 通过；人工草稿“检查→批准→发布→重启查询”闭环成立，关闭独立 AI 仓库后已有批准仍可按有效性条件处理。

**已验收（2026-11-12）**：人工草稿→三检→KP 批准→原子加载→重启查询已成立。228 项完整回归＋1 项锁边界补验，共 229 项通过，见[AI-2 机器结果](../../engineering/acceptance/ai-runtime/ai-2.json)。覆盖同/异 commandId、单次消费、双 KP、提交前/后故障、证据改动、v1 单次升级和恢复分叉。可选 AI 历史恢复为待复核附件；持久记忆的来源复核在 AI-4。

### AI-3：服务商与任务编排

依赖 AI-2。不让真实模型掩盖基础发布问题。

- [x] **AI-3.1｜AI 接入开发**：providers/base.py、deepseek.py、compatible.py 定义统一能力和错误；本机 profile CLI、脱敏显示、最小探测及启动加载。HTTPX 从开发依赖转为显式运行依赖并更新锁/安装清单。
- [x] **AI-3.2｜AI 接入开发**：coordinator.py 实现有限工具循环、结构化输出、有限修复、取消/超时、队列/Token 预算及任务租约。相同来源修订去重，重试与预算预留幂等。
- [x] **AI-3.3｜工程**：在 run.py/cli.py/server.py 组合 AI 服务及生命周期；HTTP 层不承载业务判断，AI 网络等待不占房间写锁；关闭 AI 保持既有启动与动作可用。
- [x] **AI-3.4｜AI 接入开发**：提供模拟服务和真实 DeepSeek 联调入口；记录 profile/model/能力、脱敏请求摘要、用量与结果，凭据不得入测试证据。

**退出条件**：T10/T11 通过，模型输出只进入提案。无密钥可完成模拟验收，但真实探测、生成和工具调用未完成时不能标记“真实 DeepSeek 已接入”。

**验收通过（2026-11-12）**：173 项检查/服务商/编排及受影响宿主回归通过；配置 CLI、可选启动、凭据引用、有限队列/预算/取消/重试和独立仓库已实现，见[AI-3 模拟结果](../../engineering/acceptance/ai-runtime/ai-3.json)。补充[真实 DeepSeek 联调](../../engineering/acceptance/ai-runtime/deepseek-live.json)通过：deepseek-flash 完成 JSON/工具探测、两个只读工具调用、实际 demo 提案生成与 A/B/C，未批准或发布。联调暴露完整 ChangeSet 结构提示不足，已改为提供实际 Schema 及字段错误路径，[49 项回归](../../engineering/acceptance/ai-runtime/deepseek-regression.json)通过。最终通过运行共 4 次模型请求、9,507 token；此前失败尝试单独保留，不混入成功用量。模型只开放两个读取工具，其余能力通过最终草稿后共用三检；授权房间事实外发在 AI-4。

### AI-4：授权上下文与持久记忆

依赖 AI-2/3。

- [x] **AI-4.1｜工程**：AI/context.py 与 HOST 受控端口实现一致快照、worldDigest、来源版本及外发范围；区分游戏状态变化与 AI/审计/已读变化。
- [x] **AI-4.2｜工程**：memory.py 实现事件索引、关键词检索、摘要来源、KP 确认/撤销、有效期和派生失效；来源读取和发送前后重新验证权限。
- [x] **AI-4.3｜工程＋KP**：验证房间 scope、不同 KP/玩家权限、编辑/撤回、恢复分叉及保留/备份行为；设置页显示外发范围与额度。

**退出条件**：T12/T13 通过；两份 demo 不串记忆；模型摘要不能替代主机事实；旧消息/撤权数据不能继续用于新任务。

**核心验收通过（2026-11-12）**：T12/T13 及审批/备份/编排回归共 46 项通过，见[AI-4 结果](../../engineering/acceptance/ai-runtime/ai-4.json)。两个真实 demo 目录、私聊边界、外发开关、来源变化、记忆确认/撤销/派生失效、重启/恢复均已验证；AI-4.3 的外发/额度设置面板随 AI-5 真实 Edge 验收完成。

### AI-5：需求入口与 KP 审核界面

依赖 AI-2—4。

- [x] **AI-5.1｜工程**：HOST 新增 ai_api.py，提供 AI commands/tasks/proposals/drafts；capabilities 声明 AI 协议版本、启用状态和限额，CT 与 SDK 同步封套、错误、分页及上传限额。Room 审批发布继续走已有 /commands 和回执。
- [x] **AI-5.2｜前端/工程**：UI 增加队列、方案/差异、A/B/C 报告、影响对象、风险确认及批准/加载结果；默认显示规则解释，源码可展开。手改提案产生新修订。
- [x] **AI-5.3｜工程＋KP**：接入玩家显式需求、KP 转发与可开关的指定频道前缀监听；排除 AI 消息，处理来源去重、编辑、撤回和限流。
- [x] **AI-5.4｜前端/工程**：玩家仅获自身请求的脱敏状态；KP 通过当前权限看提案。若首版开放 LAN，补 engineering/network-lan/ 路由和鉴权验收后再声明支持，不能借用未知直通路由。

**退出条件**：T14/T15 通过；自动/手动入口均需要 KP 批准，人工编辑后旧报告不能发布。

**已验收（2026-11-12）**：8 项 HTTP/实际 Edge 集成测试通过，覆盖玩家请求/脱敏、KP 转发、前缀监听/编辑/撤回、三检、逐项理由、手改修订、取消撤批、加载、回执、断线和退出清理。见[AI-5 结果](../../engineering/acceptance/ai-runtime/ai-5.json)及[浏览器记录](../../engineering/acceptance/ai-runtime/ai-5-browser.json)。首版本机，未开放 LAN。

### AI-6：实际包试点与阶段交付

依赖 AI-0—5。

- [x] **AI-6.1｜包作者**：选一个实际配置包，补约束/场景/指标及上下文映射。涉及包侧独立状态时先映射为主机版本化事实，或缩小试点，不绕过单主机发布边界。
- [ ] **AI-6.2｜KP＋规则设计者**：执行第 4 节完整脚本，评审工具证据与试玩反馈；至少包含一次修改提案、并发过期、拒绝和发布恢复。
- [x] **AI-6.3｜工程**：整理机器结果、版本、固定输入与故障证据；运行受影响宿主/聊天/规则/备份回归，核对依赖安装和禁用 AI 行为。
- [x] **AI-6.4｜工程＋文档维护者**：将已验证能力同步到当前文档、SDK/API 与目录索引，未完成项目保留在计划，释放施工登记。

**退出条件**：T16 及全部必需组通过。发布版本必须列出真实服务验证、实际包覆盖和待支持项；不以演示截图替代回执/断言。

**工程验收通过（2026-11-12）**：实际宿主 demo 直接复用原有 Lua；试点限定 demo.skill 新建初值，A/B/C、降低提案、并发过期、拒绝、发布回包丢失及恢复均有断言。完整回归 302 项、后续复验 45/23 项通过，原阶段去重 304 项；补充联调修复回归 49 项后，四次运行去重 305 项、执行 419 次；CLI 三检和 pip check 通过。见[验收摘要](../../engineering/acceptance/ai-runtime/acceptance-summary.json)。有限次数道具闭环使用技术夹具和实际 Edge；demo 试点不冒充完整 COC 或其他包覆盖。

**AI-6.2 尚未完成的部分**：真实 KP 试玩与主观规则体验反馈。自动脚本不能代替这一项；本次真实模型生成仍停在待审核提案。LAN AI 路由、非 Windows 资源隔离、flow 生成和实例迁移仍不在当前交付能力中。

<a id="3-核心验收矩阵"></a>

<a id="31-服务商与编排"></a>

<a id="32-abc-三类工具"></a>

<a id="33-上下文记忆与角色权限"></a>

<a id="34-审批并发恢复与界面"></a>

## 3. 验收矩阵与证据

下表保留验收规格，完成结果以上方各阶段及机器报告为准。测试使用隔离存档，不访问真实游玩目录；每组包含表列正反例，不能只测一条成功路径。

| 组 | 场景与必须满足的断言 | 对应测试落点（拟定） |
| --- | --- | --- |
| T01 契约 | 未知字段/版本/修改摘要字段；同内容可重现、Schema 与模型约束一致 | AT/test_contracts.py |
| T02 加载 | 错 JSON/重复键/非有限数/超限、路径与链接逃逸、文件冲突、缺依赖/环/非法 API；完整合并保留旧规则 | AT/test_base.py |
| T03 隔离 | inspect 顶层死循环、内存/输出爆增、文件/网络/宿主桥访问、子进程退出；检查和正式执行均无凭据/存档写入 | AT/test_sandbox.py、HOST 对应运行测试 |
| T04 规则 | 数值/代价/互斥/唯一资源/引用/权限；缺契约或 checker；改校验基准；旧实例数值不覆盖，旧 flow 依赖不漏查 | AT/test_pack_rules.py |
| T05 游戏性 | 同初态、角色权限及独立随机；d100 60→75 精确为 +15 个百分点/+25%；零基线、随机调用变化、循环收益、覆盖不足；主机无效果/骰点污染 | AT/test_gameplay.py |
| T06 审批 | 玩家/模型越权、伪造 pass、批准后改内容/报告/基线/条款、过期/撤权；新修订必须重新审核 | backend/tests/test_ai_approval.py |
| T07 发布 | 两 KP 并发、重复 commandId/approvalId、同 ID 不同 payload；一批准只生效一次，失败无半配置 | backend/tests/test_ai_publication.py |
| T08 故障 | 批准提交后、发布提交前/后回包前、AI 对账前故障；区分未知与拒绝，回执和发布状态一致，无重复效果 | backend/tests/test_ai_recovery.py |
| T09 迁移恢复 | v1→v2 恰一次、未知版本、旧程序边界、备份缺引用、恢复 scope 分叉/旧批准撤销、无 AI 备份仍保留已发布游戏 | backend/tests/test_ai_backup.py |
| T10 服务商 | 自定义能力不全、401/403/429/5xx/断流、空白或截断 JSON、伪造工具、非法 URL/头；有限重试、脱敏 | AT/test_providers.py＋真实联调记录 |
| T11 编排 | 队列/预算/回合/期限上限、取消、重复请求、重启 interrupted；用阻塞模拟服务证明普通动作无需等模型返回 | AT/test_coordinator.py |
| T12 上下文 | 两份 demo、公开/KP/分组/他人私聊、外发设置、超限、生成期间撤权、注入文本；无越权读取/授权升级 | AT/test_context.py |
| T13 记忆 | 玩家声称不是事实、确认后重启、来源编辑/撤回/撤权级联失效、秘密摘要、来源丢失及恢复分叉 | AT/test_memory.py |
| T14 界面入口 | 自动关闭时不调用模型、手动/自动去重、不自循环、编辑/撤回、手改提案、逐项风险理由、stale/断线状态、玩家脱敏 | UI 与 API 集成测试 |
| T15 接口一致 | CLI/面板/AI 工具结果除 ID/时间外一致；无模型仍能检查；CSRF/Origin/上传限额/权限；可选 LAN 路由 | AT/test_entrypoints.py、backend/network-lan 集成测试 |
| T16 实际闭环 | 第 4 节脚本、旧公开规则/聊天/流程/备份回归、AI 禁用、真实试点包边界和试玩反馈 | engineering/acceptance/ai-runtime/ |

每份机器结果保存：测试 ID、代码/宿主协议/契约/检查器版本、fixture/candidate/baseline 摘要、随机算法/种子/样本数或精确枚举标记、结论及证据路径。报告不含密钥、未授权会话或真实玩家私密资料。

故障注入沿用 FileDataStore 的提交边界；尤其验证 after_publish 抛错时已落盘状态仍被认定为提交。Windows 进程终止验收不宣称物理断电恢复。C 必需度量不完整必须阻断，主观风险与未必需覆盖项以 KP 理由记录，不写“已证明平衡”。

## 4. 完整体验验收脚本

1. 玩家提出“制作有限次使用、提高检定成功率的道具”，KP 转发并说明目标。
2. AI 读取授权角色、物品和包条款；材料不足时停在 needs_input，不能编造持有物。
3. 生成解释、替代方案、完整包差异与配置，A/B/C 分别给出加载、规则和影响证据；不发放物品、不投真实骰。
4. KP 要求降低收益，形成新修订；旧报告与批准失效，重新检查。
5. 在审核期间执行一次相关游戏动作，发布须返回 stale；刷新快照与评估后重新批准。
6. 批准只暂存候选，加载一次后回执、规则和配置一致；模拟回包丢失并恢复，不能重复发布。
7. KP 另行创建/发放实例，玩家调用新动作；旧规则与允许保留的旧 flow 正常执行。
8. 重启、备份到新目录恢复；已发布版本保留，旧批准不能在新 scope 消费，记忆重新校验来源。
9. 回退作为新提案检查已有引用，不撤销已发生的骰点、伤害或库存。
10. 用自动入口再走一遍，并在另一个不同秘密内容的房间验证隔离；记录 KP/玩家的体验判断。

<a id="5-文档与交付要求"></a>

## 5. 实施顺序、发布门槛与文档维护

第一施工切片固定为 AI-0.1—0.3：只创建机器契约、校验封装和最小包夹具，完成 T01 后进入 AI-1。首次可审核演示为 AI-2 结束的人工闭环；首次模型闭环为 AI-3/4/5 完成。真实包、真实 DeepSeek 与全部首版门槛未完成前保持阶段性说明。

执行者按任务登记精确路径、测试输出与运行目录，读取各级 AGENTS.md；不创建新 worktree 或切分支来绕过共享路径占用。包作者补包材料不能擅自修改工程。需要新增依赖、Schema 或包检查插件时在对应工作项记录理由与兼容影响。

每阶段交付必须有：改动文件与契约版本、验收组及可重放证据、未覆盖项、恢复/停用办法、文档同步。阶段更新按维护标准核对工程文档与实际实现；只有完成的能力进入 docs/current/。精简后的正文保留有效设计与责任分工，原长篇枚举由本表覆盖，不另存一份失效正文。

尚待项目选择的试点包、预算/保留期和游戏阈值见[设计第 11 节](ai-runtime-design.md#11-实施分期试点与待确认项)。它们不阻塞契约、通用工具和技术夹具的实现；不能据此宣称实际玩法已经适配。用户已授权逐阶段实施；已验收项按本计划勾选，其他项不得提前标为完成。
