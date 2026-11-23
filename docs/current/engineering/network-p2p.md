# 公网房间与 P2P 联机

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-13
- 最后更新：2026-11-23
- 关联文档：[快速使用](../../../engineering/network-p2p/README.md)、[目录清单](hierarchy.md)、[房间发现与同步计划](../../plans/room-discovery-p2p-package-sync.md)、[启动编排计划](../../plans/room-launch-orchestration.md)、[云部署调研](../../plans/cloud-server-deployment-research.md)

## 1. 当前实现

独立模块 `engineering/network-p2p`，本机及腾讯CVM当前均为0.2.3，2026-11-23随network-web 0.3.2部署；TURN未重启。开房与加入步骤见[快速使用](../../../engineering/network-p2p/README.md)。0.2.1 增加不可枚举的 `code` 房间、可替换主机 Peer 和浏览器信令入口扩展；平台账号、成员和分组资源由可选 [network-web](network-web.md) 提供，旧 public/private 与整包同步协议保持兼容。

0.2.2增加供可信网页主机适配器调用的 `Upstream.service_request`：显式回环服务、逐玩家Cookie/CSRF、GET/POST、大小与超时限制、拒绝重定向。只有network-web版本2按声明校验后调用；没有把包路径加入旧P2P的通用 `request` 白名单。树桩镇旧P2P入口仍仅基础状态/聊天，完整玩家模式见[包网页说明](../../../rulepacks/stumpsville/docs/current/web.md)。

| 位置 | 职责 |
| --- | --- |
| 云端 CVM | HTTPS 房间目录、发布者认证、租约与准入、WSS 信令、临时 TURN 凭据；coturn 提供 STUN/TURN |
| 房主电脑 | 借用已启动的回环宿主，审批与主机身份签名、隔离玩家登录、转发授权 API、发送玩家内容 |
| 玩家电脑 | 本机可信网页入口、浏览器 WebRTC、内容校验与缓存、隔离玩家页面 |
| 原游戏宿主 | 游戏账号、权限、规则/Lua、命令幂等与回执、权威存档 |

玩家与房主形成星形连接，使用 DTLS/SCTP DataChannel；默认 ICE 同时允许直连与 TURN 候选，可指定仅中转。云端不运行规则或保存游戏包。本模块的旧入口由各电脑本机 Python 服务提供，本机进程单独验证测试 CA；新增免安装玩家入口由 [network-web](network-web.md) 提供，并要求浏览器信任 HTTPS 证书。

## 2. 配置与分发

源码中的浏览器 `WebRtcTransport.stats()` 读取所选候选对，返回候选类型、中转判断、RTT、收发字节/包数、发送丢弃数及可用出站比特率。浏览器未提供的字段返回 `null`，零 RTT 保留为零；只知道一端且不能确认中转时也返回未知。候选对接口不提供 SCTP 重传次数，因此 `retransmittedPackets` 为 `null` 并附 `retransmissionStatus`。不导出 IP、SDP、票据或 TURN 凭据。该源码已随0.3.1/0.2.3部署；原专项证据仍只有指标契约与本机 TCP 测量，不构成公网/中转时延验收，见[引擎性能](engine-performance.md)。

完整项目可先使用[离线依赖安装 EXE](../../../engineering/network-web/installer/README.md)，无需系统预装 Python。原开发安装流程仍可用：Windows 可双击模块 `play.cmd`，缺少独立运行时时自动调用 `setup.ps1`，随后打开联网页面；需要预先安装 Python 3.14 x64（含 `py` 启动器）。升级后需重开联网进程。Ubuntu 24.04 云端使用 Python 3.12；依赖版本见[requirements.lock](../../../engineering/network-p2p/requirements.lock)。新检出先运行模块 `setup.ps1`，再按[示例](../../../engineering/network-p2p/config/client.example.json)准备 `local/client-config.json`；`start.ps1 -Config 路径` 可选其他配置。

| 字段 | 用途 |
| --- | --- |
| directory / caFile | 云端 HTTPS 根地址及可选 CA 公钥；未指定 CA 时使用系统信任链；HTTP 仅限回环测试 |
| statePath | 房主身份、稳定 roomId、会话锁与账号封禁记录 |
| upstream | 原宿主回环 HTTP 地址，默认 `http://127.0.0.1:8765`，GUI 可从识别列表选择 |
| hostDiscoveryPath | 可选宿主注册目录；Windows 默认 `%LOCALAPPDATA%/OnlineCOC/HostControl/` |
| publisherToken | 房主发布凭据，禁止放入玩家包 |
| packagePath | 可选，玩家内容导出目录；留空使用内置状态/聊天入口（默认 general 频道） |
| packageBytesPerSecond | 房主文件发送全局速率，默认 131072 字节/秒 |
| relayOnly | 无界面房主的强制中转选项；GUI 发布由复选框设置 |

