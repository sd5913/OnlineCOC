# 工程目录与施工登记

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-10-29
- 最后更新：2026-11-23
- 最近目录核对：2026-11-23（AI分步发布、投影兼容与专项验收）；2026-11-23（规则文件增量暂存、既有性能与远程KP验收清单）；详见[增量暂存验收](../../../engineering/acceptance/rule-stage-delta/README.md)。 2026-11-23（AI 模糊需求恢复源码、冻结差量和验收清单）。 2026-11-23（聊天交互修复、冻结组件与浏览器验收）。
- 关联文档：[工程文档索引](README.md)、[文档维护标准](../../standards/document-maintenance.md)

## 工程实际目录

`engineering/acceptance/ai-runtime/*-tmp/` 是验收生成的隔离宿主、身份库及日志目录，已忽略，可通过对应测试重建。该目录下精选的 XML、JSON 和截图仍按下列清单入库。

以下清单只记录实际存在的项目文件。`engineering/` 已包含本机首测后端、独立文件数据管理、Lua/流程执行器、SDK、操作台、规则包及验收驱动；原同步内存实验保留。新增、移动、重命名、删除文件时，必须在同一施工任务内同步本清单。

路径均相对项目根目录。清单覆盖项目维护的文件（含文档与配置）；版本控制内部数据（如 `.git/`）、依赖安装目录、缓存及生成产物不逐文件登记，出现这些目录时应补充目录用途与施工影响范围，不能因此忽略写入冲突。

`.git/` 已用于本地 Git 仓库的版本记录、分支、索引和远端配置，不作为项目文件入库。切换分支、更新索引或提交等操作会影响整个工作区的协作状态，施工前应登记相应范围；初始化与全局分支切换使用整个工程范围 `.`。

| 实际文件 | 用途 |
| --- | --- |
| `AGENTS.md` | Agent 协作与施工要求 |
| `.gitattributes` | 保留ISSUE-024验收及依赖冻结版本的原始字节，避免跨系统换行改变证据哈希 |
| `README.md` | 项目入口 |
| `engineering/README.md` | 工程代码目录用途与相关入口 |
| `docs/current/engineering/network-p2p.md` | 公网模块配置、玩家包/内容导出、协议、云端运维与验收 |
| `engineering/network-p2p/.gitattributes` | 固定 Linux 脚本及 Windows PowerShell 的行尾 |
| `engineering/network-p2p/.gitignore` | 排除本机凭据、运行时与测试产物 |
| `engineering/network-p2p/README.md` | 公网联机快速使用：房主开房、玩家加入及常见问题 |
| `engineering/network-p2p/acceptance/2026-11-13.json` | 46 项验收、跨机器直连/中转、玩家包与源码摘要的精选证据 |
| `engineering/network-p2p/config/client.example.json` | 不含真实凭据的配置或玩家导出示例 |
| `engineering/network-p2p/config/directory.example.json` | 不含真实凭据的配置或玩家导出示例 |
| `engineering/network-p2p/config/distribution.example.json` | 不含真实凭据的配置或玩家导出示例 |
| `engineering/network-p2p/deploy/install-remote.sh` | Ubuntu 测试服务幂等部署 |
| `engineering/network-p2p/deploy/onlinecoc-directory.service` | 受限用户和资源的目录/信令服务 |
| `engineering/network-p2p/deploy/onlinecoc-turn.service` | 受限用户和资源的 TURN 服务 |
| `engineering/network-p2p/local/README.md` | 本机凭据、证书、状态和测试输出的存放边界 |
| `engineering/network-p2p/pyproject.toml` | 独立 Python 包、CLI 与测试配置 |
| `engineering/network-p2p/requirements-test.txt` | 浏览器、pytest 与模块验收依赖 |
| `engineering/network-p2p/requirements.lock` | 已验证的全部运行依赖版本锁 |
| `engineering/network-p2p/requirements.txt` | 直接运行依赖 |
| `engineering/network-p2p/scripts/build_player.py` | 显式白名单打包玩家客户端并排除运维秘密 |
| `engineering/network-p2p/scripts/peer_probe.py` | Ubuntu 远端玩家测试，输入经 stdin 传递 |
| `engineering/network-p2p/scripts/prepare_deploy.py` | 本机准备证书、私密配置与部署包 |
| `engineering/network-p2p/scripts/real_host_fixture.py` | 当前真实宿主的独立验收启动入口 |
| `engineering/network-p2p/scripts/record_acceptance.py` | 精选非私密验收记录与源码摘要 |
| `engineering/network-p2p/scripts/server.ps1` | 使用本机配置和严格 known_hosts 的 SSH/SCP 包装 |
| `engineering/network-p2p/scripts/verify_deployment.py` | HTTPS、发布权限与 TURN TLS 握手检查 |
| `engineering/network-p2p/scripts/verify_player.py` | 独立目录中的玩家分发包启动验收 |
| `engineering/network-p2p/server-info.example.md` | 不含实际凭据的服务器资料模板 |
| `engineering/network-p2p/setup.ps1` | 安装 Python 3.14 独立联网运行时 |
| `engineering/network-p2p/src/onlinecoc_p2p/__init__.py` | 模块版本 |
| `engineering/network-p2p/src/onlinecoc_p2p/__main__.py` | Python 模块执行入口 |
| `engineering/network-p2p/src/onlinecoc_p2p/cli.py` | 目录、房主、客户端与导出 CLI |
| `engineering/network-p2p/src/onlinecoc_p2p/client.py` | Python WebRTC 玩家与验收客户端 |
| `engineering/network-p2p/src/onlinecoc_p2p/common.py` | 签名、摘要、TLS、输入边界与限流 |
| `engineering/network-p2p/src/onlinecoc_p2p/control.py` | 校验证书的目录 HTTP/WSS 客户端 |
| `engineering/network-p2p/src/onlinecoc_p2p/directory.py` | HTTPS 房间 API、准入、TURN 凭据与 WSS 信令 |
| `engineering/network-p2p/src/onlinecoc_p2p/host.py` | 借用原宿主的主机适配器、审批、玩家隔离及数据通道 |
| `engineering/network-p2p/src/onlinecoc_p2p/local_app.py` | 可信本机控制入口、私密配置边界与玩家 HTML 沙箱响应 |
| `engineering/network-p2p/src/onlinecoc_p2p/ownership.py` | 跨进程房间身份占用锁 |
| `engineering/network-p2p/src/onlinecoc_p2p/packages.py` | 玩家白名单导出、签名清单、分块校验与续传缓存 |
| `engineering/network-p2p/src/onlinecoc_p2p/rooms.py` | 房间、租约、策略、邀请与一次性票据状态机 |
| `engineering/network-p2p/src/onlinecoc_p2p/rtc.py` | ICE 配置、强制中继与候选类型诊断 |
| `engineering/network-p2p/src/onlinecoc_p2p/upstream.py` | 每玩家 Cookie/CSRF 隔离及回环宿主 API 白名单 |
| `engineering/network-p2p/src/onlinecoc_p2p/web/app.js` | 房间大厅、发布、审批、登录、内容确认和游戏状态 UI |
| `engineering/network-p2p/src/onlinecoc_p2p/web/bridge.js` | 隔离玩家页面的资源装配与受限 MessageChannel 桥 |
| `engineering/network-p2p/src/onlinecoc_p2p/web/index.html` | 联网房间页面 |
| `engineering/network-p2p/src/onlinecoc_p2p/web/style.css` | 联网入口响应式样式 |
| `engineering/network-p2p/src/onlinecoc_p2p/web/transport.js` | 浏览器 WebRTC Transport、签名、状态与 IndexedDB 同步 |
| `engineering/network-p2p/src/onlinecoc_p2p/wire.py` | 有界分帧、重组与发送背压 |
| `engineering/network-p2p/start.ps1` | 打开本机联网入口 |
| `engineering/network-p2p/tests/conftest.py` | 公网模块专项自动验收：conftest |
| `engineering/network-p2p/tests/test_admission.py` | 公网模块专项自动验收：test_admission |
| `engineering/network-p2p/tests/test_browser.py` | 公网模块专项自动验收：test_browser |
| `engineering/network-p2p/tests/test_cloud.py` | 公网模块专项自动验收：test_cloud |
| `engineering/network-p2p/tests/test_cross_machine.py` | 公网模块专项自动验收：test_cross_machine |
| `engineering/network-p2p/tests/test_local_boundary.py` | 公网模块专项自动验收：test_local_boundary |
| `engineering/network-p2p/tests/test_packages.py` | 公网模块专项自动验收：test_packages |
| `engineering/network-p2p/tests/test_real_host.py` | 公网模块专项自动验收：test_real_host |
| `engineering/network-p2p/tests/test_rooms.py` | 公网模块专项自动验收：test_rooms |
| `engineering/network-p2p/tests/test_sdk.py` | 公网模块专项自动验收：test_sdk |
| `engineering/network-p2p/tests/test_transport.py` | 公网模块专项自动验收：test_transport |
| `engineering/network-p2p/local/` | Git 忽略的私密配置、证书、部署包、测试/浏览器缓存及运行状态，不逐文件入库 |
| `engineering/network-p2p/tmp/` | 用户提供的实例导出和 SSH 私钥，Git 忽略 |
| `engineering/network-p2p/.venv/` | 独立联网开发与验收运行时，Git 忽略 |
| `engineering/network-p2p/dist/` | 生成的玩家分发 ZIP，Git 忽略 |
| `engineering/lua-authoring-prototype/README.md` | 同步原型用途、运行和边界 |
| `engineering/lua-authoring-prototype/host.lua` | Lua 简化编写同步内存实验宿主 |
| `engineering/lua-authoring-prototype/tests.lua` | 原型行为与失败条件验证套件 |
| `engineering/lua-authoring-prototype/examples/01-check.lua` | 简化检定规则 |
| `engineering/lua-authoring-prototype/examples/02-damage.lua` | 简化伤害规则 |
| `engineering/lua-authoring-prototype/examples/03-transfer.lua` | 简化物品转移规则 |
| `engineering/lua-authoring-prototype/examples/05-check-with-ruling.md` | A0 裁定流程稿，尚不可执行 |
| `docs/current/engineering/lua-authoring-prototype.md` | 原型实际能力、运行与验证限制 |
| `docs/README.md` | 全部文档索引 |
| `docs/current/README.md` | 当前文档分类入口 |
| `docs/current/design/README.md` | 设计文档索引 |
| `docs/current/design/project-overview.md` | 项目目标与阶段概况 |
| `docs/current/engineering/README.md` | 工程文档索引与同步要求 |
| `docs/current/engineering/hierarchy.md` | 实际目录清单与施工登记（本文件） |
| `docs/history/README.md` | 历史文档索引与归档说明 |
| `docs/history/2026-10-29-lua-script-reference.md` | 首轮 Lua 编写协议正文及验证背景归档 |
| `docs/plans/README.md` | 计划文档索引 |
| `docs/plans/room-launch-orchestration.md` | 统一房间入口、服务编排与配置包职责划分的评估方案 |
| `docs/plans/room-discovery-p2p-package-sync.md` | 服务器房间发现、P2P 联机与配置包同步的待实施方案 |
| `docs/plans/browser-room-portal.md` | 网页测试版实施状态，正式域名/证书与独立真人网络等后续验收 |
| `docs/plans/cloud-server-deployment-research.md` | 云服务器选型、费用测算、腾讯域名注册/解析/备案与 HTTPS 接入调研 |
| `docs/plans/ai-runtime-design.md` | 房间 AI 服务商接入、上下文与记忆、三类校验及 KP 审批发布的待实施设计 |
| `docs/plans/ai-runtime-construction-plan.md` | 房间 AI 模块分期实施、验证矩阵与完整使用闭环的待实施计划 |
| `docs/plans/ai-data-query-adjudication.md` | AI 查询已实现范围及通用记录、索引、跨存储发布的后续计划 |
| `docs/plans/speech-input-research.md` | 玩家及 KP/开发者面向独立 AI 模块的语音输入识别调研、选型与接入草案 |
| `docs/plans/speech-input-design.md` | 独立语音输入模块的服务商、录音转写、HTTP/WS 协议与 AI 文本桥接设计草案 |
| `docs/plans/speech-input-construction-plan.md` | 独立语音输入 SI-0—SI-6 施工、29 项验收及玩家/配置编写流程计划，尚未实施 |
| `docs/plans/localization-system.md` | 独立于核心和具体配置包的本地化开发工具、文件协作与可视化管理方案 |
| `docs/plans/localization-engineering-design.md` | 独立本地化工具的目录、文件契约、GUI/CLI、恢复与发布工程设计 |
| `docs/plans/localization-construction-plan.md` | 独立本地化工具 L10N-0—L10N-6 施工、证据及阶段验收计划 |
| `rulepacks/AGENTS.md` | 配置包作者只使用工程、不修改工程的施工边界 |
| `rulepacks/lasers-and-feelings/.gitignore` | 独立 L&F 配置包文件 |
| `rulepacks/lasers-and-feelings/assets/README.md` | 独立 L&F 配置包文件 |
| `rulepacks/lasers-and-feelings/config/configurations.json` | 对象配置或原规则静态资料 |
| `rulepacks/lasers-and-feelings/config/lf.json` | 对象配置或原规则静态资料 |
| `rulepacks/lasers-and-feelings/config/README.md` | 对象配置或原规则静态资料 |
| `rulepacks/lasers-and-feelings/docs/history/2026-10-31-cooperation-validation.md` | 当前包文档或历史验证记录 |
| `rulepacks/lasers-and-feelings/docs/history/README.md` | 当前包文档或历史验证记录 |
| `rulepacks/lasers-and-feelings/docs/package-preparation.md` | 当前包文档或历史验证记录 |
| `rulepacks/lasers-and-feelings/docs/README.md` | 当前包文档或历史验证记录 |
| `rulepacks/lasers-and-feelings/docs/rules.md` | 当前包文档或历史验证记录 |
| `rulepacks/lasers-and-feelings/docs/usage.md` | 当前包文档或历史验证记录 |
| `rulepacks/lasers-and-feelings/flows/README.md` | 独立 L&F 配置包文件 |
| `rulepacks/lasers-and-feelings/LICENSE.md` | 独立 L&F 配置包文件 |
| `rulepacks/lasers-and-feelings/manifest.json` | 独立 L&F 配置包文件 |
| `rulepacks/lasers-and-feelings/README.md` | 独立 L&F 配置包文件 |
| `rulepacks/lasers-and-feelings/rules/adventure.lua` | 当前可复用 Lua 规则或规则索引 |
| `rulepacks/lasers-and-feelings/rules/answer.lua` | 当前可复用 Lua 规则或规则索引 |
| `rulepacks/lasers-and-feelings/rules/cancel.lua` | 当前可复用 Lua 规则或规则索引 |
| `rulepacks/lasers-and-feelings/rules/close.lua` | 当前可复用 Lua 规则或规则索引 |
| `rulepacks/lasers-and-feelings/rules/help.lua` | 当前可复用 Lua 规则或规则索引 |
| `rulepacks/lasers-and-feelings/rules/library.lua` | 当前可复用 Lua 规则或规则索引 |
| `rulepacks/lasers-and-feelings/rules/main.lua` | 当前可复用 Lua 规则或规则索引 |
| `rulepacks/lasers-and-feelings/rules/open.lua` | 当前可复用 Lua 规则或规则索引 |
| `rulepacks/lasers-and-feelings/rules/profile.lua` | 当前可复用 Lua 规则或规则索引 |
| `rulepacks/lasers-and-feelings/rules/question.lua` | 当前可复用 Lua 规则或规则索引 |
| `rulepacks/lasers-and-feelings/rules/README.md` | 当前可复用 Lua 规则或规则索引 |
| `rulepacks/lasers-and-feelings/rules/ship.lua` | 当前可复用 Lua 规则或规则索引 |
| `rulepacks/lasers-and-feelings/sources/lasers-and-feelings-original.pdf` | 完整原始规则、来源、许可与摘要 |
| `rulepacks/lasers-and-feelings/sources/lasers-and-feelings-original.txt` | 完整原始规则、来源、许可与摘要 |
| `rulepacks/lasers-and-feelings/sources/README.md` | 完整原始规则、来源、许可与摘要 |
| `rulepacks/lasers-and-feelings/sources/source-checksums.txt` | 完整原始规则、来源、许可与摘要 |
| `rulepacks/lasers-and-feelings/start.ps1` | 独立 L&F 配置包文件 |
| `rulepacks/lasers-and-feelings/启动激光与情感.exe` | Windows 原生控制台启动入口 |
| `rulepacks/lasers-and-feelings/tools/PackLauncher.cs` | 配置包 exe 源码及退出进程清理 |
| `rulepacks/lasers-and-feelings/tools/build-launcher.ps1` | 仅在包内生成 exe 与摘要的编译脚本 |
| `rulepacks/lasers-and-feelings/tools/launcher-build.json` | 源码、exe 摘要和编译环境记录 |
| `rulepacks/lasers-and-feelings/tools/README.md` | 包工具、exe 构建和启动清理说明 |
| `rulepacks/lasers-and-feelings/tests/verify_launcher.py` | 原生 exe 的真实启动、退出清理及重启验证 |
| `rulepacks/lasers-and-feelings/tests/launcher-results.json` | 10 项原生启动验证机器结果 |
| `rulepacks/lasers-and-feelings/tests/.gitignore` | 包级验证、浏览器验证、机器证据或历史夹具 |
| `rulepacks/lasers-and-feelings/tests/cooperation-results.json` | 包级验证、浏览器验证、机器证据或历史夹具 |
| `rulepacks/lasers-and-feelings/tests/fixtures/close.lua` | 包级验证、浏览器验证、机器证据或历史夹具 |
| `rulepacks/lasers-and-feelings/tests/fixtures/help.lua` | 包级验证、浏览器验证、机器证据或历史夹具 |
| `rulepacks/lasers-and-feelings/tests/fixtures/main.lua` | 包级验证、浏览器验证、机器证据或历史夹具 |
| `rulepacks/lasers-and-feelings/tests/fixtures/roll.lua` | 包级验证、浏览器验证、机器证据或历史夹具 |
| `rulepacks/lasers-and-feelings/tests/package-results.json` | 包级验证、浏览器验证、机器证据或历史夹具 |
| `rulepacks/lasers-and-feelings/tests/README.md` | 包级验证、浏览器验证、机器证据或历史夹具 |
| `rulepacks/lasers-and-feelings/tests/ui-results.json` | 包级验证、浏览器验证、机器证据或历史夹具 |
| `rulepacks/lasers-and-feelings/tests/verify_cooperation.py` | 包级验证、浏览器验证、机器证据或历史夹具 |
| `rulepacks/lasers-and-feelings/tests/verify_package.py` | 包级验证、浏览器验证、机器证据或历史夹具 |
| `rulepacks/lasers-and-feelings/tests/verify_ui.py` | 包级验证、浏览器验证、机器证据或历史夹具 |
| `rulepacks/lasers-and-feelings/tools/client.py` | 仅使用现有 CLI/HTTP 的独立启动、导出或包工具 |
| `rulepacks/lasers-and-feelings/tools/export.py` | 仅使用现有 CLI/HTTP 的独立启动、导出或包工具 |
| `rulepacks/lasers-and-feelings/tools/launch.py` | 独立启动、同源适配及同机多账号会话槽位 |
| `rulepacks/lasers-and-feelings/tools/package.py` | 仅使用现有 CLI/HTTP 的独立启动、导出或包工具 |
| `rulepacks/lasers-and-feelings/ui/app.js` | 跑团桌面界面、样式或设计 |
| `rulepacks/lasers-and-feelings/ui/frontend-design.md` | 跑团桌面界面、样式或设计 |
| `rulepacks/lasers-and-feelings/ui/index.html` | 跑团桌面界面、样式或设计 |
| `rulepacks/lasers-and-feelings/ui/README.md` | 跑团桌面界面、样式或设计 |
| `rulepacks/lasers-and-feelings/ui/styles.css` | 跑团桌面界面、样式或设计 |
| `rulepacks/README.md` | 配置包开发指南、工程接入与支持工具入口 |
| `rulepacks/catalog.md` | 具体配置包实例、版本、状态统计与登记管理 |
| `rulepacks/investigation-vtt-reference/README.md` | 调查型线上跑团对照配置包入口 |
| `rulepacks/investigation-vtt-reference/.gitignore` | 排除参考资料的临时解压目录 |
| `rulepacks/investigation-vtt-reference/Mausritter_neural_link_export_Masterwork_Bundle.zip` | 对照研究的原始配置资料压缩包 |
| `rulepacks/investigation-vtt-reference/docs/plans/README.md` | 调查型线上跑团对照包计划索引 |
| `rulepacks/investigation-vtt-reference/docs/plans/reference-research.md` | 规则、配置与界面样本调研和适配计划 |
| `rulepacks/investigation-vtt-reference/docs/plans/mausritter-completeness.md` | Mausritter 资料树、完整性核查与后续验证计划 |
| `rulepacks/investigation-vtt-reference/docs/plans/stumpsville-foundry-plan.md` | Stumpsville 原版对照、地图、Foundry 导入及界面计划 |
| `rulepacks/investigation-vtt-reference/docs/plans/stumpsville-interface-reference.md` | Stumpsville 界面参考图集与实测清单 |
| `rulepacks/investigation-vtt-reference/assets/interface-reference/external/pips-character-sheet.jpg` | Pips & Paws 浅色角色表截图 |
| `rulepacks/investigation-vtt-reference/assets/interface-reference/external/pips-character-sheet-dark.jpg` | Pips & Paws 深色角色表截图 |
| `rulepacks/investigation-vtt-reference/assets/interface-reference/external/pips-gm-dashboard.jpg` | Pips & Paws 主持面板截图 |
| `rulepacks/investigation-vtt-reference/assets/interface-reference/external/pips-gm-battlemap.jpg` | Pips & Paws 主持战术地图截图 |
| `rulepacks/investigation-vtt-reference/assets/interface-reference/external/mausritter-character-sheet.png` | Mausritter 原版角色卡页图 |
| `rulepacks/investigation-vtt-reference/assets/interface-reference/external/mausritter-gm-tracker-es.png` | Mausritter 西语主持追踪表页图 |
| `rulepacks/investigation-vtt-reference/assets/interface-reference/wireframes/stumpsville-character-entry.png` | Stumpsville 入场与建角线框 |
| `rulepacks/investigation-vtt-reference/assets/interface-reference/wireframes/stumpsville-kp-workbench.png` | Stumpsville 主持端线框 |
| `rulepacks/investigation-vtt-reference/assets/interface-reference/wireframes/stumpsville-pl-workbench.png` | Stumpsville 玩家端线框 |
| `rulepacks/mini-detective-pack/README.md` | 铃蔓回转录资料、规则复原、本机实现与自动行动入口 |
| `rulepacks/mini-detective-pack/docs/README.md` | 铃蔓资料与计划文档索引 |
| `rulepacks/mini-detective-pack/docs/sources.md` | 五张规则图、七张工作表、三张UI参考、网络检索及原料冲突证据 |
| `rulepacks/mini-detective-pack/docs/plans/README.md` | 铃蔓规则与配置补全计划索引 |
| `rulepacks/mini-detective-pack/docs/plans/rules.md` | 六维、探索、体力、卡片与战斗的复原及试跑规则草案 |
| `rulepacks/mini-detective-pack/docs/plans/configuration.md` | 参数、对象、权限、状态机与验收规格草案 |
| `rulepacks/mini-detective-pack/docs/plans/scenario.md` | 两日主持场景、地图、库存、线索、谜题及结局补全草案 |
| `rulepacks/mini-detective-pack/docs/plans/map-and-items.md` | 宅邸与岛屿地图、22种道具分布及获取依赖的Mermaid草案 |
| `rulepacks/mini-detective-pack/docs/plans/frontend-design.md` | 新增UI参考适配、KP与PL界面和前端实施计划 |
| `rulepacks/mini-detective-pack/docs/plans/interface-flows.md` | 建卡、KP与PL操作、战斗时序和秘密信息投影Mermaid草案 |
| `rulepacks/mini-detective-pack/raw/12EC99D144C79211680B3CB83DDFDE55.png` | 用户提供的企划玩法原图 |
| `rulepacks/mini-detective-pack/raw/5576AAC5876167733B85FAEE1A978AA5.png` | 用户提供的行动轮、体力与探索原图 |
| `rulepacks/mini-detective-pack/raw/85AD675A5E3B80BE55A62EAB58577AEB.png` | 用户提供的战斗机制原图 |
| `rulepacks/mini-detective-pack/raw/99B0B7DE1C3110F18003D2D0D7A502FF.png` | 用户提供的六维与卡片机制原图 |
| `rulepacks/mini-detective-pack/raw/B1D563E533F8B0012B91AB2A2AE3B32A.png` | 用户提供的战斗示例原图 |
| `rulepacks/mini-detective-pack/raw/铃蔓回转录.xlsx` | 用户提供的场景、角色、日程与后期战斗工作簿 |
| `rulepacks/mini-detective-pack/raw/UI/65cb0a21-b583-4261-8f15-22084de2ffc9.png` | 用户新增的建角界面参考图 |
| `rulepacks/mini-detective-pack/raw/UI/9ea93a5d-5705-4b90-9591-88b7970d3507.png` | 用户新增的背包弹层参考图 |
| `rulepacks/mini-detective-pack/raw/UI/c80d39dd-b28b-4260-9866-3c028e4133a4.png` | 用户新增的叙事与选择主界面参考图 |
| `rulepacks/mini-detective-pack/assets/README.md` | 已下载网络占位素材的用途、许可与绑定索引 |
| `rulepacks/mini-detective-pack/assets/placeholders/manifest.json` | 20份占位素材的来源、作者、许可、摘要与22道具及23地点绑定 |
| `rulepacks/mini-detective-pack/assets/placeholders/CREDITS.md` | 网络占位素材逐件署名、来源与许可 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/lorc-lantern.svg` | 网络占位素材：Lantern，Lorc，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/lorc-key.svg` | 网络占位素材：Key，Lorc，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/lorc-hammer-drop.svg` | 网络占位素材：Hammer Drop，Lorc，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/lorc-broadsword.svg` | 网络占位素材：Broadsword，Lorc，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/lorc-candle-light.svg` | 网络占位素材：Candle Light，Lorc，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/lorc-scroll-unfurled.svg` | 网络占位素材：Scroll Unfurled，Lorc，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/lorc-hood.svg` | 网络占位素材：Hood，Lorc，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/lorc-pine-tree.svg` | 网络占位素材：Pine Tree，Lorc，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/lorc-castle.svg` | 网络占位素材：Castle，Lorc，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/delapouite-film-strip.svg` | 网络占位素材：Film Strip，Delapouite，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/delapouite-rope-coil.svg` | 网络占位素材：Rope Coil，Delapouite，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/delapouite-island.svg` | 网络占位素材：Island，Delapouite，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/delapouite-village.svg` | 网络占位素材：Village，Delapouite，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/delapouite-sailboat.svg` | 网络占位素材：Sailboat，Delapouite，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/lorc-meat.svg` | 网络占位素材：Meat，Lorc，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/lorc-round-bottom-flask.svg` | 网络占位素材：Round Bottom Flask，Lorc，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/sbed-health-normal.svg` | 网络占位素材：Health Normal，sbed，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/skoll-winchester-rifle.svg` | 网络占位素材：Winchester Rifle，Skoll，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/icons/lorc-umbrella.svg` | 网络占位素材：Umbrella，Lorc，CC-BY-3.0 |
| `rulepacks/mini-detective-pack/assets/placeholders/textures/parchment.png` | 网络占位素材：Parchment，Mattias Lejbrink，CC0-1.0 |
| `docs/plans/Issues/issue-003-rulepack-cooperative-ruling.md` | 配置包协作问题：包侧已解决并验证，待工程责任者复核记录 |
| `docs/plans/games/README.md` | 轻量跑团资料与适配计划索引 |
| `docs/plans/games/lasers-and-feelings/README.md` | 已迁入独立配置包的兼容入口 |
| `docs/plans/project planning/first-test-engineering-design.md` | 首测工程设计与实施对照，保留设计基线 |
| `docs/plans/project planning/first-test-construction-plan.md` | 首测 E0—E6 任务与验收基线，独立作者试写待验收 |
| `docs/plans/project planning/Issue/README.md` | 工程规划待解决问题索引 |
| `docs/plans/project planning/Issue/lua-authoring-simplification.md` | ISSUE-001：Lua 规则与流程编写体验简化议题 |
| `docs/plans/project planning/lua-authoring-facade.md` | Lua 简化编写接口与可恢复流程候选方案 |
| `docs/plans/project planning/lua-script-reference/README.md` | 旧 Lua 样例对照索引及替代关系 |
| `docs/plans/project planning/lua-script-reference/01-percentile-check.lua` | 百分骰检定规则参考 |
| `docs/plans/project planning/lua-script-reference/02-apply-damage.lua` | 护甲减伤与 HP 效果参考 |
| `docs/plans/project planning/lua-script-reference/03-transfer-item.lua` | 容量校验与物品转移参考 |
| `docs/plans/project planning/lua-script-reference/04-check-from-file.lua` | 读取配置文件的环境检定参考 |
| `docs/plans/project planning/lua-script-reference/05-check-with-ruling.lua` | 检定分支与 KP 裁定流程参考 |
| `docs/plans/project planning/lua-script-reference/06-round-status.lua` | 逻辑轮次状态规则参考 |
| `docs/plans/project planning/lua-script-reference/07-timed-choice.lua` | 限时输入与超时流程参考 |
| `docs/plans/project planning/lua-script-reference/08-grant-item.lua` | 无骰物品授予规则参考 |
| `docs/plans/project planning/lua-script-reference/09-session-damage-override.lua` | 场次临时伤害覆盖参考 |
| `docs/plans/project planning/lua-script-reference/data/environment-modifiers.json` | 环境检定的数据配置参考 |
| `docs/plans/project planning/backend-network-analysis.md` | 后端、自定义能力与联机方案分析草案 |
| `docs/plans/project planning/module-responsibilities.md` | 系统模块分层与职责设计草案 |
| `docs/plans/project planning/data-container-model.md` | 抽象数据结构与容器设计草案 |
| `docs/plans/project planning/frontend-backend-contract.md` | 前后端接口、SDK、授权投影与同步契约草案 |
| `docs/plans/coc-online-trpg-research.md` | COC 与线上跑团的图谱、规则构成及内容类型调研 |
| `docs/standards/README.md` | 通用标准索引 |
| `docs/standards/document-maintenance.md` | 文档维护及施工协调标准 |
| `.gitignore` | 首测实现 / 测试 / 配置 |
| `docs/current/engineering/first-test.md` | 工程运行与验收文档 |
| `docs/current/engineering/lua-authoring.md` | 工程运行与验收文档 |
| `engineering/acceptance/crash_worker.py` | 首测实现 / 测试 / 配置 |
| `engineering/acceptance/README.md` | 工程运行与验收文档 |
| `engineering/acceptance/server_probe.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/pyproject.toml` | 首测实现 / 测试 / 配置 |
| `engineering/backend/scripts/run.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/src/onlinecoc/__init__.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/src/onlinecoc/assets.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/src/onlinecoc/cli.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/src/onlinecoc/contracts.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/src/onlinecoc/errors.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/src/onlinecoc/execution.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/src/onlinecoc/gateway.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/src/onlinecoc/host.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/src/onlinecoc/identity.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/src/onlinecoc/lua_runtime.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/src/onlinecoc/model.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/src/onlinecoc/registry.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/src/onlinecoc/server.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/tests/conftest.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/tests/test_adapters.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/tests/test_faults.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/tests/test_foundation.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/tests/test_host.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/tests/test_model_contracts.py` | 首测实现 / 测试 / 配置 |
| `engineering/backend/tests/test_network.py` | 首测实现 / 测试 / 配置 |
| `engineering/client-sdk/client.js` | 首测实现 / 测试 / 配置 |
| `engineering/contracts/fixtures/entity-invalid-number.json` | 机器契约 / 样例 / 依赖证据 |
| `engineering/contracts/fixtures/entity-valid.json` | 机器契约 / 样例 / 依赖证据 |
| `engineering/contracts/fixtures/room-initial.json` | 机器契约 / 样例 / 依赖证据 |
| `engineering/contracts/messages.json` | 机器契约 / 样例 / 依赖证据 |
| `engineering/contracts/models.json` | 机器契约 / 样例 / 依赖证据 |
| `engineering/contracts/operations.json` | 机器契约 / 样例 / 依赖证据 |
| `engineering/contracts/README.md` | 工程运行与验收文档 |
| `engineering/data-management/onlinecoc_data/__init__.py` | 首测实现 / 测试 / 配置 |
| `engineering/data-management/onlinecoc_data/ports.py` | 首测实现 / 测试 / 配置 |
| `engineering/data-management/onlinecoc_data/store.py` | 首测实现 / 测试 / 配置 |
| `engineering/data-management/pyproject.toml` | 首测实现 / 测试 / 配置 |
| `engineering/dependency-manifest.json` | 机器契约 / 样例 / 依赖证据 |
| `engineering/requirements-dev.lock` | 依赖精确版本及安装包摘要 |
| `engineering/requirements-runtime.lock` | 依赖精确版本及安装包摘要 |
| `engineering/rulepacks/demo/attack.lua` | 首测实现 / 测试 / 配置 |
| `engineering/rulepacks/demo/check-library.lua` | 首测实现 / 测试 / 配置 |
| `engineering/rulepacks/demo/damage-library.lua` | 首测实现 / 测试 / 配置 |
| `engineering/rulepacks/demo/damage.lua` | 首测实现 / 测试 / 配置 |
| `engineering/rulepacks/demo/environment.json` | 机器契约 / 样例 / 依赖证据 |
| `engineering/rulepacks/demo/environment.lua` | 首测实现 / 测试 / 配置 |
| `engineering/rulepacks/demo/README.md` | 工程运行与验收文档 |
| `engineering/rulepacks/demo/rules.lua` | 首测实现 / 测试 / 配置 |
| `engineering/rulepacks/demo/ruling.lua` | 首测实现 / 测试 / 配置 |
| `engineering/rulepacks/demo/timed.lua` | 首测实现 / 测试 / 配置 |
| `engineering/rulepacks/demo/transfer-library.lua` | 首测实现 / 测试 / 配置 |
| `engineering/rulepacks/demo/transfer.lua` | 首测实现 / 测试 / 配置 |
| `engineering/test-console/app.js` | 首测实现 / 测试 / 配置 |
| `engineering/test-console/index.html` | 首测实现 / 测试 / 配置 |
| `engineering/test-console/style.css` | 首测实现 / 测试 / 配置 |
| `docs/current/engineering/first-test-acceptance.md` | 首测验收文档 / 证据 / 驱动 |
| `engineering/acceptance/offline_server.py` | 首测验收文档 / 证据 / 驱动 |
| `engineering/acceptance/results-2026-10-30.json` | 首测验收文档 / 证据 / 驱动 |
| `docs/current/engineering/desktop-tools.md` | Windows 安装/启动工具、配置、测试或更新问题文档 |
| `docs/plans/Issues/issue-template.md` | Windows 安装/启动工具、配置、测试或更新问题文档 |
| `docs/plans/Issues/README.md` | Windows 安装/启动工具、配置、测试或更新问题文档 |
| `engineering/desktop/build-info.json` | Windows 安装/启动工具、配置、测试或更新问题文档 |
| `engineering/desktop/build.ps1` | Windows 安装/启动工具、配置、测试或更新问题文档 |
| `engineering/desktop/desktop_host.py` | Windows 安装/启动工具、配置、测试或更新问题文档 |
| `engineering/desktop/DesktopTools.cs` | Windows 安装/启动工具、配置、测试或更新问题文档 |
| `engineering/desktop/README.md` | Windows 安装/启动工具、配置、测试或更新问题文档 |
| `engineering/desktop/tests/test_desktop.py` | Windows 安装/启动工具、配置、测试或更新问题文档 |
| `engineering/desktop/verify_environment.py` | Windows 安装/启动工具、配置、测试或更新问题文档 |
| `launcher-config.json` | Windows 安装/启动工具、配置、测试或更新问题文档 |
| `启动OnlineCOC.exe` | Windows 安装/启动工具、配置、测试或更新问题文档 |
| `安装依赖.exe` | Windows 安装/启动工具、配置、测试或更新问题文档 |
| `docs/plans/Issues/issue-002-desktop-interaction-validation.md` | 桌面工具验收记录或后续问题 |
| `engineering/desktop/acceptance-results.json` | 桌面工具验收记录或后续问题 |
| `engineering/backend/src/onlinecoc/chat.py` | 聊天室领域模型、权限、分页及操作 |
| `engineering/backend/tests/test_chat.py` | 聊天室数据/权限/恢复/故障测试 |
| `engineering/backend/tests/test_chat_network.py` | 聊天室 SDK 与真实浏览器联机验收 |
| `docs/current/engineering/chat-backend.md` | 当前聊天室后端、模型、接口及约束 |
| `engineering/acceptance/chat-results-2026-10-30.json` | 聊天室追加与完整回归的机器验收摘要 |

本次配置包实际新增文件：

| 实际文件 | 用途 |
| --- | --- |
| `rulepacks/mini-detective-pack/.gitignore` | 配置包清单／启动或忽略配置 |
| `rulepacks/mini-detective-pack/config/configurations.json` | 本包场景／对象配置 |
| `rulepacks/mini-detective-pack/config/scenario.json` | 本包场景／对象配置 |
| `rulepacks/mini-detective-pack/docs/implementation.md` | 本包当前实现与运行说明 |
| `rulepacks/mini-detective-pack/manifest.json` | 配置包清单／启动或忽略配置 |
| `rulepacks/mini-detective-pack/rules/advance.lua` | 本包Lua权威规则 |
| `rulepacks/mini-detective-pack/rules/check.lua` | 本包Lua权威规则 |
| `rulepacks/mini-detective-pack/rules/combat.lua` | 本包Lua权威规则 |
| `rulepacks/mini-detective-pack/rules/confirm.lua` | 本包Lua权威规则 |
| `rulepacks/mini-detective-pack/rules/consume.lua` | 本包Lua权威规则 |
| `rulepacks/mini-detective-pack/rules/damage.lua` | 本包Lua权威规则 |
| `rulepacks/mini-detective-pack/rules/enter.lua` | 本包Lua权威规则 |
| `rulepacks/mini-detective-pack/rules/equip.lua` | 本包Lua权威规则 |
| `rulepacks/mini-detective-pack/rules/finish.lua` | 本包Lua权威规则 |
| `rulepacks/mini-detective-pack/rules/profile.lua` | 本包Lua权威规则 |
| `rulepacks/mini-detective-pack/rules/request.lua` | 本包Lua权威规则 |
| `rulepacks/mini-detective-pack/rules/resolve.lua` | 本包Lua权威规则 |
| `rulepacks/mini-detective-pack/rules/sync.lua` | 本包Lua权威规则 |
| `rulepacks/mini-detective-pack/start.ps1` | 配置包清单／启动或忽略配置 |
| `rulepacks/mini-detective-pack/tests/README.md` | 包级验收驱动／机器结果 |
| `rulepacks/mini-detective-pack/tests/results.json` | 包级验收驱动／机器结果 |
| `rulepacks/mini-detective-pack/tests/run_ui.py` | 包级验收驱动／机器结果 |
| `rulepacks/mini-detective-pack/tests/ui-results.json` | 包级验收驱动／机器结果 |
| `rulepacks/mini-detective-pack/tests/verify_package.py` | 包级验收驱动／机器结果 |
| `rulepacks/mini-detective-pack/tests/verify_ui.py` | 包级验收驱动／机器结果 |
| `rulepacks/mini-detective-pack/tools/client.py` | 包侧公开CLI／HTTP启动与适配工具 |
| `rulepacks/mini-detective-pack/tools/launch.py` | 包侧公开CLI／HTTP启动与适配工具 |
| `rulepacks/mini-detective-pack/tools/package.py` | 包侧公开CLI／HTTP启动与适配工具 |
| `rulepacks/mini-detective-pack/ui/app.js` | 本机单标签KP／PL前端 |
| `rulepacks/mini-detective-pack/ui/index.html` | 本机单标签KP／PL前端 |
| `rulepacks/mini-detective-pack/ui/styles.css` | 本机单标签KP／PL前端 |
| `docs/plans/Issues/issue-004-mini-pack-management.md` | 配置包在线恢复与组合管理接口边界 |

账号原生入口新增文件：

| 实际文件 | 用途 |
| --- | --- |
| `rulepacks/mini-detective-pack/KP主持人.exe` | 预设账号Windows原生入口 |
| `rulepacks/mini-detective-pack/PL1观察员.exe` | 预设账号Windows原生入口 |
| `rulepacks/mini-detective-pack/PL2护卫.exe` | 预设账号Windows原生入口 |
| `rulepacks/mini-detective-pack/PL3文献员.exe` | 预设账号Windows原生入口 |
| `rulepacks/mini-detective-pack/PL4医护员.exe` | 预设账号Windows原生入口 |
| `rulepacks/mini-detective-pack/tests/launcher-results.json` | 账号启动器源码、构建、说明或验收 |
| `rulepacks/mini-detective-pack/tests/verify_account_launchers.py` | 账号启动器源码、构建、说明或验收 |
| `rulepacks/mini-detective-pack/tools/AccountLauncher.cs` | 账号启动器源码、构建、说明或验收 |
| `rulepacks/mini-detective-pack/tools/build-launchers.ps1` | 账号启动器源码、构建、说明或验收 |
| `rulepacks/mini-detective-pack/tools/launcher-build.json` | 账号启动器源码、构建、说明或验收 |
| `rulepacks/mini-detective-pack/tools/README.md` | 账号启动器源码、构建、说明或验收 |

生成目录：`rulepacks/mini-detective-pack/runtime/` 为独立游玩数据，含 `room/` 宿主存档、`room-automation/` 自动化队列与凭据及停服备份，`rulepacks/mini-detective-pack/tests/output/` 为隔离测试存档、日志和截图，均忽略且不逐文件登记，仍受对应施工范围约束。`rulepacks/lasers-and-feelings/runtime/` 为独立游玩存档，`rulepacks/lasers-and-feelings/exports/` 为导出 ZIP；均不入库且不逐文件登记。`rulepacks/lasers-and-feelings/tests/output/` 存放配置包的独立实验存档、日志与接口发现结果，不入库、不逐文件登记，仍受对应施工范围约束。`engineering/.venv/` 是依赖环境；`engineering/.runtime/` 存放游玩数据、桌面工具的独立 Python/环境、缓存及日志；`engineering/.test-output/` 存放隔离测试、离线 wheel、截图与报告；Python/pytest 缓存不登记逐文件清单。生成目录仍受其父目录施工占用约束。

本次自动化与界面新增文件：

| 实际文件 | 用途 |
| --- | --- |
| `rulepacks/mini-detective-pack/tools/scene.py` | 当前场景、可达出口及逐PL已探索／一跳周边地图投影 |
| `rulepacks/mini-detective-pack/tools/automation.py` | KP自动处理总开关、固定行动验证、恢复及人工裁决 |
| `rulepacks/mini-detective-pack/ui/workflow.js` | KP／PL分区导航、顶部自动开关和中文结果呈现 |
| `rulepacks/mini-detective-pack/docs/automation-and-ui.md` | 当前自动化、导航、Mermaid、权限及升级说明 |
| `rulepacks/mini-detective-pack/tests/verify_automation.py` | 真实宿主与桌面浏览器自动化专项 |
| `rulepacks/mini-detective-pack/tests/automation-results.json` | 自动化专项机器结果 |

## Python 独立桌面房间管理器与 LAN 模块

| 实际文件 | 用途 |
| --- | --- |
| `docs/current/engineering/room-manager.md` | 当前设计、后续计划或 WinForms 阶段归档 |
| `docs/current/engineering/network-lan.md` | 当前设计、后续计划或 WinForms 阶段归档 |
| `docs/plans/room-manager-design.md` | 当前设计、后续计划或 WinForms 阶段归档 |
| `docs/plans/room-manager-construction-plan.md` | 当前设计、后续计划或 WinForms 阶段归档 |
| `docs/history/2026-11-09-room-manager.md` | 当前设计、后续计划或 WinForms 阶段归档 |
| `docs/history/2026-11-09-room-manager-design.md` | 当前设计、后续计划或 WinForms 阶段归档 |
| `docs/history/2026-11-09-room-manager-construction-plan.md` | 当前设计、后续计划或 WinForms 阶段归档 |
| `engineering/network-lan/.gitignore` | 独立 LAN 网关、CLI、GUI 或运行依赖说明 |
| `engineering/network-lan/README.md` | 独立 LAN 网关、CLI、GUI 或运行依赖说明 |
| `engineering/network-lan/pyproject.toml` | 独立 LAN 网关、CLI、GUI 或运行依赖说明 |
| `engineering/network-lan/requirements.lock` | 独立 LAN 网关、CLI、GUI 或运行依赖说明 |
| `engineering/network-lan/src/onlinecoc_lan/__init__.py` | 独立 LAN 网关、CLI、GUI 或运行依赖说明 |
| `engineering/network-lan/src/onlinecoc_lan/__main__.py` | 独立 LAN 网关、CLI、GUI 或运行依赖说明 |
| `engineering/network-lan/src/onlinecoc_lan/gateway.py` | 独立 LAN 网关、CLI、GUI 或运行依赖说明 |
| `engineering/network-lan/src/onlinecoc_lan/gui.py` | 独立 LAN 网关、CLI、GUI 或运行依赖说明 |
| `tools/room-manager/.gitignore` | 构建、启动或依赖配置 |
| `tools/room-manager/README.md` | 当前使用、开发或验收说明 |
| `tools/room-manager/build.ps1` | 构建、启动或依赖配置 |
| `tools/room-manager/build.py` | 构建、启动或依赖配置 |
| `tools/room-manager/dist/RoomManager/_internal/` | 独立发布程序附带的 Python 运行时与依赖；不逐文件登记 |
| `tools/room-manager/dist/RoomManager/README.txt` | Python 独立发布程序、依赖锁或摘要 |
| `tools/room-manager/dist/RoomManager/RoomManager.exe` | Python 独立发布程序、依赖锁或摘要 |
| `tools/room-manager/dist/RoomManager/release.json` | Python 独立发布程序、依赖锁或摘要 |
| `tools/room-manager/dist/RoomManager/requirements-runtime.lock` | Python 独立发布程序、依赖锁或摘要 |
| `tools/room-manager/docs/acceptance.md` | 当前使用、开发或验收说明 |
| `tools/room-manager/docs/development.md` | 当前使用、开发或验收说明 |
| `tools/room-manager/docs/screenshots/lan-panel.png` | 真实 Python 原生窗口验收截图 |
| `tools/room-manager/docs/screenshots/manager.png` | 真实 Python 原生窗口验收截图 |
| `tools/room-manager/docs/usage.md` | 当前使用、开发或验收说明 |
| `tools/room-manager/legacy/winforms/README.md` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/app.manifest` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/build.ps1` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/dependency-manifest.json` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/dist/README.txt` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/dist/RoomManager.exe` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/dist/RoomManager.exe.config` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/dist/contract-baseline.json` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/dist/dependency-manifest.json` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/dist/release.json` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/dist/source-sha256.txt` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/dist/tool-config.json` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/docs/acceptance.md` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/docs/development.md` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/docs/screenshots/editing.png` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/docs/screenshots/large-list.png` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/docs/screenshots/observation.png` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/docs/usage.md` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/src/LocalSettings/Options.cs` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/src/LocalSettings/Settings.cs` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/src/Observation/Observer.cs` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/src/Program.cs` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/src/Protocol/ApiClient.cs` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/src/Protocol/Json.cs` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/src/Protocol/Validate.cs` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/src/UI/MainForm.cs` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/tests/GuiSmoke.cs` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/tests/Integration.cs` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/tests/ProtocolEdges.cs` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/tests/Reconnect.cs` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/tests/contract-baseline.json` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/tests/results.json` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/tests/run.py` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/legacy/winforms/tool-config.json` | 旧 WinForms 实现、发布或验收归档，非现行入口 |
| `tools/room-manager/manager.py` | Python 管理器源码与入口 |
| `tools/room-manager/python/room_manager/__init__.py` | Python 管理器源码与入口 |
| `tools/room-manager/python/room_manager/gui.py` | Python 管理器源码与入口 |
| `tools/room-manager/python/room_manager/protocol.py` | Python 管理器源码与入口 |
| `tools/room-manager/python/room_manager/state.py` | Python 管理器源码与入口 |
| `tools/room-manager/requirements-build.lock` | 构建、启动或依赖配置 |
| `tools/room-manager/requirements-runtime.lock` | 构建、启动或依赖配置 |
| `tools/room-manager/start.cmd` | 构建、启动或依赖配置 |
| `tools/room-manager/tests/distribution-results.json` | Python/LAN/发布验证脚本或机器结果 |
| `tools/room-manager/tests/python-results.json` | Python/LAN/发布验证脚本或机器结果 |
| `tools/room-manager/tests/verify_distribution.py` | Python/LAN/发布验证脚本或机器结果 |
| `tools/room-manager/tests/verify_python.py` | Python/LAN/发布验证脚本或机器结果 |

