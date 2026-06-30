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

## Infra (Step 1 onward)
```bash
docker compose up -d        # Postgres+PostGIS + Redis
cp .env.example .env
```

## Layout
```
app/
  main.py      FastAPI app + contract endpoints
  models.py    Pydantic schemas (the contract)
  seed.py      Step-0 fixtures (ported from the frontend mock)
```
