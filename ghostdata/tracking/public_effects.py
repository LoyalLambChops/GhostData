"""Small, public-information rules for cards created by a resolved effect.

Rules describe outcomes, not hidden card data. A prediction is attached only to
an actual new playable entity in that effect's block. A nested unrelated effect
cannot consume its parent's predictions, and unused predictions expire.
"""
from collections import deque
from dataclasses import dataclass, field


def base_id(card_id):
    return card_id[5:] if card_id.upper().startswith("CORE_") else card_id


# (source, block) -> (created identity, maximum creations, deck placement).
# Counts are caps: conditional effects must actually create their entities.
_FIXED = {
    ("REV_952", "TRIGGER"): ("CS2_101t", 2, ""),
    ("LOE_012", "TRIGGER"): ("GAME_005", 2, ""),
    ("TLC_630", "TRIGGER"): ("TLC_630t", 1, ""),
    ("JAIL_730", "TRIGGER"): ("JAIL_732", 1, ""),
    ("JAIL_733", "TRIGGER"): ("JAIL_732", 1, ""),
    ("END_025e", "TRIGGER"): ("END_025", 1, ""),
    ("EDR_978", "TRIGGER"): ("EDR_978", 1, "BOTTOM"),
    ("JAIL_399", "TRIGGER"): ("JAIL_399t1", 2, "BOTTOM"),
    ("TLC_241", "TRIGGER"): ("TLC_241t", 1, ""),
    ("TIME_875t", "TRIGGER"): ("TIME_875t", 1, ""),
    ("LOE_079", "POWER"): ("LOE_019t", 1, ""),
    ("LOE_019t", "POWER"): ("LOE_019t2", 1, ""),
    ("ICC_069", "POWER"): ("CS2_027", 1, ""),
    ("LOOT_026", "POWER"): ("LOOT_026e", 3, ""),
    ("TRL_900", "POWER"): ("TRL_348t", 10, ""),
    ("SW_439", "POWER"): ("SW_439t", 4, ""),
    ("SW_108", "POWER"): ("SW_108t", 1, ""),
    ("REV_601t", "POWER"): ("REV_601", 1, ""),
    ("REV_951", "POWER"): ("REV_951t", 3, ""),
    ("UNG_018", "POWER"): ("UNG_809t1", 1, ""),
    ("EDR_871", "POWER"): ("EDR_851t", 1, ""),
    ("TLC_902", "POWER"): ("TLC_630t", 2, ""),
    ("MEND_100", "POWER"): ("MEND_100t", 1, ""),
    ("JAIL_447", "POWER"): ("JAIL_447t", 1, ""),
    ("JAIL_720", "POWER"): ("GAME_005", 1, ""),
    ("JAIL_891", "POWER"): ("JAIL_732", 1, ""),
    ("BE_153", "POWER"): ("BE_153t", 1, ""),
}

# Public constraints on random outcomes. Empty identity is intentional: these
# rows can describe a known generated card without naming a hidden result.
_CONSTRAINED = {
    "CATA_136": ("Unknown 8+ Cost minion", None, 5),
    "CATA_190t13": ("Unknown Legendary Dragon", 1, 5),
    "WORK_004": ("Unknown class card", 1, 10),
}

LATORVIUS_REWARDS = ("UNG_116t", "UNG_920t1", "UNG_028t", "UNG_954t1",
                     "UNG_940t8", "UNG_067t1", "UNG_942t", "UNG_829t1", "UNG_934t1")


@dataclass
class EffectFrame:
    source: int = 0
    controller: int | None = None
    card_id: str = ""
    kind: str = ""
    expected: deque = field(default_factory=deque)
    location: str = ""
    hide_reveals: bool = False
    candidates: list[int] = field(default_factory=list)
    label: str = ""
    cost: int | None = None
    concealed: set[int] = field(default_factory=set)
    pool: tuple[str, ...] = ()
    order_base: int = 0
    ordered_count: int = 0
    slimed_minions: dict = field(default_factory=dict)
    stored_target: str = ""


def effect_frame(entity, kind, target, game, last_drawn, played):
    if entity is None:
        return EffectFrame(kind=kind)
    cid = base_id(entity.card_id)
    frame = EffectFrame(entity.entity_id, entity.controller, cid, kind,
                        hide_reveals=cid == "CATA_720" and kind == "POWER")
    if kind not in {"POWER", "TRIGGER"}:
        return frame
    if kind == "POWER" and cid == "TLC_602t":
        frame.pool = LATORVIUS_REWARDS
        return frame
    if kind == "POWER" and cid in _CONSTRAINED:
        frame.label, frame.cost, count = _CONSTRAINED[cid]
        frame.expected.extend([""] * count)
        return frame
    rule = _FIXED.get((cid, kind))
    if rule:
        result, count, frame.location = rule
        frame.expected.extend([result] * count)
    elif kind == "POWER" and cid in {"GIL_828", "LOOT_516"} and target and target.card_id:
        frame.expected.extend([target.card_id] * (3 if cid == "GIL_828" else 1))
    elif kind == "TRIGGER" and cid in {"ICC_082", "ICC_289"} and target and target.card_id:
        frame.expected.extend([target.card_id] * (2 if cid == "ICC_082" else 1))
    elif kind == "TRIGGER" and cid == "SCH_717":
        # The local draw is visible; the opponent's draw is not.
        if entity.controller == game.opponent_pid and last_drawn.get(game.local_player_pid):
            frame.expected.append(last_drawn[game.local_player_pid])
    elif kind == "TRIGGER" and cid == "SCH_706":
        frame.expected.extend(card for pid, turn, card in played
                              if pid != entity.controller and turn == game.global_turn)
    elif kind == "POWER" and cid == "DMF_733":
        frame.expected.extend(("DMF_057", "DMF_058"))
    elif kind == "POWER" and cid == "EDR_874":
        frame.expected.extend(("Core_CS2_008", "EX1_173"))
    return frame
