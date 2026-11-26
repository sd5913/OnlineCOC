# 房间 AI 模块

独立 Python 包，当前交付与验收状态见[工程说明](../../docs/current/engineering/ai-runtime.md)；待办见[实施计划](../../docs/plans/ai-runtime-construction-plan.md)。

## 首次安装与第一次请求（Windows x64）

1. 将**完整工程**放在可写目录，关闭正在运行的本工程房间、管理器和安装窗口，双击 [engineering/setup-game.cmd](../setup-game.cmd)。它从 `launcher-config.json` 指定地址取得完整 CPython 3.14.2，校验 SHA256，检查 Tk，并按 [requirements-runtime.lock](../requirements-runtime.lock) 的版本及 wheel 摘要创建 `engineering/.venv`。不要求预先安装 Python，也不修改系统 PATH。看到 `GAME_RUNTIME_READY` 后才继续。
2. 通过配置包的 AI 入口启动房间，例如树桩镇的 `start-ai.cmd`；保持房间运行。另双击 [start-manager.cmd](start-manager.cmd)，浏览器将打开本机管理器。**`QuickStart/安装依赖.exe`用于旧 Desktop 首测环境，写入 `.runtime/environments`；它不能替代上一步的共享 `.venv` 安装。**
3. 在“服务商”中编辑配置，核对服务类型、服务地址、模型与 `credentialRef`，启用该配置。仅在密钥输入框保存真实密钥；配置 JSON、聊天、截图和提交仓库中不要填写密钥。“测试连接（产生用量）”成功后再继续；真实服务测试会计费。
4. 添加运行中的本机房间地址，以该房间 KP 账号登录。在“KP 审核与设置 → 服务与外发范围”选择同一服务配置，开启调用，按本次任务需要明确选择外发范围并保存。服务配置与房间开关是两层设置；本机管理器登录不自动授予房间 KP 权限。
5. 新建会话，先发送讨论型需求，如“请概述当前公开资料，不执行修改”。需要配置修改时查看 A/B/C、差异和风险，再由 KP 决定是否批准。收到回答、通过检查和发布生效是不同状态，不能把模型文案当成执行凭证。

同一 `.venv` 供 AI Manager 和树桩镇当前启动入口共用；公网/P2P 的独立环境仍按对应模块安装。仅安装运行依赖不会安装 pytest、Playwright 等开发测试依赖。

### 安装与连接失败后重试

| 现象 | 处理与成功标志 |
| --- | --- |
| 下载或 pip 失败 | 查看 `engineering/.runtime/game-setup-logs/` 的本次日志，恢复网络后重跑 `setup-game.cmd`；失败不会写成功标记。不要删除房间存档。 |
| Python 摘要不匹配 | 缓存不会被执行。按日志定位该归档，移走损坏缓存后重试；不要绕过摘要检查。 |
| Python / `.venv` 目录不完整或版本不符 | 关闭使用该环境的程序，保留日志并将日志指向的**环境目录**改名留存，再重试；勿操作包的 runtime 游玩存档。 |
| 提示已有安装或桌面宿主 | 关闭原窗口后重试，安装器不会并发改写它使用的环境。 |
| 管理器无法启动 / 缺包 | 先运行 `engineering\setup-game.cmd -VerifyOnly`；若失败，重新安装。不要只从另一台机器复制 `.venv`。 |
| 管理端口被占用 | 关闭旧管理器，或运行 `engineering\ai\start-manager.cmd --port 8777`。 |
| 服务鉴权、限流或网络错误 | 在服务商面板核对密钥、启用状态、模型与地址；按错误原因修正后再“测试连接”。限流按服务提示等待，不连续反复提交。 |
| `AI_DISABLED` / `EXTERNAL_SCOPE_DISABLED` | 由 KP 检查房间调用开关与实际需要的外发范围；不靠重新输入密钥绕过权限。 |
| 消息发送失败 | 原草稿保留。恢复连接后重试该草稿；相同内容保留提交标识。若结果不确定，先看历史和真实回执，避免将“重试”当作新的增量操作。 |

离线机器可准备与锁文件匹配的 wheel 和配置中指定、摘要正确的完整 Python ZIP，然后从项目根目录运行：

```powershell
engineering\setup-game.cmd -Offline -ArchivePath "D:\offline\python-3.14.2-amd64.zip" -WheelDirectory "D:\offline\wheels"
```

2026-11-26 的默认在线新装、离线失败重试、Tk 和一次本机模拟请求证据见[安装验收](../acceptance/ai-install-guide/README.md)。历史真实 DeepSeek 证据另列在该报告中；本机模拟通过不表示当前真实服务或密钥可用。

## 已有能力与开发入口

