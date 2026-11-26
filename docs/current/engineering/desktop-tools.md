# Windows 依赖安装与一键启动

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-10-30
- 最后更新：2026-11-26
- 关联文档：[首测工程](first-test.md)、[工程索引](README.md)、[桌面工具源码](../../../engineering/desktop/README.md)、[更新问题](../../plans/Issues/README.md)

## 使用

这两个 exe 是**本机引擎首测入口**。启动路径为 `启动OnlineCOC.exe` → 项目内虚拟环境 Python → `engineering/desktop/desktop_host.py` → `Host` / HTTP 服务 → `engineering/test-console/`。默认地址是 `http://127.0.0.1:8765`，页面标题为“OnlineCOC · 本机首测”，页面内标题为“调查室”。它不自动启动树桩镇、房间管理器、LAN/中转服务或 AI runtime；安装运行依赖也不等于启用了 AI。

1. 将**完整项目**解压到较短、当前用户可写的本地目录，保持 `QuickStart/`、`launcher-config.json` 和 `engineering/` 同级。
2. 进入 `QuickStart/`，双击 [安装依赖.exe](../../../QuickStart/安装依赖.exe)，等待依赖校验完成。默认在线安装需要能够访问 python.org 和 PyPI；无须预先安装 Python、Node.js 或编译器。
3. 在同一文件夹双击 [启动OnlineCOC.exe](../../../QuickStart/启动OnlineCOC.exe)。首次创建该数据目录时，设置至少 8 位初始密码。
4. 在自动打开的浏览器中，用 `kp`、`player1` 或 `player2` 及刚设置的密码登录。三者初始密码相同；KP 可见主持人管理区域。多账号同时体验应使用不同浏览器配置或隔离会话，避免共享登录 cookie。
5. 保持启动窗口运行。结束时使用“取消 / 停止”或关闭启动窗口；再次打开同一目录会恢复房间。

两个程序从 `QuickStart/` 的上一级读取 [launcher-config.json](../../../launcher-config.json)。安装目录、端口和存档位置由这份配置决定。

安装程序校验并展开官方 Python 3.14.2 x64 完整运行时，创建项目内虚拟环境，依据共享 `engineering/requirements-runtime.lock` 安装 29 项运行依赖（含 AI 使用的 HTTPX/HTTPCore/certifi），检查版本、模块导入和 `pip check` 后才标记完成。不需要系统 Python、不注册 Python、不修改 PATH 或系统 Python 环境，不需要管理员安装。

启动程序检查环境，尚未安装或依赖锁变化时自动完成必要安装；环境就绪后启动本机服务并打开浏览器。首次启动询问初始密码，初始化 `kp`、`player1`、`player2` 三个首测账号。密码不写入配置或启动日志。后续使用同一存档目录会恢复进度。

启动窗口保持运行，可点击“打开页面”和“取消 / 停止”。停止或关闭窗口时先通知主机正常退出并释放文件锁；超过 30 秒时结束本次子进程树，下次按存档恢复。它不会停止占用相同端口的其他程序。浏览器标签页关闭不等于停止主机。

## 平台和入口边界

