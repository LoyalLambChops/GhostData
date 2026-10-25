# GhostData user manual

Phantom · Beta 1 (build 1.3.2) - Updated October 25, 2026

GhostData is a local Windows application for Hearthstone Standard match history,
deck tracking, quests and public Secret deductions. The dashboard and overlays
use Avalonia. No GhostData account is required. Match history stays on your
computer. Rails are text-only, and card metadata is imported from your installed Blizzard client and cached locally.
This candidate includes the Windows installer, bundled .NET 10 runtime, local-data importer, portable package and release-update button. Public downloads are not yet published.
The validation ledger records remaining live acceptance work.

This manual describes the current implementation. The [validation ledger](parity_validation.md)
separates verified behavior from remaining live acceptance work. The
[technical manual](TECHNICAL_MANUAL.md) explains implementation and maintenance.

## Contents

1. [Install and start](#install-and-start)
2. [Daily use and controls](#daily-use-and-controls)
3. [Read the player rail](#read-the-player-rail)
4. [Read the opponent rail](#read-the-opponent-rail)
5. [Quests and Secrets](#quests-and-secrets)
6. [Hover, scrolling and placement](#hover-scrolling-and-placement)
7. [Dashboard and filters](#dashboard-and-filters)
8. [Understand the statistics](#understand-the-statistics)
9. [Images and offline use](#images-and-offline-use)
10. [Data, backup and deletion](#data-backup-and-deletion)
11. [Troubleshooting](#troubleshooting)
12. [Advanced commands](#advanced-commands)
13. [Current boundaries](#current-boundaries)

## Install and start

### Windows installer (recommended)

1. Run `GhostData-Setup-1.3.2-x64.exe` from the candidate package. After public release, obtain Setup from this project's GitHub Releases.
2. The default destination is `%LOCALAPPDATA%\Programs\GhostData`, for the current Windows user. Setup does not require administrator privileges.
3. Choose whether to create a Desktop shortcut. A branded Start Menu shortcut is created automatically.
4. Leave **Launch GhostData** selected to open the dashboard after setup. Subsequent launches use either shortcut. Launching again brings the existing dashboard forward.
5. Start Hearthstone and reach its main menu so local card definitions can be imported. Enable Power.log logging before field testing, as described below.

Setup bundles Python and .NET 10. No SDK, separate runtime download, build command or launch script is needed. The initial beta is unsigned by choice. Windows may warn or block it under your security policy; signing is not a release requirement.

Use Windows **Settings > Apps > Installed apps > GhostData > Uninstall** to remove the program and shortcuts. Your `%USERPROFILE%\GhostDataData` history is retained. Updating or reinstalling uses that same history. Do not put personal files inside the app payload. If moving from a portable copy, close it and install to a separate folder; Setup deliberately refuses to overwrite a portable folder.

### Portable installation

1. Obtain the GhostData Windows x64 ZIP candidate. After public release, use this project's GitHub Releases.
2. Extract the whole ZIP into a writable folder, such as `Documents\GhostData`.
3. Open `GhostData.App.exe`. Python and the .NET runtime are included; no separate runtime setup is needed.
4. Start Hearthstone and reach its main menu. GhostData reads its public card tables locally, normally in several seconds, and retries if the game is not ready.
5. Select your Standard deck before starting a match. Keep the dashboard open or minimized while playing.

Windows 11 x64, Hearthstone, its Power logs and Windows' .NET Framework 4.8 are
required. Do not run from inside the ZIP or copy just the executable. Keep user
history outside the application folder (the default does this automatically).
GhostData does not install an always-running background service.

### Source-build requirements

Python 3.12+ and the .NET 10 SDK are required for development builds. Initial
package restore and pinned UnitySpy source preparation need internet access.
The development launcher and portable release are separate ways to run the same
application.

### First launch from source

1. Open the GhostData project folder containing `ghostdata.py` and
   `Build-GhostData.cmd`.
2. Run `Build-GhostData.cmd`. Wait for all build steps to succeed.
3. Run `Run-GhostData.cmd` to open the dashboard.
4. Start Hearthstone, select your Standard deck, and begin a match. Starting
   GhostData before the match gives it the best opportunity to capture the
   selected deck, opening hand and complete game transitions.
5. Finish a match and allow several seconds for the recorder and dashboard to
   update. Use **REFRESH** if necessary.

After a successful build, the generated `GhostData-Verify-Build-Launch.exe`
offers a verification/build/launch workflow. Normal daily startup is
`Run-GhostData.cmd`. The launcher runs Python tests and builds components;
the separate C# parity harness is a developer check.

### First-run SETUP

SETUP opens automatically until you save and close it. You can reopen it from the dashboard at any time. You may close it and still browse existing history if Hearthstone is unavailable.

1. Start Hearthstone and reach the main menu. Setup looks for standard installs and can detect the running game path. For a custom install, **BROWSE** to the folder containing `Hearthstone.exe`, then **SAVE FOLDER**. Restart GhostData if changing the path after tracking has started.
2. If Power logging is missing, click **ENABLE POWER LOGGING**. This changes `LogLevel` and `FilePrinting` in the Power section of `%LOCALAPPDATA%\Blizzard\Hearthstone\log.config`. Unrelated sections are preserved; an existing file is backed up beside it. A malformed file is left untouched with an error. Fully close and restart Hearthstone afterward.
3. Enter a game so Hearthstone creates a Power.log. **CHECK AGAIN** reports discovered logs; finding historical logs alone does not prove a current game is being tracked.
4. At Hearthstone's main menu, **REFRESH LOCAL CARDS** imports public definitions locally. No external card data is downloaded. If import fails after a patch, exact card accounting cannot be assumed; check for a tested app update or contact support.
5. **SAVE AND CLOSE** remembers that you have seen Setup, even if checks still need attention. The dashboard readiness line keeps outstanding checks visible. Current definitions do not certify every game mechanic; live accounting continues to label partial/unknown information.

Settings live in `GhostDataData/settings.json`, outside app files. Clearing the folder field and saving restores automatic discovery. Both recorder and live tracker use the saved install's `Logs` directory after restart; CLI `--power-log` overrides it. Default discovery scans both Program Files Hearthstone Logs roots and their dated session folders.

Setup runs only local checks and makes no network requests. UPDATE is the separate explicit release check.

## Daily use and controls

The dashboard owns application lifetime. Keep it open while playing; minimizing
it keeps recording and rails running. Closing it stops its child processes and
closes its rails. Recording is not installed as an always-running Windows service.

| Control | Action |
| --- | --- |
| **DECK RAILS** | Show or suppress player, opponent and Secret overlays for this application session. Does not erase history. |
| **UPDATE** | Refresh public definitions from the installed client and check stable GhostData GitHub releases. A verified package installs when GhostData closes. |
| **REFRESH** | Reload the dashboard when local history changes. It is not a force-reparse command for every old log. |
| **CLEAR HISTORY** | Show a confirmation dialog, then erase local recorded matches and start a new recording period. |
| **SUMMARY / MATCHES / CHARTS** | Switch dashboard views while retaining the selected filters. |

The recorder normally checks changed logs every two seconds. The dashboard
checks for history changes every four seconds. These intervals plus file writes
mean a completed game does not appear instantaneously.

## Read the player rail

The right rail combines the selected-deck baseline with observed game events.
Card name, mana cost, count and state details communicate what is known.

| Display or state | Meaning |
| --- | --- |
| Original deck row | A card in the selected starting list. Depleted rows remain visible so the original list stays recognizable. |
| Hand highlight / hand detail | At least one corresponding known card is currently in your hand. |
| Generated, copied or transformed detail | The public history distinguishes this card from an ordinary original-deck copy. |
| Burned / discarded detail | A recorded transition removed a card without the usual draw-and-play sequence. |
| **TOP / BOTTOM** | A supported public placement effect established location. A later shuffle clears known ordering. |
| Sideboard area | A separate pool belonging to its displayed owner/source card. It is not part of the ordinary remaining-deck count. |
| **DECK / HAND** | Current counts established by game state. Missing counts are not silently treated as zero. |
| **SYNCED** | Known deck accounting reconciles exactly. This is an accounting status, not a claim that every possible card-specific rule has been validated. |
| **PARTIAL** with a signed delta | Observed and accounted-for deck quantities disagree. Treat the list as incomplete; exact draw odds are withheld. |
| **WAITING FOR EXACT DECK** | The required deck/count information has not yet been established. |
| **DEMON PORTAL** | A supported special deck state has its own presentation rather than ordinary finite-deck probabilities. |
| Fatigue detail | The next fatigue amount when available from the tracked state. |

For an ordinary fully reconciled deck, a card's next-draw chance is its remaining
copies divided by eligible remaining cards. Two copies among 26 eligible cards
are about 7.7%. Known top/bottom placement changes the eligible draw calculation;
it is not always a simple count divided by total deck size. A missing percentage
means the required certainty is unavailable. It is not a zero-percent prediction.

Unsupported random generation may show a public description or unresolved pool.
GhostData does not assign a guessed identity to a concealed card. A public
possibility pool is not a promise that every listed possibility exists in hand.

## Read the opponent rail

The left rail shows publicly observed opponent cards and their tracked states.
It is not a complete inferred opponent deck. Multiple rows or states can reflect
different copies, transformations, generation or zone history.

Hand slots show position, acquisition turn and recorded origin such as opening
hand, mulligan, draw, generation, return or theft. An identity appears only when
public evidence supports it. An unknown slot remains unknown and has no invented
card-details preview. Hand position alone does not identify a card.

Displayed original identity can remain relevant after a transformation; read the
state/provenance detail as well as the name. Opponent deck and hand counts are
game-state counts, not counts of all rows displayed in the public-history list.

## Quests and Secrets

Quest, questline, sidequest and supported hero-zone objective displays retain
ownership and reported progress. They are separate from Secret candidate lists.
Progress follows available game tags; no objective completion is invented when
evidence is missing.

Secrets use a separate overlay beside the opponent rail. It appears when there
are Secrets to display and includes your active Secrets plus individual opponent
Secret slots. Each opponent slot retains its own candidate state.

- Candidate names are possibilities consistent with the available public state.
- Eliminated names remain dimmed and struck through, rather than disappearing
  without explanation.
- Both remaining and eliminated known candidates can display card-details previews.
- Ordinary Secret pools come from the installed client's active Standard set membership.
- Supported public generators can supply historical Secret pools during a
  Standard match. This does not enable Wild tracking generally.
- Insufficient metadata, an unresolved source or disruptive trigger ordering can
  prevent a deduction. An unavailable candidate list is not proof of no Secrets.

A game-build mismatch or expired rotation snapshot withholds candidate names
until refreshed. New mechanics can still require a tested GhostData engine
release. Updated card text alone does not prove that every trigger is supported.

## Hover, scrolling and placement

Hover a known card row for about 150 milliseconds to request its card-details
preview. This includes known quests, sideboard cards and Secret possibilities.
The preview opens toward the play area without taking keyboard focus. Leaving
the row dismisses it. Hover performs no network or artwork-cache access.

Card names use 15 device-independent pixels; state text and draw percentages use
11. Deck/Hand totals use 16 DIPs. Width is 180–220 DIPs and height is capped
at 780 DIPs, leaving the bottom quarter of the game clear. Long lists scroll instead of shrinking the text. Roll the mouse wheel over
the overflowing rail. Ordinary clicks pass through to Hearthstone; hovering is
the preview action.

Rails follow the Hearthstone client bounds and display scaling. They hide when
Hearthstone is minimized or another application is foreground, and return when
the active match is foreground again. Dashboard minimization does not own rail
visibility. There is currently no drag-to-save layout editor or independent
font-size slider. Mixed-monitor scaling during a live match still needs the
acceptance checks recorded in the validation ledger.

## Dashboard and filters

**SUMMARY** contains overall record, result/class distributions, deck highlights,
deck/version statistics and matchup information. **MATCHES** lists recorded games
and shows the selected match's factual details. **CHARTS** provides class, Coin,
opponent and daily result views. The selected filters apply to statistical panels
across the tabs.

| Filter | Available meaning |
| --- | --- |
| Deck | Recorded deck name. Deck selection by name can include more than one recorded deck identity with the same name. |
| Version | Full recorded composition fingerprint; short labels may show only its first eight characters. |
| Deck type | Recorded archetype/type labels when present. Current sensor capture leaves this field empty; **Unclassified** is expected, not a failed download. |
| Class | Your recorded class. |
| Time | All time, Today, Last 7 days or Last 30 days. Today uses local midnight; the latter two are rolling intervals. |
| Mode | Available recorded Standard mode labels, such as ranked or casual. |
| Opponent | Recorded opponent class. |
| Result | All results, Win or Loss. |
| Initiative | All orders, First or Second. Coin charts describe the corresponding starting order. |

Restore each filter to its **All…** option to see the complete stored history.
There is no 200-game display cutoff. Date-range pickers, saved filter presets,
rank-band filtering and full-text match search are not present in this build.

Match details include available deck/version, result, class matchup, initiative,
mode, game build, duration and turn count; opening mulligan offers/keeps/replacements;
drawn and played cards; and publicly observed opponent cards. Missing information
is shown as unavailable rather than reconstructed from a guessed deck.

## Understand the statistics

| Statistic | Calculation and interpretation |
| --- | --- |
| Games | Number of matching stored records, including ties if present. |
| Record | Wins–losses. Ties are not added to either number. |
| Win rate | `100 × wins / (wins + losses)`. No decided games means unavailable. A tie can make Games exceed the sum in Record. |
| Average time | Mean of positive recorded durations. Missing durations are excluded. |
| Average turns | Mean of positive recorded turn counts. These are log-derived counts, not a separate estimate of your personal turns. |
| Time played | Sum of positive recorded durations, displayed in hours. |
| Class distributions | Share of filtered records played as, or against, each class. |
| Matchup cells | Record and win rate against the column's class; an empty sample shows a dash. |
| Daily win rate | Decided games grouped by local calendar date. This is not a cumulative curve. |
| Mulligan history | Games in which a card was offered, kept or replaced, with resulting records. Repeated copies count once per game per category. A game can include both keeping and replacing the same card name. |

**Most played** selects the deck with the most filtered games. **Best performing**
uses a sample-weighted score, not simply the largest displayed win rate:
`decided games / (losses + 1) × min(1, decided games / 10)`.
**Fastest** and **Slowest** compare mean recorded turn counts for decks with more
than one filtered game. Their selection currently includes zero turn counts in
that ranking, whereas the displayed average excludes missing/zero turns.

Best/worst matchup labels use observed win rate with record-based tie breakers.
There is no minimum-sample guarantee: a single win can make a matchup look best.
These are descriptions of your recorded games, not causal proof that keeping a
card, changing a deck or choosing a matchup produces a particular result.

**Complete** means core match fields and a deck name or fingerprint were captured.
It does not certify a complete event transcript or every opening-hand detail.
**Limited** means those completeness conditions were not met. Quality totals
describe the loaded history; they are not a per-card accuracy rating.

## Images and offline use

Rails and hover previews are text-only. No card images are shipped, downloaded,
or read from old artwork caches. Hover shows a known card's name and local rules
text after about 150 ms. Unknown opponent identities have no preview identity.
Full-card artwork from installed assets is not implemented; third-party cached
images are not used as a substitute.

Card definitions come from the running installed Blizzard client through the
read-only UnitySpy sensor. GhostData copies names, rules, costs, classes, types,
mechanics, identifiers and current set membership into a build-specific local
snapshot. It does not download a card JSON database, contact a card-image server,
read an opponent's hidden hand through the sensor, or modify game memory.

A first import requires Hearthstone to be running and fully initialized. Later
starts can display cached text immediately while refreshing in the background.
The cache is refreshed at startup, for a newer logged build, after its rotation
validity expires, or through **UPDATE**. Expiry is the earliest upcoming client
event boundary or 24 hours, whichever is sooner. Failures preserve the previous
valid file; stale legality is not used to invent Secret candidates.

**UPDATE** also contacts this project's GitHub release endpoint. It downloads
only a newer stable Windows GhostData package, checks its SHA-256 digest and file
inventory, and stages it beside the installation. Close GhostData normally to
apply it and restart. Your match history stays in its separate data folder. If
the new UI fails to start, the update helper attempts to restore the previous
installation. Temporary rollback files are removed after successful startup.
Source checkouts only report release availability and are never replaced.

No public release, a network failure, a modified installation or insufficient
write access is reported as such; it is not labeled “up to date.” The Update
button can still refresh local definitions when the release check fails, and
vice versa. Use Blizzard's normal launcher to update Hearthstone itself. The
button reads those installed updates; it does not patch the game or generate
new engine logic from patch notes.

Normal match tracking does not require GhostData internet requests. Hearthstone
itself still needs its normal game connection. The cache is a compact text
snapshot rather than an artwork library; the verified build's snapshot contains
36,390 definitions. The portable application is about 56.4 MiB compressed and
123.2 MiB unpacked, including runtimes. These sizes are not CPU/RAM comparisons.

### Recoverable overdraw

The **RECOVERABLE OVERDRAW** section appears above ordinary rows when Godfrey's
Atlas holds burned cards until hand space opens. These cards do not count as
being in hand. The displayed cost includes the one-mana recovery discount.
Ordinary burns are not added to this section. A local returned card leaves the
section; a uniquely identifiable opponent return can be identified publicly.
If several opponent cards could have returned, the possibilities remain labeled
**MAY BE IN HAND** until public reveals or all returns resolve them. GhostData
does not assign those possibilities to hidden hand positions.

### Assemble cards

An assembled card shows the body name plus the rules component's name. Hover
shows its current cost, attack/health and the second component's rules. Different
combinations remain separate rows even when they share a body. If local definitions
lack a component, the preview says its rules are unavailable. Opponent components
appear only after public reveal; hidden choices are never inferred from private data.

## Data, backup and deletion

Default data folder: `%USERPROFILE%\GhostDataData`.

| File/folder | Purpose |
| --- | --- |
| `matches.json` | Recorded match history, including available card summaries and deck identity. |
| `selected_deck.json` | Last selected-deck sensor snapshot. |
| `history_epoch.json` | Start of the current recording period. |
| `source_index.json` | Which log sources were already scanned. |
| `ghostdata.log` | Recorder diagnostics and local file paths. |
| `recorder.lock` | Temporary recorder coordination file. |
| `local_cards` | Validated snapshots imported from installed Blizzard public definitions. |
| `card_art`, `card_renders` | Obsolete artwork caches; not read or created by this candidate. |
| `image-settings.json` | Obsolete artwork preference; ignored. |

For a backup, close GhostData and copy the data folder to a safe location.
Metadata is optional for history preservation, but is currently needed for full
card details and identity mapping. Old artwork caches need not be copied. Do not copy an active lock file as a required
backup component. Keep a backup of the existing destination before restoring.
Restore while GhostData is closed, retaining the history, epoch and index
together. This build has no backup/import/merge wizard or cloud synchronization.

**CLEAR HISTORY** removes recorded matches and advances the recording epoch,
so ordinary rescanning does not immediately resurrect pre-clear games. It does
not erase Hearthstone's own logs or the image cache. There is no undo button.
Backup before clearing if you may want the records later.

To use another data folder, set `GHOSTDATA_DATA_DIR` before launching:

```powershell
$env:GHOSTDATA_DATA_DIR = 'D:\GhostDataData'
.\Run-GhostData.cmd
```

This selects a new location; it does not migrate old data automatically. Use an
absolute path and preserve the setting in the environment used to launch the app.
Do not run two copies against different assumptions about which folder is active.

## Troubleshooting

| Symptom | Checks and recovery |
| --- | --- |
| Dashboard will not start | For the portable build, extract the complete ZIP into a writable folder and open `GhostData.App.exe`. For a source build, verify Python/.NET and retain the build error output. Set `GHOSTDATA_PYTHON` to an absolute interpreter path if source-build detection fails. |
| No new matches | Keep the dashboard open, finish a supported Standard match, reset filters, then refresh. Check that current Power logs exist and are growing. Inspect `ghostdata.log`. Opening the application starts a recording epoch; it does not promise automatic import of all older games. |
| Custom Hearthstone location | Open SETUP, select the folder containing Hearthstone.exe, SAVE FOLDER, then restart GhostData. CLI `--power-log` overrides the saved path. |
| Rails absent | Enable DECK RAILS, foreground Hearthstone, restore it from minimization and enter an active supported match. Check that the tracker backend started and logs are available. Closing/reopening GhostData restarts the backend. |
| Wrong/unavailable selected deck | Select the intended deck in Hearthstone and allow a sensor poll. Start GhostData before the next match. A game patch may require a sensor update. The disk cache is never used as proof of the current deck. Until a live read succeeds, only observed cards are shown and exact-deck accounting stays unavailable. |
| PARTIAL counts or missing odds | Preserve the log and note the card interaction, turn and game build. Missing baseline or unsupported interactions can prevent reconciliation. Restart at a clean match boundary; do not interpret missing odds as zero. |
| No full-card image | This candidate intentionally uses text previews. Local full-card artwork extraction is not implemented. |
| Empty deck types | The current sensor does not classify archetypes. Unclassified is the expected fallback. |
| Missing older games after clear | The new epoch intentionally excludes them. Restore your backup if you need the previous history. |
| Wrong placement after monitor change | Return Hearthstone to its prior monitor and reopen GhostData if necessary. Record monitor resolutions/scales for a reproducible report; live mixed-DPI acceptance remains open. |

When reporting a problem, include GhostData version, Hearthstone build, mode,
approximate local time, observed versus expected behavior and a minimal relevant
log excerpt. Review logs before sharing: they can contain names, deck information
and local paths. There is no automatic redacted support-bundle generator.

## Advanced commands

Run from the project root; replace `python` with your configured interpreter.

```powershell
python ghostdata.py --version
python ghostdata.py --update-card-data
python ghostdata.py --update
python ghostdata.py --dashboard-json
python ghostdata.py --record-once --power-log 'D:\Hearthstone\Logs'
python ghostdata.py --record-continuously --interval 2
python ghostdata.py --tracker-stream --interval 0.25
```

`--power-log` accepts a file or directory; `--data-dir` overrides the data folder
for that Python command. Tracker output is newline-delimited JSON for software
consumers. Use Ctrl+C to stop a continuously running command. Do not launch
duplicate continuous recorders unnecessarily.

`--clear-history` is also available but **acts immediately without the GUI's
confirmation dialog**. Prefer the dashboard confirmation for ordinary use.
There is no built-in CSV export or replay export command. Dashboard JSON is a
readable integration output; copying the closed application's data files is the
backup procedure.

## Current boundaries

Standard constructed is the supported scope, including recognized ranked,
casual and friendly modes. Explicit Wild, Arena and other modes are excluded;
records without historical mode tags can remain readable. There is no replay
archive, cloud statistics, tactical advice or hidden-opponent deck guessing.

The engine is GhostData's own implementation. Automated regressions do not
establish every card interaction or live reconnect. Remaining acceptance work
includes complete expansion interaction coverage, live reconnect/mixed-DPI tests
and matched resource measurements. Assemble previews combine publicly visible
components and current stats; hidden choices remain unknown. Full lower-memory/CPU
claims remain unverified.

## Application branding

Developed by **LoyalLambChops** · **LoyalLambChops@gmail.com**.
The dashboard includes the GhostData mark and a selectable contact address.
The original icon is embedded in the application for the window, taskbar and Windows shortcuts; it requires no network access.

## Community, feedback and license

The dashboard footer identifies **Phantom · Beta 1**, build **1.3.2**. TWITCH opens https://www.twitch.tv/loyallambchops; DISCORD opens https://discord.gg/H3Et7NHavZ in your default browser. CONTACT / BUG REPORT opens your email application with a draft addressed to LoyalLambChops@gmail.com. It includes the app version and a blank report template. Nothing is sent automatically and no files or match data are attached. Review any details you choose to share. If Windows cannot open the link, GhostData shows an address you can select and copy.

MIT LICENSE opens the original-software license offline. Dependency notices are included separately. The beta is free and unsigned; Windows may warn or block it according to security policy. A signing certificate is not required by GhostData.

UPDATE is explicit: this beta can offer a newer published beta or stable GhostData build. Numeric versions determine upgrade order; the release nickname is for display. It never downgrades to an older build. While the repository is private or has no compatible published release, the updater reports unavailable.
