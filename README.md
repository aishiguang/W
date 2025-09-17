# W for **W**itcher (III)
This project is a **W**itcher III FAQ. It connects to OpenAI for NLP.
It is a RAG system with **Petri-Net**, which enabling its storyline awareness.
# Classical Petri Net semantics *W* for *incidence matrix*
* ***W**⁻(p,t)* = number of tokens that transition $t$ requires from place *p*.
* ***W**⁺(p,t)* = number of tokens that transition $t$ produces into place *p*.
* A transition *t* is enabled if and only if for all input places *p*:


# init demo data
```bash
# 1) Create & activate venv
python -m venv .venv
.\.venv\Scripts\activate         # <- windows ->
source .venv/bin/activate        # <— mac/linux activate
# 2) Install deps
pip install -r requirements.txt
# 3) Copy .env.example to .env and adjust DATABASE_URL (if needed)
# 4) Seed the database
python -m src.app.seed_data
# next install frontend tooling & launch the API
# npm install
# npm run build:ts
# uvicorn src.app.api:app --reload --port 8000
```


# Start service
```bash
# 1) from project root
.\.venv\Scripts\activate         # <- windows ->
source .venv/bin/activate        # <— mac/linux activate

# 5) (Make sure MySQL and .env are set)
npm install
npm run build:ts
uvicorn src.app.api:app --reload --port 8000
```

# Try it
```bash
curl -X POST http://127.0.0.1:8000/ask ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"Who is the Bloody Baron and how does it relate to Ciri?\"}"

# adjust depth if you want broader context

-d "{\"question\":\"What happens around Ugly Baby and the Battle of Kaer Morhen?\",\"depth\":3}"
```
It should anwer something like this: (retrieved documents based on petri-net interpretation)
```JSON
{
    "answer": "The Bloody Baron, also known as Philip Strenger, is a key character in [Family Matters]. He is the lord of Crow's Perch and is deeply troubled by the disappearance of his wife, Anna, and the transformation of their child into a botchling. His storyline intertwines with Ciri's as Geralt's actions regarding the Baron can influence Ciri's fate and the overall narrative. The outcomes of the Baron’s arc, particularly the decisions made at Crookback Bog, can affect the emotional state of Ciri and the world around her, ultimately shaping her confidence and potential paths, such as becoming a witcher or an Empress.",
    "sources": [
        {
            "id": 13,
            "title": "Can Ciri become a witcher or Empress?"
        },
        {
            "id": 12,
            "title": "How do my choices influence Ciri’s fate?"
        },
        {
            "id": 3,
            "title": "Crookback Bog confrontation outcomes"
        },
        {
            "id": 11,
            "title": "Dijkstra coup: side with him or stop him?"
        },
        {
            "id": 1,
            "title": "Family Matters: Botchling vs Lubberkin — which is better?"
        }
    ]
}
```

---
