# Standard tracking validation ledger

## Version 1.2.1 late-start correction

The reported Mage opening was at 14:47:27 in the October 21 14:45:42 log session.
The prior wrapper supplied a disk-cached deck ID when the picker disappeared,
and treated that collection lookup as the current deck. A replay with the prior
engine reproduced the wrong Priest/Ghost baseline with a 26-card deck and
five-card hand. The corrected engine rejects the class conflict, retains actual
observations and reproduces fresh-start accounting when Usher arrives later.

The patch passes 182 Python regressions on both development and bundled runtimes,
36 UI checks, and a zero-warning sensor build. Seven new regressions cover
cached-read failures, fresh replacement, late local
identity, class changes, same-class replacement, and delayed reads across both
source and game boundaries. The new client LastDeckId lookup compiles against
the pinned UnitySpy implementation; in-game sensor acceptance still requires a
live field run because Hearthstone was closed during the repair. No personal
logs or match records were added to the repository.

## October 21 baseline validation

The installed expansion client is 37.0.0.255130. The read-only importer successfully
read 36,390 public definitions in approximately seven seconds end to end, with
current Standard membership derived from active client event tables. Its ordinary
Secret pool contained 11 collectible cards across Mage and Hunter. The Unity
executable version was deliberately excluded from game-build identification.
The client embeds log build 254477 in its logging method; the importer verifies
that pairing directly from the installed assembly rather than weakening build checks.

Changes in this candidate:

- Compact text rails retain 15-DIP names, 11-DIP details, 16-DIP Deck/Hand totals,
  180–220-DIP width, capped height, lower-quarter clearance and scrolling.
- Public definitions are imported locally; there are no artwork or card-database
  downloads. Missing/expired/build-mismatched legality fails closed.
- A separate recoverable-overdraw section models Atlas burns, returns, discounts,
  duplicate streams and ambiguous opponent possibilities.
- The explicit Update button refreshes local definitions and checks stable
  project releases. Hash/inventory-verified packages stage for installation on exit.
- A portable package includes Python and .NET; no end-user SDK installation.
  Measured portable output is 56.4 MiB ZIP / 123.2 MiB unpacked, including runtimes.
- Assemble rows and hover text use public body/rules components and current stats;
  distinct outcomes do not merge and hidden opponent components remain withheld.
- Existing dashboard statistics, filters, quests, Secrets and UnitySpy remain.

## Automated coverage

175 Python tests pass, including local import, current rotation, overdraw and
release-validation cases. The C# harness covers 24 dashboard/rail/hover contracts,
nine geometry/text checks and three separate-overdraw UI checks.
Geometry cases cover 720p, 1080p and 1440p, 100/125/150% scaling, a negative
monitor origin and an offset game window. These are coordinate checks, not a
claim of live multi-monitor acceptance.

| Area | Regression evidence |
| --- | --- |
| Original/depleted/held/generated/transformed cards | `test_live_deck_tracker.py`, `test_tracking_contracts.py` |
| Opponent public history, hand concealment and sideboards | `test_tracking_contracts.py`, `test_public_effects.py` |
| Draw, return, burn, discard and quest/Secret zones | `test_live_deck_tracker.py`, `test_tracking_contracts.py`, `test_powerlog.py` |
| Placement, generation, replacement and Rewind | `test_public_effects.py`, `test_reward_pools.py`, `test_rewind.py` |
| Secret trigger and interruption conditions | `test_secret_rails.py`, `test_generated_secret_rules.py`, `test_tracking_contracts.py` |
| Deck/version statistics, ties, filters and charts | `test_dashboard.py`, `test_tracking_contracts.py`, C# harness |
| Log continuity, replacement and UTF-8 chunks | `test_multisession.py`, `test_recorder.py`, `test_tracking_contracts.py` |
| Offline definitions and failed-load identity | `test_local_card_database.py` |
| Compact geometry, text hover and hidden identity guards | C# harness; sample preview renderer |

Fixtures contain synthetic data. `tests/synthetic_match.py` generates parser and
recorder streams; `tests/fixtures/preview` supplies UI examples. Generated
screenshots, personal history, game logs and reference source are not shipped.

