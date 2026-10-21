import os
from pathlib import Path
import tempfile
import unittest

from ghostdata.log_tail import LogTail


class LogTailTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "Power.log"
        self.tail = LogTail()

    def test_append_and_idle_do_not_reset_or_repeat(self):
        self.path.write_bytes(b"first\npartial")
        self.assertEqual(self.tail.read(self.path), (b"first\npartial", True))
        self.assertEqual(self.tail.read(self.path), (b"", False))
        with self.path.open("ab") as handle:
            handle.write(b" end\n")
        self.assertEqual(self.tail.read(self.path), (b" end\n", False))

    def test_in_place_rewrite_equal_and_larger_reset(self):
        for replacement in (b"new!\n", b"new!\nsecond line\n"):
            with self.subTest(replacement=replacement):
                self.path.write_bytes(b"old!\n")
                self.tail = LogTail()
                self.tail.read(self.path)
                self.path.write_bytes(replacement)
                self.assertEqual(self.tail.read(self.path), (replacement, True))

    def test_atomic_replacement_even_with_identical_content_resets(self):
        self.path.write_bytes(b"same\n")
        self.tail.read(self.path)
        replacement = self.path.with_suffix(".new")
        replacement.write_bytes(b"same\n")
        os.replace(replacement, self.path)
        self.assertEqual(self.tail.read(self.path), (b"same\n", True))

    def test_truncate_to_empty_then_append(self):
        self.path.write_bytes(b"old\n")
        self.tail.read(self.path)
        self.path.write_bytes(b"")
        self.assertEqual(self.tail.read(self.path), (b"", True))
        self.path.write_bytes(b"new\n")
        self.assertEqual(self.tail.read(self.path), (b"new\n", False))

    def test_failed_read_preserves_cursor_for_retry(self):
        self.path.write_bytes(b"old\n")
        self.tail.read(self.path)
        with self.assertRaises(OSError):
            self.tail.read(self.path.with_name("missing.log"))
        self.assertEqual(self.tail.read(self.path), (b"", False))

    def test_source_change_discards_previous_anchor(self):
        self.path.write_bytes(b"old\n")
        self.tail.read(self.path)
        other = self.path.with_name("other.log")
        other.write_bytes(b"new\n")
        self.assertEqual(self.tail.read(other), (b"new\n", True))

    def test_continuity_memory_is_bounded(self):
        self.path.write_bytes(b"a" * 10000)
        self.tail.read(self.path)
        self.assertEqual(len(self.tail.anchor), LogTail.ANCHOR_BYTES)
        with self.path.open("ab") as handle:
            handle.write(b"b")
        self.assertEqual(self.tail.read(self.path), (b"b", False))
        self.assertEqual(self.tail.anchor[-1:], b"b")


if __name__ == "__main__":
    unittest.main()
