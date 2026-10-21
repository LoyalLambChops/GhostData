import unittest

from ghostdata.tracking.parser import PowerLogParser
from ghostdata.tracker_bridge import ingest_tracker_chunk
from ghostdata.tracking.public_effects import _FIXED, base_id
import test_live_deck_tracker as fixture


class PublicEffectTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.DeckTrackerTests()
        self.f.setUp()
        self.parser = PowerLogParser(card_db=self.f.db)
        self.parser.state = self.f.state
        self.f.state.global_turn = 5

    def lines(self, *lines, task=False):
        stream = "PowerTaskList" if task else "GameState"
        raw = "".join(f"D 12:00:00.000 {stream}.DebugPrintPower() - {line}\n" for line in lines)
        ingest_tracker_chunk(self.parser, self.f.tracker, b"", raw.encode())

    def block(self, cid, kind="POWER", eid=99, target="0"):
        self.lines(f"BLOCK_START BlockType={kind} Entity=[entityName=Source id={eid} zone=PLAY zonePos=1 cardId={cid} player=2] EffectCardId= EffectIndex=0 Target={target} SubOption=-1")

    def create(self, eid=100, zone="HAND", kind="SPELL", creator=99):
        self.lines(f"FULL_ENTITY - Creating ID={eid} CardID=",
                   "tag=CONTROLLER value=2", f"tag=CARDTYPE value={kind}",
                   f"tag=ZONE value={zone}", f"tag=CREATOR value={creator}")

    def test_all_fixed_effects_only_identify_actual_creations(self):
        for (source, kind), (expected, cap, location) in _FIXED.items():
            with self.subTest(source=source, kind=kind):
                self.setUp()
                self.block(source, kind)
                self.create(zone="DECK" if location else "HAND")
                self.lines("BLOCK_END")
                self.assertEqual(expected, self.f.state.entity(100).card_id)
                self.assertEqual(1, sum(r.count for r in self.f.tracker.state.opponent_display_rows if r.card_id == expected))
                self.assertEqual(location, self.f.state.entity(100).tags.get("GHOSTDATA_DECK_LOCATION", ""))

    def test_cancelled_effect_creates_no_prediction(self):
        self.block("TLC_902")
        self.lines("BLOCK_END")
        self.assertFalse(any(r.card_id == "TLC_630t" for r in self.f.tracker.state.opponent_display_rows))

    def test_nested_effect_cannot_consume_parent_prediction(self):
        self.block("TLC_902")
        self.block("UNKNOWN", eid=98)
        self.create(100, creator=98)
        self.lines("BLOCK_END")
        self.create(101)
        self.lines("BLOCK_END")
        self.assertEqual("", self.f.state.entity(100).card_id)
        self.assertEqual("TLC_630t", self.f.state.entity(101).card_id)

    def test_enchantments_do_not_consume_and_batches_do_not_spill(self):
        self.block("CORE_SW_108")
        self.create(100, kind="ENCHANTMENT", zone="PLAY")
        self.create(101)
        self.create(102)
        self.lines("BLOCK_END")
        self.create(103)
        self.assertEqual("SW_108t", self.f.state.entity(101).card_id)
        self.assertEqual("", self.f.state.entity(100).card_id)
        self.assertEqual("", self.f.state.entity(102).card_id)
        self.assertEqual("", self.f.state.entity(103).card_id)

    def test_task_duplicates_cannot_create_extra_predictions(self):
        self.block("TLC_902")
        self.create(100)
        self.lines("BLOCK_END")
        self.lines("BLOCK_START BlockType=POWER Entity=[entityName=Source id=99 zone=PLAY zonePos=1 cardId=TLC_902 player=2] EffectCardId= EffectIndex=0 Target=0 SubOption=-1",
                   "FULL_ENTITY - Creating ID=100 CardID=", "tag=ZONE value=HAND", "BLOCK_END", task=True)
        self.assertEqual(1, sum(r.count for r in self.f.tracker.state.opponent_display_rows if r.card_id == "TLC_630t"))

    def test_task_only_creation_has_same_public_prediction(self):
        self.lines("BLOCK_START BlockType=POWER Entity=[entityName=Source id=99 zone=PLAY zonePos=1 cardId=TLC_902 player=2] EffectCardId= EffectIndex=0 Target=0 SubOption=-1",
                   "FULL_ENTITY - Creating ID=100 CardID=", "tag=CONTROLLER value=2",
                   "tag=CARDTYPE value=SPELL", "tag=ZONE value=HAND", "tag=CREATOR value=99",
                   "BLOCK_END", task=True)
        self.assertEqual("TLC_630t", self.f.tracker.state.opponent_hand[0].card_id)

    def test_blackhorn_temporary_reveals_stay_private_in_both_streams(self):
        self.f._emit_zone(100, 2, "DECK")
        self.block("CATA_720")
        self.lines("SHOW_ENTITY - Updating Entity=100 CardID=OPP_A",
                   "TAG_CHANGE Entity=[entityName=Hidden id=100 zone=DECK zonePos=0 cardId=OPP_A player=2] tag=ZONE value=GRAVEYARD",
                   "BLOCK_END")
        self.lines("BLOCK_START BlockType=POWER Entity=[entityName=Source id=99 zone=PLAY zonePos=1 cardId=CATA_720 player=2] EffectCardId= EffectIndex=0 Target=0 SubOption=-1",
                   "SHOW_ENTITY - Updating Entity=100 CardID=OPP_A", "BLOCK_END", task=True)
        self.assertEqual("", self.f.state.entity(100).card_id)
        self.assertFalse(any(r.card_id == "OPP_A" for r in self.f.tracker.state.opponent_display_rows))
        self.lines("SHOW_ENTITY - Updating Entity=100 CardID=OPP_A")
        self.assertTrue(any(r.card_id == "OPP_A" for r in self.f.tracker.state.opponent_display_rows))

    def test_blackhorn_keeps_local_destroyed_card_accounting(self):
        self.f._emit_zone(100, 1, "DECK")
        self.block("CATA_720")
        self.lines("SHOW_ENTITY - Updating Entity=100 CardID=CARD_1",
                   "TAG_CHANGE Entity=100 tag=ZONE value=GRAVEYARD", "BLOCK_END")
        row = next(r for r in self.f.tracker.state.player_display_rows if r.card_id == "CARD_1")
        self.assertEqual(1, row.count)

    def test_override_history_suppresses_unrevealed_identity(self):
        self.f._emit_zone(100, 2, "DECK")
        self.block("UNKNOWN")
        self.lines("META_DATA - Meta=OVERRIDE_HISTORY Data=0 InfoCount=0",
                   "SHOW_ENTITY - Updating Entity=100 CardID=OPP_A", "BLOCK_END")
        self.assertEqual("", self.f.state.entity(100).card_id)

    def test_public_target_copy_uses_target_not_unknown_hidden_source(self):
        target = "[entityName=Target id=98 zone=PLAY zonePos=1 cardId=OPP_A player=2]"
        self.block("CORE_LOOT_516", target=target)
        self.create(100, kind="MINION")
        self.lines("BLOCK_END")
        self.assertEqual("OPP_A", self.f.state.entity(100).card_id)

    def test_effects_reset_between_games(self):
        self.block("TLC_902")
        self.lines("CREATE_GAME")
        self.create(100)
        self.lines("BLOCK_END")
        self.assertEqual("", self.parser.state.entity(100).card_id)

    def test_random_generation_shows_constraints_without_identity_or_hover(self):
        self.block("CATA_190t13")
        self.create(100, "DECK", "MINION")
        self.lines("BLOCK_END")
        row = next(r for r in self.f.tracker.state.opponent_display_rows if r.name == "Unknown Legendary Dragon")
        self.assertEqual(("", 1, 1, "DECK"), (row.card_id, row.cost, row.count, row.zone))
        self.lines("TAG_CHANGE Entity=100 tag=ZONE value=HAND")
        self.assertEqual("Unknown Legendary Dragon", self.f.tracker.state.opponent_hand[0].name)
        self.lines("SHOW_ENTITY - Updating Entity=100 CardID=OPP_A")
        self.assertFalse(any(r.name == "Unknown Legendary Dragon" for r in self.f.tracker.state.opponent_display_rows))
        self.assertEqual("OPP_A", self.f.tracker.state.opponent_hand[0].card_id)

    def test_local_random_generation_counts_known_created_entities(self):
        self.lines("BLOCK_START BlockType=POWER Entity=[entityName=Source id=99 zone=PLAY zonePos=1 cardId=CATA_136 player=1] EffectCardId= EffectIndex=0 Target=0 SubOption=-1",
                   "FULL_ENTITY - Creating ID=100 CardID=", "tag=CONTROLLER value=1",
                   "tag=CARDTYPE value=MINION", "tag=ZONE value=DECK", "tag=CREATOR value=99", "BLOCK_END")
        self.assertEqual(1, self.f.tracker.state.player_known_non_original_in_deck)
        self.assertTrue(any(r.name == "Unknown 8+ Cost minion" for r in self.f.tracker.state.player_display_rows))

    def test_ectoplasm_only_uses_displayed_creator_for_both_players(self):
        source = self.f.state.entity(99); source.card_id = "CAP_805"; source.controller = 1
        self.create(100, "SETASIDE")
        self.create(101, "SETASIDE")
        self.lines("TAG_CHANGE Entity=100 tag=DISPLAYED_CREATOR value=99",
                   "TAG_CHANGE Entity=100 tag=ZONE value=HAND")
        self.assertEqual("CAP_805t", self.f.state.entity(100).card_id)
        self.assertEqual("", self.f.state.entity(101).card_id)
        self.assertTrue(any(r.card_id == "CAP_805t" for r in self.f.tracker.state.opponent_display_rows))

    def test_generic_discover_copy_does_not_reveal_opponent_position(self):
        self.f._emit_zone(100, 2, "HAND")
        self.lines("FULL_ENTITY - Creating ID=101 CardID=CARD_1",
                   "tag=CONTROLLER value=1", "tag=CARDTYPE value=SPELL",
                   "tag=ZONE value=HAND", "tag=COPIED_FROM_ENTITY_ID value=100")
        self.assertEqual("", self.f.tracker.state.opponent_hand[0].card_id)

    def test_ursol_public_aura_backfills_original_spell(self):
        source = self.f.state.entity(99); source.card_id = "EDR_259"; source.controller = 2
        self.f._emit_zone(100, 2, "HAND")
        self.lines("FULL_ENTITY - Creating ID=101 CardID=OPP_A",
                   "tag=CONTROLLER value=2", "tag=CARDTYPE value=SPELL", "tag=ZONE value=SECRET",
                   "tag=CREATOR value=99", "tag=COPIED_FROM_ENTITY_ID value=100")
        self.assertEqual("OPP_A", self.f.state.entity(100).card_id)

    def test_duplicate_hide_does_not_undo_later_public_show(self):
        self.f._emit_zone(100, 2, "HAND")
        self.lines("SHOW_ENTITY - Updating Entity=100 CardID=OPP_A",
                   "HIDE_ENTITY - Entity=100 tag=ZONE value=HAND",
                   "SHOW_ENTITY - Updating Entity=100 CardID=OPP_A")
        self.lines("HIDE_ENTITY - Entity=100 tag=ZONE value=HAND", task=True)
        self.assertEqual("OPP_A", self.f.tracker.state.opponent_hand[0].card_id)

    def test_hide_inline_identity_is_not_a_reveal(self):
        self.f._emit_zone(100, 2, "HAND")
        self.lines("HIDE_ENTITY - Entity=[entityName=Hidden id=100 zone=HAND zonePos=1 cardId=OPP_A player=2] tag=ZONE value=HAND")
        self.assertEqual("", self.f.state.entity(100).card_id)
        self.assertFalse(self.f.tracker.state.opponent_display_rows)

    def test_far_sight_draw_preserves_original_deck_accounting(self):
        source = self.f.state.entity(99); source.card_id = "CORE_CS2_053"; source.controller = 1
        self.f._emit_zone(100, 1, "DECK", "CARD_1")
        self.lines("TAG_CHANGE Entity=100 tag=DISPLAYED_CREATOR value=99",
                   "TAG_CHANGE Entity=100 tag=ZONE value=HAND")
        row = next(r for r in self.f.tracker.state.player_display_rows if r.card_id == "CARD_1")
        self.assertEqual((1, 1, "ORIGINAL_DECK"), (row.count, row.in_hand, row.provenance))

    def test_bottom_placement_is_displayed_and_cleared_on_shuffle(self):
        self.block("EDR_978", "TRIGGER")
        self.create(100, "DECK", "MINION")
        self.lines("BLOCK_END")
        row = next(r for r in self.f.tracker.state.opponent_display_rows if r.card_id == "EDR_978")
        self.assertEqual("BOTTOM", row.state)
        self.lines("SHUFFLE_DECK PlayerID=2")
        row = next(r for r in self.f.tracker.state.opponent_display_rows if r.card_id == "EDR_978")
        self.assertEqual("SEEN", row.state)

    def test_beatrix_public_history_identifies_only_its_actual_copies(self):
        self.block("JAIL_397", "TRIGGER")
        self.create(100, "DECK", "MINION")
        self.create(101, "DECK", "MINION")
        self.lines("META_DATA - Meta=HISTORY_TARGET Data=0 InfoCount=1",
                   "Info[0] = [entityName=Chosen id=103 zone=SETASIDE zonePos=0 cardId=OPP_A player=2]",
                   "BLOCK_END")
        self.assertEqual("OPP_A", self.f.state.entity(100).card_id)
        self.assertEqual(2, sum(r.count for r in self.f.tracker.state.opponent_display_rows if r.card_id == "OPP_A"))

    def test_eyes_in_the_sky_reveals_linked_deck_card_without_hand_guess(self):
        self.f._emit_zone(100, 2, "DECK")
        source = self.f.state.entity(99); source.card_id = "TLC_521"; source.controller = 1
        self.lines("FULL_ENTITY - Creating ID=101 CardID=OPP_A",
                   "tag=CONTROLLER value=1", "tag=CARDTYPE value=MINION", "tag=ZONE value=SETASIDE",
                   "tag=CREATOR value=99", "tag=LINKED_ENTITY value=100")
        self.assertEqual("OPP_A", self.f.state.entity(100).card_id)
        self.assertTrue(any(r.card_id == "OPP_A" and r.zone == "DECK" for r in self.f.tracker.state.opponent_display_rows))

    def test_bottom_copy_does_not_reduce_random_copy_probability_twice(self):
        for eid in range(1, 31):
            self.f._emit_zone(eid, 1, "DECK")
        self.lines("BLOCK_START BlockType=TRIGGER Entity=[entityName=Source id=99 zone=PLAY zonePos=1 cardId=JAIL_399 player=1] EffectCardId= EffectIndex=0 Target=0 SubOption=-1",
                   "FULL_ENTITY - Creating ID=100 CardID=", "tag=CONTROLLER value=1",
                   "tag=CARDTYPE value=MINION", "tag=ZONE value=DECK", "tag=CREATOR value=99", "BLOCK_END",
                   "FULL_ENTITY - Creating ID=101 CardID=JAIL_399t1", "tag=CONTROLLER value=1",
                   "tag=CARDTYPE value=MINION", "tag=ZONE value=DECK", "tag=CREATOR value=98")
        rows = {r.state:r for r in self.f.tracker.state.player_display_rows if r.card_id == "JAIL_399t1"}
        self.assertEqual(0, rows["BOTTOM"].draw_chance)
        self.assertEqual(3.2, rows["DECK"].draw_chance)
        self.lines("SHUFFLE_DECK PlayerID=1")
        row = next(r for r in self.f.tracker.state.player_display_rows if r.card_id == "JAIL_399t1")
        self.assertEqual((2, 6.2), (row.count, row.draw_chance))

    def test_delayed_task_animation_does_not_hide_next_canonical_play(self):
        self.f._emit_zone(100, 2, "HAND")
        self.lines("BLOCK_START BlockType=TRIGGER Entity=[entityName=Source id=99 zone=HAND zonePos=1 cardId=JAIL_397 player=2] EffectCardId= EffectIndex=4 Target=0 SubOption=-1",
                   "META_DATA - Meta=OVERRIDE_HISTORY Data=0 InfoCount=1", task=True)
        self.lines("SHOW_ENTITY - Updating Entity=100 CardID=OPP_A",
                   "TAG_CHANGE Entity=100 tag=ZONE value=PLAY")
        self.assertTrue(any(r.card_id == "OPP_A" for r in self.f.tracker.state.opponent_display_rows))

    def test_hidden_creation_without_card_type_is_resolved_from_public_effect(self):
        from ghostdata.tracking.card_db import CardDefinition
        self.f.db.cards["SW_108t"] = CardDefinition("SW_108t", "Second Flame", card_type="SPELL", cost=1)
        self.block("CORE_SW_108")
        self.lines("FULL_ENTITY - Creating ID=100 CardID=", "tag=ZONE value=HAND",
                   "tag=CONTROLLER value=2", "tag=ENTITY_ID value=100", "BLOCK_END")
        self.assertEqual("SW_108t", self.f.tracker.state.opponent_hand[0].card_id)

    def test_shuffle_does_not_reveal_which_known_card_was_drawn(self):
        self.f._emit_zone(100, 2, "DECK", "OPP_A")
        self.f._reveal(100, "OPP_A")
        self.lines("SHUFFLE_DECK PlayerID=2", "TAG_CHANGE Entity=100 tag=ZONE value=HAND")
        self.assertEqual("", self.f.tracker.state.opponent_hand[0].card_id)
        self.assertEqual("SEEN", self.f.tracker.state.opponent_display_rows[0].zone)

    def test_duplicate_shuffle_preserves_later_public_peek(self):
        self.f._emit_zone(100, 2, "DECK", "OPP_A")
        self.lines("SHUFFLE_DECK PlayerID=2", "SHOW_ENTITY - Updating Entity=100 CardID=OPP_A")
        self.lines("SHUFFLE_DECK PlayerID=2", task=True)
        self.lines("TAG_CHANGE Entity=100 tag=ZONE value=HAND")
        self.assertEqual("OPP_A", self.f.tracker.state.opponent_hand[0].card_id)

    def test_creation_resolution_preserves_deck_concealment(self):
        self.block("EDR_978", "TRIGGER")
        self.create(100, "DECK", "MINION")
        self.lines("HIDE_ENTITY - Entity=100 tag=ZONE value=DECK", "BLOCK_END",
                   "TAG_CHANGE Entity=100 tag=ZONE value=HAND")
        self.assertEqual("", self.f.tracker.state.opponent_hand[0].card_id)

    def test_local_dredge_options_bottom_selection_top_and_shuffle(self):
        source = self.f.state.entity(99); source.controller = 1; source.tags["DREDGE"] = "1"
        self.f._emit_zone(100, 1, "DECK")
        self.f._emit_zone(102, 1, "DECK")
        self.lines("BLOCK_START BlockType=POWER Entity=99 EffectCardId= EffectIndex=0 Target=0 SubOption=-1",
                   "FULL_ENTITY - Creating ID=101 CardID=CARD_1", "tag=CONTROLLER value=1",
                   "tag=ZONE value=SETASIDE", "tag=CREATOR value=99",
                   "tag=COPIED_FROM_ENTITY_ID value=100", "tag=LINKED_ENTITY value=100")
        self.assertEqual("BOTTOM", self.f.state.entity(100).tags["GHOSTDATA_DECK_LOCATION"])
        self.assertEqual("CARD_1", self.f.state.entity(100).card_id)
        self.lines("SHOW_ENTITY - Updating Entity=100 CardID=CARD_1", "BLOCK_END")
        self.assertEqual("TOP", self.f.state.entity(100).tags["GHOSTDATA_DECK_LOCATION"])
        self.lines("SHUFFLE_DECK PlayerID=1")
        self.assertNotIn("GHOSTDATA_DECK_LOCATION", self.f.state.entity(100).tags)

    def test_enemy_dredge_does_not_reveal_options(self):
        source = self.f.state.entity(99); source.controller = 2; source.tags["DREDGE"] = "1"
        self.f._emit_zone(100, 2, "DECK")
        self.lines("FULL_ENTITY - Creating ID=101 CardID=", "tag=CONTROLLER value=2",
                   "tag=ZONE value=SETASIDE", "tag=CREATOR value=99",
                   "tag=COPIED_FROM_ENTITY_ID value=100", "tag=LINKED_ENTITY value=100")
        self.assertNotIn("GHOSTDATA_DECK_LOCATION", self.f.state.entity(100).tags)

    def test_top_order_draw_probability_counts_only_the_actual_copy(self):
        for eid in range(1,31): self.f._emit_zone(eid,1,"DECK")
        self.f._reveal(1,"CARD_1"); self.f._reveal(2,"CARD_2")
        self.f._emit_zone(101,1,"DECK","CARD_1",creator=99)
        self.f.state.entity(1).tags.update(GHOSTDATA_DECK_LOCATION="TOP",GHOSTDATA_DECK_INDEX="200")
        self.f.state.entity(2).tags.update(GHOSTDATA_DECK_LOCATION="TOP",GHOSTDATA_DECK_INDEX="199")
        self.f.tracker.observe(self.f.state)
        rows=self.f.tracker.state.player_display_rows
        self.assertEqual(100,sum(r.draw_chance or 0 for r in rows))
        self.assertEqual("ORIGINAL_DECK",next(r for r in rows if r.draw_chance==100).provenance)
        self.lines("TAG_CHANGE Entity=1 tag=ZONE value=HAND")
        self.assertEqual("CARD_2",next(r for r in self.f.tracker.state.player_display_rows if r.draw_chance==100).card_id)

    def test_copy_discover_identity_is_unlocated_and_consumed_on_reveal(self):
        for source_id, zone in [("EDR_528", "DECK"), ("TIME_039", "HAND")]:
            with self.subTest(source=source_id):
                self.setUp()
                self.f._emit_zone(100, 2, zone)
                self.lines(f"BLOCK_START BlockType=POWER Entity=[entityName=Source id=99 zone=PLAY zonePos=1 cardId={source_id} player=1] EffectCardId= EffectIndex=0 Target=0 SubOption=-1",
                           "FULL_ENTITY - Creating ID=101 CardID=OPP_A", "tag=CONTROLLER value=1",
                           "tag=ZONE value=SETASIDE", "tag=CREATOR value=99",
                           "tag=COPIED_FROM_ENTITY_ID value=100", "BLOCK_END")
                self.assertEqual("", self.f.state.entity(100).card_id)
                self.assertTrue(any(r.state == "KNOWN COPY" for r in self.f.tracker.state.opponent_display_rows))
                self.assertFalse(any(r.card_id for r in self.f.tracker.state.opponent_hand))
                self.lines("SHOW_ENTITY - Updating Entity=100 CardID=OPP_A", "TAG_CHANGE Entity=100 tag=ZONE value=PLAY")
                self.assertFalse(any(r.state == "KNOWN COPY" for r in self.f.tracker.state.opponent_display_rows))


if __name__ == "__main__":
    unittest.main()
