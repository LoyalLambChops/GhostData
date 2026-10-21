import unittest
from ghostdata.tracking.public_effects import LATORVIUS_REWARDS
from ghostdata.tracking.parser import PowerLogParser
from ghostdata.tracker_bridge import ingest_tracker_chunk
from ghostdata.tracking.card_db import CardDefinition
import test_live_deck_tracker as fixture
from test_rewind import line


class RewardPoolTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.DeckTrackerTests(); self.f.setUp()
        self.p = PowerLogParser(card_db=self.f.db); self.p.state = self.f.state
        for cid in LATORVIUS_REWARDS:
            self.f.db.cards[cid] = CardDefinition(cid,cid,card_type="MINION",cost=5)

    def feed(self,*rows):
        ingest_tracker_chunk(self.p,self.f.tracker,b"","".join(line(r) for r in rows).encode())

    def generate(self, offset=100):
        self.feed("BLOCK_START BlockType=POWER Entity=[entityName=Latorvius id=99 zone=PLAY zonePos=1 cardId=TLC_602t player=2] EffectCardId= EffectIndex=0 Target=0 SubOption=-1")
        for i in range(9):
            self.feed(f"FULL_ENTITY - Creating ID={offset+i} CardID=", "tag=CONTROLLER value=2",
                      f"tag=ZONE value={'HAND' if i<2 else 'DECK'}", "tag=CREATOR value=99")
        self.feed("BLOCK_END")

    def pool(self):
        return [r for r in self.f.tracker.state.opponent_display_rows if r.state=="REWARD POOL"]

    def test_two_hidden_rewards_never_get_assigned_guessed_positions(self):
        self.generate()
        self.assertEqual(9,len(self.pool()))
        self.assertEqual(7,self.f.tracker.state.opponent_deck_count)
        self.assertEqual(["", ""],[c.card_id for c in self.f.tracker.state.opponent_hand])
        self.assertTrue(all(r.zone=="DECK_OR_HAND" and r.draw_chance is None for r in self.pool()))

    def test_public_play_removes_pool_candidate_without_double_counting(self):
        self.generate()
        self.feed("SHOW_ENTITY - Updating Entity=100 CardID=UNG_028t","tag=CARDTYPE value=SPELL",
                  "TAG_CHANGE Entity=100 tag=ZONE value=GRAVEYARD")
        self.assertEqual(8,len(self.pool()))
        self.assertEqual(1,sum(r.count for r in self.f.tracker.state.opponent_display_rows if r.card_id=="UNG_028t"))

    def test_repeat_battlecry_and_game_reset_have_independent_pools(self):
        self.generate(); self.generate(200)
        self.assertEqual(18,sum(r.count for r in self.pool()))
        self.feed("CREATE_GAME")
        self.assertFalse(self.pool())
