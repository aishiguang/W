from typing import Sequence
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from numpy import frombuffer, float32, dot
import numpy as np

from .models import Document, Embedding, MarkingToken, Place, Transition
from .petri import bfs_neighborhood
from .config import settings

# ---------------- Embedding helpers (unchanged) ----------------
def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    return float(dot(a, b) / denom) if denom else 0.0

def _embedding_from_bytes(blob: bytes, dim: int) -> np.ndarray:
    arr = frombuffer(blob, dtype=float32)
    return arr[:dim]

# ---------------- Base retriever (unchanged) ----------------
def retrieve_candidates(db: Session, query: str, limit: int = 25) -> list[Document]:
    sql = text("""
        SELECT d.*,
               MATCH(d.title, d.content) AGAINST (:q IN NATURAL LANGUAGE MODE) AS score
        FROM documents d
        WHERE MATCH(d.title, d.content) AGAINST (:q IN NATURAL LANGUAGE MODE)
        ORDER BY score DESC
        LIMIT :lim
    """)
    rows = db.execute(sql, {"q": query, "lim": limit}).mappings().all()
    ids = [r["id"] for r in rows]
    if not ids:
        ids = [d.id for d in db.scalars(select(Document).limit(limit)).all()]
    docs = db.scalars(select(Document).where(Document.id.in_(ids))).all()
    by_id = {d.id: d for d in docs}
    return [by_id[i] for i in ids if i in by_id]

def rerank_with_embeddings(db: Session, query_embedding: np.ndarray, docs: Sequence[Document]) -> list[tuple[Document, float]]:
    emb_map = {}
    for d in docs:
        e = db.scalar(select(Embedding).where(Embedding.doc_id == d.id))
        if e:
            emb_map[d.id] = _embedding_from_bytes(e.vector, e.dim)
    if not emb_map:
        return [(d, 0.0) for d in docs]
    scored = []
    for d in docs:
        if d.id in emb_map:
            scored.append((d, _cosine(query_embedding, emb_map[d.id])))
        else:
            scored.append((d, 0.0))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored

# ---------------- New: seed estimation & Petri-aware context ----------------
def estimate_seeds_from_query(
    db: Session,
    query: str,
    top_k: int = 5,
    base_docs: Sequence[Document] | None = None,
) -> tuple[set[int], set[int]]:
    """
    Infer relevant place/transition ids from query by looking at top documents and
    harvesting their related nodes.
    """
    docs = list(base_docs) if base_docs is not None else retrieve_candidates(db, query, limit=25)
    place_votes, trans_votes = {}, {}
    for i, d in enumerate(docs[:top_k]):
        w = 1.0 / (1 + i)  # slightly favor top results
        if d.related_place_id:
            place_votes[d.related_place_id] = place_votes.get(d.related_place_id, 0) + w
        if d.related_transition_id:
            trans_votes[d.related_transition_id] = trans_votes.get(d.related_transition_id, 0) + w
    # fallback: keyword heuristic on place/transition names
    if not place_votes and not trans_votes:
        q = query.lower()
        for p in db.scalars(select(Place)).all():
            if p.key in q or p.name.lower() in q:
                place_votes[p.id] = place_votes.get(p.id, 0) + 1.0
        for t in db.scalars(select(Transition)).all():
            if t.key in q or t.name.lower() in q:
                trans_votes[t.id] = trans_votes.get(t.id, 0) + 1.0

    seed_places = {pid for pid, _ in sorted(place_votes.items(), key=lambda kv: kv[1], reverse=True)[:3]}
    seed_trans = {tid for tid, _ in sorted(trans_votes.items(), key=lambda kv: kv[1], reverse=True)[:3]}
    # If still empty, default to “start” node if any exists
    if not seed_places and not seed_trans:
        seed_places = _fallback_seed_places(db)
    return seed_places, seed_trans


def _fallback_seed_places(db: Session) -> set[int]:
    """Default to the earliest-seeded place when no signals are present."""
    first_place = db.scalar(select(Place).order_by(Place.id))
    return {first_place.id} if first_place else set()

