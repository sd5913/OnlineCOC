# AI 阶段开发与实验记录归档

- 文档类型：历史
- 状态：已归档
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 原路径：下列各节注明的 AI 当前文档和计划中的阶段记录
- 原状态：有效／进行中
- 归档日期：2026-11-20
- 归档原因：将阶段流水和重复测试统计从现行正文移出，保留决策、失败与复验背景
- 替代文档：[当前 AI 实现](../current/engineering/ai-runtime.md)、[后续验收](../plans/ai-runtime-construction-plan.md)
- 关联文档：[历史索引](README.md)

以下版本、能力和限制均按原记录日期理解，不能作为当前接口依据。

## 运行时阶段交付

原位置：`docs/current/engineering/ai-runtime.md`。以下仅保留当时记录；当前能力以原位置的替代正文为准。

## 当前阶段

2026-11-19 宿主增加核心规则／数据、物品配置及删除配置的明确高危批准，发布前验证完整候选依赖；KP 全房间读取通过单独授权范围提供。接口、回执、权限边界与本轮测试见[高危发布与读取](../current/engineering/high-risk-publication.md)。

2026-11-17 的个人知识接入已完成，严格玩家辅助只消费宿主可复验的固定资料及显式持续授权，见[已知资料实现](../current/engineering/ai-player-knowledge.md)。本轮384项AI模块测试已通过；下述早期阶段数字保留为交付背景，不累加为本轮数量。

AI-0—AI-5 已完成本地实现与验收；AI-6 实际 demo 包的工程试点、故障/恢复脚本和最终回归已完成，真实 KP 试玩反馈待补。完整回归 **302 项通过**，末轮权限/记忆/界面复验分别 **45 项、23 项通过**；三次运行按测试 ID 去重共 **304 项**，无失败/跳过。见[交付验收摘要](../../engineering/acceptance/ai-runtime/acceptance-summary.json)、[完整回归](../../engineering/acceptance/ai-runtime/ai-6.json)、[权限补验](../../engineering/acceptance/ai-runtime/ai-6-privacy.json)及[最终上下文/浏览器复验](../../engineering/acceptance/ai-runtime/ai-6-final-context.json)。

已通过实际命令行 A/B/C 与依赖 pip check。阶段记录保留：[AI-0](../../engineering/acceptance/ai-runtime/ai-0.json)、[AI-1](../../engineering/acceptance/ai-runtime/ai-1.json)、[AI-2](../../engineering/acceptance/ai-runtime/ai-2.json)、[AI-3](../../engineering/acceptance/ai-runtime/ai-3.json)、[AI-4](../../engineering/acceptance/ai-runtime/ai-4.json)、[AI-5](../../engineering/acceptance/ai-runtime/ai-5.json)；各阶段不相加为新增测试。

2026-11-12 补充真实 DeepSeek 联调：`deepseek-flash` 的 JSON/工具探测、房间与包契约读取、提案生成和 A/B/C 均通过，见[真实联调报告](../../engineering/acceptance/ai-runtime/deepseek-live.json)。本轮针对实际机器契约提示与修复路径补强后，[49 项离线回归](../../engineering/acceptance/ai-runtime/deepseek-regression.json)通过；与上述三次运行去重共 305 项。隔离房间中的提案停在待 KP 审核，未批准或发布。密钥仅用于测试进程，未写入配置或证据；持久服务配置、房间调用与自动接收仍默认关闭。

2026-11-13 增加独立 AI 管理器、Windows 加密凭据、房间会话、嵌入组件及无界面客户端。当前使用/API 和本轮验收见[管理器与开发接入](../current/engineering/ai-manager.md)；上述 305 项属于此前交付记录，不代表新增管理功能的测试数。Stumpsville 已有包侧接入；2026-11-16 的受限 NPC 模板／规则发布与统一裁决见[现行说明](../current/engineering/ai-rulings.md)。2026-11-14 通用管理器新增房间文件夹对话、版本化数据引用与补全，并优化会话提交/读取；测量、验收及包侧交互原型入口见[管理器说明](../current/engineering/ai-manager.md)。



## Demo 试点

原位置：`docs/current/engineering/ai-runtime.md`。以下仅保留当时记录；当前能力以原位置的替代正文为准。

## 实际 demo 试点

[宿主 demo 的 AI 材料](../../engineering/rulepacks/demo/ai/rules.md)直接读取既有 10 个 Lua 文件与 environment.json，完整保留原公开规则和等待流程。试点范围为 demo.skill 新建技能默认值 0—30；不改旧技能实例、不导入包侧独立状态。

[实际包报告](../../engineering/acceptance/ai-runtime/ai-6-demo-report.json)及 [CLI 报告](../../engineering/acceptance/ai-runtime/ai-6-cli.json)已验证新技能初值 0→15 时成功率 0%→15%（精确 d100 枚举，零基线没有相对增幅），已有 value=60 的技能保持 60%，其他玩家越权调用失败。机器闭环包括降低提案到 10、旧批准撤销、审核期间主机变化导致过期、拒绝、发布后回包丢失及恢复新作用域。示例和启动步骤见[模块入口](../../engineering/ai/README.md)。

真实 DeepSeek 联调在独立 demo 房间中完成同一新技能初值 15 的提案生成；模型主动调用两个只读工具，随后 A/B/C 均 pass，C 仍标记 high 风险，需 KP 判断。新技能成功率 0%→15%，已有技能仍为 60%；游戏数据、批准数和发布数均未改变。本轮通过 Coordinator 直连真实服务，浏览器证据仍为离线服务验收。

这不是完整 COC 的平衡结论。有限次数道具由技术夹具和浏览器闭环覆盖；实际包试点限定技能初值。真实 KP 试玩反馈、LAN AI 路由及非 Windows 资源验收仍未完成。



## 任务诊断演进

原位置：`docs/current/engineering/ai-runtime.md`。以下仅保留当时记录；当前能力以原位置的替代正文为准。

### 任务诊断与查询恢复（2026-11-15）

新任务在AI历史中保存可选 `diagnostics`：当前阶段、模型回合、最多24条工具尝试与最多3项异常。记录已知工具名、参数键白名单、参数摘要、所选公开类型、引用数量及完成/拒绝/失败状态，不保存关键词、引用内容、原始模型响应、异常消息、请求头或局部变量。异常位置只记录工程模块、函数和行号，不输出本机绝对路径。失败会同时写入脱敏日志；旧任务没有诊断时不回填或迁移。

诊断随 `ai/tasks` 和会话详情的KP授权投影返回，PL不获取；原生对话显示稳定错误码、资料工具完成次数和可展开的阶段/异常位置。明确区分“模型未完成查询”“查询参数被拒绝”和“查询成功后回答失败”，成功查询依据仍由 `facts.dataQueries` 保存并复验，诊断不是授权或发布依据。

清理模型连接的异常仅记录为次要诊断，不能覆盖原错误、已保存回答或用户取消。诊断保存失败也不能替换原任务结果。按需模式的系统提示明确标注初始空上下文未预载；合法只读工具遇到可恢复的参数、结果大小或过期引用错误时，返回脱敏错误让模型在原有工具/回合/预算上限内修正，权限变化和已附加来源的复验失败仍终止任务。

