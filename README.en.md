# OnlineCOC · Online tabletop role-playing

[中文](README.md) · [Development process and AI collaboration](PROCESS.md) · [Shared issue register](docs/plans/Issues/README.md)

OnlineCOC lets a game master (GM, labelled **KP** in the interface) host a tabletop RPG for players in their browsers. The host keeps the room save. A rulepack supplies the characters, map, actions and rules. **Start with Stumpsville**, where each player plays a mouse exploring a settlement. An action can uncover a clue, open a route or change the contents of a backpack. Players can ask the GM to rule on anything the presets do not cover. To try both sides of the table on one computer, use two independent browser tabs.

## Choose your setup

| What you want to do | What you need |
| --- | --- |
| Play Stumpsville locally or use the room AI | A Windows x64 host with the full repository and the shared environment at `engineering/.venv` described below. You can turn AI off for a first game and play without a provider account. |
| Invite remote browser players | The host also needs the networking runtime and permission to publish to a room directory. Players need a WebRTC-capable browser, a portal address and a game account. |
| Try the base engine demo | In the project root, run `安装依赖.exe` (install dependencies), then `启动OnlineCOC.exe` (launch). Set an initial password of at least eight characters. Sign in at `http://127.0.0.1:8765` as `kp`, `player1` or `player2`. Use separate browser profiles for simultaneous accounts. Keep the launcher open while playing and close it to stop the host. These tools maintain a separate environment under `engineering/.runtime`. [Desktop launcher](docs/current/engineering/desktop-tools.md) |

