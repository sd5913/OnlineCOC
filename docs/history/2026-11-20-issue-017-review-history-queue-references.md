# ISSUE-017：历史回复遗漏、重复裁决与紧凑玩家引用

- 文档类型：历史
- 状态：已归档
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 原路径：docs/plans/Issues/issue-017-review-history-queue-references.md
- 原状态：进行中
- 归档日期：2026-11-20
- 归档原因：三方实现与隔离联合验收完成，保留首次失败、产品回归及复验依据
- 替代文档：[来源审核](../current/engineering/ai-debug-review.md)、[包侧调试](../../rulepacks/stumpsville/docs/current/ai-debugging.md)、[使用说明](../../rulepacks/stumpsville/docs/current/usage.md)
- 关联文档：[问题索引](../plans/Issues/README.md)、[前轮完成记录](2026-11-20-issue-016-review-continuity-notifications.md)、[AI验收](../../engineering/acceptance/review-followup/README.md)、[引擎契约验收](../../engineering/acceptance/queue-schema/README.md)

## 完成结果

1. 资料版本变化但仍获授权的原需求、AI回答和裁决摘要继续显示，旁边标注依据变化；历史只用于理解旧意图，执行仍重新校验当前资料。真正没有生成正文的失败不虚构回答；撤权、删除或无法证明的旧资料继续受限。
2. 同次提交使用稳定 submissionKey，普通发送与直接创作申请断线重试均复用；同包来源和要求重复转交复用审核任务。包按真实 request/event、flow/wait 关系提供 correlationKey，避免只凭相似文字或同玩家猜测。
3. “继续此请求”明确关联同问题的后继；只有新候选已通过检查，才将同关联旧未执行候选移入已归档，旧候选在服务端也不可再批准。归档保留原业务状态、正文、回执及前后方案入口；无明确关联的中间项可手动归档和恢复。恢复不解除已被替代关系。执行中、结果未知和部分完成仍待核对。
4. PL严格知识输出及旧版格式化器均改为名称、短说明和引用入口，不在正文铺完整属性／行动树；点击复用包的授权语义详情。通用格式由AI模块负责，Stumpsville负责语义视图与队列接线。

## 最终验收与适用边界

各层分别统计，重复运行不累加为新增用例，以下通过率不是付费模型理解成功率。

| 验证范围 | 结果 | 证据 |
| --- | --- | --- |
| AI历史、授权、提交去重、队列整理、通用组件 | 去重后的最新记录230/230；最后一轮公共路径61/61 | [汇总](../../engineering/acceptance/review-followup/results.json)、[失败与复验说明](../../engineering/acceptance/review-followup/README.md) |
| 严格命令Schema | 55/55；其他20个操作契约未改变 | [结果](../../engineering/acceptance/queue-schema/results.json) |
| 包与真实宿主整链 | 6/6：同源复用、关联后继、归档恢复、执行后原文、PL点击引用、同档重启 | [结果](../../rulepacks/stumpsville/tests/review-followup-results.json)，最终目录 `tests/output/review-followup-34c2f048` |
| 裁决工作区回归 | 14/14，含高危真实发布、390px、失败定位、来源语义视图及历史标签 | [结果](../../rulepacks/stumpsville/tests/ruling-workspace-results.json)，最终目录 `tests/output/ruling-workspace-f4ba8b50` |
| 包侧独立队列UI | 4/4，含异常DTO不能隐藏未明执行结果 | [结果](../../rulepacks/stumpsville/tests/review-queue-ui-results.json)，最终目录 `tests/output/review-queue-ui-18e5f040` |
| 来源关联纯检查／网络恢复 | 6组／15组通过；本轮未重跑旧来源审核的完整13组集成 | [纯检查](../../rulepacks/stumpsville/tests/output/ai-review-debug-cfc40a45/report.json)、[恢复](../../rulepacks/stumpsville/tests/ai-recovery-results.json) |
| 单页导出 | 重建及Node语法检查通过，未重跑公网WebRTC | [构建记录](../../rulepacks/stumpsville/tests/output/review-followup-export-20261120/build-validation.json) |

全部使用隔离存档和确定性替身，0次外部模型调用、0计费Token；最终整链为10次本地替身请求。正式存档及服务商配置未改写，也未重启正式宿主。当前运行进程需重启加载新版工程代码，浏览器需刷新；已分发的单页网页需重新导出后使用。各层仍以既有权限为上限，高危变更仍需人工审批。

### 保留的失败及处置

- 包整链首轮 `81c6ee3f` 漏显式派发KP任务，第二轮 `2ae30022` 将实际“资料依据已变化”误断言为“过时”，均为夹具问题。
- 第三轮 `bac28d7d` 确实复现PL公共提交被 `TRANSACTION_NESTED` 阻断，是本轮并发硬化引入的产品回归；AI方修复已持有事务的复用，最后6组整链及61项公共路径复验通过。三轮原始结果均留在汇总 previousRuns 与各自输出目录。
- 独立队列UI首轮 `7f67acaf` 的窄屏断言失败来自测试主区域 `width:100%` 叠加外边距，修正夹具后通过，未以修改产品CSS掩盖。
- 单页构建首次将命名导入 `requestId as newSubmissionKey` 原样放入解构导致语法错误；包构建器补齐别名转换后重建通过，构建报告保留首次原因。
- AI方生成中草稿归档、取消后仍列active、历史文本节点及直接创作重试等首次失败、夹具故障和产品修复，见AI验收说明及对应XML。

