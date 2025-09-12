from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .db import SessionLocal, init_db
from .petri import get_enabled_transitions, fire_transition, get_marking_state
from .models import Marking, MarkingToken, Place, Transition, Document
from .rag import retrieve_candidates, rerank_with_embeddings, boost_by_marking, generate_answer
from .config import settings

try:
    from openai import OpenAI
    _openai_client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
except Exception:
    _openai_client = None

app = FastAPI(title="Witcher III RAG + PetriNet")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def startup():
    init_db()

@app.get("/health")
def health():
    return {"ok": True}

class CreateMarkingIn(BaseModel):
    name: str
    starting_place_key: str

@app.post("/petri/markings")
def create_marking(payload: CreateMarkingIn, db: Session = Depends(get_db)):
    place = db.query(Place).filter(Place.key == payload.starting_place_key).first()
    if not place:
        raise HTTPException(400, f"Unknown starting place '{payload.starting_place_key}'")
    m = Marking(name=payload.name)
    db.add(m)
    db.flush()
    db.add(MarkingToken(marking_id=m.id, place_id=place.id, tokens=1))
    db.commit()
    return {"marking_id": m.id, "state": get_marking_state(db, m.id)}

@app.get("/petri/markings/{marking_id}")
def read_marking(marking_id: int, db: Session = Depends(get_db)):
    return get_marking_state(db, marking_id)

@app.get("/petri/markings/{marking_id}/enabled")
def enabled_transitions(marking_id: int, db: Session = Depends(get_db)):
    return [{"key": t.key, "name": t.name} for t in get_enabled_transitions(db, marking_id)]

class FireIn(BaseModel):
    transition_key: str

@app.post("/petri/markings/{marking_id}/fire")
def fire(marking_id: int, payload: FireIn, db: Session = Depends(get_db)):
    try:
        state = fire_transition(db, marking_id, payload.transition_key)
        return state
    except ValueError as e:
        raise HTTPException(400, str(e))

class AskIn(BaseModel):
    question: str
    marking_id: int | None = None

@app.post("/ask")
def ask(payload: AskIn, db: Session = Depends(get_db)):
    docs = retrieve_candidates(db, payload.question, limit=25)
    # Optional embedding rerank if you add embeddings later
    scored = [(d, 0.0) for d in docs]
    scored = boost_by_marking(db, payload.marking_id, scored)
    top_docs = [d for d, _ in scored[:5]]
    answer = generate_answer(top_docs, payload.question, llm=_openai_client)
    return answer
