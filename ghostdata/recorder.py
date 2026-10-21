from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from .deck_sensor import read_selected_deck
from .paths import append_log, data_paths, ensure_history_epoch
from .powerlog import discover_power_logs, parse_completed_games
from .store import MatchStore

# Schema 2 invalidates indexes written by the old session-time reconstruction,
# allowing completed games that were incorrectly classified as pre-epoch to be
# recovered on the next scan.
SOURCE_INDEX_SCHEMA = 2


@contextmanager
def _recording_lock(data_dir: Path | None, timeout: float = 8.0):
    lock = data_paths(data_dir).recorder_lock
    deadline = time.monotonic() + timeout
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()}\n".encode("ascii", "replace"))
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 30:
                    lock.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError("Another GhostData recorder process is busy.")
            time.sleep(0.1)
    try:
        yield
    finally:
        try:
            if fd is not None:
                os.close(fd)
            lock.unlink(missing_ok=True)
        except OSError:
            pass


def _core_complete(match) -> bool:
    return bool(match.result and match.player_class and match.opponent_class and match.initiative and match.started_at)


def _read_source_index(data_dir: Path | None) -> dict[str, dict]:
    path = data_paths(data_dir).source_index
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or int(raw.get("schema_version") or 0) != SOURCE_INDEX_SCHEMA:
            return {}
        sources = raw.get("sources")
        return sources if isinstance(sources, dict) else {}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _write_source_index(index: dict[str, dict], data_dir: Path | None) -> None:
    paths = data_paths(data_dir)
    payload = {"schema_version": SOURCE_INDEX_SCHEMA, "sources": index}
    tmp = paths.source_index.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, paths.source_index)


def _source_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def _source_state(path: Path) -> dict[str, int | str]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _source_unchanged(path: Path, prior: dict | None) -> bool:
    if not prior:
        return False
    try:
        current = _source_state(path)
    except OSError:
        return False
    return int(prior.get("size") or -1) == current["size"] and int(prior.get("mtime_ns") or -1) == current["mtime_ns"]


def _after_epoch(match, epoch: datetime) -> bool:
    value = match.ended_at or match.started_at
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except (AttributeError, ValueError):
        return False
    return dt >= epoch


def record_once(project_root: Path, *, power_log: Path | None = None, data_dir: Path | None = None) -> tuple[int, int]:
    """Scan every changed Hearthstone session Power log and merge completed games.

    ``power_log`` may be a single file or a directory tree. When omitted, every
    discovered Hearthstone Logs session is considered. Unchanged sources are
    skipped using ``source_index.json``; newly created or later-modified session
    logs are parsed automatically.
    """
    with _recording_lock(data_dir):
        logs = discover_power_logs(power_log)
        if not logs:
            append_log("record_once: no Power.log files found", data_dir=data_dir)
            return 0, 0

        epoch = ensure_history_epoch(data_dir=data_dir)
        store = MatchStore(data_dir)
        existing = store.load()
        known_ids = {m.match_id for m in existing if m.match_id}

        index = _read_source_index(data_dir)
        # If a previously populated match store vanished, re-scan sources that
        # had eligible games so the store can recover. If every indexed source
        # was pre-epoch/empty, the index remains safe to trust and avoids
        # reparsing old logs forever on a brand-new installation.
        store_exists = data_paths(data_dir).matches.exists()
        indexed_eligible = any(int(v.get("eligible_games_seen") or 0) > 0 for v in index.values())
        trust_index = store_exists or not indexed_eligible

        parsed_candidates: list[tuple[object, Path]] = []
        scanned_sources = 0
        changed_index = False

        for log_path in logs:
            key = _source_key(log_path)
            prior = index.get(key) if trust_index else None
            if _source_unchanged(log_path, prior):
                continue
            try:
                matches = parse_completed_games(log_path)
                state = _source_state(log_path)
            except (OSError, ValueError) as exc:
                append_log(f"source scan failed: {log_path}: {type(exc).__name__}: {exc}", data_dir=data_dir)
                continue

            scanned_sources += 1
            eligible = [m for m in matches if _after_epoch(m, epoch)]
            parsed_candidates.extend((m, log_path) for m in eligible)
            state.update({
                "last_scanned_at": datetime.now(timezone.utc).isoformat(),
                "completed_games_seen": len(matches),
                "eligible_games_seen": len(eligible),
            })
            index[key] = state
            changed_index = True

        if not parsed_candidates:
            if changed_index:
                _write_source_index(index, data_dir)
            append_log(
                f"record_once: sources={len(logs)} scanned={scanned_sources} parsed=0 added=0 total={len(existing)}",
                data_dir=data_dir,
            )
            return 0, 0

        # Client-state metadata describes the deck selected now. Apply it only
        # to the newest *new* completed match whose source file is recent. This
        # prevents an old recovered session from inheriting today's deck.
        new_candidates = [(m, p) for m, p in parsed_candidates if m.match_id not in known_ids]
        if new_candidates:
            latest_match, latest_source = max(
                new_candidates,
                key=lambda item: ((item[0].ended_at or item[0].started_at), item[0].game_index),
            )
            try:
                source_is_recent = abs(time.time() - latest_source.stat().st_mtime) <= 600
            except OSError:
                source_is_recent = False
            newest_discovered_source = logs[-1].resolve() if logs else None
            source_is_current_session = newest_discovered_source == latest_source.resolve()
            if (
                source_is_recent
                and source_is_current_session
                and not latest_match.deck_name
                and not latest_match.deck_id
                and not latest_match.deck_version
            ):
                deck = read_selected_deck(project_root, data_dir=data_dir)
                if deck:
                    latest_match.enrich_from_deck(deck)

        matches = [m for m, _ in parsed_candidates]
        for match in matches:
            match.data_quality = "COMPLETE" if _core_complete(match) and bool(match.deck_name or match.deck_version) else "LIMITED"

        records, added = store.merge(matches)
        if changed_index:
            _write_source_index(index, data_dir)
        append_log(
            f"record_once: sources={len(logs)} scanned={scanned_sources} parsed={len(matches)} added={added} total={len(records)}",
            data_dir=data_dir,
        )
        return len(matches), added


def watch(project_root: Path, *, power_log: Path | None = None, data_dir: Path | None = None, interval: float = 2.0) -> None:
    append_log("continuous recorder: started", data_dir=data_dir)
    while True:
        try:
            record_once(project_root, power_log=power_log, data_dir=data_dir)
        except Exception as exc:
            append_log(f"continuous recorder: {type(exc).__name__}: {exc}", data_dir=data_dir)
        time.sleep(max(1.0, interval))
