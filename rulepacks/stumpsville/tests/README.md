# 配置包验收

2026-11-19工作台收敛：[工作台8组](workbench-results.json)、[开场8组](room-workflow-results.json)、[统一裁决10组](keeper-queue-results.json)、[失败原因6组](action-reasons-results.json)共32组通过。新增[工作台脚本](verify_workbench.py)覆盖紧凑长文本与详情浮窗、原会话直达、跨页组件复用、资料全分类及搜索、独立AI权限页和390px单页布局。开场与裁决专项保留执行、隐私隔离及未知回执恢复。JavaScript/Python与隔离网页构建语法通过；截图在各报告的隔离输出目录。首轮测试修正了样例未准备、异步退出等待和嵌套浮窗定位；无产品失败被忽略。测试使用隔离存档、无头Edge和本机模拟AI，不改正式存档或调用真实模型。记录的加载时间仅是本机样例，不代表模型响应或跨设备耗时。

2026-11-19 SV-ISSUE-001：[本轮52组汇总](menu-safety-results.json)，包含[菜单9组](menu-knowledge-results.json)、[旧观察升级6组](menu-upgrade-results.json)、[严格知识12组](strict-known-results.json)、[18预设业务8组](scene-results.json)、[恢复6组](scene-recovery-results.json)、[场景Edge4组](scene-ui-results.json)及[双WebRTC网页7组](web-results.json)。分组数量不代表独立规则或测试函数数量。两名玩家的不同发现、共享状态不解锁他人、隐藏选项直提、实际AI工具载荷、旧引用／历史失效、显式重新揭示、旧待执行请求拒绝及原已提交回执恢复均已覆盖。测试使用隔离本机宿主与确定性模型，无真实模型调用、正式存档写入或云端部署；网页测试的两浏览器在同一电脑，不代表公网／跨设备验收。

复跑入口：`engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_menu_knowledge.py` 与 `verify_menu_upgrade.py`（后者同目录）。源码：[菜单专项](verify_menu_knowledge.py)、[升级专项](verify_menu_upgrade.py)。两者自建独立目录并关闭测试服务；截图在对应报告的 `output` 目录，含 KP 机制、PL 基础菜单及390px揭示后界面。初轮测试夹具／旧UI断言修正和预期中断日志见汇总；不把失败尝试覆盖成通过。现行声明、显示和升级步骤见[个人已知资料](../docs/current/player-knowledge.md)。

2026-11-18提示3秒淡出与新线索／结果：[专项10组](notifications-results.json)由[脚本](verify_notifications.py)验证3秒停留与280毫秒淡出、轮询不延期、队列独立计时、手动关闭／减少动画／换房间清理、事件与观察线索合并、重复观察仍有结果、新线索定向揭示、KP拒绝回复及检定后结果提示；计时断言使用暂停的浏览器时钟，业务断言使用隔离真实宿主。同步重跑[持久影响／地图12组](effects-map-results.json)，合计22组。网页发行构建、生成脚本语法和527项中英文／目录一致性通过；未修改正式存档或调用真实模型。截图 `output/screenshots/clue-result-notice.png`。

2026-11-18持久影响与地图：[专项脚本](verify_effects_map.py)的[12组隔离宿主／Edge记录](effects-map-results.json)覆盖获得／消耗／转交、伤害及宿主直接修改、燃烧进度、相反变化保留队列、刷新与语言切换去重、检定先后、390px布局、10条通路和观察隔离。同一脚本的 `presenter_lifecycle` 验证等待自动执行不阻挡其他变化、换房间／退出清空提示，已纳入12组记录。[知识12组](strict-known-results.json)、[场景8组](scene-results.json)、[反馈7组](feedback-results.json)同步通过（反馈脚本含预期的中断故障注入）。网页发行构建、脚本语法、524项中英文词条与目录校验通过。未改正式存档、未调用真实模型。截图：`output/screenshots/persistent-effects.png`、`persistent-effects-mobile.png`、`map-routes.png`。

2026-11-18行动失败说明：[专项6组](action-reasons-results.json)由[脚本](verify_action_reasons.py)验证准备/失能/属性/开场、耗尽/槽位/多格布局、失败编号去重与玩家隔离、KP批准失败留队及修正后执行、自动任务执行前状态变化、未知原因不泄露诊断、Edge弹窗与刷新后持久日志。[反馈7组](feedback-results.json)及覆盖18预设的[场景8组](scene-results.json)同步通过，共21组。网页发行构建、生成脚本语法及513项中英文/词条目录一致性检查通过。测试使用隔离真实宿主，无真实模型或正式存档写入；截图 `output/screenshots/action-blocked.png`。

