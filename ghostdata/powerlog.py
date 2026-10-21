from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
import os
import re
from typing import Iterable

from .models import CardEvent, MatchRecord

CREATE_MARKER = "GameState.DebugPrintPower() - CREATE_GAME"
GAMESTATE_POWER = "GameState.DebugPrintPower() - "
TASK_POWER = "PowerTaskList.DebugPrintPower() - "
DEBUG_GAME = "GameState.DebugPrintGame() - "
ENTITY_CHOICES = "GameState.DebugPrintEntityChoices() - "
ENTITIES_CHOSEN = "GameState.DebugPrintEntitiesChosen() - "
SEND_CHOICES = "GameState.SendChoices() - "

RE_TIME = re.compile(r"^[DVIWE]\s+(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?")
RE_PLAYER = re.compile(r"Player EntityID=(\d+) PlayerID=(\d+)")
RE_DEBUG_PLAYER = re.compile(r"PlayerID=(\d+), PlayerName=(.+)$")
RE_DEBUG_KV = re.compile(r"(BuildNumber|GameType|FormatType|ScenarioID)=(.+)$")
RE_INLINE = re.compile(
    r"\[entityName=(?P<name>.*?) id=(?P<entity>\d+) zone=(?P<zone>\w+) "
    r"zonePos=(?P<pos>\d+) cardId=(?P<card>.*?) player=(?P<player>\d+)\]"
)
RE_FULL_ID = re.compile(r"FULL_ENTITY - (?:Creating|Updating).*?(?:ID=|id=)(\d+).*?CardID=(\S*)", re.I)
RE_SHOW = re.compile(r"SHOW_ENTITY - Updating Entity=(?P<entity>.+?) CardID=(?P<card>[A-Za-z0-9_]+)")
RE_CONTEXT_TAG = re.compile(r"tag=(?P<tag>[A-Z0-9_]+|\d+) value=(?P<value>.*)$")
RE_TAG_CHANGE = re.compile(r"TAG_CHANGE Entity=(?P<entity>.+?) tag=(?P<tag>[A-Z0-9_]+|\d+) value=(?P<value>.*?)\s*$")
RE_BLOCK_PLAY = re.compile(r"BLOCK_START BlockType=PLAY Entity=(?P<entity>.*?) EffectCardId=")
RE_CHOICE_HEADER = re.compile(
    r"id=(?P<id>\d+) Player=(?P<player>.*?) TaskList=\d+ ChoiceType=(?P<type>\w+) CountMin=(?P<min>\d+) CountMax=(?P<max>\d+)"
)
RE_CHOICE_ENTITY = re.compile(r"Entities\[\d+\]=(?P<entity>\[.*\])")
RE_CHOSEN_HEADER = re.compile(r"id=(?P<id>\d+) Player=(?P<player>.*?) EntitiesCount=(?P<count>\d+)")
RE_SEND_HEADER = re.compile(r"id=(?P<id>\d+) ChoiceType=(?P<type>\w+)")
RE_SEND_ENTITY = re.compile(r"m_chosenEntities\[\d+\]=(?P<entity>\[.*\])")
SESSION_RE = re.compile(r"Hearthstone_(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})", re.I)


@dataclass(slots=True)
class Entity:
    entity_id: int
    name: str = ""
    card_id: str = ""
    controller: int = 0
    zone: str = ""
    card_type: str = ""
    hero_class: str = ""
    tags: dict[str, str] = field(default_factory=dict)

    def merge_inline(self, raw: str) -> bool:
        info = parse_inline(raw)
        if not info or info["entity_id"] != self.entity_id:
            return False
        self.controller = info["controller"] or self.controller
        self.zone = info["zone"] or self.zone
        if info["card_id"]:
            self.card_id = info["card_id"]
        if _useful_name(info["name"]):
            self.name = info["name"]
        return True


@dataclass(slots=True)
class Player:
    pid: int
    entity_id: int = 0
    name: str = ""
    hero_entity_id: int = 0
    first: bool = False
    playstate: str = ""


@dataclass(slots=True)
class Choice:
    choice_id: int
    player_name: str = ""
    choice_type: str = ""
    offered: list[int] = field(default_factory=list)
    chosen: list[int] = field(default_factory=list)


@dataclass(slots=True)
class PlayEvent:
    turn: int
    entity_id: int
    controller: int
    inline_public: bool


