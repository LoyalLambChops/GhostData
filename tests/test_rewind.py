import unittest
from ghostdata.tracking.timeline import effective_game_lines, RewindJournal
from ghostdata.tracking.parser import PowerLogParser
from ghostdata.tracker_bridge import ingest_tracker_chunk
import test_live_deck_tracker as fixture
from synthetic_match import completed_match_log


def line(body, task=False):
    return f'D 12:00:00.000 {"PowerTaskList" if task else "GameState"}.DebugPrintPower() - {body}\n'


def block(kind, eid, card, task=False):
    return line(f"BLOCK_START BlockType={kind} Entity=[entityName=Card id={eid} zone=HAND zonePos=1 cardId={card} player=1] EffectCardId= EffectIndex=0 Target=0 SubOption=-1", task)


class RewindTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.DeckTrackerTests(); self.f.setUp()
        self.p = PowerLogParser(card_db=self.f.db); self.p.state = self.f.state
        self.f._emit_zone(100, 1, "DECK", "CARD_1")
        self.f._emit_zone(100, 1, "HAND")

    def feed(self, *rows):
        ingest_tracker_chunk(self.p, self.f.tracker, b"", "".join(rows).encode())

    def test_rewind_restores_counts_provenance_and_removes_discarded_generation(self):
        self.feed(block("PLAY", 100, "CARD_1"), line("TAG_CHANGE Entity=100 tag=ZONE value=GRAVEYARD"),
                  line("FULL_ENTITY - Creating ID=200 CardID=CARD_2"), line("tag=CONTROLLER value=1"),
                  line("tag=ZONE value=HAND"), line("tag=CREATOR value=100"), line("BLOCK_END"))
        self.assertIn(200, self.p.state.entities)
        self.feed(block("POWER", 300, "TIME_000tb"))
        self.assertNotIn(200, self.p.state.entities)
        self.assertEqual("HAND", self.p.state.entity(100).zone)
        self.assertFalse(any(e.event_type == "PLAY" for e in self.p.state.events))
        row = next(r for r in self.f.tracker.state.player_display_rows if r.card_id == "CARD_1")
        self.assertEqual((1,1), (row.count,row.in_hand))
        self.feed(block("PLAY",100,"CARD_1"),line("TAG_CHANGE Entity=100 tag=ZONE value=GRAVEYARD"),line("BLOCK_END"))
        self.assertEqual(1, sum(e.event_type == "PLAY" for e in self.p.state.events))

    def test_late_task_rewind_preserves_canonical_reexecution_and_deduplicates(self):
        original = block("PLAY",100,"CARD_1")
        retry = block("PLAY",100,"CARD_1")
        rows = [original,line("TAG_CHANGE Entity=100 tag=ZONE value=GRAVEYARD"),line("BLOCK_END"),
                block("PLAY",100,"CARD_1",True),line("BLOCK_END",True),
                block("POWER",300,""),line("BLOCK_END"),retry,
                line("TAG_CHANGE Entity=100 tag=ZONE value=GRAVEYARD"),line("BLOCK_END"),
                block("POWER",300,"TIME_000tb",True),line("BLOCK_END",True)]
        self.feed(*rows)
        self.assertEqual(1, sum(e.event_type == "PLAY" for e in self.p.state.events))
        self.assertEqual("GRAVEYARD",self.p.state.entity(100).zone)
        reduced = effective_game_lines(rows)
        self.assertEqual(1, sum("BlockType=PLAY" in r for r in reduced))

    def test_pending_animated_undo_cannot_reintroduce_discarded_cards(self):
        self.feed(block("PLAY",100,"CARD_1"),line("BLOCK_END"),block("POWER",300,"TIME_000tb"))
        self.feed(block("PLAY",100,"CARD_1",True),line("FULL_ENTITY - Creating ID=200 CardID=CARD_2",True),
                  line("tag=CONTROLLER value=1",True),line("tag=ZONE value=HAND",True),line("BLOCK_END",True))
        self.assertNotIn(200,self.p.state.entities)
        self.feed(block("POWER",300,"TIME_000tb",True),line("BLOCK_END",True))
        self.assertNotIn(200,self.p.state.entities)

    def test_successive_rewinds_have_independent_intervals(self):
        rows=[]
        for eid in [300,301]:
            rows += [block("PLAY",100,"CARD_1"),line("TAG_CHANGE Entity=100 tag=ZONE value=GRAVEYARD"),
                     line("BLOCK_END"),block("POWER",eid,"TIME_000tb"),line("BLOCK_END")]
        self.feed(*rows)
        self.assertEqual("HAND",self.p.state.entity(100).zone)
        self.assertFalse(any(e.event_type=="PLAY" for e in self.p.state.events))

    def test_reset_closes_previous_game_journal(self):
        self.feed(block("PLAY",100,"CARD_1"))
        old=self.p._journal
        self.feed(line("CREATE_GAME"))
        self.assertTrue(old.file.closed)
        self.assertEqual(1,self.p._journal.count)
        self.assertEqual({},self.p._journal.base["_canonical_state_tokens"])
        self.assertEqual({},self.p._journal.base["state"].entities)
        self.p.reset_for_new_source()
        self.assertIsNone(self.p._journal)

    def test_large_game_spills_instead_of_growing_ram(self):
        journal=RewindJournal()
        try:
            for _ in range(1500): journal.append(line("X"*512))
            self.assertTrue(journal.file._rolled)
        finally: journal.close()

    def test_completed_statistics_drop_undone_play(self):
        from pathlib import Path
        import tempfile
        from ghostdata.powerlog import parse_completed_games
        rows=completed_match_log().splitlines(keepends=True)
        index=next(i for i,r in enumerate(rows) if 'tag=PLAYSTATE value=WON' in r or 'tag=PLAYSTATE value=LOST' in r)
        undone=[block('PLAY',999,'UNDONE_CARD'),line('BLOCK_END')]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'Power.log'
            path.write_text(''.join(rows),encoding='utf-8')
            baseline=parse_completed_games(path)[0]
            path.write_text(''.join(rows[:index]+undone+rows[index:]),encoding='utf-8')
            self.assertGreater(len(parse_completed_games(path)[0].cards_played),len(baseline.cards_played))
            undone += [block('POWER',1000,'TIME_000tb'),line('BLOCK_END')]
            path.write_text(''.join(rows[:index]+undone+rows[index:]),encoding='utf-8')
            actual=parse_completed_games(path)[0]
        self.assertEqual(baseline.cards_played,actual.cards_played)
        self.assertEqual(baseline.result,actual.result)


if __name__ == "__main__": unittest.main()
