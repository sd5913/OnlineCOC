# 首测工程：运行、模块与运维

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-10-30
- 最后更新：2026-11-22
- 关联文档：[工程索引](README.md)、[编写 Lua](lua-authoring.md)、[验收报告](first-test-acceptance.md)、[施工计划](<../../plans/project planning/first-test-construction-plan.md>)

## 1. 实现范围

本机首测已提供主机权威的房间存档、账号与权限、统一实例/关系、配置与个人进度、文件持久回执、Lua 动态导入与版本激活、可恢复等待流程、素材和备份恢复，聊天室后端，以及浏览器操作台。单个数据目录运行一个 `demo` 房间；多份实验使用不同目录和端口。账号 ID 在首测中等于创建时的登录名，昵称是独立字段，不用于恢复绑定。

本阶段没有数据库依赖。聊天室的结构、权限和接口见 [聊天室后端](chat-backend.md)；公网联机入口已提供基础聊天。完整 COC 等具体规则归配置包实现；地图、逻辑图、2D/3D 空间与地图战斗暂不作为必要能力。回合/实时游戏驱动和完整产品面板仍未实现。局域网可通过[独立 LAN 网关](network-lan.md)接入；公网通过[房间与 P2P 快速使用](../../../engineering/network-p2p/README.md)接入，已部署的目录/STUN/TURN 和验证范围见[工程说明](network-p2p.md)。另有可选 [network-web 网页房间](network-web.md)，提供账号、成员/黑名单和按需游戏页。宿主本身仍仅监听回环，具体包的自有服务与网页需要单独适配。

## 2. 安装与开始游玩

可信组合调用方可使用[房间内原子批次](atomic-batches.md)完成逐项预检和整批提交。支持的 21 种操作、持久随机轨迹、失败丢弃、通知边界及单条记忆事实回执以该文档为准；跨存储和外部等待组合不会静默拆批。

Windows 用户可直接使用根目录的安装与启动 exe，见 [桌面工具说明](desktop-tools.md)。它使用独立的项目内运行时和环境，不依赖下面的手工开发环境；两者默认指向同一份 `.runtime/demo`，不能同时打开该存档。以下命令仍是有效的开发和运维入口。

以下 PowerShell 命令均从项目根目录执行。验证环境为 Windows x64、CPython 3.14.2；Lua 来自 `lupa.lua54`，不需要系统 Lua 或本机 C 编译器。精确版本和平台 wheel 摘要见 [依赖清单](../../../engineering/dependency-manifest.json)。其他 Python/平台组合需另行生成锁并验收。

```powershell
python -m venv engineering/.venv
engineering/.venv/Scripts/python -m pip install --require-hashes -r engineering/requirements-dev.lock
engineering/.venv/Scripts/python engineering/backend/scripts/run.py --data-dir engineering/.runtime/demo init
engineering/.venv/Scripts/python engineering/backend/scripts/run.py --data-dir engineering/.runtime/demo serve
```

`init` 交互输入至少 8 位密码，为 `kp`、`player1`、`player2` 建立首测账号及固定测试对象。自动化可用 `ONLINECOC_BOOTSTRAP_PASSWORD` 环境变量，脚本不会打印它；不要将真实密码写进版本库。只运行服务时可以安装较小的 `requirements-runtime.lock`。

打开 `http://127.0.0.1:8765`。使用三个不同浏览器配置/隔离上下文登录三种身份；普通标签页共用 Cookie，不能视为独立身份。`--port 8766` 可变更端口。服务固定绑定 `127.0.0.1`，不默认暴露到局域网。Ctrl+C 停止服务，重开同一数据目录恢复原房间；不要加自动重载或多 worker 参数。

操作台按主机动作目录生成表单，可执行检定、伤害、转移、组合值、失败问 KP 和限时选择。KP 可以导入完整 Lua/JSON 文件组，检查暂存后激活；旧流程继续使用旧修订。管理区通用命令的可用参数以 [操作契约](../../../engineering/contracts/operations.json) 为准。

