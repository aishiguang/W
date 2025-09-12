from collections import deque, defaultdict
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Place, Transition, Arc, Marking, MarkingToken

# ---------- Existing marking helpers (kept; still useful if you ever want “interactive mode”) ----------
def get_enabled_transitions(db: Session, marking_id: int) -> list[Transition]:
    tokens = {
        (mt.place_id): mt.tokens
        for mt in db.scalars(select(MarkingToken).where(MarkingToken.marking_id == marking_id)).all()
    }
    enabled = []
    for t in db.scalars(select(Transition)).all():
        pt_arcs = db.scalars(select(Arc).where(Arc.target_transition_id == t.id, Arc.source_place_id.is_not(None))).all()
        if not pt_arcs:
            continue
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

    pt_arcs = db.scalars(select(Arc).where(Arc.target_transition_id == t.id, Arc.source_place_id.is_not(None))).all()
    for a in pt_arcs:
        mt = db.scalar(select(MarkingToken).where(MarkingToken.marking_id == marking_id, MarkingToken.place_id == a.source_place_id).limit(1))
        if not mt:
            raise RuntimeError("Invariant broken: missing marking token row")
        mt.tokens -= a.weight
        if mt.tokens < 0:
            mt.tokens = 0

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

# ---------- New: Graph traversal utilities for FAQ mode ----------
def get_place_id_map(db: Session) -> dict[str, int]:
    return {p.key: p.id for p in db.scalars(select(Place)).all()}

def get_transition_id_map(db: Session) -> dict[str, int]:
    return {t.key: t.id for t in db.scalars(select(Transition)).all()}

def neighbors_from_places(db: Session, place_ids: set[int]) -> tuple[set[int], list[Arc]]:
    """Return transitions reachable via PT arcs from these places."""
    arcs = db.scalars(select(Arc).where(Arc.source_place_id.in_(place_ids), Arc.target_transition_id.is_not(None))).all()
    return {a.target_transition_id for a in arcs}, list(arcs)

def neighbors_from_transitions_to_places(db: Session, transition_ids: set[int]) -> tuple[set[int], list[Arc]]:
    """Return places reachable via TP arcs from these transitions."""
    arcs = db.scalars(select(Arc).where(Arc.source_transition_id.in_(transition_ids), Arc.target_place_id.is_not(None))).all()
    return {a.target_place_id for a in arcs}, list(arcs)

def neighbors_to_places(db: Session, place_ids: set[int]) -> tuple[set[int], list[Arc]]:
    """Return transitions that feed into these places via TP arcs (reverse)."""
    arcs = db.scalars(select(Arc).where(Arc.target_place_id.in_(place_ids), Arc.source_transition_id.is_not(None))).all()
    return {a.source_transition_id for a in arcs}, list(arcs)

def neighbors_to_transitions_from_places(db: Session, transition_ids: set[int]) -> tuple[set[int], list[Arc]]:
    """Return places that feed into these transitions via PT arcs (reverse)."""
    arcs = db.scalars(select(Arc).where(Arc.target_transition_id.in_(transition_ids), Arc.source_place_id.is_not(None))).all()
    return {a.source_place_id for a in arcs}, list(arcs)

def bfs_neighborhood(
    db: Session,
    seed_places: set[int],
    seed_transitions: set[int],
    max_depth: int = 2
) -> dict[str, dict[int, int]]:
    """
    Bidirectional expansion (both directions along arcs) up to max_depth.
    Returns distance maps: {'place': {id: dist}, 'transition': {id: dist}}
    """
    dist_p = {pid: 0 for pid in seed_places}
    dist_t = {tid: 0 for tid in seed_transitions}
    fp = deque(seed_places)
    ft = deque(seed_transitions)

    depth = 0
    while depth < max_depth and (fp or ft):
        depth += 1
        # expand from places -> transitions -> places
        for _ in range(len(fp)):
            p = fp.popleft()
            nbr_t, _ = neighbors_from_places(db, {p})
            # nbr_t |= neighbors_to_places(db, {p})  # reverse edges into p
            trans_from_rev, _ = neighbors_to_places(db, {p})  # get the set part
            nbr_t |= trans_from_rev
            for t in nbr_t:
                if t not in dist_t:
                    dist_t[t] = dist_p[p] + 1
                    ft.append(t)
        for _ in range(len(ft)):
            t = ft.popleft()
            nbr_p, _ = neighbors_from_transitions_to_places(db, {t})
            pred_p, _ = neighbors_to_transitions_from_places(db, {t})  # reverse edges into t
            for p in (nbr_p | pred_p):
                if p not in dist_p:
                    dist_p[p] = dist_t[t] + 1
                    fp.append(p)
    return {"place": dist_p, "transition": dist_t}