2026-11-18统一KP裁决队列：[专项9组](keeper-queue-results.json)由[隔离验收脚本](verify_keeper_queue.py)验证真实宿主与Edge：角色草稿/行动/玩家辅助AI请求同页、AI任务分页、旧入口转向、配置风险输入保留与拒绝、原玩家转交及会话权限、响应丢失后按原回执恢复、宿主等待回应与异常流程取消。使用回环模型夹具，不调用真实服务商或修改正式存档。截图位于 `output/keeper-queue-*/unified-queue.png`。原[界面11组](ui-results.json)同步通过；旧测试对未探索目的地的名称假设改为目的地标识，遵守现行个人知识投影。网页发行构建、生成脚本语法、510项中英文/目录一致性与受影响文档链接检查通过；本轮不重跑公网/TURN。

2026-11-17行动等待与检定动画：[专项11组](action-experience-results.json)覆盖独立浏览器上下文自动执行、无骰观察、实际检定／优势骰／重伤豁免、历史去重、人工批准、玩家隔离、设置持久化、减少动画、390px、同浏览器唤醒及迟到响应防回退；[脚本](verify_action_experience.py)使用真实隔离宿主。相同当前后端下，旧前端4次样例中位耗时3672ms，当前前端1802ms；样例加入不同操作间隔，不能当作所有机器或真实局域网的延迟保证。可选 `--baseline tests/output/中的旧app.js快照` 仅比较前端；普通执行只测当前代码。原始请求分段耗时随结果保存。另复验[18预设8组](scene-results.json)、[恢复6组](scene-recovery-results.json)、[行动反馈7组](feedback-results.json)，合计32组。网页发行构建及生成脚本语法检查通过，本轮未重跑公网／TURN联测。截图位于 `output/screenshots/action-check-popup.png` 和 `action-check-mobile.png`。

2026-11-17房间槽位：[专项6组](slots-results.json)覆盖创建/选择、名称及路径约束、两套真实账号密码与进度隔离、运行锁定、最小化/停止/关闭、重开记住选择、旧版本明确报错、同浏览器/账号/端口下待恢复行动不串档；[面板6组](panel-results.json)复验AI加载、本地网页分享撤销、异常退出子进程清理及六个双击入口。脚本分别为[槽位](verify_slots.py)和[面板](verify_panel.py)，仅使用隔离目录与回环模型，不调用真实模型或部署云端。Tk验收需系统桌面；沙箱无法加载Tcl时转在桌面执行。截图在 `output/slots-*/slots-panel.png`；首次发现ASGI将宿主异常简化为通用失败并延迟退出，已改为面板后台先启动宿主，完整重跑通过。

同日按用户明确要求关闭旧面板，永久移除正式 `runtime/` 根下旧host（含账号、AI会话和存档代链）、package.json/锁、integrations（含网页缓存）及旧运行日志；不存在的备份目录无需处理，未保留旧档副本。保留独立ai-manager和服务商配置、网络偏好。这是一次性授权清理，正常关闭与槽位切换均保留数据。正式槽位库目前为空，用户命名创建后才初始化新房间。

2026-11-17 个人知识接入：[严格知识12组](strict-known-results.json)覆盖公开不披露、普通移动／身份揭示／撤回、不可变观察、实际模型载荷、旧档现在揭示、AI关闭重启和静态导出；[场景8组](scene-results.json)重跑全部18个预设与十地点流程。当前边界见[个人已知资料](../docs/current/player-knowledge.md)。以下旧日期的PL资料权限验收为当时规则，不替代本轮严格知识结果。

2026-11-16 PL桌面调整：[布局专项](verify_player_layout.py)的[5组结果](player-layout-results.json)覆盖1920／1440／1366常驻三栏、390窄屏栏目切换、聊天/AI草稿、轮询更新、浮窗拖动阈值/键盘移动/边界/账号隔离/刷新恢复、手记保存和KP本人PL视窗；仅使用本机模型夹具，打开AI标签不会调用模型。[一屏6组](screen-results.json)、[原界面11组](ui-results.json)与[地图/AI 11组](map-ai-results.json)同步通过，保留真实行动骰点和结果、筛选滚动、本地化、两名真实WebRTC玩家的AI及引用权限回归。截图在 `output/player-layout-*/player-desktop.png` 与 `player-mobile-ai.png`；验收等待原生组件异步样式加载完成后截图。本轮未调用真实模型、修改正式存档或部署云端。

