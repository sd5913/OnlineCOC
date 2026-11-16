# 房间格式与发行变更

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-14
- 最后更新：2026-11-14
- 关联文档：[机器契约](../../../engineering/contracts/models.json)、[完整初始化样例](../../../engineering/contracts/fixtures/room-initial.json)、[运行说明](first-test.md)、[旧格式定义](../../history/2026-11-14-room-formats-before-0.2.0.json)

## 支持矩阵与责任

| 后端版本 / 阶段 | 可加载的 Room | 行为 |
| --- | --- | --- |
| 0.1.0，AI 接入前的首测阶段 | v1 | 曾补齐缺失 chat；只作历史说明 |
| 0.1.0，2026-11-14 本次调整前 AI 工作区 | v1 / v2 | 曾将 v1 自动转成 v2，缺 chat 自动补齐 |
| **0.2.0，本次工作区实现** | **仅 v3** | 新建直接生成 v3；打开、提交、备份验证及恢复拒绝旧版、未知新版与损坏的当前格式 |

0.1.0 曾复用包版本号，不能只凭该号码确定其旧契约；上表阶段与[历史机器定义快照](../../history/2026-11-14-room-formats-before-0.2.0.json)共同标识调整前版本。0.2.0 的 Python 包版本与 `onlinecoc.version` 一致，CLI `--version` 和 `/api/v1/capabilities` 返回版本。这里的版本只属于后端，不代表 LAN、网页或桌面管理器版本。

引擎不再自动迁移业务存档。配置包开发者／数据持有方负责备份、转换、校验和选择升级时机。实际游玩数据、旧备份和包侧存档均未在本次更新中转换、删除或覆盖；仍为 v1/v2 的存档无法直接用此后端启动。正常锁文件操作不等于迁移。

## 0.2.0 / Room v3 变更

- `schemaVersion` 必须是整数 3；不接受字符串、布尔值、缺失版本、旧版或未知新版。
- `chat` 由旧 Room v2 的可选字段改为必需。因为这是不兼容约束，提升 Room 版本，避免沿用 v2 静默收紧。
- `aiControl` 延续 v2 的必需性。新建时 AI 与自动需求均关闭；即使没有启用 AI，也要保留控制结构及有效作用域。
- 移除 `RoomV1` 活跃契约、自动迁移和缺聊天补齐分支。规则执行及 AI 验证使用独立 `ExecutionSnapshot` 契约；精简投影不能保存或恢复成完整房间。
- 正常重启保持 scopeId；恢复为新副本仍创建新 scopeId、撤销 approved 状态的未消费批准、关闭自动需求及其 principal；已发布配置、回执和可选 AI 历史附件保持原恢复规则。代码为 `room_lifecycle.py`，没有格式升级职责。
- 验证器摘要覆盖当前模型、版本及相关机器契约；旧 AI 校验证据不能直接用于新验证器下发布，需重新验证与审批。

v1→v2 的历史差异是新增必需 `aiControl`。v2→v3 没有重命名实体/关系字段或改变业务数值；完整合法的 v2 数据经外部确认聊天结构、AI 作用域及引用后，才可声明 v3。不能把仅改版本号当成对缺字段、无效引用或旧批准的修复。不得就地编辑文件存储代号或忽略摘要链；应在独立副本按文件模块的导出／导入与备份约束重建并验证。

## 当前结构

所有下列 Room 顶层字段必需，无未知顶层字段。形状、长度、枚举和数值界限以机器契约为准；完整模型入口还校验引用、包含环、归属、数值和聊天约束。

| 字段 | 语义 |
| --- | --- |
| schemaVersion、roomId、name、runId、status | 格式、稳定房间身份、名称、场次及 active/paused/archived 状态 |
| entities、relations、members | 实例、关系、成员，均以稳定 ID 索引；实体归属和关系端点必须有效 |
| configurations、progress | 配置定义和成员／实体个人进度；进度所有者必须存在 |
| commands、flows、waits | 幂等执行回执、持久流程和等待，不代表玩家客户端可自行写入 |
| artifacts、activeRuleset | 完整规则工件及生效修订；初始化示例允许 null，运行宿主会装载工件 |
| assets | 素材元信息；完整备份另验证实际字节与摘要 |
| chat | schemaVersion=1 的聊天频道、消息、序号及已读结构；不能以空对象代替合法 ChatState |
| aiControl | AI 控制、scopeId、批准与发布记录；控制子格式仍为 1 |
| audit、outbox、collectionRevision | 审计、通知及集合版本，由宿主管理 |

格式号彼此独立：Room=3，Entity=1、AI 契约/控制=1、聊天=1、网络 protocolVersion=1、文件封套 format=1、备份 format=1；配置包版本由包作者维护。本次未修改独立文件数据模块或网络协议号。

## 只读验证

从工程根目录运行，`--input` 指向待校验副本：

```powershell
engineering/.venv/Scripts/python engineering/backend/scripts/run.py --version
engineering/.venv/Scripts/python engineering/backend/scripts/run.py validate-room --input engineering/contracts/fixtures/room-initial.json
engineering/.venv/Scripts/python engineering/backend/scripts/run.py validate-room --format snapshot --input D:/isolated-copy/room.json
engineering/.venv/Scripts/python engineering/backend/scripts/run.py validate-room --format backup --input D:/isolated-copy/backup
```

`room` 检查纯 Room JSON；`snapshot` 另检查导出封套 format/digest；`backup` 调用宿主完整备份验证（规则、素材、批准及可选 AI 历史）。验证不创建 Host、不占用存档锁、不写入文件、不校正内容。成功退出 0，失败退出 2，输出 JSON。纯 Room 检查不证明素材文件齐全或身份库能匹配；实际恢复仍校验身份绑定。

旧版返回 `SCHEMA_UNSUPPORTED`，detail 包含 actualVersion、supportedVersions=[3] 和本说明路径；版本值本身若非整数则返回 null，不回显任意原文。当前格式字段错误返回 `INPUT_INVALID`，如 model=Room、path=/chat、constraint=required；坏引用返回 `REFERENCE_CONFLICT` 等领域错误。不会把房间正文或密码作为错误输出。

验证证据见[专项结果](../../../engineering/acceptance/room-version-policy/results.json)。

2026-11-14 验收：后端与 AI 全量回归 367 项、单独补验恢复自动需求关闭 1 项，共 368 项通过，0 失败、0 跳过；其中本次版本策略专项 23 项。包含真实宿主子进程及浏览器；未转换真实存档、未调用真实模型服务。
