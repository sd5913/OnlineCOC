# 高危发布与 KP 授权读取验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-19
- 最后更新：2026-11-19
- 关联文档：[接口与行为](../../../docs/current/engineering/high-risk-publication.md)

全部测试使用隔离的临时房间与固定夹具，不修改正式存档、不部署、不调用外部模型。

## 已记录运行

| 文件 | 结果 | 范围 |
| --- | --- | --- |
| core.xml | 初跑 14 通过、1 失败 | 测试构造的查询证明 initiator 与读取参数不一致；修正测试输入，保留初跑记录 |
| core-retest.xml | 15 通过 | 高危判定、最终配置图、引用／依赖、KP 范围、私聊外发、撤权与大文本分片 |
| host-transactions.xml | 23 通过 | 上述 15 项和 8 项真实 Host 命令事务测试 |
| backend-regression.xml | 122 通过 | 常规宿主、聊天室、知识、模型契约、存档版本、故障与恢复 |
| host-final.xml | 26 通过 | 高危专项及 3 项可选 read_scoped／授权撤回／旧适配器兼容 |
| ai-host-regression.xml | 28 通过 | 实际 Proposals、真实 A/B/C、明确批准、幂等发布、恢复、备份 |
| probe-first.xml | 初跑 34 通过、2 失败 | 测试伤害规则依赖未包含，在线测试命令缺目录修订；修正测试夹具 |
| probe-second.xml | 复跑 35 通过、1 失败 | 在线权限校验抛 DomainError，测试错误期待 rejected 回执；修正断言 |
| probe-final.xml | 36 通过 | 26 项高危专项与 10 项真实 worker／在线宿主私有探针边界 |
| post-probe-integration.xml | 17 通过 | 最终 worker/AI 补丁后：12 项私有探针（含 AI 包装接口）、3 项真实三检审批发布／重启、2 项 Lua 执行／资源隔离 |

按测试 ID 去重，最终 **188 项通过，无未解决失败或跳过**；各轮不能直接相加。原始记录、初跑问题、最终代码及契约摘要见 [results.json](results.json)。28 项完整 AI 宿主回归在私有探针补丁前运行；其后 17 项补验覆盖变化的 worker／AI 包装路径及关键批准发布，不声称对补丁后的全部 28 项重新运行。

`test_high_risk_commands.py` 使用真实 Host、Schema、摘要、账号、存储与命令事务；PreparedBundle 的 A/B/C 报告由受信合成 resolver 提供，固定检查器代码指纹以隔离并行 AI 施工。它验证宿主强制边界，不计为真实 A/B/C 证据；实际 Proposals 与包检查器的证据来自上述联合运行。

常规回归包含一条 Starlette TestClient 的 httpx 弃用提示，不影响测试结果；本轮未更换依赖。

## 复验

从项目根目录执行，先登记源码、夹具的使用及输出目录的改动；确认 AI 检查器源码稳定后运行联合用例。不要对尚有人改动的源码启动会计算检查器摘要的测试。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
engineering/.venv/Scripts/python.exe -B -m pytest engineering/backend/tests/test_high_risk_host.py engineering/backend/tests/test_high_risk_commands.py -q -p no:cacheprovider --junitxml=engineering/acceptance/high-risk-publication/host-final.xml
engineering/.venv/Scripts/python.exe -B -m pytest engineering/backend/tests/test_ai_approval.py engineering/backend/tests/test_ai_publication.py engineering/backend/tests/test_ai_recovery.py engineering/backend/tests/test_ai_backup.py -q -p no:cacheprovider --junitxml=engineering/acceptance/high-risk-publication/ai-host-regression.xml
engineering/.venv/Scripts/python.exe -B -m pytest engineering/backend/tests/test_private_probe.py engineering/backend/tests/test_ai_publication.py::test_load_once_after_ai_store_is_closed_and_restart engineering/backend/tests/test_ai_approval.py::test_approval_stages_evidence_without_loading engineering/backend/tests/test_ai_approval.py::test_required_risk_reasons_are_enforced engineering/backend/tests/test_foundation.py::test_lua_real_execution engineering/backend/tests/test_foundation.py::test_lua_timeout_and_restricted_globals -q -p no:cacheprovider --junitxml=engineering/acceptance/high-risk-publication/post-probe-integration.xml
```

常规回归选择 `test_adapters.py`、`test_chat.py`、`test_chat_network.py`、`test_faults.py`、`test_foundation.py`、`test_host.py`、`test_knowledge.py`、`test_knowledge_network.py`、`test_model_contracts.py`、`test_room_versions.py`，同样使用 `-B -p no:cacheprovider`。本轮未重复执行浏览器布局或公网部署验收。
