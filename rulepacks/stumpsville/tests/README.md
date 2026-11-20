# 配置包验收

结果文件记录各自的执行日期、检查分组与隔离输出目录；历史阶段不能直接累加为当前完整覆盖。测试默认使用独立 `tests/output/`，不操作正式房间。阶段过程、旧格式、首次失败和历史清理依据已移至[历史记录](../docs/history/2026-11-20-development-records.md)。

## 本轮专项

| 入口 | 状态与范围 |
| --- | --- |
| [过期高危审批恢复](verify_stale_approval.py) · [结果](stale-approval-results.json) | 5组通过：同档重启复现、同摘要新修订重检、再次人工接受且只发布一次、相关配置冲突保护、失败原因及原命令定位。保留首次旧引擎将拒绝沿用到新修订的失败；隔离房间、0次外部模型调用。引擎另有[23项专项及76项回归](../../../engineering/acceptance/ruling-revisions/README.md) |
| [裁决工作区](verify_ruling_workspace.py) · [结果](ruling-workspace-results.json) | 14组通过：共用卡片／三标签、1440及390px单备注三按钮、真实引用语义预览、过期正文与提示、转交关闭、403原因与定位、高危真实发布、自动归档、简短结算标签、历史弹窗、503待核对与未加载AI入口。保留早期提交状态、夹具等待及引用前置范围未启用的失败；隔离房间、0次外部模型调用 |
| [引用语义视图](verify_reference_view.py) · [结果](reference-view-results.json) | 包侧6组通过：共用角色／物品卡、390px、旧观察原内容、安全文本、未知类型回退、不改写DTO或另查当前数据 |
| [指令包通知](verify_command_notifications.py) · [结果](command-notification-results.json) | 6组通过：KP发放及改值、收件人隔离、原命令重放、离线补取、确认断线与刷新去重、失败不通知、真实重启保留。首次2组后因新增JS未加入本机静态清单而无法登录，修复后全过；未抹除首次失败 |
| [包内恢复替身](verify_ai_recovery.mjs) · [首次／修复后结果](ai-recovery-results.json) | 首次5/11；修复及补充错误形状后15/15。明确HTTP拒绝不残留unknown，网络／超时／5xx仍保留回执恢复 |
| [真实浏览器恢复／调试](verify_ai_recovery_ui.py) · [结果](ai-recovery-ui-results.json) | 6组通过：HTTP403后继续、1440/390px顶部弹窗、正文导出、重载与导出组件。保留两次夹具前置失败；不代替公网WebRTC全链路 |
| [配置矩阵](verify_ai_config_matrix.py) · [原单房间结果](ai-config-matrix-results.json) | 首轮支持6/13、预期拒绝5/6，因30秒超时及累计STORE_FULL未到达重启；分批结果不得抹除容量问题 |
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
| 布局与本地化 | [玩家布局5组](player-layout-results.json)、[一屏6组](screen-results.json)、[工作区6组](workspace-results.json)、[原UI](ui-results.json) |
| 原业务与自动裁决 | [业务](package-results.json)、[自动裁决](automation-results.json) |
| NPC扩展与发布 | [6组](ai-extensions-results.json)、[脚本](verify_ai_extensions.py) |
| 高危配置与恢复 | [9组](ai-scenarios-results.json)、[脚本](verify_ai_scenarios.py) |
| 权限与资料申请 | [3组](ai-permissions-results.json)、[脚本](verify_ai_permissions.py) |
| 玩家创作申请 | [12组](ai-player-requests-results.json)、[脚本](verify_ai_player_requests.py) |
| 来源审核与调试 | [13组](ai-review-debug-results.json)、[脚本](verify_ai_review_debug.py) |
| 查询范围与资料桥 | [范围](ai-scopes-results.json)、[资料](ai-data-results.json)、[地图／网页AI](map-ai-results.json) |

## 真实模型证据

真实测试必须显式 `--live`，遵守当前授权和配置范围。脚本使用隔离房间与服务商副本，检查原配置字节未变，记录实际调用和确认Token；原始模型工具输入留在隔离目录，精选报告不含凭据。

| 主题 | 记录与边界 |
| --- | --- |
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
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_ai_config_matrix.py --batch items
engineering/.venv/Scripts/python.exe -B rulepacks/stumpsville/tests/verify_web.py
```

先登记输入与输出范围，并确认工程依赖没有冲突占用。浏览器专项需要Edge／Playwright；Tk专项需要Windows桌面。每次只关闭自建测试进程。故障注入的预期503须在报告中说明并验证同回执恢复，不能只忽略日志。

离线还可选 `--batch npc|map|rules|restart`。`restart` 在一次真实物品发布／消费后生成两轮回环固定回答，再关闭、从同一存档重启并继续第三轮；不调用外部模型。`all` 保留单房间累计压力复现场景，可能触及默认存储限额。

支持操作、预期拒绝、模型首次成功、修复后最终成功分别统计。HTTP成功、候选可解析、检查通过、KP批准与实际生效是不同阶段。截图和原始报告位于各结果指向的独立目录；首次失败不能被后续成功覆盖抹除。

仍未完整验收：真人独立家庭／移动网、Safari与手机、长时间多人压力、原版冒险全部资料、自然语言歧义与复杂剧情联锁。现行能力见[实现](../docs/current/implementation.md)。
