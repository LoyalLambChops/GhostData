import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import zipfile
from ghostdata.updates import stage_release, validate_members, validate_package, version, installation_context, select_release


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_version_order_is_numeric_and_prereleases_rejected(self):
        self.assertGreater(version("v1.10.0"), version("1.9.0"))
        for value in ("main", "v1.2.3-beta", "../1.2.3", "https://other"):
            with self.assertRaises(ValueError): version(value)

    def test_channels_choose_highest_numeric_published_version(self):
        releases = [dict(tag_name="v1.9.0"), dict(tag_name="v1.10.0",prerelease=True),
                    dict(tag_name="v99.0.0",draft=True), dict(tag_name="main"),
                    dict(tag_name="v1.11.0-beta",prerelease=True)]
        self.assertEqual(select_release(releases,"beta")["tag_name"],"v1.10.0")
        self.assertEqual(select_release(releases,"stable")["tag_name"],"v1.9.0")
        self.assertIsNone(select_release([releases[1]],"stable"))
        releases.append(dict(tag_name="v2.0.0"))
        self.assertEqual(select_release(releases,"beta")["tag_name"],"v2.0.0")

    def test_empty_listing_is_unavailable(self):
        def fetch(url,target,limit): target.write_text("[]")
        with patch("ghostdata.updates.fetch",side_effect=fetch):
            self.assertEqual(stage_release(self.root)["status"],"UNAVAILABLE")

    def test_invalid_release_listing_is_rejected(self):
        with self.assertRaises(ValueError): select_release({},"beta")
        with self.assertRaises(ValueError): select_release([],"typo")

    def test_archive_rejects_traversal_devices_ads_and_duplicates(self):
        for names in (("../outside",), ("/absolute",), ("C:/outside",), ("a\\b",), ("NUL.txt",), ("file:stream",), ("a", "A")):
            with self.subTest(names=names):
                buffer=io.BytesIO()
                with zipfile.ZipFile(buffer,"w") as archive:
                    for name in names: archive.writestr(name,b"x")
                if names == ("a\\b",):
                    # Windows' writer normalizes separators; model an externally produced archive.
                    buffer=io.BytesIO(buffer.getvalue().replace(b"a/b",b"a\\b"))
                buffer.seek(0)
                with zipfile.ZipFile(buffer) as archive, self.assertRaises(ValueError): validate_members(archive)

    def test_package_hashes_and_inventory_are_required(self):
        files={}
        for name in ("GhostData.App.exe", "ghostdata.py", "python/python.exe", "sensor/bin/GhostData.Sensor.exe"):
            target=self.root/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(b"test")
            files[name]=hashlib.sha256(b"test").hexdigest()
        (self.root/"ghostdata-release.json").write_text(json.dumps(dict(product="GhostData",version="1.2.0",files=files)))
        validate_package(self.root,"v1.2.0")
        (self.root/"ghostdata.py").write_bytes(b"tampered")
        with self.assertRaises(ValueError): validate_package(self.root,"1.2.0")

    def test_source_checkout_can_never_be_replaced(self):
        def fetch(url, target, limit):
            target.write_text(json.dumps([dict(tag_name="v99.0.0",assets=[],prerelease=True)]))
        with patch("ghostdata.updates.fetch",side_effect=fetch):
            result=stage_release(self.root)
        self.assertEqual(result["status"],"SOURCE_CHECKOUT")
        self.assertEqual(list(self.root.iterdir()),[])

    def test_no_release_is_not_reported_as_up_to_date(self):
        with patch("ghostdata.updates.fetch",side_effect=HTTPError("url",404,"missing",{},None)):
            self.assertEqual(stage_release(self.root)["status"],"UNAVAILABLE")


class InstalledLayoutTests(unittest.TestCase):
    def test_installer_metadata_stays_outside_verified_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); root = base / "app"; root.mkdir()
            files = {}
            for name in ("GhostData.App.exe", "ghostdata.py", "python/python.exe", "sensor/bin/GhostData.Sensor.exe"):
                target = root / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(b"test")
                files[name] = hashlib.sha256(b"test").hexdigest()
            (root / "ghostdata-release.json").write_text(json.dumps(dict(product="GhostData", version="1.3.0", files=files)))
            (base / "maintenance").mkdir(); (base / "maintenance/unins000.exe").write_bytes(b"uninstaller")
            marker = base / "ghostdata-install.json"
            marker.write_text(json.dumps(dict(product="GhostData", schema_version=1, payload="app", app_id="{1C35DA89-E657-4DD0-AEAA-EE63E6745D23}")))
            self.assertEqual(installation_context(root)["root"], str(base.resolve()))
            validate_package(root, "1.3.0")
            (root / "unknown-user-file.txt").write_text("preserve")
            with self.assertRaises(ValueError): validate_package(root, "1.3.0")
            marker.write_text(json.dumps(dict(product="GhostData", schema_version=1, payload="../outside", app_id="bad")))
            with self.assertRaises(ValueError): installation_context(root)

    def test_portable_layout_does_not_inherit_another_installer(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); root=base / "portable"; root.mkdir()
            (base / "ghostdata-install.json").write_text("invalid")
            self.assertIsNone(installation_context(root))
