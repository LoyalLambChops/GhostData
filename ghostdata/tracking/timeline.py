"""Active-game transaction journal for Hearthstone's Rewind mechanic.

Canonical power and animated TaskList messages run on separate timelines. Undo
their matching PLAY-to-Rewind intervals independently, preserving later actions
already received in the faster stream. This is ephemeral parser recovery, not a
replay recorder: one game, a 512 KiB RAM limit, and a temporary spill file.
"""
import re
import tempfile

_BLOCK = re.compile(r"BLOCK_START BlockType=(\w+) Entity=(.*?) EffectCardId=")
_INLINE_ID = re.compile(r"\bid=(\d+)")
_CARD = re.compile(r"\bcardId=(\w+)")
_IDENTITY = re.compile(r"(?:FULL_ENTITY.*?\bID=|SHOW_ENTITY.*?(?:\bid=|Entity=))(\d+).*?CardID=(\w+)")


def stream_of(line):
    if "GameState." in line:
        return "canonical"
    if "PowerTaskList.DebugPrintPower()" in line:
        return "task"
    return ""


class RewindJournal:
    def __init__(self, base=None):
        self.file = tempfile.SpooledTemporaryFile(max_size=512 * 1024, mode="w+t", encoding="utf-8", newline="\n")
        self.base = base
        self.count = 0
        self.identities = {}
        self.blocks = []
        self.rewind_ids = set()
        self.intervals = ()

    def close(self):
        self.file.close()

    def __del__(self):
        self.close()

    def append(self, line):
        index = self.count
        self.count += 1
        self.file.seek(0, 2)
        self.file.write(line.rstrip("\r\n") + "\n")
        identity = _IDENTITY.search(line)
        if identity:
            self.identities[int(identity[1])] = identity[2]
        match = _BLOCK.search(line)
        if match:
            kind, raw = match.groups()
            entity = _INLINE_ID.search(raw)
            eid = int(entity[1]) if entity else int(raw) if raw.isdigit() else 0
            card = _CARD.search(raw)
            cid = card[1] if card else self.identities.get(eid, "")
            if cid:
                self.identities[eid] = cid
            self.blocks.append((index, stream_of(line), kind, eid))
            if cid == "TIME_000tb" and kind == "POWER":
                self.rewind_ids.add(eid)
        old = self.intervals
        if self.rewind_ids and (match or identity):
            self.intervals = self._intervals()
        return index, old != self.intervals

    def _intervals(self):
        ranges = []
        for eid in sorted(self.rewind_ids):
            markers = {s: i for i, s, kind, entity in self.blocks if entity == eid and kind == "POWER"}
            starts = {}
            for stream, end in markers.items():
                plays = [(i, entity) for i, s, kind, entity in self.blocks
                         if s == stream and kind == "PLAY" and i < end
                         and not any(rs == s and lo <= i <= hi for rs, lo, hi in ranges)]
                if plays:
                    starts[stream] = plays[-1]
                    ranges.append((stream, plays[-1][0], end))
            # Until the animation catches up, discard its version of the undone
            # action as it arrives. Entity ID binds the two PLAY records.
            if "canonical" in starts and "task" not in markers:
                begin, actor = starts["canonical"]
                plays = [i for i, s, kind, entity in self.blocks
                         if s == "task" and kind == "PLAY" and entity == actor and i >= begin]
                if plays:
                    ranges.append(("task", plays[0], float("inf")))
        return tuple(sorted(ranges))

    def ignored(self, index, line):
        stream = stream_of(line)
        return any(s == stream and lo <= index <= hi for s, lo, hi in self.intervals)

    def lines(self):
        self.file.seek(0)
        for index, line in enumerate(self.file):
            yield index, line


def effective_game_lines(lines):
    """Same Rewind semantics for completed-match statistics."""
    journal = RewindJournal()
    try:
        for line in lines:
            journal.append(line)
        return [line for index, line in journal.lines() if not journal.ignored(index, line)]
    finally:
        journal.close()
