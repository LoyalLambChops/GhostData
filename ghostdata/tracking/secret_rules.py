"""Public trigger conditions for historical Secrets generated in Standard.

Conditions use observed actions and public board/hand counts, never the hidden
Secret identity. Resolution is checked by SecretTracker at the action boundary.
"""

GROUPS = {
    "attack_space": "noble sacrifice",
    "minion_attack": "judgment of justice|mystic misdirection|freezing trap",
    "hero_attack": "ice barrier|explosive trap",
    "hero_attack_space": "bear trap|wandering monster",
    "minion_hero_attack": "flame ward|vaporize",
    "minion_hero_attack_space": "shadow clone|vengeful visage",
    "friendly_attack": "bamboozle|bait and switch",
    "friendly_attack_space": "splitting image|pack tactics|snake trap|venomstrike trap|oasis ally",
    "minion_play": "snipe|explosive runes|objection!|potion of polymorph|repentance",
    "minion_play_space": "mirror entity|ambush|zombeeees!!!",
    "minion_play_hand": "frozen clone",
    "spell_play": "counterspell|ice trap|oh my yogg!",
    "spell_play_hand": "dirty tricks|mana bind",
    "spell_play_space": "cat trick|netherwind portal|sticky situation",
    "friendly_death_hand": "duplicate|getaway kodo|cheat death",
    "friendly_death_space": "redemption|effigy|emergency maneuvers",
    "third_card": "motion denied",
    "third_card_space": "rat trap|galloping savior",
    "third_card_hand": "hidden wisdom",
    "hero_damage": "eye for an eye|evasion",
}
RULES = {name: group for group, names in GROUPS.items() for name in names.split("|")}
RULES.update({name: name for name in (
    "misdirection", "sudden betrayal", "autodefense matrix", "hidden cache",
    "bargain bin", "never surrender!", "spellbender", "pressure plate", "sacred trial",
    "avenge", "hand of salvation", "untimely death", "reckoning", "perjury",
    "summoning ward", "flames of infinity", "competitive spirit", "open the cages",
    "rigged faire game", "azerite vein", "shenanigans", "dart trap", "plagiarize",
    "hidden meaning", "double cross", "kidnap")})


def matches(name, observation, owner, game):
    rule = RULES.get(name)
    if not rule or game is None:
        return False
    event = observation.event_type
    actor = game.entities.get(observation.actor_entity_id)
    target = game.entities.get(observation.target_entity_id)
    own_minions = [e for e in game.board(owner) if e.card_type == "MINION"]
    enemy_minions = [e for e in game.entities.values() if e.controller != owner and e.zone == "PLAY" and e.card_type == "MINION"]
    space = len(game.board(owner)) < 7
    hand_space = len(game.hand(owner)) < 10
    if event == "TURN_START" and observation.actor_pid == owner:
        if rule == "perjury": return True
        if rule == "summoning ward": return bool(own_minions) and space
        if rule == "flames of infinity": return bool(enemy_minions)
        if rule == "competitive spirit": return bool(own_minions)
        if rule == "open the cages": return len(own_minions) >= 2 and space
        if rule == "rigged faire game":
            return game.player(owner).tags.get("GHOSTDATA_DAMAGED_TURN") != str(game.global_turn - 1)
        if rule == "plagiarize":
            return any(e.event_type == "PLAY" and e.data.get("player") != owner and e.data.get("turn") == game.global_turn - 1 for e in game.events)
        return False
    if observation.actor_pid is None or observation.actor_pid == owner:
        return False
    if rule == "dart trap": return event == "HERO_POWER"
    if rule == "shenanigans": return event == "SECOND_DRAW"
    if rule == "hidden meaning": return event == "TURN_END" and game.player(observation.actor_pid).available_mana == 0 and space
    if rule == "double cross": return event == "MANA_ZERO" and hand_space
    if rule == "hero_damage": return event == "HERO_DAMAGED" and observation.target_pid == owner
    if rule == "reckoning":
        return event == "MINION_DAMAGE_3" and actor is not None and actor.zone == "PLAY" and (
            actor.health is None or actor.health > actor.damage)
    if event == "ATTACK":
        if observation.target_pid != owner: return False
        hero = observation.is_hero_target
        minion = observation.card_type == "MINION"
        if rule == "attack_space": return space
        if rule == "minion_attack": return minion
        if rule == "hero_attack": return hero
        if rule == "hero_attack_space": return hero and space
        if rule == "minion_hero_attack": return hero and minion
        if rule == "minion_hero_attack_space": return hero and minion and space
        if rule == "friendly_attack": return observation.is_minion_target
        if rule == "friendly_attack_space": return observation.is_minion_target and space
        if rule == "autodefense matrix": return observation.is_minion_target and target is not None and target.tags.get("DIVINE_SHIELD", "0") == "0"
        if rule == "sudden betrayal": return hero and minion and len(enemy_minions) > 1
        if rule == "misdirection":
            return hero and any(e.zone == "PLAY" and e.card_type in {"MINION", "HERO"}
                and e.entity_id not in {observation.actor_entity_id, observation.target_entity_id}
                and e.tags.get("IMMUNE", "0") == "0" for e in game.entities.values())
    if event == "MINION_DIED" and observation.target_pid == owner:
        if rule == "friendly_death_hand": return hand_space
        if rule == "friendly_death_space": return space
        if rule == "avenge": return any(e.entity_id in observation.witness_ids for e in own_minions)
        if rule == "hand of salvation": return True
        if rule == "untimely death": return target is not None and target.last_played_turn == game.global_turn - 1
    if event == "PLAY":
        last_turn = max((e.sequence for e in game.events if e.event_type == "GLOBAL_TURN"), default=0)
        played = sum(e.event_type == "PLAY" and e.sequence > last_turn and e.data.get("player") == observation.actor_pid for e in game.events)
        if rule == "third_card": return played >= 3
        if rule == "third_card_space": return played >= 3 and space
        if rule == "third_card_hand": return played >= 3 and hand_space
        if rule == "azerite vein": return actor is not None and actor.tags.get("NUM_TURNS_IN_HAND") == "1" and hand_space
        if rule == "bargain bin":
            # Unlike Dirty Tricks, this is tested even with a full hand; dormant
            # minions are excluded from its minion-play trigger.
            return observation.card_type in {"SPELL", "WEAPON"} or (
                observation.card_type == "MINION" and actor is not None and actor.tags.get("DORMANT", "0") == "0")
        if observation.card_type == "MINION":
            if rule == "kidnap": return True
            if rule == "minion_play": return actor is not None and actor.tags.get("DORMANT", "0") == "0"
            if rule == "minion_play_space": return space
            if rule == "minion_play_hand": return hand_space
            if rule == "hidden cache": return any(e.card_type == "MINION" for e in game.hand(owner))
            if rule == "sacred trial": return len(enemy_minions) >= (4 if actor and actor.zone == "PLAY" else 3)
        if observation.card_type == "SPELL":
            if rule == "spell_play": return True
            if rule == "spell_play_space": return space
            if rule == "spell_play_hand": return hand_space
            if rule == "never surrender!": return bool(own_minions)
            if rule == "pressure plate": return bool(enemy_minions)
            if rule == "spellbender":
                target = target or game.entities.get(int(actor.tags.get("CARD_TARGET", "0"))) if actor else target
                return target is not None and target.card_type == "MINION" and space
    return False
