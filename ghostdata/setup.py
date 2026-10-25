"""Explicit local setup. No network requests, game injection or hidden config edits."""
from __future__ import annotations
import configparser
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from .paths import data_paths


def settings_path(data_dir=None):
    return data_paths(data_dir).root / "settings.json"


def read_settings(data_dir=None):
    path = settings_path(data_dir)
    if not path.exists(): return {}
    try:
        result = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(result, dict) or result.get("schema_version") != 1:
            raise ValueError("unsupported settings format")
        if not isinstance(result.get("game_directory", ""), str):
            raise ValueError("invalid game directory")
        return result
    except (OSError, ValueError) as exc:
        return {"settings_error": f"Settings could not be read: {exc}. Save a valid game folder in Setup to repair them."}


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temp = Path(stream.name); stream.write(content); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp is not None: temp.unlink(missing_ok=True)


def save_settings(game_directory, data_dir=None, *, acknowledge=False):
    value = str(game_directory).strip()
    if value:
        folder = Path(value).expanduser().resolve()
        if not (folder / "Hearthstone.exe").is_file():
            raise ValueError("Choose the Hearthstone installation folder containing Hearthstone.exe, not its Logs folder.")
        value = str(folder)
    path = settings_path(data_dir); previous = read_settings(data_dir)
    if "settings_error" in previous and path.exists():
        backup = path.with_name("settings-invalid-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".bak")
        backup.write_bytes(path.read_bytes())
    result = {"schema_version": 1, "game_directory": value,
              "setup_seen": acknowledge or previous.get("setup_seen", False)}
    atomic_write(path, json.dumps(result, indent=2).encode("utf-8"))
    return result


def configured_log_path(data_dir=None):
    settings = read_settings(data_dir)
    if "settings_error" in settings: raise ValueError(settings["settings_error"])
    directory = settings.get("game_directory", "")
    return Path(directory) / "Logs" if directory else None


def logging_config_path():
    local = os.environ.get("LOCALAPPDATA")
    if not local: raise ValueError("Windows LOCALAPPDATA is unavailable.")
    return Path(local) / "Blizzard" / "Hearthstone" / "log.config"


def parse_logging(text):
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.read_string(text)
    sections = [s for s in parser.sections() if s.casefold() == "power"]
    if len(sections) > 1: raise ValueError("More than one Power section exists; review log.config manually.")
    return parser, sections[0] if sections else None


def logging_enabled(path):
    if not path.exists(): return False
    parser, section = parse_logging(path.read_text(encoding="utf-8-sig"))
    return bool(section and parser.getboolean(section, "FilePrinting", fallback=False)
                and parser.getint(section, "LogLevel", fallback=0) >= 1)


def enable_logging(path=None):
    """Only call following the user's explicit Enable logging action."""
    path = Path(path) if path is not None else logging_config_path()
    original = path.read_bytes() if path.exists() else b""
    text = original.decode("utf-8-sig")
    _, section = parse_logging(text)  # refuse malformed config; do not clobber it
    if logging_enabled(path): return "Power logging is already enabled. Restart Hearthstone if you recently changed it."
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    headers = [(i, re.match(r"^\s*\[([^]]+)\]", line)) for i,line in enumerate(lines)]
    headers = [(i,m.group(1)) for i,m in headers if m]
    if section:
        start = next(i for i,name in headers if name == section)
        end = next((i for i,_ in headers if i > start), len(lines))
        if not lines[start].endswith(("\n","\r")): lines[start] += newline
        block = lines[start+1:end]
        for key, value in (("LogLevel","1"),("FilePrinting","true")):
            found = False
            for i,line in enumerate(block):
                if re.match(r"^\s*" + key + r"\s*=",line,re.I):
                    block[i] = f"{key}={value}{newline}"; found = True
            if not found:
                if block and not block[-1].endswith(("\n","\r")): block[-1] += newline
                block.append(f"{key}={value}{newline}")
        lines[start+1:end] = block
        updated = "".join(lines)
    else:
        updated = text + (newline if text and not text.endswith(("\n","\r")) else "")
        updated += "[Power]"+newline+"LogLevel=1"+newline+"FilePrinting=true"+newline+"ConsolePrinting=false"+newline+"ScreenPrinting=false"+newline
    # Preserve a BOM if present and keep a byte-for-byte recovery copy.
    backup = None
    if original:
        backup = path.with_name("log.config.ghostdata-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".bak")
        backup.write_bytes(original)
    atomic_write(path, updated.encode("utf-8-sig" if original.startswith(b"\xef\xbb\xbf") else "utf-8"))
    return "Power logging enabled. Fully close and restart Hearthstone, then play a game." + (f" Original saved at {backup}" if backup else "")


def setup_status(project_root, data_dir=None):
    from .deck_sensor import sensor_executable
    from .powerlog import discover_power_logs
    from .tracking.card_db import CardDatabase
    settings = read_settings(data_dir); checks = []
    def add(name, status, detail): checks.append({"name":name,"status":status,"detail":detail})
    exe = sensor_executable(Path(project_root)); health = {}
    if not exe.is_file(): add("Sensor", "ACTION NEEDED", "Local reader missing. Repair GhostData using the installer.")
    else:
        try:
            result = subprocess.run([str(exe),"health"],capture_output=True,timeout=5,
                                    creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            health = json.loads(result.stdout.decode("utf-8-sig"))
            if result.returncode or health.get("status") != "READY": raise ValueError(health.get("reason","reader failed"))
            add("Sensor", "AVAILABLE", "Local reader launches. Current-deck certainty is checked separately during play.")
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            add("Sensor", "UNAVAILABLE", f"Reader could not start: {exc}. Repair the app; if this persists, contact support.")
    candidates = [Path(settings["game_directory"])] if settings.get("game_directory") else []
    if not candidates:
        if health.get("hearthstone_path"): candidates.append(Path(health["hearthstone_path"]).parent)
        candidates += [Path(os.environ.get(key,default))/"Hearthstone" for key,default in
                       [("PROGRAMFILES(X86)",r"C:\Program Files (x86)"),("PROGRAMFILES",r"C:\Program Files")]]
    game = next((p for p in candidates if (p/"Hearthstone.exe").is_file()),None)
    add("Game folder", "FOUND" if game else "ACTION NEEDED", str(game) if game else "Browse to the folder containing Hearthstone.exe.")
    if "settings_error" in settings: add("Settings","ACTION NEEDED",settings["settings_error"])
    config = logging_config_path()
    try: enabled = logging_enabled(config)
    except (OSError, ValueError, configparser.Error) as exc:
        enabled = False; add("Logging configuration","ACTION NEEDED",f"Cannot safely read {config}: {exc}. Review the file before enabling logging.")
    else: add("Power logging", "CONFIGURED" if enabled else "ACTION NEEDED", f"{config}" if enabled else "Click ENABLE POWER LOGGING, then restart Hearthstone.")
    logs = discover_power_logs(game/"Logs") if game else []
    add("Game logs", "FOUND" if logs else "WAITING", str(logs[-1]) if logs else "No Power.log found. After enabling logging, restart Hearthstone and enter a game.")
    running = health.get("hearthstone_running") is True
    add("Hearthstone", "RUNNING" if running else "WAITING", "Reach the main menu before refreshing card data." if running else "Start Hearthstone and reach its main menu. History remains available while the game is closed.")
    db = CardDatabase(data_paths(data_dir).root/"local_cards")
    try: cached = db.load_latest_cache()
    except (OSError, ValueError, TypeError): cached = False
    build = str(health.get("hearthstone_build","")).split(".")[-1]
    current = cached and db.local_source and db.legality_current and build.isdigit() and db.build_number == int(build)
    if current: add("Card definitions","CURRENT",f"Local client build {db.build_number}; {len(db.cards):,} cards. This does not certify every game mechanic.")
    else: add("Card definitions","ACTION NEEDED" if running else "WAITING", "Click REFRESH LOCAL CARDS at the main menu. Missing, expired or mismatched definitions cannot provide exact card accounting. If import fails after a patch, use UPDATE for a tested GhostData release or contact support.")
    add("Your data","LOCAL",str(data_paths(data_dir).root)+". History stays here when the app is updated or uninstalled.")
    return {"game_directory":str(game or settings.get("game_directory", "")),"setup_seen":settings.get("setup_seen",False),
            "checks":checks,"ready":bool(game and enabled and logs and running and current and "settings_error" not in settings)}
