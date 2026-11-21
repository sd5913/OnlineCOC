# AI 聊天隔离与裁决原文验收

- 文档类型：历史
- 状态：已归档
- 归档日期：2026-11-21
- 归档原因：专项实施与验收证据保存；当前规则见关联工程文档
- 替代文档：见关联文档
- 创建日期：2026-11-21
- 最后更新：2026-11-21
- 关联文档：[会话权限](../../../docs/current/engineering/ai-session-access.md)、[裁决](../../../docs/current/engineering/ai-rulings.md)、[上下文体验](../ai-context-usability/README.md)

本轮针对 ISSUE-022：普通 KP/PL 聊天不得改变默认 AI 生成、审核和执行依据；实际引用的消息仍须复验；资料失效后保留合法交付的原文，授权撤销不恢复私密内容。UI 和包侧聊天性能由配置包会话验证，引擎查询投影由引擎会话实现，本目录不把它们的测试计入 AI 单侧分母。

## 实现与边界

- 两种 Context 模式均不自动收集聊天室。默认模型不开放 channel/chat 搜索或 room_read_chat；显式转交、选择消息保留独立证明。房间查询由服务端附 roomMode=state，识别 host-room-state；普通新消息不会改变该投影。
- 新默认任务不继承旧聊天来源的助手回答证明；用户原需求仍按非权威意图处理。所选消息编辑／撤回、真实来源变化和授权撤销仍阻止旧候选执行。
- 任务原 text、initiator 和已交付 response 与实时来源详情分开。裁决公开读取保存绑定受众的摘要交付凭证，或复用同请求合法消息发布证明；资料删除后仅恢复原 summary，不恢复动作、报告、候选和执行权。
- sourceState 区分 fresh/stale/denied。无交付证明、成员授权 epoch 变化、会话删除或受众不匹配不恢复旧正文。内部读取不冒充公开 HTTP 交付。

## 失败与复验

| 证据 | 结果 | 说明 |
| --- | --- | --- |
| reproduction.xml | 1 通过 / 6 失败 | 旧代码复现默认聊天依赖及原文丢失 |
| history-first.xml | 64 通过 / 7 失败 | 仍缺引擎 state 模式；旧测试依赖隐式聊天和已废弃权限语义 |
| history-fixed-v3.xml | 69 通过 / 2 失败 | 冻结旧引擎未支持 state；人工批次夹具在创建后改上下文摘要，已修正为真实创建流程 |
| integrated-first.xml | 104 通过 / 1 失败 | 引擎 v1 集成；HTTP 夹具误走环境代理 |
| http-direct.xml / http-bound-port.xml | 失败记录保留 | 修正监听端口；授权 epoch 变化拒绝旧数据，不等同撤销登录 Cookie |
| http-and-source-fixed.xml | 14/14 | 包含真实回环 HTTP、Edge fetch、消息编辑／撤回、权限失效、交付幂等 |

后续核心回归发现批次列表使用 batchId、没有 rulingId 导致旧批次脱敏报错，已统一凭证 key；初跑和修复见 [early-failure.xml](../ai-context-usability/early-failure.xml) 与 [ruling-key-fixed.xml](../ai-context-usability/ruling-key-fixed.xml)。最终跨项复验见上下文验收；不同轮次测试数量不相加。

## 复现

在项目根目录运行 `engineering/.venv/Scripts/python.exe -X utf8 -B engineering/acceptance/ai-chat-isolation/run_tests.py --label rerun --engine engineering/acceptance/engine-chat-interface-snapshot/v2 test_chat_isolation.py test_chat_isolation_http.py`。

脚本复制隔离树，保存源码摘要和 JUnit；work/ 忽略入库。历史 XML、源码摘要和首次失败不会被后续成功覆盖。没有调用模型 API；真实模型费用另记于上下文验收的独立账本。
