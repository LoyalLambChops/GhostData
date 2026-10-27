# Hand preview coverage

Public beta 1.3.7; reviewed client 37.0.0.255790, October 27, 2026.

## Implemented behavior

Rail hover uses the client-rendered description when available, with local definition text as a fallback. Game-hand hover is a separate effect-card display: only supported summon, replay and stored-card lists open it. Ordinary hand cards, empty lists, counters, self/target context and draw/Discover-only lists produce no popup. The hovered card’s own description is never repeated there. Each related result shows its name and local rules text. Cards with the same identity retain separate entity-specific contents. Long lists remain open while the pointer is over the preview and support wheel scrolling. Local definitions arriving after the first log events enrich the original observations without changing their identities or ownership.

History observations are immutable and include controller, global turn, source instance, tribes, printed cost, mechanics and Assemble components. Deaths, plays, resolved Reborn events, discards, consumed cards and public stored contents remain separate. Reset and rewind restore their matching histories. A returned minion loses stored effects that were cleared when it left play.

### Explicit history rules

| Card | Preview contract |
|---|---|
| Army of N'Zoth (BE_017t5) | Different Deathrattle candidates; up to 4 are selected. |
| Terror of the Wastes (BE_564) | Friendly minions that died this turn. |
| Broodqueen Sha'kar (BE_565) | Friendly minions that died this turn. |
| Hungering Cavern (BE_877) | Friendly minions that died this turn. |
| Raith Van Geist (CAP_806) | Friendly minions that were Reborn; board space and random targets apply. |
| Duke of Below (CATA_493) | Observed cards discarded this game. |
| Ravenous Felfisher (CATA_529) | Fel spells played this game. |
| Confront the Tol'vir (CATA_560) | 1-Cost minions played this game; board space applies. |
| Gronn Giant (CATA_616) | Last card played; its cost determines the reduction. |
| Calia Menethil (CORE_CATA_002) | Highest-Cost friendly minions that died; ties are random. |
| Krag'wa, the Frog (CORE_TRL_345) | Spells played on your previous turn; hand space applies. |
| Mirrex, the Crystalline (DINO_407) | Last publicly played opposing minion. |
| Merithra (EDR_238) | Different friendly minions costing 8+ that died; board space applies. |
| Aessina (EDR_430) | Friendly minions that died this game. |
| Succumb to Madness (EDR_455) | Observed friendly Dragons available to Discover. |
| Ysondre (EDR_465) | Observed Ysondre deaths; Dragon summons are random. |
| Archdruid of Thorns (EDR_491) | Friendly minions with Deathrattles that died this turn. |
| Grotesque Runeblade (EDR_812) | Last card played; its runes determine the bonus. |
| Ravenous Felhunter (EDR_891) | Current resurrection pool; one is selected and copied. |
| Ferocious Felbat (EDR_892) | Current resurrection pool excluding this card type; one is selected and copied. |
| Starsurge (EDR_941) | Friendly minions that died this game. |
| Splintered Reality (END_009) | Friendly Treants that died this game. |
| Bone Flurry (JAIL_445) | Friendly minions that died this turn. |
| Slice and Dice (JAIL_500) | Other cards played this turn; replay targets and order are not predicted. |
| Zuramat's Prison (JAIL_887) | Cards discarded by a prison this game. |
| Zuramat the Obliterator (JAIL_887t2) | Observed prison discards; one card is selected each turn. |
| Defias Wannabe (JAIL_909) | Other cards played this turn. |
| Undeath Sentence (JAIL_940) | Minions whose Deathrattle may be selected at random. |
| Charity (MEND_805) | Friendly minions that died this turn; copies get +3/+3. |
| Energizing Idol (THD_040hpb) | Last observed spell played. |
| Memoriam Manifest (TIME_616) | Highest-Cost friendly Undead that died; ties are random. |
| Talanji of the Graves (TIME_619) | Observed Bwonsamdi resurrection candidates; otherwise draws him. |
| Azure Oathstone (TIME_852t3) | Friendly Dragons that died; board space applies. |
| Endbringer Umbra (TLC_106) | Observed Deathrattle pool; up to 5 are triggered. |
| Creature of the Sacred Cave (TLC_430) | Holy spells cast this turn; one is selected at random. |
| Resuscitate (TLC_818) | Resurrection candidates: one each at Costs 1, 2 and 3. |
| Vuja De (TOT_108) | Previously played spells and minions; Combo determines the second Discover. |
| Reminisce (TOT_343) | Last two publicly played opposing cards. |
| Krag'wa, the Frog (TRL_345) | Spells played on your previous turn; hand space applies. |

### Stored contents and current targets

- Ectoplasm: ordered per-token cast snapshots, both sides kept separate, duplicates retained, copied-token anchors and Assemble components preserved.
- Specimen Jar and Horrible Egg: verified current references or the captured original entity. Ordinary copied minions do not inherit guessed payloads.
- Gemstone Hoarder and Hungering Ancient: current attached references or observations attributed to this source instance.
- Iso'rath: observed stored count; unrevealed opposing hand identities remain Unknown card.
- Ursoc and Frostmourne: observed kills attributed to the current source instance, including weapon attribution for hero attacks.
- Chromie: matches played history against the existing reconciled deck inventory without reading hidden deck identities.
- Chrono-Lord Epoch and Untimely Death: currently eligible public board entities, with the trigger/target conditions stated.
- Tyrax/Terror's Grave and Husk/Eternal Life: fixed counterpart/hero references; future board space, corpses and triggers still apply.

