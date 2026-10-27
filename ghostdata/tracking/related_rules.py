"""Explicit Standard mechanic contracts over immutable public observations.

Lists are candidate pools, not random-outcome predictions. Retain multiplicity
unless the card explicitly requests different cards; never infer from names.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class HistoryRule:
    kind: str = "DEATH"
    card_type: str = ""
    race: str = ""
    mechanic: str = ""
    school: str = ""
    minimum: int | None = None
    maximum: int | None = None
    highest: bool = False
    distinct: bool = False
    turn: str = "game"
    opponent: bool = False
    exclude_self: bool = False
    only_id: str = ""
    last: int = 0
    source_id: str = ""
    label: str = "Observed resurrection candidates; selection and board space apply"


RULES = {
    "EDR_455": HistoryRule(race="DRAGON", distinct=True, label="Observed friendly Dragons available to Discover"),
    "EDR_238": HistoryRule(minimum=8, distinct=True, label="Different friendly minions costing 8+ that died; board space applies"),
    "EDR_891": HistoryRule(mechanic="DEATHRATTLE", maximum=4, label="Current resurrection pool; one is selected and copied"),
    "EDR_892": HistoryRule(mechanic="DEATHRATTLE", minimum=5, exclude_self=True, label="Current resurrection pool excluding this card type; one is selected and copied"),
    "CORE_CATA_002": HistoryRule(highest=True, label="Highest-Cost friendly minions that died; ties are random"),
    "TIME_616": HistoryRule(race="UNDEAD", highest=True, label="Highest-Cost friendly Undead that died; ties are random"),
    "TLC_818": HistoryRule(minimum=1, maximum=3, label="Resurrection candidates: one each at Costs 1, 2 and 3"),
    "BE_017t5": HistoryRule(mechanic="DEATHRATTLE", distinct=True, label="Different Deathrattle candidates; up to 4 are selected"),
    "TIME_852t3": HistoryRule(race="DRAGON", label="Friendly Dragons that died; board space applies"),
    "CAP_806": HistoryRule(kind="REBORN", label="Friendly minions that were Reborn; board space and random targets apply"),
    "JAIL_940": HistoryRule(mechanic="DEATHRATTLE", label="Minions whose Deathrattle may be selected at random"),
    "TLC_106": HistoryRule(mechanic="DEATHRATTLE", label="Observed Deathrattle pool; up to 5 are triggered"),
    "EDR_491": HistoryRule(mechanic="DEATHRATTLE", turn="current", label="Friendly minions with Deathrattles that died this turn"),
    "MEND_805": HistoryRule(turn="current", label="Friendly minions that died this turn; copies get +3/+3"),
    "TIME_619": HistoryRule(only_id="TIME_619t", label="Observed Bwonsamdi resurrection candidates; otherwise draws him"),
    "CORE_TRL_345": HistoryRule(kind="PLAY", card_type="SPELL", turn="previous_friendly", label="Spells played on your previous turn; hand space applies"),
    "TRL_345": HistoryRule(kind="PLAY", card_type="SPELL", turn="previous_friendly", label="Spells played on your previous turn; hand space applies"),
    "TLC_430": HistoryRule(kind="PLAY", card_type="SPELL", school="HOLY", turn="current", label="Holy spells cast this turn; one is selected at random"),
    "JAIL_500": HistoryRule(kind="PLAY", turn="current", exclude_self=True, label="Other cards played this turn; replay targets and order are not predicted"),
    "CATA_560": HistoryRule(kind="PLAY", card_type="MINION", minimum=1, maximum=1, label="1-Cost minions played this game; board space applies"),
    "DINO_407": HistoryRule(kind="PLAY", card_type="MINION", opponent=True, last=1, label="Last publicly played opposing minion"),
    "THD_040hpb": HistoryRule(kind="PLAY", card_type="SPELL", last=1, label="Last observed spell played"),
    "TOT_343": HistoryRule(kind="PLAY", opponent=True, last=2, label="Last two publicly played opposing cards"),
    "TOT_108": HistoryRule(kind="PLAY", distinct=True, label="Previously played spells and minions; Combo determines the second Discover"),
    "JAIL_887t2": HistoryRule(kind="DISCARD", source_id="JAIL_887", label="Observed prison discards; one card is selected each turn"),
    "JAIL_887": HistoryRule(kind="DISCARD", source_id="JAIL_887", label="Cards discarded by a prison this game"),
    # These conditional/counter cards expose the relevant history in addition
    # to the current description supplied by the visible client card.
    "EDR_430": HistoryRule(label="Friendly minions that died this game"),
    "EDR_941": HistoryRule(label="Friendly minions that died this game"),
    "END_009": HistoryRule(race="TREANT", label="Friendly Treants that died this game"),
    "EDR_465": HistoryRule(only_id="EDR_465", label="Observed Ysondre deaths; Dragon summons are random"),
    "EDR_812": HistoryRule(kind="PLAY", last=1, label="Last card played; its runes determine the bonus"),
    "CATA_616": HistoryRule(kind="PLAY", last=1, label="Last card played; its cost determines the reduction"),
    "CATA_493": HistoryRule(kind="DISCARD", label="Observed cards discarded this game"),
    "CATA_529": HistoryRule(kind="PLAY", card_type="SPELL", school="FEL", label="Fel spells played this game"),
    "BE_564": HistoryRule(turn="current", label="Friendly minions that died this turn"),
    "BE_565": HistoryRule(turn="current", label="Friendly minions that died this turn"),
    "BE_877": HistoryRule(turn="current", label="Friendly minions that died this turn"),
    "JAIL_445": HistoryRule(turn="current", label="Friendly minions that died this turn"),
    "JAIL_909": HistoryRule(kind="PLAY", turn="current", exclude_self=True, label="Other cards played this turn"),
}


def select_history(game, entity, rule):
    pid = game.opponent_pid if rule.opponent else entity.controller
    turn = None
    if rule.turn == "current": turn = game.global_turn
    if rule.turn == "previous_friendly":
        turns = [t for t, owner in game.turn_owners.items() if owner == pid and t < game.global_turn]
        turn = max(turns, default=-1)
    records = [h for h in game.card_history if h.kind == rule.kind and h.controller == pid
        and (turn is None or h.turn == turn)
        and (not rule.card_type or h.card_type == rule.card_type)
        and (not rule.race or rule.race in h.races or rule.race != "TREANT" and "ALL" in h.races)
        and (not rule.mechanic or rule.mechanic in h.mechanics)
        and (not rule.school or h.spell_school == rule.school)
        and (rule.minimum is None or h.cost is not None and h.cost >= rule.minimum)
        and (rule.maximum is None or h.cost is not None and h.cost <= rule.maximum)
        and (not rule.exclude_self or h.card_id != entity.card_id)
        and (not rule.only_id or h.card_id == rule.only_id)
        and (not rule.source_id or h.source_card_id == rule.source_id)]
    if entity.card_id == "TOT_108": records = [h for h in records if h.card_type in {"MINION", "SPELL"}]
    if rule.highest:
        maximum = max((h.cost for h in records if h.cost is not None), default=None)
        records = [h for h in records if maximum is not None and h.cost == maximum]
    if rule.distinct:
        seen = set()
        records = [h for h in records if not ((key := (h.card_id, h.components)) in seen or seen.add(key))]
    return records[-rule.last:] if rule.last else records
