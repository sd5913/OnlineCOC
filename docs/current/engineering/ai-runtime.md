# 房间 AI 模块：当前实现与验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-12
- 最后更新：2026-11-21
- 关联文档：[工程索引](README.md)、[模块入口](../../../engineering/ai/README.md)、[设计](../../plans/ai-runtime-design.md)、[施工计划](../../plans/ai-runtime-construction-plan.md)

## 当前阶段

当前为可选加载的房间 AI 服务：管理员资料查询、运行时批次和配置三检发布；玩家只消费宿主个人知识。依赖后端 0.3.0 / Room v4，关闭 AI 不影响普通游戏。

| 主题 | 唯一正文 |
| --- | --- |
| 运行入口、服务商和 API | [管理器](ai-manager.md) |
| 查询、引用和配置增量 | [数据查询](ai-data-query.md) |
| 玩家知识与创作申请 | [个人知识](ai-player-knowledge.md)、[会话权限](ai-session-access.md) |
| 批次、配置和高危审批 | [修改裁决](ai-rulings.md) |
| 嵌入、来源审核和故障导出 | [组件](ai-pack-embedding.md)、[调试](ai-debug-review.md) |

新房间默认权限和 C 评估见[默认配置验收](../../../engineering/acceptance/ai-defaults-c-review/README.md)；KP 来源采纳及真实配置增改删的成功率与失败记录见[上下文验收](../../../engineering/acceptance/ai-context-compression/README.md)，当前压缩机制及长对话对照见[官方机制适配验收](../../../engineering/acceptance/ai-official-compaction/README.md)。重启与调试修复见[此前验收](../../../engineering/acceptance/ai-runtime/repair-20261120.md)，早期阶段见[开发记录](../../history/2026-11-20-ai-development-records.md)；各轮重复用例不相加为独立覆盖。

## 已有内容

| 内容 | 实际入口与边界 |
| --- | --- |
| 机器契约 | [ai.json](../../../engineering/contracts/ai.json) 定义 Profile、包契约、上下文、提案、报告、批准等结构；顶层拒绝未知字段 |
| JSON/摘要工具 | [contracts.py](../../../engineering/ai/src/onlinecoc_ai/contracts.py)：拒绝重复键、非法 Unicode、非有限/不安全数字、过深数据；canonical 字节与现有存储一致 |
| 跨对象约束 | 候选、基线、上下文及报告摘要绑定；配置 ID/修订前置条件、工件摘要和作用域一致性检查；这些结构检查不等于主机授权 |
| 工具权限目录 | [policy.py](../../../engineering/ai/src/onlinecoc_ai/policy.py)：模型能力与禁用操作的目录；编排的基本查询工具及管理员附加管理查询均只读；配置草稿交给三检，运行时修改只提出[执行批次](ai-session-access.md)，模型不能直接审批或执行 |
| 技术包 | [包规则](../../../engineering/ai/tests/fixtures/pack/docs/rules.md)、Schema、B 正反例、C 场景和指标；仅用于工程验收，不代表实际游戏已适配 |
| 服务商模板 | [ai-providers.json](../../../engineering/ai/examples/ai-providers.json)，默认禁用，凭据仅引用 ONLINECOC_DEEPSEEK_API_KEY；[实际配置](../../../engineering/ai/config/ai-providers.json)支持本机管理及可选启动加载 |

## A/B/C 与包材料

三个工具共用 Python 服务函数，返回绑定候选、基线、上下文、包契约和检查器摘要的 `ValidationReport`。CLI 不调用模型、不写房间。缺证据、未知检查器或执行异常不能成为通过结果。

| 工具 | 开发主责 | 当前提供方式与边界 |
| --- | --- | --- |
| A `check-base` | 工程 | 严格 JSON、文件配额/路径及链接逃逸检查；完整合并保留旧规则；真实 `stage` 和宿主模型加载；包作者以本地 JSON Schema 声明数据约束，禁止外部 Schema 引用 |
| B `check-rules` | 包作者定义规则，工程实现执行器 | `PackContract`＋`CheckSpec` JSON、条款来源、每项正反 fixture；数值范围、引用、唯一性、固定场景断言使用带版本 checker ID。限制可扩展路径/命名空间；旧实例不迁移；活动 flow 与配置变更的依赖无法证明时返回 unknown |
| C `assess` | 包作者/规则设计者定义场景指标，工程负责模拟，KP 判断玩法 | `Scenario`＋`Metric` JSON 和人工清单；同一声明初态分别创建基线/候选实例；单次骰精确枚举或独立、可重放的采样；保存概率/消耗差异、骰点、覆盖与风险。覆盖不足保留 unknown，由受限的人工采纳条件判断能否进入裁决 |

