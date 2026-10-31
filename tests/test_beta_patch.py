import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ghostdata import match_decks, recorder
from ghostdata.models import DeckSnapshot, MatchRecord
from ghostdata.store import MatchStore
from ghostdata.tracking.models import GameState, EntityState
from ghostdata.tracking.card_db import CardDefinition
from ghostdata.tracking.entity_text import card_text
import test_live_deck_tracker as fixtures
import test_overdraw as overdraw_fixtures


class PatchTests(unittest.TestCase):
    def test_private_construction_without_discover_tag_never_appears(self):
        f=fixtures.DeckTrackerTests();f.setUp()
        e=f._emit_zone(900,2,"SETASIDE",creator=17)
        e.card_type="MINION"
        f._reveal(900,"OPP_B")
        f._emit_zone(900,2,"GRAVEYARD")
        self.assertFalse(f.tracker.state.opponent_display_rows)
        self.assertFalse(f.tracker.state.opponent_rows)
        # The real chosen card remains hidden; only its later public play counts.
        f._emit_zone(901,2,"SETASIDE",creator=17)
        f._emit_zone(901,2,"HAND")
        self.assertFalse(f.tracker.state.opponent_hand[0].card_id)
        f._emit_zone(901,2,"PLAY","OPP_B",creator=17)
        f._reveal(901,"OPP_B")
        self.assertEqual([r.card_id for r in f.tracker.state.opponent_display_rows],["OPP_B"])

    def test_atlas_history_copy_does_not_make_unknown_recovery_row(self):
        f=overdraw_fixtures.OverdrawTests();f.setUp()
        f.lines("FULL_ENTITY - Creating ID=99 CardID=JAIL_509e", "tag=CONTROLLER value=1", "tag=ZONE value=PLAY",
            "FULL_ENTITY - Creating ID=100 CardID=CARD_2", "tag=CONTROLLER value=1", "tag=ZONE value=DECK",
            "BLOCK_START BlockType=TRIGGER Entity=[entityName=Atlas id=99 zone=PLAY zonePos=0 cardId=JAIL_509e player=1] EffectCardId= EffectIndex=0 Target=0 TriggerKeyword=TRIGGER_VISUAL",
            "FULL_ENTITY - Creating ID=200 CardID=CARD_2", "tag=CONTROLLER value=1", "tag=CARDTYPE value=SPELL", "tag=ZONE value=SETASIDE", "tag=COPIED_FROM_ENTITY_ID value=100",
            "FULL_ENTITY - Creating ID=201 CardID=CARD_2", "tag=CONTROLLER value=1", "tag=CARDTYPE value=SPELL", "tag=ZONE value=SETASIDE", "tag=COPIED_FROM_ENTITY_ID value=200", "BLOCK_END",
            "META_DATA - Meta=BURNED_CARD Data=0 InfoCount=1", "Info[0] = 100")
        self.assertEqual([r.card_id for r in f.f.tracker.state.player_overdraw_rows],["CARD_2"])
        f.lines("TAG_CHANGE Entity=200 tag=ZONE value=HAND")
        self.assertFalse(f.f.tracker.state.player_overdraw_rows)

    def test_modular_trial_uses_each_instances_components(self):
        defs=[CardDefinition(card_id="TRIAL",name="Grueling Trial",text="In 1 turn, {0} {1}",text_builder="MODULAR_ENTITY"),
              CardDefinition(card_id="A",name="A",text="Draw 3 cards.",dbf_id=1),
              CardDefinition(card_id="B",name="B",text="Restore #12 Health to your hero.",dbf_id=2)]
        db=fixtures.FakeCardDb(defs);a=EntityState(1,card_id="TRIAL");a.tags={"MODULAR_ENTITY_PART_1":"1","MODULAR_ENTITY_PART_2":"2"}
        self.assertEqual(card_text(a,db),"In 1 turn, Draw 3 cards. Restore #12 Health to your hero.")
        b=EntityState(2,card_id="TRIAL");b.tags={"MODULAR_ENTITY_PART_1":"2","MODULAR_ENTITY_PART_2":"1"}
        self.assertEqual(card_text(b,db),"In 1 turn, Restore #12 Health to your hero. Draw 3 cards.")
        a.tags.pop("MODULAR_ENTITY_PART_2")
        self.assertIn("{1}",card_text(a,db))

    def test_bound_identity_recovers_existing_record_after_source_stops_changing(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);log=root/"Power.log";log.write_text("fixture")
            data=root/"data";data.mkdir()
            row=MatchRecord("one","2026-10-29T12:00:00+00:00","WIN","WARLOCK","MAGE","FIRST",source_session=root.name,game_index=1)
            with patch.object(recorder,"parse_completed_games",side_effect=lambda _: [copy.deepcopy(row)]), patch.object(recorder,"ensure_history_epoch",return_value=__import__('datetime').datetime(2000,1,1,tzinfo=__import__('datetime').timezone.utc)):
                recorder.record_once(root,power_log=log,data_dir=data)
                self.assertFalse(MatchStore(data).load()[0].deck_name)
                game=GameState(active=True,game_number=1,local_player_pid=1);game.player(1).player_class="WARLOCK";game.game_tags["GHOSTDATA_GAME_START"]="12:00:00"
                deck=DeckSnapshot(deck_name="ZooYork",selected_deck_id="7",player_class="WARLOCK",composition_hash="ABC",sensor_status="EXACT",game_context=True)
                self.assertTrue(match_decks.bind(log,game,deck,data))
                recorder.record_once(root,power_log=log,data_dir=data)
                self.assertEqual(MatchStore(data).load()[0].deck_name,"ZooYork")
                self.assertEqual(MatchStore(data).load()[0].data_quality,"COMPLETE")
                shifted=copy.deepcopy(row);shifted.started_at="2026-10-29T13:00:00+00:00"
                self.assertIsNone(match_decks.lookup(match_decks.load(data),log,shifted))
                deck.deck_name="Different";self.assertFalse(match_decks.bind(log,game,deck,data))
                other=copy.deepcopy(row);other.game_index=2
                self.assertIsNone(match_decks.lookup(match_decks.load(data),log,other))
                game.game_number=2;deck.game_context=False
                self.assertFalse(match_decks.bind(log,game,deck,data))
                deck.game_context=True;game.complete=True
                self.assertFalse(match_decks.bind(log,game,deck,data))


