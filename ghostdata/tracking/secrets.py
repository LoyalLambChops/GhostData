from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional

from .card_db import CardDatabase, CardDefinition
from .card_taxonomy import hero_zone_effect_kind
from .models import EntityState, GameState, SecretCandidate, SecretState
from .standard_secrets import StandardSecretCatalog
from .secret_rules import RULES as HISTORICAL_RULES, matches as historical_matches


_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    text = _TAG_RE.sub(" ", text or "")
    text = text.replace("$", "").replace("#", "")
    return _SPACE_RE.sub(" ", text).strip().lower()


@dataclass(frozen=True)
class SecretObservation:
    event_type: str
    actor_pid: Optional[int] = None
    target_pid: Optional[int] = None
    actor_entity_id: Optional[int] = None
    target_entity_id: Optional[int] = None
    card_type: Optional[str] = None
    is_hero_target: bool = False
    is_minion_target: bool = False
    witness_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class SecretTriggerRule:
    """A deliberately conservative public-trigger rule.

    These rules do not try to simulate the whole card. They answer one narrow
    question: given a completed public player action, would this Secret have
    been forced to trigger if it were active and otherwise eligible?
    """

    key: str

    def matches(self, observation: SecretObservation, secret_controller: int, state: GameState | None = None) -> bool:
        if self.key.startswith("historical:"):
            return historical_matches(self.key.split(":", 1)[1], observation, secret_controller, state)
        if self.key == "owner_turn_with_enemy_minion":
            return bool(state and observation.event_type == "TURN_START" and observation.actor_pid == secret_controller
                and any(e.controller != secret_controller for e in state.entities.values() if e.zone == "PLAY" and e.card_type == "MINION"))
        if observation.actor_pid is None or observation.actor_pid == secret_controller:
            return False
        if observation.event_type == "ATTACK" and observation.target_pid == observation.actor_pid:
            return False
        if self.key == "recent_friendly_minion_died":
            entity = state.entities.get(observation.target_entity_id) if state else None
            return bool(entity and observation.event_type == "MINION_DIED" and observation.target_pid == secret_controller
                and entity.last_played_turn is not None and entity.last_played_turn == state.global_turn - 1)
        if self.key == "third_card_with_board_space":
            if not state or observation.event_type != "PLAY":
                return False
            last_turn = max((e.sequence for e in state.events if e.event_type == "GLOBAL_TURN"), default=0)
            played = sum(1 for e in state.events if e.sequence > last_turn and e.event_type == "PLAY" and e.data.get("player") == observation.actor_pid)
            return played >= 3 and len(state.board(secret_controller)) < 7
        if self.key == "spell_with_enemy_minion":
            return bool(state and observation.event_type == "PLAY" and observation.card_type == "SPELL"
                and any(e.card_type == "MINION" for e in state.board(observation.actor_pid)))
        if self.key == "opponent_casts_spell":
            return observation.event_type == "PLAY" and observation.card_type == "SPELL"
        if self.key == "opponent_plays_minion":
            return observation.event_type == "PLAY" and observation.card_type == "MINION"
        if self.key == "opponent_plays_card":
            return observation.event_type == "PLAY"
        if self.key == "hero_attacked":
            return (
                observation.event_type == "ATTACK"
                and observation.target_pid == secret_controller
                and observation.is_hero_target
            )
        if self.key == "friendly_minion_attacked":
            return (
                observation.event_type == "ATTACK"
                and observation.target_pid == secret_controller
                and observation.is_minion_target
            )
        if self.key == "enemy_attacks":
            return observation.event_type == "ATTACK"
        if self.key == "enemy_minion_attacks":
            return observation.event_type == "ATTACK" and observation.card_type == "MINION"
        return False