`tools/room-manager/dist/RoomManager/_internal/` 为 PyInstaller 生成的 Python、Tk 与第三方运行依赖，随整个 RoomManager 目录复制，不逐文件登记；不能只复制 exe。

`rulepacks/investigation-vtt-reference/temp/` 为参考资料的临时解压目录，已忽略，可从原始 ZIP 重建。树桩镇只忽略包根目录的 `runtime*/` 游玩数据，`assets/runtime/` 为实际界面素材，随版本入库。

`tools/room-manager/.venv/` 为独立开发依赖环境，`.build/` 为构建中间文件和缓存，`.test-output/` 为隔离宿主、临时发布副本、日志与截图，均已忽略且不属于发布内容。Python 的 `__pycache__/` 为缓存。这些目录仍受各自父目录占用约束；使用者设置位于用户目录，测试以 `--settings-dir` 指向隔离目录。

首次准备回归新增文件（2026-11-05）：

| 实际文件 | 用途 |
| --- | --- |
| `rulepacks/mini-detective-pack/tests/verify_first_setup.py` | 新设备／空目录首次准备、五账号和密码认证回归 |
| `rulepacks/mini-detective-pack/tests/first-setup-results.json` | 首次准备及认证回归机器结果 |
| `docs/history/2026-11-05-issue-005-online-account-management.md` | 已完成的主机账号维护 Issue 与决策记录 |

主机账号工具新增文件（2026-11-05）：

| 实际文件 | 用途 |
| --- | --- |
| `engineering/backend/src/onlinecoc/host_control.py` | 本机主机授权、DPAPI 与实例发现记录 |
| `engineering/contracts/host-control.json` | 独立主机控制接口契约 |
| `docs/current/engineering/host-accounts.md` | 当前本机账号维护权限、接口和验证说明 |
| `tools/host-accounts/.gitignore` | 工程外账号管理工具、源码、构建或验证证据 |
| `tools/host-accounts/build-info.json` | 工程外账号管理工具、源码、构建或验证证据 |
| `tools/host-accounts/build.ps1` | 工程外账号管理工具、源码、构建或验证证据 |
| `tools/host-accounts/HostAccounts.cs` | 工程外账号管理工具、源码、构建或验证证据 |
| `tools/host-accounts/HostAccounts.exe` | 工程外账号管理工具、源码、构建或验证证据 |
| `tools/host-accounts/README.md` | 工程外账号管理工具、源码、构建或验证证据 |
| `tools/host-accounts/results.json` | 工程外账号管理工具、源码、构建或验证证据 |
| `tools/host-accounts/verify.py` | 工程外账号管理工具、源码、构建或验证证据 |

`tools/host-accounts/.test-output/` 保存隔离实例、发现记录、临时账号、后端回归及日志，不入库、不属于发行内容；测试不会修改实际服务器存档。运行中的主机发现记录位于用户目录 `%LOCALAPPDATA%/OnlineCOC/HostControl/`，包含当前用户加密管理凭据，不入库、不进入配置包导出。

配置包服务管理器新增文件（2026-11-05）：

| 实际文件 | 用途 |
| --- | --- |
| `rulepacks/mini-detective-pack/配置包服务管理.exe` | 独立本机服务启动、停止、重启与状态窗口 |
| `rulepacks/mini-detective-pack/tools/ServiceManager.cs` | 原生服务管理器与实例／进程身份核对 |
| `rulepacks/mini-detective-pack/tools/build-service-manager.ps1` | 服务管理器构建脚本 |
| `rulepacks/mini-detective-pack/tools/service-manager-build.json` | 服务管理器源码、exe摘要及构建记录 |
| `rulepacks/mini-detective-pack/tests/verify_service_manager.py` | 实际原生管理器与隔离进程生命周期验收 |
| `rulepacks/mini-detective-pack/tests/service-manager-results.json` | 原生服务管理器验收结果 |

## 树桩镇界面设计资料（2026-11-09）

