from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any


@dataclass
class EntityState:
    entity_id: int
    card_id: str = ""
    name: str = ""
    controller: Optional[int] = None
    zone: Optional[str] = None
    zone_position: int = 0
    card_type: Optional[str] = None
    card_class: Optional[str] = None
    cost: Optional[int] = None
    attack: Optional[int] = None
    health: Optional[int] = None
    damage: int = 0
    armor: int = 0
    creator: Optional[int] = None
    displayed_creator: Optional[int] = None
    copied_from_entity_id: Optional[int] = None
    revealed: Optional[bool] = None
    entered_play_sequence: Optional[int] = None
    entered_play_turn: Optional[int] = None
    last_played_turn: Optional[int] = None
    original_card_id: str = ""
    transformed_from: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def is_known(self) -> bool:
        return bool(self.card_id or self.name)

    @property
    def is_quest(self) -> bool:
        return (
            self.tags.get("QUEST") == "1"
            or self.tags.get("QUESTLINE") == "1"
            or self.tags.get("SIDE_QUEST") == "1"
        )

    @property
    def is_secret_like(self) -> bool:
        return self.zone == "SECRET"

    @property
    def effective_health(self) -> Optional[int]:
        if self.health is None:
            return None
        return self.health - self.damage + self.armor

    def update_card_identity(self, card_id: str, name: str = "") -> bool:
        """Update card identity and return True if this is a new reveal/transform."""
        if not card_id and not name:
            return False
        old = self.card_id
        changed = False
        if card_id and old != card_id:
            if old:
                self.transformed_from.append(old)
            elif not self.original_card_id:
                self.original_card_id = card_id
            self.card_id = card_id
            changed = True
        if name and name != "UNKNOWN ENTITY [cardType=INVALID]" and name != "UNKNOWN ENTITY":
            if self.name != name:
                self.name = name
                changed = True
        return changed


@dataclass
class PlayerState:
    player_id: int
    entity_id: Optional[int] = None
    name: Optional[str] = None
    player_class: Optional[str] = None
    starting_class: Optional[str] = None
    hero_entity_id: Optional[int] = None
    hero_power_entity_id: Optional[int] = None
    resources: int = 0
    resources_used: int = 0
    temp_resources: int = 0
    current_player: bool = False
    first_player: bool = False
    local_turn: int = 0
    playstate: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def available_mana(self) -> int:
        return max(0, self.resources + self.temp_resources - self.resources_used)


@dataclass
class MulliganRecord:
    choice_id: int
    player_name: str
    offered_entity_ids: List[int] = field(default_factory=list)
    # Hearthstone's GameState.SendChoices m_chosenEntities are the cards the
    # player chose to KEEP during the mulligan, not the cards replaced. Keep
    # the raw-log naming for provenance and expose explicit semantic helpers so
    # callers cannot accidentally invert this again.
    chosen_entity_ids: List[int] = field(default_factory=list)
    min_choices: int = 0
    max_choices: int = 0
    expected_chosen_count: Optional[int] = None
    completed: bool = False

    @property
    def kept_entity_ids(self) -> List[int]:
        return list(self.chosen_entity_ids)

    @property
    def replaced_entity_ids(self) -> List[int]:
        if not self.completed:
            return []
        kept = set(self.chosen_entity_ids)
        return [eid for eid in self.offered_entity_ids if eid not in kept]


@dataclass
class ChoicePrompt:
    choice_id: int
    player_name: str
    choice_type: str
    source_entity_id: Optional[int] = None
    entity_ids: List[int] = field(default_factory=list)
    min_choices: int = 0
    max_choices: int = 0
    chosen_entity_ids: List[int] = field(default_factory=list)
    completed: bool = False


@dataclass
class OptionTarget:
    index: int
    entity_id: Optional[int]
    entity_name: str = ""
    card_id: str = ""
    error: str = ""
    error_param: str = ""

    @property
    def legal(self) -> bool:
        return self.error in ("", "NONE")


@dataclass
class SubOption:
    index: int
    entity_id: Optional[int]
    entity_name: str = ""
    card_id: str = ""
    error: str = ""
    error_param: str = ""

    @property
    def legal(self) -> bool:
        return self.error in ("", "NONE")


@dataclass
class LegalOption:
    index: int
    option_type: str
    main_entity_id: Optional[int]
    main_entity_name: str = ""
    card_id: str = ""
    error: str = ""
    error_param: str = ""
    targets: List[OptionTarget] = field(default_factory=list)
    sub_options: List[SubOption] = field(default_factory=list)

    @property
    def legal(self) -> bool:
        return self.option_type == "END_TURN" or self.error in ("", "NONE")


@dataclass
class LegalOptionSet:
    option_set_id: int = 0
    timestamp: str = ""
    options: List[LegalOption] = field(default_factory=list)

    def playable(self) -> List[LegalOption]:
        return [x for x in self.options if x.legal]


@dataclass
class SecretCandidate:
    card_id: str
    name: str
    card_class: str
    rule_key: str = ""