def infer_safe_trigger_rule(card: CardDefinition) -> Optional[SecretTriggerRule]:
    """Infer only trigger templates that are safe to test from public actions.

    Card-definition data text is used so GhostData does not need static CardIDs.
    Unknown text stays unsupported rather than being guessed. This makes the
    engine extensible across Standard/Wild and future patches while failing
    closed on unfamiliar wording.
    """

    text = _normalize_text(card.text)
    special = {
        "flames of infinity": "owner_turn_with_enemy_minion",
        "untimely death": "recent_friendly_minion_died",
        "rat trap": "third_card_with_board_space",
        "pressure plate": "spell_with_enemy_minion",
    }
    if card.name.casefold() in special:
        return SecretTriggerRule(special[card.name.casefold()])
    name = card.name.casefold()
    if name in HISTORICAL_RULES and name not in {"counterspell", "explosive runes", "ice barrier",
            "mystic misdirection", "oasis ally", "explosive trap", "freezing trap", "ice trap", "mirror entity"}:
        return SecretTriggerRule("historical:" + name)
    # Historical generation pools contain conditional Secrets whose first
    # clause resembles these templates. Do not erase those extra conditions.
    if card.name.casefold() not in {"counterspell", "explosive runes", "ice barrier",
        "mystic misdirection", "oasis ally", "explosive trap", "freezing trap",
        "ice trap", "mirror entity"}:
        return None
    if not text:
        return None

    # Ordering matters: specific patterns before broader patterns.
    if re.search(r"(?:when|after) your opponent (?:casts|plays) a spell\b", text):
        return SecretTriggerRule("opponent_casts_spell")
    if re.search(r"(?:when|after) your opponent plays a minion\b", text):
        return SecretTriggerRule("opponent_plays_minion")
    if re.search(r"(?:when|after) your opponent plays a card\b", text):
        return SecretTriggerRule("opponent_plays_card")
    if re.search(r"(?:when|after) your hero is attacked\b", text):
        return SecretTriggerRule("hero_attacked")
    if re.search(r"(?:when|after) a friendly minion is attacked\b", text):
        return SecretTriggerRule("friendly_minion_attacked")
    if re.search(r"(?:when|after) an enemy minion attacks\b", text):
        return SecretTriggerRule("enemy_minion_attacks")
    if re.search(r"(?:when|after) an enemy attacks\b", text):
        return SecretTriggerRule("enemy_attacks")
    return None


