from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
from typing import Iterable

from .models import MatchRecord
from .paths import data_paths

SCHEMA_VERSION = 1


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _logical_key(match: MatchRecord) -> tuple:
    # Match IDs are authoritative. This fallback exists only for old/partial
    # records where a growing log segment may once have generated another ID.
    dt = _parse_dt(match.started_at)
    stamp = int(dt.timestamp()) if dt else None
    return (
        stamp,
        match.result,
        match.player_class,
        match.opponent_class,
        match.initiative,
        match.game_index,
        match.turn_count,
    )


def _prefer(existing: MatchRecord, incoming: MatchRecord) -> MatchRecord:
    # Never overwrite known factual identity with a later scan. Fill blanks only.
    scalar_fields = [
        "started_at", "ended_at", "result", "player_class", "opponent_class", "initiative", "format",
        "hearthstone_build", "game_type", "turn_count", "duration_seconds", "deck_name",
        "deck_id", "deck_version", "archetype_name", "data_quality", "source_session",
        "game_index",
    ]
    for field in scalar_fields:
        old = getattr(existing, field)
        new = getattr(incoming, field)
        if old in ("", 0, None) and new not in ("", 0, None):
            setattr(existing, field, new)

    list_fields = [
        "mulligan_offered", "mulligan_kept", "mulligan_replaced",
        "cards_drawn", "cards_played", "opponent_observed",
    ]
    for field in list_fields:
        if not getattr(existing, field) and getattr(incoming, field):
            setattr(existing, field, getattr(incoming, field))
    return existing


class MatchStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.paths = data_paths(data_dir)

    def load(self) -> list[MatchRecord]:
        path = self.paths.matches
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            rows = raw.get("matches", []) if isinstance(raw, dict) else []
            records = [MatchRecord.from_dict(row) for row in rows if isinstance(row, dict)]
        except (OSError, json.JSONDecodeError, TypeError):
            return []
        return self._dedupe(records)

    def merge(self, incoming: Iterable[MatchRecord]) -> tuple[list[MatchRecord], int]:
        records = self.load()
        by_id = {m.match_id: m for m in records if m.match_id}
        by_logical = {_logical_key(m): m for m in records}
        added = 0
        changed = False

        for match in incoming:
            if not match.match_id:
                continue
            existing = by_id.get(match.match_id)
            if existing is None:
                key = _logical_key(match)
                existing = by_logical.get(key)
            if existing is None:
                records.append(match)
                by_id[match.match_id] = match
                by_logical[_logical_key(match)] = match
                added += 1
                changed = True
            else:
                before = existing.as_dict()
                _prefer(existing, match)
                if existing.as_dict() != before:
                    changed = True

        repaired = self._dedupe(records)
        if len(repaired) != len(records):
            changed = True
        if changed:
            self.save(repaired)
        return repaired, added

    def save(self, records: Iterable[MatchRecord]) -> None:
        rows = sorted(list(records), key=lambda m: (m.started_at, m.match_id))
        payload = {"schema_version": SCHEMA_VERSION, "matches": [m.as_dict() for m in rows]}
        self.paths.root.mkdir(parents=True, exist_ok=True)
        tmp = self.paths.matches.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.paths.matches)

    def clear(self) -> None:
        """Clear history and move the import epoch forward so old logs stay cleared."""
        self.save([])
        now = datetime.now(timezone.utc)
        epoch_tmp = self.paths.history_epoch.with_suffix(".json.tmp")
        epoch_tmp.write_text(json.dumps({"schema_version": 1, "started_at": now.isoformat()}, indent=2), encoding="utf-8")
        os.replace(epoch_tmp, self.paths.history_epoch)
        index_tmp = self.paths.source_index.with_suffix(".json.tmp")
        index_tmp.write_text(json.dumps({"schema_version": 2, "sources": {}}, indent=2), encoding="utf-8")
        os.replace(index_tmp, self.paths.source_index)

    @staticmethod
    def _dedupe(records: list[MatchRecord]) -> list[MatchRecord]:
        out: list[MatchRecord] = []
        by_id: dict[str, MatchRecord] = {}
        by_logical: dict[tuple, MatchRecord] = {}
        for match in sorted(records, key=lambda m: (m.started_at, m.match_id)):
            if match.match_id and match.match_id in by_id:
                _prefer(by_id[match.match_id], match)
                continue
            key = _logical_key(match)
            if key in by_logical:
                winner = by_logical[key]
                _prefer(winner, match)
                if match.match_id:
                    by_id[match.match_id] = winner
                continue
            out.append(match)
            if match.match_id:
                by_id[match.match_id] = match
            by_logical[key] = match
        return out
