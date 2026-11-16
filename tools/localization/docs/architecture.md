# 独立本地化工具现行架构

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-12
- 最后更新：2026-11-12
- 关联文档：[工具入口](../README.md)、[验收记录](acceptance.md)、[工程设计](../../../docs/plans/localization-engineering-design.md)

当前实现只覆盖 L10N-0 骨架，后续文件模型、事务、CRUD、交换和资源发布仍待实施。

## 实际模块

| 目录 | 已有能力 |
| --- | --- |
| packages/contracts/src | 工具版本、限额、参数/诊断/格式化结果类型 |
| packages/messages/src | ICU MF1 命名参数、select、基数 plural 的检查与格式化；失败返回诊断 |
| packages/core/src | 当前仅导出版本及限额；尚无文件读写 |
| packages/cli/src | --help、--version；未知命令退出 2 |
| packages/desktop/src/main | Electron 窗口、原生目录对话框、projectHandle；不读取项目脚本 |
| packages/desktop/src/preload | 只暴露 chooseProject，无通用 IPC/fs/shell |
| packages/desktop/src/renderer | React 技术预览、语言/count/模板输入、错误展示 |
| packages/runtime/src | 共享 formatMessage 的独立 ESM/IIFE 试验入口 |
| scripts | 构建、边界检查、运行时下载、打包和 L10N-0 证据收集 |
| tests/unit、tests/gui | 消息行为、打包后的窗口、原生目录选择验收驱动 |

构建输入检查禁止模块外生产源码，runtime 禁止 core/desktop/CLI 依赖；浏览器包必须无外部导入。GUI 开启 sandbox/contextIsolation、关闭 nodeIntegration，拒绝外部导航/新窗口、渲染器网络请求和权限请求。IPC 校验发送窗口与主 frame；渲染器只得到随机 handle 和目录 basename。

## 冻结的技术版本

Node 24.22.1；npm 12.2.2；Electron 45.3.1；TypeScript 7.0.2；React/ReactDOM 19.3.1；Vite 8.3.8；esbuild 0.28.2；Playwright 1.65.0；intl-messageformat 12.1.5；@formatjs/icu-messageformat-parser 3.5.23；Ajv 8.20.0 已锁定但尚未接入 schema。所有传递依赖以 package-lock.json 为准。

2026-11-12 技术试验决定直接调用 intl-messageformat，并以共享外层返回 FormatResult，不再增加 i18next/i18next-icu 中间包装。GUI 与独立浏览器包共用同一实现，8 组真实窗口样本已验证一致。

GUI 打包复制 Electron 完整 Windows x64 运行目录；CLI 携带官方 Node 及许可证。发行根目录 release.json 列出其余全部文件的大小和 SHA-256，dependencies.json/许可证目录记录安装到本机的依赖。当前开发预览约 447.5 MiB，不是最终体积验收结果。

## 数据与设置边界

目前选择目录只返回 handle，不加载项目、不运行 npm/Lua/JavaScript。用户设置独立放在 IndependentLocalizer；测试传 --settings-dir 使用模块的 .test-output。工具不启动游戏后端或读取游戏配置。

首轮实际运行环境是 Windows 10 Home China 19045 x64，正式设计目标 Windows 11 x64 尚未验证。Electron 内置 Node 与独立 CLI Node 版本均记录在[机器证据](evidence/l10n-0.json)。原生对话框最终确认未完成，不能据此宣称全部路径验收已通过。
