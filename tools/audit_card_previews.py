"""Offline change audit of the installed Standard preview contracts.

Usage: python tools/audit_card_previews.py path/to/cards_BUILD_local.json
The checked-in baseline contains hashes/IDs, never card artwork or card text.
New/changed definitions require review even if they use an existing handler.
"""
import argparse
import hashlib
import json
from pathlib import Path

BASELINE = Path(__file__).resolve().parents[1] / "docs" / "preview-definition-baseline.json"
PLAYABLE = {"MINION", "SPELL", "WEAPON", "LOCATION"}


def definitions(payload):
    cards = payload["cards"]
    sets = {c["set"] for c in cards if c.get("standard") and c.get("collectible") and c.get("type") in PLAYABLE}
    prefixes = {c["id"].split("_")[0] for c in cards if c.get("set") in sets and c.get("collectible") and c.get("type") in PLAYABLE}
    # Tokens and enchantments share their source expansion prefixes. Event and
    # special-mode records can coexist in the client; eligibility is reviewed,
    # not inferred solely from the client's set-level Standard flag.
    return {c["id"]: c for c in cards if c.get("set") in sets and c["id"].split("_")[0] in prefixes
            and c.get("type") in PLAYABLE | {"ENCHANTMENT"}}


def fingerprint(card):
    fields = {k:card.get(k) for k in ("text", "cost", "type", "set", "standard", "collectible", "mechanics", "races", "textBuilder")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def audit(payload, baseline):
    current = {cid:fingerprint(card) for cid, card in definitions(payload).items()}
    old = baseline["definitions"]
    return {"build":payload["build"], "reviewed_build":baseline["build"], "checked":len(current),
            "added":sorted(current.keys()-old.keys()), "removed":sorted(old.keys()-current.keys()),
            "changed":sorted(cid for cid in current.keys() & old.keys() if current[cid] != old[cid])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot",type=Path)
    args=parser.parse_args()
    result=audit(json.loads(args.snapshot.read_text(encoding="utf-8-sig")),json.loads(BASELINE.read_text(encoding="utf-8")))
    print(json.dumps(result,indent=2))
    return 1 if any(result[k] for k in ("added","removed","changed")) else 0

if __name__ == "__main__": raise SystemExit(main())