需要 AI 时按[模块入口](../../../engineering/ai/README.md)附加 `--ai-config` 与 `--ai-pack`；服务商/加密凭据可用[独立 AI 管理器](ai-manager.md)设置。启用后操作台提供共用审核组件，另可在管理器中连接房间使用会话面板。

## 3. 模块边界

```mermaid
flowchart LR
  UI[操作台 / 自定义前端] --> SDK[Client / Transport]
  SDK --> NET[HTTP + WebSocket 适配器]
  NET --> APP[主机应用接口]
  DIRECT[InProcessTransport] --> APP
  APP --> MODEL[模型约束与权限]
  APP --> CHAT[聊天室领域模块]
  APP --> LUA[独立 Lua 5.4 工作进程]
  APP --> PORT[RoomRepository / IdentityStore]
  PORT --> FILE[FileDataStore]
  APP --> ASSET[Assets 本地素材适配器]
```

`server.py` 处理 Cookie、Origin、CSRF、Host、消息大小及订阅，业务不导入 FastAPI。`gateway.py` 定义应用接口和直接调用适配器。以后增加联机方式，应在可信边界完成身份认证，再调用相同主机接口；客户端不能自行指定权威身份或上传已计算结果。

`onlinecoc_data` 单独维护快照、CAS、查询与导出，不认识角色、Lua、HTTP。`Host(..., store_factory=...)` 可注入同契约实现；默认文件实现，内存实现仅用于测试。`RoomRepository` 和 `IdentityStore` 使用同一存储契约但拥有独立数据集。事务中的完整变更集以新状态快照提交，`expected_generation` 是内部 CAS；网络客户端只接触授权视图 token。

文件提交复用已生成的 payload 规范字节组成原格式封套，避免重复序列化；容量检查每次仍重新扫描实际代文件和暂存文件，使用目录项元数据减少 Windows 上逐文件查询。规范字节、摘要链、CAS、文件同步、原子发布、发布后丢回复恢复及历史无损压缩语义均保持不变，不缓存过期配额或跳过同步。

聊天室以独立 `chat.py` 领域模块管理频道、消息与个人已读，复用房间事务和文件存储，不绑定网络适配器；联系人目录、历史分页和写命令均有 HTTP 与进程内入口。

宿主在实际提交时完整校验一次状态，管理命令不再提前重复校验同一状态。聊天 Schema 按原模型拆分外层与消息：普通文本消息以全部字段及精确类型构成不可变缓存键，富卡片使用规范 JSON 字节。只复用内容完全相同的纯 Schema 校验结果，最多 10000 项／8 MiB 计费键大小；字段改动、非法 Python 类型或新消息重新校验。频道关系、当前成员、引用、回复顺序、公开附件和行动回执等跨记录约束每次继续检查。投影中的目录与同一请求共用快照，周期推进也复用已经取得的流程清单；对外快照仍为独立副本。缓存失效与实测见[引擎性能](engine-performance.md)。

持久定向通知由 `notifications.py` 管理，复用 Room v4 outbox 与命令回执。`notification.send` 必须明确提交受众、文字和已成功的来源动作；`GET /api/v1/notifications` 读取本人未确认项，`notification.ack` 逐人确认。离线补取、来源绑定、幂等和客户端展示去重边界见[定向通知](notifications.md)，不以快照差值代替持久事件。

个人知识由独立宿主模块 `onlinecoc.knowledge` 管理，AI关闭也可使用。持久策略保护受控资源，固定观察与持续告知分开，KP披露/撤回采用正常幂等事务。接口、提供方接入、只读证据与出口限制见[个人知识服务](player-knowledge.md)。

素材字节与业务存档分离，消息通过 `assetIds` 引用公共素材，实体仅在 `components.core.assets` 保存 `assetId`。素材适配器负责内容摘要、文件落盘、登记、读取权限与回收。

## 4. 数据与文件提交

账号和房间分别存于数据目录下的 `identity/` 与 `rooms/demo/`。每个存储包含 `writer.lock`、`generations/000000000001.json` 等最终代和 `staging/`。素材位于 `rooms/demo/assets/`，文件名为内容 SHA-256，外部读取使用 assetId 而非摘要。