`caFile/statePath/packagePath/hostDiscoveryPath` 及云目录的 `stateFile` 相对配置文件所在目录解析。本机真实配置不入库，存放边界见[local 说明](../../../engineering/network-p2p/local/README.md)。

以下命令从项目根目录执行。生成玩家 ZIP：

    engineering/network-p2p/.venv/Scripts/python.exe engineering/network-p2p/scripts/build_player.py

输出 `engineering/network-p2p/dist/onlinecoc-player.zip`，包含客户端源码、版本锁、启动脚本、玩家配置及 CA 公钥；不含房主发布凭据、SSH 密钥或 TURN 主密钥。这是需安装依赖的源码包，玩家步骤见快速使用和包内 README.txt。

发布玩家内容时，先按[distribution 示例](../../../engineering/network-p2p/config/distribution.example.json)列出允许分发的文件，再导出：

    engineering/network-p2p/.venv/Scripts/python.exe -m onlinecoc_p2p export --source PATH_TO_PUBLIC_CONTENT --descriptor PATH_TO_DISTRIBUTION_JSON --output PATH_TO_EXPORTS

将返回目录填入 `packagePath` 后重新发布房间。导出不自动适配原游戏包网页或其自有 HTTP 服务。

### 本机宿主识别

`GET /local/hosts` 仅允许持本机能力令牌且已配置发布凭据的入口访问，沿用 Host/Origin 校验。读取当前用户注册记录及已配置的回环地址，校验进程存活（Windows 同时排除 PID 重用旧记录）与 `/api/v1/capabilities`，忽略坏文件、外网地址、重定向及不可用记录；不会扫描磁盘存档或整个端口范围。

每轮最多读 64 条注册记录，8 个并发探测、单次 1.2 秒超时、3 秒缓存；只返回地址、注册名称/目录及实例标识，不解密或返回管理密钥。优先匹配已配置宿主；未匹配时，单个可用宿主自动选中，多个时由用户选择；原手填地址保留。具体实现见[discovery.py](../../../engineering/network-p2p/src/onlinecoc_p2p/discovery.py)。

## 3. 准入与协议

