# AI 首次安装、配置与请求验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-26
- 最后更新：2026-11-26
- 关联文档：[AI 模块指南](../../ai/README.md)、[共享安装脚本](../../setup-game.ps1)

本轮新增 `engineering/setup-game.cmd` / `.ps1`，让 AI Manager 和树桩镇原有入口都能使用一键创建的 `engineering/.venv`。根 Desktop 安装器仍使用 `.runtime/environments`，未改变其行为。共享入口复用 `launcher-config.json` 中完整 CPython ZIP 的 URL、SHA256 和基础运行 lock，不依赖系统 Python、不修改 PATH、不访问正式存档或真实凭据。

## 实际结果

| 验收 | 结果 | 证据及边界 |
| --- | --- | --- |
| 默认在线安装 | 成功，51.00 秒 | [online-install.json](online-install.json)：隔离副本没有 Python、`.venv`、ZIP 或 wheel；实际默认下载与哈希安装；随后实际 CMD `-VerifyOnly` 通过，2.85 秒 |
| 安装、失败重试与浏览器入门 | 10/10，100% | [results.json](results.json)、[verify.py](verify.py)、[截图](onboarding.png)；产品服务使用全新隔离环境，不用开发 `.venv`；验收驱动本身使用已有 Playwright/Edge 开发环境 |
| 服务商、管理器回归 | 55/55，100% | [provider-manager.xml](provider-manager.xml)：HTTP 鉴权/限流/超时、受限重试属性、密钥保护、Profile 配置与管理接口；一个现有 Starlette/httpx 弃用警告 |
| 真实 AI 服务 | 本轮未调用 | 下述历史证据不计入本轮模拟成功率；没有读取、打印或提交真实凭据 |

环境为 Windows x64、完整 Python 3.14.2、Tk/Tcl 8.6.15；29 项运行依赖由共享 lock 安装，`pip check` 通过。离线恢复组从完整 Python 缓存和匹配的本地 wheel 安装；默认在线组另外从无缓存目录执行，不能将两组混称为离线或在线。

10 项检查包括：错误归档摘要在执行前拒绝；空 wheel 目录导致 pip 失败且不产生成功标记；补齐 wheel 后重试成功并保留用户哨兵文件；重复安装和复验；并发安装/桌面宿主锁拒绝；全新 base Python 与真实 Tk 窗口创建；管理器一次性入口、合成密钥 DPAPI 保存与模拟连接检查；KP 房间登录和显式 public 外发；在实际管理器代理路由模拟首次提交 HTTP 503 后显示失败、保留草稿和相同 submissionKey；第二次提交产生一项离线模型请求并进入待审核，无批准或发布。

开发验收中修正了 PowerShell 环境缺少 Get-FileHash 时的兼容性（改用 .NET SHA256）、PowerShell 5.1 传递 Python 字符串的引号问题。浏览器驱动另修正了管理器多个 Shadow DOM 的同名状态选择器和代理路由故障注入位置。这些中间失败未算成通过，最终完整脚本重跑得到上述 10 项。保留的隔离工作目录 `work/` 被 Git 忽略，不作为正式存档或提交材料。

## 新用户操作（可直接用于中文 README）

1. 完整解压工程，在 Windows x64 上运行 `engineering/setup-game.cmd`；成功标志为 `GAME_RUNTIME_READY`，日志位于 `engineering/.runtime/game-setup-logs/`。安装失败时按日志修正后重新运行，不删除游戏存档。核验命令为 `engineering/setup-game.cmd -VerifyOnly`。
2. 通过配置包的 AI 启动入口启动房间，保持运行；启动 `engineering/ai/start-manager.cmd`。
3. 编辑并启用服务配置，在密钥输入框保存密钥，执行“测试连接（产生用量）”。不要把密钥放进配置 JSON、聊天、截图或仓库。
4. 添加本机房间地址并用 KP 账号登录，在“KP 审核与设置 → 服务与外发范围”选择服务配置，明确开启调用及本次需要的外发范围并保存。
5. 新建会话并发送讨论型需求。配置修改需要另查 A/B/C、差异、风险和真实执行回执；回答或检查通过不等于已发布。