2026-11-16 新增 [配置扩展验收](verify_ai_extensions.py) 与 [6 组结果](ai-extensions-results.json)，覆盖模板、动作／计算规则、一次裁决、自动配置策略、越界拒绝及重启。显式授权的 [真实 API 实验](verify_ai_rulings_live.py) 需 `--live`，实际通过／失败和用量统一见[实验记录](../../../docs/plans/ai-rulings-experiments.md)，不将首轮失败计为通过。

2026-11-16 用量统计：更新后的[地图/AI专项](verify_map_ai.py)通过9组，[结果](map-ai-results.json)包含KP读取本房间确认用量40 Token、每日不限额状态；两名真实WebRTC网页玩家验证本人用量、空账户零用量、房间汇总越权与账号注入拒绝。保留原格式、会话、回执及重启回归。使用隔离存档/本机模型夹具，无真实模型调用或云端变更。截图 `output/map-ai-ee016c25/ai-usage.png`；工程122项验收见[记录](../../../engineering/acceptance/ai-runtime/usage-results.json)。

2026-11-15 格式与会话管理：更新后的 [地图/AI 专项](verify_map_ai.py)通过 7 组，[结果](map-ai-results.json)记录本地 KP、旧咨询队列 Markdown 标题/表格、嵌入会话设置，以及两名真实 WebRTC 网页玩家的置顶、历史轮数、归档恢复和隔离。首次网页测试发现 Shadow DOM 表单事件被重定向到宿主节点，包桥改用 composedPath 后重跑通过；未放宽沙箱原生表单导航。工程侧 51 项回归及最后 4 项防重复提交复验见[证据](../../../engineering/acceptance/ai-runtime/rendering-sessions.json)。全部使用模拟服务和隔离存档；无真实模型调用、正式存档写入或云端变更。截图 `output/map-ai-6018c1a3/ai-markdown.png`。

2026-11-15 Python房间面板与生命周期更新：[面板6组](panel-results.json)覆盖真实Tk最小化/恢复、初始化与AI加载、地址复制、关闭释放、同档网页重启、公开连接信息与撤销、异常退出后无孤儿宿主及六个双击入口；[LAN10组](lan-results.json)、[AI/旧P2P5组](integrations-results.json)、[网页重启6组](web-restart-results.json)和[命令行入口5项](launcher-results.json)同期通过，共32组/项。模型使用本机模拟服务，未调用真实模型或部署云端。面板截图在 `output/panel-*/panel-running.png` 与 `panel-web.png`。Tk需正常Windows桌面；沙箱无法加载系统Tcl时转在桌面运行。命令行测试的沙箱进程树清理受限，已核实并清理自建测试进程后重跑通过；新增测试最初的重复关闭和目录列表字段断言也已修正。

同日按用户明确要求清理正式旧房间：确认host.log为STORE_LOCKED、宿主和网页适配器已脱离原启动器；先用原stop-file正常撤销网页分享，再关闭仅匹配该runtime的残留宿主。已移除runtime下host、package.json/锁、integrations、backups及旧房间日志；保留独立AI管理器和服务商配置、网卡偏好。此操作是本次明确授权的一次性清理，不是面板关闭时自动删档，也没有新增删除/迁移入口。

2026-11-15工程修复后包侧适配：核对工程实测报告中的7份源码摘要均与当前文件一致；同步咨询指南的实际计数、频道ID、只读plan与有界收尾约定，补充地图/剧情/字段单位的证据要求。[查询范围8组](ai-scopes-results.json)、[消息/裁决资料4组](ai-data-results.json)、[地图/原生AI/网页5组](map-ai-results.json)共17组通过。新增专项通过包侧公开CLI启动当前引擎，以回环模型执行实体分页、频道引用解析、聊天和NPC读取，验证HTTP协议不变、3工具轮次后仅1次无工具收尾、无草稿，并确认更新指南确实发给模型。首次新增断言误用需求text而非回复response，修正测试后完整重跑通过。该轮没有调用真实模型、改动正式存档/服务配置或部署云端；离线测试只验证接线和约束交付，不证明真实模型已遵守全部语义要求。

