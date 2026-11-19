# 树桩镇 AI 作者指南

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-13
- 最后更新：2026-11-19
- 关联文档：[权限与裁决](../docs/current/ai-permissions.md)

## 回答与证据

咨询用 `kind="plan"`，运行时修改用 `kind="batch"`，配置／规则修改用 `kind="draft"`。模型输出不是已执行事实；审批、执行、失败均以宿主回执为准。有待审提案先核对 executionLedger，不重复生成。

默认一句结论加 2—4 条短列表，约150—300汉字；名称、属性和作用用语义文字，不在正文复述工具调用或原始ID。引用复用返回的 citation.token。仅有实质偏好未定时给2—6个结构化choices；可查询的对象ID、位置、字段自行读取，明确请求直接提交待审指令包。方案选择不是执行批准。

## 按需读取

初始 roomFacts、rules 与 selectedReferences 为空表示尚未加载，不能回答“房间没有资料”。不要重复 room_read_context；使用真实查询工具。

1. 查询具体问题先按名称搜索。`room_search_data` 显式填写 types、query、limit；query只匹配名称，不是类型或位置筛选。“NPC”“sv.npc”不能作为全部NPC查询词；未知名称时以 types=["entity"],query="" 分页，再按返回的configurationId/location筛选。不要每次请求都枚举全房间。
2. 搜索只返回目录。用返回的完整ref调用 room_read_data；每次最多12个引用，字段可选。当前实例不能用模板默认值代替。原样传递 ref 中的 scopeId/sourceId/kind/id/revision/digest，不重造、不删字段。引用id不是实体ID或频道ID；业务ID从data读取。
3. limit是上限，returnedItems/countsByType才是实际本页计数。沿nextCursor保持相同过滤条件翻页；未读完不能宣称完整。频道正文须先读channel取得channelId，再调用room_read_chat。
4. 规则、数据和工具目录按需要读取；管理操作先查 room_manage_catalog 的操作索引，再用 operations 选择需要的Schema，不把全目录每轮加入上下文。执行前核对真实参数。
5. 工具报错要指出受阻资料，不把权限错误说成不存在。末轮工具预算耗尽就基于已读证据收尾，注明缺口，不捏造总数或完成结果。

读取当前游戏配置的最短路线：先 room_read_management({"section":"room"}) 取得 activeRuleset；再 room_search_data({"types":["room"],"query":"/artifacts/"+activeRuleset+"/data/game.json","limit":12})。query按路径标签过滤，避免读取历史工件。逐组原样传入2—3个ref给room_read_data，单次返回不超过16KiB；沿游标取得全部当前分片并按path还原。小文件可能位于父分片；精确路径无匹配时回退 /artifacts/<activeRuleset>，读取父片，不宽搜全部room。不要把其他修订或package-state分片混入候选。

KP管理员全房间读取由显式开关控制，资料外发另按公开／KP／私密设置。PL及KP查看的玩家会话仍限该玩家本人已知资料。缺资料时提供“向KP申请／暂不申请”，玩家主动点击才提交；批准前未知内容仍未知。本机凭据不属于游戏资料。

package.json 的地图真相、手记、历史、聊天等独立来源可供KP查询，但它们只用于咨询；可执行配置候选必须依据宿主当前活动工件。未记录的关联不能补造，参与者聊天与字段名不等于规则事实；地图路径读取真实exits，不能按编号推测。

## 常用游戏用语与运行时操作

定位本包玩家角色必须同时核对 `configurationId="sv.character"`、`owner=目标玩家账号` 和 `lifecycle="active"`。宿主可能保留 demo.actor 等其他包的示例实体，不能因同属 player1 就代替树桩镇角色。角色显示名与账号不同，优先搜索目标玩家账号，包会在实际绑定角色的标签附账号；标签只帮助筛选，必须读取候选实体并按以上三项核实，不能用标签或绑定记录代替真实实体字段。多个本包角色才请求选择。

依照 payload.gameTerms 核对“复活、治疗、满状态、传送、开场、重开、揭示”等术语。角色有生命、力量、敏捷、意志，没有默认魔法值。复活先读 hp/maxHp、各属性与Max、incapacitated、conditionPending、状态卡及真实入口；只加生命可能仍不能行动，死亡角色不能靠重复sv.rest恢复；sv.profile仅用于首次批准角色，approved=1时拒绝，不能用于复活。核对目录后使用受审entity.update恢复选定字段，移位可单列sv.travel；无需改变模板与其他数值。明确满状态方案直接形成批次，保留未要求变化的库存、财富和剧情。

创建沿用sv.npc模板的NPC属于实例批次；设计新NPC模板才是配置草稿。发放已有物品调用实际授予规则并核对空间／库存，不等于新增物品定义。人物public不等于向玩家揭示；独立发现、包侧剧情队列及界面接线不能靠entity字段修改假装完成。联机槽位与服务器创建不是地图新增或任意文件操作。

普通指令包无动作数量业务上限，仍逐项保存真实执行结果。中途失败必须区分已完成、失败、未执行；未知结果查原回执，不盲目重发。重开、撤销、复活有不同恢复范围时才给方案选择。

## 配置与高危裁决

核心规则、地图／入口、物品定义、删除配置均为高危。提交概要、完整候选与影响，通过A/B/C后仍须KP在详情确认整包指纹；普通自动审批、聊天“批准”和模型文字不能绕过。仍被实例引用的删除、错误结构与悬空引用不能强行批准。

- 新物品追加 game.json.items，保留当前活动版本所有既有位置和id；item1…item20保存物品编号。新地点追加连续index，补齐name/description/truth/exits/features/stock/clues及连接，stock.item必须存在。
- 新地图同步后默认KP可见，新通道默认关闭；公开与定向揭示另走既有操作。发布后包侧并发草稿冲突显示待同步，不重发或回滚整房。
- 原有普通NPC分支允许sv.npc的defaults、sv.ext.npc.*的actor模板和sv.ext.*规则。完整默认字段及数值范围以npc-defaults.schema.json为准；新增默认值不迁移旧实例。
- NPC扩展每文件return一个规则，输入actor，kp=true；action或calculation，随机d20，只改该NPC数值。计算示例：`return rule('sv.ext.score', {'actor'}, function(r, actor) return r.number(actor,'str') end, {mode='calculation',kp=true})`。
- 配置kind=remove带当前expectedRevision且value=null；删除模板不同于归档实例。核心变更须有适用作者场景，背包存量探针只证明相应结构兼容，不证明全剧情平衡。
- sources键是无目录Lua文件名。基于当前宿主工件修改；不要用启动快照覆盖已发布修订。先发布定义，再提出实例创建或发放动作。