| 实际文件 | 用途 |
| --- | --- |
| `rulepacks/stumpsville/assets/references/original-stumpsville-preview.jpg` | 官方树桩镇公开预览，仅供美术研究 |
| `rulepacks/stumpsville/assets/references/README.md` | 树桩镇界面设计、导航、组成树、来源或索引 |
| `rulepacks/stumpsville/assets/ui-design/01-entry.png` | 树桩镇页面、子 UI 或组件美术设计板 |
| `rulepacks/stumpsville/assets/ui-design/02-player-scene.png` | 树桩镇页面、子 UI 或组件美术设计板 |
| `rulepacks/stumpsville/assets/ui-design/03-character-inventory.png` | 树桩镇页面、子 UI 或组件美术设计板 |
| `rulepacks/stumpsville/assets/ui-design/04-journals-records.png` | 树桩镇页面、子 UI 或组件美术设计板 |
| `rulepacks/stumpsville/assets/ui-design/05-gm-workbench.png` | 树桩镇页面、子 UI 或组件美术设计板 |
| `rulepacks/stumpsville/assets/ui-design/06-location-reveal.png` | 树桩镇页面、子 UI 或组件美术设计板 |
| `rulepacks/stumpsville/assets/ui-design/07-encounters.png` | 树桩镇页面、子 UI 或组件美术设计板 |
| `rulepacks/stumpsville/assets/ui-design/08-management.png` | 树桩镇页面、子 UI 或组件美术设计板 |
| `rulepacks/stumpsville/assets/ui-design/09-subui.png` | 树桩镇页面、子 UI 或组件美术设计板 |
| `rulepacks/stumpsville/assets/ui-design/10-system-states.png` | 树桩镇页面、子 UI 或组件美术设计板 |
| `rulepacks/stumpsville/assets/ui-design/prompts.json` | 内置 image_gen 提示词与图稿修订记录 |
| `rulepacks/stumpsville/assets/ui-design/README.md` | 树桩镇界面设计、导航、组成树、来源或索引 |
| `rulepacks/stumpsville/docs/plans/story-content-expansion.md` | 树桩镇故事、多路线目标、共享物品与动态描述及内容扩展计划 |
| `rulepacks/stumpsville/docs/plans/interface-design.md` | 树桩镇界面设计、导航、组成树、来源或索引 |
| `rulepacks/stumpsville/docs/plans/README.md` | 树桩镇界面设计、导航、组成树、来源或索引 |
| `rulepacks/stumpsville/README.md` | 树桩镇界面设计、导航、组成树、来源或索引 |
| `rulepacks/stumpsville/.gitignore` | 树桩镇独立配置包入口或清单 |
| `rulepacks/stumpsville/assets/runtime/courtyard.png` | 树桩镇原创运行插画与生成记录 |
| `rulepacks/stumpsville/assets/runtime/mouse.png` | 树桩镇原创运行插画与生成记录 |
| `rulepacks/stumpsville/assets/runtime/prompts.json` | 树桩镇原创运行插画与生成记录 |
| `rulepacks/stumpsville/assets/runtime/README.md` | 树桩镇原创运行插画与生成记录 |
| `rulepacks/stumpsville/assets/runtime/welcome.png` | 树桩镇原创运行插画与生成记录 |
| `rulepacks/stumpsville/config/configurations.json` | 树桩镇配置与场景资料 |
| `rulepacks/stumpsville/config/game.json` | 树桩镇配置与场景资料 |
| `rulepacks/stumpsville/docs/current/content-configuration.md` | 树桩镇随包默认地点、角色、物品、行动与未填内容的精简概览 |
| `rulepacks/stumpsville/docs/current/implementation.md` | 树桩镇当前使用、实现与来源文档 |
| `rulepacks/stumpsville/docs/current/README.md` | 树桩镇当前使用、实现与来源文档 |
| `rulepacks/stumpsville/docs/current/sources.md` | 树桩镇当前使用、实现与来源文档 |
| `rulepacks/stumpsville/docs/current/usage.md` | 树桩镇当前使用、实现与来源文档 |
| `rulepacks/stumpsville/docs/current/player-guide.md` | 树桩镇玩家简明指南、探路取物推荐目标、基本规则及原型来源 |
| `rulepacks/stumpsville/docs/README.md` | 树桩镇当前使用、实现与来源文档 |
| `rulepacks/stumpsville/manifest.json` | 树桩镇独立配置包入口或清单 |
| `rulepacks/stumpsville/rules/check.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/create.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/damage.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/generate.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/grant.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/inventory.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/layout.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/morale.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/profile.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/ready.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/remove.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/rest.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/transfer.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/travel.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/rules/world.lua` | 树桩镇宿主 Lua 规则 |
| `rulepacks/stumpsville/start.cmd` | 树桩镇Python房间面板的本机预设入口 |
| `rulepacks/stumpsville/start-panel.cmd` | pythonw双击启动统一房间管理面板，无持续控制台 |
| `rulepacks/stumpsville/tools/panel.py` | Python/Tk启动管理、联机/AI选择、最小化、地址/日志和关闭房间 |
| `rulepacks/stumpsville/tools/processes.py` | 仅托管本次子进程树；Windows Job关闭清理、初始化/导出包装 |
| `rulepacks/stumpsville/tests/verify_panel.py` | 原生面板与六入口、正常/异常退出、同档重启及本地网页撤销专项 |
| `rulepacks/stumpsville/tests/panel-results.json` | Python面板及进程生命周期6组隔离验收结果 |
| `rulepacks/stumpsville/start.ps1` | 树桩镇独立配置包入口或清单 |
| `rulepacks/stumpsville/tests/harness.py` | 树桩镇隔离真实宿主或浏览器验收 |
| `rulepacks/stumpsville/tests/package-results.json` | 树桩镇隔离真实宿主或浏览器验收 |
| `rulepacks/stumpsville/tests/probe_host.py` | 树桩镇隔离真实宿主或浏览器验收 |
| `rulepacks/stumpsville/tests/README.md` | 树桩镇隔离真实宿主或浏览器验收 |
| `rulepacks/stumpsville/tests/ui-results.json` | 树桩镇隔离真实宿主或浏览器验收 |
| `rulepacks/stumpsville/tests/verify_package.py` | 树桩镇隔离真实宿主或浏览器验收 |
| `rulepacks/stumpsville/tests/verify_ui.py` | 树桩镇隔离真实宿主或浏览器验收 |
| `rulepacks/stumpsville/tools/client.py` | 树桩镇公开接口适配与启动工具 |
| `rulepacks/stumpsville/tools/launch.py` | 树桩镇公开接口适配与启动工具 |
| `rulepacks/stumpsville/tools/package.py` | 树桩镇公开接口适配与启动工具 |
| `rulepacks/stumpsville/ui/app.js` | 树桩镇可交互页面与样式 |
| `rulepacks/stumpsville/ui/index.html` | 树桩镇可交互页面与样式 |
| `rulepacks/stumpsville/ui/styles.css` | 树桩镇可交互页面与样式 |

`rulepacks/stumpsville/runtime*/` 为本包独立游玩或恢复存档，`rulepacks/stumpsville/tests/output/` 为隔离验收存档、日志和截图；两者不逐文件登记且不入库。
| `rulepacks/stumpsville/tests/verify_launcher.py` | 树桩镇保留的start.ps1命令行入口回归验收 |
| `rulepacks/stumpsville/tests/launcher-results.json` | 树桩镇Windows PowerShell 5.1命令行入口5项验收结果 |
| `rulepacks/stumpsville/rules/adjudicate.lua` | 树桩镇自动裁决规则及主持内部结算 |
| `rulepacks/stumpsville/rules/auto-travel.lua` | 树桩镇自动裁决规则及主持内部结算 |
| `rulepacks/stumpsville/rules/automation.lua` | 树桩镇自动裁决规则及主持内部结算 |
| `rulepacks/stumpsville/rules/check-core.lua` | 树桩镇自动裁决规则及主持内部结算 |
| `rulepacks/stumpsville/rules/inventory-core.lua` | 树桩镇自动裁决规则及主持内部结算 |
| `rulepacks/stumpsville/tests/automation-results.json` | 树桩镇自动裁决专项验收及机器结果 |
| `rulepacks/stumpsville/tests/verify_automation.py` | 树桩镇自动裁决专项验收及机器结果 |
| `rulepacks/stumpsville/docs/current/interface.md` | 树桩镇现行导航 Mermaid、悬浮面板与控制台功能树 |
| `rulepacks/stumpsville/tests/verify_feedback.py` | 树桩镇行动反馈、权限与恢复专项验收 |
| `rulepacks/stumpsville/tests/feedback-results.json` | 树桩镇持久行动反馈专项机器结果 |
| `rulepacks/stumpsville/config/scene-actions.json` | 树桩镇18个预设行动及固定做法定义 |
| `rulepacks/stumpsville/rules/scene.lua` | 树桩镇场景原子检定、资源与机关结算 |
| `rulepacks/stumpsville/tools/scenes.py` | 树桩镇有限库存映射及玩家可见场景事实 |
| `rulepacks/stumpsville/docs/current/scene-actions.md` | 树桩镇18个行动结果、自动队列导航及功能树 |
| `rulepacks/stumpsville/tests/verify_storm.py` | 暴雨三路线、替代做法、共享库存观察及重启验证 |
| `rulepacks/stumpsville/tests/verify_scenes.py` | 树桩镇全部预设、有限奖励和权限验收 |
| `rulepacks/stumpsville/tests/verify_scene_ui.py` | 树桩镇已有KP页面自动执行及玩家可见结果验收 |
| `rulepacks/stumpsville/tests/verify_scene_recovery.py` | 树桩镇场景升级、恢复与容量边界验收 |
| `rulepacks/stumpsville/tests/scene-results.json` | 树桩镇18个预设的8组机器验收结果 |
| `rulepacks/stumpsville/tests/scene-recovery-results.json` | 树桩镇场景恢复、无变化同步与权限边界6组机器结果 |
| `rulepacks/stumpsville/tests/scene-ui-results.json` | 树桩镇场景浏览器4组自动与人工闭环结果 |
| `rulepacks/stumpsville/start-lan.cmd` | 树桩镇可双击的局域网窗口入口 |
| `rulepacks/stumpsville/tools/lan.py` | 树桩镇网卡发现、端口选择、地址复制及本机服务生命周期 |
| `rulepacks/stumpsville/tests/verify_lan.py` | 树桩镇真实Tk窗口与局域网启动专项验收 |
| `rulepacks/stumpsville/tests/lan-results.json` | 树桩镇局域网启动10组机器验收结果 |

## 独立本地化工具实际文件（L10N-0）

| 实际文件 | 用途 |
| --- | --- |
| `tools/localization/.gitignore` | 独立工具依赖、类型和生成目录配置 |
| `tools/localization/.npmrc` | 独立工具依赖、类型和生成目录配置 |
| `tools/localization/README.md` | 独立本地化工具源码与包边界 |
| `tools/localization/docs/README.md` | 独立本地化当前工程文档与精选验收证据 |
| `tools/localization/docs/acceptance.md` | 独立本地化当前工程文档与精选验收证据 |
| `tools/localization/docs/architecture.md` | 独立本地化当前工程文档与精选验收证据 |
| `tools/localization/docs/evidence/l10n-0-formatter.png` | 独立本地化当前工程文档与精选验收证据 |
| `tools/localization/docs/evidence/l10n-0-gui.json` | 独立本地化当前工程文档与精选验收证据 |
| `tools/localization/docs/evidence/l10n-0-native.json` | 独立本地化当前工程文档与精选验收证据 |
| `tools/localization/docs/evidence/l10n-0.json` | 独立本地化当前工程文档与精选验收证据 |
| `tools/localization/package-lock.json` | 独立工具依赖、类型和生成目录配置 |
| `tools/localization/package.json` | 独立工具依赖、类型和生成目录配置 |
| `tools/localization/packages/cli/package.json` | 独立工具依赖、类型和生成目录配置 |
| `tools/localization/packages/cli/src/main.ts` | 独立本地化工具源码与包边界 |
| `tools/localization/packages/contracts/package.json` | 独立工具依赖、类型和生成目录配置 |
| `tools/localization/packages/contracts/src/index.ts` | 独立本地化工具源码与包边界 |
| `tools/localization/packages/core/package.json` | 独立工具依赖、类型和生成目录配置 |
| `tools/localization/packages/core/src/index.ts` | 独立本地化工具源码与包边界 |
| `tools/localization/packages/desktop/package.json` | 独立工具依赖、类型和生成目录配置 |
| `tools/localization/packages/desktop/src/main/index.ts` | 独立本地化工具源码与包边界 |
| `tools/localization/packages/desktop/src/preload/index.ts` | 独立本地化工具源码与包边界 |
| `tools/localization/packages/desktop/src/renderer/env.d.ts` | 独立本地化工具源码与包边界 |
| `tools/localization/packages/desktop/src/renderer/index.html` | 独立本地化工具源码与包边界 |
| `tools/localization/packages/desktop/src/renderer/main.tsx` | 独立本地化工具源码与包边界 |
| `tools/localization/packages/desktop/src/renderer/style.css` | 独立本地化工具源码与包边界 |
| `tools/localization/packages/messages/package.json` | 独立工具依赖、类型和生成目录配置 |
| `tools/localization/packages/messages/src/index.ts` | 独立本地化工具源码与包边界 |
| `tools/localization/packages/runtime/package.json` | 独立工具依赖、类型和生成目录配置 |
| `tools/localization/packages/runtime/src/index.ts` | 独立本地化工具源码与包边界 |
| `tools/localization/scripts/boundaries.mjs` | 独立构建、打包与检查脚本 |
| `tools/localization/scripts/build.mjs` | 独立构建、打包与检查脚本 |
| `tools/localization/scripts/package.mjs` | 独立构建、打包与检查脚本 |
| `tools/localization/scripts/prepare-runtime.ps1` | 独立构建、打包与检查脚本 |
| `tools/localization/scripts/report-l10n-0.mjs` | 独立构建、打包与检查脚本 |
| `tools/localization/tests/gui/native-dialog.mjs` | 独立消息及真实窗口验收驱动 |
| `tools/localization/tests/gui/smoke.mjs` | 独立消息及真实窗口验收驱动 |
| `tools/localization/tests/unit/messages.test.mjs` | 独立消息及真实窗口验收驱动 |
| `tools/localization/tsconfig.json` | 独立工具依赖、类型和生成目录配置 |
| `docs/current/engineering/localization.md` | 独立本地化工具已实现能力与阶段证据入口 |

`tools/localization/node_modules/`、`.cache/`、`build/`、`dist/`、`.test-output/` 为该工具自身依赖、缓存、构建、发行和隔离测试生成物，不逐文件登记、不入库。L10N-0 另将完整发行复制到 `%TEMP%/localizer-isolation-20261112-a91c/` 做仓库外启动测试；该目录不含游戏数据。

<!-- ai-runtime:files:start -->

| 实际文件 | 用途 |
| --- | --- |
| `docs/current/engineering/ai-runtime.md` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/acceptance/ai-runtime/ai-0.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/acceptance/ai-runtime/ai-0.xml` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/acceptance/ai-runtime/ai-1-gameplay.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/acceptance/ai-runtime/ai-1-host.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/acceptance/ai-runtime/ai-1-host.xml` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/acceptance/ai-runtime/ai-1.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/acceptance/ai-runtime/ai-1.xml` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/acceptance/ai-runtime/ai-2-all.xml` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/acceptance/ai-runtime/ai-2-lock.xml` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/acceptance/ai-runtime/ai-2.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/acceptance/ai-runtime/ai-2.xml` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/.gitignore` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/examples/ai-providers.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/examples/bonus-15.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/pyproject.toml` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/README.md` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/scripts/record_stage.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/scripts/run.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/__init__.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/cli.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/contracts.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/errors.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/pack.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/policy.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/proposals.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/repository.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/sandbox.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/validation/__init__.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/validation/base.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/validation/common.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/validation/gameplay.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/src/onlinecoc_ai/validation/rules.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/conftest.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/contracts-invalid.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/contracts-valid.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/digest-vectors.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/ai/checks.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/ai/contract.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/ai/fixtures/invalid-bonus.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/ai/fixtures/invalid-charges.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/ai/fixtures/valid-bonus.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/ai/fixtures/valid-charges.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/ai/fixtures/world.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/ai/metrics.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/ai/review-checklist.md` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/ai/scenarios/exhaustion.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/ai/scenarios/token.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/ai/scenarios/wrong-owner.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/ai/schemas/tuning.schema.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/config/configurations.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/config/tuning.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/docs/rules.md` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/manifest.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/fixtures/pack/rules/check.lua` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/test_base.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/test_contracts.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/test_gameplay.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/test_pack_rules.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/ai/tests/test_sandbox.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/backend/src/onlinecoc/ai_contracts.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/backend/src/onlinecoc/publication.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/backend/src/onlinecoc/room_lifecycle.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/backend/src/onlinecoc/worker_entry.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/backend/src/onlinecoc/worker_process.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/backend/tests/ai_helpers.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/backend/tests/test_ai_approval.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/backend/tests/test_ai_backup.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/backend/tests/test_ai_publication.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/backend/tests/test_ai_recovery.py` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |
| `engineering/contracts/ai.json` | 房间 AI 契约、模块、共同执行器、夹具或验收证据 |

engineering/ai/.test-output/ 和 __pycache__/ 为隔离测试/缓存，不逐文件登记，不用于真实游玩。
| `engineering/ai/config/ai-providers.json` | AI 服务商、任务编排、测试或阶段证据 |
| `engineering/ai/tests/test_coordinator.py` | AI 服务商、任务编排、测试或阶段证据 |
| `engineering/ai/tests/test_providers.py` | AI 服务商、任务编排、测试或阶段证据 |
| `engineering/ai/src/onlinecoc_ai/coordinator.py` | AI 服务商、任务编排、测试或阶段证据 |
| `engineering/ai/src/onlinecoc_ai/profiles.py` | AI 服务商、任务编排、测试或阶段证据 |
| `engineering/ai/src/onlinecoc_ai/runtime.py` | AI 服务商、任务编排、测试或阶段证据 |
| `engineering/ai/src/onlinecoc_ai/providers/base.py` | AI 服务商、任务编排、测试或阶段证据 |
| `engineering/ai/src/onlinecoc_ai/providers/compatible.py` | AI 服务商、任务编排、测试或阶段证据 |
| `engineering/ai/src/onlinecoc_ai/providers/deepseek.py` | AI 服务商、任务编排、测试或阶段证据 |
| `engineering/ai/src/onlinecoc_ai/providers/transport.py` | AI 服务商、任务编排、测试或阶段证据 |
| `engineering/ai/src/onlinecoc_ai/providers/__init__.py` | AI 服务商、任务编排、测试或阶段证据 |
| `engineering/acceptance/ai-runtime/ai-3.json` | AI 服务商、任务编排、测试或阶段证据 |
| `engineering/acceptance/ai-runtime/ai-3.xml` | AI 服务商、任务编排、测试或阶段证据 |
| `engineering/backend/src/onlinecoc/ai_sources.py` | AI 授权上下文、持久记忆、契约或验收 |
| `engineering/ai/src/onlinecoc_ai/context.py` | AI 授权上下文、持久记忆、契约或验收 |
| `engineering/ai/src/onlinecoc_ai/memory.py` | AI 授权上下文、持久记忆、契约或验收 |
| `engineering/ai/tests/test_context.py` | AI 授权上下文、持久记忆、契约或验收 |
| `engineering/ai/tests/test_memory.py` | AI 授权上下文、持久记忆、契约或验收 |
| `engineering/acceptance/ai-runtime/ai-4.json` | AI 授权上下文、持久记忆、契约或验收 |
| `engineering/acceptance/ai-runtime/ai-4.xml` | AI 授权上下文、持久记忆、契约或验收 |
| `engineering/contracts/ai-operations.json` | AI 授权上下文、持久记忆、契约或验收 |
| `engineering/ai/tests/test_entrypoints.py` | AI 接口、测试或阶段验收证据 |
| `engineering/ai/tests/test_ui.py` | AI 接口、测试或阶段验收证据 |
| `engineering/ai/tests/ui_server.py` | AI 接口、测试或阶段验收证据 |
| `engineering/ai/src/onlinecoc_ai/api.py` | AI 接口、测试或阶段验收证据 |
| `engineering/acceptance/ai-runtime/ai-5-browser.json` | AI 接口、测试或阶段验收证据 |
| `engineering/acceptance/ai-runtime/ai-5.json` | AI 接口、测试或阶段验收证据 |
| `engineering/acceptance/ai-runtime/ai-5.xml` | AI 接口、测试或阶段验收证据 |
| `engineering/backend/src/onlinecoc/ai_api.py` | AI HTTP 接线或 KP 审核面板 |
| `engineering/test-console/ai.js` | AI HTTP 接线或 KP 审核面板 |
| `engineering/ai/tests/test_pilot.py` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/acceptance/ai-runtime/acceptance-summary.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/acceptance/ai-runtime/ai-6-cli.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/acceptance/ai-runtime/ai-6-demo-report.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/acceptance/ai-runtime/ai-6-final-context.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/acceptance/ai-runtime/ai-6-final-context.xml` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/acceptance/ai-runtime/ai-6-pilot.xml` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/acceptance/ai-runtime/ai-6-privacy.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/acceptance/ai-runtime/ai-6-privacy.xml` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/acceptance/ai-runtime/ai-6.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/acceptance/ai-runtime/ai-6.xml` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/checks.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/configurations.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/contract.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/environment.schema.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/examples/skill-10.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/examples/skill-15.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/fixtures/existing-world.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/fixtures/invalid-value.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/fixtures/new-world.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/fixtures/valid-value.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/manifest.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/metrics.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/review-checklist.md` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/rules.md` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/scenarios/existing-skill.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/scenarios/new-skill.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/rulepacks/demo/ai/scenarios/wrong-owner.json` | AI 实际 demo 材料、实现或最终验收证据 |
| `engineering/ai/scripts/live_deepseek.py` | DeepSeek 真实联调脚本、诊断或回归验收证据 |
| `engineering/acceptance/ai-runtime/deepseek-live-attempt-1.json` | DeepSeek 真实联调脚本、诊断或回归验收证据 |
| `engineering/acceptance/ai-runtime/deepseek-live-attempt-2.json` | DeepSeek 真实联调脚本、诊断或回归验收证据 |
| `engineering/acceptance/ai-runtime/deepseek-live-attempt-3.json` | DeepSeek 真实联调脚本、诊断或回归验收证据 |
| `engineering/acceptance/ai-runtime/deepseek-live.json` | DeepSeek 真实联调脚本、诊断或回归验收证据 |
| `engineering/acceptance/ai-runtime/deepseek-regression.json` | DeepSeek 真实联调脚本、诊断或回归验收证据 |
| `engineering/acceptance/ai-runtime/deepseek-regression.xml` | DeepSeek 真实联调脚本、诊断或回归验收证据 |
<!-- ai-runtime:files:end -->
| `rulepacks/stumpsville/tools/chat.py` | 场景／队伍聊天的持久消息与实时位置权限 |
| `rulepacks/stumpsville/ui/chat.js` | 场景常驻聊天、管理台浮窗、多私聊与草稿隔离 |
| `rulepacks/stumpsville/ui/i18n.js` | 本包TextRef消费适配、语言切换与缺译回退 |
| `rulepacks/stumpsville/ui/messageformat.js` | 固定intl-messageformat 12.1.5浏览器消息解析依赖 |
| `rulepacks/stumpsville/ui/messageformat-LICENSE.md` | 随包消息解析器及依赖许可 |
| `rulepacks/stumpsville/localization.project.json` | 本地化作者项目契约 |
| `rulepacks/stumpsville/locales/zh-CN/ui.json` | 简体中文UI源词条 |
| `rulepacks/stumpsville/locales/en/ui.json` | 英文UI译文 |
| `rulepacks/stumpsville/locales/meta/catalog/ui.json` | UI词条参数与分发目录 |
| `rulepacks/stumpsville/docs/current/localization.md` | 本包本地化接入与现行覆盖边界 |
| `rulepacks/stumpsville/tests/verify_workspace.py` | KP独立PL视窗、聊天权限与本地化验收 |
| `rulepacks/stumpsville/tests/workspace-results.json` | 工作区0.5.0六组真实宿主和浏览器验收结果 |
| `rulepacks/stumpsville/tools/localization.py` | 仅翻译授权响应副本的受限场景内容适配器 |
| `rulepacks/stumpsville/locales/zh-CN/content.json` | 受限场景与系统结果中文词条 |
| `rulepacks/stumpsville/locales/en/content.json` | 受限场景与系统结果英文词条 |
| `rulepacks/stumpsville/locales/meta/catalog/content.json` | 受限词条语境、数字参数与分发分类 |
| `rulepacks/stumpsville/tests/verify_player_layout.py` | PL常驻三栏、聊天/AI标签、可拖动线索日志浮窗及窄屏验收 |
| `rulepacks/stumpsville/tests/player-layout-results.json` | 玩家桌面布局5组真实宿主/浏览器验收结果 |
| `rulepacks/stumpsville/tests/verify_screen.py` | 一屏布局、行动与聊天、本地化和隐藏内容边界验收 |
| `rulepacks/stumpsville/tests/screen-results.json` | 一屏三栏0.6.0六组专项验收结果 |


## AI 独立管理器与嵌入组件（2026-11-13）

| 实际文件 | 用途 |
| --- | --- |
| `docs/current/engineering/ai-manager.md` | AI 管理器运行、权限、会话、嵌入与 API 当前说明 |
| `docs/plans/stumpsville-ai-integration.md` | Stumpsville AI 接入状态与剩余配置生成、发布和上下文工作 |
| `docs/plans/stumpsville-web-integration.md` | Stumpsville 网页联机调整草案：接口桥、沙箱 UI、按需资源及分期验收 |
| `engineering/acceptance/ai-runtime/manager-baseline.xml` | AI 管理器阶段验收报告或实际界面截图 |
| `engineering/acceptance/ai-runtime/manager-browser.json` | AI 管理器阶段验收报告或实际界面截图 |
| `engineering/acceptance/ai-runtime/manager-full.xml` | AI 管理器阶段验收报告或实际界面截图 |
| `engineering/acceptance/ai-runtime/manager-new.xml` | AI 管理器阶段验收报告或实际界面截图 |
| `engineering/acceptance/ai-runtime/manager-providers.png` | AI 管理器阶段验收报告或实际界面截图 |
| `engineering/acceptance/ai-runtime/manager-room-review.png` | AI 管理器阶段验收报告或实际界面截图 |
| `engineering/ai/scripts/manager.py` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/src/onlinecoc_ai/local_lock.py` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/src/onlinecoc_ai/manager.py` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/src/onlinecoc_ai/sessions.py` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/src/onlinecoc_ai/vault.py` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/start-manager.cmd` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/tests/manager_ui_server.py` | AI 管理器、会话权限、真实启动或浏览器验收 |
| `engineering/ai/tests/test_manager.py` | AI 管理器、会话权限、真实启动或浏览器验收 |
| `engineering/ai/tests/test_manager_cli.py` | AI 管理器、会话权限、真实启动或浏览器验收 |
| `engineering/ai/tests/test_manager_ui.py` | AI 管理器、会话权限、真实启动或浏览器验收 |
| `engineering/ai/tests/test_sessions.py` | AI 管理器、会话权限、真实启动或浏览器验收 |
| `engineering/ai/web/components/client.js` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/web/components/guard.js` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/web/components/index.d.ts` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/web/components/index.js` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/web/components/panel.css` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/web/components/providers.js` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/web/components/room-panel.js` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/web/components/sessions.js` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/web/manager/index.html` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/web/manager/manager.js` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/ai/web/manager/style.css` | 独立 AI 管理器、会话、组件或开发接口 |
| `engineering/acceptance/ai-runtime/manager.json` | AI 管理器完整/专项去重验收与最终源码摘要 |
| `engineering/acceptance/ai-runtime/manager-ui.json` | AI 管理器完整/专项去重验收与最终源码摘要 |
| `engineering/acceptance/ai-runtime/manager-ui.xml` | AI 管理器完整/专项去重验收与最终源码摘要 |
| `engineering/acceptance/ai-runtime/manager-final.xml` | AI 管理器验收结果 |

`engineering/ai/.manager/` 保存本机房间地址配置，已 Git 忽略；不保存房间密码。保险库默认位于 Windows 用户 LOCALAPPDATA/OnlineCOC/AI/credentials.json，不纳入项目目录或证据；测试使用 `.test-output/` 下的隔离保险库。Profile 与保险库的 `.lock` 文件用于并发锁，测试缓存、临时存档不逐项登记。

### 树桩镇可选模块接入

| 实际文件 | 用途 |
| --- | --- |
| `rulepacks/stumpsville/start-integrated.cmd` | 树桩镇 AI/P2P 可选模块双击入口 |
| `rulepacks/stumpsville/tools/integrations.py` | 公开CLI模块编排、AI伴随快照、P2P独立身份与退出清理 |
| `rulepacks/stumpsville/ui/ai.js` | 本地化个人AI会话、KP咨询队列与服务设置 |
| `rulepacks/stumpsville/ai/guide.md` | AI可读的公开咨询边界与作者说明 |
| `rulepacks/stumpsville/docs/current/integrations.md` | 0.7.0模块接入现状、使用、边界及已验证范围 |
| `rulepacks/stumpsville/tests/verify_integrations.py` | 真实宿主/离线AI/双P2P玩家及浏览器专项验收 |
| `rulepacks/stumpsville/tests/probe_p2p.py` | 联网公开Python客户端的双玩家测试探针 |
| `rulepacks/stumpsville/tests/integrations-results.json` | 不含凭据的模块接入精选验收结果 |
| `docs/plans/Issues/issue-006-stumpsville-module-bridge.md` | 树桩镇完整P2P玩法、AI上下文与发布接口待评估问题 |
| `docs/history/2026-11-14-issue-007-room-version-policy.md` | 旧房间格式兼容移除、版本定义/日志与外部迁移责任的工程 ISSUE |
| `docs/plans/Issues/issue-008-generic-request-decision.md` | 通用请求与裁决记录的候选模型、权限/事务及接入评审 ISSUE |

