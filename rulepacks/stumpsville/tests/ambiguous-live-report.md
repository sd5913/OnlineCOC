# Stumpsville 模糊需求实测

2026-11-23 · DeepSeek 官方 API · 模型配置 `deepseek-flash`

每个需求独立开一间房。测试脚本扮演 KP，以自然语言发起需求、补充信息并点击审批。每次人工发言计一轮；发布后由原会话自动发起的续办单列。一次回复可能调用模型多次，运行时审批按提交次数统计。

| 需求 | 人工对话轮数 | 自动续办 | 审批提交 | 官方 API 调用 | 总 tokens | 验证结果 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 水纹盾：新增、发放、通知 | 1 | 1 | 2 | 9 | 161,593 | 已完成 |
| 路费：澄清对象和数额 | 3 | 0 | 1 | 14 | 305,230 | 已完成 |
| 庭院：追加一句雨景 | 2 | 0 | 2 | 6 | 104,891 | 已完成 |

3 个目标都完成，1 个只需一次人工发言。6 次人工发言、1 次自动续办、5 次审批提交，共 29 次 HTTP 200 响应，服务商计量 571,714 tokens（含重复上下文）。每个需求仅运行一次。

可用[逐轮原始证据](ambiguous-live-results.json)查看每次工具请求、实际返回的数据、模型文本、事件、检查结果、候选差异和执行后快照差异。下文列出显式调用的数据工具；工具向模型返回的数据量并不代表模型实际采用了全部内容。

## 水纹盾：新增、发放、通知

### 人工第 1 轮

**KP 原话**

> 给木栗做个叫「水纹盾」的小盾吧，强度照同类推荐。做好了发给他，也提醒他一声。

**AI 回复原文**

> 为木栗准备了一面小盾「水纹盾」的追加候选：物品表目前没有盾类定义，因此按同类轻装推定为一格、轻甲式减伤1、三次用量并在战后检查。
> 
> - 新定义 `water-shield`：占1槽，armor=1，uses=3，useDie 检查用量，说明为「木盾蒙水纹布面，装备且仍有用量时减伤1，战后检查用量」。
> - 追加不改变现有28项物品的编号与 id，木栗现有针剑、火把、口粮、绳索位置不受影响。
> - 定义发布成功后，会把盾发到木栗的空槽（当前第3、4、7—10等槽均为空），并向他发一条定向通知「收到水纹盾」；发放前会重新读取物品编号与背包空位。
> 
> 这道候选属高危物品模板修改，需 A/B/C 检查与你的独立批准；发布前不会发放，也不会先通知。

**读取与工具**　木栗的实体资料、当前房间信息、两页共 28 条物品定义，以及包声明的配置检查。模型据轻装填写减伤 1、占 1 槽、用量 3。

调用顺序：`room_read_management` → `room_search_data` → `room_read_data` → `pack_read_config_data` → `pack_read_config_data` → `pack_read_contract`。

**提交的配置**　`/data/game.json/items/28`。

- A 类 `pass`。检查 json, full-artifact, host-stage, pack-schemas, host-model, references。无检测提示。
- B 类 `pass`。检查 npc-hp, npc-maxHp, npc-str, npc-dex, npc-wil, npc-strMax, npc-dexMax, npc-wilMax, npc-armor, npc-location, npc-incapacitated, npc-lastRoll。无检测提示。
- C 类 `pass`。检查 npc-morale, npc-player-denied, gameplay-inventory, gameplay-travel。LIVE_GAMEPLAY_REVIEW。

**裁决**　KP 提交批准，业务结果 `completed`。

**实际生效**

- `/data/game.json/items/28`　新增 {"id":"water-shield","kind":"armor","name":"水纹盾","description":"蒙水纹布面的小盾，占一格。装备且仍有用量时减伤1，战后检查用量。","armor":1,"slots":1,"uses":3,"useDie":true}

本轮使用 5 次官方 API 调用。

### 发布后自动续办

沿用同一会话与原需求。发布成功触发续办，KP 没有再次发言。

**AI 回复原文**

> 水纹盾定义已发布，物品表第29项（编号29），占1槽、减伤1、用量3且战后检查。木栗当前在1号地点，背包第3、4、7—10槽空着。拟把水纹盾放进第3槽（用完3格用量），随后向木栗的持有账号 player1 发定向提醒；两项一并待你审批。

**读取与工具**　发布后的物品表、木栗的实体和槽位，以及运行时指令目录。此次读取确认了水纹盾的新编号 29。

调用顺序：`pack_read_config_data` → `room_search_data` → `pack_read_config_data` → `room_read_data` → `room_manage_catalog`。

**提交的运行指令**

1. `action.invoke` `{"actionId":"sv.grant","input":{"actor":"d47c2946ef1c4db3bd2ddb9bdc6bf779","item":29,"slot":3,"uses":3}}`
2. `notification.send` `{"recipientAccountIds":["player1"],"text":"木栗：你收到了「水纹盾」——蒙水纹布面的小盾，占一格；装备且仍有用量时减伤1，战后检查用量。现放在背包第3格，用量3。","sourceActionIndex":0}`

