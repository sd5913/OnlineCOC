# 独立本地化工具 Localizer

本目录是独立开发工具工程，自有依赖、构建与测试，不导入 OnlineCOC 核心或任何配置包。默认设计为英文 en → 中文 zh-CN，文件为协作源。

当前为 **L10N-0 技术预览，阶段验收尚未全部通过**：已有桌面窗口、原生目录选择入口、CLI 帮助、共享 ICU 格式化和最小独立打包。尚无词条文件模型、事务保存、可视化 CRUD 或资源发布能力；不要用于正式作者数据。详见[验收记录](docs/acceptance.md)与[施工计划](../../docs/plans/localization-construction-plan.md)。

## 开发与检查

开发机使用 Node 24.22.1、npm 12.2.2；精确版本在 package.json/package-lock.json 中。进入本目录后运行：

```powershell
npm ci --ignore-scripts
powershell -NoProfile -File scripts/prepare-runtime.ps1
npm run build
npm run check
npm test
npm run package
```

prepare-runtime 从 Electron 官方发行和 Node 官方站点取得锁定运行时，校验 Node 压缩包摘要；缓存仅写本目录 .cache。安装依赖需要网络，打包后使用无需网络、npm 或系统 Node。esbuild 使用锁定的 Windows 可选二进制包，无需启用其他项目的安装脚本。

本机曾无 npm，开发期间将 npm 12.2.2 下载到 .cache/package；该临时缓存不入库，也不是发行用户依赖。

## 运行技术预览

构建后的命令入口：

```powershell
node build/cli/main.cjs --help
node node_modules/electron/cli.js build/desktop/main.cjs --settings-dir .test-output/manual-settings
```

打包目录为 dist/localizer-0.1.0-win32-x64，GUI 位于 gui/Localizer.exe，CLI 位于 cli/l10n.cmd；必须保留各自完整目录。CLI 目前只支持 --help / --version，其他命令明确返回退出码 2。独立浏览器文件 runtime/localizer.mjs / localizer.js 当前只导出 formatMessage，并未实现 TextRef/fallback 解析。

本机受限执行环境在仓库内触发 Electron 的目录 ACL 检查；复制完整发行目录到普通用户临时目录并以正常用户权限运行通过。未关闭应用 sandbox、未修改系统 ACL。Windows 11 目标环境还未验收。

## 复验

```powershell
node tests/gui/smoke.mjs 'C:\test\localizer-0.1.0-win32-x64'
node tests/gui/native-dialog.mjs 'C:\test\localizer-0.1.0-win32-x64'
node scripts/report-l10n-0.mjs
```

smoke 驱动真实 Electron 窗口，检查隔离桥接、CLI 和 ICU 样本。native-dialog 打开原生目录选择，需在窗口确认打印出的测试目录，随后检查回传结果与脚本未执行；超时记录为失败。测试数据限于 .test-output，不应选择真实作者项目。开发自动化会开启临时调试端口，正常应用不启动调试端口。

## 文件入口

- [实际结构与模块边界](docs/architecture.md)
- [阶段验收与阻塞](docs/acceptance.md)
- [工程设计](../../docs/plans/localization-engineering-design.md)
- [施工计划](../../docs/plans/localization-construction-plan.md)

node_modules、.cache、build、dist、.test-output 为忽略的生成目录；精选证据位于 docs/evidence。第三方许可随发行物位于 licenses、gui/LICENSE* 和 cli/runtime/LICENSE；本阶段未为项目原创代码另行指定开源许可证。