树桩镇 `runtime*/integrations/` 和 `tests/output/` 中的派生配置、AI快照、P2P身份/本机能力令牌、隔离服务日志与浏览器截图均为Git忽略产物，不逐文件登记；其中联网配置含房主凭据，不作为玩家发行资源。
| `engineering/network-p2p/src/onlinecoc_p2p/discovery.py` | 本机已注册宿主的只读发现、进程与回环协议探测 |
| `engineering/network-p2p/src/onlinecoc_p2p/web/join.js` | 短房间码与一次粘贴加入信息的格式处理 |
| `engineering/network-p2p/play.cmd` | Windows 双击联机入口，首次自动安装独立依赖 |
| `engineering/network-p2p/tests/test_room_codes.py` | 短码迁移、唯一性、兼容与准入防绕过验收 |
| `engineering/network-p2p/tests/test_discovery.py` | 本机发现、进程过期、回环限制与凭据隔离验收 |
| `engineering/network-p2p/build/` | Git 忽略的 Python wheel 构建中间文件 |
| `engineering/network-p2p/acceptance/2026-11-13-0.2.0.json` | 0.2 短房间码、本机发现、54 项回归和玩家包的精选证据 |
| `engineering/network-web/.gitignore` | 排除本机凭据、运行时与生成产物 |
| `engineering/network-web/README.md` | 模块快速使用与验收说明 |
| `engineering/network-web/installer/README.md` | Windows 离线联机依赖安装、分发和构建说明 |
| `engineering/network-web/installer/Setup.cs` | Windows 一键 EXE、依赖自检、运行占用拒绝与备份回滚 |
| `engineering/network-web/installer/build.py` | 按锁定依赖与官方校验值构建离线 EXE |
| `engineering/network-web/installer/verify.py` | 隔离项目实际安装、重复安装、中文路径及配置保留验收 |
| `engineering/network-web/tests/test_retention.py` | 房间一天保留、重连、重启、旧数据迁移和主动移除验收 |
| `engineering/network-web/dist/` | Git 忽略的离线依赖安装 EXE 与 release.json 摘要 |
| `engineering/network-web/build/` | Git 忽略的安装器构建中间文件与 Python 官方嵌入包 |
| `engineering/network-web/acceptance/2026-11-13.json` | 14 项网页专项、54 项旧协议回归及部署摘要 |
| `engineering/network-web/acceptance/README.md` | 模块快速使用与验收说明 |
| `engineering/network-web/acceptance/2026-11-22-0.3.1.json` | 0.3.1 离线安装器、一天保留/移除、82项本地与1项公网测试及部署摘要 |
| `engineering/network-web/config/host.example.json` | 不含秘密的房主配置示例 |
| `engineering/network-web/config/server.example.json` | 不含秘密的服务端配置示例 |
| `engineering/network-web/deploy/install-remote.sh` | 独立 release、停服备份、服务切换与失败回滚 |
| `engineering/network-web/examples/core-table/index.html` | 网页房间入口或首测规则桌面玩家页 |
| `engineering/network-web/examples/core-table/reference.txt` | 游戏页按需加载的公开规则参考 |
| `engineering/network-web/examples/core-table/revealed-note.txt` | 验证账号授权后揭示的示例资源 |
| `engineering/network-web/examples/core-table/web.json` | 首测规则桌面的模块、资源组及接口声明 |
| `engineering/network-web/pyproject.toml` | 可选 Python 包、版本依赖与测试配置 |
| `engineering/network-web/scripts/configure_host.py` | 复用本机接入配置、选择宿主和导出兼容资源包 |
| `engineering/network-web/scripts/inspect_server.py` | 仅输出非秘密版本、路径和源码摘要的云端核对 |
| `engineering/network-web/scripts/prepare_deploy.py` | 显式源码白名单部署包，不包含秘密或游戏资源 |
| `engineering/network-web/scripts/verify_deployment.py` | 严格 CA HTTPS、匿名拒绝与部署源码一致性核对 |
| `engineering/network-web/src/onlinecoc_web/__init__.py` | 模块快速使用与验收说明 |
| `engineering/network-web/src/onlinecoc_web/__main__.py` | 模块快速使用与验收说明 |
| `engineering/network-web/src/onlinecoc_web/cli.py` | 网页服务、房主和资源导出命令入口 |
| `engineering/network-web/src/onlinecoc_web/host.py` | 网页主机适配、有限授权租约及资源协议 2 |
| `engineering/network-web/src/onlinecoc_web/portal.py` | 同源网页、账号与成员准入、黑名单、游戏席位及授权租约 |
| `engineering/network-web/src/onlinecoc_web/resources.py` | 不可变资源组导出、授权投影与签名清单 |
| `engineering/network-web/src/onlinecoc_web/store.py` | 账号/成员文件存储、原子提交、备份与进程锁 |
| `engineering/network-web/src/onlinecoc_web/web/app.js` | 注册/登录、代号准入、个人快捷房间和房主管理 |
| `engineering/network-web/src/onlinecoc_web/web/game.js` | 独立游戏页的连接、宿主登录、心跳与退出 |
| `engineering/network-web/src/onlinecoc_web/web/index.html` | 网页房间入口或首测规则桌面玩家页 |
| `engineering/network-web/src/onlinecoc_web/web/resources.js` | 授权资源组校验、按需加载与隔离缓存 |
| `engineering/network-web/src/onlinecoc_web/web/sandbox-boot.js` | 不接收云端素材的隔离页面启动壳 |
| `engineering/network-web/src/onlinecoc_web/web/sandbox.js` | 玩家资源装配和受限 MessageChannel 桥 |
| `engineering/network-web/src/onlinecoc_web/web/style.css` | 网页房间布局和样式 |
| `engineering/network-web/start.ps1` | 本机可选网页联机适配器启动 |
| `engineering/network-web/tests/conftest.py` | 隔离目录与真实宿主测试夹具 |
| `engineering/network-web/tests/test_browser.py` | 本地及云端双浏览器真实宿主与按需资源验收 |
| `engineering/network-web/tests/test_cloud_restart.py` | 真实 CVM 服务重启后的会话、成员及代号验收 |
| `engineering/network-web/tests/test_portal.py` | 账号/成员/重启、隐藏房间、准入和资源权限验收 |
| `docs/current/engineering/network-web.md` | 网页模块实际协议、配置、服务器部署内容与验收 |
| `engineering/network-web/local/` | Git 忽略的配置、导出、部署包、截图与隔离测试产物 |
| `engineering/network-web/src/onlinecoc_network_web.egg-info/` | Git 忽略的可编辑安装元数据 |
| `engineering/network-web/.pytest_cache/` | Git 忽略的 pytest 缓存 |
| `engineering/network-web/src/onlinecoc_web/web/remember.js` | 可选本机账密记忆、成功后保存、作用域隔离与清除 |
| `engineering/network-web/tests/test_auth_preferences.py` | 6 位密码规则、浏览器本机记忆/重启/清除/禁存储验收 |
| `engineering/network-web/acceptance/2026-11-13-0.1.1.json` | 0.1.1 账号体验、20 项本地测试、公网页面及部署源码证据 |
| `engineering/network-web/src/onlinecoc_web/bridge.py` | 版本2包服务声明、身份/方法/路径/查询参数校验 |
| `engineering/network-web/src/onlinecoc_web/web/storage.js` | 按平台/房间/游戏账号/包/资源版本隔离的声明式存储 |
| `engineering/network-web/tests/test_bridge.py` | 包桥契约与路径/参数/身份负例 |
| `rulepacks/stumpsville/start-web.cmd` | 可选网页联机双击入口 |
| `rulepacks/stumpsville/tools/build_web.py` | 固定公开模块图构建、版本2发行声明及按需资源分组 |
| `rulepacks/stumpsville/web/bridge.js` | 隔离玩家页的传输/资源/存储适配与本地表单事件 |
| `rulepacks/stumpsville/docs/current/web.md` | 网页启动、导航、完整玩法、桥权限/恢复和部署验收边界 |
| `rulepacks/stumpsville/tests/verify_web.py` | 隔离本地目录与真实双浏览器、18预设、恢复及撤权联测 |
| `rulepacks/stumpsville/tests/web-results.json` | 0.8.0网页7组验收与未执行云端/TURN的明确记录 |
| `rulepacks/stumpsville/tests/verify_web_startup.py` | 云端能力缺失、启动错误分类、凭据/权限与真实KP诊断界面专项 |
| `rulepacks/stumpsville/tests/web-startup-results.json` | 网页启动诊断6组结果，无云端改动 |
| `engineering/network-web/acceptance/2026-11-14-0.2.0.json` | 云端0.2.0/0.2.2部署、回滚位置、原数据保留、能力及39项源码摘要 |
| `rulepacks/stumpsville/tests/web-cloud-turn-results.json` | 双浏览器真实云端强制TURN、18预设、恢复/权限及清理的8组验收 |
| `rulepacks/stumpsville/tests/verify_web_restart.py` | 导出冲突复现、旧缓存/资源更新/中断/损坏及同存档重复启动验证 |
| `rulepacks/stumpsville/tests/web-restart-results.json` | 6组导出/重启回归及实际缓存隔离副本核验结果 |
| `rulepacks/stumpsville/start-ai.cmd` | 本机AI咨询双击入口 |
| `rulepacks/stumpsville/start-ai-manager.cmd` | 现有AI服务商管理器双击入口，状态写入包运行目录 |
| `rulepacks/stumpsville/tools/ai_bridge.py` | 逐玩家个人咨询固定路径/操作白名单，复用公共宿主鉴权 |
| `rulepacks/stumpsville/tests/verify_map_ai.py` | KP房间角色列表与双网页玩家AI咨询/隔离/恢复专项 |
| `rulepacks/stumpsville/tests/map-ai-results.json` | 5组地图及网页AI离线服务验收记录 |
| `engineering/network-web/src/onlinecoc_web/creation.py` | 开房串格式、同平台解析及配置包导出方法 |
| `engineering/network-web/tests/test_room_creation.py` | 单次创建、公开/密码、旧数据、三页浏览器与可选公网验收 |
| `engineering/network-web/acceptance/2026-11-14-0.3.0.json` | 34项本地、独立公网开房流程与40项部署源码证据 |
| `engineering/ai/scripts/benchmark_local.py` | 隔离房间的本地创建/详情/列表基准与 CPU 分析 |
| `engineering/ai/src/onlinecoc_ai/references.py` | 权限过滤、修订绑定和外发复验的只读数据引用 |
| `engineering/ai/tests/test_references.py` | 引用权限/HTTP/外发/版本、会话单次持久提交及详情范围验收 |
| `engineering/ai/web/components/chat.js` | 可嵌入对话区、会话列表与自适应轮询 |
| `engineering/ai/web/components/chat.css` | 对话、输入区和引用候选列表样式 |
| `engineering/ai/web/components/reference-input.js` | 两级指令/数据补全、键盘选择及异步响应清理 |
| `engineering/ai/web/manager/prototype.html` | 配置包三栏 KP/PL 人机交互演示入口 |
| `engineering/ai/web/manager/prototype.css` | 配置包交互原型响应式样式 |
| `engineering/ai/web/manager/prototype.js` | 固定内存数据、对象引用和模拟分步审核加载 |
| `docs/plans/ai-pack-interaction.md` | 可操作原型说明、包侧正式交互设计与分阶段接入计划 |
| `engineering/acceptance/ai-runtime/chat.json` | 房间对话/引用/原型最终去重337项验收与源码摘要 |
| `engineering/acceptance/ai-runtime/chat-full.xml` | 335项AI与宿主完整回归JUnit |
| `engineering/acceptance/ai-runtime/chat-final.xml` | 最终22项引用/事务/HTTP/会话/浏览器专项JUnit |
| `engineering/acceptance/ai-runtime/chat-launch.xml` | 原操作台及管理器实际启动3项复验JUnit |
| `engineering/acceptance/ai-runtime/chat-browser.json` | 真实Edge房间文件夹、引用、生成/批准/加载与原型操作记录 |
| `engineering/acceptance/ai-runtime/chat-room.png` | 真实管理器房间文件夹与对话截图 |
| `engineering/acceptance/ai-runtime/chat-pack-prototype.png` | 配置包交互原型模拟加载截图 |
| `engineering/acceptance/ai-runtime/chat-performance-before.json` | 优化前250条无关历史的服务层性能样本 |
| `engineering/acceptance/ai-runtime/chat-performance-after.json` | 优化后同负载性能及CPU分析 |
| `engineering/acceptance/ai-runtime/chat-startup.json` | 管理器进程到HTTP就绪的独立启动测量 |
| `engineering/ai/web/components/reference-editor.js` | 语义引用标签、整体增删/替换、撤销剪贴板及授权名称渲染 |
| `engineering/ai/tests/test_reference_ui.py` | 真实Edge指令补全、语义标签原子编辑与迟到名称清理专项 |
| `engineering/acceptance/ai-runtime/reference-ui.json` | 指令补全与语义引用最终9项验收及源码摘要 |
| `engineering/acceptance/ai-runtime/reference-ui.xml` | 最终9项浏览器及引用权限验收JUnit |
| `engineering/acceptance/ai-runtime/reference-ui-browser.json` | 语义输入改造后的真实管理器闭环记录 |
| `engineering/acceptance/ai-runtime/reference-ui-room.png` | 语义输入改造后的真实管理器对话截图 |
| `engineering/acceptance/ai-runtime/reference-ui-pack-prototype.png` | 语义标签原型模拟批准加载截图 |
| `engineering/acceptance/ai-runtime/reference-ui-semantic.png` | 输入区及历史消息中的旅行提灯语义标签截图 |
| `engineering/ai/web/components/reference-commands.js` | 公开指令元数据与按角色展示的候选列表 |
| `engineering/ai/web/components/tools.js` | 无界面会话/需求/引用/审核/回执工具组合 |
| `engineering/ai/web/components/views.js` | 单独页面、对话页面与可折叠面板的装配及生命周期 |
| `engineering/ai/web/components/views.css` | 三种嵌入视图、会话目录和折叠面板样式 |
| `engineering/ai/web/components/page-entry.js` | 三种独立HTML共用的房间登录及组件入口 |
| `engineering/ai/web/components/page-entry.css` | 独立HTML登录与页面布局样式 |
| `engineering/ai/web/components/page.html` | 完整房间AI页面，可直接打开或同源iframe嵌入 |
| `engineering/ai/web/components/conversation.html` | 紧凑AI对话页面，可直接打开或同源iframe嵌入 |
| `engineering/ai/web/components/collapsible.html` | 可折叠AI页面，可直接打开或同源iframe嵌入 |
| `engineering/ai/web/components/pack.js` | 不包含管理员面板的配置包公开入口 |
| `engineering/ai/web/components/pack.d.ts` | 配置包公开入口的TypeScript声明 |
| `engineering/ai/web/components/pack-manifest.json` | 配置包分发资源、页面、类型与服务路由清单 |
| `engineering/ai/tests/test_embeds.py` | 三种真实页面、iframe边界、底层工具和共享客户端生命周期验收 |
| `docs/current/engineering/ai-pack-embedding.md` | 配置包底层装配工具和三种嵌入形式的当前接入指南 |
| `engineering/acceptance/ai-runtime/embeds.json` | 配置包工具与三种嵌入视图26项回归及源码摘要 |
| `engineering/acceptance/ai-runtime/embeds.xml` | 配置包嵌入及相关回归JUnit |
| `engineering/acceptance/ai-runtime/embed-page.png` | 单独房间AI页面真实浏览器截图 |
| `engineering/acceptance/ai-runtime/embed-conversation.png` | 紧凑对话页面真实浏览器截图 |
| `engineering/acceptance/ai-runtime/embed-collapsible.png` | 可折叠面板展开状态截图 |
| `engineering/acceptance/ai-runtime/embed-collapsed.png` | 可折叠面板收起状态截图 |
| `rulepacks/stumpsville/tools/visibility.py` | 已鉴权地图位置缓存、逐玩家角色发现/隐藏与故事联系人投影 |
| `rulepacks/stumpsville/ui/ai-embedded.js` | 新版原生AI对话挂载、受控Transport、身份清理及未知回执恢复 |
| `engineering/backend/src/onlinecoc/version.py` | 后端发行与唯一支持的房间格式常量 |
| `engineering/backend/src/onlinecoc/room_validation.py` | 只读房间、导出封套与备份验证 |
| `engineering/backend/tests/test_room_versions.py` | 版本拒绝不写入、当前恢复、外部转换与CLI回归 |
| `docs/current/engineering/room-format.md` | 当前格式定义、逐版差异、迁移职责和验证方法 |
| `docs/history/2026-11-14-room-formats-before-0.2.0.json` | 调整前v1/v2及子结构机器定义，不供运行时加载 |
| `docs/plans/interaction-records.md` | ISSUE 008双模型评估、来源权限与分期接线方案 |
| `engineering/acceptance/room-version-policy/results.json` | Room v3 版本策略、完整回归与恢复生命周期验收证据 |
| `engineering/acceptance/room-version-policy/regression.xml` | Room v3 版本策略、完整回归与恢复生命周期验收证据 |
| `engineering/acceptance/room-version-policy/lifecycle.xml` | Room v3 版本策略、完整回归与恢复生命周期验收证据 |
| `engineering/backend/src/onlinecoc/data_queries.py` | 宿主受权查询、事件投影、分页与来源复验 |
| `engineering/backend/src/onlinecoc/data_adapter.py` | 管理员显式安装的可信本机数据适配端口 |
| `engineering/ai/src/onlinecoc_ai/data_queries.py` | 查询工具Schema、HTTP服务封装与动态来源绑定 |
| `engineering/ai/tests/test_data_queries.py` | 查询权限、来源变化、HTTP与模型编排专项 |
| `engineering/ai/tests/test_data_query_ui.py` | 三种真实嵌入视图的聊天引用与预览验收 |
| `engineering/acceptance/ai-runtime/data-query.xml` | AI数据查询专项JUnit证据 |
| `engineering/acceptance/ai-runtime/data-ui.xml` | 三种视图浏览器专项JUnit证据 |
| `docs/current/engineering/ai-data-query.md` | 当前AI数据查询、聊天裁决资料、来源与包侧接入说明 |
| `rulepacks/stumpsville/tools/ai_data.py` | 场景聊天、裁决和逐玩家事件只读适配 |
| `rulepacks/stumpsville/tests/verify_ai_data.py` | 真实隔离宿主与离线模型的资料链路验收 |
| `rulepacks/stumpsville/tests/ai-data-results.json` | 包侧聊天裁决资料验收摘要 |
| `rulepacks/stumpsville/tests/verify_ai_scopes.py` | 通过真实宿主和模拟模型验证外发/PL权限、指南快照、分页计数、频道/NPC查询及无工具末轮 |
| `rulepacks/stumpsville/tests/ai-scopes-results.json` | 8组离线模型查询范围、指南快照与新版引擎接线验收摘要 |
| `rulepacks/stumpsville/tests/verify_ai_demand.py` | 须显式--live的隔离样例房间真实模型按需查询验证 |
| `rulepacks/stumpsville/tests/ai-demand-results.json` | 真实模型按需查询的状态、工具与用量记录（以passed字段为准） |
| `engineering/acceptance/ai-runtime/data-full.xml` | 全量回归原始记录，旧指令断言已由data-final复验替代 |
| `engineering/acceptance/ai-runtime/data-final.xml` | 最终67项受影响路径复验JUnit |
| `engineering/acceptance/ai-runtime/data-results.json` | 387项去重通过、包侧证据及最终源码摘要 |
| `docs/plans/Issues/issue-009-ai-live-query-diagnostics.md` | AI诊断及查询修复、真实复验与尚未通过的答案语义验收 |
| `engineering/ai/src/onlinecoc_ai/diagnostics.py` | 有界脱敏任务阶段、工具元信息、异常代码位置与日志 |
| `engineering/ai/tests/test_task_diagnostics.py` | DeepSeek离线协议、查询修正、清理异常与诊断隐私回归 |
| `engineering/acceptance/ai-runtime/issue-009.xml` | ISSUE-009相关98项工程及Edge界面测试JUnit结果 |
| `engineering/acceptance/ai-runtime/issue-009-results.json` | 98项工程/10组包侧离线验收、源码摘要及真实案例待复验边界 |
| `engineering/acceptance/ai-runtime/issue-009-live-regression.xml` | 实测修复后的87项查询、上下文、编排及基础校验回归JUnit |
| `engineering/acceptance/ai-runtime/issue-009-live-results.json` | 6次真实咨询、确认用量、87项回归、源码摘要和人工质量限制 |
| `rulepacks/stumpsville/tests/ai-demand-retest-20261115.json` | 查询成功但预算预留不足的隔离实测证据 |
| `rulepacks/stumpsville/tests/ai-demand-retest-budget200k-20261115.json` | 提高隔离预算后输出截断的实测证据 |
| `rulepacks/stumpsville/tests/ai-demand-retest-output8192-20261115.json` | 自动链路通过但人工计数/频道核对未通过的实测证据 |
| `rulepacks/stumpsville/tests/ai-demand-retest-final-20261115.json` | 实际计数修复后工具回合超限的实测证据 |
| `rulepacks/stumpsville/tests/ai-demand-retest-bounded-20261115.json` | 收尾机制实测定位可选behaviors字段KeyError |
| `rulepacks/stumpsville/tests/ai-demand-retest-validated-20261115.json` | 校验修复后真实查询及回答链路通过，完整语义验收另见汇总 |


AI 格式渲染与会话管理（2026-11-15）：

| 实际文件 | 用途 |
| --- | --- |
| `engineering/ai/web/components/markdown.js` | DOM-only Markdown 子集渲染与独立显示组件，保留正文语义引用 |
| `engineering/ai/web/components/markdown.css` | 格式化回答、表格滚动、代码块及引用标签样式 |
| `engineering/ai/web/components/session-manager.js` | 可嵌入本人会话目录、设置、归档恢复和原回执查询 |
| `engineering/ai/web/components/session-manager.css` | 响应式会话管理界面样式 |
| `engineering/ai/web/components/sessions.html` | 同源可嵌入会话管理独立页面 |
| `engineering/ai/tests/test_session_ui.py` | 真实 Edge 格式安全、会话设置/隔离、草稿与回执恢复验收 |
| `engineering/acceptance/ai-runtime/markdown-embedded.png` | 标题/表格/代码/引用的格式化显示验收截图 |
| `engineering/acceptance/ai-runtime/session-management.png` | 会话管理与设置验收截图 |
| `engineering/acceptance/ai-runtime/session-ui-tests.xml` | 格式及会话首轮26项JUnit结果 |
| `engineering/acceptance/ai-runtime/session-final-tests.xml` | 格式/会话及关联模块51项回归JUnit结果 |
| `engineering/acceptance/ai-runtime/session-recovery-tests.xml` | 末轮4项界面及防重复提交复验JUnit结果 |
| `engineering/acceptance/ai-runtime/rendering-sessions.json` | 51项模块与7组包侧验收范围、源码摘要与复验说明 |

AI 可选限额与用量统计（2026-11-16）：

