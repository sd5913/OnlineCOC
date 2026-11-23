# 引擎性能验收（2026-11-22）

当前机制见[引擎性能文档](../../../docs/current/engineering/engine-performance.md)。本目录使用独立合成存档、Demo 规则与冻结 AI 依赖；没有模型 API 调用、正式存档写入或公网服务操作。

## 结果与来源

- `baseline-v1-results.json` 对比 `candidate-v2-results.json`：每项30样本，Lua、静态 stage、宿主投影、命令、Schema、100/1000/10000条历史校验与提交。
- `candidate-v3-profile.json`：冷/热 worker 分段、JSON decode 候选、完整模型 CPU profile、存储阶段、宿主进程内存采样。Lua装载约0.8–0.9ms，冷导入约496ms，未采用跨任务 Lua 状态/闭包复用。
- `baseline-v1-http.json`、`candidate-v3-http.json`：真实127.0.0.1 TCP，1/4/8并发及30次简单检定。`*-http-repeat{1,2,3}.json` 为随后交替运行的专门读取复测，每轮每并发组90样本。`summary.json` 合并270样本，各项保留原始样本和返回正文总字节数、失败数、吞吐量。
- `baseline-v1-backup.json`、`candidate-v3-backup.json`：30份3MiB素材备份，逐份重新验证。锁占用p95由30.54ms降至0.91ms，总耗时由30.70ms降至22.34ms。
- `boundaries-v2.xml`：60项专项通过。`core-v3.xml`：67通过、1项因冻结树缺崩溃驱动失败；`core-v4.xml`：补齐依赖后235通过、67项已通过用例不重复。二者并集覆盖完整后端302个不同用例。
- `joint-v1.xml`：真实HTTP→冻结AI v1分页/详情/当前来源失效及配套回归22通过，其中15个路由用例与后端重叠。URL编码冒号在HTTP中解码，旧queryless list兼容，page/detail都携带delivered=True。
- `network-stats-results.json`：4组浏览器getStats模拟契约检查。没有调用TURN，未知重传和未知候选返回null，没有伪造零丢包或直连结论。
- `extras-v5.xml`：聚合视图与相关回归57通过，其中8个新增，后端累计310个不同用例。`candidate-v5-extras.json`：同一引擎版下，KP四次/PL三次独立HTTP读取合并为一次的1/4/8并发30样本；4并发p95为KP55.56→22.35ms、PL41.48→15.76ms。
- `*-source.json`：每次隔离树逐文件SHA-256。`baseline-code/source.json` 及其13份源码保留实际修改前差异；基线AI依赖是已存在的 `engine-kp-policy-interface-snapshot/v1`，候选AI依赖是 `ai-performance-interface-snapshot/v1`。
- [引擎接口冻结v1](../engine-performance-interface-snapshot/v1/source.json)：332文件，首次性能与分页接口版；不含崩溃/离线驱动，完整回归另从旧冻结依赖补齐两份驱动。
- [引擎接口冻结v2](../engine-performance-interface-snapshot/v2/source.json)：当前聚合视图接口、AI v2依赖、完整离线驱动和网络统计源码。旧冻结版保持不变；`freeze.py` 已包含补齐离线驱动的步骤。

首次完整运行因隔离树缺 `test-console` 中断，没有作为成功；第二次缺 `acceptance/crash_worker.py` 的失败保留在XML。分段驱动首次命名为profile.py，与标准库同名，修正为phase_profile.py后重新测量。首次TCP驱动继承环境代理导致登录失败，改为trust_env=False后重新使用独立数据目录测量。这些均为验收驱动问题，不计入成功率分母；有效性能样本全部成功。

## 重现

从项目根目录使用 `engineering/.venv/Scripts/python.exe`，为每轮选择不存在的名字，避免复用已有存档：

```powershell
& engineering/.venv/Scripts/python.exe engineering/acceptance/engine-performance/freeze.py my-run ai-performance-interface-snapshot/v1
& engineering/.venv/Scripts/python.exe engineering/acceptance/engine-performance/benchmark.py my-run
& engineering/.venv/Scripts/python.exe engineering/acceptance/engine-performance/phase_profile.py my-run
& engineering/.venv/Scripts/python.exe engineering/acceptance/engine-performance/http_probe.py my-run
& engineering/.venv/Scripts/python.exe engineering/acceptance/engine-performance/backup_probe.py my-run
node engineering/acceptance/engine-performance/network_stats.mjs
```

基线重现需在独立复制的引擎接口v1树中覆盖 `baseline-code/engineering/`，并使用旧冻结AI目录与ai.json；核对baseline-v1-source.json中的生产源码哈希，不能把当前优化版重新命名为“基线”。全量pytest在隔离树的engineering目录运行，`--basetemp`和XML指向本目录work及证据目录。生成的work目录不入库、不用作正式存档。

## 取舍和限制

完整图约束、跨记录引用、授权、规范字节、CAS、fsync和回执恢复均保留。普通消息内容键与预建validator只缓存纯结构检查。没有采用调用者自报写集、通用不可变子树、房间日志式存储或JSON decode替代快照拷贝；后者在本机p95更差，且会改变通用Python值类型契约。

简单动作的真实回环p95约730→84ms。读取复测的p95为：1并发3.72→4.10ms，4并发16.76→16.26ms，8并发33.56→32.20ms。1并发增加0.38ms（约10.2%），因此不能宣称严格满足所有路径“不超过10%回退”；中位数与不同轮次存在波动。样本来自有其他协作进程的同机环境，没有独占CPU保证。

峰值内存仅记录宿主进程，未包含完整worker树；冷worker/故障替换仍约半秒。没有真实LAN、WAN、TURN、物理断电或SCTP重传测量。包资源导出与多组件就绪由所属模块处理；本轮未改这些模块，也未改变旧存档的自动加载规则。
