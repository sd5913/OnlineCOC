# OnlineCOC

[简体中文](README.zh-CN.md) · [Update notes](UPDATE-NOTES.md) · [Development process](PROCESS.md) · [Player feedback](feedback/README.md)

Host a tabletop RPG from a Windows PC and let players join in their browsers. The host keeps the save. A rulepack supplies the characters, map and rules, and the game master (**KP** in the interface) decides what happens when players try something outside the preset actions.

**First game? Try Stumpsville.** Lead a party of mice into a settlement, discover a route together and bring something back. You can play both the GM and a player in two independent tabs on one computer.

| I want to… | Start here |
| --- | --- |
| Play or host Stumpsville | [Install and play](#play-stumpsville) |
| Invite another player | [LAN and remote browser play](#multiplayer) |
| Use AI during a session | [Configure the room assistant](#room-ai) |
| Try the base engine console | [Windows QuickStart](#engine-demo) |

<a id="play-stumpsville"></a>

## Play Stumpsville

Clone the [repository](https://github.com/sd5913/OnlineCOC) or download and extract the full ZIP to a short, writable path such as `D:\OnlineCOC`. Run launchers from the extracted project. Commands below start in the folder containing `launcher-config.json`.

1. **Install.** On Windows x64, run [setup-game.cmd](engineering/setup-game.cmd). The first run downloads Python, checks Tk and installs the locked dependencies into `engineering/.venv`. When you see `GAME_RUNTIME_READY`, the game panel and AI manager are ready to open.
2. **Open a room.** Run [start-panel.cmd](rulepacks/stumpsville/start-panel.cmd), select **Local** (本机), create a save slot, set its initial password and click **Start room** (启动房间). You can clear **AI assistant** for this first game. Keep the host panel running. The local address defaults to `http://127.0.0.1:8899`.
3. **Seat the GM and player.** Sign in as `kp` and click **一键开场** on the Room page. Open the base address again for an independent login and sign in as `player1` with the slot's initial password. Submit a preset character. The GM approves it under **Rulings** (裁决), then the player checks their backpack and marks themselves ready. Keep a signed-in GM page open for automatic rulings.
4. **Make a discovery.** In **01 · Entrance Tunnel**, choose **Inspect the ground → Look closely** (观察地面 → 仔细观察). Check the player's journal for the ground-impression clue and their map for **02 · Main Gate**. For a short expedition, record two discoveries, collect one new item and get everyone back to the entrance. For the longer story, take the commission in the courtyard. [Player guide](rulepacks/stumpsville/docs/current/player-guide.md)
5. **Save and return.** Click **Stop room** in the panel. Reopen the same slot to resume with its active rules. Saves are under `rulepacks/stumpsville/runtime/slots/`. [Backup and recovery](rulepacks/stumpsville/docs/current/usage.md)

<details>
<summary>Verify, repair or install dependencies manually</summary>

Run `.\engineering\setup-game.cmd -VerifyOnly` from the project root. If setup failed, check `engineering/.runtime/game-setup-logs/`, correct the reported problem and rerun the installer.

For a manual install, use full CPython 3.14.2 x64 with Tk and the Python launcher. The initial download requires internet access. Lua comes with the locked dependencies.

```powershell
py -3.14 -m venv engineering/.venv
.\engineering\.venv\Scripts\python.exe -m pip install --require-hashes -r engineering/requirements-runtime.lock
.\engineering\.venv\Scripts\python.exe -m pip check
```

</details>

<a id="multiplayer"></a>

## Invite players

The initial demo accounts share a password. In the host panel's **Account management** (账号管理), create individual game accounts or change their passwords before inviting others.

### On the same LAN

Run [start-lan.cmd](rulepacks/stumpsville/start-lan.cmd), choose the LAN adapter and save slot, and start the room. Copy the **player address** from the panel. Players open it in their browsers and sign in with their game accounts. If they cannot connect, check the adapter, port and diagnostics. The loopback address `127.0.0.1` works only on the host. [LAN guide](rulepacks/stumpsville/docs/current/usage.md)

### Across the internet

1. **Host software.** Prepare the shared game environment above. On Windows 10/11 x64, run the separately distributed `OnlineCOC-Network-Setup.exe`, select the **project root containing engineering** and click **一键安装**. It installs the network runtime offline. If the runtime is busy, stop sharing and retry in the same directory. [Installer guide](engineering/network-web/installer/README.md)
2. **Directory access.** Obtain the publishing configuration, authorisation and public CA certificate from the platform operator. The default config path is `engineering/network-p2p/local/client-config.json`. Players using the test portal need to obtain and trust its public CA certificate through a trusted channel. [Self-hosted deployment](docs/current/engineering/network-p2p.md)
3. **Host invitation.** Run [start-web.cmd](rulepacks/stumpsville/start-web.cmd), select a slot and start the room. In **网页分享与连接**, copy the creation string into the portal's **Create room** page. Choose visibility and password. The single-use creation string is for the host and expires after ten minutes. Give players the **join URL and eight-character code**, plus their individual game accounts.
4. **Player login.** Use a WebRTC-capable browser to sign in to the portal, enter the code and any room password, and wait for approval if enabled. Click **Enter game → Connect to host**, then sign in with the **game account**. Exchange a message in global chat. Keep the host panel and a GM page running. [Stumpsville web guide](rulepacks/stumpsville/docs/current/web.md)

<details>
<summary>Source-only networking setup and the legacy P2P client</summary>

With a source checkout and Python 3.14 x64 with the `py` launcher, run these commands in PowerShell to prepare the networking environment:

```powershell
.\engineering\network-p2p\setup.ps1
.\engineering\network-p2p\.venv\Scripts\python.exe -m pip install --no-deps -e engineering/network-web
```

For legacy P2P state and chat, start the host, run `engineering/network-p2p/play.cmd`, select the running host and publish. The player extracts the supplied ZIP on Windows with Python 3.14 x64, runs `play.cmd` online for its first installation, connects with the full join information, signs in and downloads the content. [Legacy P2P guide](engineering/network-p2p/README.md)

</details>

<a id="room-ai"></a>

## Ask the room AI

1. After installing the shared game environment, run [start-ai-manager.cmd](rulepacks/stumpsville/start-ai-manager.cmd) on the host. Under **Providers** (服务商), enable DeepSeek or a compatible service, enter its endpoint and model ID, and save the key in the credential field. **Test connection** uses real provider quota.
2. Open [start-ai.cmd](rulepacks/stumpsville/start-ai.cmd) or enable AI in the room panel. Start the slot, sign in as `kp`, and under **AI settings** select the provider, allow calls and choose which information may leave the room. Set player chat permissions as needed. In the standalone manager, add the local host address under **Rooms and sessions** and sign in as KP to configure the same room.
3. On the GM's **Rulings** page, ask “How can I start this session with the information available in the room?” Check for a reply. Players with permission have a personal AI tab. For a rule change or item grant, review the proposed changes and risks in the ruling queue, then check the execution result.

If no reply appears, check the provider probe, the selected model, the room's call and data permissions, and the task status. [Manager guide](docs/current/engineering/ai-manager.md) · [Pack integration](rulepacks/stumpsville/docs/current/integrations.md)

<a id="engine-demo"></a>

## Windows QuickStart for the base engine

Open the **QuickStart** folder in the full project. Run [安装依赖.exe](QuickStart/安装依赖.exe) to install dependencies, then [启动OnlineCOC.exe](QuickStart/启动OnlineCOC.exe) to start the console. Set an initial password of at least eight characters. Sign in at `http://127.0.0.1:8765` as `kp`, `player1` or `player2`. Use separate browser profiles for simultaneous accounts. Closing the launcher stops the host. This demo uses its own environment under `engineering/.runtime`. [Desktop guide](docs/current/engineering/desktop-tools.md)

## What has been tested

| Scenario | Evidence |
| --- | --- |
| First installation | An empty-cache Windows install verified Tk and 29 dependencies. The base console also passed login, shared Lua action and save/restart checks. [Shared setup](engineering/acceptance/ai-install-guide/README.md) · [Base engine](engineering/desktop/acceptance-install-audit/README.md) |
| Multiplayer | The network installer recovered from a busy runtime. Two browsers on one computer exercised 18 Stumpsville actions over WebRTC. Earlier runs covered public TURN and remote GM operation. A human playthrough on independent home or mobile networks remains open. [Installer](engineering/network-web/acceptance/2026-11-26-firstplay.json) · [Two browsers](rulepacks/stumpsville/tests/web-results.json) · [Remote GM](rulepacks/stumpsville/tests/remote-kp-cloud-results.json) |
| Room AI | The onboarding check used a simulated provider and retried a submission through GM review. A previous run exercised the real DeepSeek service. [Onboarding](engineering/acceptance/ai-install-guide/README.md) · [Live-provider record](engineering/acceptance/ai-runtime/deepseek-live.json) |

## Credits and developer resources

- Stumpsville adapts the Mausritter SRD by Isaac Williams / Losing Games. The pack distinguishes the rules, third-party adventure references, original branches and generated runtime art. Check the corresponding terms before redistributing assets. [Sources and licensing](rulepacks/stumpsville/docs/current/sources.md) · [Runtime illustrations](rulepacks/stumpsville/assets/runtime/README.md)
- The project uses Python, FastAPI, WebSocket, Lua/Lupa and browser WebRTC. Dated changes, tests, open issues and the use of AI during development are documented in the [development record](PROCESS.md), [shared issues and plans](docs/plans/Issues/README.md) and [engine acceptance report](docs/current/engineering/first-test-acceptance.md).
- Rule authors can start with the [Lua guide](docs/current/engineering/lua-authoring.md), [rulepack directory](rulepacks/README.md) and [developer reference](docs/current/engineering/developer-reference/README.md). [Lasers & Feelings](rulepacks/lasers-and-feelings/README.md) is another playable pack.
- For operations, see the [base host](docs/current/engineering/first-test.md), [chat backend](docs/current/engineering/chat-backend.md), [desktop room manager](tools/room-manager/README.md) and [account tools](tools/host-accounts/README.md). Contributors can consult the [workspace register](docs/current/engineering/hierarchy.md), [documentation standard](docs/standards/document-maintenance.md) and [documentation index](docs/README.md).
