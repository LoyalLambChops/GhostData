"""Deck previews from reconciled inventory and explicitly observed placements.

Never read arbitrary private deck identities. Candidate lists preserve copies;
random selections and unresolved bottom slots are not predicted.
"""
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class DeckRule:
    card_type: str = ""
    races: tuple[str, ...] = ()
    school: str = ""
    exclude_self: bool = False
    label: str = "Tracked deck candidates; selection is not predicted"


DECK_RULES = {
    "EDR_226": DeckRule("MINION", ("BEAST",)),
    "EDR_572": DeckRule("MINION", ("DRAGON",)),
    "END_003": DeckRule("MINION", ("UNDEAD",)),
    "CORE_KAR_061": DeckRule("MINION", ("BEAST", "DRAGON", "MURLOC"),
        label="Tracked Beast, Dragon and Murloc candidates; one of each is drawn"),
    "CORE_CFM_344": DeckRule("MINION", ("MURLOC",),
        label="Tracked Murloc summon candidates; requires an attack that kills a minion"),
    "FIR_929": DeckRule("SPELL", school="FIRE"),
    "TLC_223": DeckRule("SPELL", school="FIRE"),
    "RLK_511": DeckRule("SPELL", school="FROST"),
    "TLC_226": DeckRule("SPELL"),
    "BE_EVENT_101": DeckRule("SPELL"),
    "JAIL_882": DeckRule("SPELL", label="Tracked spells copied by the Battlecry; Deathrattle draws one"),
    "BE_250": DeckRule("SPELL", label="Tracked spells moved to the top; their resulting order is unknown"),
    "BE_143": DeckRule("SPELL", school="HOLY", label="Tracked Holy spells whose copies are shuffled into the deck"),
    "CORE_DS1_184": DeckRule(label="Tracked deck Discover candidates; offered choices are not predicted"),
    "TLC_515": DeckRule(label="Tracked deck Discover candidates; offered choices are not predicted"),
    "TLC_451": DeckRule(exclude_self=True, label="Tracked other-card Discover candidates; offered choices are not predicted"),
    "TIME_701": DeckRule(label="Tracked deck Discover candidates; the unchosen offers go to the bottom"),
    "CATA_591": DeckRule(label="Tracked candidates for future deck Discovers; deck changes still apply"),
    "BE_EVENT_100": DeckRule("MINION"),
    "BE_208": DeckRule("MINION"),
    "EDR_856": DeckRule("MINION", label="Tracked minion Discover candidates; offered choices are not predicted"),
    "FIR_941": DeckRule("MINION"),
    "TIME_003": DeckRule("MINION"),
    "TIME_037": DeckRule("MINION"),
    "TIME_870": DeckRule("MINION"),
    "TIME_750": DeckRule("MINION", label="Tracked minion draw candidates; requires holding a minion that costs (5) or more"),
    "CATA_820": DeckRule("MINION"),
    "JAIL_866": DeckRule("MINION"),
}


def deck_candidates(entity, db, known_deck):
    rule = DECK_RULES[entity.card_id]
    if known_deck is None:
        return (), "Deck candidates unavailable until the deck inventory is tracked."
    result = []
    missing = 0
    for cid in known_deck:
        card = db.get(cid)
        if card is None:
            missing += 1
            continue
        if rule.card_type and card.card_type != rule.card_type: continue
        if rule.races and not set(card.races).intersection((*rule.races, "ALL")): continue
        if rule.school and card.spell_school != rule.school: continue
        if rule.exclude_self and cid == entity.card_id: continue
        result.append(cid)
    label = rule.label + "; unknown deck identities are omitted"
    if missing: label += f"; {missing} card definition(s) unavailable"
    if not result: label += " — no tracked matches"
    return tuple(result), label


def bottom_candidates(game, entity, db):
    """Newest explicitly appended batches occupy the deepest deck slots.

    A batch has no inferred internal order. If it crosses the requested depth,
    all matching members are candidates, with the ambiguity stated explicitly.
    Dredge observations without a placement batch do not establish an order.
    """
    depth = 3 if entity.card_id == "JAIL_510" else 2
    slots = min(depth, game.deck_count(entity.controller))
    groups = defaultdict(list)
    for card in game.entities.values():
        if card.controller != entity.controller or card.zone != "DECK": continue
        if card.tags.get("GHOSTDATA_DECK_LOCATION") != "BOTTOM": continue
        try: batch = int(card.tags.get("GHOSTDATA_BOTTOM_BATCH", "0"))
        except (ValueError, TypeError): continue
        if batch > 0: groups[batch].append(card)
    result = []
    unresolved = slots
    ambiguous = False
    for batch in sorted(groups, reverse=True):
        if not unresolved: break
        cards = groups[batch]
        take = min(unresolved, len(cards))
        ambiguous |= len(cards) > take
        for card in cards:
            # Captured at the public placement; HIDE/zone changes clear it.
            cid = card.tags.get("GHOSTDATA_BOTTOM_CARD", "")
            if card.card_id != cid: cid = ""
            definition = db.get(cid) if cid else None
            if not definition: continue
            if entity.card_id == "JAIL_510" and (
                definition.card_type != "MINION" or not set(definition.races).intersection({"DEMON", "ALL"})):
                continue
            result.append(cid)
        # Unknown identities in a known batch are still unresolved information.
        unknown = sum(not db.get(c.tags.get("GHOSTDATA_BOTTOM_CARD", ""))
                      or c.card_id != c.tags.get("GHOSTDATA_BOTTOM_CARD", "") for c in cards)
        unresolved -= take
        if unknown: ambiguous = True
    label = f"Observed bottom-{depth} " + ("Demon candidates" if entity.card_id == "JAIL_510" else "draw candidates")
    if unresolved: label += f"; {unresolved} position(s) not observed"
    if ambiguous: label += "; batch order or identities unresolved, listed cards are possible outcomes"
    elif not unresolved: label += "; within these positions, order not predicted"
    if entity.card_id == "JAIL_510": label += "; board space applies"
    if not result: label += " — no known candidates"
    return tuple(result), label
