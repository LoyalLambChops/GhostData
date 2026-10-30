"""User-requested GhostData releases. No network activity during normal tracking."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
import zipfile
from . import __version__, __release_channel__
from .local_card_data import import_card_data

REPOSITORY = "LoyalLambChops/GhostData"
API = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=100"
ARCHIVE = "GhostData-win-x64.zip"
MAX_ARCHIVE = 180 * 1024 * 1024
MAX_EXPANDED = 600 * 1024 * 1024


def version(value):
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", str(value)):
        raise ValueError("Unrecognized release version.")
    return tuple(map(int, value.lstrip("v").split(".")))


def select_release(releases, channel):
    """Use numeric tags for upgrade ordering, GitHub's flag for beta status."""
    if channel not in {"beta", "stable"} or not isinstance(releases, list):
        raise ValueError("Unrecognized release channel or release listing.")
    eligible = []
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        if release.get("prerelease") and channel != "beta":
            continue
        try:
            number = version(release.get("tag_name", ""))
        except ValueError:
            continue
        eligible.append((number, release))
    return max(eligible, key=lambda entry: entry[0])[1] if eligible else None


class ReleaseRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or parsed.hostname not in {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}:
            raise ValueError("Unexpected release download redirect.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, target, limit):
    opener = build_opener(ReleaseRedirects())
    request = Request(url, headers={"User-Agent":"GhostData-Updater", "Accept":"application/vnd.github+json"})
    digest = hashlib.sha256(); total = 0
    with opener.open(request, timeout=30) as response, target.open("wb") as output:
        while chunk := response.read(128 * 1024):
            total += len(chunk)
            if total > limit: raise ValueError("Release download exceeds its size limit.")
            output.write(chunk); digest.update(chunk)
    return digest.hexdigest()


def validate_members(archive):
    members = archive.infolist(); seen = set(); total = 0
    if len(members) > 10000: raise ValueError("Release contains too many files.")
    for member in members:
        path = PurePosixPath(member.filename)
        parts = path.parts
        if (member.orig_filename != member.filename or not parts or path.is_absolute() or "\\" in member.filename or ":" in member.filename
                or any(p in {".", ".."} or p.endswith((".", " ")) or p.split(".")[0].upper() in
                    {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))} for p in parts)
                or (member.external_attr >> 16) & 0o170000 == 0o120000):
            raise ValueError("Unsafe release archive path.")
        key = str(path).casefold()
        if key in seen: raise ValueError("Duplicate release path.")
        seen.add(key); total += member.file_size
        if total > MAX_EXPANDED: raise ValueError("Release expands beyond its size limit.")
    return members


def validate_package(root, expected_version):
    manifest = json.loads((root / "ghostdata-release.json").read_text(encoding="utf-8-sig"))
    if manifest.get("product") != "GhostData" or version(manifest.get("version")) != version(expected_version):
        raise ValueError("The downloaded package has the wrong product or version.")
    files = manifest.get("files")
    if not isinstance(files, dict) or not {"GhostData.App.exe", "ghostdata.py", "python/python.exe", "sensor/bin/GhostData.Sensor.exe"} <= files.keys():
        raise ValueError("The downloaded package is incomplete.")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} - {"ghostdata-release.json"}
    if actual != set(files): raise ValueError("Release file inventory does not match.")
    for name, digest in files.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Release file verification failed.")
    return manifest


def installation_context(root: Path):
    """Installer metadata lives outside the hash-verified application payload."""
    root = Path(root).resolve()
    marker = root.parent / "ghostdata-install.json"
    if root.name.casefold() != "app" or not marker.is_file():
        return None
    context = json.loads(marker.read_text(encoding="utf-8-sig"))
    if (context.get("product") != "GhostData" or context.get("schema_version") != 1
            or context.get("payload") != "app"
            or not re.fullmatch(r"\{[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}", str(context.get("app_id", "")))):
        raise ValueError("Installation identity is invalid; repair with the GhostData installer.")
    return {"root": str(root.parent), "app_id": context["app_id"]}


def stage_release(root: Path):
    """A source checkout can check availability but can never replace itself."""
    root = root.resolve()
    installation_context(root)
    with tempfile.TemporaryDirectory(prefix="ghostdata-release-") as temp:
        temp = Path(temp); metadata = temp / "release.json"
        try:
            fetch(API, metadata, 2 * 1024 * 1024)
        except HTTPError as exc:
            if exc.code == 404: return {"status":"UNAVAILABLE", "message":"No public GhostData release is available."}
            raise
        release = select_release(json.loads(metadata.read_text(encoding="utf-8")), __release_channel__)
        if release is None:
            return {"status":"UNAVAILABLE", "message":"No compatible public GhostData release is available."}
        tag = release.get("tag_name", "")
        if version(tag) <= version(__version__): return {"status":"CURRENT", "message":f"GhostData {__version__} is installed and up to date. No files needed replacing."}
        marker = root / "ghostdata-release.json"
        if not marker.is_file() or (root / ".git").exists():
            return {"status":"SOURCE_CHECKOUT", "message":f"GhostData {tag} is available. Install its portable package to enable in-app installation."}
        installed = json.loads(marker.read_text(encoding="utf-8-sig"))
        if installed.get("product") != "GhostData" or version(installed.get("version")) != version(__version__):
            raise ValueError("Installed release identity is invalid.")
        # Refuse to remove an installation containing user files or modifications.
        validate_package(root, __version__)
        asset = next((a for a in release.get("assets", []) if a.get("name") == ARCHIVE), None)
        expected_url = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{ARCHIVE}"
        if not asset or asset.get("browser_download_url") != expected_url:
            raise ValueError("The release does not contain the expected Windows package.")
        digest = str(asset.get("digest", ""))
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest): raise ValueError("The release has no SHA-256 verification digest.")
        archive = temp / ARCHIVE
        if fetch(expected_url, archive, MAX_ARCHIVE) != digest[7:]: raise ValueError("Release download failed SHA-256 verification.")
        staged = Path(tempfile.mkdtemp(prefix=".ghostdata-update-", dir=root.parent))
        try:
            with zipfile.ZipFile(archive) as zip_file:
                members = validate_members(zip_file)
                zip_file.extractall(staged, members)
            validate_package(staged, tag)
            return {"status":"STAGED", "version":tag, "staged_path":str(staged), "message":f"GhostData {tag} verified. It will install when you close GhostData."}
        except Exception:
            shutil.rmtree(staged)
            raise


def update(root: Path, data_dir=None):
    result = {}
    try:
        local = import_card_data(root, data_dir=data_dir)
        result["cards"] = f"Local game build {local['build']}: {local['cards']:,} card definitions refreshed."
    except Exception as exc:
        result["cards"] = "Card refresh unavailable: " + str(exc)
    try:
        result["release"] = stage_release(root)
    except Exception as exc:
        result["release"] = {"status":"ERROR", "message":"Release check failed: " + str(exc)}
    return result
