from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .card_db import CardDatabase, CardDefinition


def _norm(text: str) -> str:
    return " ".join(str(text or "").strip().casefold().split())


@dataclass(frozen=True)
class StandardSecretCatalog:
    """Patch-scoped, fail-closed Standard Secret allow-list.

    Card-definition data exposes every collectible Secret in the client build, which
    includes Wild cards. GhostData therefore keeps a tiny independently
    maintained Standard legality layer for Secret Intelligence.  A class is
    narrowed only when *every* catalog name resolves in the current card cache;
    otherwise callers must withhold candidate names while preserving the already
    known Secret class. Widening into historical/Wild noise is not permitted.
    """

    patch: str
    source: str
    source_url: str
    classes: dict[str, tuple[str, ...]]

    @classmethod
    def load(cls, path: Path) -> "StandardSecretCatalog":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        classes: dict[str, tuple[str, ...]] = {}
        for card_class, names in (raw.get("classes") or {}).items():
            if not isinstance(names, list):
                continue
            clean = tuple(str(x).strip() for x in names if str(x).strip())
            if clean:
                classes[str(card_class).upper()] = clean
        return cls(
            patch=str(raw.get("patch") or ""),
            source=str(raw.get("source") or ""),
            source_url=str(raw.get("source_url") or ""),
            classes=classes,
        )

    def names_for_class(self, card_class: str) -> tuple[str, ...]:
        return self.classes.get(str(card_class or "").upper(), tuple())

    def resolve_cards(self, card_db: CardDatabase, card_class: str) -> tuple[CardDefinition, ...]:
        """Resolve one current card definition per catalog name.

        Return an empty tuple unless the entire named pool resolves.  That
        conservative all-or-nothing contract prevents a stale or incomplete card
        cache from accidentally shrinking the player's candidate set.
        """
        wanted = self.names_for_class(card_class)
        if not wanted or not card_db.ready:
            return tuple()
        class_cards = [
            c for c in card_db.secret_cards_for_class(card_class)
            if _norm(c.name) in {_norm(x) for x in wanted}
        ]
        by_name: dict[str, list[CardDefinition]] = {}
        for card in class_cards:
            by_name.setdefault(_norm(card.name), []).append(card)

        chosen: list[CardDefinition] = []
        for name in wanted:
            rows = by_name.get(_norm(name), [])
            if not rows:
                return tuple()
            # Prefer the current Core representation when Card-definition data also
            # contains a legacy version of the same collectible card.
            rows = sorted(
                rows,
                key=lambda c: (
                    0 if str(c.card_set or "").upper() == "CORE" else 1,
                    0 if str(c.card_id or "").upper().startswith("CORE_") else 1,
                    c.card_id,
                ),
            )
            chosen.append(rows[0])
        return tuple(chosen)