2026-11-15完成AI诊断、查询恢复、分页实际计数、频道业务ID指引、末轮收尾和可选behaviors校验修复。本轮[87项回归及真实调用汇总](../../../engineering/acceptance/ai-runtime/issue-009-live-results.json)保留6次隔离咨询的全部结果。最终真实查询成功枚举29实体、13配置和1频道，正常回答；但答案中未经规则核验的地图/剧情推断仍待处理，不算完整语义验收。此前[98项工程与界面验收](../../../engineering/acceptance/ai-runtime/issue-009-results.json)及10组包侧测试为前阶段证据，与本轮不累加。原3473 tokens失败记录保留，确切原因未确认，见[ISSUE-009](../../../docs/plans/Issues/issue-009-ai-live-query-diagnostics.md)。

2026-11-15追加按需查询排查（本地10组通过）：最新真实请求外发范围已全开，但没有资料查询记录；模型将未加载roomFacts误解为空房间，并仍使用旧指南快照。包指南增加先枚举、再读取、分页与空上下文语义；设置页增加旧指南/旧后台重启提示。[查询范围5组](ai-scopes-results.json)覆盖真实工具执行链及快照诊断，[集成专项](integrations-results.json)覆盖当前指南无警告、旧后台诊断字段缺失时提示重启。此处模拟服务的通过不能证明真实模型一定主动查询。

[真实模型专项](verify_ai_demand.py)必须显式 `--live`，仅在用户授权后使用当前已启用服务配置向隔离样例房间提问“查看所有房间信息并梳理”。凭据由正常宿主解析，脚本不读取或输出密钥；运行资料在忽略的output目录，精选报告不含凭据。使用新的 `--result-name ai-demand-本次英文标识.json` 保留旧结果；`--token-budget` 允许10000–200000（默认100000），`--max-output-tokens` 允许128–8192（默认2200），仅调整隔离副本。最终复验使用200000/8192、6工具轮次及最多7次请求，正式配置不变。脚本的 passed 只代表自动链路、详情与名称检查，仍须人工核对回复。原[3473 tokens失败](ai-demand-results.json)、中途失败和[最新链路通过](ai-demand-retest-validated-20261115.json)均保留；完整答案审核结果以汇总为准，不能仅看passed。

2026-11-15裁决布局与AI空查询定位：本轮31组通过，包含[查询范围4组](ai-scopes-results.json)、[地图/原生AI/网页5组](map-ai-results.json)、[本机AI/旧P2P5组](integrations-results.json)、[一屏6组](screen-results.json)和[浏览器交互11组](ui-results.json)。桌面裁决去掉页标题横栏与外层重复AI标题，原生AI填满中栏；1600×1000、1440×900、1366×768无整页溢出。顶栏折叠保留草稿、切页和刷新状态，不同登录身份互不影响；真实网页玩家同时覆盖存储桥下的折叠操作。截图在 `output/map-ai-*/kp-rulings.png`、`kp-rulings-collapsed.png`。

实际工具链确认：外发范围全关会过滤全部房间搜索结果，仅KP范围可查两只蜘蛛、守卫蛇及当前位置；`npc` 不匹配它们的显示名称，memory没有已确认事实时应为空。PL申请经KP转交仍不能读取KP专属NPC。新[查询范围脚本](verify_ai_scopes.py)使用隔离存档及回环模型服务；本轮未改真实存档、未调用真实模型、未部署云端。以下为此前阶段记录。

2026-11-15当前引擎与模块适配：树桩镇0.9.0使用Room v3和包格式2；旧升级操作、自动补字段及发现回填已移除。真实runtime已完成一次性转换，原始配对快照与完整旧房间链保存在runtime/backups/2026-11-15-current-format；30个实体、144个命令、聊天和AI scope均保留，账号库和AI历史未改。转换未保留脚本或运行入口，证据在output/current-format-faa812cf/result.json。

本轮55组通过：原业务15、自动裁决/当前格式7、场景恢复5、一屏6、启动诊断6、地图/原生AI/网页资料5、本机AI资料4、完整双WebRTC网页7（覆盖全部18预设）。

