# 聊天与 AI 依据隔离验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-21
- 最后更新：2026-11-21
- 关联文档：[接口与实现](../../../docs/current/engineering/chat-isolation.md)

## 证据入口

`results.json` 汇总最终专项、回归、浏览器对照和生产源码摘要。`first-failures.json` 保留首次脚本失败、无效夹具及 v1 性能回退原因；这些失败样本不替代最终结果。`new-files.json` 供工程目录索引合并。

最终 14 项专项与 85 项回归均通过，共 99 个最终测试；包含初轮 13 项在内，记录了 112 次通过的测试执行。等价负载中，发送回执 p50/p95 从 1148/1297 ms 降至 121/136 ms，全部页面同步从 1252/2106 ms 降至 316/1081 ms；两组聊天及审批均无失败。独立依赖隔离实验的审批失败由 4/4 降至 0/4。

| 文件 | 含义 |
| --- | --- |
| before.json / after.json | 附带完整房间查询的聊天与审批并发；优化前查询为 records，优化后为 state，用于验证普通聊天不使依据失效 |
| before-control.json / after-control.json | 不额外加入完整房间查询，双方审批均成功的等价负载性能对照 |
| before-source.json / after-source.json | 两个隔离引擎使用的生产代码与接口文件摘要 |
| initial.xml / cache-fixed.xml | 13 项初始检查及增加审批缓存/发布验证后的 14 项专项 |
| regression.xml | 宿主、聊天、网络、知识撤权和 AI 发布回归 |
| profile-before.txt / profile-0.txt 至 profile-4.txt | schema 热点诊断，带剖析器开销；不作为浏览器延迟数据 |

所有房间、账号及审批均为合成数据，外部模型 API 调用数为 0。`work/` 为忽略的可重建运行目录。

## 复现

在项目根目录使用 `engineering/.venv/Scripts/python.exe -B` 执行脚本。`prepare.py after` 将当前已登记的引擎文件与冻结 AI v2 合并到隔离目录。`before` 是修改前已冻结的基线，不能在生产代码修改后重新运行 `prepare.py before` 来替代旧基线。

`bench.py after` 执行依赖隔离实验；`bench.py before control` 和 `bench.py after control` 顺序执行等价负载对照。三个独立 Edge 会话按 KP、PL1、PL2 轮流发送 30 条消息，同时通过独立 HTTP 会话提交 4 次真实审批。初始房间有 1200 条消息和额外 120 个实体。所有页面使用实际 SDK 与 WebSocket，记录从发送到回执及全部页面收到序号的耗时；原始样本随 JSON 保存。

这不是公网测试，也不是包 UI 的输入框可重发耗时。4 次审批中的 4 次成功仅代表本次小样本，不能推算通用成功率。包界面与当前 AI 实现由协调线程使用 v2 冻结引擎另做联测。
