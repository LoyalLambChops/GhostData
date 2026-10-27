"""Import public card definitions from the installed Blizzard client only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from datetime import datetime, timezone

from .deck_sensor import sensor_executable
from .paths import data_paths
from .tracking.card_db import CardDatabase


def validate_import(payload: dict) -> int:
    if not isinstance(payload, dict) or payload.get("status") != "READY":
        raise ValueError(str(payload.get("reason", "Local card data unavailable.")) if isinstance(payload, dict) else "Invalid sensor response.")
    if payload.get("schema_version") != 1 or payload.get("source") != "BLIZZARD_LOCAL_CLIENT":
        raise ValueError("Unrecognized local card-data source.")
    build = payload.get("build")
    if type(build) is not int or build <= 0 or not str(payload.get("client_version", "")).endswith(f".{build}"):
        raise ValueError("Local card build identity does not match.")
    if type(payload.get("log_build")) is not int or payload["log_build"] <= 0:
        raise ValueError("Missing verified client log build.")
    if not re.fullmatch(r"[0-9a-f]{64}", str(payload.get("assembly_sha256", ""))):
        raise ValueError("Missing local assembly fingerprint.")
    try:
        expiry = datetime.fromisoformat(payload["valid_until"].replace("Z", "+00:00"))
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise ValueError("Local rotation dates have expired.")
    except (KeyError, TypeError) as exc:
        raise ValueError("Missing local rotation dates.") from exc
    rows = payload.get("cards")
    if not isinstance(rows, list) or not 1000 <= len(rows) <= 100000:
        raise ValueError("Local card definitions are incomplete.")
    ids, dbfs = set(), set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid local card row.")
        cid, dbf = row.get("id"), row.get("dbfId")
        if not isinstance(cid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", cid) or type(dbf) is not int or dbf <= 0:
            raise ValueError("Invalid local card identity.")
        if cid in ids or dbf in dbfs:
            raise ValueError("Duplicate local card identity.")
        if not isinstance(row.get("name"), str) or not isinstance(row.get("mechanics"), list) or type(row.get("standard")) is not bool:
            raise ValueError("Incomplete local card properties.")
        if "races" in row and (not isinstance(row["races"], list) or not all(isinstance(v,str) for v in row["races"])):
            raise ValueError("Invalid local tribe metadata.")
        if "textBuilder" in row and not isinstance(row["textBuilder"], str):
            raise ValueError("Invalid local text reference metadata.")
        ids.add(cid)
        dbfs.add(dbf)
    return build


def import_card_data(project_root: Path, *, data_dir: Path | None = None, timeout: float = 60) -> dict:
    """Validate the whole snapshot before atomically replacing any usable data."""
    exe = sensor_executable(project_root)
    if not exe.is_file():
        raise ValueError("GhostData's local card reader is missing.")
    result = subprocess.run([str(exe), "card-data"], capture_output=True, timeout=timeout,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if len(result.stdout) > 32 * 1024 * 1024:
        raise ValueError("Local card snapshot exceeds the size limit.")
    try:
        payload = json.loads(result.stdout.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("The local reader returned invalid card data.") from exc
    build = validate_import(payload)
    if result.returncode:
        raise ValueError("The local reader did not finish successfully.")
    folder = data_paths(data_dir).root / "local_cards"
    folder.mkdir(parents=True, exist_ok=True)
    db = CardDatabase(folder)
    # Private staging name prevents a running reader from observing half a file.
    staging = None
    try:
        with tempfile.NamedTemporaryFile(dir=folder, suffix=".tmp", delete=False) as stream:
            staging = Path(stream.name)
            stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, db._cache_path(build))
    finally:
        if staging is not None:
            staging.unlink(missing_ok=True)
    return {"status": "READY", "build": build, "cards": len(payload["cards"]), "source": payload["source"]}