新版平台开房使用0.3.0的开房串、创建/管理/加入三页；真实双网页玩家覆盖四个AI数据查询接口与新版语义组件，本机AI资料链路覆盖消息→申请→裁决→查询及来源失效。本轮模型使用本机模拟服务，没有真实服务商调用或云端部署。下列历史阶段记录不代表当前仍提供旧格式升级功能。

2026-11-14独立页面与新版AI接入：[地图/网页AI专项](verify_map_ai.py)及[5组结果](map-ai-results.json)通过。实际宿主、两名WebRTC网页玩家和本机KP验证KP地图只列玩家（含KP本人）、PL同地点玩家与个人发现的NPC、手动揭示/隐藏、移动刷新与重启持久化；验证独立房间/地图/裁决页面、消息与裁决队列、常驻聊天、新版原生AI对话和语义引用、外发范围拒绝、跨账号/管理路由隔离、KP显式调用及未知结果按原回执恢复。AI只调用本机模拟服务，未调用真实服务商、未新增公网AI验收、未改真实存档。截图在 `output/map-ai-*/kp-map.png`、`kp-rulings.png`、`ai-web.png`。

本次重新通过6组一屏、5组本机AI/旧P2P、15组原业务、6组网页启动诊断、10组浏览器交互和4组场景浏览器回归。旧场景脚本原先等待已移除的控制台文字，改为核对实际执行器在线状态；聊天和裁决验收改走独立裁决页，重跑通过。新版组件的内部文案主要为中文；中英验收覆盖包侧外层UI，不代表上游原生AI内部已完成英语本地化。

此前2026-11-14首次地图/网页AI接入阶段：重新通过6组一屏和5组本机AI/旧P2P回归、网页及本机AI双击入口各5项；新增管理器入口以隔离关闭配置启动，验证UI、未登录拒绝与清理。入口结果在 `output/web-launcher-results.json`、`ai-launcher-results.json`、`ai-manager-launcher-results.json`。首次网页入口测试的进程清理因沙箱权限失败，核实仅为自建测试进程后清理并重跑通过。另以当时真实AI配置在隔离新存档启动，公开能力确认模块可用、deepseek-main仍停用；没有发起模型调用或修改该配置。

2026-11-14重复启动修复：新增[6组导出/重启专项](web-restart-results.json)，真实复现 `EXPORT_ALREADY_EXISTS`，验证旧导出复用、部分资源变化、导出中断、缓存损坏拒绝、同一存档下适配器及完整宿主重启。房间ID/代号与所有持久化角色字段保持一致，Edge实际玩家加载复用资源并读取角色成功；宿主重启正常轮换的 `viewToken` 单独核对。另用用户当前15个导出缓存文件的隔离副本完成连续导出，原缓存摘要未变。此轮不部署云端、不修改真实存档；启动诊断6组也重新通过。

2026-11-14公网部署后，**8组强制TURN专项全部通过**，覆盖真实云端目录、双浏览器全部18预设、私聊/权限、响应丢失恢复且不重掷、重连、资源/存储、一屏、封禁及停止分享；两连接均验证为TURN中继，测试房间已永久关闭。脚本使用独立团档和随机命名测试平台账号，未改真实团档。测试账号及关闭的房间元数据保留在云端；浏览器在同一物理电脑，不声称独立家庭实测。首次公网运行在已通过18预设后触发本地默认5秒UI断言超时；外网UI等待设为有界30秒后完整重跑通过。证据见[结果](web-cloud-turn-results.json)和[部署记录](../../../engineering/network-web/acceptance/2026-11-14-0.2.0.json)。

公网自动化浏览器使用 `ignore_https_errors` 接受测试CA；Python、宿主与部署HTTPS检查仍严格校验证书。截图：`output/web-cloud-turn-*/web-player.png`。需要真实云端验收时显式运行 `verify_web.py --cloud --relay`；默认仍为隔离本地目录，不访问云端。

2026-11-13启动诊断修复：新增6组[诊断专项](web-startup-results.json)，覆盖真实HTTP404文本、旧能力、无效/超大响应、HTTP服务错误、重定向、凭据隔离、CA缺失；失败在构建/发布前停止，真实宿主继续可用，仅本机KP可读诊断，Edge显示修复建议和日志路径且无溢出。启动诊断时只读核对云端接口为404；后续经用户授权已更新云端，该错误已消除。截图在 `output/web-startup-*/startup-error.png`。

