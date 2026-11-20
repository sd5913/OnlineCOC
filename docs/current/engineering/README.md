# 工程文档

工程文档必须与当前代码、配置及实际文件结构一致，描述已经存在的实现、接口、运行与验证方式。尚未实现的内容放入 [计划目录](../../plans/README.md)。

工程代码目录为 [`engineering/`](../../../engineering/README.md)。已包含本机首测后端、独立文件数据管理、Lua 执行器、HTTP/WebSocket、SDK、测试操作台及验收驱动；完整产品功能仍在后续范围。原同步内存实验保留。

| 文档 | 说明 |
| --- | --- |
| [开发者参考](developer-reference/README.md) | 基于实际配置包的面板树、通知、规则定义与数据管理速查 |
| [AI 回答、语义引用与选择项](ai-responses.md) | 简洁分段、授权引用详情、稳定渲染、结构化选择及独立嵌入组件 |
| [AI 数据查询与聊天裁决资料](ai-data-query.md) | 按需工具、来源复验、语义引用、包侧只读适配、Room v4与个人知识边界 |
| [网页房间与按需游戏页](network-web.md) | 可选 network-web：开房串、创建/管理/加入三页、可选公开与密码、成员/黑名单及按需游戏页 |
| [配置包 AI 工具、嵌入视图与会话管理](ai-pack-embedding.md) | pack.js 无界面工具、三种对话视图、独立会话管理/设置、用量统计、Markdown 显示、同源 iframe 与资源清单 |
| [AI 来源审核、调试导出与模型标识](ai-debug-review.md) | KP 来源卡、顶部调试子窗口、授权导出、失败处理与实际模型记录 |
| [AI 管理器、嵌入组件与开发接口](ai-manager.md) | 房间文件夹与对话界面、服务商/加密密钥、可选日限额与用量统计、只读数据引用、可嵌入组件/API、增量刷新与包侧接入 |
| [房间 AI 模块](ai-runtime.md) | 模块边界、启动配置、三检、上下文/记忆、服务商与配置发布；阶段验收已归档 |
| [高危配置发布与 KP 全房间读取](high-risk-publication.md) | 完整候选明确批准、配置删除依赖、发布回执及受授权的 Room 分片读取 |
| [独立本地化工具](localization.md) | 独立 Electron/CLI 骨架、共享 ICU 与便携试打包；L10N-0 的 3/4 条件通过，原生目录确认待验收 |
| [本机主机账号维护](host-accounts.md) | 工程外账号工具、运行实例选择、主机用户授权和在线密码重设 |
| [公网房间与 P2P 联机](network-p2p.md) | 短房间码、本机宿主识别、玩家分发、腾讯 CVM 运维和验收；开房/加入见[快速使用](../../../engineering/network-p2p/README.md) |
| [局域网联网模块](network-lan.md) | 独立 LAN HTTP/WS、身份与路由边界、启停 GUI |
| [独立桌面房间管理工具](room-manager.md) | 工程外 Python/Tkinter GUI、现有管理接口、变化观察、关注、回执与备份创建 |
| [Windows 安装与启动工具](desktop-tools.md) | 两个 exe、共享配置、独立运行时、更新与启停 |
| [首测工程与运行](first-test.md) | 模块、实际接口、部署、文件存档、备份恢复与限额 |
| [聊天室后端](chat-backend.md) | 频道/消息/权限、分页、结果卡片、存档与 SDK 接入 |
| [持久定向操作通知](notifications.md) | 审批包显式通知、已提交原动作绑定、离线补取、逐人确认及去重边界 |
| [Lua 规则与流程编写](lua-authoring.md) | 当前可执行语法、短指令、阶段等待和版本导入 |
| [首测验收报告](first-test-acceptance.md) | 自动测试证据、实测性能、未验收边界与作者体验待办 |
| [Lua 简化编写实验原型](lua-authoring-prototype.md) | 实际实现、运行方式、56 项断言及尚未具备的能力 |
| [hierarchy：工程目录与施工登记](hierarchy.md) | 实际文件清单、Agent 与人员的使用/改动占用记录 |

每次阶段更新（阶段交付、里程碑完成或集中同步工程状态）必须逐项核对工程文档与实际工程，删除失效路径、已移除功能、旧配置、旧命令和其他废弃说明；有追溯价值的内容移入 [历史目录](../../history/README.md)，不得留在当前工程正文中。日常变更也应及时同步，无需等到阶段更新。

所有 Agent 和人员施工前必须先读 hierarchy，检查范围冲突、登记唯一 ID 并确认；施工结束、取消或交接时释放自己的登记。详细要求见 [文档维护标准](../../standards/document-maintenance.md)。

## 版本管理

项目根目录使用 Git 管理，远端 `origin` 为 [sd5913/OnlineCOC](https://github.com/sd5913/OnlineCOC)。保留原项目提交历史，`main` 为主分支，`spathering` 从主分支创建并作为当前开发分支。

可用 `git status --short --branch` 检查当前工作区和分支，用 `git remote -v` 检查远端配置。分支切换与提交前须遵守 hierarchy 占用规则。初始化与本地分支创建不会自动推送至远端；远端分支及上游关联需在实际推送后确认。

- [房间格式与发行变更](room-format.md)：后端 0.3.0 / Room v4，严格加载及显式离线转换。
- [玩家知识服务](player-knowledge.md)：持久披露、固定观察、持续告知、统一出口与验收。

- [AI 会话权限与执行批次](ai-session-access.md)：管理员／玩家分级、同房间重启后的历史读取、执行审批和删除审计。

- [AI 修改裁决与配置包扩展](ai-rulings.md)：整批审批、裁决修订与旧回执兼容、自动策略、Stumpsville 模板／规则边界。

- [AI 嵌入渲染与玩家知识排查](ai-rendering-knowledge.md)：样式生命周期修正、个人场景知识、指南隔离、旧存档与基本实体边界。
- [AI 玩家已知资料](ai-player-knowledge.md)：严格知识读取、不可变引用、证据选择输出与撤权边界。
