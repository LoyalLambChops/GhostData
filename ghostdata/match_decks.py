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


PREGAME_HANDOFF_MAX_AGE_SECONDS = 10.0


def is_fresh_pregame_handoff(deck, game, request_game_number, age_seconds):
    """Allow only a fresh lobby selection to cross into its just-started match."""
    try:
        age = float(age_seconds)
    except (TypeError, ValueError):
        return False
    return (
        request_game_number == 0
        and 0.0 <= age <= PREGAME_HANDOFF_MAX_AGE_SECONDS
        and bool(game.active)
        and not game.complete
        and game.game_number >= 1
        and not getattr(deck, "game_context", False)
        and deck.sensor_status == "EXACT"
        and str(deck.format).upper() == "STANDARD"
    )


def bind(source, game, deck, data_dir=None, *, request_game_number=None, request_age_seconds=None):
    if not source or not game.active or game.complete or game.game_number < 1:
        return False
    if deck.sensor_status != "EXACT" or str(deck.format).upper() != "STANDARD":
        return False
    binding_source = "IN_GAME_CONTEXT"
    if not getattr(deck, "game_context", False):
        if not is_fresh_pregame_handoff(deck, game, request_game_number, request_age_seconds):
            return False
        binding_source = "FRESH_PREGAME"
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
    binding = {k: v for k, v in asdict(deck).items()
               if k not in {"cards", "sideboards", "hero_card_ids"}}
    # Keep sensor fact and match-link evidence separate.
    binding["_match_binding_source"] = binding_source
    bindings[identity] = binding
    _atomic_write_json(_path(data_dir), dict(list(bindings.items())[-2000:]))
    return True


def lookup(bindings, source, match):
    value = bindings.get(key(source, match.game_index, match.started_at[11:19]))
    if not isinstance(value, dict):
        return None
    binding = dict(value)
    binding_source = binding.pop("_match_binding_source", "")
    try:
        deck = DeckSnapshot(**binding)
    except TypeError:
        return None
    trusted_link = deck.game_context or binding_source == "FRESH_PREGAME"
    return deck if trusted_link and deck.player_class == match.player_class else None