| 实际文件 | 用途 |
| --- | --- |
| `engineering/ai/src/onlinecoc_ai/usage.py` | 只读授权用量统计、确认/预留分离、原需求归属及日期/明细分页 |
| `engineering/ai/web/components/usage.js` | 可独立嵌入的日期/服务配置/会话用量统计面板 |
| `engineering/ai/web/components/usage.css` | 用量卡片、筛选及滚动表格样式 |
| `engineering/ai/tests/test_usage.py` | 不限额、可选日限额、统计口径、旧记录、重试/取消及HTTP授权验收 |
| `engineering/ai/tests/test_usage_ui.py` | 真实Edge额度开关、用量面板、管理器代理与身份清理验收 |
| `engineering/acceptance/ai-runtime/usage-core-tests.xml` | 用量及编排/契约/管理109项回归JUnit |
| `engineering/acceptance/ai-runtime/usage-ui-tests.xml` | 用量、管理器、三种嵌入与会话13项Edge回归JUnit |
| `engineering/acceptance/ai-runtime/usage-panel.png` | 会话用量统计界面验收截图 |
| `engineering/acceptance/ai-runtime/budget-optional.png` | 每日限额默认关闭的服务配置界面验收截图 |
| `engineering/acceptance/ai-runtime/usage-results.json` | 122项模块与9组树桩镇用量验收、配置变更和源码摘要 |
| `docs/current/engineering/ai-session-access.md` | 会话等级与创建者绑定、玩家开关、执行批次、删除审计及接入边界 |
| `docs/plans/Issues/issue-010-ai-package-mutations.md` | 待实施的配置删除、包侧事务与自动发布接口问题 |
| `engineering/ai/src/onlinecoc_ai/access.py` | 服务端会话权限上限与历史资料持续复验 |
| `engineering/ai/src/onlinecoc_ai/batches.py` | 不可变执行批次、管理员审批、原回执恢复与只读管理查询 |
| `engineering/ai/tests/test_access_batches.py` | 14项权限、玩家数据、审批、取消、历史证据和重启专项 |
| `engineering/ai/tests/test_access_ui.py` | 真实Edge分级权限、归档恢复稳定性、删除、审批与窄屏验收 |
| `engineering/acceptance/ai-runtime/access-settings.png` | 服务与权限两栏布局及默认策略验收截图 |
| `engineering/acceptance/ai-runtime/execution-batches.png` | 执行批次审核与逐项回执界面截图 |
| `engineering/acceptance/ai-runtime/session-permissions-mobile.png` | 玩家会话管理窄屏界面截图 |
| `engineering/acceptance/ai-runtime/session-access-results.json` | 323项模块、32组包侧验收、复测关系和源码摘要 |
| `docs/current/engineering/ai-responses.md` | 简洁回答、可验证语义引用、结构化选项及独立嵌入接口 |
| `engineering/ai/src/onlinecoc_ai/answers.py` | 回答引用白名单与纯文字选择项契约校验 |
| `engineering/ai/web/components/choices.js` | 独立可嵌入选项组件；回调填写需求，不执行命令 |
| `engineering/ai/web/components/choices.css` | 遵守宿主CSP的选项卡片与窄屏样式 |
| `engineering/ai/tests/test_answers.py` | 模型引用、选择项约束、资料证据与权限撤销测试 |
| `engineering/ai/tests/test_answers_ui.py` | 三种视图、独立选项、语义名称、草稿与CSP的Edge验收 |
| `engineering/acceptance/ai-runtime/answer-choices.png` | 授权语义引用、选择卡片与保留草稿的界面截图 |
| `engineering/acceptance/ai-runtime/ai-responses-results.json` | 86项模块与10组树桩镇回归、源码摘要和模型风格验收边界 |
| `engineering/ai/web/components/reference-details.js` | 授权引用详情、精确修订、键盘弹层与请求竞态保护 |
| `engineering/ai/web/components/reference-details.css` | 详情弹层的响应式独立样式 |
| `engineering/ai/tests/test_reference_details_ui.py` | 引用详情权限／过期／乱序与历史节点稳定性浏览器验收 |
| `engineering/acceptance/ai-runtime/reference-details.png` | 可点击引用详情的桌面界面截图 |
| `engineering/acceptance/ai-runtime/reference-details-results.json` | 65项模块／11组树桩镇补验、覆盖范围与源码摘要 |
| `engineering/ai/src/onlinecoc_ai/rulings.py` | 统一运行时／配置裁决与明确批准绑定 |
| `engineering/ai/src/onlinecoc_ai/validation/extensions.py` | 包声明的 NPC 模板与规则场景检查 |
| `engineering/ai/tests/test_rulings.py` | 裁决、幂等批准和模型输出原因验收 |
| `engineering/ai/web/components/rulings.js` | 可嵌入 AI 修改裁决队列 |
| `engineering/ai/web/components/rulings.css` | 裁决队列样式 |
| `rulepacks/stumpsville/tools/ai_extensions.py` | 模板规则扩展契约、字段范围及三检材料 |
| `rulepacks/stumpsville/tests/verify_ai_extensions.py` | 公开 HTTP 配置裁决、规则执行及重启验收 |
| `rulepacks/stumpsville/tests/verify_ai_rulings_live.py` | 显式授权的真实 API 裁决与格式故障注入实验 |
| `rulepacks/stumpsville/tests/ai-extensions-results.json` | 模板／动作／计算、整批裁决及重启六组验收 |
| `docs/plans/ai-rulings-experiments.md` | 裁决、修正与决策实验用例和结果判定 |
| `docs/current/engineering/ai-rulings.md` | 统一裁决、自动策略、配置包扩展边界与开发者建议 |
| `engineering/acceptance/ai-runtime/rulings-results.json` | 离线去重、包侧及真实 API 实验、缺口和源码摘要 |
| `engineering/acceptance/ai-runtime/ai-rulings.png` | 配置与规则整批裁决界面验收 |
| `engineering/acceptance/ai-runtime/rulings-regression-tests.xml` | 本轮裁决／修正／界面回归 JUnit 证据 |
| `engineering/acceptance/ai-runtime/rulings-final-tests.xml` | 本轮裁决／修正／界面回归 JUnit 证据 |
| `engineering/acceptance/ai-runtime/rulings-output-tests.xml` | 本轮裁决／修正／界面回归 JUnit 证据 |
| `engineering/acceptance/ai-runtime/rulings-ui-tests.xml` | 本轮裁决／修正／界面回归 JUnit 证据 |
| `engineering/acceptance/ai-runtime/rulings-source-tests.xml` | 本轮裁决／修正／界面回归 JUnit 证据 |
| `engineering/acceptance/ai-runtime/rulings-repairs-tests.xml` | 本轮裁决／修正／界面回归 JUnit 证据 |
| `rulepacks/stumpsville/tests/ai-rulings-live-results.json` | 隔离 DeepSeek 实验结果，含失败、修正与确认用量 |
| `rulepacks/stumpsville/tests/ai-rulings-live-retest-results.json` | 隔离 DeepSeek 实验结果，含失败、修正与确认用量 |
| `rulepacks/stumpsville/tests/ai-rulings-live-final-results.json` | 隔离 DeepSeek 实验结果，含失败、修正与确认用量 |
| `engineering/ai/web/components/styles.js` | 可复用 Shadow DOM 样式加载、重挂载保持及失败重试 |
| `engineering/ai/web/manager/session-prototype.html` | 会话管理可操作原型入口，使用内存演示数据 |
| `engineering/ai/web/manager/session-prototype.css` | 会话工作台桌面三栏与窄屏样式 |
| `engineering/ai/web/manager/session-prototype.js` | 原型筛选、权限身份、创建、归档撤销与设置交互 |
| `engineering/ai/tests/test_style_stability.py` | 样式失败／重挂载及会话管理原型浏览器验收 |
| `rulepacks/stumpsville/ai/player-guide.md` | 不包含主持秘密的玩家 AI 来源指南 |
| `rulepacks/stumpsville/tests/verify_ai_knowledge.py` | 个人场景知识、KP 揭示界面、引用隔离与重启验收 |
| `rulepacks/stumpsville/tests/ai-knowledge-results.json` | 五组个人知识与玩家指南验收结果 |
| `docs/current/engineering/ai-rendering-knowledge.md` | AI 样式生命周期、个人场景知识与边界排查 |
| `docs/plans/ai-session-management-prototype.md` | 会话管理交互方案、可试玩入口与后续验收条件 |
| `engineering/acceptance/ai-runtime/rendering-knowledge-results.json` | 55项模块、28组包侧回归、限制与源码摘要 |
| `engineering/acceptance/ai-runtime/style-prototype-tests.xml` | 样式及原型初测 JUnit |
| `engineering/acceptance/ai-runtime/rendering-knowledge-tests.xml` | 相关模块初次回归，保留过期测试预期失败证据 |
| `engineering/acceptance/ai-runtime/rendering-retest.xml` | 嵌入与原型补测，保留裁决状态文案预期失败证据 |
| `engineering/acceptance/ai-runtime/rendering-final-tests.xml` | 配置裁决嵌入完整执行复测通过证据 |
| `engineering/acceptance/ai-runtime/session-prototype.png` | 桌面会话管理原型截图 |
| `engineering/acceptance/ai-runtime/session-prototype-mobile.png` | 玩家窄屏会话详情原型截图 |
| `docs/history/2026-11-17-issue-011-player-knowledge-authorization.md` | ISSUE-011首版完成记录与原始问题评估 |
| `docs/history/2026-11-17-ai-player-knowledge.md` | A0—A3 已完成实施计划与决策背景 |
| `docs/current/design/ai-player-knowledge.md` | PL 已知信息设计边界：固定观察、同版本引用、严格故障拒绝、证据输出与验收 |
| `docs/history/2026-11-17-player-knowledge-engineering-design.md` | ISSUE-011首版工程设计实施归档 |
| `docs/history/2026-11-17-player-knowledge-construction-plan.md` | ISSUE-011首版K0—K5与27项验收完成归档 |
| `engineering/ai/src/onlinecoc_ai/known_answers.py` | 严格 PL 证据选择、不可变引用编码与可信排版 |
| `engineering/ai/src/onlinecoc_ai/knowledge.py` | 个人知识能力、查询及复验消费端 |
| `engineering/ai/tests/test_known_answers.py` | 模型输出和引用编码边界测试 |
| `engineering/ai/tests/test_knowledge_port.py` | 知识消费端主体／故障／外发契约测试 |
| `engineering/acceptance/ai-runtime/known-a0.xml` | A0 严格输出及消费端18项验收 |
| `docs/current/engineering/ai-player-knowledge.md` | AI 已知资料实现与验收事实 |
| `engineering/contracts/knowledge.json` | Room v4 知识策略、分面、披露、读取与复验契约 |
| `engineering/backend/src/onlinecoc/knowledge/__init__.py` | 知识服务公共入口 |
| `engineering/backend/src/onlinecoc/knowledge/models.py` | 知识账本校验与摘要 |
| `engineering/backend/src/onlinecoc/knowledge/provider.py` | 宿主状态知识提供方示例 |
| `engineering/backend/src/onlinecoc/knowledge/service.py` | 持久知识披露、不可变观察与权限复验 |
| `engineering/backend/src/onlinecoc/room_migration.py` | Room v3 到 v4 显式离线转换 |
| `engineering/backend/tests/test_knowledge.py` | 知识服务核心权限与快照验收 |
| `engineering/backend/tests/test_knowledge_network.py` | 知识 HTTP/WS、迁移与发送边界验收 |
| `engineering/ai/examples/knowledge-investigation.py` | 不同玩法的证词固定观察提供方示例 |
| `engineering/ai/tests/test_known_runtime.py` | 严格PL上下文、跨主体、在途撤权、证词与转交KP测试 |
| `engineering/ai/tests/test_known_ui.py` | 知识引用原子编辑、原观察详情及撤回清理验收 |
| `engineering/acceptance/ai-runtime/known-a1.xml` | A1初次6项集成验收 |
| `engineering/acceptance/ai-runtime/known-a2.xml` | A2初次5项浏览器验收 |
| `engineering/acceptance/ai-runtime/known-regression.xml` | 权限升级首轮回归，保留旧断言失败以追溯 |
| `engineering/acceptance/ai-runtime/known-full.xml` | AI全量回归原始JUnit记录 |
| `engineering/acceptance/ai-runtime/known-runtime-final.xml` | AI已知信息与授权85项专项通过 |
| `engineering/acceptance/ai-runtime/known-ui-final.xml` | 嵌入组件专项原始记录，后续补验见汇总 |
| `rulepacks/stumpsville/tools/knowledge_provider.py` | 受信分面、当前源版本、观察触发及个人结果投影 |
| `rulepacks/stumpsville/tools/knowledge_client.py` | 显式知识策略、披露、撤回与查询客户端 |
| `rulepacks/stumpsville/tests/verify_strict_known.py` | 公开HTTP及Edge严格知识隔离验收 |
| `rulepacks/stumpsville/tests/strict-known-results.json` | 严格知识12组精选验收结果 |
| `rulepacks/stumpsville/docs/current/player-knowledge.md` | 个人知识接入、旧档现在揭示及开发者边界 |
| `docs/current/engineering/player-knowledge.md` | 引擎Room v4知识服务、出口边界及验收 |
| `engineering/acceptance/ai-runtime/known-ui-retest.xml` | 最终2项宿主操作台补验通过 |
| `engineering/acceptance/ai-runtime/known-results.json` | 384项AI去重通过、包侧12及8组和源码摘要汇总 |
| `engineering/acceptance/knowledge/ai-host-regression.xml` | ISSUE-011首版知识服务验收：ai-host-regression.xml |
| `engineering/acceptance/knowledge/backend-regression.xml` | ISSUE-011首版知识服务验收：backend-regression.xml |
| `engineering/acceptance/knowledge/backend-release.xml` | ISSUE-011首版知识服务验收：backend-release.xml |
| `engineering/acceptance/knowledge/batch-egress-tests.xml` | ISSUE-011首版知识服务验收：batch-egress-tests.xml |
| `engineering/acceptance/knowledge/benchmark.py` | ISSUE-011首版知识服务验收：benchmark.py |
| `engineering/acceptance/knowledge/core-tests.xml` | ISSUE-011首版知识服务验收：core-tests.xml |
| `engineering/acceptance/knowledge/dto-tests.xml` | ISSUE-011首版知识服务验收：dto-tests.xml |
| `engineering/acceptance/knowledge/edges.xml` | ISSUE-011首版知识服务验收：edges.xml |
| `engineering/acceptance/knowledge/network-paths.xml` | ISSUE-011首版知识服务验收：network-paths.xml |
| `engineering/acceptance/knowledge/network-regression.xml` | ISSUE-011首版知识服务验收：network-regression.xml |
| `engineering/acceptance/knowledge/network-retest.xml` | ISSUE-011首版知识服务验收：network-retest.xml |
| `engineering/acceptance/knowledge/performance.json` | ISSUE-011首版知识服务验收：performance.json |
| `engineering/acceptance/knowledge/README.md` | ISSUE-011首版知识服务验收：README.md |
| `engineering/acceptance/knowledge/record_report.py` | ISSUE-011首版知识服务验收：record_report.py |
| `engineering/acceptance/knowledge/results.json` | ISSUE-011首版知识服务验收：results.json |
| `engineering/acceptance/knowledge/sdk-sessions.xml` | ISSUE-011首版知识服务验收：sdk-sessions.xml |
| `engineering/acceptance/knowledge/test_edges.py` | ISSUE-011首版知识服务验收：test_edges.py |
| `engineering/acceptance/knowledge/test_network_paths.py` | ISSUE-011首版知识服务验收：test_network_paths.py |
| `engineering/acceptance/knowledge/test_sdk_sessions.py` | ISSUE-011首版知识服务验收：test_sdk_sessions.py |
| `engineering/acceptance/knowledge/test_ws_boundary.py` | ISSUE-011首版知识服务验收：test_ws_boundary.py |
| `engineering/acceptance/knowledge/validation-retest.xml` | ISSUE-011首版知识服务验收：validation-retest.xml |
| `engineering/acceptance/knowledge/ws-enqueue.xml` | ISSUE-011首版知识服务验收：ws-enqueue.xml |
| `engineering/test-output/knowledge/` | 隔离性能/文档检查及施工辅助生成产物，不作为正式存档 |
| `rulepacks/stumpsville/tools/slots.py` | 命名房间槽位、固定ID路径、元信息与上次选择 |
| `rulepacks/stumpsville/tests/verify_slots.py` | 两槽位真实账号/存档隔离、切换持久化、版本错误与窗口生命周期验收 |
| `rulepacks/stumpsville/tests/slots-results.json` | 房间槽位6组隔离验收结果 |
| `rulepacks/stumpsville/tools/action_errors.py` | 标准包条件诊断、具体原因和PL/KP处理指引，不暴露宿主诊断 |
| `rulepacks/stumpsville/tests/verify_action_reasons.py` | 失败具体原因、持久反馈、裁决留队及浏览器专项验收 |
| `rulepacks/stumpsville/tests/action-reasons-results.json` | 行动失败说明6组隔离验收记录 |
| `rulepacks/stumpsville/ui/keeper-queue.js` | 统一AI待办、分页、原会话/转交、处理记录子窗口及原回执恢复 |
| `rulepacks/stumpsville/ui/ruling-card.js` | 人工、AI裁决与结果通知共用卡片结构 |
| `rulepacks/stumpsville/ui/keeper-rulings.js` | 包侧AI裁决详情、可选备注、显式高危确认与结果通知 |
| `rulepacks/stumpsville/tests/verify_ruling_workspace.py` | 裁决标签、共用卡片、自动关闭、高危发布与失败定位隔离浏览器验收 |
| `rulepacks/stumpsville/tests/ruling-workspace-results.json` | 裁决工作区专项结果及历次验证记录 |
| `rulepacks/stumpsville/tests/verify_keeper_queue.py` | 角色/行动/玩家及辅助AI请求、宿主流程与断线回执的隔离验收 |
| `rulepacks/stumpsville/tests/keeper-queue-results.json` | 统一KP队列9组真实宿主/Edge离线验收记录 |
| `rulepacks/stumpsville/ui/dice.js` | 已确认骰点的小窗动画、减少动画、偏好开关及事件去重 |
| `rulepacks/stumpsville/tests/verify_action_experience.py` | 隔离真实宿主的行动耗时、检定小窗、偏好及多标签页验收 |
| `rulepacks/stumpsville/tests/action-experience-results.json` | 行动反馈与动画验收及本机请求耗时记录 |
| `engineering/ai/tests/test_chat_polish.py` | AI聊天模板新增交互与浏览器验收 |
| `engineering/acceptance/ai-runtime/chat-polish-collapsible-mobile.png` | AI聊天模板迭代的截图或验收证据 |
| `engineering/acceptance/ai-runtime/chat-polish-collapsible.png` | AI聊天模板迭代的截图或验收证据 |
| `engineering/acceptance/ai-runtime/chat-polish-conversation-mobile.png` | AI聊天模板迭代的截图或验收证据 |
| `engineering/acceptance/ai-runtime/chat-polish-conversation.png` | AI聊天模板迭代的截图或验收证据 |
| `engineering/acceptance/ai-runtime/chat-polish-empty.png` | AI聊天模板迭代的截图或验收证据 |
| `engineering/acceptance/ai-runtime/chat-polish-page-mobile.png` | AI聊天模板迭代的截图或验收证据 |
| `engineering/acceptance/ai-runtime/chat-polish-page.png` | AI聊天模板迭代的截图或验收证据 |
| `engineering/acceptance/ai-runtime/chat-polish-results.json` | AI聊天模板迭代的截图或验收证据 |
| `engineering/acceptance/ai-runtime/chat-polish-round1.xml` | AI聊天模板迭代的截图或验收证据 |
| `engineering/acceptance/ai-runtime/chat-polish-round2.xml` | AI聊天模板迭代的截图或验收证据 |
| `engineering/acceptance/ai-runtime/chat-polish-round3-retest.xml` | AI聊天模板迭代的截图或验收证据 |
| `engineering/acceptance/ai-runtime/chat-polish-round3-targeted.xml` | AI聊天模板迭代的截图或验收证据 |
| `engineering/acceptance/ai-runtime/chat-polish-round3.xml` | AI聊天模板迭代的截图或验收证据 |
| `engineering/acceptance/ai-runtime/capability-fix-core.xml` | JSON适配、HTTP错误脱敏及PL链路66项验收 |
| `engineering/acceptance/ai-runtime/capability-fix-regression.xml` | 权限、上下文、输出修复和浏览器149项回归 |
| `engineering/acceptance/ai-runtime/capability-fix-live.json` | DeepSeek合成请求、格式纠正和用量证据 |
| `engineering/acceptance/ai-runtime/capability-fix-results.json` | 215项去重结果、实测边界与源码摘要 |
| `rulepacks/stumpsville/ui/effects.js` | 本人结果／新线索／持久影响、授权快照差值、3秒淡出队列与去重 |
| `rulepacks/stumpsville/ui/map.js` | 单侧出口无向去重、观察门状态和避开房间卡片的通路 |
| `rulepacks/stumpsville/tests/verify_effects_map.py` | 隔离宿主／Edge持久影响、玩家隔离、通路观察与绘制验收 |
| `rulepacks/stumpsville/tests/effects-map-results.json` | 持久影响与地图专项验收结果 |
| `rulepacks/stumpsville/tests/verify_notifications.py` | 3秒淡出、计时队列、线索与结果合并、定向揭示和真实宿主专项验收 |
| `rulepacks/stumpsville/tests/notifications-results.json` | 3秒淡出、新线索与结果提示10组计时／真实宿主验收记录 |
| `docs/current/engineering/developer-reference/README.md` | 开发者参考分类索引 |
| `docs/current/engineering/developer-reference/stumpsville.md` | Stumpsville 开发参考导航与适用范围 |
| `docs/current/engineering/developer-reference/stumpsville-interface.md` | Stumpsville 界面与层级：面板组成树、对象功能与界面源码入口 |
| `docs/current/engineering/developer-reference/stumpsville-notifications.md` | Stumpsville 信息通知：类型、触发条件、内容、接收对象与事件分发 |
| `docs/current/engineering/developer-reference/stumpsville-rules-data.md` | Stumpsville 规则与数据定义：对象模板、规则清单、配置示例与修改入口 |
| `docs/current/engineering/developer-reference/stumpsville-data-management.md` | Stumpsville 数据管理：存储结构、写入恢复与个人知识权限 |
| `docs/plans/Issues/issue-012-authorized-data-presentation.md` | 引擎已授权资料语义展示契约评估，尚未实施 |
| `rulepacks/stumpsville/docs/Issues/` | 配置包侧待处理问题，与引擎 Issues 分别登记 |
| `rulepacks/stumpsville/docs/Issues/README.md` | 树桩镇包侧问题索引 |
| `rulepacks/stumpsville/docs/history/2026-11-19-issue-001-player-knowledge-presentation.md` | 已完成的安全菜单问题背景，现行规则迁入个人已知资料 |
| `engineering/acceptance/ai-runtime/data-presentation-chat.png` | AI 数据语义展示与角色分层验收证据 |
| `engineering/acceptance/ai-runtime/data-presentation-core-retest.xml` | AI 数据语义展示与角色分层验收证据 |
| `engineering/acceptance/ai-runtime/data-presentation-core.xml` | AI 数据语义展示与角色分层验收证据 |
| `engineering/acceptance/ai-runtime/data-presentation-final.xml` | AI 数据语义展示与角色分层验收证据 |
| `engineering/acceptance/ai-runtime/data-presentation-keeper.png` | AI 数据语义展示与角色分层验收证据 |
| `engineering/acceptance/ai-runtime/data-presentation-player.png` | AI 数据语义展示与角色分层验收证据 |
| `engineering/acceptance/ai-runtime/data-presentation-regression.xml` | AI 数据语义展示与角色分层验收证据 |
| `engineering/acceptance/ai-runtime/data-presentation-results.json` | AI 数据展示最终134项去重结果、初跑记录、源码摘要和未实施边界 |
| `rulepacks/stumpsville/tools/scene_knowledge.py` | 玩家安全行动声明、个人发现条件、严格分面Schema和旧原版兼容 |
| `rulepacks/stumpsville/tests/verify_menu_knowledge.py` | 18预设、双玩家、HTTP/AI/Edge菜单安全专项 |
| `rulepacks/stumpsville/tests/verify_menu_upgrade.py` | 真实旧提供方、显式绑定、旧证据失效和重启回滚专项 |
| `rulepacks/stumpsville/tests/menu-knowledge-results.json` | 9组个人菜单、原始载荷、UI和撤回验收 |
| `rulepacks/stumpsville/tests/menu-upgrade-results.json` | 6组旧观察与AI历史升级验收 |
| `rulepacks/stumpsville/tests/menu-safety-results.json` | SV-ISSUE-001本轮52组汇总、初跑记录、源码摘要及边界 |
| `rulepacks/stumpsville/docs/history/README.md` | 包侧归档索引 |
| `rulepacks/stumpsville/docs/history/` | 已完成或被替代的包侧决策与问题记录 |
| `rulepacks/stumpsville/tests/verify_room_workflow.py` | 房间总览、一键开场、回执恢复、可执行裁决与桌面/窄屏隔离验收 |
| `rulepacks/stumpsville/tests/room-workflow-results.json` | 开场与裁决工作流专项通过记录 |
| `engineering/ai/web/components/settings.js` | 独立KP服务权限设置页面与原生组件 |
| `engineering/ai/web/components/settings.css` | 独立KP服务权限设置页面与原生组件 |
| `engineering/ai/web/components/settings.html` | 独立KP服务权限设置页面与原生组件 |
| `engineering/ai/tests/test_workbench.py` | 任务会话定位、可见性和归档删除验收 |
| `engineering/ai/tests/test_workbench_ui.py` | 独立设置、紧凑裁决、目标会话并行加载与窄屏验收 |
| `engineering/acceptance/ai-runtime/workbench-access.xml` | AI工作台设置、裁决与加载验收证据 |
| `engineering/acceptance/ai-runtime/workbench-compact.xml` | AI工作台设置、裁决与加载验收证据 |
| `engineering/acceptance/ai-runtime/workbench-core-retest.xml` | AI工作台设置、裁决与加载验收证据 |
| `engineering/acceptance/ai-runtime/workbench-core.xml` | AI工作台设置、裁决与加载验收证据 |
| `engineering/acceptance/ai-runtime/workbench-load-measurement.json` | AI工作台设置、裁决与加载验收证据 |
| `engineering/acceptance/ai-runtime/workbench-results.json` | AI工作台设置、裁决与加载验收证据 |
| `engineering/acceptance/ai-runtime/workbench-ruling-detail.png` | AI工作台设置、裁决与加载验收证据 |
| `engineering/acceptance/ai-runtime/workbench-rulings-mobile.png` | AI工作台设置、裁决与加载验收证据 |
| `engineering/acceptance/ai-runtime/workbench-settings-mobile.png` | AI工作台设置、裁决与加载验收证据 |
| `engineering/acceptance/ai-runtime/workbench-settings.png` | AI工作台设置、裁决与加载验收证据 |
| `engineering/acceptance/ai-runtime/workbench-ui-final.xml` | AI工作台设置、裁决与加载验收证据 |
| `engineering/acceptance/ai-runtime/workbench-ui-retest.xml` | AI工作台设置、裁决与加载验收证据 |
| `engineering/acceptance/ai-runtime/workbench-ui.xml` | AI工作台设置、裁决与加载验收证据 |
| `rulepacks/stumpsville/tests/verify_workbench.py` | 配置包责任者已创建：紧凑裁决、资料分类、AI设置与加载性能验收 |
| `rulepacks/stumpsville/tests/workbench-results.json` | 紧凑裁决、资料全分类、AI设置与导航加载专项验收 |
| `engineering/ai/src/onlinecoc_ai/change_policy.py` | 完整候选高危分类与可审核差异 |
| `engineering/ai/src/onlinecoc_ai/knowledge_requests.py` | PL自愿知识申请、真实披露与原回执恢复 |
| `engineering/ai/src/onlinecoc_ai/validation/live.py` | 按真实实例ID运行作者声明的存量兼容性探针 |
| `engineering/ai/tests/test_policies.py` | 高危、权限、无批次数量上限和真实知识披露验收 |
| `engineering/ai/tests/test_policies_ui.py` | 显式权限、高危指纹和玩家自愿申请浏览器验收 |
| `engineering/backend/src/onlinecoc/room_read.py` | 引擎责任者确认：KP全房间授权与确定性分片 |
| `engineering/backend/tests/test_high_risk_host.py` | 引擎责任者确认：高危及全房间读取核心专项 |
| `engineering/backend/tests/test_high_risk_commands.py` | 引擎责任者确认：真实命令与发布事务专项 |
| `docs/current/engineering/high-risk-publication.md` | 引擎责任者维护：高危发布与全房间查询契约 |
| `engineering/acceptance/high-risk-publication/README.md` | 引擎责任者确认：高危发布及查询验收记录 |
| `engineering/acceptance/high-risk-publication/core.xml` | 引擎责任者确认：高危发布及查询验收记录 |
| `engineering/acceptance/high-risk-publication/core-retest.xml` | 引擎责任者确认：高危发布及查询验收记录 |
| `engineering/acceptance/high-risk-publication/host-transactions.xml` | 引擎责任者确认：高危发布及查询验收记录 |
| `engineering/acceptance/high-risk-publication/host-final.xml` | 引擎责任者确认：高危发布及查询验收记录 |
| `engineering/acceptance/high-risk-publication/backend-regression.xml` | 引擎责任者确认：高危发布及查询验收记录 |
| `engineering/acceptance/ai-runtime/policies-debug.xml` | AI高危与权限联调初跑及复验记录 |
| `engineering/acceptance/ai-runtime/policies-core-retest.xml` | AI高危与权限联调初跑及复验记录 |
| `engineering/acceptance/ai-runtime/policies-core-final.xml` | AI高危与权限联调初跑及复验记录 |
| `engineering/backend/tests/test_private_probe.py` | 引擎责任者确认：KP名单私有规则离线探针与线上权限隔离 |
| `rulepacks/stumpsville/tools/ai_gameplay.py` | 包责任者确认：高危作者Schema、编号引用和存量场景 |
| `rulepacks/stumpsville/tools/publication_sync.py` | 包责任者确认：发布工件三方同步与冲突处理 |
| `rulepacks/stumpsville/ai/game-terms.json` | 包责任者确认：游戏术语与方案映射 |
| `rulepacks/stumpsville/docs/plans/ai-usage-scenarios.md` | 包责任者维护：KP和PL使用场景草稿 |
| `rulepacks/stumpsville/docs/current/ai-permissions.md` | 包责任者维护：AI权限与高危裁决 |
| `rulepacks/stumpsville/tests/verify_ai_scenarios.py` | 包责任者确认：高危发布、地图物品、恢复验收 |
| `rulepacks/stumpsville/tests/verify_ai_permissions.py` | 包责任者确认：真实申请披露与权限页浏览器验收 |
| `rulepacks/stumpsville/tests/verify_ai_scenarios_live.py` | 包责任者确认：隔离DeepSeek场景实验 |
| `rulepacks/stumpsville/tests/ai-scenarios-results.json` | 包责任者维护：场景验收结果（阶段结果随实测更新） |
| `engineering/acceptance/high-risk-publication/ai-host-regression.xml` | 引擎责任者确认：真实宿主与私有探针验收记录 |
| `engineering/acceptance/high-risk-publication/probe-first.xml` | 引擎责任者确认：真实宿主与私有探针验收记录 |
| `engineering/acceptance/high-risk-publication/probe-second.xml` | 引擎责任者确认：真实宿主与私有探针验收记录 |
| `engineering/acceptance/high-risk-publication/probe-final.xml` | 引擎责任者确认：真实宿主与私有探针验收记录 |
| `engineering/acceptance/ai-runtime/policies-ui.xml` | AI权限与资料申请浏览器验收证据 |
| `engineering/acceptance/ai-runtime/policies-settings.png` | AI权限与资料申请浏览器验收证据 |
| `engineering/acceptance/ai-runtime/policies-settings-mobile.png` | AI权限与资料申请浏览器验收证据 |
| `engineering/acceptance/ai-runtime/policies-knowledge-review.png` | AI权限与资料申请浏览器验收证据 |
| `engineering/acceptance/ai-runtime/policies-player-request.png` | AI权限与资料申请浏览器验收证据 |
| `engineering/acceptance/high-risk-publication/post-probe-integration.xml` | 引擎责任者确认：私有探针后的真实集成补验 |
| `engineering/acceptance/high-risk-publication/results.json` | 引擎责任者维护：188项去重结果、初跑与源码摘要 |
| `engineering/acceptance/ai-runtime/policies-budget-retest.xml` | AI策略、披露与请求容量回归记录（保留初跑与最新去重结果） |
| `engineering/acceptance/ai-runtime/policies-context.xml` | AI策略、披露与请求容量回归记录（保留初跑与最新去重结果） |
| `engineering/acceptance/ai-runtime/policies-ui-dedup.xml` | AI策略、披露与请求容量回归记录（保留初跑与最新去重结果） |
| `engineering/acceptance/ai-runtime/policies-ui-final.xml` | AI策略、披露与请求容量回归记录（保留初跑与最新去重结果） |
| `engineering/acceptance/ai-runtime/policies-validation.xml` | AI策略、披露与请求容量回归记录（保留初跑与最新去重结果） |
| `engineering/acceptance/ai-runtime/policies-results.json` | AI策略、披露与请求容量回归记录（保留初跑与最新去重结果） |
| `rulepacks/stumpsville/tests/ai-scenarios-live-results.json` | 包责任者维护：真实 DeepSeek 阶段用量、工具证据与验收状态 |
| `rulepacks/stumpsville/tests/ai-permissions-results.json` | 包责任者维护：PL主动披露、KP选择与权限面板3组浏览器验收 |
| `engineering/backend/tests/test_entity_labels.py` | 引擎责任者维护：KP实体检索标签、回退、外发与玩家隔离专项 |
| `engineering/acceptance/entity-search-label/core.xml` | 引擎实体标签15项专项验收记录 |
| `engineering/acceptance/entity-search-label/results.json` | 实体检索标签76项去重结果与源码摘要 |
| `engineering/acceptance/entity-search-label/regression.xml` | 实体标签及既有查询、知识和引用的76项回归记录 |
| `engineering/acceptance/entity-search-label/README.md` | 引擎实体检索标签的范围、76项去重验收与使用边界 |
| `engineering/acceptance/ai-runtime/policies-batch-repair.xml` | 批次输出格式、修正反馈与5次额度验收，保留初跑／回归／最终回放 |
| `engineering/acceptance/ai-runtime/policies-batch-repair-regression.xml` | 批次输出格式、修正反馈与5次额度验收，保留初跑／回归／最终回放 |
| `engineering/acceptance/ai-runtime/policies-batch-repair-final.xml` | 批次输出格式、修正反馈与5次额度验收，保留初跑／回归／最终回放 |
| `engineering/acceptance/ai-runtime/policies-receipts.xml` | 已执行批次来源变化／撤权脱敏、重复批准及既有裁决回归 |
| `engineering/acceptance/ai-runtime/policies-receipts-regression.xml` | 已执行批次来源变化／撤权脱敏、重复批准及既有裁决回归 |
| `engineering/ai/src/onlinecoc_ai/player_requests.py` | 玩家创作意图、KP私有审核会话和人工审批边界 |
| `engineering/ai/tests/test_player_requests.py` | 个人目录、查询错误分类、创作申请隔离与手动审批专项 |
| `engineering/ai/tests/test_player_requests_ui.py` | 玩家直提、错误提示、KP接收和私有会话定位浏览器验收 |
| `rulepacks/stumpsville/docs/history/2026-11-19-issue-002-player-ai-requests.md` | 包责任者委托登记：PL查询与创作申请已修复归档记录 |
| `rulepacks/stumpsville/tests/verify_ai_player_requests.py` | 包责任者委托登记：本人装备、申请桥、KP高危审批隔离验收 |
| `rulepacks/stumpsville/tests/verify_ai_player_requests_live.py` | 包责任者委托登记：原始问句的隔离DeepSeek实测 |
| `engineering/acceptance/ai-runtime/player-requests-core.xml` | 玩家查询与创作申请本轮原始测试记录（包括初跑与复验） |
| `engineering/acceptance/ai-runtime/player-requests-core2.xml` | 玩家查询与创作申请本轮原始测试记录（包括初跑与复验） |
| `engineering/acceptance/ai-runtime/player-requests-core3.xml` | 玩家查询与创作申请本轮原始测试记录（包括初跑与复验） |
| `engineering/acceptance/ai-runtime/player-requests-core4.xml` | 玩家查询与创作申请本轮原始测试记录（包括初跑与复验） |
| `engineering/acceptance/ai-runtime/player-requests-initial.xml` | 玩家查询与创作申请本轮原始测试记录（包括初跑与复验） |
| `engineering/acceptance/ai-runtime/player-requests-validation.xml` | 玩家查询与创作申请本轮原始测试记录（包括初跑与复验） |
| `engineering/acceptance/ai-runtime/player-requests-mobile.png` | 玩家直接提交创作申请的390px嵌入页面截图 |
| `engineering/acceptance/ai-runtime/player-requests-embeds.xml` | 玩家查询、申请与嵌入本轮原始验收记录（含复验） |
| `engineering/acceptance/ai-runtime/player-requests-final.xml` | 玩家查询、申请与嵌入本轮原始验收记录（含复验） |
| `engineering/acceptance/ai-runtime/player-requests-notice.xml` | 玩家查询、申请与嵌入本轮原始验收记录（含复验） |
| `engineering/acceptance/ai-runtime/player-requests-regression.xml` | 玩家查询、申请与嵌入本轮原始验收记录（含复验） |
| `engineering/acceptance/ai-runtime/player-requests-results.json` | 个人知识与创作申请190项去重验收、复验关系和源码摘要 |
| `rulepacks/stumpsville/tests/ai-player-requests-results.json` | 包责任者委托登记：12组本人装备／申请／高危审批及嵌入验收 |
| `rulepacks/stumpsville/tests/ai-player-requests-live-results.json` | 包责任者委托登记：3条原问句DeepSeek通过、6次调用及28259tokens |
| `engineering/acceptance/ai-runtime/player-requests-boundaries.xml` | 原申请人绑定、标签外发及既有申请／严格知识30项定向回归 |
| `engineering/backend/tests/test_ai_debug_route.py` | 引擎责任者委托登记：只读AI调试HTTP路由与SDK参数隔离验收 |
| `engineering/acceptance/ai-debug-route/README.md` | 引擎责任者委托登记：16项路由SDK与1项LAN验收范围说明 |
| `engineering/acceptance/ai-debug-route/test_lan.py` | 引擎责任者委托登记：真实回环LAN只读调试转发验收 |
| `engineering/acceptance/ai-debug-route/routes.xml` | 引擎责任者委托登记：保留初次LAN环境依赖失败证据 |
| `engineering/acceptance/ai-debug-route/routes-retest.xml` | 引擎责任者委托登记：路由和SDK 16项复验通过 |
| `engineering/acceptance/ai-debug-route/lan.xml` | 引擎责任者委托登记：LAN回环1项验收通过 |
| `engineering/acceptance/ai-debug-route/results.json` | 引擎责任者委托登记：17项结果与源码摘要 |
| `rulepacks/stumpsville/docs/history/2026-11-19-issue-003-kp-ai-review-debug.md` | SV-ISSUE-003完成归档：来源审核、调试与精确配置追加闭环 |
| `rulepacks/stumpsville/tools/ai_review.py` | 包责任者委托登记：裁决来源快照与持久AI审核信封 |
| `rulepacks/stumpsville/tests/verify_ai_review_debug.py` | 包责任者委托登记：审核转交、调试和物品查询隔离验收 |
| `engineering/ai/src/onlinecoc_ai/reviews.py` | KP来源引用审核、幂等创建与意图/执行分离 |
| `engineering/ai/src/onlinecoc_ai/debug.py` | 当前授权只读调试投影、正文显式选择和凭据脱敏 |
| `engineering/ai/web/components/debug.js` | 嵌入定位复制、调试导出和审核来源卡 |
| `engineering/ai/tests/test_review_debug.py` | 审核主体、审批、导出隔离和实际模型标识验收 |
| `engineering/ai/tests/test_review_debug_ui.py` | 真实浏览器来源卡与显式导出、失效保护验收 |
| `engineering/acceptance/ai-runtime/review-debug-core.xml` | 70项初验，保留两个新夹具前置条件失败 |
| `engineering/acceptance/ai-runtime/review-debug-ui.xml` | 新核心和嵌入24项通过、管理器旧文案断言失败记录 |
| `docs/current/engineering/ai-debug-review.md` | 来源引用审核、授权调试导出与模型版本标识的现行接口 |
| `engineering/acceptance/ai-runtime/review-debug-regression.xml` | 189项权限、上下文、审批、契约、服务商及管理器回归 |
| `engineering/acceptance/ai-runtime/review-debug-ui-retest.xml` | 管理器、权限和调试界面5项浏览器复验 |
| `engineering/acceptance/ai-runtime/review-debug-http.xml` | 真实HTTP登录、PL权限、no-store和只读导出验收 |
| `engineering/acceptance/ai-runtime/review-debug-copy.xml` | HTTP无剪贴板的定位回退和导出边界复验 |
| `rulepacks/stumpsville/tests/verify_ai_review_debug_live.py` | 包责任者委托登记：PL组合申请到KP审核候选的真实模型闭环 |
| `rulepacks/stumpsville/docs/current/ai-debugging.md` | 包责任者委托登记：KP来源、资料查询和调试排障当前指南 |
| `engineering/acceptance/ai-runtime/review-debug-legacy.xml` | 旧审核来源显示/外发、玩家申请、HTTP与上下文48项复验 |
| `engineering/acceptance/ai-runtime/review-debug-model.xml` | 请求/实际模型标识和用量持久化至调试导出验收 |
| `engineering/acceptance/ai-runtime/review-debug-results.json` | AI来源审核与调试220项去重结果、初验复验关系及源码摘要 |
| `rulepacks/stumpsville/tests/ai-review-debug-results.json` | 包侧来源审核、引用导航、权限和导出隔离验收结果 |
| `rulepacks/stumpsville/tests/ai-review-debug-live-results.json` | 真实 DeepSeek 组合申请闭环、调用用量与失败历史 |
| `engineering/ai/src/onlinecoc_ai/data_edits.py` | 绑定基线的配置节点读取与显式增量展开 |
| `engineering/ai/tests/test_data_edits.py` | 配置增量、精确版本、重复键与完整候选验收 |
| `engineering/acceptance/ai-runtime/data-edits-core.xml` | 22项精确增量专项验收 |
| `engineering/acceptance/ai-runtime/data-edits-copy.xml` | 增量复制与隔离2项复验 |
| `engineering/acceptance/ai-runtime/data-edits-results.json` | 115项精确增量及相关回归、失败复验关系与51项源码摘要 |
| `engineering/acceptance/ai-runtime/data-edits-regression.xml` | 93项配置、权限、响应与预算回归初验 |
| `engineering/acceptance/ai-runtime/data-edits-budget.xml` | 旧预算替身兼容后的定向复验 |
| `docs/history/2026-11-20-issue-013-ai-session-restart.md` | AI 同房间重启历史复验修复、失败与验收归档 |
| `engineering/ai/tests/test_session_restart.py` | 同目录重启和连续对话回归 |
| `engineering/acceptance/ai-runtime/restart-initial.xml` | 重启历史失效首次复现证据 |
| `engineering/ai/tests/test_debug_dialog_ui.py` | 顶部调试弹窗、范围选择、正文导出和窄屏浏览器验收 |
| `engineering/acceptance/ai-runtime/debug-dialog-initial.xml` | 静态服务器 MIME 前置失败原始记录 |
| `engineering/acceptance/ai-runtime/debug-dialog-retest.xml` | 顶部调试弹窗双宽度浏览器复验 |
| `engineering/acceptance/ai-runtime/debug-modal-390.png` | 390px 调试子窗口截图 |
| `engineering/acceptance/ai-runtime/debug-modal-1100.png` | 桌面调试子窗口截图 |
| `engineering/acceptance/ai-runtime/restart-integrated.xml` | 33项会话、个人知识、重启及调试联合回归 |
| `docs/history/2026-11-20-ai-development-records.md` | AI 阶段证据、早期方案和重复验收统计归档 |
| `engineering/backend/tests/test_history_context.py` | 引擎责任者交付：只读历史重启复验及执行边界 |
| `engineering/acceptance/history-context/.gitignore` | 引擎历史专项隔离输出忽略规则 |
| `engineering/acceptance/history-context/README.md` | 引擎历史复验接口和验收说明 |
| `engineering/acceptance/history-context/core-initial.xml` | 引擎历史初验及夹具失败证据 |
| `engineering/acceptance/history-context/core-retest.xml` | 引擎29项历史专项复验 |
| `engineering/acceptance/history-context/regression.xml` | 引擎110项历史、权限与发布回归 |
| `engineering/acceptance/history-context/results.json` | 引擎历史专项汇总与源码摘要 |
| `docs/history/2026-11-20-issue-014-ai-console-rulings-client.md` | 已完成：旧首测操作台裁决接线与浏览器复验归档 |
| `engineering/acceptance/ai-runtime/full-20261120.xml` | 519项AI全量首轮：515通过、4失败；保留原始失败 |
| `engineering/acceptance/ai-runtime/access-debug-20261120.xml` | 旧文案断言失败的隔离复现 |
| `engineering/acceptance/ai-runtime/access-retest-20261120.xml` | 修正文案断言后的权限与会话UI复验 |
| `engineering/acceptance/ai-runtime/feedback-20261120.xml` | 失败反馈初验：富文本断言类型不匹配记录 |
| `engineering/acceptance/ai-runtime/feedback-retest-20261120.xml` | 3项顶部弹窗及失败恢复浏览器复验 |
| `engineering/acceptance/rulings-sdk/test_client.mjs` | 真实旧SDK与合成Transport的8项裁决接线验收 |
| `engineering/acceptance/rulings-sdk/core.xml` | 8项旧SDK接线、代际与订阅边界通过证据 |
| `engineering/acceptance/rulings-sdk/README.md` | 旧操作台SDK接口、验证方式与边界 |
| `engineering/acceptance/rulings-sdk/results.json` | SDK测试结果、方法范围及源码摘要 |
| `engineering/acceptance/ai-runtime/full-retest-20261120.xml` | 5项审核、发布、设置及紧凑裁决浏览器复验 |
| `engineering/acceptance/ai-runtime/repair-20261120-results.json` | AI本轮528项去重、存储及真实配置成功率、失败复验和源码摘要 |
| `engineering/acceptance/ai-runtime/repair-20261120.md` | 本轮重启、调试、失败处理与成功率验收入口 |
| `docs/history/2026-11-20-issue-015-ai-store-growth.md` | 已完成：AI累计配额故障、保留全历史的压缩实现及验收归档 |
| `rulepacks/stumpsville/ui/ai-recovery.js` | 包侧交付：HTTP error classification and status-preserving package transport |
| `rulepacks/stumpsville/tests/verify_ai_recovery.mjs` | 包侧交付：Package transport and queue recovery regression |
| `rulepacks/stumpsville/tests/verify_ai_recovery_ui.py` | 包侧交付：Actual package browser recovery, debug dialog and exported component validation |
| `rulepacks/stumpsville/tests/verify_ai_config_matrix.py` | 包侧交付：Public HTTP configuration matrix and isolated restart batches |
| `rulepacks/stumpsville/tests/verify_ambiguous_live.py` | 隔离 KP 房间真实 DeepSeek 多轮模糊需求验收入口 |
| `rulepacks/stumpsville/tests/ambiguous_suite.py` | 复杂模糊需求用例、预设重大决策和目标达成条件 |
| `rulepacks/stumpsville/tests/summarize_ambiguous_matrix.py` | 按人工发言、技术恢复和审批汇总真实 API 对照 |
| `rulepacks/stumpsville/tests/ambiguous-suite-live-report.md` | 16 项模糊需求的前后对照与逐轮对话 |
| `rulepacks/stumpsville/tests/ambiguous-suite-live-summary.json` | 逐例人工轮数、达成、审批和 API 用量 |
| `rulepacks/stumpsville/tests/ambiguous-suite-live-traces.json.gz` | 优化前后及诊断样本的完整工具返回与状态差异 |
| `rulepacks/stumpsville/tests/ambiguous-live-report.md` | 逐轮对话、读取、检查、目标达成和统计 |
| `rulepacks/stumpsville/tests/ambiguous-live-results.json` | 三间隔离房的工具参数、返回、回执及实际状态差异 |
| `rulepacks/stumpsville/tests/verify_ai_config_live.py` | 包侧交付：Opt-in bounded three-batch DeepSeek matrix |
| `rulepacks/stumpsville/tests/ai-recovery-results.json` | 包侧交付：Initial and final 15-case recovery evidence |
| `rulepacks/stumpsville/tests/ai-config-matrix-results.json` | 包侧交付：First cumulative room matrix, timeouts and storage exhaustion |
| `rulepacks/stumpsville/tests/ai-config-matrix-items-results.json` | 包侧交付：Item batch and initial order-sensitive restart assertion |
| `rulepacks/stumpsville/tests/ai-config-matrix-map-results.json` | 包侧交付：Map batch, scene coverage gap and restart |
| `rulepacks/stumpsville/tests/ai-config-matrix-rules-results.json` | 包侧交付：Rule batch, unsupported source removal and restart |
| `rulepacks/stumpsville/tests/ai-config-matrix-restart-results.json` | 包侧交付：Published item plus two/three loopback plans across restart |
| `rulepacks/stumpsville/tests/ai-config-matrix-summary.json` | 包侧交付：Deduplicated latest results without erasing cumulative storage failure |
| `rulepacks/stumpsville/tests/ai-config-live-npc-results.json` | 包侧交付：真实DeepSeek NPC增改删首轮失败、修复复验与调用用量 |
| `rulepacks/stumpsville/tests/ai-repair-handoff.json` | 包侧交付：Root coordinator handoff and new actual file list |
| `rulepacks/stumpsville/docs/plans/ai-restart-configuration-matrix.md` | 包侧交付：Coverage, failures, limits and live handoff commands |
| `rulepacks/stumpsville/docs/history/2026-11-20-development-records.md` | 包侧交付：Archived development history replaced by concise current documentation |
| `engineering/ai/tests/test_management_queries.py` | 真实NPC失败的参数纠错、权威模板读取和来源边界离线重放 |
| `engineering/acceptance/store-compaction/.gitignore` | 无损压缩实验输出忽略规则 |
| `engineering/acceptance/store-compaction/test_compression.py` | 15项全历史保留、配额、故障、锁与损坏检查 |
| `engineering/acceptance/store-compaction/large-fixture-results.json` | 原527 MB失败样本复制后压缩、12次续写和重开结果 |
| `engineering/acceptance/store-compaction/README.md` | 无损历史压缩行为、兼容边界与验收入口 |
| `engineering/acceptance/ai-runtime/query-storage-initial-20261120.xml` | 8项管理查询与15项压缩初验全部通过 |
| `engineering/acceptance/ai-runtime/query-storage-regression-20261120.xml` | 226项AI管理查询、审核、会话与引擎存储回归全部通过 |
| `rulepacks/stumpsville/tests/ai-config-live-items-results.json` | 真实DeepSeek物品、武器、普通容器新增及实际发放验收 |
| `rulepacks/stumpsville/tests/ai-config-live-map-rules-results.json` | 真实DeepSeek地图、规则、危险删除拒绝与提示复验 |

