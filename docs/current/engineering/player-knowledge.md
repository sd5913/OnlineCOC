# 个人知识与资料披露服务

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-17
- 最后更新：2026-11-17
- 关联文档：[机器契约](../../../engineering/contracts/knowledge.json)、[房间格式](room-format.md)、[施工验收记录](../../history/2026-11-17-player-knowledge-construction-plan.md)、[ISSUE-011](../../history/2026-11-17-issue-011-player-knowledge-authorization.md)

## 权威记录和使用边界

`onlinecoc.knowledge` 属于宿主后端，不依赖 AI、模型 API 或数据库。Room v4 的 `knowledge` 必须存在，包含独立 `scopeId`、策略、不可变观察、授权与主体版本。账号和本次成员 ID 共同标识主体；成员重建不能继承原授权。

`observed_snapshot` 保存披露当时的分面数据、来源修订、摘要与来源类别。原正文更新不覆盖旧观察；原实体归档不自动删除历史。提供方的硬使用限制仍可阻断历史。`live_scope` 每次读取当前已授权数据，适用于持续告知的本人状态等内容；能否持续读取由提供方再次检查，不能将到访直接当作持续订阅。

知识授权只改变读取资格。它不授予对象写权限，不代表一次观察足以调用任何规则。固定资料片段不作为 Entity，也不附带旧实体 `viewToken`。

完整本人实体兼容需分面明确声明 `entityProjection=true` 且仅支持 `live_scope`。提供方返回完整合法Entity，关键身份/修订字段须与权威实例一致，owner须等于主体。有效持续授权下，该实体可进入旧view/query并取得绑定知识引用的viewToken；撤回后实体与旧令牌失效。默认分面不走此路径，不能把固定资料拼成可写实体。

同一观察可以有多条授权；只撤回一条而存在等价授权时引用继续有效。撤回最后一条后旧引用不可读；另一版本的授权不能替代。记录保留在存档中，撤回不声称能抹去已发送到客户端或人记忆中的信息。

## 可信提供方与持久策略

本机装配调用 `host.register_knowledge_provider(descriptor, provider)`，返回包含 `descriptorDigest` 的描述符。HTTP 不接受 Python 路径、动态代码或调用方提供的分面 Schema。注册与策略绑定分开：KP 通过命令确认绑定后，描述符才进入房间存档。

描述符包含命名空间、选择器、分面 Schema/模式与出口处理声明。当前选择器支持实体配置 ID、配置前缀或实体 ID，以及明确资产/包资源 ID。策略覆盖未来符合条件的实体。存在重叠选择器时保守拒绝绑定，不按提供方加载顺序决定权限。

提供方必须实现以下本机 Python 方法：

| 方法 | 作用 |
| --- | --- |
| `pin(resource, facet_ids, context)` | 返回同一来源版本的 `sourceRevision`、`facets`、`sourceGuard` |
| `read_live(resource, facet_ids, context)` | 检查持续资格后读取当前值，返回同样结构 |
| `check_guard(source_guard, context)` | 检查固定观察的当前硬使用限制，不用最新正文替换快照 |
| `derive_observations(outcome, context)`，可选 | 从宿主成功动作及entity.create/update/patch提出观察，记录与该动作同一次提交 |
| `authorize_operation(operation, args, context)`，可选 | 严格玩家调用规则前的输入资格校验 |
| `project_operation(operation, result, reads, context)`，可选 | 返回适合该玩家的结果；返回 `None` 表示不披露 |
| `project_catalog(actions, context)`，可选 | 给出安全目录；缺省不公布严格玩家规则目录 |

`context` 包含当前房间副本、`accountId`、`memberId`、`player`、每请求 `cache` 与本机宿主引用。提供方属于受信代码，不应在这些方法中调用网络、执行模型请求或自行提交房间。多次读取包文件应使用请求缓存保证来源版本一致。

自动观察的outcome包含commandId、operation（规则ID或管理命令名）、input、result、effects；context.previousState提供提交前执行态。返回列表项为subjectMemberId、resource、facetIds。宿主生成来源事件键、时间与执行者，不接受客户端自报到访。独立包事务没有宿主回执时仍使用KP显式披露。

参考实现 `HostStateProvider` 使用安装时的字段映射，例如 `{'identity': {'name': 'name'}}`；字段路径不是客户端提供的 JSONPath 或脚本。未安装提供方、版本摘要不符或提供方出错时，持久策略继续保护资源，读取不会退回旧 public 语义。

CLI 可独立于 AI 装配：

```powershell
engineering/.venv/Scripts/python engineering/backend/scripts/run.py --data-dir D:/isolated/room serve --knowledge-provider D:/trusted/provider.py --knowledge-data-path D:/isolated/package
```

模块提供 `install(host, data_path)`；安装完成后宿主才继续恢复需要知识提供方的待执行动作。未给出提供方时，已绑定策略的房间保持资料阻断。

## 命令和读取接口

命令仍走 `/api/v1/commands`，复用 commandId 幂等、authorityEpoch、权限及文件提交事务。

| 命令 | 关键参数 |
| --- | --- |
| `knowledge.policy.bind` | `policyId`、安装描述符摘要、`expectedRevision`；初次为 0 |
| `knowledge.observe` | 策略版本、主体 memberId、resource、分面、预览的来源版本、reason |
| `knowledge.subscribe` | 策略版本、主体 memberId、resource、分面、reason |
| `knowledge.revoke` | grantId、当前授权 revision、reason |

四项命令均要求 KP。调用方不能上传正文、观察时间、来源类别或执行者身份。观察、授权、审计与回执一起提交；同 ID 同参数返回原回执，异参数冲突。发生未知结果时先查回执。

