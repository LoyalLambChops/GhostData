"""Observable Standard tracking contracts."""
import unittest
from dataclasses import replace
from ghostdata.dashboard import build_dashboard
from ghostdata.models import MatchRecord
from ghostdata.tracker_bridge import ingest_tracker_chunk
from ghostdata.tracking.models import GameState, SecretState, SecretCandidate, MulliganRecord
from ghostdata.tracking.secrets import SecretObservation, SecretTriggerRule
from ghostdata.tracking.parser import PowerLogParser
from ghostdata.tracker_bridge import _secret_reads
import test_live_deck_tracker as tracker_fixture
import test_secret_rails as secret_fixture


class RailParityTests(unittest.TestCase):
    def setUp(self):
        self.f = tracker_fixture.DeckTrackerTests()
        self.f.setUp()

    def row(self, cid):
        return next(r for r in self.f.tracker.state.player_display_rows if r.card_id == cid)

    def test_full_hidden_deck_swap_and_return_restore_baseline(self):
        for eid in range(1, 31):
            self.f._emit_zone(eid, 1, "DECK")
        for eid in range(1, 31):
            self.f._emit_zone(eid, 2, "DECK")
        self.assertEqual(0, self.f.tracker.state.original_cards_remaining)
        for eid in range(1, 31):
            self.f._emit_zone(eid, 1, "DECK")
        self.assertEqual(30, self.f.tracker.state.original_cards_remaining)
        self.assertEqual("EXACT", self.f.tracker.state.player_accounting_status)

    def test_full_deck_replacement_uses_current_generated_cards(self):
        for eid in range(1, 31):
            self.f._emit_zone(eid, 1, "DECK")
        self.f.state.global_turn = 8
        for eid in range(1, 31):
            self.f._emit_zone(eid, 1, "SETASIDE")
        for eid in range(31, 34):
            self.f._emit_zone(eid, 1, "DECK", "CARD_2", creator=99)
        self.assertEqual("EXACT", self.f.tracker.state.player_accounting_status)
        self.assertEqual(0, self.f.tracker.state.original_cards_remaining)
        created = next(r for r in self.f.tracker.state.player_display_rows if r.provenance == "GENERATED")
        self.assertEqual((3, 100), (created.count, created.draw_chance))

    def test_portal_is_infinite_and_has_no_probability(self):
        hero = self.f.state.entity(99); hero.controller = 1; hero.tags["DEMON_PORTAL_DECK"] = "1"
        self.f._emit_zone(100, 1, "DECK", "CARD_2", creator=99)
        self.assertTrue(self.f.tracker.state.player_portal)
        self.assertEqual("PORTAL", self.f.tracker.state.player_accounting_status)
        self.assertTrue(all(r.draw_chance is None for r in self.f.tracker.state.player_display_rows))
        self.assertFalse(any(r.provenance == "GENERATED" for r in self.f.tracker.state.player_display_rows))

    def test_conceal_hides_hand_identity_but_keeps_history(self):
        self.f._emit_zone(100, 2, "DECK")
        self.f._reveal(100, "OPP_A")
        self.f.state.emit("00:00:00", "HIDE", "", entity_id=100)
        self.f.tracker.observe(self.f.state)
        self.f._emit_zone(100, 2, "HAND")
        self.assertEqual("", self.f.tracker.state.opponent_hand[0].card_id)
        self.assertEqual("SEEN", self.f.tracker.state.opponent_display_rows[0].zone)
        self.f._reveal(100, "OPP_A")
        self.assertEqual("OPP_A", self.f.tracker.state.opponent_hand[0].card_id)

    def test_same_identity_show_after_hide_is_new_public_reveal(self):
        parser = PowerLogParser(card_db=self.f.db); parser.state = self.f.state
        self.f._emit_zone(100, 2, "HAND")
        for text in ("SHOW_ENTITY - Updating Entity=100 CardID=OPP_A",
                     "HIDE_ENTITY - Entity=100 tag=ZONE value=HAND",
                     "SHOW_ENTITY - Updating Entity=100 CardID=OPP_A"):
            ingest_tracker_chunk(parser, self.f.tracker, b"", ("D 12:00:00.000 GameState.DebugPrintPower() - " + text + "\n").encode())
        self.assertEqual("OPP_A", self.f.tracker.state.opponent_hand[0].card_id)

    def test_unchanged_sensor_snapshot_does_not_reconcile_entities(self):
        from unittest.mock import patch
        with patch.object(self.f.tracker, "_reconcile_existing_entities") as reconcile:
            self.assertTrue(self.f.tracker.seed_selected_deck(self.f.snapshot, self.f.state))
            reconcile.assert_not_called()

    def test_new_build_metadata_refreshes_names_without_resetting_draws(self):
        self.f._emit_zone(1, 1, "DECK", "CARD_1")
        self.f._emit_zone(1, 1, "HAND")
        card=replace(self.f.db.cards["CARD_1"], name="Updated name", text="Updated text")
        self.f.db.cards["CARD_1"]=card; self.f.db.cards_by_dbf[1]=card
        self.f.tracker.seed_selected_deck(self.f.snapshot, self.f.state, refresh_metadata=True)
        row=self.row("CARD_1")
        self.assertEqual(("Updated name", "Updated text", 1, 1), (row.name,row.text,row.count,row.in_hand))

    def test_shattered_pool_has_exact_counts_without_guessed_entity_ids(self):
        from ghostdata.tracking.card_db import CardDefinition
        source = CardDefinition("CATA_EVENT_110", "Dragon Soul, Shattered", "NEUTRAL", "SPELL", dbf_id=900)
        self.f.db.cards[source.card_id] = source; self.f.db.cards_by_dbf[900] = source
        self.f.tracker.seed_selected_deck(replace(self.f.snapshot, cards=((900,1),), deck_hash="shattered"), self.f.state)
        self.f._emit_zone(10, 1, "DECK", source.card_id)
        self.f.state.emit("00:00:00", "TRIGGER", "", entity_id=10)
        self.f.tracker.observe(self.f.state)
        self.f._emit_zone(10, 1, "SETASIDE")
        for i in range(6):
            self.f._emit_zone(20+i, 1, "DECK", creator=10)
        self.assertEqual("EXACT", self.f.tracker.state.player_accounting_status)
        self.assertEqual(6, sum(r.count for r in self.f.tracker.state.player_display_rows if r.state=="SHUFFLED"))
        self.f._reveal(20, "CATA_EVENT_110t2")
        self.f._emit_zone(20, 1, "HAND")
        self.assertEqual("EXACT", self.f.tracker.state.player_accounting_status)
        self.assertEqual(5, sum(r.count for r in self.f.tracker.state.player_display_rows if r.state=="SHUFFLED"))
        for i in range(6):
            self.f._emit_zone(20+i, 1, "SETASIDE")
        self.assertFalse(any(r.state=="SHUFFLED" for r in self.f.tracker.state.player_display_rows))

    def test_depleted_card_remains_and_highlights_hand(self):
        for eid in (1, 2):
            self.f._emit_zone(eid, 1, "DECK", "CARD_1")
            self.f._emit_zone(eid, 1, "HAND", "CARD_1")
        row = self.row("CARD_1")
        self.assertEqual((0, 2, True), (row.count, row.in_hand, row.exhausted))

    def test_generated_hand_and_deck_do_not_merge_with_original(self):
        self.f._emit_zone(100, 1, "HAND", "CARD_1", creator=999)
        rows = [r for r in self.f.tracker.state.player_display_rows if r.card_id == "CARD_1"]
        self.assertEqual(2, len(rows))
        self.assertEqual({("DECK", 2), ("HAND", 1)}, {(r.zone, r.count) for r in rows})
        self.assertEqual(0, next(r for r in rows if r.zone == "DECK").in_hand)

    def test_mulligan_replacement_hand_slot(self):
        self.f._emit_zone(100, 2, "HAND")
        self.f.state.mulligans[1] = MulliganRecord(1, "Opponent", offered_entity_ids=[100])
        self.f._emit_zone(100, 2, "DECK")
        self.f._emit_zone(101, 2, "HAND")
        self.assertEqual("MULLIGAN", self.f.tracker.state.opponent_hand[0].origin)

    def test_hero_fatigue_and_standard_scope(self):
        e = self.f.state.entity(99); e.controller = 1; e.tags["FATIGUE"] = "3"
        self.f.tracker.observe(self.f.state)
        self.assertEqual(3, self.f.tracker.state.player_fatigue)
        self.f.state.format_type = "FT_WILD"
        self.f.tracker.observe(self.f.state)
        self.assertFalse(self.f.tracker.state.active)
        self.f.state.format_type = "FT_STANDARD"; self.f.state.game_type = "GT_ARENA"
        self.f.tracker.observe(self.f.state)
        self.assertFalse(self.f.tracker.state.active)

    def test_opponent_transform_keeps_first_public_identity(self):
        self.f._emit_zone(100, 2, "HAND", "CARD_1")
        self.f._reveal(100, "OPP_A")
        self.f._reveal(100, "CARD_2")
        self.assertEqual(["OPP_A"], [r.card_id for r in self.f.tracker.state.opponent_display_rows])

    def test_without_selected_deck_local_revealed_history_remains(self):
        self.f.tracker.reset_runtime(preserve_selected_deck=False)
        self.f._emit_zone(100, 1, "DECK", "CARD_1")
        self.f._emit_zone(100, 1, "HAND")
        self.f._emit_zone(100, 1, "GRAVEYARD")
        self.assertEqual(["CARD_1"], [r.card_id for r in self.f.tracker.state.player_display_rows])

    def test_late_creator_retracts_original_assignment(self):
        e = self.f._emit_zone(100, 1, "DECK", "CARD_1")
        self.f._emit_zone(100, 1, "HAND")
        e.creator = 999
        self.f.state.emit("00:00:00", "PROVENANCE_CHANGE", "", entity_id=100)
        self.f.tracker.observe(self.f.state)
        original = next(r for r in self.f.tracker.state.player_rows if r.card_id == "CARD_1")
        self.assertEqual(2, original.remaining_copies)

    def test_transform_back_restores_original_deck_identity(self):
        self.f._emit_zone(1, 1, "DECK", "CARD_1")
        self.f._reveal(1, "CARD_2")
        self.assertEqual(1, self.row("CARD_1").count)
        self.f._reveal(1, "CARD_1")
        self.assertEqual(2, self.row("CARD_1").count)

    def test_late_corrected_baseline_reconciles_original_not_transformed_identity(self):
        self.f._emit_zone(1, 1, "DECK", "CARD_1")
        self.f._reveal(1, "CARD_2")
        self.f._emit_zone(1, 1, "HAND")
        self.f.tracker.seed_selected_deck(replace(self.f.snapshot, deck_hash="corrected"), self.f.state)
        self.assertEqual(1, self.row("CARD_1").count)
        self.assertEqual(2, self.row("CARD_2").count)

    def test_burn_discard_and_play_are_distinct(self):
        self.f._emit_zone(1, 1, "DECK", "CARD_1")
        self.f._emit_zone(1, 1, "GRAVEYARD")
        self.assertIn("BURNED 1", self.row("CARD_1").state)
        self.f._emit_zone(2, 1, "DECK", "CARD_2")
        self.f._emit_zone(2, 1, "HAND")
        self.f._emit_zone(2, 1, "GRAVEYARD")
        self.assertIn("DISCARDED 1", self.row("CARD_2").state)
        self.f._emit_zone(3, 1, "DECK", "CARD_3")
        self.f._emit_zone(3, 1, "HAND")
        self.f.state.emit("00:00:00", "PLAY", "", entity_id=3)
        self.f.tracker.observe(self.f.state)
        self.f._emit_zone(3, 1, "GRAVEYARD")
        self.assertNotIn("DISCARDED", self.row("CARD_3").state)

    def test_opponent_same_card_in_different_zones_stays_separate(self):
        for eid in (100, 101):
            self.f._emit_zone(eid, 2, "DECK")
            self.f._emit_zone(eid, 2, "HAND")
            self.f._reveal(eid, "OPP_A")
        self.f._emit_zone(100, 2, "PLAY")
        rows = self.f.tracker.state.opponent_display_rows
        self.assertEqual({("PLAY", 1), ("HAND", 1)}, {(r.zone, r.count) for r in rows})

    def test_hidden_hand_identity_is_not_serialized(self):
        self.f._emit_zone(100, 2, "HAND", "OPP_A")
        slot = self.f.tracker.state.opponent_hand[0]
        self.assertEqual("", slot.card_id)
        self.assertEqual("Unknown card", slot.name)

    def test_returned_opponent_card_keeps_identity_and_acquisition_turn(self):
        self.f._emit_zone(100, 2, "HAND")
        self.f._reveal(100, "OPP_A")
        self.f._emit_zone(100, 2, "PLAY")
        self.f.state.global_turn = 8
        self.f._emit_zone(100, 2, "HAND")
        slot = self.f.tracker.state.opponent_hand[0]
        self.assertEqual(("OPP_A", "RETURNED", 8), (slot.card_id, slot.origin, slot.turn))

    def test_sideboards_are_separate_and_deplete_by_source(self):
        self.f.tracker.seed_selected_deck(replace(self.f.snapshot, sideboards=((1, 2, 1),)), self.f.state)
        self.f._emit_zone(1, 1, "DECK", "CARD_1")
        self.f._emit_zone(100, 1, "SETASIDE", "CARD_2", creator=1)
        self.assertEqual(1, self.f.tracker.state.player_sideboard_rows[0].count)
        self.f._emit_zone(100, 1, "HAND")
        self.assertEqual(0, self.f.tracker.state.player_sideboard_rows[0].count)
        self.assertEqual(30, self.f.tracker.state.starting_cards)

    def test_sideboard_hand_copy_consumes_linked_pool_once(self):
        self.f.tracker.seed_selected_deck(replace(self.f.snapshot, sideboards=((1, 2, 1),)), self.f.state)
        self.f._emit_zone(1, 1, "DECK", "CARD_1")
        self.f._emit_zone(100, 1, "SETASIDE", "CARD_2", creator=1)
        e = self.f._emit_zone(101, 1, "HAND", "CARD_2", creator=1)
        e.copied_from_entity_id = 100
        self.f.state.emit("00:00:00", "PROVENANCE_CHANGE", "", entity_id=101)
        self.f.tracker.observe(self.f.state)
        row = self.f.tracker.state.player_sideboard_rows[0]
        self.assertEqual((0, 1), (row.count, row.in_hand))
        self.assertEqual(30, self.f.tracker.state.starting_cards)

    def test_stream_consumes_each_transition_and_preserves_partial_utf8(self):
        class Parser:
            state = None
            def parse_line(self, line): self.state = line
        class Tracker:
            states = []
            def observe(self, state, *, publish=True):
                if not publish: self.states.append(state)
        parser, tracker = Parser(), Tracker()
        pending = ingest_tracker_chunk(parser, tracker, b"", "DECK\nHAND\nCaf".encode())
        self.assertEqual(["DECK", "HAND"], tracker.states)
        pending = ingest_tracker_chunk(parser, tracker, pending, "é\n".encode())
        self.assertEqual(["DECK", "HAND", "Café"], tracker.states)
        self.assertEqual(b"", pending)

    def test_one_chunk_replay_preserves_original_draw_and_burn(self):
        parser = PowerLogParser(card_db=self.f.db)
        parser.state = self.f.state
        payload = "\n".join("D 12:00:00.000 GameState.DebugPrintPower() - " + line for line in (
            "FULL_ENTITY - Creating ID=10 CardID=CARD_1",
            "    tag=CONTROLLER value=1",
            "    tag=ZONE value=DECK",
            "TAG_CHANGE Entity=10 tag=ZONE value=HAND",
            "TAG_CHANGE Entity=10 tag=ZONE value=DECK",
            "TAG_CHANGE Entity=10 tag=ZONE value=GRAVEYARD",
        )) + "\n"
        ingest_tracker_chunk(parser, self.f.tracker, b"", payload.encode())
        row = next(r for r in self.f.tracker.state.player_rows if r.card_id == "CARD_1")
        self.assertEqual((1, 1), (row.remaining_copies, row.drawn_copies))
        self.assertIn("BURNED", self.row("CARD_1").state)


