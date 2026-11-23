# AI 配置分步推进验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-23
- 最后更新：2026-11-23
- 关联文档：[修改裁决](../../../docs/current/engineering/ai-rulings.md)、[运行说明](../../../docs/current/engineering/ai-runtime.md)

本轮负责 AI 工程；树桩镇包的 schema 生成器、配置列表和完整 HTTP 联验由包侧维护。全程使用隔离存档和冻结引擎 v2，未修改正式房间、未做 Git 发布，真实模型 API 调用为 **0**。模型阶段使用可控 provider，宿主、发布、批次、通知、持久化、Lua worker 和浏览器均实际运行。

## 结果与范围

| 验收 | 符合预期 / 总数 | 比例 | 证据 |
| --- | --- | --- | --- |
| AI 核心回归 | 766 / 766 | 100% | [full-regression.xml](full-regression.xml) |
| 新增物品发布、持有实例、通知及会话浏览器 | 21 / 21 | 100% | [staged-ui.xml](staged-ui.xml) |
| 最后 A/B/C、分步、NPC 未写字段回归 | 78 / 78 | 100% | [final-validation.xml](final-validation.xml) |
| v2 调度和分步最终复验 | 15 / 15 | 100% | [idle-stage-final.xml](idle-stage-final.xml) |
| 真实新旧包及活动 artifact A 校验 | 10 / 10 | 100% | [pack-matrix-final.json](pack-matrix-final.json) |

各轮用例重叠，不能相加为独立覆盖，也不能作为真实 DeepSeek 的自然语言成功率。核心回归完成后增加了存量字段兼容、UI 标记及空闲等待优化；受影响范围分别由后续专项复验，未冒称在最终字节上重跑全部 766 项。[verification.json](verification.json) 列出与核心回归的源码差异和最终冻结比对。

最终接口副本为 [v2/source.json](../ai-staged-interface-snapshot/v2/source.json)，226 文件，清单摘要 `a1a4cd65d54ee3009e9c00c31792f719ce3e5da921f4049b52e926d66b76ae46`。v1 保留作包侧首轮联验依据；v2 恢复无待办时的事件等待，仅活跃续办需要定时检查，接口不变。每轮 `*-source.json` 保存具体运行树与文件摘要；`work/` 中隔离存档、临时服务和浏览器产物被 Git 忽略。

## 已验证行为

- 真实旧注册包在新增物品、完整继承紧凑 scene-actions 时返回 PACK_SCHEMA_INVALID；新包允许该结构，新增两种物品和物品／地点／NPC／规则数据修改无需改动场景。7 个合法候选全部通过 A；旧 schema 和两种非法投影修改 3 个拒绝全部符合预期。该矩阵不声称执行了 HTTP 发布或 C 玩法覆盖。
- schema 的作者声明 `x-ai-inherited-only` 仅允许命中投影原样继承；修改 digest 或 actions 均拒绝。完整作者文档通过正常 schema，未对未改文件关闭校验。
- 模型 draft 的 afterPublish 持久化到固定提案修订；只收到 approval 不续办，真实 publication 后才保存一个后续请求并派发。后续请求沿用原用户文本，模型建议独立标注，不伪装成新的用户指令。
- 新物品配置批准发布后，生成玩家持有实例与 sourceActionIndex 通知批次；第二次运行批准前无实例、无通知，批准后实例归 player1 且通知仅一份。另有改名通知用例验证重复 reconcile 不重复命令或模型调用。
- 会话归档、账号授权版本撤销、来源取消、提案改版阻止续办；记录内容篡改被存储校验拒绝。请求落盘后派发故障保留相同请求 ID，恢复只派发一次；重启已派发任务标 interrupted，不自动重放。后续模型再次造配置被拒绝并在有限修复后失败，原发布与正文保留。
- 冻结引擎连续两次发布通过；外部状态变化后的旧基线仍拒绝。包侧在施工源码上遇到的 VALIDATOR_STALE 发生于草稿创建，不能据此认定发布缺陷，也未通过放松检查修复。
- changeOverview 从完整差异产生真实 JSON Pointer、add/replace/remove 和简短概述，40 项截断仍保留总数；紧凑列表与详情一致，保留 highRisk，撤权时不通过概述泄露详情。通用会话标记“发布后继续”，刷新不会重复标记或发送请求。
- NPC 真实 Lua 治疗探针允许继承未写 location=15 的旧范围问题并记录 inheritedValidationFindings；新模板和实际写入字段严格检查。越界 HP、改为非法地点、显式写回同一个非法地点及根级复合约束均拒绝，真实探针不修改原世界。

