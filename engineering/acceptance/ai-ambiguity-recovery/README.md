# 模糊需求的技术纠错与执行恢复验收

本轮对应 ISSUE-025，使用冻结后端和合成房间执行确定性回归；AI 工程侧外部 API 调用为 0。包侧同组真实 DeepSeek 实验独立记录，不能用下列通过数替代模型语义成功率。

## 交付内容

- 只兼容单个合法 plan/clarification 的错误工具外壳；未知工具、批次和发布命令仍拒绝。
- 错误 fields 在相同授权 refs 上重读；不透明实体引用仅凭本轮真实 host-state 详情解析，不猜名称或 ID。与格式、预检、配置纠错共用最多两次额度。
- 字符串 append、普通数组 append_value；父数组末尾追加和旧元素独立字段可共存，真重叠及唯一键冲突仍拒绝。分页给出实际零基路径及原记录 id/index/name。
- 执行账本关联原请求、实际动作、回执状态和新候选修改前数字；只在原来源仍可授权查看且外发允许时提供详情，并沿历史证明链复验。最多 8 项、详情共 24 KiB；修改前数字最多 8 KiB，旧记录不猜补。
- 已识别的简短继续表达，对最近同会话意图已完成、待批或结果不明动作的相同写目标进行防重复反馈；明确新增加的需求不被旧动作永久去重。普通发放是增量，已有库存不能冒充本次发放凭证。金额支付或收取的重大未决方向由模型澄清。
- DATA_REFERENCE_CONFLICT 可在同一提案上修订并重新执行完整 A/B/C；自环反馈指明真实 JSON 下标。持续失败仍保留报告且禁止发布。权限、作者政策及 C 接受边界未放宽。
- 修复空闲 reconcile 与关闭同时发生时丢失唤醒、关闭持续等待的竞态。

## 测试记录

| 运行 | 结果 | 解释 |
| --- | --- | --- |
| engine-stale-reproduction | 0/1 | 初始夹具先触发作者规则限制，未到发布；随后改用合法源码注释增量 |
| engine-stale-confirmed | 1/1 | 小夹具精确路径未命中，不能证明自失效已修复；随后加非空查询断言 |
| engine-self-stale | 0/1 | 有效 artifacts 查询，approve 成功，apply SOURCE_STALE；确认引擎问题 |
| repairs-first | 中断，不计通过率 | 澄清已保存 needs_input，关闭竞态使测试不能结束；原存档摘要与原因见 interrupted JSON |
| repairs-second | 49/50 | AI 专项49通过；旧引擎自失效仍失败，未绕过 |
| edit-publication | 3/3 | 保密字符串、双向地图、重复库存均通过实际三检、人工高危批准和活动工件核对 |
| combined-targeted | 82/83 | 自失效修复通过；外部竞争正确被更早 BASELINE_STALE 拦截，原断言只接受 SOURCE_STALE，修正断言而未改产品 |
| full-regression（v1） | 793/794 | 错 fields 已在本地修正，真实线路少一次模型工具往返；旧诊断断言未同步，更新断言并要求存在 QUERY_FIELDS_REPAIRED |
| v2-targeted | 103/103 | 防重放、新增需求、原数值、权限撤销、引用错误修正与耗尽拒绝通过 |
| v2-full-regression | 800/800，100% | 最终51个非浏览器测试文件，525.706秒；0失败／错误／跳过；67个运行源码与冻结组合完全一致 |

各行保留同名 XML 和 source.json；失败与中断没有被后续结果覆盖。重复测试不能相加为独立覆盖。最终全量结果见 [XML](v2-full-regression.xml) 和 [机器摘要](verification.json)，本轮源码、文档和证据逐文件摘要见 [清单](files-manifest.json)。

实际外部竞争用例在 approve 与 apply 之间更改已查询实体：apply 拒绝，活动工件未改变。无外部变化时两步均 committed。引擎差量与独立边界验收见 [ISSUE-025 引擎记录](../engine-issue-025/README.md)。

## 冻结与复现

基础 AI 为 [ai-staged-interface-snapshot/v2](../ai-staged-interface-snapshot/v2/source.json)。本轮差量只包含变化文件，按 engineering 相对路径覆盖；source.json 含 base、baseFilesDigest、files、fileCount、removedFiles 和 filesDigest。

| 差量 | 文件数 | filesDigest |
| --- | --- | --- |
| [v1](../ai-ambiguity-interface-snapshot/v1/source.json) | 5 | ab94d058c0aadd809c2b45411ba496dce77d487a6d7db4eaae792f9ece2d6bef |
| [v2](../ai-ambiguity-interface-snapshot/v2/source.json) | 10 | 47473304a9f95e6309633cac61a53b5fdc8f1d16e1d56f9334fca22a455419d0 |

v2 直接覆盖基础 AI，无须先叠 v1。引擎顺序为 engine-performance-interface-snapshot/v2、rule-stage-delta/interface-v1、engine-issue-025/interface-v1。最后一项只有 data_queries.py，SHA-256 为 4c2f9955a6cb343c08405dbcf46e708625b45093a9c75a201a0278d7405c584a。

项目根目录运行（驱动会复制依赖，输出只落在本目录 work 中）：

```powershell
engineering/.venv/Scripts/python.exe -X utf8 -B engineering/acceptance/ai-ambiguity-recovery/run_tests.py --label rerun --engine engineering/acceptance/engine-performance-interface-snapshot/v2 --engine-overlay engineering/acceptance/rule-stage-delta/interface-v1 --engine-overlay engineering/acceptance/engine-issue-025/interface-v1 --core
```

默认测试当前 AI；可用 --ai-source 指定已装配的冻结完整树。--core 排除浏览器用例，本轮未修改 UI，未重跑浏览器专项。FastAPI/httpx 的现有弃用警告不影响结果。

## 范围与局限

自然语言目标匹配、金额方向与候选语义核对仍依赖模型；没有宣称能自动证明任意文字的正确性。防重放针对已识别的继续表达、最近同会话意图与可授权读取的实际动作，不按对象同名或文本相似建立业务关联，不阻止明确的新一笔交易。历史详情因撤权隐藏时不恢复原数据，也不伪造成功；未知回执不能重放。

原始失败均保留：技术错误先在共用额度内修复；持续错误显示稳定错误码和原检查报告；涉及用户真实决策时一次澄清；未知执行结果查原回执；成功或部分成功不得整体重做。实际发放、发布和通知必须分别核对宿主状态及回执。

2026-11-23 包侧 v2 全组复测回报：发绳索与双向地图各一次发言达成；饭钱在第二次明确扣款后达成；同会话“继续”新增扣款／通知均为 0，明确新开销后各为 1。包侧同时保留小盾误选成武器、仅添一句却重写旧文、独立 calculation 的 B.EXTENSION_RULE_INTERFACE／误增配置、饭钱首轮 MODEL_OUTPUT_INVALID 等失败，并在包作者指南作语义和范围的定向优化。这是独立真实模型实验的阶段回报，不是本目录确定性用例，也不能据此将整组语义正确率写成 100%。
