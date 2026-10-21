import unittest
from ghostdata.tracking.parser import PowerLogParser
from ghostdata.tracker_bridge import ingest_tracker_chunk
import test_live_deck_tracker as fixture


class OverdrawTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.DeckTrackerTests(); self.f.setUp()
        self.parser = PowerLogParser(card_db=self.f.db); self.parser.state = self.f.state

    def lines(self, *lines, task=False):
        stream = "PowerTaskList" if task else "GameState"
        data = "".join(f"D 12:00:00.000 {stream}.DebugPrintPower() - {s}\n" for s in lines)
        ingest_tracker_chunk(self.parser, self.f.tracker, b"", data.encode())

    def capture(self, old=100, new=200, pid=1, task=False):
        self.lines("FULL_ENTITY - Creating ID=99 CardID=JAIL_509e", f"tag=CONTROLLER value={pid}",
            "tag=CARDTYPE value=ENCHANTMENT", "tag=ZONE value=PLAY", task=task)
        self.lines(f"BLOCK_START BlockType=TRIGGER Entity=[entityName=Atlas id=99 zone=PLAY zonePos=0 cardId=JAIL_509e player={pid}] EffectCardId= EffectIndex=0 Target=0 TriggerKeyword=TRIGGER_VISUAL",
            f"FULL_ENTITY - Creating ID={new} CardID=", f"tag=CONTROLLER value={pid}",
            "tag=CARDTYPE value=SPELL", "tag=ZONE value=SETASIDE", "BLOCK_END",
            f"FULL_ENTITY - Creating ID={old} CardID=CARD_2", f"tag=CONTROLLER value={pid}", "tag=ZONE value=GRAVEYARD",
            "META_DATA - Meta=BURNED_CARD Data=0 InfoCount=1",
            f"Info[0] = [entityName=Card id={old} zone=GRAVEYARD zonePos=0 cardId=CARD_2 player={pid}]", task=task)

    def test_recoverable_is_separate_discounted_and_not_counted_in_hand(self):
        self.capture()
        rows = self.f.tracker.state.player_overdraw_rows
        self.assertEqual([(r.card_id, r.cost, r.state) for r in rows], [("CARD_2", 0, "AWAITING SPACE")])
        self.assertEqual(self.f.tracker.state.player_hand_count, 0)
        self.lines("TAG_CHANGE Entity=200 tag=ZONE value=HAND")
        self.assertEqual(self.f.tracker.state.player_overdraw_rows, ())
        self.assertEqual(self.f.tracker.state.player_hand_count, 1)

    def test_duplicate_task_stream_does_not_duplicate_pool(self):
        self.capture(); self.capture(task=True)
        self.assertEqual(len(self.f.tracker.state.player_overdraw_rows), 1)

    def test_unique_opponent_return_is_public_and_delayed_burn_cannot_resurrect_pool(self):
        self.capture(pid=2)
        self.lines("TAG_CHANGE Entity=200 tag=ZONE value=HAND")
        self.assertEqual(self.f.tracker.state.opponent_hand[0].card_id, "CARD_2")
        self.lines("META_DATA - Meta=BURNED_CARD Data=0 InfoCount=1", "Info[0] = 100", task=True)
        self.assertEqual(self.f.tracker.state.opponent_overdraw_rows, ())

    def test_ordinary_burn_has_no_recovery_pool(self):
        self.lines("FULL_ENTITY - Creating ID=100 CardID=CARD_2", "tag=CONTROLLER value=1",
            "tag=ZONE value=GRAVEYARD", "META_DATA - Meta=BURNED_CARD Data=0 InfoCount=1", "Info[0] = 100")
        self.assertEqual(self.f.tracker.state.player_overdraw_rows, ())

    def test_opponent_ambiguous_return_retains_possibilities_and_hidden_hand(self):
        self.capture(pid=2); self.capture(old=101, new=201, pid=2)
        self.lines("TAG_CHANGE Entity=200 tag=ZONE value=HAND")
        rows = self.f.tracker.state.opponent_overdraw_rows
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r.state == "MAY BE IN HAND" for r in rows))
        self.assertEqual(self.f.tracker.state.opponent_hand[0].card_id, "")
        self.lines("SHOW_ENTITY - Updating Entity=200 CardID=CARD_2")
        self.assertEqual(len(self.f.tracker.state.opponent_overdraw_rows), 1)
        self.lines("TAG_CHANGE Entity=201 tag=ZONE value=HAND")
        self.assertEqual(self.f.tracker.state.opponent_overdraw_rows, ())

    def test_new_game_clears_pool(self):
        self.capture(); self.lines("CREATE_GAME")
        self.assertEqual(self.f.tracker.state.player_overdraw_rows, ())
