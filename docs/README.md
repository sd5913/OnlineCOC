# 文档索引

本目录按文档用途与生命周期组织项目知识。游玩从[英文首页](../README.md)或[中文指南](../README.zh-CN.md)开始；版本变化见[更新日志](../UPDATE-NOTES.md)，试玩观察可记入[用户反馈](../feedback/README.md)。

具体包的名单、版本和状态见[配置包实例统计与管理](../rulepacks/catalog.md)，工程接入与开发约定见[配置包开发指南](../rulepacks/README.md)。包内计划须注明状态；工程接入问题统一登记到 [Issues](plans/Issues/README.md)。

规则编写、联调、本地化、AI 校验和语音输入统一从[支持工具清单](../rulepacks/README.md#rulepack-development-tools)进入，按各模块的当前能力与验收接入。

| 目录 | 含义 | 入口 |
| --- | --- | --- |
| `current/` | 当前文档入口，下分设计与工程 | [当前文档索引](current/README.md) |
| `current/design/` | 当前有效的项目目标、设计与约束 | [设计文档索引](current/design/README.md) |
| `current/engineering/` | 与当前代码、配置和文件结构一致的工程说明 | [工程文档索引](current/engineering/README.md) |
| `current/engineering/developer-reference/` | 基于实际配置包的精简开发速查 | [开发者参考](current/engineering/developer-reference/README.md) |
| `plans/` | 尚待讨论、验证或实施的需求、调研与方案 | [计划文档索引](plans/README.md) |
| `history/` | 已被替代、取消或完成归档的材料 | [历史文档索引](history/README.md) |
| `standards/` | 跨阶段适用的通用规则和标准 | [通用标准索引](standards/README.md) |

开始使用首测版请阅读 [安装与运行](current/engineering/first-test.md)、[Lua 编写](current/engineering/lua-authoring.md) 和 [验收报告](current/engineering/first-test-acceptance.md)。

聊天室后端已实现的结构、权限及接口见 [聊天室后端](current/engineering/chat-backend.md)。

公网开房、短房间码加入和本机宿主识别从[快速使用](../engineering/network-p2p/README.md)开始；配置、玩家包生成、云端运维和验收见[公网联机工程说明](current/engineering/network-p2p.md)。

免安装玩家入口 [network-web](current/engineering/network-web.md) 0.3.2 已部署测试版：开房串导入，创建/管理/加入三页，可选公开列表与房间密码，以及快捷重入、黑名单、预设 KP 账号远程登录和独立按需游戏页；离线房间默认保留一天、房主可立即移除，Windows 房主可用[离线安装器](../engineering/network-web/installer/README.md)；平台密码最低 6 位，支持可选在访问者本机记住账密。首测规则桌面已适配；公网暂用测试 CA，正式域名、可信证书及独立网络验收见[后续计划](plans/browser-room-portal.md)，腾讯域名操作见[接入步骤](plans/cloud-server-deployment-research.md#61-在腾讯云取得并接入域名)。

配置包可用 [AI 底层工具与三种嵌入视图](current/engineering/ai-pack-embedding.md) 自行装配，或选择单独页面、对话页面、可折叠面板；提供同源 HTML 入口与资源/路由清单。

AI 的独立服务商/密钥管理、房间文件夹对话、数据引用与可嵌入面板见[管理器与开发接入](current/engineering/ai-manager.md)；树桩镇已有 AI 咨询、P2P 基础启动及完整网页玩法，实际边界见[包接入说明](../rulepacks/stumpsville/docs/current/integrations.md)与[网页说明](../rulepacks/stumpsville/docs/current/web.md)，剩余工作见[Stumpsville 规划](plans/stumpsville-web-integration.md)。

建议先阅读 [项目概况](current/design/project-overview.md)，再按需要查阅计划或标准。施工前必须检查 [hierarchy 目录与施工登记](current/engineering/hierarchy.md)，登记自己的 ID 与使用或改动范围，结束后释放。

分类取决于内容用途：标准放入 `standards/`，即使它目前正在生效；未落地方案放入 `plans/`，即使它已获确认。历史文档仅用于追溯，不作为当前操作依据。

工程规划中的待解决设计问题见[Issue 索引](<plans/project planning/Issue/README.md>)；Lua 首轮参考样例已归入[工程规划目录](<plans/project planning/lua-script-reference/README.md>)，其编写体验仍需简化。

维护方式见 [文档维护标准](standards/document-maintenance.md)。各分类的 `README.md` 维护本分类的文档清单。

后续更新的问题入口为 [Issues](plans/Issues/README.md)，新增问题使用其中的模板；原规划 Issue 保留正文并通过该索引链接。Windows 快速使用见 [exe 工具说明](current/engineering/desktop-tools.md)。

独立桌面房间管理工具已迁移到 Python，并增加[LAN 模块与面板](current/engineering/network-lan.md)，见[当前工程说明](current/engineering/room-manager.md)和[使用文档](../tools/room-manager/docs/usage.md)。[施工计划](plans/room-manager-construction-plan.md)保留完整变更历史与存档管理等后续工作。

配置包侧的对象引用、AI 对话与 KP 审核布局见[可操作原型与接入计划](plans/ai-pack-interaction.md)，演示使用固定数据，不写入游戏。

- [房间格式与发行变更](current/engineering/room-format.md)：当前支持版本、旧定义、外部迁移责任和只读检查。
