# OnlineCOC

[简体中文](README.zh-CN.md) · [Engine design](docs/current/design/project-overview.md) · [Development process](PROCESS.md) · [Update notes](UPDATE-NOTES.md)

OnlineCOC is a prototype engine for running multiplayer tabletop RPGs. The host's computer resolves actions and saves the room between sessions. Players use a browser and see the information their characters are allowed to know.

## How the engine fits together

| Part | Responsibility |
| --- | --- |
| Engine | The Python host checks permissions, runs Lua rules and records the results in the room's save. Players share one campaign, even when they have discovered different things. [Engine architecture](docs/current/engineering/first-test.md) |
| Extension modules | The LAN gateway and web module connect players to the host. The optional room AI can propose rule changes for the game master (GM) to review during play. [Module directory](engineering/README.md) |
| Rulepacks | A pack supplies a particular game's rules, content and player interface. Stumpsville is one example. [Rulepack directory](rulepacks/README.md) |

**For GMs and players**, the engine supports local playtests, LAN tables and remote browser sessions that can resume from the same save. **For rule authors**, a pack is a place to try a new mechanic: write the action in Lua, run it in a test room and inspect the result. [Lua authoring guide](docs/current/engineering/lua-authoring.md)

<a id="play-stumpsville"></a>

## Try a rulepack · Stumpsville

<details>
<summary>Expand for the Windows download, first-session walkthrough and videos</summary>

This example uses the **Stumpsville** rulepack. The host needs Windows 10/11 x64. One computer with two browser tabs is enough to try the GM and player roles. The preview includes the runtime for offline installation. [Release notes](https://github.com/sd5913/OnlineCOC/releases/tag/v0.1.0-preview.2)

**Launch the example**

1. Download the [Win64 preview ZIP](https://github.com/sd5913/OnlineCOC/releases/download/v0.1.0-preview.2/OnlineCOC-Win64-v0.1.0-preview.2.zip).
2. Extract the entire ZIP to a short, writable path such as `D:\Games`.
3. Double-click `OnlineCOC-preview\Start.cmd`. The menu appears when setup is complete.

<a id="from-source"></a>

From a full source checkout, use these two steps instead:

1. Run [setup-game.cmd](engineering/setup-game.cmd) with internet access.
2. When `GAME_RUNTIME_READY` appears, run [start-panel.cmd](rulepacks/stumpsville/start-panel.cmd).

**Host a local session**

1. Select local play (**本机树桩镇** in the preview menu).
2. Create a save slot in the host panel.
3. Set an initial password of at least eight characters.
4. Click **启动房间** to start the room.

**Take both seats on one computer**

1. Sign in to the room as `kp` with the slot password.
2. Click **一键开场** on the GM's Room page.
3. Open the room address in a second browser tab.
4. Sign in as `player1` with the slot password.
5. Submit a preset character from the player tab.
6. Approve the character under **裁决** in the GM tab.
7. Confirm readiness in the player tab.

Keep the host panel and GM tab open during play. For character rules, combat and map controls, see the [Stumpsville player guide](rulepacks/stumpsville/docs/current/player-guide.md). [Save and resume](rulepacks/stumpsville/docs/current/usage.md) · [Credits and licensing](rulepacks/stumpsville/docs/current/sources.md)

<a id="multiplayer"></a>
<a id="room-ai"></a>

**Other ways to play**

- **Same LAN.** Friends join using the player address shown on the host's LAN panel. [LAN setup](rulepacks/stumpsville/docs/current/usage.md)
- **Remote play.** The host needs publishing authorization and trusted HTTPS. Players join with a URL and room code. [Web hosting guide](rulepacks/stumpsville/docs/current/web.md)
- **Room AI.** The preview's AI settings use a DeepSeek preset and the host's own API key. The GM controls which room data may be shared. [Room AI guide](rulepacks/stumpsville/docs/current/integrations.md)

**Trailer · 32 seconds**

https://github.com/user-attachments/assets/77f2f9d5-764e-4253-a489-76faf2667087

**First-session walkthrough · 1 min 45 sec · Chinese narration, English and Chinese captions**

https://github.com/user-attachments/assets/b236b238-37fa-4cf6-8eb6-e6061aa46a11

</details>

<a id="engine-demo"></a>

[Base engine QuickStart](docs/current/engineering/desktop-tools.md) · [Documentation](docs/README.md) · [Feedback](feedback/README.md)
