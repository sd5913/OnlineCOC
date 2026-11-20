# Stumpsville 数据管理

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-19
- 最后更新：2026-11-19
- 关联文档：[Stumpsville 导航](stumpsville.md)、[规则与数据定义](stumpsville-rules-data.md)、[玩家知识服务](../player-knowledge.md)

基于本仓库 `rulepacks/stumpsville/`（树桩镇，manifest 版本 `0.9.0`）源码核查。下文路径除链接外均相对该包；KP 为主持，PL 为玩家。只概括当前实现，游戏资料中标注“待终校”的内容仍不是已核实的原版规则。

## 存储结构

```text
运行数据根目录（启动面板默认 runtime/）
├─ slot-selection.json                  上次选择
└─ slots/<固定ID>/                      一个房间槽位
   ├─ slot.json                        槽位名称/创建时间
   ├─ host/                            宿主实体、规则修订、命令回执与知识账本
   ├─ package.json                     包侧 format=2：草稿、请求、任务、事件、地点、聊天、笔记等
   └─ package-backups/                  包侧快照与宿主备份引用
```

## 写入与恢复

源码：[slots.py](../../../../rulepacks/stumpsville/tools/slots.py)、[launch.py](../../../../rulepacks/stumpsville/tools/launch.py)、[package.py](../../../../rulepacks/stumpsville/tools/package.py)。`package/state` 返回授权视图；写入先保存任务步骤与命令信封，恢复时查询原回执，再继续未完成步骤。`package.json` 使用临时文件、落盘、替换保存。浏览器只保留布局/偏好/已读状态/待确认命令等客户端状态，不能据此判定游戏结算成功。

裁决转 AI 的信封独立保存在包侧任务 `aiReview` 中，未知结果先查 AI 回执；不会混入游戏指令回执或将原裁决标为执行完成。来源带类别、ID、修订和原申请人，只是提交时快照；发布配置仍须依据当前活动工件。调试导出是授权只读查询与本地下载，不创建持久导出任务。

## 权限分层

个人知识分面由 [knowledge_provider.py](../../../../rulepacks/stumpsville/tools/knowledge_provider.py) 定义：`scene/identity` 是固定观察，`sheet/play` 是持续告知。进入地点或KP向本人揭示产生观察；地点发布、前端隐藏、KP预览均不能代替个人授权。扩展资料时一并定义可见字段、来源版本与揭示条件；KP `truth`、完整场景状态及其他玩家私有数据不进入PL通知或AI上下文。

本人角色的 `sheet` 投影补充实际所持物品的名称、公开说明及当前用量；不包含完整物品库、隐藏定义或原始私密元数据。仅补语义表示，不改变个人授权与固定观察。

KP资料页读取 `admin.configurations`、完整活动规则工件、全部规则数据键及 `contracts`；按类型生成子标签，并提供当前房间场景和活动实例等管理快照。列表搜索、详情按需打开；活动实例不含归档对象。数据仅在KP授权页加载，不进入玩家静态包。

AI 高危配置发布后，`publication_sync.py` 根据旧工件、包侧草稿和批准工件做三方同步；新增地点使用持久命令信封恢复。冲突显示已发布但待同步，不覆盖本地草稿。KP 全读包内资料由宿主传入受信 `kp-room` 范围，PL 不能通过同一参数扩权。详见[AI 权限与裁决](../../../../rulepacks/stumpsville/docs/current/ai-permissions.md)。

配置局部编辑先读取目标节点取得版本引用，再由 AI 模块展开完整候选，保留未修改字段；追加物品保持已有编号，校验重复 id。实际发布仍通过三检与 KP 高危确认，见[调试与查询](../../../../rulepacks/stumpsville/docs/current/ai-debugging.md)。
