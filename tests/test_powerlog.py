from pathlib import Path
from datetime import datetime
import tempfile
import unittest

from ghostdata.powerlog import parse_completed_games, started_at
from synthetic_match import write_match_log


class PowerLogTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.fixture = Path(folder.name) / "Power.log"
        write_match_log(self.fixture)

    def test_synthetic_fixture_extracts_one_completed_match(self):
        matches = parse_completed_games(self.fixture)
        self.assertEqual(1, len(matches))
        match = matches[0]
        self.assertEqual("WIN", match.result)
        self.assertEqual("PRIEST", match.player_class)
        self.assertEqual("WARLOCK", match.opponent_class)
        self.assertEqual("SECOND", match.initiative)
        self.assertGreater(match.turn_count, 0)
        self.assertGreater(match.duration_seconds, 0)
        self.assertGreaterEqual(len(match.mulligan_offered), 3)
        self.assertTrue(match.mulligan_kept)
        self.assertTrue(match.mulligan_replaced)
        self.assertTrue(match.cards_drawn)
        self.assertTrue(match.cards_played)
        self.assertTrue(match.opponent_observed)

    def test_match_id_is_stable_when_postgame_log_grows(self):
        with tempfile.TemporaryDirectory() as td:
            copy = Path(td) / "Power.log"
            write_match_log(copy)
            before = parse_completed_games(copy)[0].match_id
            with copy.open("a", encoding="utf-8") as handle:
                handle.write("D 23:59:59.0000000 harmless post-game bookkeeping\n")
                handle.write("D 23:59:59.1000000 another line after terminal result\n")
            after = parse_completed_games(copy)[0].match_id
            self.assertEqual(before, after)

    def test_opening_hand_is_not_counted_as_normal_draw_history(self):
        match = parse_completed_games(self.fixture)[0]
        opening = set(match.mulligan_offered)
        self.assertTrue(opening)
        # A card can be drawn again later, but the first ordinary draw should not be
        # a turn-zero opening-hand event.
        self.assertTrue(all(event.turn > 0 for event in match.cards_drawn))

    def test_session_clock_later_than_folder_time_stays_on_session_date(self):
        path = Path("Hearthstone_2026_10_07_07_54_33") / "Power.log"
        value = started_at(path, ["D 08:25:15.1406171 later game in same session\n"])
        parsed = datetime.fromisoformat(value)
        self.assertEqual((2026, 10, 7, 8, 25), (parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute))

    def test_session_crossing_midnight_advances_to_next_date(self):
        path = Path("Hearthstone_2026_10_07_23_54_33") / "Power.log"
        value = started_at(path, ["D 00:25:15.0000000 game after midnight\n"])
        parsed = datetime.fromisoformat(value)
        self.assertEqual((2026, 10, 8, 0, 25), (parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute))


if __name__ == "__main__":
    unittest.main()
