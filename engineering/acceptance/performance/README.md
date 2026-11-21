# ISSUE-019 引擎性能与语义保护验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 关联文档：[首测工程](../../../docs/current/engineering/first-test.md)、[汇总与清单](results.json)

本目录验证真实 Host／Uvicorn／SDK／Edge 单页与四页并发。每页使用隔离浏览器身份，保持 WebSocket 订阅，循环执行 view、聊天历史、发送、已读及 Lua 检定；记录请求时间、消息提交到完整快照可见的时间、失败、快照 reset 与真正的连接关闭。只使用全新合成存档；未访问正式房间、修改正式配置或重启正式进程，未调用模型。包代理和 AI 投影优化的结果由各负责人单独记录。

## 已定位与修复

原实现每次普通管理写先 validate，commit 又 validate；ChatState 会反复校验整段既有消息。1000 条聊天与回执、936145 字节状态的基线，完整校验 p50 约 151ms；单次聊天 CPU 剖析约 74% 时间在两次校验、23% 在完整深复制。剖析绝对时间有额外开销，实际延迟使用无 profiler 的浏览器样本。

当前提交只做一次完整状态校验，复用未变化消息的纯 Schema 结果。缓存键为完整规范字节，最多 10000 项／8 MiB，非原生 JSON 树不命中缓存，防止 tuple 等编码归一化绕过类型检查；字段改动重新验证。频道、成员、回复、附件、行动回执等跨记录约束仍每次校验。目录与投影共用请求快照，tick 不再为同一流程清单再复制整房间。

配额扫描保留实时目录检查，改用 scandir 目录项元数据；四页压力中扫描 p50 从约 26ms 降至 3.7ms。提交复用 payload 规范字节，生成的存储封套与原格式逐字节相同。保留 fsync、CAS、排他锁、原子发布、丢回复恢复及无损压缩，不以减少持久化保证换取速度。

WebSocket 最终持锁复验在线程中执行，授权检查与发送调度仍位于同一锁边界。无外部知识策略且 generation 未变时省去重复投影，每轮仍检查登录；有动态知识提供方时保持实时复验。旧的 `reconnectWaits` 计数实际为 client.connected 不可用期间的等待，包含安全 reset；它不能单独作为网络断连证据。

## 可比较的测量

每页 8 轮。表中为 p50 毫秒；原始 JSON 同时保留 p95、样本数、每次采样、吞吐与数据规模。

| 初始规模／页数 | 聊天发送：前→后 | 聊天已读：前→后 | Lua 检定：前→后 | 吞吐 req/s：前→后 |
| --- | --- | --- | --- | --- |
| 1000 聊天＋1000 回执，936145 B／1 页 | 458.3→103.2 | 447.4→105.6 | 1175.6→890.0 | 2.273→3.763 |
| 同上／4 页 | 1413.0→370.4 | 1822.0→538.1 | 3708.2→2204.5 | 2.086→3.783 |
| 100 聊天＋100 回执，415768 B／1 页 | 85.5→26.0 | 90.2→27.7 | 616.7→510.8 | 5.082→5.819 |
| 同上／4 页 | 282.1→64.7 | 367.7→83.1 | 1654.5→1044.1 | 4.876→7.796 |

后一规模使用合成审计填充，使体积接近协调方提供的正式房间统计；内容分布、实体数量并不完全相同，不能当作正式存档实测。它使用忽略目录中的旧源码镜像，[重建脚本](baseline_sources.py)先与首次基线的五项 SHA-256 逐字节核对，未改当前源码。两种规模全部操作最终通过，无回执重复副作用；玩家看不到 KP 私有实体。

415768 B 四页基线有 38 次快照 reset、33 次等待，但 0 次 socket close；优化后 reset、等待及 close 均为 0。原大规模早期样本未单独统计 socket close，仅保留旧等待字段，不对其物理连接状态作推断。

