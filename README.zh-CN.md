# OnlineCOC · 线上跑团引擎

[English](README.md) · [引擎设计](docs/current/design/project-overview.md) · [开发与 AI 协作记录](PROCESS.md) · [更新日志](UPDATE-NOTES.md)

OnlineCOC 是一套用于多人线上跑团的引擎原型。房主电脑负责结算行动、保存房间进度，方便下次继续同一场冒险。玩家通过浏览器入座，只能看到角色有权知晓的信息。

## 引擎结构与设计

| 组成 | 职责 |
| --- | --- |
| 引擎 | Python 宿主检查权限、运行 Lua 规则，并将结果写入房间存档。各玩家可以掌握不同线索，同时共享同一份剧情进度。[引擎架构](docs/current/engineering/first-test.md) |
| 扩展模块 | 局域网网关与网页联机模块负责把玩家接入房主的游戏。可选的房间 AI 能在游玩过程中起草规则改动，交由主持人审核。[工程模块目录](engineering/README.md) |
| 配置包 | 每个包定义具体游戏的规则、内容和玩家界面。《树桩镇》是其中一个实例。[配置包目录](rulepacks/README.md) |

**主持人和玩家**可以在本机试跑、同一局域网开桌，或让异地玩家通过浏览器加入，下次从同一存档继续。**规则作者**可以在配置包中用 Lua 编写一项新行动，在测试房间中试玩，查看实际结算结果。[Lua 编写指南](docs/current/engineering/lua-authoring.md)

<a id="play-stumpsville"></a>

## 配置包体验示例 · 树桩镇

<details>
<summary>展开 Windows 下载、首次开局步骤与演示视频</summary>

以下以 **《树桩镇》配置包**为例。房主需要 Windows 10/11 x64。一台电脑、两个浏览器标签页即可分别体验主持和玩家视角。体验包内含离线安装所需的运行环境。[版本说明](https://github.com/sd5913/OnlineCOC/releases/tag/v0.1.0-preview.2)

**启动示例**

1. 下载 [Win64 体验包 ZIP](https://github.com/sd5913/OnlineCOC/releases/download/v0.1.0-preview.2/OnlineCOC-Win64-v0.1.0-preview.2.zip)。
2. 将整个 ZIP 解压至较短的可写路径，如 `D:\Games`。
3. 双击 `OnlineCOC-preview\Start.cmd`。环境就绪后会显示主菜单。

<a id="from-source"></a>

已有完整源码时，可用以下两步启动：

1. 在联网环境中运行 [setup-game.cmd](engineering/setup-game.cmd)。
2. 看到 `GAME_RUNTIME_READY` 后，运行 [start-panel.cmd](rulepacks/stumpsville/start-panel.cmd)。

**在本机开房**

1. 选择本机游玩模式（体验包主菜单中的「本机树桩镇」）。
2. 在房主面板创建存档槽位。
3. 设置至少八位的初始密码。
4. 点击「启动房间」。

**在一台电脑上分别入座**

1. 用 `kp` 和槽位密码登录房间。
2. 在主持的「房间」页点击「一键开场」。
3. 在第二个浏览器标签页打开房间地址。
4. 用 `player1` 和槽位密码登录。
5. 在玩家页提交预设角色。
6. 在主持页的「裁决」中批准角色。
7. 在玩家页确认准备。

游玩期间保持房主面板和主持标签页打开。角色规则、战斗和地图操作见[《树桩镇》玩家指南](rulepacks/stumpsville/docs/current/player-guide.md)。[存档与恢复](rulepacks/stumpsville/docs/current/usage.md) · [来源与许可](rulepacks/stumpsville/docs/current/sources.md)

<a id="multiplayer"></a>
<a id="room-ai"></a>

**其他使用场景**

- **同一局域网。** 朋友通过房主局域网面板显示的玩家访问地址入座。[局域网设置](rulepacks/stumpsville/docs/current/usage.md)
- **异地游玩。** 房主需要平台发布授权和可信 HTTPS。玩家使用加入网址和房间代号进房。[网页开房指南](rulepacks/stumpsville/docs/current/web.md)
- **房间 AI。** 体验包预设 DeepSeek，使用房主自己的 API Key；允许外发的房间资料由主持决定。[房间 AI 指南](rulepacks/stumpsville/docs/current/integrations.md)

**宣传片 · 32 秒**

https://github.com/user-attachments/assets/77f2f9d5-764e-4253-a489-76faf2667087

**开局指南 · 1 分 45 秒 · 中文旁白，中英文字幕**

https://github.com/user-attachments/assets/b236b238-37fa-4cf6-8eb6-e6061aa46a11

</details>

<a id="engine-demo"></a>

[基础引擎 QuickStart](docs/current/engineering/desktop-tools.md) · [项目文档](docs/README.md) · [玩家反馈](feedback/README.md)
