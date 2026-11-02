import json
from pathlib import Path
import tempfile
import unittest
from ghostdata.deck_sensor import _snapshot_from_payload, save_cached_deck
from ghostdata.deck_library import save_deck, dashboard_decks
from ghostdata.models import MatchRecord

class DeckLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
    def deck(self,card="CARD_A",deckid="1",status="EXACT",side=None):
        return _snapshot_from_payload(dict(status=status,format="STANDARD",deck_name="Same name",selected_deck_id=deckid,
            hero_card_ids=["HERO_08"],cards=[dict(card_id=card,count=30)],sideboards=side or []))
    def test_versions_and_same_named_decks_remain_distinct(self):
        for deck in [self.deck(),self.deck("CARD_B"),self.deck(deckid="2")]:save_deck(deck,data_dir=self.root)
        rows=dashboard_decks([],data_dir=self.root)
        self.assertEqual(len(rows),3)
        self.assertEqual(len({row['key'] for row in rows}),3)
        self.assertEqual({row['cards'][0]['card_id'] for row in rows},{"CARD_A","CARD_B"})
    def test_unchanged_snapshot_does_not_rewrite_and_rename_does(self):
        deck=self.deck();self.assertTrue(save_deck(deck,data_dir=self.root))
        path=next((self.root/'deck_library').glob('*.json'));before=path.stat().st_mtime_ns
        self.assertFalse(save_deck(deck,data_dir=self.root));self.assertEqual(before,path.stat().st_mtime_ns)
        deck.deck_name="Renamed";self.assertTrue(save_deck(deck,data_dir=self.root))
        self.assertEqual(dashboard_decks([],data_dir=self.root)[0]['name'],"Renamed")
    def test_partial_nonstandard_and_inconsistent_snapshots_are_rejected(self):
        self.assertFalse(save_deck(self.deck(status="PARTIAL"),data_dir=self.root))
        deck=self.deck();deck.format="WILD";self.assertFalse(save_deck(deck,data_dir=self.root))
        deck=self.deck();deck.composition_hash="wrong";self.assertFalse(save_deck(deck,data_dir=self.root))
    def test_bootstrap_cached_deck_and_keep_sideboard_separate(self):
        deck=self.deck(side=[dict(owner_card_id="CARD_A",card_id="SIDE",count=3)])
        save_cached_deck(deck,data_dir=self.root)
        rows=dashboard_decks([],data_dir=self.root)
        self.assertEqual(rows[0]['total'],30)
        self.assertEqual(rows[0]['sideboard'][0]['count'],3)
        self.assertEqual(rows[0]['sideboard'][0]['owner'],'CARD_A')
    def test_historical_version_is_not_substituted_with_current_deck(self):
        deck=self.deck();save_deck(deck,data_dir=self.root)
        match=MatchRecord(match_id='m',started_at='',result='WIN',player_class='MAGE',opponent_class='PRIEST',initiative='FIRST',
            deck_id='1',deck_name='Same name',deck_version='old-version')
        rows=dashboard_decks([match],data_dir=self.root)
        old=next(r for r in rows if r['version']=='old-version')
        self.assertFalse(old['available']);self.assertEqual(old['cards'],[])
        match.deck_version=deck.composition_hash
        self.assertEqual(len(dashboard_decks([match],data_dir=self.root)),1)
    def test_corrupt_entry_does_not_break_offline_library(self):
        save_deck(self.deck(),data_dir=self.root)
        (self.root/'deck_library'/'bad.json').write_text('broken')
        self.assertEqual(len(dashboard_decks([],data_dir=self.root)),1)

    def test_unchanged_selected_snapshot_does_not_invalidate_dashboard_cache(self):
        deck=self.deck();save_cached_deck(deck,data_dir=self.root)
        path=self.root/'selected_deck.json';before=path.stat().st_mtime_ns
        save_cached_deck(deck,data_dir=self.root)
        self.assertEqual(before,path.stat().st_mtime_ns)

    def test_status_text_has_no_encoding_artifacts(self):
        save_deck(self.deck(),data_dir=self.root)
        row=dashboard_decks([],data_dir=self.root)[0]
        self.assertEqual(row['status'],'Exact saved composition - card wording from installed game definitions')
        self.assertEqual(row['deck_code'],'')
