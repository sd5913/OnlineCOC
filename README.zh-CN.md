# OnlineCOC · 线上跑团

[English](README.md) · [下载 Windows x64 体验包](https://github.com/sd5913/OnlineCOC/releases/download/win64-preview-e5b3244/OnlineCOC-Windows-x64-preview-e5b3244.zip) · [版本说明与字幕](https://github.com/sd5913/OnlineCOC/releases/tag/win64-preview-e5b3244) · [玩家反馈](feedback/README.md)

房主在 Windows 电脑上开桌，朋友用浏览器入座。第一次游玩推荐 **《树桩镇》**：带一队小鼠进镇探路，把发现写进手记。玩家决定下一步行动，主持人（界面称 **KP**）负责裁决，进度保存在房主电脑上。

**宣传片 · 32 秒。** 和同伴在入口隧道找到线索，再看一条临时规则如何改变玩家的检定。AI 段使用模拟服务提供的候选规则，主持批准与玩家检定均为实机画面。

https://github.com/user-attachments/assets/77f2f9d5-764e-4253-a489-76faf2667087

[第一次开局](#play-stumpsville) · [邀请玩家](#multiplayer) · [使用房间 AI](#room-ai) · [从源码运行](#from-source)

<a id="play-stumpsville"></a>

## 第一次开局

**房主环境**为 Windows 10/11 x64、PowerShell 5.1 或更高版本、.NET Framework 和浏览器。体验包内含 Python 和游戏依赖，首次安装可离线完成。一台电脑即可分别尝试主持与玩家视角。

1. **启动。** 下载 [Windows 体验包 ZIP](https://github.com/sd5913/OnlineCOC/releases/download/win64-preview-e5b3244/OnlineCOC-Windows-x64-preview-e5b3244.zip)，完整解压到较短的可写路径，如 `D:\Games`。双击 `OnlineCOC-preview\Start.cmd`，环境就绪后选择菜单首项「本机树桩镇」。
2. **开房。** 在房主面板选择本机游玩，创建存档槽位，设置至少八位初始密码并启动房间。首次可关闭 AI 助手。保持面板运行，默认地址为 `http://127.0.0.1:8899`。
3. **入座。** 用 `kp` 登录，在「房间」点「一键开场」。另开标签页，从房间根地址用 `player1` 和槽位密码登录，提交预设角色。主持在「裁决」批准，玩家检查背包并确认准备。游玩期间保持主持页面打开。
4. **寻找线索。** 在 **01 入口隧道**选择「观察地面 → 仔细观察」。玩家手记会出现「入口地面的压痕」，地图会揭示 **02 主门**。想继续主线，可去庭院接委托。[玩家简明指南](rulepacks/stumpsville/docs/current/player-guide.md)
5. **继续存档。** 在面板停止房间，下次选同一槽位。备份前先停服，体验包存档位于 `userdata/rooms/`。试用其他版本时保留旧目录。[版本说明与校验值](https://github.com/sd5913/OnlineCOC/releases/tag/win64-preview-e5b3244)

**开局指南 · 1 分 45 秒。** 从解压启动，到主持批准角色、玩家发现线索，再到重开同一存档。两支视频均有中文旁白与中英文字幕。

https://github.com/user-attachments/assets/b236b238-37fa-4cf6-8eb6-e6061aa46a11

<a id="multiplayer"></a>

## 邀请玩家

先在房主面板「账号管理」中为玩家创建独立游戏账号，或分别修改示例密码。体验包的联机入口位于主菜单「联网设置与安装」。

| 玩家位置 | 房主操作 | 玩家操作 |
| --- | --- | --- |
| 同一局域网 | 选择局域网网卡和槽位，启动房间，复制**玩家访问地址**。 | 用浏览器打开该地址，以游戏账号登录。 |
| 异地网络 | 安装随包联网环境，填写平台目录地址、发布令牌和所需的可信 CA。启动网页房间，在平台认领开房串。 | 登录平台，输入八位房间代号及房间密码（如有），选择「进入游戏 → 连接房主」，再用游戏账号登录。 |

一次性开房串由房主认领，十分钟有效。发给玩家的是加入网址和房间代号。测试平台使用项目 CA，需从可信渠道取得公钥证书。同网玩家连接失败时，先核对网卡和端口；玩家电脑上的 `127.0.0.1` 指向玩家自己。[局域网说明](rulepacks/stumpsville/docs/current/usage.md) · [网页联机说明](rulepacks/stumpsville/docs/current/web.md) · [自建服务](docs/current/engineering/network-p2p.md)

<a id="room-ai"></a>

## 使用房间 AI

1. 从体验包菜单打开「AI 设置」。DeepSeek 服务地址和模型已预填，房主只需填写自己的 API Key。密钥保存在当前 Windows 用户的受保护存储中。「测试连接」和模型调用会使用房主的服务商额度。
2. 在房主面板启用「AI 助手」。以 `kp` 登录，选择服务商，开启调用并指定允许外发的房间资料，按需开放玩家对话。
3. 可先询问「根据当前房间资料，我该如何开局？」。想临场引入新规则时，主持查看候选改动和风险，批准发布后让玩家在原房间试用。收不到回答时，依次检查连接测试、房间权限与任务状态。[AI 管理器](docs/current/engineering/ai-manager.md) · [树桩镇 AI 接入](rulepacks/stumpsville/docs/current/integrations.md)

<a id="from-source"></a>

## 从源码运行

要尝试最新的战斗规则与地图控制，可使用 `main` 源码。可下载的体验包基于 [e5b3244](https://github.com/sd5913/OnlineCOC/commit/e5b3244aaa30ba7905bcf8f4bf57b28c7a76a652) 构建。

| 场景 | 源码入口 |
| --- | --- |
| 安装 | 克隆仓库或完整解压源码 ZIP 到较短的可写目录。在项目根目录运行 [setup-game.cmd](engineering/setup-game.cmd)，首次联网下载 Python 和锁定依赖，等待出现 `GAME_RUNTIME_READY`。 |
| 启动或恢复 | 运行 [start-panel.cmd](rulepacks/stumpsville/start-panel.cmd)，按上面的开房与入座步骤操作。源码版存档位于 `rulepacks/stumpsville/runtime/slots/`。 |
| 邀请玩家 | 使用 [start-lan.cmd](rulepacks/stumpsville/start-lan.cmd) 或 [start-web.cmd](rulepacks/stumpsville/start-web.cmd)。网页模式需先按下方说明准备独立联网环境。[联网安装器](engineering/network-web/installer/README.md) |
| 配置 AI | 打开 [start-ai-manager.cmd](rulepacks/stumpsville/start-ai-manager.cmd)，启用服务商，填写地址、模型和房主密钥。运行 [start-ai.cmd](rulepacks/stumpsville/start-ai.cmd)，或在房主面板启用 AI。 |

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

<details>
<summary>从源码安装联网模块，或使用旧 P2P 客户端</summary>

只有源码时，安装含 `py` 启动器的 Python 3.14 x64，然后在根目录 PowerShell 运行：

```powershell
.\engineering\network-p2p\setup.ps1
.\engineering\network-p2p\.venv\Scripts\python.exe -m pip install --no-deps -e engineering/network-web
```

旧 P2P 客户端提供基础状态与聊天。房主先启动宿主，再运行 `engineering/network-p2p/play.cmd`、选择宿主并发布。玩家在装有 Python 3.14 x64 的 Windows 上解压房主提供的 ZIP，运行 `play.cmd` 联网完成首次安装，然后用完整加入信息连接、登录并下载内容。[旧 P2P 客户端说明](engineering/network-p2p/README.md)

</details>

<a id="engine-demo"></a>

<details>
<summary>用 Windows QuickStart 体验基础引擎</summary>

打开完整项目中的 **QuickStart** 文件夹，先运行 [安装依赖.exe](QuickStart/安装依赖.exe)，再运行 [启动OnlineCOC.exe](QuickStart/启动OnlineCOC.exe)。首次设置至少八位密码，然后在 `http://127.0.0.1:8765` 用 `kp`、`player1` 或 `player2` 登录。多账号同时登录时请用独立浏览器配置文件。关闭启动窗口即可停止宿主。此演示使用 `engineering/.runtime` 下的独立环境。[桌面工具说明](docs/current/engineering/desktop-tools.md)

</details>

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
