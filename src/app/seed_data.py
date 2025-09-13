# src/app/seed_data.py
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import SessionLocal, init_db
from .models import Place, Transition, Arc, Document

# ---------- Helpers ----------
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

# ---------- Seed graph ----------
def seed_story_graph(db: Session):
    """
    Builds a mainstream Petri-Net for TW3 with consequence-rich states.
    Places = in-game statuses (alive/dead, quest outcome, world-state flags)
    Transitions = events/choices that change those statuses
    """

    # === Prologue / Onboarding states ===
    p_start = upsert_place(db, "prologue_white_orchard", "Prologue — White Orchard",
                           "Tutorial + Griffin. Baseline world with no major consequences applied.")
    t_to_velen = upsert_transition(db, "to_velen_after_nilfgaard", "Sail/Travel to Velen",
                                   "Leave White Orchard; the Family Matters arc begins.")

    # === Velen: Family Matters / Ladies of the Wood (Whispering Hillock) ===
    # Core beats
    p_fm_active = upsert_place(db, "family_matters_active", "Velen — Family Matters ongoing",
                               "Following Ciri’s trail via the Bloody Baron’s family.")
    t_meet_baron = upsert_transition(db, "meet_bloody_baron", "Meet the Bloody Baron", "Begin Family Matters properly.")

    # Botchling / Lubberkin choice produces guidance but not major global flag
    p_baby_lubberkin = upsert_place(db, "baby_turned_lubberkin", "Botchling laid to rest (Lubberkin)",
                                    "Performed the ritual; spirit guides you to clues at Crow’s Perch.")
    p_baby_killed = upsert_place(db, "baby_killed", "Botchling killed",
                                 "You chose to kill the botchling. Fewer clues; rougher outcomes in Velen.")
    t_baby_ritual = upsert_transition(db, "ritual_baby_choice", "Botchling choice",
                                      "Choose ritual (Lubberkin) or kill the botchling.")

    # Whispering Hillock major branch
    t_wh_free = upsert_transition(db, "free_whispering_hillock", "Free the spirit under the Hillock",
                                  "Release the spirit; consequences ripple into Anna/Bloody Baron line and Crookback Bog.")
    t_wh_kill = upsert_transition(db, "kill_whispering_hillock", "Kill the spirit under the Hillock",
                                  "Kill the spirit; different consequences in Crookback Bog.")

    p_spirit_freed = upsert_place(db, "spirit_freed", "Whispering Hillock — Spirit freed",
                                  "Some orphans may live, but Anna is cursed harsher; Baron’s line worsens.")
    p_spirit_killed = upsert_place(db, "spirit_killed", "Whispering Hillock — Spirit killed",
                                   "Fate of orphans grim, but Anna’s outcome differs; Baron line resolves differently.")

    # Anna/Baron consequence states (mainstream outcomes)
    t_crookback_confront = upsert_transition(db, "crookback_bog_confrontation", "Confrontation at Crookback Bog",
                                             "Resolves Anna/Baron arc depending on Hillock decision.")
    p_anna_alive_broken = upsert_place(db, "anna_alive_broken", "Anna alive but broken",
                                       "Spirit freed → Anna heavily cursed; Baron attempts to take her away.")
    p_baron_hangs = upsert_place(db, "baron_commits_suicide", "Baron dead (suicide)",
                                 "Often follows freeing the spirit; dark consequence for Velen line.")
    p_anna_dies = upsert_place(db, "anna_dies", "Anna dies",
                               "Spirit killed path can lead to Anna’s death depending on choices.")
    p_baron_leaves = upsert_place(db, "baron_leaves_with_anna", "Baron leaves with Anna for treatment",
                                  "Generally tied to killing the spirit and mitigating the curse.")

    # Wiring Velen
    add_arc_pt(db, p_start, t_to_velen);               add_arc_tp(db, t_to_velen, p_fm_active)
    add_arc_pt(db, p_fm_active, t_meet_baron)          # next place is still fm_active (we'll branch on baby)
    add_arc_tp(db, t_meet_baron, p_fm_active)

    add_arc_pt(db, p_fm_active, t_baby_ritual);        add_arc_tp(db, t_baby_ritual, p_baby_lubberkin)
    add_arc_pt(db, p_fm_active, t_baby_ritual);        add_arc_tp(db, t_baby_ritual, p_baby_killed)

    add_arc_pt(db, p_fm_active, t_wh_free);            add_arc_tp(db, t_wh_free, p_spirit_freed)
    add_arc_pt(db, p_fm_active, t_wh_kill);            add_arc_tp(db, t_wh_kill, p_spirit_killed)

    # Consequent confrontation
    add_arc_pt(db, p_spirit_freed, t_crookback_confront);   add_arc_tp(db, t_crookback_confront, p_anna_alive_broken)
    add_arc_pt(db, p_spirit_freed, t_crookback_confront);   add_arc_tp(db, t_crookback_confront, p_baron_hangs)
    add_arc_pt(db, p_spirit_killed, t_crookback_confront);  add_arc_tp(db, t_crookback_confront, p_anna_dies)
    add_arc_pt(db, p_spirit_killed, t_crookback_confront);  add_arc_tp(db, t_crookback_confront, p_baron_leaves)

    # === Novigrad spine: Pyres/Get Junior/Triss choice (Mages) ===
    p_novi_main = upsert_place(db, "novigrad_mainline", "Novigrad — Mainline active",
                               "Pyres of Novigrad, Get Junior, Triss/Radovid strands intersect here.")
    t_to_novigrad = upsert_transition(db, "to_novigrad", "Travel to Novigrad", "Advance to Novigrad arc.")
    add_arc_pt(db, p_fm_active, t_to_novigrad);        add_arc_tp(db, t_to_novigrad, p_novi_main)

    # Whoreson Junior outcome (not world-scale, but referenced by FAQs)
    t_whoreson_spare = upsert_transition(db, "spare_whoreson", "Spare Whoreson Junior")
    t_whoreson_kill = upsert_transition(db, "kill_whoreson", "Kill Whoreson Junior")
    p_whoreson_spared = upsert_place(db, "whoreson_spared", "Whoreson spared", "Minor later scenes differ.")
    p_whoreson_killed = upsert_place(db, "whoreson_killed", "Whoreson killed", "Minor later scenes differ.")
    add_arc_pt(db, p_novi_main, t_whoreson_spare);      add_arc_tp(db, t_whoreson_spare, p_whoreson_spared)
    add_arc_pt(db, p_novi_main, t_whoreson_kill);       add_arc_tp(db, t_whoreson_kill, p_whoreson_killed)

    # Triss — help mages or not
    t_help_triss = upsert_transition(db, "help_triss_escape", "Help Triss evacuate mages",
                                     "Aid mages at the docks; affects later scenes.")
    t_refuse_triss = upsert_transition(db, "refuse_triss", "Refuse to help Triss",
                                       "Refuse aid; fewer allies and scenes shift.")
    p_mages_saved = upsert_place(db, "mages_evacuated", "Novigrad mages evacuated",
                                 "Mages escape Novigrad; contributes to later tone/allies.")
    p_mages_abandoned = upsert_place(db, "mages_abandoned", "Novigrad mages abandoned",
                                     "Darker Novigrad; fewer mage allies.")
    add_arc_pt(db, p_novi_main, t_help_triss);          add_arc_tp(db, t_help_triss, p_mages_saved)
    add_arc_pt(db, p_novi_main, t_refuse_triss);        add_arc_tp(db, t_refuse_triss, p_mages_abandoned)

    # === Skellige: Lord of Undvik, King’s Gambit (Cerys vs Hjalmar) ===
    p_skellige_open = upsert_place(db, "skellige_open", "Skellige — Mainline open",
                                   "Sail to Skellige and progress its quests.")
    t_to_skellige = upsert_transition(db, "sail_to_skellige", "Sail to Skellige", "Travel to the Isles.")
    add_arc_pt(db, p_novi_main, t_to_skellige);         add_arc_tp(db, t_to_skellige, p_skellige_open)

    # King’s Gambit outcome
    t_crown_cerys = upsert_transition(db, "crown_cerys", "Crown Cerys an Craite",
                                      "Cerys becomes Queen; stability improves across Skellige.")
    t_crown_hjalmar = upsert_transition(db, "crown_hjalmar", "Crown Hjalmar an Craite",
                                        "Hjalmar becomes King; more warlike tone.")
    p_cerys_queen = upsert_place(db, "cerys_queen", "Cerys crowned Queen", "Stable Skellige outcome.")
    p_hjalmar_king = upsert_place(db, "hjalmar_king", "Hjalmar crowned King", "More martial Skellige.")
    add_arc_pt(db, p_skellige_open, t_crown_cerys);     add_arc_tp(db, t_crown_cerys, p_cerys_queen)
    add_arc_pt(db, p_skellige_open, t_crown_hjalmar);   add_arc_tp(db, t_crown_hjalmar, p_hjalmar_king)

    # === Keira Metz sub-branch (affects Battle of Kaer Morhen) ===
    p_keira_unknown = upsert_place(db, "keira_unknown", "Keira Metz — unresolved",
                                   "After ‘Hunting a Witch’/‘Wandering in the Dark’.")
    t_send_keira_kaer = upsert_transition(db, "send_keira_to_kaer_morhen", "Send Keira to Kaer Morhen",
                                          "Persuade Keira to help at Kaer Morhen (lives, aids battle).")
    t_keira_killed = upsert_transition(db, "keira_killed", "Kill Keira Metz",
                                       "Confrontation ends in her death; she won’t help later.")
    p_keira_ally = upsert_place(db, "keira_will_help", "Keira will fight at Kaer Morhen",
                                "Alive and recruited.")
    p_keira_dead = upsert_place(db, "keira_dead", "Keira dead", "Unavailable for later battle.")
    add_arc_pt(db, p_novi_main, t_send_keira_kaer);     add_arc_tp(db, t_send_keira_kaer, p_keira_ally)
    add_arc_pt(db, p_novi_main, t_keira_killed);        add_arc_tp(db, t_keira_killed, p_keira_dead)
    # Optional unresolved node connects from early Novigrad too:
    add_arc_pt(db, p_novi_main, t_help_triss);          # allows traversal reach

    # === Ugly Baby → Battle of Kaer Morhen ===
    p_uma_brought = upsert_place(db, "uma_at_kaer_morhen", "Uma at Kaer Morhen",
                                 "‘Ugly Baby’ complete; preparations underway.")
    t_ugly_baby = upsert_transition(db, "bring_uma", "Bring Uma to Kaer Morhen",
                                    "Trigger the Kaer Morhen preparation arc.")
    add_arc_pt(db, p_skellige_open, t_ugly_baby);       add_arc_tp(db, t_ugly_baby, p_uma_brought)

    p_battle_km = upsert_place(db, "battle_of_kaer_morhen", "Battle of Kaer Morhen",
                               "Defense against the Wild Hunt begins.")
    t_defend_km = upsert_transition(db, "defend_kaer_morhen", "Defend Kaer Morhen")
    add_arc_pt(db, p_uma_brought, t_defend_km);         add_arc_tp(db, t_defend_km, p_battle_km)

    # Allies toggles influencing the battle (Keira example already modeled)
    p_km_allies_boost = upsert_place(db, "km_allies_boost", "Allies: Boosted",
                                     "Represents having recruited multiple allies (Keira, Roche, Zoltan, etc.).")
    t_sum_allies = upsert_transition(db, "sum_allies", "Allies tallied",
                                     "Abstract event that accumulates allies' presence as a boost flag.")
    # Connect plausible ally inputs:
    add_arc_pt(db, p_keira_ally, t_sum_allies);         add_arc_tp(db, t_sum_allies, p_km_allies_boost)
    add_arc_pt(db, p_mages_saved, t_sum_allies);        add_arc_tp(db, t_sum_allies, p_km_allies_boost)

    # === Final Preparations → Through Time and Space → End ===
    p_final_prep = upsert_place(db, "final_preparations", "Final Preparations",
                                "Novigrad wrap-up before the last arc.")
    t_to_final_prep = upsert_transition(db, "to_final_preparations", "Move to Final Preparations")
    add_arc_pt(db, p_battle_km, t_to_final_prep);       add_arc_tp(db, t_to_final_prep, p_final_prep)

    p_worlds = upsert_place(db, "through_time_and_space", "Through Time and Space",
                            "Follow Avallac’h across worlds.")
    t_worlds = upsert_transition(db, "go_worlds", "Go with Avallac’h")
    add_arc_pt(db, p_final_prep, t_worlds);             add_arc_tp(db, t_worlds, p_worlds)

    p_final = upsert_place(db, "tedd_deireadh", "Tedd Deireadh, The Final Age", "Endgame lead-in.")
    t_final = upsert_transition(db, "final_confrontation", "Final confrontation with Eredin")
    add_arc_pt(db, p_worlds, t_final);                  add_arc_tp(db, t_final, p_final)

    # === Global politics (Radovid/Dijkstra) affects epilogues/world tone ===
    p_radovid_alive = upsert_place(db, "radovid_alive", "Radovid alive", "Redania dominance persists.")
    p_radovid_dead = upsert_place(db, "radovid_dead", "Radovid assassinated", "Nilfgaard likely prevails.")
    t_kill_radovid = upsert_transition(db, "kill_radovid", "Assassinate Radovid",
                                       "Side with Roche/Thaler/Ves; opens Dijkstra confrontation.")
    t_spare_radovid = upsert_transition(db, "spare_radovid", "Spare Radovid", "Redania continues under Radovid.")
    add_arc_pt(db, p_novi_main, t_kill_radovid);        add_arc_tp(db, t_kill_radovid, p_radovid_dead)
    add_arc_pt(db, p_novi_main, t_spare_radovid);       add_arc_tp(db, t_spare_radovid, p_radovid_alive)

    # Dijkstra aftermath (simplified)
    p_dijkstra_rules = upsert_place(db, "dijkstra_rules", "Dijkstra seizes power", "If you side with him after Radovid.")
    p_roche_survives = upsert_place(db, "roche_survives", "Roche survives", "If you oppose Dijkstra’s coup.")
    t_side_dijkstra = upsert_transition(db, "side_with_dijkstra", "Side with Dijkstra")
    t_stop_dijkstra = upsert_transition(db, "stop_dijkstra", "Oppose Dijkstra")
    add_arc_pt(db, p_radovid_dead, t_side_dijkstra);    add_arc_tp(db, t_side_dijkstra, p_dijkstra_rules)
    add_arc_pt(db, p_radovid_dead, t_stop_dijkstra);    add_arc_tp(db, t_stop_dijkstra, p_roche_survives)

    # === Ciri fate determinants (abstracted as toggle places via micro-choices) ===
    # We model them as cumulative morale/agency toggles to help the RAG reason about outcomes.
    p_ciri_confident = upsert_place(db, "ciri_confidence_up", "Ciri confidence boosted",
                                    "Sum of positive choices: snowball, lab alone, visit grave, etc.")
    p_ciri_shaken = upsert_place(db, "ciri_confidence_down", "Ciri confidence shaken",
                                 "Sum of negative choices: scold at Lodge, take payment from Emperor, etc.")
    t_ciri_up = upsert_transition(db, "ciri_positive_choice", "Encourage Ciri (positive choice)")
    t_ciri_down = upsert_transition(db, "ciri_negative_choice", "Undercut Ciri (negative choice)")
    # Allow these toggles during Final Preparations:
    add_arc_pt(db, p_final_prep, t_ciri_up);            add_arc_tp(db, t_ciri_up, p_ciri_confident)
    add_arc_pt(db, p_final_prep, t_ciri_down);          add_arc_tp(db, t_ciri_down, p_ciri_shaken)

    # === Endings (simplified mainstream set) ===
    p_ciri_witcher = upsert_place(db, "ending_ciri_witcher", "Ending — Ciri becomes a witcher",
                                  "High confidence + certain political outcomes.")
    p_ciri_empress = upsert_place(db, "ending_ciri_empress", "Ending — Ciri becomes Empress",
                                  "If introduced to Emperor and world settled under Nilfgaard.")
    p_ciri_dies = upsert_place(db, "ending_ciri_dies", "Ending — Ciri dies",
                               "Low morale and poor choices.")
    t_epilogue = upsert_transition(db, "compute_epilogue", "Resolve Ciri’s fate",
                                   "Abstract epilogue computation from toggles + politics.")

    # Wire ending influences
    add_arc_pt(db, p_final, t_epilogue)
    add_arc_pt(db, p_ciri_confident, t_epilogue);       add_arc_tp(db, t_epilogue, p_ciri_witcher)
    add_arc_pt(db, p_radovid_dead, t_epilogue);         add_arc_tp(db, t_epilogue, p_ciri_empress)
    add_arc_pt(db, p_ciri_shaken, t_epilogue);          add_arc_tp(db, t_epilogue, p_ciri_dies)

    # === Example “level / item” status nodes (useful for FAQs/puzzles) ===
    p_level16plus = upsert_place(db, "level_16_plus", "Character Level ≥ 16",
                                 "Many mid-game quests are tuned around ~16.")
    p_ancient_sword_destroyed = upsert_place(db, "ancient_sword_destroyed", "Quest item destroyed",
                                             "Represents a puzzle/quest outcome where an item can be lost (abstract).")
    t_ding16 = upsert_transition(db, "reach_level_16", "Reach level 16")
    t_break_item = upsert_transition(db, "destroy_ancient_sword", "Destroy the ancient sword")
    add_arc_pt(db, p_novi_main, t_ding16);              add_arc_tp(db, t_ding16, p_level16plus)
    add_arc_pt(db, p_skellige_open, t_break_item);      add_arc_tp(db, t_break_item, p_ancient_sword_destroyed)

    # Return some anchors if needed elsewhere
    return {
        "start": p_start,
        "novigrad": p_novi_main,
        "skellige": p_skellige_open,
        "final": p_final,
    }

