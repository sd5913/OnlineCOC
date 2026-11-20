# AI 调试只读路由、SDK 与 LAN 验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-19
- 最后更新：2026-11-19
- 关联文档：[宿主 AI 路由](../../backend/src/onlinecoc/ai_api.py)、[局域网模块](../../../docs/current/engineering/network-lan.md)

## 实际契约

宿主提供 `GET /api/v1/ai/debug`，沿用当前账号认证，调用独立模块 `Application.debug(account, options)`。必须提供至少一个 `sessionId`、`requestId` 或 `rulingId`，均为非空、最多 200 字符；可同时提供多个过滤条件。`includeContent` 默认 false，HTTP 只接受 `true`、`false` 两个字面并转换为布尔。重复／未知参数、空 ID、超长 ID 或其他开关取值拒绝为 `INPUT_INVALID`；账号不能通过查询参数覆盖。

返回 JSON 使用 no-store。请求不调用 command／receipt；实际资料授权、脱敏和正文投影由 AI 模块执行，不能把 includeContent 当作提权。SDK `Client.aiDebug(options)` 使用同名过滤字段及布尔正文开关，URL 编码参数，复用会话切换保护，不增加待执行命令。

LAN 仅增加此 GET 路径，转发客户端原 Cookie 和查询参数，保留 no-store。POST 同路径、其他 AI 路径和 host-control 仍不开放。P2P／网页通用白名单未变；配置包通过已有声明式服务桥接入，由包侧分别验证。

## 证据与边界

| 文件 | 结果 | 范围 |
| --- | --- | --- |
| routes.xml | 初跑 16 通过、1 失败 | HTTP／SDK 已通过；LAN 测试环境缺 aiohttp |
| routes-retest.xml | 16 通过 | 默认元数据、显式正文、真实 HTTP 查询解析、认证传递、参数拒绝、错误映射、SDK 编码与会话切换 |
| lan.xml | 1 通过 | 独立联网环境的真实回环 HTTP、Cookie／查询转发、GET 白名单及禁止路径 |

最终 **17 项通过**，不累加初跑重复项。LAN 用例移至本目录 `test_lan.py` 并使用已有联网环境；没有安装或升级依赖。后端 Starlette 的 httpx 弃用提示及联网 pytest-asyncio 配置提示保留，不影响结果。摘要与代码哈希见 `results.json`。

HTTP 专项用合成 AI 安装端口及 Application 替身隔离并行施工，证明路由参数／认证传递和无命令分发；不声称完成真实 AI 资料权限、敏感内容脱敏或历史投影验收。真实模块与包侧验收由对应测试报告提供。本轮不接触正式房间、外部模型或部署。

## 复验命令

从项目根目录运行，先按 hierarchy 登记源码／运行时使用和输出改动：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
engineering/.venv/Scripts/python.exe -B -m pytest engineering/backend/tests/test_ai_debug_route.py -q -p no:cacheprovider --junitxml=engineering/acceptance/ai-debug-route/routes-retest.xml
engineering/network-p2p/.venv/Scripts/python.exe -B -m pytest engineering/acceptance/ai-debug-route/test_lan.py -q -p no:cacheprovider --junitxml=engineering/acceptance/ai-debug-route/lan.xml
```

前者使用已有 Node 执行 SDK 内存传输测试，后者使用已安装 aiohttp 的独立联网运行时。两者均使用合成数据；没有实际 API 密钥或玩家资料。
