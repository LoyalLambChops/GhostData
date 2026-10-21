"""Regression coverage for starting the tracker after switching decks/sessions."""
from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from ghostdata.deck_sensor import read_selected_deck, save_cached_deck
from ghostdata.models import DeckSnapshot
from ghostdata.tracking.models import GameState
from ghostdata.tracking.tracker import DeckTrackerEngine
import test_live_deck_tracker as fixture


class DeckLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.DeckTrackerTests()
        self.f.setUp()

    def test_stale_priest_seed_is_dropped_when_local_mage_becomes_known(self):
        tracker = self.f.tracker
        priest = replace(self.f.snapshot, class_id="PRIEST", deck_name="Ghost", deck_hash="priest")
        tracker.seed_selected_deck(priest)
        self.f.state.local_player_pid = None
        self.f._emit_zone(100, 1, "DECK", "CARD_1")
        self.f._emit_zone(100, 1, "HAND")
        self.f.state.local_player_pid = 1
        tracker.observe(self.f.state)
        self.assertEqual("", tracker.state.player_deck_name)
        self.assertEqual("MAGE", tracker.state.player_class)
        self.assertFalse(tracker.state.player_rows)
        self.assertEqual("WAITING_FOR_EXACT_DECK", tracker.state.source_status)
        self.assertEqual(["CARD_1"], [r.card_id for r in tracker.state.player_display_rows])
        self.assertFalse(tracker.seed_selected_deck(priest, self.f.state))
        self.assertTrue(tracker.seed_selected_deck(self.f.snapshot, self.f.state))
        self.assertEqual(29, tracker.state.original_cards_remaining)
        self.assertEqual(1, next(r for r in tracker.state.player_rows if r.card_id == "CARD_1").drawn_copies)

    def test_same_class_replacement_clears_old_original_assignments(self):
        self.f._emit_zone(100, 1, "DECK", "CARD_1")
        self.f._emit_zone(100, 1, "HAND")
        corrected = replace(self.f.snapshot, cards=((2, 30),), deck_hash="different-mage", deck_name="Other Mage")
        self.f.tracker.seed_selected_deck(corrected, self.f.state)
        self.assertEqual(["CARD_2"], [r.card_id for r in self.f.tracker.state.player_rows])
        self.assertEqual("UNKNOWN", next(r for r in self.f.tracker.state.player_display_rows if r.card_id == "CARD_1").provenance)

    def test_hero_class_change_during_game_does_not_discard_starting_deck(self):
        self.f.tracker.observe(self.f.state)
        self.f.state.player(1).player_class = "PRIEST"
        self.f.tracker.observe(self.f.state)
        self.assertEqual(self.f.snapshot, self.f.tracker.selected_snapshot)
        self.assertTrue(self.f.tracker.seed_selected_deck(self.f.snapshot, self.f.state, refresh_metadata=True))

    def test_new_game_rechecks_class_even_with_reused_player_id(self):
        self.f.tracker.observe(self.f.state)
        game = GameState(active=True, game_number=2, local_player_pid=1)
        game.player(1).player_class = "PRIEST"
        self.f.tracker.observe(game)
        self.assertFalse(self.f.tracker.state.player_rows)
        self.assertEqual("PRIEST", self.f.tracker.state.player_class)

    def test_unavailable_or_missing_sensor_never_promotes_disk_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            save_cached_deck(DeckSnapshot(deck_name="Ghost", selected_deck_id="old", sensor_status="EXACT"), data_dir=folder)
            self.assertIsNone(read_selected_deck(folder, data_dir=folder))
            exe = folder / "reader.exe"; exe.touch()
            for result in (SimpleNamespace(returncode=1, stdout=""), SimpleNamespace(returncode=0, stdout='{"status":"UNAVAILABLE"}')):
                with patch("ghostdata.deck_sensor.sensor_executable", return_value=exe), patch("ghostdata.deck_sensor.subprocess.run", return_value=result) as run:
                    self.assertIsNone(read_selected_deck(folder, data_dir=folder))
                    self.assertNotIn("--deck-id", run.call_args.args[0])

    def test_fresh_sensor_result_replaces_cache_without_old_deck_id_argument(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); exe = folder / "reader.exe"; exe.touch()
            save_cached_deck(DeckSnapshot(deck_name="Ghost", selected_deck_id="old"), data_dir=folder)
            payload = dict(status="EXACT", deck_name="Usher", selected_deck_id="new", hero_card_ids=["HERO_08"], cards=[dict(card_id="MAGE_CARD", count=30)])
            with patch("ghostdata.deck_sensor.sensor_executable", return_value=exe), patch("ghostdata.deck_sensor.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload))) as run:
                deck = read_selected_deck(folder, data_dir=folder)
                self.assertEqual("Usher", deck.deck_name)
                self.assertEqual("MAGE", deck.player_class)
                self.assertNotIn("--deck-id", run.call_args.args[0])


class StreamDeckBoundaryTests(unittest.TestCase):
    def test_old_same_class_result_cannot_cross_session_or_game_boundary(self):
        from concurrent.futures import Future
        from ghostdata.tracker_bridge import run_tracker_stream
        from ghostdata.tracking.parser import PowerLogParser
        from ghostdata.tracking.snapshot import TrackerDeckSnapshot
        snapshot = TrackerDeckSnapshot("EXACT", "Previous Mage", "MAGE", ((1, 30),), ())
        for new_source in (False, True):
            with self.subTest(new_source=new_source), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); round_number = [-1]; published = []
                parser = PowerLogParser()
                class Worker:
                    def __init__(self, **kwargs): pass
                    def submit(self, function, *args, **kwargs):
                        future = Future()
                        # A read begun before the boundary returns the old deck.
                        future.set_result(snapshot if function.__name__ == "read_selected_deck" and round_number[0] <= 2 else None)
                        return future
                def logs(_):
                    round_number[0] += 1
                    if round_number[0] >= 6: raise StopIteration
                    return [root / ("new.log" if new_source and round_number[0] >= 3 else "old.log")]
                def ingest(p, tracker, pending, chunk):
                    if p.state.game_number == 0 or (not new_source and round_number[0] == 3):
                        p.state.reset()
                        p.state.local_player_pid = 1
                        p.state.player(1).player_class = "MAGE"
                    tracker.observe(p.state)
                    return b""
                with patch("ghostdata.tracker_bridge.discover_power_logs", side_effect=logs), \
                     patch("ghostdata.tracker_bridge.PowerLogParser", return_value=parser), \
                     patch("ghostdata.tracker_bridge.ThreadPoolExecutor", Worker), \
                     patch("ghostdata.tracker_bridge.LogTail") as tail, \
                     patch("ghostdata.tracker_bridge.ingest_tracker_chunk", side_effect=ingest), \
                     patch("ghostdata.tracker_bridge._tracker_snapshot", side_effect=lambda value, db: value), \
                     patch("ghostdata.tracker_bridge.time.monotonic", side_effect=lambda: (round_number[0]+2)*10), \
                     patch("ghostdata.tracker_bridge.time.sleep"), \
                     patch("ghostdata.tracker_bridge._emit", side_effect=lambda seq, tracker, p: published.append((round_number[0], tracker.state.player_deck_name))):
                    tail.return_value.read.return_value = (b"frame", False)
                    with self.assertRaises(StopIteration):
                        run_tracker_stream(root, data_dir=root)
                self.assertTrue(any(name == "Previous Mage" for tick, name in published if tick < 3))
                self.assertTrue(any(tick >= 3 for tick, name in published))
                self.assertTrue(all(not name for tick, name in published if tick >= 3), published)
