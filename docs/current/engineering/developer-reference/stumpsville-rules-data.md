# Stumpsville 规则与数据定义

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-19
- 最后更新：2026-11-19
- 关联文档：[Stumpsville 导航](stumpsville.md)、[Lua 编写](../lua-authoring.md)、[数据管理](stumpsville-data-management.md)

基于本仓库 `rulepacks/stumpsville/`（树桩镇，manifest 版本 `0.9.0`）源码核查。下文路径除链接外均相对该包；KP 为主持，PL 为玩家。只概括当前实现，游戏资料中标注“待终校”的内容仍不是已核实的原版规则。

## 文件与对象

| 定义位置 | 内容 / 定义方法 |
| --- | --- |
| [manifest.json](../../../../rulepacks/stumpsville/manifest.json) | 包ID/版本/入口；`rules` 列 Lua 文件，`data` 列 JSON 文件，`configurations` 指向对象模板。`tools/package.py:bundle()` 按清单装载 |
| [config/configurations.json](../../../../rulepacks/stumpsville/config/configurations.json) | 7类模板：`configurationId` 唯一名、`revision` 修订、`typeRef: "actor"`、`defaults` 数值默认项；安装时逐条 `configuration.put` |
| [config/game.json](../../../../rulepacks/stumpsville/config/game.json) | `items` 物品定义，`locations` 地点/真相/出口/库存/线索，`presets` 建角预设，`npcs` 生物模板，`encounters` 遭遇文字，`rules` 规则速查，`sourceStatus` 核查状态 |
| [config/scene-actions.json](../../../../rulepacks/stumpsville/config/scene-actions.json) | 18项行动：`id/location/label/hint/choices`；每个做法含 `id/label/process`。这些字段定义选项与说明，实际效果在 `rules/scene.lua` |
| [rules/](../../../../rulepacks/stumpsville/rules/) | 21个 Lua 文件，定义校验、骰点、数值效果及返回结果；通过 `action.invoke` 调用公开动作 |

| 模板ID | 对象职责与主要数值 |
| --- | --- |
| `sv.character` | PL角色：`str/dex/wil`及上限、`hp/maxHp/armor`、`pips/xp/level/grit`、位置、审核/准备、失能、光源、物品槽 |
| `sv.draft` | 随机建角骰盘：属性、HP、钱币、生成次数；名称/提交与退回状态在包侧草稿中 |
| `sv.session` | 场次：`phase/round/autoResolve`、`doorA_B`公开通路标记 |
| `sv.world` | KP世界：`generated4/generated7/pots/rats`，记录一次性生成结果 |
| `sv.scene` | KP场景状态：机关/门/人物状态、发现标记、剩余钱币和有限库存 |
| `sv.location` | 地点实体：`index`；描述、真相、出口等正文放包侧地点资料 |
| `sv.npc` | KP生物：属性/上限、HP/护甲、失能、位置、最近骰点；初始化只创建 `verified:true` 的预置NPC |

物品按 `game.items` 的**1起始数组编号**存入 `itemN`，对应 `usesN/ticksN`；不是直接存物品字符串ID。`sv.layout` 计算多格占位、钱币占槽、护甲和超载。角色经 `source` 关系指向场次，场次以 `references` 指回角色。

模板最小实例（取自现有地点定义；放入模板数组中）：

```json
{"configurationId":"sv.location","revision":"1","typeRef":"actor","defaults":{"index":1}}
```

## 规则清单

| 规则ID（统一 `sv.` 前缀） | 职责 / 调用限制 |
| --- | --- |
| `create`、`profile`、`ready` | 随机建角、写入审核属性、准备；`profile`限KP |
| `layout`、`automation` | 计算物品布局；检查场次及自动裁决开关；均为非公开计算规则 |
| `check`、`check.core` | 自动裁决检查后执行d20属性检定；核心非公开，优势取低/劣势取高，超载等可强制劣势 |
| `inventory`、`inventory.core` | 移动、消耗、点亮/熄灭；核心非公开，包装规则先检查自动裁决 |
| `grant`、`remove`、`transfer` | 授予、移除、跨角色转交物品；限KP |
| `damage`、`rest`、`morale` | 护甲/HP/溢出伤害及重伤、休息恢复、士气；限KP |
| `world`、`generate` | 开场/推进/结束、光源耗用；器具/鼠帮一次性数量及遭遇/反应/战利品骰；限KP |
| `travel`、`travel.auto` | KP移动；自动移动额外校验已发布地点、相邻通路与自动裁决 |
| `adjudicate`、`scene.resolve` | KP执行检定/物品裁决；按行动ID和做法结算场景、库存、伤害、揭示及耗时；限KP |

现有规则的最小组合示例（[check.lua](../../../../rulepacks/stumpsville/rules/check.lua)）：

```lua
return rule('sv.check', {'actor', 'attribute:text', 'mode:text'}, function(r, actor, attribute, mode)
  r.call('sv.automation', actor)
  return r.call('sv.check.core', actor, attribute, mode)
end, {dependencies={'sv.automation', 'sv.check.core'}})
```

`rule(ID, 参数, 函数, 选项)` 定义规则；`r.number/read`读状态、`r.readData('game.json')`读随规则装载的资料、`r.roll`投骰、`r.set`写数值、`r.call`复用规则。选项用 `kp=true`限制KP、`public=false`禁止直接公开调用、`mode='calculation'`声明计算、`dependencies`列依赖；完整约定见[Lua 编写](../lua-authoring.md)。

## 修改入口

1. **对象/静态资料**：按现有模板补 `configurationId/revision/typeRef/defaults`；在 `game.json` 定义物品、地点、NPC等，保持编号引用一致。现有物品与地点编号保持稳定，允许尾部追加；删除或重排既有编号需迁移方案。AI 修改走高危裁决，并验证当前实例的背包结构。
2. **场景行动**：在 `scene-actions.json` 定义按钮和做法；在 `scene.lua` 实现同名 `action/choice` 分支及结构化结果。新增状态同时维护 `configurations.json` 的 `sv.scene` 和 [tools/scenes.py](../../../../rulepacks/stumpsville/tools/scenes.py) 的默认值/库存映射；按需补个人知识投影和错误说明。
3. **装配与调用**：新 Lua/数据文件加入 manifest，声明依赖；通过包侧 `Job.invoke` 接宿主规则。前端调用 `package/action`，输入 `{id, operation, args}`；新增界面操作还需在 `Package.execute` 中定义权限、校验和处理，不能只加按钮。
4. **发布与核对**：资料库导入 `sources/data` → 检查暂存 → 预览 → 激活。该路径不等于更新对象模板或迁移既有实例；模板安装另走 `configuration.put`。用独立存档核对权限、成功/失败、重复请求和重启恢复，不直接改运行存档模拟效果。

包侧编排：`session.start`统一初始化/个人资料订阅/恢复/开场；`resolve`的可选`resolution`允许KP为自由/互动/复核申请执行检定、伤害、休息或授予物品，目标固定为申请者角色。两者复用原命令回执恢复，不在前端直接改数值。
