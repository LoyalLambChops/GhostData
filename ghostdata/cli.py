from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .dashboard import load_dashboard
from .recorder import record_once, watch
from .tracker_bridge import run_tracker_stream
from .store import MatchStore


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ghostdata", description="Local Hearthstone match-history recorder and dashboard backend")
    p.add_argument("--version", action="store_true")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dashboard-json", action="store_true")
    mode.add_argument("--record-once", action="store_true")
    mode.add_argument("--record-continuously", action="store_true")
    mode.add_argument("--tracker-stream", action="store_true")
    mode.add_argument("--clear-history", action="store_true")
    mode.add_argument("--update-card-data", action="store_true")
    mode.add_argument("--update", action="store_true")
    mode.add_argument("--verify-release", type=Path)
    mode.add_argument("--setup-status", action="store_true")
    mode.add_argument("--save-game-directory", type=str)
    mode.add_argument("--enable-power-logging", action="store_true")
    p.add_argument("--acknowledge-setup", action="store_true")
    p.add_argument("--power-log", type=Path)
    p.add_argument("--data-dir", type=Path)
    p.add_argument("--interval", type=float, default=2.0)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    if args.setup_status or args.save_game_directory is not None or args.enable_power_logging:
        from .setup import setup_status, save_settings, enable_logging
        try:
            if args.setup_status: result = setup_status(root, args.data_dir)
            elif args.enable_power_logging: result = {"message": enable_logging()}
            else: result = save_settings(args.save_game_directory, args.data_dir, acknowledge=args.acknowledge_setup)
            print(json.dumps(result, ensure_ascii=False)); return 0
        except Exception as exc:
            print(str(exc), file=sys.stderr); return 1
    if args.verify_release:
        from .updates import validate_package
        validate_package(args.verify_release, __version__)
        return 0
    if args.update:
        from .updates import update
        print(json.dumps(update(root, args.data_dir), ensure_ascii=False))
        return 0
    if args.version:
        print(__version__)
        return 0
    if args.update_card_data:
        from .local_card_data import import_card_data
        try:
            print(json.dumps(import_card_data(root, data_dir=args.data_dir)))
            return 0
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.dashboard_json:
        print(json.dumps(load_dashboard(data_dir=args.data_dir), ensure_ascii=False))
        return 0
    if args.record_once or args.record_continuously or args.tracker_stream:
        from .setup import configured_log_path
        if args.power_log is None: args.power_log = configured_log_path(args.data_dir)
    if args.record_once:
        parsed, added = record_once(root, power_log=args.power_log, data_dir=args.data_dir)
        print(json.dumps({"parsed_completed_games": parsed, "new_matches": added}))
        return 0
    if args.record_continuously:
        watch(root, power_log=args.power_log, data_dir=args.data_dir, interval=args.interval)
        return 0
    if args.tracker_stream:
        run_tracker_stream(root, power_log=args.power_log, data_dir=args.data_dir, interval=args.interval)
        return 0
    if args.clear_history:
        MatchStore(args.data_dir).clear()
        print(json.dumps({"status": "cleared"}))
        return 0
    parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
