# OnlineCOC · 线上跑团

[English](README.en.md) · [项目开发与 AI 协作记录（英文）](PROCESS.md) · [共享任务与问题](docs/plans/Issues/README.md)

OnlineCOC 是给主持人（KP / GM）、玩家和规则作者使用的多人跑团工具。房主电脑保存房间，规则包决定角色、地图和行动如何运作。**第一次游玩推荐《树桩镇》Stumpsville**：一人主持，其他人扮演小鼠。一次探索会改变角色已知的地点、线索和背包，主持可以裁决预设以外的行动。一个人也可以用两个浏览器标签分别体验主持和玩家视角。

## 先选要运行的内容

| 目标 | 在哪台设备准备什么 |
| --- | --- |
| 玩树桩镇，或使用房间 AI | 房主在 Windows x64 上取得完整项目，准备下述共用环境 `engineering/.venv`。本机试玩可关掉 AI，无需服务商账号。 |
| 让异地玩家从网页加入 | 房主额外安装联网运行时，取得房间目录的发布配置。玩家只需支持 WebRTC 的浏览器、平台入口和游戏账号。 |
| 单独体验基础引擎 | 在完整项目根目录双击 `安装依赖.exe`，再双击 `启动OnlineCOC.exe`，首次设置至少 8 位密码。在 `http://127.0.0.1:8765` 用 `kp`、`player1` 或 `player2` 登录，同时登录多个账号请用独立浏览器配置文件。保持启动窗口运行，关闭窗口可停止宿主。两个 EXE 使用独立的 `engineering/.runtime` 环境。详见[桌面工具](docs/current/engineering/desktop-tools.md)。 |

