from __future__ import annotations

from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time

from .deck_sensor import read_selected_deck
from .log_tail import LogTail
from .local_card_data import import_card_data
from .paths import data_paths
from .powerlog import discover_power_logs
from .tracking import DeckTrackerEngine, PowerLogParser
from .tracking.card_db import CardDatabase
from .tracking.snapshot import TrackerDeckSnapshot


ALL_PLAYER_CLASSES = (
    "DEATHKNIGHT", "DEMONHUNTER", "DRUID", "HUNTER", "MAGE", "PALADIN",
    "PRIEST", "ROGUE", "SHAMAN", "WARLOCK", "WARRIOR",
)


def ingest_tracker_chunk(parser, tracker, pending: bytes, chunk: bytes) -> bytes:
    """Publish each lifecycle transition before the next line mutates its entity.

    Keep a partial final line across polls: file writes need not end on a newline.
    """
    lines = (pending + chunk).split(b"\n")
    parser._rebuild_tracker = tracker
    for raw in lines[:-1]:
        parser.parse_line(raw.rstrip(b"\r").decode("utf-8", errors="replace"))
        tracker.observe(parser.state, publish=False)
    if len(lines) > 1:
        tracker.observe(parser.state)
    return lines[-1]


def _tracker_snapshot(snapshot, card_db: CardDatabase) -> TrackerDeckSnapshot | None:
    cards: list[tuple[int, int]] = []
    for row in snapshot.cards:
        card_id = str(row.get("card_id") or row.get("cardId") or "").strip()
        dbf = card_db.dbf_id_for_card_id(card_id)
        count = int(row.get("count") or 0)
        if dbf and count > 0:
            cards.append((dbf, count))
        else:
            # A partially mapped multiset must never be labeled an exact deck.
            return None

    heroes = tuple(
        dbf for card_id in snapshot.hero_card_ids
        if (dbf := card_db.dbf_id_for_card_id(str(card_id)))
    )
    card_class = snapshot.player_class
    if not card_class and heroes:
        card_class = card_db.class_for_dbf(heroes[0])
    if not cards or not card_class:
        return None

    sideboards: list[tuple[int, int, int]] = []
    for row in snapshot.sideboards:
        owner = card_db.dbf_id_for_card_id(str(row.get("owner_card_id") or row.get("ownerCardId") or ""))
        card = card_db.dbf_id_for_card_id(str(row.get("card_id") or row.get("cardId") or ""))
        count = int(row.get("count") or 0)
        if owner and card and count > 0:
            sideboards.append((owner, card, count))
        else:
            # Preserve the previous complete seed until metadata can resolve
            # every source pool; never silently publish a shortened sideboard.
            return None

    return TrackerDeckSnapshot(
        status="EXACT" if snapshot.sensor_status == "EXACT" else snapshot.sensor_status,
        deck_name=snapshot.deck_name,
        class_id=card_class,
        cards=tuple(cards),
        hero_dbf_ids=heroes,
        sideboards=tuple(sideboards),
        deck_hash=snapshot.composition_hash,
    )


