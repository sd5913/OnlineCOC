# 配置包验收

2026-11-23：[远程 KP 专项](verify_remote_kp.py) · [本地结果](remote-kp-results.json)。真实双浏览器验证非平台房主登录预设 KP、错误密码、PL 权限拒绝、审批/开场、远程自动执行以及同平台账号切换为玩家后的隔离；未使用本机 KP 浏览器。原双玩家 18 预设 [网页回归](web-results.json) 同轮通过。

结果文件记录各自的执行日期、检查分组与隔离输出目录；历史阶段不能直接累加为当前完整覆盖。测试默认使用独立 `tests/output/`，不操作正式房间。阶段过程、旧格式、首次失败和历史清理依据已移至[历史记录](../docs/history/2026-11-20-development-records.md)。

使用 `verify_context_autonomy.py --source . --staged` 可从一次 KP 请求验证真实浏览器裁决、配置发布、同会话续办、玩家收取装备和一次定向通知。[分步验收结果](context-autonomy-results.json)使用本地模拟服务商。 2026-11-23 联合验收覆盖普通物品、武器、占槽容器、NPC、地图、场景文案和 Lua；14 项正常流程及 7 项应拒绝输入均符合预期。旧房间另在同一测试存档复现旧伴随包的场景格式错误，重启加载新伴随包后成功提交并发布物品。

[真实 DeepSeek 模糊需求实录](ambiguous-live-report.md)记录 3 个隔离房间的完整对话、工具读取、审批与生效差异。水纹盾、路费、庭院雨景分别用了 1、3、2 轮人工对话；[逐轮证据](ambiguous-live-results.json)保留失败与自动续办。

## 真实模型的模糊需求对照

[逐项对照和对话实录](ambiguous-suite-live-report.md)涵盖 16 项不同需求；[统计 JSON](ambiguous-suite-live-summary.json)记录每例目标、人工轮数、审批与调用量，[压缩证据](ambiguous-suite-live-traces.json.gz)保存工具参数、返回、候选和生效差异。旧的三例报告独立保留。运行下列命令会调用已配置的真实 DeepSeek 官方 API，需使用新的输出目录。每个用例随房间独立启动。

```powershell
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_ambiguous_live.py all --live --output rulepacks/stumpsville/tests/output/new-comparison/after --workers 4
```

对照不同工程版本时用 `--engine-root` 指向包含 `engineering/` 的冻结根目录，保持包和模型配置来源明确。单例可将 `all` 替换为 `travel` 等用例名。对 `dinner` 或 `all` 加 `--receipt-probe`，会在饭钱目标达成后，另测原会话中说“继续”和明确要求支付一笔新饭钱。两次诊断单独计数。[用例和验收条件](ambiguous_suite.py)包含运行时、配置与只读任务。使用[汇总工具](summarize_ambiguous_matrix.py)读取包含 `before/` 和 `after/` 的目录，输出到指定报告目录。可选 `guide-only/` 用于单独记录仅修改包指南的诊断样本。

完整对照的输入子目录为 `before`（优化前）、`after`（第一版）和 `after-v2`（第二版）。`guide-only`、`targeted` 分别保存两次包指南诊断。最终包指南先测 5 项并输出到 `targeted`，另外 11 项保存于 `final-rest`。汇总时核对 16 项互不重复，另保留最初五项的对照表。`drop-check` 是追加说明后的背包咨询单项复测，独立计数。只生成报告时运行 `engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/summarize_ambiguous_matrix.py <各组数据的上级目录> <报告目录>`。

## AI 聊天窗口滚动与输入

[包侧 Edge 回归](verify_player_layout.py)通过正常页面入口验证 PL 场景、独立弹窗和 KP 裁决页。将光标放在草稿中间重绘整页，检查焦点、选区和后续输入；另用浏览器原生组字事件，在组词期间重绘并提交中文。旧的整页替换方式在同一操作下丢失输入焦点。组合验证核对宿主实际提供的三个聊天组件资源与冻结版本的 SHA-256，结果为[8 组通过](player-layout-results.json)。通用组件的空闲一秒跟随、手动翻阅、触屏和周期轮询见[组件专项](../../../engineering/acceptance/ai-chat-interaction/targeted.xml)。

