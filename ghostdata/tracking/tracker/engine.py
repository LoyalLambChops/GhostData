from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass, replace
from typing import Dict, Iterable, Optional

from ..snapshot import TrackerDeckSnapshot
from ..scope import is_standard_constructed
from ..card_db import CardDatabase
from ..models import EntityState, GameState, SemanticEvent
from ..overdraw import rows as overdraw_rows
from .models import DeckTrackerState, HeroZoneEffectRow, OpponentObservedRow, PlayerDeckRow, PlayerExtraDeckRow, Provenance, RailCardRow, HandSlot
from ..card_taxonomy import hero_zone_effect_kind, is_playable_card_entity, quest_progress, resolved_card_type

# Public, deterministic Start-of-Game replacements. The children arrive in an
# unknown order, so these are multisets, never invented entity assignments.
_SHATTERED_POOLS = {
    "CATA_EVENT_110": tuple(f"CATA_EVENT_110t{i}" for i in range(2, 8)),
    "DMF_254": ("DMF_254t3", "DMF_254t4", "DMF_254t5", "DMF_254t7"),
}


@dataclass
class _TrackedEntity:
    entity_id: int
    first_controller: int | None = None
    controller: int | None = None
    first_zone: str = ""
    zone: str = ""
    previous_zone: str = ""
    first_card_id: str = ""
    card_id: str = ""
    creator: int | None = None
    displayed_creator: int | None = None
    copied_from_entity_id: int | None = None
    original_dbf: int | None = None
    original_card_id: str = ""
    provenance: str = Provenance.UNKNOWN
    entered_deck_from_elsewhere: bool = False
    ever_hand: bool = False
    ever_left_deck: bool = False
    transformed: bool = False
    publicly_revealed: bool = False
    first_public_card_id: str = ""
    hand_turn: int = 0
    hand_origin: str = "DRAWN"
    discarded: bool = False
    burned: bool = False
    played: bool = False
    first_turn: int = 0
    identity_hidden: bool = False