模型列表结果提供当前授权页的实际数量，提示明确区分查询上限与结果条数，并要求解析频道详情后再使用业务 ID。工具回合达到 Profile 上限后，原有最后一次模型请求不再提供工具，要求只汇总已取得的证据并明确未读详情、未访问分页和未解决错误；不增加请求额度。若服务商仍返回工具调用则拒绝。该收尾机制仍受总期限、消息大小和预算限制，不能保证任意大房间一次完整阅读。

只读查询、概览及未要求修改配置的建议，提示要求使用 `kind=plan`，不生成配置草稿。A 校验允许合法配置省略可选 `behaviors`，按空规则引用集合校验；已有规则引用仍须存在于候选工件中，未放宽三检或发布条件。

用户授权后的真实DeepSeek复验已跑通分页搜索、详情读取和最终回答，最终样例29实体、13配置及频道general核对一致；本轮87项回归通过，见[汇总](../../engineering/acceptance/ai-runtime/issue-009-live-results.json)。真实复验发现并修复了可选behaviors字段的KeyError。最初3473 tokens失败只有响应摘要，仍无法确认其确切根因。完整答案仍有未读规则却推断地图及剧情语义的问题；[ISSUE-009](../plans/Issues/issue-009-ai-live-query-diagnostics.md)保留该验收缺口，链路通过不代表所有推论准确。

生成提示从 `ChangeSet` 机器契约提取实际 Schema 及依赖定义，明确完整配置值、字符串修订与未改文件的合并方式。结构化草稿不合法时，默认最多 5 次自动修正，反馈稳定错误码、字段路径和约束；校验标准不因模型输出而放宽。

