# ISSUE-018 宿主与 SDK 错误链验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 关联文档：[首测工程](../../../docs/current/engineering/first-test.md)、[HTTP 实现](../../backend/src/onlinecoc/server.py)、[SDK](../../client-sdk/client.js)、[机器错误封套](../../contracts/messages.json)

本轮修复 SDK 的 HTTP 错误形状，并接入 AI 负责人新增的两处 HTTP 读取交付标记。隔离复验不访问正式存档或正式进程，不调用真实模型。包侧代理与界面由包负责人维护；通用 AI 客户端、历史交付策略与其 HTTP 集成测试由 AI 负责人维护。

## 当前行为与范围

`HttpTransport.request` 的错误含 `code/errorKind/status/operation/requestId/commandId`。定位来自原请求，不能由服务器返回值覆盖；没有相应 ID 时为 null。ID 及操作名有长度和字符限制，读接口操作名去掉查询参数。错误不复制响应正文、底层异常文本、Cookie、CSRF 或 detail/message。

| 场景 | 结果 |
| --- | --- |
| 非 JSON HTTP 500／宿主未捕获 OSError | HTTP_ERROR、http、status=500，保留可用请求定位 |
| StoreError | STORAGE_UNAVAILABLE、http、status=503 |
| JSON HTTP 错误 | 保留合法大写机器 code、数值 HTTP 状态；非法 code 退化为 HTTP_ERROR |
| fetch 连接拒绝 | NETWORK_ERROR、network、status=null |
| HTTP 成功但正文不能解析 | INVALID_RESPONSE、response，保留数值 HTTP 状态 |
| 本地序列化失败／命令离线／同 ID 不同输入 | INVALID_REQUEST／DISCONNECTED／COMMAND_ID_CONFLICT、client、status=null |
| 账号重置后旧请求完成 | SESSION_CHANGED、session，清空旧请求定位 |
| 已进入执行的权限拒绝 | HTTP 200 的 rejected/PERMISSION_DENIED 回执原样返回，原 ID 可查且重试不重算 |
| 命令参数 Schema 无效 | HTTP 409 INPUT_INVALID；对应回执仍 unknown |
| HTTP 200 的 unknown | 原样返回，不转换成明确拒绝 |

HTTP、网络或解析错误均不能单独证明原动作未提交；应按原 commandId／AI requestId 查询回执。SDK 不自动重试，不替换命令 ID。读取列表失败也不能证明写动作失败。

共享 messages.json 的 error 仍只允许 `{code}`，宿主默认未捕获异常仍为纯文本 500；本轮未改变它们。`ai_api.py` 仅在 `GET /ai/tasks` 与 `GET /ai/sessions/{session_id}` 两处调用增加 `delivered=True`，历史策略与接口集成结果见 AI 负责人的 message-history 验收。本目录没有宣称复现用户截图那一次未知异常。

## 证据

| 文件 | 内容 |
| --- | --- |
| [probe_transport.mjs](probe_transport.mjs)、[initial-probe.json](initial-probe.json) | 修复前 6 种合成 SDK 场景原始观察；脚本重跑反映当前代码 |
| [test_http_errors.py](test_http_errors.py)、[http-probe.xml](http-probe.xml)、[results.json](results.json) | 首阶段真实 Host/ASGI 4 项全部通过；JSON 内“未修改生产代码”和摘要仅描述当时审计基线 |
| [serve_fixture.py](serve_fixture.py)、[test_transport.mjs](test_transport.mjs) | 全新存档、随机回环端口、真实 Uvicorn/Host、真实连接拒绝及 SDK 行为复验 |
| [sdk-initial.xml](sdk-initial.xml) | 首轮 14 项中 8 项失败：测试路由被根静态挂载遮住，实际返回 404/405；已修正夹具路由优先级 |
| [sdk-retest.xml](sdk-retest.xml) | 最终 15 项错误链复验全部通过，包括请求定位、回执语义和旧账号隔离 |
| [sdk-regression.xml](sdk-regression.xml) | 原有通知／裁决 SDK 的 12 项回归全部通过 |
| [record_results.py](record_results.py)、[repair-results.json](repair-results.json) | 修复验收汇总、当前源码摘要及完整新增文件清单 |

夹具只写本目录忽略的 `sdk-live-tmp/`，Node 隐藏启动独立子进程并只关闭自己创建的宿主；没有打开真实模型配置。精选输出不记录密码、令牌、请求正文或真实日志。首次失败与旧审计证据保留，最终通过不覆盖首次失败。

```powershell
node --test --test-reporter=spec --test-reporter-destination=stdout --test-reporter=junit --test-reporter-destination=engineering/acceptance/http-errors/sdk-retest.xml engineering/acceptance/http-errors/test_transport.mjs
node --test --test-reporter=spec --test-reporter-destination=stdout --test-reporter=junit --test-reporter-destination=engineering/acceptance/http-errors/sdk-regression.xml engineering/acceptance/notifications/test_client.mjs engineering/acceptance/rulings-sdk/test_client.mjs
engineering/.venv/Scripts/python.exe -B engineering/acceptance/http-errors/record_results.py
```

重跑首阶段 ASGI 用例时应更换 XML 文件名及 basetemp，保留原始审计证据。根 hierarchy 的新增目录清单由包负责人依据 repair-results.json 统一登记。