def _secret_reads(game, card_db=None) -> list[dict]:
    opponent_pid = game.opponent_pid
    if opponent_pid is None:
        return []
    rows: list[dict] = []
    for entity_id, secret in sorted(game.secrets.items()):
        entity = game.entities.get(entity_id)
        if secret.controller != opponent_pid:
            continue
        if entity is not None and (str(entity.zone or "").upper() != "SECRET" or entity.is_quest):
            continue
        names = [secret.resolved_name or secret.resolved_card_id] if secret.resolved else sorted({
            str(candidate.name or candidate.card_id)
            for candidate in secret.candidates.values()
            if candidate.name or candidate.card_id
        })
        status = (
            "REVEALED" if secret.resolved else
            "NARROWED" if names and secret.eliminations else
            "ACTIVE" if names else
            "CURRENT OPTIONS UNAVAILABLE"
        )
        rows.append({
            "entity_id": int(secret.entity_id),
            "secret_class": str(secret.secret_class or "").upper(),
            "candidate_names": names,
            "candidate_cards": [{"card_id": candidate.card_id, "name": candidate.name,
                "text": card.text if card_db and (card := card_db.get(candidate.card_id)) else ""}
                for candidate in sorted(secret.candidates.values(), key=lambda c: c.name)] if not secret.resolved else
                [{"card_id": secret.resolved_card_id, "name": secret.resolved_name, "text": ""}],
            "eliminated_names": sorted(secret.eliminated_names.values()) if not secret.resolved else [],
            "eliminated_cards": [{"card_id": cid, "name": name,
                "text": card.text if card_db and (card := card_db.get(cid)) else ""}
                for cid, name in sorted(secret.eliminated_names.items(), key=lambda item:item[1])] if not secret.resolved else [],
            "candidate_count": len(names),
            "eliminated_count": len(secret.eliminations),
            "candidate_scope": str(secret.candidate_scope or ""),
            "inference_status": status,
            "generated": str(secret.provenance or "").lower() == "generated",
        })
    return rows


def _emit(sequence: int, tracker: DeckTrackerEngine, parser: PowerLogParser) -> None:
    payload = asdict(tracker.state)
    payload["secret_reads"] = _secret_reads(parser.state, tracker.card_db)
    envelope = {
        "schema_version": 1,
        "message_type": "TRACKER_STATE",
        "event_type": "DECK_TRACKER_UPDATED",
        "sequence": sequence,
        "payload": {"tracker": payload},
    }
    print(json.dumps(envelope, ensure_ascii=False, separators=(",", ":")), flush=True)


def _load_build_metadata(cache_dir, build, project_root=None, data_dir=None, refresh=False):
    if refresh:
        result = import_card_data(project_root, data_dir=data_dir)
        build = result["build"]
    fresh = CardDatabase(cache_dir)
    return fresh if (fresh.load_for_build(build) if build else fresh.load_latest_cache()) else None


