# 历史上下文只读复验验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 关联文档：[引擎契约](../../../docs/current/engineering/high-risk-publication.md#历史上下文的只读复验)、[房间格式](../../../docs/current/engineering/room-format.md)、[专项源码](../../backend/tests/test_history_context.py)

## 结果与范围

`publication.check_history_context(host, state, account, context)` 允许同目录正常重启后复验持久历史，不改写旧 context 或 Room。它忽略仅用于执行的 authorityEpoch 和检查器指纹，保留当前授权、scope、包契约、管理员基线、来源及严格玩家知识复验。现有 `check_context`、批准、发布与普通命令的当前 epoch 约束保留。

| 原始记录 | 结果 | 说明 |
| --- | --- | --- |
| [core-initial.xml](core-initial.xml) | 25 通过、1 失败 | 合成候选无高危改动却使用高危批准理由，触发 RISK_REVIEW_REQUIRED；修正测试夹具为删除未引用配置，未放宽产品校验 |
| [core-retest.xml](core-retest.xml) | 29 通过 | 修正夹具，增加严格玩家停用／授权版本及 KP 全房间读取撤权覆盖 |
| [regression.xml](regression.xml) | 110 通过，0 失败／错误／跳过 | 包含全部 29 项专项，以及既有宿主、知识、高危发布、存档格式、Lua／文件存储回归 |

最终按测试 ID 去重为 **110 项通过**，不累加三次运行。逐项状态、源码摘要及运行命令见 [results.json](results.json)。

新专项使用真实 Host、同目录关闭／重开、FileDataStore、知识提供方、命令与回执，覆盖：

- 重启后原上下文仍可读，输入字节、Room 内容及两份存储代号不变。
- 历史可读不恢复旧批准；旧 epoch 的未执行普通命令、新批准和发布仍拒绝。
- 执行检查器版本变化不阻断只读历史，执行校验仍拒绝旧版本。
- 账号／角色／授权版本、恢复 scope、包契约、活动规则、配置及世界基线变化仍拒绝。
- 外发策略、服务配置、会话访问回调、聊天修改／撤回／权限和查询证明重新检查。
- 严格玩家知识撤回、提供方缺失、硬使用限制、错误主体、策略变化及停用仍拒绝；撤销 KP 全房间读取权限仍拒绝。

发布用例复用引擎的受信合成 PreparedBundle，执行检查器指纹固定，不读取并行施工中的 AI 目录；它证明宿主边界，不冒充真实 A/B/C、AI 连续对话、浏览器或模型验收。AI 侧 historyContexts 与 Context.history 的接线和联合验证由 AI 责任者单独维护。本轮没有调用模型、部署服务或读写正式房间。

## 复验

从项目根目录执行，先登记 backend、contracts、data-management、demo 规则和运行时的使用，以及本目录输出改动。`*-tmp/` 是可重建的隔离测试数据，已忽略。

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
engineering/.venv/Scripts/python.exe -B -m pytest engineering/backend/tests/test_history_context.py -q -p no:cacheprovider --basetemp=engineering/acceptance/history-context/retest-tmp --junitxml=engineering/acceptance/history-context/core-retest.xml
engineering/.venv/Scripts/python.exe -B -m pytest engineering/backend/tests/test_history_context.py engineering/backend/tests/test_high_risk_commands.py engineering/backend/tests/test_high_risk_host.py engineering/backend/tests/test_knowledge.py engineering/backend/tests/test_host.py engineering/backend/tests/test_room_versions.py engineering/backend/tests/test_foundation.py -q -p no:cacheprovider --basetemp=engineering/acceptance/history-context/regression-tmp --junitxml=engineering/acceptance/history-context/regression.xml
```
