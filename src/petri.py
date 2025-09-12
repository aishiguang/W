from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Place, Transition, Arc, Marking, MarkingToken

def get_enabled_transitions(db: Session, marking_id: int) -> list[Transition]:
    """
    A transition is enabled if all its input places (Place -> Transition arcs)
    have tokens >= arc.weight in this marking.
    """
    # Gather tokens for this marking
    tokens = {
        (mt.place_id): mt.tokens
        for mt in db.scalars(select(MarkingToken).where(MarkingToken.marking_id == marking_id)).all()
    }

    enabled = []
    for t in db.scalars(select(Transition)).all():
        # All PT arcs for this transition
        pt_arcs = db.scalars(select(Arc).where(Arc.target_transition_id == t.id, Arc.source_place_id.is_not(None))).all()
        if not pt_arcs:
            continue  # transitions with no preset are not allowed here
        ok = True
        for a in pt_arcs:
            if tokens.get(a.source_place_id, 0) < a.weight:
                ok = False
                break
        if ok:
            enabled.append(t)
    return enabled

def fire_transition(db: Session, marking_id: int, transition_key: str) -> dict:
    t = db.scalar(select(Transition).where(Transition.key == transition_key))
    if not t:
        raise ValueError(f"Unknown transition: {transition_key}")

    enabled = {tr.id for tr in get_enabled_transitions(db, marking_id)}
    if t.id not in enabled:
        raise ValueError(f"Transition '{transition_key}' is not enabled for marking {marking_id}")

    # Subtract tokens from all input places
    pt_arcs = db.scalars(select(Arc).where(Arc.target_transition_id == t.id, Arc.source_place_id.is_not(None))).all()
    for a in pt_arcs:
        mt = db.scalar(select(MarkingToken).where(MarkingToken.marking_id == marking_id, MarkingToken.place_id == a.source_place_id).limit(1))
        if not mt:
            raise RuntimeError("Invariant broken: missing marking token row")
        mt.tokens -= a.weight
        if mt.tokens < 0:
            mt.tokens = 0

    # Add tokens to all output places
    tp_arcs = db.scalars(select(Arc).where(Arc.source_transition_id == t.id, Arc.target_place_id.is_not(None))).all()
    for a in tp_arcs:
        mt = db.scalar(select(MarkingToken).where(MarkingToken.marking_id == marking_id, MarkingToken.place_id == a.target_place_id).limit(1))
        if not mt:
            mt = MarkingToken(marking_id=marking_id, place_id=a.target_place_id, tokens=0)
            db.add(mt)
        mt.tokens += a.weight

    db.commit()
    return get_marking_state(db, marking_id)

def get_marking_state(db: Session, marking_id: int) -> dict:
    state = []
    for row in db.scalars(select(MarkingToken).where(MarkingToken.marking_id == marking_id)).all():
        state.append({"place_id": row.place_id, "tokens": row.tokens})
    return {"marking_id": marking_id, "tokens": state}
