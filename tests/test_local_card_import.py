import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from ghostdata.local_card_data import import_card_data, validate_import
from ghostdata.tracking.card_db import CardDatabase


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.exe = self.root / "reader.exe"; self.exe.touch()
        self.payload = dict(status="READY", source="BLIZZARD_LOCAL_CLIENT", schema_version=1, build=255130,
            client_version="37.0.0.255130", log_build=254477, assembly_sha256="a"*64,
            valid_until=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
            cards=[dict(id=f"CARD_{i}", dbfId=i, name="Étoile", mechanics=[], standard=True) for i in range(1,1001)])

    def import_payload(self, payload):
        result = subprocess.CompletedProcess([], 0, json.dumps(payload, ensure_ascii=False).encode(), b"")
        with patch("ghostdata.local_card_data.sensor_executable", return_value=self.exe), patch("ghostdata.local_card_data.subprocess.run", return_value=result), patch("urllib.request.urlopen", side_effect=AssertionError("Network forbidden")):
            return import_card_data(self.root, data_dir=self.root)

    def test_unicode_snapshot_is_atomic_local_and_loadable(self):
        self.import_payload(self.payload)
        db = CardDatabase(self.root / "local_cards")
        self.assertTrue(db.load_for_build(255130)); self.assertTrue(db.local_source)
        self.assertTrue(db.legality_current); self.assertEqual(db.get("CARD_1").name, "Étoile")
        self.assertTrue(db.matches_log_build(254477)); self.assertFalse(db.matches_log_build(254478))
        self.assertEqual(len(list(db.cache_dir.iterdir())), 1)

    def test_invalid_snapshot_preserves_previous_good_file(self):
        self.import_payload(self.payload)
        target = self.root / "local_cards" / "cards_255130_local.json"; before = target.read_bytes()
        self.payload["cards"].append(self.payload["cards"][0])
        with self.assertRaises(ValueError): self.import_payload(self.payload)
        self.assertEqual(target.read_bytes(), before)

    def test_untrusted_identity_and_expired_legality_are_rejected(self):
        for changes in ({"source":"REMOTE"}, {"build":123}, {"assembly_sha256":""},
                {"valid_until":"2000-01-01T00:00:00+00:00"}, {"cards":[]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_import(self.payload | changes)
