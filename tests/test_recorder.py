from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ghostdata.models import DeckSnapshot, MatchRecord
from ghostdata.recorder import record_once
from ghostdata.store import MatchStore
import json
from synthetic_match import write_match_log

ROOT = Path(__file__).resolve().parents[1]


class RecorderTests(unittest.TestCase):
    def test_new_match_gets_selected_deck_once(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            log = td / "Power.log"
            write_match_log(log)
            import os
            os.utime(log, None)
            data = td / "data"
            data.mkdir()
            (data / "history_epoch.json").write_text(json.dumps({"schema_version": 1, "started_at": "2000-01-01T00:00:00+00:00"}))
            deck = DeckSnapshot(deck_name="Ghost", selected_deck_id="7", player_class="PRIEST", composition_hash="ABC123")
            with patch("ghostdata.recorder.read_selected_deck", return_value=deck):
                _, added = record_once(ROOT, power_log=log, data_dir=data)
            self.assertEqual(1, added)
            row = MatchStore(td / "data").load()[0]
            self.assertEqual("Ghost", row.deck_name)
            self.assertEqual("ABC123", row.deck_version)
            self.assertEqual("COMPLETE", row.data_quality)

    def test_rescan_does_not_stamp_a_later_selected_deck(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            log = td / "Power.log"
            write_match_log(log)
            data = td / "data"
            data.mkdir()
            (data / "history_epoch.json").write_text(json.dumps({"schema_version": 1, "started_at": "2000-01-01T00:00:00+00:00"}))
            with patch("ghostdata.recorder.read_selected_deck", return_value=None):
                record_once(ROOT, power_log=log, data_dir=data)
            with patch("ghostdata.recorder.read_selected_deck", return_value=DeckSnapshot(deck_name="Wrong Later Deck", selected_deck_id="9", composition_hash="BAD")):
                record_once(ROOT, power_log=log, data_dir=data)
            row = MatchStore(td / "data").load()[0]
            self.assertEqual("", row.deck_name)
            self.assertEqual("", row.deck_version)
            self.assertEqual("LIMITED", row.data_quality)

    def test_first_launch_epoch_excludes_prior_completed_games(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            log = td / "Power.log"
            write_match_log(log)
            # Make the copied file and its fallback match timestamp clearly older
            # than the first-run epoch created by record_once.
            import os, time
            old = time.time() - 3600
            os.utime(log, (old, old))
            data = td / "data"
            with patch("ghostdata.recorder.read_selected_deck", return_value=DeckSnapshot(deck_name="Current", composition_hash="NOW")):
                parsed, added = record_once(ROOT, power_log=log, data_dir=data)
            self.assertEqual((0, 0), (parsed, added))
            self.assertEqual([], MatchStore(data).load())
            self.assertTrue((data / "history_epoch.json").exists())

    def test_stale_unrecorded_log_is_imported_without_current_deck_identity(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            log = td / "Power.log"
            write_match_log(log)
            data = td / "data"
            data.mkdir()
            (data / "history_epoch.json").write_text(json.dumps({"schema_version": 1, "started_at": "2000-01-01T00:00:00+00:00"}))
            import os, time
            old = time.time() - 7200
            os.utime(log, (old, old))
            with patch("ghostdata.recorder.read_selected_deck", return_value=DeckSnapshot(deck_name="Current Wrong Deck", composition_hash="BAD")):
                parsed, added = record_once(ROOT, power_log=log, data_dir=data)
            self.assertEqual((1, 1), (parsed, added))
            row = MatchStore(data).load()[0]
            self.assertEqual("", row.deck_name)
            self.assertEqual("", row.deck_version)
            self.assertEqual("LIMITED", row.data_quality)

    def test_current_deck_metadata_applies_only_to_latest_new_completed_game(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            log = td / "Power.log"
            log.write_text("placeholder")
            data = td / "data"
            data.mkdir()
            (data / "history_epoch.json").write_text(json.dumps({"schema_version": 1, "started_at": "2000-01-01T00:00:00+00:00"}))
            first = MatchRecord("a", "2026-09-12T10:00:00+00:00", "WIN", "PRIEST", "MAGE", "FIRST", game_index=1)
            second = MatchRecord("b", "2026-09-12T10:20:00+00:00", "LOSS", "PRIEST", "WARLOCK", "SECOND", game_index=2)
            deck = DeckSnapshot(deck_name="Ghost", selected_deck_id="7", player_class="PRIEST", composition_hash="ABC123")
            with patch("ghostdata.recorder.parse_completed_games", return_value=[first, second]), patch("ghostdata.recorder.read_selected_deck", return_value=deck):
                parsed, added = record_once(ROOT, power_log=log, data_dir=data)
            self.assertEqual((2, 2), (parsed, added))
            rows = {r.match_id: r for r in MatchStore(data).load()}
            self.assertEqual("", rows["a"].deck_name)
            self.assertEqual("Ghost", rows["b"].deck_name)

    def test_game_started_before_epoch_but_completed_after_epoch_is_kept(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            log = td / "Power.log"
            log.write_text("placeholder")
            data = td / "data"
            data.mkdir()
            (data / "history_epoch.json").write_text(json.dumps({"schema_version": 1, "started_at": "2026-09-12T10:05:00+00:00"}))
            row = MatchRecord("midgame", "2026-09-12T10:00:00+00:00", "WIN", "PRIEST", "MAGE", "FIRST", ended_at="2026-09-12T10:10:00+00:00", game_index=1)
            with patch("ghostdata.recorder.parse_completed_games", return_value=[row]), patch("ghostdata.recorder.read_selected_deck", return_value=None):
                parsed, added = record_once(ROOT, power_log=log, data_dir=data)
            self.assertEqual((1, 1), (parsed, added))
            self.assertEqual(1, len(MatchStore(data).load()))


if __name__ == "__main__": unittest.main()
