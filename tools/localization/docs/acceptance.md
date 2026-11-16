# 本地化工具阶段验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-12
- 最后更新：2026-11-12
- 关联文档：[工具入口](../README.md)、[现行架构](architecture.md)、[施工计划](../../../docs/plans/localization-construction-plan.md)

## L10N-0：进行中，3/4 条件通过

| 条件 | 结果与证据 |
| --- | --- |
| E0-1 | 通过：完整 GUI/CLI 复制到仓库外临时目录；清理游戏变量和 PATH；真实窗口与随包 Node CLI 启动通过 |
| E0-2 | **未通过验收**：原生对话框已打开并导航到“中文 空格 project”，最终选择确认未完成；脚本等待 300 秒后超时，不能将导航当作目录回传成功 |
| E0-3 | 通过：8 组英文、中文、引号、花括号、复数和坏模板在真实窗口/独立解析包结果一致；2 组单元测试通过 |
| E0-4 | 通过：类型检查、构建输入边界、精确依赖锁和最小打包通过；真实窗口驱动锁定为 Playwright 1.65.0 |

[机器报告](evidence/l10n-0.json)、[真实窗口结果](evidence/l10n-0-gui.json)、[原生窗口未完成记录](evidence/l10n-0-native.json)、[错误模板截图](evidence/l10n-0-formatter.png)保留当前证据。阶段不是“完成”，L10N-1～6 尚未开始。

## 阻塞与复验

原生对话框的 AX 树可见，但 Computer Use 返回 `element … is not available in cached app state` / `Cannot set a value for an element that is not settable`，截图返回 `window capture timed out`。键盘导航已到目标目录，最终“选择文件夹”未操作成功；用户答复暂时无法操作。该结果反映自动化路径未完成，不证明工具的原生对话框有功能缺陷。测试窗口已由 finally 关闭。

恢复时运行 README 的 native-dialog 命令，选择脚本打印的隔离目录，取得 native-dialog.json 的 passed=true、回传 basename 和未执行脚本断言，再重新生成报告。只有 E0 全部通过后才开始 L10N-1。

仓库内受限执行触发 Electron 的安装目录 ACL 检查。复制到仓库外并正常用户权限启动通过；未使用 --no-sandbox，未变更系统 ACL。首测系统为 Windows 10 19045，不能替代 Windows 11 新环境验收。

## 未验收范围

文件 schema、状态摘要、写锁、事务恢复、正式可视化 CRUD、引用/交换、public/restricted 构建、TextRef fallback、性能、无开发工具的 Windows 11 完整任务均未实施或验收。GUI 截图只证明该次窗口状态，不代替这些阶段。
