from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .db import SessionLocal, init_db
from .petri import get_enabled_transitions, fire_transition, get_marking_state
from .models import Marking, MarkingToken, Place, Transition, Document
from .rag import petri_aware_retrieve, generate_answer
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

# --------- Petri endpoints (unchanged) ---------
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

# --------- New /ask that infers “latent” state & traverses Petri ---------
class AskIn(BaseModel):
    question: str
    marking_id: int | None = None
    depth: int = 2  # how far to traverse the graph for context
    max_docs: int = 12

@app.post("/ask")
def ask(payload: AskIn, db: Session = Depends(get_db)):
    docs = petri_aware_retrieve(
        db,
        query=payload.question,
        marking_id=payload.marking_id,   # optional; not required for FAQ mode
        neighborhood_depth=payload.depth,
        max_docs=payload.max_docs
    )
    answer = generate_answer(docs, payload.question, llm=_openai_client)
    return answer
