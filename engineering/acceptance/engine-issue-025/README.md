# ISSUE-025 稳定房间工件投影验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-23
- 最后更新：2026-11-23
- 关联文档：[现行投影契约](../../../docs/current/engineering/chat-isolation.md)、[问题记录](../../../docs/plans/Issues/issue-025-ai-ambiguous-goals.md)

## 结果与边界

批准会先把候选工件写入 `artifacts`，旧稳定房间查询因此改变结果集，导致没有外部写入的发布仍返回 `SOURCE_STALE`。修复只修改宿主 `data_queries.py`：状态查询保留活动工件，以及 pending 规则命令和 running/waiting/needs_attention 流程固定的工件；详情附加 `artifactUsage=active|in-flight`，标签使用对应前缀。完整记录查询继续包含所有暂存、活动和历史工件。

真实 A/B/C 校验与风险采纳后，批准暂存、发布及重复回执均通过；实体变化、活动规则切换和撤权仍拒绝旧批准，工件内容及在途生命周期变化仍使相关来源证明失效。未修改来源校验、审批权限、事务或回执恢复。

## 冻结差量

[interface-v1/source.json](interface-v1/source.json) 是单文件 sparse overlay 清单，按项目根目录的相对路径覆盖 `engineering/backend/src/onlinecoc/data_queries.py`。它可叠加在 engine-performance-interface-snapshot/v2 上，与 rule-stage-delta/interface-v1 相互独立；不是完整可启动工程。该目录已释放写占用。

- 清单 SHA256：`4d5d70c57c4124552db4d16e758961b2bffe26a7ed957dc23efae780bd6b35f1`
- 代码 SHA256：`4c2f9955a6cb343c08405dbcf46e708625b45093a9c75a201a0278d7405c584a`

工件用途标记会改变引用摘要，校验器摘要也随代码更新。联测应重新读取、生成和批准候选，不沿用旧进程的查询证明或旧批准。

## 证据

| 文件 | 结果 |
| --- | --- |
| [baseline2.xml](baseline2.xml) | 修复前 1 项预期失败：真实 A/B/C 全过、approve committed、apply SOURCE_STALE |
| [backend-regression.xml](backend-regression.xml) | 104/104，通过；包含 15 项新增投影/分片/分页/发布/失效专项，以及历史权限、高风险事务、发布回执、房间版本和宿主执行回归 |
| [ai-query-context.xml](ai-query-context.xml) | 冻结 AI 查询与上下文 29/29，通过；有 1 条既有 Starlette/httpx 弃用提示 |
| [ai-wait-diagnostics.json](ai-wait-diagnostics.json) | 扩展生成用例在基线和修复树均出现 30 秒 asyncio 等待，均中断，不计通过；AI 所有者另行报告并修复关闭竞态 |
| [baseline.xml](baseline.xml) | 首次夹具未去掉无须采纳的 gameplay-risk，审批拒绝；未用作根因证据 |
| [fixed.xml](fixed.xml) | 首版修复 8 过 5 失败，暴露管理命令 pending 时没有 ruleset；随后增加筛选并纳入测试 |
| [fixed2.xml](fixed2.xml) | 修正管理命令兼容后 13/13 通过；最终增加分片与 records 测试后纳入上述 104 项 |

总计 133 项不同测试通过，15 项为本次新增专项。相关 `*-source.json` 保存每轮实际工程的逐文件摘要。所有测试使用独立合成房间、测试账号及冻结 `ai-staged-interface-snapshot/v2`，没有读取活动 AI 目录或调用外部模型。AI 新差量和包侧 16 项真实 API 复测由对应所有者联测，本目录不宣称其结果。

## 重现

从项目根目录运行 `engineering/.venv/Scripts/python.exe engineering/acceptance/engine-issue-025/freeze.py <未使用的名称>`，在该名称下生成隔离工程并写出源码清单。冻结脚本只读取当前引擎、数据管理、契约和既有冻结 AI，不读取活动 AI 目录。

在隔离工程的 `engineering/backend` 下运行 pytest：`tests/test_room_state_artifacts.py tests/test_history_context.py tests/test_high_risk_host.py tests/test_high_risk_commands.py tests/test_ai_publication.py tests/test_room_versions.py tests/test_host.py`。在同一工程的 `engineering/ai` 下运行 `tests/test_data_queries.py tests/test_context.py`。使用项目虚拟环境 Python；`work/` 被 Git 忽略，不作为正式存档。
