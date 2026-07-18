# RouteSarthi — Introduction

> This file, together with `ARCHITECTURE.md`, `DECISIONS.md`, and
> `CHALLENGES.md` in the repo root, is meant to be a **complete, standalone
> explanation of this project** — written so someone with zero prior context
> (a future engineer, an interviewer, or the author revisiting this in six
> months) can understand it without needing any conversation history.
> `README.md` (the original, shorter root readme) still exists alongside
> this file for anyone who just wants the quick-start commands.

## 1. What this project is

RouteSarthi is a travel-planning web app for train (and, secondarily,
bus/cab) journeys across India. The tagline used throughout the codebase is
**"Peace of mind, every time."**

### The real-world problem it solves

Existing Indian train-booking tools (IRCTC's own site, ixigo, RailYatri,
etc.) are built around one assumption: you search "from your city." That
assumption breaks down for a large fraction of India, where a traveler's own
town either has no railway station at all, or only a handful of weak,
usually-waitlisted trains. The nearby *better-connected* city — sometimes
50–200 km away — often has abundant, confirmed trains toward the same
destination, and the extra road hop to get there is a net win. Nobody
searches that way manually, because it requires knowing the regional rail
geography.

RouteSarthi's core differentiator, called **cross-origin routing** throughout
the code and docs, is to do that lookup automatically: given any two places
in India (not just major cities — any of ~8,000+ towns, or any of the
~8,900+ railway stations directly), it finds nearby "railheads" for both the
origin and destination, evaluates direct trains *and* one-transfer journeys
through busier hub stations, adds the road leg needed to reach that hub, and
ranks every resulting door-to-door option together.

Two further differentiators, in progressively earlier stages of being real:

- **Delay-aware connection safety** — when a journey requires changing
  trains, the app doesn't just check "is there enough time on paper," it
  estimates the probability that the *first* train's typical lateness would
  still let you catch the *second* one, using either a full year of measured
  historical delay data or (on a dated search) a trained ML model that
  conditions the delay distribution on day-of-week/month/position in the
  journey.
- **The "Lifeline"** — a live-journey mode with a "Save me!" button that is
  meant to re-route a traveler in real time if a leg is running late enough
  to jeopardize a connection. Today this exists only as a *scripted UI
  simulation* on the frontend (see §8 "Current status" — this is explicitly
  not real yet).

### Who it's for / the context it was built in

This is a **personal/portfolio project**, built solo, outside of any
internship or coursework program. It doubles as a technical showcase — the
repository maintains its own `ENGINEERING_NOTES.md` (deep, plain-language
write-ups of every hard bug and the reasoning behind each fix) and
`PROJECT_LOG.md` (a running changelog) specifically so the work is legible
and defensible in an interview setting later. There is no team; every
decision recorded in `DECISIONS.md` was a single person's call.

## 2. High-level: how it works

There are two halves that currently run somewhat independently and are
being merged together incrementally.

**The frontend** (`frontend/`) is a React single-page app. It was built
*first*, entirely against a **mock API** (via Mock Service Worker, MSW) that
serves three hand-written example corridors (Rourkela→Nashik,
Bhuj→Shimla, Imphal→Bengaluru) with fully fleshed-out fake data — routes,
legs, delay profiles, reasoning text, everything the UI needs to render. The
mock API's request/response shapes were deliberately frozen as a *contract*
(`frontend/API_CONTRACT.md`) that the real backend would later have to
reproduce byte-for-byte, so that swapping the mock for the real API wouldn't
require touching any page or component code — just flipping an environment
flag (`VITE_USE_REAL_API=true`).