## 初跑失败与处理记录

| 轮次 | 结果 | 原因与处理 | 后续证据 |
| --- | --- | --- | --- |
| staged-first | 8/11 | 测试把整数授权 epoch 写成字符串；读取公开会话中不存在的 requestIds；使用了不存在的 ai.approval.create。改为整数递增、仓库会话记录及 ai.proposal.approve | staged-second.xml |
| staged-second | 9/11 | 前两个夹具错误仍在。逐项修正，未改工程权限语义 | staged-third.xml |
| staged-third | 12/13 | 测试误以为默认 KP 提交必然自动派发。按实际返回显式派发 | staged-ui.xml |
| extension-live | 21/23 | 新 Lua 夹具漏掉 kp=true，被真实扩展接口检查拒绝 | extension-live-verified.xml |
| extension-live-verified | 22/23 | 新模板缺 location 数字字段，写入先被执行器拒绝；补齐合法初态 | [extension-live-final.xml](extension-live-final.xml)：23/23 |

上述失败 XML 与源码清单均保留；它们属于验收夹具错误，不伪装成业务成功或删去失败样本。

## 失败反馈与恢复

| 失败 | 当前反馈与处理 |
| --- | --- |
| PACK_SCHEMA_INVALID | A 报告保留路径及 schema 原因；更正作者注册包或候选后重新检查，不删除无关基线文件 |
| PACK_PROJECTION_EDIT_FORBIDDEN | A 明示投影只可继承，要求完整作者文档；生成器只作有限技术修复，不能把改 digest 当作恢复文案 |
| CONTINUATION_SESSION_REQUIRED / PERMISSION_DENIED | 需要原管理员会话和当前授权；不得用模型文字提权 |
| SESSION_ARCHIVED / CANCELLED / PROPOSAL_STALE | 停止或取消原续办；恢复会话只可能处理未派发阶段，不能复用旧批准 |
| 派发故障 | continuation.status=blocked，保留稳定 error 和已落盘请求；相同去重键恢复派发 |
| MODEL_OUTPUT_INVALID / PROCESS_RESTARTED | failed/interrupted 留在原任务与诊断中；不自动再次调用模型。用户核对已完成发布与回执后明确重试剩余工作 |
| 批次 unknown / partial / failed / rolled_back | 保留真实执行状态与回执，沿用原批次 reconcile；不靠换命令 ID 重新发放或提前通知 |

模糊需求推荐、已确认设计不重复询问已写入系统提示；确定性测试验证协议与状态机，不证明真实模型每次都遵循。实际包 HTTP、外部服务质量和更广泛玩法仍须按包侧联验记录判断。

## 复现

使用项目 Python，运行 `run_tests.py --label <新标签> --engine engineering/acceptance/engine-performance-interface-snapshot/v2 --core` 或指定测试文件。驱动只向本轮 work/ 和标签对应证据写入，不修改共享引擎。`verify_pack.py --help` 给出旧/新注册包、真实 artifact、隔离工程树及结果路径参数；实际输入摘要记录于矩阵 JSON，临时冻结目录不保证长期存在。

接口及状态枚举的唯一正文见[分步推进](../../../docs/current/engineering/ai-rulings.md#发布后继续运行需求)，本报告不复制接线代码。
