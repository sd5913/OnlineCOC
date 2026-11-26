# Update notes

[User guide](README.md) · [Development process](PROCESS.md) · [Issue register](docs/plans/Issues/README.md)

## 26 November 2026 · Windows x64 v0.1.0-preview.2

- Packaged the Stumpsville combat rules and map controls from [217039b](https://github.com/sd5913/OnlineCOC/commit/217039bc179246c1eb2b0bd6156cd153176ccb20). Players can fight the same enemy and flee, and can zoom or reset the map on desktop and mobile layouts. [Download and release notes](https://github.com/sd5913/OnlineCOC/releases/tag/v0.1.0-preview.2)

## 26 November 2026 · Windows x64 v0.1.0-preview.1

- Added a downloadable offline build of Stumpsville from `e5b3244`, with a unified launcher, networking setup and a single-key DeepSeek preset. The bilingual guides include the trailer and first-session video. [Release notes and downloads](https://github.com/sd5913/OnlineCOC/releases/tag/v0.1.0-preview.1)
- On `main`, Stumpsville adds shared combat, escape and incapacitation, plus map zoom and reset controls on desktop and mobile. The downloadable preview predates these changes. [Player guide](rulepacks/stumpsville/docs/current/player-guide.md)

## 26 November 2026 · Documentation and desktop tools

- The repository now opens with the English guide. The [Chinese guide](README.zh-CN.md) follows the same routes for local play, multiplayer, room AI and the engine demo.
- The Windows base-engine installer and launcher are in [QuickStart](QuickStart/). Keep that folder beside `engineering/` and the root `launcher-config.json`. Existing installations keep their project-relative runtime and save paths.
- Playtesters can record bugs, suggestions and observations in the [feedback folder](feedback/README.md).

## 26 November 2026

- Added one-step Windows setup for Stumpsville and the AI manager. The installer prepares the shared Python/Tk environment and exposes a verification command.
- Published bilingual first-play guides, an English development record and installation evidence covering the engine, AI, LAN and browser play. [Commit 4e2273e](https://github.com/sd5913/OnlineCOC/commit/4e2273eab925b6d6eca2e59bd73e54ef6fd429b4)

## 20–23 November 2026

- Added a starter objective for Stumpsville and support for a remote GM. Players can pick up eligible objects directly from a scene. [Starter objective](https://github.com/sd5913/OnlineCOC/commit/653dd842348c389543a46c3a469ac643e379ff92) · [Remote GM and pickups](https://github.com/sd5913/OnlineCOC/commit/32cd26ba6393ce037b989b0a4481ba6f80b01c47)
- Improved review continuity and history recovery for room AI. Revised staged configuration changes, recovery from ambiguous requests and the chat editor's behaviour during updates. [Review history](https://github.com/sd5913/OnlineCOC/commit/d879cefd2e8e400e600c8f35dfc6611519fa3250) · [Staged changes and chat](https://github.com/sd5913/OnlineCOC/commit/86ee58ff364f4a122b682802d385c50a313bf6f4)

## 16–19 November 2026

- Integrated browser networking, localisation tools and the room AI with Stumpsville. Player knowledge then determined which clues and scene actions each participant could see. [Integrated build](https://github.com/sd5913/OnlineCOC/commit/a59d875aa6f4c23b87e69a211a2d23a4cbbfdf56) · [Player knowledge and menus](https://github.com/sd5913/OnlineCOC/commit/5c4ff689e6067183d4a6d352f8082e12eafd19d4)

## 10–12 November 2026

- Added the Stumpsville pack and LAN gateway, followed by a LAN launcher, connection diagnostics and a fix for player actions over HTTP. [Stumpsville and LAN](https://github.com/sd5913/OnlineCOC/commit/11306869d0b2c48d380882fa11f8ffc4acceb8fd) · [LAN follow-up](https://github.com/sd5913/OnlineCOC/commit/dff35404a661f8f483b4ee3c3741cd5fc866c28a)

## 5 November 2026

- Added playable rulepacks, dedicated launchers and automated game workflows. Room and host-account managers gave the GM controls for administering a running session. [Playable packs](https://github.com/sd5913/OnlineCOC/commit/73832baae4138caabfb2734ae8970f54b206557b) · [Room tools](https://github.com/sd5913/OnlineCOC/commit/4c593cc3fa4141bf95913f45964aa33233c45007)

## 30 October 2026

- Introduced the Lua authoring prototype and the first playable host, including persistent rooms, chat, the browser console and Windows setup tools. [Prototype](engineering/lua-authoring-prototype/README.md) · [First host](https://github.com/sd5913/OnlineCOC/commit/4cafe52f5cc846ef9f0ca9c9a3f4c54d5aca5291)
