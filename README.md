# GhostData 1.2.2

GhostData is a local Windows dashboard and deterministic deck tracker for Hearthstone Standard.

Developed by **LoyalLambChops** · **LoyalLambChops@gmail.com**.
Version 1.2.2 adds original local app/shortcut icons and dashboard branding.

This repository starts from the GhostData 1.2.0 source baseline. Version 1.2.1 corrects stale selected-deck handling on late starts and session changes. It includes the current app,
sensor, build tooling, manuals and synthetic tests. Personal match history,
captured logs, caches, backup archives and obsolete version snapshots are excluded.

It records completed matches across Hearthstone log sessions and presents results, deck identity, deck composition versions, opponent classes, initiative, match duration, mulligan choices, and factual card history. The live rails provide deterministic deck accounting, observed opponent history, hero-zone effects, and separately labeled Secret possibilities. It does not provide turn-by-turn advice or make causal claims about why a game was won or lost.

**Version 1.2.0 baseline, October 21:** compact text-only rails, separate
recoverable overdraw, Blizzard-local definition import, current client rotation
membership, a portable Windows package and an explicit release Update button.
The installed 37.0.0.255130 client supplied 36,390 public definitions during
validation. Full interaction/reconnect and matched resource acceptance remain
open; see the [validation ledger](docs/parity_validation.md).

## Product surface

- One local Summary / Matches / Charts dashboard with deck/version and matchup statistics.
- In-match opponent-left and player-right deck rails, enabled by default and controlled from the dashboard.
- A separate Secret tracker, retained quest progress, readable card names and draw odds, and text card-detail previews.
- Verified Standard Secret candidate tracking with conservative public non-trigger elimination.
- Background local match recorder while the dashboard is open.
- Multi-session `Power.log` discovery so Hearthstone restarts do not split or lose history.
- Persistent source index so unchanged historical sessions are not reparsed on every Refresh.
- Actual Hearthstone deck name when the selected-deck sensor can read it.
- Exact deck-composition fingerprint kept separately from deck name.
- Factual match, mulligan, draw, play, and public opponent-card history.
- Local storage under `%USERPROFILE%\GhostDataData` by default.

## Requirements

- Windows 11 x64 and Hearthstone with Power.log logging enabled.
- The portable package bundles Python and .NET 8. The sensor uses Windows' .NET Framework 4.8.
- Building from source additionally requires Python 3.12+ and the .NET 10 SDK.

## Start

For the portable package, extract the entire ZIP to a writable folder and open
`GhostData.App.exe`. Keep the folder together. Start Hearthstone and reach its
main menu to import local definitions. Click **UPDATE** for a local card refresh
and a GitHub release check; verified engine updates install on application exit.

From source, run `Build-GhostData.cmd` once, then `Run-GhostData.cmd`.
Maintainers create a self-contained package with `tools/Build-Portable.ps1`.

The build publishes a Windows x64 application under `app/GhostData.App/bin/Release/win-x64`.
Other operating systems' native libraries and debug symbols are excluded from that output.

The Python backend uses only the standard library. The selected-deck sensor build downloads a pinned MIT-licensed UnitySpy source revision and preserves its license beside the built sensor.

See `START_HERE_GHOSTDATA.md` for the validation workflow.

Read the [complete user manual](docs/USER_MANUAL.md) for setup, controls, card
states, statistics, images, backup and troubleshooting. The separate
[technical manual](docs/TECHNICAL_MANUAL.md) covers architecture, data contracts,
builds, tests and maintenance. Both describe current behavior and its limitations.

See [third-party notices](THIRD_PARTY_NOTICES.md) and
[tracking coverage and verification](docs/tracking_coverage.md).
