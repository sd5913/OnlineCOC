# ISSUE-021：新房间默认AI、账号管理与C类裁决

- 文档类型：历史
- 状态：已归档
- 创建日期：2026-11-21
- 最后更新：2026-11-21
- 原路径：docs/plans/Issues/issue-021-ai-defaults-c-review.md
- 原状态：进行中
- 归档日期：2026-11-21
- 归档原因：三方实现与隔离联合验收完成，模型实验边界单列
- 替代文档：[默认与账号](../../rulepacks/stumpsville/docs/current/usage.md)、[AI裁决](../current/engineering/ai-rulings.md)
- 关联文档：[统一计划](2026-11-21-ai-defaults-c-review.md)、[问题索引](../plans/Issues/README.md)

## 初始证据与期望

只读核查：PanelWindow与命令参数默认ai=false，新槽位要求手填初始密码；宿主已有本机身份查询、创建、改密，未有删除；AI的allowPlayerChat默认false，读取能力与资料外发分别控制。EXTENSION_FORBIDDEN会出现在多个检查位置，LIVE_SCENARIO_COVERAGE_MISSING来自实况场景覆盖检查；不能仅靠前端忽略报错实现KP决策。

用户要求的默认值、C类评估裁决及动态依据见统一计划。由引擎与AI责任会话补工程能力，包侧接线并联合验证；正式房间不做迁移或实验。最短复现、实际接口、首次失败与验收结果在统一计划和各模块报告记录。

## 复现与处理结果

原面板新建槽位可复现AI默认未选及手填密码；AI准备C覆盖不足候选后，原流程直接拒绝，缺乏人工采纳与动态依据。包侧无法通过忽略错误解决，已由引擎、AI责任方和包侧共同接线。新默认、账号管理和两种C风险的真实发布／消费已通过，详细实现与分阶段测试口径见统一计划。首次`INPUT_INVALID`来自房间Approval格式遗漏，另有服务关闭后依据读取器失效，均保留失败并完成修复。
