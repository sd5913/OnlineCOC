# 树桩镇公开行动执行矩阵

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-20
- 最后更新：2026-11-20
- 关联文档：[案例及判定器](cases.json)、[展开前置状态](prestates.json)、[生成输入上下文](contexts.json)、[实际行动目录](catalog.json)、[验收结果与新增路径](results.json)、[原子批次接口](../../../docs/current/engineering/atomic-batches.md)

## 1. 已验证范围

当前包真实 Lua 目录中的 17 个公开 actionId 各有一个合法执行正例，集合自动核对相等。第一轮 24 个唯一案例全部符合预期，没有跳过或失败。分类分别为 17 个合法正例、2 个正常玩法失败、1 个业务阻塞、4 个技术拒绝；后面三类不算成“达成目标”。

使用真实 Host、FileDataStore 和独立 Lua 工作进程，通过 `Host.execute_batch` 提交单项 `action.invoke`。只有测试夹具的随机源使用预先列明的骰序列，仍经过真实宿主持久随机日志；没有替换规则或模型返回。每例独立初始化房间，核对预检不写状态、真实回执、完整实体变化、其他集合不变，再以相同 commandId 重放一次，确认不再次修改状态或抽取随机数。

没有调用模型 API，因此这些结果不是模型成功率。没有读取 AI 施工代码/配置，没有使用包 tools/tests，没有修改生产 backend、契约、Lua 或 config；前后文件 SHA256 一致。所有身份、角色、存档和素材均为本目录合成夹具；不接入正式房间。

## 2. 17 个合法执行样例

| actionId | 主体 | 最小游戏条件与实际 oracle |
| --- | --- | --- |
| `sv.create` | player1 | 自己的 `sv.draft`；11 次合成 d6 后三属性为7、HP4、pips2、generation加1 |
| `sv.profile` | KP | 尚未批准的 `sv.character`；按指定初始数值更新属性/上限/资源并批准 |
| `sv.ready` | player1 | 自己的已批准角色；ready从0变1 |
| `sv.check` | player1 | 已批准/准备/可行动、关联开始的会话；d20=5通过STR10，记录checks和lastRoll |
| `sv.inventory` | player1 | 角色关联自动结算会话，第5槽为定义3口粮；uses5从3变2 |
| `sv.grant` | KP | 第5槽为空；授予定义3口粮，item5=3、uses5=3 |
| `sv.remove` | KP | 第5槽为点燃的火把；清空物品/用量/计时及litSlot |
| `sv.transfer` | KP | 两个不同角色，来源第5槽有口粮、目标第6槽空；物品/用量/计时完整转移 |
| `sv.damage` | KP | 无护甲且HP4的角色；2点伤害使HP变2，无溢出 |
| `sv.rest` | KP | 活着但失能、HP1/maxHP4；短休d6=2恢复至4并解除失能 |
| `sv.morale` | KP | `sv.npc` 的WIL10；d20=7通过，记录lastRoll |
| `sv.travel` | KP | 已批准角色与存在的地点编号2；location变2 |
| `sv.travel.auto` | player1 | 已批准/准备、开始的会话、门1–2开放；移动到公开地点对象index2 |
| `sv.world` | KP | `sv.session`；start使phase从0变1 |
| `sv.generate` | KP | 尚未生成锅具的 `sv.world`；d6=4，pots=4、generated4=1 |
| `sv.adjudicate` | KP | 自动结算关闭但会话已开始；KP按全部必填字段裁定DEX检定，d20=6通过 |
| `sv.scene.resolve` | KP | 入口角色/会话/场景/世界实体齐备；观察地面使trapKnown=1，返回业务success和发现地点2 |

“最小”指规则所需游戏实体子图：仅创建案例列出的实体、关系及配置；Host仍保留格式要求的普通房间集合和合成账号。配置默认值从当前包展开，不省略规则会访问的空槽、属性等数值字段。样例中的 actor/session 等是夹具ID，不能当正式房间ID；版本和目录修订由实际加载的配置/规则产生。

## 3. 必要边界

- 普通检定 d20=20 未过STR10：事务 committed，passed=false，checks和骰值保留；同ID不重掷。
- 已知机关的解除检定失败：事务 committed，`public.outcome=failure`，实际伤害、机关触发状态、轮次保留；奶酪未取得。
- 未发现机关连接却谨慎取奶酪：事务 committed，`public.outcome=blocked`，目标未达成、无骰子或实体改动；不能据回执已提交自动归档需求。
- 将物品定义编号3错用为slot3：该槽实际是奶酪，口粮在槽5；技术拒绝 `SV_ITEM_NO_USES_OR_MANUAL_SPELL`，不扣用量。
- 玩家调用KP专用grant、slot为字符串、相邻门未开放：分别按权限、Schema、规则前置条件拒绝，无业务残留。

仅覆盖各 actionId 的一个正例和上述边界，不声称穷尽 18 项场景配置的所有 choice，也不替代 HTTP/浏览器接线验收或模型生成实验。

## 4. 机器文件与复验

`cases.json` 包含自然语言意图、主体、最小 stateSpec、精确 actions/args、合成骰序列和 oracle。配置公共默认值在同一文件中；`prestates.json` 展开每例真正用于执行的实体/关系/配置。`contexts.json` 提供独立的合成输入资料和“槽位—定义编号—剩余用量”对照，不包含预期 args、oracle 或骰序列，可用于后续 AI 上下文补证。使用它不代表本专项测过模型生成。

`catalog.json` 保存宿主实际生成的公开目录、参数 Schema、KP标志、规则修订与源文件摘要。`runs/run-001.json` 保留首轮逐项预检、真实回执、骰序列、状态及耗时；`results.json` 汇总分类、唯一计数、文件摘要和供目录维护者合并的 newFiles。

项目根目录 PowerShell，先完成路径登记：

```powershell
engineering/.venv/Scripts/python.exe -B -X utf8 engineering/acceptance/stumpsville-action-matrix/build_cases.py
engineering/.venv/Scripts/python.exe -B -X utf8 engineering/acceptance/stumpsville-action-matrix/run_matrix.py
engineering/.venv/Scripts/python.exe -B -X utf8 engineering/acceptance/stumpsville-action-matrix/finalize.py
```

每次执行保存独立的 `runs/run-NNN.json` 和忽略的 `work-tmp/run-NNN/` 存储，不覆盖旧运行证据。禁止把 work 路径改成正式房间。当前未修改任何生产功能或接口，所以没有新增生产能力声明。
