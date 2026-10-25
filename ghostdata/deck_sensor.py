from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
from typing import Any

from .models import DeckSnapshot
from .paths import data_paths
from .powerlog import class_from_card_id


def _stable_composition_hash(cards: list[dict[str, Any]], sideboards: list[dict[str, Any]] | None = None) -> str:
    main: list[tuple[str, int]] = []
    for row in cards or []:
        card_id = str(row.get("card_id") or row.get("cardId") or "").strip()
        count = int(row.get("count") or 0)
        if card_id and count > 0:
            main.append((card_id, count))
    main.sort()

    side: list[tuple[str, str, int]] = []
    for row in sideboards or []:
        owner = str(row.get("owner_card_id") or row.get("ownerCardId") or "").strip()
        card_id = str(row.get("card_id") or row.get("cardId") or "").strip()
        count = int(row.get("count") or 0)
        if card_id and count > 0:
            side.append((owner, card_id, count))
    side.sort()

    basis = json.dumps({"cards": main, "sideboards": side}, separators=(",", ":"), sort_keys=True)
    return sha256(basis.encode("utf-8")).hexdigest().upper()


def _derive_class(hero_card_ids: list[str]) -> str:
    for card_id in hero_card_ids or []:
        cls = class_from_card_id(str(card_id))
        if cls:
            return cls
    return ""


def sensor_executable(project_root: Path) -> Path:
    candidates = [
        project_root / "sensor" / "bin" / "GhostData.Sensor.exe",
        project_root / "sensor" / "GhostData.Sensor" / "bin" / "Release" / "net48" / "GhostData.Sensor.exe",
        project_root / "sensor" / "GhostData.Sensor" / "bin" / "Debug" / "net48" / "GhostData.Sensor.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _snapshot_from_payload(payload: dict[str, Any]) -> DeckSnapshot | None:
    status = str(payload.get("status") or "").lower()
    if status not in {"ok", "exact", "partial"}:
        return None
    deck_name = str(payload.get("deck_name") or "").strip()
    selected_id = str(payload.get("selected_deck_id") or "").strip()
    cards = list(payload.get("cards") or [])
    sideboards = list(payload.get("sideboards") or [])
    if not deck_name and not selected_id and not cards:
        return None

    hero_ids = [str(x) for x in (payload.get("hero_card_ids") or []) if str(x)]
    composition_hash = _stable_composition_hash(cards, sideboards) if cards else ""
    return DeckSnapshot(
        deck_name=deck_name,
        selected_deck_id=selected_id,
        player_class=_derive_class(hero_ids),
        format=str(payload.get("format") or "").upper(),
        composition_hash=composition_hash,
        archetype_name="",
        hearthstone_build=str(payload.get("hearthstone_build") or ""),
        sensor_status=str(payload.get("status") or "").upper(),
        hero_card_ids=hero_ids,
        cards=cards,
        sideboards=sideboards,
    )


def read_selected_deck(project_root: Path, *, data_dir: Path | None = None, timeout: float = 4.0) -> DeckSnapshot | None:
    exe = sensor_executable(project_root)
    if not exe.exists():
        return None

    args = [str(exe), "selected-deck", "--json"]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        if proc.returncode != 0:
            return None
        payload = json.loads(proc.stdout.strip() or "{}")
        snapshot = _snapshot_from_payload(payload)
        if snapshot:
            save_cached_deck(snapshot, data_dir=data_dir)
            return snapshot
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    return None


def save_cached_deck(snapshot: DeckSnapshot, *, data_dir: Path | None = None) -> None:
    paths = data_paths(data_dir)
    payload = asdict(snapshot)
    _atomic_write_json(paths.selected_deck, payload)


def load_cached_deck(*, data_dir: Path | None = None) -> DeckSnapshot | None:
    paths = data_paths(data_dir)
    if not paths.selected_deck.exists():
        return None
    try:
        raw = json.loads(paths.selected_deck.read_text(encoding="utf-8"))
        return DeckSnapshot(**raw)
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