| `rulepacks/stumpsville/tests/verify_stale_approval.py` | 同档重启、高危过期批准、重检恢复与冲突保护隔离验收 |
| `rulepacks/stumpsville/tests/stale-approval-results.json` | 过期高危审批复现与后续修复复验，保留首轮失败 |

| `engineering/ai/tests/test_ruling_revisions.py` | 同摘要新修订、旧回执兼容、未知执行保守阻断及真实重启发布专项 |
| `engineering/acceptance/ruling-revisions/.gitignore` | 裁决修订验收隔离目录忽略规则 |
| `engineering/acceptance/ruling-revisions/README.md` | 裁决修订恢复、兼容策略与验收入口 |
| `engineering/acceptance/ruling-revisions/initial.xml` | 修复前2项旧blocked覆盖新修订的失败证据 |
| `engineering/acceptance/ruling-revisions/core.xml` | 修复后23项裁决修订与兼容专项通过 |
| `engineering/acceptance/ruling-revisions/regression.xml` | 76项裁决、权限、来源、重启与高危发布回归通过 |
| `engineering/acceptance/ruling-revisions/results.json` | 99项去重通过、初验复验对应及源码摘要 |

| `docs/history/2026-11-20-issue-016-review-continuity-notifications.md` | 已完成审核连续性、语义引用、自动归档与通知协作；保留真实模型失败及复验 |
| `rulepacks/stumpsville/ui/reference-view.js` | 角色、物品和已知场景的只读语义视图与常规页面共用显示函数 |

| `engineering/backend/src/onlinecoc/notifications.py` | 绑定宿主成功动作的持久定向通知、只读收件箱与逐人确认 |
| `engineering/backend/tests/test_notifications.py` | 26项通知、权限、幂等、HTTP、真实崩溃及备份恢复专项 |
| `engineering/contracts/notifications.json` | 通知send/ack、持久记录及读取DTO的机器契约 |
| `docs/current/engineering/notifications.md` | 显式通知操作、受众、原动作绑定、分页确认及恢复边界 |
| `engineering/acceptance/notifications/.gitignore` | 通知验收隔离输出忽略规则 |
| `engineering/acceptance/notifications/test_client.mjs` | 通知SDK分页、确认幂等与登录代际隔离4项测试 |
| `engineering/acceptance/notifications/core.xml` | 首轮20项通知专项全部通过 |
| `engineering/acceptance/notifications/regression.xml` | 通知26项与现有引擎69项联合回归通过 |
| `engineering/acceptance/notifications/sdk.xml` | 通知SDK4项通过证据 |
| `engineering/acceptance/notifications/results.json` | 通知专项99项去重通过与源码及证据摘要 |
| `engineering/acceptance/notifications/README.md` | 通知验收范围、复验命令及跨模块联测边界 |

| `rulepacks/stumpsville/tests/verify_reference_view.py` | 包侧语义引用角色、物品及旧观察只读渲染与窄屏安全验证 |
| `rulepacks/stumpsville/tests/reference-view-results.json` | 六组包侧语义引用视图独立验收及历史复验 |
| `rulepacks/stumpsville/tests/verify_command_notifications.py` | 真实宿主指令包通知、定向隔离、离线补取、确认故障及重启验收 |
| `rulepacks/stumpsville/tests/command-notification-results.json` | 六组通知联测，保留静态脚本漏装的首轮失败 |
| `rulepacks/stumpsville/tests/verify_review_identity_live.py` | 有界真实DeepSeek原申请人识别、过期短确认与显式通知批次对照 |
| `rulepacks/stumpsville/tests/review-identity-live-deepseek-flash-results.json` | Flash三阶段真实验收、原始失败、最终2/2、调用用量与指南摘要 |
| `rulepacks/stumpsville/tests/review-identity-live-deepseek-v4-pro-results.json` | Pro两阶段真实验收、过期短确认成功、术语失败及未重跑边界 |

| `engineering/ai/src/onlinecoc_ai/history.py` | 过期管理员历史只读授权、意图凭据与重新查询约束 |
| `engineering/ai/tests/test_history_continuity.py` | 18项过期历史、旧存档、撤权删除、重新查询及模型纠错专项 |
| `engineering/ai/tests/test_batch_notifications.py` | 12项真实宿主通知审批、受众与回执恢复专项 |
| `engineering/ai/tests/test_reference_renderer_ui.py` | 4项引用扩展、窄屏、生命周期与历史通知展示浏览器专项 |
| `engineering/acceptance/review-continuity/.gitignore` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/core-first.xml` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/core.xml` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/final.xml` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/history-first-fix.xml` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/history-initial.xml` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/model-repair.xml` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/notification-first.xml` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/README.md` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/reference-final.xml` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/reference-renderer-core.xml` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/reference-renderer-interrupted.json` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/regression-first.xml` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/results.json` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/security-final.xml` | 审核连续性与通知专项证据；首轮及复验详见 README |
| `engineering/acceptance/review-continuity/ui.xml` | 审核连续性与通知专项证据；首轮及复验详见 README |

| `engineering/acceptance/review-continuity/status-initial.xml` | 新任务错误继承历史过期标记的初验与69项复验 |
| `engineering/acceptance/review-continuity/status-final.xml` | 新任务错误继承历史过期标记的初验与69项复验 |

| `rulepacks/stumpsville/tests/ai-recovery-ui-results.json` | 真实浏览器恢复、调试窗口与响应拒绝后的继续操作验收结果 |

| `docs/history/2026-11-20-issue-017-review-history-queue-references.md` | 历史原文、重复裁决及紧凑玩家引用的完成归档、失败和联合验收 |
| `rulepacks/stumpsville/tests/verify_review_followup.py` | 历史正文、关联裁决、手动归档及紧凑玩家引用的真实宿主与浏览器联合验收 |
| `rulepacks/stumpsville/tests/review-followup-results.json` | 六组真实宿主联合验收结果，保留夹具失败和PL事务嵌套产品回归 |
| `rulepacks/stumpsville/tests/verify_review_queue_ui.py` | 包侧队列整理封套、分类计数、后续入口和窄屏详情的独立浏览器验收 |
| `rulepacks/stumpsville/tests/review-queue-ui-results.json` | 包侧四组队列UI验收与首轮夹具布局失败证据 |
| `engineering/acceptance/queue-schema/.gitignore` | 忽略队列契约验收的临时运行目录 |
| `engineering/acceptance/queue-schema/test_schema.py` | 归档、提交键及来源关联命令的严格Schema验收 |
| `engineering/acceptance/queue-schema/core.xml` | 55项队列Schema验收结果 |
| `engineering/acceptance/queue-schema/change-manifest.json` | 本轮命令Schema变更和未改变命令的核对清单 |
| `engineering/acceptance/queue-schema/README.md` | 队列契约责任范围、验收入口和交付边界 |
| `engineering/acceptance/queue-schema/results.json` | 队列契约验收汇总、源码摘要与新增文件清单 |
| `engineering/ai/src/onlinecoc_ai/review_queue.py` | 独立队列整理元数据、关联替代、提交键和归档CAS |
| `engineering/ai/tests/test_review_followup.py` | 历史正文、裁决去重与队列整理的确定性回归 |
| `engineering/ai/tests/test_review_followup_ui.py` | 紧凑引用、继续请求及历史原文的通用组件浏览器回归 |
| `engineering/acceptance/review-followup/.gitignore` | 忽略本轮AI验收的隔离生成目录 |
| `engineering/acceptance/review-followup/README.md` | 历史、队列、紧凑引用的责任边界与失败复验说明 |
| `engineering/acceptance/review-followup/boundaries-final.xml` | 队列归档边界最终验收 |
| `engineering/acceptance/review-followup/boundaries-initial.xml` | 队列归档边界首次失败证据 |
| `engineering/acceptance/review-followup/dispatch-final.xml` | 派发与归档并发修复后验收 |
| `engineering/acceptance/review-followup/first.xml` | 历史及引用首阶段修复后验收 |
| `engineering/acceptance/review-followup/freeze.xml` | 核心阶段冻结验收 |
| `engineering/acceptance/review-followup/history-ui.png` | 通用组件保留历史原文的浏览器证据 |
| `engineering/acceptance/review-followup/initial.xml` | 首轮夹具错误及旧展开格式断言记录 |
| `engineering/acceptance/review-followup/manifest.json` | 本轮28个实际新增源码与验收文件清单 |
| `engineering/acceptance/review-followup/nodes-final.xml` | 历史节点授权修复后的回归 |
| `engineering/acceptance/review-followup/nodes-verified.xml` | 历史节点专项复验 |
| `engineering/acceptance/review-followup/nodes.xml` | 历史节点文本变化首次失败证据 |
| `engineering/acceptance/review-followup/pl-dispatch-initial.xml` | PL自动派发事务嵌套首次失败 |
| `engineering/acceptance/review-followup/pl-final.xml` | PL派发与提交重试修复后验收 |
| `engineering/acceptance/review-followup/player-retry-initial.xml` | 直接创作申请重试键首次失败 |
| `engineering/acceptance/review-followup/public-paths.xml` | 最后61项公共路径回归 |
| `engineering/acceptance/review-followup/queue-first.xml` | 队列整理与去重阶段验收 |
| `engineering/acceptance/review-followup/record_results.py` | 汇总XML并按用例ID保存最新去重结果 |
| `engineering/acceptance/review-followup/regression.xml` | AI既有能力回归 |
| `engineering/acceptance/review-followup/results.json` | 230项最新去重结果、各轮失败及源码摘要 |
| `engineering/acceptance/review-followup/test_history_nodes.py` | 历史文本、删除和撤权的授权边界测试 |
| `engineering/acceptance/review-followup/test_player_retry.py` | 创作申请重试及新意图提交键浏览器验证 |
| `engineering/acceptance/review-followup/test_queue_boundaries.py` | 生成、取消、归档并发及重启边界测试 |
| `engineering/acceptance/review-followup/ui-first.xml` | 通用历史、引用和继续请求界面验收 |

