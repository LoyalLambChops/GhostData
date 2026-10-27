import unittest
from dataclasses import replace
from pathlib import Path
from ghostdata.tracking.models import GameState, EntityState
from ghostdata.tracking.card_db import CardDatabase, CardDefinition
from ghostdata.tracking.card_history import observe
from ghostdata.tracking.related_cards import related_cards
from ghostdata.tracking.parser import PowerLogParser


class RelatedHistoryTests(unittest.TestCase):
    def setUp(self):
        self.g = GameState(active=True, local_player_pid=1, current_player_pid=1, global_turn=3)
        self.g.player(1); self.g.player(2)
        self.db = CardDatabase(Path("unused"))
        definitions = [
            CardDefinition("A", "Small Dragon", card_type="MINION", cost=1, races=("DRAGON",)),
            CardDefinition("B", "Large Undead", card_type="MINION", cost=8, races=("UNDEAD",), mechanics=("DEATHRATTLE",)),
            CardDefinition("C", "Dual Tribe", card_type="MINION", cost=8, races=("DRAGON", "UNDEAD")),
            CardDefinition("D", "Small Rattle", card_type="MINION", cost=3, mechanics=("DEATHRATTLE",)),
            CardDefinition("H", "Holy Spell", card_type="SPELL", cost=2, spell_school="HOLY"),
            CardDefinition("F", "Fire Spell", card_type="SPELL", cost=1, spell_school="FIRE"),
            CardDefinition("Z", "Zero", card_type="MINION", cost=0),
        ]
        self.db.cards = {c.card_id:c for c in definitions}
        self.p = PowerLogParser(card_db=self.db); self.p.state=self.g
        self.next_id=10
    def entity(self,cid,pid=1,zone="HAND"):
        self.next_id+=1
        d=self.db.get(cid)
        e=EntityState(self.next_id,card_id=cid,controller=pid,zone=zone,
                      card_type=d.card_type if d else "MINION",cost=d.cost if d else 5)
        self.g.entities[e.entity_id]=e
        return e
    def record(self,cid,kind="DEATH",pid=1,turn=3,source=None):
        e=self.entity(cid,pid)
        observe(self.g,e,self.db,kind,source,turn)
        return e
    def result(self,cid):
        rows,label=related_cards(self.g,self.entity(cid),self.db)
        return [r.card_id for r in rows],label
    def feed(self,*body,task=False):
        for text in body:
            self.p.parse_line("D 12:00:00.000 "+("PowerTaskList" if task else "GameState")+".DebugPrintPower() - "+text+"\n")
    def test_tribes_highest_ties_and_distinctness(self):
        for c in ["A","B","C","B","D","Z"]: self.record(c)
        self.record("B",pid=2)
        self.assertEqual(["A","C"],self.result("EDR_455")[0])
        self.assertEqual(["B","C","B"],self.result("TIME_616")[0])
        self.assertEqual(["B","C"],self.result("EDR_238")[0])
        self.assertEqual(["A","D"],self.result("TLC_818")[0])
        self.assertEqual(["B","D"],self.result("BE_017t5")[0])
        self.assertEqual(["D"],self.result("EDR_891")[0])
    def test_different_felbat_and_all_tribe(self):
        self.db.cards["EDR_892"]=CardDefinition("EDR_892","Felbat",card_type="MINION",cost=6,mechanics=("DEATHRATTLE",))
        self.record("EDR_892"); self.record("B")
        self.assertEqual(["B"],self.result("EDR_892")[0])
        self.db.cards["X"]=CardDefinition("X","All tribes",card_type="MINION",cost=9,races=("ALL",))
        self.record("X")
        self.assertEqual(["X"],self.result("EDR_455")[0])
    def test_snapshot_survives_transform_discount_and_control_change(self):
        e=self.record("B");e.card_id="A";e.controller=2;e.cost=0
        self.assertEqual(["B"],self.result("CORE_CATA_002")[0])
        self.assertEqual(["B"],self.result("TIME_616")[0])
    def test_turn_windows_extra_turns_and_repeated_plays(self):
        self.g.global_turn=6;self.g.turn_owners={1:1,2:2,3:1,4:1,5:2,6:1}
        self.record("F","PLAY",turn=3);self.record("H","PLAY",turn=4)
        self.record("H","PLAY",turn=4);self.record("F","PLAY",turn=6)
        self.record("H","PLAY",turn=6);self.record("A","PLAY",turn=6)
        self.record("JAIL_500","PLAY",turn=6)
        self.assertEqual(["H","H"],self.result("CORE_TRL_345")[0])
        self.assertEqual(["H"],self.result("TLC_430")[0])
        self.assertEqual(["F","H","A"],self.result("JAIL_500")[0])
        self.assertEqual(["A"],self.result("CATA_560")[0])
    def test_reborn_is_not_a_death_and_owner_is_preserved(self):
        e=self.entity("B",zone="PLAY")
        self.feed(f"TAG_CHANGE Entity={e.entity_id} tag=HAS_BEEN_REBORN value=1")
        self.feed(f"TAG_CHANGE Entity={e.entity_id} tag=HAS_BEEN_REBORN value=1",task=True)
        e.controller=2
        self.assertEqual(["B"],self.result("CAP_806")[0])
        self.assertEqual([],self.result("CORE_CATA_002")[0])
    def test_death_transition_deduplication_and_repeated_death(self):
        e=self.entity("B",zone="PLAY")
        death=f"TAG_CHANGE Entity={e.entity_id} tag=ZONE value=GRAVEYARD"
        self.feed(death);self.feed(death,task=True)
        self.assertEqual(["B"],self.result("CORE_CATA_002")[0])
        self.feed(f"TAG_CHANGE Entity={e.entity_id} tag=ZONE value=PLAY",death)
        self.assertEqual(["B","B"],self.result("CORE_CATA_002")[0])
    def test_discard_late_flag_is_not_death_or_burn(self):
        source=self.entity("JAIL_887",zone="PLAY");e=self.entity("H")
        self.feed(f"BLOCK_START BlockType=POWER Entity={source.entity_id} EffectCardId= EffectIndex=0 Target=0 SubOption=-1",
                  f"TAG_CHANGE Entity={e.entity_id} tag=ZONE value=GRAVEYARD",
                  f"TAG_CHANGE Entity={e.entity_id} tag=DISCARDED value=1", "BLOCK_END")
        self.assertEqual(["H"],self.result("JAIL_887t2")[0])
        burn=self.entity("B",zone="DECK");self.feed(f"TAG_CHANGE Entity={burn.entity_id} tag=ZONE value=GRAVEYARD")
        self.assertEqual([],self.result("CORE_CATA_002")[0])
    def test_empty_pool_is_explicit_and_foreign_hand_never_gets_preview(self):
        self.assertIn("none observed",self.result("CORE_CATA_002")[1])
        e=self.entity("CORE_CATA_002",2)
        self.assertEqual(((),""),related_cards(self.g,e,self.db))
    def test_hoarders_do_not_mix_their_discards(self):
        a=self.entity("CATA_897");b=self.entity("CATA_897")
        self.record("H","DISCARD",source=a);self.record("F","DISCARD",source=b)
        self.assertEqual(["H"],[r.card_id for r in related_cards(self.g,a,self.db)[0]])
    def test_killer_instance_is_preserved(self):
        a=self.entity("EDR_819");b=self.entity("EDR_819")
        self.record("A",source=a,pid=2);self.record("B",source=b)
        self.assertEqual(["A"],[r.card_id for r in related_cards(self.g,a,self.db)[0]])
    def test_reset_clears_histories_and_turns(self):
        self.record("B");self.g.turn_owners[3]=1;self.g.reset()
        self.assertEqual([],self.g.card_history);self.assertEqual({},self.g.turn_owners)
    def test_plain_jar_copy_does_not_inherit_unverified_storage(self):
        original=self.entity("TLC_841t");self.g.stored_card_pools[original.entity_id]=("B",)
        copy=self.entity("TLC_841t");copy.copied_from_entity_id=original.entity_id
        self.assertEqual((),related_cards(self.g,copy,self.db)[0])

    def test_reference_builders_distinguish_entity_ids_from_counts(self):
        target=self.entity("B",zone="SETASIDE");owner=self.entity("TOKEN")
        owner.tags["TAG_SCRIPT_DATA_NUM_1"]=str(target.entity_id)
        self.db.cards["TOKEN"]=CardDefinition("TOKEN","Token",text="Summon {0}.",text_builder="SCRIPT_DATA_NUM_1")
        self.assertEqual((),related_cards(self.g,owner,self.db)[0])
        self.db.cards["TOKEN"]=replace(self.db.cards["TOKEN"],text_builder="REFERENCE_SCRIPT_DATA_NUM_1_ENTITY")
        self.assertEqual(["B"],[r.card_id for r in related_cards(self.g,owner,self.db)[0]])
    def test_attached_references_ignore_removed_enchants_and_hidden_opponent(self):
        owner=self.entity("TOKEN");target=self.entity("B",2,"HAND")
        enchant=self.entity("ENCH",zone="PLAY");enchant.card_type="ENCHANTMENT"
        enchant.tags.update(ATTACHED=str(owner.entity_id),TAG_SCRIPT_DATA_NUM_1=str(target.entity_id))
        self.db.cards["ENCH"]=CardDefinition("ENCH","Effect",text="Stored {0}.",text_builder="REFERENCE_SCRIPT_DATA_NUM_1_ENTITY")
        self.assertEqual((),related_cards(self.g,owner,self.db)[0])
        target.controller=1
        self.assertEqual(["B"],[r.card_id for r in related_cards(self.g,owner,self.db)[0]])
        enchant.zone="GRAVEYARD"
        self.assertEqual((),related_cards(self.g,owner,self.db)[0])
    def test_jar_dbf_reference_and_duplicate_spells_are_distinct(self):
        self.db.cards_by_dbf[500]=self.db.cards["B"]
        jar=self.entity("JAR");jar.tags["TAG_SCRIPT_DATA_NUM_6"]="500"
        self.db.cards["JAR"]=CardDefinition("JAR","Jar",text="Release {5}.",text_builder="MULTIPLE_ALT_TEXT_SCRIPT_DATA_NUMS_REF_SDN6_CARD_DBID")
        self.assertEqual(["B"],[r.card_id for r in related_cards(self.g,jar,self.db)[0]])
        owner=self.entity("CAST");a=self.entity("H");b=self.entity("H")
        self.db.cards["CAST"]=CardDefinition("CAST","Cast",text="Cast {0} and {1}.",text_builder="DRUSTVAR_HORROR")
        owner.tags.update(TAG_SCRIPT_DATA_NUM_1=str(a.entity_id),TAG_SCRIPT_DATA_NUM_2=str(b.entity_id))
        self.assertEqual(["H","H"],[r.card_id for r in related_cards(self.g,owner,self.db)[0]])
    def test_unreferenced_slot_cannot_become_a_phantom_card(self):
        owner=self.entity("CAST");a=self.entity("H");b=self.entity("F")
        self.db.cards["CAST"]=CardDefinition("CAST","Cast",text="Cast {0}.",text_builder="DRUSTVAR_HORROR")
        owner.tags.update(TAG_SCRIPT_DATA_NUM_1=str(a.entity_id),TAG_SCRIPT_DATA_NUM_2=str(b.entity_id))
        self.assertEqual(["H"],[r.card_id for r in related_cards(self.g,owner,self.db)[0]])
    def test_hidden_secret_identity_is_not_opponent_play_history(self):
        self.db.cards["S"]=CardDefinition("S","Secret",card_type="SPELL",mechanics=("SECRET",))
        self.record("S",kind="PLAY",pid=2)
        self.assertEqual([],self.g.card_history)
    def test_bounced_hoarder_does_not_keep_a_previous_incarnations_contents(self):
        owner=self.entity("CATA_897",zone="PLAY")
        self.record("H",kind="DISCARD",source=owner)
        self.feed(f"TAG_CHANGE Entity={owner.entity_id} tag=ZONE value=HAND")
        self.assertEqual((),related_cards(self.g,owner,self.db)[0])
    def test_parser_records_play_once_across_both_streams(self):
        e=self.entity("H")
        block=f"BLOCK_START BlockType=PLAY Entity={e.entity_id} EffectCardId= EffectIndex=0 Target=0 SubOption=-1"
        self.feed(block,"BLOCK_END");self.feed(block,"BLOCK_END",task=True)
        self.assertEqual(["H"],self.result("TLC_430")[0])

    def test_bounced_jar_loses_enchantment_payload(self):
        jar=self.entity("TLC_841t",zone="PLAY");self.g.stored_card_pools[jar.entity_id]=("B",)
        self.feed(f"TAG_CHANGE Entity={jar.entity_id} tag=ZONE value=HAND")
        self.assertNotIn(jar.entity_id,self.g.stored_card_pools)
    def test_empty_extra_turn_is_recorded_without_reusing_an_older_spell_turn(self):
        self.g.turn_owners={1:1,2:2,3:1};self.record("H","PLAY",turn=3)
        self.g.player(1).entity_id=2;self.g.player(2).entity_id=3
        self.feed("TAG_CHANGE Entity=2 tag=CURRENT_PLAYER value=1", "TAG_CHANGE Entity=GameEntity tag=TURN value=4",
                  "TAG_CHANGE Entity=GameEntity tag=STEP value=MAIN_START")
        self.g.global_turn=6
        self.assertEqual([],self.result("CORE_TRL_345")[0])
        self.assertEqual(1,self.g.turn_owners[3]);self.assertEqual(1,self.g.turn_owners[4])

    def test_chromie_uses_known_deck_inventory_without_peeking_at_deck_entities(self):
        self.record("H","PLAY");owner=self.entity("TIME_103")
        hidden=self.entity("",zone="DECK")
        result=related_cards(self.g,owner,self.db,known_deck=("H","H","F"))[0]
        self.assertEqual(["H","H"],[r.card_id for r in result]);self.assertEqual("",hidden.card_id)

    def test_repeated_same_entity_spell_reference_preserves_both_effects(self):
        owner=self.entity("CAST");spell=self.entity("H")
        self.db.cards["CAST"]=CardDefinition("CAST","Cast",text="Cast {0} and {1}.",text_builder="DRUSTVAR_HORROR")
        owner.tags.update(TAG_SCRIPT_DATA_NUM_1=str(spell.entity_id),TAG_SCRIPT_DATA_NUM_2=str(spell.entity_id))
        self.assertEqual(["H","H"],[r.card_id for r in related_cards(self.g,owner,self.db)[0]])
    def test_devouring_opponent_hand_preserves_count_without_exposing_identity(self):
        source=self.entity("CATA_481",zone="PLAY");hidden=self.entity("B",2)
        self.feed(f"BLOCK_START BlockType=POWER Entity={source.entity_id} EffectCardId= EffectIndex=0 Target=0 SubOption=-1",
                  f"TAG_CHANGE Entity={hidden.entity_id} tag=ZONE value=SETASIDE", "BLOCK_END")
        result=related_cards(self.g,source,self.db)[0]
        self.assertEqual(1,len(result));self.assertEqual("",result[0].card_id);self.assertEqual("Unknown card",result[0].name)
    def test_all_tribes_is_not_the_special_treant_identity(self):
        self.db.cards["X"]=CardDefinition("X","All tribes",card_type="MINION",cost=9,races=("ALL",))
        self.record("X")
        self.assertEqual([],self.result("END_009")[0])


    def test_late_metadata_repairs_original_snapshot_without_revealing_hidden_cards(self):
        from ghostdata.tracking.card_history import refresh_metadata
        unknown=self.entity("NEW");unknown.card_type="MINION";unknown.cost=None
        observe(self.g,unknown,self.db,"DEATH")
        anonymous=observe(self.g,unknown,self.db,"CAPTURED",anonymous=True,append=False)
        self.g.stored_card_details[500]=(anonymous,)
        unknown.card_id="B";unknown.controller=2
        self.db.cards["NEW"]=CardDefinition("NEW","New Dragon",text="Local rules",card_type="MINION",cost=9,races=("DRAGON",))
        refresh_metadata(self.g,self.db)
        record=self.g.card_history[0]
        self.assertEqual(("NEW",1,9,("DRAGON",),"New Dragon"),(record.card_id,record.controller,record.cost,record.races,record.name))
        self.assertEqual(["NEW"],self.result("EDR_455")[0])
        self.assertEqual("",self.g.stored_card_details[500][0].card_id)
        self.assertEqual("Unknown card",self.g.stored_card_details[500][0].name)


    def test_friendly_hand_preview_reaches_tracker_without_selected_deck(self):
        from ghostdata.tracking.tracker.engine import DeckTrackerEngine
        tracker=DeckTrackerEngine(card_db=self.db)
        self.feed("FULL_ENTITY - Creating ID=501 CardID=H", "tag=CONTROLLER value=1",
                  "tag=CARDTYPE value=SPELL", "tag=ZONE value=HAND")
        tracker.observe(self.g)
        slot=next(h for h in tracker.state.player_hand if h.entity_id==501)
        self.assertEqual("H",slot.card_id)
        self.assertEqual("Holy Spell",slot.name)
        self.assertNotIn((501,"H"),tracker._observed_pairs)
        self.feed("HIDE_ENTITY - Entity=501 tag=ZONE value=HAND")
        tracker.observe(self.g)
        self.assertEqual("",next(h for h in tracker.state.player_hand if h.entity_id==501).card_id)

    def test_unrevealed_opponent_hand_identity_stays_hidden(self):
        from ghostdata.tracking.tracker.engine import DeckTrackerEngine
        tracker=DeckTrackerEngine(card_db=self.db)
        self.feed("FULL_ENTITY - Creating ID=502 CardID=", "tag=CONTROLLER value=2",
                  "tag=CARDTYPE value=SPELL", "tag=ZONE value=HAND")
        tracker.observe(self.g)
        self.g.entities[502].card_id="H"  # Internal knowledge is not a reveal event.
        tracker.observe(self.g)
        slot=next(h for h in tracker.state.opponent_hand if h.entity_id==502)
        self.assertEqual("",slot.card_id)

if __name__=="__main__":unittest.main()
