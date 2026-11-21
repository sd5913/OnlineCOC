# 更新问题记录

此目录存放后续更新需要讨论、修复或验证的问题，属于计划材料；问题存在不等于已承诺实施。每个问题单独建文档，使用稳定编号和英文文件名，例如 `issue-002-launcher-upgrade.md`。

## 新增问题

复制 [问题模板](issue-template.md)，填写现象、复现方法、影响、相关证据、候选处理方式和验收条件，并在下表登记。未确定的处理方式保留“待讨论”，不要写入当前工程能力说明。完成后把已确认实现同步到 `docs/current/engineering/`，有追溯价值的问题按 [维护标准](../../standards/document-maintenance.md) 归档到历史目录。

| 编号 | 问题 | 问题状态 | 正文 |
| --- | --- | --- | --- |
| ISSUE-001 | Lua 编写体验简化与独立作者试写 | 待独立试写 | [既有设计议题](<../project planning/Issue/lua-authoring-simplification.md>) |
| ISSUE-002 | 桌面工具窗口交互验收 | 待交互验证 | [正文](issue-002-desktop-interaction-validation.md) |
| ISSUE-003 | 配置包多人协助与结构化裁定接入边界 | 包侧已实现并验证，待工程责任者复核记录 | [正文](issue-003-rulepack-cooperative-ruling.md) |
| ISSUE-004 | 配置包在线恢复与组合管理事务边界 | 文档／接口已核查，待方案确认 | [正文](issue-004-mini-pack-management.md) |
| ISSUE-005 | 简易账号工具与在线身份管理接口 | 已实现并验证，已归档 | [历史记录](../../history/2026-11-05-issue-005-online-account-management.md) · [现行说明](../../current/engineering/host-accounts.md) |
| ISSUE-006 | 树桩镇 P2P、网页与 AI 完整玩法接入边界 | 网页桥及完整玩法本地/公网TURN通过；真人独立网络和AI上下文/发布仍开放 | [正文](issue-006-stumpsville-module-bridge.md) |
| ISSUE-007 | 移除旧房间格式兼容与版本迁移责任 | 已实现并归档；0.2.0 仅支持 Room v3 | [正文](../../history/2026-11-14-issue-007-room-version-policy.md) |
| ISSUE-008 | 通用请求与裁决记录模型 | 已评估；推荐双模型与读取试点，宿主接线待实施 | [正文](issue-008-generic-request-decision.md) |
| ISSUE-009 | 真实AI查询失败与异常诊断缺口 | 工程缺陷修复、87项回归及真实查询通过；完整答案语义待验收 | [正文](issue-009-ai-live-query-diagnostics.md) |
| ISSUE-010 | 配置包业务事务与 AI 批次接入 | 配置删除已实现；通用包业务注册、回执与跨存储事务仍待实施 | [正文](issue-010-ai-package-mutations.md) |
| ISSUE-011 | 通用个人知识记录与跨入口授权投影 | 首版已实现并验收，已归档 | [完成记录](../../history/2026-11-17-issue-011-player-knowledge-authorization.md) · [当前服务](../../current/engineering/player-knowledge.md) · [验收](../../../engineering/acceptance/knowledge/README.md) |
| ISSUE-013 | AI 重启后历史读取与继续对话 | 已实现并联合验收，已归档 | [完成记录](../../history/2026-11-20-issue-013-ai-session-restart.md) |
| ISSUE-012 | 已授权资料的语义展示契约 | 待引擎责任者评估；AI 通用排版兜底已实现 | [正文](issue-012-authorized-data-presentation.md) |
| ISSUE-014 | 旧操作台缺少 AI 裁决客户端方法 | 已实现并浏览器复验，已归档 | [完成记录](../../history/2026-11-20-issue-014-ai-console-rulings-client.md) |
| ISSUE-015 | AI 全量快照累计导致存储提前耗尽 | 无损压缩已实现并隔离验证，已归档 | [完成记录](../../history/2026-11-20-issue-015-ai-store-growth.md) |
| ISSUE-016 | 审核会话连续性、引用视图和指令包通知 | 协作实现及隔离联合测试完成；保留真实模型失败／复验，已归档 | [完成记录](../../history/2026-11-20-issue-016-review-continuity-notifications.md) |
| ISSUE-017 | 历史回复遗漏、重复裁决与紧凑玩家引用 | 三方实现及隔离联合验收完成，已归档 | [完成记录](../../history/2026-11-20-issue-017-review-history-queue-references.md) |
| ISSUE-018 | 会话交付记录、需求完成归档与本机连接诊断 | 三方实现及联合验收完成；旧现场异常未复现，已归档 | [完成记录](../../history/2026-11-20-issue-018-message-history-resolution.md) |
| ISSUE-019 | 本机交互性能、生成快照与过程展示 | 三方实现及四页联合验收完成，保留性能边界，已归档 | [完成记录](../../history/2026-11-20-issue-019-performance-generation-progress.md) |
| ISSUE-020 | 批次零成功误显部分完成与物品槽位混淆 | 隔离修复与自然槽5/7复验通过；待正式跑测及泛化观察 | [正文](issue-020-batch-partial-slot-diagnostics.md) |
| ISSUE-021 | 新房间默认AI、账号管理与C类裁决 | 三方实现及隔离联合验收完成，已归档；API未覆盖和表达约束单列 | [完成记录](../../history/2026-11-21-issue-021-ai-defaults-c-review.md) |

| ISSUE-022 | 裁决状态栏、过期原文、聊天隔离与上下文体验 | 三方实现及联合验收完成，已归档；模型语义失败与小样本边界保留 | [完成记录](../../history/2026-11-21-issue-022-chat-isolation-ruling-status.md) |

| ISSUE-023 | 上下文压缩、KP自主方案与主分支发布 | 三方实施与实验中 | [正文](issue-023-context-compression-kp-autonomy.md) |

ISSUE-001 的正文仍在原位置，本目录只链接它，不复制成第二份。后续新问题统一从本目录登记；编号从 ISSUE-024 继续。配置包作者仅记录证据与需求，由工程责任者判断并处理工程侧问题。与当前功能、版本和运行相关的事实见 [工程索引](../../current/engineering/README.md)。
