# RouteSarthi — Backend (Phase B)

The routing + reliability engine. Reproduces the shapes in
[`../frontend/API_CONTRACT.md`](../frontend/API_CONTRACT.md) — first from seed
fixtures (Step 0), then from real data + the cross-origin engine (Step 1+).

See [`../PHASE_B_PLAN.md`](../PHASE_B_PLAN.md) for the full data map, algorithm,
and ML plan, and [`../PROJECT_LOG.md`](../PROJECT_LOG.md) for step-by-step
progress.

## Stack
Python · FastAPI · PostgreSQL + PostGIS · Redis · self-hosted OSRM (road
first/last-mile). Trains-first; buses/cabs are first/last-mile road legs.

## Run (Step 0 — scaffold, no DB needed)
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Try: http://localhost:8000/api/routes?from=Rourkela&to=Nashik&pref=confirmed

## Full engine (Step 1 — real data)
```bash
cp .env.example .env         # then set DATABASE_URL (team Supabase, or local Docker below)
python etl/download.py       # fetch raw data into data/raw/ (gitignored)
python etl/load_all.py       # load Postgres/PostGIS (~2 min)
python etl/verify.py         # sanity-check counts + core queries
uvicorn app.main:app --reload --port 8000
```
Without a `.env`, the server still boots and serves the 3 seed corridors —
the engine gracefully falls back. First boot with a DB builds
`data/processed/graph_cache.pkl` (~30s once, ~0.5s after).

Local infra alternative (if you have Docker):
```bash
docker compose up -d        # Postgres+PostGIS + Redis
```

## Auth + personalization (signup/login, saved trips, recent searches)
```bash
python -m etl.init_auth_tables     # one-time: creates users/password_resets/saved_trips/recent_searches
```
Also needs in `.env` (see `.env.example`):
- `SECRET_KEY` — any long random string. Must be **identical across every
  server process** (a per-process auto-generated one would cause
  intermittent, worker-dependent 401s) — so unlike `DATABASE_URL`, this fails
  loudly rather than degrading gracefully. Everything except signup/login/
  saved-trips/recent-searches still works without it.
- `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM_EMAIL` — for password-reset
  emails, via Brevo's free SMTP relay (300/day, no domain verification
  needed — just a single verified sender email). Without these,
  forgot-password still responds 200 but only logs the reset link instead of
  emailing it. See ENGINEERING_NOTES.md P17 for why Brevo over Resend.

## Layout
```
app/
  main.py      FastAPI app + contract + auth + personalization endpoints
  models.py    Pydantic schemas (the contract)
  auth.py      password hashing, JWT sessions, password-reset tokens
  email.py     password-reset email (SMTP via Brevo)
  seed.py      Step-0 fixtures (ported from the frontend mock)
```
