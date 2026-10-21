# GhostData feature roadmap

This is a planning backlog, not a list of shipped features or a promise that all
items are part of the current parity build. Consult the [user manual](USER_MANUAL.md)
and [validation ledger](parity_validation.md) for implemented behavior and evidence.
The current release scope is a lightweight local Standard dashboard and rails.
Replay/archive features, cloud services and other game modes are excluded.

GhostData should become the most trustworthy local-first Hearthstone record and
deck-tracking companion. New work should preserve its central boundary: observed
facts and transparent, bounded inference rather than tactical coaching.

## Product goals

1. Never silently lose or mislabel a completed Standard match.
2. Make every tracker value explainable from public game state.
3. Turn local match history into useful, honest review without claiming causality.
4. Remain fast, quiet, configurable, and fully useful without an online account.

## Phase 1 — Trust, diagnostics, and daily usability

These are the highest-priority improvements because every later feature depends
on reliable capture and a player being able to understand system state.

### 1.1 Health and diagnostics center — P0, medium effort

- Show recorder, Power.log, selected-deck sensor, card database, rail process,
  Hearthstone build, and last successful match-capture status.
- Distinguish healthy, waiting, degraded, and failed states.
- Provide actionable recovery steps instead of raw exceptions.
- Add one-click creation of a privacy-reviewed diagnostic bundle containing app
  logs, versions, settings, and redacted parser evidence.
- Acceptance: a user can determine why rails or history are missing without
  opening PowerShell.

### 1.2 Capture confidence and recovery — P0, medium effort

- Display the timestamp and identity of the last recorded match.
- Detect incomplete or interrupted games and explain why they were excluded.
- Add a rescan/recovery command for historical Power.log sessions.
- Record parser/sensor compatibility against each Hearthstone build.
- Preserve unknown events in a bounded diagnostic ledger for future fixtures.
- Acceptance: restarting Hearthstone, GhostData, or Windows does not silently
  produce gaps or duplicate games.

### 1.3 Safe local data management — P0, small-to-medium effort

- Automatic versioned backup before schema migration or history deletion.
- Replace irreversible clear with move-to-backup plus restore-last-backup.
- Export/import canonical JSON and CSV.
- Add schema migrations and validation rather than relying on permissive reads.
- Acceptance: upgrades and user mistakes cannot destroy the only history copy.

### 1.4 Settings and overlay calibration — P0, medium effort

- Persist rail enablement, width, vertical offset, scale, opacity, and text size.
- Provide an unlock/calibration mode with sample rows and reset-to-default.
- Support per-monitor DPI, windowed/borderless/fullscreen transitions, and
  Hearthstone resolution changes.
- Add independent toggles for player rail, opponent rail, thumbnails, Secrets,
  generated cards, and hero-zone effects.
- Acceptance: rails remain correctly positioned and legible across supported
  display configurations without editing files.

## Phase 2 — Stronger in-match factual tracking

### 2.1 Card inspection and provenance — P1, medium effort

- Hover a rail row to show a larger card preview without intercepting game clicks.
- Mark each card as original-deck, generated, discovered, transformed, shuffled,
  stolen, returned, or publicly revealed when the log supports that fact.
- Preserve source-card relationships for generated cards.
- Add compact filters/collapse controls for long lists.

### 2.2 Explainable Secret intelligence — P1, large effort

- Cover every verified current-Standard Secret class from a versioned catalog.
- Show why each candidate remains or was eliminated, including the triggering
  public observation and turn.
- Track multiple simultaneous Secrets independently and handle ordering safely.
- Add fixtures for every supported trigger rule and fail closed after patches.
- Clearly distinguish confirmed identity, possible identity, and unavailable
  candidate data.

### 2.3 Public zone and resource history — P1, medium-to-large effort

- Optional graveyard/history panel for cards that died, were destroyed, discarded,
  burned, transformed, or returned to hand/deck.
- Player and opponent fatigue counters.
- Opponent hand-age markers and public origin markers, without identifying hidden
  cards.
- Turn timer plus total player/opponent elapsed time.
- Keep every feature individually disableable.

### 2.4 Deck-accounting resilience — P1, large effort

- Expand tests for tradeable cards, sideboards, tourists, multi-class cards,
  temporary deck copies, shuffled cards, transformed cards, and deck swaps.
