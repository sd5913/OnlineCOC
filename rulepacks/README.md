# 配置包开发指南

面向配置包作者，集中提供工程接入、支持工具与开发约定。
具体包的名单、版本和进展已迁至[配置包实例统计与管理](catalog.md)；本页保留开发入口。

## 工程接入

配置包维护自己的资料、配置、Lua 规则、流程、界面、资源和测试。
通过[现行工程接口](../docs/current/engineering/first-test.md)使用宿主能力；工程缺口提交 [Issues](../docs/plans/Issues/README.md)，不在包施工中改动核心。
操作前遵守[配置包施工边界](AGENTS.md)和[文档维护标准](../docs/standards/document-maintenance.md)。

<a id="rulepack-development-tools"></a>

## 支持工具

核对日期：2026-11-12；AI 工具条目更新于 2026-11-16。工具各自维护和发布；实际能力以其当前说明及验收为准。

| 工具或能力 | 用途与入口 | 可用状态 |
| --- | --- | --- |
| Lua 编写 | [动作、计算与可恢复流程](../docs/current/engineering/lua-authoring.md) | 已有首测能力，规则由包作者维护 |
| SDK 与操作台 | [界面联调、导入、检查与激活](../docs/current/engineering/first-test.md) | 已有能力，依赖运行中的宿主 |
| 房间管理与 LAN | [数据、规则、回执与联机工具](../tools/room-manager/README.md) | 已有实现，限现行宿主与可信局域网能力 |
| 本机账号工具 | [测试账号创建、查询与密码维护](../tools/host-accounts/README.md) | 已有实现，限本机授权实例 |
| 独立本地化 | [工具与验收](../tools/localization/README.md)、[设计](../docs/plans/localization-engineering-design.md)、[施工](../docs/plans/localization-construction-plan.md) | 技术预览；正式 CRUD、资源发布与 TextRef/fallback 未完成 |
| AI 接入与界面 | [底层工具与三种嵌入视图](../docs/current/engineering/ai-pack-embedding.md)、[管理器与 API](../docs/current/engineering/ai-manager.md) | 已有 pack.js、无界面工具、单独/对话/折叠视图及同源页面；包须接真实会话与路由/资源白名单 |
| A/B/C 配置检查 | [现有运行时与验收](../docs/current/engineering/ai-runtime.md)、[包契约及作者分工](../docs/plans/ai-runtime-design.md#75-开发主责与交付边界) | 工程执行 A/B/C；包作者提供规则、Schema、场景及指标，发布仍须 KP 审核 |
| 网页联机 | [开房串、公开列表、独立游戏页与资源桥](../docs/current/engineering/network-web.md) | 0.3.0 测试版；包须完成资源/接口适配 |
| 独立语音输入 | [转写与文本接入设计](../docs/plans/speech-input-design.md)、[施工](../docs/plans/speech-input-construction-plan.md) | 待实施；只负责转文字，不直接执行或发布配置 |

## 网页联网接入

使用 [network-web 接入契约](../docs/current/engineering/network-web.md#32-开房串与配置包管理页)提供的 `WebHost.prepare_creation()` 或 `export_room_setup(state_path)` 取得开房串。建议将联网功能放在**独立管理页面**，集中提供启停分享、诊断、“复制开房串”和平台入口；由房主复制后在平台创建页粘贴，设置公开与密码。

开房串是十分钟、一次性的房主认领凭据；仅从本机受权接口返回，禁止进入玩家资源包或普通日志。包侧实现复制按钮与剪贴板失败回退。游戏页只负责游玩，公开列表、创建和成员管理复用平台页面；具体方法、限制与旧版兼容以契约为准。

## 开发约定

- 包内资料使用稳定目录和版本，保留来源、许可与署名；凭据和运行存档不入库。
- 词库、规则约束、测试场景与包侧适配由作者管理；工具代码与依赖独立维护。
- 联调使用隔离数据目录；GUI、CLI、运行库与嵌入面板分别按实际接入方式验收。
- 发布时记录所用接口版本和资源修订；模块维护者同步本表状态，包实例变更更新[统计管理表](catalog.md)。

返回[项目入口](../README.md)。

## AI 扩展默认建议

建议新配置包默认提供受限的配置模板与规则扩展：明确命名空间／可替换字段、Schema、B 正反例、C 场景和指标、风险项、语义引用与 KP 裁决队列。运行时和配置自动批准分别设置，默认关闭；公开人物与玩家已知人物分别建模。组件可直接嵌入，也可通过底层 API 自装配。NPC 家族参考 Stumpsville 的材料；其他业务模型提供自己的场景，不照搬其 NPC 探测器。细节及写入边界见[AI 修改裁决与配置包扩展](../docs/current/engineering/ai-rulings.md)。
