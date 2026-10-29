from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class CardEvent:
    turn: int = 0
    card_id: str = ""
    card_name: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CardEvent":
        return cls(
            turn=int(data.get("turn") or 0),
            card_id=str(data.get("card_id") or ""),
            card_name=str(data.get("card_name") or ""),
        )


@dataclass(slots=True)
class DeckSnapshot:
    deck_name: str = ""
    selected_deck_id: str = ""
    player_class: str = ""
    format: str = "STANDARD"
    composition_hash: str = ""
    archetype_name: str = ""
    hearthstone_build: str = ""
    sensor_status: str = ""
    game_context: bool = False
    hero_card_ids: list[str] = field(default_factory=list)
    cards: list[dict[str, Any]] = field(default_factory=list)
    sideboards: list[dict[str, Any]] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return bool(self.deck_name or self.composition_hash or self.selected_deck_id)


@dataclass(slots=True)
class MatchRecord:
    match_id: str
    started_at: str
    result: str
    player_class: str
    opponent_class: str
    initiative: str
    ended_at: str = ""
    format: str = "STANDARD"
    hearthstone_build: str = ""
    game_type: str = ""
    turn_count: int = 0
    duration_seconds: int = 0
    deck_name: str = ""
    deck_id: str = ""
    deck_version: str = ""
    archetype_name: str = ""
    mulligan_offered: list[str] = field(default_factory=list)
    mulligan_kept: list[str] = field(default_factory=list)
    mulligan_replaced: list[str] = field(default_factory=list)
    cards_drawn: list[CardEvent] = field(default_factory=list)
    cards_played: list[CardEvent] = field(default_factory=list)
    opponent_observed: list[CardEvent] = field(default_factory=list)
    data_quality: str = "LIMITED"
    source_session: str = ""
    game_index: int = 0

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["cards_drawn"] = [x.as_dict() for x in self.cards_drawn]
        payload["cards_played"] = [x.as_dict() for x in self.cards_played]
        payload["opponent_observed"] = [x.as_dict() for x in self.opponent_observed]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatchRecord":
        return cls(
            match_id=str(data.get("match_id") or ""),
            started_at=str(data.get("started_at") or ""),
            result=str(data.get("result") or ""),
            player_class=str(data.get("player_class") or ""),
            opponent_class=str(data.get("opponent_class") or ""),
            initiative=str(data.get("initiative") or ""),
            ended_at=str(data.get("ended_at") or ""),
            format=str(data.get("format") or "STANDARD"),
            hearthstone_build=str(data.get("hearthstone_build") or ""),
            game_type=str(data.get("game_type") or ""),
            turn_count=int(data.get("turn_count") or 0),
            duration_seconds=int(data.get("duration_seconds") or 0),
            deck_name=str(data.get("deck_name") or ""),
            deck_id=str(data.get("deck_id") or ""),
            deck_version=str(data.get("deck_version") or ""),
            archetype_name=str(data.get("archetype_name") or ""),
            mulligan_offered=[str(x) for x in data.get("mulligan_offered") or []],
            mulligan_kept=[str(x) for x in data.get("mulligan_kept") or []],
            mulligan_replaced=[str(x) for x in data.get("mulligan_replaced") or []],
            cards_drawn=[CardEvent.from_dict(x) for x in data.get("cards_drawn") or [] if isinstance(x, dict)],
            cards_played=[CardEvent.from_dict(x) for x in data.get("cards_played") or [] if isinstance(x, dict)],
            opponent_observed=[CardEvent.from_dict(x) for x in data.get("opponent_observed") or [] if isinstance(x, dict)],
            data_quality=str(data.get("data_quality") or "LIMITED"),
            source_session=str(data.get("source_session") or ""),
            game_index=int(data.get("game_index") or 0),
        )

    def enrich_from_deck(self, deck: DeckSnapshot) -> None:
        if not deck.available:
            return
        if not self.deck_name:
            self.deck_name = deck.deck_name
        if not self.deck_id:
            self.deck_id = deck.selected_deck_id
        if not self.deck_version:
            self.deck_version = deck.composition_hash
        if not self.archetype_name:
            self.archetype_name = deck.archetype_name
        if not self.hearthstone_build:
            self.hearthstone_build = deck.hearthstone_build
        if not self.player_class:
            self.player_class = deck.player_class
