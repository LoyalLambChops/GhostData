import unittest
from ghostdata.tracking.card_db import CardDefinition, CardDatabase
from ghostdata.tracking.models import GameState, SecretState, SecretCandidate
from ghostdata.tracking.secrets import SecretTracker, SecretObservation, infer_safe_trigger_rule
from pathlib import Path


class GeneratedSecretRulesTests(unittest.TestCase):
    def setUp(self):
        self.game = GameState(global_turn=5, local_player_pid=1, current_player_pid=1)
        self.db = CardDatabase(Path('.'))
        self.tracker = SecretTracker(self.db)
        self.game.player(1); self.game.player(2)
        self.minion(10, 1); self.minion(20, 2)

    def minion(self, eid, owner, zone='PLAY'):
        entity = self.game.entity(eid)
        entity.card_type = 'MINION'; entity.controller = owner; entity.zone = zone
        return entity

    def seed(self, *names):
        secret = self.game.entity(100); secret.controller = 2; secret.zone = 'SECRET'
        candidates = {}
        for name in names:
            card = CardDefinition(name, name, card_type='SPELL', mechanics=('SECRET',))
            self.db.cards[name] = card
            rule = infer_safe_trigger_rule(card)
            self.assertIsNotNone(rule, name)
            candidates[name] = SecretCandidate(name, name, 'MAGE', rule.key)
        self.game.secrets[100] = SecretState(100, 2, 1, candidates=candidates)

    def resolve(self, observation):
        self.tracker.observe_public_event(self.game, observation)
        self.tracker.flush_pending_tests(self.game)
        return set(self.game.secrets[100].eliminations)

    def test_attack_constraints_and_hand_board_limits(self):
        self.seed('Noble Sacrifice', 'Vaporize', 'Autodefense Matrix', 'Misdirection', 'Shadow Clone')
        event = SecretObservation('ATTACK', actor_pid=1, actor_entity_id=10, target_pid=2, is_hero_target=True, card_type='MINION')
        self.assertEqual({'Noble Sacrifice', 'Vaporize', 'Misdirection', 'Shadow Clone'}, self.resolve(event))
        self.setUp()
        for eid in range(21,27): self.minion(eid,2)
        self.seed('Noble Sacrifice','Shadow Clone')
        self.assertEqual(set(),self.resolve(event))

    def test_dormant_play_keeps_damage_secrets_but_tests_kidnap(self):
        # Dormant minion play: Kidnap is outside the
        # DORMANT check; Snipe, Repentance and Bargain Bin are inside it.
        self.game.entity(10).tags['DORMANT'] = '1'
        self.seed('Kidnap', 'Snipe', 'Repentance', 'Bargain Bin')
        self.assertEqual({'Kidnap'}, self.resolve(SecretObservation(
            'PLAY', actor_pid=1, actor_entity_id=10, card_type='MINION')))

    def test_bargain_bin_tests_full_hand_for_each_playable_type(self):
        for kind in ('MINION', 'SPELL', 'WEAPON'):
            with self.subTest(kind=kind):
                self.setUp()
                for eid in range(30, 40): self.minion(eid, 2, 'HAND')
                self.seed('Bargain Bin', 'Dirty Tricks')
                self.assertEqual({'Bargain Bin'}, self.resolve(SecretObservation(
                    'PLAY', actor_pid=1, actor_entity_id=10, card_type=kind)))

    def test_reckoning_keeps_candidate_when_dealer_has_lethal_damage(self):
        self.seed('Reckoning')
        actor = self.game.entity(10); actor.health = 3
        self.tracker.observe_public_event(self.game, SecretObservation(
            'MINION_DAMAGE_3', actor_pid=1, actor_entity_id=10))
        actor.damage = 3  # death tag/zone transition can arrive later
        self.tracker.flush_pending_tests(self.game)
        self.assertIn('Reckoning', self.game.secrets[100].candidates)

    def test_oasis_ally_does_not_test_forced_attack_on_owners_turn(self):
        card = CardDefinition('OASIS', 'Oasis Ally', card_type='SPELL', mechanics=('SECRET',),
            text='Secret: When a friendly minion is attacked, summon a Water Elemental.')
        self.db.cards[card.card_id] = card
        self.seed('Kidnap')
        self.game.secrets[100].candidates = {'OASIS': SecretCandidate(
            'OASIS', card.name, 'MAGE', infer_safe_trigger_rule(card).key)}
        self.game.current_player_pid = 2
        event = SecretObservation('ATTACK', actor_pid=1, actor_entity_id=10,
            target_pid=2, target_entity_id=20, is_minion_target=True, card_type='MINION')
        self.assertEqual(set(), self.resolve(event))
        self.game.current_player_pid = 1
        self.assertEqual({'OASIS'}, self.resolve(event))

    def test_spell_target_arrives_after_play_and_before_resolution(self):
        self.seed('Spellbender','Dirty Tricks','Never Surrender!','Cat Trick')
        self.game.entity(10).card_type='SPELL'
        self.tracker.observe_public_event(self.game,SecretObservation('PLAY',actor_pid=1,actor_entity_id=10,card_type='SPELL'))
        self.game.entity(10).tags['CARD_TARGET']='20'
        self.tracker.flush_pending_tests(self.game)
        self.assertEqual(4,len(self.game.secrets[100].eliminations))

    def test_non_targeted_spell_keeps_spellbender_and_full_hand_keeps_draw(self):
        for eid in range(30,40): self.minion(eid,2,'HAND')
        self.seed('Spellbender','Dirty Tricks','Mana Bind')
        self.assertEqual(set(),self.resolve(SecretObservation('PLAY',actor_pid=1,actor_entity_id=10,card_type='SPELL')))

    def test_deathrattle_fills_board_before_redemption_and_new_minion_not_avenge_witness(self):
        self.seed('Redemption','Avenge')
        self.tracker.observe_public_event(self.game,SecretObservation('MINION_DIED',actor_pid=1,target_pid=2,target_entity_id=21,witness_ids=(20,)))
        self.game.entity(20).zone='GRAVEYARD'
        for eid in range(30,37): self.minion(eid,2)
        self.assertEqual(0,self.tracker.flush_pending_tests(self.game))

    def test_draw_hero_power_mana_and_damage_are_separate_events(self):
        for event, name in [('SECOND_DRAW','Shenanigans'),('HERO_POWER','Dart Trap'),('MANA_ZERO','Double Cross'),('HERO_DAMAGED','Evasion')]:
            with self.subTest(event=event):
                self.setUp();self.seed(name)
                self.assertEqual({name},self.resolve(SecretObservation(event,actor_pid=1,target_pid=2)))

    def test_rigged_faire_game_remembers_armor_damage_and_plagiarize_previous_turn(self):
        self.game.global_turn=6
        self.game.player(2).tags['GHOSTDATA_DAMAGED_TURN']='5'
        self.game.emit('00:00:00','PLAY','',player=1,turn=5)
        self.seed('Rigged Faire Game','Plagiarize','Perjury','Summoning Ward')
        self.assertEqual({'Plagiarize','Perjury','Summoning Ward'},self.resolve(SecretObservation('TURN_START',actor_pid=2)))

    def test_locked_secret_cannot_be_eliminated(self):
        self.seed('Dart Trap'); self.game.entity(100).tags['SECRET_LOCKED']='1'
        self.assertEqual(set(),self.resolve(SecretObservation('HERO_POWER',actor_pid=1)))

    def test_parser_damage_and_hero_power_feed_the_same_action_boundary(self):
        from ghostdata.tracking.parser import PowerLogParser
        self.seed('Evasion','Dart Trap','Reckoning')
        hero=self.game.entity(30);hero.controller=2;hero.zone='PLAY';hero.card_type='HERO'
        power=self.game.entity(99);power.controller=1;power.card_type='HERO_POWER'
        parser=PowerLogParser(card_db=self.db);parser.state=self.game;parser.secret_tracker=self.tracker
        def feed(*rows):
            for row in rows: parser.parse_line('D 12:00:00.000 GameState.DebugPrintPower() - '+row+'\n')
        feed('BLOCK_START BlockType=POWER Entity=99 EffectCardId= EffectIndex=0 Target=0 SubOption=-1',
             'TAG_CHANGE Entity=30 tag=DAMAGE value=2','BLOCK_END')
        self.assertEqual({'Evasion','Dart Trap'},set(self.game.secrets[100].eliminations))
        for damage in [4,6]:
            feed('BLOCK_START BlockType=ATTACK Entity=10 EffectCardId= EffectIndex=0 Target=30 SubOption=-1',
                 f'TAG_CHANGE Entity=30 tag=DAMAGE value={damage}','BLOCK_END')
        self.assertIn('Reckoning',self.game.secrets[100].candidates)
        feed('BLOCK_START BlockType=ATTACK Entity=10 EffectCardId= EffectIndex=0 Target=30 SubOption=-1',
             'TAG_CHANGE Entity=30 tag=DAMAGE value=9','BLOCK_END')
        self.assertIn('Reckoning',self.game.secrets[100].eliminations)

    def test_fast_combat_preserves_attempted_attack_but_not_after_combat_tests(self):
        self.seed('Noble Sacrifice','Vaporize')
        extra=self.game.entity(101);extra.controller=2;extra.zone='SECRET'
        self.game.secrets[101]=SecretState(101,2,1)
        self.tracker.observe_public_event(self.game,SecretObservation('ATTACK',actor_pid=1,actor_entity_id=10,
            card_type='MINION',target_pid=2,is_hero_target=True))
        self.game.secrets[101].resolved_card_id='TRAP'
        self.game.secrets[101].resolved_name='Freezing Trap'
        self.game.secrets[101].publicly_revealed=True
        extra.zone='GRAVEYARD'
        self.tracker.flush_pending_tests(self.game)
        self.assertEqual({'Noble Sacrifice'},set(self.game.secrets[100].eliminations))

    def test_replayed_secret_starts_a_new_activation(self):
        self.seed('Dart Trap')
        old=self.game.secrets[100];old.eliminate('Dart Trap','earlier activation')
        old.publicly_revealed=True;old.resolved_card_id='Dart Trap'
        self.tracker.on_zone_change(self.game,self.game.entity(100),'HAND','SECRET')
        self.assertIsNot(old,self.game.secrets[100])
        self.assertFalse(self.game.secrets[100].resolved)
        self.assertEqual({},self.game.secrets[100].eliminations)

    def test_hidden_cache_can_use_a_later_public_minion_reveal(self):
        self.seed('Hidden Cache')
        unknown=self.game.entity(30);unknown.controller=2;unknown.zone='HAND'
        self.tracker.observe_public_event(self.game,SecretObservation('PLAY',actor_pid=1,actor_entity_id=10,card_type='MINION'))
        self.tracker.flush_pending_tests(self.game)
        self.assertIn('Hidden Cache',self.game.secrets[100].candidates)
        self.db.cards['MINION']=CardDefinition('MINION','Minion',card_type='MINION')
        unknown.card_id='MINION'
        self.tracker.on_identity_change(self.game,unknown)
        self.assertIn('Hidden Cache',self.game.secrets[100].eliminations)


if __name__ == '__main__': unittest.main()
