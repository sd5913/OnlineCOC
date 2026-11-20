# 历史文档

保存已被替代的设计与标准、已结束的调研、已完成或取消的计划及有价值的决策记录。历史文档仅用于追溯，不作为当前事实或操作依据。

归档材料保留决策背景，现行方案通过替代文档阅读。

| 文档 | 归档日期 | 原因 / 后续文档 |
| --- | --- | --- |
| [AI 玩家知识接入计划](2026-11-17-ai-player-knowledge.md) | 2026-11-17 | A0—A3 首版完成；现行见 [AI 玩家已知资料](../current/engineering/ai-player-knowledge.md) |
| [2026-11-09-room-manager](2026-11-09-room-manager.md) | 2026-11-09 | Python/LAN 迁移前材料；现行见[工程说明](../current/engineering/room-manager.md) |
| [2026-11-09-room-manager-design](2026-11-09-room-manager-design.md) | 2026-11-09 | Python/LAN 迁移前材料；现行见[工程说明](../current/engineering/room-manager.md) |
| [2026-11-09-room-manager-construction-plan](2026-11-09-room-manager-construction-plan.md) | 2026-11-09 | Python/LAN 迁移前材料；现行见[工程说明](../current/engineering/room-manager.md) |

| [主机账号维护 ISSUE-005](2026-11-05-issue-005-online-account-management.md) | 2026-11-05 | 已实现，[本机主机账号维护](../current/engineering/host-accounts.md)为现行说明 |
| [首轮 Lua 编写协议参考](2026-10-29-lua-script-reference.md) | 2026-10-29 | 原作者协议由[宿主 API 与简化方案](<../plans/project planning/lua-authoring-facade.md>)替代；旧样例仍供对照 |

归档文件使用 `YYYY-MM-DD-原文件名.md` 命名，日期为归档日期。文档顶部必须注明原路径、原状态、归档日期、归档原因和替代文档；没有替代文档时明确写“无”。如当天同名冲突，追加 `-02` 等序号。

保留原文中的决策背景。仅为修正事实错误、补充替代关系或修复链接修改历史文档，并注明修订说明。

维护规则见 [文档维护标准](../standards/document-maintenance.md)。

- [ISSUE-007 处理记录](2026-11-14-issue-007-room-version-policy.md)：旧格式自动迁移策略被后端 0.2.0 严格加载替代；[旧机器定义](2026-11-14-room-formats-before-0.2.0.json)仅供外部迁移参考，不作为运行时后备。

## 2026-11-17 ISSUE-011首版

- [工程设计归档](2026-11-17-player-knowledge-engineering-design.md)：已实现接口与原始决策，现行说明见个人知识服务。
- [施工与验收归档](2026-11-17-player-knowledge-construction-plan.md)：K0—K5及K-01—K-27完成记录。
- [ISSUE-011完成记录](2026-11-17-issue-011-player-knowledge-authorization.md)：跨入口资料授权问题及处理结果。

- [AI 阶段开发与实验记录](2026-11-20-ai-development-records.md)：取代当前文档中的阶段流水及早期完整实施计划，保留失败、复验与决策背景。

- [ISSUE-013 重启历史恢复](2026-11-20-issue-013-ai-session-restart.md)：独立只读复验与执行 epoch 分离，含首次失败及联合验收。

- [ISSUE-014 旧操作台裁决接线](2026-11-20-issue-014-ai-console-rulings-client.md)：SDK 方法与订阅补齐，含原始失败、独立8项及浏览器5项复验。

- [ISSUE-015：AI 累计存储与全历史无损压缩](2026-11-20-issue-015-ai-store-growth.md)：原始失败、方案取舍、故障与大样本验证；现行说明见工程存储文档。

- [ISSUE-016：审核连续性、语义引用与指令包通知](2026-11-20-issue-016-review-continuity-notifications.md)：三方实现边界、过期历史和生成状态修复、自动归档与单次通知、64次真实模型调用及全部失败／复验记录。
