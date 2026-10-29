"""Verified deck identities bound to a particular log session and game."""
from dataclasses import asdict
import json
from pathlib import Path
from .deck_sensor import _atomic_write_json
from .models import DeckSnapshot
from .paths import data_paths


def _path(data_dir):
    return data_paths(data_dir).root / "match_decks.json"


def load(data_dir=None):
    try:
        value = json.loads(_path(data_dir).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def key(source, game_number, clock):
    return str(Path(source).resolve().parent).casefold() + "|" + str(game_number) + "|" + clock


def bind(source, game, deck, data_dir=None):
    if not source or not game.active or game.complete or game.game_number < 1:
        return False
    if not getattr(deck, "game_context", False) or deck.sensor_status != "EXACT" or deck.format != "STANDARD":
        return False
    player = game.players.get(game.local_player_pid)
    if player is None or deck.player_class != (player.starting_class or player.player_class):
        return False
    bindings = load(data_dir)
    clock = game.game_tags.get("GHOSTDATA_GAME_START", "")
    if len(clock) != 8:
        return False
    identity = key(source, game.game_number, clock)
    # A changed selection must never rewrite the identity of an existing game.
    if identity in bindings:
        return False
    bindings[identity] = {k: v for k, v in asdict(deck).items()
                          if k not in {"cards", "sideboards", "hero_card_ids"}}
    _atomic_write_json(_path(data_dir), dict(list(bindings.items())[-2000:]))
    return True


def lookup(bindings, source, match):
    value = bindings.get(key(source, match.game_index, match.started_at[11:19]))
    try:
        deck = DeckSnapshot(**value) if isinstance(value, dict) else None
    except TypeError:
        return None
    return deck if deck and deck.game_context and deck.player_class == match.player_class else None