每代文件包含格式版本、代号、前代摘要、规范化 JSON 字节数及摘要。提交执行：CAS → 配额检查 → 暂存文件写入/flush/fsync → 发布最终代。打开时校验整个已发布链；缺中间代、校验失败、不支持格式均停止打开，不自动回退。未发布暂存不参与恢复。文件格式仍为1；后端0.3.0只接受Room v4，chat、aiControl、knowledge均必需。打开时拒绝旧版，不自动补字段。显式v3→v4独立输出转换、只读验证及恢复分叉见[房间格式](room-format.md)。

Windows 已验证进程强制退出下的发布恢复。文件 fsync 不等于断电下目录元数据一定持久；本次没有物理断电实验。保留外部备份，不能把这一实现称为已验证的断电容灾系统。

主机按房间串行处理写命令。T1 保存固定输入、规则锁和执行快照；每次随机调用在返回 Lua 前单独记录；T2 原子保存实体/引用、最终回执、流程节点/等待、审计及 Outbox。失败丢弃拟效果。进程重启继续 pending 尝试，并使用原随机序列。已提交命令不重算。

每个账号的 commandId 是幂等键。同 ID 同 payload 返回原结果；不同 payload 为 `COMMAND_ID_CONFLICT`。协议/当前权限/目录等准入失败在 T1 前返回错误；已进入执行的成功和拒绝保存回执。查询旧回执仍按当前权限过滤。连接和登录会话不等于房间或场次；每次启动更换 authorityEpoch。

统一实例包括角色、背包、物品、武器、技能、状态。数值表保存原始量，组合值通过只读 Lua 查询。配置变更不会静默覆盖已有实例数值；实例保留创建时配置修订。关系存房间级表，支持类型、标签与元数据，检查目标存在、唯一持有、包含环及归档引用。成员/实体个人记录与世界状态共同持久化。

## 5. 管理和恢复

常见管理命令：`configuration.put/remove`、`entity.create/update/patch/archive`、`relation.set/remove`、`member.add/update`、`progress.set`、`room.status`、`flow.respond/retry/cancel`、`asset.attach/remove`。实例/配置管理除自有对象改名和指定身份回应待办外，由 KP 执行；chat.* 写入使用独立频道与作者权限。普通玩家不能直接修改受保护数值或关系。KP 数值修改同样经过模型校验并记录审计。

配置的 `behaviors` 与实例的 `rules` 采用 `{event: {ruleId: "..."}}`，通过 `behavior.invoke` 解析入口；公开动作目录仍控制可调用范围。属性/关系属于实例数据，不附在规则引用里。旧流程已经固定规则 ID、修订及输入，不随配置入口改写。

Windows 主机可用[本机账号工具](host-accounts.md)在线查询完整账号、创建身份或重设密码；权限绑定启动实例的 Windows 用户，与 KP 房间权限分离。以下离线 CLI 仍需先停止持有该目录的服务，否则排他锁拒绝第二主机：

```powershell
engineering/.venv/Scripts/python engineering/backend/scripts/run.py --data-dir engineering/.runtime/demo account-create alice --role player
engineering/.venv/Scripts/python engineering/backend/scripts/run.py --data-dir engineering/.runtime/demo password alice
engineering/.venv/Scripts/python engineering/backend/scripts/run.py --data-dir engineering/.runtime/demo backup --output engineering/.runtime/backup-01 --include-identity
engineering/.venv/Scripts/python engineering/backend/scripts/run.py --data-dir engineering/.runtime/restored restore --bundle engineering/.runtime/backup-01
```

备份锁住房间写入、规则发布和资源回收，导出一代完整业务状态及引用资源，最后写 manifest。`--include-identity` 额外包含账号密码散列，但清空登录会话；它是完整主机迁移备份，应按账号资料保护。网页按钮默认只备份房间，返回本机数据目录 `backups/<backupId>`。

仅房间备份恢复时指定 `--identity-dir <原主机数据目录/identity>`，原身份库必须处于停止状态。恢复验证账号 ID 与密码散列绑定，不按昵称匹配。若之后改过密码导致绑定不匹配，应重新制作一致备份；首测没有自动跨账号映射。恢复目标必须不存在，先校验素材和清单再发布新目录，原存档不被覆盖。失败可能留下独立 `.restoring-<id>` 目录供诊断，不能当作成功存档使用。

