from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ghostdata.tracking.card_db import CardDefinition
from ghostdata.tracking.models import GameState
from ghostdata.tracking.parser import PowerLogParser
from ghostdata.tracking.snapshot import TrackerDeckSnapshot
from ghostdata.tracking.tracker import DeckTrackerEngine
from ghostdata.tracking.tracker.models import Provenance


class FakeCardDb:
    local_source = False
    def __init__(self, definitions):
        self.cards = {c.card_id: c for c in definitions}
        self.cards_by_dbf = {c.dbf_id: c for c in definitions if c.dbf_id is not None}
        self.ready = True

    def get(self, card_id):
        return self.cards.get(card_id)

    def get_by_dbf(self, dbf):
        return self.cards_by_dbf.get(int(dbf))

    def dbf_id_for_card_id(self, card_id):
        card = self.get(str(card_id))
        if card and card.dbf_id:
            return card.dbf_id
        text = str(card_id or "")
        return int(text) if text.isdigit() and int(text) > 0 else None


class DeckTrackerTests(unittest.TestCase):
    def setUp(self):
        defs = []
        for dbf in range(1, 17):
            defs.append(CardDefinition(
                card_id=f"CARD_{dbf}", name=f"Card {dbf:02d}", card_class="MAGE",
                card_type="SPELL", cost=(dbf - 1) % 8, collectible=True, dbf_id=dbf,
            ))
        defs.append(CardDefinition(
            card_id="OPP_A", name="Opponent A", card_class="PALADIN",
            card_type="SPELL", cost=2, collectible=True, dbf_id=101,
        ))
        defs.append(CardDefinition(
            card_id="OPP_B", name="Opponent B", card_class="PALADIN",
            card_type="MINION", cost=4, collectible=True, dbf_id=102,
        ))
        defs.append(CardDefinition(
            card_id="HERO_06", name="Malfurion Stormrage", card_class="DRUID",
            card_type="HERO", cost=0, collectible=False, dbf_id=274,
        ))
        defs.append(CardDefinition(
            card_id="HERO_CARD", name="Played Hero Card", card_class="PALADIN",
            card_type="HERO", cost=8, collectible=True, dbf_id=103,
        ))
        self.db = FakeCardDb(defs)
        cards = tuple((dbf, 2) for dbf in range(1, 16))  # 30 cards
        self.snapshot = TrackerDeckSnapshot(
            status="EXACT", deck_name="Test Mage", deck_hash="deck-1",
            class_id="MAGE", hero_dbf_ids=(637,), cards=cards,
        )
        self.tracker = DeckTrackerEngine(card_db=self.db, supported_player_classes=("MAGE", "PRIEST"))
        self.assertTrue(self.tracker.seed_selected_deck(self.snapshot))
        self.state = GameState(active=True, game_number=1, local_player_pid=1)
        self.state.player(1).player_class = "MAGE"
        self.state.player(2).player_class = "PALADIN"

    def _emit_zone(self, eid, controller, new_zone, card_id="", creator=None):
        e = self.state.entity(eid)
        e.controller = controller
        if creator is not None:
            e.creator = creator
        if card_id:
            e.card_id = card_id
        old = e.zone or ""
        e.zone = new_zone
        self.state.emit("12:00:00", "ZONE_CHANGE", f"{old}->{new_zone}",
                        entity_id=eid, old_zone=old, new_zone=new_zone, player=controller, card_id=e.card_id)
        self.tracker.observe(self.state)
        return e

    def _reveal(self, eid, card_id):
        e = self.state.entity(eid)
        e.update_card_identity(card_id)
        self.state.emit("12:00:01", "REVEAL", card_id, entity_id=eid, card_id=card_id, player=e.controller)
        self.tracker.observe(self.state)
        return e

    def test_player_original_multiset_tracks_draw_and_shuffle_back(self):
        # 30 hidden original entities begin in deck.
        for eid in range(1, 31):
            self._emit_zone(eid, 1, "DECK")
        s = self.tracker.state
        self.assertEqual(30, s.original_cards_remaining)
        self.assertEqual(30, s.player_deck_count)
        self.assertEqual("EXACT", s.player_accounting_status)

        self._reveal(1, "CARD_1")
        self._emit_zone(1, 1, "HAND", "CARD_1")
        s = self.tracker.state
        row = next(r for r in s.player_rows if r.dbf_id == 1)
        self.assertEqual(1, row.remaining_copies)
        self.assertEqual(1, row.drawn_copies)
        self.assertEqual(29, s.original_cards_remaining)
        self.assertEqual(29, s.player_deck_count)
        self.assertEqual("EXACT", s.player_accounting_status)

        # A mulligan/shuffle return of the same original entity restores it.
        self._emit_zone(1, 1, "DECK", "CARD_1")
        s = self.tracker.state
        row = next(r for r in s.player_rows if r.dbf_id == 1)
        self.assertEqual(2, row.remaining_copies)
        self.assertEqual(30, s.original_cards_remaining)
        self.assertEqual(30, s.player_deck_count)
        self.assertEqual("EXACT", s.player_accounting_status)

    def test_generated_card_in_deck_never_consumes_original_copy(self):
        for eid in range(1, 31):
            self._emit_zone(eid, 1, "DECK")
        self._reveal(1, "CARD_1")
        self._emit_zone(1, 1, "HAND", "CARD_1")

        # New generated entity begins outside deck and is then shuffled in.
        self._emit_zone(100, 1, "SETASIDE", "CARD_1", creator=999)
        self._emit_zone(100, 1, "DECK", "CARD_1", creator=999)
        s = self.tracker.state
        row = next(r for r in s.player_rows if r.dbf_id == 1)
        self.assertEqual(1, row.remaining_copies)
        self.assertEqual(29, s.original_cards_remaining)
        self.assertEqual(30, s.player_deck_count)
        self.assertEqual(1, s.player_known_non_original_in_deck)
        self.assertEqual("EXACT", s.player_accounting_status)

    def test_transformed_original_in_deck_does_not_claim_original_card_remains(self):
        for eid in range(1, 31):
            self._emit_zone(eid, 1, "DECK")
        self._reveal(1, "CARD_1")
        # Transform while still in deck.
        self._reveal(1, "CARD_2")
        s = self.tracker.state
        row = next(r for r in s.player_rows if r.dbf_id == 1)
        self.assertEqual(1, row.remaining_copies)
        self.assertEqual(29, s.original_cards_remaining)
        self.assertEqual(1, s.player_known_non_original_in_deck)
        self.assertEqual(30, s.player_deck_count)
        self.assertEqual("EXACT", s.player_accounting_status)

    def test_opponent_is_observational_and_idempotent(self):
        for eid in range(201, 231):
            self._emit_zone(eid, 2, "DECK")
        self._reveal(201, "OPP_A")
        self._emit_zone(201, 2, "HAND", "OPP_A")
        # PLAY after REVEAL must not double count the same entity/card identity.
        self.state.emit("12:00:02", "PLAY", "Opponent A", entity_id=201, card_id="OPP_A", player=2)
        self.tracker.observe(self.state)
        s = self.tracker.state
        self.assertEqual(1, len(s.opponent_rows))
        self.assertEqual("OPP_A", s.opponent_rows[0].card_id)
        self.assertEqual(1, s.opponent_rows[0].observed_copies)
        self.assertEqual(1, s.opponent_rows[0].known_in_hand)
        self.assertEqual(29, s.opponent_deck_count)

        # Unrevealed OPP_B is not invented into the observed list.
        self.assertNotIn("OPP_B", {r.card_id for r in s.opponent_rows})

    def test_opponent_starting_hero_is_not_a_card_history_row(self):
        hero = self.state.entity(200)
        hero.controller = 2
        hero.card_id = "HERO_06"
        hero.card_type = "HERO"
        hero.zone = "PLAY"
        self.state.player(2).hero_entity_id = 200
        self.state.emit("12:00:00", "REVEAL", "Malfurion Stormrage", entity_id=200, card_id="HERO_06", player=2)
        self.tracker.observe(self.state)
        self.assertNotIn("HERO_06", {r.card_id for r in self.tracker.state.opponent_rows})

    def test_opponent_hero_card_played_from_hand_remains_observed(self):
        self._emit_zone(202, 2, "HAND", "HERO_CARD")
        self._reveal(202, "HERO_CARD")
        self._emit_zone(202, 2, "PLAY", "HERO_CARD")
        self.state.emit("12:00:02", "PLAY", "Played Hero Card", entity_id=202, card_id="HERO_CARD", player=2)
        self.tracker.observe(self.state)
        self.assertIn("HERO_CARD", {r.card_id for r in self.tracker.state.opponent_rows})

    def test_unchosen_discover_option_revealed_in_graveyard_is_not_observed(self):
        # Match the live Breakout Architect lifecycle: an option is created in
        # SETASIDE, revealed while discarded to GRAVEYARD, and only afterwards
        # receives its WAS_DISCOVER_OPTION tag.
        option = self._emit_zone(203, 2, "SETASIDE", creator=201)
        option.card_type = "SPELL"
        self._reveal(203, "OPP_A")
        self._emit_zone(203, 2, "GRAVEYARD", "OPP_A", creator=201)
        # Canonical and task streams can expose the same SHOW_ENTITY after the
        # graveyard move, before the trailing option tag has been applied.
        self.state.emit("12:00:02", "REVEAL", "OPP_A", entity_id=203, card_id="OPP_A", player=2)
        self.tracker.observe(self.state)
        self.assertNotIn("OPP_A", {r.card_id for r in self.tracker.state.opponent_rows})

        option.tags["WAS_DISCOVER_OPTION"] = "1"
        self.tracker.observe(self.state)
        self.assertNotIn("OPP_A", {r.card_id for r in self.tracker.state.opponent_rows})

    def test_selected_discover_option_that_enters_hand_remains_eligible(self):
        option = self._emit_zone(204, 2, "SETASIDE", creator=201)
        option.card_type = "SPELL"
        option.tags["WAS_DISCOVER_OPTION"] = "1"
        self._emit_zone(204, 2, "HAND", "OPP_A", creator=201)
        self._reveal(204, "OPP_A")
        self.assertIn("OPP_A", {r.card_id for r in self.tracker.state.opponent_rows})

    def test_game_reset_clears_match_observations_but_preserves_selected_deck(self):
        self._emit_zone(201, 2, "HAND", "OPP_A")
        self._reveal(201, "OPP_A")
        self.assertEqual(1, len(self.tracker.state.opponent_rows))

        self.state = GameState(active=True, game_number=2, local_player_pid=1)
        self.state.player(1).player_class = "MAGE"
        self.state.player(2).player_class = "PRIEST"
        self.state.emit("12:10:00", "GAME_START", "new", game_number=2)
        self.tracker.observe(self.state)
        s = self.tracker.state
        self.assertEqual(2, s.game_number)
        self.assertEqual(30, s.starting_cards)
        self.assertEqual(30, s.original_cards_remaining)
        self.assertEqual(0, len(s.opponent_rows))



    def test_late_sensor_baseline_reconciles_warm_replayed_entities(self):
        # Simulate the real live-runtime order: Power.log reconstructs first,
        # then the asynchronous exact-deck sensor result arrives.
        tracker = DeckTrackerEngine(card_db=self.db, supported_player_classes=("MAGE", "PRIEST"))
        state = GameState(active=True, game_number=1, local_player_pid=1)
        state.player(1).player_class = "MAGE"
        state.player(2).player_class = "PALADIN"

        def zone(eid, zone_name, card_id=""):
            e = state.entity(eid)
            e.controller = 1
            if card_id:
                e.card_id = card_id
            old = e.zone or ""
            e.zone = zone_name
            state.emit("12:20:00", "ZONE_CHANGE", f"{old}->{zone_name}", entity_id=eid, old_zone=old, new_zone=zone_name, player=1, card_id=e.card_id)
            tracker.observe(state)

        for eid in range(1, 31):
            zone(eid, "DECK")
        # One original card is drawn/revealed before the selected-deck baseline exists.
        zone(1, "HAND", "CARD_1")
        self.assertEqual(0, tracker.state.starting_cards)

        self.assertTrue(tracker.seed_selected_deck(self.snapshot, state))
        current = tracker.state
        row = next(r for r in current.player_rows if r.dbf_id == 1)
        self.assertEqual(29, current.original_cards_remaining)
        self.assertEqual(1, row.remaining_copies)
        self.assertEqual(1, row.drawn_copies)
        self.assertEqual("EXACT", current.player_accounting_status)


    def test_inline_identity_after_hidden_draw_restores_exact_accounting(self):
        """A local CardID first exposed by an inline Power.log reference must reach the tracker.

        Current Hearthstone logs can move a hidden entity DECK->HAND and only
        expose the local card identity later in an inline TAG_CHANGE / Options
        reference.  v46.1 updated GameState in that situation but emitted no
        semantic identity event, leaving the tracker one original card high.
        """
        parser = PowerLogParser(card_db=self.db, emit_events=False)
        tracker = DeckTrackerEngine(card_db=self.db, supported_player_classes=("MAGE", "PRIEST"))
        self.assertTrue(tracker.seed_selected_deck(self.snapshot))

        def feed(line):
            parser.parse_line(line)
            tracker.observe(parser.state)

        feed("D 12:30:00.0000000 GameState.DebugPrintPower() - CREATE_GAME\n")
        parser.state.local_player_pid = 1
        parser.state.player(1).player_class = "MAGE"
        parser.state.player(2).player_class = "PALADIN"

        # Reconstruct the 30 hidden original deck entities.
        for eid in range(1, 31):
            feed(f"D 12:30:00.0000000 GameState.DebugPrintPower() - FULL_ENTITY - Creating ID={eid} CardID=\n")
            feed("D 12:30:00.0000000 GameState.DebugPrintPower() -     tag=ZONE value=DECK\n")
            feed("D 12:30:00.0000000 GameState.DebugPrintPower() -     tag=CONTROLLER value=1\n")

        self.assertEqual("EXACT", tracker.state.player_accounting_status)
        self.assertEqual(30, tracker.state.original_cards_remaining)

        # The card leaves the deck while still hidden.  At this instant the
        # fail-closed tracker correctly notices a one-card identity gap.
        feed("D 12:30:01.0000000 GameState.DebugPrintPower() - TAG_CHANGE Entity=1 tag=ZONE value=HAND \n")
        self.assertEqual(29, tracker.state.player_deck_count)
        self.assertEqual(30, tracker.state.original_cards_remaining)
        self.assertEqual("PARTIAL", tracker.state.player_accounting_status)
        self.assertEqual(-1, tracker.state.player_accounting_delta)

        # Hearthstone then reveals the local identity only inside an inline
        # reference on a non-zone tag.  This must now emit a deduplicated REVEAL
        # event so the incremental tracker assigns the original copy.
        feed("D 12:30:01.1000000 GameState.DebugPrintPower() - TAG_CHANGE Entity=[entityName=Card 01 id=1 zone=HAND zonePos=1 cardId=CARD_1 player=1] tag=ZONE_POSITION value=1 \n")
        self.assertEqual(29, tracker.state.original_cards_remaining)
        self.assertEqual("EXACT", tracker.state.player_accounting_status)
        self.assertEqual(0, tracker.state.player_accounting_delta)
        row = next(r for r in tracker.state.player_rows if r.dbf_id == 1)
        self.assertEqual(1, row.remaining_copies)
        self.assertEqual(1, row.drawn_copies)
        reveals = [e for e in parser.state.events if e.event_type == "REVEAL" and e.data.get("entity_id") == 1]
        self.assertEqual(1, len(reveals))

    def test_twenty_card_priest_baseline_is_supported(self):
        priest_cards = tuple((dbf, 2) for dbf in range(1, 11))
        snapshot = TrackerDeckSnapshot(
            status="EXACT", deck_name="20 Card Priest", deck_hash="priest-20",
            class_id="PRIEST", hero_dbf_ids=(813,), cards=priest_cards,
        )
        tracker = DeckTrackerEngine(card_db=self.db, supported_player_classes=("MAGE", "PRIEST"))
        self.assertTrue(tracker.seed_selected_deck(snapshot))
        self.assertEqual(20, tracker.state.starting_cards)
        self.assertEqual(20, tracker.state.original_cards_remaining)

    def test_original_card_stolen_by_opponent_preserves_stolen_provenance(self):
        for eid in range(1, 31):
            self._emit_zone(eid, 1, "DECK")
        self._reveal(1, "CARD_1")
        self._emit_zone(1, 1, "HAND", "CARD_1")
        # Controller transition to opponent, followed by an observed play.
        e = self.state.entity(1)
        old_controller = e.controller
        e.controller = 2
        self.state.emit(
            "12:00:03", "CONTROLLER_CHANGE", "1->2",
            entity_id=1, old_controller=old_controller, new_controller=2, card_id=e.card_id,
        )
        self.tracker.observe(self.state)
        self.state.emit("12:00:04", "PLAY", "Card 01", entity_id=1, card_id="CARD_1", player=2)
        self.tracker.observe(self.state)
        row = next(r for r in self.tracker.state.opponent_rows if r.card_id == "CARD_1")
        self.assertEqual(Provenance.STOLEN, row.provenance)

    def test_parser_emits_zone_and_controller_events_for_tracker(self):
        parser = PowerLogParser()
        parser.parse_lines([
            "D 12:00:00.0000000 GameState.DebugPrintPower() - CREATE_GAME\n",
            "D 12:00:00.0000000 GameState.DebugPrintPower() -     FULL_ENTITY - Creating ID=7 CardID=\n",
            "D 12:00:00.0000000 GameState.DebugPrintPower() -         tag=CONTROLLER value=1\n",
            "D 12:00:00.0000000 GameState.DebugPrintPower() -         tag=ZONE value=DECK\n",
            "D 12:00:01.0000000 GameState.DebugPrintPower() -     TAG_CHANGE Entity=7 tag=ZONE value=HAND \n",
            "D 12:00:01.0000000 GameState.DebugPrintPower() -     TAG_CHANGE Entity=7 tag=CONTROLLER value=2 \n",
        ])
        kinds = [e.event_type for e in parser.state.events]
        self.assertIn("ZONE_CHANGE", kinds)
        self.assertIn("CONTROLLER_CHANGE", kinds)
        zones = [e for e in parser.state.events if e.event_type == "ZONE_CHANGE"]
        self.assertEqual("DECK", zones[0].data["new_zone"])
        self.assertEqual("HAND", zones[-1].data["new_zone"])

    def test_snapshot_is_json_serializable_for_ndjson_bridge(self):
        payload = json.dumps(self.tracker.state.__dict__, default=lambda x: x.__dict__)
        self.assertIn("player_rows", payload)


if __name__ == "__main__":
    unittest.main()
