# GhostData product definition

GhostData records and organizes factual local Hearthstone Standard match history
and presents deterministic live player, opponent and Secret rails. Current
behavior and limitations are documented in the [user manual](USER_MANUAL.md).

## Principles

- Record observed facts before deriving statistics.
- Keep deck name, archetype label, and exact composition version as separate concepts.
- Never infer a missing deck identity from a later selected deck.
- A Hearthstone restart must not create a history gap merely because a new `Power.log` was created.
- Repeated scans, application restarts, and dashboard refreshes must be idempotent.
- Display descriptive history without claiming that a card, mulligan, or deck change caused a result.
- Keep the live Hearthstone experience quiet: only the optional deterministic deck rails appear in game; there is no coaching HUD.

## Dashboard

GhostData displays overall record, recorded win rate, average match duration, deck-version records, opponent-class records, first/second records, factual mulligan history, filters, recent matches, and selected-match card history.

Archetype is optional metadata. If GhostData cannot establish it from a dedicated factual source, it remains unclassified rather than being guessed.

## Live deck rails

The player rail shows the selected original deck, remaining copies, hand/deck
counts, generated or inserted cards, and active hero-zone effects. The opponent
rail shows only publicly observed card history and public counts/effects.

Secret candidates and supported public effect/placement deductions are bounded
inferences. Candidate slots are separated from observed opponent history and
withheld when the required class/source pool is unresolved. Ordinary Secrets use
the patch-scoped Standard catalog; supported historical generators use explicit
public source pools. Engine-known hidden identity must never disclose concealed
cards before public reveal. Quest progress and owner-labelled sideboards remain
separate displays.