# ---------- Seed documents (FAQ/RAG) ----------
def seed_documents(db: Session):
    """
    Curated, short original notes for FAQs:
    - how to do X (puzzles/quests),
    - what happens if I choose Y,
    - state explanations tied to places/transitions.
    """
    docs = [
        # Velen — Family Matters
        ("Family Matters: Botchling vs Lubberkin — which is better?",
         "If you perform the naming ritual and turn the botchling into a lubberkin, it guides you to more clues peacefully. "
         "Killing it is faster but yields fewer leads and a harsher tone with the Baron.",
         "family_matters_active", None, {"topic":"faq","spoiler":"low","consequence":"branching"}),

        ("Whispering Hillock: free or kill the spirit?",
         "Freeing the spirit can save some innocents but worsens Anna's fate and the Baron's line; killing the spirit "
         "tends to spare Anna differently but has grim implications for others. Choose based on which consequence you prefer.",
         None, "free_whispering_hillock", {"topic":"faq","spoiler":"medium","consequence":"major"}),

        ("Crookback Bog confrontation outcomes",
         "The confrontation at Crookback Bog resolves the Baron/Anna arc. Results depend on your Hillock decision: "
         "spirit freed often leads to Anna surviving but broken and the Baron's despair; spirit killed can lead to Anna's death but the Baron departing to seek help.",
         "family_matters_active", "crookback_bog_confrontation", {"topic":"faq","spoiler":"high","consequence":"major"}),

        # Novigrad — puzzles/how-to + choices
        ("Wandering in the Dark: how to solve the mirror/portal puzzle",
         "Follow symbols of the swallow and switch to portals marked with the swallow icon. If you hit dead ends with "
         "gargoyles, backtrack to the prior junction and choose the other swallow-marked portal.",
         "novigrad_mainline", None, {"topic":"howto","spoiler":"low","quest":"Wandering in the Dark"}),

        ("Help Triss at the docks — does it matter?",
         "Helping Triss evacuate the mages changes Novigrad's tone, preserves allies, and affects later scenes. "
         "Refusing leads to darker outcomes and fewer allies.",
         "novigrad_mainline", "help_triss_escape", {"topic":"faq","spoiler":"medium","consequence":"allies"}),

        ("Whoreson Junior: spare or kill?",
         "Sparing Whoreson preserves a pitiful version of him and minor later scenes. Killing him removes those scenes. "
         "It has little impact on the grand plot.",
         None, "kill_whoreson", {"topic":"faq","spoiler":"low","consequence":"minor"}),

        # Skellige — King's Gambit outcomes
        ("King’s Gambit: should I crown Cerys or Hjalmar?",
         "Cerys favors a steadier, domestic-oriented Skellige with less bloodshed; Hjalmar leans into valor and conflict. "
         "Pick Cerys for stability or Hjalmar for a harsher, warlike tone. Neither blocks the main quest.",
         "skellige_open", "crown_cerys", {"topic":"faq","spoiler":"medium","consequence":"regional"}),

        # Keira Metz branch and Kaer Morhen
        ("Keira Metz: convince her to go to Kaer Morhen or fight her?",
         "Convincing Keira to go to Kaer Morhen keeps her alive and she helps during the battle. Fighting and killing her "
         "removes a potential ally and darkens the Novigrad arc.",
         None, "send_keira_to_kaer_morhen", {"topic":"faq","spoiler":"medium","consequence":"allies"}),

        ("Battle of Kaer Morhen: how to prepare well",
         "Recruit as many allies as you can (e.g., Keira, Zoltan, Roche). Upgrade bombs/oils and repair gear. "
         "Complete ‘Ugly Baby’ to unlock preparations. More allies = easier defense.",
         "battle_of_kaer_morhen", None, {"topic":"howto","spoiler":"medium","consequence":"difficulty"}),

        # Politics — Radovid/Dijkstra
        ("Should I assassinate Radovid?",
         "Killing Radovid topples Redania’s tyranny and paves the way for Nilfgaard to control the North, triggering the Dijkstra decision. "
         "Sparing him keeps Redania dominant under harsh rule.",
         None, "kill_radovid", {"topic":"faq","spoiler":"high","consequence":"world"}),

        ("Dijkstra coup: side with him or stop him?",
         "Siding with Dijkstra grants him control (efficient but ruthless). Opposing him preserves Roche and friends. "
         "This choice colors the epilogue but doesn't prevent the main ending path.",
         "final_preparations", "side_with_dijkstra", {"topic":"faq","spoiler":"high","consequence":"world"}),

        # Ciri fate — guidance (no heavy spoilers)
        ("How do my choices influence Ciri’s fate?",
         "Encouraging Ciri (let her decide, support her privately, avoid taking credit or payment on her behalf) "
         "raises her confidence. Undermining her lowers it. These small choices, plus politics, shape her ending.",
         "final_preparations", "ciri_positive_choice", {"topic":"faq","spoiler":"medium","consequence":"ending"}),

        ("Can Ciri become a witcher or Empress?",
         "High confidence and certain decisions can lead Ciri to a witcher path. If you involve the Emperor and the world "
         "stabilizes under Nilfgaard, she can become Empress. Poor support can lead to a tragic end.",
         "tedd_deireadh", "compute_epilogue", {"topic":"faq","spoiler":"high","consequence":"ending"}),

        # Level & Item (utility)
        ("Recommended level for Novigrad/Skellige arcs?",
         "Novigrad mainline plays comfortably around level 10–16; Skellige arcs around mid-teens and up. "
         "Gear up as needed and check individual quest level suggestions.",
         "level_16_plus", None, {"topic":"faq","spoiler":"none","utility":"leveling"}),

        ("I accidentally destroyed a quest item — am I stuck?",
         "Most critical items cannot be permanently lost; vendors or quest steps usually restore progress. "
         "If something breaks, revisit the quest giver or re-check the marked area for a replacement path.",
         "ancient_sword_destroyed", None, {"topic":"faq","spoiler":"none","utility":"fail-safe"}),
    ]

    for title, content, place_key, transition_key, tags in docs:
        rp = db.scalar(select(Place).where(Place.key == place_key)) if place_key else None
        rt = db.scalar(select(Transition).where(Transition.key == transition_key)) if transition_key else None
        db.add(Document(
            title=title,
            content=content,
            related_place_id=rp.id if rp else None,
            related_transition_id=rt.id if rt else None,
            tags=tags
        ))

# ---------- Entrypoint ----------
def seed():
    init_db()
    db = SessionLocal()
    try:
        anchors = seed_story_graph(db)
        seed_documents(db)
        db.commit()
        print("Seeded Witcher 3 Petri-Net with consequence-rich mainstream paths and FAQs.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
