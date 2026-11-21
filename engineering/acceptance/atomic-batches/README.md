# 原子批次引擎验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 关联文档：[接口及边界](../../../docs/current/engineering/atomic-batches.md)、[机器契约](../../contracts/atomic-batches.json)、[结果与新增清单](results.json)

## 结果

专项原 75 项及新增 2 项条数兼容用例通过，现有后端回归 67 项通过，共 144 个唯一用例。另两处小修正分别重跑 9 项不支持组合准入标签与 2 项 CAS 冲突分类，均通过；这些是重复执行，不增加唯一分母。代码、契约与当前文档已冻结供 AI/包侧联合验收，完整产品接线不由本专项替代。

首次执行 35 项中 5 项失败：合成夹具沿用 demo 生命上限 10，却测试生命值 11/12/19，触发正确的模型拒绝。保留 [initial.xml](initial.xml) 与 [initial-failures.json](initial-failures.json)，把专用夹具上限设为 100 后，35 项核心复验通过。扩展 63 项也通过。全部历史运行共 288 次用例执行，283 次通过、5 次夹具失败；不把历史复跑计作额外覆盖。

最终兼容性修正移除了最初新增的 32 项业务条数限制，保留 32 KiB、时间与随机预算；33 条小动作正例及超字节拒绝见 [count-limit.xml](count-limit.xml)。短修改登记复核发现 AI 方同期已新增 backend/契约读取占用，本方未及时停止短修改；发现后立即冻结并释放重叠改动登记。集成方需要按 results.json 中更新后的生产摘要重新读取；不沿用此前包含 32 项限制的隔离副本。

## 覆盖与限制

- 21 种支持操作各有真实执行正例；首项、中间、末项错误均没有业务残留。
- 无写入/无掷骰预检、顺序依赖、参数路径、Lua 内层安全规则码、PL 诊断与回执权限过滤。
- 正常判定 `false` 提交一次；业务 `outcome: blocked` 原样保留，不误当技术失败重掷。
- 意图、随机、逐项暂存、最终发布四处真实进程强制退出及重启恢复；同标识重试复用随机轨迹。
- 并发线程、重入房间变更、恢复前房间变更、存储 CAS 冲突不覆盖他人修改。
- 通知只随成功提交可见，后项失败丢弃通知，重复调用仅产生一份通知。
- 单条宿主记忆事实/回执的确认、撤销、版本/身份/作用域/Schema 约束与发布丢回复恢复。
- 实际树桩镇 Lua/配置的合成案例：槽 3 是奶酪（定义编号 6），槽 5 是口粮（定义编号 3）；错误槽位安全报因、正确消耗/短休/通知、末项失败整批丢弃、口粮移槽不猜测。

这些测试不调用模型 API，不接入正式房间，不写正式 API 配置；所有存档、素材与工作进程参数均为合成夹具。真实 API 成功率与 AI 层语义判断由相应协作方单独统计。文件存储故障无法写终态时可以保持 pending，必须原 ID 对账。预检到随机判定即停止推演，不能保证之后一定成功。跨存储多项事务、flow、发布和外部副作用明确不支持。

## 复验

项目根目录 PowerShell：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
engineering/.venv/Scripts/python.exe -B -m pytest engineering/acceptance/atomic-batches/test_atomic.py engineering/acceptance/atomic-batches/test_stumpsville.py -q -p no:cacheprovider --basetemp engineering/acceptance/atomic-batches/recheck-tmp --junitxml engineering/acceptance/atomic-batches/recheck.xml
engineering/.venv/Scripts/python.exe -B -m pytest engineering/backend/tests/test_host.py engineering/backend/tests/test_foundation.py engineering/backend/tests/test_model_contracts.py engineering/backend/tests/test_notifications.py engineering/backend/tests/test_knowledge.py -q -p no:cacheprovider --basetemp engineering/acceptance/atomic-batches/regression-recheck-tmp --junitxml engineering/acceptance/atomic-batches/regression-recheck.xml
engineering/.venv/Scripts/python.exe -B engineering/acceptance/atomic-batches/record_results.py
```

每次复验先登记输入和输出路径。`*-tmp/` 为忽略的独立存储，不能指向正式数据目录。`record_results.py` 汇总本轮保留的八份 XML、唯一用例、首次失败和生产文件摘要；新增复验报告应显式加入记录后再重新统计。回归中有一个既有 Starlette/httpx 弃用警告，没有测试失败。
