"""Local-player effect counters sourced from authoritative game tags.

Never infer Herald triggers from played cards: repeated effects and Deathrattles
can change its amount independently. Unknown values are deliberately explicit.
"""
from dataclasses import dataclass

HERALD_CARDS = frozenset("CATA_150 CATA_151 CATA_155 CATA_726 CATA_153 CATA_154 CATA_725 CATA_722 CATA_492 CATA_525 CATA_497 CATA_530 CATA_561 CATA_565 CATA_580 CATA_156 CATA_158 CATA_160 CATA_785 CATA_780 CATA_190h".split())

@dataclass(frozen=True)
class EffectCounter:
    key: str
    name: str
    value: str
    detail: str


def counters(game, local_pid, baseline_ids=()):
    if not game or not game.active or game.complete or local_pid not in game.players:
        return ()
    tags = game.players[local_pid].tags
    # Exclude temporary choice entities, even on the local player's side.
    known = set(baseline_ids)
    known.update(e.card_id for e in game.entities.values()
                 if e.controller == local_pid and e.zone in {"HAND", "DECK", "PLAY", "GRAVEYARD"})
    result = []
    def amount(tag):
        try:
            value = int(tags[tag])
            return value if value >= 0 else None
        except (KeyError, ValueError, TypeError):
            return None
    deaths = amount("NUM_FRIENDLY_MINIONS_THAT_DIED_THIS_GAME")
    # A complete log starts all cumulative counters at zero. A partial attach
    # must wait for an authoritative tag rather than inventing a count.
    if deaths is None and game.game_tags.get("GHOSTDATA_GAME_START"):
        deaths = sum(1 for event in game.card_history
                     if event.kind == "DEATH" and event.controller == local_pid
                     and event.card_type == "MINION")
    if "EDR_430" in known:
        result.append(EffectCounter("aessina", "Aessina", "? / 20" if deaths is None else f"{deaths} / 20",
            "Waiting for game data" if deaths is None else "Ready" if deaths >= 20 else f"{20-deaths} friendly death{'s' if deaths != 19 else ''} remaining"))
    elif "EDR_941" in known:
        result.append(EffectCounter("friendly_deaths", "Friendly minions died", "?" if deaths is None else str(deaths), "Starsurge Ã‚Â· this game"))
    if known & HERALD_CARDS or "HERALD_COLOSSAL_AMOUNT" in tags:
        value = amount("HERALD_COLOSSAL_AMOUNT")
        if value is None and game.game_tags.get("GHOSTDATA_GAME_START"):
            value = 0
        result.append(EffectCounter("herald", "Herald", "?" if value is None else str(value),
            "Waiting for game data" if value is None else "Herald effects triggered"))
    return tuple(result)
