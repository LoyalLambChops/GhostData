from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrackerDeckSnapshot:
    """Exact selected-deck shape consumed by the deterministic tracker."""

    status: str
    deck_name: str
    class_id: str
    cards: tuple[tuple[int, int], ...]
    hero_dbf_ids: tuple[int, ...]
    sideboards: tuple[tuple[int, int, int], ...] = ()
    deck_hash: str = ""

    @property
    def exact(self) -> bool:
        return self.status == "EXACT" and bool(self.class_id) and bool(self.cards)
