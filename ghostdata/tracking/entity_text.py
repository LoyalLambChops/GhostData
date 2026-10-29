"""Resolve locally observed modular card wording without guessing missing parts."""
import re


def card_text(entity, database):
    card = database.get(entity.card_id)
    if card is None:
        return ""
    text = card.text
    if card.text_builder != "MODULAR_ENTITY":
        return text
    def part(match):
        value = entity.tags.get("MODULAR_ENTITY_PART_" + str(int(match[1]) + 1), "")
        definition = database.get_by_dbf(int(value)) if str(value).isdigit() else None
        return definition.text if definition else match[0]
    return re.sub(r"\{(\d+)\}", part, text)