Clone the [project repository](https://github.com/sd5913/OnlineCOC) or download its ZIP and extract it into a short, writable path such as `D:\OnlineCOC`. Paths below start in the folder containing `launcher-config.json`, `engineering` and `rulepacks`. Run launchers from your local copy.

## Play your first Stumpsville session

1. **Install the host dependencies in one step.** Double-click [engineering/setup-game.cmd](engineering/setup-game.cmd) with internet access on the first run. It downloads and verifies full Python, checks Tk and installs the locked dependencies. No system Python is required. Look for `GAME_RUNTIME_READY` before opening the pack panel or AI manager. To check again, run `.\engineering\setup-game.cmd -VerifyOnly` in PowerShell at the root. After a failure, check `engineering/.runtime/game-setup-logs/`, correct the reported issue and rerun setup.

   For manual setup, use the full Windows x64 distribution of CPython 3.14.2 with Tk and the Python launcher. In PowerShell at the project root, run the following commands. The initial dependency download requires internet access. The locked dependencies include Lua.

   ```powershell
   py -3.14 -m venv engineering/.venv
   .\engineering\.venv\Scripts\python.exe -m pip install --require-hashes -r engineering/requirements-runtime.lock
   .\engineering\.venv\Scripts\python.exe -m pip check
   ```

2. **Start the host.** Double-click [start-panel.cmd](rulepacks/stumpsville/start-panel.cmd) to select Stumpsville. Choose Local (本机). For a first session, you can clear AI assistant (AI助手). Create a save slot, set and confirm its initial password, then click Start room (启动房间). The local address defaults to `http://127.0.0.1:8899`. Keep the host panel running. You can minimise it.
3. **Seat the GM and a player.** Sign in as `kp` and start the session (一键开场) from the Room page (房间). Open the base address again or select New independent login page (新开独立登录页), and sign in as `player1` with the new slot's initial password. The player chooses and submits a preset character in the lobby. The GM approves it under Rulings (裁决). The player checks their backpack and marks themselves ready. Keep a signed-in GM page open to process actions.
4. **Check the first interaction.** At location 01, the entrance tunnel, choose Inspect the ground → Look closely (观察地面 → 仔细观察). A clue about impressions in the ground appears in the player's journal, and location 02, the main gate, appears on their map. For a first expedition, agree to record two distinct discoveries, bring back one item acquired during play and return everyone to the entrance. The GM checks the outcome. To follow the longer story, continue to the courtyard and take the village commission. [Stumpsville player guide](rulepacks/stumpsville/docs/current/player-guide.md)
5. **Stop and resume.** Click Stop room (停止房间) in the panel. Select the same slot next time. Saves live under `rulepacks/stumpsville/runtime/slots/`. An existing slot retains its active rules. Create a new one to try the pack's current defaults. [Save and recovery guide](rulepacks/stumpsville/docs/current/usage.md)

## Invite other players

The demo accounts in a fresh slot share the initial password. Before inviting others, use Account management (账号管理) in the host panel to create individual accounts or set separate passwords. Keep the GM login with the keeper.

**On the same network**, the host runs [start-lan.cmd](rulepacks/stumpsville/start-lan.cmd), selects the LAN adapter and save slot, starts the room, and copies the player address from the panel. Players on that network open the address and sign in with their game accounts. If a device cannot connect, check the selected adapter, listening port and connection diagnostics. The loopback address `127.0.0.1` works only on the host. [LAN instructions](rulepacks/stumpsville/docs/current/usage.md)

**For remote browser play**, use web mode for the full Stumpsville table. The older P2P client has its own basic state and chat interface. To use it, the host starts the game, runs `engineering/network-p2p/play.cmd`, selects the running host and publishes. The player obtains the complete join information, player ZIP and game account, extracts the ZIP on Windows with Python 3.14 x64, and runs `play.cmd`. After the first online installation, the player connects, signs in, downloads the content and sends a test chat message. [Legacy P2P client guide](engineering/network-p2p/README.md)

1. **Install networking on the host.** On Windows 10/11 x64, obtain the maintainer-built `OnlineCOC-Network-Setup.exe`, run it, select the **project root containing engineering**, and click One-click install (一键安装). It installs offline into `engineering/network-p2p/.venv`. If that runtime is busy, close the networking process normally and retry. The EXE is a build artifact. From a source-only checkout, install Python 3.14 x64 with the `py` launcher and run `.\engineering\network-p2p\setup.ps1` from the root in PowerShell. Then run `.\engineering\network-p2p\.venv\Scripts\python.exe -m pip install --no-deps -e engineering/network-web` to add the web module to that source environment. With the offline EXE, continue directly to step 2. [Installer, build instructions and checks](engineering/network-web/installer/README.md)
2. **Prepare the host's publishing configuration.** Obtain the directory configuration (default `engineering/network-p2p/local/client-config.json`), public CA certificate and publishing authorisation from the platform operator. For a self-hosted service, use the repository's configuration examples and [deployment guide](docs/current/engineering/network-p2p.md). The test portal uses a test CA. Browser players must obtain and trust its public certificate through a trusted channel.
3. **Publish the room.** Run [start-web.cmd](rulepacks/stumpsville/start-web.cmd), select the save slot and start it. In room management, open Web sharing and connections (网页分享与连接) and copy the creation string. Sign in to the portal's Create room page, paste the string, and select visibility and password settings. The host's single-use creation string expires after ten minutes. Send players the **join URL and eight-character room code** and assign game accounts separately.
4. **Join from a browser.** Register or sign in to the portal. Enter the room code and any required password, and wait for approval if enabled. Click Enter game (进入游戏), then Connect to host (连接房主), and sign in with the **game account** supplied by the host. Exchange messages in global chat to check the connection, then create characters as above. The host panel and a signed-in GM game page must stay open for play. [Stumpsville web guide](rulepacks/stumpsville/docs/current/web.md)

## Ask the room AI a question

1. Install the shared Stumpsville environment above. On the host, run [start-ai-manager.cmd](rulepacks/stumpsville/start-ai-manager.cmd). Under Providers (服务商), choose DeepSeek or a compatible service, enter the endpoint, model ID and credential supplied by your provider, enable the profile, and click Test connection (测试连接). The probe uses real provider quota. Enter the credential in the host's local manager.
2. Run [start-ai.cmd](rulepacks/stumpsville/start-ai.cmd), or select AI assistant in the room panel before starting a slot. Sign in as `kp`. In AI settings (AI 设置), confirm the provider, permission to make calls, which room information may be sent and whether players may start conversations. Existing slots retain their settings. Alternatively, in the standalone manager, add the local host address under Rooms and sessions, sign in as KP, and choose the provider and external-data scopes under KP review and settings.
3. Open AI chat on the GM's Rulings page and send a read-only question such as “How can I start this session with the information available in the room?” Look for the reply in that conversation. An authorised player can use the personal AI tab on the right of their scene. For a rule change or item grant, the GM can inspect the proposed changes, risks and execution result in the ruling queue.
4. If the manager fails to open, check the shared environment. If it opens but no answer appears, check the provider probe, the room's chosen model, its call and data permissions, and the task status. [AI manager](docs/current/engineering/ai-manager.md) · [Stumpsville integration](rulepacks/stumpsville/docs/current/integrations.md)

## Verification scope

The shared installer ran in a fresh Windows x64 project with an empty cache. Tk and all 29 runtime dependencies passed their checks. The AI onboarding test configured a simulated provider, retried a failed submission and confirmed that the request reached GM review. A previous run exercised the real DeepSeek service. [Current AI onboarding checks](engineering/acceptance/ai-install-guide/README.md) · [Historical live-provider result](engineering/acceptance/ai-runtime/deepseek-live.json)

The base engine installed from an empty cache in an isolated directory. Three accounts signed in, the clients saw the same Lua action result, and the save survived a restart. The networking installer reported a busy runtime and succeeded in the same directory after it was stopped. [Engine installation checks](engineering/desktop/acceptance-install-audit/README.md) · [Networking installation checks](engineering/network-web/acceptance/2026-11-26-firstplay.json)

On 26 November 2026, a fresh Windows room reproduced the entrance action, the personal clue and the map update. Two browsers on one computer entered the same Stumpsville room over real WebRTC and exercised 18 preset actions. A human playthrough across independent home or mobile networks is still open. Historical public-network checks include forced TURN relay and remote GM operation. [Two-browser results](rulepacks/stumpsville/tests/web-results.json) · [Earlier public remote GM check](rulepacks/stumpsville/tests/remote-kp-cloud-results.json)

## Credits, progress and developer resources

- Stumpsville adapts the Mausritter SRD by Isaac Williams / Losing Games. The pack distinguishes the rules, third-party adventure references, original branches and generated runtime art. Check the corresponding terms before redistributing assets. [Sources and licensing](rulepacks/stumpsville/docs/current/sources.md) · [Runtime illustrations](rulepacks/stumpsville/assets/runtime/README.md)
- The project uses Python, FastAPI, WebSocket, Lua/Lupa and browser WebRTC. Dated changes, tests, open issues and the use of AI during development are documented in the [development record](PROCESS.md), [shared issues and plans](docs/plans/Issues/README.md) and [engine acceptance report](docs/current/engineering/first-test-acceptance.md).
- Rule authors can start with the [Lua guide](docs/current/engineering/lua-authoring.md), [rulepack directory](rulepacks/README.md) and [developer reference](docs/current/engineering/developer-reference/README.md). [Lasers & Feelings](rulepacks/lasers-and-feelings/README.md) is another playable pack.
- For operations, see the [base host](docs/current/engineering/first-test.md), [chat backend](docs/current/engineering/chat-backend.md), [desktop room manager](tools/room-manager/README.md) and [account tools](tools/host-accounts/README.md). Contributors can consult the [workspace register](docs/current/engineering/hierarchy.md), [documentation standard](docs/standards/document-maintenance.md) and [documentation index](docs/README.md).