另一次旧版工作台套件在长裁决卡片高度断言处停止。恢复旧的整页替换方式后，同一条长申请仍为 634px，超过该套件的 125px 阈值。主持聊天输入由上述独立用例覆盖。

## 本轮专项

| 入口 | 状态与范围 |
| --- | --- |
| [官方压缩适配的包侧联合验收](official-compaction-results.json) | ISSUE-024三版AI冻结源码各219项与宿主327项逐文件核对；v1资料4、嵌入6、批次5、来源采纳4项通过，v2采纳4项复验通过，v3超大末条历史/零预算两项边界复核通过。0外部API，不计入真实长对话成功率；保留旧结果与两处独立审查发现 |
| [参考资料风险界面](verify_consultation_review.py) · [结果](consultation-review-results.json) | 4组合成DTO Edge检查通过：来源与C评估同次接受、高危整包指纹、拒绝不夹带确认、缺失证明禁用批准、运行时失败原因与390px转义；0外部API。实际服务权限／落地另见下面的联合测试 |
| [参考资料与KP采纳联测](verify_context_autonomy.py) · [旧基线](context-autonomy-baseline-results.json) · [结果](context-autonomy-results.json) | 最新4/4组通过，使用宿主KP策略v1＋AI官方压缩适配v2和真实树桩镇隔离宿主。旧基线复现CONSULTATION_ONLY；改后配置生成、缺失/错误证明与PL拒绝、包界面接受后只追加一次、运行时自动审批开启仍须接受来源评估，接受后钱币+1与单次定向通知。完整房间实体路径误拒绝已修复且沿用原查询复验；保留夹具及产品首次失败。0外部API |
| [聊天对照与恢复](verify_chat_delivery.py) · [基线](chat-delivery-baseline-results.json) · [改后](chat-delivery-optimized-results.json) · [引擎v2＋AI v1](chat-delivery-combined-results.json) | 四个真实本机页面、每组六条消息、0外部API；旧引擎固定对照接收p50从2582.56ms降至1300.74ms，p95从4410.37ms降至2223.79ms；新组合1239.04/2756.93ms。5组包括裁决处理中发送、在途新草稿、丢响应原ID恢复且只发一次、宿主历史不等待包锁、私聊/场景隔离与编辑/撤回/队伍同步。端到端含浏览器断言等待，发送输入框尾延迟仍约2秒；保留两次夹具首失败，不混同引擎纯HTTP数据 |
| [聊天与包配置依据](verify_chat_sources.py) · [基线](chat-sources-baseline-results.json) · [结果](chat-sources-results.json) | 4组通过：普通发送/编辑/撤回/已读及恢复账本使宽配置摘要变化由4/4降至0/4；真正游戏资料变化仍改变摘要；明确聊天编辑/撤回、事件裁决和权限边界保留。0外部API |
| [冻结接口组合](verify_chat_combined.py) · [结果](chat-combined-results.json) | 最新宿主KP策略v1与AI官方压缩适配v1逐文件哈希核对，4组通过：实际资料链4项、AI嵌入/调试/导出6项、原子批次5项，以及来源/导出白名单检查。使用--batch-workflow复验自动槽位修复、消耗/短休/通知和幂等恢复；本轮未重跑四页延迟，保留此前独立证据。旧PL直接资料API夹具曾被403正确拒绝，首次结果保留 |
| [默认启动与账号管理](verify_panel_defaults.py) · [结果](panel-defaults-results.json) | 10组通过：原生Tk标签与恢复状态、真实隔离宿主三个默认账号/全部AI能力和外发权限、账号创建/改密/删除/历史保留/最后KP保护、重启保持密码和关闭的权限。最新使用引擎冻结v3；0外部API。保留截图依赖、删除列表预期、输入Schema及Origin夹具首失败 |
| [C类评估裁决界面](verify_c_review_ui.py) · [结果](c-review-ui-results.json) | 5组合成DTO Edge检查通过：风险/依据/版本、三动作与可选备注、采纳提交精确证明且关窗、拒绝不附采纳证明、过期重检及390px转义。0外部API；真实发布与动态依据另外由工程联测验证 |
| [批次完整联测](verify_batch_workflow.py) · [结果](batch-workflow-results.json) | 5组通过：真实Host/AI/Edge，合成模型首次错槽位后自动修正；批准前零副作用，批准后三项及定向通知原子提交；原请求重放无额外扣物/骰子/通知，通知逐项可读。每轮2次回环调用、0外部API；保留夹具漏必填参数及CSP等待方式首次失败 |
| [逐项批次展示](verify_batch_details.py) · [结果](batch-details-results.json) | 9组合成DTO浏览器通过：业务结果与提交区分、顺序与预检、立即关窗、逐项通知与定位、阻塞禁止批准、旧首拒绝0成功、未知回执、转义与390px、终态归档。0外部调用，不代替宿主原子性验收；保留夹具JS MIME和导航竞争首次失败 |
| [本机连接性能](verify_local_performance.py) · [对照](local-performance-results.json) | 常量真实回环TCP、各12样本：代理单并发p50 324.954→6.841ms、四并发1401.274→28.385ms；四请求组合109.593→4.167ms／418.360→17.182ms。包含并发身份／Cookie槽位隔离；不等同完整引擎或模型耗时 |
| [浏览器请求合并](verify_request_coalescing.py) · [结果](request-coalescing-results.json) | 3组通过：同频道十次刷新仅一次请求、账号切换拒绝迟到旧正文、裁决十次刷新合并为当前与一次后续查询 |
| [引用标签读取](verify_ai_binding_labels.py) · [结果](ai-binding-labels-results.json) | 4组通过：200次并发标签读取仅一次文件解析、同大小／mtime原子替换仍更新、删除／旧格式清除、损坏／超限拒绝；仅保存显示绑定标签，不缓存资料或权限。首次Windows stat/fstat的ctime语义不同导致未命中，已修复且保留证据 |
| [四页面性能与生成连续性](verify_performance_workflow.py) · [结果](performance-workflow-results.json) | 引擎v2＋AI v1，6组通过：32聊天/8AI暖历史、宽room读取后生成期间私聊与实际批准、工具／校验／执行时间线、真实值变化保留回答、503恢复、390px。聊天/裁决/普通检定HTTP p50为109.28/54.57/683.13ms，各8样本；0外部API。新增长对话网格溢出首失败及修复几何数据，左队列标签不再随AI滚动出视口；旧失败继续保留 |
| [本机消息与引用连续性](verify_message_continuity.py) · [结果](message-continuity-results.json) | 5组通过：真实发送／回复时间、撤权后正文及灰引用、审核来源原玩家的一次信息揭示、写入成功后刷新失败仍显示完成、同档重启保持。首轮夹具plan未附choices而进入历史，补齐待办条件后通过；原失败保留 |
| [裁决时间顺序与固定状态](verify_queue_chronology.py) · [结果](queue-chronology-results.json) | 4组通过：混合来源实际DOM从旧到新、刷新／追加／归档、390px固定12px单行与回执恢复、灰底原文无绿色块、查询恢复清除旧提示；保留按钮最小高度导致裁切的首失败，无外部模型 |
| [本机代理错误链](verify_local_errors.py) · [结果](local-errors-results.json) | 11组通过：原9组超时、拒连、协议、资源和HTTP分类，新增共享同步池错误形状与Cookie/CSRF隔离；请求定位和安全日志、非JSON状态保留、真实回环关闭端口。未宣称复现用户旧现场异常 |
| [历史／队列／紧凑引用整链](verify_review_followup.py) · [结果](review-followup-results.json) | 6组通过：同来源复用、提交键及明确后继、持久归档恢复、执行后历史原文、PL授权语义详情、同档重启；本轮增加真实成功回执触发前驱归档及不可恢复断言。10次本地替身调用、0外部调用；保留前轮两次夹具失败及PL事务嵌套产品回归。见[ISSUE-017](../../../docs/history/2026-11-20-issue-017-review-history-queue-references.md)和[ISSUE-018](../../../docs/history/2026-11-20-issue-018-message-history-resolution.md) |
| [队列整理UI](verify_review_queue_ui.py) · [结果](review-queue-ui-results.json) | 4组通过：三动作与单备注、精确归档封套和计数、替代项禁止批准、异常DTO也不能隐藏执行中／未知／部分完成，390px无横向溢出。首轮失败来自夹具宽度叠加外边距，原结果保留 |
| [过期高危审批恢复](verify_stale_approval.py) · [结果](stale-approval-results.json) | 5组通过：同档重启复现、同摘要新修订重检、再次人工接受且只发布一次、相关配置冲突保护、失败原因及原命令定位。保留首次旧引擎将拒绝沿用到新修订的失败；隔离房间、0次外部模型调用。引擎另有[23项专项及76项回归](../../../engineering/acceptance/ruling-revisions/README.md) |
| [裁决工作区](verify_ruling_workspace.py) · [结果](ruling-workspace-results.json) | 14组通过：共用卡片／三标签、1440及390px单备注三按钮、真实引用语义预览、过期正文与提示、转交关闭、403原因与定位、高危真实发布、自动归档、简短结算标签、历史弹窗、503待核对与未加载AI入口。保留早期提交状态、夹具等待及引用前置范围未启用的失败；隔离房间、0次外部模型调用 |
| [引用语义视图](verify_reference_view.py) · [结果](reference-view-results.json) | 包侧6组通过：共用角色／物品卡、390px、旧观察原内容、安全文本、未知类型回退、不改写DTO或另查当前数据 |
| [指令包通知](verify_command_notifications.py) · [结果](command-notification-results.json) | 6组通过：KP发放及改值、收件人隔离、原命令重放、离线补取、确认断线与刷新去重、失败不通知、真实重启保留。首次2组后因新增JS未加入本机静态清单而无法登录，修复后全过；未抹除首次失败 |
| [包内恢复替身](verify_ai_recovery.mjs) · [首次／修复后结果](ai-recovery-results.json) | 首次5/11；修复及补充错误形状后15/15。明确HTTP拒绝不残留unknown，网络／超时／5xx仍保留回执恢复 |
| [真实浏览器恢复／调试](verify_ai_recovery_ui.py) · [结果](ai-recovery-ui-results.json) | 2026-11-21以引擎v3＋AI v2冻结组合再次6/6：HTTP403后继续、1440/390px顶部弹窗、正文导出、重载与网页导出组件图，无未捕获脚本错误。0外部API；保留旧夹具首失败，不代替公网WebRTC全链路 |
| [配置矩阵](verify_ai_config_matrix.py) · [单房间结果](ai-config-matrix-results.json) | 同一隔离存档连续检查物品、NPC、地图、场景文案、Lua 及重启。早期超时、容量不足、场景格式、C 类确认及地点范围问题保留在历史轮次。 |
| 分批复测 | [物品](ai-config-matrix-items-results.json)：业务7/7，原重启比较因目录排序失败；[地图](ai-config-matrix-map-results.json)：5/6，场景文案缺C覆盖，重启按ID比较通过；[规则](ai-config-matrix-rules-results.json)：6/6 |
| [同档多轮重启](ai-config-matrix-restart-results.json) | 2/2：新增物品发布并发放；配置完成后两轮固定回答，同档重启后可读并继续第三轮。3次回环替身调用、0次外部调用 |
| [去重汇总](ai-config-matrix-summary.json) · [工程交接清单](ai-repair-handoff.json) | 最新20/21：支持目标13/14（92.86%），预期拒绝7/7（100%）。场景文案仍未支持；累计存储耗尽仍未修复，分批成功不等于长时间房间验收通过 |
| [验收计划](../docs/plans/ai-restart-configuration-matrix.md) | 支持与预期拒绝分别统计，真实模型场景及未完成项以本轮结果为准 |

