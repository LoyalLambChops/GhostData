# GhostData architecture

GhostData combines local recording, selected-deck sensing, deterministic live
tracking and an Avalonia dashboard with three independent overlays. For the full
current architecture, contracts and timing, see the [technical manual](TECHNICAL_MANUAL.md).

## 1. Multi-session Power.log recorder

`ghostdata/powerlog.py` discovers all Hearthstone `Power*.log` files across dated session folders and parses completed Standard matches, local result, classes, initiative, turns, duration, mulligan choices, player draws/plays, and publicly observed opponent plays. Match identity freezes at the first authoritative terminal result boundary so later post-game log growth does not create another match.

`ghostdata/recorder.py` maintains `%USERPROFILE%\GhostDataData\source_index.json`. Unchanged session logs are skipped. New or modified sessions are parsed and merged, allowing GhostData to recover a Hearthstone session that occurred while GhostData was closed as long as the match completed at/after the persistent history epoch.

## 2. Selected-deck sensor

`sensor/GhostData.Sensor` reads the currently selected deck from the Hearthstone client using pinned MIT-licensed UnitySpy source. The Python boundary calculates an order-independent composition fingerprint. Current deck metadata is attached only when the newest newly completed game belongs to the newest discovered Hearthstone session. Older recovered sessions are never assigned today's selected deck.

## 3. Local store

`ghostdata/store.py` writes `%USERPROFILE%\GhostDataData\matches.json` atomically. It deduplicates by stable match ID and a conservative logical-match key, fills missing facts without overwriting known identity, and serializes recorder writes through a local lock.

## 4. Live tracker and dashboard

`GhostData.App` owns a dashboard plus independent player, opponent and Secret
overlays. It starts separate Python recorder and tracker processes. The tracker
consumes complete log lines, maintains public state and emits NDJSON snapshots.
The recorder performs idempotent multi-session scans. Dashboard refresh loads
changed local history through a cached JSON snapshot; it does not itself reparse
every historical log. Closing the dashboard ends owned processes and overlays;
minimizing it allows eligible rails to remain over Hearthstone.