The Windows candidate publishes with zero warnings and errors. Sample renders
verify 30-row scrolling, unchanged name font size, known-card hit testing,
16-DIP totals and absence of row images. The narrowest 180-DIP and maximum
220-DIP rails were visually inspected. The running installed instance was not
replaced during verification; this candidate is staged separately.

## Installer and remaining acceptance

The external installer was exercised in isolated package directories with
controlled startup executables. Successful startup replaced the package and
removed its temporary predecessor. Failed startup restored the original
executable byte-for-byte. This tests the actual PowerShell transaction, separately
from Python archive/path/hash validation. It does not certify a power-loss case
or a download-and-upgrade from a publicly hosted release that does not yet exist.

The portable Python 3.14 runtime also passed all 175 regressions. A fresh local
log snapshot of 226,592 lines across 11 games passed through the production
chunk-ingestion path in 4.31 seconds, exposing four public Assemble variants.
This is a parser smoke check, not a complete interaction or runtime comparison.
The final packaged sensor correctly reported unavailable after Hearthstone closed;
the earlier successful live import remains the positive import evidence.

Rendered preview checks confirmed readable names, vertical overflow, known-card
hover hit testing, 16-DIP totals and text-only rows with the new overdraw section.
The preview is synthetic; it is not evidence of every live interaction.

Remaining acceptance:

1. Broader expansion-specific interaction transcripts. Public Assemble tags now
   drive composed rows and previews, with three focused regressions; unsupported
   hidden outcomes are not guessed. Sun's Reckoning has a bounded
   deterministic creation rule based on its installed-client definition.
2. Live recoverable-overdraw interaction with multiple opponent returns, plus
   complete reconnect/restart and asynchronous multi-Secret timelines.
3. Live minimize/focus and mixed-monitor DPI transitions.
4. A matched whole-process-tree CPU/RAM comparison. Package size alone does not
   prove lower runtime overhead. No such performance superiority is claimed.
5. Optional locally extracted full-card artwork remains unimplemented. Text-only
   hover is the supported behavior, with no external-image fallback.

Replay, cloud statistics and non-Standard modes remain outside scope.

## Version 1.3.0 packaging/runtime evidence — October 22, 2026

The .NET 10 application and harness built successfully. The self-contained UI uses runtime 10.0.13; the sensor remains on Windows .NET Framework 4.8. The Python regression suite passed 184 checks and the C# harness passed 40 checks, including single-instance ownership, activation signaling and release of the instance identity. NuGet vulnerability queries for the app and sensor, including transitive packages, reported no known vulnerabilities at validation time. This does not certify the absence of all vulnerabilities.

An actual Inno Setup installer was compiled with an isolated test AppId and installed into a path containing spaces. Start Menu and Desktop shortcut targets/icons were checked. The installed .NET 10 app rendered its synthetic dashboard and rails successfully. A reinstall removed an obsolete-file fixture. The actual update helper completed a successful payload replacement, and a deliberately failing startup restored the previous executable byte-for-byte; uninstall metadata remained unchanged in both cases. Windows uninstall removed the test payload, registration and shortcuts while preserving an external history sentinel.

These checks ran on the development machine. They do not establish clean-VM operation without developer prerequisites, interactive wizard accessibility, non-ASCII paths, power-loss recovery, downloaded-artifact reputation, signing, or public-release update acceptance. The user's existing installation and data were not replaced. No public release was created.


## October 26 automatic startup and hand previews

The maintainer confirmed that build 1.3.2 installed and ran successfully on a separate clean Windows 11 PC. Feedback identified avoidable setup clicks and card-preview gaps; build 1.3.3 addresses those with automatic logging setup, the existing background local card importer, a direct friendly-hand hover sensor and per-Ectoplasm payloads.

The new source passes 211 Python tests and 49 UI/lifecycle checks. A read-only live client check on build 37.0.0.255130 returned the correct hovered entity and rendered Nightblade wording, plus all six visible hand descriptions, with no sensor errors across 41 samples. A local log reconstruction distinguished both Ectoplasm boards and retained duplicate minions. Private logs were not committed. A separate regression checks that Rewind removes an undone cast's stored payload.

This does not certify every related-card mechanic. See HAND_PREVIEWS.md for supported evidence and remaining rule coverage. Actual supported-Standard overlay acceptance and final release checks remain required.
