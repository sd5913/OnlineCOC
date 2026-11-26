# 网页房间与按需游戏页

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-13
- 最后更新：2026-11-26
- 关联文档：[快速使用](../../../engineering/network-web/README.md)、[P2P 基础](network-p2p.md)、[后续验收](../../plans/browser-room-portal.md)、[域名步骤](../../plans/cloud-server-deployment-research.md#61-在腾讯云取得并接入域名)、[目录清单](hierarchy.md)

## 1. 已实现范围

独立可选模块 `network-web 0.3.2`，复用 `network-p2p 0.2.3`。平台提供 **创建 `/create`、管理 `/manage`、加入 `/join`** 三页，根地址打开加入页。公开列表只含已认领、在线、可加入且设为公开的网页房间；私密、未认领、离线或已解散房间不展示。旧房间默认私密。

公开列表允许未登录浏览，仅提供房间名、包名/版本、代号、席位及密码/审批/邀请标记；规则、人员、完整包信息在准入后查看。底层仍为 `visibility=code`，旧 P2P 列表和加入接口不能绕过平台权限；网页是否公开由独立持久化字段控制。

玩家流程：**平台注册/登录 → 选择公开房间或凭 8 位代号加入 → 房间信息 → 独立游戏页 → P2P 与游戏账号登录 → 按需资源**。加入后持久保存快捷入口，跨设备、服务重启仍有效；房主离线保留带时间的旧摘要，默认 24 小时后移除。

房主粘贴本机开房串创建并绑定平台账号，创建时设置是否公开、是否有密码；管理页可继续调整并处理审批、黑名单和资源授权。公开与密码互相独立，私密房间仍可凭代号准入。房间密码为 1–128 个字符；改密影响首次加入，已有成员保留快捷重入。平台房主身份不等于游戏 KP；封禁撤销准入及连接，解封后须重新加入。目录不可达时，旧连接受最长约 15 秒的授权租约约束。

房间页只显示信息，不连接游戏或下载运行资源。每账号每房间一席；房间页/游戏页分别每 10/8 秒心跳，35 秒超时。关闭房间页不影响游戏，刷新或崩溃后须手动重连。

### 停用保留与主动移除

“不使用”按停止分享、房主信令断开或租约失效计时；在线等待玩家不计入。默认 `roomRetentionSeconds=86400`，可在服务器配置为 1–2592000 秒。离线时间持久化，服务重启不会重置；在线活动每约 60 秒写检查点。首次升级无时间字段的旧房间给予完整一天宽限。

一天内重新连接清除离线计时，沿用身份和成员；到期清理目录、代号、成员/黑名单/认领信息及所有快捷入口。后台每约 2 秒和网页请求前检查；公开列表仍只显示在线房间。房主“解散并移除”立即执行同样清理并撤销连接，旧版已解散记录在升级时清除。服务器备份可能保留旧记录，不等同安全擦除。

删除后后台重发旧身份会失败；房主显式重启适配器时可创建新身份/代号，需要重新认领与加入。此操作不删除账号或房主本机游戏存档。

远程 KP：与玩家一样先通过平台准入，再在游戏页输入宿主配置好的 KP 账密；不要求是平台房主。游戏权限由每条连接的独立宿主会话决定，游戏账号切换不继承上次 KP 权限，平台黑名单和撤权照常生效。配置包须按宿主角色返回界面和授权投影；KP 专属包服务仍必须在服务端校验角色，不能仅靠隐藏按钮。

## 2. 账号与持久化

- **平台账号**：名称为 3–32 位字母、数字、下划线或连字符；密码最低 6 个字符，无组合要求或密码专用上限，仍受请求大小限制。默认开放注册，上限 2000，可配置关闭。采用 Argon2id、受保护 Cookie、CSRF/Origin 校验和限流；会话有效期 7 天，每账号最多 8 个。
- **记住账密**：平台与游戏登录均默认关闭；成功验证后保存到访问者浏览器 `localStorage`，失败不覆盖。平台保存一组，游戏按平台账号和房间隔离。保存的是可回填的明文账密，不含恢复码或会话令牌，不上传记忆副本或跨设备同步；正常认证仍发送必要凭据。退出保留记忆，取消勾选或清除按钮立即删除；禁用存储不影响登录。
- **账号恢复**：注册时一次性显示恢复码，服务端只存摘要；恢复更换密码/恢复码、注销旧会话并撤销游戏连接。未接短信或邮箱。平台密码不交给房主，游戏权限仍由宿主账号决定。

`PortalStore` 通过进程锁、原子替换和 fsync 保存账号、会话、成员、黑名单及摘要，保留上一代 `.backup.json`；损坏时拒启，不自动回退。在线状态和席位不持久化。资源缓存按账号/房间隔离，退出账号或游戏时清理；已查看或另存的内容无法收回。

## 3. 配置包接入与资源协议

Windows x64 的项目部署可使用[离线依赖安装器](../../../engineering/network-web/installer/README.md)，安装 Python 与联机依赖到原启动器使用的 `.venv` 路径；玩家浏览器免安装，游戏宿主依赖另行准备。

声明示例见 [web.json](../../../engineering/network-web/examples/core-table/web.json)：必填 `webVersion`、`package`、`rules`、`modules`、`groups`、`routes`。版本1保持兼容；版本2必须额外提供严格的 `bridge` 声明。当前只接受 `required=["network-web"]`，`optional` 不自动启动服务。

- `startup` 须为 `members` 级别并提供 HTML 入口；其余组可用 `members` 或 `grant`。授权按稳定平台账号检查，未授权组名、清单和摘要不下发。
- `routes` 声明方法、路径和可选 `requires` 资源组，最终与宿主白名单取交集；不代理任意 URL、管理接口或请求头，未就绪的必需组会阻止操作。
- 资源协议 2 使用签名清单、块/文件 SHA-256 和 `resource.manifest/chunk/ready`；启动组就绪即可游玩，其余通过 `resource.load` 加载。房间固定资源版本，更新内容须用新房间身份，不可退回整包协议。
- 导出拒绝穿越、链接、私密路径和可执行文件。单文件最多 64 MiB、每组及发布总量最多 512 MiB；文件传输全房间默认限速 131072 字节/秒，各阶段均校验授权。

可信壳负责登录、连接和缓存；包 UI 在无同源权限的沙箱运行，禁止直接联网、子框架和表单，通过 MessageChannel 的 `request/subscribe/resource.load` 通信。HTML/脚本应预先打包；不支持任意 ESM 相对依赖或 CSS 资源树改写。云端不保存玩家包 HTML。

已适配“首测规则桌面”和 [Stumpsville 0.9.0](../../../rulepacks/stumpsville/docs/current/web.md)。树桩镇完整玩家 UI/包侧 HTTP 已完成本地和公网强制TURN双浏览器联测；网页 AI、真人独立家庭/移动网验收未完成。同一宿主的多种远程入口尚无统一身份/席位管理，当前须选一种。

### 3.1 版本2包服务与存储契约

`bridge` 只允许 `version:1`、`service`、`storage` 三个键。`service` 含1–16条唯一的方法/路径声明；方法限 GET/POST，路径限 `package/` 下小写字母、斜线与连字符（后缀1–60字符）。每项明确 `query`，最多8个参数；名称1–24个小写字母，值须为声明的有限字符串枚举（每参数1–16个值，每值最多64字符）。GET无请求体，POST须为JSON对象。

主机配置必须显式设置 `packageService: {version:1, url, packageId, packageVersion}`，URL只允许回环服务，包ID和版本必须匹配发行描述。网页启动前 GET `/v1/web/capabilities`，要求 `packageBridge=1`、`storageBridge=1`，不满足时拒绝发布版本2房间。

`service.request` 只在已准入、已登录并就绪的控制通道可用；请求仅允许 `path/method/query/body`。每次检查平台授权租约、当前游戏账号 ID 及宿主返回的 `player/kp` 角色。远程可登录预设 KP 账号，角色或账号不匹配返回 `GAME_IDENTITY_INVALID`；不会依据平台房主身份提升权限。逐连接复用真实游戏 Cookie/CSRF，不复用房主会话，不开放任意URL、请求头、重定向或通用commands隧道。HTTP总超时15秒、连接3秒；请求最多64KiB，响应受既有协议上限约束。包服务仍负责动作权限、版本与幂等。

可信壳新增 `bridge.info`、`service.request`、`storage.snapshot`、`storage.write`、`session.leave`。包存储按平台账号、房间、游戏账号、包ID及资源版本隔离；每次读写重新验证当前游戏身份。仅声明的精确键或有前缀的末尾 `*` 可用，禁止根通配；最多16项声明，键最多180字符、值16384字符、每作用域64键/序列化65536字符。存储不可用会拒绝写入，包应在提交重要待办前等待成功；不开放平台账密或会话存储。资源版本变化创建新作用域，包自行校验业务规则修订。

沙箱仍为 `allow-scripts`，没有同源、原生表单导航或直接联网权限。游戏挂载后可信外壳只保留连接栏及离开入口，包占据其余视口。含交互表单的包应以DOM事件实现本地提交，不能请求放宽沙箱。

### 3.2 开房串与配置包管理页

配置包启动 `WebHost` 后，可调用 `await adapter.prepare_creation()` 刷新并取得开房串；使用 CLI 子进程的包可调用：

```python
from onlinecoc_web.creation import export_room_setup
setup_string = export_room_setup(state_path)
```

也可运行 `onlinecoc-web room-setup --state-path <房间状态目录>`，或读取 `web-entry.json` 的 `creationString`。读取方法不刷新有效期；过期须由运行中的适配器重新生成，或重启适配器。CLI 仅在显式导出时输出开房串，正常启动日志不输出它。

开房串格式为 `OCOC-ROOM1.` 加 Base64URL JSON，包含版本、平台 Origin、房间代号及一次性认领凭据；Base64 不是加密。服务端校验所属平台、主机在线、十分钟有效期及单次使用。解析预览不创建房间；提交创建才绑定账号并保存公开/密码设置，重复或并发消费仅一次成功。资源与游戏仍由运行中的房主提供。

**建议配置包把联网功能集中在独立管理页面**：启停分享、连接状态、“复制开房串”、打开平台创建/管理页。复制按钮从本机受权接口取得上述返回值，再调用浏览器剪贴板 API；剪贴板不可用时显示只读文本供手动复制。包作者负责本机/KP 授权与按钮实现，不把该方法开放给玩家沙箱，不记录或分享开房串；其中不包含发布令牌、SSH 密钥或游戏账密。现有包不会自动新增按钮，旧认领入口仍兼容。

## 4. API 与配置

网页和 API 同源，前缀 `/v1/web/`：

| 路径 | 用途 |
| --- | --- |
| `GET capabilities` | 包/存储桥、开房/公开列表能力及 `roomRetentionSeconds` |
| `POST auth/{register,login,recover,logout}`、`GET me` | 平台账号与会话 |
| `GET public-rooms?offset=0` | 每页最多 50 个公开房间，返回 `nextOffset` |
| `POST rooms/preview、rooms/create` | `setupString` 解析；创建另传 `public` 布尔值及 `password`（空串为无密码） |
| `GET rooms`、`POST join、claim` | 个人快捷房间（含 owner 标记）、代号加入、旧版认领兼容 |
| `POST rooms/{rid}/presence` | 授权摘要与人员 |
| `POST rooms/{rid}/manage` | 审批/黑名单/资源/解散移除（`action=close`）；`action=settings` 传 `public`、`passwordMode=keep/set/clear`，set 时传 password |
| `POST host/{rid}`、`host/{rid}/guard` | 主机发布摘要与续期授权 |
| `POST game/{session,join,ping,leave}` | 游戏席位、心跳与退出 |

页面另有房主管理 `/manage/{rid}`、成员信息 `/room/{rid}`、独立游戏 `/game/{rid}`；静态资源与隔离壳为 `/assets/*`、`/sandbox.html`。URL 不放密码、邀请或票据；目录/WSS/TURN 沿用 P2P 协议。

主机新增 `webPackagePath`、`webPolicy`，`statePath` 与旧 P2P 房间分开。策略支持 `approvalRequired/passwordVerifier/invitationHash`，默认凭代号加入；邀请为共享凭据，撤换只影响后续首次加入。`fileBytesPerSecond` 控制资源速率。平台创建或修改设置后，主机重新发布不会覆盖平台已保存的准入策略。

`host --stop-file <路径>` 可选本机停止信号；文件出现时优雅撤销房间并退出适配器，保留借用宿主。版本2还需上述 `packageService` 配置；版本1不得声明该服务。

服务端新增 `webStateFile`，可选 `publicOrigin/registration/maxAccounts/roomRetentionSeconds`。示例见模块 `config/`；真实配置和证书放 `local/` 或服务器受限目录。域名接入时同步 Origin、目录地址、证书和 TURN 地址。

## 5. 服务器实际部署

沿用腾讯广州 CVM：Ubuntu 24.04、2 核 2 GiB、3 Mbps；未增加数据库、COS 或 CDN。

2026-11-23 已部署 0.3.2 / 0.2.3，release 为 `/opt/onlinecoc-network/releases/web-20261123T020818Z`，回滚备份为同名 `rollback/` 目录；严格 CA HTTPS 与 40 个运行源码摘要核对通过。部署时 443 活跃连接为 0，沿用停服备份流程，TURN 服务保持运行。本轮未改变账号或房间数据结构。

| 服务 / 目录 | 内容 |
| --- | --- |
| `onlinecoc-directory.service` | 网页、账号/成员/黑名单、摘要、目录/WSS、临时 TURN 凭据；TCP 443 |
| `onlinecoc-turn.service` | coturn 中转；UDP/TCP 3478、TCP 5349、UDP 49160–49259 |
| `/opt/onlinecoc-network/` | `releases/web-时间/` 代码与 venv、`current-web-release` 标记、`rollback/` 更新备份 |
| `/etc/onlinecoc-network/` | `directory.json`、HTTPS/TURN 证书私钥及 `turnserver.conf` |
| `/var/lib/onlinecoc-network/` | 原目录/TURN 数据、`web-accounts.json` 及其备份/锁 |
| `/home/ubuntu/onlinecoc-web-deploy/` | 源码部署包与安装脚本 |

服务使用 `onlinecoc-net` 受限用户与 systemd 限制，TCP 22 用于密钥 SSH。**游戏后端、Lua、存档、素材、包侧服务和 AI 密钥均留在房主本机。**

### 更新、备份与恢复

使用 P2P 独立 Python 运行 [prepare_deploy.py](../../../engineering/network-web/scripts/prepare_deploy.py)，生成 `engineering/network-web/local/web.tar.gz`；经 [server.ps1](../../../engineering/network-p2p/scripts/server.ps1) 上传，再执行服务器部署目录的 `install-remote.sh`。须在无玩家时更新：脚本准备环境、停服备份并切换网页服务，失败还原 service/config；TURN 不重启。**勿重跑旧 P2P 安装脚本，否则会覆盖网页入口。**

`.backup.json` 仅为上一代。长期备份须停服保存状态目录、配置目录及 release 标记；恢复前保留现状，恢复同一代数据/配置与匹配代码，属主 `onlinecoc-net`、状态目录 0700、账号文件 0600。单独回退账号文件会影响黑名单/会话，须审查并注销旧会话后再开放；重启后主机重新发布，玩家重新连接。

## 6. 验收与边界

2026-11-26 [入门与安装复核](../../../engineering/network-web/acceptance/2026-11-26-firstplay.json)：离线 EXE 首次安装、运行占用拒绝后重试通过；网页模块 39 项通过、3 项云端跳过。同轮 Stumpsville 双浏览器本机 WebRTC、18 预设及可见行动结果由配置包会话提供并单列来源。新增[目录选择/失败重试教学](../../../engineering/network-web/installer/README.md)与[首次网页互动](../../../engineering/network-web/README.md#树桩镇第一次网页互动)。本轮未复核公网可用性、计费或证书状态；以下部署与公网结果保留其原验收日期。

[0.3.2 验收记录](../../../engineering/network-web/acceptance/2026-11-23-0.3.2.json)：网页模块 39 项通过、3 项云端用例跳过；树桩镇新增[远程 KP 专项](../../../rulepacks/stumpsville/tests/remote-kp-results.json)及原双玩家 18 预设回归通过，独立验证游戏 KP 权限与平台房主身份分离。另行[公网强制 TURN 主持流程](../../../rulepacks/stumpsville/tests/remote-kp-cloud-results.json)通过，包括同平台账号切换游戏角色后权限隔离；首次页面加载超过 60 秒，调整测试等待上限为 180 秒后通过，不等同独立网络或性能验收。下方 0.3.1 为上次安装器/生命周期基线，不重复计数。

0.3.1：网页本地 **39 项通过、3 项云端跳过**；P2P 本地 **43 项通过、11 项环境/云端跳过**。另行执行 **1 项公网三页浏览器测试通过**，覆盖公开/密码、私密切换、权限及解散后双方快捷入口移除。一天到期使用模拟时间边界测试，覆盖 86399/86401 秒、重连清除计时、重启保留期限及旧数据宽限；不声称已实等 24 小时。严格 CA HTTPS 与 40 项部署源码一致。详见[本次记录](../../../engineering/network-web/acceptance/2026-11-22-0.3.1.json)。

离线 EXE 实测首次/重复安装、中文空格路径、无系统 Python 路径、运行占用拒绝、配置保留、两个 CLI 及 WebRTC 自检；未在另一台干净实体电脑人工验收。旧版与树桩镇公网 TURN 记录见[验收入口](../../../engineering/network-web/acceptance/README.md)，不计作本次重跑。`WEB_BROWSER_CHANNEL=msedge` 可使用已安装 Edge。

目前使用测试 CA：云测浏览器显式允许测试证书，Python/房主仍校验 CA。正式域名/可信 HTTPS、真人独立家庭或移动网、手机/Safari、长期负载及跨设备长时恢复尚未验收，见[后续计划](../../plans/browser-room-portal.md)。不提供云端游戏托管。
