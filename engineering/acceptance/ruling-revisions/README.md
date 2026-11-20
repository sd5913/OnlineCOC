# 裁决修订与旧回执兼容验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 关联文档：[裁决接口与恢复](../../../docs/current/engineering/ai-rulings.md)、[专项测试](../../ai/tests/test_ruling_revisions.py)

## 修复范围

配置裁决意图保存 proposalRevision；当前队列按修订号及候选摘要同时筛选状态和回执。同内容重新修订后的 candidateDigest 可以不变，旧修订的 blocked 不再覆盖新修订。宿主权限、完整候选风险确认、固定命令 ID 和真实 publication 的完成事实保持原语义。

旧记录只在全部 commandId 精确指向同一提案、同一修订及 approve/apply 阶段时推断归属。缺失回执、混合修订、不完整 ID 或元数据冲突不被猜测为过期；同摘要决定继续保留，无法定位的 unknown/executing 即使摘要变化仍阻止重试。读取不迁移或删除旧决定；原宿主回执及原 AI 命令回执可继续查询。

## 证据

| 文件 | 结果与作用 |
| --- | --- |
| [initial.xml](initial.xml) | 修复前 2 项失败，均复现重启后新修订被旧 blocked 覆盖；保留原始失败 |
| [core.xml](core.xml) | 修复后 23 项通过；首轮 2 项失败均有同名通过复验 |
| [regression.xml](regression.xml) | 76 项通过：现有裁决、HTTP/命令权限、来源审核、会话重启及宿主高危发布的相关回归 |
| [results.json](results.json) | 99 项去重通过的机器统计、失败复验对应、测试 ID 及本次源码摘要 |

专项使用真实 Host、FileDataStore、Proposals 和公开 AI command，在临时目录创建并多次重开房间；A/B/C 使用技术包及真实检查器，无模型调用。覆盖旧 epoch 明确拒绝、相同摘要 revision 1→2、新修订未检查时不可批准、三检后 pending、玩家拒绝、高危指纹和风险理由必填、发布一次、再次重启后不重发，以及原拒绝回执不变。另验证旧 unknown/executing 跨修订及重启仍阻止执行、回执命令 ID 的精确匹配和歧义保守处理。

全部测试只写本目录忽略的 `*-tmp/`。未读取或改写用户真实存档、未批准真实锅盖候选，未运行包侧浏览器；包侧真实界面恢复与 diff.before 冲突保护需在引擎交接后独立联测。

## 复验命令

项目根目录 PowerShell：

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
engineering/.venv/Scripts/python.exe -B -m pytest engineering/ai/tests/test_ruling_revisions.py -q -p no:cacheprovider --basetemp=engineering/acceptance/ruling-revisions/core-tmp --junitxml=engineering/acceptance/ruling-revisions/core.xml
engineering/.venv/Scripts/python.exe -B -m pytest engineering/ai/tests/test_rulings.py engineering/ai/tests/test_entrypoints.py engineering/ai/tests/test_review_debug.py engineering/ai/tests/test_session_restart.py engineering/backend/tests/test_ai_publication.py engineering/backend/tests/test_high_risk_host.py engineering/backend/tests/test_high_risk_commands.py -q -p no:cacheprovider --basetemp=engineering/acceptance/ruling-revisions/regression-tmp --junitxml=engineering/acceptance/ruling-revisions/regression.xml
```

已有历史证据需要保留时，用新的输出文件名和 basetemp。当前 pytest 输出的 Starlette/httpx 弃用提示与本次裁决修订问题无关。
