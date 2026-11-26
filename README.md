# OnlineCOC

[简体中文](README.zh-CN.md) · [Download for Windows x64](https://github.com/sd5913/OnlineCOC/releases/download/v0.1.0-preview.2/OnlineCOC-Win64-v0.1.0-preview.2.zip) · [Release v0.1.0-preview.2](https://github.com/sd5913/OnlineCOC/releases/tag/v0.1.0-preview.2)

Host a tabletop RPG on Windows and let friends join in their browsers. Start with **Stumpsville**: lead a party of mice into the entrance tunnel, follow clues and uncover the map together.

**Trailer · 32 seconds**

https://github.com/user-attachments/assets/77f2f9d5-764e-4253-a489-76faf2667087

<a id="play-stumpsville"></a>

## Play your first session

1. On Windows 10/11 x64, extract the downloaded ZIP to a short writable path such as `D:\Games`. Double-click `OnlineCOC-preview\Start.cmd`. The first run installs the bundled dependencies offline.
2. Choose **本机树桩镇** (local Stumpsville), create a save slot, set a password of at least eight characters and start the room. You can leave AI off.
3. Sign in as `kp` and select **一键开场**. In another tab, sign in as `player1` with the slot password and submit a character. The GM approves it under **裁决** (Rulings), then the player confirms readiness.
4. In the entrance tunnel, choose **观察地面 → 仔细观察** (Inspect the ground → Look closely). Check the journal and map for your discovery. Keep the host panel and GM page open during play. Stop the room from the panel and reopen the same slot to resume.

<details>
<summary>Watch the first-session guide · 1 min 45 sec · Chinese narration, English and Chinese captions</summary>

https://github.com/user-attachments/assets/b236b238-37fa-4cf6-8eb6-e6061aa46a11

</details>

<a id="multiplayer"></a>
<a id="room-ai"></a>

## Multiplayer and AI

| Scenario | How to start |
| --- | --- |
| Same LAN | In **Network settings**, choose the LAN adapter and share the player address. Give each player a game account. [LAN guide](rulepacks/stumpsville/docs/current/usage.md) |
| Remote play | Configure the operator's publishing token and trusted HTTPS, then share the join URL and room code. [Web hosting guide](rulepacks/stumpsville/docs/current/web.md) |
| Room AI | In **AI settings**, enter the host's DeepSeek API key. Enable AI in the room and choose what information the GM allows it to send. Calls use the host's quota. [AI guide](rulepacks/stumpsville/docs/current/integrations.md) |

<a id="from-source"></a>
<a id="engine-demo"></a>

## From source

Run [setup-game.cmd](engineering/setup-game.cmd) from a full checkout. First-time setup needs internet. After `GAME_RUNTIME_READY`, run [start-panel.cmd](rulepacks/stumpsville/start-panel.cmd). The Windows preview includes shared combat and map zoom/reset from [217039b](https://github.com/sd5913/OnlineCOC/commit/217039bc179246c1eb2b0bd6156cd153176ccb20). [Base engine QuickStart](docs/current/engineering/desktop-tools.md)

[Player guide](rulepacks/stumpsville/docs/current/player-guide.md) · [Credits & licensing](rulepacks/stumpsville/docs/current/sources.md) · [Development process](PROCESS.md) · [Update notes](UPDATE-NOTES.md) · [Feedback](feedback/README.md)
