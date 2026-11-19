# KP 实体搜索标签验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-19
- 最后更新：2026-11-19
- 关联文档：[AI 数据查询](../../../docs/current/engineering/ai-data-query.md)、[专项测试](../../backend/tests/test_entity_labels.py)

## 实际变更

宿主 `data_queries.rows` 在实体可见性投影、多接收者交集及外发过滤后，仅在账号和 initiator 均为 KP 时尝试调用可信包适配器 `reference_label('entity', instanceId, originalName)`。去除首尾空白后为 1—160 字符且可编码为 UTF-8 的字符串才用于候选搜索及读取展示；扩展不存在、异常、空值、类型错误、非法 Unicode 或超长时回退原名。

包侧可据真实绑定显示“木栗（player1 的树桩镇角色）”，帮助区分默认示例实体与实际游戏角色。标签必须只描述当前实体同一可见等级的资料，不引入额外隐藏剧情。实体原始 name、owner、configurationId、lifecycle、完整数据、可见性及六字段引用均不改变。最终执行应读取并核对实体真实身份，不能将展示文字作为授权或事实证明。

PL 请求继续走 knowledge；KP 代 PL 请求及混合接收者不使用该钩子。标签影响搜索匹配、分页快照和查询证明；标签变化后旧查询证明按既有规则报 `SOURCE_STALE`。AI 引用组件仍显示原实体名，本轮只修改模型实际使用的宿主数据查询入口。

## 证据

`core.xml` 记录 15 项专项全部通过：实际角色标签命中、读取后核对原文、六字段引用不变、非法标签／异常回退、长度边界、外发过滤、混合接收者、严格 PL 路径、分页与证明复验。对应脚本为 `test_entity_labels.py`，全部为隔离夹具，不调用外部模型。

查询／引用／知识及高危读取的回归见 [regression.xml](regression.xml)：**76 项全部通过**，包含上述 15 项，去重仍为 76 项。数量与代码摘要见 [results.json](results.json)。现有 Starlette TestClient 的 httpx 弃用提示不影响结果，本轮未修改依赖。包侧确定性验收与真实 DeepSeek K08 另由包测试维护，不计入本目录的宿主结果；此处通过不代表模型一定选对角色。

## 复验命令

先按 hierarchy 登记依赖使用及输出改动，并确认源码稳定，再从项目根目录运行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
engineering/.venv/Scripts/python.exe -B -m pytest engineering/backend/tests/test_entity_labels.py -q -p no:cacheprovider --junitxml=engineering/acceptance/entity-search-label/core.xml
engineering/.venv/Scripts/python.exe -B -m pytest engineering/backend/tests/test_entity_labels.py engineering/backend/tests/test_high_risk_host.py engineering/backend/tests/test_knowledge.py engineering/ai/tests/test_data_queries.py engineering/ai/tests/test_references.py -q -p no:cacheprovider --junitxml=engineering/acceptance/entity-search-label/regression.xml
```

未修改正式存档、包数据、账号凭据或运行服务；未调用付费 API。本轮不重复计算先前 188 项宿主或其他聊天的 AI 测试数量。