房间元数据及活动检查点持久化，默认离线/停止分享 24 小时后移除（`roomRetentionSeconds=86400`）；在线待客不回收。旧数据升级给予一天宽限。网页房主还可主动立即解散移除，详见[生命周期](network-web.md#停用保留与主动移除)。租约、会话、申请及票据仅在云端单进程内存中。重启不恢复虚假在线状态；房主每约 15 秒续租，租约 60 秒，重新发布推进 `connectionEpoch`。本机 `statePath` 文件锁阻止同一房间身份被重复占用，崩溃后由操作系统释放；停止联机仅撤下连接，不停止借用的宿主。

云目录为每个 roomId 分配唯一的 8 位 `roomCode`，字符集排除 0、1、I、O；显示为 `ABCD-EFGH`，输入忽略大小写、空白和连字符。短码持久绑定 roomId，重启/撤下后不转分给其他房间；旧目录状态自动补码，在线租约仍不恢复。

`POST /v1/join-intents` 接受 `roomId` 或 `roomCode` 二选一；解析短码后使用同一限流、邀请、密码、审批和票据流程。没有公开的私房短码查询接口，未知、离线或私房凭据错误均返回 `ROOM_UNAVAILABLE`。短码不是准入凭据。

“复制加入信息”生成短码，私房则生成含邀请的 `OCOC1:<房间码>:<邀请>` 文本，玩家一次粘贴后拆分提交；不包含房间密码、游戏账号或本机入口令牌。私有邀请只在房主本机进程内保留，刷新页面后可再次复制。Python 客户端可用 `Player.join(room_code=...)`，浏览器 `WebRtcTransport.connect({roomCode, ...})`；原 roomId 调用兼容。

发布者令牌保存 SHA-256 摘要，房间密码用固定参数 Argon2id；请求按 IP、设备、房间限流。私有房间不进入公开列表；GUI 支持审批、锁定、踢出与封禁，生成的邀请默认一天有效、最多使用 100 次。

| 接口组 | 权限与用途 |
| --- | --- |
| `GET /health`、`GET /v1/rooms` | 健康检查、在线公开列表（每页最多 50） |
| `POST /v1/client-sessions` | 注册临时玩家 P-256 公钥 |
| `/v1/rooms`、`/{rid}/heartbeat`、`/{rid}/lease` | 发布、策略修订、续租、撤下；需发布者凭据或当前租约 |
| `/v1/join-intents`、`/{iid}`、`/{iid}/decision` | 申请者提交/查询自己的申请，当前房主决策 |
| `POST /v1/join-tickets/redeem`、`/v1/members/{iid}/ready 或 release` | 房主兑换一次性票据、确认就绪或释放席位 |
| `POST /v1/turn-credentials`、`WSS /v1/signaling` | 已准入连接领取 600 秒 TURN 凭据，按房间和申请认证后交换 SDP |

完整路由和方法见[directory.py](../../../engineering/network-p2p/src/onlinecoc_p2p/directory.py)。申请/票据有效 60 秒，文件同步席位预留 600 秒。票据绑定玩家公钥、房间、策略版本与连接代次；客户端签署挑战后房主才兑换。房主长期 P-256 身份签署 offer/answer 的 DTLS 指纹；信令拒绝任意转发目标及旧租约。

`control/state/package` 三通道使用有界分帧、背压与接收并发限制：RPC 请求 64 KiB、逻辑响应 2 MiB、线上帧 16 KiB。内容校验并提交 READY 前不能执行游戏命令或订阅状态。

每玩家独立宿主 Cookie/CSRF；仅开放认证、能力/契约、授权视图/查询、命令/计算/回执及基础聊天。方法、路径、选项按[upstream.py](../../../engineering/network-p2p/src/onlinecoc_p2p/upstream.py)白名单处理，不转发任意 URL/请求头、本机管理、备份或包自有服务；权限仍由原宿主裁定。

浏览器[transport](../../../engineering/network-p2p/src/onlinecoc_p2p/web/transport.js)实现 `request(path, options)` 与 `open(onMessage, onClose)`。接入 Client SDK 顺序为：P2P 准入 → 游戏登录 → 内容同步 → `Client.resume()`。断线或授权 reset 时 UI 清空状态并移除玩家 iframe。

## 4. 玩家文件与隔离页面

导出契约为 `packageId/version/entry/files`，只读取显式白名单，生成不可变清单和 SHA-256 blob。拒绝路径穿越、符号链接/junction、硬链接、设备名、大小写冲突、私密目录及可执行/密钥扩展；作者仍须确认文件适合所有获准玩家。

单文件上限 64 MiB、包 512 MiB、清单 10000 项，区块 256 KiB。客户端验证房主签名、区块及完整文件摘要，复用已验证块，完整提交后进入 READY；浏览器用 IndexedDB，Python 验收客户端用磁盘缓存。

玩家 HTML 位于不带 `allow-same-origin` 的 sandbox iframe；CSP 限制外部请求、嵌套页及表单，仅通过 MessageChannel 的受限 request/subscribe 取得授权数据。渲染地址有短期一次性凭据，响应头也设置 sandbox；包页面无法取得发布凭据、宿主 Cookie 或本机控制权限。已交付玩家的文件不能保证远程收回。

本机渲染请求上限为 64 KiB JSON，入口 HTML 应保持小型。支持清单中 HTML src/href 引用的独立 JS/CSS/图片；脚本和样式需预先打包，尚无任意 ES module 相对依赖、CSS url() 资源树改写或动态资源代理。

## 5. 云端部署与 SSH

已用广州 CVM，2 核 2 GiB、3 Mbps、50 GiB、Ubuntu 24.04。实例资料记录到期时间为 **2026-12-13 11:41:20（北京时间）**，续费状态以云控制台为准；IP 和密钥路径仅保存在 `local/`、`tmp/`。

| 入站端口 | 当前用途 |
| --- | --- |
| TCP 22 | SSH，适应出差 IP 变化，来源 0.0.0.0/0；已关闭密码及交互式密码认证 |
| TCP 443 | 合并的 network-web 网页/API、HTTPS 目录、WSS 信令 |
| UDP/TCP 3478 | STUN/TURN，默认客户端路径 |
| TCP 5349 | TURN TLS，仅验证监听与证书握手 |
| UDP 49160–49259 | TURN relay 端口池 |

IPv4 全端口允许已移除，IPv6 拒绝。SSH 使用私钥与严格 known_hosts；初始指纹来自首次连接，尚未在控制台独立核验。默认浏览器未使用 5349，测试 CA 也未加入浏览器 TURN TLS 系统信任；此部署不保证仅允许 TCP 443 出网的网络可用。

`onlinecoc-directory` 和 `onlinecoc-turn` 两个 systemd 服务使用无登录用户 `onlinecoc-net`，限制可写路径、内存及进程数。代码/运行时在 `/opt/onlinecoc-network`，配置/证书在 `/etc/onlinecoc-network`，数据在 `/var/lib/onlinecoc-network`。

coturn 使用短期 HMAC 凭据，用户/总 allocation 配额为 4/64，单 allocation 上限 65536 字节/秒；`bps-capacity=1048576` 是会话预留容量，不能视为全局整形，公网总出口仍受 3 Mbps 限制。拒绝向私网、回环、元数据网段及多播中继；主密钥和发布凭据不写共享日志。

SSH/SCP 继续使用 [server.ps1](../../../engineering/network-p2p/scripts/server.ps1)。当前云端已合并网页模块，更新与回滚须使用 [network-web 部署流程](network-web.md#5-服务器实际部署)。旧 `prepare_deploy.py/install-remote.sh` 仍供纯 P2P 首装，重跑会覆盖当前网页入口；其私密部署包含服务端私钥，禁止分发。部署会重启测试服务，应在无玩家时执行。

## 6. 验收及实用边界

2026-11-22：0.2.3 本地 **43 项通过、11 项环境/云端跳过**，另有网页模块 39 项本地及 1 项公网测试通过，详见[0.3.1 联合记录](../../../engineering/network-web/acceptance/2026-11-22-0.3.1.json)。以下为历史基线，不计入本次重跑。

[0.2.0 验收记录](../../../engineering/network-p2p/acceptance/2026-11-13-0.2.0.json)为 54 项基线，原[0.1 的 46 项记录](../../../engineering/network-p2p/acceptance/2026-11-13.json)保留追溯。2026-11-13 增加网页扩展后，**54 项全部再次通过，零跳过**；本次摘要与网页专项证据见 [network-web 验收](../../../engineering/network-web/acceptance/2026-11-13.json)。

- 短码冲突重试、旧状态迁移与稳定性、私有准入防绕过、离线房间拒绝。
- 本机发现的失效记录/进程、凭据隔离、真实宿主注册；浏览器选择宿主、复制私有加入信息、审批、登录与同步。

- 准入、重放防护、租约/重启、持久封禁、进程锁和本机权限边界。
- 当前真实宿主/Client SDK、双玩家 Cookie 隔离、规则/状态/聊天/幂等/撤权、浏览器发布和隔离页面；停止联机后原宿主仍运行。
- 真实 DataChannel 传输 640000 字节、分块恢复/校验，缓存命中后零重复下载；玩家 ZIP 独立启动且无发布权限。
- 公网短码加入及 UDP/TCP 强制 TURN；Windows↔Ubuntu 强制模式为 `relay/relay`，自动模式本次为 `host/prflx` 直连。

复测先安装模块 `requirements-test.txt` 和 Playwright Chromium，再从模块目录执行：

    $env:PYTHONDONTWRITEBYTECODE='1'
    $env:PYTHONUTF8='1'
    $env:PLAYWRIGHT_BROWSERS_PATH="$PWD/local/browsers"
    $env:P2P_BROWSER_TEST='1'
    $env:P2P_CLOUD_TEST='1'
    $env:P2P_REAL_HOST_TEST='1'
    .venv/Scripts/python.exe -m pytest -q --tb=short --junitxml=local/acceptance/final-0.2.xml

未设开关时对应专项跳过；公网测试创建并撤下临时房间，真实宿主测试使用当前工程运行时和临时存档，执行前按项目规则登记占用。

尚未完成真人独立家庭/移动网络、80 玩家、长期满载及长时 TURN 凭据续期验收。自动重连/ICE restart、房主迁移、运行中换包、缓存 LRU、统一 SessionController 仍在计划中。持久成员快捷重入与账号差异化资源组已由可选 [network-web](network-web.md) 实现，不改变旧模式的整包规则。树桩镇的[完整网页UI/服务](../../../rulepacks/stumpsville/docs/current/web.md)已接入network-web版本2，旧P2P入口仍为[通用宿主基础接入](../../../rulepacks/stumpsville/docs/current/integrations.md)，两者使用借用宿主模式。

## 7. 技术来源

具体接口以源码和验收为准；参考 [aiortc API](https://aiortc.readthedocs.io/en/latest/api.html)、[coturn 官方配置](https://github.com/coturn/coturn/blob/master/examples/etc/turnserver.conf)，查阅日期 2026-11-13。