@dataclass
class SecretState:
    entity_id: int
    controller: int
    created_turn: int
    provenance: str = "unknown"
    created_by: Optional[int] = None
    # Secret class is public board-state information. Hearthstone exposes the
    # class tag on the hidden Secret entity and the board also renders
    # class-specific Secret art. Keep this separate from exact identity.
    secret_class: str = ""
    # Engine truth is intentionally richer than player disclosure. Power.log /
    # client-state enrichment may expose an exact hidden Secret identity before
    # Hearthstone reveals it to the player. Internal tracking may use this for
    # coaching, but UI-safe DTOs must never serialize these fields pre-reveal.
    engine_card_id: str = ""
    engine_name: str = ""
    engine_identity_source: str = ""
    publicly_revealed: bool = False
    # Public reveal state. These fields become populated only once the Secret
    # actually reveals/leaves the hidden Secret zone.
    resolved_card_id: str = ""
    resolved_name: str = ""
    candidates: Dict[str, SecretCandidate] = field(default_factory=dict)
    eliminations: Dict[str, str] = field(default_factory=dict)
    eliminated_names: Dict[str, str] = field(default_factory=dict)
    candidate_scope: str = "unknown"

    @property
    def resolved(self) -> bool:
        return bool(self.publicly_revealed and self.resolved_card_id)

    @property
    def engine_known(self) -> bool:
        return bool(self.engine_card_id or self.engine_name)

    def eliminate(self, card_id: str, reason: str) -> None:
        candidate = self.candidates.pop(card_id, None)
        if candidate is not None:
            self.eliminations[card_id] = reason
            self.eliminated_names[card_id] = candidate.name or card_id


