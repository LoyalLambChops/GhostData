from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DataPaths:
    root: Path
    matches: Path
    runtime_log: Path
    selected_deck: Path
    recorder_lock: Path
    history_epoch: Path
    source_index: Path


def data_paths(root: Path | None = None) -> DataPaths:
    if root is None:
        configured = os.environ.get("GHOSTDATA_DATA_DIR", "").strip()
        root = Path(configured) if configured else Path.home() / "GhostDataData"
    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return DataPaths(
        root=root,
        matches=root / "matches.json",
        runtime_log=root / "ghostdata.log",
        selected_deck=root / "selected_deck.json",
        recorder_lock=root / "recorder.lock",
        history_epoch=root / "history_epoch.json",
        source_index=root / "source_index.json",
    )


def append_log(message: str, *, data_dir: Path | None = None) -> None:
    from datetime import datetime, timezone
    paths = data_paths(data_dir)
    try:
        with paths.runtime_log.open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")
    except OSError:
        pass


def ensure_history_epoch(*, data_dir: Path | None = None):
    from datetime import datetime, timezone
    import json
    paths = data_paths(data_dir)
    if paths.history_epoch.exists():
        try:
            raw = json.loads(paths.history_epoch.read_text(encoding="utf-8"))
            value = str(raw.get("started_at") or "")
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    now = datetime.now(timezone.utc)
    tmp = paths.history_epoch.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"schema_version": 1, "started_at": now.isoformat()}, indent=2), encoding="utf-8")
    os.replace(tmp, paths.history_epoch)
    return now
