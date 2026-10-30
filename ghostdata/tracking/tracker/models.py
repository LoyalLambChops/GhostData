from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple


class Provenance:
    ORIGINAL_DECK = "ORIGINAL_DECK"
    GENERATED = "GENERATED"
    COPIED = "COPIED"
    STOLEN = "STOLEN"
    TRANSFORMED = "TRANSFORMED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RailCardRow:
    card_id: str
    name: str
    cost: int | None
    count: int
    zone: str
    provenance: str = Provenance.UNKNOWN
    in_hand: int = 0
    state: str = ""
    exhausted: bool = False
    draw_chance: float | None = None
    owner_card_id: str = ""
    text: str = ""


@dataclass(frozen=True)
class HandSlot:
    entity_id: int
    position: int
    turn: int
    card_id: str = ""
    name: str = "Unknown card"
    origin: str = "DRAWN"
    text: str = ""
    related_cards: tuple = ()
    related_label: str = ""
    related_kind: str = ""


@dataclass(frozen=True)
class PlayerDeckRow:
    dbf_id: int
    card_id: str
    name: str
    cost: int | None
    initial_copies: int
    remaining_copies: int
    seen_copies: int
    drawn_copies: int


@dataclass(frozen=True)
class PlayerExtraDeckRow:
    card_id: str
    name: str
    cost: int | None
    copies_in_deck: int
    provenance: str
    card_type: str = ""
    spell_school: str = ""


@dataclass(frozen=True)
class OpponentObservedRow:
    dbf_id: int | None
    card_id: str
    name: str
    cost: int | None
    observed_copies: int
    known_in_hand: int
    last_zone: str
    provenance: str
    card_type: str = ""
    spell_school: str = ""
    hero_zone_kind: str = ""


@dataclass(frozen=True)
class HeroZoneEffectRow:
    entity_id: int
    owner: str
    kind: str
    card_id: str = ""
    name: str = ""
    known: bool = False
    cost: int | None = None
    spell_school: str = ""
    progress: int | None = None
    progress_total: int | None = None
    candidate_count: int = 0
    provenance: str = Provenance.UNKNOWN
    text: str = ""


@dataclass(frozen=True)
class DeckTrackerState:
    schema_version: int = 2
    revision: int = 0
    game_number: int = 0
    active: bool = False
    complete: bool = False
    source_status: str = "WAITING"

    player_deck_hash: str = ""
    player_deck_name: str = ""
    player_class: str = ""
    starting_cards: int = 0
    original_cards_remaining: int = 0
    player_hand_count: int | None = None
    player_deck_count: int | None = None
    player_known_non_original_in_deck: int = 0
    player_accounting_delta: int | None = None
    player_accounting_status: str = "UNAVAILABLE"
    player_rows: Tuple[PlayerDeckRow, ...] = field(default_factory=tuple)
    player_extra_deck_rows: Tuple[PlayerExtraDeckRow, ...] = field(default_factory=tuple)

    opponent_class: str = ""
    opponent_hand_count: int | None = None
    opponent_deck_count: int | None = None
    opponent_rows: Tuple[OpponentObservedRow, ...] = field(default_factory=tuple)
    player_hero_zone_effects: Tuple[HeroZoneEffectRow, ...] = field(default_factory=tuple)
    opponent_hero_zone_effects: Tuple[HeroZoneEffectRow, ...] = field(default_factory=tuple)
    player_display_rows: Tuple[RailCardRow, ...] = field(default_factory=tuple)
    opponent_display_rows: Tuple[RailCardRow, ...] = field(default_factory=tuple)
    player_sideboard_rows: Tuple[RailCardRow, ...] = field(default_factory=tuple)
    player_overdraw_rows: Tuple[RailCardRow, ...] = field(default_factory=tuple)
    opponent_overdraw_rows: Tuple[RailCardRow, ...] = field(default_factory=tuple)
    player_hand: Tuple[HandSlot, ...] = field(default_factory=tuple)
    opponent_hand: Tuple[HandSlot, ...] = field(default_factory=tuple)
    player_counters: tuple = ()
    player_fatigue: int = 0
    opponent_fatigue: int = 0
    player_portal: bool = False
    opponent_portal: bool = False

    unknown_provenance_events: int = 0
    warnings: Tuple[str, ...] = field(default_factory=tuple)