def run_tracker_stream(
    project_root: Path,
    *,
    power_log: Path | None = None,
    data_dir: Path | None = None,
    interval: float = 0.25,
) -> None:
    paths = data_paths(data_dir)
    card_db = CardDatabase(paths.root / "local_cards")
    card_db.load_latest_cache()
    parser = PowerLogParser(card_db=card_db, emit_events=False)
    tracker = DeckTrackerEngine(card_db=card_db, supported_player_classes=ALL_PLAYER_CLASSES)

    current_source: Path | None = None
    tail = LogTail()
    last_revision = -1
    last_secret_signature: tuple = ()
    last_sensor_poll = 0.0
    sequence = 0
    pending_line = b""
    sensor_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="selected-deck")
    sensor_result = None
    sensor_context = None
    source_epoch = 0
    last_sensor_snapshot = None
    metadata_result = None
    metadata_refresh = False
    metadata_attempt = (None, 0.0)
    startup_imported = False
    metadata_stamp = None
    last_metadata_check = 0.0
    legality_current = card_db.legality_current

    while True:
        now = time.monotonic()
        logs = discover_power_logs(power_log)
        source = logs[-1] if logs else None
        if source != current_source:
            current_source = source
            tail = LogTail()
            pending_line = b""
            parser.reset_for_new_source()
            tracker.reset_runtime(preserve_selected_deck=False)
            source_epoch += 1
            last_sensor_snapshot = None
            last_revision = -1
            last_secret_signature = ()

        if sensor_result is not None and sensor_result.done():
            try:
                snapshot = sensor_result.result()
                if snapshot is not None and sensor_context == (source_epoch, parser.state.game_number):
                    last_sensor_snapshot = snapshot
                    converted = _tracker_snapshot(snapshot, card_db)
                    if converted is not None:
                        tracker.seed_selected_deck(converted, parser.state)
            except Exception as exc:
                print(f"selected deck warning: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            sensor_result = None
        if sensor_result is None and now - last_sensor_poll >= 3.0:
            last_sensor_poll = now
            sensor_context = (source_epoch, parser.state.game_number)
            sensor_result = sensor_worker.submit(read_selected_deck, project_root, data_dir=data_dir)

        if current_source is not None:
            try:
                chunk, reset = tail.read(current_source)
                if reset:
                    pending_line = b""
                    parser.reset_for_new_source()
                    tracker.reset_runtime(preserve_selected_deck=False)
                    source_epoch += 1
                    last_sensor_snapshot = None
                    last_revision = -1
                    last_secret_signature = ()
                if chunk:
                    previous_game = parser.state.game_number
                    pending_line = ingest_tracker_chunk(parser, tracker, pending_line, chunk)
                    if parser.state.game_number != previous_game:
                        tracker.clear_selected_deck(parser.state)
                        last_sensor_snapshot = None
                        last_sensor_poll = 0.0
            except (OSError, ValueError) as exc:
                print(f"tracker source warning: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)

        # Share the one I/O worker with sensor polling; neither operation may
        # pause log ingestion. Publish a complete new database on this thread.
        if metadata_result is not None and metadata_result.done():
            try:
                fresh = metadata_result.result()
                if fresh:
                    card_db.cards, card_db.cards_by_dbf = fresh.cards, fresh.cards_by_dbf
                    card_db.build_number, card_db.loaded_from = fresh.build_number, fresh.loaded_from
                    card_db.local_source, card_db.valid_until = fresh.local_source, fresh.valid_until
                    card_db.log_build = fresh.log_build
                    startup_imported = startup_imported or metadata_refresh
                    metadata_stamp = Path(fresh.loaded_from).stat().st_mtime_ns
                    converted = _tracker_snapshot(last_sensor_snapshot, card_db) if last_sensor_snapshot else tracker.selected_snapshot
                    if converted:
                        tracker.seed_selected_deck(converted, parser.state, refresh_metadata=True)
                    parser.secret_tracker.refresh_metadata(parser.state)
                    tracker.observe(parser.state)
                    last_secret_signature = ()
            except Exception as exc:
                print(f"card metadata warning: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            metadata_result = None
        build = parser.state.build_number
        if card_db.legality_current != legality_current:
            legality_current = card_db.legality_current
            parser.secret_tracker.refresh_metadata(parser.state)
            last_secret_signature = ()
        if metadata_result is None and now - last_metadata_check >= 2:
            last_metadata_check = now
            path = card_db._cache_path(card_db.build_number) if card_db.build_number else None
            stamp = path.stat().st_mtime_ns if path and path.exists() else None
            if stamp is not None and stamp != metadata_stamp:
                metadata_stamp = stamp
                metadata_refresh = False
                metadata_result = sensor_worker.submit(_load_build_metadata, paths.root / "local_cards", card_db.build_number)
        if (not startup_imported or not card_db.ready or not card_db.legality_current or (build and build > (card_db.log_build or card_db.build_number or 0))) and metadata_result is None:
            if build != metadata_attempt[0] or now - metadata_attempt[1] >= 60:
                metadata_attempt = (build, now)
                metadata_refresh = True
                metadata_result = sensor_worker.submit(_load_build_metadata, paths.root / "local_cards", build, project_root, data_dir, True)

        secrets = tuple(
            (row["entity_id"], tuple(row["candidate_names"]), row["eliminated_count"], row["inference_status"])
            for row in _secret_reads(parser.state)
        )
        if tracker.state.revision != last_revision or secrets != last_secret_signature:
            last_revision = tracker.state.revision
            last_secret_signature = secrets
            sequence += 1
            _emit(sequence, tracker, parser)
        time.sleep(max(0.05, interval))
