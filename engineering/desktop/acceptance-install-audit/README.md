# 根目录安装器与基础操作台验收

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-26
- 最后更新：2026-11-26
- 关联文档：[桌面工具](../../../docs/current/engineering/desktop-tools.md)、[源码入口](../README.md)

本报告记录移至 `QuickStart/` 之前的根目录布局及其构建摘要。现行入口与迁移复测见[桌面工具](../../../docs/current/engineering/desktop-tools.md)。

## 结果

根目录两个 exe 和 `DesktopTools.cs` 的摘要均匹配既有 `build-info.json`，本轮没有重编译 exe。它们是 Windows x64 / WinForms 工具，启动 `desktop_host.py`，监听回环地址并提供 `engineering/test-console/`。默认 AI capability 的 `available` 和 `enabled` 都是 false。

| 验证 | 实测结果与证据 |
| --- | --- |
| 全新离线安装、重复检查、锁升级、损坏修复、运行与恢复、错误边界 | [8/8 JUnit](desktop-tests-short-path.xml)，138.48 秒；依赖计数 29 |
| 默认在线来源，无 ZIP 缓存 | [安装日志](online-install.log)与[机器结果](online-browser.json)，72.99 秒成功，子进程 PATH 不含系统 Python |
| 完整 Python/Tk 模块 | Python 3.14.2 x64；tkinter/_tkinter 导入成功，Tcl 8.6.15；未验证 Tk 图形窗口 |
| 首次未提供密码 | 启动器拒绝；要求至少 8 位初始密码 |
| 网页与账号 | Edge 158，kp/player1/player2 三个独立上下文；均登录并连接 WebSocket，只有 KP 显示管理区 |
| Lua 行动与恢复 | player1 在页面执行 demo.damage，HP 9→4，KP 同步；正常停止后重新启动仍为 4；页面脚本错误 0 |
| 原生发行签名 | 两个 exe 的 Authenticode 状态均为 NotSigned |

[KP 截图](console-kp.png)与[玩家截图](console-player.png)已目视检查。测试在 Windows 10 x64 19045 上进行；主机已有 .NET、Edge 和开发工具，不是裸系统虚拟机。安装器无头执行，因此不声称验收原生窗口、密码弹窗、系统拦截提示或默认浏览器自动打开。未测试 Linux/macOS/ARM64 原生运行，也未在本任务测试 AI 或树桩镇入口。

## 首轮失败与修正

[首轮 XML](desktop-tests.xml)有 8 项夹具错误：原测试临时路径加上 Python 的解压暂存后缀和最长 ZIP 条目达到 269 字符，触及 .NET 路径限制。同一副本的默认安装路径最长为 225 字符。测试随机目录后缀从 32 缩为 12 位；同时把旧的 `DEPENDENCIES_OK 26` 断言改为读取 lock 计数。没有修改安装器代码、权限或摘要校验。

网页首轮因开发机没有 Playwright 自带 Chromium 而中断，随后使用已安装的 Edge。第二轮字符串 `wait_for_function` 被页面 CSP 拦截，改为 DOM 定位等待后通过；没有放宽 CSP。在线安装结果保留，网页重试使用 `--browser-only`，没有把重复安装时间冒充首次安装时间。

## 重现与目录交接

`prepare.py` 将已登记输入复制到 `%TEMP%/oc-install-c4b4-1126/`，并校验构建摘要；`source.json` 保存初轮文件摘要，`source-short-path.json` 保存测试临时目录修正后的实际副本摘要。为防覆盖，准备脚本在目标已存在时拒绝运行，重跑应先选定新的已登记临时目录。

在隔离工程中，用已有开发 Python 执行 `-m pytest engineering/desktop/tests/test_desktop.py -q`。然后在项目根执行 `engineering/.venv/Scripts/python.exe engineering/desktop/acceptance-install-audit/verify_online.py`，测试默认在线安装和页面。浏览器阶段使用已有 Edge，失败后可用 `--browser-only` 重试；完整重现应使用新副本。两个 exe 的安装/启动进程均只访问隔离副本，未打开正式 `.runtime/demo`。

根 README、英文 README、PROCESS 与 hierarchy 正文由课程交付协调者维护。本目录新增文件清单见 `index-paths.json`，用于其目录同步；本会话仅修改桌面工具已有说明、两处过期测试和本目录证据。

## 可供 README 采用的中文步骤

Windows 10/11 x64 用户应将完整项目解压到较短的可写目录。先运行根目录 `安装依赖.exe`，联网等待官方 Python 3.14.2 与锁定依赖安装完成，再运行 `启动OnlineCOC.exe`。首次设置至少 8 位密码，在 `http://127.0.0.1:8765` 使用 `kp`、`player1` 或 `player2` 和该密码登录。不同账号使用隔离浏览器会话；游玩时保持启动窗口运行，结束时关闭启动窗口以保存并停止服务。

此入口是本机引擎测试操作台，不是树桩镇或 AI 入口。环境装在 `.runtime/environments`，不会生成 `.venv`；其他入口须使用各自安装步骤。房间保存于 `engineering/.runtime/demo`，再次打开同一目录会恢复。exe 不能脱离完整工程单独使用；网络、端口占用、深路径和未签名发行物是首次启动应说明的限制。

## English text for README

On Windows 10/11 x64, extract the complete project into a short, writable local path. Run `安装依赖.exe` in the project root and wait for Python 3.14.2 and the locked dependencies to be installed. Internet access to python.org and PyPI is required for the default installation; a system Python installation is not required. Then run `启动OnlineCOC.exe`, set an initial password of at least eight characters, and open `http://127.0.0.1:8765`. Sign in as `kp`, `player1`, or `player2` using that password. Use separate browser profiles for simultaneous accounts. Keep the launcher window open while playing; close it to stop the service. Reopening the same data directory restores the room.

This starts the local engine test console, not Stumpsville, the room manager, or the AI runtime. The root installer creates an environment under `engineering/.runtime/environments`, not `engineering/.venv`; other entry points require their own setup. Keep the executables with the complete project. The default room is stored in `engineering/.runtime/demo`. The tested platform is Windows 10 x64 with .NET and Edge already installed; native launcher dialogs, SmartScreen, other operating systems and ARM64 were not tested. The executables are unsigned, and deep paths can hit the .NET path-length limit.

## 可核实的协作案例

建议采用 [ISSUE-025 验收](../../acceptance/engine-issue-025/README.md)：任务要求保留来源失效和权限边界。AI 侧复现“读取工件→A/B/C通过→KP风险采纳并批准→发布却 SOURCE_STALE”，引擎侧将原因定位为批准自身暂存候选改变了稳定查询集合。实现选择只投影活动及在途工件，保留完整历史入口；没有跳过 stale 校验。该目录保留修复前失败、修复后 104 项引擎及 29 项 AI 查询测试证据，并提供单文件冻结差量供其他协作者联验。这里可核实的是任务约束、工程取舍和合成验收中的 KP 决策，不应据此编造一次真实玩家访谈或直接引述用户原话。