class MulliganVisibilityTests(unittest.TestCase):
    def test_setup_identity_waits_for_fresh_post_mulligan_reveal(self):
        from ghostdata.tracking.parser import PowerLogParser
        from ghostdata.tracker_bridge import ingest_tracker_chunk
        f=fixtures.DeckTrackerTests(); f.setUp()
        f.state.game_tags["GHOSTDATA_GAME_START"]="12:00:00"
        f.state.local_player_pid=None
        parser=PowerLogParser(card_db=f.db); parser.state=f.state
        def line(payload, task=False):
            stream="PowerTaskList" if task else "GameState"
            ingest_tracker_chunk(parser,f.tracker,b"",f"D 12:00:00.000 {stream}.DebugPrintPower() - {payload}\n".encode())
        line("FULL_ENTITY - Creating ID=900 CardID=")
        line("tag=ZONE value=DECK")
        line("tag=CONTROLLER value=2")
        for task in (False,True):
            line("SHOW_ENTITY - Updating Entity=900 CardID=OPP_A",task)
        f.state.local_player_pid=1
        f.tracker.observe(f.state)
        self.assertFalse(f.tracker.state.opponent_rows)
        self.assertFalse(f.tracker.state.opponent_display_rows)
        f.state.players[1].tags["MULLIGAN_STATE"]="DONE"
        f.state.players[2].tags["MULLIGAN_STATE"]="INPUT"
        line("SHOW_ENTITY - Updating Entity=900 CardID=OPP_A")
        self.assertFalse(f.tracker.state.opponent_display_rows)
        f.state.players[2].tags["MULLIGAN_STATE"]="DONE"
        f.tracker.observe(f.state)
        self.assertFalse(f.tracker.state.opponent_display_rows)
        line("SHOW_ENTITY - Updating Entity=900 CardID=OPP_A")
        self.assertEqual([row.card_id for row in f.tracker.state.opponent_display_rows],["OPP_A"])
