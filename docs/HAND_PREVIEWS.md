# Hand preview coverage

Build 1.3.3 development candidate, October 26, 2026.

- Every visible friendly hand card can be identified by its actual hovered entity. Its current rendered description is read locally and reused in its rail preview.
- Ectoplasm has a per-token, ordered list of the publicly observed minions captured by its creating cast. Duplicates, the two boards, copied tokens and separate casts remain separate. Empty observed casts are distinct from missing history.
- Other cards with explicit local set-aside LINKED_ENTITY relationships show the known linked cards. A shared upstream creator alone does not establish a complete list.
- The current implementation does **not** certify related-card pools for every Standard mechanic. Resurrection pools, arbitrary recast histories and cards without an explicit relationship need individual rule validation. They must not be advertised as universally complete. Random effects cannot promise exact future outcomes.
- Stored lists describe captured contents, not a simulation of board capacity, replacement effects, target selection or future deaths. Incomplete game history is reported as unavailable/observed rather than reconstructed from hidden memory.
- Definition-only descriptions containing unresolved runtime arguments display a readable availability message. Exact dynamic wording is used when the client has rendered the visible hand card.

Validation: synthetic regressions cover independent tokens, duplicate entries, copied tokens, hidden identity rejection, public destruction snapshots, reset, text markers, stale IDs and match completion. A local game-log replay recovered two distinct Ectoplasm boards. A live Practice client check verified friendly hand identities and rendered text. No private logs are committed. Full Standard UI and mechanic acceptance remains a release gate.
