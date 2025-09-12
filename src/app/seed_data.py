from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import SessionLocal, init_db
from .models import Place, Transition, Arc, Document

def upsert_place(db: Session, key: str, name: str, desc: str = "") -> Place:
    p = db.scalar(select(Place).where(Place.key == key))
    if not p:
        p = Place(key=key, name=name, description=desc)
        db.add(p)
        db.flush()
    return p

def upsert_transition(db: Session, key: str, name: str, desc: str = "") -> Transition:
    t = db.scalar(select(Transition).where(Transition.key == key))
    if not t:
        t = Transition(key=key, name=name, description=desc)
        db.add(t)
        db.flush()
    return t

def add_arc_pt(db: Session, p: Place, t: Transition, w: int = 1):
    db.add(Arc(source_place_id=p.id, target_transition_id=t.id, weight=w))

def add_arc_tp(db: Session, t: Transition, p: Place, w: int = 1):
    db.add(Arc(source_transition_id=t.id, target_place_id=p.id, weight=w))

def seed():
    init_db()
    db = SessionLocal()
    try:
        # Places (very high-level beats)
        p_white = upsert_place(db, "white_orchard", "Prologue — White Orchard")
        p_velen = upsert_place(db, "baron_family_matters", "Velen — Family Matters")
        p_novigrad = upsert_place(db, "novigrad_main", "Novigrad — Pyres of Novigrad")
        p_skellige = upsert_place(db, "destination_skellige", "Sail to Skellige")
        p_ugly = upsert_place(db, "ugly_baby", "Ugly Baby — Kaer Morhen")
        p_battle = upsert_place(db, "battle_kaer_morhen", "Battle of Kaer Morhen")
        p_finalprep = upsert_place(db, "final_preparations", "Final Preparations")
        p_worlds = upsert_place(db, "through_time_space", "Through Time and Space")
        p_final = upsert_place(db, "tedd_deireadh", "Tedd Deireadh, The Final Age")
        p_epilogues = upsert_place(db, "epilogues", "Endings (Ciri outcomes)")

        # Transitions (events)
        t_arrive = upsert_transition(db, "arrive_white_orchard", "Arrive in White Orchard")
        t_meet_baron = upsert_transition(db, "meet_baron", "Meet the Bloody Baron")
        t_investigate_nov = upsert_transition(db, "investigate_novigrad", "Investigate in Novigrad")
        t_sail = upsert_transition(db, "sail_to_skellige", "Sail to Skellige")
        t_ugly = upsert_transition(db, "summon_ugly_baby", "Bring Uma to Kaer Morhen")
        t_defend = upsert_transition(db, "defend_kaer_morhen", "Defend Kaer Morhen")
        t_prep = upsert_transition(db, "hunt_ermen", "Hunt the Crone/Eredin leads")
        t_worlds = upsert_transition(db, "go_avalacch_worlds", "Follow Avallac'h through worlds")
        t_final = upsert_transition(db, "final_confrontation", "Final confrontation")

        # Arcs: linear chain (you can branch later)
        add_arc_pt(db, p_white, t_meet_baron);      add_arc_tp(db, t_meet_baron, p_velen)
        add_arc_pt(db, p_velen, t_investigate_nov); add_arc_tp(db, t_investigate_nov, p_novigrad)
        add_arc_pt(db, p_novigrad, t_sail);         add_arc_tp(db, t_sail, p_skellige)
        add_arc_pt(db, p_skellige, t_ugly);         add_arc_tp(db, t_ugly, p_ugly)
        add_arc_pt(db, p_ugly, t_defend);           add_arc_tp(db, t_defend, p_battle)
        add_arc_pt(db, p_battle, t_prep);           add_arc_tp(db, t_prep, p_finalprep)
        add_arc_pt(db, p_finalprep, t_worlds);      add_arc_tp(db, t_worlds, p_worlds)
        add_arc_pt(db, p_worlds, t_final);          add_arc_tp(db, t_final, p_final)
        # optional: move token to epilogues after final
        add_arc_pt(db, p_final, t_final);           add_arc_tp(db, t_final, p_epilogues)

        # A few documents (short, lore-friendly summaries—expand later)
        docs = [
            ("Who is the Bloody Baron?",
             "A warlord ruling Crow's Perch in Velen. His questline 'Family Matters' involves his missing wife and daughter and intersects with Ciri's trail.",
             "baron_family_matters"),
            ("What happens in Ugly Baby?",
             "Geralt brings Uma to Kaer Morhen. The witchers and Yennefer attempt to lift the curse, revealing crucial information about Ciri.",
             "ugly_baby"),
            ("What is the Battle of Kaer Morhen?",
             "A major defense of the witcher stronghold against the Wild Hunt. Many allies can participate depending on prior choices.",
             "battle_kaer_morhen"),
            ("What are the possible endings for Ciri?",
             "Ciri's fate varies based on key choices. Outcomes range from becoming a witcher to becoming Empress, or a tragic end.",
             "epilogues"),
            ("Why go to Skellige?",
             "Leads suggest Ciri was seen on the Skellige Isles. Traveling there advances the main quest and opens new leads.",
             "destination_skellige"),
        ]
        for title, content, place_key in docs:
            place = db.scalar(select(Place).where(Place.key == place_key))
            db.add(Document(title=title, content=content, related_place_id=place.id, related_transition_id=None, tags={"topic":"faq"}))

        db.commit()
        print("Seeded Petri Net and documents.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
