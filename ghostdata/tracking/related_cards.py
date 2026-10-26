"""Per-entity related cards from observed game relationships, never hidden identities."""
from dataclasses import dataclass

@dataclass(frozen=True)
class RelatedCard:
    card_id: str
    name: str
    text: str = ""
    count: int = 1


def number(entity, key):
    try: return int(entity.tags.get(key, 0))
    except (ValueError, TypeError): return 0


def related_cards(game, entity, db):
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
        source = game.entities.get(anchor.creator or anchor.displayed_creator or 0)
        if not source or source.card_id != "CAP_805":
            return (), "Stored minions unavailable: the creating effect was not observed."
        if anchor.entity_id in game.stored_card_pools:
            captured = game.stored_card_pools[anchor.entity_id]
            return rows(captured), "Stored minions (summoned in this order; board space still applies)" if captured else "No minions stored by this cast."
        stop = min((e.entity_id for e in game.entities.values()
                    if e.entity_id > anchor.entity_id and e.card_id == "CAP_805t"
                    and (e.creator or e.displayed_creator) == source.entity_id), default=2**31)
        stored = sorted((e for e in game.entities.values()
                         if anchor.entity_id < e.entity_id < stop
                         and e.creator == source.entity_id and e.controller == anchor.controller
                         and e.card_type == "MINION" and e.copied_from_entity_id), key=lambda e:e.entity_id)
        return rows([e.card_id for e in stored]), "Stored minions (summoned in this order; board space still applies)" if stored else "No stored minions observed."
    # Explicitly linked set-aside entities are useful across mechanics. Do not
    # treat a shared creator alone as a storage relationship or a complete pool.
    stored = sorted((e for e in game.entities.values() if e.zone == "SETASIDE"
                     and e.controller == game.local_player_pid and e.card_id
                     and e.card_type in {"MINION", "SPELL", "WEAPON", "LOCATION"}
                     and number(e, "LINKED_ENTITY") == entity.entity_id), key=lambda e:e.entity_id)
    if stored: return rows([e.card_id for e in stored]), "Linked cards observed"
    return (), ""
