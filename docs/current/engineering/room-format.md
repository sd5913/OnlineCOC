# 房间格式与发行变更

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-14
- 最后更新：2026-11-20
- 关联文档：[机器契约](../../../engineering/contracts/models.json)、[知识契约](../../../engineering/contracts/knowledge.json)、[初始化样例](../../../engineering/contracts/fixtures/room-initial.json)、[运行说明](first-test.md)、[个人知识服务](player-knowledge.md)

## 当前支持

后端 **0.3.0 仅加载 Room v4**。新建直接生成 v4；打开、提交、备份验证和恢复拒绝旧版本、未知版本及损坏格式。Python包版本、`onlinecoc.version`、CLI `--version` 和 `/api/v1/capabilities` 对齐。LAN、P2P、网页与桌面管理器版本独立。

v4 新增必需 `knowledge`：子格式1、独立scopeId、revision、policies、observations、grants、subjectEpochs。它属于宿主权威存档，即使AI关闭也保留。主体、观察摘要、授权引用、容量与提供方策略均参与验证。原v3的chat、aiControl继续必需。

后端不在打开或查询时自动迁移。已有v3需要显式复制转换；真实游玩数据与旧备份不因更新代码而改变。更早v1/v2不在本转换器范围，其历史契约见[旧格式快照](../../history/2026-11-14-room-formats-before-0.2.0.json)。

## 完整结构

所有顶层字段必需，无未知顶层字段。完整验证另检查世界引用、归属、包含环、数值、聊天、AI批准工件与知识账本。

| 字段 | 语义 |
| --- | --- |
| schemaVersion、roomId、name、runId、status | 格式、房间身份、名称、场次及运行状态 |
| entities、relations、members | 实例、关系、成员，使用稳定ID索引 |
| configurations、progress | 配置定义与成员／实例进度 |
| commands、flows、waits | 幂等回执、持久流程、等待 |
| artifacts、activeRuleset | 规则工件及生效版本 |
| assets | 素材元信息；备份另外验证实际文件 |
| chat | 频道、消息、序号与个人已读 |
| aiControl | AI设置、独立scope、批准与发布记录 |
| knowledge | 持久策略、固定观察和个人授权 |
| audit、outbox、collectionRevision | 审计、通知与集合版本 |

版本号彼此独立：Room=4，Entity=1，AI契约/控制=1，知识=1，聊天=1，网络protocolVersion=1，文件封套format=1，备份format=1。执行态ExecutionSnapshot仍是精简投影，不能作为完整Room打开；知识账本不直接传入Lua。

outbox 兼容旧动作提示，并保存子格式1的 `kind:notification` [定向通知](notifications.md)。新记录绑定已提交原动作、受众授权版本和逐人确认，参与完整房间验证；旧存档无需新增顶层字段或转换。正常重启及备份恢复保留通知与确认事实，不重做来源动作。

## 显式v3→v4转换

以下命令从项目根目录运行，输入必须是停止写入的独立副本或已导出备份。输出必须不存在，不能与输入相同或位于输入目录内。

```powershell
engineering/.venv/Scripts/python engineering/backend/scripts/run.py convert-room --format room --input D:/isolated/v3-room.json --output D:/isolated/v4-room.json
engineering/.venv/Scripts/python engineering/backend/scripts/run.py convert-room --format snapshot --input D:/isolated/v3-snapshot.json --output D:/isolated/v4-snapshot.json
engineering/.venv/Scripts/python engineering/backend/scripts/run.py convert-room --format backup --input D:/isolated/v3-backup --output D:/isolated/v4-backup
```

转换器验证输入版本、封套/备份摘要和文件，再复制形成合法v4，输出源/目标SHA-256。原文件字节不变；新知识账本为空，生成独立知识scope。历史pending执行快照的格式标识同步为4，原命令与随机记录保留。转换不批准新动作，不伪造过去场景的正文或到访时间。

转换报告historicalKnowledgeImported=false。包侧旧locationKnowledge只表明曾有记录，不能证明旧时正文；须在包提供的KP预览后明确执行“现在揭示”。不要在原数据代链中直接改版本号和摘要。

只读检查通过后，仍需要正确身份绑定、素材和包提供方才能实际恢复。部署时停止旧服务，选定新程序及新副本；回滚使用原程序和原备份，新版期间产生的数据不会自动反向合并。

## 验证与恢复

```powershell
engineering/.venv/Scripts/python engineering/backend/scripts/run.py --version
engineering/.venv/Scripts/python engineering/backend/scripts/run.py validate-room --input engineering/contracts/fixtures/room-initial.json
engineering/.venv/Scripts/python engineering/backend/scripts/run.py validate-room --format snapshot --input D:/isolated/v4-snapshot.json
engineering/.venv/Scripts/python engineering/backend/scripts/run.py validate-room --format backup --input D:/isolated/v4-backup
```

room校验纯Room；snapshot另校验封套；backup验证完整备份。检查不启动Host、不占存档锁、不修改输入，成功退出0、失败退出2并输出JSON。SCHEMA_UNSUPPORTED只报告整数版本或null、支持版本[4]和文档路径，不回显正文。当前格式字段错误使用INPUT_INVALID，无效引用使用相关领域错误。

普通重启保留AI与知识scope。恢复为新副本分别生成新AI/知识scope，撤销未消费的approved批准，关闭自动需求；已发布数据与回执保持恢复规则。知识内部观察/授权ID保留，但对外ref的scope与opaque ID改变，旧引用不能读新副本。

普通重启会更换运行期 `authorityEpoch`。引擎的[历史上下文只读复验](high-risk-publication.md#历史上下文的只读复验)允许同 scope 且当前授权、基线和来源仍有效的旧上下文被读取，不改写其原 epoch 或持久内容。旧批准与未执行命令仍受当前 epoch 校验；恢复分叉仍拒绝原 scope 的历史。该读取入口不改变 Room v4 或存档迁移规则。

核心验收覆盖三种离线转换、原字节不变、冷启动、备份恢复和知识引用分叉，见[专项测试](../../../engineering/backend/tests/test_knowledge_network.py)。本轮不转换或覆盖正式存档。