服务鉴权错误先核对密钥/服务配置；限流按服务提示等待；`AI_DISABLED` 和 `EXTERNAL_SCOPE_DISABLED` 应由 KP 修改对应开关。发送失败会保留草稿和相同内容的提交标识；结果不确定时先查历史/回执。详细恢复表以[模块指南](../../ai/README.md#安装与连接失败后重试)为准。

## README-ready English steps

1. Extract the complete project into a writable directory on Windows x64. Run `engineering/setup-game.cmd`. It downloads and verifies the configured full CPython runtime, checks Tk, and installs hash-locked runtime dependencies into `engineering/.venv`. No preinstalled Python is required. Look for `GAME_RUNTIME_READY`; logs are under `engineering/.runtime/game-setup-logs/`. Correct the logged problem and rerun after a failure. Do not delete game saves. Use `engineering/setup-game.cmd -VerifyOnly` to check the environment.
2. Start an AI-enabled room using the rule pack's launcher and keep it running. Open `engineering/ai/start-manager.cmd`.
3. Edit and enable a provider profile. Save the API key only in the credential field, then use “Test connection” (billable with a real provider). Never put the key in configuration JSON, chat, screenshots or the repository.
4. Add the local room URL and sign in with that room's KP account. In KP Review & Settings, select the profile and explicitly enable AI calls and the required external-data scopes. Save the settings.
5. Create a conversation and send a discussion request. Configuration changes require separate review of A/B/C results, the diff, risks and actual execution receipts. A model response or passed validation does not prove publication.

The root desktop installer targets `.runtime/environments`; the shared AI/Stumpsville installer targets `.venv`. They are separate entry points. Recheck credentials for authentication errors, wait as directed for rate limits, and let the KP resolve disabled-call or external-scope errors. Failed submissions retain the draft and submission identity; inspect history and receipts before retrying an uncertain result.

## 真实服务证据与限制

[deepseek-live.json](../ai-runtime/deepseek-live.json)记录 **2026-11-12** 一次官方 DeepSeek JSON、工具调用和生成三检通过：总用量 **9,507 Token**，隔离 demo、公开夹具上下文、状态 `review_ready`。它是历史实测，不是 2026-11-26 对当前账户/余额/网络/模型的保证，也不证明已批准发布。需要重新测真实服务时，使用模块指南中的 `live_deepseek.py`，在不回显终端输入密钥；该操作会产生用量。

本轮模拟提供方确定性返回、阻止外网；模拟连接检查和 10 项成功率不表示真实模型能力。未测试其他操作系统、实体手机或所有系统策略。共享运行安装不包含 pytest/Playwright，也不替代公网/P2P 模块的独立安装。普通用户不需要运行本验收驱动。

## 可核实的用户决策与 AI 协作案例

用户针对长消息更新和输入中断，明确要求：更新时最近 1 秒无操作则跟随最新，有操作则保持当前位置。AI 工程会话负责组件中的活动记录、滚动锚点、正文/输入节点和 IME；树桩镇会话负责外层刷新/挂载。工程先记录 12 项基线的 9 个失败，修复后专项与相关回归去重 **61/61**，包侧独立组合联验 **8/8**；以三个组件文件的 SHA256 冻结差量交接。

证据：[交互报告](../ai-chat-interaction/README.md)、[基线](../ai-chat-interaction/baseline.xml)、[去重结果](../ai-chat-interaction/verification.json)、[冻结清单](../ai-chat-ui-interface-snapshot/v1/source.json)。这体现了用户决定交互规则，两方按边界实施、用失败复现和真实浏览器结果验证，而非只接受模型口头判断。

English case: The user specified a one-second interaction rule for live chat updates: follow the latest content when idle, preserve the reading position during input. The AI engineering chat handled activity tracking, scroll anchors, stable DOM nodes and IME; the Stumpsville chat fixed the outer refresh/mount lifecycle. Nine of twelve baseline checks failed before the fix. Final engineering regressions passed 61/61, and the package's separate joint checks passed 8/8. A SHA256 manifest identified the three delivered component files.

## 复核与清单交接

从项目根目录运行 `engineering/.venv/Scripts/python.exe -X utf8 -B engineering/acceptance/ai-install-guide/verify.py` 可复现隔离安装和本机模拟请求。需要已安装的开发测试环境、Edge，以及 `engineering/.test-output/launcher-bootstrap/` 和 `engineering/.test-output/wheels/` 的完整缓存；这是验收驱动的前提，**普通共享安装入口不要求这些测试缓存**。

`source.json` 为本轮源码摘要；`files-manifest.json` 列出需纳入工程清单的新增文件及证据摘要。根 README、英文 README、PROCESS、TODO 和 hierarchy 实际目录正文由提交助手汇总；本会话仅维护自己的施工登记，未发布 Git。
