# AI 队列整理与提交关联 Schema 验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 关联文档：[机器契约说明](../../contracts/README.md#ai-队列整理与提交关联字段)、[命令 Schema](../../contracts/ai-operations.json)

本次仅修改 ai-operations.json 的三项现有命令并新增 ai.queue.archive；其他 20 项命令 Schema 逐项比较保持不变，无命令删除。新增字段及条件按 AI 模块责任者给出的精确约定实施，保留旧调用形式及参数边界。没有修改宿主执行或 AI 服务代码，没有运行真实房间或调用模型。

| 证据 | 内容 |
| --- | --- |
| [test_schema.py](test_schema.py) | 55 项检查：全部命令 Schema 结构、旧调用、新字段长度、五类 targetId、理由条件必填、摘要及引用 ID、分支互斥和未知字段拒绝 |
| [core.xml](core.xml) | 55 项全部通过，无失败或跳过 |
| [change-manifest.json](change-manifest.json) | 修改前后文件摘要、修改／新增／未改动命令列表 |
| [results.json](results.json) | 测试 ID、统计与契约、测试源码及证据摘要 |

归档时 reason 必填；恢复时可省略。submissionKey 不得用于 player.request 的 requestId 转交分支；correlationKey 仅用于 package 来源。新摘要和 ID 严格限制小写十六进制，拒绝尾部换行；可选字段显式传 null 同样拒绝。旧 package context 的既有自由对象语义不变。

Schema 只验证输入形状，不能证明 digest 等于当前 DTO queueDigest、前继属于同一会话、当前状态允许归档或幂等键归属有效。这些运行时约束及业务状态、回执保持由 AI 服务与包侧联测验证，本报告不作已通过声明。

项目根目录 PowerShell：

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
engineering/.venv/Scripts/python.exe -B -m pytest engineering/acceptance/queue-schema/test_schema.py -q -p no:cacheprovider --basetemp=engineering/acceptance/queue-schema/core-tmp --junitxml=engineering/acceptance/queue-schema/core.xml
```

独立使用 jsonschema，无需导入正在施工的 AI 模块。临时输出仅限本目录忽略的 `*-tmp/`；保留旧证据时更换输出名称。
