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
