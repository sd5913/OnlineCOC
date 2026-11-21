# 主机账号管理工具

先在本机启动新版宿主，再双击 [HostAccounts.exe](HostAccounts.exe)。工具位于 `engineering/` 外，使用 Windows x64 / .NET Framework，不依赖 Python、浏览器或 KP 密码；源码与构建脚本在本目录。

1. 点击“扫描本机实例”，选择地址、PID 和存档路径对应的实例。
2. 查看账号 ID、登录名、昵称、可用状态和房间角色。
3. 重设密码时先选中账号，输入两次新密码，确认目标实例和账号后提交。
4. 创建账号时输入登录名和两次新密码。当前宿主同时创建 player 房间成员，可直接登录进房；旧版原生窗口中“另外绑定成员”的提示已不适用于新版宿主。

仅能管理当前 Windows 用户在本机通过新版 `serve` 启动的实例。普通客户端设备没有主机实例记录时不提供管理目标；远程连接、房间 KP 登录或浏览器 Cookie 都不能获得这项权限。已经运行的旧宿主需要先停止，再按原方式重新启动同一存档；重启不会重新初始化账号。

密码原文无法查询。新密码为 8–1024 位；重设后目标账号全部旧会话失效，包括目标本人是 KP 的情况，其他账号会话保留。登录名当前也是账号 ID，创建后保持稳定。此工具不提供账号改名、停用或角色修改。

操作结果不明时，“查询原操作结果”使用原请求编号确认，必要时重发同一个请求；不会以新编号自动重设。原实例重启后，可以在工具保持打开的情况下继续查询同一存档。结果未确认时表单和实例切换锁定。密码只临时保存在进程内存，不写工具设置或日志；关闭窗口会丢失未决操作编号，窗口会提示这一点。

宿主发现目录默认 `%LOCALAPPDATA%/OnlineCOC/HostControl/`，记录中的管理凭据使用 Windows DPAPI CurrentUser 加密。实例关闭后删除自己的记录；异常终止留下的旧记录会被扫描忽略。凭据不能转移到其他 Windows 用户或其他电脑使用。若用户环境不能使用 DPAPI，房间服务继续运行，但本机账号管理入口关闭。自定义发现目录仅用于部署／测试，宿主参数为 `serve --host-control-dir <目录>`；工具验证入口支持 `--probe <目录>` 和 `--smoke <目录>`，日常使用默认目录即可。

创建指定角色、删除及脚本调用使用公开 `run.py --data-dir <存档> host-account-request` 客户端，stdin 传 JSON；详细入口、权限、回执和跨库恢复说明见[当前工程文档](../../docs/current/engineering/host-accounts.md)。删除会停用身份及成员，撤销全部旧会话，并保护最后一个可登录 KP。当前 WinForms 二进制未增加删除按钮，本次新能力由客户端接口和包面板使用。Windows DPAPI 说明见 [Microsoft 文档](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)。

## 构建与验证

从项目根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/host-accounts/build.ps1
engineering/.venv/Scripts/python.exe -B tools/host-accounts/verify.py
```

`build-info.json` 保存源码和 exe 摘要。验证要求真实 Windows 用户环境可以访问 DPAPI；在阻止访问用户密钥的沙箱内无法完成此项验证，不应因此改用明文管理密钥。

[历史结果](results.json)记录旧版 40 项专项与 74 项后端回归，原生验证覆盖 DPAPI、实例扫描、接口查询和窗口加载。2026-11-21 新增账号事务、删除与 stdin 客户端的验证见[专项验收](../../engineering/acceptance/local-accounts/README.md)；旧计数不作为新增能力证据。所有验证使用隔离存档。