2026-11-13，0.8.0网页接入：**7组网页专项通过，覆盖全部18个预设**；实际使用两个Edge上下文、独立平台与游戏账号、本地目录和真实WebRTC。覆盖KP离线/恢复、检定/叙述/资源/线索、真实UI已提交响应丢失与同ID恢复、过期规则停止重发、场景/队伍/私聊、懒加载、存储隔离、重连和封禁/解封、一屏视口及停止分享保留宿主，无浏览器JS异常。截图在 `output/web-*/web-player.png`。

本轮重新通过：15组原业务（含重启/配对备份恢复）、10组LAN（真实本机WLAN IPv4、Tk/双击入口）、6组一屏、5组AI/旧P2P、5项新增网页启动器。工程网页模块29项通过、2项云端跳过；P2P上游/传输相关回归4项通过、3项外部环境用例跳过。所有数据隔离，不改正式存档；上述本地阶段未部署云端、未强制TURN、未跨家庭/移动网，跳过不计通过；后续部署验收另行记录。功能与待上线条件见[网页说明](../docs/current/web.md)。

0.7.0模块接入已通过5组专项、5组新增双击入口、15组原业务及6组一屏布局回归。AI仅使用本机模拟服务；P2P使用本地目录和两名真实WebRTC客户端，本轮没有真实付费模型或跨家庭网络/TURN验收。模块细节见[接入说明](../docs/current/integrations.md)。

测试通过公开 CLI/HTTP/WebSocket 操作真实宿主；数据全部写入本包被忽略的 `tests/output/`，不使用工程存档。测试自动结束自己的服务进程，不写入正式 `runtime/`。

2026-11-13：0.6.0通过15组业务、10组页面、6组工作区、4组场景浏览器、8组全预设业务及6组一屏专项验收（共49组）。既有局域网10组结果保留其实际验收日期，本次没有改动启动或网络实现。新增覆盖KP本人随机／预设建角、审批、准备与独立PL页真实检定；玩家投影排除管理资料；场景聊天移动后的服务端读写权限、幂等与重启持久化；队伍及私聊隔离；纯文本安全显示、多私聊窗口、分会话草稿与Ctrl+Enter；中英切换、作用域拒绝、缺译回退、刷新保持语言及390px聊天布局。两套浏览器验收均未捕获JS异常。独立验证了ICU复数、参数类型错误及无效HTML模板回退。

一屏专项覆盖1920／1440／1366桌面与390窄屏、三栏边界、日志独立滚动及筛选、真实救援骰点和变化、聊天草稿、空私聊、语言切换、18个预设文本完整性和受限译文权限。截图：`output/screenshots/screen-1366.png`、`screen-english.png`、`screen-mobile-*.png`。当时385项UI及421项内容词条的覆盖边界见本地化文档。业务仍通过真实宿主接口；所有测试均未改动正式游玩存档。

2026-11-12：0.4.2扩展局域网启动10组专项并通过，已有浏览器10组回归也通过。使用实际 `pythonw.exe` 和Tk窗口，在本机真实WLAN IPv4验证网卡名称、端口与密码校验、首次准备、KP及两PL登录、Origin／本机账号控制边界、地址复制与主持页链接、占用冲突、停止释放端口、重启保留账号／存档、关闭窗口清理，以及实际 `start-lan.cmd` 的中文／空格路径。

本次新增断言覆盖KP专属房间／连线账号／IP投影、PL与预览隔离、心跳在线／失联／离线与退出清理、真实来源IP、诊断报告及密码排除。Edge使用真实HTTP局域网地址，明确断言非安全上下文，实际提交属性检定并看到结果，验证房间地址复制、近期访问折叠状态保留、390px主持页面及无JS错误。截图位于 `output/screenshots/lan-running.png`、`lan-diagnostics.png`、`lan-room-console.png`。所有客户端仍在同一物理电脑；不声称已完成跨设备或实际防火墙拦截环境验收。

2026-11-10 0.4.0通过55组验收：15组已有业务、6组通用自动裁决、7组行动反馈、10组已有浏览器交互、8组场景预设、5组场景恢复及4组场景浏览器闭环。浏览器未捕获 JavaScript 异常；包含旧地址兼容、单页面板开关/折叠/状态恢复、内嵌 KP 裁决、玩家原页结果更新、编辑手记时保留草稿、实时消息、390px窄屏及同浏览器账号隔离。