@dataclass(slots=True)
class ZoneEvent:
    turn: int
    entity_id: int
    controller: int
    old_zone: str
    new_zone: str
    after_mulligan: bool


class GameParser:
    def __init__(self) -> None:
        self.entities: dict[int, Entity] = {}
        self.players: dict[int, Player] = {}
        self.player_entity_to_pid: dict[int, int] = {}
        self.player_name_to_pid: dict[str, int] = {}
        self.debug_player_order: list[int] = []
        self.choices: dict[int, Choice] = {}
        self.local_choice_id: int | None = None
        self.local_pid: int | None = None
        self.first_pid: int | None = None
        self.result = ""
        self.format = "STANDARD"
        self.game_type = ""
        self.build_number = ""
        self.turn = 0
        self.main_started = False
        self.context_entity: int | None = None
        self.task_context_entity: int | None = None
        self.choice_context: int | None = None
        self.chosen_context: int | None = None
        self.send_context: int | None = None
        self.public_reveals: set[int] = set()
        self.play_events: list[PlayEvent] = []
        self.zone_events: list[ZoneEvent] = []
        self.start_clock: float | None = None
        self.end_clock: float | None = None
        self.terminal_line_index: int | None = None

    def entity(self, entity_id: int) -> Entity:
        if entity_id not in self.entities:
            self.entities[entity_id] = Entity(entity_id)
        return self.entities[entity_id]

    def player(self, pid: int) -> Player:
        if pid not in self.players:
            self.players[pid] = Player(pid)
        return self.players[pid]

    def parse(self, lines: list[str]) -> None:
        for index, line in enumerate(lines):
            if self.start_clock is None:
                self.start_clock = line_clock_seconds(line)
            if GAMESTATE_POWER in line:
                self._power(line.split(GAMESTATE_POWER, 1)[1].rstrip(), canonical=True, index=index, raw_line=line)
            elif TASK_POWER in line:
                self._power(line.split(TASK_POWER, 1)[1].rstrip(), canonical=False, index=index, raw_line=line)
            elif DEBUG_GAME in line:
                self._debug_game(line.split(DEBUG_GAME, 1)[1].strip())
            elif ENTITY_CHOICES in line:
                self._entity_choices(line.split(ENTITY_CHOICES, 1)[1].strip())
            elif ENTITIES_CHOSEN in line:
                self._entities_chosen(line.split(ENTITIES_CHOSEN, 1)[1].strip())
            elif SEND_CHOICES in line:
                self._send_choices(line.split(SEND_CHOICES, 1)[1].strip())
        self._resolve_local_pid()
        self._resolve_result()

    def _power(self, payload: str, *, canonical: bool, index: int, raw_line: str) -> None:
        p = payload.strip()
        if not p:
            return
        context_attr = "context_entity" if canonical else "task_context_entity"
        context_id = getattr(self, context_attr)
        m = RE_CONTEXT_TAG.fullmatch(p)
        if m and context_id is not None:
            self._entity_tag(self.entity(context_id), m.group("tag"), m.group("value"))
            return
        setattr(self, context_attr, None)

        m = RE_PLAYER.search(p)
        if m:
            eid, pid = int(m.group(1)), int(m.group(2))
            player = self.player(pid)
            player.entity_id = eid
            self.player_entity_to_pid[eid] = pid
            ent = self.entity(eid)
            ent.controller = pid
            ent.card_type = "PLAYER"
            setattr(self, context_attr, eid)
            return

        m = RE_FULL_ID.search(p)
        if m:
            eid = int(m.group(1))
            ent = self.entity(eid)
            inline = RE_INLINE.search(p)
            if inline:
                self._merge_inline(ent, inline.group(0))
            card = m.group(2) or ""
            if card:
                ent.card_id = card
            setattr(self, context_attr, eid)
            return

        m = RE_SHOW.search(p)
        if m:
            raw = m.group("entity")
            info = parse_inline(raw)
            if info:
                ent = self.entity(info["entity_id"])
                self._merge_inline(ent, raw)
                ent.card_id = m.group("card") or ent.card_id
                self.public_reveals.add(ent.entity_id)
                setattr(self, context_attr, ent.entity_id)
            elif raw.strip().isdigit():
                eid = int(raw.strip())
                self.entity(eid).card_id = m.group("card")
                self.public_reveals.add(eid)
                setattr(self, context_attr, eid)
            return

        m = RE_TAG_CHANGE.search(p)
        if m:
            self._tag_change(m.group("entity"), m.group("tag"), m.group("value"), index=index, raw_line=raw_line)
            return

        if canonical:
            m = RE_BLOCK_PLAY.search(p)
            if m:
                info = parse_inline(m.group("entity"))
                if info:
                    ent = self.entity(info["entity_id"])
                    self._merge_inline(ent, m.group("entity"))
                    inline_public = bool(info["card_id"] or _useful_name(info["name"]))
                    self.play_events.append(PlayEvent(self.turn, ent.entity_id, ent.controller, inline_public))
                return

    def _merge_inline(self, ent: Entity, raw: str) -> None:
        ent.merge_inline(raw)
        ent.hero_class = ent.hero_class or class_from_card_id(ent.card_id)

    def _entity_tag(self, ent: Entity, tag: str, value: str) -> None:
        value = value.strip()
        old_zone = ent.zone
        ent.tags[tag] = value
        if tag == "CONTROLLER":
            ent.controller = _int(value)
        elif tag == "ZONE":
            ent.zone = value
        elif tag == "CARDTYPE":
            ent.card_type = value
        elif tag == "CLASS":
            ent.hero_class = value
        elif tag == "HERO_ENTITY" and ent.card_type == "PLAYER":
            pid = self.player_entity_to_pid.get(ent.entity_id) or ent.controller
            if pid:
                self.player(pid).hero_entity_id = _int(value)
        if ent.card_id and not ent.hero_class:
            ent.hero_class = class_from_card_id(ent.card_id)
        if tag == "ZONE" and old_zone != ent.zone:
            self.zone_events.append(ZoneEvent(self.turn, ent.entity_id, ent.controller, old_zone, ent.zone, self.main_started))

    def _tag_change(self, entity_raw: str, tag: str, value: str, *, index: int, raw_line: str) -> None:
        value = value.strip()
        raw = entity_raw.strip()
        info = parse_inline(raw)
        ent: Entity | None = None
        pid: int | None = None
        if info:
            ent = self.entity(info["entity_id"])
            self._merge_inline(ent, raw)
            pid = self.player_entity_to_pid.get(ent.entity_id)
            if pid is None and ent.card_type == "PLAYER":
                pid = ent.controller
        elif raw.isdigit():
            eid = int(raw)
            ent = self.entity(eid)
            pid = self.player_entity_to_pid.get(eid)
        elif raw == "GameEntity":
            pass
        else:
            pid = self.player_name_to_pid.get(raw)

        if ent is not None and (pid is None or ent.card_type != "PLAYER"):
            self._entity_tag(ent, tag, value)
            if pid is None:
                pid = self.player_entity_to_pid.get(ent.entity_id)

        if raw in {"GameEntity", "1"} and pid is None:
            if tag == "TURN":
                self.turn = max(self.turn, _int(value))
            elif tag in {"STEP", "NEXT_STEP"} and value in {"MAIN_READY", "MAIN_START", "MAIN_ACTION"}:
                self.main_started = True
            return

        if pid is None:
            return
        player = self.player(pid)
        if tag == "HERO_ENTITY":
            player.hero_entity_id = _int(value)
        elif tag == "FIRST_PLAYER" and value == "1":
            player.first = True
            self.first_pid = pid
        elif tag == "PLAYSTATE":
            player.playstate = value
            if value in {"WON", "LOST", "CONCEDED"} and self.terminal_line_index is None:
                self.terminal_line_index = index
                self.end_clock = line_clock_seconds(raw_line)

    def _debug_game(self, payload: str) -> None:
        m = RE_DEBUG_KV.fullmatch(payload)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if key == "BuildNumber": self.build_number = value
            elif key == "GameType": self.game_type = value
            elif key == "FormatType": self.format = value.replace("FT_", "")
            return
        m = RE_DEBUG_PLAYER.fullmatch(payload)
        if not m:
            return
        pid, name = int(m.group(1)), m.group(2).strip()
        player = self.player(pid)
        if name and name != "UNKNOWN HUMAN PLAYER":
            player.name = name
            self.player_name_to_pid[name] = pid
            if pid not in self.debug_player_order:
                self.debug_player_order.append(pid)

    def _entity_choices(self, payload: str) -> None:
        m = RE_CHOICE_HEADER.fullmatch(payload)
        if m:
            cid = int(m.group("id"))
            self.choices[cid] = Choice(cid, m.group("player").strip(), m.group("type").strip())
            self.choice_context = cid
            return
        m = RE_CHOICE_ENTITY.fullmatch(payload)
        if m and self.choice_context in self.choices:
            info = parse_inline(m.group("entity"))
            if info:
                ent = self.entity(info["entity_id"])
                self._merge_inline(ent, m.group("entity"))
                if ent.card_id != "GAME_005":
                    self.choices[self.choice_context].offered.append(ent.entity_id)

    def _entities_chosen(self, payload: str) -> None:
        m = RE_CHOSEN_HEADER.fullmatch(payload)
        if m:
            self.chosen_context = int(m.group("id"))
            return
        m = RE_CHOICE_ENTITY.fullmatch(payload)
        if m and self.chosen_context in self.choices:
            info = parse_inline(m.group("entity"))
            if info:
                ent = self.entity(info["entity_id"])
                self._merge_inline(ent, m.group("entity"))
                if ent.entity_id not in self.choices[self.chosen_context].chosen:
                    self.choices[self.chosen_context].chosen.append(ent.entity_id)

    def _send_choices(self, payload: str) -> None:
        m = RE_SEND_HEADER.fullmatch(payload)
        if m:
            self.send_context = int(m.group("id"))
            if m.group("type") == "MULLIGAN":
                self.local_choice_id = self.send_context
            return
        m = RE_SEND_ENTITY.fullmatch(payload)
        if m and self.send_context in self.choices:
            info = parse_inline(m.group("entity"))
            if info:
                ent = self.entity(info["entity_id"])
                self._merge_inline(ent, m.group("entity"))
                if ent.entity_id not in self.choices[self.send_context].chosen:
                    self.choices[self.send_context].chosen.append(ent.entity_id)
                if self.local_pid is None and ent.controller:
                    self.local_pid = ent.controller

    def _resolve_local_pid(self) -> None:
        if self.local_pid is not None:
            return
        if self.local_choice_id in self.choices:
            choice = self.choices[self.local_choice_id]
            for eid in choice.offered + choice.chosen:
                controller = self.entity(eid).controller
                if controller:
                    self.local_pid = controller
                    return
            pid = self.player_name_to_pid.get(choice.player_name)
            if pid:
                self.local_pid = pid
                return
        if self.debug_player_order:
            self.local_pid = self.debug_player_order[0]
        elif self.players:
            self.local_pid = sorted(self.players)[0]

    def _resolve_result(self) -> None:
        if self.local_pid is None:
            return
        local = self.players.get(self.local_pid)
        if local and local.playstate == "WON": self.result = "WIN"
        elif local and local.playstate in {"LOST", "CONCEDED"}: self.result = "LOSS"
        if self.result:
            return
        for pid, player in self.players.items():
            if pid == self.local_pid:
                continue
            if player.playstate == "WON": self.result = "LOSS"
            elif player.playstate in {"LOST", "CONCEDED"}: self.result = "WIN"
            if self.result:
                return

    def class_for_pid(self, pid: int | None) -> str:
        if not pid:
            return ""
        player = self.players.get(pid)
        if not player:
            return ""
        if player.hero_entity_id:
            hero = self.entities.get(player.hero_entity_id)
            if hero:
                return hero.hero_class or class_from_card_id(hero.card_id)
        for ent in self.entities.values():
            if ent.controller == pid and ent.card_id.startswith("HERO_"):
                value = ent.hero_class or class_from_card_id(ent.card_id)
                if value:
                    return value
        return ""

    def build_match(self, lines: list[str], source: Path, game_index: int) -> MatchRecord | None:
        self.parse(lines)
        if not self.result or self.local_pid is None:
            return None
        if self.format and self.format != "STANDARD":
            return None
        opponent_pids = [pid for pid in self.players if pid != self.local_pid]
        opponent_pid = opponent_pids[0] if len(opponent_pids) == 1 else None
        local_class = self.class_for_pid(self.local_pid)
        opponent_class = self.class_for_pid(opponent_pid)
        initiative = "FIRST" if self.first_pid == self.local_pid else "SECOND" if self.first_pid else ""
        start = started_at(source, lines)
        duration = duration_seconds(self.start_clock, self.end_clock)
        end = ended_at(start, duration)
        stable_end = self.terminal_line_index if self.terminal_line_index is not None else len(lines) - 1
        fingerprint = sha256("".join(lines[: stable_end + 1]).encode("utf-8", "replace")).hexdigest()[:32]
        offered, kept, replaced = self._mulligan()
        drawn = self._draw_history(self.local_pid)
        played = self._play_history(self.local_pid, public_only=False)
        observed = self._play_history(opponent_pid, public_only=True) if opponent_pid else []
        quality = "LIMITED"
        return MatchRecord(
            match_id="match_" + fingerprint,
            started_at=start,
            result=self.result,
            player_class=local_class,
            opponent_class=opponent_class,
            initiative=initiative,
            ended_at=end,
            format=self.format or "STANDARD",
            hearthstone_build=self.build_number,
            game_type=self.game_type,
            turn_count=self.turn,
            duration_seconds=duration,
            mulligan_offered=offered,
            mulligan_kept=kept,
            mulligan_replaced=replaced,
            cards_drawn=drawn,
            cards_played=played,
            opponent_observed=observed,
            data_quality=quality,
            source_session=source.parent.name,
            game_index=game_index,
        )

    def _mulligan(self) -> tuple[list[str], list[str], list[str]]:
        choice = self.choices.get(self.local_choice_id or -1)
        if choice is None and self.local_pid:
            for candidate in self.choices.values():
                controllers = {self.entity(eid).controller for eid in candidate.offered}
                if self.local_pid in controllers and candidate.choice_type == "MULLIGAN":
                    choice = candidate
                    break
        if choice is None:
            return [], [], []
        offered_ids = [eid for eid in choice.offered if self.entity(eid).card_id != "GAME_005"]
        chosen = set(choice.chosen)
        offered = [self._card_label(eid) for eid in offered_ids]
        kept = [self._card_label(eid) for eid in offered_ids if eid in chosen]
        replaced = [self._card_label(eid) for eid in offered_ids if eid not in chosen]
        return [x for x in offered if x], [x for x in kept if x], [x for x in replaced if x]

    def _draw_history(self, pid: int) -> list[CardEvent]:
        out: list[CardEvent] = []
        seen: set[tuple[int, int]] = set()
        for event in self.zone_events:
            if event.controller != pid or not event.after_mulligan:
                continue
            if event.old_zone != "DECK" or event.new_zone != "HAND":
                continue
            key = (event.turn, event.entity_id)
            if key in seen:
                continue
            seen.add(key)
            ent = self.entities.get(event.entity_id)
            if not ent:
                continue
            label = ent.name or ent.card_id
            if label:
                out.append(CardEvent(event.turn, ent.card_id, label))
        return out

    def _play_history(self, pid: int | None, *, public_only: bool) -> list[CardEvent]:
        if pid is None:
            return []
        out: list[CardEvent] = []
        seen: set[int] = set()
        for event in self.play_events:
            if event.controller != pid or event.entity_id in seen:
                continue
            ent = self.entities.get(event.entity_id)
            if not ent:
                continue
            if public_only and not (event.inline_public or event.entity_id in self.public_reveals):
                continue
            label = ent.name or ent.card_id
            if not label or label.upper().startswith("UNKNOWN ENTITY"):
                continue
            seen.add(event.entity_id)
            out.append(CardEvent(event.turn, ent.card_id, label))
        return out

    def _card_label(self, eid: int) -> str:
        ent = self.entities.get(eid)
        if not ent:
            return ""
        return ent.name or ent.card_id or f"Card {eid}"