所有 p95 并未都下降：415768 B 四页 view 的 p95 从 984.7ms 变为 1302.9ms。新鲜 Lua 隔离进程启动、规则执行期间房间锁仍影响混合负载尾延迟。发送响应提前返回也不等于其他页面立即可见；订阅约 250ms 周期仍存在，汇总另算 chatVisible。每页仅 8 轮且本机有其他开发进程，数字用于定位与复跑，不是服务等级保证。

从开始发送到本页完整快照可见的 p50：1000 条历史四页由 2011.2ms 降至 643.1ms；415768 B 四页由 420.3ms 降至 252.5ms。后一规模单页为 255.5→251.3ms，已接近既有订阅周期，并没有随 HTTP 返回时间等比例缩短。

## 保护验证与证据

| 文件 | 内容 |
| --- | --- |
| [baseline.json](baseline.json)、[optimized.json](optimized.json) | 1000 条历史的原始前后样本、分段计时与源码摘要 |
| [current-scale-baseline.json](current-scale-baseline.json)、[current-scale-optimized.json](current-scale-optimized.json) | 415768 B 同规模前后样本及真实 reset/close 计数 |
| [profile-baseline.txt](profile-baseline.txt)、[profile_command.py](profile_command.py) | 单次真实聊天提交的 CPU 剖析与可复跑入口 |
| [core.xml](core.xml) | 64 项基础存储、聊天、模型和崩溃恢复回归 |
| [test_boundaries.py](test_boundaries.py)、[boundaries.xml](boundaries.xml) | 35 项缓存变异、类型、跨记录约束、字节兼容、配额、无损压缩与分片结束前撤权验证 |
| [boundaries-initial.xml](boundaries-initial.xml) | 首轮 34 通过／1 失败；测试误要求额外属性错误路径以斜杠结尾，已修正断言 |
| [regression.xml](regression.xml) | 宿主、适配器、持久通知、个人知识和真实聊天浏览器回归；数量见汇总 |
| [initial-fixture-failure.json](initial-fixture-failure.json) | CSP 等夹具失误及早期四页 SDK DISCONNECTED 观察，不抹除失败 |
| [worker_probe.py](worker_probe.py)、[worker-probe.json](worker-probe.json) | 各 8 次新进程启动探针；禁用自动 site 只带来有限收益，本轮未采用，也未复用执行过规则的进程 |
| [record_results.py](record_results.py)、[results.json](results.json) | 验收总数、前后表、可见延迟、当前摘要和全部新增文件清单 |

计时包装为 inclusive：如 commit 包含 canonical/fsync，tick 包含等锁，不能将这些分段直接求和。夹具、日志和源码镜像仅位于忽略的 `*-tmp/`，精选文件不含真实对话、登录凭据或模型密钥。

## 复跑

以下从项目根目录执行；重跑前按 hierarchy 登记依赖与独立输出。原始证据应改名保留。

```powershell
engineering/.venv/Scripts/python.exe -B engineering/acceptance/performance/benchmark.py --output engineering/acceptance/performance/optimized.json
engineering/.venv/Scripts/python.exe -B engineering/acceptance/performance/baseline_sources.py
engineering/.venv/Scripts/python.exe -B engineering/acceptance/performance/benchmark.py --baseline --history 100 --padding 300000 --generations 100 --pages 1 4 --output engineering/acceptance/performance/current-scale-baseline.json
engineering/.venv/Scripts/python.exe -B engineering/acceptance/performance/benchmark.py --history 100 --padding 300000 --generations 100 --pages 1 4 --output engineering/acceptance/performance/current-scale-optimized.json
engineering/.venv/Scripts/python.exe -B engineering/acceptance/performance/record_results.py
```

目录清单由总协调方根据 results.json 的 newFiles 同步。后续源码变更导致旧镜像摘要不匹配时脚本主动停止，不能忽略校验继续宣称旧基线。
