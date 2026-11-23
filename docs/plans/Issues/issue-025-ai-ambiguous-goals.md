# ISSUE-025　模糊需求中的澄清失败、写入目标误用与发布依据过期

- 文档类型：计划
- 创建及更新日期：2026-11-23
- 状态：进行中
- 问题状态：AI 正在处理技术恢复；宿主审批自生来源冲突已最小复现，待引擎修复
- 影响范围：Stumpsville 配置包的 KP 助手，DeepSeek Flash 单次样本
- 关联材料：[逐轮实录](../../../rulepacks/stumpsville/tests/ambiguous-live-report.md)、[逐轮证据](../../../rulepacks/stumpsville/tests/ambiguous-live-results.json)

## 现象及复查条件

| 场景 | 实测与影响 | 复测目标 |
| --- | --- | --- |
| “给一个玩家添点路费”缺少对象和数额 | 模型拟出了有用的澄清问题，但把 `clarification` 当作可调用工具，任务以 `TOOL_FORBIDDEN` 结束，没有交付问题正文。 | 对该输出做有界格式纠错或提示模型以澄清答复返回；用户看见一次有针对性的提问。 |
| 已指定木栗加 3 枚并通知 | 模型把搜索结果的 `ref.id` 填进 `entity.update.args.id`，预检返回 `NOT_VISIBLE`，通知因依赖项失败而被阻断。下一轮读到真实 `instanceId` 后，钱币由 3 变为 6，并送达一次通知。两轮间没有放宽权限。 | 在当前授权读取结果中区分读取引用和写入目标；若可唯一匹配，以正确实例重做预检。仍须拒绝越权与歧义目标。 |
| 庭院描述追加雨景 | 首个候选的 A/B/C 均通过，宿主 `publication.apply` 却以 `SOURCE_STALE` 拒绝。未写入任何改动。重读活动地点并按相同文本提交成功。具体来源变动仍待定位。 | 以记录的裁决 ID 和发布回执检视失效的依赖，给出可追溯原因。当实际基线或授权变化时仍应阻止旧候选发布。 |

可使用测试脚本的 `travel` 和 `courtyard` 用例从新隔离房间复跑。模型输出存在随机性，定位时以已保存的工具参数、预检项目和回执为准。

## 2026-11-23 引擎侧最小复现与委托

已在冻结引擎 performance v2、无外部写入的隔离房间复现：管理员 `roomMode=state` 搜索实际命中的 `artifacts` 片段，保存证明；候选只在既有 Lua 末尾追加注释产生新工件，按现有 A/B/C 与风险采纳正常批准。`ai.proposal.approve` committed 后，紧接的 `publication.apply` 以 SOURCE_STALE 拒绝。[失败 XML](../../../engineering/acceptance/ai-ambiguity-recovery/engine-self-stale.xml) 与[源码清单](../../../engineering/acceptance/ai-ambiguity-recovery/engine-self-stale-source.json)保留复现。

根因：稳定房间投影已排除审批／回执等控制记录，但仍枚举全部 artifacts；批准自身把候选放入 artifacts，查询集合随之改变。真实庭院用例的 `game.json` 查询还会把尚未发布的候选误作现行事实。不能忽略 SOURCE_STALE，也不能续用旧批准掩盖冲突。

本轮引擎委托仅调整该读投影：活动态查询只包含活动规则及真正需要的在途固定版本，明确区别暂存候选；保留按需历史／记录入口及权限。验收必须包括“批准暂存不使自身查询失效”“未发布候选不伪装为现行状态”“活动工件、真实业务数据或访问权限改变仍拒绝旧证明”。返回差量冻结路径和逐文件摘要供包侧叠加联合复测；其他引擎优化不在范围内。
