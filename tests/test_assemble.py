import unittest
from dataclasses import replace

import test_live_deck_tracker as fixture
from ghostdata.tracking.parser import PowerLogParser


class AssembleTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.DeckTrackerTests()
        self.f.setUp()
        for cid, text in (("OPP_A", "Second component rules."), ("OPP_B", "Original body rules.")):
            card = replace(self.f.db.cards[cid], text=text)
            self.f.db.cards[cid] = card
            self.f.db.cards_by_dbf[card.dbf_id] = card

    def assemble(self, eid, owner=1, rules="101"):
        entity = self.f.state.entity(eid)
        entity.tags.update(ASSEMBLED_MINION="1", CRAFTABLE_SECOND_HALF_DBID=rules,
                           ATK="3", HEALTH="4", COST="3")
        self.f._emit_zone(eid, owner, "HAND", "OPP_B", creator=99)
        return entity

    def test_distinct_rules_and_costs_do_not_merge_and_override_body_text(self):
        self.assemble(100)
        self.assemble(101, rules="999999")
        entity = self.assemble(102)
        entity.tags["COST"] = "1"
        self.f.tracker.observe(self.f.state)
        rows = [r for r in self.f.tracker.state.player_display_rows if r.card_id == "OPP_B"]
        self.assertEqual(3, len(rows))
        self.assertEqual([1, 3, 3], sorted(r.cost for r in rows))
        self.assertTrue(all("Original body rules" not in r.text for r in rows))
        self.assertTrue(any("Second component rules." in r.text for r in rows))
        self.assertTrue(any("Rules unavailable" in r.text for r in rows))

    def test_hidden_opponent_components_require_public_reveal(self):
        self.assemble(100, owner=2)
        self.assertEqual("", self.f.tracker.state.opponent_hand[0].card_id)
        self.assertFalse(self.f.tracker.state.opponent_display_rows)
        self.f._reveal(100, "OPP_B")
        self.assertIn("Second component rules.", self.f.tracker.state.opponent_hand[0].text)
        self.f.state.emit("00:00:00", "HIDE", "", entity_id=100)
        self.f.tracker.observe(self.f.state)
        self.assertEqual("", self.f.tracker.state.opponent_hand[0].text)
        self.assertNotIn("Second component", self.f.tracker.state.opponent_display_rows[0].text)

    def test_public_show_entity_tags_reach_composed_preview(self):
        self.f._emit_zone(100, 2, "HAND")
        parser = PowerLogParser(card_db=self.f.db)
        parser.state = self.f.state
        for detail in ("SHOW_ENTITY - Updating Entity=100 CardID=OPP_B",
                       "    tag=ASSEMBLED_MINION value=1",
                       "    tag=CRAFTABLE_SECOND_HALF_DBID value=101",
                       "    tag=COST value=3", "    tag=ATK value=3", "    tag=HEALTH value=4"):
            parser.parse_line("D 12:00:00.000 GameState.DebugPrintPower() - " + detail + "\n")
            self.f.tracker.observe(parser.state)
        row = self.f.tracker.state.opponent_display_rows[0]
        self.assertEqual("Opponent B + Opponent A", row.name)
        self.assertEqual(3, row.cost)
        self.assertIn("Second component rules.", row.text)