@dataclass
class SemanticEvent:
    sequence: int
    timestamp: str
    event_type: str
    text: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GameState:
    active: bool = False
    complete: bool = False
    game_number: int = 0
    build_number: Optional[int] = None
    game_type: Optional[str] = None
    format_type: Optional[str] = None
    scenario_id: Optional[int] = None
    global_turn: int = 0
    sequence: int = 0
    local_player_pid: Optional[int] = None
    local_player_name: Optional[str] = None
    current_player_pid: Optional[int] = None
    first_player_pid: Optional[int] = None
    result: Optional[str] = None
    players: Dict[int, PlayerState] = field(default_factory=dict)
    name_to_pid: Dict[str, int] = field(default_factory=dict)
    entities: Dict[int, EntityState] = field(default_factory=dict)
    game_tags: Dict[str, str] = field(default_factory=dict)
    mulligans: Dict[int, MulliganRecord] = field(default_factory=dict)
    choices: Dict[int, ChoicePrompt] = field(default_factory=dict)
    current_choice_id: Optional[int] = None
    legal_options: LegalOptionSet = field(default_factory=LegalOptionSet)
    secrets: Dict[int, SecretState] = field(default_factory=dict)
    events: List[SemanticEvent] = field(default_factory=list)
    stored_card_pools: Dict[int, tuple[str, ...]] = field(default_factory=dict)
    # Immutable public observations survive zone moves, transforms and control changes.
    card_history: List[Any] = field(default_factory=list)
    stored_card_details: Dict[int, tuple[Any, ...]] = field(default_factory=dict)
    turn_owners: Dict[int, int] = field(default_factory=dict)
    play_sequence_counter: int = 0
    raw_counts: Dict[str, int] = field(default_factory=dict)
    recoverable_overdraw: List[dict] = field(default_factory=list)

    def reset(self, game_number: Optional[int] = None) -> None:
        next_number = game_number if game_number is not None else self.game_number + 1
        self.__dict__.update(GameState(game_number=next_number, active=True).__dict__)

    @property
    def opponent_startup_pending(self) -> bool:
        return bool(self.game_tags.get("GHOSTDATA_GAME_START")) and not (
            self.game_tags.get("GHOSTDATA_TASK_STARTED") == "1" or all(
                self.game_tags.get(f"GHOSTDATA_TASK_MULLIGAN_{pid}") == "DONE" for pid in (1, 2)))

    def entity(self, entity_id: int) -> EntityState:
        if entity_id not in self.entities:
            self.entities[entity_id] = EntityState(entity_id=entity_id)
        return self.entities[entity_id]

    def player(self, pid: int) -> PlayerState:
        if pid not in self.players:
            self.players[pid] = PlayerState(player_id=pid)
        return self.players[pid]

    @property
    def local_player(self) -> Optional[PlayerState]:
        if self.local_player_pid is None:
            return None
        return self.players.get(self.local_player_pid)

    @property
    def opponent_pid(self) -> Optional[int]:
        if self.local_player_pid is None:
            return None
        others = [pid for pid in self.players if pid != self.local_player_pid]
        return others[0] if len(others) == 1 else None

    @property
    def opponent(self) -> Optional[PlayerState]:
        pid = self.opponent_pid
        return self.players.get(pid) if pid is not None else None

    def bind_name(self, name: str, pid: Optional[int] = None) -> Optional[int]:
        if not name or name in ("GameEntity", "UNKNOWN HUMAN PLAYER"):
            return None
        if name in self.name_to_pid:
            return self.name_to_pid[name]
        if pid is None:
            # If local is known and this is not the local name, the remaining PID is safe in 1v1 constructed.
            if self.local_player_name and name != self.local_player_name and self.opponent_pid is not None:
                pid = self.opponent_pid
            elif self.local_player_name == name and self.local_player_pid is not None:
                pid = self.local_player_pid
        if pid is None:
            return None
        self.name_to_pid[name] = pid
        player = self.player(pid)
        player.name = name
        return pid

    def zone_entities(self, pid: int, zone: str) -> List[EntityState]:
        out = [e for e in self.entities.values() if e.controller == pid and e.zone == zone]
        return sorted(out, key=lambda e: (e.zone_position if e.zone_position > 0 else 999, e.entity_id))

    def hand(self, pid: int) -> List[EntityState]:
        return self.zone_entities(pid, "HAND")

    def board(self, pid: int) -> List[EntityState]:
        return [
            e for e in self.zone_entities(pid, "PLAY")
            if e.card_type in ("MINION", "LOCATION")
        ]

    def graveyard(self, pid: int) -> List[EntityState]:
        return self.zone_entities(pid, "GRAVEYARD")

    def deck_count(self, pid: int) -> int:
        return sum(1 for e in self.entities.values() if e.controller == pid and e.zone == "DECK")

    def hero(self, pid: int) -> Optional[EntityState]:
        p = self.players.get(pid)
        if not p or p.hero_entity_id is None:
            return None
        return self.entities.get(p.hero_entity_id)

    def emit(self, timestamp: str, event_type: str, text: str, **data: Any) -> SemanticEvent:
        self.sequence += 1
        ev = SemanticEvent(self.sequence, timestamp, event_type, text, data)
        self.events.append(ev)
        return ev

    def summary(self) -> Dict[str, Any]:
        def ent(e: EntityState) -> Dict[str, Any]:
            return {
                "id": e.entity_id,
                "name": e.name or None,
                "card_id": e.card_id or None,
                "zone": e.zone,
                "position": e.zone_position,
                "cost": e.cost,
                "atk": e.attack,
                "health": e.health,
                "damage": e.damage,
                "creator": e.creator,
            }

        lp = self.local_player
        op = self.opponent
        lhero = self.hero(lp.player_id) if lp else None
        ohero = self.hero(op.player_id) if op else None
        return {
            "game_number": self.game_number,
            "active": self.active,
            "complete": self.complete,
            "build": self.build_number,
            "game_type": self.game_type,
            "format": self.format_type,
            "global_turn": self.global_turn,
            "local": {
                "pid": lp.player_id if lp else None,
                "name": lp.name if lp else None,
                "class": lp.player_class if lp else None,
                "turn": lp.local_turn if lp else None,
                "mana": lp.available_mana if lp else None,
                "resources": lp.resources if lp else None,
                "resources_used": lp.resources_used if lp else None,
                "health": lhero.effective_health if lhero else None,
                "hand": [ent(e) for e in self.hand(lp.player_id)] if lp else [],
                "board": [ent(e) for e in self.board(lp.player_id)] if lp else [],
                "deck_count": self.deck_count(lp.player_id) if lp else None,
            },
            "opponent": {
                "pid": op.player_id if op else None,
                "name": op.name if op else None,
                "class": op.player_class if op else None,
                "turn": op.local_turn if op else None,
                "mana": op.available_mana if op else None,
                "health": ohero.effective_health if ohero else None,
                "hand_count": len(self.hand(op.player_id)) if op else None,
                "known_hand": [ent(e) for e in self.hand(op.player_id) if e.is_known] if op else [],
                "board": [ent(e) for e in self.board(op.player_id)] if op else [],
                "deck_count": self.deck_count(op.player_id) if op else None,
            },
            "first_player_pid": self.first_player_pid,
            "current_player_pid": self.current_player_pid,
            "result": self.result,
            "mulligans": {str(k): asdict(v) for k, v in self.mulligans.items()},
            "active_secrets": {
                str(k): {
                    "controller": v.controller,
                    "secret_class": v.secret_class or None,
                    "resolved": v.resolved,
                    "resolved_card_id": v.resolved_card_id or None,
                    "resolved_name": v.resolved_name or None,
                    "candidates": sorted(v.candidates),
                    "eliminations": v.eliminations,
                    "candidate_scope": v.candidate_scope,
                    "candidate_names": sorted(c.name for c in v.candidates.values()),
                }
                for k, v in self.secrets.items()
            },
            "legal_option_set_id": self.legal_options.option_set_id,
            "legal_options": [
                {
                    "index": x.index,
                    "type": x.option_type,
                    "entity_id": x.main_entity_id,
                    "name": x.main_entity_name,
                    "card_id": x.card_id,
                    "error": x.error,
                    "legal": x.legal,
                    "targets": [asdict(t) | {"legal": t.legal} for t in x.targets],
                    "sub_options": [asdict(s) | {"legal": s.legal} for s in x.sub_options],
                }
                for x in self.legal_options.options
            ],
        }
