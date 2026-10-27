"""Resolve only reference tags whose client text-builder contract is known.

Script values are not universally entity IDs: some are counts, DBF IDs or races.
This module never interprets arbitrary numeric script data as card identities.
"""
import re

ENTITY_BUILDERS = {
    "DRUSTVAR_HORROR": (1, 2),
    "REFERENCE_SCRIPT_DATA_NUM_1_ENTITY": (1,),
    "REFERENCE_SCRIPT_DATA_NUM_1_ENTITY_POWER": (1,),
    "REFERENCE_SCRIPT_DATA_NUM_1_NUM_2_ENTITY": (1, 2),
    "REFERENCE_SCRIPT_DATA_NUM_1_NUM_2_ENTITY_POWER": (1, 2),
    "ALT_TEXT_REFERENCE_SCRIPT_DATA_NUM_1_NUM_2_ENTITY_POWER": (1, 2),
}
DBF_BUILDERS = {"REFERENCE_SCRIPT_DATA_NUM_1_CARD_DBID": (1,),
                "MULTIPLE_ALT_TEXT_SCRIPT_DATA_NUMS_REF_SDN6_CARD_DBID": (6,)}


def visible_references(game, owner, db):
    if owner.controller != game.local_player_pid:
        return ()
    attached = sorted((e for e in game.entities.values() if e.card_type == "ENCHANTMENT"
                       and e.zone not in {"GRAVEYARD", "REMOVEDFROMGAME"}
                       and e.tags.get("ATTACHED") == str(owner.entity_id)), key=lambda e:e.entity_id)
    result, seen = [], set()
    for entity in (owner, *attached):
        definition = db.get(entity.card_id)
        builder = definition.text_builder if definition else ""
        slots = {int(v) for v in re.findall(r"\{(\d+)(?:[^{}]*)\}", definition.text)} if definition else set()
        tags = [f"TAG_SCRIPT_DATA_NUM_{i}" for i in ENTITY_BUILDERS.get(builder, ()) if i-1 in slots]
        if builder == "MULTIPLE_ENTITY_NAMES":
            tags = [f"CARDTEXT_ENTITY_{i}" for i in range(10) if i in slots]
        for tag in tags:
            try: eid = int(entity.tags.get(tag, 0))
            except (TypeError, ValueError): continue
            target = game.entities.get(eid)
            # Identity must already be in our visible history. No memory reads
            # of the referenced entity and no opposing private-zone identities.
            if not target or not target.card_id or (target.controller != owner.controller
                    and target.zone not in {"PLAY", "GRAVEYARD"}):
                continue
            if ("entity",entity.entity_id,tag,eid) not in seen:
                seen.add(("entity",entity.entity_id,tag,eid));result.append((target.card_id,eid))
        for index in DBF_BUILDERS.get(builder, ()):
            if index-1 not in slots: continue
            try: dbf = int(entity.tags.get(f"TAG_SCRIPT_DATA_NUM_{index}", 0))
            except (TypeError, ValueError): continue
            target = db.get_by_dbf(dbf) if dbf > 0 else None
            if target and ("dbf", entity.entity_id, index) not in seen:
                seen.add(("dbf",entity.entity_id,index));result.append((target.card_id,0))
    return tuple(result)
