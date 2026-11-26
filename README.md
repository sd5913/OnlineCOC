# OnlineCOC

[简体中文](README.zh-CN.md) · [Download for Windows x64](https://github.com/sd5913/OnlineCOC/releases/download/win64-preview-e5b3244/OnlineCOC-Windows-x64-preview-e5b3244.zip) · [Release notes & subtitles](https://github.com/sd5913/OnlineCOC/releases/tag/win64-preview-e5b3244) · [Player feedback](feedback/README.md)

Host a tabletop RPG on Windows and invite friends to play in their browsers. In **Stumpsville**, your party of mice explores a settlement together. Players choose actions and keep their discoveries. The game master (**KP** in the interface) handles rulings and the host keeps the save.

**Trailer · 32 seconds.** Explore the entrance tunnel with a friend, then see a rule change take effect during play. The AI sequence uses a simulated proposal and shows the actual GM approval and player roll.

https://github.com/user-attachments/assets/77f2f9d5-764e-4253-a489-76faf2667087

[Start a session](#play-stumpsville) · [Invite players](#multiplayer) · [Use AI](#room-ai) · [Run from source](#from-source)

<a id="play-stumpsville"></a>

## Start your first session

**Host requirements:** Windows 10/11 x64, PowerShell 5.1+, .NET Framework and a browser. The preview includes Python and the game dependencies for offline setup. One computer is enough to try both roles.

1. **Launch.** Download the [Windows preview ZIP](https://github.com/sd5913/OnlineCOC/releases/download/win64-preview-e5b3244/OnlineCOC-Windows-x64-preview-e5b3244.zip) and extract it to a short, writable path such as `D:\Games`. Open `OnlineCOC-preview\Start.cmd`. When setup finishes, choose the first menu item, **本机树桩镇** (local Stumpsville).
2. **Create a room.** In the host panel, choose local play, create a save slot, set an initial password of at least eight characters and start the room. You can leave AI off. Keep the panel running. The default address is `http://127.0.0.1:8899`.
3. **Take your seats.** Sign in as `kp` and click **一键开场** on the Room page. Open the room's base address in another tab. Sign in as `player1` with the slot password and submit a preset character. The GM approves it under **裁决** (Rulings), then the player checks their backpack and confirms readiness. Keep the GM page open.
4. **Find a clue.** At **01 · Entrance Tunnel**, choose **观察地面 → 仔细观察** (Inspect the ground → Look closely). Check the player's journal for the marks in the mud and the map for **02 · Main Gate**. For a longer expedition, take the commission in the courtyard. [Player guide](rulepacks/stumpsville/docs/current/player-guide.md)
5. **Return later.** Stop the room in the host panel. Select the same slot next time. Back up `userdata/rooms/` with the room stopped and keep the old directory when trying another version. [Preview notes & checksum](https://github.com/sd5913/OnlineCOC/releases/tag/win64-preview-e5b3244)

**First-session video · 1 minute 45 seconds.** Follow the host and player through installation, character approval, discovery and save recovery. Both films have Chinese narration and English and Chinese subtitles.

https://github.com/user-attachments/assets/b236b238-37fa-4cf6-8eb6-e6061aa46a11

<a id="multiplayer"></a>

## Invite players

Before sharing a room, create individual game accounts or change the demo passwords under **账号管理** (Account management). Open **联网设置与安装** (Network settings) in the preview menu.

| Where are the players? | Host | Player |
| --- | --- | --- |
| Same LAN | Select the LAN adapter and slot, start the room and copy the **player address**. | Open that address in a browser and sign in with a game account. |
| Different networks | Install the bundled network runtime. Enter the operator's directory URL, publishing token and trusted CA if required. Start the web room and claim the creation string in the portal. | Sign in to the portal, enter the eight-character room code and any room password, then choose **Enter game → Connect to host** and sign in with a game account. |

The creation string belongs to the host and expires after ten minutes. Share the join URL and room code with players. The test portal uses a project CA. Obtain its public certificate through a trusted channel. If a LAN player cannot connect, check the chosen adapter and port. `127.0.0.1` points to the player's own computer. [LAN guide](rulepacks/stumpsville/docs/current/usage.md) · [Remote play](rulepacks/stumpsville/docs/current/web.md) · [Self-hosting](docs/current/engineering/network-p2p.md)

<a id="room-ai"></a>

## Use AI at the table

1. In the preview menu, open **AI 设置**. The DeepSeek endpoint and model are preset. The host enters their own API key. Saving it keeps it in the current Windows user's protected store. **Test connection** and model requests use the host's provider quota.
2. Enable **AI assistant** in the room panel. As `kp`, select the provider, allow calls and choose what room information may be sent. Grant player chat access as needed.
3. Ask how to begin the adventure using the room's current information. For a rule change, review the proposal and its risks, approve publication, then try the action in the same room. If no answer appears, check the connection test, room permissions and task status. [AI manager](docs/current/engineering/ai-manager.md) · [Stumpsville AI integration](rulepacks/stumpsville/docs/current/integrations.md)

<a id="from-source"></a>

## Run from source

Use a checkout of `main` for the latest combat rules and map controls. The downloadable preview is built from [e5b3244](https://github.com/sd5913/OnlineCOC/commit/e5b3244aaa30ba7905bcf8f4bf57b28c7a76a652).

| Task | Source entry point |
| --- | --- |
| Install | Clone or extract the complete repository into a short writable path. Run [setup-game.cmd](engineering/setup-game.cmd) from the project root. The first run downloads Python and the locked dependencies. Wait for `GAME_RUNTIME_READY`. |
| Start or resume | Run [start-panel.cmd](rulepacks/stumpsville/start-panel.cmd) and follow the room and player steps above. Source saves live in `rulepacks/stumpsville/runtime/slots/`. |
| Host multiplayer | Use [start-lan.cmd](rulepacks/stumpsville/start-lan.cmd) or [start-web.cmd](rulepacks/stumpsville/start-web.cmd). Prepare the separate web runtime using the instructions below. [Network installer](engineering/network-web/installer/README.md) |
| Configure AI | Open [start-ai-manager.cmd](rulepacks/stumpsville/start-ai-manager.cmd), enable a provider, set its endpoint and model, and save the host's key. Use [start-ai.cmd](rulepacks/stumpsville/start-ai.cmd) or enable AI in the room panel. |

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

<details>
<summary>Source-only networking setup and the legacy P2P client</summary>

With a source checkout and Python 3.14 x64 with the `py` launcher, run these commands in PowerShell to prepare the networking environment:

```powershell
.\engineering\network-p2p\setup.ps1
.\engineering\network-p2p\.venv\Scripts\python.exe -m pip install --no-deps -e engineering/network-web
```

For legacy P2P state and chat, start the host, run `engineering/network-p2p/play.cmd`, select the running host and publish. The player extracts the supplied ZIP on Windows with Python 3.14 x64, runs `play.cmd` online for its first installation, connects with the full join information, signs in and downloads the content. [Legacy P2P guide](engineering/network-p2p/README.md)

</details>

<a id="engine-demo"></a>

<details>
<summary>Windows QuickStart for the base engine</summary>

Open the **QuickStart** folder in the full project. Run [安装依赖.exe](QuickStart/安装依赖.exe) to install dependencies, then [启动OnlineCOC.exe](QuickStart/启动OnlineCOC.exe) to start the console. Set an initial password of at least eight characters. Sign in at `http://127.0.0.1:8765` as `kp`, `player1` or `player2`. Use separate browser profiles for simultaneous accounts. Closing the launcher stops the host. This demo uses its own environment under `engineering/.runtime`. [Desktop guide](docs/current/engineering/desktop-tools.md)

</details>

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
