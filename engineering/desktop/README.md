# Windows 安装与启动工具

根目录的 `安装依赖.exe` 和 `启动OnlineCOC.exe` 是由 `DesktopTools.cs` 编译的 Windows x64 WinForms 程序，共用根目录 `launcher-config.json`。使用及配置维护见 [桌面工具说明](../../docs/current/engineering/desktop-tools.md)。

它们启动的是 `http://127.0.0.1:8765` 上的本机基础操作台，默认不挂载 AI runtime 或配置包界面。运行环境装在 `engineering/.runtime/environments/`，不会生成开发和部分包脚本使用的 `engineering/.venv`。完整项目必须保留；两个 exe 不能单独分发为可用应用。

| 文件 | 职责 |
| --- | --- |
| `DesktopTools.cs` | 配置读取、下载摘要、Python 展开、独立依赖环境、窗口、服务监督 |
| `build.ps1` | 使用 Windows .NET Framework C# 编译器构建两个 exe |
| `build-info.json` | 本次构建时间、编译器版本、源码及 exe 摘要 |
| `verify_environment.py` | 按共享 lock 校验包版本、Python 架构和导入 |
| `desktop_host.py` | 与现有 Host/HTTP 适配器组合，stdin 控制正常停止 |
| `tests/test_desktop.py` | 对编译后 exe 做安装、更新、修复、启停和错误验证 |

从项目根重新构建：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File engineering/desktop/build.ps1
```

构建只需 Windows .NET Framework 4.x 的 x64 C# 编译器；运行两个 exe 不需要预装 Python。Python 包及 SHA-256 来自 [Python 官方发布清单](https://www.python.org/ftp/python/3.14.2/windows-3.14.2.json)，没有使用 embeddable 精简包或第三方运行时。构建产物当前未做发行者代码签名。

自动测试需要已有开发环境、锁对应的 wheel 缓存 `engineering/.test-output/wheels/` 和官方完整 Python zip `engineering/.test-output/launcher-bootstrap/python-3.14.2-amd64.zip`。缺少测试前置文件会明确失败，不作为通过或跳过。

```powershell
engineering/.venv/Scripts/python -m pytest engineering/desktop/tests -q
```

2026-11-26 的隔离安装、真实 exe 8 项回归、首次启动限制及页面验收见 [验收记录](acceptance-install-audit/README.md)。测试会解压新的 Python 并创建独立环境；路径过深可能触及 .NET 260 字符限制，临时目录使用缩短的随机后缀。依赖数量由共享锁文件计算，避免依赖升级后旧断言失效。