def documents_in_neighborhood(
    db: Session,
    place_dist: dict[int, int],
    trans_dist: dict[int, int],
    base_docs: Sequence[Document],
    max_docs: int = 12
) -> list[tuple[Document, float]]:
    """
    Rank documents by:
      - whether they’re in the Petri neighborhood (distance-based bonus),
      - their initial fulltext position (use base_docs order),
      - optional small title match bonus.
    """
    index_pos = {d.id: i for i, d in enumerate(base_docs)}
    scored: list[tuple[Document, float]] = []
    all_docs = list(db.scalars(select(Document)).all())

    def dist_bonus(d: Document) -> float:
        bonus = 0.0
        if d.related_place_id and d.related_place_id in place_dist:
            bonus += max(0.0, 1.0 - 0.25 * place_dist[d.related_place_id])  # depth decay
        if d.related_transition_id and d.related_transition_id in trans_dist:
            bonus += max(0.0, 1.0 - 0.25 * trans_dist[d.related_transition_id])
        return bonus

    for d in all_docs:
        base = 0.0
        if d.id in index_pos:
            base = max(0.0, 1.0 - 0.05 * index_pos[d.id])  # earlier FT hit → slightly higher
        title_hit = 0.1 if any(tok in (d.title or "").lower() for tok in ("ciri", "kaer morhen", "baron", "uma", "eredin", "skellige")) else 0.0
        score = base + title_hit + dist_bonus(d)
        if score > 0.0:
            scored.append((d, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:max_docs]

def boost_by_marking(db: Session, marking_id: int | None, docs: Sequence[tuple[Document, float]]) -> list[tuple[Document, float]]:
    if marking_id is None:
        return list(docs)
    active_place_ids = [mt.place_id for mt in db.scalars(select(MarkingToken).where(MarkingToken.marking_id == marking_id)).all() if mt.tokens > 0]
    boosted = []
    for d, s in docs:
        bonus = 0.15 if (d.related_place_id in active_place_ids) else 0.0
        boosted.append((d, s + bonus))
    boosted.sort(key=lambda x: x[1], reverse=True)
    return boosted

def generate_answer(context_chunks: list[Document], question: str, llm=None) -> dict:
    sources = [{"id": d.id, "title": d.title} for d in context_chunks[:5]]
    if llm is None or not context_chunks:
        snippet = (context_chunks[0].content[:600] + "...") if context_chunks else "No context found."
        return {"answer": snippet, "sources": sources}
    content = "\n\n".join([f"### {d.title}\n{d.content}" for d in context_chunks[:8]])
    prompt = (
        "You are a Witcher 3 storyline FAQ assistant.\n"
        "Answer ONLY using the provided context. Prefer concise, spoiler-aware explanations.\n"
        "Cite titles inline like [Title].\n\n"
        f"# Question\n{question}\n\n# Context\n{content}\n"
    )
    model_name = settings.openai_model or "gpt-4o-mini"
    resp = llm.chat.completions.create(
        model=model_name,
        messages=[{"role":"user", "content":prompt}],
        temperature=0.2,
    )
    return {"answer": resp.choices[0].message.content, "sources": sources}

# ---------------- Orchestrator called by /ask ----------------
def petri_aware_retrieve(
    db: Session,
    query: str,
    marking_id: int | None = None,
    neighborhood_depth: int = 2,
    max_docs: int = 12
) -> list[Document]:
    # 1) Fulltext first-pass
    ft_docs = retrieve_candidates(db, query, limit=25)

    # 2) Seed estimation if no explicit marking
    seed_places, seed_trans = estimate_seeds_from_query(db, query, base_docs=ft_docs)

    # 3) Build Petri neighborhood
    dist = bfs_neighborhood(db, seed_places, seed_trans, max_depth=neighborhood_depth)

    # 4) Rank docs with neighborhood awareness
    scored = documents_in_neighborhood(db, dist["place"], dist["transition"], ft_docs, max_docs=max_docs)

    # 5) Optional: boost by marking if supplied (kept for future interactive features)
    scored = boost_by_marking(db, marking_id, scored)

    return [d for d, _ in scored]
