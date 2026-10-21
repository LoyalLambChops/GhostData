# GhostData — dashboard and deck rails field checklist

Current baseline acceptance checklist. Use with the [user manual](USER_MANUAL.md)
and [validation ledger](parity_validation.md). Record the app commit, Hearthstone
build, mode, monitor resolutions/scales and outcomes; an unchecked case is not
an implied pass. Keep captured game logs outside the repository.

## Start field validation with the installed app

The portable application is already built. Field validation does not require
build scripts, Python test discovery or the .NET SDK. On this machine the app is
in `C:\Users\admin\GhostData`; its separate source checkout is in
`C:\Users\admin\GhostDataSource`.

Open the GhostData Desktop/Start Menu shortcut, or run this from any PowerShell
working directory:

```powershell
& "$env:USERPROFILE\GhostData\GhostData.App.exe"
```

Start Hearthstone and reach its main menu so GhostData can import local card
definitions. Select a Standard deck before entering a match. A fresh installation
starts with empty GhostData history; new completed matches populate the dashboard.
Record each live check below as passed, failed or not exercised.

## Dashboard and live-match gate

1. Launch the installed app as above; confirm the dashboard opens and refreshes.
2. Confirm `DECK RAILS` is checked by default.
3. Select a Standard deck and begin a match.
4. Confirm opponent-left and player-right rails appear inside Hearthstone.
5. Resize/move Hearthstone and confirm both rails follow without covering the center board.
6. Confirm player remaining-card accounting updates after ordinary draws and plays.
7. Confirm opponent rows contain only publicly observed cards.
8. Confirm generated/inserted cards are separated from original-deck cards.
   Also check copied/transformed, burned/discarded and depleted/held states.
   Verify owner-labelled sideboard consumption, known top/bottom ordering and
   shuffle reset; exact draw odds must be withheld when accounting is partial.
   Check both players' quest/objective progress and supported Rewind corrections.
9. End the match; confirm both rails hide and the completed game is recorded exactly once.

## Secret Intelligence gate

When the opponent plays a Secret naturally:

1. Confirm possibilities appear in the independent Secret overlay, with separate
   opponent slots and your active Secrets.
2. Confirm the displayed class matches the Secret entity's public class.
3. Confirm ordinary names come from the installed client's current Standard definitions; supported
   historical generators must use their explicit public source pools.
4. Confirm safe public non-trigger evidence may narrow the list.
5. Confirm exact hidden identity is not disclosed before public reveal.
6. An unresolved pool must show `CURRENT OPTIONS UNAVAILABLE`, never a guessed pool.
7. Check nested actions, multiple-Secret interruptions, hand/board capacity and
   dormancy before accepting eliminations. Eliminated candidates remain dimmed,
   struck through and hoverable.

## Toggle and lifecycle gate

1. Uncheck `DECK RAILS`; all applicable rails must hide within one second.
2. Recheck it; applicable rails must return with current state.
3. Minimize GhostData while Hearthstone is foreground; active-match rails remain.
4. Minimize Hearthstone or foreground another application; rails hide. Restore
   Hearthstone to the foreground and verify eligible rails return.
5. Move between monitors at different DPI, including negative screen coordinates;
   verify readable layout, hover placement and focus.
6. Verify one inward text preview after hovering a known row; it dismisses on
   exit without activation. Unknown opponent cards have no invented preview.
7. Scroll a long rail without shrinking text or scrolling the window underneath;
   normal clicks pass through to Hearthstone.
8. Exercise real reconnects and an application restart during a Standard match;
   check counts, public state, focus, Secrets and placement after recovery.
9. Close GhostData; recorder/tracker children and all rail windows must terminate.

## Dashboard, offline operation and local storage

- Cross-check Summary/Matches/Charts under the shared filters, ties and missing
  values. Unclassified deck types are expected when no label was supplied.
- Verify idempotent recording across multiple Hearthstone sessions.
- Use isolated test data for history-clear confirmation and recording-epoch tests.
- Verify known card text on hover and explicit unavailability for missing text.
- Verify no artwork or metadata network requests during normal play or preview.
- Test empty/missing/corrupt local definitions: parsing continues, but unavailable
  metadata must not be reported as an exact deck or a complete Secret pool.
- Confirm both rails stay above the lower player banner and totals remain
  readable at each supported resolution and display scale.

## Resource acceptance

Measure GhostData and the reference under equivalent game/cache conditions
without UI automation. Include the dashboard, both Python processes and sensor
children. Record startup/steady CPU, private/working memory, disk/cache growth
and network requests (normal gameplay should make none). Separate application files from runtimes/user data. Update
the validation ledger with measured results and explicit outstanding gates.

## Developer-only automated checks

These commands apply to the source checkout, not the portable installation.
They regenerate build outputs and are unnecessary for ordinary field testing.
The previously reported commands failed from `C:\Users\admin` because neither
the build script nor the `tests` directory lives there. An explicit working
folder is required:

```powershell
Set-Location "$env:USERPROFILE\GhostDataSource"
.\Build-GhostData.cmd
python -m unittest discover -s tests -p "test_*.py" -q
dotnet build tests/GhostData.ParityHarness/GhostData.ParityHarness.csproj -c Release -m:1 -p:UseSharedCompilation=false
dotnet tests/GhostData.ParityHarness/bin/Release/net8.0/GhostData.ParityHarness.dll
```

Require zero build errors and all tests passing before validating a changed
source build. The portable 1.2.0 candidate already passed 175 Python tests and
36 UI checks; see the validation ledger for its evidence and remaining live gates.
