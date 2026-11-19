# 计划文档

收录待讨论、待验证或待实施的需求、调研、设计提案及实施计划。计划被接受不代表功能已经实现。

ISSUE-011首版与AI消费接入已完成，见[现行知识服务](../current/engineering/player-knowledge.md)、[有效设计](../current/design/ai-player-knowledge.md)及[归档施工记录](../history/2026-11-17-player-knowledge-construction-plan.md)。

新增计划时，在下表登记，并在正文写清目标、范围、待确认问题、实施步骤与验收条件。

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [AI 数据查询与聊天裁决资料后续计划](ai-data-query-adjudication.md) | 进行中 | 四类查询、来源复验、组件引用与树桩镇只读适配已实现；通用记录、索引与跨存储发布仍待实施 |
| [Stumpsville 网页联机调整规划](stumpsville-web-integration.md) | 进行中 | S0–S2、云端部署及S3本地/强制TURN双浏览器验收完成；真人独立家庭/移动网待验收 |
| [配置包 AI 人机交互原型与接入计划](ai-pack-interaction.md) | 草案 | 已交付 KP／PL 可操作演示；对象引用、对话与分步审核，包侧正式接线和配置闭环待实施 |
| [Stumpsville AI 接入计划](stumpsville-ai-integration.md) | 进行中 | 0.7.0咨询启动与KP/PL会话已接入；首个受限配置发布、包侧授权来源及跨设备多人验收仍待实施 |
| [房间启动入口、服务编排与配置包职责](room-launch-orchestration.md) | 进行中 | P2P 借用宿主与会话锁已实现；完整创建/继续存档、多入口和具体包编排待实施 |
| [服务器房间发现、P2P 联机与配置包同步](room-discovery-p2p-package-sync.md) | 进行中 | 短房间码、本机宿主识别与测试云已实现；完整包迁移、自动重入和长期验证待补 |
| [公网大厅与按需游戏页](browser-room-portal.md) | 进行中 | network-web 0.3.0 三页、开房串与可选公开已部署；正式域名/证书、独立真人网络与长期验收待补 |
| [阿里云与腾讯云服务器选型及部署调研](cloud-server-deployment-research.md) | 进行中 | 腾讯 CVM 测试部署；补充域名注册、DNS、备案与 HTTPS 步骤，续费和扩容按实际需求评估 |
| [房间 AI 接入与运行时配置设计](ai-runtime-design.md) | 进行中 | DeepSeek 与自定义服务商、房间上下文与记忆、三类校验、KP 审核及原子发布 |
| [房间 AI 模块实施与验收计划](ai-runtime-construction-plan.md) | 进行中 | AI-0—AI-5、AI-6 实际 demo 工程试点及真实 DeepSeek 联调通过，人工试玩待补 |
| [AI 语音输入识别调研与接入方案](speech-input-research.md) | 草案 | 玩家及 KP/开发者输入场景；云端/本地识别方案、接入条件、费用及官方来源 |
| [独立语音输入模块工程设计](speech-input-design.md) | 草案 | 阿里云首选与豆包备选、浏览器 PCM 流程、独立模块与协议、AI-0 文本字段映射及 LAN 条件 |
| [独立语音输入模块施工与验收](speech-input-construction-plan.md) | 草案 | SI-0—SI-6 工作包、29 项验收矩阵及玩家/配置编写完整流程；尚未实施 |
| [独立本地化开发模块与工具](localization-system.md) | 进行中 | 独立于核心和具体配置包；文件契约、可视化 CRUD、翻译管理、资源构建与可选解析库 |
| [独立本地化工具工程设计](localization-engineering-design.md) | 进行中 | 独立目录与发行、JSON 数据契约、GUI/CLI、文件事务、资源构建与解析库 |
| [独立本地化工具施工与验收](localization-construction-plan.md) | 进行中 | L10N-0 已实施骨架并通过 3/4 条件；原生目录确认待验收，后续阶段未开始 |
| [房间管理器后续设计](room-manager-design.md) | 进行中 | Python 与 LAN 已实施；权威历史、完整存档及网络扩展待设计 |
| [房间管理器施工状态](room-manager-construction-plan.md) | 进行中 | 首版与 Python/LAN 迁移验收，后续 H/S 工作包 |
| [轻量跑团规则与前端](../../rulepacks/lasers-and-feelings/README.md) | 当前实现入口 | Lasers & Feelings 规则包与独立桌面已实现；包内使用和设计为现行正文，早期验证已归档 |
| [更新问题 Issues](Issues/README.md) | 进行中 | 后续问题统一索引、模板，并链接已有设计议题 |
| [首测版工程设计](<project planning/first-test-engineering-design.md>) | 进行中 | 首测技术基线、独立文件数据管理模块、房间与实例结构、事务/恢复、动态 Lua 及本机 HTTP/WS；已有本机首测实现，实际状态见当前工程 |
| [首测版施工计划](<project planning/first-test-construction-plan.md>) | 进行中 | E0—E6 工作包、依赖、退出条件与故障验收矩阵；首测施工顺序的统一入口；工程自动验收已落地，独立作者试写待验收 |
| [Lua 简化编写接口与可恢复流程方案](<project planning/lua-authoring-facade.md>) | 进行中 | 已有 A0 同题稿与 A1 同步内存简化层，56 项断言通过；正式首测已实现持久流程与短声明，独立作者试写待验收 |
| [工程规划 Issue](<project planning/Issue/README.md>) | 进行中 | Lua 编写简化方案获准分期推进，同步原型已有验证，完整验收待完成 |
| [Lua 规则与流程脚本设计参考](<project planning/lua-script-reference/README.md>) | 草案 | 旧样例对照索引：9 个脚本与数据保留，原协议正文已归档；现行编写方向见宿主 API 与简化方案 |
| [前后端对接与同步契约设计](<project planning/frontend-backend-contract.md>) | 草案 | 逻辑协议与 SDK、HTTP/实时映射、授权投影、快照恢复、Lua 动态动作目录及资源接口 |
| [系统模块分层与职责设计](<project planning/module-responsibilities.md>) | 草案 | 从原分析第 2 节拆出：模块层级、职责、协作关系及业务场景映射 |
| [抽象数据结构与容器设计](<project planning/data-container-model.md>) | 草案 | 长期房间与主机权威、个人事件记录、统一实例、原始/组合数值、类型化引用与事件规则入口，以及 CRUD 和内核约束 |
| [后端、自定义能力与联机方案分析](<project planning/backend-network-analysis.md>) | 草案 | 基于跑团与联机调研，分析数据模型、容器、Lua 规则与流程、运行中新增规则与版本管理、持久流程、授权、联机适配及资源管理；Lua 语言已选定，首测已验证 Python/Lua/文件/本机 HTTP/WS，更广范围仍待验证 |
| [COC 与线上跑团的工程构成调研](coc-online-trpg-research.md) | 进行中 | 从图谱分支、规则元素与对象、内容类型及格式用途三条主线开展调研；已整理首轮公开资料，完整规则核查与平台实测待开展 |

计划落地后，将有效结论整理到 [当前文档](../current/README.md) 或 [通用标准](../standards/README.md)，再将原计划归档到 [历史目录](../history/README.md)，补充结果和后续文档链接。部分落地的计划应明确已完成与剩余内容。

维护规则见 [文档维护标准](../standards/document-maintenance.md)。

- [通用请求与决定工程评估](interaction-records.md)：双模型、读取试点、权限与事务边界，宿主接线尚未实现。

- [AI 裁决与输出修正实验](ai-rulings-experiments.md)：离线故障注入、真实 API 与隔离房间验收。

- [AI 会话管理交互原型](ai-session-management-prototype.md)：房间／列表／详情三栏、KP／PL、归档撤销和窄屏交互，等待试玩反馈。