两个 exe 用 `/platform:x64` 编译，依赖 Windows .NET Framework 4.x / WinForms；构建记录使用 .NET Framework 4.8 编译器。所用 Python 3.14 的官方平台要求为 Windows 10 及以上，见 [Python Windows 支持说明](https://docs.python.org/3.14/using/windows.html#supported-windows-versions)。本项目入口按 Windows x64 验证；没有提供 Linux/macOS 原生入口或 Windows ARM64 原生发行物，也没有完成这些平台验收。

QuickStart 安装器的虚拟环境位于 `engineering/.runtime/environments/<摘要>/`，**不会创建 `engineering/.venv`**。直接复制文档中的 `.venv/Scripts/python` 开发命令，或运行依赖 `.venv` 的配置包脚本，仍需对应入口自己的环境准备。QuickStart 启动器只监听 `127.0.0.1`；另一台电脑不能用此地址加入，联机使用相应 LAN/中转或房间管理入口。

## 配置的唯一来源

| 配置 | 用途与更新方式 |
| --- | --- |
| `python.version`、`archiveUrl`、`sha256` | 固定运行时版本、完整 zip 和摘要；三项须成组更新并验证 ABI |
| `python.directory`、`cacheFile` | 项目内运行时目录与下载缓存；升级 Python 时使用新的版本目录 |
| `dependencies.lockFile` | 唯一运行依赖版本与 wheel 摘要清单，安装器不另硬编码包版本 |
| `dependencies.environmentRoot` | 虚拟环境根目录；项目位置、Python 摘要或 lock 内容变化会生成新环境 |
| `dependencies.indexUrl`、`wheelDirectory`、`offline` | HTTPS 软件源、本地 wheel 来源与离线模式 |
| `dependencies.probeModules` | 安装后必须可导入的模块，新增关键依赖时同步添加 |
| `application.entryPoint` | 当前桌面宿主入口脚本 |
| `application.dataDirectory` | 房间/账号数据目录，默认与原 CLI 的 `.runtime/demo` 相同 |
| `application.port`、`openBrowser`、`startupTimeoutSeconds` | 回环端口、是否自动打开页面、就绪等待时间 |
| `logsDirectory` | 安装/启动日志目录 |

配置中的路径均相对项目根目录，拒绝绝对路径与越出工程目录的路径。配置文件不能存放密码、令牌或带账号密码的软件源 URL。更改存档目录表示打开另一份房间，不会自动迁移旧数据。

Python 来源和摘要使用 [官方 Windows 发布清单](https://www.python.org/ftp/python/3.14.2/windows-3.14.2.json) 的标准 x64 完整包；沿用本工程已经验证的 3.14.2，未在本次更换后端 Python 基线。

## 依赖更新与失败恢复

更新包版本时先同步运行 lock、开发 lock 和依赖清单，再运行安装 exe 与相关回归。修改现有配置内容和 lock 不需要重新编译 exe；修改 C# 程序时运行 [构建脚本](../../../engineering/desktop/build.ps1)，同步两个二进制及 `build-info.json`。

新依赖组合使用新的环境目录，保留旧环境，避免失败时破坏上一组合；不移动或覆盖存档。安装中断的环境不会有完成标记，重试会按 lock 重装。已标记环境若检测到依赖损坏，安装 exe 会尝试按原 lock 修复。启动时校验失败会显示错误，可运行安装 exe 修复。旧环境和下载暂存不自动删除。

默认数据与环境在 `engineering/.runtime/`，已被 Git 忽略。项目搬移后重新运行安装程序；Python 可重新验证使用，虚拟环境因绝对路径变化重新建立。同步代码时不要用空存档覆盖已有 `.runtime/demo`。

离线安装需先备好 `python.cacheFile` 对应的官方 zip 和锁对应的 wheel，将 `wheelDirectory` 指向它们并设 `offline: true`；缺包或摘要错误时明确失败。下载内容通过 SHA-256 后才展开，pip 安装使用 `--require-hashes --only-binary=:all:`。

## 自动化和故障定位

窗口下方显示进度，详细日志位于 `logsDirectory`。两个工具通过项目级锁避免同时安装/启动；原 CLI 主机仍由文件数据模块排他锁保护。

测试支持 `--headless`、`--config <文件>`、`--check`；启动额外支持 `--no-browser` 和 `--run-seconds N`。自定义配置只覆盖设置，工程根仍为 `QuickStart/` 的上一级。无人值守首次初始化可使用 `ONLINECOC_BOOTSTRAP_PASSWORD` 环境变量；宿主使用后立即从自身环境移除，避免传给 Lua 子进程。

常见处理：端口占用时修改配置或停止旧服务；依赖损坏时重跑安装器；Python 缓存摘要错误时检查配置和缓存来源；下载/安装失败时查看日志并重试。正式备份恢复仍使用 [首测运维步骤](first-test.md#5-管理和恢复)。

首次安装还需留意：当前 exe 未做发行者签名；本轮没有验收系统下载标记或 SmartScreen 交互。项目路径过深时，.NET 解压 Python 可能报告 260/248 字符限制；优先将完整项目移到更短的可写目录后重新安装。`--config` 只改变配置文件，程序仍从 `QuickStart/` 的上一级解析工程路径。删除或改换数据目录会打开另一份房间；安装器不会替你找回旧存档。

## QuickStart 迁移验证（2026-11-26）

两个程序已从 `QuickStart/` 重新构建。以独立测试存档运行桌面套件，8 项全部通过，涵盖全新安装、依赖变更与修复、启动与执行行动、停止与重开、配置错误和端口占用。另在空运行环境的隔离副本中，从其他工作目录执行两款工具的 `--headless --check`，均读取了项目根目录的默认配置，并正确提示需先安装。当前可执行文件与源码摘要见[构建记录](../../../engineering/desktop/build-info.json)。

## 迁移前的安装与浏览器验收（2026-11-26）

以下为迁移前根目录布局及当时构建的记录。本轮复制到独立短路径工程后验收，不读写默认游玩存档。具体脚本、源码清单和机器结果见 [安装与页面验收](../../../engineering/desktop/acceptance-install-audit/README.md)。

8 项真实 exe 自动测试全部通过，无跳过，耗时 138.48 秒，见 [JUnit](../../../engineering/desktop/acceptance-install-audit/desktop-tests-short-path.xml)。覆盖全新 Python/虚拟环境离线安装、重复检查、锁文件变更生成新环境、损坏包修复、启动后执行 Lua 行动、正常停止和重开保持进度、重复工具拒绝、越界路径/错误摘要/缺少离线缓存及端口占用。

默认在线来源在没有 Python ZIP 缓存的新副本中安装成功，耗时 72.99 秒；启动子进程的 PATH 已排除系统 Python。`tkinter`、`_tkinter` 导入和 Tcl 8.6.15 探针通过。Windows 10 x64（19045）和 Edge 158 的三个隔离浏览器会话均登录成功、WebSocket 已连接；只有 KP 显示管理区。玩家执行 `demo.damage` 后，HP 从 9 变为 4，KP 页面同步为 4，正常停止后重新启动仍为 4；没有页面脚本错误。见 [机器结果](../../../engineering/desktop/acceptance-install-audit/online-browser.json) 和验收目录截图。

首次重跑暴露旧测试的深层临时路径超过 .NET 上限，8 项均在共享夹具初始化时出错；已保留 [原始结果](../../../engineering/desktop/acceptance-install-audit/desktop-tests.xml)。测试随后缩短临时目录，并将过期的“26 项依赖”断言改为读取当前锁文件计数（当前为 29 项）；未重编译或改变 exe。

这组测试以无头方式执行真实 exe，不代表原生窗口视觉、首次密码弹窗、下载拦截提示已验收；原生交互待办仍见 [ISSUE-002](../../plans/Issues/issue-002-desktop-interaction-validation.md)。

“干净环境”在本轮指新解压的 Python、新虚拟环境、新合成房间且子进程不从 PATH 使用系统 Python。测试主机本身已有 Windows/.NET/Edge 和开发测试工具，并非刚安装的裸系统虚拟机；也没有验证 Tk 图形窗口或其他操作系统。
