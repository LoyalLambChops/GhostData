import unittest
from pathlib import Path
import tempfile
from ghostdata.dashboard import load_dashboard

from ghostdata.dashboard import build_dashboard
from ghostdata.models import CardEvent, MatchRecord


def game(mid: str, result: str, name: str, version: str, opponent: str, initiative: str, started: str, game_type: str = "GT_RANKED") -> MatchRecord:
    return MatchRecord(
        match_id=mid,
        started_at=started,
        result=result,
        player_class="PRIEST",
        opponent_class=opponent,
        initiative=initiative,
        turn_count=10,
        duration_seconds=600,
        deck_name=name,
        deck_version=version,
        mulligan_offered=["Card A", "Card B", "Card C"],
        mulligan_kept=["Card A", "Card C"],
        mulligan_replaced=["Card B"],
        cards_drawn=[CardEvent(2, "X", "Draw X")],
        cards_played=[CardEvent(3, "A", "Card A")],
        opponent_observed=[CardEvent(4, "O", "Enemy")],
        data_quality="COMPLETE",
        format="STANDARD",
        game_type=game_type,
    )


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            game("a", "WIN", "Ghost", "AAA111", "MAGE", "FIRST", "2026-09-12T10:00:00-04:00"),
            game("b", "LOSS", "Ghost", "BBB222", "WARLOCK", "SECOND", "2026-09-12T11:00:00-04:00"),
        ]

    def test_same_deck_name_different_versions_are_distinct(self):
        dash = build_dashboard(self.rows)
        self.assertEqual(2, len(dash["deck_versions"]))
        self.assertTrue(all("Ghost" in x["label"] for x in dash["deck_versions"]))

    def test_dashboard_contains_facts_without_notes_or_recommendation_fields(self):
        dash = build_dashboard(self.rows)
        text = repr(dash).lower()
        for forbidden in ("note", "guidance", "recommend", "adherence", "sample size"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(2, dash["total_recorded_matches"])
        self.assertEqual("1-1", dash["overall"]["record"])
        self.assertEqual("10m 00s", dash["overall"]["average_duration"])

    def test_opening_dashboard_establishes_fresh_history_epoch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dash = load_dashboard(data_dir=root)
            self.assertEqual(0, dash["total_recorded_matches"])
            self.assertTrue((root / "history_epoch.json").exists())

    def test_ranked_and_casual_modes_are_explicit(self):
        rows = [self.rows[0], game("c", "WIN", "Ghost", "AAA111", "MAGE", "FIRST", "2026-09-12T12:00:00-04:00", "GT_CASUAL")]
        dash = build_dashboard(rows)
        self.assertEqual(["Standard Casual", "Standard Ranked"], sorted(x["mode_label"] for x in dash["recent_matches"]))


if __name__ == "__main__":
    unittest.main()
