import unittest
from ghostdata.tracking.models import GameState
from ghostdata.tracking.related_cards import related_cards
from ghostdata.tracking.card_db import CardDefinition
from ghostdata.tracking.parser import PowerLogParser
from ghostdata.tracker_bridge import ingest_tracker_chunk
import test_live_deck_tracker as fixture

class RelatedCardsTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.DeckTrackerTests();self.f.setUp()
        self.game=self.f.state;self.game.local_player_pid=1
        self.db=self.f.db
        self.parser=PowerLogParser(card_db=self.db);self.parser.state=self.game
    def entity(self,eid,cid,pid=1,zone='SETASIDE',creator=None,kind='MINION'):
        e=self.game.entity(eid);e.card_id=cid;e.controller=pid;e.zone=zone;e.creator=creator;e.card_type=kind
        return e
    def token(self,eid,pid=1,creator=90):
        e=self.entity(eid,'CAP_805t',pid,'HAND',creator,'SPELL')
        e.tags['TAG_SCRIPT_DATA_NUM_2']=str(eid);e.tags['GHOSTDATA_STORAGE_OWNER']=str(pid)
        return e
    def contents(self,e):return [x.card_id for x in related_cards(self.game,e,self.db)[0]]
    def test_two_tokens_and_repeated_casts_keep_distinct_contents_and_duplicates(self):
        self.entity(90,'CAP_805',kind='SPELL');a=self.token(100)
        for i,cid in [(101,'CARD_1'),(102,'CARD_1')]:self.entity(i,cid,creator=90).copied_from_entity_id=i-50
        b=self.token(110,2);self.entity(111,'CARD_2',2,creator=90).copied_from_entity_id=51
        self.entity(190,'CAP_805',kind='SPELL');c=self.token(200,creator=190)
        self.entity(201,'CARD_3',creator=190).copied_from_entity_id=52
        self.assertEqual(['CARD_1','CARD_1'],self.contents(a));self.assertEqual([],self.contents(b))
        self.assertEqual(['CARD_3'],self.contents(c))
    def test_copied_token_uses_original_anchor(self):
        self.entity(90,'CAP_805',kind='SPELL');a=self.token(100)
        self.entity(101,'CARD_1',creator=90).copied_from_entity_id=51
        copy=self.token(200,creator=999);copy.tags['TAG_SCRIPT_DATA_NUM_2']='100'
        self.assertEqual(['CARD_1'],self.contents(copy))
    def test_public_snapshot_survives_controller_and_identity_changes(self):
        self.entity(90,'CAP_805',kind='SPELL');token=self.token(100,2)
        self.game.stored_card_pools[100]=('CARD_1','CARD_2')
        token.controller=1
        self.assertEqual(['CARD_1','CARD_2'],self.contents(token))
    def test_missing_source_is_explicit_not_guessed(self):
        token=self.token(100)
        self.assertEqual([],self.contents(token))
        self.assertIn('unavailable',related_cards(self.game,token,self.db)[1])
    def test_explicit_links_only_and_no_hidden_card_identity(self):
        owner=self.entity(90,'CARD_1',zone='HAND',kind='SPELL')
        good=self.entity(100,'CARD_2');good.tags['LINKED_ENTITY']='90'
        hidden=self.entity(101,'');hidden.tags['LINKED_ENTITY']='90'
        foreign=self.entity(102,'CARD_3',2);foreign.tags['LINKED_ENTITY']='90'
        self.entity(103,'CARD_4')
        self.assertEqual(['CARD_2'],self.contents(owner))
    def test_public_destruction_snapshot_and_new_game_reset(self):
        source=self.entity(90,'CAP_805',kind='SPELL');m=self.entity(50,'CARD_1',zone='PLAY');m.zone_position=2
        lines=['BLOCK_START BlockType=POWER Entity=[entityName=Source id=90 zone=PLAY zonePos=1 cardId=CAP_805 player=1] EffectCardId= EffectIndex=0 Target=0 SubOption=-1',
               'TAG_CHANGE Entity=50 tag=TO_BE_DESTROYED value=1','FULL_ENTITY - Creating ID=100 CardID=CAP_805t', 'tag=CONTROLLER value=1', 'tag=CARDTYPE value=SPELL', 'tag=ZONE value=HAND', 'tag=CREATOR value=90', 'BLOCK_END']
        for stream in ('GameState','PowerTaskList'):
            raw=''.join('D 12:00:00.000 '+stream+'.DebugPrintPower() - '+line+'\n' for line in lines)
            ingest_tracker_chunk(self.parser,self.f.tracker,b'',raw.encode())
        self.assertEqual(('CARD_1',),self.game.stored_card_pools[100])
        self.parser.reset_for_new_source();self.assertEqual({},self.parser.state.stored_card_pools)

    def test_repeated_same_source_preserves_prior_token_snapshot(self):
        self.entity(90,'CAP_805',kind='SPELL')
        a=self.token(100);b=self.token(200)
        self.game.stored_card_pools[100]=('CARD_1','CARD_1')
        self.game.stored_card_pools[200]=('CARD_3',)
        self.assertEqual(['CARD_1','CARD_1'],self.contents(a))
        self.assertEqual(['CARD_3'],self.contents(b))

    def test_empty_observed_cast_is_distinct_from_unavailable(self):
        self.entity(90,'CAP_805',kind='SPELL');a=self.token(100)
        self.game.stored_card_pools[100]=()
        self.assertEqual([],self.contents(a))
        self.assertEqual('No minions stored by this cast.',related_cards(self.game,a,self.db)[1])

    def test_assembled_contents_keep_rules_component_after_original_transforms(self):
        from dataclasses import replace
        self.db.cards["CARD_1"]=replace(self.db.cards["CARD_1"], text="Body")
        body=self.entity(50,"CARD_1",zone="PLAY")
        rules=self.db.cards["CARD_2"]
        body.tags.update(ASSEMBLED_MINION="1",CRAFTABLE_SECOND_HALF_DBID=str(rules.dbf_id))
        self.entity(90,"CAP_805",kind="SPELL")
        lines=["BLOCK_START BlockType=POWER Entity=90 EffectCardId= EffectIndex=0 Target=0 SubOption=-1",
               "TAG_CHANGE Entity=50 tag=TO_BE_DESTROYED value=1", "FULL_ENTITY - Creating ID=100 CardID=CAP_805t",
               "tag=CONTROLLER value=1","tag=CARDTYPE value=SPELL","tag=ZONE value=HAND","tag=CREATOR value=90","BLOCK_END"]
        for line in lines:self.parser.parse_line("D 12:00:00.000 GameState.DebugPrintPower() - "+line+"\n")
        body.card_id="CARD_3";body.tags.clear()
        row=related_cards(self.game,self.game.entities[100],self.db)[0][0]
        self.assertIn(rules.name,row.name)
        self.assertIn(" + ",row.name)
