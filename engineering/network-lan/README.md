# OnlineCOC 局域网联网模块

独立 HTTP/WebSocket 网关，连接已运行的本机宿主。模块不导入后端、不读写存档、不执行游戏规则。设计、权限边界及限制见[工程文档](../../docs/current/engineering/network-lan.md)。

常用 GUI 在[Python 房间管理器](../../tools/room-manager/README.md)的“局域网联机”页；打包 EXE 支持 `--lan` 单独打开面板。

## 第一次让玩家加入

1. 房主先用项目原入口启动游戏宿主，确认本机能够登录，并准备玩家各自的游戏账号。
2. 使用已有发布包时，保留整个 `tools/room-manager/dist/RoomManager/` 目录，双击其中 `RoomManager.exe`，进入“局域网联机”。该发布目录自带 Python/Tk 运行时。源码安装方式见下文。
3. 填写实际宿主地址（例如 `http://127.0.0.1:8765`）、房主当前网卡 IPv4 和共享端口 `8877`，确认可信网络后启动。不要把玩家电脑地址填入网卡栏。
4. 把面板给出的共享地址发给同一可信局域网内的玩家；玩家在浏览器打开地址、使用自己的游戏账号登录，在通用操作台发送测试聊天或执行获准操作，由另一账号确认结果。
5. 不再分享时停止网关；原游戏宿主继续运行。需要停止游戏时回到原启动入口操作。

玩家用共享地址访问通用操作台，无需安装 LAN Python 模块。该网关不提供房间列表、房间密码/审批或玩家配置包下载，也不转发配置包自己的页面与服务；游戏账号认证由宿主处理。需要配置包页面时使用该包明确支持的入口，需要公网玩家包同步时见 [P2P](../network-p2p/README.md) 或 [网页模块](../network-web/README.md)。

## 源码安装与故障重试

独立安装与启动（项目根目录）：

```powershell
python -m pip install -r engineering/network-lan/requirements.lock
python -m pip install --no-deps -e engineering/network-lan
python -m onlinecoc_lan --gui
# 或独立命令行运行，按实际宿主与网卡填写地址：
python -m onlinecoc_lan --upstream http://127.0.0.1:8765 --bind 192.168.1.20 --port 8877
```

其他电脑连接 `http://192.168.1.20:8877`。此地址仅为示例，必须替换为当前机器实际 IP。HTTP 仅用于可信局域网；Windows 防火墙端口放行由操作者处理。Ctrl+C 停止网关，原宿主继续运行。默认 CLI 只绑定回环，需明确指定 LAN 地址才会开放局域网。

| 现象 | 处理后重试 |
| --- | --- |
| 源码安装网络失败/缺少 aiohttp | 在同一 Python 环境重新执行上面两条 pip 命令，成功后再启动；不要用一个环境安装、另一个环境运行 |
| 上游不可用或协议错误 | 先在房主本机确认宿主地址正确且已启动，再启动网关；网关不会代为开房 |
| 端口被占用 | 更换共享端口，或关闭占用该端口的自有网关后再启动；新地址需重新发给玩家 |
| 登录失败 | 核对宿主中的游戏账号和密码，在当前页面重新登录；LAN 不另设一套游戏账号 |
| 房主能打开，其他设备打不开 | 确认两端同网段、使用实际网卡地址、不是 `127.0.0.1`，并检查 Windows 防火墙和访客 Wi-Fi 隔离 |

2026-11-26 使用真实宿主和两个独立玩家 Cookie 会话验证了端口占用后重试、错误密码后重试、HTTP 聊天与另一账号读取、WS 快照、命令幂等、禁止 host-control，以及停止/重启网关时宿主和登录会话仍可用。[脚本](../network-p2p/acceptance/test_firstplay.py)与[结果](../network-p2p/acceptance/2026-11-26-firstplay.json)在共享的本地首次交互验收中。此次绑定 `127.0.0.1`，所有进程在同一电脑；未重新测试原生面板、发布包安装或跨设备防火墙。历史 WLAN 与原生窗口证据见[工程说明](../../docs/current/engineering/network-lan.md#验证范围)。