恢复会为 AI 创建新 scopeId、撤销未消费批准并关闭自动需求；已发布配置/工件不丢失。可选 AI 历史在恢复目录中作为待复核附件保留，不直接复用旧授权。相同存档正常重启保留 scopeId；恢复分叉与正常重启不同。

`asset.remove` 只移除无引用登记，字节延迟回收；离线 `collect-assets` 清理超过一天的未引用字节/暂存文件。快照代和旧规则工件不自动裁剪。单存储默认累计配额 512 MiB。FileDataStore 提供 `compress_history(expected_generation=...)`，逐代校验完整链后将较早 JSON 无损压缩为 `.json.gz`，保留每代原始字节、代号和摘要；默认最近两代保留原文件。仅在压缩副本发布、同步及回读一致后移除其冗余原文件。AI Repository 默认在提交即将超过配额时自动触发；房间和身份存储仍默认关闭自动压缩。压缩不会删除会话、审计或回执，当前状态和压缩后的历史仍会增长；真正不足时仍返回 STORE_FULL，需备份并恢复到新目录建立新链，不能手动删除历史中间代。备份失败没有最终 manifest 时视为未完成。

新读取器兼容原 JSON 链及 JSON/gzip 混合链；压缩后的存储不能直接交给旧读取器。文件封套版本仍为 1，原字节均可从 gzip 还原；回退程序前应使用兼容读取器导出并恢复到独立目录。压缩保持单写锁和 CAS，临时写失败或同时存在两种表示时必须校验原字节一致，损坏不回退。已验证原 527106299 字节失败样本的隔离副本压缩至 143448602 字节，158 代全部保留，再写 12 代并重开成功；详见[压缩验收](../../../engineering/acceptance/store-compaction/README.md)。

在线备份在房间锁内捕获一致房间代、身份绑定及可选逻辑 AI 快照，并暂时固定其资源摘要；随后在锁外写入、验证资源及同步文件。资源回收会避开仍被备份固定的字节。只有最后的 manifest 完成才返回成功，不把排队或半份备份报告为完成；文件格式及恢复分叉规则不变。AI 历史须由调用方提供完整逻辑快照，宿主不会自动复制 AI 物理目录。

## 6. 协议与首测限额

| 入口 | 用途 |
| --- | --- |
| `GET /api/v1/capabilities`、`/contracts` | 协议、限额和公共机器契约 |
| `POST /login`、`GET /me`、`POST /logout` | 身份和 CSRF |
| `GET /view`、`/catalog`；`POST /query`、`/calculate` | 授权投影、动作、受限查询、只读计算 |
| `POST /commands`；`GET /receipts/{commandId}` | 管理/行动/聊天命令及结果查询 |
| `GET /chat/members`；`POST /chat/history` | 活跃成员公开目录、授权聊天历史分页 |
| `WS /api/v1/connect` | 原子分片快照订阅、重连 |
| `POST /preview` | KP 对指定修订的隔离预览，不提交效果 |
| `POST /assets`、`GET /assets/{assetId}` | KP 上传、授权下载 |
| `GET /admin`、`/admin/artifacts/{revision}` | 管理、审计、计时、规则源码/数据差异 |
| `POST /backup` | 一致房间备份 |

表中省略的前缀为 `/api/v1`。HTTP 写请求需要同源 Origin，登录后的写请求还需要 CSRF header；登录 Cookie 为 HttpOnly、SameSite=Strict。页面固定 JS/CSS MIME 类型，避免 Windows 注册表关联影响脚本加载。