| `docs/history/2026-11-20-issue-018-message-history-resolution.md` | 消息与时间留存、灰引用、完成归档及本机诊断的协作结果、失败和验收边界 |
| `rulepacks/stumpsville/tests/verify_queue_chronology.py` | 混合来源裁决DOM时间顺序、归档切换和查询错误恢复验证 |
| `rulepacks/stumpsville/tests/queue-chronology-results.json` | 队列时间线三组浏览器验收及失败历史 |
| `rulepacks/stumpsville/tests/verify_local_errors.py` | 本机代理分类、日志定位与真实回环拒连验证 |
| `rulepacks/stumpsville/tests/local-errors-results.json` | 本机错误链九组验收和安全日志证据 |
| `rulepacks/stumpsville/tests/verify_message_continuity.py` | 本机原消息、失权引用、真实时间、揭示收件人与同档重启联合验收 |
| `rulepacks/stumpsville/tests/message-continuity-results.json` | 本机五组整链验收及首轮夹具待办状态失败证据 |
| `engineering/ai/src/onlinecoc_ai/messages.py` | 会话主体绑定的消息发布证明、交付快照和旧最终正文迁移 |
| `engineering/ai/tests/test_message_history.py` | 正文留存、失权引用、时间、完成回执与受众边界专项 |
| `engineering/ai/tests/test_message_history_ui.py` | 灰色禁用引用和真实消息时间的浏览器专项 |
| `engineering/acceptance/message-history/.gitignore` | 忽略会话历史专项的隔离生成数据 |
| `engineering/acceptance/message-history/README.md` | 会话发布、时间、失权引用及需求完成验收说明 |
| `engineering/acceptance/message-history/boundaries-final.xml` | 七项来源与错误定位边界最终验证 |
| `engineering/acceptance/message-history/boundaries.xml` | 边界验证首次夹具转义失败证据 |
| `engineering/acceptance/message-history/first.xml` | 历史专项首轮四通过一失败记录 |
| `engineering/acceptance/message-history/freeze.xml` | 核心冻结111项回归 |
| `engineering/acceptance/message-history/live-results.json` | DeepSeek两用例、10调用51510 tokens及30次查询延迟记录 |
| `engineering/acceptance/message-history/live_experiments.py` | 有调用与Token上限的隔离真实模型实验 |
| `engineering/acceptance/message-history/manifest.json` | 本轮20项新增文件与6份当前工程文档清单 |
| `engineering/acceptance/message-history/receipt-final.xml` | 完成凭证权限过滤修复后48项定向回归 |
| `engineering/acceptance/message-history/receipt-visibility.xml` | 失权后完成凭证重曝命令定位的首次失败 |
| `engineering/acceptance/message-history/record_results.py` | 按真实测试文件归一用例并生成去重验收统计 |
| `engineering/acceptance/message-history/references.png` | 灰色失权引用与消息时间浏览器证据 |
| `engineering/acceptance/message-history/results.json` | 119项最新去重记录、各轮失败及源码摘要 |
| `engineering/acceptance/message-history/second.xml` | 历史和引用第二轮验收失败记录 |
| `engineering/acceptance/message-history/test_boundaries.py` | 旧消息受众、错误安全定位和完成凭证权限边界 |
| `engineering/acceptance/message-history/third.xml` | 引用灰色样式覆盖缺陷的第三轮证据 |
| `engineering/acceptance/http-errors/.gitignore` | 忽略HTTP错误链隔离运行数据 |
| `engineering/acceptance/http-errors/README.md` | 宿主HTTP与SDK错误定位、修复边界和验收说明 |
| `engineering/acceptance/http-errors/http-probe.xml` | 首轮真实HTTP错误行为核查 |
| `engineering/acceptance/http-errors/initial-probe.json` | 修复前SDK六类错误形状采样 |
| `engineering/acceptance/http-errors/probe_transport.mjs` | SDK传输错误初始探针 |
| `engineering/acceptance/http-errors/record_results.py` | HTTP错误链验收汇总生成器 |
| `engineering/acceptance/http-errors/repair-results.json` | SDK修复后15项与既有12项回归汇总及源码摘要 |
| `engineering/acceptance/http-errors/results.json` | HTTP错误链初审基线结果 |
| `engineering/acceptance/http-errors/sdk-initial.xml` | SDK联测首次夹具路由失败证据 |
| `engineering/acceptance/http-errors/sdk-regression.xml` | 既有通知与裁决SDK回归 |
| `engineering/acceptance/http-errors/sdk-retest.xml` | SDK错误形状修复后真实HTTP验收 |
| `engineering/acceptance/http-errors/serve_fixture.py` | 隔离宿主错误路由夹具 |
| `engineering/acceptance/http-errors/test_http_errors.py` | 宿主HTTP拒绝及异常分类验证 |
| `engineering/acceptance/http-errors/test_transport.mjs` | SDK HTTP、网络、解析及会话错误验证 |

| `docs/history/2026-11-20-issue-019-performance-generation-progress.md` | 三方性能优化、发送快照与过程展示的完成归档、失败及四页联合验收 |
| `rulepacks/stumpsville/tests/verify_local_performance.py` | 包代理与组合请求的真实回环TCP性能、并发身份隔离对照 |
| `rulepacks/stumpsville/tests/local-performance-results.json` | 连接池优化前后单并发和四并发计时、源码摘要及隔离证据 |
| `rulepacks/stumpsville/tests/verify_request_coalescing.py` | 聊天与裁决读取并发合并及迟到旧身份响应的真实浏览器验收 |
| `rulepacks/stumpsville/tests/request-coalescing-results.json` | 三组读取合并、账号切换和刷新意图保留结果 |
| `rulepacks/stumpsville/tests/verify_ai_binding_labels.py` | 角色引用标签文件复用、并发读取与原子替换失效验证 |
| `rulepacks/stumpsville/tests/ai-binding-labels-results.json` | 四组标签缓存验收及Windows stat/fstat时间语义首次失败 |
| `rulepacks/stumpsville/tests/verify_performance_workflow.py` | 四页面真实宿主性能及生成中私聊、审批、暂时刷新失败的联合验收脚本 |
| `rulepacks/stumpsville/tests/performance-workflow-results.json` | 四页面性能与生成连续性联合结果，保留夹具、历史基线误拒绝和重查超时各轮证据 |
| `engineering/acceptance/performance/.gitignore` | 忽略性能验收的隔离宿主、源码镜像和浏览器工作目录 |
| `engineering/acceptance/performance/README.md` | 引擎性能归因、前后对比、保护边界及残余尾延迟 |
| `engineering/acceptance/performance/baseline.json` | 1000聊天和回执规模的原始引擎基线 |
| `engineering/acceptance/performance/baseline_sources.py` | 按基线摘要核对并重建旧源码隔离镜像 |
| `engineering/acceptance/performance/benchmark.py` | 真实宿主、SDK与浏览器单页及四页负载测量 |
| `engineering/acceptance/performance/boundaries-initial.xml` | 边界回归首次斜杠断言夹具失败记录 |
| `engineering/acceptance/performance/boundaries.xml` | 35项Schema复用、存储与分片撤权保护验证 |
| `engineering/acceptance/performance/core.xml` | 64项基础存储、聊天、模型与崩溃回归 |
| `engineering/acceptance/performance/current-scale-baseline.json` | 约416KB与100回执合成房间的优化前样本 |
| `engineering/acceptance/performance/current-scale-optimized.json` | 同规模优化后样本及快照reset和连接关闭计数 |
| `engineering/acceptance/performance/host_fixture.py` | 独立性能宿主、合成历史与安全访问夹具 |
| `engineering/acceptance/performance/initial-fixture-failure.json` | CSP等初始夹具失败与早期SDK不可写等待证据 |
| `engineering/acceptance/performance/optimized.json` | 1000历史规模优化后计时与源码摘要 |
| `engineering/acceptance/performance/profile-baseline.txt` | 单次真实聊天提交的CPU剖析原始记录 |
| `engineering/acceptance/performance/profile_command.py` | 可重复的隔离CPU剖析入口 |
| `engineering/acceptance/performance/record_results.py` | 汇总前后性能、保护回归及新增文件 |
| `engineering/acceptance/performance/regression.xml` | 宿主、通知、知识及真实聊天浏览器62项回归 |
| `engineering/acceptance/performance/results.json` | 161次执行、160独立用例和全部前后测量汇总 |
| `engineering/acceptance/performance/test_boundaries.py` | 缓存键、跨记录约束、字节兼容及权限边界测试 |
| `engineering/acceptance/performance/worker-probe.json` | 新鲜规则进程启动开销与候选方案对照 |
| `engineering/acceptance/performance/worker_probe.py` | 规则执行隔离进程启动探针 |

| `engineering/acceptance/ai-snapshot-performance/.gitignore` | 忽略隔离AI验收工作目录和运行数据 |
| `engineering/acceptance/ai-snapshot-performance/baseline-rate-limit.json` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/baseline-setup-error.json` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/baseline-source.json` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/baseline.json` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/benchmark.py` | 非空AI历史存档的单并发与四并发查询测量 |
| `engineering/acceptance/ai-snapshot-performance/browser.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/cache-regression.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/document-check.json` | AI当前文档链接及文件摘要核对 |
| `engineering/acceptance/ai-snapshot-performance/final-core-all.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/final-core.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/final-regression.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/freeze-core.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/history-cache.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/history-diagnosis.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/history-final.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/history-performance-before.json` | 历史图重复授权复制和重查的原始性能证据 |
| `engineering/acceptance/ai-snapshot-performance/history-performance.json` | 同历史图优化后剖析与调用次数对照 |
| `engineering/acceptance/ai-snapshot-performance/history-tool-first.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/history-tool-fixed.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/history_benchmark.py` | 14上下文历史图及真实依赖改变的性能剖析 |
| `engineering/acceptance/ai-snapshot-performance/interrupted-regression.json` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/live-preflight.json` | 真实实验预留额度阻断与零调用记录 |
| `engineering/acceptance/ai-snapshot-performance/live-results.json` | 单次DeepSeek实验、2次调用13485 tokens及隔离发布结果 |
| `engineering/acceptance/ai-snapshot-performance/live_experiment.py` | 有界真实DeepSeek生成中聊天及隔离发布实验 |
| `engineering/acceptance/ai-snapshot-performance/manifest.json` | 本轮AI新增源码与验收文件清单 |
| `engineering/acceptance/ai-snapshot-performance/optimized-final.json` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/optimized.json` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/progress.png` | AI处理过程与重新生成入口的浏览器截图 |
| `engineering/acceptance/ai-snapshot-performance/README.md` | AI性能、发送快照与过程展示的验收范围和首次失败说明 |
| `engineering/acceptance/ai-snapshot-performance/record_results.py` | 原始XML去重汇总与源码摘要生成 |
| `engineering/acceptance/ai-snapshot-performance/results.json` | 200项唯一用例结果、全部尝试及最终源码摘要 |
| `engineering/acceptance/ai-snapshot-performance/smoke.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/snapshot-first.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/storage-growth.json` | 四次工具读取后AI持久增量与有效上下文数量 |
| `engineering/acceptance/ai-snapshot-performance/tools-diagnosis.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/acceptance/ai-snapshot-performance/tools-fixed.xml` | AI性能与发送快照的阶段原始验收证据，最终结论见同目录README |
| `engineering/ai/src/onlinecoc_ai/generation.py` | 发送时只读生成快照、实时权限保护与具体依赖变化校验 |
| `engineering/ai/tests/test_generation_snapshot.py` | 冻结生成、历史图缓存、权限撤销与存储增量专项 |
| `engineering/ai/tests/test_progress_ui.py` | 通用过程卡与资料变化后重新生成入口的浏览器专项 |

| `docs/plans/Issues/issue-025-ai-ambiguous-goals.md` | 真实模糊需求验收中的澄清、写入对象和发布依据问题 |
| `docs/plans/Issues/issue-020-batch-partial-slot-diagnostics.md` | 零成功批次误显部分完成及物品槽位混淆的现场、隔离修复和正式跑测边界 |

| `docs/plans/ai-command-reliability.md` | 全类型指令生成样例、真实 API 测试、自动修复与整批事务实施计划 |

| `rulepacks/stumpsville/ui/batch-details.js` | 批次有序指令、逐项预检/结果与安全通知摘要展示 |
| `rulepacks/stumpsville/tests/verify_batch_details.py` | 合成DTO隔离浏览器：序号、撤销、旧首项失败、未知回执与窄屏展示 |
| `rulepacks/stumpsville/tests/batch-details-results.json` | 逐项批次展示9组浏览器结果，保留夹具MIME与导航失败 |

| `rulepacks/stumpsville/tests/verify_batch_workflow.py` | 真实隔离宿主与合成模型：槽位自动修复、批次批准、通知与重放联合验收 |

| `docs/current/engineering/atomic-batches.md` | 原子批次当前接口与限制 |
| `engineering/acceptance/atomic-batches/.gitignore` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/README.md` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/admission.xml` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/conflict.xml` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/conftest.py` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/core.xml` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/count-limit.xml` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/crash_worker.py` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/extended.xml` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/final.xml` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/initial-failures.json` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/initial.xml` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/record_results.py` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/regression.xml` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/results.json` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/test_atomic.py` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/acceptance/atomic-batches/test_stumpsville.py` | 原子批次隔离验收、源码摘要与保留的历史执行证据 |
| `engineering/backend/src/onlinecoc/atomic_batches.py` | 原子批次宿主实现 |
| `engineering/contracts/atomic-batches.json` | 原子批次机器契约 |

| `engineering/acceptance/stumpsville-action-matrix/.gitignore` | 树桩镇17类行动最小上下文、参数、24例真实宿主结果及幂等证据 |
| `engineering/acceptance/stumpsville-action-matrix/build_cases.py` | 树桩镇17类行动最小上下文、参数、24例真实宿主结果及幂等证据 |
| `engineering/acceptance/stumpsville-action-matrix/cases.json` | 树桩镇17类行动最小上下文、参数、24例真实宿主结果及幂等证据 |
| `engineering/acceptance/stumpsville-action-matrix/catalog.json` | 树桩镇17类行动最小上下文、参数、24例真实宿主结果及幂等证据 |
| `engineering/acceptance/stumpsville-action-matrix/contexts.json` | 树桩镇17类行动最小上下文、参数、24例真实宿主结果及幂等证据 |
| `engineering/acceptance/stumpsville-action-matrix/finalize.py` | 树桩镇17类行动最小上下文、参数、24例真实宿主结果及幂等证据 |
| `engineering/acceptance/stumpsville-action-matrix/prestates.json` | 树桩镇17类行动最小上下文、参数、24例真实宿主结果及幂等证据 |
| `engineering/acceptance/stumpsville-action-matrix/README.md` | 树桩镇17类行动最小上下文、参数、24例真实宿主结果及幂等证据 |
| `engineering/acceptance/stumpsville-action-matrix/results.json` | 树桩镇17类行动最小上下文、参数、24例真实宿主结果及幂等证据 |
| `engineering/acceptance/stumpsville-action-matrix/run_matrix.py` | 树桩镇17类行动最小上下文、参数、24例真实宿主结果及幂等证据 |
| `engineering/acceptance/stumpsville-action-matrix/runs/run-001.json` | 树桩镇17类行动最小上下文、参数、24例真实宿主结果及幂等证据 |

| `rulepacks/stumpsville/tests/batch-workflow-results.json` | 真实隔离Host与AI自动修复及浏览器执行联合验收，保留所有尝试 |

| `engineering/acceptance/ai-command-reliability/.gitignore` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/README.md` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/atomic-first.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/atomic-second.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/atomic-third.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/baseline-reassessment.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/baseline-source.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/batch-details-1100.png` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/batch-details-390.png` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/batch-ui-first.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/bounded_provider.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/budget.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/casebook.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/cases.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/catalog-final.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/coordinator-1795183044989840600.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/coordinator-1795183647247512600.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/coordinator-1795184194107020600.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/coordinator-regression-source.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/coordinator-regression.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/coordinator_live.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/core-first-source.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/core-first.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/core-repaired-source.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/core-repaired.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/document-check.json` | 文档链接与冻结源码摘要检查 |
| `engineering/acceptance/ai-command-reliability/engine-interface-source.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/evaluate.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/failure-register.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/feedback-followup-source.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/feedback-followup.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/finalize.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/followup-1795184808338206200.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/followup-1795185119230842500.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/followup-verification.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/freeze-smoke.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/improved-system.txt` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/independent-reassessment.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/live-ledger.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/live.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/lua-author-check.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/new-files.json` | 本次新增路径交接清单 |
| `engineering/acceptance/ai-command-reliability/oracle-check.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/probe-cases.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/production-freeze.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/production-source-before-input-boundaries.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/production-source.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/recovery-first.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/reference-feedback-source.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/reference-feedback.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/reference-input-boundaries-source.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/reference-input-boundaries.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/regression-coverage.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/repair_saved.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/replay-1795183317010503400.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/replay_outputs.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/results.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/run_tests.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/saved-repair-1795183760607024700.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/saved-repair-1795184015563359400.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/saved-repair-1795184146769813400.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/setup-attempts.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/strict-pack-v2-source.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/technical-repair-fixed.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/technical-repair.xml` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/valid-cases.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/valid-fixture-checks.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/valid-input-source.json` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/valid_cases.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/valid_live.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/verify_followups.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/acceptance/ai-command-reliability/work/` | Git忽略的隔离API请求原件、运行存储、日志与快照；只含合成测试数据，不逐项入库 |
| `engineering/ai/src/onlinecoc_ai/batch_execution.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/ai/src/onlinecoc_ai/reliability.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/ai/src/onlinecoc_ai/runtime_references.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/ai/tests/test_atomic_integration.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/ai/tests/test_atomic_recovery.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/ai/tests/test_batch_details_ui.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/ai/tests/test_command_reliability.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |
| `engineering/ai/tests/test_runtime_references.py` | AI指令可靠性实现/回归/分轮实验与失败证据（详见验收README） |

| `docs/history/2026-11-21-ai-defaults-c-review.md` | 默认初始化、账号管理、C类评估实施及有界实验归档 |
| `docs/history/2026-11-21-issue-021-ai-defaults-c-review.md` | ISSUE-021三方实现与联合验收归档 |

| `rulepacks/stumpsville/tools/accounts.py` | 启动面板账号标签，使用本机公开CLI与同请求恢复 |
| `rulepacks/stumpsville/tests/verify_panel_defaults.py` | 默认AI与账号标签的隔离原生UI和真实宿主验收 |
| `rulepacks/stumpsville/tests/panel-defaults-results.json` | 面板默认与账号管理分轮结果，保留首次夹具失败 |

| `rulepacks/stumpsville/tests/verify_c_review_ui.py` | C类评估、显式采纳证明与过期重检的浏览器隔离验收 |
| `rulepacks/stumpsville/tests/c-review-ui-results.json` | C类包侧5组展示/交互与窄屏结果 |

| `engineering/acceptance/engine-accounts-interface-snapshot/.gitignore` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/engine-accounts-interface-snapshot/v1/source.json` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/engine-accounts-interface-snapshot/v2/source.json` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/engine-accounts-interface-snapshot/v3/source.json` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/.gitignore` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/README.md` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/c-command.xml` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/c-first.xml` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/c-fixed.xml` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/checkpoint.py` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/client.xml` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/conftest.py` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/crash_worker.py` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/durability.xml` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/final.xml` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/finalize.py` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/initial-failures.json` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/initial.xml` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/lifecycle-fixed.xml` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/network-fixed.xml` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/persisted.xml` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/prepare.py` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/regression-fixed.xml` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/regression.xml` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/results.json` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/serve_fixture.py` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/source.json` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/test_accounts.py` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/test_c_command_recovery.py` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/test_c_gate.py` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/test_client.py` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/test_durability.py` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/triage.xml` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/backend/src/onlinecoc/host_control_client.py` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/backend/src/onlinecoc/local_accounts.py` | 本机账号事务、C发布证明及其专项/回归证据（详见local-accounts验收） |
| `engineering/acceptance/local-accounts/work/` | Git忽略的合成账号、DPAPI目录、故障夹具和隔离引擎，不逐项入库 |
| `engineering/acceptance/engine-accounts-interface-snapshot/v1/engineering/` | Git忽略的v1只读联测工程镜像，保留source.json摘要 |
| `engineering/acceptance/engine-accounts-interface-snapshot/v2/engineering/` | Git忽略的v2只读联测工程镜像，保留source.json摘要 |
| `engineering/acceptance/engine-accounts-interface-snapshot/v3/engineering/` | Git忽略的v3只读联测工程镜像，保留source.json摘要 |

| `engineering/acceptance/ai-c-review-interface-snapshot/.gitignore` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-c-review-interface-snapshot/source-v2.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-c-review-interface-snapshot/source.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-c-review-interface-snapshot/v1/` | Git忽略的隔离工程镜像或合成实验运行数据，不逐文件入库；摘要和精选证据另列 |
| `engineering/acceptance/ai-c-review-interface-snapshot/v2/` | Git忽略的隔离工程镜像或合成实验运行数据，不逐文件入库；摘要和精选证据另列 |
| `engineering/acceptance/ai-defaults-c-review/.gitignore` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/README.md` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/active-tree.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/actual-c-publication-1795193350815570100.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/actual-c-publication-1795193884905932300.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/actual-c-review-after.png` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/actual-c-review-before.png` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/bounded_provider.py` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/budget.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/coordinator_live.py` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/core-integrated-source.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/core-integrated.xml` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/core-v3-final-source.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/core-v3-final.xml` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/coverage-first-source.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/coverage-first.xml` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/coverage-fixed-source.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/coverage-fixed.xml` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/defaults-first-source.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/defaults-first.xml` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/document-check.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/evidence-repair-1795194368156215900.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/failure-register.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/finalize.py` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/independent-oracle-check.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/integrated-current-source.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/integrated-source.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/integrated-v3-source.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/lifecycle-evidence-fixed-source.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/lifecycle-evidence-fixed.xml` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/lifecycle-evidence-source.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/lifecycle-evidence.xml` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/live-ledger.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/natural-1795193315656682400.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/new-files.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/repair_evidence.py` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/replay-1795194105655650000.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/replay_saved.py` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/results.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/run_tests.py` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/setup-attempts.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/strict-pack-source.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/ui-first-source.json` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/ui-first.xml` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/verify_c_publication.py` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/acceptance/ai-defaults-c-review/work/` | Git忽略的隔离工程镜像或合成实验运行数据，不逐文件入库；摘要和精选证据另列 |
| `engineering/ai/src/onlinecoc_ai/c_review.py` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/ai/src/onlinecoc_ai/room_defaults.py` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/ai/tests/test_c_review_defaults.py` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |
| `engineering/ai/tests/test_c_review_ui.py` | 新房间默认权限、C类KP采纳/动态依据、回归与API分轮证据（详见ai-defaults-c-review验收） |

| `docs/history/2026-11-21-issue-022-chat-isolation-ruling-status.md` | 固定裁决状态行、过期原文与聊天隔离/性能联合实施 |