- 指令 1 预检 `passed`。
- 指令 2 预检 `passed`。

**裁决**　KP 提交批准，业务结果 `completed`。

**实际生效**

- `/notices/player1/1`　新增 木栗：你收到了「水纹盾」——蒙水纹布面的小盾，占一格；装备且仍有用量时减伤1，战后检查用量。现放在背包第3格，用量3。
- `/players/player1/item3`　0 → 29
- `/players/player1/uses3`　0 → 3

本轮使用 4 次官方 API 调用。

## 路费：澄清对象和数额

### 人工第 1 轮

**KP 原话**

> 想给一个玩家添点路费，你帮我安排一下吧。

**会话返回** `TOOL_FORBIDDEN`。这轮没有交付 AI 回复正文。模型在工具参数中拟问：

> 要给哪一位玩家加路费、加多少枚钱币？确定后我会直接准备待审的数值调整和定向通知。

**读取与工具**　搜索实体、读取房间及两名角色、搜索记忆等既有记录，查询改数值与发通知的指令格式。模型拟询问接收者与数额，随后尝试调用 clarification。

调用顺序：`room_search_data` → `room_read_management` → `room_read_data` → `room_search_data` → `room_manage_catalog` → `clarification`。

本轮没有可审批的候选或指令。


**实际生效**　该轮前后的配置、两名玩家角色数值与定向通知都没有变化。

本轮使用 4 次官方 API 调用。

### 人工第 2 轮

**KP 原话**

> 给木栗，也就是 player1，加 3 枚钱币。发一条通知就好，豆叶不用改。

**AI 回复原文**

> 预检返回「对象不可见」，因此我把查找结果中的实体 ID 原样重试了一次；木栗仍是唯一匹配到的 active 的 sv.character、owner=player1 的角色，当前 pips=3。
> 
> - **改动**：pips 由 3 改为 6，其他字段不变。
> - **通知**：给 player1，绑定在钱币更新成功之后才投递。
> - 若这次仍被挡，说明是宿主对实体写入的可见范围限制，而非角色数据缺失；此时需要你在管理员设置中放宽相应范围，或由你改用其他途径处理。

**读取与工具**　按“木栗”检索实体、读取改数值与发通知的指令格式，再读取角色字段。一次带字段筛选的读取返回参数错误。随后取得的数据包含可用于读取的 ref.id，模型把它填进了写入指令的实体 ID。

调用顺序：`room_search_data` → `room_manage_catalog` → `room_read_data` → `room_read_data` → `room_search_data`。

**提交的运行指令**

1. `entity.update` `{"id":"c2101f330564e4619cbdd4198914bb765cfb7ac0efdbc282415ba3f810b1894b","numbers":{"pips":6}}`
2. `notification.send` `{"recipientAccountIds":["player1"],"sourceActionIndex":0,"text":"木栗：你收到了 3 枚钱币作为路费，现在共 6 枚。"}`

- 指令 1 预检 `blocked`。NOT_VISIBLE 对象不存在或当前主体无权访问。
- 指令 2 预检 `blocked`。BATCH_DEPENDENCY_FAILED 前项检查失败，当前项未执行。

**实际生效**　该轮前后的配置、两名玩家角色数值与定向通知都没有变化。

本轮使用 6 次官方 API 调用。

### 人工第 3 轮

**KP 原话**

> 就按刚才说好的做法继续，查当前数据，把未完成的部分提交裁决。

**AI 回复原文**

> 已重新核对：木栗（player1 的树桩镇角色）现为 active、owner=player1，当前钱币 pips=3，因此按原方案 3→6。此前那份因对象不可见被挡下的提案仍在待审并受阻，本次是替代它的新候选；请以这份为准。豆叶不改。
> 
> - **数值**：仅把 numbers.pips 更新为 6，其余字段（含背包、生命、属性、位置）保持不变。
> - **通知**：投递给 player1，位于钱币更新之后，只有该更新实际成功才发送。文案：路费已到账，你的钱币增加了 3 枚。

**读取与工具**　重新搜索实体和指令目录。一次带字段的读取再次报错，随后不带字段筛选读取木栗，使用实际 instanceId 核对所属玩家与当前 3 枚钱币。

调用顺序：`room_search_data` → `room_manage_catalog` → `room_read_data` → `room_read_data`。

**提交的运行指令**

1. `entity.update` `{"id":"500c23736bb24a60ac43fc867e2bd68c","numbers":{"pips":6}}`
2. `notification.send` `{"recipientAccountIds":["player1"],"text":"路费已到账，你的钱币增加了 3 枚。","sourceActionIndex":0}`

- 指令 1 预检 `passed`。
- 指令 2 预检 `passed`。

**裁决**　KP 提交批准，业务结果 `completed`。

**实际生效**

- `/notices/player1/1`　新增 路费已到账，你的钱币增加了 3 枚。
- `/players/player1/pips`　3 → 6

