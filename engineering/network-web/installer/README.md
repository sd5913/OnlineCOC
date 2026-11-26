# 联机依赖一键安装

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-22
- 最后更新：2026-11-26
- 关联文档：[网页联机](../README.md)、[P2P](../../network-p2p/README.md)、[工程说明](../../../docs/current/engineering/network-web.md)

## 给其他电脑使用

网页玩家和远程 KP **只需浏览器，不安装此 EXE**。Windows 房主，以及运行传统本机 P2P 客户端的设备，使用联机运行时。

1. 先取得完整项目与维护者提供的 `OnlineCOC-Network-Setup.exe`、`release.json`。当前产物位于 [dist/](../dist/)，该目录不入 Git；仅 clone 源码不会得到 EXE，维护者须随分发包提供，或按下文构建。
2. 正常停止正在运行的网页/P2P 分享，然后双击 EXE，点击“选择目录”。选择 **OnlineCOC 项目根目录**，例如 `D:\Games\OnlineCOC`；打开该目录后应直接看到 `engineering/`，其中含 `network-p2p/pyproject.toml` 和 `network-web/pyproject.toml`。
3. 点击“一键安装”，等待“安装完成”。安装后继续按[网页房主步骤](../README.md#房主)配置和分享，无需再运行 pip。
4. 树桩镇房主另按[包侧启动教学](../../../rulepacks/stumpsville/docs/current/usage.md)准备游戏宿主运行时；此 EXE 仅负责联机环境。

- 适用 Windows 10/11 x64，使用系统 .NET Framework；EXE 约 46 MiB，包含独立 Python 3.14.2 与当前 `requirements.lock` 的联机依赖，安装时无需网络或已有 Python。
- 安装到 `engineering/network-p2p/.venv/`，直接供现有网页/P2P 启动器使用；两个联网模块从所选项目源码加载。EXE 不包含游戏包或项目源码，所以必须先复制项目。
- 自检通过后才切换运行时。已有环境保留在 `network-p2p/local/runtime-backups/`；发现正在使用该环境的程序会拒绝替换，须先正常关闭。安装失败不会主动终止游戏程序。
- 不修改系统 PATH、服务器、网络规则、账号、证书、凭据或存档。首次安装后仍需准备本机游戏宿主及合法的目录/发布权限配置；此包只安装联机依赖，不安装游戏宿主、AI 或开发测试依赖。
- EXE 未做发布者代码签名。分发时可用同目录 `release.json` 中的 SHA-256 核对文件；运行时和第三方许可随安装内容保留。

不要直接在此嵌入运行时内运行 pip 升级依赖。需要更新时重新构建并运行安装器；开发者仍可用原 `setup.ps1` 建立常规 venv。跨电脑不要复制原 `.venv` 或私钥作为安装方法。

## 失败后重试

| 提示或情况 | 处理方式 |
| --- | --- |
| 请选择包含 engineering 的项目根目录 | 重新选择完整项目根目录；确认上面的两个 `pyproject.toml` 均存在，再点“一键安装” |
| 请先关闭正在使用该联机环境的程序 | 正常停止网页/P2P 分享，等待其退出，保留同一目标目录，再点“一键安装” |
| 另一安装器正在运行或文件被占用 | 关闭重复安装窗口，等待当前安装结束后再重试 |
| 安装包损坏 | 从同一可信分发来源重新取得 EXE，按 `release.json` 核对 SHA-256 后重试 |
| 依赖自检失败、超时或目录无法写入 | 保存错误文字，确认完整项目位于可写的本地普通目录（不支持目录联接/符号链接）；重新运行。持续失败时将错误和包版本交给维护者 |

重试不要求删除配置或存档。成功替换前会先自检，旧运行时备份到 `engineering/network-p2p/local/runtime-backups/`；本轮已验证“运行占用拒绝 → 停止测试进程 → 同目录重试成功”。自检失败的暂存目录可能保留，先保留用于定位问题。

## 构建与验证

在已安装锁定依赖的开发环境，从项目根运行：

```powershell
$env:PYTHONUTF8='1'
engineering/network-p2p/.venv/Scripts/python.exe engineering/network-web/installer/build.py
engineering/network-p2p/.venv/Scripts/python.exe engineering/network-web/installer/verify.py
```

构建从 Python 官方下载嵌入包，按官方 SPDX 中的 SHA-256 校验；只收集锁定依赖的发行文件，排除项目私密配置、缓存和测试依赖。产物在 `network-web/dist/`，构建中间文件在 `build/installer/`，均不入库。依据：[Python 嵌入发行说明](https://docs.python.org/3.14/using/windows.html#the-embeddable-package)、[3.14.2 官方文件](https://www.python.org/downloads/release/python-3142/)（2026-11-22 核对，版本与本项目已验证环境一致）。

`verify.py --output <结果文件>` 可指定结果位置；用中文/空格路径的隔离项目实际运行 EXE，隐藏系统 Python 路径，验证首次安装、重复安装备份、依赖/WebRTC 自检、两个 CLI、运行占用拒绝及配置保留；未代替另一台干净实体电脑的人工验收。

自动部署可运行 `OnlineCOC-Network-Setup.exe --install "项目根目录"`；`--verify` 只做自检，退出码 0 为成功、1 为失败。GUI 与命令行共用安装逻辑。

2026-11-26 本机复核见[安装与入场记录](../acceptance/2026-11-26-firstplay.json)：实际 EXE 首次安装、占用失败后重试、配置保留及依赖自检通过。使用 EXE 命令行验证共用安装逻辑，未人工点击 GUI，也未在另一台干净实体电脑验证。
