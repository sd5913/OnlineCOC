# 持久定向通知验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 关联文档：[通知接口与恢复](../../../docs/current/engineering/notifications.md)、[后端专项](../../backend/tests/test_notifications.py)、[SDK 专项](test_client.mjs)

本轮实现绑定原宿主 committed 动作的 KP 显式定向通知、只读收件箱及逐人确认。不调用模型，不读取或修改正式房间，不改 AI 或配置包源码。AI 审批包中的来源动作索引解析、普通包侧持久 Job 接线、PL 弹窗与浏览器持久去重由对应责任者联测。

| 证据 | 结果 |
| --- | --- |
| [core.xml](core.xml) | 首轮 20 项通知专项全部通过 |
| [regression.xml](regression.xml) | 95 项全部通过：扩充后的通知专项 26 项，加现有宿主、存储、模型、格式和聊天回归 69 项 |
| [sdk.xml](sdk.xml) | 4 项全部通过：分页参数、CSRF 确认和命令幂等、读取与确认的登录代际隔离 |
| [results.json](results.json) | 最终 99 项去重通过、完整测试 ID、源码与证据摘要 |

专项使用真实 Host/FileDataStore 和 HTTP TestClient，覆盖离线补取、同目录重开、备份恢复、确认持久化、多收件人独立确认、同原动作换发送命令 ID 去重、变更内容冲突、来源失败/未知/未完成流程拒绝、部分完成定位、发送者及收件人权限、撤权/重入不复活旧通知、无效字段与损坏记录拒绝。

发送与确认分别在 before_notification_commit / after_notification_commit 注入真实子进程 `os._exit(17)`，共四个窗口；重开核对磁盘状态及原回执，再验证同封套重试或未发布命令的新 epoch 封套恢复，不重复创建通知。HTTP 验证认证、Origin、CSRF、no-store 和参数隔离。SDK 使用真实 Client 与内存 transport；未冒充真实浏览器联测。

数据仅写本目录忽略的 `*-tmp/`。确认后不再投递；未确认项可重复返回，前端按 notificationId 去重。跨设备弹窗严格一次、物理断电和包侧/AI 跨模块联测不在本轮通过声明内。pytest 的 Starlette/httpx 弃用提示不影响本轮结果。

项目根目录 PowerShell 复验：

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
engineering/.venv/Scripts/python.exe -B -m pytest engineering/backend/tests/test_notifications.py engineering/backend/tests/test_host.py engineering/backend/tests/test_foundation.py engineering/backend/tests/test_model_contracts.py engineering/backend/tests/test_room_versions.py engineering/backend/tests/test_chat.py -q -p no:cacheprovider --basetemp=engineering/acceptance/notifications/regression-tmp --junitxml=engineering/acceptance/notifications/regression.xml
node --test --test-reporter=spec --test-reporter-destination=stdout --test-reporter=junit --test-reporter-destination=engineering/acceptance/notifications/sdk.xml engineering/acceptance/notifications/test_client.mjs
```

需要保留历史证据时使用新的输出文件名和 basetemp。源码冻结后方可由其他责任者登记 backend/contracts/SDK 的使用并运行联合测试。