| HTTP | SDK | 权限及返回 |
| --- | --- | --- |
| `GET /knowledge/capabilities` | `knowledgeCapabilities()` | 玩家只见最小能力状态，KP另见安装描述符与绑定 |
| `POST /knowledge/preview` | `knowledgePreview(args)` | KP预览当前分面与来源版本；不产生授权 |
| `POST /knowledge/search` | `knowledgeSearch(args)` | 只列调用账号当前授权资料；默认每资源/分面最新观察 |
| `POST /knowledge/read` | `knowledgeRead(refs)` | 按完整版本引用批量读详情；任一无效整批失败 |
| `POST /knowledge/grants/query` | `knowledgeGrants(args)` | KP分页查授权记录 |

路径均以 `/api/v1` 为前缀。POST 要求现有登录和 CSRF；不支持 `asAccount`。`InProcessTransport` 有对应下划线命名方法，保持相同权限检查。LAN/P2P 只增加上述明确路由；网页包仍须在自身路由清单中声明。

`KnowledgeRef` 是 `{schemaVersion, scopeId, id, revision, digest}`。必须原样保留，不按资源 ID 重新查最新版本冒充原引用。详情含同版本 `label`、`facetId`、`mode`、`observedAt`、`data`、`provenance.kind`。个人资料统一按 `visibility=private` 分类，原世界对象 public 不自动允许向外部模型发送。

搜索页返回 `items`、`nextCursor`、`coverage=authorized-query`、`viewRevision`。游标绑定主体和授权查询结果，过期时返回 `SOURCE_STALE`；重启后重新搜索。`includeHistory=true` 列出仍有授权的旧观察。默认 20、最多 50 项；一次详情最多 12 引用，响应不超过 64 KiB。

## 出口与只读证据

受控对象从未获授权的旧 `/view`、集合查询和进程内视图中移除。严格玩家的关系、进度、wait与流程数据缺少安全投影时移除；规则目录和执行需要提供方明确支持。旧回执再次按当前权限投影；授权过一次不代表旧回执永远可读。

素材直接地址也检查策略和受控实体附件。首版不披露受控二进制资源。普通聊天参与者权限继续生效，但受控角色名、附件和旧行动结果卡不能绕过资料过滤；严格模式不允许通过 `chat.message.share` 广播原始规则结果。人工聊天正文仍是参与者表达，不自动成为世界事实或新观察。

WS 发送完整分块快照。发送最终 end 前在宿主锁内重新验证当前授权投影与登录，校验成功后排入发送任务，随后释放锁等待网络。撤权先发生则发 reset，SDK丢弃临时块；已排队或已经发送的字节无法撤回。

SDK 登录、恢复身份与退出时立即清空旧视图、临时块和命令缓存；连接回调绑定连接代号，HTTP 结果绑定会话代号。旧连接迟到的消息或关闭通知不能覆盖新账号，跨会话返回的查询以 `SESSION_CHANGED` 拒绝。界面仍应在身份切换事件中清空自己保存的详情；不得绕过 SDK 复用上个账号的资料。

`capture`、`evidence`、`recheck` 提供只读证据门面。证据绑定主体、知识作用域、策略和具体分面版本；不相关角色变化不使固定资料失效。AI 的严格玩家上下文使用 `knowledgeProofs`，实际绑定会话 owner，仍检查会话、外发策略和提供方；发布与执行批准继续使用原完整基线，严格只读上下文不能作为批准依据。AI 内容与界面验收独立于本模块核心测试。

`recheck_many(account, proofs, state=...)` 在一个一致读取中批量复验，最多100份proof、1,000个去重引用；不按每份proof重复加载来源。AI消费者调用 `require_egress(account, 'ai')`，显式 `denied` 高于提供方安全投影钩子。view、query、rules和receipts同样遵守各自声明；知识专用接口不是原始Entity出口。受控资产二进制尚未支持披露，继续拒绝。

## 容量与验证

一次观察限一个主体/资源、最多 8 分面；单分面 8 KiB，单观察 32 KiB；房间最多 10,000 观察、50,000 授权、知识记录合计 16 MiB。达到任一限制则拒绝，无自动清理历史或截断正文。

核心测试为 `engineering/backend/tests/test_knowledge.py` 与 `test_knowledge_network.py`，另有 `engineering/acceptance/knowledge/test_edges.py`。覆盖主体隔离、固定/实时版本、等价授权、伪造、幂等、提交故障、提供方缺失、未来对象、旧令牌、素材出口、WS撤权屏障、显式转换、恢复分叉和容量拒绝。最终宿主/联网176项、AI384项去重测试全部通过，另有Stumpsville12组知识与8组场景回归；逐项K-01—K-27、原始失败/复验及源码摘要见[验收报告](../../../engineering/acceptance/knowledge/README.md)。

中样例为20名玩家主体、1,000个资源、5,000条授权，知识约3.01 MB。在本机Windows/CPython 3.14.2各运行100次，warm搜索50项/读取12项/复验12项的p95分别约71.5/68.9/70.4 ms，同数据legacy扫描基线约67.4 ms，满足2倍基线加20 ms的门槛。每请求仅捕获一份文件存储内存快照；完整数据和计数见[性能记录](../../../engineering/acceptance/knowledge/performance.json)。

大账本首次结构验证与全量文件写入仍有成本：新进程冷开约2.06秒；5,000授权后新增一次观察的完整命令约1.44秒，其中文件提交约443 ms。结构缓存只保存已验证内容的摘要，不缓存授权或来源检查；篡改和跨记录引用仍验证。首版仍使用全量文件代及现有累计配额，不承诺数据库级写入延迟；高频大型房间需另行评估存储策略。
