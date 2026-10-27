# Public beta release status

Released October 27, 2026: **GhostData — Phantom · Beta 1, build 1.3.7**.

- [Windows installer](https://github.com/LoyalLambChops/GhostData/releases/download/v1.3.7/GhostData-Setup-1.3.7-x64.exe): the single download most users need.
- [Release notes, checksums, provenance and optional portable ZIP](https://github.com/LoyalLambChops/GhostData/releases/tag/v1.3.7).
- [Public source](https://github.com/LoyalLambChops/GhostData) and [website](https://loyallambchops.github.io/ghostdata-site/).

## Scope and packaging

Windows 11 x64, Hearthstone Standard, local match history and analytics, text rails, quests, separate Secret possibilities and recoverable overdraw. Power.log configuration and local card-definition import are automatic. The game may need one restart if logging was enabled while it was already running.

Game-hand hover displays only supported summon, replay and stored-card results. Ordinary cards produce no duplicate description popup. Rail hover retains full descriptions and broader tracked context. Missing information remains unknown; unsupported specialized previews and random outcomes are not advertised as complete. See [hand-preview coverage](HAND_PREVIEWS.md).

Setup includes the application, Python and .NET, creates a Start Menu shortcut, offers a Desktop shortcut, and can launch the app when finished. Users do not need developer tools or a separate ZIP. Updates and uninstall preserve the external data folder. Original software is MIT; bundled components retain their notices.

The first beta is unsigned, as selected by the maintainer. Windows may warn or block it under SmartScreen, Smart App Control or managed policies. Published SHA-256 hashes verify file consistency; they do not authenticate a publisher. Signing is optional future work, not an unresolved beta prerequisite.

## Completed verification

- [x] Candidate source `5ce239cf00cc6ac4fa505f95b2276b94499ee8af` passed 261 Python regressions and 67 UI/lifecycle checks.
- [x] Clean Windows CI passed dependency audits, self-contained packaging, installer creation, install/reinstall, shortcut checks, update success, startup rollback and uninstall/data preservation.
- [x] The same tagged source passed [public CI run 40596676836](https://github.com/LoyalLambChops/GhostData/actions/runs/40596676836). Published assets retain the provenance of their original successful candidate run in BUILD_INFO.json; byte-identical rebuilds are not claimed.
- [x] The maintainer reported clean-machine installation, launch and a completed Standard match on build 1.3.5. Later hover changes have synthetic regressions and an actual Avalonia popup render; this does not imply every mechanic was live-tested on the second PC.
- [x] Anonymous installer download succeeded and matched both the local candidate hash and the release asset digest.
- [x] An isolated copy of the real 1.3.6 updater discovered the public 1.3.7 beta, downloaded and verified its ZIP, installed it, received application startup acknowledgement and preserved a local-data sentinel. The real local installation then moved to 1.3.7 without changing saved match history.
- [x] The 1.3.7 updater reports CURRENT against the public release API without credentials.
- [x] README and website link directly to Setup. Live home, development and privacy pages were checked after deployment.
- [x] Current tracked files and reachable history were reviewed for private paths and credential patterns. Source was transferred to a separate clean repository. The excluded historical commit is absent there, and anonymous access to it and to the retained private history returns 404.
- [x] MIT, exact-package third-party notices, privacy/support/security/contributing documents and bug-report guidance are included.

## Beta follow-up and known limits

These are documented limits and follow-up work, not claims of completed acceptance:

- Live coverage across every supported effect, reconnect/deck-switch sequence, focus transition and DPI arrangement remains incomplete. Keep recording scoped field results in FIELD_TEST_CHECKLIST.md and parity_validation.md.
- Cost/attack/provenance-dependent tutors and general random-generation pools need additional reviewed preview contracts. Full-card artwork, replay and non-Standard modes are outside this beta.
- Turn timers and additional counters are post-beta priorities. Complete parity with another application is not the product goal.
- No matched whole-process CPU/RAM comparison has been completed. “Lightweight” describes the local design, not benchmark superiority.
- Non-ASCII installation paths, power-loss/interrupted update scenarios and every Windows security policy have not been exhaustively tested. A copied clean-machine install and anonymous download verification do not certify browser download-origin behavior on every machine.

For subsequent releases, follow [RELEASE_RUNBOOK.md](RELEASE_RUNBOOK.md), keep the numeric tag and source versions consistent, and publish exact tested assets with their hashes and known limitations.
