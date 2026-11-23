# AI 聊天滚动与输入交互验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-23
- 最后更新：2026-11-23
- 关联文档：[嵌入指南](../../../docs/current/engineering/ai-pack-embedding.md)、[工程清单](../../../docs/current/engineering/hierarchy.md)

本轮修复通用聊天组件的更新滚动策略、消息节点重建和输入生命周期。包侧另外修复页面刷新时卸下再插回 AI 容器、PL 弹窗被底层页面刷新销毁的问题；两侧组合验收与下列工程用例分开计数。没有改变权限、审批或模型调用逻辑，没有调用外部模型 API。

## 当前行为

- 内容更新时，最近 1 秒没有键盘、输入、滚轮、指针或触屏操作则跟随最新；有操作时保留可见消息的位置。持续按住、拖动、触摸和中文组字不受 1 秒超时打断。规则在更新时判断，不在空闲满 1 秒时主动跳转。
- “回到最新”和主动切换会话定位最新。异步引用回填在实际改变标签前后保存、恢复当前阅读锚点；过期、暂停或其他会话的解析结果不能改变当前滚动。
- 变更消息在原位置更新；保留未变化的正文和输入节点。上方消息变高不再挤走当前阅读位置，进度变化不清空未变化正文的选区。
- 普通键入不重建文本节点、重设选区或反复设置 contentEditable；中文组字期间推迟输入框引用标签回填。退出、权限变化、归档及他人会话的限制仍有效。
- 等待新会话加载期间继续键入的内容保存在原会话草稿中；旧读取和提交回包不覆盖另一会话草稿。

## 实验与成功率

Windows 本机真实 Edge 158.0.4370.33、Playwright 无头浏览器；24 轮长会话，三种嵌入形式。宿主夹具使用隔离目录和模拟模型提供方。

| 实验 | 结果 | 解释与证据 |
| --- | --- | --- |
| 修复前同组基线 | 3/12，25% | [baseline.xml](baseline.xml)：3 种空闲跟随、5 种操作结束后的跟随及正文节点/选区保留失败 |
| 修复后专项与既有聊天/引用 | 25/25，100% | [targeted.xml](targeted.xml)：16 项新交互用例、9 项既有用例；约 136 秒 |
| 相关 UI 首轮 | 33/36，91.7% | [related-ui.xml](related-ui.xml)：3 项旧测试准备/断言问题，见下表；约 187 秒 |
| 失败场景和同组 KP 页面复测 | 4/4，100% | [related-ui-recheck.xml](related-ui-recheck.xml)：约 40 秒 |
| 本轮修复后去重结果 | 61/61，100% | 最终结果按 classname/name 合并，复测替代对应首次失败；不把重复运行累加为新增用例 |
| 包侧组合联验 | 包侧报告 8/8 | [组合结果](../../../rulepacks/stumpsville/tests/player-layout-results.json)、[驱动](../../../rulepacks/stumpsville/tests/verify_player_layout.py)：KP/PL、弹窗、原生 IME、选区、桌面及手机宽度；正常 `/ai-ui/` 入口逐字节确认 3 个组件资源，与工程 61 项分开 |

专项涵盖真实鼠标滚轮、按住鼠标后在组件外释放、CDP 原生触屏事件和中文组字提交、周期轮询期间持续键入、异步引用回包、上方内容增高、回答选区、旧读取回包及加载期间补写草稿。事件类型矩阵另使用 DOM 事件精确检查 1 秒窗口。[截图](long-history-editor.png)为组字提交后继续输入且历史仍停在阅读位置的实际页面。

| 失败 | 核实与处理 | 复验 |
| --- | --- | --- |
| 长会话空闲更新不跟随 | 原逻辑仅按距底部 80px 判断；改为用户活动时间及持续手势状态 | 三种视图及五类事件通过 |
| 进度更新丢失正文节点/选区 | 原逻辑先卸下旧行再插入，正文也暂时移出 DOM；改为原位协调节点并保存可见消息锚点 | 正文、选区、上方增高用例通过 |
| 批次权限 UI 等待“已执行” | 当前运行时成功文案已是“指令已提交”；真实回执 committed、提交 1 项。更新旧断言，同时检查提交/撤销/失败/未执行数量 | 权限、归档恢复、删除和手机布局完整用例通过 |
| 两个 PL 嵌入等待 EXTERNAL_SCOPE_DISABLED，实际 AI_DISABLED | 测试漏开更早的服务总开关。显式开启服务、保持全部外发关闭，继续断言正确的外发拒绝和不提供转交按钮 | 两种 PL 嵌入通过，KP 同组亦通过 |

最后三项只调整测试，已交付的产品冻结 v1 未变。首次失败 XML 保留；[verification.json](verification.json)列出每轮失败 ID、计数和源码核对结果。开发测试时发现的脚本字符串转义、合成事件未穿过 Shadow DOM 问题已修正，不计入产品成功率。

## 冻结与复核

包侧使用 [v1/source.json](../ai-chat-ui-interface-snapshot/v1/source.json)列出的项目相对路径覆盖现有工程，共 3 个文件：chat.js、chat.css、reference-editor.js。无需新增公开接口或静态分发文件。

source.json SHA256：`260872b2fb0e2c606c5f61450bbe3c959463cb9a847a92d89155d0199b703eec`。

[source.json](source.json)记录本次产品及测试文件摘要；[files-manifest.json](files-manifest.json)记录验收产物摘要。从项目根目录执行：

```powershell
engineering/.venv/Scripts/python.exe -X utf8 -B engineering/acceptance/ai-chat-interaction/verify.py
engineering/.venv/Scripts/python.exe -X utf8 -B -m pytest engineering/ai/tests/test_chat_interaction.py engineering/ai/tests/test_chat_polish.py engineering/ai/tests/test_reference_ui.py -q
```

相关 UI 回归为 tests 下的 test_access_ui、test_answers_ui、test_debug_dialog_ui、test_embeds、test_progress_ui、test_reference_details_ui、test_reference_renderer_ui、test_session_ui、test_style_stability、test_message_history_ui、test_player_requests_ui、test_review_followup_ui。无 Python 服务逻辑改动，本轮没有重跑上一轮 800 项核心回归，也没有 Git 发布。

## 范围限制

成功率针对上述确定性 UI 场景，不代表模型任务成功率或全部终端表现。原生组字和触屏通过 Edge CDP 驱动，未人工操作 Windows 输入法候选窗，也未在实体手机、Safari 或 Firefox 上验收。页面重载、退出和销毁后的草稿仍不持久化。包侧整页挂载修复应与本组件差量一并构建后使用；已有导出网页不会自动更新。
