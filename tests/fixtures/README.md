# Synthetic verification data

`preview/dashboard.json` and `preview/tracker.json` are invented display examples
for the current Avalonia dashboard and rails. They are not a user's saved match
history and are never imported during normal startup.

`../synthetic_match.py` generates a minimal fictitious Power stream in temporary
test directories. Recorder, parser and Rewind tests use that generated stream.
Do not commit captured Power logs, account identifiers, personal match-store
files, rendered screenshots or downloaded card artwork here.