def _useful_name(name: str) -> bool:
    value = (name or "").strip()
    return bool(value and not value.upper().startswith("UNKNOWN ENTITY"))


def _int(value: object) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def parse_inline(raw: str) -> dict[str, object] | None:
    m = RE_INLINE.search(raw)
    if not m:
        return None
    return {
        "entity_id": int(m.group("entity")),
        "name": m.group("name").strip(),
        "zone": m.group("zone").strip(),
        "zone_position": int(m.group("pos")),
        "card_id": m.group("card").strip(),
        "controller": int(m.group("player")),
    }


def class_from_card_id(card_id: str) -> str:
    m = re.match(r"HERO_(\d{2})", str(card_id or ""))
    if not m:
        return ""
    return {
        "01": "WARRIOR", "02": "SHAMAN", "03": "ROGUE", "04": "PALADIN",
        "05": "HUNTER", "06": "DRUID", "07": "WARLOCK", "08": "MAGE",
        "09": "PRIEST", "10": "DEMON_HUNTER", "11": "DEATH_KNIGHT",
    }.get(m.group(1), "")


def line_clock_seconds(line: str) -> float | None:
    m = RE_TIME.match(line)
    if not m:
        return None
    h, minute, second = map(int, m.groups()[:3])
    fraction = float("0." + (m.group(4) or "0"))
    return h * 3600 + minute * 60 + second + fraction


