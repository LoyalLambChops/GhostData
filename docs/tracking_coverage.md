# Standard rails and statistics overhaul

GhostData uses its own Python engine, Avalonia controls and open-source UnitySpy
sensor. This candidate is undergoing the local-data migration described in the
[validation ledger](parity_validation.md).

## Implemented behavior

| Area | Behavior |
| --- | --- |
| Player cards | Full selected-deck baseline, depleted rows retained, original cards held in hand highlighted, generated/copied/transformed cards separated, burn/discard labels, exact draw probabilities only when the entire deck count reconciles. |
| Opponent cards | Publicly observed identities, original public identity retained across transforms, separate zone/provenance states, no hidden hand or secret identity disclosure. |
| Hand | Position, acquisition turn, opening/mulligan/drawn/generated/returned/stolen origin, and publicly known identity. |
| Sideboards | Separate owner-labelled pools; setaside-to-hand acquisitions and linked hand copies consume the matching source pool once. |
| Quests | Existing quest, questline, sidequest and other hero-zone effects retain progress and ownership. |
| Secrets | Independent overlay with player active secrets and each opponent secret's candidate area; ruled-out names remain dimmed and struck through. Ordinary candidates use the Standard catalog; supported historical generators use their public source pool. Both active and ruled-out possibilities have hover previews. |
| Secret inference | Nested action boundaries, controller-scoped duplicate exclusion, spell/attack/minion/turn/death rules, board-space and dormant checks, after-spell target checks, locked Secrets, revealed duplicate exclusion, and trigger handling that retains safe armor-only deductions and withholds deductions after disruptive triggers. |
| Replacement effects | Complete starting-entity accounting supports whole-deck swaps, returns and replacements. Demon Portal uses an infinite-deck presentation. Public shattered-card triggers provide multiset predictions without inventing entity identities. |
| Public generation | Bounded rules attach to actual creations in canonical or TaskList effect blocks. Covers Core generation, First/Second Flame, Infestation/Gorishi Stingers, Void Souls, Meadowstrider, Imp Gang Stooge, Eternal Firebolt, Kiri, Stellar Balance, and other explicitly named outcomes. Nested effects and duplicate streams cannot create phantom rows. |
| Copies and disclosure | Public target copies, Beatrix history announcements, Eyes in the Sky links, Ursol's public aura, and Slime 'em! Ectoplasms. Far Sight retains original-deck accounting. Random generation displays public constraints without a fabricated identity or hover identity. Warmaster Blackhorn/overridden history and concealment records cannot disclose hidden cards. |
| Deck placement | Dredge choices identify local bottom cards and the selected top card; Overplanner retains chosen order; Kaldorei Cultivator retains bottom placement. TOP/BOTTOM labels do not duplicate original-deck rows. Top-card probabilities follow the actual copy, bottom cards are excluded while other cards remain above them, and shuffles clear placement. |
| Rewind | Undo the most recent PLAY transaction in canonical and TaskList streams independently, restoring cards, counts, provenance, choices and Secret deductions. Delayed animation cannot resurrect undone cards or erase a newer retried play. Completed-match statistics use the same correction. |
| Mixed rewards and copies | Latorvius displays the nine public quest rewards as an unresolved hand/deck pool, consuming possibilities as real cards become public. Nightmare Fuel and Deja Vu display unique known identities without identifying hidden hand slots. Wizened Truthseeker clears inferred hand-cost overrides. |
| Generated historical Secrets | Explicit public conditions cover attack, minion/spell play, deaths, damage, second draw, hero powers, zero mana and turn boundaries. Includes late spell targets, deathrattle board-space checks, Hidden Cache's later minion evidence, fast combat interruptions and a fresh activation when a Secret is played again. |
| Hover and readability | Names use 15 DIPs and details/draw percentages 11 DIPs. Long decks scroll instead of shrinking. Widths are 180–220 DIPs, heights cap at 780 DIPs, and the lower game quarter remains clear. Deck/Hand totals use 16 DIPs. A single non-activating, inward-facing text preview displays known cards, quests, sideboards and Secret possibilities; unknown hands have no preview identity. |
| Counts | Live deck/hand counts, accounting status and next fatigue; no opponent deck guessed from an archetype. |
| Dashboard | Summary/Matches/Charts; win rate, played-class and opponent distributions; per-deck/version stats and opponent-class matchup matrices; deck-performance highlights, averages, play time, best/worst matchups, Coin and class win rates, initiative and mulligan history. All statistical panels share the selected filters. |
| History | No 200-match truncation; ties excluded from win-rate denominator; full version hashes used for grouping/filtering. |
| Scope | Standard constructed only. Explicit Wild/Arena/other mode records are excluded. Legacy records with missing mode tags remain readable. |

Power.log is consumed one complete line at a time so transitions in one filesystem read are not collapsed into an entity's final state. Partial UTF-8 lines remain buffered until complete. UI state is published once per chunk. Log replacement/truncation resets runtime entity history.

## Verification and remaining work

See the [validation ledger](parity_validation.md) for current test evidence and
open acceptance gates. The source contains independently authored regressions
and synthetic UI data. No external application code is packaged.

The candidate imports public card metadata directly from the installed Blizzard
client and derives Standard membership from its active rotation tables. There
are no card-image or remote-card-database requests. Separate recoverable overdraw,
a portable runtime package and explicit GitHub release staging/installation are
implemented. Text hover remains the supported preview. Full expansion interaction,
reconnect and matched resource acceptance are still open.

Use the [technical manual](TECHNICAL_MANUAL.md) for build and preview commands.
The [user manual](USER_MANUAL.md) describes the actual available controls.
