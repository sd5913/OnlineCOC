# 树桩镇 Stumpsville

0.9.0提供 [网页联机双击入口](start-web.cmd)：本机 KP、浏览器 PL、完整场景行动与聊天、隔离存储和按需资源，本轮验证本地WebRTC；原0.8.0阶段已通过两名真实网页玩家及全部18个预设的公网强制TURN联测，本轮未重做公网验收。**云端桥已更新；真人独立家庭/移动网仍待验收**；操作与边界见[网页联机](docs/current/web.md)。

原 [AI 与 P2P 入口](start-integrated.cmd) 保留 AI 个人会话、KP 转交与咨询回复，以及旧 P2P 基础状态/聊天；旧 P2P 不提供完整树桩镇玩法。2026-11-14已接通网页玩家个人咨询；网页入口默认加载 AI，本机咨询可双击 [start-ai.cmd](start-ai.cmd)，服务商管理可双击 [start-ai-manager.cmd](start-ai-manager.cmd)。AI 已支持受限 NPC 模板／规则的三检与整批 KP 裁决，详见[接入说明](docs/current/integrations.md)。

玩家桌面使用固定一屏布局：顶部导航、左栏角色状态与背包、中栏地图及行动、右栏聊天与AI对话标签。线索和行动日志放进左上角可拖动、可折叠浮窗；窄屏在同一页切换角色／场景／聊天与AI三栏。513项UI词条和424项受限内容词条覆盖玩家主要流程、18个预设及系统结果；属性和状态使用可读名称。KP独立地图只显示玩家角色数量与名单；PL场景使用本人观察快照，身份披露可供本人知识查询；原动态联系人投影暂不输出。KP房间管理、裁决与地图现为独立页面，裁决页同时包含消息队列、统一待办队列（角色/行动/流程/玩家及辅助AI请求）、新版内嵌AI和常驻聊天。保留KP管理与本人PL页分离、多个私聊、局域网双击启动／诊断、预设自动裁决及独立登录；自动场景执行仍需管理台在线。

双击 **[start-panel.cmd](start-panel.cmd)** 打开 Python 房间管理面板：创建或选择房间数据槽位，选择本机、局域网或网页联机，设置端口及 AI 开关；新槽位首次填写初始密码后点击启动。支持最小化、停止、日志查看、管理页和连接信息复制；最小化继续运行，关闭面板停止房间。原 [start.cmd](start.cmd)、[start-lan.cmd](start-lan.cmd)、[start-web.cmd](start-web.cmd) 等入口均打开同一面板并预选对应方式。共用本包 `runtime/` 槽位库，各槽位独立存储在 `runtime/slots/<槽位ID>/`，切换前先停止。详细步骤见[使用与恢复](docs/current/usage.md)。

当前依赖后端0.3.0 / Room v4与包格式2；旧宿主档须使用引擎显式离线转换，启动不自动迁移。PL资料按[个人知识接入](docs/current/player-knowledge.md)授权，旧地点记录需KP选择现在揭示。每次打开根地址或点击“新开独立登录页”，均可登录另一个账号。

冒险专属遭遇表、Jack/Ernie 数值等仍待原版正文终校。首版提供主持填写及裁定入口，不能把待核模板视为完整原版内容。

| 入口 | 内容 |
| --- | --- |
| [场景预设行动](docs/current/scene-actions.md) | 18个行动、检定与实际结果、自动队列和恢复 |
| [当前实现](docs/current/implementation.md) | 实际页面、规则、数据边界及人工裁定事项 |
| [场景桌面与主持控制台](docs/current/interface.md) | 当前导航 Mermaid、功能组成树及反馈语义 |
| [使用与恢复](docs/current/usage.md) | 启动、玩家入场、局域网连接诊断、备份与恢复 |
| [AI 与 P2P 接入](docs/current/integrations.md) | 双击入口、咨询流程、联网基础能力与未完成接口 |
| [网页联机](docs/current/web.md) | 0.9.0双击入口、两次登录、完整玩家桌面、接口/资源/恢复边界 |
| [本地化接入](docs/current/localization.md) | 语言资源、切换、缺译回退及当前覆盖边界 |
| [来源与许可](docs/current/sources.md) | SRD、冒险资料的核对范围、原创资源 |
| [验证记录](tests/README.md) | 真实宿主与浏览器验收、可重跑脚本 |
| [设计计划](docs/plans/README.md) | 页面、导航、界面组成与验收范围 |
| [网页联机调整规划](../../docs/plans/stumpsville-web-integration.md) | S0–S2、云端部署和S3强制TURN联测已落地，真人独立网络验收待完成 |
| [界面图集](assets/ui-design/README.md) | 页面效果图、子 UI、状态与组件图 |
| [原版参考来源](assets/references/README.md) | 原版纸面表单、场景预览与使用说明 |
| [场景依据](../investigation-vtt-reference/docs/plans/stumpsville-foundry-plan.md) | 十地点对照和原 Foundry 方案 |

设计图作为美术参考，实际功能以当前实现及测试记录为准。运行插画独立放在 [assets/runtime](assets/runtime/README.md)，参考原图不通过游戏服务公开。
