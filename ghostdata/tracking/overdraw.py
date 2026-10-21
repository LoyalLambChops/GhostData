"""Public evidence for cards held outside the hand by Godfrey's Atlas."""
ATLAS = "JAIL_509e"


def created(state, entity_id, frame):
    if frame.card_id != ATLAS or frame.kind != "TRIGGER" or not getattr(frame, "overdraw_capture", False):
        return
    source = state.entities.get(frame.source)
    if source is None or not source.controller:
        return
    pool = state.recoverable_overdraw
    if any(r["new"] == entity_id for r in pool):
        return
    pending = next((r for r in pool if r["controller"] == source.controller and not r["new"]), None)
    if pending is not None:
        pending["new"] = entity_id
    else:
        pool.append(dict(controller=source.controller, old=0, new=entity_id, returned=False))


def burned(state, entity):
    if entity.tags.get("GHOSTDATA_OVERDRAW_CAPTURED") == "1":
        return
    if not entity.controller or not any(e.card_id == ATLAS and e.controller == entity.controller
            and e.zone == "PLAY" for e in state.entities.values()):
        return
    entity.tags["GHOSTDATA_OVERDRAW_CAPTURED"] = "1"
    pool = state.recoverable_overdraw
    if any(r["old"] == entity.entity_id for r in pool):
        return
    pending = next((r for r in pool if r["controller"] == entity.controller and not r["old"]), None)
    if pending is not None:
        pending["old"] = entity.entity_id
    else:
        pool.append(dict(controller=entity.controller, old=entity.entity_id, new=0, returned=False))


def reconcile(state):
    """Retain ambiguous opponent possibilities until a public reveal resolves them."""
    pool = state.recoverable_overdraw
    revealed = []
    for row in list(pool):
        entity = state.entities.get(row["new"])
        if entity is None:
            continue
        if entity.zone == "HAND":
            row["returned"] = True
        if not row["returned"]:
            continue
        peers = [r for r in pool if r["controller"] == row["controller"]]
        public = entity.card_id and (entity.controller == state.local_player_pid or
            entity.zone in {"PLAY", "SECRET", "GRAVEYARD"} or entity.tags.get("GHOSTDATA_OVERDRAW_REVEALED") == "1")
        if row["controller"] == state.local_player_pid or public or len(peers) == 1:
            original = state.entities.get(row["old"])
            if len(peers) == 1 and not entity.card_id and original and original.card_id:
                entity.update_card_identity(original.card_id, original.name)
                entity.tags["GHOSTDATA_OVERDRAW_DISCOUNT"] = "1"
                revealed.append(entity)
            pool.remove(row)
    for controller in {r["controller"] for r in pool}:
        peers = [r for r in pool if r["controller"] == controller]
        if peers and all(r["returned"] for r in peers):
            pool[:] = [r for r in pool if r["controller"] != controller]
    return revealed


def rows(state, controller, database):
    from .tracker.models import RailCardRow
    if state is None or controller is None:
        return ()
    result = []
    pool = [r for r in state.recoverable_overdraw if r["controller"] == controller]
    ambiguous = controller != state.local_player_pid and any(r["returned"] for r in pool)
    for row in pool:
        original = state.entities.get(row["old"])
        cid = original.card_id if original else ""
        card = database.get(cid)
        cost = card.cost if card else original.cost if original else None
        result.append(RailCardRow(card_id=cid, name=card.name if card else original.name or cid if original else "Unknown card",
            cost=max(0, cost - 1) if cost is not None else None, count=1, zone="OVERDRAW",
            state="MAY BE IN HAND" if ambiguous else "AWAITING SPACE", text=card.text if card else ""))
    return tuple(result)
