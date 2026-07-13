# RouteSarthi — Backend (Phase B)

The routing + reliability engine. Reproduces the shapes in
[`../frontend/API_CONTRACT.md`](../frontend/API_CONTRACT.md) — first from seed
fixtures (Step 0), then from real data + the cross-origin engine (Step 1+).

See [`../PHASE_B_PLAN.md`](../PHASE_B_PLAN.md) for the full data map, algorithm,
and ML plan, and [`../PROJECT_LOG.md`](../PROJECT_LOG.md) for step-by-step
progress.

## Stack
Python · FastAPI · PostgreSQL + PostGIS · Redis · OpenRouteService (road
first/last-mile; self-hosted OSRM optional, see below). Trains-first;
buses/cabs are first/last-mile road legs.

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

## Maintenance — delay-prediction model staleness

`app/data/delay_model.joblib` is trained ONCE on a fixed data window (currently
Feb 2025–Feb 2026) — nothing retrains it automatically as real-world delay
patterns drift (schedule changes, new trains, seasonal shifts). Check
`GET /health`'s `delayModel.stale` field, or watch the backend startup log for
a `WARNING: delay_model.joblib is N days old` line
(`delay_model.STALE_AFTER_DAYS = 180`).

**When it's stale**, re-run:
```bash
python -m etl.train_delay_model     # ~5-6 min, streams the 1 GB delay dump
```
and restart the server (no code changes needed — it's a sidecar artifact, not
part of the graph cache). Re-run this whenever `combined_delay.csv` is
refreshed with a newer data window, or at that ~180-day mark, whichever comes
first. There's no scheduler wired up for this yet (no infra to run one) — it's
a manual step, made visible rather than silent.

## Real road-routing setup (OpenRouteService)

Road legs (first/last-mile access AND the standalone "direct by road" option)
use `app/roads.py` to get real routed distance/duration, falling back cleanly
to a haversine-distance estimate when nothing is configured or the service is
unreachable — this fallback is not a placeholder, it's a genuine,
always-available path (see `app/roads.py`'s circuit breaker: one failure
disables real routing for 30s so an outage can't slow every leg of every
search).

**OpenRouteService (ORS) is the default** — a hosted API, free tier (2000
requests/day), no Docker, no VM, no card. Takes about 5 minutes:

1. Go to [openrouteservice.org](https://openrouteservice.org) and sign up
   (free).
2. In your dashboard, create a new API key (the default "Free" token works).
3. Open `backend/.env` (copy from `.env.example` if you haven't yet) and set:
   ```
   ORS_API_KEY=<your key>
   ```
4. Restart the backend (`uvicorn app.main:app --reload --port 8000`). Search
   a corridor with a road leg (e.g. a first/last-mile access leg) — its
   duration/fare should now reflect real routed distance instead of the flat
   haversine estimate.

That's it — no further setup. **Add your key directly to `.env` yourself**;
don't paste it into chat or commit it.

### Optional, for later: self-hosted OSRM

If you ever want to remove ORS's rate limits, `app/roads.py` also supports a
self-hosted OSRM instance — **just set `OSRM_URL`**, no code changes, and it
takes priority over `ORS_API_KEY` automatically. Skip this section entirely
unless/until you want it.

OSRM needs a real India-wide routing graph in memory, which needs Docker —
unavailable on a typical Windows dev machine, so it runs on **one small
persistent VM**, shared by local dev and production (`OSRM_URL` set the same
way in both — same pattern already used for Supabase Postgres). Once you have
a VM (a small Ubuntu box on any provider — Oracle Cloud's Always-Free ARM
tier is genuinely free and has plenty of RAM; a small
DigitalOcean/Linode/Vultr droplet, ~$6-12/mo for 2-4GB RAM, is the
simpler-signup paid alternative):

```bash
# 1. Install Docker on the VM
curl -fsSL https://get.docker.com | sh

# 2. Download the India OSM extract (standard OSM community source, ~1-1.5 GB)
mkdir -p ~/osrm-data && cd ~/osrm-data
wget https://download.geofabrik.de/asia/india-latest.osm.pbf

# 3. Build the routing graph (MLD algorithm — memory-efficient for a
#    country-sized region; matches backend/docker-compose.yml's osrm service).
#    This is CPU-heavy — expect 15-60+ minutes depending on VM specs.
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-extract -p /opt/car.lua /data/india-latest.osm.pbf
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-partition /data/india-latest.osrm
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-customize /data/india-latest.osrm

# 4. Run it, surviving reboots
docker run -d --name osrm --restart unless-stopped -p 5000:5000 \
  -v "${PWD}:/data" osrm/osrm-backend osrm-routed --algorithm mld /data/india-latest.osrm

# 5. Verify directly (independent of this app)
curl "http://localhost:5000/route/v1/driving/77.209,28.6139;77.0266,28.4595"
```

No architecture-specific steps needed for an ARM VM (e.g. Oracle's) —
`osrm/osrm-backend` publishes multi-arch images. **Firewall note:** OSRM has
no built-in auth — restrict port 5000 at the VM's firewall to known caller
IPs where the provider allows it, rather than leaving it open to the world.

Then set `OSRM_URL=http://<vm-ip>:5000` in `backend/.env` (dev) and, later,
as a Render env var (prod) — no other code changes needed; `app/roads.py`
only cares about the URL. Test end-to-end: search a corridor with a road leg
and confirm its duration/fare changed from the ORS/haversine numbers.

If `docker-compose` happens to be available on the VM too, `backend/docker-compose.yml`'s
`osrm` service is an equivalent, already-defined alternative to steps 1-4
above (`docker compose up -d osrm` once the extract is downloaded and built).

## Layout
```
app/
  main.py      FastAPI app + contract + auth + personalization endpoints
  models.py    Pydantic schemas (the contract)
  auth.py      password hashing, JWT sessions, password-reset tokens
  email.py     password-reset email (SMTP via Brevo)
  seed.py      Step-0 fixtures (ported from the frontend mock)
```
