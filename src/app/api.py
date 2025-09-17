from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal, init_db
from .models import Marking, MarkingToken, Place, Transition, Document
from .petri import get_enabled_transitions, fire_transition, get_marking_state, get_petri_graph
from .rag import petri_aware_retrieve, generate_answer

app = FastAPI(title="Witcher III RAG + PetriNet")
app.mount("/static", StaticFiles(directory="src/app/static"), name="static")

try:
    from openai import OpenAI

    _openai_client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
except Exception:
    _openai_client = None


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


@app.get("/petri/graph/data")
def petri_graph_data(db: Session = Depends(get_db)):
    return get_petri_graph(db)


@app.get("/", response_class=FileResponse)
def root_page():
    return FileResponse("src/app/static/index.html")


class AskIn(BaseModel):
    question: str
    marking_id: int | None = None
    depth: int = 2
    max_docs: int = 12


@app.post("/ask")
def ask(payload: AskIn, db: Session = Depends(get_db)):
    docs = petri_aware_retrieve(
        db,
        query=payload.question,
        marking_id=payload.marking_id,
        neighborhood_depth=payload.depth,
        max_docs=payload.max_docs,
    )
    answer = generate_answer(docs, payload.question, llm=_openai_client)
    return answer