## 现象与影响

用户在前轮升级后反馈：旧AI消息在相关内容变化后仍只剩 SOURCE_STALE 和“原操作状态保留”等提示；同一请求可能生成多个裁决；同事件的中间申请挤占待处理列表；玩家提问后的引用展开成大量“已记录行动／条目／属性”树，正文难以阅读。

截图证据为本轮用户附件 `codex-clipboard-2e827878-ab12-4b8c-ad29-508d0bffac99.png`、`codex-clipboard-1b0589ab-da2b-498e-8c25-c386856e91ae.png`。截图不能单独证明后台丢失了原文，需分别核查服务端历史授权与通用组件渲染；不把真实生成失败伪装成存在回答。

已核查包侧：`keeper-queue.js` 将无 proposalId/batchId 的 needs_input/blocked/failed/interrupted/stale 任务列为待处理；只按终态分流，缺少“已转交／已替代／手动收起”的持久标记。`keeper-rulings.js` 对所有非终态裁决逐项显示。仅用文字相似或同一会话自动合并，会误伤不同业务。

## 责任边界与步骤

1. AI模块负责历史原文读取／渲染修复、权限不变、稳定请求去重、显式关联的后继关系及可追溯队列整理接口；不能只在前端隐藏服务端仍可批准的重复候选。
2. 通用玩家回答组件负责引用的紧凑入口与说明，详细授权内容留在点击后的引用视图；不能使用未核验的模型自由文本取代严格玩家知识输出。
3. Stumpsville负责队列状态和操作接线、已有语义详情复用、指南说明及真实宿主／浏览器联合验收。需要的引擎接口由工程责任者维护，本包不编辑工程代码。
4. 优先确定性与浏览器复现。不得改写正式存档或默认调用外部模型；保留首次失败与修复后证据。

## 验收条件

- 已完成回复在允许读取的资料版本变化后仍显示原文和过期提示；生成真正失败但从未有正文时只解释失败。撤权、删除、跨作用域仍不泄漏，原执行状态与回执不丢失。
- 同一显式来源的重复提交／转交复用任务或审核会话；关联的新版本有替代关系，旧版不可继续批准；不同玩家、不同目标和不同未关联请求不能被误合并。
- 无需继续处理的中间请求可持久整理进已归档，刷新、重启不再挤占计数，能从历史查看来源和后续项。执行中、结果未知、部分完成不得自动隐藏或当成未执行。
- PL聊天显示与问题相关的短答案或已知范围、引用名称／简短说明和查看入口，不默认展开整棵字段树。引用详情仍复用授权视图，旧观察不套用当前事实；验证窄屏和无关资料不铺满正文。

## 实施过程（归档时保留）

- 已将用户原始现象和接口需求通知 AI 模块责任者；包侧开始核查和准备联合验收，尚不声明以上变更已完成。
- AI方已确定待实现契约：统一 `ai.queue.archive {targetId,digest,archived,reason?}`，归档必须提供原因；DTO提供 `queueTargetId/queueDigest/queueStatus/correlationId/canArchive/canRestore/archived/archiveReason/supersededBy/supersedes`，业务status与回执不改。明确关联由包 `source.correlationKey` 或同会话 `replyToRequestId` 提供；`submissionKey` 用于同次提交去重。只有已验证的新候选可替代同关联旧待审项。
- 引擎子任务限定为 `engineering/contracts/ai-operations.json` 的命令Schema同步，由引擎责任者与AI方对齐精确参数；不修改宿主执行或通知实现。共享路径需AI方先释放使用登记，引擎方完成后再释放以供联合测试。
- 引擎Schema已完成，55项通过。包侧来源关联6组、既有网络恢复15组、独立队列UI4组和整包工作台14组通过。真实宿主新联测已证实同源复用、显式后继替代、归档恢复及执行后历史原文保留；首轮漏显式派发、第二轮“过时”与“资料依据已变化”文案断言差异均保留，PL与重启尚待完成。包网页构建的命名导入别名转换缺陷已修，Node语法检查通过。
- AI方另复现生成中草稿可归档、取消关联请求后队列状态仍active两个边界；包已释放AI读取占用，由AI方补修后再冻结联合复验。不得把阶段通过计数简单累加为最终独立用例数。
- 硬化后第三轮真实联合验收通过前4组及原工作台14组，但PL公共提交被 `TRANSACTION_NESTED` 阻止，记录于 `rulepacks/stumpsville/tests/output/review-followup-bac28d7d/report.json`；该项是产品回归，与前两轮夹具失败分开。已交AI方修复自动派发的事务嵌套，并补直接创作申请断线重试提交键；PL引用和重启仍需完整复验。
- 最后复验已完成：6组真实宿主整链全部通过，PL引用实际点击详情及同档重启均成功；14组工作台与4组独立UI通过，最终报告包含源码摘要，AI方230个独立用例最新记录及引擎55项契约分别通过。以上早期“待完成”只保留为施工过程，不代表交付状态。