**The backend** (`backend/`) is a Python/FastAPI service that was built
*second*, specifically to satisfy that frozen contract with real data
instead of fixtures. At startup it loads an entire national rail timetable
(~10,100 trains, ~200,000+ scheduled stops) into an in-memory data structure
(not because that's fashionable, but because an earlier version tried to do
the routing as SQL joins against Postgres and that took 80–100 seconds per
search — see `CHALLENGES.md`, Case Study 1). A search request geocodes the
two place names, finds nearby stations for each side, searches the in-memory
timetable for direct and one-transfer journeys, attaches a road ("first/last
mile") leg using either a real routing API or a straight-line estimate,
scores every candidate route on a handful of factors (time, cost,
reliability, connection safety, number of transfers), and returns the ranked
list in exactly the shape the frontend/mock contract defined.

Today the frontend talks to the real backend during local development (via
a Vite dev-server proxy forwarding `/api/*` requests to
`http://127.0.0.1:8000`), and personalization (accounts, saved trips, recent
searches) is fully real and backed by Postgres. The three original mock
corridors still exist as a documented fallback: if the backend can't
geocode a place, or the backend/database is unreachable at all, the
frontend transparently gets served the mock data for those three corridors
instead of an error.

## 3. Tech stack, and why each piece was chosen

### Frontend
| Piece | Why |
|---|---|
| **React 19** (plain JavaScript, no TypeScript) | Built solo, fast-iteration UI work; TypeScript was a deliberate omission for velocity in a one-person project, not an oversight. |
| **Vite** | Fast dev server + build; its built-in dev proxy (`vite.config.js`) is what lets the frontend call the real backend same-origin without configuring CORS during development. |
| **React Router v7** | Standard client-side routing; `RequireAuth` route wrapper gates every screen except the landing page and the auth flow. |
| **Zustand** (+ its `persist` middleware) | Minimal global state — four small stores (journey/search state and filters, auth session, theme, toasts) instead of Redux ceremony. |
| **Tailwind CSS v4** (via `@tailwindcss/vite`) | Utility-first styling; the project layers a full **semantic design-token system** on top (`bg-surface`, `text-content`, `text-muted`, …, defined once in `src/index.css`) so light/dark theming is a matter of flipping CSS variables, not chasing every component. |
| **MSW (Mock Service Worker)** | Lets the entire frontend be built and demoed with zero backend, by intercepting `fetch` calls at the network layer — indistinguishable from a real API to the rest of the app. |
| **MapLibre GL** (+ free OpenFreeMap tiles) | Open, no-API-key map rendering, used as the guaranteed-to-work fallback map. |
| **Mappls (MapMyIndia) SDK**, optional | A commercial India-accurate map provider, used when `VITE_MAPPLS_KEY` is set, specifically because OpenStreetMap/OpenFreeMap render India's Jammu & Kashmir/Ladakh/Arunachal Pradesh borders in the internationally-disputed style rather than India's official claimed borders — a real correctness/sensitivity issue for an India-focused product. Falls back to MapLibre automatically if the SDK fails to load. |
| **motion** (the `motion/react` package, formerly Framer Motion) | Page transitions, card reveals, the animated reliability gauge, the "how we found this route" decision-reasoning strip. |
| **lucide-react** | Icon set used throughout. |

### Backend
| Piece | Why |
|---|---|
| **Python + FastAPI** | Fast to write, automatic OpenAPI docs (`/docs`), good enough performance once the actual bottleneck (see below) was fixed. |
| **PostgreSQL + PostGIS**, hosted on **Supabase's free tier** | Chosen over local Docker specifically because **Docker is unavailable in the development environment used for this project** (confirmed by a live check — see `DECISIONS.md`). A hosted Postgres instance also means dev and (eventual) production share one database with no migration step. PostGIS is used only for its original purpose (nearest-station spatial queries) very early on; it was later replaced by an in-memory haversine scan for performance (see `CHALLENGES.md`), so PostGIS today is mostly vestigial infrastructure rather than a load-bearing dependency. |
| **psycopg3 + psycopg-pool** | Postgres driver + a small connection pool, warmed at server startup, specifically to avoid paying a fresh TLS+auth handshake to a database hosted in another country on every request. |
| **In-memory Python dictionaries** for the actual routing graph (`app/graph.py`) | The single most important architectural decision in the backend — see `DECISIONS.md` §1 and `CHALLENGES.md` Case Study 1. Real transit-routing engines (the Connection Scan Algorithm / RAPTOR family) work this way; a relational database is the wrong tool for repeated graph traversal. |
| **scikit-learn** (`HistGradientBoostingRegressor`, `IsotonicRegression`) | Used for two independent things: (1) predicting a *delay distribution* per train leg, conditioned on day-of-week/month/etc. — chosen over LightGBM (the roadmap's original pick) because it's the same histogram-gradient-boosting algorithm family with no native/OpenMP wheel to deploy, for effectively no accuracy cost; (2) fitting a monotonic (isotonic) regression of real fare vs. distance per travel class, replacing an earlier 50 km bucket-median approach. |
| **bcrypt + PyJWT** | Password hashing and stateless bearer-token sessions for the real (non-mock) auth system. |
| **httpx** | The one HTTP client used everywhere outbound: ETL downloads, the OpenRouteService/OSRM road-routing client, and the training-data fetchers. |
| **OpenRouteService (ORS)**, with self-hosted **OSRM** as an optional swap-in | Real road-routing distance/duration for the first/last-mile leg. ORS is a free-tier hosted API requiring only a signup, chosen as the *default* specifically because self-hosting OSRM needs Docker and a dedicated VM, which was more infrastructure than was worth taking on immediately (see `DECISIONS.md`). The code is written so that setting one environment variable (`OSRM_URL`) switches to self-hosted OSRM later with **zero code changes** — `OSRM_URL` takes priority over `ORS_API_KEY` when both are set. |
| **Brevo** (SMTP relay), for password-reset emails | Chosen over an initial attempt with Resend, whose free/no-domain "sandbox" sender can only email the developer's own inbox — useless for a real multi-user product. Brevo's free tier only requires verifying a single sender *email address* (no DNS) to send to anyone. See `CHALLENGES.md` P17. |
| **pytest** | 91 tests as of the most recent run — a mix of pure unit tests (always run, no infra needed) and DB-gated integration tests (skip gracefully via a `need_engine` fixture when there's no reachable database, so a fresh clone with no `.env` still runs a meaningful subset). |
| **GitHub Actions CI** (`.github/workflows/ci.yml`) | Runs the backend pytest suite and the frontend lint+build on every push/PR to `main`. No deploy step yet — deployment is a manual, not-yet-executed next phase (see §8). |

## 4. How to set it up and run it, on a clean machine

These are the exact commands; versions are pinned loosely in
`backend/requirements.txt` / `frontend/package.json` (e.g. Python's FastAPI
`>=0.115`, React `^19.2.7`). Developed and tested on Windows with Git Bash;
the commands below show the Windows venv-activation variant, with the
POSIX equivalent noted.

### 4.1 Backend, without any real data (fastest path — a demo on 3 fixed corridors)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows. POSIX: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- Health check: `http://127.0.0.1:8000/health`
- Interactive API docs: `http://127.0.0.1:8000/docs`
- Try it: `http://127.0.0.1:8000/api/routes?from=Rourkela&to=Nashik&pref=confirmed`

With no `.env` file at all, the server still boots and serves the three
seed/mock corridors — every route in the code that talks to the database or
the in-memory graph is wrapped so a missing/unreachable database degrades
to this fallback instead of crashing.

### 4.2 Backend, with the full real engine

```bash
cd backend
cp .env.example .env
# then edit .env: set DATABASE_URL to a Postgres+PostGIS connection string
# (a free Supabase project is the documented path — enable the postgis
# extension via `create extension postgis;` in its SQL editor)
python -m etl.init_auth_tables      # one-time: users/password_resets/saved_trips/recent_searches tables
uvicorn app.main:app --reload --port 8000
```

The first boot with a real database builds an in-memory graph cache file
(`data/processed/graph_cache.pkl`) from the database (~10–30s); every later
boot loads that cache file instead (~0.5s).

**Auth-specific setup:** signup/login will fail with a clear runtime error
until `SECRET_KEY` (any long random string, but it must be byte-identical
across every server process) is set in `.env`. Password-reset email
additionally needs `SMTP_USER`/`SMTP_PASSWORD`/`SMTP_FROM_EMAIL` (Brevo's
free tier — see `.env.example` for the exact steps); without them,
forgot-password still returns success but only logs the reset link to the
server console instead of emailing it.

**Real road-routing (optional):** set `ORS_API_KEY` in `.env` (free signup
at openrouteservice.org, documented step-by-step in `backend/README.md`).
Without it, or without `OSRM_URL`, first/last-mile road legs fall back to a
straight-line-distance estimate — the app functions correctly either way.

### 4.3 Rebuilding the database from scratch (only needed without a pre-populated DB)

This is a multi-step ETL pipeline, since the real timetable/fare/delay data
comes from several different downloadable sources, some requiring a manual
Kaggle login (Kaggle blocks scripted downloads):

```bash
cd backend
python etl/download.py              # auto-fetches the datameet + GeoNames sources into data/raw/
# ...manually download the Kaggle datasets listed by download.py's output
# into data/raw/candidates/... (see the script's docstring for exact paths)...
python -m etl.load_v2                # current (~2026) timetable -> trains/stops tables
python -m etl.load_fares             # real IRCTC fares -> app/data/fare_table.json
python -m etl.load_delays            # a full year of measured delays -> train_delays table
python -m etl.load_schedule_extra    # real per-stop distances + ~1,500 extra trains
python -m etl.train_delay_model      # optional: trains the ML delay-prediction model (~5-6 min)
python etl/verify.py                 # sanity-check row counts + core queries
```

Do **not** run `etl/load_all.py` — it is explicitly deprecated (it creates a
`trains` table missing columns the current engine requires) and is kept
only for historical reference.

### 4.4 Frontend

```bash
cd frontend
npm install
echo VITE_USE_REAL_API=true > .env.local   # talk to the real backend instead of the mock layer
npm run dev                                  # http://localhost:5173
```

Omitting the `.env.local` file (or setting the flag to anything but
`true`) makes the frontend run entirely against the MSW mock layer, with no
backend needed at all — this is also what happens automatically in a
production build unless the flag is baked in at build time.

Optional: set `VITE_MAPPLS_KEY` in `.env.local` to use the Mappls map
provider instead of the free MapLibre fallback.

### 4.5 Tests

```bash
cd backend && .venv\Scripts\python -m pytest -q
cd frontend && npm run lint && npm run build
```

The backend suite is safe to run with **no database connection at all** —
DB-gated tests are automatically skipped, not failed, via a `need_engine`
pytest fixture that checks `/health`'s reported graph-loaded state.

## 5. Folder / file structure

```
RouteSarthi/
├── README.md                    Original short root readme (quick-start + status)
├── Introduction.md               This file
├── ARCHITECTURE.md               Module/data-flow/algorithm deep dive
├── DECISIONS.md                  Every major technical decision + alternatives rejected
├── CHALLENGES.md                 Every significant bug/failure mode + fix, with diagnosis
├── PHASE_B_PLAN.md               The backend's original research + roadmap document
├── PROJECT_LOG.md                Running, dated changelog of every work session
├── ENGINEERING_NOTES.md          Deep case-studies of hard bugs (source material for CHALLENGES.md)
├── CLAUDE.md                     Instructions for AI coding-assistant tooling on this repo
├── .github/workflows/ci.yml      GitHub Actions: backend pytest + frontend lint/build
│
├── backend/
│   ├── README.md                 Backend-specific setup/runbook docs (incl. ORS/OSRM setup)
│   ├── requirements.txt          Python dependencies
│   ├── .env.example               Every configurable setting, documented inline
│   ├── docker-compose.yml        Local Postgres+PostGIS+Redis+OSRM stubs (mostly unused — see DECISIONS.md)
│   ├── app/
│   │   ├── main.py               FastAPI app: every HTTP endpoint (routes, auth, saved trips, recent searches)
│   │   ├── config.py             Settings loaded from .env (pydantic-settings)
│   │   ├── db.py                 Postgres connection + pool helper
│   │   ├── auth.py               Password hashing, JWT sessions, password-reset tokens
│   │   ├── email.py              Password-reset email via Brevo SMTP
│   │   ├── models.py             Pydantic schemas mirroring the frontend's API contract
│   │   ├── seed.py               The 3 mock/fallback corridors, ported from the frontend's mock fixtures
│   │   ├── graph.py               The in-memory rail-network graph + routing search (the routing "engine's engine")
│   │   ├── metrics.py             Delay/confirmation/fare/reliability scoring models
│   │   ├── delay_model.py         Loads + queries the trained ML delay-prediction model
│   │   ├── roads.py                Real road-routing client (OpenRouteService, or self-hosted OSRM)
│   │   ├── engine.py               Cross-origin search orchestration: geocoding → candidate generation → scoring → ranking
│   │   └── data/                  Small data artifacts shipped with the app (fare table, calendar, delay model, cumulative distances)
│   ├── etl/                       One-off/periodic data-loading scripts (see §4.3); each has a docstring explaining its role
│   └── tests/                     pytest suite (conftest.py + one file per module)
│
└── frontend/
    ├── README.md                  Frontend-specific docs
    ├── API_CONTRACT.md            The frozen mock-API shapes the real backend reproduces
    ├── package.json
    ├── vite.config.js             Build config + the dev-mode /api proxy to the backend
    └── src/
        ├── App.jsx                 Route table (which URL renders which page, and the auth gate)
        ├── main.jsx                 Entry point; decides whether to boot the MSW mock layer
        ├── index.css                 Tailwind theme + every semantic design token + light/dark values
        ├── pages/                    One file per screen (Onboarding, Auth, Search, Results, RouteDetail, LiveJourney, SavedTrips, Compare, HubPicker, ResetPassword)
        ├── components/                Every reusable UI piece (~35 files) — route cards, the map, the delay-model tooltip, the decision-reasoning animation, etc.
        ├── store/                    4 Zustand stores: useJourneyStore, useAuthStore, useThemeStore, useToastStore
        ├── lib/                       api.js (authenticated-fetch helper), utils.js (formatting + filter-matching helpers)
        ├── data/                      routes.js (mock fixtures, mirrors backend/app/seed.py), cityGeo.js, riskCalendar.js
        └── mocks/                     MSW handlers.js + browser.js (the mock API layer)
```

## 6. Current status: what's done, what's incomplete, what's known-broken

### Fully working today
- Cross-origin routing over the real national rail network (10,100+
  trains), with real fares (isotonic regression on scraped IRCTC price
  data), real per-stop distances, and a full year of measured delay data
  for 7,000+ trains.
- ML-predicted, date-conditioned delay distributions (mean + quantiles) for
  dated searches, with an honest confidence signal and a refusal to predict
  for journeys more than 1 day out (the model was measurably worse than the
  flat historical average there — see `CHALLENGES.md` P20).
- Real road-routing (distance/duration) for first/last-mile legs via
  OpenRouteService, with a graceful haversine-distance fallback and a
  circuit breaker + result cache to avoid hammering the free API tier or
  stalling on an outage.
- Real email+password accounts (bcrypt + JWT), server-owned saved trips and
  recent searches (Postgres, per-user), password reset via Brevo.
- A polished, fully responsive, light/dark-theming frontend with 9+ screens,
  an interactive map, and extensive motion/microcopy work.
- A CI pipeline (backend tests + frontend lint/build) on every push.

### Explicitly incomplete / deferred by design, not by accident
- **Seat-confirmation prediction is a heuristic, not ML**, and is meant to
  stay that way until a live PNR/booking-status data collector exists —
  there is currently no free source of real confirmation outcomes to train
  on, and the project's own engineering notes are explicit that training a
  model on zero real labels would be worse than an honest, transparent
  quota-rule heuristic.
- **The "Lifeline" live-monitoring / auto-reroute feature is a scripted
  frontend simulation**, not a real system. `LiveJourney.jsx` plays back a
  timed sequence of fake delay events and a fake re-route on any route the
  user opens — there is no live GPS/status feed behind it. This is Phase E
  in the project's own roadmap and has not been started.
- **Result caching and the transfer-route detail store are in-process, not
  persistent.** They reset on every server restart, and a transfer route's
  detail page (`/routes/:id`) can 404 after a restart until that corridor is
  searched again (direct routes are exempt — their IDs are rebuildable
  purely from the graph). Redis is the documented, not-yet-built fix.
- **`RAPIDAPI_KEY` is a reserved, unused configuration field.** It's wired
  into `config.py` and `.env.example` for a planned budget-guarded
  train-validity spot-check feature, but no code path actually calls it
  yet.
- **Learning-to-rank for the composite reliability score is not built** —
  the weights (e.g. 50% confirmation / 30% on-time / 20% first-mile-access
  for a direct route) are hand-set, not learned from real user behavior,
  because there's no click/booking data yet to learn from.
- **Deployment has not happened.** The app has never been deployed to a
  public URL; both frontend and backend currently only run locally. A
  deployment plan (Render for the backend, Vercel for the frontend) exists
  but has not been executed — see `DECISIONS.md` and `PROJECT_LOG.md` for
  the plan's details.
- **`frontend/src/components/JourneyBackdrop.jsx` is confirmed dead code**
  (zero imports anywhere in the codebase) — kept intentionally per an
  explicit earlier decision, not an oversight.
- **Bus/scheduled-transit data is not integrated.** Buses only ever appear
  as an undifferentiated "cab or bus" first/last-mile road option; there is
  no real bus timetable or GTFS integration.
- **Village-level (non-town) coverage via OpenStreetMap's Overpass API was
  planned but not built** — city/town coverage (~8,000 places via GeoNames,
  plus every railway station directly) is what actually exists.

### Known-fragile areas worth flagging to a new reader
See `CHALLENGES.md`'s final section for the full list with explanations;
briefly: the connection-wait calculation between two trains at a transfer
hub uses a `% 1440` (minutes-in-a-day) wraparound that cannot distinguish
"30 minutes later" from "30 minutes later, tomorrow," geocoding is
vulnerable to a class of GeoNames data-quality issues (duplicate same-named
places in the wrong state, sometimes with an inflated population that
would otherwise win a naive "most populous" tie-break) that required a
rail-aware disambiguation heuristic to work around, and the delay-model
training pipeline joins across three different bulk CSV data sources whose
station-code systems don't fully agree with each other or with the live
routing graph's own codes.
