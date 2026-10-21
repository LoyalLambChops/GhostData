# START HERE — GhostData 1.2.1

GhostData is one local-first Windows application combining a factual Hearthstone
match-history dashboard with deterministic in-match deck-tracker rails.

Full documentation: [user manual](docs/USER_MANUAL.md) and
[technical manual](docs/TECHNICAL_MANUAL.md).

The portable package includes its runtimes. Extract it and open
`GhostData.App.exe`; start Hearthstone at its main menu for local card import.
**UPDATE** refreshes installed game data and checks stable GhostData releases.
See the [validation ledger](docs/parity_validation.md) for remaining acceptance.

## Product surfaces

- The dashboard is the primary window and owns application lifetime.
- A background recorder maintains factual match history in `%USERPROFILE%\GhostDataData`.
- During an active match, an opponent rail appears inside the left edge of the
  Hearthstone client and a player-deck rail appears inside the right edge.
- The dashboard `DECK RAILS` control enables or suppresses the deck and Secret rails.
- Opponent card history is observation-only.
- Secret possibilities occupy a separate rail. Ordinary Secrets use the
  installed client’s current Standard class pool; supported historical generators use their
  public source pool. Unknown conditions are not eliminated speculatively.
- Card names and draw odds retain their font size in long decks. Scroll over
  an overflowing rail; hover a known card, quest, sideboard card, or Secret
  possibility for its locally available card text. Clicks pass through to Hearthstone.
- Rails survive dashboard minimization, and hide when another application is
  foreground or Hearthstone is minimized.

## Explicit exclusions

GhostData records observed facts and bounded public-state deductions. Tactical
recommendations, replay archives, cloud statistics and non-Standard modes are
outside this application's scope.

## Runtime architecture

```text
Hearthstone selected-deck sensor + Power.log
                    |
        deterministic tracker/parser
           |                    |
     TRACKER_STATE         completed games
           |                    |
   Avalonia deck rails     local match store
                 \          /
                  dashboard
```

The deck tracker code lives under `ghostdata/tracking`. The tracker-only NDJSON
entry point is `python ghostdata.py --tracker-stream`. Avalonia owns the child
process through `DeckRailCoordinator`.

## One-click verify, build, and run

Double-click `GhostData-Verify-Build-Launch.exe`. It runs the complete Python
test suite, builds the sensor and dashboard, and launches GhostData only when
both gates succeed. Progress and actionable failures appear in its own window.

## Manual build and validate

Builds require a .NET 10 SDK so Avalonia 12.1.2 analyzers run against a compatible
Roslyn compiler. The produced desktop application continues to target `net8.0`.

```powershell
.\Build-GhostData.cmd
python -m unittest discover -s tests -p "test_*.py" -q
.\Run-GhostData.cmd
```

Use `docs\FIELD_TEST_CHECKLIST.md` for the native Hearthstone gate.
Only current product documentation and synthetic fixtures belong in this
repository; personal history, logs, caches and backup archives are excluded.