## 既有精选证据

下表为已保存的专项证据，是否覆盖当前修改须看报告日期及源码；不声称本轮已全部重跑。

| 主题 | 结果／入口 |
| --- | --- |
| 安全菜单与旧观察升级 | [52组汇总](menu-safety-results.json)、[菜单](verify_menu_knowledge.py)、[升级](verify_menu_upgrade.py)；包括实际AI工具载荷和同机WebRTC，未调用真实模型 |
| 个人知识 | [严格知识12组](strict-known-results.json)、[脚本](verify_strict_known.py) |
| 场景业务／恢复／浏览器 | [业务8组](scene-results.json)、[恢复6组](scene-recovery-results.json)、[浏览器4组](scene-ui-results.json)，覆盖18预设 |
| 工作台／开场／统一队列 | [工作台8组](workbench-results.json)、[开场8组](room-workflow-results.json)、[队列10组](keeper-queue-results.json) |
| 行动失败与通知 | [失败原因6组](action-reasons-results.json)、[反馈7组](feedback-results.json)、[提示10组](notifications-results.json)、[影响／地图12组](effects-map-results.json) |
| 行动耗时与动画 | [11组](action-experience-results.json)、[脚本](verify_action_experience.py)；本机样例耗时不保证跨设备表现 |
| 启动面板／槽位／LAN | [面板6组](panel-results.json)、[槽位6组](slots-results.json)、[LAN10组](lan-results.json)、[命令行5项](launcher-results.json) |
| 网页玩法 | [本机双WebRTC7组](web-results.json)、[脚本](verify_web.py)；含18预设、权限及恢复 |
| 网页公网 | [2026-11-14强制TURN8组](web-cloud-turn-results.json)；双浏览器同一物理电脑，测试证书例外，不能等同独立家庭／移动网 |
| 网页启动与导出缓存 | [诊断6组](web-startup-results.json)、[重启6组](web-restart-results.json) |
| 本机与旧P2P集成 | [5组](integrations-results.json)、[脚本](verify_integrations.py) |
| 布局与本地化 | [玩家布局与 AI 输入8组](player-layout-results.json)、[一屏6组](screen-results.json)、[工作区6组](workspace-results.json)、[原UI](ui-results.json) |
| 原业务与自动裁决 | [业务](package-results.json)、[自动裁决](automation-results.json) |
| NPC扩展与发布 | [6组](ai-extensions-results.json)、[脚本](verify_ai_extensions.py) |
| 高危配置与恢复 | [9组](ai-scenarios-results.json)、[脚本](verify_ai_scenarios.py) |
| 权限与资料申请 | [3组](ai-permissions-results.json)、[脚本](verify_ai_permissions.py) |
| 玩家创作申请 | [12组](ai-player-requests-results.json)、[脚本](verify_ai_player_requests.py) |
| 来源审核与调试 | [13组](ai-review-debug-results.json)、[脚本](verify_ai_review_debug.py) |
| 查询范围与资料桥 | [范围](ai-scopes-results.json)、[资料](ai-data-results.json)、[地图／网页AI](map-ai-results.json) |