### Deck candidates and fixed generation

- Rail hover: 28 explicit draw, deck-Discover, copy and summon contracts use the reconciled remaining-deck inventory. Examples include Exotic Houndmaster, Tormented Dreadwing, The Curator, Living Flame, Conjured Bookkeeper, Tracking and Cultist Map. Duplicates are retained; dual tribes and All tribes are handled. Candidate lists never claim to predict the offered choices or random draw. The definitive mapping is `ghostdata/tracking/deck_previews.py`.
- Annihilation and Contingency use explicitly observed bottom-insertion batches, including Imp Gang Stooge, Meadowstrider and Kaldorei Cultivator. Newer batches are deeper. A batch crossing the bottom-two/three boundary produces possible candidates, not guaranteed outcomes. Unobserved slots remain unknown; unranked Dredge information is not treated as an exact order.
- Shuffle events, unlocated insertions and supported reorder effects invalidate placement evidence. Drawn cards leave their batch. Concealed or changed identities cannot reuse a stale preview name. State reset and journal replay reconstruct placement alongside the other parser state.
- Rail hover: fixed generated identities reuse the existing reviewed creation contracts as conditional previews, with a maximum quantity. This does not create tracker entities or imply the effect has resolved.

### Generic local reference contracts

The importer reads the installed client's CardRace records and Assets.Card.CardTextBuilderType metadata. Recognized reference builders distinguish entity IDs from DBF IDs, counts and race IDs. Only referenced placeholders are inspected. This covers attached effects and stored-spell tokens, including carved spells and multiple-name lists. Hidden-choice builders are deliberately not interpreted. Same-card duplicates are retained; missing references stay unavailable.

The current implementation resolves entity-reference, entity-power, paired-reference, DBF-reference, script-slot-six DBF, inherited paired-reference and CARDTEXT_ENTITY_0 through _9 multiple-name formats. Private opposing zones are not traversed for identities. Neither a shared creator nor an arbitrary numeric script tag establishes a stored-card list.

## Evidence and limits

- 261 Python regression tests and 67 UI/lifecycle checks passed during this development pass. Tests exercise filters, ties, tribes, repeated deaths/plays, extra turns, returns, hidden identities, duplicated streams, stored references, Assemble payloads and rewind.
- The updated client imported 36,390 definitions successfully, including 572 records with multiple tribe values. The local hand stream returned READY for all 12 sampled main-menu readings.
- General random generation pools and cost/attack/provenance-dependent tutors still need additional contracts. These unsupported candidate lists are not advertised as complete. Live acceptance across every mechanic family remains unverified. The beta scope is dependable supported behavior and honest unknowns, rather than complete parity with another application.
- Lists distinguish stored contents, current eligible pools, references and observed history. Random targets/outcomes and future effects are not guaranteed. Missing history cannot be reconstructed as exact results.
- This is a documented coverage expansion, not certification that every feature or every possible interaction is equivalent to another application. Additional families remain explicitly outside the supported contracts.

## Patch change gate

Run `python tools/audit_card_previews.py <local snapshot path>`. The baseline fingerprints 2,444 constructed-set definitions/tokens/enchantments from build 255790, without distributing card text. New, removed or changed definitions return a failing status for review. Set/prefix selection is an audit aid, not a claim that every client record is legally playable. A passing fingerprint check does not detect server-only behavior changes and is not proof of universal mechanic correctness.


### Live sensor and tracker check — October 27, 2026

On client 37.0.0.255790, a 12-second Practice-match capture returned 104 READY samples, all identifying the hovered friendly Annihilation card. The entity ID and CardID matched Power.log. Integration validation exposed an opponent-only observation check suppressing friendly hand identities; build 1.3.5 fixes this. Reprocessing the match with the fix resolved the same card in the published player-hand state and identified all four friendly hand cards without a selected-deck seed. Two regressions cover the friendly reveal/hide boundary and unrevealed opponent identities.

Current rendered wording was returned, including the game's formatting markers for the UI formatter to remove. The capture remains in ignored local scratch storage. This validates the read-only sensor and tracker association, not the visible production popup or Annihilation's bottom-of-deck summon preview. Practice is intentionally excluded by the Standard scope filter; a supported Standard match is required for end-to-end overlay acceptance. No scope setting or saved match data was changed.

### Public beta verification

The source tagged v1.3.7 passed [public CI](https://github.com/LoyalLambChops/GhostData/actions/runs/40596676836). The effect-only hand popup was rendered from the real Avalonia control with synthetic stored minions; the hovered card description was absent and duplicate result cards remained in order. This visual check is not a live capture of every mechanic. Anonymous download, verified public update from 1.3.6 and startup/data-preservation checks are recorded in PUBLIC_RELEASE_READINESS.md.