class StatisticsParityTests(unittest.TestCase):
    def test_nonstandard_history_is_out_of_scope(self):
        row = MatchRecord("1", "2026-10-01", "WIN", "MAGE", "PRIEST", "FIRST")
        self.assertEqual(1, build_dashboard([row, replace(row, match_id="2", format="WILD"),
            replace(row, match_id="3", game_type="GT_ARENA")])["overall"]["games"])

    def test_history_is_not_silently_limited_to_200(self):
        rows = [MatchRecord(str(i), "2026-10-01", "WIN", "MAGE", "PRIEST", "FIRST") for i in range(205)]
        self.assertEqual(205, len(build_dashboard(rows)["recent_matches"]))

    def test_ties_do_not_lower_win_rate(self):
        rows = [MatchRecord(str(i), "2026-10-01", result, "MAGE", "PRIEST", "FIRST") for i, result in enumerate(("WIN", "LOSS", "TIE"))]
        self.assertEqual(50, build_dashboard(rows)["overall"]["win_rate"])


class SecretParityTests(unittest.TestCase):
    def test_metadata_refresh_preserves_public_eliminations_and_hover_names(self):
        f = secret_fixture.SecretRailTests(); f.setUp(); self.addCleanup(f.doCleanups)
        f.add_secret(); f.game.secrets[100].eliminate("COUNTER", "spell resolved")
        f.tracker.refresh_metadata(f.game)
        row=_secret_reads(f.game,f.db)[0]
        self.assertNotIn("Counterspell",row["candidate_names"])
        self.assertEqual("COUNTER",row["eliminated_cards"][0]["card_id"])

    def test_armor_only_secret_preserves_attack_deductions(self):
        f = secret_fixture.SecretRailTests(); f.setUp(); self.addCleanup(f.doCleanups)
        e = f.add_secret(100); f.add_secret(101)
        f.tracker.observe_public_event(f.game, SecretObservation("ATTACK", actor_pid=1, target_pid=2, card_type="MINION", is_hero_target=True))
        e.card_id="BARRIER"; e.zone="GRAVEYARD"
        f.tracker.reveal_public_identity(f.game, e)
        f.tracker.on_zone_change(f.game, e, "SECRET", "GRAVEYARD")
        f.tracker.flush_pending_tests(f.game)
        self.assertNotIn("MISDIRECT", f.game.secrets[101].candidates)
        self.assertIn("COUNTER", f.game.secrets[101].candidates)

    def test_locked_secret_is_not_eliminated(self):
        f = secret_fixture.SecretRailTests(); f.setUp(); self.addCleanup(f.doCleanups)
        e = f.add_secret(); e.tags["SECRET_LOCKED"] = "1"
        f.tracker.observe_public_event(f.game, SecretObservation("PLAY", actor_pid=1, card_type="SPELL"))
        self.assertEqual(0, f.tracker.flush_pending_tests(f.game))
        self.assertIn("COUNTER", f.game.secrets[100].candidates)

    def test_triggered_identity_excludes_other_existing_slots(self):
        f = secret_fixture.SecretRailTests(); f.setUp(); self.addCleanup(f.doCleanups)
        e = f.add_secret(100); f.add_secret(101)
        f.tracker.observe_public_event(f.game, SecretObservation("PLAY", actor_pid=1, card_type="SPELL"))
        e.card_id = "COUNTER"; e.zone = "GRAVEYARD"
        f.tracker.reveal_public_identity(f.game, e)
        f.tracker.on_zone_change(f.game, e, "SECRET", "GRAVEYARD")
        self.assertNotIn("COUNTER", f.game.secrets[101].candidates)
        self.assertIn("RUNES", f.game.secrets[101].candidates)
        f.add_secret(102)
        self.assertIn("COUNTER", f.game.secrets[102].candidates)

    def test_late_generator_uses_past_pool_without_secret_identity(self):
        from ghostdata.tracking.card_db import CardDefinition
        f = secret_fixture.SecretRailTests(); f.setUp(); self.addCleanup(f.doCleanups)
        past = replace(secret_fixture.secret_card("PAST", "Spellbender", "Conditional secret"), card_set="EXPERT1", spell_school="ARCANE")
        frost = replace(past, card_id="PAST_FROST", name="Ice Block", spell_school="FROST")
        source = CardDefinition("ALTER", "Alter Time", "MAGE", "SPELL")
        f.db.cards.update({c.card_id:c for c in (past, frost, source)})
        e = f.add_secret(); generator=f.game.entity(50); generator.card_id="ALTER"; generator.zone="GRAVEYARD"
        e.creator=50; e.card_id="PAST_FROST"
        f.tracker.on_provenance_change(f.game, e)
        self.assertEqual(["Spellbender"], _secret_reads(f.game)[0]["candidate_names"])
        self.assertEqual("PAST", _secret_reads(f.game, f.db)[0]["candidate_cards"][0]["card_id"])

    def test_conditional_historical_secret_not_eliminated_by_broad_template(self):
        from ghostdata.tracking.secrets import infer_safe_trigger_rule
        card = secret_fixture.secret_card("TEST", "Conditional Secret", "After your opponent casts a spell, if it costs (10), draw.")
        self.assertIsNone(infer_safe_trigger_rule(card))

    def test_eliminated_names_remain_available_to_secret_area(self):
        f = secret_fixture.SecretRailTests(); f.setUp(); self.addCleanup(f.doCleanups)
        f.add_secret(100)
        f.game.secrets[100].eliminate("COUNTER", "spell resolved")
        self.assertEqual(["Counterspell"], _secret_reads(f.game)[0]["eliminated_names"])

    def test_untimely_death_requires_play_not_summon(self):
        state = GameState(global_turn=4)
        e = state.entity(1); e.controller = 2; e.entered_play_turn = 3
        rule = SecretTriggerRule("recent_friendly_minion_died")
        action = SecretObservation("MINION_DIED", actor_pid=1, target_pid=2, target_entity_id=1)
        self.assertFalse(rule.matches(action, 2, state))
        e.last_played_turn = 3
        self.assertTrue(rule.matches(action, 2, state))

    def test_nested_trigger_does_not_eliminate_before_reveal(self):
        f = secret_fixture.SecretRailTests(); f.setUp(); self.addCleanup(f.doCleanups)
        f.add_secret()
        parser = PowerLogParser(card_db=f.db); parser.state = f.game; parser.secret_tracker = f.tracker
        spell = f.game.entity(20); spell.controller=1; spell.card_type="SPELL"; spell.zone="HAND"
        def line(text): parser.parse_line("D 12:00:00.000 GameState.DebugPrintPower() - " + text)
        line("BLOCK_START BlockType=PLAY Entity=[entityName=Spell id=20 zone=HAND zonePos=1 cardId=COUNTER player=1] EffectCardId= Target=0")
        line("BLOCK_START BlockType=TRIGGER Entity=[entityName=Unknown id=100 zone=SECRET zonePos=1 cardId= player=2] EffectCardId= Target=0")
        self.assertIn("COUNTER", f.game.secrets[100].candidates)
        line("BLOCK_END")
        self.assertIn("COUNTER", f.game.secrets[100].candidates)
        line("BLOCK_END")
        self.assertNotIn("COUNTER", f.game.secrets[100].candidates)

    def test_duplicate_exclusion_is_scoped_to_controller(self):
        f = secret_fixture.SecretRailTests(); f.setUp(); self.addCleanup(f.doCleanups)
        f.add_secret(100)
        e = f.game.entity(101); e.controller = 1; e.zone = "SECRET"
        f.game.secrets[101] = SecretState(101, 1, 0, candidates={"COUNTER": SecretCandidate("COUNTER", "Counterspell", "MAGE")})
        f.tracker.reconcile_duplicate_active_secrets(f.game)
        self.assertIn("COUNTER", f.game.secrets[100].candidates)

    def test_pressure_plate_requires_enemy_minion(self):
        state = GameState(); rule = SecretTriggerRule("spell_with_enemy_minion")
        action = SecretObservation("PLAY", actor_pid=1, card_type="SPELL")
        self.assertFalse(rule.matches(action, 2, state))
        e = state.entity(1); e.controller = 1; e.zone = "PLAY"; e.card_type = "MINION"
        self.assertTrue(rule.matches(action, 2, state))
        e.card_type = "LOCATION"
        self.assertFalse(rule.matches(action, 2, state))

    def test_pressure_plate_is_not_excluded_if_spell_clears_board(self):
        f = secret_fixture.SecretRailTests(); f.setUp(); self.addCleanup(f.doCleanups)
        f.add_secret(100)
        f.game.secrets[100].candidates = {"PLATE": SecretCandidate("PLATE", "Pressure Plate", "HUNTER", rule_key="spell_with_enemy_minion")}
        e = f.game.entity(20); e.controller = 1; e.zone = "PLAY"; e.card_type = "MINION"
        f.tracker.observe_public_event(f.game, SecretObservation("PLAY", actor_pid=1, card_type="SPELL"))
        e.zone = "GRAVEYARD"
        f.tracker.flush_pending_tests(f.game)
        self.assertIn("PLATE", f.game.secrets[100].candidates)

    def test_flames_checks_owners_turn_and_enemy_board(self):
        state = GameState(); rule = SecretTriggerRule("owner_turn_with_enemy_minion")
        e = state.entity(1); e.controller = 1; e.zone = "PLAY"; e.card_type = "MINION"
        self.assertFalse(rule.matches(SecretObservation("TURN_START", actor_pid=1), 2, state))
        self.assertTrue(rule.matches(SecretObservation("TURN_START", actor_pid=2), 2, state))