- Surface accounting confidence (`EXACT`, `RECONCILED`, `LIMITED`) with an
  explanation when counts diverge.
- Add a compact end-of-game accounting report for diagnostic review.

## Phase 3 — Match review and personal analytics

### 3.1 Factual match detail improvements — future consideration

- Improve navigation of the existing stored mulligan, draw/play and public
  opponent summaries without introducing a replay archive or export format.
- Never reconstruct hidden information that was unavailable during the match.

### 3.2 Dashboard filtering and navigation — P1, medium effort

- Date range, season, patch/build, ranked rank band, deck version, opponent class,
  result, initiative, and match-duration filters.
- Full-text search for deck names and observed cards.
- Consider virtualization for very large histories; the former 200-match cap has
  already been removed.
- Saved filter presets such as “this season, Standard Ranked, current deck.”

### 3.3 Deck-version laboratory — P1, medium effort

- Visual diff between two exact deck fingerprints: added, removed, and changed
  cards/sideboards.
- Version timeline showing when each list was first and last played.
- Descriptive record and matchup table per version.
- Let players name or annotate versions without changing factual identity.
- Avoid declaring that a deck change caused a win-rate change.

### 3.4 Honest performance views — P1, medium effort

- Rolling record and win-rate trend by date/session with visible sample sizes.
- Matchup matrix by player deck/version and opponent class.
- First-versus-second, duration, and turn-count distributions.
- Mulligan frequency and kept/replaced records with minimum-sample warnings.
- Draw/play timing summaries by card and matchup.
- Clearly label small samples and descriptive—not causal—statistics.

### 3.5 Notes, tags, and sessions — P2, medium effort

- Optional post-game notes and user-defined tags.
- Group games into play sessions with session record, duration, and decks used.
- Bookmark notable games and filter to bookmarks.
- Preserve notes through deduplication and record enrichment.

## Phase 4 — Deck and collection workflow

### 4.1 Deck-code interoperability — P2, medium effort

- Import/export official Hearthstone deck codes.
- Copy the currently selected deck code and exact version from the dashboard.
- Keep deck name, user label, archetype label, and composition fingerprint separate.

### 4.2 Local collection snapshot — P2, large research effort

- Capture normal, golden, signature/diamond, collectible, and craftable counts only
  when the selected-deck sensor exposes them reliably.
- Store capture timestamp and Hearthstone build.
- Show missing cards for a selected/imported deck and factual crafting cost.
- Fail closed if collection representation is incomplete or ambiguous.

### 4.3 Card-data lifecycle — P1, medium effort

- Version card metadata and Standard-set legality by Hearthstone build.
- Refresh metadata automatically after a new build, with last-known-good rollback.
- Pre-fetch art for the active deck and Secret pool; retain offline cache behavior.
- Show data version and freshness in the diagnostics center.

## Phase 5 — Polish and distribution

### 5.1 Installation and updates — P2, large effort

- Signed installer, Start-menu integration, clean uninstall, and optional launch
  with Windows.
- In-app update availability check with release notes and explicit user approval.
- Package Python/runtime dependencies so normal use does not require developer SDKs.

### 5.2 Accessibility and localization — P2, medium effort

- Scalable text, high-contrast and color-vision-safe palettes, keyboard navigation,
  screen-reader labels, and reduced-animation behavior.
- Localizable UI strings and card-name display based on Hearthstone locale.

### 5.3 Optional extension boundary — P3, large effort

- Documented read-only event/export interface for community tools.
- Sandboxed extensions must not alter core records or access hidden information.
- Defer this until storage schemas and public event contracts are stable.

## Recommended delivery order

1. Health and diagnostics center.
2. Safe backups, export/import, and schema migrations.
3. Overlay calibration and persisted settings.
4. Card-data lifecycle plus patch compatibility reporting.
5. Explainable Secret intelligence expansion.
6. Navigation of factual match details within the local storage scope.
7. Dashboard date/season filters and deck-version comparison.
8. Honest trend and matchup analytics.
9. Card provenance, graveyard/history, timers, and fatigue.
10. Deck-code and collection workflows.
11. Installer, updater, accessibility, localization, then extensions.

## Explicit non-goals

- No live tactical recommendation engine or tactical HUD.
- No hidden-information disclosure.
- No unverified archetype guessing presented as fact.
- No “this card caused the win” claims from observational history.
- No cloud account requirement for core tracking and review.
