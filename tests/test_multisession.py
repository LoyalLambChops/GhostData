from __future__ import annotations

from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from ghostdata.models import MatchRecord
from ghostdata.powerlog import discover_power_logs
from ghostdata.recorder import record_once
from ghostdata.store import MatchStore

ROOT = Path(__file__).resolve().parents[1]


def match(mid: str, started: str, opponent: str, index: int, ended: str | None = None) -> MatchRecord:
    return MatchRecord(
        match_id=mid,
        started_at=started,
        ended_at=ended or started,
        result="WIN" if index % 2 else "LOSS",
        player_class="PRIEST",
        opponent_class=opponent,
        initiative="FIRST" if index % 2 else "SECOND",
        turn_count=8 + index,
        duration_seconds=480,
        game_index=index,
    )


class MultiSessionTests(unittest.TestCase):
    def _data(self, root: Path, epoch: str = "2000-01-01T00:00:00+00:00") -> Path:
        data = root / "data"
        data.mkdir()
        (data / "history_epoch.json").write_text(
            json.dumps({"schema_version": 1, "started_at": epoch}), encoding="utf-8"
        )
        return data

    def test_discovery_returns_every_nested_session_power_log(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = []
            for stamp in ("2026_09_10_090000", "2026_09_11_100000", "2026_09_12_110000"):
                folder = root / f"Hearthstone_{stamp}"
                folder.mkdir()
                log = folder / "Power.log"
                log.write_text("x", encoding="utf-8")
                expected.append(log.resolve())
            self.assertEqual(expected, discover_power_logs(root))

    def test_three_sessions_five_games_refresh_restart_and_log_growth_stay_five(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = self._data(root)
            logs = []
            rows_by_path = {}
            specs = [
                ("Hearthstone_2026_09_10_09_00_00", [
                    match("a1", "2026-09-10T13:05:00+00:00", "MAGE", 1),
                    match("a2", "2026-09-10T13:20:00+00:00", "WARLOCK", 2),
                ]),
                ("Hearthstone_2026_09_11_10_00_00", [
                    match("b1", "2026-09-11T14:05:00+00:00", "PRIEST", 1),
                ]),
                ("Hearthstone_2026_09_12_11_00_00", [
                    match("c1", "2026-09-12T15:05:00+00:00", "ROGUE", 1),
                    match("c2", "2026-09-12T15:20:00+00:00", "WARRIOR", 2),
                ]),
            ]
            for folder_name, rows in specs:
                folder = root / folder_name
                folder.mkdir()
                log = folder / "Power.log"
                log.write_text("session", encoding="utf-8")
                logs.append(log.resolve())
                rows_by_path[str(log.resolve())] = rows

            def parse(path):
                return rows_by_path[str(Path(path).resolve())]

            with patch("ghostdata.recorder.read_selected_deck", return_value=None), patch(
                "ghostdata.recorder.parse_completed_games", side_effect=parse
            ) as parser:
                parsed, added = record_once(ROOT, power_log=root, data_dir=data)
                self.assertEqual((5, 5), (parsed, added))
                self.assertEqual(5, len(MatchStore(data).load()))
                self.assertEqual(3, parser.call_count)

                # Plain Refresh: all three sources are unchanged, so none are reparsed.
                parsed, added = record_once(ROOT, power_log=root, data_dir=data)
                self.assertEqual((0, 0), (parsed, added))
                self.assertEqual(5, len(MatchStore(data).load()))
                self.assertEqual(3, parser.call_count)

                # Simulate harmless post-game growth in the newest session.
                with logs[-1].open("a", encoding="utf-8") as handle:
                    handle.write("more bookkeeping")
                os.utime(logs[-1], None)
                parsed, added = record_once(ROOT, power_log=root, data_dir=data)
                self.assertEqual((2, 0), (parsed, added))
                self.assertEqual(5, len(MatchStore(data).load()))
                self.assertEqual(4, parser.call_count)

                # A process restart reads the same persistent source index.
                parsed, added = record_once(ROOT, power_log=root, data_dir=data)
                self.assertEqual((0, 0), (parsed, added))
                self.assertEqual(5, len(MatchStore(data).load()))
                self.assertEqual(4, parser.call_count)

            self.assertTrue((data / "source_index.json").exists())

    def test_session_missed_while_ghostdata_was_closed_is_recovered_after_epoch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = self._data(root, "2026-09-12T14:00:00+00:00")
            a_dir = root / "Hearthstone_2026_09_12_10_10_00"
            a_dir.mkdir()
            a = a_dir / "Power.log"
            a.write_text("A", encoding="utf-8")
            rows = {str(a.resolve()): [match("a", "2026-09-12T14:15:00+00:00", "MAGE", 1)]}

            def parse(path):
                return rows[str(Path(path).resolve())]

            with patch("ghostdata.recorder.read_selected_deck", return_value=None), patch(
                "ghostdata.recorder.parse_completed_games", side_effect=parse
            ):
                self.assertEqual((1, 1), record_once(ROOT, power_log=root, data_dir=data))

                # GhostData is now "closed". A later Hearthstone session appears.
                b_dir = root / "Hearthstone_2026_09_12_11_30_00"
                b_dir.mkdir()
                b = b_dir / "Power.log"
                b.write_text("B", encoding="utf-8")
                rows[str(b.resolve())] = [match("b", "2026-09-12T15:35:00+00:00", "WARLOCK", 1)]

                # Next launch/Refresh sees the previously unseen session.
                self.assertEqual((1, 1), record_once(ROOT, power_log=root, data_dir=data))

            self.assertEqual({"a", "b"}, {m.match_id for m in MatchStore(data).load()})


    def test_prior_session_is_not_stamped_with_deck_from_newer_empty_session(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = self._data(root)
            old_dir = root / "Hearthstone_2026_09_12_10_00_00"
            old_dir.mkdir()
            old_log = old_dir / "Power.log"
            old_log.write_text("completed", encoding="utf-8")
            new_dir = root / "Hearthstone_2026_09_12_11_00_00"
            new_dir.mkdir()
            new_log = new_dir / "Power.log"
            new_log.write_text("new empty session", encoding="utf-8")
            rows = {
                str(old_log.resolve()): [match("old-session", "2026-09-12T14:05:00+00:00", "MAGE", 1)],
                str(new_log.resolve()): [],
            }

            def parse(path):
                return rows[str(Path(path).resolve())]

            from ghostdata.models import DeckSnapshot
            wrong = DeckSnapshot(deck_name="Current Session Deck", composition_hash="WRONG")
            with patch("ghostdata.recorder.parse_completed_games", side_effect=parse), patch(
                "ghostdata.recorder.read_selected_deck", return_value=wrong
            ) as deck_reader:
                self.assertEqual((1, 1), record_once(ROOT, power_log=root, data_dir=data))
            row = MatchStore(data).load()[0]
            self.assertEqual("", row.deck_name)
            self.assertEqual("", row.deck_version)
            deck_reader.assert_not_called()

    def test_pre_epoch_missed_session_remains_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = self._data(root, "2026-09-12T14:00:00+00:00")
            session = root / "Hearthstone_2026_09_12_08_00_00"
            session.mkdir()
            log = session / "Power.log"
            log.write_text("old", encoding="utf-8")
            old = match("old", "2026-09-12T12:00:00+00:00", "MAGE", 1, "2026-09-12T12:10:00+00:00")
            with patch("ghostdata.recorder.parse_completed_games", return_value=[old]), patch(
                "ghostdata.recorder.read_selected_deck", return_value=None
            ):
                self.assertEqual((0, 0), record_once(ROOT, power_log=root, data_dir=data))
            self.assertEqual([], MatchStore(data).load())


if __name__ == "__main__":
    unittest.main()
