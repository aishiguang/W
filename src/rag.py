from typing import Sequence
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from numpy import frombuffer, float32, dot
import numpy as np
from .models import Document, Embedding, MarkingToken

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    return float(dot(a, b) / denom) if denom else 0.0

def _embedding_from_bytes(blob: bytes, dim: int) -> np.ndarray:
    arr = frombuffer(blob, dtype=float32)
    return arr[:dim]

def retrieve_candidates(db: Session, query: str, limit: int = 25) -> list[Document]:
    # FULLTEXT search (MySQL) as a simple first cut
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
        # fallback: keyword LIKE (very small datasets)
        ids = [d.id for d in db.scalars(select(Document).limit(limit)).all()]
    docs = db.scalars(select(Document).where(Document.id.in_(ids))).all()
    # keep order by ids
    docs_by_id = {d.id: d for d in docs}
    return [docs_by_id[i] for i in ids if i in docs_by_id]

def rerank_with_embeddings(db: Session, query_embedding: np.ndarray, docs: Sequence[Document]) -> list[tuple[Document, float]]:
    # Only rerank docs having embeddings
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
    """
    If an LLM client is provided, ask it to answer using the chunks.
    Otherwise, return a concise extractive answer with sources.
    """
    sources = [{"id": d.id, "title": d.title} for d in context_chunks[:5]]
    if llm is None:
        # Simple extractive: pick top doc's first ~600 chars
        snippet = (context_chunks[0].content[:600] + "...") if context_chunks else "No context found."
        return {"answer": snippet, "sources": sources}
    # LLM mode
    content = "\n\n".join([f"### {d.title}\n{d.content}" for d in context_chunks[:5]])
    prompt = f"You are a Witcher 3 lore assistant. Answer the user's question using ONLY the context.\n\n# Context\n{content}\n\n# Question\n{question}\n\nBe concise and cite titles inline like [Title]."
    resp = llm.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user", "content":prompt}],
        temperature=0.2,
    )
    return {"answer": resp.choices[0].message.content, "sources": sources}