## 真实模型证据

真实测试必须显式使用 `--live` 或对应驱动指定的 `--run`，遵守当前授权和配置范围。脚本使用隔离房间与服务商副本，检查原配置字节未变，记录实际调用和确认Token；原始模型工具输入留在隔离目录，精选报告不含凭据。

| 主题 | 记录与边界 |
| --- | --- |
| 官方机制压缩适配（ISSUE-024） | [报告](../../../engineering/acceptance/ai-official-compaction/README.md) · [统计](../../../engineering/acceptance/ai-official-compaction/comparison.json)：23次／413419tokens，旧版3/3、适配v1为0/1、v2复测3/3；HP5首次语义错误和摘要一次格式修复均保留。单组合成长历史对照：tokens下降13.68%，端到端仅下降1.96%，首项更慢；未实触发工具裁剪或上游超限。v2核心717/717＋v3差异100/100，范围不累加；v3未重复实模，离线证明确认本组三例输入选择不变 |
| 上下文与减少往返 | [工程报告](../../../engineering/acceptance/ai-context-usability/README.md)：18次／140825已确认tokens、0未知用量。3例配对严格可用率2/3→2/3；明确模板修改调用2→1、tokens14084→7082。另加跨4轮bonus13案例1/1且实际审批成功，非配对提升率。错误能力说明保留为失败，最终技术纠正尚未重跑该真实歧义例 |
| 语义压缩与KP参考方案 | [报告](../../../engineering/acceptance/ai-context-compression/README.md) · [统计](../../../engineering/acceptance/ai-context-compression/results-summary.json)：49次／912755tokens，未知0。8个支持修改目标最终8/8、全部有效请求8/9、首次任务内7/8（含技术修复）；负例零业务4/4但准确拒绝仅1/4；所有18次请求完整质量9/18。跨30轮修改HP3→4并发布/重启/创建，最终2/2业务步骤完成，保留两次压缩失败；最终输入448206→56534字节。原字段数量和不支持删除的误导措辞均保留为质量失败。单次AI完整回归692/692，不与实模分母混算 |
| 新房间默认与C类KP裁决 | [工程报告](../../../engineering/acceptance/ai-defaults-c-review/README.md) · [16个自然案例](../../../engineering/acceptance/ai-defaults-c-review/natural-1795193315656682400.json)：首轮完整7/16，终结输出格式15/15，语义复核14/15；修改首轮2/9，v3原输出重放9/9实际生效，正确拒绝2/2。43次／597278 tokens。1例预算未完成；短反馈事实查询成功但有多余来源文字，非完整提示复测。核心648/648＋Edge4/4，不与38项重复相加 |
| 全类型指令可靠性 | [工程报告](../../../engineering/acceptance/ai-command-reliability/README.md) · [71类有效参数样例](../../../engineering/acceptance/ai-command-reliability/valid-cases.json)：JSON71/71，首次严格意图63/71、独立复核67/71（含正确拒绝，非执行率）；自然槽5/7完整流程2/2，发布后消费零API5/5。199登记／198响应，已知1,556,280 tokens，未知预留44,218；首次失败、错误夹具与修复重放分开保留 |
| ISSUE-019生成快照与进度 | [DeepSeek Flash](../../../engineering/acceptance/ai-snapshot-performance/live-results.json)：1/1隔离任务，2次调用／13485 tokens，生成中闲聊、三检和隔离人工发布成功；初始预留额度阻断0调用也保留。样本先于长历史图修复，后者由200项确定性回归与包侧四页6组覆盖，未额外调用模型 |
| 本轮会话发布与需求完成 | [DeepSeek Flash](../../../engineering/acceptance/message-history/live-results.json)：2/2，10次／51510 tokens；原配置未改。生成期间30次公共HTTP查询均成功，最长0.0894秒。隔离样本未复现用户旧现场异常，不能作为所有本机连接故障已排除的证明 |
| 复活、新物品、未知资料申请 | [场景记录](ai-scenarios-live-results.json)；保留 previousRuns 与失败历史，不等于53类场景均已通过 |
| [审核身份与过期短确认](verify_review_identity_live.py) | [Flash](review-identity-live-deepseek-flash-results.json)：最终2/2，11次／169882 tokens，0次输出格式修正；[V4 Pro](review-identity-live-deepseek-v4-pro-results.json)：最新1/2，20次／324478 tokens，2次输出格式修正，未使用最终术语指南重跑。两者过期短确认均通过；首轮接口过早stale、后续钱币语义失败都保留，不能据不同指南阶段宣称模型固有优劣。全部轮次64次／1030828 tokens；正式服务配置未变 |
| 玩家原句 | [原句复测](ai-player-requests-live-results.json)：当前行动、已知线索、火把＋针剑申请，3例通过 |
| 组合申请到配置发布 | [完整复测](ai-review-debug-live-results.json)：9次调用、137337 tokens；保留首次13次／261009 tokens的失败。仅隔离发布 |
| 本轮配置增删改 | [脚本](verify_ai_config_live.py)已准备NPC、物品和地图／规则三批9例；首次在权限必填参数前置失败，0次外部调用，参数已修正。真实运行交回原授权聊天；见[范围、上限和输出](../docs/plans/ai-restart-configuration-matrix.md#分批复测与真实模型交接) |
| 早期按需查询 | [初始失败](ai-demand-results.json)、[后续链路](ai-demand-retest-validated-20261115.json)；自动passed不能代替人工答案语义审核 |
| 早期模板／批次实验 | [实验记录](ai-rulings-live-results.json)、[复验](ai-rulings-live-retest-results.json)、[后续结果](ai-rulings-live-final-results.json)，保留每轮状态 |

## 执行与结果判定

从项目根目录执行单项脚本，例如：

```powershell
node rulepacks/stumpsville/tests/verify_ai_recovery.mjs
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_stale_approval.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_ruling_workspace.py
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_context_autonomy.py --source .
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_ai_config_matrix.py --batch items
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_web.py
```

先登记输入与输出范围，并确认工程依赖没有冲突占用。浏览器专项需要Edge／Playwright；Tk专项需要Windows桌面。每次只关闭自建测试进程。故障注入的预期503须在报告中说明并验证同回执恢复，不能只忽略日志。

`verify_context_autonomy.py --source .`使用当前检出工程，在独立目录创建测试房间与本地模拟模型，不需要真实API密钥。阶段联合测试使用`--source`指向按双方摘要核对的临时组合目录；宿主临时镜像与运行存档不入库，AI只读源码快照、版本摘要及首次失败保留。`verify_chat_combined.py`用于已有本机冻结镜像的协作核对；普通克隆可直接运行当前树的各专项入口。

离线还可选 `--batch npc|map|rules|restart`。`restart` 在一次真实物品发布／消费后生成两轮回环固定回答，再关闭、从同一存档重启并继续第三轮；不调用外部模型。`all` 保留单房间累计压力复现场景，可能触及默认存储限额。

支持操作、预期拒绝、模型首次成功、修复后最终成功分别统计。HTTP成功、候选可解析、检查通过、KP批准与实际生效是不同阶段。截图和原始报告位于各结果指向的独立目录；首次失败不能被后续成功覆盖抹除。

仍未完整验收：真人独立家庭／移动网、Safari与手机、长时间多人压力、原版冒险全部资料、自然语言歧义与复杂剧情联锁。现行能力见[实现](../docs/current/implementation.md)。

## 2026-11-22 丢弃与性能排查

[验证脚本](verify_drop_performance.py)、[结果](drop-performance-results.json)：7组通过，包含真实宿主、恢复和Edge桌面/390px；本轮无外部API。10组操作计时与保存/内部HTTP计数见结果。早期两次测试设置错误、一次产品反馈标题缺失均已定位，详见[性能计划](../../../docs/plans/operation-performance-audit.md)。后续改进截图等待完成并关闭历史通知，不改变产品行为。

[四页脚本](verify_performance_workflow.py)最新使用当前工作源码，6组通过、18次本机回环模型调用、0外部API；状态/聊天/检定p50为44.87/94.48/670.63ms。此前冻结版测量保留在previousRuns与旧隔离目录，不能当作同负载A/B提升率。

补拍无遮挡界面见结果中的visualSupplement；先前截图等待错误保留在initialFailures。网页导出及脚本语法检查通过，260个受影响文档本地链接均可解析。

[包侧性能优化三轮对照](operation-optimization-results.json)记录三个独立房间、每轮十类各30样本的时延和调用计数。脚本参数 `--comparison before` 和 `--comparison after` 分别在对应源码运行，保留原丢弃基准报告。

运行 `verify_drop_performance.py --scale` 可复现 100、1,000 和 10,000 条行动的存档对照及中断恢复。使用 `--archive-backup` 可将分段存档的配对备份恢复到第二个空房间并核对同编号重试。聊天投递脚本 `verify_chat_delivery.py` 支持 `--samples`、`--latency-ms` 和 `--output-only`，额外记录提交到接收页出现正文的时间及 HTTP 传输量。

## 暴雨主线（0.10.0）

在仓库根目录运行 `engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_storm.py home`。路线参数为 `home`、`allied`、`evacuated`；追加 `--alternate` 切换替代做法。撤离主路线通过无头 Edge 确认结局。脚本使用独立的 `tests/output/storm-*/` 房间，并在同一测试数据目录重启验证。推演和覆盖范围见[故事计划](../docs/plans/story-content-expansion.md)。

本轮隔离回归还覆盖原十地点 18 个预设、最后一件库存的并发领取、浏览器手动／自动裁决，以及配置导入、预览、备份和恢复。结果分别见[场景验收](scene-results.json)、[浏览器验收](scene-ui-results.json)及[基础包验收](package-results.json)。

2026-11-23：[远程 KP 公网强制 TURN 结果](remote-kp-cloud-results.json)通过同一主持闭环及角色切换隔离；两个浏览器在同一物理电脑，实际流量经过公网 TURN，不代替真人独立网络验收。首次 60 秒页面加载等待超时，扩大有界等待后通过，未作为性能承诺。

运行 `verify_drop_performance.py --pickups` 验证物资搜索前后可见性、已知地点与角色限制、双玩家竞争、手动裁决模式下自动拿取，以及玩家窄屏页面选择物资后库存耗尽。

`--pickups` 同时校核全地点清单；即使已经达成协议、移除机关或取得许可，事件奖励仍只从原事件获取。`verify_storm.py home --alternate` 覆盖已完成委托和修泵旧申请、道具与回合的幂等核对，及结局的重启恢复。

运行 `verify_storm.py --races` 在隔离房间以两个 PL 同时提交、两个 KP 登录会话同时结算，核对首次搜查、支付口粮换蛇笛、安抚守卫、开门、有限库存、等待援队、勘路和人工修泵申请。每组自动任务重试原编号并比对完整回执；详细结果在该次房间的 `event-races.json` 中。完整行动分类见[场景行动逐项对照](../docs/current/scene-actions.md#规则配置逐项对照)。

2026-11-23 的 `verify_storm.py --catalog` 检查 40 个行动、85 个做法在满足条件时的可达性，以及各声明式步骤的完成、前置、互斥和缺货分支。最终两个独立房间的多人专项均通过，每房 10 组。两份本机记录分别在 `tests/output/event-races-9c5da529/event-races.json` 和 `tests/output/event-races-619014cf/event-races.json`。一次实际打捞失败后，另一旧请求没有再次掷骰或耗轮。两位 KP 同时批准同一项修泵工作，两人合计只消耗一个齿轮、一格密封蜡、一个回合。三种结局的主要与备用路线、恢复专项和玩家界面均另行验证。

运行 `verify_combat_map.py` 建立两名玩家和一名 KP 的隔离房间，检查蛇笼与蛛网屋事件、战斗小窗、逃跑成功与失败、多人攻击同一目标、原编号重试、胜利后的开门和角色失能。桌面 1366×768 与手机宽度 390×844 通过 Edge 验证缩放、复位及地图区域的尺寸。

2026-11-23，战斗与地图专项在当前模板和缺少战斗字段的旧模板（`--legacy-fields`）各通过一次。另复跑场景目录（40 项行动、85 个做法）、双玩家争用专项及本机双浏览器 WebRTC 回归（18 项原有预设），均通过。
