# Phantom · Beta 1 — build 1.3.10

- Fix premature opponent deck identities during setup and mulligan, including Azalina Soulsever. Internal setup reveals no longer appear on the opponent rail before both players finish choosing.
- Completing the mulligan does not automatically expose a suppressed identity. A fresh reveal is required; the legitimate post-mulligan start-of-game reveal remains visible.
- Apply the observation boundary to both log streams and add a regression for the period when the local player has not yet been identified.

Validation: 271 Python tests and line-by-line replay of the reported match passed. This remains an unsigned beta; match history and game definitions remain local.

# Phantom · Beta 1 — build 1.3.9

- Add a separate Avalonia effect-counter panel beneath the player rail: Aessina progress and remaining friendly deaths, Starsurge death count, and the authoritative Herald amount.
- Reserve space within the existing overlay bounds to protect the game hand and player banner. Hide irrelevant counters and reset with each match.
- Show unknown rather than inventing a total when attaching to incomplete game data.
- Make the Update result identify the installed version when no files need replacing.
- Correct stale current installation/manual versions and publication instructions; check guide versions during release validation.

This update does not claim universal mechanic-counter coverage. Game data, match history and definitions remain local. Historical release notes follow.

# Phantom · Beta 1 — build 1.3.8

Observation-only and tracking reliability patch:

- Exclude discarded private Assemble/choice artifacts from opponent rails, including choices without a Discover-option tag. Cards actually observed in gameplay remain tracked.
- Correct Godfrey's recoverable-overdraw list: exclude history-display copies, show the original card names and discounted costs, preserve capture order, and remove entries when they return to hand. The list stays separate from ordinary deck/hand rows.
- Resolve Grueling Trial's rail description from its own locally observed modular components. Do not reuse another instance's effects or fetch external definitions.
- Capture verified deck identity during each active game. Persist it by log session, game number and start time so an unavailable end-of-game sensor read does not permanently lose the deck name. Recover saved blank identities when a matching binding arrives; never use a later deck selection to label an older game.
- Log sensor status failures for future diagnosis. Existing historical records without a verified game binding are not guessed or automatically relabeled.

Local Standard tracking, MIT licensing, local data storage and the existing hand-effect-only hover scope remain unchanged. The Windows installer includes the required runtimes. This beta is unsigned. Specialized mechanic coverage remains bounded; see HAND_PREVIEWS.md.

Validation: synthetic regression tests plus local replay of the reported Assemble, Godfrey and Grueling Trial logs. This does not claim every card mechanic or every Windows configuration has been field-tested.

# Phantom · Beta 1 — build 1.3.7 beta candidate

- Correct game-hand hover: display only related effect cards for supported summon, replay and stored-card mechanics. Do not duplicate the hovered card's description.
- Suppress the popup for ordinary hand cards, empty results, counter/history context, and draw/Discover-only lists. These broader lists remain available through rail hover.
- Keep each Ectoplasm's stored minions separate, in order and with duplicates. Show the resulting cards' readable local rules text.
- Preserve full card descriptions on rail hover and refresh an open effect list if its contents change.

261 Python regressions and 67 UI/lifecycle checks pass locally. Build 1.3.6 is superseded and must not be published as the beta. No repository visibility change has been made while this correction is being validated.

# Phantom · Beta 1 — build 1.3.6 beta candidate

- Add tracked draw/copy/summon and deck-Discover candidates for 28 reviewed card contracts, preserving duplicate copies, multiple tribes and spell-school filters.
- Add observed bottom-of-deck previews for Annihilation and Contingency. Newer placement batches take precedence; unknown positions and unordered batch boundaries are explicit.
- Discard stale placement evidence after shuffles, unlocated insertions, reorder effects, concealment or identity changes.
- Show fixed generated-card identities as conditional possibilities, with capped quantities; do not predict random results.
- Retain automatic local setup, local card import, per-entity hand previews, quests, separate Secrets and local match analytics.

