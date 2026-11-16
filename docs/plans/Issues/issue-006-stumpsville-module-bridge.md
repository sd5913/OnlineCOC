# ISSUE-006：树桩镇 P2P、网页与 AI 完整玩法接入边界

- 文档类型：计划
- 状态：进行中
- 创建日期：2026-11-13
- 最后更新：2026-11-14
- 关联文档：[问题索引](README.md)、[公网模块](../../current/engineering/network-p2p.md)、[网页调整规划](../stumpsville-web-integration.md)、[AI 接入计划](../stumpsville-ai-integration.md)、[包侧已实现接入](../../../rulepacks/stumpsville/docs/current/integrations.md)
- 问题状态：网页服务/存储桥及完整玩家UI已完成本地/公网强制TURN联测；真人跨网络验收与AI上下文/发布仍待完成
- 当前版本：本地network-p2p 0.2.2、network-web 0.2.0、树桩镇0.8.0；云端已更新到0.2.2/0.2.0（初次复现基线为 network-p2p 0.1.0）
- 优先级：完整公网玩法的阻塞项

## 现象与预期

旧P2P入口可借用实际游戏宿主、通过真实 WebRTC 登录和使用通用状态/聊天。旧联网适配器只允许通用 `/api/v1/` 白名单；树桩镇依赖 `/package/state`、`/package/action`、`/package/chat/history` 及已登录 KP 页面自动执行预设行动。这些包侧接口无法通过旧P2P桥使用。`ai/*` 同样不在联网白名单中。版本2网页桥另行提供按声明和逐玩家权限的有界传输，不开放任意 URL 或文件。

上述现象仍适用于旧P2P入口。2026-11-13用户明确授权工程侧例外及S0–S3实施后，network-web 0.2.0增加独立的版本2包服务/存储桥，原核心白名单保持不变；树桩镇0.8.0已提供沙箱发行包并通过本地双浏览器完整玩法。当前说明见[网页接入](../../../rulepacks/stumpsville/docs/current/web.md)，公网部署和后续验收见[规划](../stumpsville-web-integration.md)。原始AI路由仍不开放；2026-11-14已通过 `POST package/ai` 的严格个人咨询白名单接通网页会话、提交/取消和回执，KP转交仍在本机完成。本地双浏览器与模拟回复已验收，详见[5组专项](../../../rulepacks/stumpsville/tests/map-ai-results.json)。

AI 可以通过包侧 companion manifest 启动并提供个人会话、KP 转交及咨询回复。原根 manifest 包含 `name/status/entry/contentLicense` 等键，而 AI Pack 的根 manifest 采用严格键集合；简单添加 `ai/manifest.json` 不会覆盖已有根 manifest。此点为文档和源码核查，未把启动失败作为实际复现证据。包侧已通过显式 `--ai-pack` 指向生成快照解决本轮启动问题，不需要修改内核。

AI 上下文仍只包含通用宿主授权实体/聊天，无法直接读取包侧的个人线索、笔记、行动日志及场景/队伍聊天。AI publication 若直接修改通用宿主规则，会与包侧 `activeRevision`、修订表及备份恢复账本缺少共同提交保证。当前包侧代理明确拒绝草稿/审批/发布；未验证此跨账本发布流程。

## 实际复现与证据

以下为最初包侧基础接入验收，不是本次文档更新重新执行的测试。在项目根目录使用现有宿主 Python 可运行 `rulepacks/stumpsville/tests/verify_integrations.py`。所有房间、目录服务、模拟 AI 服务与玩家缓存都位于该包 `tests/output/`，不使用工程存档或云端凭据。

1. 包侧启动真实宿主，公开 CLI 启动联网本地入口，经 `/local/host/start` 借用宿主。
2. 两个 `onlinecoc_p2p.client.Player` 分别完成准入、登录及内容确认，能读取各自投影、发送基础聊天并订阅快照。
3. 同一真实 DataChannel 请求 `package/state`、`package/action`、`ai/tasks` 和 `host-control/accounts`，均得到 `ROUTE_NOT_EXPOSED`。最后一项应始终保持拒绝，作为权限负例。
4. 关闭 P2P 后目录撤房，原游戏宿主与角色状态仍可访问。
5. AI 通过显式 companion pack 启动；PL 自有会话→KP 转交→回环模拟服务回复成功，PL 不能读取模型回复或他人会话，人物状态不变。真实服务商与跨网络环境未在本轮测试。

证据脚本：[模块验收](../../../rulepacks/stumpsville/tests/verify_integrations.py)、[双玩家探针](../../../rulepacks/stumpsville/tests/probe_p2p.py)。本地结果位于 `rulepacks/stumpsville/tests/output/integrations-results.json`，只记录断言与边界，不记录凭据。

## 处理进展与责任边界

已按授权增加版本化包侧服务能力、来源及路径/参数白名单、逐玩家Cookie/CSRF、请求/响应与超时限制；状态沿用轮询，动作沿用原命令ID和幂等。受限存储按平台/房间/游戏账号/包/资源版本隔离。远程KP、任意URL、初始化、包导出、主机控制和AI请求继续拒绝。契约见[工程说明](../../current/engineering/network-web.md)。

配置包已实现固定模块图打包、最小启动组、按需英文/头像、MessageChannel传输和存储适配；未导出完整原包。[7组本地网页验收](../../../rulepacks/stumpsville/tests/web-results.json)及部署后的[8组公网强制TURN验收](../../../rulepacks/stumpsville/tests/web-cloud-turn-results.json)覆盖全部18个预设、两玩家、权限、恢复及撤权；原AI/旧P2P专项重新通过。云端新桥已部署，真人独立家庭/移动网及AI事项仍待完成。

AI 作者侧先确定首个配置扩展点、独立检查、场景与指标；包侧可提供经过已有授权投影的上下文适配器。工程侧需要明确动态包侧来源的授权/版本验证方式，以及配置发布与包侧修订账本的共同提交或可靠通知接口。是否需要修改核心待方案评估，不预设全部问题都属于内核缺陷。

## 验收条件

- 两名公网玩家在沙箱中实际完成登录、建角、场景移动、预设检定、结果变化、线索和多频道聊天，普通动作不需要额外手工命令。
- 包侧与 AI 路由只按声明暴露；跨账号、KP 私密信息、原包完整下载、host-control 和本机管理令牌访问持续拒绝。
- 断线、重连、重发、撤房不产生重复扣除；P2P 分享停止不关闭借用的游戏宿主。
- 包侧 AI 上下文逐来源授权，外发默认关闭，引用版本过期时重新审核。
- AI 配置候选通过作者 A/B/C 检查、KP 审批及包侧修订账本一致性验收后才开放发布与恢复。

初次包侧接入未修改 `engineering/`；接口施工阶段未部署云端；用户随后明确授权更新，已于2026-11-13部署新桥并备份云端账号/房间状态，未改真实团档。本问题部分解决：网页完整玩法本地及公网强制TURN闭环已通过；真人跨网络和AI上下文/配置发布事项保持开放。

2026-11-14追加：树桩镇已按新[配置包嵌入指南](../../current/engineering/ai-pack-embedding.md)接入原生紧凑对话组件；KP裁决页内嵌，PL使用弹窗。公开资源固定图、语义引用查询/解析及外发复验已接线；配置发布仍关闭，包侧独立场景/笔记不是核心引用来源。实际功能与本地双浏览器证据见包侧当前接入和测试文档。
