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
# next Launch the API
# uvicorn src.app.api:app --reload --port 8000
```


# Start service
```bash
# 1) from project root
.\.venv\Scripts\activate         # <- windows ->
source .venv/bin/activate        # <— mac/linux activate

# 5) (Make sure MySQL and .env are set)
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