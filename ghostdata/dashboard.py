from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import MatchRecord
from .store import MatchStore
from .paths import ensure_history_epoch


def _pct(wins: int, games: int) -> float:
    return round((wins / games * 100.0), 1) if games else 0.0


def _duration(seconds: int) -> str:
    if not seconds:
        return "—"
    minutes, sec = divmod(max(0, int(seconds)), 60)
    return f"{minutes}m {sec:02d}s"


def _deck_label(match: MatchRecord) -> str:
    return match.deck_name or match.archetype_name or match.player_class.title() or "Unknown deck"


def _summary(rows: Iterable[MatchRecord]) -> dict[str, Any]:
    items = list(rows)
    wins = sum(1 for m in items if m.result == "WIN")
    losses = sum(1 for m in items if m.result == "LOSS")
    durations = [m.duration_seconds for m in items if m.duration_seconds > 0]
    average_seconds = round(sum(durations) / len(durations)) if durations else 0
    return {
        "games": len(items),
        "wins": wins,
        "losses": losses,
        "record": f"{wins}-{losses}",
        "win_rate": _pct(wins, wins + losses),
        "average_duration_seconds": average_seconds,
        "average_duration": _duration(average_seconds),
    }


def _breakdowns(rows: list[MatchRecord], key_fn, label_fn=None) -> list[dict[str, Any]]:
    groups: dict[Any, list[MatchRecord]] = defaultdict(list)
    for row in rows:
        groups[key_fn(row)].append(row)
    output: list[dict[str, Any]] = []
    for key, group_rows in groups.items():
        output.append({
            "key": str(key),
            "label": label_fn(key, group_rows) if label_fn else str(key),
            **_summary(group_rows),
        })
    output.sort(key=lambda r: (-r["games"], r["label"]))
    return output


def _deck_versions(rows: list[MatchRecord]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[MatchRecord]] = defaultdict(list)
    for row in rows:
        groups[(row.deck_name, row.archetype_name, row.deck_version, row.player_class)].append(row)
    output: list[dict[str, Any]] = []
    for (deck_name, archetype, version, player_class), group_rows in groups.items():
        display_name = deck_name or player_class.title() or "Unknown deck"
        detail_parts: list[str] = []
        if archetype:
            detail_parts.append(archetype)
        else:
            detail_parts.append(player_class.title() if player_class else "Unclassified")
        if version:
            detail_parts.append("Version " + version[:8])
        detail = " · ".join(detail_parts)
        output.append({
            "key": "|".join([deck_name, archetype, version, player_class]),
            "label": display_name,
            "deck_name": deck_name,
            "archetype_name": archetype,
            "player_class": player_class,
            "version": version[:8] if version else "",
            "detail": detail,
            **_summary(group_rows),
        })
    output.sort(key=lambda r: (-r["games"], r["label"], r["version"]))
    return output


def _record_text(rows: list[MatchRecord]) -> str:
    wins = sum(1 for m in rows if m.result == "WIN")
    losses = sum(1 for m in rows if m.result == "LOSS")
    return f"{wins}-{losses}" if rows else "—"


def _mulligan_history(rows: list[MatchRecord]) -> list[dict[str, Any]]:
    offered: Counter[str] = Counter()
    kept: Counter[str] = Counter()
    replaced: Counter[str] = Counter()
    kept_games: dict[str, list[MatchRecord]] = defaultdict(list)
    replaced_games: dict[str, list[MatchRecord]] = defaultdict(list)
    for match in rows:
        offered.update(match.mulligan_offered)
        kept.update(match.mulligan_kept)
        replaced.update(match.mulligan_replaced)
        for card in set(match.mulligan_kept):
            kept_games[card].append(match)
        for card in set(match.mulligan_replaced):
            replaced_games[card].append(match)
    cards = sorted(offered, key=lambda c: (-offered[c], c))
    return [
        {
            "card_name": card,
            "offered_games": offered[card],
            "kept_games": kept[card],
            "replaced_games": replaced[card],
            "kept_record": _record_text(kept_games[card]),
            "replaced_record": _record_text(replaced_games[card]),
        }
        for card in cards
    ]


def _event_rows(events) -> list[dict[str, Any]]:
    return [{"turn": e.turn, "card_id": e.card_id, "card_name": e.card_name} for e in events]


def _mode_label(game_type: str, format_name: str) -> str:
    game_type = (game_type or "").upper()
    format_name = (format_name or "STANDARD").upper()
    prefix = "Standard" if format_name == "STANDARD" else format_name.replace("_", " ").title()
    if game_type == "GT_RANKED":
        return f"{prefix} Ranked"
    if game_type == "GT_CASUAL":
        return f"{prefix} Casual"
    return prefix


def build_dashboard(records: list[MatchRecord]) -> dict[str, Any]:
    from .tracking.scope import is_standard_constructed
    rows = sorted((m for m in records if is_standard_constructed(m.format, m.game_type)),
                  key=lambda m: (m.started_at, m.match_id), reverse=True)
    recent = []
    for m in rows:
        recent.append({
            "match_id": m.match_id,
            "recorded_at": m.started_at,
            "result": m.result,
            "result_label": "Win" if m.result == "WIN" else "Loss" if m.result == "LOSS" else m.result.title(),
            "player_class": m.player_class,
            "opponent_class": m.opponent_class,
            "initiative": m.initiative,
            "initiative_label": m.initiative.title() if m.initiative else "Unknown",
            "deck_label": _deck_label(m),
            "deck_name": m.deck_name,
            "deck_id": m.deck_id,
            "archetype_name": m.archetype_name,
            "deck_version": m.deck_version or "",
            "hearthstone_build": m.hearthstone_build,
            "format": m.format,
            "game_type": m.game_type,
            "mode_label": _mode_label(m.game_type, m.format),
            "turn_count": m.turn_count,
            "duration_seconds": m.duration_seconds,
            "duration_text": _duration(m.duration_seconds),
            "mulligan_offered": list(m.mulligan_offered),
            "mulligan_kept": list(m.mulligan_kept),
            "mulligan_replaced": list(m.mulligan_replaced),
            "cards_drawn": _event_rows(m.cards_drawn),
            "cards_played": _event_rows(m.cards_played),
            "opponent_observed": _event_rows(m.opponent_observed),
            "data_quality": m.data_quality,
        })

    builds = [m.hearthstone_build for m in rows if m.hearthstone_build]
    active_build = builds[0] if builds else ""
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_recorded_matches": len(rows),
        "active_hearthstone_build": active_build,
        "overall": _summary(rows),
        "deck_versions": _deck_versions(rows),
        "by_opponent_class": _breakdowns(rows, lambda m: m.opponent_class or "UNKNOWN", lambda k, _: str(k).replace("_", " ").title()),
        "by_initiative": _breakdowns(rows, lambda m: m.initiative or "UNKNOWN", lambda k, _: str(k).replace("_", " ").title()),
        "mulligan_history": _mulligan_history(rows),
        "recent_matches": recent,
        "data_quality": {
            "complete_matches": sum(1 for m in rows if m.data_quality.upper() == "COMPLETE"),
            "limited_matches": sum(1 for m in rows if m.data_quality.upper() != "COMPLETE"),
        },
    }


def load_dashboard(*, data_dir: Path | None = None) -> dict[str, Any]:
    ensure_history_epoch(data_dir=data_dir)
    return build_dashboard(MatchStore(data_dir).load())
