"""Local definition loading must never initiate a network request."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ghostdata.tracking.card_db import CardDatabase


class LocalCardDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = CardDatabase(self.root)

    def write(self, build, rows):
        (self.root / f"cards_{build}_local.json").write_text(json.dumps(rows), encoding="utf-8")

    def test_missing_build_does_not_contact_network(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("Unexpected network request")):
            self.assertFalse(self.db.load_for_build(999))
            self.assertFalse(self.db.load_latest_cache())
        self.assertIsNone(self.db.build_number)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_local_definitions_map_identity_and_rules(self):
        self.write(1, [dict(id="SAMPLE", dbfId=1, name="Example", cardClass="MAGE", type="SPELL",
                            cost=3, collectible=True, mechanics=["SECRET"], text="Example rules.")])
        with patch("urllib.request.urlopen", side_effect=AssertionError("Unexpected network request")):
            self.assertTrue(self.db.load_for_build(1))
        self.assertEqual(self.db.get_by_dbf(1).name, "Example")
        self.assertEqual(self.db.secret_cards_for_class("MAGE")[0].text, "Example rules.")

    def test_failed_new_build_preserves_last_successful_identity(self):
        self.write(1, [dict(id="SAMPLE", name="Example")])
        self.assertTrue(self.db.load_for_build(1))
        for bad in ([], {}, [dict(id="OTHER"), 7], [dict(id="OTHER", mechanics=7)], [dict(id="OTHER", races=7)], [dict(id="OTHER", textBuilder=7)]):
            self.write(2, bad)
            self.assertFalse(self.db.load_for_build(2))
            self.assertEqual(self.db.build_number, 1)
            self.assertEqual(list(self.db.cards), ["SAMPLE"])

    def test_corrupt_file_is_unavailable(self):
        (self.root / "cards_2_local.json").write_text("{", encoding="utf-8")
        self.assertFalse(self.db.load_for_build(2))
        self.assertFalse(self.db.ready)

    def test_latest_cache_skips_unusable_files(self):
        self.write(1, [dict(id="SAMPLE", name="Example")])
        self.write(2, [])
        self.assertTrue(self.db.load_latest_cache())
        self.assertEqual(self.db.build_number, 1)
