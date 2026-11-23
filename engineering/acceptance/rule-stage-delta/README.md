# 活动修订上的规则增量暂存验收

2026-11-23，隔离 Demo 工件与存档；不读取树桩镇活动目录，不修改 AI 模块，不操作正式房间或 Git。

## 协议与实现

新增普通命令 `rule.stage.delta`，参数 `{baseRevision, sources?, data?, removeSources?, removeData?}`。在KP权限和房间锁下确认 `baseRevision == activeRuleset`，深拷贝完整基线，按文件键替换/删除，然后调用既有完整 `registry.stage` 校验及原房间事务提交。成功result仍为修订ID，只暂存，不激活。旧 `rule.stage` 不变。

`sources/data` 是按键完整替换而非深层JSON合并；data的null是普通值。删除不存在的键返回 `RULE_FILE_NOT_FOUND`；空增量或增删冲突为 `INPUT_INVALID`；过时或非活动基线为 `VERSION_CONFLICT`。Schema另拒绝未知字段、重复删除键、非字符串源码等。详见[使用文档](../../../docs/current/engineering/lua-authoring.md#文件增量暂存)。

## HTTP测证

`measurements.json` 记录真实ASGI HTTP入口的实际序列化字节，未调用外部服务。基线工件采用不同长度的合法Lua注释和JSON字符串；每次只增改一个小JSON值，完整与增量暂存产物完全一致，活动修订不变。

| 完整请求字节 | 增量请求字节 | 完整请求HTTP | 增量请求HTTP |
| --- | --- | --- | --- |
| 62,963 | 530 | 200 | 200 |
| 122,963 | 530 | 413 | 200 |
| 194,963 | 530 | 413 | 200 |

无Content-Length的分段流式请求：65,536字节成功；65,537字节仍413。`maxCommandBytes`仍65536，完整工件的64个Lua文件、源码/数据各1MiB和worker资源限制不变。本测量是包体边界与行为验证，不是网络延迟基准。

## 自动验证与重现

`delta-v3.xml`：73项通过，覆盖新增增量专项与test_host、test_foundation、test_model_contracts、test_faults。包括完整工件等价、基线不变、JSON null、删除与显式依赖、语法/重复ID/大小和文件数量、KP授权、过时/非活动基线、同ID冲突、原封套跨重启回执、发布前故障不提交、发布后丢回复恢复、并发激活锁边界、旧流程锁定、HTTP 413与旧接口兼容。

前两次失败保留于 `delta-v1.xml`、`delta-v2.xml`：第一轮测试把未声明的Demo动态调用误作静态依赖；第二轮用新catalog重建了同ID封套，违反原有幂等协议。分别修正为显式依赖夹具和保留原始封套后全量通过，没有放宽生产校验。

`v1-source.json`、`v2-source.json`、`v3-source.json` 记录对应隔离树逐文件哈希。AI依赖采用既有 `ai-performance-interface-snapshot/v3`，不读取正在修改的AI目录。`interface-v1/source.json` 列出本任务三个生产文件的冻结副本；它是供当前引擎联测覆盖的文件集合，不是独立安装包。`handoff.json` 记录当前修改、文档、测试与证据清单及最终哈希。

从项目根目录使用不存在的新目录名运行：

```powershell
& engineering/.venv/Scripts/python.exe engineering/acceptance/rule-stage-delta/freeze.py rerun
& engineering/.venv/Scripts/python.exe engineering/acceptance/rule-stage-delta/measure.py rerun
```

在生成的 `work/rerun/engineering` 中用同一虚拟环境执行上述五个pytest文件；将basetemp与XML输出放在本验收目录内。`work/` 被忽略，不是正式存档。

## 限制

仍须传送每个改动文件的完整内容，单个巨大文件、巨大数据值或大批修改依然可能超64KiB；没有文本行补丁或分块上传。只允许活动基线，不允许将未激活暂存版本隐式当作增量分支。静态检查只识别显式依赖，动态规则调用保留既有运行时检查。SDK通用command可调用新操作，未新增操作台专用编辑界面。
