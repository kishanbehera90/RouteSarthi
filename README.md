# RouteSarthi

**Peace of mind, every time.** An AI-powered travel assistant that finds
*confirmed, reliable* ways to travel across India — even from poorly connected
towns — by routing you through nearby better-connected hubs, scoring
connections on delay history, and acting as a live lifeline if a leg breaks
mid-journey.

Monorepo: **[`frontend/`](frontend/)** (React) + **[`backend/`](backend/)**
(FastAPI engine). Progress is tracked in **[`PROJECT_LOG.md`](PROJECT_LOG.md)**,
hard-problem write-ups in **[`ENGINEERING_NOTES.md`](ENGINEERING_NOTES.md)**,
the roadmap in **[`PHASE_B_PLAN.md`](PHASE_B_PLAN.md)**.

## Where the project is (Jul 2026)

- **Phase A — frontend** ✅ complete (design system, dark mode, 9 screens,
  interactive map, live-journey sim, share).
- **Phase B — backend engine** 🔄 Steps 1–4 done: cross-origin routing over
  the **real** rail network (10,100+ trains — May-2026 timetable + gap-fill +
  1,511 trains recovered from a delay dataset), served from an in-memory graph
  (~0.8s cold, instant cached). Fares, distances, and on-time % are now
  **measured** (IRCTC price data + a year of real arrival records for 7,000+
  trains), not just modelled — only seat confirmation is still an honest
  "(est.)" pending a free PNR feed. Real per-class fares, corrected
  running-days (fixed a broken "everything is Daily" scrape bug),
  running-day filtering, autocomplete, decision-reasoning + Plan B, self-drawing
  map through real stations. Next: **ML delay prediction** (see Phase C in the
  log) and the collector.

---

## Run it (pull → running in ~3 minutes)

The frontend talks to the backend via a Vite dev proxy. Start the backend
first, then the frontend.

### 1. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                 # Windows  (source .venv/bin/activate on mac/Linux)
pip install -r requirements.txt
cp .env.example .env                     # then paste the team DATABASE_URL into .env
uvicorn app.main:app --reload --port 8000
```
- Health: http://127.0.0.1:8000/health  ·  Docs: http://127.0.0.1:8000/docs
- **No `.env`?** It still boots and serves the 3 seed corridors (engine falls
  back). For the full engine you need the team's Supabase `DATABASE_URL`.
- **First run with a DB** builds `data/processed/graph_cache.pkl` (~30s once,
  ~0.5s after). To rebuild the DB from scratch (rarely needed) see
  "Rebuild the database from scratch" below — it's now a multi-step pipeline
  (timetable → fares → delays → distances/extra trains).

### 2. Frontend
```bash
cd frontend
npm install
echo VITE_USE_REAL_API=true > .env.local   # use the real backend (omit to use mocks only)
npm run dev                                  # http://localhost:5173
```

### 3. Tests
```bash
cd backend && .venv\Scripts\python -m pytest -q     # 35 tests: metrics (pure, always run) + engine/contract (skip without a DB)
cd frontend && npm run lint && npm run build
```

## Rebuild the database from scratch (no team DB)

If you don't have the team's `DATABASE_URL`, stand up your own DB and load it:

1. **Get a Postgres + PostGIS database.** Easiest: a free
   [Supabase](https://supabase.com) project (enable the `postgis` extension in
   the SQL editor: `create extension postgis;`). Or run local infra:
   `cd backend && docker compose up -d` (needs Docker). Put the connection
   string in `backend/.env` as `DATABASE_URL` (use the **Session/Transaction
   pooler** string on Supabase, not the IPv6-only "Direct" one).
2. **Download the auto-fetchable sources** (datameet stations + GeoNames
   cities): `cd backend && python etl/download.py` → writes `data/raw/`.
3. **Manually download the Kaggle datasets** (login required — Kaggle blocks
   scripted download) into `backend/data/raw/candidates/`. Running
   `python etl/download.py` lists every file and reports which are missing:
   - `fresh-2026/IRCTC_cleaned.csv` — the current base timetable the engine
     runs on (~8.3k trains).
   - `irctc-2023/price_data.csv` (~124 MB) — real IRCTC fares (fare table).
   - `delay/combined_delay.csv` (~1 GB), `delay/combined_schedule.csv`,
     `delay/train_details.csv`, `delay/station_full_names.csv` — a full year of
     measured delays + a schedule with real per-stop distances.
   *(Exact dataset choices + why are in [`PROJECT_LOG.md`](PROJECT_LOG.md).)*
4. **Load it (in order):**
   - `python -m etl.load_v2` (~20s) — timetable → `trains`/`stops` tables.
   - `python -m etl.load_fares` — `price_data.csv` → `app/data/fare_table.json`.
   - `python -m etl.load_delays` (~5 min, streams 1 GB) — `train_delays` table,
     running-day corrections, seasonal-train detection.
   - `python -m etl.load_schedule_extra` — real per-stop distances
     (`app/data/train_cumdist.json`) + ~1,500 extra trains.
   Do **not** run the deprecated `load_all.py` — it breaks the current schema.
5. **Verify:** `python etl/verify.py` (row counts + core queries) and
   `python etl/benchmark.py` (duration sanity vs real trains).
6. **Run:** `uvicorn app.main:app --port 8000`. The first boot builds
   `data/processed/graph_cache.pkl` from the DB (~30s once); later boots load
   it in ~0.5s. (Delete the `.pkl` after any DB reload to force a rebuild.)

## Data & credentials

- `backend/.env`, `backend/data/`, `frontend/.env.local`, `graph_cache.pkl` are
  **gitignored** — share the `.env` privately (not in a group chat).
- Data sources (all free/open) and the freshness strategy: see
  [`PHASE_B_PLAN.md`](PHASE_B_PLAN.md) §4 and the changelog.

## For contributors

Every work session appends to `PROJECT_LOG.md`; every hard bug becomes a case
study in `ENGINEERING_NOTES.md` (P1–P11 so far). Keep that up — it's the team's
shared memory and the interview record.
