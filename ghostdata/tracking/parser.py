from __future__ import annotations

import re
from copy import deepcopy
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque, Dict, Iterable, Iterator, List, Optional, Tuple

from .card_db import CardDatabase
from ..paths import data_paths
from .models import (
    ChoicePrompt,
    EntityState,
    GameState,
    LegalOption,
    LegalOptionSet,
    MulliganRecord,
    OptionTarget,
    PlayerState,
    SubOption,
)
from .secrets import SecretObservation, SecretTracker
from .public_effects import effect_frame
from . import overdraw
from .timeline import RewindJournal, stream_of


RE_TS = re.compile(r"^[A-Z]\s+(?P<time>\d{2}:\d{2}:\d{2}\.\d+)\s+")
GAMESTATE_POWER_MARKER = "GameState.DebugPrintPower() - "
TASK_POWER_MARKER = "PowerTaskList.DebugPrintPower() - "
DEBUG_GAME_MARKER = "GameState.DebugPrintGame() - "
ENTITY_CHOICES_MARKER = "GameState.DebugPrintEntityChoices() - "
SEND_CHOICES_MARKER = "GameState.SendChoices() - "
ENTITIES_CHOSEN_MARKER = "GameState.DebugPrintEntitiesChosen() - "
OPTIONS_MARKER = "GameState.DebugPrintOptions() - "

RE_PLAYER = re.compile(r"Player EntityID=(?P<entity>\d+) PlayerID=(?P<pid>\d+)")
RE_FULL_ENTITY = re.compile(r"FULL_ENTITY - (?:Creating|Updating).*?(?:ID=|id=)(?P<entity>\d+).*?CardID=(?P<card>\S*)", re.I)
RE_SHOW_SIMPLE = re.compile(r"SHOW_ENTITY - Updating Entity=(?P<entity>\d+) CardID=(?P<card>[A-Za-z0-9_]+)")
RE_SHOW_COMPLEX = re.compile(r"SHOW_ENTITY - Updating Entity=\[entityName=(?P<name>.*?) id=(?P<entity>\d+) .*? player=(?P<player>\d+)\] CardID=(?P<card>[A-Za-z0-9_]+)")
RE_HIDE_ENTITY = re.compile(r"HIDE_ENTITY - Entity=(?P<entity>.+?) tag=(?P<tag>[A-Z0-9_]+) value=(?P<value>\S+)")
RE_INLINE_ENTITY = re.compile(r"\[entityName=(?P<name>.*?) id=(?P<entity>\d+) zone=(?P<zone>\w+) zonePos=(?P<pos>\d+) cardId=(?P<card>.*?) player=(?P<player>\d+)\]")
RE_TAG_CHANGE = re.compile(r"TAG_CHANGE Entity=(?P<entity>.+?) tag=(?P<tag>[A-Z0-9_]+|\d+) value=(?P<value>.*?)\s*$")
RE_CONTEXT_TAG = re.compile(r"tag=(?P<tag>[A-Z0-9_]+|\d+) value=(?P<value>.*)$")
RE_BLOCK = re.compile(
    r"BLOCK_START BlockType=(?P<kind>[A-Z_]+) "
    r"Entity=(?P<entity>.*?) EffectCardId=.*? Target=(?P<target>.*?)(?: SubOption=| TriggerKeyword=|$)"
)
RE_DEBUG_PLAYER = re.compile(r"PlayerID=(?P<pid>\d+), PlayerName=(?P<name>.+)$")
RE_DEBUG_KV = re.compile(r"(?P<key>BuildNumber|GameType|FormatType|ScenarioID)=(?P<value>.+)$")
RE_CHOICE_HEADER = re.compile(
    r"id=(?P<id>\d+) Player=(?P<player>.*?) TaskList=\d+ ChoiceType=(?P<type>\w+) CountMin=(?P<min>\d+) CountMax=(?P<max>\d+)"
)
RE_CHOICE_ENTITY = re.compile(r"Entities\[(?P<idx>\d+)\]=(?P<entity>\[.*\])")
RE_CHOSEN_HEADER = re.compile(r"id=(?P<id>\d+) Player=(?P<player>.*?) EntitiesCount=(?P<count>\d+)")
RE_SEND_HEADER = re.compile(r"id=(?P<id>\d+) ChoiceType=(?P<type>\w+)")
RE_SEND_ENTITY = re.compile(r"m_chosenEntities\[(?P<idx>\d+)\]=(?P<entity>\[.*\])")
RE_OPTION_HEADER = re.compile(r"id=(?P<id>\d+)$")
RE_OPTION = re.compile(r"option (?P<idx>\d+) type=(?P<type>\w+) mainEntity=(?P<entity>.*?) error=(?P<error>\S*) errorParam=(?P<param>.*)$")
RE_TARGET = re.compile(r"target (?P<idx>\d+) entity=(?P<entity>.*?) error=(?P<error>\S*) errorParam=(?P<param>.*)$")
RE_SUBOPTION = re.compile(r"subOption (?P<idx>\d+) entity=(?P<entity>.*?) error=(?P<error>\S*) errorParam=(?P<param>.*)$")

FINAL_TASK_TAGS = {"PLAYSTATE", "STEP", "NEXT_STEP", "STATE"}
FINAL_TASK_VALUES = {"WON", "LOST", "CONCEDED", "LOSING", "FINAL_WRAPUP", "FINAL_GAMEOVER", "COMPLETE"}


def _timestamp(line: str) -> str:
    m = RE_TS.search(line)
    return m.group("time").split(".")[0] if m else "--:--:--"


def _timestamp_seconds(line: str) -> float:
    m = RE_TS.search(line)
    if not m:
        return 0.0
    token = m.group("time")
    hh, mm, ss = token.split(":")
    return int(hh) * 3600 + int(mm) * 60 + float(ss)


def _to_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_inline_entity(raw: str) -> Optional[Dict[str, object]]:
    m = RE_INLINE_ENTITY.search(raw)
    if not m:
        return None
    return {
        "entity_id": int(m.group("entity")),
        "name": m.group("name"),
        "zone": m.group("zone"),
        "zone_position": int(m.group("pos")),
        "card_id": m.group("card"),
        "controller": int(m.group("player")),
    }