场景专项遍历全部18个预设，验证成功和失败的真实骰点、叙述、机关／库存／门／线索效果，重复领取与两玩家竞争最后一件物品，旧规则补充安装、背包已满阻止，以及主事务提交后和反馈发布时中断的恢复。自动执行使用现有已登录KP页面，不新增账号、不持久化KP凭据。浏览器覆盖离线等待、重开KP页面自动继续、主动人工申请与真实结果返回；自动队列不会显示为待KP人工批准。截图见 `output/screenshots/scene-action-*.png` 和 `scene-kp-console.png`。

反馈专项验证自动骰点、物品与位置前后值、人工申请等待/批准/拒绝、转交双方资源通知、账号可见性、重启持久化，以及“宿主已提交但反馈阶段中断”后恢复同一行动不重掷。反馈与场景恢复专项显式注入 ConnectionError，预期产生503日志，随后恢复验证通过；不是正常运行故障。业务验收同时包含配对备份恢复到第二个空目录。

2026-11-09 启动修复补验通过5项：Windows PowerShell 5.1 文件解析、真实 `start.cmd` 启动、中文/空格路径与参数透传、独立未初始化存档页面，以及测试进程清理。此前业务和浏览器脚本直接使用 Python，未覆盖 CMD/PowerShell 入口；新增测试补上这一缺口。