class DeckTrackerEngine:
    """Deterministic player-deck and observational opponent tracker.

    The selected-deck sensor supplies the authoritative original multiset. The
    Power.log parser supplies entity lifecycle facts. This engine intentionally
    does not infer unobserved opponent cards or mutate original-deck counts when
    provenance cannot be justified.
    """

    def __init__(
        self,
        *,
        card_db: Optional[CardDatabase] = None,
        supported_player_classes: Optional[Iterable[str]] = None,
    ):
        self.card_db = card_db or CardDatabase.__new__(CardDatabase)  # replaced below for type-safe fallback
        if card_db is None:
            # A tiny inert CardDatabase-shaped fallback keeps unit tests/network
            # independence simple without touching the filesystem.
            self.card_db = _NullCardDatabase()
        self.supported_player_classes = frozenset(
            str(value or "").strip().upper().replace(" ", "_")
            for value in (supported_player_classes or ())
            if str(value or "").strip()
        ) or frozenset({"DEATHKNIGHT", "DEMONHUNTER", "DRUID", "HUNTER", "MAGE", "PALADIN", "PRIEST", "ROGUE", "SHAMAN", "WARLOCK", "WARRIOR"})

        self._selected: Optional[TrackerDeckSnapshot] = None
        self._baseline: Counter[int] = Counter()
        self._baseline_meta: Dict[int, tuple[str, str, int | None]] = {}
        self._entities: Dict[int, _TrackedEntity] = {}
        self._observed_pairs: set[tuple[int, str]] = set()
        self._opponent_observation_provenance: Dict[tuple[int, str], str] = {}
        self._last_event_sequence = 0
        self._event_cursor = 0
        self._game_number = 0
        self._last_local_player_pid: int | None = None
        self._initial_player_class = ""
        self._revision = 0
        self._last_state: Optional[DeckTrackerState] = None
        self._warnings: deque[str] = deque(maxlen=8)
        self._predicted_pools: dict[int, tuple[int, tuple[str, ...]]] = {}
        self._mixed_pools = []
        self._unique_public_cards = set()

    @property
    def state(self) -> DeckTrackerState:
        return self._last_state or self._build_state(None)

    @property
    def selected_snapshot(self) -> Optional[TrackerDeckSnapshot]:
        return self._selected

    def seed_selected_deck(self, snapshot: TrackerDeckSnapshot, game: Optional[GameState] = None, *, refresh_metadata: bool = False) -> bool:
        """Accept only an exact in-scope Standard starting composition.

        ``game`` is optional so a late asynchronous sensor result can be
        reconciled against Power.log entities that were already reconstructed.
        This is essential on warm start: log ingestion must never block on the
        process-memory sensor, but tracker truth must still recover once the
        exact selected deck arrives.
        """
        if not snapshot.exact:
            return False
        class_id = str(snapshot.class_id or "").upper()
        if class_id not in self.supported_player_classes:
            return False

        initial_class = self._starting_class(game)
        if initial_class and initial_class != class_id:
            return False

        if snapshot == self._selected and not refresh_metadata:
            return True

        changed = self._selected is None or snapshot.deck_hash != self._selected.deck_hash or snapshot.cards != self._selected.cards
        self._selected = snapshot
        self._baseline = Counter({int(dbf): int(count) for dbf, count in snapshot.cards})
        self._baseline_meta.clear()
        for dbf in sorted(self._baseline):
            card = self.card_db.get_by_dbf(dbf)
            self._baseline_meta[dbf] = (
                str(card.card_id if card else dbf),
                str(card.name if card else f"DBF {dbf}"),
                card.cost if card else None,
            )
        if changed and self._game_number <= 0:
            self._entities.clear()
            self._observed_pairs.clear()
            self._opponent_observation_provenance.clear()
        elif changed:
            for mem in self._entities.values():
                mem.original_dbf = None
                mem.original_card_id = ""

        # The live sensor is intentionally asynchronous. On a warm start the
        # current Power.log game may already have been reconstructed before the
        # exact selected composition arrives. Reconcile every already-observed
        # identity now so earlier draws/plays are not permanently left UNKNOWN.
        if game is not None:
            self._reconcile_existing_entities(game)
        self._refresh_state(game)
        return True

    def _starting_class(self, game):
        if game is None or game.local_player_pid is None:
            return ""
        if game.game_number == self._game_number and self._initial_player_class:
            return self._initial_player_class
        player = game.players.get(game.local_player_pid)
        return str(player.starting_class or player.player_class or "").upper() if player else ""

    def clear_selected_deck(self, game=None):
        """Drop only the starting-deck assumption, retaining observed match facts."""
        self._selected = None
        self._baseline.clear()
        self._baseline_meta.clear()
        for mem in self._entities.values():
            mem.original_dbf = None
            mem.original_card_id = ""
            if game and (entity := game.entities.get(mem.entity_id)) is not None:
                mem.provenance = self._derive_nonoriginal_provenance(game, entity, mem)
        if game is not None:
            self._refresh_state(game)

    def _reconcile_existing_entities(self, game: GameState) -> None:
        for eid, mem in list(self._entities.items()):
            entity = game.entities.get(eid)
            if entity is None or not entity.card_id:
                continue
            self._sync_identity(game, entity, mem)
            if mem.original_dbf is None:
                mem.provenance = self._derive_nonoriginal_provenance(game, entity, mem)
            elif mem.transformed:
                mem.provenance = Provenance.TRANSFORMED
            elif (
                mem.first_controller is not None
                and entity.controller is not None
                and mem.first_controller != entity.controller
            ):
                mem.provenance = Provenance.STOLEN
            else:
                mem.provenance = Provenance.ORIGINAL_DECK

    def reset_runtime(self, *, preserve_selected_deck: bool = True) -> None:
        selected = self._selected if preserve_selected_deck else None
        baseline = Counter(self._baseline) if preserve_selected_deck else Counter()
        baseline_meta = dict(self._baseline_meta) if preserve_selected_deck else {}
        self._entities.clear()
        self._observed_pairs.clear()
        self._opponent_observation_provenance.clear()
        self._last_event_sequence = 0
        self._event_cursor = 0
        self._game_number = 0
        self._last_local_player_pid = None
        self._initial_player_class = ""
        self._warnings.clear()
        self._predicted_pools.clear()
        self._mixed_pools.clear()
        self._unique_public_cards.clear()
        self._selected = selected
        self._baseline = baseline
        self._baseline_meta = baseline_meta
        self._refresh_state(None)

    def observe(self, game: GameState, *, publish: bool = True) -> bool:
        """Consume new parser semantic events and publish a new immutable state when changed."""
        if game.game_number != self._game_number:
            self._begin_game(game.game_number)
        elif game.sequence < self._last_event_sequence:
            # Parser/source reconstruction boundary. Preserve the selected deck,
            # but never combine entity history from two authoritative streams.
            self._begin_game(game.game_number)

        # Hearthstone can reveal opening-hand CardIDs before DebugPrintGame has
        # identified which PlayerID is local.  Those identities are deliberately
        # not classified as ORIGINAL_DECK until local ownership is authoritative.
        # When local identity becomes known, revisit already-seen entities once.
        # This is a bounded reconciliation checkpoint, not recurring full-state
        # polling, and fixes the real Gate-7 field ordering without weakening the
        # provenance gate or rescanning history on every line.
        if not self._initial_player_class:
            self._initial_player_class = self._starting_class(game)
        if self._selected and self._initial_player_class and self._selected.class_id.upper() != self._initial_player_class:
            self.clear_selected_deck(game)

        current_local_pid = game.local_player_pid
        if current_local_pid is not None and current_local_pid != self._last_local_player_pid:
            self._last_local_player_pid = current_local_pid
            if self._selected is not None and self._baseline:
                self._reconcile_existing_entities(game)

        # Live runtime calls observe() after nearly every parsed Power.log line.
        # Consume only newly appended semantic events so tracker work remains
        # O(new events), not O(total game events) per line.
        if self._event_cursor > len(game.events):
            self._event_cursor = 0
        for event in game.events[self._event_cursor:]:
            if event.sequence <= self._last_event_sequence:
                continue
            self._consume_event(game, event)
            self._last_event_sequence = max(self._last_event_sequence, event.sequence)
        self._event_cursor = len(game.events)

        # Some facts (hand/deck counts, class identity) are current-state values,
        # so rebuild even when the last parser line did not create a semantic event.
        return self._refresh_state(game) if publish else False

    def _begin_game(self, game_number: int) -> None:
        self._predicted_pools.clear()
        self._mixed_pools.clear()
        self._unique_public_cards.clear()
        self._entities.clear()
        self._observed_pairs.clear()
        self._opponent_observation_provenance.clear()
        self._last_event_sequence = 0
        self._event_cursor = 0
        self._game_number = int(game_number or 0)
        self._last_local_player_pid = None
        self._initial_player_class = ""
        self._warnings.clear()

    def _consume_event(self, game: GameState, event: SemanticEvent) -> None:
        if event.event_type == "GAME_START":
            return
        if event.event_type == "PUBLIC_POOL":
            self._mixed_pools.append((event.data["player"], tuple(event.data["cards"]), frozenset(event.data["members"])))
        if event.event_type == "PUBLIC_UNIQUE":
            self._unique_public_cards.add((event.data["player"], event.data["card_id"]))
        if event.event_type == "TRIGGER":
            source = game.entities.get(_event_entity_id(event))
            if source and source.card_id in _SHATTERED_POOLS and source.controller is not None and game.global_turn <= 1:
                self._predicted_pools[source.entity_id] = (source.controller, _SHATTERED_POOLS[source.card_id])
        if event.event_type in {"ZONE_CHANGE", "CONTROLLER_CHANGE", "PROVENANCE_CHANGE", "REVEAL", "PLAY", "HIDE"}:
            eid = _event_entity_id(event)
            if eid is None:
                return
            entity = game.entities.get(eid)
            if entity is None:
                return
            mem = self._sync_entity(game, entity, event)
            if event.event_type == "HIDE":
                mem.identity_hidden = True
                mem.publicly_revealed = False
            if event.event_type == "PLAY":
                mem.played = True
                mem.discarded = False
            if event.event_type == "REVEAL" and entity.card_id and not (
                entity.controller == game.opponent_pid and entity.zone == "SECRET"
                and hero_zone_effect_kind(entity, self.card_db) == "SECRET"
            ):
                # REVEAL is the semantic public-identity boundary. Merely knowing
                # a hidden entity CardID internally is not sufficient to expose it.
                mem.publicly_revealed = True
                mem.identity_hidden = False
                self._unique_public_cards.discard((entity.controller, entity.card_id))
            if event.event_type == "PLAY":
                mem.identity_hidden = False
            if mem.publicly_revealed or event.event_type == "PLAY":
                self._observe_identity(game, entity, mem)

    def _sync_entity(self, game: GameState, entity: EntityState, event: SemanticEvent) -> _TrackedEntity:
        mem = self._entities.get(entity.entity_id)
        if mem is None:
            mem = _TrackedEntity(entity_id=entity.entity_id, first_turn=game.global_turn)
            self._entities[entity.entity_id] = mem

        old_controller = mem.controller
        if mem.first_controller is None and entity.controller is not None:
            mem.first_controller = entity.controller
        mem.controller = entity.controller
        mem.creator = entity.creator if entity.creator != entity.entity_id else None
        mem.displayed_creator = entity.displayed_creator if entity.displayed_creator != entity.entity_id else None
        displayed_source = game.entities.get(mem.displayed_creator or 0)
        if displayed_source and displayed_source.card_id in {"CS2_053", "CORE_CS2_053", "VAN_CS2_053"}:
            # Far Sight decorates an ordinary draw with DISPLAYED_CREATOR.
            # It did not create a replacement for that starting-deck card.
            mem.displayed_creator = None
        mem.copied_from_entity_id = entity.copied_from_entity_id
        if mem.original_dbf is not None and not mem.transformed and entity.card_id == mem.card_id and (mem.creator or mem.displayed_creator or mem.copied_from_entity_id):
            # FULL_ENTITY metadata may follow identity and zone. A late creator
            # invalidates the provisional baseline assignment.
            mem.original_dbf = None
            mem.original_card_id = ""

        old_zone = str(event.data.get("old_zone") or mem.zone or "") if event.event_type == "ZONE_CHANGE" else mem.zone
        new_zone = str(event.data.get("new_zone") or entity.zone or "") if event.event_type == "ZONE_CHANGE" else str(entity.zone or mem.zone or "")
        if not mem.first_zone and new_zone:
            mem.first_zone = old_zone or new_zone
        if old_zone and new_zone == "DECK" and old_zone != "DECK" and mem.first_zone != "DECK":
            mem.entered_deck_from_elsewhere = True
        if mem.zone and mem.zone != "DECK" and new_zone == "DECK" and mem.first_zone != "DECK":
            mem.entered_deck_from_elsewhere = True
        if new_zone and new_zone != "DECK" and mem.first_zone == "DECK":
            mem.ever_left_deck = True
        if new_zone == "HAND" and old_zone != "HAND":
            mem.played = False
            mem.ever_hand = True
            mem.hand_turn = game.global_turn
            mem.hand_origin = "RETURNED" if old_zone == "PLAY" else "GENERATED" if mem.creator or mem.displayed_creator else "DRAWN"
        if event.event_type == "ZONE_CHANGE" and new_zone == "GRAVEYARD":
            mem.discarded = old_zone == "HAND" and not mem.played
            mem.burned = old_zone == "DECK"
        if new_zone:
            mem.previous_zone = mem.zone
            mem.zone = new_zone

        if entity.card_id:
            self._sync_identity(game, entity, mem)

        if old_controller is not None and entity.controller is not None and old_controller != entity.controller:
            mem.provenance = Provenance.STOLEN

        if mem.original_dbf is None:
            mem.provenance = self._derive_nonoriginal_provenance(game, entity, mem)
        elif mem.transformed:
            mem.provenance = Provenance.TRANSFORMED
        elif (
            mem.first_controller is not None
            and entity.controller is not None
            and mem.first_controller != entity.controller
        ):
            # Preserve that an original local card changed ownership. This does
            # not change the selected-deck baseline, but it matters when the
            # same entity is later observed on the opponent side.
            mem.provenance = Provenance.STOLEN
        else:
            mem.provenance = Provenance.ORIGINAL_DECK
        return mem

    def _sync_identity(self, game: GameState, entity: EntityState, mem: _TrackedEntity) -> None:
        new_card_id = str(entity.card_id or "")
        if not new_card_id:
            return
        if mem.first_card_id and mem.card_id and mem.card_id != new_card_id:
            mem.transformed = True
        if not mem.first_card_id:
            mem.first_card_id = new_card_id
        mem.card_id = new_card_id

        if mem.original_dbf is None and self._eligible_original_entity(game, entity, mem):
            dbf = self.card_db.dbf_id_for_card_id(mem.first_card_id or new_card_id)
            if dbf is not None and dbf in self._baseline:
                assigned = sum(1 for x in self._entities.values() if x.original_dbf == dbf)
                if assigned < self._baseline[dbf]:
                    mem.original_dbf = dbf
                    mem.original_card_id = mem.first_card_id or new_card_id
                    mem.transformed = self.card_db.dbf_id_for_card_id(new_card_id) != dbf
                    mem.provenance = Provenance.TRANSFORMED if mem.transformed else Provenance.ORIGINAL_DECK
        elif mem.original_dbf is not None:
            dbf = self.card_db.dbf_id_for_card_id(new_card_id)
            if dbf is not None:
                mem.transformed = dbf != mem.original_dbf
            if mem.transformed:
                mem.provenance = Provenance.TRANSFORMED

    def _eligible_original_entity(self, game: GameState, entity: EntityState, mem: _TrackedEntity) -> bool:
        if not self._selected or not self._baseline:
            return False
        local_pid = game.local_player_pid
        origin_controller = mem.first_controller if mem.first_controller is not None else entity.controller
        if local_pid is None or origin_controller != local_pid:
            return False
        if mem.first_zone != "DECK" or mem.entered_deck_from_elsewhere:
            return False
        if mem.creator or mem.displayed_creator or mem.copied_from_entity_id:
            return False
        return True

    def _derive_nonoriginal_provenance(self, game: GameState, entity: EntityState, mem: _TrackedEntity) -> str:
        if mem.transformed:
            return Provenance.TRANSFORMED
        if mem.first_controller is not None and entity.controller is not None and mem.first_controller != entity.controller:
            return Provenance.STOLEN
        if entity.copied_from_entity_id:
            return Provenance.COPIED
        creator_id = mem.creator or mem.displayed_creator
        if creator_id:
            creator = game.entities.get(creator_id)
            if creator and creator.card_id and entity.card_id and creator.card_id == entity.card_id:
                return Provenance.COPIED
            return Provenance.GENERATED
        if mem.entered_deck_from_elsewhere or (mem.first_zone and mem.first_zone != "DECK"):
            return Provenance.UNKNOWN
        return Provenance.UNKNOWN

    def _observe_identity(self, game: GameState, entity: EntityState, mem: _TrackedEntity) -> None:
        if not entity.card_id:
            return

        # Opponent ownership must be positively established. Controller 0/None
        # and local Quest/reward implementation entities are not observations
        # of the opponent's cards.
        opponent_pid = game.opponent_pid
        local_pid = game.local_player_pid
        if opponent_pid is None or entity.controller != opponent_pid:
            return

        # Generated child entities can momentarily carry surprising controller
        # values while their creator chain still proves they originated from a
        # local effect.  Do not let those system transitions become opponent
        # observations unless the entity has actually changed ownership.
        creator_owner = self._creator_owner_pid(game, entity)
        if (
            local_pid is not None
            and creator_owner == local_pid
            and mem.provenance != Provenance.STOLEN
            and entity.tags.get("GHOSTDATA_PUBLIC_CREATION") != "1"
        ):
            return

        if not self._eligible_opponent_card_observation(game, entity, mem):
            return

        pair = (entity.entity_id, entity.card_id)
        provenance = mem.provenance
        if provenance == Provenance.ORIGINAL_DECK:
            # We never claim an opponent card was originally in their deck from
            # our selected-deck baseline; opponent origin remains observational.
            provenance = Provenance.UNKNOWN
        if pair in self._observed_pairs:
            # Provenance tags can arrive after the public identity. Upgrade an
            # earlier UNKNOWN observation (e.g. The Coin / copied cards) without
            # adding another observed copy or rescanning the game.
            existing = self._opponent_observation_provenance.get(pair, Provenance.UNKNOWN)
            if existing == Provenance.UNKNOWN and provenance != Provenance.UNKNOWN:
                self._opponent_observation_provenance[pair] = provenance
            return
        self._observed_pairs.add(pair)
        if not mem.first_public_card_id:
            mem.first_public_card_id = entity.card_id
        self._opponent_observation_provenance[pair] = provenance

    def _creator_owner_pid(self, game: GameState, entity: EntityState) -> int | None:
        """Resolve the nearest authoritative player owner in a creator chain.

        Hearthstone can materialize generated Quest/Secret/reward helpers under
        controller 0/None (or other transient controller values).  Creator and
        DISPLAYED_CREATOR links provide a bounded provenance path back to the
        player-owned source. Missing/ambiguous chains return None; GhostData
        never guesses an owner from card class or name.
        """
        valid_pids = set(game.players)
        current = entity
        seen: set[int] = {entity.entity_id}
        for _ in range(8):
            creator_id = current.creator or current.displayed_creator
            if not creator_id or creator_id in seen:
                return None
            seen.add(creator_id)
            creator = game.entities.get(creator_id)
            if creator is None:
                return None
            if creator.controller in valid_pids:
                return creator.controller
            current = creator
        return None

    def _hero_zone_owner_pid(self, game: GameState, entity: EntityState) -> int | None:
        """Resolve an active hero-zone effect owner without class/name inference.

        Generated hero-zone effects are non-transferable state in ordinary play,
        so a proven creator-chain owner is the strongest signal.  Manually played
        effects have no creator and fall back to their direct player controller.
        """
        creator_owner = self._creator_owner_pid(game, entity)
        if creator_owner is not None:
            return creator_owner
        return entity.controller if entity.controller in game.players else None

    def _eligible_opponent_card_observation(
        self, game: GameState, entity: EntityState, mem: _TrackedEntity
    ) -> bool:
        """Return True only for legitimately observed playable card entities.

        The card rail is not a dump of every named Power.log entity. Hero powers,
        enchantments, game/player entities, and SETASIDE implementation tokens are
        state artifacts, not cards the opponent can be said to have played/drawn.
        Generated entities revealed while still in DECK are also deferred until
        they enter an actionable zone, preventing start-of-game helper tokens from
        masquerading as deck cards.
        """
        if not is_playable_card_entity(entity, self.card_db):
            return False
        if self._is_unselected_discover_option(entity, mem):
            return False

        zone = str(entity.zone or mem.zone or "").upper()
        card_type = resolved_card_type(entity, self.card_db)
        if (
            card_type == "HERO"
            and str(mem.first_zone or "").upper() == "PLAY"
            and not mem.ever_hand
            and not mem.ever_left_deck
        ):
            # The starting class portrait is a HERO entity in PLAY and is
            # publicly revealed during game setup. It is identity/state, not a
            # card the opponent drew or played. Actual Hero cards arrive from
            # HAND/DECK and remain eligible for factual history.
            return False
        if zone == "SETASIDE":
            return False
        if zone not in {"DECK", "HAND", "PLAY", "GRAVEYARD", "SECRET"}:
            return False

        creator_id = entity.creator or entity.displayed_creator
        effect_kind = hero_zone_effect_kind(entity, self.card_db)
        if zone == "DECK" and creator_id and entity.tags.get("GHOSTDATA_PUBLIC_CREATION") != "1":
            # A generated helper/token can be created in DECK as an implementation
            # detail and immediately moved SETASIDE.  It becomes a rail card only
            # after it reaches a player-actionable/public zone.
            return False
        if zone == "SECRET" and effect_kind and creator_id:
            # A Quest/Secret/Aura/etc. materialized by another card is active
            # hero-zone state, not a separate card the opponent drew/played from
            # hand.  Keep it on the hero-zone surface while active; if it later
            # becomes a public playable/reward entity, that later observation can
            # enter card history with generated provenance.
            return False
        return True

    @staticmethod
    def _is_unselected_discover_option(entity: EntityState, mem: _TrackedEntity) -> bool:
        """Identify revealed Discover choices that never became opponent cards.

        Hearthstone reveals unchosen choices while moving them directly from
        SETASIDE to GRAVEYARD. The WAS_DISCOVER_OPTION tag can arrive after the
        reveal/zone events, so this predicate is also applied while rendering
        rows to retract an early provisional observation deterministically.
        A selected option reaches HAND (or another actionable zone) and remains
        eligible if it is later publicly revealed or played.
        """
        tags = {str(key or "").upper(): str(value or "") for key, value in entity.tags.items()}
        return (
            tags.get("WAS_DISCOVER_OPTION") == "1"
            and str(mem.first_zone or "").upper() == "SETASIDE"
            and str(entity.zone or mem.zone or "").upper() == "GRAVEYARD"
            and not mem.ever_hand
            and not mem.ever_left_deck
        )

    def _player_extra_deck_rows(
        self, game: Optional[GameState], local_pid: Optional[int]
    ) -> list[PlayerExtraDeckRow]:
        """Known non-original cards currently inside the player's deck.

        Accounting has tracked these since v46, but the right rail previously
        hid their identities.  Group only entities whose current identity and
        local DECK location are known; unresolved inserts remain fail-closed in
        the accounting delta instead of being invented into this list.
        """
        if game is None or local_pid is None:
            return []

        grouped: dict[str, dict[str, object]] = {}
        for mem in self._entities.values():
            if (
                mem.controller != local_pid
                or mem.zone != "DECK"
                or not mem.card_id
                or (mem.original_dbf is not None and not mem.transformed)
            ):
                continue
            data = grouped.setdefault(mem.card_id, {"count": 0, "provenance": set()})
            data["count"] = int(data["count"]) + 1
            data["provenance"].add(mem.provenance)  # type: ignore[index]

        rows: list[PlayerExtraDeckRow] = []
        for card_id, data in grouped.items():
            card = self.card_db.get(card_id)
            provenances = set(data["provenance"])  # type: ignore[arg-type]
            provenance = next(iter(provenances)) if len(provenances) == 1 else "MIXED"
            rows.append(PlayerExtraDeckRow(
                card_id=card_id,
                name=str(card.name if card else card_id),
                cost=card.cost if card else None,
                copies_in_deck=int(data["count"]),
                provenance=provenance,
                card_type=str(card.card_type or "").upper() if card else "",
                spell_school=str(card.spell_school or "").upper() if card else "",
            ))
        return sorted(rows, key=lambda r: (r.cost if r.cost is not None else 99, r.name.lower(), r.card_id))

    def _hero_zone_effect_rows(
        self, game: Optional[GameState], pid: Optional[int], owner: str
    ) -> list[HeroZoneEffectRow]:
        if game is None or pid is None:
            return []

        rows: dict[int, HeroZoneEffectRow] = {}
        for entity in game.entities.values():
            if str(entity.zone or "").upper() != "SECRET":
                continue
            if self._hero_zone_owner_pid(game, entity) != pid:
                continue
            kind = hero_zone_effect_kind(entity, self.card_db)
            if not kind:
                continue
            card = self.card_db.get(entity.card_id) if entity.card_id else None
            progress, total = quest_progress(entity)
            mem = self._entities.get(entity.entity_id)
            provenance = mem.provenance if mem is not None else (
                Provenance.GENERATED if entity.creator or entity.displayed_creator else Provenance.UNKNOWN
            )
            # Opponent hidden Secrets remain observation-only on the tracker rail.
            # Hearthstone may expose an exact hidden identity internally; Match
            # Intelligence can use that privately, but the tracker must not render
            # it until the Secret is publicly revealed/observed. Quests and other
            # visible hero-zone effects remain fully identified.
            protect_hidden_opponent_secret = (
                owner == "OPPONENT"
                and kind == "SECRET"
                and not (mem is not None and mem.publicly_revealed)
            )
            rows[entity.entity_id] = HeroZoneEffectRow(
                entity_id=entity.entity_id,
                owner=owner,
                kind=kind,
                card_id="" if protect_hidden_opponent_secret else str(entity.card_id or ""),
                name="Unknown Secret" if protect_hidden_opponent_secret else str((card.name if card else entity.name) or entity.card_id or f"Unknown {kind.title()}"),
                known=False if protect_hidden_opponent_secret else bool(entity.card_id),
                cost=None if protect_hidden_opponent_secret else (card.cost if card else entity.cost),
                spell_school="" if protect_hidden_opponent_secret else (str(card.spell_school or "").upper() if card else ""),
                progress=progress,
                progress_total=total,
                candidate_count=0,
                provenance=provenance,
            )

        # The existing SecretTracker owns hidden-opponent Secret state.  Preserve
        # that information without fabricating a CardID or mixing the slot into
        # generic opponent card history.
        for secret in game.secrets.values():
            if secret.controller != pid or secret.resolved:
                continue
            if secret.entity_id in rows:
                existing = rows[secret.entity_id]
                if existing.kind == "SECRET" and not existing.known:
                    rows[secret.entity_id] = replace(
                        existing, candidate_count=len(secret.candidates),
                        provenance=(Provenance.GENERATED if secret.provenance == "generated" else existing.provenance),
                    )
                continue
            rows[secret.entity_id] = HeroZoneEffectRow(
                entity_id=secret.entity_id,
                owner=owner,
                kind="SECRET",
                name="Unknown Secret",
                known=False,
                candidate_count=len(secret.candidates),
                provenance=Provenance.GENERATED if secret.provenance == "generated" else Provenance.UNKNOWN,
            )

        return sorted(rows.values(), key=lambda r: (r.kind, r.cost if r.cost is not None else 99, r.name.lower(), r.entity_id))

    def _assembled_card(self, entity):
        """Compose only an already-visible entity's public Assemble components."""
        if entity.tags.get("ASSEMBLED_MINION") != "1":
            return None
        body = self.card_db.get(entity.card_id)
        rules_id = entity.tags.get("CRAFTABLE_SECOND_HALF_DBID", "")
        rules = self.card_db.get_by_dbf(int(rules_id)) if str(rules_id).isdigit() else None
        name = f"{body.name if body else entity.card_id} + {rules.name if rules else 'Unknown rules'}"
        stats = " / ".join(str(entity.tags.get(tag, "?")) for tag in ("ATK", "HEALTH"))
        cost_tag = str(entity.tags.get("COST", ""))
        cost = int(cost_tag) if cost_tag.lstrip("-").isdigit() else (body.cost if body else None)
        text = f"Assembled minion · {stats} attack / health · Cost {cost if cost is not None else '?'}\n"
        text += f"Rules: {rules.name}\n{rules.text}" if rules else "Rules unavailable in local data."
        return name, cost, text

    def _display_rows(self, game, pid, baseline_rows=()):
        if game is None or pid is None:
            return [RailCardRow(r.card_id, r.name, r.cost, r.remaining_copies, "DECK", Provenance.ORIGINAL_DECK) for r in baseline_rows]
        local = pid == game.local_player_pid
        result = []
        deck_count = game.deck_count(pid)
        portal = self._has_portal(game, pid)
        for row in baseline_rows:
            held = sum(1 for m in self._entities.values() if m.controller == pid and m.zone == "HAND"
                and m.original_dbf == row.dbf_id and m.card_id == row.card_id)
            discarded = sum(1 for m in self._entities.values() if m.original_dbf == row.dbf_id and m.discarded)
            burned = sum(1 for m in self._entities.values() if m.original_dbf == row.dbf_id and m.burned)
            detail = [f"HAND {held}"] if held else []
            if discarded: detail.append(f"DISCARDED {discarded}")
            if burned: detail.append(f"BURNED {burned}")
            result.append(RailCardRow(row.card_id, row.name, row.cost, row.remaining_copies, "DECK",
                Provenance.ORIGINAL_DECK, held, " · ".join(detail), row.remaining_copies == 0,
                round(100 * row.remaining_copies / deck_count, 1) if deck_count and row.remaining_copies <= deck_count else None))
        groups = Counter()
        for mem in self._entities.values():
            entity = game.entities.get(mem.entity_id)
            if entity is None or not mem.card_id or self._is_unselected_discover_option(entity, mem):
                continue
            if not is_playable_card_entity(entity, self.card_db):
                continue
            if local:
                if mem.controller != pid:
                    continue
                if portal and mem.zone == "DECK":
                    continue
                if mem.zone not in {"HAND", "DECK"} and (
                    baseline_rows or mem.provenance in {Provenance.GENERATED, Provenance.COPIED}
                    or mem.zone not in {"PLAY", "GRAVEYARD", "SECRET", "REMOVEDFROMGAME"}
                ):
                    continue
                if mem.original_dbf is not None and not mem.transformed and baseline_rows:
                    continue
                identity = mem.card_id
            else:
                # Public observations only; never expose internally supplied identities.
                observed = [cid for eid, cid in self._observed_pairs if eid == mem.entity_id]
                if not observed:
                    continue
                identity = mem.first_public_card_id
                if mem.provenance in {Provenance.GENERATED, Provenance.COPIED} and mem.zone == "SETASIDE":
                    continue
            zone = mem.zone if mem.controller == pid else "STOLEN"
            if not local and mem.identity_hidden:
                zone = "SEEN"
            state = "BURNED" if mem.burned else "DISCARDED" if mem.discarded else "TRANSFORMED" if mem.transformed else zone
            if zone == "DECK" and entity.tags.get("GHOSTDATA_DECK_LOCATION"):
                state = entity.tags["GHOSTDATA_DECK_LOCATION"]
            assembled = self._assembled_card(entity) if (local or (
                not mem.identity_hidden and identity == entity.card_id
                and (mem.entity_id, entity.card_id) in self._observed_pairs)) else None
            groups[(identity, zone, mem.provenance, state, assembled)] += 1
        for (cid, zone, provenance, state, assembled), count in groups.items():
            card = self.card_db.get(cid)
            name, cost, text = assembled or (card.name if card else cid, card.cost if card else None, "")
            result.append(RailCardRow(cid, name, cost,
                count, zone, provenance, count if zone == "HAND" else 0, state,
                draw_chance=round(100 * count / deck_count, 1) if local and zone == "DECK" and deck_count else None,
                text=text))
        for predicted in self._predicted_pool_rows(game, pid):
            known = sum(r.count for r in result if r.card_id == predicted.card_id and r.zone == "DECK")
            if predicted.count > known and not portal:
                count = predicted.count - known
                result.append(replace(predicted, count=count,
                    draw_chance=round(100 * count / deck_count, 1) if local and deck_count else None))
        constrained = Counter()
        for entity in game.entities.values():
            if (entity.controller == pid and not entity.card_id
                    and entity.zone in {"DECK", "HAND"}
                    and entity.tags.get("GHOSTDATA_PUBLIC_LABEL")
                    and not (portal and entity.zone == "DECK")):
                constrained[(entity.tags["GHOSTDATA_PUBLIC_LABEL"], entity.tags.get("GHOSTDATA_PUBLIC_COST"), entity.zone)] += 1
        for (label, cost, zone), count in constrained.items():
            result.append(RailCardRow("", label, int(cost) if cost else None, count,
                zone, Provenance.GENERATED, count if zone == "HAND" else 0, "GENERATED"))
        for owner, identities, members in self._mixed_pools:
            if owner != pid or portal:
                continue
            remaining = Counter(identities)
            for eid in members:
                mem = self._entities.get(eid)
                if mem and (local or ((mem.publicly_revealed or mem.played) and not mem.identity_hidden)):
                    remaining[mem.first_public_card_id or mem.card_id] -= 1
            for cid, count in remaining.items():
                if count > 0:
                    card = self.card_db.get(cid)
                    result.append(RailCardRow(cid, card.name if card else cid, card.cost if card else None,
                        count, "DECK_OR_HAND", Provenance.GENERATED, state="REWARD POOL"))
        for owner, cid in self._unique_public_cards:
            if owner == pid and not any(r.card_id == cid and r.zone in {"DECK", "HAND"} for r in result):
                card = self.card_db.get(cid)
                result.append(RailCardRow(cid, card.name if card else cid, card.cost if card else None,
                    1, "DECK_OR_HAND", Provenance.UNKNOWN, state="KNOWN COPY"))
        if local:
            ordered = [m for m in self._entities.values() if m.controller == pid and m.zone == "DECK"
                       and game.entities[m.entity_id].tags.get("GHOSTDATA_DECK_LOCATION") == "TOP"]
            bottom = [m for m in self._entities.values() if m.controller == pid and m.zone == "DECK"
                      and game.entities[m.entity_id].tags.get("GHOSTDATA_DECK_LOCATION") == "BOTTOM"]
            if bottom:
                random_count = (deck_count or 0) - len(bottom)
                adjusted = []
                for row in result:
                    if row.zone == "DECK":
                        fixed = row.count if row.state == "BOTTOM" else sum(1 for m in bottom
                            if m.card_id == row.card_id and m.provenance == row.provenance
                            and row.provenance == Provenance.ORIGINAL_DECK)
                        chance = round(100 * max(0, row.count - fixed) / random_count, 1) if random_count else None
                        row = replace(row, draw_chance=chance)
                    adjusted.append(row)
                result = adjusted
            if ordered:
                next_card = max(ordered, key=lambda m: int(game.entities[m.entity_id].tags.get("GHOSTDATA_DECK_INDEX", "0")))
                winner = next((i for i, r in enumerate(result) if r.zone == "DECK"
                    and r.card_id == next_card.card_id and r.provenance == next_card.provenance
                    and (r.provenance == Provenance.ORIGINAL_DECK or r.state == "TOP")), None)
                result = [replace(r, draw_chance=(100.0 if i == winner else 0.0)
                    if winner is not None and r.zone == "DECK" else None) for i, r in enumerate(result)]
            # Baseline rows aggregate original copies; expose known placement
            # without adding another copy of the same card to the rail.
            for index, row in enumerate(result):
                if row.provenance == Provenance.ORIGINAL_DECK and row.zone == "DECK":
                    marks = [mark for mark, entries in (("TOP", ordered), ("BOTTOM", bottom))
                             if any(m.card_id == row.card_id for m in entries)]
                    if marks:
                        result[index] = replace(row, state=" · ".join(filter(None, [row.state, *marks])))
        if local and (portal or sum(r.count for r in result if r.zone == "DECK") != deck_count):
            result = [replace(r, draw_chance=None) for r in result]
        return sorted(result, key=lambda r: (r.cost if r.cost is not None else 99, r.name.casefold(), r.provenance, r.zone))

    def _predicted_pool_rows(self, game, pid):
        if game is None or pid is None:
            return []
        totals = Counter()
        for source, (owner, identities) in self._predicted_pools.items():
            if owner != pid:
                continue
            members = [m for m in self._entities.values() if m.creator == source or m.displayed_creator == source]
            if len(members) == len(identities) and (pid == game.local_player_pid or all(m.publicly_revealed and not m.identity_hidden for m in members)) and not any(m.zone == "DECK" and m.controller == pid for m in members):
                continue
            for cid in identities:
                consumed = sum(1 for m in self._entities.values() if m.first_card_id == cid
                    and (m.creator == source or m.displayed_creator == source)
                    and (m.zone != "DECK" or m.controller != pid)
                    and (pid == game.local_player_pid or (m.publicly_revealed and not m.identity_hidden)))
                totals[cid] += max(0, 1 - consumed)
        return [RailCardRow(cid, card.name if (card := self.card_db.get(cid)) else cid,
            card.cost if card else None, count, "DECK", Provenance.GENERATED, state="SHUFFLED")
            for cid, count in totals.items() if count]

    def _hand_slots(self, game, pid, known_deck=None):
        if game is None or pid is None:
            return []
        slots = []
        offered = {eid for rec in game.mulligans.values() for eid in rec.offered_entity_ids
            if (ent := game.entities.get(eid)) is not None and ent.controller == pid}
        for index, entity in enumerate(game.hand(pid), 1):
            mem = self._entities.get(entity.entity_id)
            known = mem is not None and not mem.identity_hidden and (entity.entity_id, entity.card_id) in self._observed_pairs
            card = self.card_db.get(entity.card_id) if known else None
            assembled = self._assembled_card(entity) if known else None
            origin = mem.hand_origin if mem else "UNKNOWN"
            if mem and mem.first_controller != mem.controller:
                origin = "STOLEN"
            elif mem and (mem.creator or mem.displayed_creator):
                origin = "GENERATED" if origin != "RETURNED" else origin
            elif mem and mem.hand_turn <= 1:
                origin = "MULLIGAN" if offered and entity.entity_id not in offered else "OPENING"
            from ..related_cards import related_cards
            related, label = related_cards(game, entity, self.card_db, known_deck) if known else ((), "")
            slots.append(HandSlot(entity.entity_id, entity.zone_position or index,
                mem.hand_turn if mem else 0, entity.card_id if known else "",
                assembled[0] if assembled else (card.name if card else entity.card_id) if known else entity.tags.get("GHOSTDATA_PUBLIC_LABEL", "Unknown card"),
                origin, text=assembled[2] if assembled else card.text if card else "", related_cards=related, related_label=label))
        return slots

    def _sideboard_rows(self, game):
        if not self._selected:
            return []
        rows = []
        for owner, dbf, count in self._selected.sideboards:
            card = self.card_db.get_by_dbf(dbf)
            source = self.card_db.get_by_dbf(owner)
            # Sideboards are a separate starting pool. Acquisitions can move the
            # setaside entity itself or create a hand copy linked to that entity.
            consumed = set()
            held = 0
            if game and source and card:
                owners = {o for o, c, _ in self._selected.sideboards if c == dbf}
                for m in self._entities.values():
                    if not m.ever_hand or m.first_card_id != card.card_id or m.first_controller != game.local_player_pid:
                        continue
                    origin = self._entities.get(m.copied_from_entity_id or 0)
                    copied_from_pool = origin is not None and origin.zone == "SETASIDE" and origin.first_zone in {"DECK", "SETASIDE"}
                    direct_from_pool = m.first_zone == "SETASIDE"
                    if not copied_from_pool and not direct_from_pool:
                        continue
                    creator_id = (origin.creator or origin.displayed_creator) if copied_from_pool else (m.creator or m.displayed_creator)
                    creator = game.entities.get(creator_id or 0)
                    if creator and creator.card_id:
                        if creator.card_id != source.card_id:
                            continue
                    elif not copied_from_pool or len(owners) != 1 or origin.first_zone != "DECK" or origin.provenance not in {Provenance.GENERATED, Provenance.COPIED}:
                        continue
                    consumed.add(origin.entity_id if copied_from_pool else m.entity_id)
                    if m.controller == game.local_player_pid and m.zone == "HAND":
                        held += 1
            used = len(consumed)
            rows.append(RailCardRow(card.card_id if card else str(dbf), card.name if card else f"DBF {dbf}",
                card.cost if card else None, max(0, count-used), "SIDEBOARD", Provenance.ORIGINAL_DECK,
                in_hand=held, state=source.name if source else str(owner), exhausted=used >= count,
                owner_card_id=source.card_id if source else str(owner)))
        return rows

    @staticmethod
    def _has_portal(game, pid):
        return bool(game and pid is not None and any(e.controller == pid and
            e.tags.get("DEMON_PORTAL_DECK", "0") != "0" for e in game.entities.values()))

    def _original_pool_left(self, local_pid):
        # A complete starting entity census proves wholesale replacement/swap
        # even when those original identities were never revealed. Returning
        # the same entities restores the baseline without a guessed new deck.
        pool = [m for m in self._entities.values() if m.first_controller == local_pid
            and m.first_zone == "DECK" and m.first_turn <= 1
            and not (m.creator or m.displayed_creator or m.copied_from_entity_id)]
        return bool(self._baseline and len(pool) == sum(self._baseline.values())
            and not any(m.controller == local_pid and m.zone == "DECK" for m in pool))

    @staticmethod
    def _fatigue(game, pid):
        if game is None or pid is None:
            return 0
        player = game.players.get(pid)
        values = [player.tags.get("FATIGUE", "0")] if player else []
        values.extend(e.tags.get("FATIGUE", "0") for e in game.entities.values() if e.controller == pid)
        return max((int(v) for v in values if str(v).isdigit()), default=0)

    def _refresh_state(self, game: Optional[GameState]) -> bool:
        candidate = self._build_state(game)
        comparable = replace(candidate, revision=0)
        previous = replace(self._last_state, revision=0) if self._last_state is not None else None
        if previous == comparable:
            return False
        self._revision += 1
        self._last_state = replace(candidate, revision=self._revision)
        return True

    def _build_state(self, game: Optional[GameState]) -> DeckTrackerState:
        selected = self._selected
        baseline_total = sum(self._baseline.values())
        local_pid = game.local_player_pid if game else None
        opponent_pid = game.opponent_pid if game else None
        portal = self._has_portal(game, local_pid)
        original_pool_left = portal or self._original_pool_left(local_pid)

        assigned_by_dbf: dict[int, list[_TrackedEntity]] = defaultdict(list)
        for mem in self._entities.values():
            if mem.original_dbf is not None:
                assigned_by_dbf[mem.original_dbf].append(mem)

        rows: list[PlayerDeckRow] = []
        original_remaining = 0
        for dbf, initial in sorted(self._baseline.items(), key=self._player_sort_key):
            assigned = assigned_by_dbf.get(dbf, [])
            out_of_original_deck = 0
            seen = 0
            drawn = 0
            for mem in assigned:
                seen += 1
                if mem.ever_hand:
                    drawn += 1
                present_as_original = (
                    local_pid is not None
                    and mem.controller == local_pid
                    and mem.zone == "DECK"
                    and not mem.transformed
                    and self.card_db.dbf_id_for_card_id(mem.card_id) == dbf
                )
                if not present_as_original:
                    out_of_original_deck += 1
            remaining = 0 if original_pool_left else max(0, initial - out_of_original_deck)
            original_remaining += remaining
            card_id, name, cost = self._baseline_meta.get(dbf, (str(dbf), f"DBF {dbf}", None))
            rows.append(PlayerDeckRow(
                dbf_id=dbf,
                card_id=card_id,
                name=name,
                cost=cost,
                initial_copies=initial,
                remaining_copies=remaining,
                seen_copies=min(initial, seen),
                drawn_copies=min(initial, drawn),
            ))

        player_hand_count = len(game.hand(local_pid)) if game and local_pid is not None else None
        player_deck_count = game.deck_count(local_pid) if game and local_pid is not None else None
        known_non_original_in_deck = 0
        if game and local_pid is not None:
            for mem in self._entities.values():
                if (
                    mem.controller == local_pid
                    and mem.zone == "DECK"
                    and (mem.card_id or game.entities[mem.entity_id].tags.get("GHOSTDATA_PUBLIC_LABEL"))
                    and (mem.original_dbf is None or mem.transformed)
                ):
                    known_non_original_in_deck += 1

        accounting_delta: int | None = None
        for predicted in self._predicted_pool_rows(game, local_pid):
            known = sum(1 for m in self._entities.values() if m.controller == local_pid and m.zone == "DECK" and m.card_id == predicted.card_id)
            known_non_original_in_deck += max(0, predicted.count - known)
        accounting_status = "UNAVAILABLE"
        if player_deck_count is not None and selected is not None:
            accounting_delta = player_deck_count - (original_remaining + known_non_original_in_deck)
            accounting_status = "EXACT" if accounting_delta == 0 else "PARTIAL"
        if portal:
            accounting_status = "PORTAL"
            accounting_delta = None

        opponent_rows = self._opponent_rows(game, opponent_pid)
        opponent_hand_count = len(game.hand(opponent_pid)) if game and opponent_pid is not None else None
        opponent_deck_count = game.deck_count(opponent_pid) if game and opponent_pid is not None else None
        opponent_class = ""
        if game and opponent_pid is not None:
            opponent = game.players.get(opponent_pid)
            opponent_class = str(opponent.player_class or "").upper() if opponent else ""

        unknown_events = sum(
            1 for mem in self._entities.values()
            if mem.card_id and mem.provenance == Provenance.UNKNOWN and (
                mem.entered_deck_from_elsewhere or (mem.first_zone and mem.first_zone != "DECK")
            )
        )
        warnings = list(self._warnings)
        if accounting_status == "PARTIAL" and accounting_delta is not None:
            if accounting_delta < 0:
                warnings.append(
                    f"player deck accounting is partial by {accounting_delta:+d}; "
                    f"{-accounting_delta} local deck exit(s) do not yet have a resolved original-card identity"
                )
            elif accounting_delta > 0:
                warnings.append(
                    f"player deck accounting is partial by {accounting_delta:+d}; "
                    f"{accounting_delta} card(s) currently in deck are not yet explained by original/non-original provenance"
                )

        if selected is None:
            source_status = "WAITING_FOR_EXACT_DECK"
        elif game is None or game.game_number <= 0:
            source_status = "DECK_READY"
        elif game.complete:
            source_status = "GAME_COMPLETE"
        elif game.active:
            source_status = "TRACKING"
        else:
            source_status = "WAITING_FOR_GAME"

        player_display = self._with_card_text(self._display_rows(game, local_pid, rows))
        known_deck = tuple(row.card_id for row in player_display if row.zone == "DECK" and row.card_id
                           for _ in range(max(0,row.count)))
        return DeckTrackerState(
            revision=self._revision,
            game_number=int(game.game_number if game else self._game_number),
            active=bool(game and game.active and is_standard_constructed(game.format_type, game.game_type)),
            complete=bool(game.complete if game else False),
            source_status=source_status,
            player_deck_hash=selected.deck_hash if selected else "",
            player_deck_name=selected.deck_name if selected else "",
            player_class=str(selected.class_id or "").upper() if selected else self._starting_class(game),
            starting_cards=baseline_total,
            original_cards_remaining=original_remaining,
            player_hand_count=player_hand_count,
            player_deck_count=player_deck_count,
            player_known_non_original_in_deck=known_non_original_in_deck,
            player_accounting_delta=accounting_delta,
            player_accounting_status=accounting_status,
            player_rows=tuple(rows),
            player_extra_deck_rows=tuple(self._player_extra_deck_rows(game, local_pid)),
            opponent_class=opponent_class,
            opponent_hand_count=opponent_hand_count,
            opponent_deck_count=opponent_deck_count,
            opponent_rows=tuple(opponent_rows),
            player_hero_zone_effects=self._with_card_text(self._hero_zone_effect_rows(game, local_pid, "PLAYER")),
            opponent_hero_zone_effects=self._with_card_text(self._hero_zone_effect_rows(game, opponent_pid, "OPPONENT")),
            player_display_rows=player_display,
            opponent_display_rows=self._with_card_text(self._display_rows(game, opponent_pid)),
            player_sideboard_rows=self._with_card_text(self._sideboard_rows(game)),
            player_overdraw_rows=overdraw_rows(game, local_pid, self.card_db),
            opponent_overdraw_rows=overdraw_rows(game, opponent_pid, self.card_db),
            player_hand=self._with_card_text(self._hand_slots(game, local_pid, known_deck)),
            opponent_hand=self._with_card_text(self._hand_slots(game, opponent_pid)),
            player_fatigue=self._fatigue(game, local_pid),
            opponent_fatigue=self._fatigue(game, opponent_pid),
            player_portal=portal,
            opponent_portal=self._has_portal(game, opponent_pid),
            unknown_provenance_events=unknown_events,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _with_card_text(self, rows):
        return tuple(replace(row, text=row.text or (card.text if (card := self.card_db.get(row.card_id)) else "")) for row in rows)

    def _player_sort_key(self, item: tuple[int, int]) -> tuple[int, str, int]:
        dbf = item[0]
        card_id, name, cost = self._baseline_meta.get(dbf, (str(dbf), f"DBF {dbf}", None))
        return (cost if cost is not None else 99, name.lower(), dbf)

    def _opponent_rows(self, game: Optional[GameState], opponent_pid: Optional[int]) -> list[OpponentObservedRow]:
        if game is None or opponent_pid is None:
            return []
        grouped: dict[str, dict[str, object]] = {}
        for eid, card_id in sorted(self._observed_pairs):
            entity = game.entities.get(eid)
            if entity is None:
                continue
            mem = self._entities.get(eid)
            if mem is not None and self._is_unselected_discover_option(entity, mem):
                continue
            # Keep observations even when a stolen/transformed entity changed
            # controller later; the card was still legitimately observed.
            row = grouped.setdefault(card_id, {
                "entity_ids": set(), "known_in_hand": set(), "zones": [], "provenance": set(),
            })
            row["entity_ids"].add(eid)  # type: ignore[index]
            if entity.controller == opponent_pid and entity.zone == "HAND" and entity.card_id == card_id:
                row["known_in_hand"].add(eid)  # type: ignore[index]
            if entity.card_id == card_id and entity.zone:
                row["zones"].append(entity.zone)  # type: ignore[index]
            row["provenance"].add(self._opponent_observation_provenance.get((eid, card_id), Provenance.UNKNOWN))  # type: ignore[index]

        out: list[OpponentObservedRow] = []
        for card_id, data in grouped.items():
            card = self.card_db.get(card_id)
            dbf = self.card_db.dbf_id_for_card_id(card_id)
            provenances = set(data["provenance"])  # type: ignore[arg-type]
            provenance = next(iter(provenances)) if len(provenances) == 1 else "MIXED"
            zones = list(data["zones"])  # type: ignore[arg-type]
            sample_entity = None
            for eid in data["entity_ids"]:  # type: ignore[assignment]
                candidate = game.entities.get(eid)
                if candidate is not None and candidate.card_id == card_id:
                    sample_entity = candidate
                    break
            card_type = str(card.card_type or "").upper() if card else (
                resolved_card_type(sample_entity, self.card_db) if sample_entity is not None else ""
            )
            effect_kind = hero_zone_effect_kind(sample_entity, self.card_db) if sample_entity is not None else ""
            out.append(OpponentObservedRow(
                dbf_id=dbf,
                card_id=card_id,
                name=str(card.name if card else card_id),
                cost=card.cost if card else None,
                observed_copies=len(data["entity_ids"]),  # type: ignore[arg-type]
                known_in_hand=len(data["known_in_hand"]),  # type: ignore[arg-type]
                last_zone=zones[-1] if zones else "",
                provenance=provenance,
                card_type=card_type,
                spell_school=str(card.spell_school or "").upper() if card else "",
                hero_zone_kind=effect_kind,
            ))
        return sorted(out, key=lambda x: (x.cost if x.cost is not None else 99, x.name.lower(), x.card_id))


class _NullCardDatabase:
    ready = False

    def get(self, _card_id: str):
        return None

    def get_by_dbf(self, _dbf: int):
        return None

    def dbf_id_for_card_id(self, card_id: str):
        text = str(card_id or "").strip()
        return int(text) if text.isdigit() and int(text) > 0 else None


def _event_entity_id(event: SemanticEvent) -> int | None:
    raw = event.data.get("entity_id")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None
