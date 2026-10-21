from pathlib import Path
import json
import tempfile
import unittest

from ghostdata.models import MatchRecord
from ghostdata.store import MatchStore


def record(match_id: str, *, deck_name: str = "", version: str = "") -> MatchRecord:
    return MatchRecord(
        match_id=match_id,
        started_at="2026-09-12T10:00:00-04:00",
        result="WIN",
        player_class="PRIEST",
        opponent_class="MAGE",
        initiative="FIRST",
        turn_count=9,
        deck_name=deck_name,
        deck_version=version,
        game_index=1,
    )


class StoreTests(unittest.TestCase):
    def test_same_match_id_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            store = MatchStore(Path(td))
            _, added1 = store.merge([record("match_a")])
            _, added2 = store.merge([record("match_a")])
            self.assertEqual(1, added1)
            self.assertEqual(0, added2)
            self.assertEqual(1, len(store.load()))

    def test_legacy_logical_duplicate_collapses(self):
        with tempfile.TemporaryDirectory() as td:
            store = MatchStore(Path(td))
            store.merge([record("match_a"), record("match_b")])
            self.assertEqual(1, len(store.load()))

    def test_rescan_fills_missing_deck_metadata_but_does_not_overwrite_identity(self):
        with tempfile.TemporaryDirectory() as td:
            store = MatchStore(Path(td))
            store.merge([record("match_a")])
            store.merge([record("match_a", deck_name="Ghost", version="ABCDEF")])
            current = store.load()[0]
            self.assertEqual("Ghost", current.deck_name)
            self.assertEqual("ABCDEF", current.deck_version)
            store.merge([record("match_a", deck_name="Other", version="999999")])
            current = store.load()[0]
            self.assertEqual("Ghost", current.deck_name)
            self.assertEqual("ABCDEF", current.deck_version)

    def test_clear_advances_epoch_and_prevents_history_reappearing(self):
        with tempfile.TemporaryDirectory() as td:
            store = MatchStore(Path(td))
            store.merge([record("match_a")])
            store.clear()
            self.assertEqual([], store.load())
            epoch = json.loads((Path(td) / "history_epoch.json").read_text(encoding="utf-8"))
            index = json.loads((Path(td) / "source_index.json").read_text(encoding="utf-8"))
            self.assertTrue(epoch["started_at"])
            self.assertEqual({}, index["sources"])


if __name__ == "__main__":
    unittest.main()
