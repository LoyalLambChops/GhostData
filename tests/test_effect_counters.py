import unittest
from ghostdata.tracking.effect_counters import counters
from ghostdata.tracking.models import GameState
from ghostdata.tracking.card_history import CardObservation

class EffectCounterTests(unittest.TestCase):
    def setUp(self):
        self.game = GameState(active=True, local_player_pid=1)
        self.game.player(1)
        self.game.player(2)

    def test_aessina_threshold_and_authoritative_value(self):
        for value, detail in [(0, "20 friendly deaths remaining"), (19, "1 friendly death remaining"), (20, "Ready"), (25, "Ready")]:
            self.game.players[1].tags["NUM_FRIENDLY_MINIONS_THAT_DIED_THIS_GAME"] = str(value)
            row, = counters(self.game, 1, ["EDR_430"])
            self.assertEqual(row.value, f"{value} / 20")
            self.assertEqual(row.detail, detail)

    def test_herald_uses_absolute_tag_not_played_cards(self):
        self.game.players[2].tags["HERALD_COLOSSAL_AMOUNT"] = "99"
        for value in (0, 1, 1, 4, 2):
            self.game.players[1].tags["HERALD_COLOSSAL_AMOUNT"] = str(value)
            self.assertEqual(counters(self.game, 1, ["CATA_725"])[0].value, str(value))

    def test_partial_log_unknown_and_complete_start_zero(self):
        self.assertEqual(counters(self.game, 1, ["EDR_430"])[0].value, "? / 20")
        self.game.game_tags["GHOSTDATA_GAME_START"] = "12:00:00"
        self.assertEqual(counters(self.game, 1, ["CATA_155"])[0].value, "0")
        self.game.card_history.extend([
            CardObservation("DEATH", 10, "A", 1, 1, card_type="MINION"),
            CardObservation("DEATH", 11, "B", 2, 1, card_type="MINION"),
            CardObservation("PLAY", 12, "C", 1, 1, card_type="MINION")])
        self.assertEqual(counters(self.game, 1, ["EDR_430"])[0].value, "1 / 20")

    def test_relevance_and_lifecycle(self):
        self.assertEqual(counters(self.game, 1), ())
        entity = self.game.entity(10)
        entity.card_id, entity.controller, entity.zone = "EDR_430", 2, "HAND"
        self.assertEqual(counters(self.game, 1), ())
        entity.controller, entity.zone = 1, "SETASIDE"
        self.assertEqual(counters(self.game, 1), ())
        entity.zone = "HAND"
        self.assertEqual(counters(self.game, 1)[0].key, "aessina")
        self.game.complete = True
        self.assertEqual(counters(self.game, 1), ())
        self.game.reset()
        self.assertEqual(counters(self.game, 1), ())

    def test_invalid_tag_is_unknown(self):
        self.game.players[1].tags["HERALD_COLOSSAL_AMOUNT"] = "-2"
        self.assertEqual(counters(self.game, 1, ["CATA_725"])[0].value, "?")
