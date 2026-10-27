from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class CardDefinition:
    card_id: str
    name: str
    card_class: str = ""
    card_type: str = ""
    cost: Optional[int] = None
    collectible: bool = False
    mechanics: tuple[str, ...] = ()
    card_set: str = ""
    text: str = ""
    dbf_id: Optional[int] = None
    spell_school: str = ""
    standard: bool | None = None
    races: tuple[str, ...] = ()
    text_builder: str = ""

    @property
    def is_secret(self) -> bool:
        return "SECRET" in self.mechanics


class CardDatabase:
    """Optional Hearthstone card-definition cache.

    GhostData can reconstruct a game solely from Power.log. The database improves
    names/metadata and seeds Secret candidate pools. We intentionally fail
    closed: if local definitions are unavailable, game parsing continues but
    Secret candidate enumeration is marked unavailable instead of guessed.
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cards: Dict[str, CardDefinition] = {}
        self.cards_by_dbf: Dict[int, CardDefinition] = {}
        self.build_number: Optional[int] = None
        self.loaded_from: Optional[str] = None
        self.local_source = False
        self.valid_until = None
        self.log_build = None

    def _cache_path(self, build: int) -> Path:
        return self.cache_dir / f"cards_{build}_local.json"

    def load_for_build(self, build: int) -> bool:
        """Read local definitions only; never download during match tracking."""
        cache = self._cache_path(build)
        payload = None
        if cache.exists():
            try:
                payload = json.loads(cache.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = None
        local_source = isinstance(payload, dict) and payload.get("source") == "BLIZZARD_LOCAL_CLIENT"
        valid_until = None
        log_build = None
        if isinstance(payload, dict):
            if not local_source or payload.get("schema_version") != 1 or payload.get("build") != build:
                return False
            log_build = payload.get("log_build")
            if type(log_build) is not int or log_build <= 0:
                return False
            try:
                valid_until = datetime.fromisoformat(payload["valid_until"].replace("Z", "+00:00"))
                if valid_until.tzinfo is None:
                    return False
            except (KeyError, TypeError, ValueError):
                return False
            payload = payload.get("cards")
        if not isinstance(payload, list):
            return False
        cards: Dict[str, CardDefinition] = {}
        cards_by_dbf: Dict[int, CardDefinition] = {}
        for row in payload:
            if not isinstance(row, dict):
                return False
            if local_source and type(row.get("standard")) is not bool:
                return False
            card_id = str(row.get("id") or "")
            if not card_id:
                continue
            if "races" in row and (not isinstance(row["races"], list) or not all(isinstance(v,str) for v in row["races"])):
                return False
            if "textBuilder" in row and not isinstance(row["textBuilder"], str):
                return False
            mechanics = row.get("mechanics") or []
            if not isinstance(mechanics, list):
                return False
            dbf_raw = row.get("dbfId")
            dbf_id = dbf_raw if isinstance(dbf_raw, int) and dbf_raw > 0 else None
            definition = CardDefinition(
                card_id=card_id,
                name=str(row.get("name") or card_id),
                dbf_id=dbf_id,
                card_class=str(row.get("cardClass") or ""),
                card_type=str(row.get("type") or ""),
                cost=row.get("cost") if isinstance(row.get("cost"), int) else None,
                collectible=bool(row.get("collectible", False)),
                mechanics=tuple(str(x) for x in mechanics),
                card_set=str(row.get("set") or ""),
                text=str(row.get("text") or ""),
                spell_school=str(row.get("spellSchool") or ""),
                races=tuple(str(x) for x in row.get("races", [])),
                text_builder=str(row.get("textBuilder") or ""),
                standard=row.get("standard") if isinstance(row.get("standard"), bool) else None,
            )
            cards[card_id] = definition
            if dbf_id is not None:
                cards_by_dbf[dbf_id] = definition
        if not cards:
            return False
        self.cards, self.cards_by_dbf = cards, cards_by_dbf
        self.build_number, self.loaded_from = build, str(cache)
        self.local_source = local_source
        self.valid_until = valid_until
        self.log_build = log_build
        return True

    def matches_log_build(self, build) -> bool:
        return build == (self.log_build if self.local_source else self.build_number)

    @property
    def legality_current(self) -> bool:
        return not self.local_source or (self.valid_until is not None and datetime.now(timezone.utc) < self.valid_until)

    def load_latest_cache(self) -> bool:
        """Load the newest available local card-definition cache."""
        if not self.cache_dir.exists():
            return False
        candidates = sorted(self.cache_dir.glob("cards_*_local.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        for cache in candidates:
            try:
                build = int(cache.name.split("_")[1])
            except (IndexError, ValueError):
                continue
            if self.load_for_build(build):
                return True
        return False

    def get(self, card_id: str) -> Optional[CardDefinition]:
        return self.cards.get(card_id)

    def get_by_dbf(self, dbf_id: int) -> Optional[CardDefinition]:
        return self.cards_by_dbf.get(int(dbf_id))

    def dbf_id_for_card_id(self, card_id: str) -> Optional[int]:
        text = str(card_id or "").strip()
        if text.isdigit():
            value = int(text)
            return value if value > 0 else None
        card = self.cards.get(text)
        return card.dbf_id if card else None

    def class_for_dbf(self, dbf_id: int) -> str:
        card = self.get_by_dbf(dbf_id)
        return str(card.card_class or "").upper() if card else ""

    def secret_cards_for_class(self, card_class: str) -> List[CardDefinition]:
        cls = card_class.upper()
        return sorted(
            [
                c for c in self.cards.values()
                if c.collectible and c.is_secret and c.card_class.upper() == cls
            ],
            key=lambda c: (c.name, c.card_id),
        )

    @property
    def ready(self) -> bool:
        return bool(self.cards)