每日累计限额默认关闭（Profile.limits.dailyTokenBudget=null），正整数显式启用；不限额时仍保留完整记账。每次网络尝试在独立仓库持久预留额度，成功按用量结算；失败或中断保留预留量，避免把可能计费的调用当作免费。使用 UTF-8 字节作保守输入估算；每日额度是按房间＋服务配置＋UTC日期计算的本地约束，不是服务商账单保证。授权只读 `GET /api/v1/ai/usage` 区分确认消耗、调用中预留和待核实预留；KP可查整个房间，PL只查本人原始需求，接口/界面和升级步骤见[每日限额与统计](../current/engineering/ai-manager.md#每日限额与用量统计)。任务重启变为 interrupted，不自动重发。取消/关闭会终止网络等待并等待本地检查收尾；模型等待及三检均不占房间写锁。

启动可选参数为 `serve --ai-config <配置文件> --ai-pack <带AI契约的包目录>`；不提供时不创建 AI 服务。配置和房间开关均默认关闭；房间开关由 KP 在操作台设置，本机服务商配置由独立管理器或管理员 CLI 维护，下一次调用前按配置文件摘要刷新；当前任务仍绑定原 Profile 修订。队列、用量和错误存在独立 AI 仓库；模型输出进入方案／配置草稿／管理员执行批次，不能获得 KP 审核权限。



## 本地性能测量

原位置：`docs/current/engineering/ai-manager.md`。以下仅保留当时记录；当前能力以原位置的替代正文为准。

## 本地延迟与测量

此次定位到创建会话会为 pending、业务状态和回执重复校验/提交整个 AI 仓库；会话详情还会遍历无关请求及其提案。已将自包含会话命令合并为一次持久事务，并在任务查询前按本会话 requestIds 过滤。没有关闭最终校验或磁盘同步。

前端创建成功直接使用 committed 回执渲染，不串行重读列表和详情；服务商和 KP 审核按需挂载，关闭审核即销毁。只轮询选中会话，生成中约 0.9—1.2 秒、空闲约 12 秒，后台标签不查询；不为全部房间后台加载历史。搜索仅覆盖房间名称及已加载会话，不是跨账号全文搜索。

同机隔离存档，251 条请求（250 条无关历史＋1 条当前需求），每项 7 次样本：

| 服务层调用 | 优化前中位数 | 优化后中位数 |
| --- | --- | --- |
| 新建会话 | 158.58 ms | 57.53 ms |
| 当前会话详情 | 6.76 ms | 3.16 ms |
| 会话列表 | 1.08 ms | 1.14 ms |

创建约减少 64%，详情约减少 53%；列表没有明显改善。脚本新建 Host＋Runtime 为 724 ms，计时从 Python 导入后开始；它不代表整个服务启动。完整管理器进程到 HTTP 就绪的单样本为 1572.88 ms（约 1.57 秒），见[启动测量](../../engineering/acceptance/ai-runtime/chat-startup.json)，包含解释器与导入，不含浏览器启动、旧存档和模型请求。没有充分证据宣称冷启动本身获得同等幅度优化。

最终真实 Edge 浏览器中的新建会话单样本 50.24 ms，包含点击、HTTP 代理、宿主提交与界面更新；该样本为空的隔离测试房间，不可与 250 条历史的服务层样本混为同一负载。生成采用离线确定性服务商。DeepSeek 网络推理、三检执行、历史规模扩大后的完整仓库校验仍可能耗时；本轮没有改变为流式输出，也没有宣称缩短真实模型生成时间。

证据：[优化前](../../engineering/acceptance/ai-runtime/chat-performance-before.json)、[优化后](../../engineering/acceptance/ai-runtime/chat-performance-after.json)、[浏览器](../../engineering/acceptance/ai-runtime/chat-browser.json)。复测用 [benchmark_local.py](../../engineering/ai/scripts/benchmark_local.py) 指向一个尚不存在的临时目录；不打开现有游戏存档、不调用模型。小样本是当前机器定位结果，不是高并发或长期负载保证。



## 管理器验收

原位置：`docs/current/engineering/ai-manager.md`。以下仅保留当时记录；当前能力以原位置的替代正文为准。

## 验收与参考

2026-11-17 聊天模板完成三轮迭代：第一轮 12 项既有回归通过；第二轮 5 项新交互测试通过；第三轮补充发送切换竞态，最终按测试 ID 去重 **27 项通过（含 6 项新增交互测试）**。末轮初跑 25 项通过、2 项旧定位断言失败；限定补全候选定位后，两项复测通过。见[逐轮结果与源码摘要](../../engineering/acceptance/ai-runtime/chat-polish-results.json)。覆盖本机管理器、三种嵌入形态、390 px 窄容器/移动视口、引用详情与原子编辑、权限和归档删除；使用真实 Edge、隔离宿主及离线模型，无真实 API 消耗。前端优化不代表推理延迟优化。

2026-11-16：日限额默认关闭、授权用量查询与可嵌入统计通过122项模块测试和9组树桩镇接入验收。证据见[用量验收](../../engineering/acceptance/ai-runtime/usage-results.json)；覆盖额度重新启用、失败/取消/重启保留、旧记录、分页、原玩家归属、HTTP越权、真实Edge管理器及双网页玩家。全部为离线模型与隔离存档。

2026-11-15：格式化回答、独立会话管理与设置已完成；51 项模块回归和 7 组树桩镇接入验收通过，细节及当前入口见[嵌入指南](../current/engineering/ai-pack-embedding.md#验收)。结果、复验范围与源码摘要见[本轮记录](../../engineering/acceptance/ai-runtime/rendering-sessions.json)。以下性能样本和阶段数字仍保留其原测量日期。

2026-11-14 新增配置包专用入口、无界面工具和三种视图/HTML 入口，并对三条房间页面开放同源 iframe。生命周期、分发与验收见[嵌入说明](../current/engineering/ai-pack-embedding.md)，证据见[嵌入阶段](../../engineering/acceptance/ai-runtime/embeds.json)。

2026-11-14 追加指令名称补全与语义引用编辑。最终 9 项专项全部通过，结果见[引用交互验收](../../engineering/acceptance/ai-runtime/reference-ui.json)及[原型截图](../../engineering/acceptance/ai-runtime/reference-ui-semantic.png)；覆盖原子增删/替换、撤销重做、剪贴板、光标中段补全、IME 组合事件边界、名称安全渲染、过期/迟到响应及原管理器生成审核流程。本次没有改动后端存储协议，也没有重新执行全部宿主测试；下述 337 项属于前一轮回归。

2026-11-14 完整 AI＋宿主回归 335 项通过，末轮引用/事务/HTTP/会话/真实管理器浏览器专项 22 项通过；原操作台及真实启动复验 3 项通过；按测试 ID 去重共 337 项，无失败/跳过。按测试 ID 去重的最终结果见[本轮验收摘要](../../engineering/acceptance/ai-runtime/chat.json)，各轮不相加当作新增测试。

本轮覆盖真实 Windows DPAPI、管理器 CLI、房间文件夹、快捷引用与预览、版本及外发边界、提交/回执单次落盘和失败回滚、KP 生成→三检→批准→加载、归档重开、PL 隔离、锁定及原型角色切换。界面截图见[管理器](../../engineering/acceptance/ai-runtime/chat-room.png)和[配置包原型](../../engineering/acceptance/ai-runtime/chat-pack-prototype.png)。

此前管理器 AM-0—AM-4 的 331 项去重验收及组件双挂载/迟到响应证据见[历史阶段记录](../../engineering/acceptance/ai-runtime/manager.json)。此次浏览器使用离线确定性服务商，没有再次调用真实 DeepSeek；既有真实服务结果见 [deepseek-live.json](../../engineering/acceptance/ai-runtime/deepseek-live.json)。配置包原型不写入树桩镇，真实 KP 试玩、完整本地化、非 Windows 保险库及跨设备完整配置发布未由此次测试证明。

管理功能组织参考 [CC Switch 官方项目](https://github.com/farion1231/cc-switch)，查阅于 2026-11-13；2026-11-14 对话与房间分组参考 [ChatGPT Projects 官方说明](https://help.openai.com/en/articles/10169521-projects-in-chatgpt)，借鉴侧栏分组和独立会话的组织思路，不复制其代码或资源，也不把 ChatGPT 项目的功能直接作为本模块承诺。

会话分级、玩家开关、批次动作／审批／原回执和删除语义统一维护于[会话权限与执行批次](../current/engineering/ai-session-access.md)。配置删除、高危审批与管理员全读采用新版公开契约；包侧跨账本写入仍需另行适配。

2026-11-16 验收：模块按测试 ID 去重 323 项、树桩镇 32 组通过，覆盖分级权限、直接排队、批次审批／恢复、归档／删除、双网页玩家及原生 KP。均使用隔离存档和离线服务，未调用真实模型或修改正式存档；[验收汇总](../../engineering/acceptance/ai-runtime/session-access-results.json)保存逐项结果、复测关系和源码摘要。

对话区现接入[语义引用与结构化选择](../current/engineering/ai-responses.md)：精简正文，工具诊断单独展示，普通选择项填写输入框后再发送；玩家明确点击资料／创作申请按钮则提交对应原问题。

输出修正次数默认 5，可在服务商编辑的调用限制中设置。运行时与配置自动批准分别配置；KP 的 AI 修改裁决队列统一处理批次与通过三检的配置。详细规则以[修改裁决](../current/engineering/ai-rulings.md)和[输出修正](../current/engineering/ai-responses.md#基础错误修正与用户决策)为准。

2026-11-17 对话布局参照 [ChatGPT 网页入口](https://chatgpt.com/) 的清晰正文、底部输入区和新对话引导；本项目保留房间身份、数据引用和 KP 审核入口，使用自己的组件实现。

2026-11-19：新增可独立挂载的 KP 服务／权限设置页、紧凑裁决详情弹窗；任务列表直接返回会话定位，恢复会话减少串行读取。接口、分发、iframe 限制与性能证据统一见[嵌入指南](../current/engineering/ai-pack-embedding.md#独立设置与紧凑裁决)。


2026-11-19：服务与权限面板及独立设置组件显式提供管理员全房间读取、AI 查询工具、运行时／配置写入、PL 使用／自愿申请、外发三范围及普通自动审批开关。高危修改固定要求人工核对完整候选和指纹，不能自动通过；具体默认值和申请流程以[会话权限](../current/engineering/ai-session-access.md)及[裁决契约](../current/engineering/ai-rulings.md)为准。

玩家创作申请与资料披露分别设开关；输入区可直接提交创作需求，KP 接收后打开私有审核会话，后续变更仍人工批准。详见[申请规则](../current/engineering/ai-session-access.md#玩家创作与配置申请)与[嵌入接口](../current/engineering/ai-pack-embedding.md#玩家创作申请接入)。



## 嵌入组件验收

原位置：`docs/current/engineering/ai-pack-embedding.md`。以下仅保留当时记录；当前能力以原位置的替代正文为准。

## 验收

2026-11-19 数据排版与角色分层更新通过 134 项相关测试，含真实 Edge 的预览／引用详情和既有三种嵌入回归；[结果与范围](../../engineering/acceptance/ai-runtime/data-presentation-results.json)。本次未重建树桩镇分发网页，也未实施包侧行动内容投影。

2026-11-17 聊天模板完成三轮迭代：第一轮 12 项既有回归通过；第二轮 5 项新交互测试通过；第三轮补充发送切换竞态，最终按测试 ID 去重 **27 项通过（含 6 项新增交互测试）**。末轮初跑 25 项通过、2 项旧定位断言失败；限定补全候选定位后，两项复测通过。见[逐轮结果与源码摘要](../../engineering/acceptance/ai-runtime/chat-polish-results.json)。覆盖本机管理器、三种嵌入形态、390 px 窄容器/移动视口、引用详情与原子编辑、权限和归档删除；使用真实 Edge、隔离宿主及离线模型，无真实 API 消耗。前端优化不代表推理延迟优化。

2026-11-16 的不限额与用量统计新增验收为122项模块测试及9组树桩镇接入，详见[用量结果](../../engineering/acceptance/ai-runtime/usage-results.json)及[界面截图](../../engineering/acceptance/ai-runtime/usage-panel.png)。以下为此前格式/会话阶段结果，不重复累加。

三种页面经真实 Edge＋隔离宿主验证，覆盖同源 iframe、折叠暂停／恢复、草稿保留、窄屏、组件共用客户端、迟到响应清理、幂等与越权拒绝；资源清单验证模块依赖闭合。2026-11-16 新增玩家直接排队、权限、执行批次和归档／删除验收，详见[会话权限](../current/engineering/ai-session-access.md)。

2026-11-15 格式与会话管理更新通过 **51 项模块回归、7 组树桩镇接入验收**；防重复提交的 4 项复验包含在 51 项内。证据见[结果与源码摘要](../../engineering/acceptance/ai-runtime/rendering-sessions.json)，截图见[格式渲染](../../engineering/acceptance/ai-runtime/markdown-embedded.png)、[会话管理](../../engineering/acceptance/ai-runtime/session-management.png)。覆盖真实 Edge、本地 KP、两名 WebRTC 网页玩家、旧咨询队列和沙箱表单；全部使用隔离存档/模拟服务，没有调用真实 DeepSeek、修改正式存档或新增云端部署。此前三种视图 26 项验收保留于[原记录](../../engineering/acceptance/ai-runtime/embeds.json)。



## 个人知识阶段验收

原位置：`docs/current/engineering/ai-player-knowledge.md`。以下仅保留当时记录；当前能力以原位置的替代正文为准。

## 分阶段验收

2026-11-19 已知资料排版、旧回复只读转换及 KP／PL 显示分层通过 134 项相关测试，详见[显示验收](../current/engineering/ai-responses.md#验收)。仅改变已授权数据的表现，不放宽严格 evidence 门槛；包侧内容投影缺口单列 ISSUE。

2026-11-18 玩家 JSON 模式兼容修复已通过实际 DeepSeek 请求及 215 项相关测试，见[本轮记录](../../engineering/acceptance/ai-runtime/capability-fix-results.json)。下面的 384 项为此前个人知识阶段，不与本轮数字相加。

2026-11-17 按 A0—A3 与工程侧 K0—K5 对接。最终 **384 项 AI 测试去重全部通过**：全量原始记录为 383 通过、1 项测试操作遗漏；补齐 KP 转交步骤后 2 项操作台补验通过。原始失败保留，不重复累加。明细见[汇总](../../engineering/acceptance/ai-runtime/known-results.json)、[全量](../../engineering/acceptance/ai-runtime/known-full.xml)、[补验](../../engineering/acceptance/ai-runtime/known-ui-retest.xml)。阶段专项如下：

| 阶段 | 交付及证据 |
| --- | --- |
| A0 | 严格输出、引用编码、能力／外发拒绝、批量复验；最初 18 项见 [A0](../../engineering/acceptance/ai-runtime/known-a0.xml)，后续扩展纳入运行时专项 |
| A1 | 主体隔离、固定观察、无完整指南、在途撤权、旧回复复验、第二包证词及转交 KP；[85 项运行时专项](../../engineering/acceptance/ai-runtime/known-runtime-final.xml)全部通过 |
| A2 | 单独／对话／折叠嵌入、原子引用、原观察详情、撤权清空、会话权限；初次 [5 项界面验收](../../engineering/acceptance/ai-runtime/known-a2.xml)通过，扩展的 17 项组件／操作台浏览器测试均在最终全量及补验中通过 |
| A3 | [Stumpsville 12 组](../../rulepacks/stumpsville/tests/strict-known-results.json)公开 HTTP／Edge 测试；原十地点／18 行动 [8 组回归](../../rulepacks/stumpsville/tests/scene-results.json)通过；不同玩法[证词示例](../../engineering/ai/examples/knowledge-investigation.py)不跟随未来改口 |

测试使用隔离存档、确定性模型及本机 HTTP。断言实际提供方输入和最终显示结果，包括模型夹带秘密的拒绝／重试，不以模型偶然未泄露代替权限验证。本轮未调用真实模型、修改正式房间或部署云端。



## 回答与显示验收

原位置：`docs/current/engineering/ai-responses.md`。以下仅保留当时记录；当前能力以原位置的替代正文为准。

## 验收

2026-11-19 数据显示修复：最终 **134 项去重测试通过**（最终核心／权限 71 项、相关回归 63 项），覆盖结构排版、旧回答复验后转换、撤权、三类会话展示、预览与详情、390 px 窄屏、三种嵌入及 HTTP。最初一项转义断言误把安全的转义子串当作失败，修正断言后全部通过，原始记录保留。[结果与源码摘要](../../engineering/acceptance/ai-runtime/data-presentation-results.json)、[PL 对话](../../engineering/acceptance/ai-runtime/data-presentation-chat.png)、[玩家详情](../../engineering/acceptance/ai-runtime/data-presentation-player.png)、[管理员技术详情](../../engineering/acceptance/ai-runtime/data-presentation-keeper.png)。使用隔离宿主和确定性服务，未调用真实 API、修改正式存档或重建 Stumpsville 分发包；该批次未覆盖包侧安全投影；后续 Stumpsville ISSUE-001 已补充行动菜单投影，当前状态以包侧集成文档为准。

2026-11-18 服务商兼容修复：**215 项离线测试通过**（核心 66 项、相关回归 149 项），包含严格 PL 的真实 HTTP 适配层模拟、知识查询／读取／回答、400 错误不重试、状态脱敏及 KP／PL 浏览器显示。真实 DeepSeek 共 4 次合成请求：玩家主路径和旧提示词兜底均通过；额外通用探针返回过 1 次无效 JSON，1 次纠正后通过。已确认用量合计 1704 tokens，另一次失败探针的用量未保留，不将其计作零。见[逐项验收](../../engineering/acceptance/ai-runtime/capability-fix-results.json)与[真实 API 记录](../../engineering/acceptance/ai-runtime/capability-fix-live.json)。未发送房间数据或修改正式存档；未重新构建 Stumpsville 分发包。

2026-11-16：按测试 ID 去重 86 项模块测试、10 组树桩镇验收通过。覆盖服务端引用／选项约束、权限撤销、三种视图、独立装配、真实引用解析、草稿保留、无自动提交、CSP 样式及两名 WebRTC 玩家。均为隔离存档／离线服务；[结果和源码摘要](../../engineering/acceptance/ai-runtime/ai-responses-results.json)，[界面截图](../../engineering/acceptance/ai-runtime/answer-choices.png)。

同日引用详情补验：65 项去重模块测试、11 组树桩镇验收通过，覆盖精确修订、失权清空、异步乱序、键盘／移动端、轮询及状态更新无标签闪回、先构造后插入节点、三种嵌入和打包网页双玩家。见[本轮结果及源码摘要](../../engineering/acceptance/ai-runtime/reference-details-results.json)、[详情面板截图](../../engineering/acceptance/ai-runtime/reference-details.png)。仍为隔离存档与离线模型，生成篇幅是提示约束，未宣称真实模型稳定达标。




## 来源审核验收

原位置：`docs/current/engineering/ai-debug-review.md`。以下仅保留当时记录；当前能力以原位置的替代正文为准。

## 验收

引擎薄路由、SDK 和 LAN 共 17 项通过，见[独立记录](../../engineering/acceptance/ai-debug-route/README.md)。其中 HTTP 使用 AI 端口替身；本模块另用真实 Application/宿主夹具检查权限、来源、审批、撤权与只读导出，使用真实 Edge 检查来源卡和导出行为。本轮按测试 ID 的最新结果去重 **220 项通过、0 失败、0 跳过**；首次失败、复验关系与源码摘要见[模块验收记录](../../engineering/acceptance/ai-runtime/review-debug-results.json)。模块未进行付费模型调用。配置包的完整离线/模型验收独立记录，不与模块计数相加。



## 原 ai-runtime-design.md

原位置：`docs/plans/ai-runtime-design.md`。以下仅保留当时记录；当前能力以原位置的替代正文为准。

# 房间 AI 接入与运行时配置设计

- 文档类型：计划
- 状态：进行中
- 创建日期：2026-11-12
- 最后更新：2026-11-13
- 关联文档：[实施与验收计划](../plans/ai-runtime-construction-plan.md)、[计划索引](../plans/README.md)、[项目概况](../current/design/project-overview.md)

2026-11-12：用户确认 A/B/C 的责任分工与交付方式，并要求精简和深化设计。本文保留已确认方向和首版方案。用户现已授权逐阶段实施：AI-0—AI-2 的契约、检查工具、共同执行器、人工提案、审批/发布与迁移恢复已完成，AI-3 服务商与编排已通过模拟及真实 DeepSeek 联调，AI-4 上下文/记忆与 AI-5 HTTP/SDK/KP 界面已验收，AI-6 实际 demo 工程试点与回归已完成；真实 KP 试玩反馈待补；实际能力见[工程说明](../current/engineering/ai-runtime.md)，任务及验收在实施计划维护。

2026-11-13：用户明确要求立即实现独立管理器和嵌入组件，Stumpsville 仅计划。新增交付与 AM-0—AM-4 验收见[当前管理器文档](../current/engineering/ai-manager.md)；树桩镇的具体依赖、阶段与门槛统一见[接入计划](../plans/stumpsville-ai-integration.md)。本文件保留原 AI-0—AI-6 的范围与人工试玩待办，不将包侧适配标记为已完成。

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

实施顺序固定为：契约/最小包 → A/B/C 与共同沙箱 → 审批发布 → 服务商/任务 → 记忆/入口/KP 界面 → 真实包试点。先人工草稿完成“检查—审批—加载”，再接模型，详见[实施计划](../plans/ai-runtime-construction-plan.md)。

当前采用的工程默认：文件存储、宿主内组合服务、首版本机、非流式结果、自动接收默认关闭、明确需求按钮/前缀优先、无实例迁移；自动监听排除 AI 自己消息，以来源 ID＋修订去重，编辑/撤回取消未发布任务。外部输入须先转成可确认文本，不扩展本轮为语音模块。

实施前需决定的仅保留：真实试点包及维护者、房间预算/保留期、包的游戏性阈值。可先用 engineering/ai/tests/fixtures/pack/ 的最小技术包推进；它不代表任何现有包已适配。更换试点不改变协议，阈值不得由通用平台猜测。

机器契约与 AI-0 源码已创建；其余候选路径在相应实施任务施工前登记，真正创建时同步实际目录。既有主机权威、配置与实例分离、旧流程版本固定等决策保留，重复风险说明与逐条测试已集中到实施计划。


## 原 ai-runtime-construction-plan.md

原位置：`docs/plans/ai-runtime-construction-plan.md`。以下仅保留当时记录；当前能力以原位置的替代正文为准。

# 房间 AI 模块实施与验收计划

- 文档类型：计划
- 状态：进行中
- 创建日期：2026-11-12
- 最后更新：2026-11-13
- 关联文档：[设计正文](../plans/ai-runtime-design.md)、[计划索引](../plans/README.md)、[文档维护标准](../standards/document-maintenance.md)

2026-11-13：用户明确要求立即实现独立管理器和嵌入组件，Stumpsville 仅计划。新增交付与 AM-0—AM-4 验收见[当前管理器文档](../current/engineering/ai-manager.md)；树桩镇的具体依赖、阶段与门槛统一见[接入计划](../plans/stumpsville-ai-integration.md)。本文件保留原 AI-0—AI-6 的范围与人工试玩待办，不将包侧适配标记为已完成。

## 1. 交付目标与本次状态

用户已确认按阶段实施。AI-0—AI-2 已完成；T01—T09 连同既有宿主共 229 项通过；AI-3 的 173 项模拟及受影响回归通过，并已在用户提供测试凭据后完成真实 DeepSeek 联调；AI-4 的 46 项和 AI-5 的 8 项 HTTP/真实 Edge 验收已通过；AI-6 工程试点及最终回归已完成，真实 KP 试玩反馈待补。实际能力见[工程说明](../current/engineering/ai-runtime.md)。真实服务、模拟服务与人工试玩分别记录，不互相替代。

首版完整交付为 DeepSeek/自定义兼容服务、独立 A/B/C 工具、房间上下文与记忆、手动/自动需求、KP 审批及原子加载。flow 生成、实例迁移、跨包侧存档发布、向量检索和其他协议适配器不进入首版。规范与默认值以[设计正文](../plans/ai-runtime-design.md)为唯一来源，本文件只维护施工和验收。

## 2. 工作包、依赖与退出条件

工程侧负责执行器、接口和存储；包作者负责 Schema、条款约束、场景/指标；AI 接入开发负责调用与编排；KP/规则设计者参与风险与体验验收。具体分工见[设计第 7.5 节](../plans/ai-runtime-design.md#75-开发主责与交付边界)。

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

尚待项目选择的试点包、预算/保留期和游戏阈值见[设计第 11 节](../plans/ai-runtime-design.md#11-实施分期试点与待确认项)。它们不阻塞契约、通用工具和技术夹具的实现；不能据此宣称实际玩法已经适配。用户已授权逐阶段实施；已验收项按本计划勾选，其他项不得提前标为完成。



## ISSUE-010 早期复评

原位置：`docs/plans/Issues/issue-010-ai-package-mutations.md`；其配置删除缺口已被 2026-11-19 实现替代。保留原分工背景，当前待办以原位置新正文为准。

# ISSUE-010：AI 修改的配置包事务与发布边界

- 文档类型：计划
- 状态：草案
- 创建日期：2026-11-16
- 最后更新：2026-11-17
- 关联文档：[当前会话与批次](../current/engineering/ai-session-access.md)、[问题索引](../plans/Issues/README.md)、[配置包接入](../current/engineering/ai-pack-embedding.md)

## 依据与范围

本轮代码核查：宿主已有 entity/action/session 等命令可经 AI 执行批次审批调用，但配置变更 ChangeSet 仅支持 add/replace；A/B/C 与 prepared bundle 不覆盖配置删除。树桩镇另有 package.json 中的发现、裁决、物品编号和游戏流程状态，通用 Host 命令不能代表包侧完整事务。本轮已接入受限 NPC 模板与规则的配置裁决；包侧独立事务仍不属于该范围。

因此“管理员可以增删查改所有信息”目前在公开引擎命令和会话层落地；配置删除和包侧独立状态写入尚未实现；统一裁决及通过三检后的可选自动配置发布已实现。此记录为接口／代码核查，未声称已经做了这些操作的真实游戏验收。

## 待实施设计

责任划分（2026-11-16 代码核查）：

| 需求 | 当前基础能力 | 主要后续负责方 |
| --- | --- | --- |
| 用现有 NPC 模板新增实例 | 管理员批次已有 `entity.create`；不要求配置扩展点 | 包作者确认实例字段和包侧联动；模型按目录提出批次，KP 批准 |
| 新增／修改配置模板或规则 | AI 已有整批裁决与发布；树桩镇提供 NPC 模板、action/calculation 的扩展材料 | 包作者定义扩展点、B 规则正反例、C 场景指标、发布／恢复接线；无需重做通用 A/B/C |
| 修改发现记录、剧情、包内裁决等独立状态 | 目前没有通用 package 目标及跨账本事务适配；Host 实体修改不能替代它 | AI／引擎先补注册、预检、版本与幂等回执／恢复契约，包作者再实现具体操作适配 |
| 删除配置 | 当前候选和验证链不覆盖完整删除依赖 | 引擎／AI 模块补基础模型与检查，包作者补依赖及游戏性验收 |

“没有配置扩展点”不能解释为“不能用已有模板新建实体”。树桩镇已有 `actor.reveal` 包侧手动操作，尚未装配为 AI 批次目标；公开 NPC 不自动生成玩家发现记录。也不能笼统称所有剧情标记不可写：`sv.scene.numbers` 是可写宿主实体字段，包流程另同步 sceneState、库存和门状态；裸 patch 不构成完整场景事务，部分值可能被后续同步覆盖。当前准确边界见[运行时写入目标](../current/engineering/ai-session-access.md#运行时写入目标与树桩镇限制)。此表描述分工与当前入口，不将后续支持写成已实现。

1. 引擎责任方扩展可校验的配置删除／引用依赖影响模型、prepared bundle、恢复与原回执；保留 A/B/C 和风险决策，不通过直接 configuration.remove 绕过。
2. AI 模块责任方提供包侧批次目标注册契约：固定 operation/schema、受信执行器、作用域、版本前置条件、幂等命令 ID、可查询回执；禁止模型选择文件路径或代码。
3. 配置包责任方将已有公开业务操作装配进该契约，定义玩家知识投影和配置草稿提审格式。树桩镇配置扩展已覆盖；后续注册包侧操作，不直接写 package.json。
4. 自动配置批准已由单独开关控制，默认关闭，要求 A/B/C 通过并记录策略风险接受。现行接口和限制见[修改裁决](../current/engineering/ai-rulings.md)。

## 临时用法与验收条件

玩家可以先要求 AI 代写说明／配置候选供 KP 审核；支持完整 AI 包契约的包继续走三检提案流程。树桩镇模板／规则候选经 KP 整批裁决加载；发现、场景等独立业务状态通过现有包操作处理。

后续验收须覆盖删除被引用配置的拒绝、包侧状态与宿主状态不一致时停止、审批期间版本变化、玩家拒绝任意写入、提交后回包丢失和重启恢复，不得重复执行。只有确认后的实现和证据进入当前工程文档。

## 工程复评（2026-11-17）

问题成立，现有边界描述准确；建议继续保留待实施，不重复建设已经落地的统一裁决。此次为代码与契约核查，未新增功能或真实游戏写入测试。

- [配置契约](../../engineering/contracts/ai.json)的 ConfigurationChange 仍仅允许 add/replace；[批次执行器](../../engineering/ai/src/onlinecoc_ai/batches.py)的 target 仍仅允许 host/ai。配置删除与 package 目标均不能作为当前能力提供。
- 建议调整后续职责：**包业务命令、版本和可查询回执属于引擎／包适配层的通用契约，独立于 AI 使用；AI 模块只把已注册操作装配到审批批次。** 这样手动界面、规则流程和 AI 使用同一条业务入口，关闭 AI 后仍可执行和对账。此前“AI 模块提供包侧目标”的表述应理解为 AI 批次接入，不让 AI 仓库成为包状态的权威事务账本。
- 当前 runtime 批次逐项执行，失败即停，可能部分完成或结果未知。后续包目标必须声明自身的提交边界：单个操作的原子性、跨宿主／包存储的一致性、整批审批分别说明。先实现固定命令 ID、持久执行意图、版本检查、原回执查询及重启对账；没有完整协议前，不承诺跨两份存储整批原子成功，也不自动重放未知结果。
- 配置删除建议单独排期。首版仅讨论依赖检查后明确无引用的删除；被实例、规则、流程或其他配置引用时拒绝并列出审核人有权查看的影响，不自动级联删除实例。旧工件、审计与原回执仍需可追溯。现有新增／替换及实例归档可继续使用，不能把归档实例称为删除配置。

优先顺序建议：先冻结通用包操作／回执契约，并选一个现有包操作试点；配置删除随后独立实现。ISSUE-011 的原生宿主披露操作可以先完成，不必等待所有包侧跨存储事务；涉及包独立状态的发现操作再遵守本 ISSUE 的提交约束。该顺序为评估建议，尚未取得新的实施结论。


## ai-data-query 补充阶段证据

原位置：`docs/current/engineering/ai-data-query.md`；当前行为见原位置替代正文。

2026-11-15经授权追加真实DeepSeek隔离验证，分页枚举、详情读取、实际数量与最终回答链路通过；同时保留未读规则却推断游戏含义的答案质量缺口。见[实测与87项回归汇总](../../engineering/acceptance/ai-runtime/issue-009-live-results.json)。未修改用户存档或部署公网，不能将链路通过等同于完整事实审核。

2026-11-15 验收汇总：全量运行后修正一项旧指令列表断言，最终受影响路径 67 项通过；按测试名称取最新结果去重，共 387 项通过、0 失败、0 跳过。另通过树桩镇资料链路 4 组及既有自动裁决/恢复 6 组验收。[汇总及源码摘要](../../engineering/acceptance/ai-runtime/data-results.json)保留了全量运行与复验的关系。

2026-11-19 实体标签与相关查询回归共 76 项去重通过（包含 15 项新增专项），覆盖检索、回退、外发过滤、玩家隔离、引用不变和分页复验，另验既有高危读取、知识与 AI 引用。见[验收说明与证据](../../engineering/acceptance/entity-search-label/README.md)。不与此前模块或引擎阶段数累加；真实模型效果由 Stumpsville 的独立实测记录维护。

## ai-pack-embedding 补充阶段证据

原位置：`docs/current/engineering/ai-pack-embedding.md`；当前行为见原位置替代正文。

2026-11-19 工作台验收：81 项按测试 ID 去重通过，包含42项会话／请求／裁决、25项权限／知识、14项浏览器检查；复测不累加。桌面与390px截图、初跑失败原因、请求并行屏障、源码摘要和包侧独立验收边界见[结果记录](../../engineering/acceptance/ai-runtime/workbench-results.json)。测试不调用真实模型、不改正式房间。

## ai-player-knowledge 补充阶段证据

原位置：`docs/current/engineering/ai-player-knowledge.md`；当前行为见原位置替代正文。

2026-11-19 本轮查询与创作申请验收：按测试 ID 取最新结果去重 **190 项通过，0 失败、0 跳过**。覆盖真实宿主权限、私有审核、普通自动审批拦截、重启和 Edge 嵌入界面；初跑问题、复验关系与源码摘要见[本轮结果](../../engineering/acceptance/ai-runtime/player-requests-results.json)。模块未调用付费 API、未修改正式房间；包侧隔离模型实测另行记录，不合并测试数。

## ai-rulings 补充阶段证据

原位置：`docs/current/engineering/ai-rulings.md`；当前行为见原位置替代正文。

2026-11-19 模块验收按测试 ID 取最新结果去重：281 项通过、0 失败、0 跳过。覆盖真实宿主执行、人工高危指纹、普通自动审批、个人披露、存量实体探针、容量边界和 Edge 嵌入界面；初跑失败与复验关系保存在[验收报告](../../engineering/acceptance/ai-runtime/policies-results.json)。模块测试使用隔离房间与离线服务；引擎和真实 DeepSeek 记录分别由报告中的关联验收维护，不将不同阶段次数相加。

## ai-session-access 补充阶段证据

原位置：`docs/current/engineering/ai-session-access.md`；当前行为见原位置替代正文。

2026-11-16 验收：模块按测试 ID 去重 323 项、树桩镇 32 组通过，覆盖分级权限、直接排队、批次审批／恢复、归档／删除、双网页玩家及原生 KP。均使用隔离存档和离线服务，未调用真实模型或修改正式存档；[验收汇总](../../engineering/acceptance/ai-runtime/session-access-results.json)保存逐项结果、复测关系和源码摘要。

2026-11-19 本轮查询与创作申请验收：按测试 ID 取最新结果去重 **190 项通过，0 失败、0 跳过**。覆盖真实宿主权限、私有审核、普通自动审批拦截、重启和 Edge 嵌入界面；初跑问题、复验关系与源码摘要见[本轮结果](../../engineering/acceptance/ai-runtime/player-requests-results.json)。模块未调用付费 API、未修改正式房间；包侧隔离模型实测另行记录，不合并测试数。

## 目录核对流水（截至 2026-11-20）

原位置：`docs/current/engineering/hierarchy.md` 的最近目录核对字段。以下是历次局部核对范围，不代表同日完成全仓库复验。

- 最近目录核对：2026-11-20（AI 重启、顶部调试弹窗、开发记录归档与引擎历史复验交付）；2026-11-19（来源调试13组、队列10组、精确增量115项、DeepSeek闭环及SV-ISSUE-003归档）；2026-11-19（AI来源审核、只读调试、模型身份、220项模块验收及引擎17项/包侧委托目录登记）；2026-11-19（个人已知目录、创作申请与嵌入入口、190项去重验收，以及包责任者委托登记的ISSUE-002／2份脚本）；2026-11-19（AI高危／权限／自愿披露、累计请求容量与批次输出修正、281项去重回归、引擎标签76项及3个真实模型用例、引擎／包侧委托目录登记）；2026-11-19（AI独立设置页、紧凑裁决、会话定位与81项回归；包工作台脚本由并行责任者确认后代登记）；2026-11-19（树桩镇集中开场/全局统计、可执行裁决、折叠回复与专项验收）；2026-11-19（Stumpsville 安全菜单、旧证据升级、52组验收、SV-ISSUE-001归档及开发参考拆分索引）；2026-11-19（AI 数据展示与引擎／包侧 ISSUE；并行施工者委托代登记的2份开发参考已核对文件存在）；2026-11-18（树桩镇3秒淡出、线索／结果通知及10组专项、12组回归）；2026-11-18（树桩镇行动未完成原因、处理指引及专项验收）；2026-11-18（AI 玩家 JSON 兼容、HTTP 错误分类和215项回归及4次合成API记录）；2026-11-18（树桩镇统一KP裁决队列、AI转交/回执恢复与9组隔离验收）；2026-11-17（树桩镇行动等待优化、检定动画及专项验收文件；并行AI模板施工者交付的测试和截图目录）；2026-11-17（树桩镇房间槽位管理、旧v3房间清理及6组槽位/6组面板验收）；2026-11-17（ISSUE-011首版完成：Room v4、知识服务、SDK/联网、176项工程及384项AI测试、两包与计划归档）；2026-11-17（AI A0—A3、Stumpsville个人知识、设计迁移及计划归档）；2026-11-17（ISSUE-011首版工程设计、接口基线及K0—K5/27项验收计划，未实施）；2026-11-17（新增 PL 已知信息设计细则，更新 AI 计划与 ISSUE-011，尚未实施）；2026-11-16（玩家知识职责评估、引擎 ISSUE-011 与 AI 消费侧计划，仅文档）；2026-11-16（AI 样式稳定、玩家个人场景知识及会话管理原型，55项模块／28组包侧验收）；2026-11-16（树桩镇PL角色/地图/聊天AI三栏、可拖动线索日志浮窗及5组布局验收）；2026-11-16（引用详情二级面板、稳定渲染、简洁分段与65项模块／11组树桩镇补验）；2026-11-16（AI语义回答、结构化选项、CSP样式与86项模块／10组树桩镇验收）；2026-11-16（AI会话分级、玩家直达、执行批次、删除与323项模块／32组包侧验收）；2026-11-16（AI默认不限额、授权用量统计与122项模块/9组树桩镇验收）；2026-11-15（AI格式渲染、可嵌入会话管理/设置、51项模块及7组树桩镇验收）；2026-11-15（树桩镇统一Python面板、Windows进程树托管、旧房间清理及32组/项验收）；2026-11-15（树桩镇对接AI查询计数/频道/末轮收尾、咨询解释边界及17组包侧离线回归）；2026-11-15（ISSUE-009：6次DeepSeek隔离实测、87项回归及答案语义验收缺口）；2026-11-15（ISSUE-009脱敏任务诊断、查询恢复、KP诊断视图及98项工程/10组包侧离线验收）；2026-11-15（ISSUE-009：一次授权DeepSeek查询失败及诊断缺口）；2026-11-15（树桩镇按需空上下文查询指南、旧快照检测与显式真实模型专项）；2026-11-15（树桩镇裁决满幅布局、顶栏折叠及AI查询外发/名称语义4组专项）；2026-11-15（树桩镇0.9.0当前格式、一次性存档转换与新版AI/网页接入；未新增持久迁移工具）；2026-11-15（AI四类查询、Room v3来源复验、包侧事件资料及组件验收）；2026-11-14（后端0.2.0/Room v3严格加载、历史格式快照、只读校验与请求/决定方案）；2026-11-14（新增ISSUE-007旧房间版本策略与ISSUE-008通用请求裁决设计）；2026-11-14（新增AI数据查询与聊天裁决资料草稿及计划索引）；2026-11-14（独立KP房间/裁决/地图页、PL角色发现及新版AI原生组件/引用接入）；2026-11-14（配置包工具、三种嵌入视图/HTML、同源iframe、清单及26项回归）；2026-11-14（指令名称补全、语义引用编辑器及9项专项验收）；2026-11-14（AI房间文件夹对话、短指令引用/补全、包侧交互原型、性能优化及337项去重验收）；2026-11-14（network-web 0.3.0 开房串、公开列表、三页、专项验收与部署）；2026-11-14（KP地图角色列表、网页AI咨询桥/公开SDK构建、两个AI双击入口与5组专项）；2026-11-14（树桩镇导出冲突修复、6组重复启动/缓存专项及用户缓存隔离核验）；2026-11-14（云端0.2.0/0.2.2部署、原账号/房间保留及树桩镇8组公网强制TURN验收）；2026-11-13（树桩镇网页启动诊断、6组专项和只读云端404核对）；2026-11-13（树桩镇0.8.0网页发行/双击入口、包服务与隔离存储桥、真实双浏览器18预设及文档）；2026-11-13（Stumpsville 网页联机调整规划与相关现状/索引同步）；2026-11-13（network-web 0.1.1 本机账密组件、专项测试与验收记录）；2026-11-13（network-web 全部源码、测试、部署、文档及精选验收记录）；2026-11-13（新增公网大厅与按需游戏页草稿、域名接入步骤和相关索引）；2026-11-13（公网 0.2 短房间码、本机宿主识别、双击入口与 54 项验收）；2026-11-13（树桩镇0.7.0 AI咨询/P2P基础接入、双击入口、专项测试及ISSUE-006）；2026-11-13（公网模块完整源码、浏览器、部署、46 项验收及玩家分发脚本）；2026-11-13（AI 独立管理器、加密凭据、会话/组件/API、Stumpsville 接入计划及验收）；2026-11-13（核对公网联机 tmp 接入资料区与本机 SSH 检查产物）；2026-11-13（新增公网联机模块目录与本地接入资料模板）；2026-11-13（树桩镇0.6.0一屏三栏、受限内容本地化及专项验收新增文件）；2026-11-12（DeepSeek 真实联调、49 项补验及累计去重 305 项）；2026-11-12（AI-6 实际 demo、CLI 与最终去重 304 项验收）；2026-11-12（AI-4 上下文/记忆 46 项与 AI-5 HTTP/Edge 8 项）；2026-11-12（AI-3 配置/服务商/编排及 173 项验收）；2026-11-12（AI-2 人工提案、发布/恢复与 229 项验收）；2026-11-12（拆分配置包实例统计与开发指南）；2026-11-12（AI-1 A/B/C、共同执行器与 128＋74 项验收）；2026-11-12（增核独立语音输入工程设计与施工计划）；2026-11-12（AI-0 契约、最小包与 64 项验收）；2026-11-12（增核 AI 语音输入识别调研文档）；2026-11-12（增核独立本地化 L10N-0 实际源码、构建与精选证据）；2026-11-12（增核独立本地化工程设计与施工计划文档）；2026-11-12（增核房间入口、服务编排与配置包职责方案）；2026-11-12（增核房间发现/P2P/配置包同步及云服务器调研文档）；2026-11-12（增核房间 AI 设计及实施验收计划）；2026-11-12（增核配置包本地化方案文档）；2026-11-12（增核stumpsville 0.4.1局域网启动窗口、入口和专项验收）；2026-11-10（本次增核stumpsville 0.4.0十地点预设自动裁决、场景状态和恢复验收；其他范围沿用下列日期）；2026-11-09（本次核对 Python 桌面管理器、LAN 模块及相关发布、测试、归档和文档；mini-detective-pack 核对仍为 2026-11-02，全工程目录核对仍为 2026-11-01）；同日增核调查型线上跑团对照包文档、Mausritter 独立核查、Stumpsville 导入计划与界面参考资源，及 stumpsville 新包的页面导航、组成树、十张界面设计板和0.1.0包侧实现、运行资源及验收文件（含Windows PowerShell 5.1真实启动入口修复）

## 2026-11-16 裁决与输出修正实验

原位置：`docs/plans/ai-rulings-experiments.md`。



2026-11-16 已完成隔离实验。真实服务使用当前配置的 deepseek-flash；测试代理只注入首次坏 JSON，后续均调用真实 API。所有正式存档和持久服务配置在实验过程中保持不变。

| 运行 | 实际结果 | 真实调用／确认 Token | 证据 |
| --- | --- | --- | --- |
| 首轮 | R9、R4、R5 通过；R6 连续结构错误耗尽修正，失败如实保留。反馈只有根路径，未保存错误候选，不能确认其唯一字段原因 | 13／162,441 | [首轮](../../rulepacks/stumpsville/tests/ai-rulings-live-results.json) |
| 模板复测 | R6 通过；一次注入响应错误、两次 RULE_INVALID 后在同一提案修正，三检及裁决加载成功 | 7／95,606 | [复测](../../rulepacks/stumpsville/tests/ai-rulings-live-retest-results.json) |
| 最后一轮 | 四项核心用例通过；R9 的 MODEL_JSON_INVALID 修正成功，R4 等待选择，R5 两次批准均 completed 且只产生一个实例，R6 三检／加载成功 | 10／111,484 | [最终样本](../../rulepacks/stumpsville/tests/ai-rulings-live-final-results.json) |

总计 **30 次真实调用、369,531 确认 Token**；三次本地故障注入不计服务商调用。没有再次申请正式房间数据或修改正式存档。最后一轮从提交到模型／校验结果约为 6.20、11.26、12.31、20.20 秒；这些是本机样本，不是性能保证。真实费用未查询服务商账单。

修复反馈现在包含约束说明，机器 Schema 明确 sources/data 文件名必须为不含目录的 basename，包指南提供可运行 Lua 示例。有效 HTTP 响应即使正文 JSON 错误也保留确认用量，由编排器统一修正，避免把已发生消耗丢进无法确认的预留。

人工质量核对：最后一轮的一句话请求已按一句话回答；配置正文仍会保留部分开发字段。R4 已返回结构化选项且未创建修改，但正文仍重复友好／敌对选项，并出现“选定风格与位置后”的多余措辞。**表达质量未完全通过**；后续改进项保留在[接入后续计划](../plans/stumpsville-ai-integration.md)，不能把自动流程通过写成任意回答都准确简洁。

离线／浏览器按测试 ID 去重 177 项通过，包侧 6＋11 组通过。回归清单、复测关系及最终源码摘要见 [统一验收结果](../../engineering/acceptance/ai-runtime/rulings-results.json)。自动通过不等于长期游戏性保证；真实回复的可读性需要审阅样本。权限、回执丢失和重启故障使用确定性离线实验；不以一次真实模型成功取代这些测试。


## 模型人工核验备注（2026-11-19）

原位置：`docs/current/engineering/ai-debug-review.md`。

2026-11-19 根据 [DeepSeek 官方模型页](https://api-docs.deepseek.com/quick_start/pricing/) 核验，当前官方 deepseek-flash 对应 DeepSeek-V4.1-Flash-1017；本机 deepseek-main 只补版本备注、依据与日期，模型、密钥及请求/额度参数未改。之后需按实际服务商再核验，不能把本日映射作为永久事实。

## 配置精确增量真实实验（2026-11-19）

原位置：`docs/current/engineering/ai-debug-review.md`。

模块精确增量专项和相关回归最新去重 115 项通过，见[后续验收](../../engineering/acceptance/ai-runtime/data-edits-results.json)。包责任者于 2026-11-19 确认第二次真实 DeepSeek 闭环通过：9 调用、137337 tokens，经高危人工批准后仅追加物品定义，原物品及角色背包保持不变；正式房间未变。第一次 13 调用、261009 tokens 的失败保留在包侧 previousRuns，两次为单场景记录，不代表稳定性能基准。

## Stumpsville 场景联调阶段记录

原位置：`docs/current/engineering/ai-rulings.md`。

同日 Stumpsville 隔离联调：包侧 18 组确定性验收通过，选定的 K08 复活、K12 新物品、P04 玩家自愿资料申请三个真实 DeepSeek 用例均通过。复活生成待审批次后由 KP 批准执行，物品和财富保留；新物品经高危提案审批落库。累计 46 次 API 调用、686207 tokens，包括失败调试；另保留一次未调用模型的测试前置失败。最终复活用例为 4 次调用，单次验收的 11.65 秒模型耗时不代表普遍延迟。详见[包侧实测](../../rulepacks/stumpsville/tests/ai-scenarios-live-results.json)与[包侧确定性验收](../../rulepacks/stumpsville/tests/ai-scenarios-results.json)；53 项草稿场景并未全部实测。没有修改正式存档或服务商配置。
