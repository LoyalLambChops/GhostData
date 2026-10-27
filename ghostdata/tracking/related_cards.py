"""Per-entity related cards from observed game relationships, never hidden identities."""
from dataclasses import dataclass
from .related_rules import RULES, select_history
from .card_references import visible_references
from .deck_previews import DECK_RULES, deck_candidates, bottom_candidates
from .public_effects import _FIXED, base_id
from .card_history import observe as observe_card

@dataclass(frozen=True)
class RelatedCard:
    card_id: str
    name: str
    text: str = ""
    count: int = 1


def number(entity, key):
    try: return int(entity.tags.get(key, 0))
    except (ValueError, TypeError): return 0


def related_cards(game, entity, db, known_deck=None):
    if entity.controller != game.local_player_pid or not entity.card_id:
        return (), ""
    def rows(cards):
        result = []
        for cid in cards:
            definition = db.get(cid)
            result.append(RelatedCard(cid, definition.name if definition else cid or "Unknown minion",
                                      definition.text if definition else ""))
        return tuple(result)
    # Each Ectoplasm's script anchor identifies its original token, including
    # copies. Its stored minions follow that anchor in the creating spell's
    # entity sequence. Keep duplicates/order and never mix the other board.
    if entity.card_id == "CAP_805t":
        anchor = game.entities.get(number(entity, "TAG_SCRIPT_DATA_NUM_2"))
        if anchor is None and entity.copied_from_entity_id:
            anchor = game.entities.get(entity.copied_from_entity_id)
        anchor = anchor or entity
        if anchor.entity_id in game.stored_card_pools:
            captured = game.stored_card_pools[anchor.entity_id]
            details = game.stored_card_details.get(anchor.entity_id, ())
            shown = tuple(RelatedCard(h.card_id,h.name,h.text) for h in details if h) if details else rows(captured)
            return shown, "Stored minions (summoned in this order; board space still applies)" if captured else "No minions stored by this cast."
        source = game.entities.get(anchor.creator or anchor.displayed_creator or 0)
        if not source or source.card_id != "CAP_805":
            return (), "Stored minions unavailable: the creating effect was not observed."
        stop = min((e.entity_id for e in game.entities.values()
                    if e.entity_id > anchor.entity_id and e.card_id == "CAP_805t"
                    and (e.creator or e.displayed_creator) == source.entity_id), default=2**31)
        stored = sorted((e for e in game.entities.values()
                         if anchor.entity_id < e.entity_id < stop
                         and e.creator == source.entity_id and e.controller == anchor.controller
                         and e.card_type == "MINION" and e.copied_from_entity_id), key=lambda e:e.entity_id)
        return rows([e.card_id for e in stored]), "Stored minions (summoned in this order; board space still applies)" if stored else "No stored minions observed."
    references = visible_references(game, entity, db)
    if references and (entity.card_id not in RULES or entity.card_id in {"JAIL_887", "JAIL_887t2"}):
        result = []
        for cid, eid in references:
            target = game.entities.get(eid)
            captured = observe_card(game, target, db, "REFERENCE", append=False) if target else None
            result.extend([RelatedCard(captured.card_id,captured.name,captured.text)] if captured else rows([cid]))
        return tuple(result), "Cards referenced by this card's current effects"
    if entity.card_id in {"EDR_454t", "TLC_841t"}:
        if entity.entity_id in game.stored_card_pools:
            return rows(game.stored_card_pools[entity.entity_id]), "Stored minion released by this card"
    if entity.card_id in {"EDR_494", "CATA_897", "CATA_481"}:
        kind = {"EDR_494":"CONSUMED", "CATA_897":"DISCARD", "CATA_481":"CAPTURED"}[entity.card_id]
        source = entity.entity_id
        history = [h for h in game.card_history if h.kind == kind and h.source == source
                   and h.source_instance == number(entity, "GHOSTDATA_INSTANCE")]
        return tuple(RelatedCard(h.card_id,h.name,h.text) for h in history), "Observed contents of this card; returned on Deathrattle"
    if entity.card_id in RULES:
        rule = RULES[entity.card_id]
        history = select_history(game, entity, rule)
        records = tuple(RelatedCard(h.card_id, h.name, h.text) for h in history)
        return records, rule.label + ("" if records else " — none observed")
    if entity.card_id == "TIME_714":
        opponent_turns = [t for t, pid in game.turn_owners.items() if pid == game.opponent_pid and t < game.global_turn]
        turn = max(opponent_turns, default=-1)
        played = {h.entity_id for h in game.card_history if h.kind == "PLAY" and h.controller == game.opponent_pid and h.turn == turn}
        targets = [e.card_id for e in game.board(game.opponent_pid) if e.card_type == "MINION" and e.entity_id in played]
        return rows(targets), "Opposing minions still in play from their previous turn"
    if entity.card_id == "TIME_620":
        targets = [e.card_id for e in game.board(entity.controller) if e.card_type == "MINION"
                   and e.last_played_turn is not None and e.last_played_turn + 1 == game.global_turn]
        return rows(targets), "Currently eligible friendly minions; the Secret still requires a qualifying death"
    if entity.card_id in {"TIME_618", "TIME_618t"}:
        hero = game.hero(entity.controller)
        return rows([hero.card_id] if hero and hero.card_id else []), "Your hero; resurrection Health depends on corpses available when the Deathrattle resolves"
    if entity.card_id == "TIME_103":
        played = {h.card_id for h in game.card_history if h.kind == "PLAY" and h.controller == entity.controller}
        deck = known_deck if known_deck is not None else [e.card_id for e in game.entities.values()
                 if e.zone == "DECK" and e.controller == entity.controller and e.card_id]
        return rows([cid for cid in deck if cid in played]), "Tracked remaining deck copies of previously played cards; unknown identities are omitted"
    if entity.card_id in DECK_RULES:
        candidates, label = deck_candidates(entity, db, known_deck)
        return rows(candidates), label
    if entity.card_id in {"JAIL_510", "TIME_023"}:
        candidates, label = bottom_candidates(game, entity, db)
        return rows(candidates), label
    if entity.card_id in {"TLC_433t", "TLC_433t2"}:
        return rows(["TLC_433t2" if entity.card_id == "TLC_433t" else "TLC_433t"]), "Deathrattle creates"
    if entity.card_id in {"EDR_819", "CORE_RLK_086", "RLK_086"}:
        history = [h for h in game.card_history if h.kind == "DEATH" and h.source == entity.entity_id
                   and h.source_instance == number(entity, "GHOSTDATA_INSTANCE")]
        return tuple(RelatedCard(h.card_id,h.name,h.text) for h in history), "Observed minions killed by this instance; board space applies"
    # Explicitly linked set-aside entities are useful across mechanics. Do not
    # treat a shared creator alone as a storage relationship or a complete pool.
    stored = sorted((e for e in game.entities.values() if e.zone == "SETASIDE"
                     and e.controller == game.local_player_pid and e.card_id
                     and e.card_type in {"MINION", "SPELL", "WEAPON", "LOCATION"}
                     and number(e, "LINKED_ENTITY") == entity.entity_id), key=lambda e:e.entity_id)
    if stored: return rows([e.card_id for e in stored]), "Linked cards observed"
    # Fixed generated identities are effect possibilities, never evidence that
    # the effect has resolved or that all capped creations will occur.
    fixed = [_FIXED[key] for key in ((base_id(entity.card_id), "POWER"),
             (base_id(entity.card_id), "TRIGGER")) if key in _FIXED]
    if fixed:
        cid, cap, location = fixed[0]
        definition = db.get(cid)
        if definition and definition.card_type in {"MINION", "SPELL", "WEAPON", "LOCATION"}:
            return (RelatedCard(cid, definition.name, definition.text, cap),), (
                f"Effect can create up to {cap}; trigger conditions and available space apply"
                + ("; placed on the bottom of the deck" if location == "BOTTOM" else ""))
    return (), ""
