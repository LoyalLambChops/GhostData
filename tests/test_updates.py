import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import zipfile
from ghostdata.updates import stage_release, validate_members, validate_package, version


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_version_order_is_numeric_and_prereleases_rejected(self):
        self.assertGreater(version("v1.10.0"), version("1.9.0"))
        for value in ("main", "v1.2.3-beta", "../1.2.3", "https://other"):
            with self.assertRaises(ValueError): version(value)

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
            target.write_text(json.dumps(dict(tag_name="v99.0.0",assets=[])))
        with patch("ghostdata.updates.fetch",side_effect=fetch):
            result=stage_release(self.root)
        self.assertEqual(result["status"],"SOURCE_CHECKOUT")
        self.assertEqual(list(self.root.iterdir()),[])

    def test_no_release_is_not_reported_as_up_to_date(self):
        with patch("ghostdata.updates.fetch",side_effect=HTTPError("url",404,"missing",{},None)):
            self.assertEqual(stage_release(self.root)["status"],"UNAVAILABLE")