C 依据版本、可采纳错误白名单、KP 显式证明及硬边界统一见[可变评估依据](ai-rulings.md#c-类评估与可变依据)。人工采纳不改写报告；自动批准仍要求三检 pass。

技术包含正常玩家、错误持有人和资源耗尽三种场景。[实测报告](../../../engineering/acceptance/ai-runtime/ai-1-gameplay.json)记录 d100 成功率 60%→75%，增加 15 个百分点、相对增加 25%，消耗均为 1；C 的 pass 仅表示必需证据完整，风险仍为 high，需要 KP 判断。固定场景和有限采样不能证明所有玩法平衡。

包从本机管理员选择的目录读取成有配额的内存快照；候选不能改写校验条款、Schema、场景或指标。支持常规 rules/config 目录，以及 ai/manifest.json 声明 layout=flat 的既有平铺包；Lua 换行与宿主加载器一致，原始材料仍参与契约摘要。常规映射见[技术包 manifest](../../../engineering/ai/tests/fixtures/pack/manifest.json)。当前不是任意既有配置包的通用导入器。

## 共同执行限制

正式 Lua、规则 inspect 与 A/B/C 均调用宿主 `worker_process.py`。子进程使用隔离 Python 启动和清理后的环境，不继承密钥/代理变量；Lua 无 os/io/package/debug/Python 属性访问。Lua 内存 32 MiB、进程内存 512 MiB、单进程、JSON 输入/输出各 8 MiB；正式执行默认 10 秒，场景默认 30 秒。Windows 使用 Job Object，父进程关闭任务即终止 worker；输出和等待均有界。

Windows 恢复发布目录遇短暂共享/访问占用时最多尝试 6 次，仍不覆盖既有目标，持续失败保留暂存目录。

Windows 上已验证顶层死循环、内存/输出膨胀、文件/网络与 Python 桥访问、进程失败及原宿主回归。这是受限 Lua 运行边界，不是对任意原生程序或解释器漏洞的隔离保证；非 Windows 资源策略尚未实机验收。

## 人工提案、审批与加载

[Proposals](../../../engineering/ai/src/onlinecoc_ai/proposals.py) 提供 `create/revise/validate/prepared/get/reconcile`；[Repository](../../../engineering/ai/src/onlinecoc_ai/repository.py) 使用独立 FileDataStore，默认在主机数据目录的 `ai/`。草稿保存完整候选、不可变内容修订、上下文和检查报告；修改产生新修订，并先在主机撤销旧批准。外部草稿不能携带“通过”报告代替实际检查。

服务通过本机组合端口 `Host.register_ai` 登记受信提案解析器和包契约。解析 PreparedBundle 在房间锁外完成；主机在锁内重新验证 KP、作用域、基线、来源、条款/检查器版本和风险理由。人工入口包括 Python 服务、HTTP 草稿上传和操作台，不依赖模型调用。

以下管理操作已进入 `operations.json`，沿用 `POST /api/v1/commands` 及既有命令封套/回执：

| 操作 | args | 实际行为 |
| --- | --- | --- |
| `ai.proposal.approve` | `proposalId`、`proposalRevision`、`riskDecisions`，高危另需 `explicitHighRiskDigest`，C 待采纳另需 `cReview`，独立来源待采纳另需 `consultationReview` | 仅当前 KP；把候选工件暂存并复制报告/配置变更到 Room，不激活配置；风险决定、高危指纹、C 依据与来源接受证明按[裁决契约](ai-rulings.md)提交；来源接受不绕过 A/B 或当前目标检查 |
| `ai.proposal.revoke` | `approvalId` | KP 撤销尚未消费的批准；已发布不能用撤销回滚 |
| `publication.apply` | `approvalId` | 当前批准者仍为有效 KP，且批准未过期、未撤销、基线与证据未变时，一次提交配置、活动工件、消费标记、发布记录、审计和回执 |

批准由 `approvalDigest` 绑定全部不可变审核证据；此摘要用于检测改动，授权仍由受信提案解析与主机权限检查提供。候选与批准证据保存在 Room；关闭 AI 服务后的依据与权限回调重新读取持久化仓库，原批准仍须通过当前依据和来源复验，不跳过检查。相同 commandId 返回原回执，相同 approvalId 最多生效一次；相同 commandId 的不同内容拒绝。提交后异常会按已落盘回执返回成功，不改写为拒绝。`reconcile` 只对账 AI 状态，不重复应用配置。

审核及发布会保守检查整个游戏快照摘要。两名 KP 审核同一基线时，先发布者生效，后者得到 `BASELINE_STALE`。批准暂存和 AI 历史变化不会改变游戏摘要。当前按原批准 KP 发布；旧实例数值和已发生的随机/伤害不回滚。

## 升级与备份恢复

后端 0.3.0 只接受 Room schemaVersion=4，chat、aiControl 与 knowledge 均必需；文件数据管理格式仍为 1。加载时拒绝其他版本，不自动补齐或改档。v3 可通过独立离线转换器生成新副本；格式、命令及回滚步骤见[房间格式](room-format.md)。新建房间直接使用 v4。同一存档重启保留 AI 与知识 scopeId，主机 authorityEpoch 会改变，因此未消费的旧批准需要重新检查和审核；已消费命令回执仍可查询。

AI Repository 在默认文件存储即将超过累计配额时无损压缩较早快照，保留每代原字节、完整链、审计和回执；不裁剪业务历史。压缩后的目录需新版读取器，仍受 512 MiB 和临时空间约束，不能视为无限容量。接口与隔离大样本验证见[存储运维](first-test.md#5-管理和恢复)及[压缩验收](../../../engineering/acceptance/store-compaction/README.md)。

恢复到新目录会生成新 scopeId、撤销未消费批准、关闭自动需求；已发布配置和工件保留。备份验证工件引用、批准证据摘要及可选 AI 快照引用。`Assets.backup(..., ai_snapshot=...)` 可携带独立历史；恢复为 `ai-history-before-restore.json` 附件，不自动把旧作用域历史当作新房间有效记忆。没有 AI 附件也能恢复已发布游戏。

## 服务商与任务编排

本机配置为 `engineering/ai/config/ai-providers.json`；模板的 `enabled=false`，已保存的启停状态以本机管理器为准；`credentialRef` 使用 env: 引用；先查本机管理器的 Windows DPAPI 保险库，再回退进程或当前 Windows 用户环境变量。本机 CLI 提供 `profile-init/profile-list/profile-put/profile-probe`；修改完整 Profile 时自动递增修订。不要把密钥写入 JSON。示例：

~~~powershell
engineering/.venv/Scripts/python engineering/ai/scripts/run.py profile-list
engineering/.venv/Scripts/python engineering/ai/scripts/run.py profile-put --input 完整Profile文件.json
~~~

`profile-probe --profile deepseek-main` 会实际发送最小 JSON 和工具能力请求，只有用户配置凭据并明确执行时才运行。真实联调脚本已调用同一 `probe()` 验证两项能力。DeepSeek 使用非流式 Chat Completions、显式关闭 thinking、JSON object 输出；兼容服务使用相同协议而省略厂商扩展。格式依据 [DeepSeek 官方 API](https://api-docs.deepseek.com/api/create-chat-completion/)、[JSON 输出](https://api-docs.deepseek.com/guides/json_mode/)及[工具调用](https://api-docs.deepseek.com/guides/tool_calls/)，于 2026-11-12 核对；JSON/工具响应仍由本地严格验证。

HTTPX 0.28.1、HTTPCore 1.0.9、certifi 已列为运行依赖并锁定 wheel。连接时解析并检查 DNS，TCP 使用已核验地址、TLS 保留原主机名；默认禁止私有地址，不继承代理、不跟随重定向。支持显式私有兼容端点，但须管理员配置 `allowPrivateEndpoint=true`。异常输出只保留稳定错误码，不记录原始错误响应或凭据。

Coordinator 每房间只运行一个任务，队列、总期限、工具回合、修复和传输重试有上限。请求按提交 ID 幂等、按来源修订去重；未知/发布类工具拒绝。模型按会话权限获得基础、数据、管理员管理及配置节点读取工具；玩家使用独立个人知识工具，见[数据查询](ai-data-query.md)；最终结构化草稿走与人工相同的三检服务，模型仍无批准/发布权限。可选启动服务按会话身份捕获发送时的授权快照，管理员历史意图可有界保留并进行可追溯语义压缩。

### 任务诊断与查询恢复

任务记录脱敏阶段、工具尝试、错误、模型标识及用量；只有 KP 可见诊断。按需初始空上下文不等于无资料；可恢复查询错误和结构错误在原回合、期限与修正额度内反馈模型；撤权、外发授权缩减或会话失效阻止新输出，普通业务修订按发送快照与依赖变化机制处理。具体工具、配额和错误边界见[数据查询](ai-data-query.md)、[回答协议](ai-responses.md)。

每日限额默认关闭但始终记账。每次调用先预留、成功后结算，失败／取消／重启保留待核实预留。任务重启标 interrupted，不自动重发；用量口径见[统计](ai-manager.md#每日限额与用量统计)。

可选启动参数为 `serve --ai-config <配置> --ai-pack <包>`；模板服务商配置默认关闭；采用显式新房间初始化时按[默认权限](ai-session-access.md#新房间初始化)选择服务并开启使用／外发权限，普通重启不重置既有设置。模型只提出方案／草稿／批次。配置修改按摘要刷新，当前任务绑定原 Profile 修订；网络等待和本地三检不占房间写锁。

## 授权上下文和持久记忆

启动 Runtime 使用按需上下文；旧 Context 构造模式仍可整理实体、配置和每频道最近 50 条消息。新查询、来源绑定及聊天裁决资料统一见[数据查询与事件资料](ai-data-query.md)。外发范围读取房间当前设置，来源和权限仍逐次复验，玩家陈述不能替代主机事实。

上下文记录来源修订／摘要、包含／遗漏清单、外发策略摘要和房间 scope。初始资料组装上限为 2 MiB，模型序列化请求最多 768 KiB，并受 Profile 模型窗口、输出和协议余量约束；管理员历史可触发保留原文与来源锚点的语义压缩。具体限额、遗漏、回读和失败处理统一见[上下文连续性与预算](ai-session-access.md#上下文连续性与预算)及[语义压缩](ai-session-access.md#语义压缩与原文定位)。

排队和生成期间读取发送时的授权快照，继续复验成员、会话、权限与外发范围；撤权或授权缩减仍阻止新输出。普通业务变化在生成后按实际读取依赖记录为 dependencyCheck，保留回答和候选供继续讨论或按最新资料重新生成，不自动重跑或执行。真正批准、加载和批次执行仍校验当前权限、来源及基线；变化提示不赋予旧结果执行权。进程重启将未完成任务标为 interrupted，不能用新资料假装续跑。详见[发送快照与执行校验](ai-session-access.md#发送快照与执行校验)。

显式数据引用由 `References` 解析并加入 `selectedReferences`。配置/实体绑定修订，工件数据绑定活动规则版本；提交和生成时检查发起者与审核者均可访问，生成还检查外发范围。提交时已失效的引用标记须重新选择；生成后的依赖变化按上述快照规则处理。引用不赋予写权限，A/B/C、KP 审核与宿主发布流程继续适用。具体 API、配额与组件见[管理器说明](ai-manager.md#数据引用与短指令)。

`Memory.create` 只创建有来源的草稿；`confirm/revoke` 需要 KP，`search` 是有数量限制的关键词检索。确认条目同时保存在 Room.aiControl.memoryFacts，发布时不用读取独立 AI 仓库。每次检索重新检查来源、权限、有效期和派生链；Room 中已确认/撤销的记忆不能被 AI 仓库旧草稿重新确认。来源修改、撤权、撤销及作用域恢复分叉后，旧记忆不可用。私密来源不能生成公开摘要，KP-only 内容不能降为公开。事件、裁决、偏好、摘要均使用 MemoryEntry 契约；对话语义压缩不自动写入或覆盖已确认事实，长期记忆仍需 KP 确认；当前不提供向量检索。

主机来源校验也用于审批/发布，确认记忆的修订变化会使依赖它的上下文失效。两个真实 demo 数据目录的秘密与记忆隔离已测试。操作台已提供外发设置、上下文上限/额度、记忆创建/确认/撤销；界面用可见对象作为记忆依据，其他来源可通过 API 指定。

## HTTP、SDK 与审核面板

可选 AI 服务启用后，`capabilities.ai` 返回 version、available、enabled、maxCommandBytes、maxDraftBytes、maxPage；未组合 AI 时 available=false，AI 路由不安装。首版通用 AI 面板/API 验收以本机回环为准；包侧网页咨询已有独立受限桥，具体范围见[Stumpsville 接入计划](../../plans/stumpsville-ai-integration.md)，不据此宣称完整 LAN 审核/发布已开放。

| 入口 | 输入及行为 |
| --- | --- |
| `POST /api/v1/ai/commands` | `{requestId,authorityEpoch,op,args}`；64 KiB，账号由会话绑定，参数见 [ai-operations.json](../../../engineering/contracts/ai-operations.json) |
| `POST /api/v1/ai/drafts` | 同一封套，仅 ai.draft.create / ai.proposal.revise，8 MiB；人工草稿和修改都重新三检 |
| `GET /api/v1/ai/receipts/{id}` | 当前账号的幂等回执；pending/committed/rejected/unknown，重启时未完成回执标记 unknown/PROCESS_RESTARTED |
| `GET /api/v1/ai/tasks?before=&limit=` | 请求分页，上限 100；玩家开关启用后可见本人玩家会话的授权回答；诊断／报告仍限 KP，来源读取重新复验 |
| `GET /api/v1/ai/proposals/{id}` | 当前审核者可读提案及报告；旧回执同样重新验证来源，撤权后不返回旧正文 |
| `GET /api/v1/ai/contracts` | 当前 JSON 操作 Schema 与依赖定义，需登录 |
| `GET /api/v1/ai/sessions` / `sessions/{id}` | KP 全部／PL 本人会话列表及详情；create/update/submit/delete 命令与有限会话历史，详见[管理器接口](ai-manager.md) |
| `GET /api/v1/ai/references?kind=&q=` / `POST /api/v1/ai/references/resolve` | 当前账号可见的配置、活动实体与 KP 工件数据；修订绑定、只读预览与外发复验，详见[引用契约](ai-manager.md#数据引用与短指令) |
| `GET /api/v1/ai/settings` | KP 可见房间开关、服务配置公开标识、外发范围、额度和有效记忆 |

审核组件已统一在 `engineering/ai/web/components/room-panel.js`，操作台通过 `engineering/test-console/ai.js` 转用；另有独立管理器和会话组件。源码、挂载、销毁及 Transport 契约见[组件说明](ai-manager.md)。

所有写入复用 Origin、会话和 CSRF。SDK 提供 aiCommand/aiReceipt/aiTasks/aiProposal/aiSettings；审批和加载沿用普通 command/receipt。结果未知时查询相应回执，不换 ID 重做。请求取消撤销未消费批准；手改产生新修订并保留原来源约束。

操作台包含玩家需求、KP 转发、人工 JSON 导入、队列、报告/影响对象、候选差异、逐项风险理由、批准与加载。自动接收默认关闭，只监听 KP 指定且有权读取的频道和前缀；开启时跳过既有消息，以来源修订去重；编辑/撤回取消旧任务。只处理普通文本，AI 结果不写回监听频道。纯文字方案和澄清同样保留来源，撤权后队列仅显示过期状态；手工修订仍保留原来源绑定。退出或权限重置会清除面板缓存。AI 页面模块加载失败时普通操作台仍可使用。[Edge 证据](../../../engineering/acceptance/ai-runtime/ai-5-browser.json)使用离线确定性服务，不代表真实 DeepSeek 联调。

## 实际 demo 试点

早期 demo.skill 默认值对照、故障恢复和 DeepSeek 样例见[历史试点记录](../../history/2026-11-20-ai-development-records.md)。实际 Stumpsville 接入由[包侧当前文档](../../../rulepacks/stumpsville/docs/current/integrations.md)维护；有限测试不能替代真实 KP 试玩。

## 验收命令

在项目根目录、现有开发环境中执行：

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'
engineering/.venv/Scripts/python engineering/ai/scripts/run.py check-base --pack engineering/ai/tests/fixtures/pack --changes engineering/ai/examples/bonus-15.json
engineering/.venv/Scripts/python engineering/ai/scripts/run.py check-rules --pack engineering/ai/tests/fixtures/pack --changes engineering/ai/examples/bonus-15.json
engineering/.venv/Scripts/python engineering/ai/scripts/run.py assess --pack engineering/ai/tests/fixtures/pack --changes engineering/ai/examples/bonus-15.json
$run='engineering/ai/.test-output/recheck-'+[guid]::NewGuid().ToString('N')
engineering/.venv/Scripts/python -m pytest engineering/backend/tests engineering/ai/tests -q --basetemp $run -p no:cacheprovider --junitxml=engineering/ai/.test-output/recheck.xml
~~~

测试使用公开的固定夹具，不读取真实游戏存档。服务商模板不是密钥存储，不能把实际密钥写入仓库。显式真实联调命令与不回显输入说明见[模块入口](../../../engineering/ai/README.md)；真实服务结果与本地模拟结果分别记录。

会话级权限、玩家直接转交、管理员执行批次、自动批准和删除行为见[会话权限与执行批次](ai-session-access.md)。配置发布仍使用既有三检与独立风险批准。
