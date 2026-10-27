"""Immutable player-visible history for card-effect previews.

Records are owned by GameState, so existing reset/rewind snapshots include them.
A death is a PLAY -> GRAVEYARD transition, never a discard, burn or shuffle.
"""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class CardObservation:
    kind: str
    entity_id: int
    card_id: str
    controller: int
    turn: int
    name: str = ""
    text: str = ""
    card_type: str = ""
    cost: int | None = None
    races: tuple[str, ...] = ()
    mechanics: tuple[str, ...] = ()
    spell_school: str = ""
    source: int = 0
    source_card_id: str = ""
    paid_cost: int | None = None
    components: tuple[str, ...] = ()
    source_instance: int = 0


def observe(game, entity, db, kind, source=None, turn=None, *, append=True, anonymous=False):
    if (not entity.card_id and not anonymous) or entity.controller not in (1, 2):
        return
    definition = None if anonymous else db.get(entity.card_id)
    if entity.controller != game.local_player_pid and kind == "PLAY" and (
            entity.zone == "SECRET" or definition and definition.is_secret) and entity.revealed is not True:
        return
    name = "Unknown card" if anonymous else definition.name if definition else entity.name or entity.card_id
    text = definition.text if definition else ""
    cost = definition.cost if definition else None
    races = definition.races if definition else ()
    mechanics = definition.mechanics if definition else ()
    components = ()
    if not anonymous and entity.tags.get("ASSEMBLED_MINION") == "1":
        try: rules = db.get_by_dbf(int(entity.tags.get("CRAFTABLE_SECOND_HALF_DBID", 0)))
        except (ValueError, TypeError): rules = None
        components = (entity.card_id, rules.card_id if rules else "")
        name += " + " + (rules.name if rules else "Unknown component")
        text = rules.text if rules else "Rules unavailable in local data."
        # Assembled bodies retain their constructed cost rather than reverting
        # to the ordinary printed card cost. Hand discounts aren't base stats.
        cost = entity.cost
        mechanics = rules.mechanics if rules else ()
    try: paid = int(entity.tags.get("TAG_LAST_KNOWN_COST_IN_HAND", entity.cost))
    except (ValueError, TypeError): paid = None
    record = CardObservation(kind, entity.entity_id, "" if anonymous else entity.card_id, entity.controller,
        game.global_turn if turn is None else turn, name, text,
        entity.card_type or (definition.card_type if definition else ""), cost,
        races, mechanics, definition.spell_school if definition else "",
        source.entity_id if source else 0, source.card_id if source else "", paid, components,
        int(source.tags.get("GHOSTDATA_INSTANCE", 0)) if source else 0)
    if append:
        game.card_history.append(record)
    return record


def refresh_metadata(game, db):
    """Fill definitions arriving after log ingestion without replaying events.

    Resolve the original observed identity, not the entity's later identity.
    Anonymous opposing cards remain anonymous.
    """
    def enrich(record):
        if record is None or not record.card_id:
            return record
        definition = db.get(record.card_id)
        if definition is None:
            return record
        rules = db.get(record.components[1]) if len(record.components) > 1 else None
        name, text, mechanics = definition.name, definition.text, definition.mechanics
        if record.components:
            name += " + " + (rules.name if rules else "Unknown component")
            text = rules.text if rules else record.text
            mechanics = rules.mechanics if rules else record.mechanics
        return replace(record,
            name=name if not record.name or record.name == record.card_id or record.components else record.name,
            text=text if not record.text or record.components else record.text,
            card_type=record.card_type or definition.card_type,
            cost=record.cost if record.cost is not None or record.components else definition.cost,
            races=record.races or definition.races,
            mechanics=record.mechanics or mechanics,
            spell_school=record.spell_school or definition.spell_school)
    game.card_history[:] = [enrich(record) for record in game.card_history]
    game.stored_card_details = {eid: tuple(enrich(record) for record in records)
                                for eid, records in game.stored_card_details.items()}
