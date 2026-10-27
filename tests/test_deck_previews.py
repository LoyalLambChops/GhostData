import unittest
from pathlib import Path
from ghostdata.tracking.models import GameState, EntityState
from ghostdata.tracking.card_db import CardDatabase, CardDefinition
from ghostdata.tracking.related_cards import related_cards, related_preview_kind
from ghostdata.tracking.parser import PowerLogParser
from ghostdata.tracking.deck_previews import DECK_RULES


class DeckPreviewTests(unittest.TestCase):
    def setUp(self):
        self.game = GameState(active=True, local_player_pid=1, current_player_pid=1)
        self.game.player(1); self.game.player(2)
        self.db = CardDatabase(Path("unused"))
        definitions = [
            CardDefinition("D", "Demon", card_type="MINION", races=("DEMON",)),
            CardDefinition("A", "All tribes", card_type="MINION", races=("ALL",)),
            CardDefinition("B", "Beast Dragon", card_type="MINION", races=("BEAST", "DRAGON")),
            CardDefinition("U", "Undead", card_type="MINION", races=("UNDEAD",)),
            CardDefinition("M", "Murloc", card_type="MINION", races=("MURLOC",)),
            CardDefinition("H", "Holy", card_type="SPELL", spell_school="HOLY"),
            CardDefinition("F", "Fire", card_type="SPELL", spell_school="FIRE"),
            CardDefinition("I", "Frost", card_type="SPELL", spell_school="FROST"),
            CardDefinition("JAIL_399t1", "Gang Demon", card_type="MINION", races=("DEMON",)),
            CardDefinition("EDR_978", "Meadowstrider", card_type="MINION", races=("BEAST",)),
            CardDefinition("TLC_451", "Catacombs", card_type="SPELL"),
        ]
        self.db.cards = {d.card_id:d for d in definitions}
        self.parser = PowerLogParser(card_db=self.db); self.parser.state = self.game
        self.card = EntityState(10, card_id="JAIL_510", controller=1, zone="HAND")
        self.game.entities[10] = self.card

    def preview(self, cid=None, deck=None):
        if cid: self.card.card_id = cid
        rows, label = related_cards(self.game, self.card, self.db, deck)
        return [r.card_id for r in rows], label

    def deck(self, eid, cid="", batch=0, pid=1):
        e = EntityState(eid, card_id=cid, controller=pid, zone="DECK")
        if batch: e.tags.update(GHOSTDATA_DECK_LOCATION="BOTTOM", GHOSTDATA_BOTTOM_BATCH=str(batch), GHOSTDATA_BOTTOM_CARD=cid)
        self.game.entities[eid] = e
        return e

    def lines(self, *lines, task=False):
        for line in lines:
            self.parser.parse_line(f'D 12:00:00.000 {"PowerTaskList" if task else "GameState"}.DebugPrintPower() - {line}\n')

    def block(self, cid, eid=50):
        self.lines(f'BLOCK_START BlockType=TRIGGER Entity=[entityName=Source id={eid} zone=PLAY zonePos=1 cardId={cid} player=1] EffectCardId= EffectIndex=0 Target=0 SubOption=-1')

    def create(self, eid):
        self.lines(f"FULL_ENTITY - Creating ID={eid} CardID=", "tag=CONTROLLER value=1", "tag=CARDTYPE value=MINION", "tag=ZONE value=DECK")

    def test_filters_use_inventory_preserve_duplicates_and_dual_tribes(self):
        ids, label = self.preview("EDR_226", ("D", "B", "B", "A", "H"))
        self.assertEqual(["B", "B", "A"], ids)
        self.assertIn("unknown deck identities", label)
        self.assertEqual(["H"], self.preview("BE_143", ("H", "F", "D"))[0])
        self.assertEqual(["A", "B", "M"], self.preview("CORE_KAR_061", ("A", "B", "D", "M"))[0])

    def test_missing_inventory_does_not_read_raw_hidden_deck_ids(self):
        self.deck(20, "B")
        self.assertEqual([], self.preview("EDR_226")[0])
        self.assertIn("unavailable", self.preview()[1])

    def test_empty_inventory_and_missing_definitions_are_distinct(self):
        self.assertIn("no tracked matches", self.preview("EDR_226", ())[1])
        self.assertIn("1 card definition", self.preview("EDR_226", ("UNKNOWN",))[1])

    def test_deck_discover_excludes_same_identity_not_just_entity(self):
        self.assertEqual(["H", "H"], self.preview("TLC_451", ("TLC_451", "H", "H"))[0])
        self.assertEqual(["H", "H", "B"], self.preview("CORE_DS1_184", ("H", "H", "B"))[0])

    def test_every_declared_rule_resolves_without_private_fallback(self):
        for cid in DECK_RULES:
            with self.subTest(cid=cid):
                self.assertIn("unavailable", self.preview(cid)[1])
                rows, label = self.preview(cid, ("D", "A", "B", "H", "F", "I", "U", "M"))
                self.assertTrue(label)
                self.assertNotIn("UNKNOWN", rows)

    def test_enemy_card_never_gets_friendly_inventory(self):
        self.card.controller = 2
        self.assertEqual(([], ""), self.preview("EDR_226", ("B",)))

    def test_bottom_demons_keep_known_duplicates_and_unknown_slot(self):
        self.deck(20, "D", 100); self.deck(21, "D", 100); self.deck(22)
        ids, label = self.preview()
        self.assertEqual(["D", "D"], ids)
        self.assertIn("1 position(s) not observed", label)

    def test_newer_bottom_batches_displace_older_cards(self):
        self.deck(20, "D", 100)
        self.deck(21, "B", 200); self.deck(22, "B", 200); self.deck(23, "B", 200)
        self.assertEqual([], self.preview()[0])
        self.assertNotIn("not observed", self.preview()[1])

    def test_cut_batch_lists_possibilities_not_guaranteed_summons(self):
        for i, cid in enumerate(("D", "B", "A", "D"), 20): self.deck(i, cid, 100)
        ids, label = self.preview()
        self.assertEqual(["D", "A", "D"], ids)
        self.assertIn("possible outcomes", label)

    def test_hidden_batch_member_is_not_a_negative_demon_result(self):
        self.deck(20, "", 100)
        ids, label = self.preview()
        self.assertEqual([], ids)
        self.assertIn("identities unresolved", label)

    def test_contingency_counts_all_types_and_small_deck(self):
        self.deck(20, "F", 100)
        self.assertEqual(["F"], self.preview("TIME_023")[0])
        self.assertNotIn("not observed", self.preview()[1])

    def test_unranked_dredge_and_opponent_identities_not_used(self):
        e = self.deck(20, "D"); e.tags["GHOSTDATA_DECK_LOCATION"] = "BOTTOM"
        self.deck(21, "D", 200, 2)
        self.assertEqual([], self.preview()[0])
        self.assertIn("not observed", self.preview()[1])

    def test_parser_tracks_actual_created_batch_and_removes_drawn_copy(self):
        self.deck(19)
        self.block("JAIL_399"); self.create(20); self.create(21); self.lines("BLOCK_END")
        self.assertEqual(["JAIL_399t1"] * 2, self.preview()[0])
        self.lines("TAG_CHANGE Entity=20 tag=ZONE value=HAND")
        self.assertEqual(["JAIL_399t1"], self.preview()[0])
        self.assertNotIn("GHOSTDATA_BOTTOM_BATCH", self.game.entities[20].tags)

    def test_shuffle_during_creating_effect_does_not_restore_order(self):
        self.block("JAIL_399"); self.create(20)
        self.lines("SHUFFLE_DECK PlayerID=1", "BLOCK_END")
        self.assertEqual([], self.preview()[0])

    def test_unlocated_insertion_invalidates_known_bottom_window(self):
        self.block("JAIL_399"); self.create(20); self.lines("BLOCK_END")
        self.create(21)
        self.assertEqual([], self.preview()[0])

    def test_nested_bottom_insertions_keep_chronological_batches(self):
        self.block("JAIL_399"); self.create(20)
        self.block("EDR_978", 51); self.create(21); self.lines("BLOCK_END")
        self.create(22); self.lines("BLOCK_END")
        batch = lambda eid: int(self.game.entities[eid].tags["GHOSTDATA_BOTTOM_BATCH"])
        self.assertLess(batch(20), batch(21)); self.assertLess(batch(21), batch(22))
        self.assertEqual(["JAIL_399t1", "EDR_978"], self.preview("TIME_023")[0])

    def test_hiding_or_shuffling_does_not_leave_old_preview_identity(self):
        self.block("JAIL_399"); self.create(20); self.lines("BLOCK_END")
        self.lines("HIDE_ENTITY - Entity=20 tag=ZONE value=DECK")
        self.assertEqual([], self.preview()[0])
        self.lines("SHUFFLE_DECK PlayerID=1")
        self.assertNotIn("GHOSTDATA_BOTTOM_BATCH", self.game.entities[20].tags)

    def test_reordering_effect_invalidates_bottom_without_shuffle_event(self):
        self.deck(20, "D", 100)
        self.lines('BLOCK_START BlockType=POWER Entity=[entityName=Discs id=51 zone=PLAY zonePos=1 cardId=BE_250 player=1] EffectCardId= EffectIndex=0 Target=0 SubOption=-1')
        self.assertEqual([], self.preview()[0])
        self.assertNotIn("GHOSTDATA_DECK_LOCATION", self.game.entities[20].tags)

    def test_changed_identity_never_uses_old_bottom_snapshot(self):
        e = self.deck(20, "D", 100); e.card_id = "B"
        self.assertEqual([], self.preview()[0])
        self.assertIn("identities unresolved", self.preview()[1])

    def test_hand_presentation_separates_results_from_deck_and_counter_context(self):
        for cid, kind in [("CAP_805t", "STORED"), ("JAIL_510", "RESULT"),
                          ("CORE_CFM_344", "RESULT"), ("FIR_941", "RESULT"),
                          ("TLC_106", "RESULT"), ("JAIL_500", "RESULT"),
                          ("CORE_DS1_184", "DECK"), ("EDR_226", "DECK"),
                          ("TIME_023", "DECK"), ("EDR_430", "HISTORY"),
                          ("TIME_714", "TARGET"), ("TIME_618", "SELF"),
                          ("JAIL_399", "GENERATED"), ("EDR_455", "DISCOVER")]:
            with self.subTest(cid=cid):
                self.card.card_id = cid
                self.assertEqual(kind, related_preview_kind(self.card, ("D",)))
                self.assertEqual("", related_preview_kind(self.card, ()))

    def test_fixed_generation_is_capped_preview_not_mutation(self):
        self.card.card_id = "JAIL_399"
        rows, label = related_cards(self.game, self.card, self.db)
        self.assertEqual(("JAIL_399t1", 2), (rows[0].card_id, rows[0].count))
        self.assertIn("can create up to 2", label)
        self.assertEqual(1, len(self.game.entities))


if __name__ == "__main__": unittest.main()