本机适配器每约 250ms 检查投影变化，使用 begin/part/end 完整快照，客户端收齐后原子替换；后续更改再次发送最新快照。慢连接不堆积历史增量，单次发送超过 2 秒关闭，重连重新获取完整视图。能力返回 `resumeWindow: 0`，没有跨连接增量回放；Outbox 已与提交同存，但此适配器用最新状态实现最终同步。权限变化也用新投影移除字段/对象，彻底撤权发送 reset 后断开。聊天订阅仅发送可见频道元信息和修订，不携带历史正文；频道修订变化后客户端查询历史并使旧页缓存失效，频道消失时清空缓存，详见 [聊天室同步约定](chat-backend.md#7-实时同步与缓存)。

投影获取及最终分片的持锁复验在线程中执行，避免同步等待房间锁阻塞 HTTP／WebSocket 事件循环；最终授权检查与发送调度仍处于同一锁边界。没有外部知识策略且房间存储 generation 未变化时跳过重复投影，每轮仍校验登录会话；有知识提供方时继续实时复验，不能只依赖存储代号。并发改变投影可能触发安全 reset，此时 SDK 暂时等待完整快照，不等同于物理连接关闭。隔离浏览器负载、分段成本和验证范围见[性能验收](../../../engineering/acceptance/performance/README.md)。

普通 API 请求 64 KiB；AI 人工草稿入口 8 MiB；上传素材 10 MiB；投影 2 MiB；单文件存储 512 MiB；Lua 内存 32 MiB、工作进程内存 512 MiB、JSON 输入/输出各 8 MiB、默认 10 秒、API 调用 2048 次、拟效果 256 条、规则文件 64 个、流程节点 32 个。inspect、正式运行与 [AI 离线检查](ai-runtime.md)共用最多两个清理环境的受限 Python 子进程；每个任务仍新建 Lua 解释器与执行上下文，不保留 Lua 全局、闭包或随机通道。成功进程最多复用 64 次或 90 秒，故障/超时即销毁；等待进程槽位也计入请求期限。Windows 每个 worker 使用单进程 Job Object。HTTP 命令入口最多 128 个在途请求，主机内部另有有界准入。持久流程不保存协程栈，等待期限不因重启重置。暂停房间不推进待办；恢复后已过期等待按超时分支处理。

客户端只在收到完整快照后允许新写入，保留原始命令封套用于同 ID 重试；页面刷新会丢失内存命令封套，结果不明时先按 commandId 查询，不能换 ID 盲目重复操作。正式离线队列、长期客户端缓存及多语言 SDK 尚不在此版本。

`client-sdk/client.js` 的 `HttpTransport.request` 抛出的错误提供 `code`、`errorKind`、`status`、`operation`、`requestId`、`commandId`。HTTP 拒绝保留数值状态码和合法机器错误码；无合法 JSON 错误码时使用 `HTTP_ERROR`，不会把非 JSON 的 500 误当网络断连。`fetch` 失败使用 `NETWORK_ERROR/network`，没有 HTTP 响应时 `status=null`；成功状态的正文无法解析则使用 `INVALID_RESPONSE/response` 并保留状态码。本地请求序列化失败为 `INVALID_REQUEST/client`。命令离线和相同 ID 不同输入分别为 `DISCONNECTED/client`、`COMMAND_ID_CONFLICT/client`；账号切换后丢弃旧请求结果，返回 `SESSION_CHANGED/session` 并清空旧请求定位。

诊断定位取自本地原请求：命令使用 `op` 与封套 ID，其余使用去掉查询参数的 `METHOD path`；缺失或格式不安全的字段为 `null`。错误不复制响应正文、服务器 detail/message、Cookie、CSRF 或底层异常；共享 HTTP error Schema 仍为 `{code}`，这些定位字段是 SDK 补充的本地信息。HTTP 200 中的 `rejected`／`unknown` 回执原样返回。HTTP 失败、网络中断或解析失败本身都不能证明写操作未提交，应查询原 commandId／AI requestId；SDK 不自动重放。真实回环 HTTP、连接拒绝、业务回执与会话隔离证据见[错误链验收](../../../engineering/acceptance/http-errors/README.md)。

常见错误：`VERSION_CONFLICT` 刷新后重新确认；`STALE_CATALOG` 重新选择动作；`RULE_TIMEOUT/RULE_FAILED` 检查脚本，失败不提交拟效果；`FLOW_ALREADY_RESOLVED` 查询原待办；`STORE_LOCKED` 停止另一个宿主；`STORE_CORRUPT_OR_UNSUPPORTED` 保留故障目录并从有效备份恢复；`STORE_FULL` 不得删除中间代。