本轮使用 4 次官方 API 调用。

## 庭院：追加一句雨景

### 人工第 1 轮

**KP 原话**

> 庭院有点冷清。帮我在现场描述里添一句雨天的气氛，别动玩法。

**AI 回复原文**

> 庭院（地点3）常描述已确认为“庭院中央有池塘，梯子通往树桩上的房屋。 栗婶正清点避雨的居民。”我准备在它的**描述**末尾追加一句雨天气氛描写，不改 exits、features、stock、truth 或任何规则／数值。
> 
> - 拟追加文字：「雨丝顺着树桩屋檐挂成细帘，池面被敲出一圈圈涟漪。」
> - 影响范围：仅该地点 description 文本；入口隧道已提示“暴雨将至”，与既有世界设定一致。
> - 这是活动工件 game.json 的地点描述修改，属高危数据文件，需 A/B/C 三检后由你整包确认指纹发布，我不会自行批准。
> 
> 提交后仍是待审候选，未发布。

**读取与工具**　读取房间信息，检索 courtyard 和 game.json，随后直接读取 game.json 的 locations，定位到编号 3 的庭院并取得原描述。

调用顺序：`room_read_management` → `room_search_data` → `room_search_data` → `pack_read_config_data`。

**提交的配置**　`/data/game.json/locations/2/description`。

- A 类 `pass`。检查 json, full-artifact, host-stage, pack-schemas, host-model, references。无检测提示。
- B 类 `pass`。检查 npc-hp, npc-maxHp, npc-str, npc-dex, npc-wil, npc-strMax, npc-dexMax, npc-wilMax, npc-armor, npc-location, npc-incapacitated, npc-lastRoll。无检测提示。
- C 类 `pass`。检查 npc-morale, npc-player-denied, gameplay-inventory, gameplay-travel。LIVE_GAMEPLAY_REVIEW。

**裁决**　KP 提交批准，业务结果 `blocked`。 宿主发布回执 `SOURCE_STALE`；本次记录未定位到具体变动的来源。

**实际生效**　该轮前后的配置、两名玩家角色数值与定向通知都没有变化。

本轮使用 4 次官方 API 调用。

### 人工第 2 轮

**KP 原话**

> 就是地图上名为庭院的地点。雨声或雨滴都行，你来定稿，提交修改。

**AI 回复原文**

> 已按你的定稿准备「庭院」（地点3）描述追加一句雨景，仅改文本，不动出口、特征、库存、真相或规则。
> 
> - 拟追加：「雨丝顺着树桩屋檐挂成细帘，池面被敲出一圈圈涟漪。」
> - 影响面：仅该地点 description 字符串末尾；index、exits、features、stock、pips、truth 全部保留。
> - 这是 game.json 高危数据修改，提交后仍为待审候选；A/B/C 检查结果与整包指纹需你在详情中确认后才发布。
> 
> 上一条同目标的候选已被阻断，本次以当前活动版本重建基线后重新提交，请以这份为准。

**读取与工具**　重新读取房间信息与活动 locations，再次提议同一句雨景。两次候选的描述文本相同。

调用顺序：`room_read_management` → `pack_read_config_data`。

**提交的配置**　`/data/game.json/locations/2/description`。

- A 类 `pass`。检查 json, full-artifact, host-stage, pack-schemas, host-model, references。无检测提示。
- B 类 `pass`。检查 npc-hp, npc-maxHp, npc-str, npc-dex, npc-wil, npc-strMax, npc-dexMax, npc-wilMax, npc-armor, npc-location, npc-incapacitated, npc-lastRoll。无检测提示。
- C 类 `pass`。检查 npc-morale, npc-player-denied, gameplay-inventory, gameplay-travel。LIVE_GAMEPLAY_REVIEW。

**裁决**　KP 提交批准，业务结果 `completed`。

**实际生效**

- `/data/game.json/locations/2/description`　庭院中央有池塘，梯子通往树桩上的房屋。 栗婶正清点避雨的居民。 → 庭院中央有池塘，梯子通往树桩上的房屋。 栗婶正清点避雨的居民。雨丝顺着树桩屋檐挂成细帘，池面被敲出一圈圈涟漪。

本轮使用 2 次官方 API 调用。

## 测试边界与复跑

房间状态由真实宿主读回，人工审批由脚本提交。测试覆盖配置表、Lua 源、实体模板、两名玩家角色数值与通知的前后差异。水纹盾验证了定义、发放和通知；盾的战斗减伤效果未在本实验触发。

首次搭建时，测试脚本遗漏权限接口的一个必填字段，三个房间均在模型调用前退出。修正后使用三个新房间完成上述样本。

运行[测试入口](verify_ambiguous_live.py)时，需要显式指定 `--live`、一个用例（`shield`、`travel` 或 `courtyard`）和独立的 `--output` 目录。每个用例最多 4 次人工发言、32 次外部调用。测试代理沿用已配置模型的请求设置，隔离配置允许最多 5 次技术纠错，关闭传输重试，单任务超时为 300 秒。
