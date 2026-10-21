"""Incremental log reads with bounded continuity checks across replacements."""
from __future__ import annotations

import os
from pathlib import Path


class LogTail:
    ANCHOR_BYTES = 4096

    def __init__(self) -> None:
        self.path: Path | None = None
        self.identity: tuple[int, int] | None = None
        self.offset = 0
        self.anchor = b""

    def read(self, path: Path) -> tuple[bytes, bool]:
        """Return new bytes and whether the consumer must discard prior state.

        Check the opened handle so a rename between stat/open cannot mix files.
        Commit the cursor only after success; sharing errors remain retryable.
        """
        path = path.resolve()
        with path.open("rb") as handle:
            stat = os.fstat(handle.fileno())
            identity = (stat.st_dev, stat.st_ino)
            reset = path != self.path or identity != self.identity or stat.st_size < self.offset
            if not reset and self.anchor:
                handle.seek(self.offset - len(self.anchor))
                reset = handle.read(len(self.anchor)) != self.anchor
            handle.seek(0 if reset else self.offset)
            chunk = handle.read()
            new_offset = handle.tell()
        previous = b"" if reset else self.anchor
        self.path, self.identity, self.offset = path, identity, new_offset
        self.anchor = chunk[-self.ANCHOR_BYTES:] if len(chunk) >= self.ANCHOR_BYTES else (previous + chunk)[-self.ANCHOR_BYTES:]
        return chunk, reset
