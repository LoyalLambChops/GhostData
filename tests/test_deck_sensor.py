import unittest
from pathlib import Path

from ghostdata.deck_sensor import _snapshot_from_payload, _stable_composition_hash
from ghostdata.models import DeckSnapshot
from ghostdata.tracker_bridge import _tracker_snapshot
from ghostdata.tracking.card_db import CardDatabase, CardDefinition


class DeckSensorTests(unittest.TestCase):
    def test_tracker_requires_all_sideboard_entries_to_map(self):
        db = CardDatabase(Path("unused-test-cache"))
        db.cards = {name: CardDefinition(name, name, dbf_id=i)
                    for i, name in enumerate(("MAIN", "OWNER", "SIDE"), 1)}
        snapshot = DeckSnapshot(sensor_status="EXACT", player_class="MAGE",
                                cards=[{"card_id": "MAIN", "count": 2}])
        valid = {"owner_card_id": "OWNER", "card_id": "SIDE", "count": 1}
        snapshot.sideboards = [valid]
        mapped = _tracker_snapshot(snapshot, db)
        self.assertIsNotNone(mapped)
        self.assertEqual(((2, 3, 1),), mapped.sideboards)
        for invalid in ({**valid, "card_id": "UNKNOWN"},
                        {**valid, "owner_card_id": "UNKNOWN"},
                        {**valid, "count": 0}):
            with self.subTest(invalid=invalid):
                snapshot.sideboards = [valid, invalid]
                self.assertIsNone(_tracker_snapshot(snapshot, db))

    def test_composition_hash_is_order_independent(self):
        a = [{"card_id": "CARD_B", "count": 1}, {"card_id": "CARD_A", "count": 2}]
        b = list(reversed(a))
        self.assertEqual(_stable_composition_hash(a), _stable_composition_hash(b))

    def test_selected_deck_keeps_name_class_and_version_separate(self):
        snapshot = _snapshot_from_payload({
            "status": "ok",
            "selected_deck_id": "123",
            "deck_name": "Ghost",
            "format": "STANDARD",
            "hero_card_ids": ["HERO_09"],
            "cards": [{"card_id": "CARD_A", "count": 2}],
            "hearthstone_build": "12345",
        })
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual("Ghost", snapshot.deck_name)
        self.assertEqual("PRIEST", snapshot.player_class)
        self.assertTrue(snapshot.composition_hash)
        self.assertEqual("", snapshot.archetype_name)


if __name__ == "__main__":
    unittest.main()