**独立面板入口：[start-manager.cmd](start-manager.cmd)**。启动本机浏览器管理器，默认以房间文件夹组织会话，提供底部对话输入、服务商/密钥管理和按需打开的 KP 审核面板。房间仍由原宿主运行，默认管理端口 8776。首次使用、权限边界、嵌入组件、JavaScript/HTTP/Python 接口见[管理器与开发接入](../../docs/current/engineering/ai-manager.md)。树桩镇已接入咨询与配置裁决，当前范围见[包侧集成](../../rulepacks/stumpsville/docs/current/integrations.md)。管理器左下角“配置包交互原型”提供 KP／PL 可操作演示，设计与接入步骤见[原型计划](../../docs/plans/ai-pack-interaction.md)。

- 机器契约：[ai.json](../contracts/ai.json)。
- 脱敏服务商配置：[ai-providers.json](config/ai-providers.json)（[模板](examples/ai-providers.json)默认关闭），只有凭据引用；管理器使用 Windows 当前用户加密存储，兼容环境变量回退。
- 配置包专用入口：[pack.js](web/components/pack.js)、[类型声明](web/components/pack.d.ts)、[资源与路由清单](web/components/pack-manifest.json)。支持底层工具自由装配、独立KP设置页、紧凑裁决弹窗，以及单独页面/对话页面/可折叠面板三种版本，详见[接入指南](../../docs/current/engineering/ai-pack-embedding.md)。原 index.js 保持兼容，管理组件仍只用于本机管理员。
- 独立页面：在运行房间的站点打开 `/ai-ui/page.html`、`/ai-ui/conversation.html`、`/ai-ui/collapsible.html`、`/ai-ui/sessions.html`；可直接登录，也支持同源 iframe。使用这些新入口前重启宿主以加载同源嵌入响应头，已有管理器不需要改变配置。
- 用量统计：新配置默认关闭每日累计限额（`dailyTokenBudget: null`），仍记录确认消耗和预留；本机管理器与嵌入对话提供“用量统计”。KP可查本房间，PL仅本人；开发者可用 `mountUsage` / `AiClient.aiUsage` / `createAITools.usage`。从旧版升级需重启宿主和管理器以加载新Schema，详情见[额度与统计](../../docs/current/engineering/ai-manager.md#每日限额与用量统计)。
- 会话管理：本机管理器和三种嵌入对话均提供入口；可用 `mountSessionManager` 独立挂载，支持搜索、置顶、归档恢复、0—4 轮历史携带和格式化/原始文本切换。回答支持安全 Markdown 子集及语义引用，低层可用 `mountMarkdown` / `renderMarkdown`。
- 数据引用：输入 `/` 或 `/en` 等前缀先补全指令，再搜索 `/config`（配置）、`/entity`（活动实体）或 `/data`（KP 的活动工件 JSON 数据）。方向键及 Enter/Tab 选择后显示“旅行提灯”等语义标签，整体增删；底层保留带修订的引用标记。引用只读，发送前可查看实际值，生成仍需外发授权。
- 裁决大历史：AiClient 支持紧凑分页与单条详情；独立 AI 历史使用有版本分片和交付证明窄写，权限及批准仍实时复验。接口见[裁决](../../docs/current/engineering/ai-rulings.md#紧凑分页与按需详情)，配额与恢复见[运行说明](../../docs/current/engineering/ai-runtime.md#升级与备份恢复)。
- 最小技术包：[fixtures/pack](tests/fixtures/pack/docs/rules.md)，不得当作具体游戏规则。
- 来源审核与调试：KP 审核通过来源卡引用玩家申请／裁决，所有转交会话的修改另行人工批准；对话和裁决支持复制定位、授权 JSON 导出。服务商版本备注与实际响应标识分开记录，详见[接口与边界](../../docs/current/engineering/ai-debug-review.md)。
- 任务诊断：KP原生对话显示资料工具执行次数、稳定错误码和可展开的失败阶段；日志不含完整对话、密钥或异常消息。按需空上下文、查询修正与诊断边界见[运行说明](../../docs/current/engineering/ai-runtime.md#任务诊断与查询恢复)。

在项目根目录使用现有开发环境执行测试：

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'
engineering/.venv/Scripts/python -m pytest engineering/ai/tests -p no:cacheprovider
~~~

如默认系统临时目录不可写，使用 `--basetemp engineering/ai/.test-output/新的测试目录名`，不要把游玩存档放入测试目录。

离线 A/B/C 示例：

~~~powershell
engineering/.venv/Scripts/python engineering/ai/scripts/run.py assess --pack engineering/ai/tests/fixtures/pack --changes engineering/ai/examples/bonus-15.json
~~~

`assess` 可换为 `check-base` 或 `check-rules`。仓库 CLI 输出 UTF-8 JSON 报告；退出码 0 表示证据检查通过，1 表示 fail/unknown/error 报告，2 表示输入或初始化失败。C 的通过不代表玩法风险低。`--state` 可提供只读房间/执行快照；完整房间使用其当前工件，未提供则使用包场景夹具。停用时不启动 CLI；宿主共用执行器仍承担正式 Lua 的限制。

实际宿主 demo 的 AI 材料位于 [rulepacks/demo/ai](../rulepacks/demo/ai/rules.md)。在已初始化的独立首测存档中启动：

~~~powershell
engineering/.venv/Scripts/python engineering/backend/scripts/run.py --data-dir engineering/.runtime/ai-demo init
engineering/.venv/Scripts/python engineering/backend/scripts/run.py --data-dir engineering/.runtime/ai-demo serve --ai-config engineering/ai/config/ai-providers.json --ai-pack engineering/rulepacks/demo
~~~

`init` 交互设置房间密码，已有存档不要重复初始化。打开本机操作台，KP 可在“房间 AI 助手”导入 [skill-15.json](../rulepacks/demo/ai/examples/skill-15.json)，执行三检、填写风险理由、批准后加载；此流程不需要密钥或开启 AI 调用。示例针对尚未修改的 demo.skill 修订 1。

新建服务配置、房间调用和外发范围默认关闭；已有本机设置以管理器当前状态为准。正式启用时在管理器保存密钥（或设置 credentialRef 指向的环境变量），启用 Profile，再由 KP 选择房间服务配置和外发范围。已组合 AI 的宿主会在下一次调用前读取同一配置文件的更新，无需重启；未组合 AI 的宿主仍须带上述启动参数。密钥不写入服务商 JSON 或聊天。配置 CLI、预算、工具限制与测试边界见工程说明。

已完成一次真实 DeepSeek JSON、工具调用和生成三检联调，见[结果](../acceptance/ai-runtime/deepseek-live.json)。需要显式重测时执行以下命令，按提示在终端输入密钥（不回显）：

~~~powershell
engineering/.venv/Scripts/python engineering/ai/scripts/live_deepseek.py
~~~

此命令会调用官方服务并产生用量，不随 pytest 或正常启动运行。它只使用独立 demo 存档及公开测试上下文，临时启用进程中的 Profile 副本，密钥仅保留在该进程；无法关闭终端回显时拒绝读取。任务限定 180 秒、最多 4 个工具回合和 1 次结构修复、无传输重试。提案仅生成和检查，不批准或加载，持久配置保持不变。报告覆盖 `deepseek-live.json`，如需保留前次结果请先另存；报告包含候选、三检、用量和摘要，不包含凭据。

本地性能复测（独立临时目录，250 条历史请求、7 次样本，不调用模型）：

```powershell
engineering/.venv/Scripts/python -B engineering/ai/scripts/benchmark_local.py engineering/ai/.test-output/bench-新目录名
```

目录必须尚不存在。测量和适用范围见[管理器性能说明](../../docs/current/engineering/ai-manager.md#本地延迟与测量)。

会话权限与执行批次已接入：KP 默认管理员会话，PL 开关默认关闭；开启后玩家需求直接转交且限于绑定玩家资料。管理面板可审核运行时／会话批次、选择自动批准，嵌入管理支持归档目录与删除。配置发布仍需三检及单独批准。详见[权限与接口](../../docs/current/engineering/ai-session-access.md)。

严格 PL 接入依赖后端 0.3.0 / Room v4 知识服务。包须注册受信提供方并绑定策略，KP 允许玩家对话及 private 外发后，玩家只查询本人固定观察或明确持续告知的内容；模型仅选择证据，服务端排版。未知内容通过选项向 KP 提交需求。详见[已知资料与验收](../../docs/current/engineering/ai-player-knowledge.md)，不同玩法示例见 [knowledge-investigation.py](examples/knowledge-investigation.py)。

高危核心规则／地图／物品配置／删除必须 KP 核对整包和指纹，普通自动审批不能绕过；批次不设业务条数上限。权限开关、PL 自愿披露申请与包作者校验声明见[裁决与扩展](../../docs/current/engineering/ai-rulings.md)。

玩家查询先读取本人已知目录，再读取相关详情；关键词未命中不等于权限不足。组合物品、设计内容可通过“提交创作申请”交给 KP，独立于资料查询和披露；接收后在 KP 私有会话生成方案，所有修改另行人工审核。接口见[玩家申请](../../docs/current/engineering/ai-session-access.md#玩家创作与配置申请)。
