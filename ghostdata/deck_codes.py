"""Local Standard deck-code export using the public Blizzard deckstring protocol.

Protocol reference: https://hearthsim.info/docs/deckstrings/
Sideboard extension: HearthSim/python-hearthstone deckstrings documentation.
No third-party runtime or network requests are used.
"""
import base64
from collections import Counter


def deck_code(deck, database):
    """Return a complete import code, or empty when any identity is unresolved."""
    def resolve(card_id):
        value = database.dbf_id_for_card_id(card_id)
        if type(value) is not int or value <= 0:
            raise ValueError("Unresolved card identity")
        return value

    try:
        if deck.get("format") != "STANDARD" or len(deck.get("hero_card_ids", [])) != 1:
            return ""
        hero = resolve(deck["hero_card_ids"][0])
        main, side = Counter(), Counter()
        for row in deck["cards"]:
            if type(row["count"]) is not int or row["count"] <= 0:
                return ""
            main[(resolve(row["card_id"]),)] += row["count"]
        if not main:
            return ""
        for row in deck.get("sideboards", []):
            count = row["count"]
            owner = resolve(row["owner_card_id"])
            if type(count) is not int or count <= 0 or (owner,) not in main:
                return ""
            side[(resolve(row["card_id"]), owner)] += count
        values = [0, 1, 2, 1, hero]  # reserved, version, Standard, one starting hero
        for entries in (main, side):
            if entries is side:
                values.append(int(bool(side)))
                if not side:
                    break
            for copies in (1, 2, None):
                group = sorted(((key, n) for key, n in entries.items()
                                if (n == copies if copies else n > 2)),
                               key=lambda item: tuple(reversed(item[0])))
                values.append(len(group))
                for key, n in group:
                    values.append(key[0])
                    if copies is None:
                        values.append(n)
                    values.extend(key[1:])
        binary = bytearray()
        for number in values:
            while number >= 128:
                binary.append((number & 127) | 128)
                number >>= 7
            binary.append(number)
        return base64.b64encode(binary).decode("ascii")
    except (KeyError, TypeError, ValueError):
        return ""
