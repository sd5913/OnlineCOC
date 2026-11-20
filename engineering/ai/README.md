# 房间 AI 模块

独立 Python 包，当前交付与验收状态见[工程说明](../../docs/current/engineering/ai-runtime.md)；待办见[实施计划](../../docs/plans/ai-runtime-construction-plan.md)。

**独立面板入口：[start-manager.cmd](start-manager.cmd)**。启动本机浏览器管理器，默认以房间文件夹组织会话，提供底部对话输入、服务商/密钥管理和按需打开的 KP 审核面板。房间仍由原宿主运行，默认管理端口 8776。首次使用、权限边界、嵌入组件、JavaScript/HTTP/Python 接口见[管理器与开发接入](../../docs/current/engineering/ai-manager.md)。树桩镇已接入咨询与配置裁决，当前范围见[包侧集成](../../rulepacks/stumpsville/docs/current/integrations.md)。管理器左下角“配置包交互原型”提供 KP／PL 可操作演示，设计与接入步骤见[原型计划](../../docs/plans/ai-pack-interaction.md)。

- 机器契约：[ai.json](../contracts/ai.json)。
- 脱敏服务商配置：[ai-providers.json](config/ai-providers.json)（[模板](examples/ai-providers.json)默认关闭），只有凭据引用；管理器使用 Windows 当前用户加密存储，兼容环境变量回退。
- 配置包专用入口：[pack.js](web/components/pack.js)、[类型声明](web/components/pack.d.ts)、[资源与路由清单](web/components/pack-manifest.json)。支持底层工具自由装配、独立KP设置页、紧凑裁决弹窗，以及单独页面/对话页面/可折叠面板三种版本，详见[接入指南](../../docs/current/engineering/ai-pack-embedding.md)。原 index.js 保持兼容，管理组件仍只用于本机管理员。
- 独立页面：在运行房间的站点打开 `/ai-ui/page.html`、`/ai-ui/conversation.html`、`/ai-ui/collapsible.html`、`/ai-ui/sessions.html`；可直接登录，也支持同源 iframe。使用这些新入口前重启宿主以加载同源嵌入响应头，已有管理器不需要改变配置。
- 用量统计：新配置默认关闭每日累计限额（`dailyTokenBudget: null`），仍记录确认消耗和预留；本机管理器与嵌入对话提供“用量统计”。KP可查本房间，PL仅本人；开发者可用 `mountUsage` / `AiClient.aiUsage` / `createAITools.usage`。从旧版升级需重启宿主和管理器以加载新Schema，详情见[额度与统计](../../docs/current/engineering/ai-manager.md#每日限额与用量统计)。
- 会话管理：本机管理器和三种嵌入对话均提供入口；可用 `mountSessionManager` 独立挂载，支持搜索、置顶、归档恢复、0—4 轮历史携带和格式化/原始文本切换。回答支持安全 Markdown 子集及语义引用，低层可用 `mountMarkdown` / `renderMarkdown`。
- 数据引用：输入 `/` 或 `/en` 等前缀先补全指令，再搜索 `/config`（配置）、`/entity`（活动实体）或 `/data`（KP 的活动工件 JSON 数据）。方向键及 Enter/Tab 选择后显示“旅行提灯”等语义标签，整体增删；底层保留带修订的引用标记。引用只读，发送前可查看实际值，生成仍需外发授权。
- 最小技术包：[fixtures/pack](tests/fixtures/pack/docs/rules.md)，不得当作具体游戏规则。
- 来源审核与调试：KP 审核通过来源卡引用玩家申请／裁决，所有转交会话的修改另行人工批准；对话和裁决支持复制定位、授权 JSON 导出。服务商版本备注与实际响应标识分开记录，详见[接口与边界](../../docs/current/engineering/ai-debug-review.md)。
- 任务诊断：KP原生对话显示资料工具执行次数、稳定错误码和可展开的失败阶段；日志不含完整对话、密钥或异常消息。按需空上下文、查询修正与诊断边界见[运行说明](../../docs/current/engineering/ai-runtime.md#任务诊断与查询恢复2026-11-15)。

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
