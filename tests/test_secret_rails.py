from pathlib import Path
import tempfile
import unittest

from ghostdata.tracker_bridge import _secret_reads
from ghostdata.tracking.card_db import CardDatabase, CardDefinition
from ghostdata.tracking.models import GameState
from ghostdata.tracking.parser import PowerLogParser
from ghostdata.tracking.secrets import SecretObservation, SecretTracker
from ghostdata.tracking.standard_secrets import StandardSecretCatalog


def secret_card(card_id: str, name: str, text: str) -> CardDefinition:
    return CardDefinition(card_id, name, "MAGE", "SPELL", 3, True, ("SECRET",), "CORE", text)


class SecretRailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = CardDatabase(Path(self.tmp.name))
        cards = [
            secret_card("COUNTER", "Counterspell", "Secret: When your opponent casts a spell, Counter it."),
            secret_card("RUNES", "Explosive Runes", "Secret: After your opponent plays a minion, deal 6 damage to it."),
            secret_card("BARRIER", "Ice Barrier", "Secret: When your hero is attacked, gain 8 Armor."),
            secret_card("ALLY", "Oasis Ally", "Secret: When a friendly minion is attacked, summon a Water Elemental."),
            secret_card("MISDIRECT", "Mystic Misdirection", "Secret: When an enemy minion attacks, transform it into a 1/1 Sheep."),
        ]
        self.db.cards = {card.card_id: card for card in cards}
        self.db.loaded_from = "test"
        self.catalog = StandardSecretCatalog(
            patch="36.4.2", source="test", source_url="test",
            classes={"MAGE": tuple(card.name for card in cards)},
        )
        self.tracker = SecretTracker(self.db, standard_catalog=self.catalog)
        self.game = GameState(active=True, complete=False, game_number=1, local_player_pid=1)
        self.game.player(1).player_class = "PRIEST"
        self.game.player(2).player_class = "MAGE"

    def add_secret(self, entity_id: int = 100):
        entity = self.game.entity(entity_id)
        entity.controller = 2
        entity.zone = "SECRET"
        entity.card_type = "SPELL"
        entity.card_class = "MAGE"
        entity.tags["SECRET"] = "1"
        self.tracker.on_zone_change(self.game, entity, "HAND", "SECRET")
        return entity

    def test_verified_candidates_are_presented_separately(self):
        self.add_secret()
        row = _secret_reads(self.game)[0]
        self.assertEqual("MAGE", row["secret_class"])
        self.assertEqual(5, row["candidate_count"])
        self.assertEqual("ACTIVE", row["inference_status"])

    def test_local_standard_legality_overrides_fixture_catalog_and_expires_closed(self):
        from dataclasses import replace
        from datetime import datetime, timezone, timedelta
        self.db.local_source = True
        self.db.build_number = 255130
        self.db.log_build = self.game.build_number = 254477
        self.db.valid_until = datetime.now(timezone.utc) + timedelta(hours=1)
        self.db.cards = {cid: replace(card, standard=cid == "COUNTER") for cid, card in self.db.cards.items()}
        self.add_secret()
        self.assertEqual(_secret_reads(self.game)[0]["candidate_names"], ["Counterspell"])
        self.db.valid_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.tracker.refresh_metadata(self.game)
        self.assertEqual(_secret_reads(self.game)[0]["candidate_count"], 0)
        self.db.valid_until = datetime.now(timezone.utc) + timedelta(hours=1)
        self.game.build_number += 1
        self.tracker.refresh_metadata(self.game)
        self.assertEqual(_secret_reads(self.game)[0]["candidate_count"], 0)

    def test_safe_non_trigger_narrows_candidates(self):
        self.add_secret()
        self.tracker.observe_public_event(
            self.game, SecretObservation("PLAY", actor_pid=1, card_type="SPELL")
        )
        self.assertEqual(1, self.tracker.flush_pending_tests(self.game, "spell settled"))
        row = _secret_reads(self.game)[0]
        self.assertNotIn("Counterspell", row["candidate_names"])
        self.assertEqual("NARROWED", row["inference_status"])

    def test_enemy_minion_attack_non_trigger_eliminates_mystic_misdirection(self):
        self.add_secret()
        self.tracker.observe_public_event(
            self.game, SecretObservation("ATTACK", actor_pid=1, card_type="MINION")
        )
        self.assertEqual(1, self.tracker.flush_pending_tests(self.game, "attack settled"))
        row = _secret_reads(self.game)[0]
        self.assertNotIn("Mystic Misdirection", row["candidate_names"])

    def test_hidden_engine_identity_does_not_leak_to_rail(self):
        entity = self.add_secret()
        before = _secret_reads(self.game)[0]["candidate_names"]
        self.tracker.learn_internal_identity(
            self.game, entity, source="sensor", card_id="COUNTER", name="Counterspell"
        )
        self.assertEqual(before, _secret_reads(self.game)[0]["candidate_names"])


    def test_task_only_generated_secret_registers_when_controller_arrives_after_zone(self):
        parser = PowerLogParser(card_db=self.db)
        parser.secret_tracker = SecretTracker(self.db, standard_catalog=self.catalog)
        parser.parse_lines([
            "D 12:00:00.0000000 GameState.DebugPrintPower() - CREATE_GAME\n",
            "D 12:00:01.0000000 PowerTaskList.DebugPrintPower() - FULL_ENTITY - Updating [entityName=UNKNOWN ENTITY [cardType=INVALID] id=106 zone=SECRET zonePos=0 cardId= player=2] CardID=\n",
            "D 12:00:01.0000000 PowerTaskList.DebugPrintPower() -     tag=ZONE value=SECRET\n",
            "D 12:00:01.0000000 PowerTaskList.DebugPrintPower() -     tag=CONTROLLER value=2\n",
            "D 12:00:01.0000000 PowerTaskList.DebugPrintPower() -     tag=ENTITY_ID value=106\n",
            "D 12:00:01.0000000 PowerTaskList.DebugPrintPower() -     tag=SECRET value=1\n",
            "D 12:00:01.0000000 PowerTaskList.DebugPrintPower() -     tag=CLASS value=MAGE\n",
        ])
        secret = parser.state.secrets[106]
        self.assertEqual(2, secret.controller)
        self.assertEqual("MAGE", secret.secret_class)
        self.assertEqual(5, len(secret.candidates))