class PowerLogParser:
    def __init__(
        self,
        *,
        local_player_name: Optional[str] = None,
        card_db: Optional[CardDatabase] = None,
        emit_events: bool = False,
    ):
        self.state = GameState()
        self.requested_local_name = local_player_name
        self.card_db = card_db or CardDatabase(data_paths().root / "local_cards")
        self.secret_tracker = SecretTracker(self.card_db)
        self.emit_events = emit_events
        self._entity_context_id: Optional[int] = None
        self._task_entity_context_id: Optional[int] = None
        self._choice_context_id: Optional[int] = None
        self._chosen_context_id: Optional[int] = None
        self._send_context_id: Optional[int] = None
        self._current_option: Optional[LegalOption] = None
        self._pending_plays: Dict[int, Tuple[str, int, str]] = {}
        self._revealed_pairs: set[Tuple[int, str]] = set()
        self._current_time_seconds: float = 0.0
        self._canonical_state_tokens: Dict[Tuple[object, ...], Deque[float]] = defaultdict(deque)
        self._dedupe_window_seconds: float = 30.0
        self._block_depth = 0
        self._effects = []
        self._task_effects = []
        self._created_entities: set[int] = set()
        self._suppressed_identities: set[int] = set()
        self._last_drawn: dict[int, str] = {}
        self._played_this_turn = []
        self._history_target = {"canonical": False, "task": False}
        self._parsing_source = "canonical"
        self._journal = None
        self._rebuild_tracker = None
        self._deck_order = 0
        self._copy_predictions = set()

    def reset_for_new_source(self) -> None:
        """Reset parser state while preserving configuration and card cache.

        Used when Hearthstone rotates or truncates Power.log. The caller keeps
        the same parser object, while all per-game/per-stream state is rebuilt
        from the new authoritative log source.
        """
        if self._journal is not None:
            self._journal.close()
        requested_local_name = self.requested_local_name
        card_db = self.card_db
        emit_events = self.emit_events
        self.__init__(
            local_player_name=requested_local_name,
            card_db=card_db,
            emit_events=emit_events,
        )

    # ---------- public helpers ----------
    def parse_file(self, path: Path) -> GameState:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                self.parse_line(line)
        return self.state

    def parse_lines(self, lines: Iterable[str]) -> GameState:
        for line in lines:
            self.parse_line(line)
        return self.state

    def parse_line(self, line: str) -> None:
        if stream_of(line):
            new_game = GAMESTATE_POWER_MARKER in line and line.split(GAMESTATE_POWER_MARKER, 1)[1].strip() == "CREATE_GAME"
            if new_game:
                if self._journal is not None:
                    self._journal.close()
                self._journal = None
                # Clear the prior game's stream caches before taking the base
                # snapshot; otherwise the journal retains them for another game.
                self._parse_line(line)
            if self._journal is None:
                runtime = {k:v for k,v in self.__dict__.items() if k not in {"_journal", "_rebuild_tracker", "card_db"}}
                if new_game:
                    runtime["state"] = GameState(game_number=self.state.game_number - 1)
                self._journal = RewindJournal(deepcopy(runtime, {id(self.card_db): self.card_db}))
            index, changed = self._journal.append(line)
            if new_game:
                return
            if changed:
                self._restore_timeline()
                return
            if self._journal.ignored(index, line):
                return
        self._parse_line(line)

    def _restore_timeline(self):
        journal, tracker, db = self._journal, self._rebuild_tracker, self.card_db
        self.__dict__.update(deepcopy(journal.base, {id(db): db, id(journal.base["secret_tracker"].card_db): db}))
        self.card_db = db
        self.secret_tracker.card_db = db
        if tracker is not None:
            tracker.reset_runtime(preserve_selected_deck=True)
        for index, line in journal.lines():
            if not journal.ignored(index, line):
                self._parse_line(line)
                if tracker is not None:
                    tracker.observe(self.state, publish=False)

    def _parse_line(self, line: str) -> None:
        self._parsing_source = "canonical"
        ts = _timestamp(line)
        self._current_time_seconds = _timestamp_seconds(line)

        if GAMESTATE_POWER_MARKER in line:
            payload = line.split(GAMESTATE_POWER_MARKER, 1)[1].rstrip("\n")
            self._parse_power(payload, ts, canonical=True)
            return

        if TASK_POWER_MARKER in line:
            self._parsing_source = "task"
            payload = line.split(TASK_POWER_MARKER, 1)[1].rstrip("\n")
            self._parse_task_state(payload, ts)
            return

        if DEBUG_GAME_MARKER in line:
            payload = line.split(DEBUG_GAME_MARKER, 1)[1].strip()
            self._parse_debug_game(payload, ts)
            return

        if ENTITY_CHOICES_MARKER in line:
            payload = line.split(ENTITY_CHOICES_MARKER, 1)[1].strip()
            self._parse_entity_choices(payload, ts)
            return

        if ENTITIES_CHOSEN_MARKER in line:
            payload = line.split(ENTITIES_CHOSEN_MARKER, 1)[1].strip()
            self._parse_entities_chosen(payload, ts)
            return

        if SEND_CHOICES_MARKER in line:
            payload = line.split(SEND_CHOICES_MARKER, 1)[1].strip()
            self._parse_send_choices(payload, ts)
            return

        if OPTIONS_MARKER in line:
            payload = line.split(OPTIONS_MARKER, 1)[1].rstrip("\n")
            self._parse_options(payload.strip(), ts)
            return

    # ---------- event utilities ----------
    def _emit(self, ts: str, event_type: str, text: str, **data: object) -> None:
        event = self.state.emit(ts, event_type, text, **data)
        if self.emit_events:
            print(f"[{event.timestamp}] {event.event_type:<12} {event.text}", flush=True)

    def _entity(self, entity_id: int) -> EntityState:
        return self.state.entity(entity_id)

    def _update_entity_from_inline(
        self, raw: str, *, ts: str | None = None, update_zone: bool = False
    ) -> Optional[EntityState]:
        """Merge an inline entity reference into canonical state.

        Power.log often exposes a local card identity first inside an inline
        entity reference on TAG_CHANGE / Options / Choice lines rather than in
        SHOW_ENTITY. Incremental consumers such as DeckTrackerEngine need a
        REVEAL event as authoritative hand/deck counts advance. Emit the same
        deduplicated identity event
        whenever an inline reference is the first place the CardID becomes
        known.
        """
        info = parse_inline_entity(raw)
        if not info:
            return None
        e = self._entity(int(info["entity_id"]))
        e.controller = int(info["controller"])
        if update_zone:
            e.zone = str(info["zone"])
            e.zone_position = int(info["zone_position"])
        changed = False
        if e.entity_id not in self._suppressed_identities and not self._hide_identity(e):
            changed = e.update_card_identity(str(info["card_id"]), str(info["name"]))
        if changed and ts is not None:
            self._on_identity_change(e, ts)
        return e

    def _resolve_named_pid(self, name: str) -> Optional[int]:
        if name in self.state.name_to_pid:
            return self.state.name_to_pid[name]
        if self.state.local_player_name == name and self.state.local_player_pid is not None:
            return self.state.bind_name(name, self.state.local_player_pid)
        if name and name not in ("GameEntity", "UNKNOWN HUMAN PLAYER") and self.state.opponent_pid is not None:
            return self.state.bind_name(name, self.state.opponent_pid)
        return None

    def _resolve_entity_ref(self, raw: str, *, ts: str | None = None) -> Tuple[Optional[EntityState], Optional[int], Optional[str]]:
        raw = raw.strip()
        inline = self._update_entity_from_inline(raw, ts=ts)
        if inline:
            return inline, inline.controller, None
        if raw.isdigit():
            eid = int(raw)
            e = self._entity(eid)
            pid = None
            for player_id, p in self.state.players.items():
                if p.entity_id == eid:
                    pid = player_id
                    break
            return e, pid, None
        if raw == "GameEntity":
            return None, None, "GameEntity"
        pid = self._resolve_named_pid(raw)
        return None, pid, raw

    # ---------- main power stream ----------
    def _parse_power(self, payload: str, ts: str, canonical: bool) -> None:
        p = payload.strip()
        if not p:
            return
        self.state.raw_counts["canonical_power"] = self.state.raw_counts.get("canonical_power", 0) + 1

        # Context tags belong to the immediately preceding FULL_ENTITY/SHOW_ENTITY.
        m = RE_CONTEXT_TAG.fullmatch(p)
        if m and self._entity_context_id is not None:
            self._apply_entity_tag(self._entity(self._entity_context_id), m.group("tag"), m.group("value"), ts)
            return

        # A non-context power line ends the current entity-definition context.
        self._entity_context_id = None

        if self._parse_public_metadata(p, ts, "canonical"):
            return

        if p == "CREATE_GAME":
            game_no = self.state.game_number + 1
            self.state.reset(game_no)
            # CREATE_GAME is a hard parser lifecycle boundary. GameState.reset()
            # clears persisted game data, but parser-side stream contexts must be
            # cleared independently so a warm-replayed choice/option ID from the
            # previous game can never address the new empty dictionaries.
            self._entity_context_id = None
            self._task_entity_context_id = None
            self._choice_context_id = None
            self._chosen_context_id = None
            self._send_context_id = None
            self._current_option = None
            self._pending_plays.clear()
            self._block_depth = 0
            self._effects.clear()
            self._task_effects.clear()
            self._created_entities.clear()
            self._suppressed_identities.clear()
            self._last_drawn.clear()
            self._played_this_turn.clear()
            self._history_target = {"canonical": False, "task": False}
            self._deck_order = 0
            self._copy_predictions.clear()
            self._revealed_pairs.clear()
            self._canonical_state_tokens.clear()
            self.secret_tracker.reset()
            self._emit(ts, "GAME_START", f"New game #{game_no}")
            return

        m = RE_PLAYER.search(p)
        if m:
            pid = int(m.group("pid"))
            eid = int(m.group("entity"))
            player = self.state.player(pid)
            player.entity_id = eid
            e = self._entity(eid)
            e.controller = pid
            e.card_type = "PLAYER"
            self._entity_context_id = eid
            return

        m = RE_FULL_ENTITY.search(p)
        if m:
            eid = int(m.group("entity"))
            card_id = m.group("card") or ""
            e = self._entity(eid)
            changed = e.update_card_identity(card_id)
            if eid not in self._created_entities:
                self._created_entities.add(eid)
                if self._effects:
                    self._effects[-1].candidates.append(eid)
                    overdraw.created(self.state, eid, self._effects[-1])
            self._entity_context_id = eid
            if changed:
                self._on_identity_change(e, ts)
            return

        m = RE_SHOW_COMPLEX.search(p) or RE_SHOW_SIMPLE.search(p)
        if m:
            eid = int(m.group("entity"))
            card_id = m.group("card")
            e = self._entity(eid)
            if m.groupdict().get("player"):
                e.controller = int(m.group("player"))
            if self._hide_identity(e):
                self._suppressed_identities.add(eid)
                self._entity_context_id = eid
                return
            self._suppressed_identities.discard(eid)
            self._show_deck_selection(e)
            name = m.groupdict().get("name") or ""
            changed = e.update_card_identity(card_id, name)
            self._entity_context_id = eid
            if changed or (eid, card_id) not in self._revealed_pairs:
                self._on_identity_change(e, ts)
            return

        m = RE_HIDE_ENTITY.search(p)
        if m:
            self._conceal(m, ts, "canonical")
            return

        m = RE_TAG_CHANGE.search(p)
        if m:
            self._apply_tag_change(m.group("entity"), m.group("tag"), m.group("value"), ts)
            return

        if p == "BLOCK_END":
            if self._effects:
                self._resolve_creations(self._effects.pop(), ts)
            self._block_depth = max(0, self._block_depth - 1)
            if self._block_depth == 0:
                self.secret_tracker.flush_pending_tests(self.state, reason="outer action resolved")
            return

        m = RE_BLOCK.search(p)
        if m:
            # Nested trigger/deathrattle blocks are part of the same action.
            # Testing at BLOCK_START used to eliminate a Secret just before its
            # own nested trigger revealed it.
            self._block_depth += 1
            self._parse_block(m.group("kind"), m.group("entity"), m.group("target"), ts)
            self._effects[-1].overdraw_capture = "TriggerKeyword=TRIGGER_VISUAL" in p
            return

        if "META_DATA - Meta=OVERRIDE_HISTORY" in p and self._effects:
            self._effects[-1].hide_reveals = True

    def _parse_task_state(self, payload: str, ts: str) -> None:
        """Consume TaskList state transitions without duplicating visible actions.

        GameState.DebugPrintPower is our authority for PLAY/ATTACK ordering, but
        Hearthstone emits some nested deaths/transforms/final state only through
        PowerTaskList. State mutations are idempotent, so we ingest TaskList
        entity/tag updates while ignoring its duplicate action blocks/CREATE_GAME.
        """
        p = payload.strip()
        if not p:
            return

        m = RE_CONTEXT_TAG.fullmatch(p)
        if m and self._task_entity_context_id is not None:
            self._apply_entity_tag(self._entity(self._task_entity_context_id), m.group("tag"), m.group("value"), ts, source="task")
            return

        self._task_entity_context_id = None

        if self._parse_public_metadata(p, ts, "task"):
            return

        # Some creations exist only in TaskList. Each entity can belong to one
        # stream's batch; duplicate action records cannot create another card.
        if p == "BLOCK_END":
            if self._task_effects:
                self._resolve_creations(self._task_effects.pop(), ts)
            if not self._task_effects and not self._effects:
                self.secret_tracker.flush_pending_tests(self.state, reason="animated action resolved")
            return
        m = RE_BLOCK.search(p)
        if m:
            e = self._update_entity_from_inline(m.group("entity"), ts=ts)
            if e is None and m.group("entity").isdigit():
                e = self.state.entities.get(int(m.group("entity")))
            target = self._update_entity_from_inline(m.group("target"), ts=ts)
            if target is None and m.group("target").isdigit():
                target = self.state.entities.get(int(m.group("target")))
            self._task_effects.append(effect_frame(e, m.group("kind"), target,
                                                   self.state, self._last_drawn, self._played_this_turn))
            self._task_effects[-1].overdraw_capture = "TriggerKeyword=TRIGGER_VISUAL" in p
            return
        if "META_DATA - Meta=OVERRIDE_HISTORY" in p and self._task_effects:
            self._task_effects[-1].hide_reveals = True
            return

        m = RE_FULL_ENTITY.search(p)
        if m:
            eid = int(m.group("entity"))
            card_id = m.group("card") or ""
            e = self._entity(eid)
            changed = e.update_card_identity(card_id)
            self._task_entity_context_id = eid
            if eid not in self._created_entities:
                self._created_entities.add(eid)
                if self._task_effects:
                    self._task_effects[-1].candidates.append(eid)
                    overdraw.created(self.state, eid, self._task_effects[-1])
            if changed:
                self._on_identity_change(e, ts)
            self.state.raw_counts["task_entity"] = self.state.raw_counts.get("task_entity", 0) + 1
            return

        m = RE_SHOW_COMPLEX.search(p) or RE_SHOW_SIMPLE.search(p)
        if m:
            eid = int(m.group("entity"))
            card_id = m.group("card")
            e = self._entity(eid)
            if m.groupdict().get("player"):
                e.controller = int(m.group("player"))
            if self._hide_identity(e):
                self._suppressed_identities.add(eid)
                self._task_entity_context_id = eid
                return
            self._suppressed_identities.discard(eid)
            self._show_deck_selection(e)
            name = m.groupdict().get("name") or ""
            changed = e.update_card_identity(card_id, name)
            self._task_entity_context_id = eid
            if changed or (eid, card_id) not in self._revealed_pairs:
                self._on_identity_change(e, ts)
            self.state.raw_counts["task_entity"] = self.state.raw_counts.get("task_entity", 0) + 1
            return

        m = RE_HIDE_ENTITY.search(p)
        if m:
            self._conceal(m, ts, "task")
            return

        m = RE_TAG_CHANGE.search(p)
        if m:
            self.state.raw_counts["task_tag"] = self.state.raw_counts.get("task_tag", 0) + 1
            self._apply_tag_change(m.group("entity"), m.group("tag"), m.group("value"), ts, task_fallback=True)
            return

        # Intentionally ignore CREATE_GAME, Player definitions and BLOCK_START
        # here. Those are duplicated visible-action/control records.

    def _parse_block(self, kind: str, entity_raw: str, target_raw: str, ts: str) -> None:
        if not self._effects:
            for entity in self.state.entities.values():
                for key in [k for k in entity.tags if k.startswith("GHOSTDATA_DAMAGE_")]:
                    entity.tags.pop(key)
        if kind == "PLAY":
            info = parse_inline_entity(entity_raw)
            if info:
                self._suppressed_identities.discard(int(info["entity_id"]))
        e = self._update_entity_from_inline(entity_raw, ts=ts)
        if e is None and entity_raw.isdigit():
            e = self.state.entities.get(int(entity_raw))
        target = self._update_entity_from_inline(target_raw, ts=ts)
        if target is None and target_raw.isdigit():
            target = self.state.entities.get(int(target_raw))
        self._effects.append(effect_frame(e, kind, target, self.state,
                                          self._last_drawn, self._played_this_turn))
        if not e:
            return
        if kind == "TRIGGER":
            self._emit(ts, "TRIGGER", "Public effect resolved", entity_id=e.entity_id, player=e.controller, card_id=e.card_id)
        if kind == "POWER" and e.card_type == "HERO_POWER":
            self.secret_tracker.observe_public_event(self.state, SecretObservation("HERO_POWER", actor_pid=e.controller))
        if kind == "POWER" and e.card_id == "TIME_057":
            for card in self.state.entities.values():
                if card.zone == "HAND":
                    card.tags.pop("GHOSTDATA_PUBLIC_COST", None)
        if kind == "PLAY":
            e.last_played_turn = self.state.global_turn
            self._played_this_turn = [p for p in self._played_this_turn if p[1] == self.state.global_turn]
            if e.card_id:
                self._played_this_turn.append((e.controller, self.state.global_turn, e.card_id))
            if e.is_known:
                shown = e.name or e.card_id
                self._emit(ts, "PLAY", f"P{e.controller}: {shown}", player=e.controller, entity_id=e.entity_id, card_id=e.card_id, turn=self.state.global_turn)
            else:
                self._pending_plays[e.entity_id] = (ts, int(e.controller or 0), target_raw)
            self.secret_tracker.observe_public_event(self.state, SecretObservation("PLAY", actor_pid=e.controller, actor_entity_id=e.entity_id, card_type=e.card_type, target_entity_id=target.entity_id if target else None))
        elif kind == "ATTACK":
            attacker_name = e.name or e.card_id or f"entity {e.entity_id}"
            target_name = (target.name or target.card_id or f"entity {target.entity_id}") if target else target_raw
            self._emit(ts, "ATTACK", f"P{e.controller}: {attacker_name} -> {target_name}", player=e.controller, attacker=e.entity_id, target=target.entity_id if target else None)
            self.secret_tracker.observe_public_event(
                self.state,
                SecretObservation(
                    "ATTACK",
                    actor_pid=e.controller,
                    target_pid=target.controller if target else None,
                    actor_entity_id=e.entity_id,
                    target_entity_id=target.entity_id if target else None,
                    card_type=e.card_type,
                    is_hero_target=bool(target and target.card_type == "HERO"),
                    is_minion_target=bool(target and target.card_type == "MINION"),
                ),
            )

    def _on_identity_change(self, e: EntityState, ts: str) -> None:
        if e.zone == "HAND" and e.card_id:
            e.tags["GHOSTDATA_OVERDRAW_REVEALED"] = "1"
        self._reconcile_overdraw(ts)
        self._public_copy_and_order(e, ts)
        key = (e.entity_id, e.card_id)
        if e.card_id and key not in self._revealed_pairs:
            self._revealed_pairs.add(key)
            self._emit(ts, "REVEAL", f"P{e.controller or '?'} {e.name or e.card_id}", entity_id=e.entity_id, card_id=e.card_id, player=e.controller)
        self.secret_tracker.on_identity_change(self.state, e)
        pending = self._pending_plays.pop(e.entity_id, None)
        if pending:
            original_ts, player, _ = pending
            shown = e.name or e.card_id or f"entity {e.entity_id}"
            self._emit(ts, "PLAY", f"P{player}: {shown}", player=player, entity_id=e.entity_id, card_id=e.card_id, delayed_resolution=True, original_play_timestamp=original_ts)

    def _reconcile_overdraw(self, ts):
        for entity in overdraw.reconcile(self.state):
            card = self.card_db.get(entity.card_id)
            if entity.cost is None and card and card.cost is not None:
                entity.cost = max(0, card.cost - 1)
            self._on_identity_change(entity, ts)

    def _has_dredge(self, entity):
        card = self.card_db.get(entity.card_id) if entity else None
        return bool(entity and (entity.tags.get("DREDGE") == "1" or (card and "DREDGE" in card.mechanics)))

    def _public_copy_and_order(self, entity, ts):
        frames = self._effects if self._parsing_source == "canonical" else self._task_effects
        creator = self.state.entities.get(entity.creator or 0)
        target = self.state.entities.get(entity.copied_from_entity_id or 0)
        if (entity.controller == self.state.local_player_pid and entity.card_id and target
                and any(f.card_id in {"EDR_528", "TIME_039"} for f in frames)):
            # Discover reveals a possible identity, never which hidden slot it
            # belongs to. Keep the prediction detached from the source entity.
            token = ("COPY_POOL", entity.entity_id, entity.card_id)
            if token not in self._copy_predictions:
                self._copy_predictions.add(token)
                self._emit(ts, "PUBLIC_UNIQUE", "Public copy reveals an unlocated card",
                           player=target.controller, card_id=entity.card_id)
        linked = self.state.entities.get(_to_int(entity.tags.get("LINKED_ENTITY", "")) or 0)
        if (target and linked is target and entity.zone == "SETASIDE" and target.zone == "DECK"
                and entity.controller == self.state.local_player_pid and self._has_dredge(creator)
                and not any(f.card_id in {"REV_365", "ULD_216"} for f in frames)):
            target.tags["GHOSTDATA_DECK_LOCATION"] = "BOTTOM"
            # This private choice is visible to the local player.
            if entity.card_id and not target.card_id:
                target.update_card_identity(entity.card_id)
                self._on_identity_change(target, ts)
    def _show_deck_selection(self, entity):
        frames = self._effects if self._parsing_source == "canonical" else self._task_effects
        if (entity.zone == "DECK" and entity.controller == self.state.local_player_pid
                and entity.tags.get("GHOSTDATA_DECK_LOCATION") == "BOTTOM" and frames
                and self._has_dredge(self.state.entities.get(frames[-1].source))):
            entity.tags["GHOSTDATA_DECK_LOCATION"] = "TOP"
            self._deck_order += 100
            entity.tags["GHOSTDATA_DECK_INDEX"] = str(self._deck_order)

    def _hide_identity(self, entity):
        frames = self._effects if self._parsing_source == "canonical" else self._task_effects
        return (self.state.local_player_pid is None or entity.controller != self.state.local_player_pid) and any(
            f.hide_reveals for f in frames)

    def _parse_public_metadata(self, payload, ts, source):
        burn_key = "GHOSTDATA_BURN_META_" + source
        if "META_DATA - Meta=BURNED_CARD" in payload:
            self.state.game_tags[burn_key] = "1"
            return True
        if payload.startswith("Info[") and self.state.game_tags.get(burn_key) == "1":
            info = parse_inline_entity(payload)
            match = re.search(r"Info\[\d+\]\s*=\s*(\d+)\b", payload)
            eid = int(info["entity_id"]) if info else int(match.group(1)) if match else None
            if eid is not None:
                entity = self._entity(eid)
                if info:
                    entity.controller = entity.controller or int(info["controller"])
                    entity.update_card_identity(str(info["card_id"]), str(info["name"]))
                overdraw.burned(self.state, entity)
                if entity.card_id:
                    self._on_identity_change(entity, ts)
            return True
        self.state.game_tags.pop(burn_key, None)
        shuffle = re.search(r"SHUFFLE_DECK PlayerID=(\d+)", payload)
        if shuffle:
            pid = int(shuffle.group(1))
            token = ("SHUFFLE", pid)
            if source == "task" and self._consume_canonical_token(token):
                return True
            if source == "canonical":
                self._record_canonical_token(token)
            for entity in self.state.entities.values():
                if entity.controller == pid:
                    entity.tags.pop("GHOSTDATA_DECK_LOCATION", None)
                    entity.tags.pop("GHOSTDATA_DECK_INDEX", None)
                    if pid == self.state.opponent_pid and entity.zone == "DECK" and entity.card_id:
                        self._revealed_pairs.discard((entity.entity_id, entity.card_id))
                        self._emit(ts, "HIDE", "Shuffle conceals future draw identity", entity_id=entity.entity_id)
            return True
        frames = self._effects if source == "canonical" else self._task_effects
        if "META_DATA - Meta=HISTORY_TARGET" in payload:
            self._history_target[source] = True
            return True
        if payload.startswith("Info[") and self._history_target[source]:
            # Beatrix's chosen minion is announced publicly in history. Its
            # actual created entities may precede that announcement.
            if frames and frames[-1].card_id == "JAIL_397" and frames[-1].kind == "TRIGGER":
                info = parse_inline_entity(payload)
                entity = self.state.entities.get(int(info["entity_id"])) if info else None
                cid = str(info["card_id"]) if info else ""
                cid = cid or (entity.card_id if entity else "")
                if cid:
                    frames[-1].expected.clear()
                    frames[-1].expected.extend([cid] * 10)
            return True
        self._history_target[source] = False
        return False

    def _conceal(self, match, ts, source):
        raw = match.group("entity").strip()
        info = parse_inline_entity(raw)
        eid = int(info["entity_id"]) if info else int(raw) if raw.isdigit() else None
        if eid is None:
            return
        # HIDE's inline CardID is not a public reveal.
        ent = self._entity(eid)
        tag, value = match.group("tag"), match.group("value")
        self._apply_entity_tag(ent, tag, value, ts, source=source)
        token = ("HIDE", eid, tag, value)
        if source == "task" and self._consume_canonical_token(token):
            return
        if source == "canonical":
            self._record_canonical_token(token)
        self._revealed_pairs.discard((eid, ent.card_id))
        ent.tags.pop("GHOSTDATA_PUBLIC_LABEL", None)
        ent.tags.pop("GHOSTDATA_PUBLIC_COST", None)
        frames = self._effects if source == "canonical" else self._task_effects
        for frame in frames:
            if eid in frame.candidates:
                frame.concealed.add(eid)
        self._emit(ts, "HIDE", "Card identity concealed", entity_id=eid)

    def _resolve_creations(self, frame, ts):
        """Resolve only this completed effect's newly created playable cards."""
        if frame.pool and frame.candidates:
            members = [eid for eid in frame.candidates if self.state.entities[eid].controller == frame.controller
                       and self.state.entities[eid].zone in {"DECK", "HAND", "GRAVEYARD"}]
            if members:
                self._emit(ts, "PUBLIC_POOL", "Public reward multiset, locations unresolved",
                           entity_id=frame.source, player=frame.controller, cards=list(frame.pool), members=members)
        for eid in frame.candidates:
            e = self.state.entities[eid]
            card = self.card_db.get(e.card_id) if e.card_id else None
            card_type = e.card_type or (card.card_type if card else "")
            playable = card_type in {"MINION", "SPELL", "WEAPON", "LOCATION"}
            # Opponent FULL_ENTITY normally omits CARDTYPE as well as CardID.
            # HAND/DECK identify real cards; anonymous SETASIDE helpers do not.
            hidden_card = card_type in {"", "INVALID"} and e.zone in {"HAND", "DECK"}
            if (not frame.expected or e.controller != frame.controller
                    or not (playable or hidden_card)
                    or e.zone not in {"DECK", "HAND", "SETASIDE", "GRAVEYARD", "REMOVEDFROMGAME"}
                    or (e.creator and e.creator != frame.source)):
                continue
            predicted = frame.expected.popleft()
            # Logged identity wins over predictions, including transformations.
            if predicted and e.card_id and e.card_id != predicted:
                continue
            e.tags["GHOSTDATA_PUBLIC_CREATION"] = "1"
            if not e.creator:
                self._apply_entity_tag(e, "CREATOR", str(frame.source), ts)
            if frame.location and e.zone == "DECK":
                e.tags["GHOSTDATA_DECK_LOCATION"] = frame.location
            if frame.label and not e.card_id:
                e.tags["GHOSTDATA_PUBLIC_LABEL"] = frame.label
                if frame.cost is not None:
                    e.tags["GHOSTDATA_PUBLIC_COST"] = str(frame.cost)
                self._emit(ts, "PROVENANCE_CHANGE", "Public effect constrains generated card",
                           entity_id=eid, player=e.controller)
                continue
            if not e.card_id and predicted:
                e.update_card_identity(predicted)
                definition = self.card_db.get(predicted)
                if definition:
                    e.name = definition.name
                    e.card_type = definition.card_type
                    e.cost = e.cost if e.cost is not None else definition.cost
            self._on_identity_change(e, ts)
            self._emit(ts, "REVEAL", "Public effect identifies created card",
                       entity_id=eid, card_id=e.card_id, player=e.controller)
            if eid in frame.concealed and e.zone == "DECK" and e.controller == self.state.opponent_pid:
                self._revealed_pairs.discard((eid, e.card_id))
                self._emit(ts, "HIDE", "Generated deck identity has unknown position", entity_id=eid)

    def _record_canonical_token(self, token: Tuple[object, ...]) -> None:
        self._canonical_state_tokens[token].append(self._current_time_seconds)

    def _consume_canonical_token(self, token: Tuple[object, ...]) -> bool:
        dq = self._canonical_state_tokens.get(token)
        if not dq:
            return False
        now = self._current_time_seconds
        while dq and now - dq[0] > self._dedupe_window_seconds:
            dq.popleft()
        if dq:
            dq.popleft()
            if not dq:
                self._canonical_state_tokens.pop(token, None)
            return True
        self._canonical_state_tokens.pop(token, None)
        return False

    def _apply_entity_tag(self, e: EntityState, tag: str, value: str, ts: str, *, source: str = "canonical") -> None:
        token = ("E", e.entity_id, tag, value)
        if source == "task":
            if self._consume_canonical_token(token):
                return
        else:
            self._record_canonical_token(token)
        old_zone = e.zone
        old_controller = e.controller
        old_creator = e.creator
        old_displayed_creator = e.displayed_creator
        old_copied_from = e.copied_from_entity_id
        old_damage, old_armor = e.damage, e.armor
        e.tags[tag] = value
        if tag == "CONTROLLER":
            e.controller = _to_int(value)
            if str(e.zone or "").upper() == "SECRET":
                # Generated Secrets may exist only in PowerTaskList, whose
                # FULL_ENTITY tags commonly arrive ZONE first and CONTROLLER
                # second. Retry registration now that ownership exists.
                self.secret_tracker.on_zone_change(self.state, e, e.zone, e.zone)
        elif tag == "ZONE":
            e.zone = value
        elif tag == "ZONE_POSITION":
            e.zone_position = _to_int(value) or 0
        elif tag == "CARDTYPE":
            e.card_type = value
        elif tag == "CLASS":
            e.card_class = value
            if e.card_type == "HERO" and e.controller:
                player = self.state.player(e.controller)
                player.player_class = value
                if not player.starting_class:
                    player.starting_class = value
            if str(e.zone or "").upper() == "SECRET" and e.entity_id not in self.state.secrets:
                # Repair a late class tag after provisional registration.
                self.secret_tracker.on_zone_change(self.state, e, e.zone, e.zone)
            # Hidden Secret class is deterministic board-state information and
            # may arrive after ZONE=SECRET. Rebind the disclosure-safe candidate
            # pool to the entity's exact class rather than the hero-class fallback.
            self.secret_tracker.on_class_change(self.state, e)
        elif tag in ("COST", "TAG_LAST_KNOWN_COST_IN_HAND"):
            parsed = _to_int(value)
            if parsed is not None and tag == "COST":
                e.cost = parsed
        elif tag == "ATK":
            e.attack = _to_int(value)
        elif tag == "HEALTH":
            e.health = _to_int(value)
        elif tag == "DAMAGE":
            e.damage = _to_int(value) or 0
        elif tag == "ARMOR":
            e.armor = _to_int(value) or 0
        elif tag == "CREATOR":
            e.creator = _to_int(value)
        elif tag == "DISPLAYED_CREATOR":
            e.displayed_creator = _to_int(value)
        elif tag == "COPIED_FROM_ENTITY_ID":
            e.copied_from_entity_id = _to_int(value)
        elif tag == "REVEALED":
            e.revealed = value == "1"
        elif tag in ("QUEST", "QUESTLINE", "SIDE_QUEST", "OBJECTIVE", "PALADIN_AURA", "AURA", "SIGIL") and value == "1":
            # Several persistent hero-zone effects share ZONE=SECRET internally
            # but are not hidden Secrets. Purge provisional Secret classification.
            self.state.secrets.pop(e.entity_id, None)
        elif tag == "HERO_ENTITY" and e.card_type == "PLAYER":
            # Player entity controller equals PlayerID in this log format.
            if e.controller:
                self.state.player(e.controller).hero_entity_id = _to_int(value)

        if tag in {"CREATOR", "COPIED_FROM_ENTITY_ID", "LINKED_ENTITY", "CONTROLLER", "ZONE"}:
            self._public_copy_and_order(e, ts)
            if e.copied_from_entity_id:
                for row in self.state.recoverable_overdraw:
                    if row["old"] == e.copied_from_entity_id and not row["new"]:
                        row["new"] = e.entity_id
            self._reconcile_overdraw(ts)

        damage = max(0, e.damage - old_damage) + max(0, old_armor - e.armor)
        if damage and e.tags.get("IMMUNE", "0") == "0":
            if e.card_type == "HERO" and e.controller:
                self.state.player(e.controller).tags["GHOSTDATA_DAMAGED_TURN"] = str(self.state.global_turn)
                if e.damage > old_damage:
                    self.secret_tracker.observe_public_event(self.state, SecretObservation("HERO_DAMAGED",
                        actor_pid=self.state.current_player_pid, target_pid=e.controller, target_entity_id=e.entity_id))
            frames = self._effects if source == "canonical" else self._task_effects
            dealer = self.state.entities.get(frames[-1].source) if frames else None
            if dealer and dealer.card_type == "MINION":
                key = f"GHOSTDATA_DAMAGE_{self._block_depth}_{dealer.entity_id}_{e.entity_id}"
                total = int(dealer.tags.get(key, "0")) + damage
                dealer.tags[key] = str(total)
                if total >= 3:
                    self.secret_tracker.observe_public_event(self.state, SecretObservation("MINION_DAMAGE_3",
                        actor_pid=dealer.controller, actor_entity_id=dealer.entity_id))

        if old_controller != e.controller and tag == "CONTROLLER":
            self._emit(
                ts, "CONTROLLER_CHANGE",
                f"Entity {e.entity_id} controller {old_controller or '?'} -> {e.controller or '?'}",
                entity_id=e.entity_id, old_controller=old_controller, new_controller=e.controller,
                card_id=e.card_id,
            )

        if tag in {"CREATOR", "DISPLAYED_CREATOR", "COPIED_FROM_ENTITY_ID"}:
            changed = (
                old_creator != e.creator
                or old_displayed_creator != e.displayed_creator
                or old_copied_from != e.copied_from_entity_id
            )
            if changed:
                # Provenance metadata frequently arrives *after* CardID/controller
                # exposure (notably The Coin and copied/generated cards).  Emit a
                # neutral semantic update so incremental consumers can upgrade an
                # earlier UNKNOWN classification without rescanning all entities.
                self._emit(
                    ts, "PROVENANCE_CHANGE",
                    f"Entity {e.entity_id} provenance metadata updated",
                    entity_id=e.entity_id, card_id=e.card_id, player=e.controller,
                    creator=e.creator, displayed_creator=e.displayed_creator,
                    copied_from_entity_id=e.copied_from_entity_id,
                )
                self.secret_tracker.on_provenance_change(self.state, e)

        # Both Ectoplasm spells have this displayed source. Hidden copies of
        # the destroyed minions only have CREATOR and must stay anonymous.
        displayed = self.state.entities.get(e.displayed_creator or 0)
        if displayed and displayed.card_id == "CAP_805" and not e.card_id:
            e.update_card_identity("CAP_805t")
            e.tags["GHOSTDATA_PUBLIC_CREATION"] = "1"
            self._on_identity_change(e, ts)

        # Ursol publicly casts a copy of the spell removed from its hand.
        # Only that explicit source permits reverse propagation to a hidden
        # original; generic Discover/copy links do not reveal hand positions.
        copied = self.state.entities.get(e.copied_from_entity_id or 0)
        creator = self.state.entities.get(e.creator or 0)
        if (copied and not copied.card_id and e.card_id and creator
                and creator.card_id == "EDR_259" and copied.zone in {"HAND", "SETASIDE"}
                and e.zone in {"PLAY", "SECRET", "GRAVEYARD"}):
            copied.update_card_identity(e.card_id)
            self._on_identity_change(copied, ts)

        linked = self.state.entities.get(_to_int(e.tags.get("LINKED_ENTITY", "")) or 0)
        if (linked and not linked.card_id and linked.zone == "DECK" and e.card_id
                and e.controller == self.state.local_player_pid
                and ((creator and creator.card_id == "TLC_521")
                     or any(f.card_id == "TLC_521" for f in (*self._effects, *self._task_effects)))):
            linked.update_card_identity(e.card_id)
            linked.card_type = linked.card_type or e.card_type
            self._on_identity_change(linked, ts)

        if old_zone != e.zone:
            if old_zone == "DECK" and e.zone == "HAND" and e.controller == self.state.current_player_pid:
                player = self.state.player(e.controller)
                key = "GHOSTDATA_DRAW_TURN"
                count = int(player.tags.get("GHOSTDATA_DRAWS", "0")) + 1 if player.tags.get(key) == str(self.state.global_turn) else 1
                player.tags[key] = str(self.state.global_turn); player.tags["GHOSTDATA_DRAWS"] = str(count)
                if count >= 2:
                    self.secret_tracker.observe_public_event(self.state, SecretObservation("SECOND_DRAW", actor_pid=e.controller))
            if old_zone == "DECK" and e.zone == "HAND" and e.controller == self.state.local_player_pid and e.card_id:
                self._last_drawn[e.controller] = e.card_id
            if e.zone != "DECK":
                e.tags.pop("GHOSTDATA_DECK_LOCATION", None)
                e.tags.pop("GHOSTDATA_DECK_INDEX", None)
            elif e.controller == self.state.local_player_pid:
                frames = self._effects if source == "canonical" else self._task_effects
                if frames and frames[-1].card_id in {"TIME_730", "VAC_444"}:
                    e.tags["GHOSTDATA_DECK_LOCATION"] = "BOTTOM" if frames[-1].card_id == "TIME_730" else "TOP"
                    frame = frames[-1]
                    if not frame.order_base:
                        self._deck_order += 100
                        frame.order_base = self._deck_order
                    e.tags["GHOSTDATA_DECK_INDEX"] = str(frame.order_base - frame.ordered_count)
                    frame.ordered_count += 1
            if old_zone == "PLAY" and e.zone == "GRAVEYARD" and e.card_type == "MINION":
                self.secret_tracker.observe_public_event(self.state, SecretObservation(
                    "MINION_DIED", actor_pid=self.state.current_player_pid,
                    target_pid=e.controller, target_entity_id=e.entity_id,
                    witness_ids=tuple(m.entity_id for m in self.state.board(e.controller) if m.card_type == "MINION")))
            if e.zone == "PLAY" and e.card_type in ("MINION", "LOCATION") and e.entered_play_sequence is None:
                self.state.play_sequence_counter += 1
                e.entered_play_sequence = self.state.play_sequence_counter
                e.entered_play_turn = self.state.global_turn
            self.secret_tracker.on_zone_change(self.state, e, old_zone, e.zone)
            self._emit(
                ts, "ZONE_CHANGE",
                f"Entity {e.entity_id}: {old_zone or '?'} -> {e.zone or '?'}",
                entity_id=e.entity_id, old_zone=old_zone or "", new_zone=e.zone or "",
                player=e.controller, card_id=e.card_id,
            )

        if e.card_id and self.card_db.ready:
            card = self.card_db.get(e.card_id)
            if card:
                e.name = e.name or card.name
                e.card_type = e.card_type or card.card_type
                e.card_class = e.card_class or card.card_class
                if e.cost is None:
                    e.cost = card.cost

    def _apply_tag_change(self, entity_raw: str, tag: str, value: str, ts: str, task_fallback: bool = False) -> None:
        ent, pid, name = self._resolve_entity_ref(entity_raw, ts=ts)
        source = "task" if task_fallback else "canonical"
        if ent is not None and pid is None:
            # Numeric/inline player entities can resolve to player IDs.
            for player_id, p in self.state.players.items():
                if p.entity_id == ent.entity_id:
                    pid = player_id
                    break

        if ent is not None and (pid is None or ent.card_type != "PLAYER"):
            self._apply_entity_tag(ent, tag, value, ts, source=source)
            # Some numeric entities are player entities even before CARDTYPE context is complete.
            for player_id, p in self.state.players.items():
                if p.entity_id == ent.entity_id:
                    pid = player_id
                    break

        if entity_raw.strip() in ("GameEntity", "1") and pid is None:
            token = ("G", tag, value)
            if source == "task" and self._consume_canonical_token(token):
                return
            if source == "canonical":
                self._record_canonical_token(token)
            self.state.game_tags[tag] = value
            if tag == "STEP" and value == "MAIN_END":
                self.secret_tracker.observe_public_event(self.state, SecretObservation("TURN_END", actor_pid=self.state.current_player_pid))
            if tag == "TURN":
                eliminated = self.secret_tracker.flush_pending_tests(self.state, reason="turn boundary")
                if eliminated:
                    self._emit(ts, "SECRET_UPDATE", f"Eliminated {eliminated} Secret candidate(s) at turn boundary")
                t = _to_int(value)
                if t is not None and t != self.state.global_turn:
                    self.state.global_turn = t
                    self._emit(ts, "GLOBAL_TURN", f"Global turn {t}", turn=t)
            elif tag in ("STEP", "NEXT_STEP") and value == "FINAL_GAMEOVER":
                self.secret_tracker.flush_pending_tests(self.state, reason="game over")
                if not self.state.complete:
                    self.state.complete = True
                    self.state.active = False
                    self._emit(ts, "GAME_OVER", "Final game over")
            elif tag == "STATE" and value == "COMPLETE":
                self.state.complete = True
                self.state.active = False
            return

        if pid is None and name:
            pid = self._resolve_named_pid(name)
        if pid is None:
            return

        token = ("P", pid, tag, value)
        if source == "task" and self._consume_canonical_token(token):
            return
        if source == "canonical":
            self._record_canonical_token(token)
        player = self.state.player(pid)
        player.tags[tag] = value
        if name and not player.name and name not in ("GameEntity", "UNKNOWN HUMAN PLAYER"):
            self.state.bind_name(name, pid)
        if tag == "HERO_ENTITY":
            player.hero_entity_id = _to_int(value)
        elif tag == "RESOURCES":
            player.resources = _to_int(value) or 0
        elif tag == "RESOURCES_USED":
            player.resources_used = _to_int(value) or 0
            if player.available_mana == 0 and pid == self.state.current_player_pid:
                self.secret_tracker.observe_public_event(self.state, SecretObservation("MANA_ZERO", actor_pid=pid))
        elif tag in ("TEMP_RESOURCES", "TEMPORARY_RESOURCES"):
            player.temp_resources = _to_int(value) or 0
        elif tag == "CURRENT_PLAYER":
            on = value == "1"
            was_current = player.current_player
            player.current_player = on
            if on:
                self.state.current_player_pid = pid
                for other_pid, other in self.state.players.items():
                    if other_pid != pid:
                        other.current_player = False
                if not was_current:
                    self.secret_tracker.observe_public_event(self.state, SecretObservation("TURN_START", actor_pid=pid))
        elif tag == "FIRST_PLAYER":
            if value == "1":
                player.first_player = True
                self.state.first_player_pid = pid
        elif tag == "TURN":
            new_turn = _to_int(value)
            if new_turn is not None and new_turn != player.local_turn:
                player.local_turn = new_turn
                self._emit(ts, "PLAYER_TURN", f"{player.name or 'P'+str(pid)} turn {player.local_turn}", player=pid, turn=player.local_turn)
        elif tag == "PLAYSTATE":
            previous = player.playstate
            terminal = {"WON", "LOST", "CONCEDED"}
            # TaskList can replay intermediate LOSING after a canonical terminal
            # state. Once terminal, do not regress the authoritative result.
            if previous in terminal and value not in terminal:
                return
            player.playstate = value
            if value in terminal and previous not in terminal:
                self._emit(ts, "PLAYSTATE", f"{player.name or 'P'+str(pid)} = {value}", player=pid, playstate=value, task_fallback=task_fallback)
                if self.state.local_player_pid is not None:
                    local_pid = self.state.local_player_pid
                    local = self.state.player(local_pid)
                    # Prefer an explicit terminal state on the local player.
                    if local.playstate == "WON":
                        self.state.result = "WIN"
                    elif local.playstate in ("LOST", "CONCEDED"):
                        self.state.result = "LOSS"
                    # Constructed Standard is a two-player game. A terminal
                    # opponent state is therefore also authoritative when the
                    # client reports it before (or instead of) a mirrored local
                    # terminal state. This is especially important for an
                    # opponent concession, which means the local player won.
                    elif pid != local_pid:
                        if value == "WON":
                            self.state.result = "LOSS"
                        elif value in ("LOST", "CONCEDED"):
                            self.state.result = "WIN"
                # A terminal local PLAYSTATE is itself authoritative proof that
                # the match has ended. Do not require a later GameEntity
                # FINAL_GAMEOVER/STATE=COMPLETE marker: current clients may omit,
                # delay, or format that secondary marker differently. Mark the
                # game complete at the first proven local result and emit the
                # semantic GAME_OVER event exactly once.
                if self.state.result and not self.state.complete:
                    self.state.complete = True
                    self.state.active = False
                    self.state.raw_counts["terminal_completion_playstate"] = self.state.raw_counts.get("terminal_completion_playstate", 0) + 1
                    self._emit(ts, "GAME_OVER", f"Terminal result from PLAYSTATE: {self.state.result}", completion_source="PLAYSTATE")
        elif tag == "MULLIGAN_STATE" and value == "DONE":
            for rec in self.state.mulligans.values():
                if rec.player_name == (player.name or name):
                    rec.completed = True

    # ---------- game metadata ----------
    def _parse_debug_game(self, payload: str, ts: str) -> None:
        m = RE_DEBUG_KV.fullmatch(payload)
        if m:
            key, value = m.group("key"), m.group("value")
            if key == "BuildNumber":
                build = _to_int(value)
                self.state.build_number = build
                if build and not self.card_db.ready:
                    self.card_db.load_for_build(build)
            elif key == "GameType":
                self.state.game_type = value
            elif key == "FormatType":
                self.state.format_type = value
            elif key == "ScenarioID":
                self.state.scenario_id = _to_int(value)
            return
        m = RE_DEBUG_PLAYER.fullmatch(payload)
        if m:
            pid = int(m.group("pid"))
            name = m.group("name").strip()
            if name != "UNKNOWN HUMAN PLAYER":
                self.state.bind_name(name, pid)
                if self.requested_local_name:
                    if name == self.requested_local_name:
                        self.state.local_player_pid = pid
                        self.state.local_player_name = name
                elif self.state.local_player_pid is None:
                    self.state.local_player_pid = pid
                    self.state.local_player_name = name
            return

    # ---------- choices / mulligan ----------
    def _parse_entity_choices(self, payload: str, ts: str) -> None:
        m = RE_CHOICE_HEADER.fullmatch(payload)
        if m:
            cid = int(m.group("id"))
            prompt = ChoicePrompt(
                choice_id=cid,
                player_name=m.group("player"),
                choice_type=m.group("type"),
                min_choices=int(m.group("min")),
                max_choices=int(m.group("max")),
            )
            self.state.choices[cid] = prompt
            self.state.current_choice_id = cid
            self._choice_context_id = cid
            if prompt.choice_type == "MULLIGAN":
                self.state.mulligans[cid] = MulliganRecord(
                    choice_id=cid,
                    player_name=prompt.player_name,
                    min_choices=prompt.min_choices,
                    max_choices=prompt.max_choices,
                )
            # Bind opponent name when it becomes available.
            if prompt.player_name not in ("UNKNOWN HUMAN PLAYER", self.state.local_player_name):
                self._resolve_named_pid(prompt.player_name)
            return
        m = RE_CHOICE_ENTITY.fullmatch(payload)
        if m and self._choice_context_id is not None:
            info = parse_inline_entity(m.group("entity"))
            if info:
                eid = int(info["entity_id"])
                self._update_entity_from_inline(m.group("entity"), ts=ts)
                prompt = self.state.choices.get(self._choice_context_id)
                if prompt is None:
                    # Orphaned choice detail can occur around client/log lifecycle
                    # boundaries. Fail soft instead of terminating live coaching.
                    self.state.raw_counts["orphan_choice_detail"] = self.state.raw_counts.get("orphan_choice_detail", 0) + 1
                    self._choice_context_id = None
                    return
                prompt.entity_ids.append(eid)
                rec = self.state.mulligans.get(self._choice_context_id)
                if rec:
                    ent = self.state.entity(eid)
                    if ent.card_id != "GAME_005" and ent.tags.get("COIN_CARD") != "1":
                        rec.offered_entity_ids.append(eid)
            return
        if payload.startswith("Source=") and self._choice_context_id is not None:
            raw = payload.split("=", 1)[1]
            info = parse_inline_entity(raw)
            if info:
                prompt = self.state.choices.get(self._choice_context_id)
                if prompt is None:
                    self.state.raw_counts["orphan_choice_source"] = self.state.raw_counts.get("orphan_choice_source", 0) + 1
                    self._choice_context_id = None
                    return
                prompt.source_entity_id = int(info["entity_id"])

    def _parse_entities_chosen(self, payload: str, ts: str) -> None:
        m = RE_CHOSEN_HEADER.fullmatch(payload)
        if m:
            cid = int(m.group("id"))
            self._chosen_context_id = cid
            player_name = m.group("player")
            if player_name not in ("UNKNOWN HUMAN PLAYER", self.state.local_player_name):
                self._resolve_named_pid(player_name)
            if cid in self.state.choices:
                if player_name != "UNKNOWN HUMAN PLAYER":
                    self.state.choices[cid].player_name = player_name
                if int(m.group("count")) == 0:
                    self.state.choices[cid].completed = True
            rec = self.state.mulligans.get(cid)
            if rec:
                if player_name != "UNKNOWN HUMAN PLAYER":
                    rec.player_name = player_name
                rec.expected_chosen_count = int(m.group("count"))
                if rec.expected_chosen_count == 0:
                    rec.completed = True
            return
        m = RE_CHOICE_ENTITY.fullmatch(payload)
        if m and self._chosen_context_id is not None:
            info = parse_inline_entity(m.group("entity"))
            if not info:
                return
            eid = int(info["entity_id"])
            self._update_entity_from_inline(m.group("entity"), ts=ts)
            prompt = self.state.choices.get(self._chosen_context_id)
            if prompt and eid not in prompt.chosen_entity_ids:
                prompt.chosen_entity_ids.append(eid)
                prompt.completed = True
            rec = self.state.mulligans.get(self._chosen_context_id)
            if rec:
                if eid not in rec.chosen_entity_ids:
                    rec.chosen_entity_ids.append(eid)
                if rec.expected_chosen_count is not None and len(rec.chosen_entity_ids) >= rec.expected_chosen_count:
                    rec.completed = True
            return

    def _parse_send_choices(self, payload: str, ts: str) -> None:
        m = RE_SEND_HEADER.fullmatch(payload)
        if m:
            self._send_context_id = int(m.group("id"))
            return
        m = RE_SEND_ENTITY.fullmatch(payload)
        if m and self._send_context_id is not None:
            info = parse_inline_entity(m.group("entity"))
            if not info:
                return
            eid = int(info["entity_id"])
            self._update_entity_from_inline(m.group("entity"), ts=ts)
            prompt = self.state.choices.get(self._send_context_id)
            if prompt and eid not in prompt.chosen_entity_ids:
                prompt.chosen_entity_ids.append(eid)
            rec = self.state.mulligans.get(self._send_context_id)
            if rec and eid not in rec.chosen_entity_ids:
                rec.chosen_entity_ids.append(eid)

    # ---------- legal options ----------
    def _parse_options(self, payload: str, ts: str) -> None:
        m = RE_OPTION_HEADER.fullmatch(payload)
        if m:
            # Options are printed only after the preceding action has settled.
            eliminated = self.secret_tracker.flush_pending_tests(self.state, reason="options boundary")
            if eliminated:
                self._emit(ts, "SECRET_UPDATE", f"Eliminated {eliminated} Secret candidate(s) before options")
            oid = int(m.group("id"))
            self.state.legal_options = LegalOptionSet(option_set_id=oid, timestamp=ts)
            self._current_option = None
            return
        m = RE_OPTION.fullmatch(payload)
        if m:
            info = parse_inline_entity(m.group("entity")) if m.group("entity") else None
            if info:
                self._update_entity_from_inline(m.group("entity"), ts=ts)
            opt = LegalOption(
                index=int(m.group("idx")),
                option_type=m.group("type"),
                main_entity_id=int(info["entity_id"]) if info else None,
                main_entity_name=str(info["name"]) if info else "",
                card_id=str(info["card_id"]) if info else "",
                error=m.group("error"),
                error_param=m.group("param"),
            )
            self.state.legal_options.options.append(opt)
            self._current_option = opt
            return
        m = RE_TARGET.fullmatch(payload)
        if m and self._current_option is not None:
            info = parse_inline_entity(m.group("entity")) if m.group("entity") else None
            if info:
                self._update_entity_from_inline(m.group("entity"), ts=ts)
            self._current_option.targets.append(
                OptionTarget(
                    index=int(m.group("idx")),
                    entity_id=int(info["entity_id"]) if info else None,
                    entity_name=str(info["name"]) if info else "",
                    card_id=str(info["card_id"]) if info else "",
                    error=m.group("error"),
                    error_param=m.group("param"),
                )
            )
            return
        m = RE_SUBOPTION.fullmatch(payload)
        if m and self._current_option is not None:
            info = parse_inline_entity(m.group("entity")) if m.group("entity") else None
            if info:
                self._update_entity_from_inline(m.group("entity"), ts=ts)
            self._current_option.sub_options.append(
                SubOption(
                    index=int(m.group("idx")),
                    entity_id=int(info["entity_id"]) if info else None,
                    entity_name=str(info["name"]) if info else "",
                    card_id=str(info["card_id"]) if info else "",
                    error=m.group("error"),
                    error_param=m.group("param"),
                )
            )