def duration_seconds(start: float | None, end: float | None) -> int:
    if start is None or end is None:
        return 0
    delta = end - start
    if delta < 0:
        delta += 24 * 3600
    if delta < 0 or delta > 8 * 3600:
        return 0
    return int(round(delta))


def started_at(path: Path, lines: list[str]) -> str:
    anchor: datetime | None = None
    session_anchor = False
    for part in reversed(path.parts):
        m = SESSION_RE.search(part)
        if m:
            try:
                anchor = datetime(*map(int, m.groups()))
                session_anchor = True
            except ValueError:
                pass
            break
    if anchor is None:
        try:
            anchor = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            anchor = datetime.now()
    clock = next((line_clock_seconds(line) for line in lines if line_clock_seconds(line) is not None), None)
    if clock is not None:
        h = int(clock // 3600)
        minute = int((clock % 3600) // 60)
        second = int(clock % 60)
        micros = int(round((clock - int(clock)) * 1_000_000))
        if micros >= 1_000_000:
            micros = 999_999
        candidate = anchor.replace(hour=h, minute=minute, second=second, microsecond=micros)
        if session_anchor:
            # A dated Hearthstone session folder records when the client session
            # began, not when each later game began. A later clock on the same
            # date is therefore expected. Only advance a day when the embedded
            # clock wrapped materially behind the session-start clock.
            if candidate < anchor - timedelta(minutes=5):
                candidate += timedelta(days=1)
        elif candidate > anchor + timedelta(minutes=5):
            # Without a dated session folder, file mtime is the best available
            # date anchor and log content cannot legitimately post-date it by
            # hours (copied historical fixtures are the usual case).
            candidate -= timedelta(days=1)
        anchor = candidate
    return anchor.astimezone().isoformat()


def ended_at(started: str, duration: int) -> str:
    if not started:
        return ""
    try:
        dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return (dt + timedelta(seconds=max(0, duration))).isoformat()


def split_games(path: Path) -> list[list[str]]:
    games: list[list[str]] = []
    current: list[str] = []
    with Path(path).open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if CREATE_MARKER in line:
                if current:
                    games.append(current)
                current = [line]
            elif current:
                current.append(line)
    if current:
        games.append(current)
    return games


def discover_power_logs(path: Path | None = None) -> list[Path]:
    """Return every readable Hearthstone Power log in deterministic order.

    A Hearthstone client restart creates a new dated session folder/Power.log.
    GhostData therefore treats the Logs tree as an append-only set of sources
    rather than assuming that the newest file contains all history.
    """
    if path is not None:
        p = Path(path).expanduser()
        if p.is_file():
            return [p.resolve()]
        if p.is_dir():
            try:
                candidates = [
                    x.resolve()
                    for x in p.rglob("Power*.log")
                    if x.is_file()
                ]
            except OSError:
                return []
            return _sort_power_logs(candidates)
        return []

    roots = [
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Hearthstone" / "Logs",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Hearthstone" / "Logs",
    ]
    candidates: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        try:
            rows = root.rglob("Power*.log")
            for candidate in rows:
                if not candidate.is_file():
                    continue
                resolved = candidate.resolve()
                key = os.path.normcase(str(resolved))
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(resolved)
        except OSError:
            continue
    return _sort_power_logs(candidates)


def _sort_power_logs(candidates: Iterable[Path]) -> list[Path]:
    def key(path: Path):
        match = SESSION_RE.search(path.parent.name)
        if match:
            return (0, tuple(int(x) for x in match.groups()), str(path).lower())
        try:
            return (1, (int(path.stat().st_mtime_ns),), str(path).lower())
        except OSError:
            return (2, (0,), str(path).lower())
    return sorted(dict.fromkeys(candidates), key=key)


def resolve_power_log(path: Path | None = None) -> Path | None:
    """Compatibility helper: return the newest discovered Power log."""
    candidates = discover_power_logs(path)
    return candidates[-1] if candidates else None


def parse_completed_games(path: Path) -> list[MatchRecord]:
    from .tracking.timeline import effective_game_lines
    source = Path(path).resolve()
    records: list[MatchRecord] = []
    for index, lines in enumerate(split_games(source), 1):
        match = GameParser().build_match(effective_game_lines(lines), source, index)
        if match is not None:
            records.append(match)
    return records