260 Python regressions and 49 UI/lifecycle checks pass locally. The maintainer reported successful clean-machine installation and a completed Standard match on build 1.3.5. The new 1.3.6 preview cases have synthetic regression coverage; live acceptance of every mechanic is not claimed.

**Beta boundaries:** Windows x64, Standard, local storage and text previews. Unsupported cost/attack/provenance-dependent tutors and general random generation pools do not have exhaustive candidate previews. Missing history and private identities remain unknown. Turn timers and additional counters are planned after beta. This is unsigned software. The installer is the only file needed for normal installation; the portable ZIP is an alternative and update payload.

# Phantom · Beta 1 — build 1.3.5 development candidate

- Fix friendly hand previews being suppressed by an opponent-only observation check.
- Preserve reveal/hide boundaries and support friendly hand identification without a selected-deck seed.
- Found by correlating the live hand sensor with the parser and tracker on client 255790.

Broader preview coverage and supported Standard overlay acceptance remain pending.

# Phantom · Beta 1 — build 1.3.4 development candidate

- Expanded resurrection, replay, Reborn, death/discard and stored-card previews.
- Read local tribe and verified text-reference metadata from the installed Blizzard client.
- Preserve per-instance histories, Assemble components, duplicates and rewind boundaries.
- Keep hidden opposing stored identities anonymous; distinguish random candidate pools from stored contents.
- Use reconciled deck inventory for deck-history previews and separate descriptions for same-card hand copies.
- Add an offline definition-change audit for patch reviews.
- Allow scrolling long hover lists and enrich observations when startup definitions arrive late.

The updated build 255790 was read successfully. Its previously imported definition properties were unchanged from 255130. See HAND_PREVIEWS.md for implemented contracts and validation limits. Public release and full live Standard acceptance remain pending.

# Phantom · Beta 1 — build 1.3.3 candidate

- Automatic Power logging and background local card import; the first-run modal is removed.
- Friendly hand hover uses the game's own hovered entity and rendered text.
- Cleaner rail text without raw game-formatting markers.
- Per-Ectoplasm stored-minion previews, with separate boards, casts and duplicates.
- Observed linked stored-card previews and stale-hover rejection.

This remains a private validation candidate. Universal related-card mechanic coverage is not complete; see HAND_PREVIEWS.md. A clean Windows 11 install/run of build 1.3.2 passed according to the maintainer; the changed startup and hover behavior needs acceptance on this candidate.

# GhostData — Phantom · Beta 1

Candidate build: **1.3.2**. Free software under MIT. Windows 11 x64 / Hearthstone Standard. This candidate is not yet a public release.

## Install

Use `GhostData-Setup-1.3.2-x64.exe`. Python and .NET are bundled; Start Menu and optional Desktop shortcuts are included. A fully extracted portable ZIP is the alternative. No developer tools are needed. This is unsigned software; Windows may warn or block it under its security policy.

## New in this candidate

- First-run SETUP with custom game-folder selection and persistent local settings.
- Explicit Power logging configuration with preservation of other sections and an original-file backup.
- Clear checks for missing game/logs/sensor and missing, expired or mismatched card definitions.
- Local card refresh without an external download.
- Startup errors keep the dashboard usable; a failed tracker hides stale rails.
- Pinned GitHub Actions packaging workflow, dependency auditing, regression tests, installer lifecycle checks, checksums and build provenance.

## Known limitations and release gates

The separate clean-Windows and real-download tests, live reconnect/quest/Secret/overdraw and mixed-DPI acceptance, and final repository history/privacy review remain open. Automated development-machine and CI tests are not substitutes for those checks. Full-card artwork extraction is not implemented; hover is text-only. Unsupported or unresolved game states must remain partial/unknown. No comparative CPU/RAM performance claim is made.

A GhostData account is not required. Updating or uninstalling preserves your separate match data. The Update button is explicit. Contacts and community links are in the dashboard; reports attach nothing automatically.