class SecretTracker:
    """Hidden-Secret candidate tracker with conservative negative inference.

    Capabilities:
      * candidate seeding from the current Hearthstone card-definition build;
      * provenance (played/unknown vs generated);
      * exact reveal/trigger resolution;
      * duplicate-active-Secret reconciliation;
      * delayed candidate elimination after trigger-capable public actions;
      * dynamic trigger-template discovery from current card text.

    Candidate seeding first uses the hidden Secret entity's deterministic class
    tag and a patch-scoped Standard legality catalog. If that current-Standard
    pool cannot be fully reconciled, GhostData withholds candidate names rather
    than widening to historical/Wild noise. The class boundary is never widened.
    Unsupported Secret text is never eliminated.

    Exact hidden Secret identity is a separate engine-truth channel. If Power.log
    or client-state enrichment supplies the exact identity before public reveal,
    Internal state may retain it while player-facing candidates and tracker rails
    remain disclosure-safe until Hearthstone reveals the Secret.

    The trust boundary applies to every Secret class. Multiple active Secrets
    are modeled conservatively. If an action ends
    with *none* of the active slots revealing or leaving play, trigger candidates
    that were forced to fire can be eliminated from every slot.  If any slot
    triggers during that action, disruptive or unfamiliar triggers suppress
    negative elimination. An armor-only Ice Barrier trigger preserves the
    remaining attack deductions because it does not redirect or stop the attack.
    """

    def __init__(self, card_db: CardDatabase, *, standard_catalog: StandardSecretCatalog | None = None):
        self.card_db = card_db
        self.standard_catalog = standard_catalog
        # controller -> pending action test.  Each row captures the exact active
        # unresolved slot set at action start plus candidates forced to trigger.
        self._pending_tests: Dict[int, dict] = {}
        self._hidden_cache_witnesses = {}

    def reset(self) -> None:
        self._pending_tests.clear()
        self._hidden_cache_witnesses.clear()

    def refresh_metadata(self, state):
        for secret in state.secrets.values():
            entity = state.entities.get(secret.entity_id)
            if entity is None or entity.zone != "SECRET" or secret.resolved:
                continue
            ruled_out = {name.casefold() for name in secret.eliminated_names.values()}
            candidates, scope = self._seed_candidates(state, entity.controller, secret.secret_class, entity)
            secret.candidates = candidates
            secret.candidate_scope = scope
            secret.eliminations.clear()
            secret.eliminated_names.clear()
            for cid, candidate in list(candidates.items()):
                if candidate.name.casefold() in ruled_out:
                    secret.eliminate(cid, "public deduction retained across metadata refresh")
        self.reconcile_duplicate_active_secrets(state)

    @staticmethod
    def _secret_class(state: GameState, entity: EntityState, controller: int) -> str:
        # The hidden Secret entity's CLASS tag is deterministic and outranks hero
        # class inference. Hero class is only a fallback for older/incomplete log
        # slices that have not emitted the Secret entity CLASS tag yet.
        explicit = str(entity.card_class or entity.tags.get("CLASS") or "").upper().strip()
        if explicit and explicit not in {"INVALID", "NEUTRAL"}:
            return explicit
        player = state.players.get(controller)
        return str(player.player_class or "").upper().strip() if player else ""

    def _seed_candidates(self, state: GameState, controller: int, secret_class: str, entity: EntityState | None = None) -> tuple[Dict[str, SecretCandidate], str]:
        card_class = str(secret_class or "").upper().strip()
        if not card_class:
            return {}, "secret_class_unavailable"
        if not self.card_db.ready:
            return {}, f"{card_class.lower()}_secret_candidates_withheld_no_card_database"

        if self.card_db.local_source:
            if state.build_number and not self.card_db.matches_log_build(state.build_number):
                return {}, f"{card_class.lower()}_secret_candidates_withheld_build_mismatch"
            if not self.card_db.legality_current:
                return {}, f"{card_class.lower()}_secret_candidates_withheld_rotation_refresh"
        generated = self._public_generator_pool(state, entity, card_class) if entity else None
        cards = tuple()
        if generated is not None:
            cards, scope = generated
        elif self.card_db.local_source:
            cards = tuple(c for c in self.card_db.secret_cards_for_class(card_class) if c.standard is True)
            scope = f"local_standard_build_{self.card_db.build_number}"
        elif self.standard_catalog is not None and self.standard_catalog.names_for_class(card_class):
            cards = self.standard_catalog.resolve_cards(self.card_db, card_class)
            if cards:
                scope = f"verified_standard_patch_{self.standard_catalog.patch}"
            else:
                # Fail closed on names, not on the already-known Secret class. A
                # stale/incomplete cache must never expand a known-class Secret
                # into historical/Wild noise or another class's candidates.
                return {}, f"{card_class.lower()}_secret_candidates_withheld_catalog_mismatch"
        else:
            return {}, f"{card_class.lower()}_secret_candidates_withheld_no_standard_catalog"

        out: Dict[str, SecretCandidate] = {}
        for card in cards:
            rule = infer_safe_trigger_rule(card)
            out[card.card_id] = SecretCandidate(
                card_id=card.card_id,
                name=card.name,
                card_class=card.card_class,
                rule_key=rule.key if rule else "",
            )
        return out, scope

    def _public_generator_pool(self, state, entity, card_class):
        source = state.entities.get(entity.creator or entity.displayed_creator)
        if source is None or source.zone not in {"PLAY", "GRAVEYARD", "SECRET"}:
            return None
        card = self.card_db.get(source.card_id)
        if card and card.name == "The Origin Stone":
            # Trace the public Discover's generator, never the hidden option's
            # identity. Every option in that Discover shares the same pool.
            options = [e for e in state.entities.values() if e.entity_id < entity.entity_id
                and e.controller == entity.controller and e.tags.get("WAS_DISCOVER_OPTION") == "1" and e.creator]
            option = max(options, key=lambda e: e.entity_id, default=None)
            source = state.entities.get(option.creator) if option else None
            card = self.card_db.get(source.card_id) if source else None
        if not card or card.name not in {"Timelooper Toki", "Alter Time", "Disco at the End of Time"}:
            return None
        if self.standard_catalog is None and not self.card_db.local_source:
            return (), "generated_past_pool_unavailable"
        current = ({c.name.casefold() for c in self.card_db.secret_cards_for_class(card_class) if c.standard is True}
                   if self.card_db.local_source else {n.casefold() for n in self.standard_catalog.names_for_class(card_class)})
        by_name = {}
        for candidate in self.card_db.secret_cards_for_class(card_class):
            if candidate.name.casefold() in current or candidate.card_set in {"CORE", "PLACEHOLDER"}:
                continue
            if card.name == "Alter Time" and candidate.spell_school != "ARCANE":
                continue
            by_name.setdefault(candidate.name.casefold(), candidate)
        return tuple(by_name.values()), f"generated_past_pool:{card.card_id}"

    def _refresh_pool(self, state, entity, secret):
        candidates, scope = self._seed_candidates(state, entity.controller, secret.secret_class, entity)
        if scope != secret.candidate_scope:
            secret.candidates = candidates
            secret.candidate_scope = scope
            secret.eliminations.clear()
            secret.eliminated_names.clear()

    def on_zone_change(self, state: GameState, entity: EntityState, old_zone: Optional[str], new_zone: Optional[str]) -> None:
        if new_zone == "SECRET":
            effect_kind = hero_zone_effect_kind(entity, self.card_db)
            if effect_kind and effect_kind != "SECRET":
                # QUEST/QUESTLINE/SIDEQUEST/OBJECTIVE/AURA/SIGIL share the
                # internal hero-zone/SECRET zone but are not hidden Secrets.
                state.secrets.pop(entity.entity_id, None)
                self._pending_tests.pop(entity.entity_id, None)
                return
            if entity.controller is None:
                return
            secret = state.secrets.get(entity.entity_id)
            if secret is not None and old_zone != "SECRET" and (secret.resolved or old_zone in {"HAND", "DECK", "GRAVEYARD"}):
                # The same entity can return and be played again. Its earlier
                # activation's exclusions and public reveal no longer apply.
                state.secrets.pop(entity.entity_id)
                self._hidden_cache_witnesses.pop(entity.entity_id, None)
                secret = None
            if secret is None:
                secret_class = self._secret_class(state, entity, entity.controller)
                candidates, candidate_scope = self._seed_candidates(state, entity.controller, secret_class, entity)
                secret = SecretState(
                    entity_id=entity.entity_id,
                    controller=entity.controller,
                    created_turn=state.global_turn,
                    provenance="generated" if entity.creator or entity.displayed_creator else "played_or_unknown",
                    created_by=entity.creator or entity.displayed_creator,
                    secret_class=secret_class,
                    candidates=candidates,
                    candidate_scope=candidate_scope,
                )
                state.secrets[entity.entity_id] = secret
            else:
                secret.controller = entity.controller
                explicit_class = self._secret_class(state, entity, entity.controller)
                if explicit_class:
                    secret.secret_class = explicit_class
            if entity.card_id:
                self.learn_internal_identity(state, entity, source="entity_hidden_identity")
        elif old_zone == "SECRET" and new_zone != "SECRET":
            secret = state.secrets.get(entity.entity_id)
            if secret is not None and secret.engine_known:
                self.reveal_public_identity(state, entity)
            if secret is not None and secret.resolved:
                # Other already-active slots could not have been the Secret
                # that just left. Future slots are not included in this pass.
                name = (self.card_db.get(secret.resolved_card_id).name if self.card_db.get(secret.resolved_card_id)
                    else secret.resolved_name).casefold()
                for other in self.active_for_player(state, secret.controller).values():
                    for cid, candidate in list(other.candidates.items()):
                        if candidate.name.casefold() == name and not self._locked(state, other):
                            other.eliminate(cid, "another simultaneously active Secret revealed this identity")
            self._pending_tests.pop(entity.entity_id, None)

    def on_identity_change(self, state: GameState, entity: EntityState) -> None:
        if not entity.card_id:
            return
        definition = self.card_db.get(entity.card_id)
        if definition and definition.card_type == "MINION":
            for sid, witnesses in self._hidden_cache_witnesses.items():
                secret = state.secrets.get(sid)
                if secret and entity.entity_id in witnesses and not self._locked(state, secret):
                    for cid, candidate in list(secret.candidates.items()):
                        if candidate.name.casefold() == "hidden cache":
                            secret.eliminate(cid, "a minion in hand during an earlier eligible play was revealed")
        effect_kind = hero_zone_effect_kind(entity, self.card_db)
        if effect_kind and effect_kind != "SECRET":
            state.secrets.pop(entity.entity_id, None)
            self._pending_tests.pop(entity.entity_id, None)
            return
        if entity.entity_id in state.secrets:
            if str(entity.zone or "").upper() == "SECRET":
                # Hidden engine truth is not the same thing as public reveal.
                self.learn_internal_identity(state, entity, source="entity_hidden_identity")
            else:
                self.reveal_public_identity(state, entity)

    def on_provenance_change(self, state: GameState, entity: EntityState) -> None:
        """Upgrade Secret source provenance when creator tags arrive late."""
        secret = state.secrets.get(entity.entity_id)
        if secret is None:
            return
        created_by = entity.creator or entity.displayed_creator
        if created_by:
            secret.provenance = "generated"
            secret.created_by = created_by
            self._refresh_pool(state, entity, secret)

    def on_class_change(self, state: GameState, entity: EntityState) -> None:
        """Bind a hidden Secret to its deterministic entity CLASS tag.

        ZONE=SECRET may arrive before CLASS in the same entity definition. The
        controller's hero class is therefore only a provisional fallback. Once
        the Secret entity emits CLASS, reseed player-safe candidates against that
        exact class boundary. This also handles cross-class generated Secrets.
        """
        secret = state.secrets.get(entity.entity_id)
        if secret is None or entity.controller is None:
            return
        card_class = self._secret_class(state, entity, entity.controller)
        if not card_class or card_class == secret.secret_class:
            return
        secret.secret_class = card_class
        candidates, scope = self._seed_candidates(state, entity.controller, card_class, entity)
        secret.candidates = candidates
        secret.candidate_scope = scope
        secret.eliminations.clear()
        secret.eliminated_names.clear()
        self.reconcile_duplicate_active_secrets(state)

    def learn_internal_identity(
        self,
        state: GameState,
        entity: EntityState,
        *,
        source: str = "engine",
        card_id: str | None = None,
        name: str | None = None,
    ) -> None:
        """Record deterministic hidden Secret truth without disclosing it.

        This method is also the enrichment boundary for sensor/client-state data:
        callers may provide card_id/name even when the public EntityState remains
        intentionally anonymous. Candidate sets are *not* collapsed to the exact
        hidden identity because they model what the player can safely infer.
        """
        secret = state.secrets.get(entity.entity_id)
        if not secret:
            return
        cid = str(card_id or entity.card_id or "").strip()
        nm = str(name or entity.name or "").strip()
        if cid:
            secret.engine_card_id = cid
            if self.card_db.ready:
                card = self.card_db.get(cid)
                if card:
                    nm = nm or card.name
                    if card.card_class:
                        secret.secret_class = str(card.card_class).upper()
        if nm:
            secret.engine_name = nm
        if cid or nm:
            secret.engine_identity_source = str(source or "engine")

    def reveal_public_identity(self, state: GameState, entity: EntityState) -> None:
        """Promote engine truth to player-visible truth after Hearthstone reveals it."""
        secret = state.secrets.get(entity.entity_id)
        if not secret:
            return
        self.learn_internal_identity(state, entity, source=secret.engine_identity_source or "public_reveal")
        cid = str(entity.card_id or secret.engine_card_id or "").strip()
        nm = str(entity.name or secret.engine_name or cid).strip()
        if not cid and not nm:
            return
        secret.publicly_revealed = True
        secret.resolved_card_id = cid
        secret.resolved_name = nm
        self._pending_tests.pop(entity.entity_id, None)
        if cid and cid in secret.candidates:
            secret.candidates = {cid: secret.candidates[cid]}
        elif cid:
            # Public reveal is authoritative even when the candidate catalog was
            # unavailable or stale. It is now safe to clear player possibilities.
            secret.candidates.clear()
        self.reconcile_duplicate_active_secrets(state)

    # Backward-compatible name used by older acceptance helpers. Public callers
    # should prefer reveal_public_identity when disclosure is intended.
    def resolve(self, state: GameState, entity: EntityState) -> None:
        self.reveal_public_identity(state, entity)

    def reconcile_duplicate_active_secrets(self, state: GameState) -> None:
        active = []
        for sid, secret in state.secrets.items():
            ent = state.entities.get(sid)
            if ent and ent.zone == "SECRET" and not ent.is_quest:
                active.append(secret)

        # Exact reveals are authoritative.
        resolved_ids = {(s.controller, s.resolved_card_id) for s in active if s.resolved_card_id}
        for secret in active:
            if secret.resolved or self._locked(state, secret):
                continue
            for controller, card_id in resolved_ids:
                if controller == secret.controller:
                    secret.eliminate(card_id, "another active Secret is already confirmed as this card")

        # Hearthstone does not permit two copies of the same Secret to be active
        # simultaneously.  A singleton candidate therefore safely excludes that
        # identity from every other unresolved slot.  Iterate to a fixed point as
        # one exclusion can create another singleton.
        changed = True
        while changed:
            changed = False
            unresolved = [s for s in active if not s.resolved]
            singletons = {
                (s.controller, next(iter(s.candidates)))
                for s in unresolved
                if len(s.candidates) == 1
            }
            for secret in unresolved:
                if self._locked(state, secret):
                    continue
                own = next(iter(secret.candidates)) if len(secret.candidates) == 1 else None
                for controller, card_id in singletons:
                    if controller != secret.controller or card_id == own:
                        continue
                    if card_id in secret.candidates:
                        secret.eliminate(card_id, "another active Secret is narrowed to this identity")
                        changed = True

    @staticmethod
    def _locked(state, secret):
        entity = state.entities.get(secret.entity_id)
        return bool(entity and entity.tags.get("SECRET_LOCKED", "0") != "0")

    def _active_unresolved_by_controller(self, state: GameState) -> Dict[int, list[SecretState]]:
        grouped: Dict[int, list[SecretState]] = {}
        for sid, secret in state.secrets.items():
            ent = state.entities.get(sid)
            if not ent or ent.zone != "SECRET" or ent.is_quest or secret.resolved:
                continue
            grouped.setdefault(secret.controller, []).append(secret)
        return grouped

    def observe_public_event(self, state: GameState, observation: SecretObservation) -> None:
        """Record candidates that would be forced to trigger on this action.

        Snapshot all unresolved Secret slots controlled by the opponent.
        Elimination remains delayed until the action boundary so reveal/trigger
        order is known before any negative inference is applied.
        """
        self.reconcile_duplicate_active_secrets(state)
        grouped = self._active_unresolved_by_controller(state)
        for controller, secrets in grouped.items():
            active_ids = tuple(sorted(s.entity_id for s in secrets))
            expected_by_secret: Dict[int, dict] = {}
            for secret in secrets:
                if self._locked(state, secret):
                    continue
                expected: dict = {}
                if observation.event_type == "PLAY" and observation.card_type == "MINION" and observation.actor_pid != controller:
                    self._hidden_cache_witnesses.setdefault(secret.entity_id, set()).update(e.entity_id for e in state.hand(controller))
                for card_id, candidate in secret.candidates.items():
                    if not candidate.rule_key:
                        continue
                    rule = SecretTriggerRule(candidate.rule_key)
                    actor = state.entities.get(observation.actor_entity_id)
                    if candidate.name.casefold() in {"oasis ally", "mirror entity"} and len(state.board(controller)) >= 7:
                        continue
                    if candidate.name.casefold() == "oasis ally" and state.current_player_pid != observation.actor_pid:
                        continue
                    if candidate.name.casefold() == "explosive runes" and actor and actor.tags.get("DORMANT") in {"1", "2"}:
                        continue
                    deferred_target = candidate.name.casefold() == "spellbender" and observation.event_type == "PLAY" and observation.card_type == "SPELL" and observation.actor_pid != controller
                    if deferred_target or rule.matches(observation, controller, state):
                        expected[card_id] = (
                            f"did not trigger after {observation.event_type.lower()} "
                            f"that matches {candidate.rule_key}", observation
                        )
                if expected:
                    expected_by_secret[secret.entity_id] = expected
            if expected_by_secret:
                previous = self._pending_tests.get(controller)
                if previous and previous["active_ids"] == active_ids:
                    for sid, expected in previous["expected_by_secret"].items():
                        expected_by_secret.setdefault(sid, {}).update(expected)
                self._pending_tests[controller] = {
                    "active_ids": active_ids,
                    "expected_by_secret": expected_by_secret,
                }

    def flush_pending_tests(self, state: GameState, reason: str = "action resolved") -> int:
        """Apply safe negative inference after the prior action fully resolves.

        For multiple active Secrets, negative inference is safe only when none of
        the slots present at action start revealed, resolved, or left SECRET.  If
        any slot changed, GhostData discards that action's negative tests and
        relies on the reveal plus duplicate-active reconciliation instead.
        """
        eliminated = 0
        for controller, pending in list(self._pending_tests.items()):
            original_ids = tuple(pending.get("active_ids", ()))
            expected_by_secret = pending.get("expected_by_secret", {})
            triggered_or_changed = False
            changed_slots = []
            for sid in original_ids:
                secret = state.secrets.get(sid)
                ent = state.entities.get(sid)
                if secret is None or ent is None or ent.zone != "SECRET" or ent.is_quest or secret.resolved:
                    triggered_or_changed = True
                    changed_slots.append(secret)

            current = self._active_unresolved_by_controller(state).get(controller, [])
            current_ids = tuple(sorted(s.entity_id for s in current))
            # Ice Barrier only adds armor: its public trigger cannot suppress
            # other attack Secrets. Preserve those deductions, while disruptive
            # or unresolved triggers still invalidate the action's tests.
            harmless_trigger = bool(changed_slots) and all(s and s.resolved and
                (self.card_db.get(s.resolved_card_id).name if self.card_db.get(s.resolved_card_id)
                 else s.resolved_name).casefold() == "ice barrier" for s in changed_slots)
            fast_combat = bool(changed_slots) and all(s and s.resolved and
                (self.card_db.get(s.resolved_card_id).name if self.card_db.get(s.resolved_card_id)
                 else s.resolved_name).casefold() in {"freezing trap", "explosive trap", "misdirection", "noble sacrifice", "vaporize", "ice barrier"}
                for s in changed_slots)
            if (triggered_or_changed and not (harmless_trigger or fast_combat)) or set(current_ids) - set(original_ids):
                self._pending_tests.pop(controller, None)
                self.reconcile_duplicate_active_secrets(state)
                continue

            for sid, expected in expected_by_secret.items():
                secret = state.secrets.get(sid)
                entity = state.entities.get(sid)
                if secret is None or secret.resolved or entity is None or entity.zone != "SECRET" or self._locked(state, secret):
                    continue
                for card_id, (why, observation) in expected.items():
                    if card_id in secret.candidates:
                        # After-spell triggers require a target after resolution,
                        # not just when the spell was initially played.
                        candidate = secret.candidates[card_id]
                        if triggered_or_changed and not harmless_trigger:
                            fast_names = {"noble sacrifice", "judgment of justice", "mystic misdirection",
                                "wandering monster", "vengeful visage", "ice barrier", "explosive trap",
                                "bamboozle", "bait and switch", "autodefense matrix", "splitting image",
                                "pack tactics", "snake trap", "venomstrike trap", "oasis ally"}
                            if observation.is_minion_target:
                                fast_names.add("freezing trap")
                            if observation.event_type != "ATTACK" or candidate.name.casefold() not in fast_names:
                                continue
                        actor = state.entities.get(observation.actor_entity_id)
                        if candidate.name.casefold() in {"spellbender", "redemption", "effigy", "emergency maneuvers", "avenge", "reckoning"} and not historical_matches(candidate.name.casefold(), observation, controller, state):
                            continue
                        if candidate.name.casefold() == "explosive runes" and (
                            actor is None or actor.zone != "PLAY" or actor.tags.get("DORMANT") in {"1", "2"}
                        ):
                            continue
                        if candidate.rule_key == "spell_with_enemy_minion" and not any(
                            e.zone == "PLAY" and e.card_type == "MINION" and e.controller != controller
                            for e in state.entities.values()
                        ):
                            continue
                        secret.eliminate(card_id, f"{why}; boundary={reason}")
                        eliminated += 1
            self._pending_tests.pop(controller, None)
            self.reconcile_duplicate_active_secrets(state)
        return eliminated

    def active_for_player(self, state: GameState, pid: int) -> Dict[int, SecretState]:
        out = {}
        for sid, secret in state.secrets.items():
            ent = state.entities.get(sid)
            if secret.controller == pid and ent and ent.zone == "SECRET" and not ent.is_quest:
                out[sid] = secret
        return out
