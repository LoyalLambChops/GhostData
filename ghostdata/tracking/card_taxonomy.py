from __future__ import annotations

from typing import Optional

from .card_db import CardDatabase, CardDefinition
from .models import EntityState

# Constructed Hearthstone's five playable card types.  These are the only
# card-type families eligible for the Deck Tracker's card-history rails.
PLAYABLE_CARD_TYPES = frozenset({"MINION", "SPELL", "WEAPON", "HERO", "LOCATION"})

# Engine/client entities that may have names/CardIDs but are not cards played
# from a Constructed deck/hand and must never become deck-history rows.
NON_RAIL_CARD_TYPES = frozenset({
    "", "INVALID", "GAME", "PLAYER", "HERO_POWER", "ENCHANTMENT", "PET",
})

# Hero-zone effects are SPELL cards mechanically, but they have persistent
# state that deserves a separate state surface from generic card history.
HERO_ZONE_KINDS = frozenset({
    "SECRET", "QUEST", "QUESTLINE", "SIDEQUEST", "OBJECTIVE", "AURA", "SIGIL",
})


def _mechanics(card: Optional[CardDefinition]) -> set[str]:
    return {str(x or "").upper() for x in (card.mechanics if card else ())}


def resolved_card_definition(entity: EntityState, card_db: CardDatabase):
    if not entity.card_id:
        return None
    try:
        return card_db.get(entity.card_id)
    except Exception:
        return None


def resolved_card_type(entity: EntityState, card_db: CardDatabase) -> str:
    direct = str(entity.card_type or "").upper()
    if direct and direct != "INVALID":
        return direct
    card = resolved_card_definition(entity, card_db)
    return str(card.card_type or "").upper() if card else ""


def is_playable_card_entity(entity: EntityState, card_db: CardDatabase) -> bool:
    return resolved_card_type(entity, card_db) in PLAYABLE_CARD_TYPES


def hero_zone_effect_kind(entity: EntityState, card_db: CardDatabase) -> str:
    """Classify persistent hero-zone spell effects without guessing identity.

    Quest/Secret/Aura/etc. are mechanics on SPELL cards, not additional main
    card types.  Power.log sometimes exposes only entity tags, while the local
    card-definition cache may expose mechanics, so use both.  This function is
    intentionally generic across classes because Priest copy/steal and Mage
    generation can surface effects outside their native class pools.
    """
    tags = {str(k or "").upper(): str(v or "") for k, v in entity.tags.items()}
    card = resolved_card_definition(entity, card_db)
    mechanics = _mechanics(card)

    # Most-specific first.  Questline/Sidequest are Quest-family mechanics but
    # should not be flattened because their lifecycle/progress semantics differ.
    if "QUESTLINE" in mechanics or tags.get("QUESTLINE") == "1":
        return "QUESTLINE"
    if "SIDE_QUEST" in mechanics or "SIDEQUEST" in mechanics or tags.get("SIDE_QUEST") == "1":
        return "SIDEQUEST"
    if "QUEST" in mechanics or tags.get("QUEST") == "1":
        return "QUEST"
    if "SECRET" in mechanics:
        return "SECRET"
    if "SIGIL" in mechanics or tags.get("SIGIL") == "1":
        return "SIGIL"
    if (
        "PALADIN_AURA" in mechanics
        or "AURA" in mechanics
        or tags.get("PALADIN_AURA") == "1"
        or tags.get("AURA") == "1"
    ):
        return "AURA"
    if "OBJECTIVE" in mechanics or tags.get("OBJECTIVE") == "1":
        return "OBJECTIVE"

    # A hidden entity in SECRET zone with no public identity is still known to
    # be a Secret-like hero-zone slot.  Known Quests/Objectives are caught above.
    if str(entity.zone or "").upper() == "SECRET":
        return "SECRET"
    return ""


def is_hero_zone_effect(entity: EntityState, card_db: CardDatabase) -> bool:
    return bool(hero_zone_effect_kind(entity, card_db))


def quest_progress(entity: EntityState) -> tuple[int | None, int | None]:
    """Best-effort current/total progress from named Power.log tags.

    Tag naming can vary by client build.  Missing values remain None rather than
    being inferred from card text.
    """
    tags = {str(k or "").upper(): str(v or "") for k, v in entity.tags.items()}

    def _first_int(keys: tuple[str, ...]) -> int | None:
        for key in keys:
            raw = tags.get(key)
            if raw is None:
                continue
            try:
                return int(raw)
            except (TypeError, ValueError):
                continue
        return None

    current = _first_int(("QUEST_PROGRESS", "QUEST_PROGRESS_CURRENT"))
    total = _first_int(("QUEST_PROGRESS_TOTAL",))
    return current, total