| `rulepacks/stumpsville/tests/verify_chat_delivery.py` | 四页聊天收发对照、裁决并发、原ID恢复与频道权限验收 |
| `rulepacks/stumpsville/tests/chat-delivery-baseline-results.json` | ISSUE-022旧聊天实现基线及夹具首失败 |
| `rulepacks/stumpsville/tests/chat-delivery-optimized-results.json` | ISSUE-022包侧聊天优化、恢复和权限结果 |
| `engineering/acceptance/chat-isolation/.gitignore` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/README.md` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/after-cache-miss.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/after-control.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/after-proof-fixture.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/after-source.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/after-v1-regression.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/after.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/before-control.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/before-proof-fixture.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/before-source.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/before.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/bench.py` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/cache-fixed.xml` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/conftest.py` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/finalize.py` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/first-failures.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/fixture.py` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/freeze.py` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/initial.xml` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/new-files.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/prepare.py` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/profile-0.txt` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/profile-1.txt` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/profile-2.txt` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/profile-3.txt` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/profile-4.txt` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/profile-before.txt` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/profile_chat.py` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/regression.xml` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/results.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/serve.py` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/test_isolation.py` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/chat-isolation/work/` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/engine-chat-interface-snapshot/.gitignore` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/engine-chat-interface-snapshot/v1/engineering/` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/engine-chat-interface-snapshot/v1/source.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/engine-chat-interface-snapshot/v2/engineering/` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `engineering/acceptance/engine-chat-interface-snapshot/v2/source.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `rulepacks/stumpsville/tests/verify_chat_sources.py` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `rulepacks/stumpsville/tests/chat-sources-baseline-results.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `rulepacks/stumpsville/tests/chat-sources-results.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `rulepacks/stumpsville/tests/verify_chat_combined.py` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `rulepacks/stumpsville/tests/chat-combined-results.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |
| `rulepacks/stumpsville/tests/chat-delivery-combined-results.json` | ISSUE-022聊天隔离、并发性能与接口冻结证据 |

| `engineering/acceptance/ai-chat-interface-snapshot/v1/engineering/` | AI冻结接口源码，详细文件摘要见同版source.json |
| `engineering/acceptance/ai-chat-interface-snapshot/v1/source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-interface-snapshot/v2/engineering/` | AI冻结接口源码，详细文件摘要见同版source.json |
| `engineering/acceptance/ai-chat-interface-snapshot/v2/source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/.gitignore` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/README.md` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/context-first-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/context-first.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/history-first-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/history-first.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/history-fixed-v3-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/history-fixed-v3.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/http-and-source-fixed-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/http-and-source-fixed.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/http-bound-port-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/http-bound-port.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/http-direct-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/http-direct.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/integrated-first-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/integrated-first.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/reproduction-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/reproduction.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/run_tests.py` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-chat-isolation/work/` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/.gitignore` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/README.md` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/bounded_provider.py` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/budget.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/context-before.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/context-corrected-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/context-corrected.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/context-fixed-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/context-fixed.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/context-second-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/context-second.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/core-failures-fixed-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/core-failures-fixed.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/core-v2-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/core-v2.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/document-check.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/early-failure-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/early-failure.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/failure-register.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/independent-audit.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/inheritance-and-choice-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/inheritance-and-choice.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/live-after-13-1795224663994047400.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/live-after-1795224465250881100.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/live-before-1795224329641832900.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/live-ledger.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/live_trials.py` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/new-files.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/preparation-fixed-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/preparation-fixed.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/results.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/ruling-key-fixed-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/ruling-key-fixed.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/run_tests.py` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/technical-feedback-fixed-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/technical-feedback-fixed.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/technical-feedback-verified-source.json` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/technical-feedback-verified.xml` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/acceptance/ai-context-usability/work/` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/ai/src/onlinecoc_ai/intent_context.py` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/ai/src/onlinecoc_ai/preparation.py` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/ai/src/onlinecoc_ai/ruling_history.py` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/ai/tests/test_chat_isolation.py` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/ai/tests/test_chat_isolation_http.py` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |
| `engineering/ai/tests/test_context_usability.py` | ISSUE-022上下文、聊天隔离与已交付原文的实现或验收证据 |

| `docs/history/2026-11-21-issue-023-context-compression-kp-autonomy.md` | 上下文压缩、KP风险裁决、实际测试统计和GitHub交付归档 |

| `rulepacks/stumpsville/tests/verify_consultation_review.py` | 参考来源风险展示、KP明确接受和执行结果的真实浏览器验证 |
| `rulepacks/stumpsville/tests/consultation-review-results.json` | 参考来源风险展示、KP明确接受和执行结果的真实浏览器验证 |

| `rulepacks/stumpsville/tests/verify_context_autonomy.py` | 实际树桩镇资料到配置候选、KP接受和发布的隔离验收 |
| `rulepacks/stumpsville/tests/context-autonomy-baseline-results.json` | 实际树桩镇资料到配置候选、KP接受和发布的隔离验收 |

| `engineering/acceptance/engine-kp-policy-interface-snapshot/.gitignore` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/engine-kp-policy-interface-snapshot/v1/engineering/` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/engine-kp-policy-interface-snapshot/v1/source.json` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/.gitignore` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/README.md` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/compatibility-source.json` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/failures.json` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/finalize.py` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/first-field-error.xml` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/first-source.json` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/fixed.xml` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/freeze.py` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/new-files.json` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/official.xml` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/parameter-expectation.xml` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/prepare.py` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/results.json` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/source.json` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/special.xml` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/test_kp_policy.py` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |
| `engineering/acceptance/kp-policy-audit/work/` | ISSUE-023宿主来源风险接受、发布校验及冻结接口证据 |

| `rulepacks/stumpsville/tests/context-autonomy-results.json` | 真实树桩镇配置/运行时参考来源接受、权限和幂等结果 |

| `engineering/acceptance/ai-compression-interface-snapshot/contracts-v1/ai-operations.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-compression-interface-snapshot/contracts-v1/ai.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-compression-interface-snapshot/contracts-v1/consultation.py` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-compression-interface-snapshot/contracts-v1/source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-compression-interface-snapshot/v1/source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-compression-interface-snapshot/v2/source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-compression-interface-snapshot/v3/source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/.gitignore` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/README.md` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/bounded_provider.py` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/budget.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/compression-1795247144510978100.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/compression-1795247324248927700.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/compression-1795247490062917900.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/compression-1795247911156773000.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/compression-completed-review.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/compression-initial-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/compression-initial.xml` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/consultation-1795248177952401900.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/consultation-1795248549857621900.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/final-core-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/final-core.xml` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/frozen-repro-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/frozen-repro.xml` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/integration-initial-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/integration-initial.xml` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/items-1795248206108486700.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/live-ledger.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/live_scenarios.py` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/management-recheck-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/management-recheck.xml` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/map-1795248371462053900.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/map-1795248575201243400.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/new-files.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/npc-1795248289799830800.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/offline-review.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/pl-1795248201266683700.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/profile-migration.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/provider-defaults-review.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/release-core-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/release-core.xml` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/release-verification.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/results-summary.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/review_results.py` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/run_tests.py` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/strict-pack-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/targeted-fixed-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/targeted-fixed.xml` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/targeted-v1-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/targeted-v1.xml` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/v2-concurrency-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/v2-concurrency.xml` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/v2-critical-fixed-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/v2-critical-fixed.xml` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/v2-critical-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/v2-critical.xml` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/v2-release-fixed-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/v2-release-fixed.xml` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/v2-release-source.json` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/acceptance/ai-context-compression/v2-release.xml` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/ai/src/onlinecoc_ai/compression.py` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/ai/src/onlinecoc_ai/consultation.py` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/ai/src/onlinecoc_ai/context_budget.py` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |
| `engineering/ai/tests/test_context_compression.py` | ISSUE-023 AI语义压缩、来源风险采纳与实际实验的可追溯源码/证据 |

| `engineering/acceptance/ai-compression-interface-snapshot/v1/engineering/` | ISSUE-023 AI冻结源码；具体文件与SHA256见同版source.json，禁止覆盖历史版本 |
| `engineering/acceptance/ai-compression-interface-snapshot/v2/engineering/` | ISSUE-023 AI冻结源码；具体文件与SHA256见同版source.json，禁止覆盖历史版本 |
| `engineering/acceptance/ai-compression-interface-snapshot/v3/engineering/` | ISSUE-023 AI冻结源码；具体文件与SHA256见同版source.json，禁止覆盖历史版本 |
| `docs/current/engineering/chat-isolation.md` | 聊天与AI状态依赖隔离的当前工程说明 |
| `engineering/acceptance/ai-command-reliability/probe-source/casebook.py` | 指令可靠性实验的独立来源探针与复核脚本 |
| `engineering/acceptance/ai-command-reliability/probe-source/evaluate.py` | 指令可靠性实验的独立来源探针与复核脚本 |
| `engineering/acceptance/ai-command-reliability/probe-source/live.py` | 指令可靠性实验的独立来源探针与复核脚本 |

| `docs/history/2026-11-21-issue-024-deepseek-official-compaction.md` | 官方压缩机制适配、真实对照与失败修复的完成记录 |
| `rulepacks/stumpsville/tests/official-compaction-results.json` | ISSUE-024冻结接口的包侧19项验收、来源哈希与测试边界 |
| `engineering/acceptance/engine-kp-policy-interface-snapshot/v1/engineering/` | ISSUE-024复现依赖的宿主冻结源码；只按同版source.json列出的327项入库，不含运行存档 |

| `engineering/ai/src/onlinecoc_ai/compaction_units.py` | 完整历史/工具单元、短需求预算选择与安全工具文字裁剪 |
| `engineering/ai/tests/test_official_compaction.py` | 官方压缩适配、关键原文、工具保护与明确溢出恢复专项 |
| `engineering/acceptance/ai-official-compaction/.gitignore` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/README.md` | ISSUE-024当前机制、确定性/真实API证据与重现边界 |
| `engineering/acceptance/ai-official-compaction/adapted-1795256916717539800.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/adapted-1795257596167240900.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/baseline-1795256781623400600.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/baseline-source.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/bounded_provider.py` | ISSUE-024隔离构建、限额模型调用或统计重算驱动 |
| `engineering/acceptance/ai-official-compaction/budget.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/comparison.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/diagnostic-correction-source.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/diagnostic-correction.xml` | ISSUE-024保留的单轮回归结果，含失败与复测 |
| `engineering/acceptance/ai-official-compaction/final-core-source.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/final-core.xml` | ISSUE-024保留的单轮回归结果，含失败与复测 |
| `engineering/acceptance/ai-official-compaction/handoff-files.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/initial-source.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/initial.xml` | ISSUE-024保留的单轮回归结果，含失败与复测 |
| `engineering/acceptance/ai-official-compaction/integration-v1-source.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/integration-v1.xml` | ISSUE-024保留的单轮回归结果，含失败与复测 |
| `engineering/acceptance/ai-official-compaction/live-ledger.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/live_pair.py` | ISSUE-024隔离构建、限额模型调用或统计重算驱动 |
| `engineering/acceptance/ai-official-compaction/live_support.py` | ISSUE-024隔离构建、限额模型调用或统计重算驱动 |
| `engineering/acceptance/ai-official-compaction/mechanism-fixed-source.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/mechanism-fixed.xml` | ISSUE-024保留的单轮回归结果，含失败与复测 |
| `engineering/acceptance/ai-official-compaction/mechanism-source.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/mechanism-verified-source.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/mechanism-verified.xml` | ISSUE-024保留的单轮回归结果，含失败与复测 |
| `engineering/acceptance/ai-official-compaction/mechanism.xml` | ISSUE-024保留的单轮回归结果，含失败与复测 |
| `engineering/acceptance/ai-official-compaction/official-sources.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/run_tests.py` | ISSUE-024隔离构建、限额模型调用或统计重算驱动 |
| `engineering/acceptance/ai-official-compaction/short-instructions-source.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/short-instructions.xml` | ISSUE-024保留的单轮回归结果，含失败与复测 |
| `engineering/acceptance/ai-official-compaction/summarize.py` | ISSUE-024隔离构建、限额模型调用或统计重算驱动 |
| `engineering/acceptance/ai-official-compaction/tail-boundary-source.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/tail-boundary.xml` | ISSUE-024保留的单轮回归结果，含失败与复测 |
| `engineering/acceptance/ai-official-compaction/tail-selection-proof.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction/verification.json` | ISSUE-024精选来源、预算、实验、统计或交接证据 |
| `engineering/acceptance/ai-official-compaction-interface-snapshot/v1/source.json` | ISSUE-024本版冻结清单与逐文件SHA256 |
| `engineering/acceptance/ai-official-compaction-interface-snapshot/v1/engineering/` | ISSUE-024不可变冻结源码，具体219项路径和哈希见同版source.json |
| `engineering/acceptance/ai-official-compaction-interface-snapshot/v2/source.json` | ISSUE-024本版冻结清单与逐文件SHA256 |
| `engineering/acceptance/ai-official-compaction-interface-snapshot/v2/engineering/` | ISSUE-024不可变冻结源码，具体219项路径和哈希见同版source.json |
| `engineering/acceptance/ai-official-compaction-interface-snapshot/v3/source.json` | ISSUE-024本版冻结清单与逐文件SHA256 |
| `engineering/acceptance/ai-official-compaction-interface-snapshot/v3/engineering/` | ISSUE-024不可变冻结源码，具体219项路径和哈希见同版source.json |
| `engineering/acceptance/ai-official-compaction/work/` | Git忽略的隔离运行树、生成档案与测试证据临时目录；禁止用作正式存档 |

| `docs/plans/operation-performance-audit.md` | 2026-11-22本机操作性能采样、原因、候选缓存/校验优化与验收计划 |
| `rulepacks/stumpsville/rules/ground-take.lua` | KP同场景领取掉落物，保留用量及光源计时 |
| `rulepacks/stumpsville/tests/verify_drop_performance.py` | 隔离宿主丢弃/领取/丢回复恢复、浏览器及性能测量 |
| `rulepacks/stumpsville/tests/drop-performance-results.json` | 丢弃7组验收与操作时延、保存次数、来源哈希 |

| `rulepacks/stumpsville/tests/operation-optimization-results.json` | 包侧保存、状态读取及缓存优化的三轮30样本对照 |

| `engineering/acceptance/engine-performance/.gitignore` | 引擎性能验收目录约定 |
| `engineering/acceptance/engine-performance/README.md` | 引擎性能验收说明 |
| `engineering/acceptance/engine-performance/backup_probe.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/baseline-code/engineering/backend/src/onlinecoc/ai_api.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/baseline-code/engineering/backend/src/onlinecoc/assets.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/baseline-code/engineering/backend/src/onlinecoc/contracts.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/baseline-code/engineering/backend/src/onlinecoc/host.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/baseline-code/engineering/backend/src/onlinecoc/knowledge/provider.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/baseline-code/engineering/backend/src/onlinecoc/knowledge/service.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/baseline-code/engineering/backend/src/onlinecoc/lua_runtime.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/baseline-code/engineering/backend/src/onlinecoc/registry.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/baseline-code/engineering/backend/src/onlinecoc/server.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/baseline-code/engineering/backend/src/onlinecoc/worker_entry.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/baseline-code/engineering/backend/src/onlinecoc/worker_process.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/baseline-code/engineering/client-sdk/client.js` | 引擎性能验收目录约定 |
| `engineering/acceptance/engine-performance/baseline-code/engineering/data-management/onlinecoc_data/store.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/baseline-code/source.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/baseline-v1-backup.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/baseline-v1-http-repeat1.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/baseline-v1-http-repeat2.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/baseline-v1-http-repeat3.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/baseline-v1-http.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/baseline-v1-results.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/baseline-v1-source.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/benchmark.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/boundaries-v2.xml` | 引擎回归结果 |
| `engineering/acceptance/engine-performance/candidate-v1-results.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/candidate-v1-source.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/candidate-v2-results.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/candidate-v2-source.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/candidate-v3-backup.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/candidate-v3-http-repeat1.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/candidate-v3-http-repeat2.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/candidate-v3-http-repeat3.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/candidate-v3-http.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/candidate-v3-profile.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/candidate-v3-source.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/candidate-v4-source.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/candidate-v5-extras.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/candidate-v5-source.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/core-v3.xml` | 引擎回归结果 |
| `engineering/acceptance/engine-performance/core-v4.xml` | 引擎回归结果 |
| `engineering/acceptance/engine-performance/extras-v5.xml` | 引擎回归结果 |
| `engineering/acceptance/engine-performance/extras_probe.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/freeze.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/http_probe.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/joint-v1.xml` | 引擎回归结果 |
| `engineering/acceptance/engine-performance/network-stats-results.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/network_stats.mjs` | 网络指标验证驱动 |
| `engineering/acceptance/engine-performance/phase_profile.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/run_joint.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/run_remaining.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/acceptance/engine-performance/summary.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance/test_joint_page.py` | 引擎性能隔离驱动、边界或联测 |
| `engineering/backend/tests/test_engine_performance.py` | 引擎权限、回归与性能边界测试 |
| `engineering/backend/tests/test_ruling_page_route.py` | 引擎权限、回归与性能边界测试 |
| `engineering/backend/tests/test_view_extras.py` | 引擎权限、回归与性能边界测试 |
| `engineering/acceptance/engine-performance/handoff-files.json` | 引擎性能基线、复测或交接证据 |
| `engineering/acceptance/engine-performance-interface-snapshot/v1/source.json` | 冻结引擎源码清单与逐文件摘要 |
| `engineering/acceptance/engine-performance-interface-snapshot/v1/engineering/` | 不可变联合验收源码，共 332 项，路径见同版 source.json |
| `engineering/acceptance/engine-performance-interface-snapshot/v2/source.json` | 冻结引擎源码清单与逐文件摘要 |
| `engineering/acceptance/engine-performance-interface-snapshot/v2/engineering/` | 不可变联合验收源码，共 338 项，路径见同版 source.json |

### AI 操作性能与冻结验收

| 路径 | 内容 |
| --- | --- |
| `engineering/ai/src/onlinecoc_ai/segmented_store.py` | 按内容摘要提交 AI 分段存储 |
| `engineering/ai/tests/test_operation_performance.py` | 裁决性能、存储恢复或交付凭证回归 |
| `engineering/ai/tests/test_segmented_store.py` | 裁决性能、存储恢复或交付凭证回归 |
| `engineering/ai/tests/test_delivery_write_sets.py` | 裁决性能、存储恢复或交付凭证回归 |
| `engineering/acceptance/ai-operation-performance/.gitignore` | 隔离工作区忽略规则 |
| `engineering/acceptance/ai-operation-performance/adapted-benchmark.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/baseline-benchmark.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/baseline-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/benchmark.py` | AI 性能基准或验收驱动 |
| `engineering/acceptance/ai-operation-performance/compact-metadata-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/compact-metadata.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/comparison.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/core-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/core-v2-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/core-v2.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/core.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/delivery-cold-v2-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/delivery-cold-v2.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/delivery-cold-v3-recovered-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/delivery-cold-v3-recovered.log` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/delivery-cold-v3-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/delivery-cold-v3.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/delivery-crash-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/delivery-crash.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/delivery-large-history-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/delivery-large-history.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/delivery-write-sets-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/delivery-write-sets.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/first-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/first.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/handoff-files.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/history-readonly-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/history-readonly.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/integration-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/integration.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/interrupted-runs.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/large-history-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/large-history.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/large_history.py` | AI 性能基准或验收驱动 |
| `engineering/acceptance/ai-operation-performance/memory-check-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/memory-check.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/memory-fixed-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/memory-fixed.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/optimized-benchmark-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/optimized-benchmark.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/performance-regression-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/performance-regression.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/README.md` | AI 操作性能验收报告 |
| `engineering/acceptance/ai-operation-performance/release-core-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/release-core.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/release-v3-core-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/release-v3-recovered-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/release-v3-recovered.log` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/release-v3-recovered.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/run_tests.py` | AI 性能基准或验收驱动 |
| `engineering/acceptance/ai-operation-performance/segment-analysis.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/segmented-benchmark-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/segmented-benchmark.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/segments-optimized-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/segments-optimized.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/segments-partitioned-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/segments-partitioned.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/segments-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/segments-verified-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/segments-verified.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/segments.xml` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/summarize.py` | AI 性能基准或验收驱动 |
| `engineering/acceptance/ai-operation-performance/v2-benchmark-source.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/v2-benchmark.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/verification.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/verify-client.mjs` | AI 性能基准或验收驱动 |
| `engineering/acceptance/ai-operation-performance/web-client-proof.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-operation-performance/web-client-v2-proof.json` | AI 性能采样、回归或验收记录 |
| `engineering/acceptance/ai-performance-interface-snapshot/v1/source.json` | 冻结 AI 源码清单与逐文件摘要 |
| `engineering/acceptance/ai-performance-interface-snapshot/v1/engineering/` | 冻结 AI 源码，共 220 项，路径见同版 source.json |
| `engineering/acceptance/ai-performance-interface-snapshot/v2/source.json` | 冻结 AI 源码清单与逐文件摘要 |
| `engineering/acceptance/ai-performance-interface-snapshot/v2/engineering/` | 冻结 AI 源码，共 222 项，路径见同版 source.json |
| `engineering/acceptance/ai-performance-interface-snapshot/v3/source.json` | 冻结 AI 源码清单与逐文件摘要 |
| `engineering/acceptance/ai-performance-interface-snapshot/v3/engineering/` | 冻结 AI 源码，共 223 项，路径见同版 source.json |

| `docs/current/engineering/engine-performance.md` | 当前引擎性能机制、接口与验收边界 |

| `rulepacks/stumpsville/tests/verify_remote_kp.py` | 远程 KP 双浏览器登录、主持、自动裁决及角色切换验收 |
| `rulepacks/stumpsville/tests/remote-kp-results.json` | 远程 KP 本地真实 WebRTC 验收结果 |

| `rulepacks/stumpsville/tests/remote-kp-cloud-results.json` | 远程 KP 公网强制 TURN 登录、主持及角色切换隔离证据 |

| `engineering/network-web/acceptance/2026-11-23-0.3.2.json` | 远程 KP 登录、本地及公网 TURN 主持闭环与 0.3.2 部署摘要 |

| `engineering/acceptance/rule-stage-delta/.gitignore` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/README.md` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/delta-v1.xml` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/delta-v2.xml` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/delta-v3.xml` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/freeze.py` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/handoff.json` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/interface-v1/engineering/backend/src/onlinecoc/host.py` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/interface-v1/engineering/backend/src/onlinecoc/registry.py` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/interface-v1/engineering/contracts/operations.json` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/interface-v1/source.json` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/measure.py` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/measurements.json` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/v1-source.json` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/v2-source.json` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/acceptance/rule-stage-delta/v3-source.json` | 活动规则修订增量暂存的专项、接口冻结、复现驱动或验收证据 |
| `engineering/backend/tests/test_rule_stage_delta.py` | 规则增量暂存的权限、完整校验、HTTP限额与故障恢复专项 |
| `engineering/acceptance/rule-stage-delta/work/` | Git忽略的隔离宿主、冻结运行树与pytest临时数据；不得用作正式存档 |

| `engineering/ai/src/onlinecoc_ai/change_overview.py` | AI 分步发布、配置校验及复现证据 |
| `engineering/ai/src/onlinecoc_ai/continuations.py` | AI 分步发布、配置校验及复现证据 |
| `engineering/ai/tests/test_staged_configuration.py` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/.gitignore` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/README.md` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/extension-live-final-source.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/extension-live-final.xml` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/extension-live-source.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/extension-live-verified-source.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/extension-live-verified.xml` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/extension-live.xml` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/files-manifest.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/final-validation-source.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/final-validation.xml` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/freeze.py` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/full-regression-source.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/full-regression.xml` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/idle-stage-final-source.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/idle-stage-final.xml` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/pack-matrix-final.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/pack-matrix.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/run_tests.py` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/staged-final-source.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/staged-final.xml` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/staged-first-source.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/staged-first.xml` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/staged-second-source.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/staged-second.xml` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/staged-third-source.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/staged-third.xml` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/staged-ui-source.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/staged-ui.xml` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/verification.json` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-configuration/verify_pack.py` | AI 分步发布、配置校验及复现证据 |
| `engineering/acceptance/ai-staged-interface-snapshot/v1/source.json` | AI 分步推进冻结源码清单与逐文件摘要 |
| `engineering/acceptance/ai-staged-interface-snapshot/v1/engineering/` | AI 分步推进冻结工程，226项详见同版source.json |
| `engineering/acceptance/ai-staged-interface-snapshot/v2/source.json` | AI 分步推进冻结源码清单与逐文件摘要 |
| `engineering/acceptance/ai-staged-interface-snapshot/v2/engineering/` | AI 分步推进冻结工程，226项详见同版source.json |
| `engineering/acceptance/ai-staged-configuration/work/` | Git忽略的隔离工程、存档与浏览器临时输出，不作为正式房间 |

| `engineering/acceptance/engine-issue-025/.gitignore` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/ai-query-context.xml` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/ai-wait-diagnostics.json` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/backend-regression.xml` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/baseline-source.json` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/baseline.xml` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/baseline2-source.json` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/baseline2.xml` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/fixed-source.json` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/fixed.xml` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/fixed2-source.json` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/fixed2.xml` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/freeze.py` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/handoff.json` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/interface-v1/engineering/backend/src/onlinecoc/data_queries.py` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/interface-v1/source.json` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/README.md` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/regression-source.json` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/backend/tests/test_room_state_artifacts.py` | ISSUE-025 稳定房间工件投影测试、差量与验收证据 |
| `engineering/acceptance/engine-issue-025/work/` | Git 忽略的基线、修复与回归隔离工程；非正式房间 |

| `engineering/acceptance/ai-ambiguity-recovery/.gitignore` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/README.md` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/combined-targeted-source.json` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/combined-targeted.xml` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/edit-publication-source.json` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/edit-publication.xml` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/engine-self-stale-source.json` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/engine-self-stale.xml` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/engine-stale-confirmed-source.json` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/engine-stale-confirmed.xml` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/engine-stale-reproduction-source.json` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/engine-stale-reproduction.xml` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/files-manifest.json` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/freeze.py` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/full-regression-source.json` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/full-regression.xml` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/repairs-first-interrupted.json` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/repairs-first-source.json` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/repairs-second-source.json` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/repairs-second.xml` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/run_tests.py` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/v2-full-regression-source.json` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/v2-targeted-source.json` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/v2-targeted.xml` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/verification.json` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-recovery/verify.py` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/ai/src/onlinecoc_ai/execution_ledger.py` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/ai/tests/test_ambiguity_recovery.py` | AI 模糊需求技术纠错、回执防重放或确定性验收证据 |
| `engineering/acceptance/ai-ambiguity-interface-snapshot/v1/source.json` | AI 模糊需求恢复冻结差量与逐文件摘要 |
| `engineering/acceptance/ai-ambiguity-interface-snapshot/v1/engineering/` | AI 模糊需求恢复冻结工程差量；逐文件清单见同版source.json |
| `engineering/acceptance/ai-ambiguity-interface-snapshot/v2/source.json` | AI 模糊需求恢复冻结差量与逐文件摘要 |
| `engineering/acceptance/ai-ambiguity-interface-snapshot/v2/engineering/` | AI 模糊需求恢复冻结工程差量；逐文件清单见同版source.json |
| `engineering/acceptance/ai-ambiguity-recovery/work/` | Git忽略的冻结依赖装配、合成房间和pytest输出；非正式存档 |

| `engineering/acceptance/ai-ambiguity-recovery/v2-full-regression.xml` | AI v2最终800项完整非浏览器回归结果 |

| `engineering/acceptance/ai-chat-interaction/baseline.xml` | AI 聊天滚动、输入与浏览器回归证据 |
| `engineering/acceptance/ai-chat-interaction/browser.json` | AI 聊天滚动、输入与浏览器回归证据 |
| `engineering/acceptance/ai-chat-interaction/files-manifest.json` | AI 聊天滚动、输入与浏览器回归证据 |
| `engineering/acceptance/ai-chat-interaction/long-history-editor.png` | AI 聊天滚动、输入与浏览器回归证据 |
| `engineering/acceptance/ai-chat-interaction/README.md` | AI 聊天滚动、输入与浏览器回归证据 |
| `engineering/acceptance/ai-chat-interaction/related-ui-recheck.xml` | AI 聊天滚动、输入与浏览器回归证据 |
| `engineering/acceptance/ai-chat-interaction/related-ui.xml` | AI 聊天滚动、输入与浏览器回归证据 |
| `engineering/acceptance/ai-chat-interaction/source.json` | AI 聊天滚动、输入与浏览器回归证据 |
| `engineering/acceptance/ai-chat-interaction/targeted.xml` | AI 聊天滚动、输入与浏览器回归证据 |
| `engineering/acceptance/ai-chat-interaction/verification.json` | AI 聊天滚动、输入与浏览器回归证据 |
| `engineering/acceptance/ai-chat-interaction/verify.py` | AI 聊天滚动、输入与浏览器回归证据 |
| `engineering/ai/tests/test_chat_interaction.py` | 长会话用户活动、原生组字、触屏、轮询及会话草稿浏览器回归 |
| `engineering/acceptance/ai-chat-ui-interface-snapshot/v1/source.json` | 聊天交互 v1 冻结差量逐文件摘要 |
| `engineering/acceptance/ai-chat-ui-interface-snapshot/v1/engineering/` | 聊天交互 v1 的三个冻结组件文件；逐文件清单见同版 source.json |

## 施工登记

本表是 Agent 和人员共同使用的占用登记表。所有施工开始前必须先读取本文件，按路径范围检查冲突，登记自己的唯一 ID、使用方式与任务。登记后重新读取确认记录仍在且无冲突，才可开始工作。详细规则见 [施工占用与冲突处理](../../standards/document-maintenance.md#8-施工占用与冲突处理)。

<!-- occupancy:start -->
| ID | 路径范围（相对项目根目录） | 方式 | 任务 | 开始时间（含时区） | 最后确认时间（含时区） |
| --- | --- | --- | --- | --- | --- |
<!-- occupancy:end -->

施工结束、取消或交接时必须释放自己的记录；无活动记录表示当前没有已登记的占用，不代表不存在未遵守约定的并发工作。
