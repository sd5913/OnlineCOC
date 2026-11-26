# OnlineCOC · 线上跑团

[English](README.md) · [更新日志](UPDATE-NOTES.md) · [开发与 AI 协作记录](PROCESS.md) · [玩家反馈](feedback/README.md)

房主用 Windows 电脑开房并保存进度，玩家用浏览器入座。配置包提供角色、地图和规则；遇到预设以外的行动，由主持人（界面中称为 **KP**）裁决。

**第一次玩，推荐《树桩镇》Stumpsville。** 带一队小鼠进镇探路，记下发现，带回物资。一个人也可以用两个独立标签页分别体验主持和玩家视角。

| 我想做什么 | 从这里开始 |
| --- | --- |
| 第一次主持或游玩树桩镇 | [安装并开局](#play-stumpsville) |
| 邀请其他玩家 | [局域网与异地联机](#multiplayer) |
| 在房间里使用 AI | [配置房间助手](#room-ai) |
| 只体验基础引擎操作台 | [Windows QuickStart](#engine-demo) |

<a id="play-stumpsville"></a>

## 安装并开一局树桩镇

克隆[项目仓库](https://github.com/sd5913/OnlineCOC)，或下载完整 ZIP 并解压到较短的可写路径，如 `D:\OnlineCOC`。请从解压后的本机目录启动。下文命令均从含 `launcher-config.json` 的项目根目录执行。

1. **安装。** 在 Windows x64 上双击 [setup-game.cmd](engineering/setup-game.cmd)。首次运行会联网下载 Python，检查 Tk，并将锁定依赖安装到 `engineering/.venv`。看到 `GAME_RUNTIME_READY` 后即可打开游戏面板和 AI 管理器。
2. **开房。** 双击 [start-panel.cmd](rulepacks/stumpsville/start-panel.cmd)，选择「本机」，创建存档槽位，设置初始密码，点击「启动房间」。首次体验可取消勾选「AI 助手」。保持房主面板运行，默认本机地址为 `http://127.0.0.1:8899`。
3. **入座。** 用 `kp` 登录，在「房间」点击「一键开场」。再开一个根地址作为独立登录页，用 `player1` 和槽位初始密码登录，提交预设角色。主持在「裁决」批准，玩家检查背包并确认准备。保留一个已登录的主持页面处理自动裁决。
4. **找到第一条线索。** 在 **01 入口隧道**选择「观察地面 → 仔细观察」。个人手记会出现「入口地面的压痕」，玩家地图会出现 **02 主门**。首局可以约定记录两条不同发现、带回一件新物品、全员返回入口。想继续主线，可去庭院接委托。[玩家简明指南](rulepacks/stumpsville/docs/current/player-guide.md)
5. **下次接着玩。** 在面板点击「停止房间」，下次选择同一槽位即可恢复，原槽位继续使用其活动规则。存档位于 `rulepacks/stumpsville/runtime/slots/`。[备份与恢复](rulepacks/stumpsville/docs/current/usage.md)

<details>
<summary>核验、修复或手工安装依赖</summary>

在根目录运行 `.\engineering\setup-game.cmd -VerifyOnly`。安装失败时查看 `engineering/.runtime/game-setup-logs/`，修正报错后重跑安装器。

手工安装请使用包含 Tk 和 Python 启动器的 Windows x64 完整版 CPython 3.14.2，在 PowerShell 运行以下命令。首次下载依赖需要联网，Lua 随依赖安装。

```powershell
py -3.14 -m venv engineering/.venv
.\engineering\.venv\Scripts\python.exe -m pip install --require-hashes -r engineering/requirements-runtime.lock
.\engineering\.venv\Scripts\python.exe -m pip check
```

</details>

<a id="multiplayer"></a>

## 邀请玩家

新槽位的示例账号共用初始密码。邀请他人前，请在房主面板「账号管理」中为玩家创建独立账号或分别改密。

### 同一局域网

房主运行 [start-lan.cmd](rulepacks/stumpsville/start-lan.cmd)，选择局域网网卡与槽位，启动房间。将面板中的**玩家访问地址**发给同一网络的玩家，各自在浏览器用游戏账号登录。连不上时核对网卡、监听端口和连接诊断。`127.0.0.1` 只在房主电脑上有效。[局域网说明](rulepacks/stumpsville/docs/current/usage.md)

### 异地网页联机

1. **安装联网环境。** 房主先准备上述游戏环境。在 Windows 10/11 x64 上运行维护者单独分发的 `OnlineCOC-Network-Setup.exe`，选择**含 engineering 的项目根目录**，点击「一键安装」。安装器可离线安装；如提示占用，正常停止分享后在同一目录重试。[安装器说明](engineering/network-web/installer/README.md)
2. **取得发布权限。** 向平台维护者取得目录配置、发布授权与 CA 公钥证书。配置默认位于 `engineering/network-p2p/local/client-config.json`。使用测试平台时，玩家需从可信渠道取得并信任测试 CA 的公钥证书。[自建服务部署](docs/current/engineering/network-p2p.md)
3. **房主邀请。** 运行 [start-web.cmd](rulepacks/stumpsville/start-web.cmd)，选择槽位并启动。从「网页分享与连接」复制开房串，到平台「创建房间」粘贴，设置公开性和密码。一次性开房串由房主认领，十分钟有效。发给玩家的是**加入网址和八位房间代号**，游戏账号另行分配。
4. **玩家登录。** 用支持 WebRTC 的浏览器登录平台，输入代号、房间密码（如有），按设置等待批准。点「进入游戏 → 连接房主」，用**游戏账号**登录。在全局频道互发消息确认连接。游玩期间保持房主面板与主持游戏页运行。[树桩镇网页联机](rulepacks/stumpsville/docs/current/web.md)

<details>
<summary>从源码安装联网模块，或使用旧 P2P 客户端</summary>

只有源码时，安装含 `py` 启动器的 Python 3.14 x64，然后在根目录 PowerShell 运行：

```powershell
.\engineering\network-p2p\setup.ps1
.\engineering\network-p2p\.venv\Scripts\python.exe -m pip install --no-deps -e engineering/network-web
```

旧 P2P 客户端提供基础状态与聊天。房主先启动宿主，再运行 `engineering/network-p2p/play.cmd`、选择宿主并发布。玩家在装有 Python 3.14 x64 的 Windows 上解压房主提供的 ZIP，运行 `play.cmd` 联网完成首次安装，然后用完整加入信息连接、登录并下载内容。[旧 P2P 客户端说明](engineering/network-p2p/README.md)

</details>

<a id="room-ai"></a>

## 在房间中使用 AI

1. 完成共用环境安装后，房主运行 [start-ai-manager.cmd](rulepacks/stumpsville/start-ai-manager.cmd)。在「服务商」启用 DeepSeek 或兼容服务，填写地址和模型 ID，在凭据栏保存密钥。「测试连接」会产生实际服务用量。
2. 运行 [start-ai.cmd](rulepacks/stumpsville/start-ai.cmd)，或在面板勾选「AI 助手」。启动槽位，以 `kp` 登录，在「AI 设置」选择服务商、开启调用并指定允许外发的资料，按需开放玩家对话。在独立管理器中，也可以在「房间与会话」添加本机宿主地址，以 KP 登录后设置同一房间。
3. 在主持「裁决」页询问「根据当前房间资料，我该如何开始这局游戏？」，查看会话中的回答。获准的玩家可打开个人 AI 标签。修改规则或发放物品时，主持在裁决队列查看改动、风险及执行结果。

如果收不到回答，依次检查服务商连接测试、选中的模型、房间调用与外发权限，以及任务状态。[管理器说明](docs/current/engineering/ai-manager.md) · [配置包接入](rulepacks/stumpsville/docs/current/integrations.md)

<a id="engine-demo"></a>

## 用 Windows QuickStart 体验基础引擎

打开完整项目中的 **QuickStart** 文件夹，先运行 [安装依赖.exe](QuickStart/安装依赖.exe)，再运行 [启动OnlineCOC.exe](QuickStart/启动OnlineCOC.exe)。首次设置至少八位密码，然后在 `http://127.0.0.1:8765` 用 `kp`、`player1` 或 `player2` 登录。多账号同时登录时请用独立浏览器配置文件。关闭启动窗口即可停止宿主。此演示使用 `engineering/.runtime` 下的独立环境。[桌面工具说明](docs/current/engineering/desktop-tools.md)

## 验证记录

| 场景 | 覆盖范围与证据 |
| --- | --- |
| 首次安装 | 无缓存 Windows 安装已检查 Tk 和 29 项依赖。基础操作台验证了登录、Lua 行动同步及重启恢复。[共用安装](engineering/acceptance/ai-install-guide/README.md) · [基础引擎](engineering/desktop/acceptance-install-audit/README.md) |
| 多人联机 | 联网安装器在解除占用后重试成功。同机双浏览器通过 WebRTC 验证了 18 项树桩镇行动。此前曾验证公网 TURN 与远程主持，独立家庭或移动网络的真人试玩仍待补验。[安装器](engineering/network-web/acceptance/2026-11-26-firstplay.json) · [双浏览器](rulepacks/stumpsville/tests/web-results.json) · [远程主持](rulepacks/stumpsville/tests/remote-kp-cloud-results.json) |
| 房间 AI | 入门验收使用模拟服务，重试后请求进入待审核状态。真实 DeepSeek 调用记录来自此前联测。[入门验收](engineering/acceptance/ai-install-guide/README.md) · [真实服务记录](engineering/acceptance/ai-runtime/deepseek-live.json) |

## 来源与开发入口

- 树桩镇适配 Isaac Williams / Losing Games 的 Mausritter SRD。规则、第三方冒险参考、原创分支及生成式运行插画分别标注来源。分发素材前请核对其对应许可。[来源与许可](rulepacks/stumpsville/docs/current/sources.md) · [运行插画](rulepacks/stumpsville/assets/runtime/README.md)
- 项目使用 Python、FastAPI、WebSocket、Lua/Lupa 和浏览器 WebRTC。提交、测试、已知问题和 AI 协作过程见[开发记录](PROCESS.md)、[共享问题与计划](docs/plans/Issues/README.md)和[首测验收](docs/current/engineering/first-test-acceptance.md)。
- 规则作者可从[Lua 编写说明](docs/current/engineering/lua-authoring.md)、[配置包目录](rulepacks/README.md)和[开发者参考](docs/current/engineering/developer-reference/README.md)开始，另有[《激光与情感》](rulepacks/lasers-and-feelings/README.md)。
- 运维与工程入口包括[基础宿主](docs/current/engineering/first-test.md)、[聊天室](docs/current/engineering/chat-backend.md)、[桌面房间管理器](tools/room-manager/README.md)和[账号工具](tools/host-accounts/README.md)。协作前查看[工程登记](docs/current/engineering/hierarchy.md)、[文档规范](docs/standards/document-maintenance.md)和[文档索引](docs/README.md)。
