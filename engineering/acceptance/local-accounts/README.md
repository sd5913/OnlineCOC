# 本机账号事务与 C 发布审核验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-21
- 最后更新：2026-11-21
- 关联文档：[本机账号](../../../docs/current/engineering/host-accounts.md)、[发布审核](../../../docs/current/engineering/high-risk-publication.md)、[结果与源码摘要](results.json)

所有测试使用本目录 `work/` 内的合成宿主和独立 DPAPI 发现目录。没有访问正式账号、存档或 API 配置，外部模型调用为 0。

`prepare.py` 将已登记的当前引擎及测试依赖复制到隔离镜像；初轮 AI 使用已释放的 `ai-c-review-interface-snapshot/v1`，生命周期和 C 发布复测使用 v2，不读取并行施工中的 AI 源码。`source.json` 记录最终引擎输入及 AI 冻结输入摘要。`checkpoint.py vN` 生成不可覆写的联测快照，v1 保留初始接口，v2 加入 C 依据指纹，v3 修正持久 Approval schema 并区分 POST 结果未知。

专项包含 54 个用例：账号核心 21、真实 HTTP/DPAPI/stdin 客户端与 WebSocket 6、硬退出和文件发布故障 10、C gate 16，以及人工 C 采纳经真实 Host.command 批准／发布后重启和同 ID 回执恢复 1。C 基础候选使用真实 Lua 夹具准备；拒绝反例有意修改受信 resolver 的报告，以检验宿主不信任报告布尔值和批准摘要。它们不计为模型生成或真实业务包场景验证。

账号检查覆盖两库完成后才成功、player/KP 角色绑定、旧四字段请求兼容、同 ID 改密码不再执行、稳定拒绝回执、最后可登录 KP、成员不可复活、历史归属保留、HTTP/WS 撤销、无代理、过期和异存档发现记录、进程退出恢复及提交后丢回复。C 检查覆盖三类可采纳 unknown、技术失败不能采纳、精确报告／依据绑定、动态依据失效、房间持久格式和发布消费。

受影响回归使用当前后端的 host、network、faults、ai_approval、ai_publication、ai_recovery、high_risk_host、high_risk_commands、history_context。最终计数以 `results.json.finalCounts` 为准，去重键为 JUnit classname 和用例名；所有初跑 XML、错误及重跑均保留，不将失败覆盖为通过。

最终 160 个唯一用例全部通过（54 专项、106 回归），无跳过；历轮累计 373 次执行，332 次通过、39 次失败、2 次环境错误，历史失败均在后续修复或夹具补齐后通过。最后 `lifecycle-fixed.xml` 的 18 项覆盖 AI v2 与当前宿主的关闭服务发布、C gate、真实命令发布及重启恢复。

首次失败及处理：

- C 首轮 6 个测试请求漏填已有高危批准摘要／理由，补齐夹具后通过，宿主没有放宽高危检查。
- 回归暴露真实实现漏项：`models.json` 的持久 Approval schema 未允许 C 字段。已同步可选 CReview/CAssessment，增加持久格式检查，并验证真实 Host.command。
- 隔离工程首次遗漏旧 network/faults 启动脚本及网页静态依赖，补登记并复制后重跑。
- 旧 `test_poison_cannot_be_caught` 仍期待 EXECUTION_REJECTED；任务前冻结执行器与当前代码摘要一致，实际约定已是保留首个 INPUT_INVALID。修正断言并增加 HP 无写入检查，未修改执行器。
- AI v1 关闭仓库后残留 resolver 导致 STORE_CLOSED。AI v2 在关闭流程中改装持久化读取器，每次复验当前依据；宿主原关闭服务发布回归已通过，没有跳过依据检查。

复现（项目根目录）：

```powershell
engineering/.venv/Scripts/python.exe -B engineering/acceptance/local-accounts/prepare.py
engineering/.venv/Scripts/python.exe -B -m pytest engineering/acceptance/local-accounts/test_accounts.py engineering/acceptance/local-accounts/test_client.py engineering/acceptance/local-accounts/test_durability.py engineering/acceptance/local-accounts/test_c_gate.py engineering/acceptance/local-accounts/test_c_command_recovery.py -q -p no:cacheprovider --basetemp engineering/acceptance/local-accounts/work/recheck
engineering/.venv/Scripts/python.exe -B engineering/acceptance/local-accounts/finalize.py
```

生成镜像、临时身份库、日志及缓存均忽略入库。原 WinForms 二进制没有重编译，包侧面板和 AI 真实调用由各责任会话另行验收。
