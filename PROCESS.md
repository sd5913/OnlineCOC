# How OnlineCOC was built

[User guide](README.md) · [Update notes](UPDATE-NOTES.md) · [Shared issue register](docs/plans/Issues/README.md)

Could a group change the rules of a running game, ask its game master for a ruling, and continue with everyone seeing the same outcome? We tried that first in a small Lua host. Stumpsville gave us a practical test: a player should be able to create a mouse, act in a scene and see the ruling reflected in their own view. [Lua prototype](engineering/lua-authoring-prototype/README.md)

The [update notes](UPDATE-NOTES.md) trace the implementation from the first host through browser play and the shared Windows installer. The decisions below show how the project lead and the Codex work sessions used those builds to test the game.

## Who sees what at the table?

The project lead asked for separate GM controls and player views, an independent chat window, and private conversations alongside room, scene and party channels. A player looking at the GM map could learn about locations their mouse had yet to discover.

The Stumpsville work session separated the GM's room, map and ruling pages. A GM can also open a player view to check what that player actually sees. The player's journal and map reflect discoveries made during play. [Interface guide](rulepacks/stumpsville/docs/current/interface.md) · [Player knowledge](rulepacks/stumpsville/docs/current/player-knowledge.md)

## When should the assistant ask the GM?

The AI and Stumpsville work sessions tried **16 ambiguous requests** against a live DeepSeek service in isolated rooms. A scripted GM supplied decisions about a travel payment and whether to reveal a plot hint. The tests compared the resulting inventory, scene, rule or answer with the request.

| Check | Before | After the final full run |
| --- | ---: | ---: |
| Requests whose actual outcome matched the intended result | 12 of 16 | 15 of 16 |

The team revised how the assistant resolved references, retried technical failures and published changes. It also corrected a test that searched for the word *rain* even though the new scene description already said the eaves were dripping. The report preserves that extra exchange and the remaining failure. [Live comparison](rulepacks/stumpsville/tests/ambiguous-suite-live-report.md) · [Recovery tests](engineering/acceptance/ai-ambiguity-recovery/README.md)

## Why did chat lose its place?

When a new message arrived, a reader could lose their place and someone composing Chinese text could lose focus. The project lead set a concrete rule: follow new messages after a second without interaction, and preserve the reading position while the user types or scrolls.

The AI component work session changed how the message list and editor updated. The pack work session kept the embedded editor alive when the player page refreshed. Both changes mattered because either component could interrupt the same keystroke.

| Test stage | What the team observed |
| --- | --- |
| Before the fix | Only 3 of 12 baseline checks passed. |
| After the fix | 61 distinct component checks passed. Eight separate pack checks exercised the GM view, player view and pop-up. |

The runs used Edge and simulated input events. Physical phone input remains open. [Baseline and retests](engineering/acceptance/ai-chat-interaction/README.md) · [Pack results](rulepacks/stumpsville/tests/player-layout-results.json)

## Could a first-time host start a session?

On 26 November, the project lead chose Stumpsville as the recommended first game and requested installation guides in English and Chinese. Codex coordinated the engine, networking, AI and pack work sessions. Comparing the startup paths exposed a mismatch: the base demo installed its own environment, while the Stumpsville panel and AI manager expected another interpreter.

The AI work session added a shared installer and tested it in a fresh project with no Python on the path and no download cache. The pack session checked the other end of the experience: inspecting the ground in a new room added a clue to the journal and revealed the main gate on the map. These became the first and last checks for a new host following the guide. [Installer evidence](engineering/acceptance/ai-install-guide/README.md) · [First-play steps](rulepacks/stumpsville/README.md)

## Contributions and evidence

Codex assisted with implementation, diagnosis, automated checks and documentation. During a game, the optional room AI operates within the permissions and review settings chosen by the GM. Generated illustrations are credited in the pack's asset notes. For dated changes, outstanding work and playtest observations, see the linked records.

[Update notes](UPDATE-NOTES.md) · [AI development archive](docs/history/2026-11-20-ai-development-records.md) · [Artwork credits](rulepacks/stumpsville/assets/runtime/README.md) · [User feedback](feedback/README.md)
