# OnlineCOC · 线上跑团

[English](README.md) · [下载 Windows x64 体验包](https://github.com/sd5913/OnlineCOC/releases/download/v0.1.0-preview.2/OnlineCOC-Win64-v0.1.0-preview.2.zip) · [v0.1.0-preview.2 版本说明](https://github.com/sd5913/OnlineCOC/releases/tag/v0.1.0-preview.2)

房主在 Windows 电脑上开桌，朋友用浏览器入座。推荐从 **《树桩镇》** 开始，带一队小鼠走进入口隧道，寻找线索，一起揭开地图。

**宣传片 · 32 秒**

https://github.com/user-attachments/assets/77f2f9d5-764e-4253-a489-76faf2667087

<a id="play-stumpsville"></a>

## 第一次开局

1. 在 Windows 10/11 x64 上，将体验包完整解压到较短的可写路径，如 `D:\Games`。双击 `OnlineCOC-preview\Start.cmd`，首次运行会离线安装随包依赖。
2. 选择「本机树桩镇」，创建存档槽位，设置至少八位密码并启动房间。首次体验可关闭 AI。
3. 用 `kp` 登录，点「一键开场」。另开标签页，用 `player1` 和槽位密码登录，提交角色。主持在「裁决」批准，玩家确认准备。
4. 在入口隧道选择「观察地面 → 仔细观察」，打开手记和地图查看发现。游玩期间保持房主面板和主持页运行。结束时在面板停止房间，下次选同一槽位即可继续。

<details>
<summary>观看开局指南 · 1 分 45 秒 · 中文旁白，中英文字幕</summary>

https://github.com/user-attachments/assets/b236b238-37fa-4cf6-8eb6-e6061aa46a11

</details>

<a id="multiplayer"></a>
<a id="room-ai"></a>

## 联机与 AI

| 场景 | 操作 |
| --- | --- |
| 同一局域网 | 在「联网设置」选择局域网网卡，将玩家访问地址发给朋友，并分配各自的游戏账号。[局域网说明](rulepacks/stumpsville/docs/current/usage.md) |
| 异地游玩 | 配置平台发布令牌和可信 HTTPS，再分享加入网址与房间代号。[网页开房指南](rulepacks/stumpsville/docs/current/web.md) |
| 房间 AI | 在「AI 设置」填写房主自己的 DeepSeek API Key，在房间启用 AI，并由主持选择允许外发的资料。调用使用房主额度。[AI 使用说明](rulepacks/stumpsville/docs/current/integrations.md) |

<a id="from-source"></a>
<a id="engine-demo"></a>

## 从源码运行

在完整仓库中运行 [setup-game.cmd](engineering/setup-game.cmd)，首次安装需联网。看到 `GAME_RUNTIME_READY` 后运行 [start-panel.cmd](rulepacks/stumpsville/start-panel.cmd)。Windows 体验包已包含多人战斗与地图缩放、复位，基于 [217039b](https://github.com/sd5913/OnlineCOC/commit/217039bc179246c1eb2b0bd6156cd153176ccb20) 构建。[基础引擎 QuickStart](docs/current/engineering/desktop-tools.md)

[玩家指南](rulepacks/stumpsville/docs/current/player-guide.md) · [来源与许可](rulepacks/stumpsville/docs/current/sources.md) · [开发与 AI 协作记录](PROCESS.md) · [更新日志](UPDATE-NOTES.md) · [玩家反馈](feedback/README.md)
