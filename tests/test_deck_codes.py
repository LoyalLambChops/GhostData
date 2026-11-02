import base64
import unittest
from ghostdata.deck_codes import deck_code

class Database:
    def dbf_id_for_card_id(self, cid):
        return {"HERO":7,"A":1,"B":2,"C":300,"SIDE":400}.get(cid)

class DeckCodeTests(unittest.TestCase):
    def deck(self):
        return dict(format="STANDARD",hero_card_ids=["HERO"],cards=[
            dict(card_id="C",count=3),dict(card_id="A",count=1),dict(card_id="B",count=2)])
    def test_golden_binary_groups_and_multibyte_ids(self):
        code=deck_code(self.deck(),Database())
        self.assertEqual(base64.b64decode(code),bytes([0,1,2,1,7,1,1,1,2,1,172,2,3,0]))
    def test_sideboard_count_and_owner_are_preserved(self):
        deck=self.deck();deck['sideboards']=[dict(card_id='SIDE',owner_card_id='C',count=3)]
        self.assertEqual(base64.b64decode(deck_code(deck,Database())),bytes([
            0,1,2,1,7,1,1,1,2,1,172,2,3,1,0,0,1,144,3,3,172,2]))
    def test_missing_id_never_exports_a_shortened_deck(self):
        for field in ('cards','hero_card_ids','sideboards'):
            deck=self.deck()
            if field=='hero_card_ids':deck[field]=['UNKNOWN']
            elif field=='cards':deck[field].append(dict(card_id='UNKNOWN',count=1))
            else:deck[field]=[dict(card_id='SIDE',owner_card_id='UNKNOWN',count=1)]
            self.assertEqual(deck_code(deck,Database()),'')
    def test_order_independent_and_duplicate_rows_combined(self):
        deck=self.deck();expected=deck_code(deck,Database());deck['cards'].reverse()
        self.assertEqual(deck_code(deck,Database()),expected)
        deck['cards']=[dict(card_id='B',count=1),dict(card_id='B',count=1),dict(card_id='A',count=1),dict(card_id='C',count=3)]
        self.assertEqual(deck_code(deck,Database()),expected)
    def test_invalid_inputs_fail_closed(self):
        for change in [dict(format='WILD'),dict(hero_card_ids=[]),dict(cards=[dict(card_id='A',count=-1)])]:
            deck=self.deck();deck.update(change);self.assertEqual(deck_code(deck,Database()),'')