将[项目仓库](https://github.com/sd5913/OnlineCOC)完整克隆或下载 ZIP 后解压到层级较浅的可写目录（如 `D:\OnlineCOC`）。下文路径都从含有 `launcher-config.json`、`engineering` 和 `rulepacks` 的项目根目录开始。在 GitHub 网页上阅读时，请在本机文件夹中运行对应程序。

## 本机跑一局树桩镇

1. **一键准备依赖。** 双击 [engineering/setup-game.cmd](engineering/setup-game.cmd)，首次联网下载并校验完整 Python、Tk 和锁定依赖，无需预装 Python。看到 `GAME_RUNTIME_READY` 后即可打开树桩镇面板或 AI 管理器。需复查时在根目录 PowerShell 运行 `.\engineering\setup-game.cmd -VerifyOnly`。失败时查看 `engineering/.runtime/game-setup-logs/`，修正报错后重跑安装。

   若需手工安装，可使用 Windows x64 完整版 CPython 3.14.2，含 Tk 和 Python 启动器。在根目录的 PowerShell 执行以下命令。首次下载依赖需要联网，Lua 随锁定依赖安装。

   ```powershell
   py -3.14 -m venv engineering/.venv
   .\engineering\.venv\Scripts\python.exe -m pip install --require-hashes -r engineering/requirements-runtime.lock
   .\engineering\.venv\Scripts\python.exe -m pip check
   ```

2. **房主开房。** 双击 [start-panel.cmd](rulepacks/stumpsville/start-panel.cmd) 即选中树桩镇。选择“本机”，首次试玩可取消“AI助手”。创建新存档槽位，设置并确认初始密码，点击“启动房间”。默认本机地址为 `http://127.0.0.1:8899`。房间面板负责运行服务，游玩期间可以最小化。
3. **主持和玩家入场。** 在打开的页面用 `kp` 登录，在“房间”点击“一键开场”。另开根地址，或点“新开独立登录页”，用 `player1` 和新槽位的初始密码登录。玩家在大厅选择预设角色并提交，主持到“裁决”批准，玩家检查背包并确认准备。保留至少一个已登录的主持页面处理行动。
4. **检查首次互动。** 在“01 入口隧道”选择“观察地面 → 仔细观察”。玩家手记应出现“入口地面的压痕”，地图上应出现“02 主门”。首局可约定“探路取物”：记录两条不同发现、带回一件非初始物品，全员返回入口，由主持核对。完整冒险可以继续到庭院接任务。[玩家简明指南](rulepacks/stumpsville/docs/current/player-guide.md)
5. **结束或恢复。** 在面板点击“停止房间”，下次选择同一槽位恢复。存档位于 `rulepacks/stumpsville/runtime/slots/`。旧槽位沿用已激活的规则，想体验当前出厂内容可新建槽位。[存档与恢复](rulepacks/stumpsville/docs/current/usage.md)

## 邀请玩家联机

新槽位中的示例账号共用创建时的初始密码。邀请其他人之前，在房主面板的“账号管理”给每位玩家创建账号或分别改密，单独保留主持账号。

**同一局域网。** 房主双击 [start-lan.cmd](rulepacks/stumpsville/start-lan.cmd)，选局域网网卡、槽位并启动。在面板复制玩家访问地址给同一网络的玩家。玩家用浏览器打开该地址，登录自己的游戏账号。若无法连入，先在面板核对网卡、监听端口与连接诊断。回环地址 `127.0.0.1` 只在房主电脑上有效。[局域网说明](rulepacks/stumpsville/docs/current/usage.md)

**异地网页联机。** 完整树桩镇桌面使用网页模式。旧 P2P 客户端另有基础状态与聊天入口。若要使用该客户端，房主先启动宿主，再运行 `engineering/network-p2p/play.cmd`、选择本机宿主并发布。玩家取得完整加入信息、玩家 ZIP 与游戏账号，在装有 Python 3.14 x64 的 Windows 电脑解压 ZIP，运行 `play.cmd`，首次联网安装后连接、登录、下载内容并发送测试聊天。[旧 P2P 客户端](engineering/network-p2p/README.md)

1. **房主安装。** Windows 10/11 x64 房主取得维护者分发的 `OnlineCOC-Network-Setup.exe` 后双击，选择**含 engineering 的项目根目录**，点击“一键安装”。它离线安装到 `engineering/network-p2p/.venv`。若提示占用，正常关闭联网进程后重试。该 EXE 是构建产物。只有源码时，安装含 `py` 的 Python 3.14 x64，在根目录 PowerShell 运行 `.\engineering\network-p2p\setup.ps1` 并等待成功。然后运行 `.\engineering\network-p2p\.venv\Scripts\python.exe -m pip install --no-deps -e engineering/network-web` 将网页模块加入源码环境。使用离线 EXE 时可直接进入下一步。[安装器、构建与自检](engineering/network-web/installer/README.md)
2. **准备发布配置。** 房主从平台维护者取得与所用目录服务匹配的本机配置（默认 `engineering/network-p2p/local/client-config.json`）、CA 公钥证书与发布授权。仓库提供代码与示例，自建服务的部署和配置见[联网工程说明](docs/current/engineering/network-p2p.md)。测试平台使用测试 CA，玩家需从可信渠道取得并信任其公钥证书。
3. **房主分享。** 双击 [start-web.cmd](rulepacks/stumpsville/start-web.cmd)，选择槽位并启动。在房间管理页打开“网页分享与连接”，复制开房串，在平台“创建房间”登录后粘贴，选择公开性和密码。开房串供房主一次认领，十分钟有效。发给玩家的是**加入网址和八位房间代号**，另行分配游戏账号。
4. **玩家加入。** 在浏览器注册或登录平台，输入代号和所需密码，按房间设置等待批准。点“进入游戏”→“连接房主”，用房主分配的**游戏账号**登录。两人在全局频道互发一条消息可确认连接，再按上节建角、开场。房主保持面板运行，主持保持游戏页在线。[网页房间说明](rulepacks/stumpsville/docs/current/web.md)

## 在房间中使用 AI

1. 先完成树桩镇的共用环境安装。房主本机双击 [start-ai-manager.cmd](rulepacks/stumpsville/start-ai-manager.cmd) 打开服务商管理器。在“服务商”选择 DeepSeek 或兼容服务，按服务商提供的信息填写地址、模型 ID、凭据并启用，再点“测试连接”。测试会产生实际调用用量，密钥只在本机管理器配置。
2. 双击 [start-ai.cmd](rulepacks/stumpsville/start-ai.cmd)，或在房间面板勾选“AI助手”后启动槽位。以 `kp` 登录，在“AI 设置”确认选中的服务、是否允许调用、可向服务商发送的资料以及玩家对话权限。已有槽位保留原设置。也可在独立管理器的“房间与会话”添加本机宿主地址，以 KP 登录后，在“KP 审核与设置 → 服务与外发范围”配置同一房间。
3. 在主持裁决页的 AI 对话中发一个只读问题，例如“根据当前房间资料，我该如何开始这局游戏？”。等待会话里出现回答。获准的玩家也可从场景右栏打开个人 AI 对话。需要修改规则或发放物品时，主持可在裁决队列检查差异、风险和执行结果。
4. 若管理器打不开，先检查共用环境；若面板正常但没有回答，依次核对服务商测试、房间选用的模型、调用与资料权限及任务状态。[管理器说明](docs/current/engineering/ai-manager.md) · [树桩镇 AI 接入](rulepacks/stumpsville/docs/current/integrations.md)

## 验证范围

共用安装器已在无缓存的 Windows x64 隔离副本中完成安装，Tk 和 29 项运行依赖通过检查。本轮用模拟 AI 服务完成配置，首次提交失败后重试，同一请求进入待审核状态。真实 DeepSeek 的记录来自此前联测。[本轮 AI 安装与请求验收](engineering/acceptance/ai-install-guide/README.md) · [历史真实服务记录](engineering/acceptance/ai-runtime/deepseek-live.json)

基础引擎在隔离目录完成无缓存在线安装，三个账号能登录，两端同步 Lua 行动结果，重启后保留进度。网页联网 EXE 在运行时被占用时提示失败，关闭占用后同目录重试成功。[引擎安装验收](engineering/desktop/acceptance-install-audit/README.md) · [联网安装验收](engineering/network-web/acceptance/2026-11-26-firstplay.json)

2026-11-26 在 Windows 隔离新房间验证了入口观察、个人线索和地图更新。本机双浏览器通过真实 WebRTC 进入同一间树桩镇房间并覆盖 18 项预设行动。独立家庭或移动网络的真人试玩仍待补验。历史公网强制 TURN 与远程主持证据单列。[双浏览器结果](rulepacks/stumpsville/tests/web-results.json) · [历史公网主持验证](rulepacks/stumpsville/tests/remote-kp-cloud-results.json)

## 来源、进度与开发入口

- 树桩镇适配 Isaac Williams / Losing Games 的 Mausritter SRD。规则、第三方冒险参考、原创分支及生成式运行插画分别标注来源。分发素材前请核对其对应许可。[来源与许可](rulepacks/stumpsville/docs/current/sources.md) · [运行插画](rulepacks/stumpsville/assets/runtime/README.md)
- 项目使用 Python、FastAPI、WebSocket、Lua/Lupa 和浏览器 WebRTC。提交、测试、已知问题和 AI 协作过程见[开发记录](PROCESS.md)、[共享问题与计划](docs/plans/Issues/README.md)和[首测验收](docs/current/engineering/first-test-acceptance.md)。
- 规则作者可从[Lua 编写说明](docs/current/engineering/lua-authoring.md)、[配置包目录](rulepacks/README.md)和[开发者参考](docs/current/engineering/developer-reference/README.md)开始，另有[《激光与情感》](rulepacks/lasers-and-feelings/README.md)。
- 运维与工程入口包括[基础宿主](docs/current/engineering/first-test.md)、[聊天室](docs/current/engineering/chat-backend.md)、[桌面房间管理器](tools/room-manager/README.md)和[账号工具](tools/host-accounts/README.md)。协作前查看[工程登记](docs/current/engineering/hierarchy.md)、[文档规范](docs/standards/document-maintenance.md)和[文档索引](docs/README.md)。