从项目根目录运行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_package.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_panel.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_slots.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_web.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_web_startup.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_web_restart.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_launcher.py --web
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_integrations.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_launcher.py --integrated
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_ui.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_workspace.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_screen.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_player_layout.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_automation.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_feedback.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_action_experience.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_scenes.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_scene_recovery.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_scene_ui.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_launcher.py
engineering/.venv/Scripts/pythonw.exe -B rulepacks/stumpsville/tests/verify_lan.py
```

| 证据 | 内容 |
| --- | --- |
| [panel-results.json](panel-results.json) · [脚本](verify_panel.py) | 6组真实原生面板、最小化、正常/异常退出、网页撤销、重新打开存档和六个双击入口 |
| [ai-demand-results.json](ai-demand-results.json) · [脚本](verify_ai_demand.py) | 原始3473 tokens真实失败，保留追溯，不代表当前链路结果 |
| [最新真实链路](ai-demand-retest-validated-20261115.json) · [完整汇总](../../../engineering/acceptance/ai-runtime/issue-009-live-results.json) | 87项回归、6次隔离咨询、计数核对及尚未通过的答案语义；全部尝试见汇总，不用自动passed替代人工审核 |
| [ai-scopes-results.json](ai-scopes-results.json) · [脚本](verify_ai_scopes.py) | 8组外发/PL权限交集、名称与空上下文、指南快照、分页计数、频道/NPC读取和无工具末轮；本机模拟模型 |
| [web-restart-results.json](web-restart-results.json) · [脚本](verify_web_restart.py) | 6组导出冲突、缓存完整性与同存档重复启动；截图在output/web-restart-*/restarted-player.png |
| [web-startup-results.json](web-startup-results.json) · [脚本](verify_web_startup.py) | 6组启动失败分类、保留宿主、权限、无凭据预检和真实Edge诊断页 |
| [web-cloud-turn-results.json](web-cloud-turn-results.json) · [脚本](verify_web.py) | 8组真实云端、双浏览器强制TURN、18预设及完整恢复/权限闭环 |
| [web-results.json](web-results.json) · [脚本](verify_web.py) | 7组真实双浏览器完整玩法、18预设、服务/存储边界、响应丢失恢复、撤权与生命周期；网页启动器结果在output/web-launcher-results.json |
| [integrations-results.json](integrations-results.json) · [脚本](verify_integrations.py) · [P2P 探针](probe_p2p.py) | 5组真实宿主AI会话/权限/模拟服务、P2P双玩家/边界/生命周期及KP/PL浏览器验收；截图与启动器详细结果在忽略的output目录 |
| [screen-results.json](screen-results.json) · [脚本](verify_screen.py) | 6组一屏三栏、日志与聊天、语言切换及受限内容权限验收 |
| [workspace-results.json](workspace-results.json) · [脚本](verify_workspace.py) | 6组KP独立PL视窗、场景／队伍／私聊权限与UI、多窗口草稿、本地化及重启恢复 |
| [lan-results.json](lan-results.json) · [脚本](verify_lan.py) | 10组真实Tk窗口、LAN入口、房间／在线状态及权限、诊断、HTTP浏览器提交、冲突和生命周期；pythonw无控制台，完成情况查看结果文件，失败信息在output/lan-error.log |
| [scene-results.json](scene-results.json) · [脚本](verify_scenes.py) | 全部18个预设的8组真实宿主结果、有限库存、失败后果与权限验收 |
| [scene-recovery-results.json](scene-recovery-results.json) · [脚本](verify_scene_recovery.py) | 6组当前格式、无变化同步、丢失回执、中断恢复、容量及手动开关验收 |
| [scene-ui-results.json](scene-ui-results.json) · [脚本](verify_scene_ui.py) | 4组已有KP页面自动执行、玩家过程／结果、断线继续及主动人工裁决 |
| [package-results.json](package-results.json) | 真实宿主业务、权限、幂等、回合/光源、物品碰撞、有限库存、公开/私密、聊天、版本、备份和重启/恢复 |
| [ui-results.json](ui-results.json) | Edge/Playwright，规范页面及旧地址、浮层、控制台裁决、即时反馈、消息、独立会话、1440px与390px布局及JS错误 |
| [feedback-results.json](feedback-results.json) | 7组持久行动通知、变化、隐私、人工回复及中断/重启恢复 |
| [verify_feedback.py](verify_feedback.py) | 隔离真实宿主的反馈专项及包侧故障注入 |
| [automation-results.json](automation-results.json) | 6组自动/人工裁决、宿主权限、复核、重启、规则升级结果 |
| [verify_automation.py](verify_automation.py) | 独立真实宿主的自动裁决专项脚本 |
| [launcher-results.json](launcher-results.json) | 保留的start.ps1命令行入口5项：PowerShell 5.1解析、实际HTTP启动、参数、隔离存档及清理；CMD面板入口见panel结果 |
| [verify_launcher.py](verify_launcher.py) | 独立临时目录、随机端口、不打开浏览器的启动回归脚本 |
| `output/screenshots/` | 场景悬浮面板、主持控制台及消息、地点、窄屏实际截图，可重建 |
| [harness.py](harness.py) | 隔离宿主/适配器生命周期与API账号夹具 |
| [probe_host.py](probe_host.py) | 前期核对 progress 个人记录写入权限的独立探针 |

验收记录包含检查时间和具体断言分组，不能把分组数量等同全部规则覆盖。跨设备LAN、防火墙、完整原版冒险内容、长时间多人压力场景未验收。目录中的运行账号和随机口令不入库；结果JSON与截图不包含口令。

返回[当前实现](../docs/current/implementation.md)。

- [AI 高危场景](verify_ai_scenarios.py) · [9 组通过记录](ai-scenarios-results.json)：真实公开 API、整包人工批准、新物品／入口、编号与引用校验、拒绝及重启恢复。
- [AI 权限与资料申请](verify_ai_permissions.py) · [结果](ai-permissions-results.json)：玩家主动申请、KP 预览披露、接收人隔离、全部权限开关及窄屏。
- [DeepSeek 场景实测](verify_ai_scenarios_live.py) · [结果与失败历史](ai-scenarios-live-results.json)：须显式 `--live`，隔离测试复活、新物品和未知资料申请；结果记录实际用量与失败，不修改正式房间。

- [verify_ai_knowledge.py](verify_ai_knowledge.py)：隔离两玩家验证个人进入记录、KP 定向揭示页面、公开不等于已知、复制引用越权、玩家指南及重启持久化；结果见 [ai-knowledge-results.json](ai-knowledge-results.json)。

- [PL 查询与创作申请](verify_ai_player_requests.py) · [结果](ai-player-requests-results.json)：12 组通过：本人装备语义、两玩家知识、网页与窄屏申请、KP 私有审阅、高危再批准与开关。
- [PL 原句 DeepSeek 复测](verify_ai_player_requests_live.py) · [结果](ai-player-requests-live-results.json)：显式 `--live`，隔离房间重放当前行动、已有线索和火把＋针剑需求；3 句通过，本轮 6 次真实调用、28,259 tokens；正式存档未改动。
