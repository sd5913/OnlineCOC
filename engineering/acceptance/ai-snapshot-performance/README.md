# AI 发送快照、进度与历史负载验收

2026-11-20。当前行为见[会话权限](../../../docs/current/engineering/ai-session-access.md#发送快照与执行校验)；联合结论由 [ISSUE-019 归档](../../../docs/history/2026-11-20-issue-019-performance-generation-progress.md) 汇总。这里记录 AI 侧样本和边界，不代替配置包四页整链或引擎验收。

## 结果与证据

最终两组共 **200 个唯一用例，200/200 通过、0 跳过，成功率 100%**。逐项状态见 [results.json](results.json)，原始尝试和源码 SHA-256 同时保留。确定性用例的通过率只表示本次覆盖结果，不代表所有实际模型输入的成功概率。

| 最终证据 | 通过 | 覆盖 |
| --- | ---: | --- |
| [history-cache.xml](history-cache.xml) | 35/35 | 冻结生成、历史授权、缓存限额／循环、全房间授权和下一请求撤权 |
| [cache-regression.xml](cache-regression.xml) | 165/165 | 审批执行、配置增删改、玩家知识、工具错误、历史留存、定向通知、HTTP 和真实 Edge 进度交互 |

较早三组 [final-core-all.xml](final-core-all.xml)、[final-regression.xml](final-regression.xml)、[history-final.xml](history-final.xml) 共 269 次执行、197 个唯一用例通过；之后多页面复测仍暴露长历史重复校验问题，故只作为阶段证据保留。最终重跑新增 3 项缓存与授权边界，不把重复执行相加为独立用例。

快照专项覆盖两个时间窗口：任务已排队但 worker 未开始；provider 已等待但尚未读取工具。后续聊天不混入输入；真正实体／独立包资料修订保留原回答和候选并列出检查项；旧候选不能绕过当前执行校验。账号撤权、会话删除、取消、外发关闭和旧 PL 历史撤回仍阻止新输出。历史中已交付的正文按原受众保留，不意味着可再次外发撤权资料。

同一会话先产生历史、修改世界、再继续生成的用例，在首次工具 attach 路径复现了 BASELINE_STALE。修复只调整 AI 层对历史读取依赖的检查：先前回答的整房间执行基线不代替本次候选基线；来源、权限和策略仍复验。宿主 publication / 批准硬校验没有放宽。修复前 [history-tool-first.xml](history-tool-first.xml) 0/1；修复后 [history-tool-fixed.xml](history-tool-fixed.xml) 6/6（含撤权等边界），后续完整相关组为 73/73。

## 性能

同一生成脚本、200 tasks / 400 requests / 2 个会话 / 20 批次 / 1000 条聊天。AI JSON 约 1.3 MB、房间约 687 KB，非空保存。每个暖查询 12 样本；p95 为向上取整的样本分位数。4 并发指同账号 TestClient 的 4 个请求 worker，不冒充四个真实浏览器。真实网页整链由配置包另测。

| 路径 | 优化前 p50 / p95（ms） | 最终 p50 / p95（ms） |
| --- | ---: | ---: |
| tasks，30 条 | 12953.25 / 14971.58 | 57.64 / 62.78 |
| session，100 条 | 8041.55 / 9282.33 | 138.18 / 268.39 |
| rulings，20 批次 | 1084.89 / 1379.23 | 184.19 / 318.51 |
| tasks，4 并发 | 55869.43 / 83751.69 | 249.05 / 345.68 |

数据：[baseline.json](baseline.json)、[optimized-final.json](optimized-final.json)；中间一次测量 [optimized.json](optimized.json) 也保留。首次 tasks 投影另计，约 14106→205 ms；不会把首次持久化成本藏进暖查询。单次仓库快照最终 p50/p95=14.29/25.28 ms、状态写=155.74/239.70 ms，并未变成空写。

主要变化是按权限过滤、先分页，再投影；一次只读请求复用仓库快照、会话来源和相同上下文检查。写入／事务结束立即清除读取缓存，原 state() 仍返回独立副本。前后还包含同期引擎优化，不能把全部时间差归因于单一补丁。测试为本机 ASGI 调度，期间存在其他回归负载，不是公网或不同硬件延迟保证。此批量夹具只有两个共享上下文，不能覆盖真实会话历史图的增长。

### 长历史复现与补充修复

配置包四页面联动在第二个含真实资料变化的候选生成成功后，仍出现 GET 超时；一条 rulings 历史重查持有房间锁，其他页面状态读取等待。`history_benchmark.py` 单独构造 28 实体、1000 聊天、12 个历史计划，再创建／批准一个读实体批次并生成第二个资料变化候选，共 14 个上下文（每轮最多引用前 4 轮）。不调用外部模型。

同脚本带 cProfile 的 GET session 单次由 **3.142 秒降至 0.263 秒**；历史检查 105→14 次，递归 assess 调用 304→60 次。第 14 轮生成由 5.672→3.402 秒。原始证据为 [history-performance-before.json](history-performance-before.json) 与 [history-performance.json](history-performance.json)。这是本机单次 profile 对照，不将其称为 p50/p95 或多页面最终成绩；包侧会记录真实四页面复测。

修复消除 AI 全房间授权回调重复复制 Host、让一次生成权限递归共用本次当前房间，并在单次 tasks/rulings 读取内复用历史祖先校验。缓存保留每个根的实际可达节点集合，100 节点上限与循环拒绝不因命中而跳过；101 个独立根不共用全局限额。缓存不跨请求、不跨写入，撤权仍按当前房间拒绝。

## 存储与进度

[storage-growth.json](storage-growth.json)：941542 字节房间完成 4 次管理工具读取后，AI 存档增加 11711 字节；最终保留 1 个有效上下文。发送快照只在进程 RAM 中保留，未被其他记录引用的中间工具上下文会被替换；不在每一步重复嵌套整份房间。

进度包含有序 seq、时间、状态、耗时、安全工具／操作名；生成中可见，结束后可折叠。完整指令参数及实际回执通过已有裁决详情查看。PL 只见本人任务；不输出隐藏推理、原始工具参数或凭据。截图 [progress.png](progress.png)，浏览器入口 `test_progress_ui.py`。明确重新生成按钮只恢复原需求并关联，发送后才调用模型；不自动重复执行。

## 真实 DeepSeek

[live-results.json](live-results.json)：**1/1 隔离任务通过**，2 次真实 API 请求，returnedModel=`deepseek-flash`，服务商实耗 **13485 tokens**；生成中插入无关聊天后，配置候选、A/B/C 和人工批准的隔离发布均成功。正式服务配置前后摘要相同；仅使用新建的隔离宿主，未读写正式游戏状态。

初始 20000 预留单位预检被正确阻断，0 外部请求，见 [live-preflight.json](live-preflight.json)。系统按 UTF-8 请求字节加最大输出预留，首轮需 27911 单位；协作确认后本次隔离上限改为 50000 预留单位，最多 4 次调用、1 次修正，未修改正式预算。预留单位不等于实耗 tokens，不能宣称实耗受原 20000 上限保证。该真实小样本先于长历史分支修复完成，不覆盖长历史；该分支使用确定性和配置包整链复验，不追加真实调用凑结果。

## 失败与处理

| 原始记录 | 失败分类与处理 | 后续证据 |
| --- | --- | --- |
| baseline-setup-error.json / baseline-rate-limit.json | 基准夹具漏取完整 batch、聊天时间戳触发真实限流；修正夹具，不关闭限流 | baseline.json，所有请求无错误 |
| smoke.xml（30/31）、snapshot-first.xml（49/50） | 撤权已正确阻断，但错误码意外改变；恢复原错误契约 | 最终核心组通过 |
| tools-diagnosis.xml、tools-fixed.xml | 只实现 state() 的嵌入仓库兼容失败；冻结对象错误引入不存在的全房间授权回调；分别补兼容和保留原回调边界 | 最终核心／配置增量组通过 |
| history-diagnosis.xml | 旧测试仍要求已交付正文被删除，与 ISSUE-018 受众绑定留存规则冲突；改为检查正文只读保留且不能进入新的模型上下文 | 最终历史组通过 |
| interrupted-regression.json | 发现上述问题后停止一次广泛初跑，未产生完整 XML；不统计其成功率 | 三组完整最终 XML |
| history-tool-first.xml | 联合测试暴露旧历史整房间基线被错误用于新任务工具校验 | 精准复现、6/6 边界、73/73 相关复验 |
| history-performance-before.json | 真实形状的历史图在一次读取中重复校验祖先、复制房间，长时间持锁；旧批量夹具未覆盖 | history-performance.json、缓存／授权边界，以及包侧四页面复验 |
| live-preflight.json | 预算预留阻断，0 调用；保留失败原因并先明确新上限 | 单次真实实验，不无限重试 |

权限拒绝先修合法授权；资料变化先核对变化项，再由 KP 决定重新生成；未知／部分执行先查原回执，不重放整批。中断进程不会恢复 RAM 快照，旧在途任务标记 interrupted；阶段摘要不是执行凭证，成功以原回执为准。

## 复现

使用 `engineering/.venv/Scripts/python.exe -X utf8 -B`，PYTHONPATH 包含 `engineering/ai/src;engineering/backend/src;engineering/data-management`。pytest 使用独立临时目录；复现建议指定本目录 `work/` 下的 basetemp 和 `-p no:cacheprovider`。`work/` 已忽略，不入库身份库或运行时存档。

- `benchmark.py --label <独立标签> --tasks 200 --samples 12`：确定性性能，无外部模型。
- `history_benchmark.py`：14 上下文历史图，修改世界、批准批次、生成中真实依赖变化，再 profile 一次会话读取；会写 `history-performance.json`，比较前先保留旧证据。
- `record_results.py`：重新汇总已有 XML、结果与源码摘要，不调用模型。
- `live_experiment.py`：只预检；只有显式 `--run --budget 50000` 才调用真实模型并可能计费，须在授权预算内使用。

文件清单见 [manifest.json](manifest.json)。失败证据不覆盖为通过，最终统计按测试名去重，不把不同阶段相加为独立用例。
