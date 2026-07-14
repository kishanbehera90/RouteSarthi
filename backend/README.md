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

### Self-hosted OSRM (primary road backend, ORS stays as the fallback)

`app/roads.py` tries backends as a chain: **OSRM (`OSRM_URL`) → ORS
(`ORS_API_KEY`) → haversine.** Setting `OSRM_URL` promotes a self-hosted OSRM
to primary (fast, no rate limit); ORS is automatically kept as a live safety
net for whenever OSRM's circuit breaker is open. Each backend has its own
breaker, so OSRM being down instantly falls through to ORS on the same call.

OSRM needs an India-wide routing graph in RAM (needs Docker — unavailable on a
typical Windows dev machine), so it runs on **one small persistent VM**, shared
by local dev and production (`OSRM_URL` set the same way in both — same pattern
as Supabase Postgres).

**Recommended host — Oracle Cloud Always Free ARM (Ampere A1).** As of
2026-06-15 the free allowance is **2 OCPU / 12 GB RAM** (halved from 4/24;
still ample — the India extract build peaks around ~7 GB). 200 GB free block
storage covers the ~10 GB of graph files easily.
- **Region:** pick **Mumbai (ap-mumbai-1)** or **Singapore (ap-singapore-1)** —
  closest to Indian users (lowest routing latency) AND the ARM tier provisions
  fastest there. Busy regions (US East) often return **"Out of host capacity"**
  for ARM; if so, try a different fault domain or one of the above regions.
- Create a **VM.Standard.A1.Flex** instance, Ubuntu 22.04, 2 OCPU / 12 GB.
- A paid DigitalOcean/Hetzner/Vultr box (~$6-12/mo, ≥4 GB RAM) is the
  simpler-signup alternative if Oracle capacity is unavailable.

```bash
# 1. Install Docker on the VM
curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER   # re-login after

# 1b. Safety-margin swap (cheap insurance so the ~7 GB extract can't OOM on 12 GB)
sudo fallocate -l 8G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 2. Download the India OSM extract (Geofabrik, ~1.3 GB)
mkdir -p ~/osrm-data && cd ~/osrm-data
wget https://download.geofabrik.de/asia/india-latest.osm.pbf

# 3. Build the routing graph (MLD — memory-efficient for a country-sized
#    region). CPU-heavy: ~20-60 min on 2 OCPU. osrm/osrm-backend is multi-arch,
#    so the same commands work on ARM (Oracle) and x86.
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-extract -p /opt/car.lua /data/india-latest.osm.pbf
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-partition /data/india-latest.osrm
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-customize /data/india-latest.osrm

# 4. Run it, surviving reboots
docker run -d --name osrm --restart unless-stopped -p 5000:5000 \
  -v "${PWD}:/data" osrm/osrm-backend osrm-routed --algorithm mld /data/india-latest.osrm

# 5. Verify locally on the VM (independent of this app)
curl "http://localhost:5000/route/v1/driving/77.209,28.6139;77.0266,28.4595?overview=false"
```

**⚠️ Oracle networking has TWO firewalls — both block port 5000 by default,
and this is the #1 reason "curl works on the VM but my backend can't reach
it":**
1. **Cloud security list / NSG** (in the OCI console): VCN → your subnet →
   Security List → add an **Ingress rule** for TCP **5000** from your
   backend's source (ideally the deploy host's IP, not `0.0.0.0/0`).
2. **Host firewall** (Oracle's Ubuntu images ship locked-down iptables):
   `sudo iptables -I INPUT -p tcp --dport 5000 -j ACCEPT` then persist it
   (`sudo netfilter-persistent save`, installing `iptables-persistent` if
   needed). OSRM has no built-in auth, so prefer restricting the source over
   opening it to the world.

Then set `OSRM_URL=http://<vm-public-ip>:5000` in `backend/.env` (dev) and as
a prod env var — no code changes; keep `ORS_API_KEY` set too so the fallback
survives an OSRM outage. Test end-to-end: search a corridor with a road leg
and confirm its duration/fare changed from the ORS/haversine numbers, and that
`/health`-style checks still pass if OSRM is stopped (falls through to ORS).

If `docker-compose` is available on the VM, `backend/docker-compose.yml`'s
`osrm` service is an equivalent, already-defined alternative to steps 3-4
(`docker compose up -d osrm` once the extract is downloaded).

## Layout
```
app/
  main.py      FastAPI app + contract + auth + personalization endpoints
  models.py    Pydantic schemas (the contract)
  auth.py      password hashing, JWT sessions, password-reset tokens
  email.py     password-reset email (SMTP via Brevo)
  seed.py      Step-0 fixtures (ported from the frontend mock)
```
