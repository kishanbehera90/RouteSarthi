# RouteSarthi — Project Log

A running, step-by-step record of everything built and everything planned,
updated as the project progresses. Phases map to
[`PHASE_B_PLAN.md`](PHASE_B_PLAN.md) and the original product plan.

> **Deep dives:** detailed, plain-language case studies of the hard problems
> (with diagnosis, the fix, *why* that fix, and measured impact — written for
> interview prep) live in **[`ENGINEERING_NOTES.md`](ENGINEERING_NOTES.md)**.

Legend: ✅ done · 🔄 in progress · ⏳ planned · ⏸️ deferred

---

## Phase A — Frontend clickable prototype (mock data) — ✅ COMPLETE (deploy deferred)

A responsive React app on a mock API, demonstrating the full product story end
to end. Lives in `frontend/`.

### Foundation
- ✅ Vite + React 19 (JavaScript) + React Router + Zustand + Tailwind CSS v4.
- ✅ MSW mock API layer; endpoint shapes frozen as the backend contract
  (`frontend/API_CONTRACT.md`).
- ✅ Mock data fixtures for 3 corridors (Rourkela→Nashik, Bhuj→Shimla,
  Imphal→Bengaluru) with routes, legs, connections, delay profiles, reasoning.
- ✅ Monorepo restructure: app moved under `frontend/` (room for `backend/`).
- ✅ `VITE_USE_REAL_API` flag to switch mocks off without code changes.

### Design system & theming
- ✅ Brand identity: indigo `brand`, semantic `safe`/`caution`/`risk`, `mist`
  accent, `sand` neutrals; Clash Display + Inter type.
- ✅ Semantic design tokens (`surface`, `content`, `muted`, `line`, …) with a
  full **light/dark mode** (class-based, persisted, no-FOUC inline script).
- ✅ Custom SVG logo/wordmark; vertical rail; route-doodle motifs.
- ✅ Component vocabulary: RouteCard, ReliabilityBadge, ConfirmationPill,
  LegTimeline, WhyThisRoute, PlanBChip, PreferenceControl, FiltersPanel,
  ModeIcon, EyebrowLabel, ArrowButton, BackLink, Skeleton, Toaster.

### Screens
- ✅ Onboarding (hero, 3 pillars, cinematic band, footer).
- ✅ Login (phone + OTP mock auth, persisted).
- ✅ Search (hero, from/to, compact risk-aware date picker, preference control,
  popular corridors).
- ✅ Results (decision-reasoning animation, sort + filters sidebar, route grid).
- ✅ Compare (direct vs cross-origin).
- ✅ Hub Picker (origin-hub options).
- ✅ Route Detail (animated reliability gauge with tappable breakdown,
  interactive map, full leg timeline with on-time bars, Plan B, per-leg booking
  deep-links, save, share).
- ✅ Live Journey / Lifeline (animated journey simulation: moving map dot,
  per-leg states, scripted delay events, auto Plan-B, "Save me!",
  play/pause/restart).
- ✅ Saved Trips (persisted; photographic empty state).

### Signature features
- ✅ **Cross-origin reasoning** — animated "how we found this route" strip
  (direct fails → hubs scanned → winner).
- ✅ **Delay-aware confidence** — reliability score + breakdown (confirmation ·
  on-time · connection safety); per-leg waitlist-clearance prediction widget.
- ✅ **The lifeline** — full live-journey simulation with auto reroute.
- ✅ Risk Calendar (seasonal travel-risk heatmap folded into the date picker).
- ✅ Interactive route map (MapLibre + free OpenFreeMap tiles, brand-tinted,
  self-drawing line, mode badges, live-mode pulsing dot; lazy-loaded).
- ✅ Share journey (Web Share API + clipboard, screenshot-friendly card).
- ✅ Motion throughout (page transitions, card reveals, count-up gauge,
  animated bars), reduced-motion respected.
- ✅ Loading skeletons on every async screen; toast feedback system.
- ✅ On-brand photography (hero + empty states) with indigo tint treatment.
- ✅ Working filters incl. avoid-late-night; preference re-sorting.

### Phase A — remaining
- ⏸️ Deploy to a shareable URL — **deferred**: will deploy frontend + backend
  together once the backend is ready.

### Known minor cleanups (non-blocking, tracked)
- README leads with a Hindi tagline (UI is correctly all-English).
- Mock "no-service" direct route (Imphal) sorts first under cheapest/fastest
  (₹0/0min) — needs sentinel values or exclusion.
- A couple of no-op hover states and a leftover tint token on Route Detail.
- Tiny copy typo in the share card; one redundant import.
- Unused `framer-motion` dependency (standardised on `motion`).

---

## Phase B — Backend routing + reliability engine — ✅ ~COMPLETE (collector deferred)

Strategy: multi-modal (road competes with rail) · free/open data only · every
city (~8k towns). Full detail in [`PHASE_B_PLAN.md`](PHASE_B_PLAN.md).
Lives in `backend/`.

> **Status (2026-07-08):** Steps 1, 3, 4, 5 are done and the reliability layer
> moved from *modelled* to **measured** — real IRCTC fares, real per-stop
> distances, and a full year of measured delays (7,024 trains); only seat
> **confirmation** stays modelled ("est.") because no free PNR feed exists.
> Step 2 (the collector) is intentionally **deferred** — no real users to
> collect from yet. See the 2026-07-08 changelog entries for the full detail;
> the step notes below are the original historical record.

- ✅ **Step 0 — Scaffold.** FastAPI app serving the API contract from seed
  fixtures (ported from the frontend mock). Health + all 4 endpoints
  (`/api/corridors`, `/api/corridors/:id`, `/api/routes`, `/api/routes/:id`),
  correct `pref` sorting, 404s, and `from` alias. Verified two ways: (1) an
  in-process contract smoke test, and (2) a real `.venv` + `uvicorn` server
  hit over live HTTP — confirmed correct sorting per `pref`
  (confirmed/cheapest/fastest), correct 404s, correct UTF-8 byte-level
  encoding, CORS scoped to the frontend dev origin, and `/docs` +
  `/openapi.json` reachable. Docker Compose (Postgres+PostGIS + Redis) and
  Pydantic contract models in place for the next steps.
- ✅ **Database provisioned.** Postgres + PostGIS hosted on Supabase's free
  tier (chosen over local Docker/native Postgres since Docker isn't available
  in the local dev environment, and a hosted DB doubles as the production
  database later — no migration needed). PostGIS extension enabled and
  verified (v3.3.7) alongside Postgres 17.6. Connection lives in `backend/.env`
  (gitignored, never committed). **Gotchas hit and resolved** (useful if a
  teammate sets this up too): (1) a DB password containing special characters
  broke URL parsing — fixed by using an alphanumeric-only password; (2)
  Supabase's "Direct connection" host is IPv6-only and fails to resolve on
  IPv4-only networks — use the "Session" or "Transaction" pooler connection
  string instead; (3) one network (a college/institutional connection) blocked
  outbound port 5432 entirely — the Transaction pooler's port 6543 worked
  once switched to a different network. Verified via a connection script that
  checks Postgres + PostGIS without ever printing the connection string.
- 🔄 **Step 1 — Cross-Origin v1.** Data layer DONE + engine WORKING; perf
  optimization pending.
  - ✅ **Data loaded into Postgres/PostGIS** (ETL `backend/etl/load_all.py`,
    fast COPY, ~106s): 8,990 stations (w/ geo + per-station train-density),
    417,080 stops, 5,208 trains, **557,994 cities/towns/villages** (GeoNames
    India, class P — true "every city" coverage, not just metros). Sources are
    free/open (datameet CC0; GeoNames CC-BY); downloaded into `data/raw/`
    (gitignored). Verified via `backend/etl/verify.py` (counts, geocoding,
    PostGIS nearest-railhead, direct-train generation).
  - ✅ **Cross-origin engine** (`backend/app/engine.py`, endpoint `/api/search`):
    geocode any place → candidate railheads (nearest stations UNION nearest
    major hubs, so remote origins find the real gateway, not dead-end halts) →
    single-train journeys AND one-transfer journeys via busy hubs (feasible
    same-day connection window) → first/last-mile road legs (straight-line
    heuristic) → multi-factor ranking (time / cost / train-density / transfers,
    `pref`-aware) → contract-shaped routes with generated "why". Proven on all
    three flagship corridors on REAL data: Rourkela→Nashik (direct trains),
    Bhuj→Shimla (via Ahmedabad Jn, 1 change), Imphal→Bengaluru (via Howrah Jn).
  - ✅ **PERFORMANCE FIXED (architecture rewrite).** Root cause of the ~80–100s
    transfer latency was doing routing as huge SQL self-joins on the 417k-row
    `stops` table (with ~2k-element IN-lists), over the network, multiple times
    per request. Fix: load the whole timetable into memory **once**
    (`app/graph.py`) and route as in-memory scans; the DB now only does what
    it's good at (PostGIS nearest-railhead + geocoding, one indexed query each).
    Routing itself measured at **0.06 ms** (down from ~100s) on a synthetic
    network with correctness assertions (direct + one-transfer found, infeasible
    <30-min connection correctly filtered). Per-request cost is now ~the geocode
    + railhead DB round-trips (~1s cold) + instant routing; an in-process result
    cache makes repeats instant. One-time graph load (~10–30s) runs at server
    startup (FastAPI lifespan) so the first real request is already warm.
    **Live end-to-end confirmed over HTTP:** first API request **0.85s**,
    subsequent cold **~0.79s**, cached repeats **0.02s** — vs ~100s before.
    Further wins applied after the first benchmark: (a) **nearest-railhead moved
    in-memory** too (haversine over 8.7k stations, sub-ms) — eliminated the two
    heavy PostGIS spatial queries per request; (b) **geocode index fix** — the
    `OR lower(name)` clause was forcing a 558k-row seq scan, added
    `cities_name_lower_idx`; (c) **local graph cache** (`data/processed/
    graph_cache.pkl`) — startup dropped 37s→0.47s and removed a fragile 417k-row
    fetch over the pooler on every boot (the pooler intermittently dropped it:
    "lost synchronization"); DB build has a 3× retry; (d) **connection pool**
    (psycopg_pool) warmed at startup — killed the per-request TLS/auth cost
    (first request 6s→0.85s); (e) **in-process result cache**. Net per-request
    cost is now ~2 geocode round-trips to the Tokyo DB (network latency only) +
    instant in-memory routing.
  - ✅ **Connection-safety prior** — `connectionSafetyPct` (previously empty) now
    filled by a transparent buffer→probability curve (logistic: ~54% at 60min,
    ~91% at 120min, ~97% at 180min+; null below the 30-min min buffer), and
    folded into transfer-route reliability so risky connections rank lower.
    Replaced by per-train historical delay distributions in Step 3.
  - ✅ **Route diversification** — caps near-identical options (≤2 per hub, 1 per
    hub+first-train) so distinct hubs/trains surface instead of six variations of
    the same journey.
  - ⚠️ **Remaining limitations:** (1) **OSRM not yet wired** — first/last-mile
    uses straight-line distance, not real road time/cost. (2) **`reliability` is
    still a connectivity heuristic** until delay (Step 3) + confirmation (Step 4)
    data/ML land. (3) Extremely remote multi-change cases may need a 2nd transfer.
  - ✅ **Frontend connected to the live engine (verification slice of Phase C).**
    `/api/routes` + `/api/routes/:id` are now engine-backed (with a route store
    so the detail page can resolve dynamically-generated route ids); legs carry
    real station coordinates so the map draws for real stations. Frontend uses a
    Vite dev proxy (`/api` → `127.0.0.1:8000`) + `VITE_USE_REAL_API=true`
    (`.env.local`) to bypass MSW. Verified in-browser: Search → Results → Route
    Detail (gauge + leg timeline + map with 7–9 real markers) all run on live
    data for any Indian city pair.
  - ⏳ **Remaining for Step 1:** OSRM wiring, ranking tuning, generate the
    hub-scan `reasoning` for the decision animation, then formally unify
    `/api/search` into `/api/routes`.
- ⏳ **Step 2 — Data collector.** Daily live-status + PNR snapshots.
- ✅ **Step 3 — Delay-aware scoring — now MEASURED.** Started as a model in
  `app/metrics.py` (delay + on-time% from class/priority/length/halts); as of
  2026-07-08 it uses a **full year of real observed delays** (`train_delays`,
  7,024 trains, avg/p50/p80/p90/on-time%) with the model as fallback, tagged
  `delaySource: measured | modelled`. Connection safety uses the incoming
  train's measured distribution; the min transfer buffer now covers its p50
  delay. See ENGINEERING_NOTES P13/P15 + the 2026-07-08 changelog.
- 🟡 **Step 4 — Confirmation — MODELLED by design (honest ceiling).**
  `confirmationPct` + state from a demand proxy (class scarcity, train priority,
  lead-time, peak season), labelled "est." in the UI. Stays modelled until the
  collector gathers PNR data — no free availability feed exists. This is the
  intended final state for now, not a gap.
- ✅ **Fares — now MEASURED.** Real IRCTC median fare per (class, distance band)
  from `price_data.csv` (`app/data/fare_table.json`, `metrics.rail_fare`), over
  real per-stop distances; modelled surcharge structure only as fallback.
- ✅ **Step 5 — Composite ranking + explainability.** Reliability breakdown
  (measured vs "est." factors), dynamic `why`, date-aware Plan B, seasonal-train
  gating, and a reliability-tie preference for friction-free direct routes.

---

## Phase C — Wire frontend ↔ real backend — 🔄 STARTED (local verification done)
A working local slice is done (dev proxy + engine-backed `/api/routes`,
`.env.local` turns MSW off — see Step 1). Remaining for full Phase C: replace
the `fetch` calls with TanStack Query (caching/loading/error states), a proper
API base-URL config for deploy (not just a dev proxy), and emit corridor
`reasoning` so the decision animation works on real searches.

### Phase C — ML roadmap (added 2026-07-08, once the measured-data layer landed)
The 2026-07-08 data upgrade (fares, distances, delays → measured; see the
changelog entry below) is what unlocks real ML — before it, `metrics.py` had
no labelled dataset to fit a model to. Ranked by value ÷ effort, using data we
already have on disk **now** (no collector needed to start):

1. **Delay prediction — ✅ DONE (2026-07-13).** `etl/train_delay_model.py` →
   scikit-learn HistGradientBoosting (chosen over LightGBM: same algorithm, no
   native-dep deploy risk), predicting a coherent distribution (mean + quantiles)
   from serve-time-safe features (baseline + day-of-week + month + position +
   scheduled hour). `delaySource:"predicted"` tier in `metrics.leg_delay_profile`,
   fired on dated searches. MAE 26.9 vs 29.3 flat-baseline; near-perfect quantile
   calibration. 1.7 MB sidecar artifact, no infra. NOTE vs the original sketch
   below: "upstream delay" was dropped (it's a live signal, not knowable at plan
   time — the train's historical baseline substitutes). See ENGINEERING_NOTES P18.
2. **Connection safety as a learned probability — ✅ DONE (2026-07-13).**
   `metrics.connection_safety` now reads the arriving train's predicted quantile
   CDF at the buffer (a coherent P(delay≤buffer)), falling back to the old
   exponential when a leg isn't predicted. Realised as a CDF rather than a
   fixed-threshold classifier so it answers any buffer and stays consistent with
   the displayed p50/p90. Also fixed the latent avg-vs-p50 split. See P18.
   - **Bonus (not on the original list): demand-aware fare advisory.** The user
     asked for "price by festival/weekend". Train fares are regulated (fixed) so
     there's no varying target to ML — instead, a festival/holiday calendar drives
     a real flexi-fare multiplier for premium dynamic-fare trains + a scarcity
     advisory, all "est."-labelled. See ENGINEERING_NOTES P19.
3. **Seat confirmation model** — the one number still honestly labelled
   "(est.)". Needs booking/PNR snapshots we don't have yet; **blocked on the
   collector** (Phase B Step 2, deferred — no real users to collect from). Do
   not attempt without that data; a model trained on nothing is worse than an
   honest heuristic.
4. **Learning-to-rank** for the composite `reliability` weights (currently
   hand-set 50/30/20 etc.) — needs real user click/booking feedback. Deferred
   with the collector, same reason as #3.

Items 1 & 2 shipped 2026-07-13. Items 3 & 4 remain blocked on the collector.

## Phase D — Confidence layer — ⏳ PLANNED
Stronger confirmation prediction, comfort/safety filters, split-ticketing.

## Phase E — Lifeline (real) — ⏳ PLANNED
Live per-leg monitoring, auto Plan-B triggers, GPS reroute, push (PWA).

## Phase F — Community & growth — ⏳ PLANNED
Travel-buddy, carpool deep-links, festival intelligence, more modes, monetisation.

## Deployment — ⏸️ DEFERRED
Frontend + backend deployed together at the end. (Vercel note: frontend root
must be set to `frontend/`.)

---

## Changelog
- **2026-07-15 (first deploy: Render + Vercel, and two deploy-only bugs)** —
  backend live on Render (free tier; graph cache committed so cold starts skip
  the ~30s rebuild; UptimeRobot pings `/health` every 5min to prevent the
  15min free-tier sleep), frontend live on Vercel (`vercel.json` rewrites
  `/api/*` to Render — same-origin, no CORS). Two bugs only visible once
  actually deployed (neither showed up in 116 local tests) — full writeup in
  ENGINEERING_NOTES P23:
  1. **SPA routing broken.** A custom `vercel.json` silently disables Vercel's
     default SPA fallback, so every direct link (including the emailed
     password-reset link) hit a static 404 before React Router loaded. Fixed
     with a second rewrite (`/((?!api/).*) -> /index.html`), confirmed safe
     against static assets via Vercel's filesystem-first rewrite behavior.
  2. **Password-reset emails always "timed out."** Render blocks ALL outbound
     SMTP ports (25/465/587) on its free tier (Sep 2025 policy) — no amount of
     correct Brevo SMTP config can get past a blocked port. Switched
     `app/email.py` from raw `smtplib` to Brevo's HTTPS transactional-email
     API (same provider/tier, travels over 443, which is never blocked).
     `BREVO_API_KEY` replaces `SMTP_HOST/PORT/USER/PASSWORD` in config/env.
  +5 tests (email.py had zero coverage before) -> 116 pass.
- **2026-07-14 (pre-deploy security hardening pass)** — five-part sweep before
  going live:
  1. **Tiered rate limiting** (`app/ratelimit.py` `limiter()` dependency): STRICT
     on auth (login 15/IP + 8/email per 5min checked *before* bcrypt, signup
     5/IP/hr, forgot/reset 10/IP/hr), MODERATE on public (search 30/min,
     reads 60/min, autocomplete 120/min), LOOSE on authed actions (100/min).
     `/health` stays unlimited so the uptime pinger never trips it.
  2. **Strict input validation:** a `StrictModel` base with `extra="forbid"`
     (unknown fields rejected, not ignored) + bounded lengths on every body;
     query params typed (`pref` is a `Literal`, `date` a regex, place names
     capped); `SaveTripRequest.route` size-capped (storage-DoS guard).
  3. **Secret scan:** no hardcoded keys/passwords in source or any tracked file;
     `.env`/`.env.local` gitignored and never committed in history. Only client
     var shipped is `VITE_MAPPLS_KEY` (a map SDK key — public by design;
     domain-restrict it in the Mappls console).
  4. **Dependency audit:** `npm audit` 0 vulns; `pip-audit` clean after bumping
     `pip` (the one flagged package — a tool, not a runtime dep) to 26.1.2.
  5. **Error handling:** a global exception handler logs full tracebacks
     server-side but returns a generic message — clients never see stack traces,
     file paths, or raw DB errors. Curated messages on all intentional 4xx.
  +9 tests (validation, rate-limit wiring, generic-500) -> 111 pass.
- **2026-07-13 (OSRM real road-routing wired in, plus CI)** — `osrm_url` had
  been a config field since Phase B, read by zero runtime code; all road-leg
  numbers (first/last-mile access + the standalone direct-road option) were
  haversine-distance arithmetic with flat constants. New `app/osrm.py` — a
  thin `httpx` client mirroring `delay_model.py`'s graceful-degradation
  contract (returns `None` on any failure, never raises) — plus
  `engine._road_km_mins()` wiring in both call sites, with the haversine
  fallback now consistently getting the `ROAD_ROUTE_FACTOR` correction that
  first/last-mile legs had been missing entirely (only the standalone
  direct-road option had it before).
  - **Environment reality check:** neither this dev environment nor the
    user's own machine has Docker, so self-hosted OSRM (the project's
    original plan) can't run locally at all — it needs one persistent cloud
    VM, shared by dev and prod via `OSRM_URL`, exactly like Supabase Postgres
    already works. Complete setup runbook in `backend/README.md`; `docker-
    compose.yml`'s OSRM service definition completed/uncommented as the
    equivalent container spec for that VM.
  - **A real bug found by testing the failure path, not just the happy
    path:** smoke-tested against OSRM's public demo server first (worked —
    real routed distances came back sensibly different from the haversine
    guess), then deliberately pointed `OSRM_URL` at a refused connection to
    test resilience. A single failed call took **~2.9s** before failing —
    without a fix, a search with a dozen-plus road legs would pay that cost
    once PER LEG, and every subsequent search would pay it again for as long
    as OSRM stayed down (one test request hung past 20s). Added a circuit
    breaker: one failure disables OSRM for a 30s cooldown, auto-recovers
    after. Verified: first search after a failure = 3.19s total (pays the
    cost once); the next search = 1.03s (breaker open, zero network calls).
    See ENGINEERING_NOTES P22.
  - **Minimal CI added** (`.github/workflows/ci.yml`): backend `pytest -q`
    (pure tests always run; DB-gated ones skip gracefully without a
    `DATABASE_URL` secret) + frontend `lint`/`build`, on every push/PR to
    `main`. No deploy step — Render/Vercel will handle that independently
    once connected.
  - Tests: +18 (OSRM client mocked success/failure/circuit-breaker, engine
    fallback logic) → 88/88 passing.
  - **Deployment (Render + Vercel) is next**, now that `OSRM_URL` is a real
    production env var to set alongside the others.
- **2026-07-14 (pivot: OpenRouteService as default road-routing backend, OSRM
  demoted to switch-on-later)** — user found the self-hosted OSRM runbook
  (VM provisioning, Docker, multi-step graph build) too heavy to want to run
  right now. Rebuilt `app/osrm.py` into `app/roads.py`: a dual-backend router
  that tries `OSRM_URL` first (unchanged), then falls back to a new
  `ors_api_key`-based OpenRouteService client (hosted API, free tier, 5-minute
  signup, zero infra) — with neither configured, or either unreachable, it
  still returns `None` and callers fall back to haversine, same contract as
  before. Setting `OSRM_URL` alone (no code changes) switches the app to
  self-hosted OSRM later, since it's tried first. `backend/README.md`
  restructured to lead with the simple ORS signup steps; the OSRM VM runbook
  is now clearly marked optional/for-later. Tests: renamed/added for the new
  module (`test_roads.py` replaces `test_osrm.py`) → 91/91 passing.
  - **Live verification caught a second real bug:** once the user added a
    real `ORS_API_KEY`, a live search of a cross-origin corridor started
    logging `429 Too Many Requests` from ORS mid-search. Cause: several
    candidate routes in one search share the same first/last-mile city pair
    (e.g. every SAMBALPUR-hub route needs the identical "MANMAD JN → Nashik"
    leg) — each was firing its own independent network call for the same
    coordinates, burning through ORS's free-tier rate limit on pure
    duplicates within a single request. Fix: an in-memory cache in
    `roads.py` keyed on rounded coordinates, caching only successful lookups
    (failures still go through the existing circuit breaker so a transient
    outage can recover). Verified: a cold search of a new corridor takes
    ~15s (each distinct leg pays one real network call); a repeat search of
    the same corridor takes ~1s (cache hit, zero network calls) — and the
    429s stopped entirely. Confirmed end-to-end in the browser too: the
    route-detail page for Rourkela→Nashik via SAMBALPUR now shows "~221 km
    road to SAMBALPUR" — the real ORS-routed distance, not the haversine
    guess. Tests updated to reset the cache between cases → still 91/91.
  Deployment is next.
- **2026-07-13 (fare accuracy: isotonic regression, not IRCTC scraping)** —
  asked for "a program that finds real fares per route." Declined to build an
  IRCTC scraper (ToS-prohibited) or hardcode "official" fare rates from
  memory (unverified, risks silently wrong numbers). Instead improved what we
  already had: `fare_table.json` was a median of real scraped fares bucketed
  into 50km bands — real data, diluted into ~80 coarse buckets with no
  monotonicity guarantee (adjacent bucket medians could dip from sampling
  noise). `etl/load_fares.py` now fits a monotonic isotonic regression per
  class directly on every (distance, fare) sample (52–345 breakpoints/class,
  denser where the data is denser); `metrics.real_fare` interpolates between
  them. Same data, no bucketing, and fare-never-decreases-with-distance is now
  a mathematical guarantee, not a hope. Verified with a dense 25km-step scan
  from 50–3000km asserting no dip anywhere. The one place live data would
  genuinely help — premium/flexi-fare occupancy-based pricing — is left as a
  cost decision (the reserved `RAPIDAPI_KEY` free tier is ~10 calls/month,
  fine for spot-checks, not bulk fetching; a paid tier is the user's call to
  make, not assumed). See ENGINEERING_NOTES P21.
- **2026-07-13 (delay-model transparency: confidence, staleness, multi-day risk)** —
  four Part-C product gaps closed. `leg_delay_profile` now carries `nObs` +
  `confidence` (none/limited/moderate/high, from how many real observations
  back the number) on every tier, and `multiDay` (journey spans 2+ calendar
  days — the sparsest, riskiest slice) regardless of tier. New
  `GET /api/delay-model-info` exposes `trained_at`/`n_rows`/MAE; `/health` gets
  a compact `delayModel: {loaded, ageDays, stale}`, and the backend prints a
  startup warning past `delay_model.STALE_AFTER_DAYS=180` — a model trained
  once on a fixed window silently drifts otherwise. `LegTimeline.jsx` shows the
  observation count inline ("· 22,526 past arrivals"), a caution note on
  multi-day legs, and the model's data-through date in the Predicted tooltip.
  Backtest-loop (predicted vs. eventual actual) stays deferred — genuinely
  blocked on the same collector gap as seat-confirmation, not a "now" item.
- **2026-07-13 (delay-model coherence fix: one curve, not two disconnected models)** —
  user caught a real-looking contradiction: a leg's "average delay" (113 min)
  looked bigger than its 75-min connection buffer, yet connection safety showed
  56%. Investigated properly instead of trusting or dismissing it: the
  underlying skew is REAL (the raw measured data for this train already shows
  avg=91 vs p50=39 — a long tail of catastrophic delays drags the average up
  while most runs are far better), and the old pre-ML exponential heuristic
  would have shown ~55% for the same average/buffer — so the math wasn't new
  or wrong. But auditing surfaced a genuine architecture gap: "average delay"
  came from a SEPARATELY trained squared-error model with no guaranteed
  relationship to the five quantile models behind p50/p90/on-time%/connection-
  safety. Fix: dropped the standalone mean model; `average` is now derived by
  integrating the SAME quantile curve (added a 0.99 quantile to ground the
  tail). Average, typical, worst-case and connection safety now read off one
  coherent distribution — that class of contradiction is structurally
  impossible now, not just unlikely. Two more fixes from the same audit: (1)
  the connection feasibility gate (`graph.one_transfer`) now uses the
  date-conditioned predicted p50 as its minimum-buffer floor when available,
  not just the flat undated measured one; (2) the UI leads with the TYPICAL
  (p50) delay instead of the average ("Typically ~57 min late… up to ~250 min
  on a bad day"), which alone removes most of the visual-contradiction feel
  even where the math was already fine. Added stratified (per-tier, per-
  day_offset) calibration reporting to the training script — an aggregate MAE
  number can't catch a thin, unusual slice (like this train's 3+ day journey)
  being poorly calibrated; only a stratified report can. **That report then
  proved the point**: p50-MAE is 19.9 min for same-day legs but **70.7 min for
  day_offset≥2** — worse than the 29.3-min flat baseline the model exists to
  beat. Added `delay_model.MAX_RELIABLE_DAY_OFFSET=1`: the model now refuses to
  predict past day_offset 1 and falls back to measured/modelled, because a
  model demonstrably worse than what it replaces shouldn't replace it — evidence
  drove the fix, not intuition. See ENGINEERING_NOTES P20 for the full
  investigation.
- **2026-07-13 (Phase C ML: delay prediction + learned connection safety + demand-aware fare advisory)** —
  the first real ML lands, plus an honest reframe of "price prediction".
  - **Delay prediction (roadmap item 1) — DONE.** `etl/train_delay_model.py`
    streams the 38.4M-row delay dump (reservoir-samples ~2.75M rows across 6,991
    trains), joins the per-stop schedule, and trains **scikit-learn
    HistGradientBoosting** — chosen over LightGBM (same histogram-GBT family, but
    no native OpenMP wheel to deploy, ~zero accuracy cost). It predicts a
    **coherent distribution** (mean + quantiles {0.1,0.25,0.5,0.75,0.9}); p90,
    on-time % (P≤30) and connection safety (P≤buffer) are all derived from that
    one calibrated CDF so they can't disagree. Held-out **MAE 26.9 vs 29.3 min**
    for the flat average (+8.4%), quantile calibration near-perfect (0.5→0.505,
    0.9→0.901). Serve-time-safe features only — the roadmap's "upstream delay" is
    a live signal we don't have when planning, so the model refines the train's
    historical baseline using day-of-week/month/position/scheduled-hour. New
    `delaySource:"predicted"` tier in `metrics.leg_delay_profile` (above
    measured, above modelled), fired only on a DATED search. 1.7 MB sidecar
    artifact loaded like `fare_table.json` — no new infra, no graph-cache bump.
  - **Learned connection safety (roadmap item 2) — DONE.** `connection_safety`
    now reads the arriving train's predicted quantile CDF at the buffer instead
    of a single-average exponential, and this fixed a latent inconsistency (the
    feasibility gate used p50 while the displayed % used the average — now both
    read one distribution). Falls back to the old exponential when a leg isn't
    predicted.
  - **"Price by festival/weekend" — reframed, honestly.** Verified first: Indian
    train fares in our data are regulated distance-slab fares, static per (route,
    class), zero date variation — an ML price model would train on a constant. So
    instead of faking it: a curated `app/data/india_calendar.json` (festivals +
    national holidays, 2025-26) drives `metrics.demand_level(date)` →
    (a) a real flexi-fare multiplier for premium dynamic-fare trains only
    (Rajdhani/Shatabdi/Duronto, IRCTC's published tier rule; regulated trains
    stay fixed at ×1.0), and (b) a `demandAdvisory` on the results page ("Diwali
    week — premium trains pricier, sleeper likely sold out"). All "est."-labelled.
    See ENGINEERING_NOTES P18 (delay model) + P19 (the fare reframe).
  - **Deferred, unchanged:** seat-confirmation ML and learning-to-rank stay
    blocked on the collector (no booking/PNR/click data yet).
  - Deps: `scikit-learn` + `pandas` uncommented in requirements (sklearn is a
    runtime dep now — load + predict; pandas is training-only). Tests: +11
    (pure demand/flexi/safety/CDF/tier + gated predicted-source & advisory
    checks). Frontend: results-page advisory banner (caution styling), lint+build
    clean.
- **2026-07-12 (real accounts: signup/login, per-user personalization, departure-time filter)** —
  the app stops being anonymous. `useAuthStore`'s phone+OTP theater (any 4-6
  digit code passed; the whole "user database" sat in localStorage, zero
  backend calls) is replaced with real email+password accounts.
  - **Auth:** `users`/`password_resets`/`saved_trips`/`recent_searches` tables
    (`etl/init_auth_tables.py`); bcrypt + stateless JWT (`app/auth.py`,
    14-day expiry, `Authorization: Bearer` header, no cookies — this app's
    own deploy notes plan the frontend and backend on separate origins, so
    bearer avoids cross-site cookie fragility). `SECRET_KEY` fails loudly if
    unset (unlike DB/graph, a JWT secret must be identical across every
    worker process — an auto-generated one would cause intermittent,
    worker-dependent 401s, worse than a clean failure). Password-reset email
    via **Brevo SMTP** (`app/email.py`, Python's stdlib `smtplib`, no new
    dependency), rate-limited to one send per 2 minutes per account,
    always-200 response (no email enumeration). *(Started on Resend — its
    free/no-domain sandbox sender can only email the Resend account's own
    address, which breaks for every other real user; switched to Brevo, whose
    free tier only requires verifying a single sender EMAIL — a
    confirmation-link click, no DNS — to send to anyone.)*
  - **Every page except the landing page now requires login.** New
    `RequireAuth.jsx` wraps the existing `<Layout/>` route block; a three-state
    `status` (`checking`/`authenticated`/`unauthenticated`, not a boolean) avoids
    both flashing protected content and flash-redirecting a valid session while
    a persisted token is being re-verified against `/api/auth/me`.
  - **Saved trips and recent searches moved server-side, per-user.** Saved
    trips store the full route JSON snapshot (not just an id) — transfer-route
    ids can't be stably rebuilt after a restart without the Redis store this
    project doesn't have yet (`engine.get_stored_route`'s comment already says
    so), so the DB snapshot substitutes for that. `SavedTrips.jsx` now shows
    "Saved on {date}" rather than presenting a frozen fare/reliability number
    as if it were live. Recent searches dedupe by (from,to) case-insensitively
    (`from_key`/`to_key` columns) — "Delhi" and "delhi" upsert the same row,
    bumping it to the top, rather than creating near-duplicates.
  - **Cross-user data leak closed:** explicit logout now clears
    `useJourneyStore`'s personalization AND hard-navigates
    (`window.location.href`, not a router navigate) — without this, a second
    user logging in on the same tab would briefly see the first user's saved
    trips/recent searches still sitting in memory.
  - **New filter: preferred departure time** (`FiltersPanel.jsx`), RedBus-style
    multi-select — Early Morning (4–10am) / Afternoon (10am–5pm) / Evening
    (5–10pm) / Late Night (10pm–4am, wraps midnight). Implemented entirely
    client-side in `Results.jsx`'s existing filter pass (same pattern as the
    pre-existing `avoidLateNight`), no backend change needed; an empty
    selection is behaviourally identical to today.
  - Backend: 51/51 pytest passing (`test_auth.py` new — pure hash/JWT unit
    tests plus DB-gated signup/login/saved-trips/recent-searches integration
    tests). Frontend: lint + production build both clean.
  - **Known gaps, documented not hidden:** no server-side session revocation
    (stateless JWT, logout is client-side only); no "refresh this saved trip"
    re-fetch action yet (a real gap given snapshots go stale — flagged as a
    follow-up); a residual timing side-channel on `forgot-password`
    (registered vs. unregistered email) is accepted, not engineered away.
  - **User-verified end-to-end** on a real browser (this session's own
    Chrome-extension check never connected, so this was the actual
    confirmation): signup/login, route guarding, saved trips, recent
    searches, and the departure filter all confirmed working. Forgot-password
    was the one exception — see the Resend→Brevo entry above and
    ENGINEERING_NOTES P17 for the diagnosis.
  - **Recent-searches redesigned to match ixigo (user-requested):** the
    static always-visible chip row is replaced by a dropdown that appears
    under the **From** field on focus when it's empty (`Search.jsx`'s
    `PlaceInput`, now shared between place-autocomplete and recent-searches —
    typing 2+ characters switches it back to place suggestions). Each row
    shows a clock icon, `From → To`, and the date. Picking one fills the form
    without auto-navigating, so the user still confirms with "Find my route" —
    matching ixigo's actual behaviour, not just its look. The search form no
    longer defaults to the hardcoded "Rourkela → Nashik" placeholder values
    now that there's a real personalization feature to show instead.
  - **Password visibility toggle, made consistent app-wide:** `Auth.jsx`'s
    login/signup form already had a show/hide eye icon on its password
    fields; `ResetPassword.jsx` was missed and didn't (user-caught). Extracted
    the toggle into a shared `components/PasswordField.jsx` used by both, so
    every current and future password field gets it automatically rather than
    each page reimplementing (and risking forgetting) it.
- **2026-07-12 (station-identity mismatch fixed + general geo-guard)** — user
  caught a Gorakhpur train (`15909 Avadh Assam Exp`) shown reaching "Sangar"
  (near Katra, J&K) — it really stops at **Sangariya** (Rajasthan). Root cause:
  the timetable name→code matcher bound the "Sangariya" stop to the wrong
  station **SGRR "Sangar" (J&K)** instead of **SGRA "Sangaria" (Rajasthan)**,
  ~340 km off, so the train appeared to teleport north and back.
  - **Detector (`graph.mislocated_stations`, no hand list):** every stop's
    *expected* location is the midpoint of its neighbours; across all a station's
    trains those cluster where it really is. A station whose STORED coord sits
    >150 km from that cluster in >60% of its trains is mis-identified. Found
    **70** such codes (distinct from legitimate reversal junctions like Itarsi,
    which are not flagged).
  - **Repair (`etl/fix_station_mismatches.py`, applied):** for the high-confidence
    cases — another station whose name shares a long prefix sitting ≤10 km from
    the expected spot — remap the stops to the correct code. **9 stations, 195
    stop rows** repointed in the DB (SGRR→SGRA, HCM→HCR, GPPR→GBK, AGCI→AAM,
    AWL→AIH, JMRA→JMIR, MH→MHA, RSLR→RPGU, SGRD→SGRE); num_trains recomputed;
    cache v4→v5. (The collateral false-positive MBY "Mandi Dabwali" — flagged
    only because its neighbour SGRR was wrong — was correctly NOT remapped, and
    un-flagged itself after the fix.)
  - **General guard (`graph.stop_detour_km` in `single_train`/`one_transfer`):**
    the router now refuses to board/alight at any stop that is a gross detour
    (>150 km) in its own train path — so a bad-geo station can never produce a
    nonsense route, including the **58** remaining flagged codes with no clean
    same-name match. Only judges the board/alight stop itself, so a real reversal
    junction as a pass-through is unaffected.
  - Verified: Gorakhpur→Katra now tops with Gorakhpur→Jammu Tawi (correct J&K
    railhead), 0 legs through "Sangar". Tests: +1 regression (router never emits
    a gross-outlier board/alight, codes not hardcoded so it survives the repair)
    → **38/38 pass**. See ENGINEERING_NOTES P16.
- **2026-07-08 (seasonal/special trains date-gated via the calendar)** — a Magh
  Mela special (`5002 GKP JI MAGH MELA`) was showing on every date though it
  only runs a few days in January. Now special trains surface only near their
  season, using the date the user already picks.
  - **Detection (data-driven, in `etl/load_delays.py`):** the same 1-GB delay
    stream now also collects each train's distinct **origin operating dates** →
    a train is "seasonal" if it ran on **≤30 distinct days across ≤3 calendar
    months** in the full year. Stores `operating_months` (e.g. "1,2") on the
    `trains` table (NULL = year-round). **111 seasonal trains** detected — Magh
    Mela / festival / summer specials (57 carry an explicit SPL/MELA/SPECIAL
    keyword; the rest are sparse DEMU/PASS seasonals). Kept, not deleted —
    they're real and useful in-season, and deleting would lose their delay
    history.
  - **Gating (`graph.runs_in_month` + `engine.search`):** a seasonal train is
    included only when the travel month ∈ its window; **hidden on an undated
    search** (can't confirm it runs). Regular trains are never affected.
    Verified: 5002 hidden undated & in July, shown Jan 13 with a
    "Seasonal · runs in Jan" badge (new amber chip on `RouteCard`).
  - **Ranking fix it surfaced:** with the Magh Mela specials (which board at
    Gorakhpur) gated out, an undated GKP→Prayagraj search suddenly topped with a
    *Basti* cross-origin — because it **tied on reliability** with the best
    Gorakhpur-direct and won the raw-time tiebreak, ignoring its 90-min
    first-mile road. Fixed `_rank`: on a reliability tie, a friction-free
    **direct** now beats a cross-origin (don't send someone to another town's
    railhead when their own station has an equally-reliable train). Top is
    Gorakhpur again.
  - Tests: +1 seasonal regression (hidden undated/off-season, shown + labelled
    in-season); the rank fix restored 3 corridor tests that had encoded the old
    special-dominated top → **35/35 pass**. Cache v3→v4 (adds `TRAIN_MONTHS`).
  - **Note on 5002 specifically:** it ran only Jan 1/3/13 2026 in the data —
    the Magh Mela snan window at Prayagraj. Magh Mela is an *annual* event, so IR
    reissues these specials every Jan-Feb; our one-year dataset only proves it's
    strictly seasonal (hence NULL weekday-days, Jan-only window), not the
    year-over-year recurrence (that's from IR's standing practice).
- **2026-07-08 (user-caught batch: Plan B, connection buffer, premium classes)** —
  three fixes after the measured-data upgrade.
  - **Plan B was nonsensical** — a route departing 21:30 showed "next train"
    departing 13:45 (already gone). Root cause: planB was just `routes[i+1]`
    (next in the *ranking*), ignoring departure time. Fixed: `_first_train_dep_min`
    + pick the alternative that departs **soonest AFTER** this route (a real "if
    you miss it" fallback); if none is later, keep the route's own delay/hub
    advice. Verified live on GKP→Prayagraj: 21:30 route → "Next train: 15004
    departing 23:15".
  - **Connection buffer now covers the incoming train's typical delay** —
    `graph.one_transfer` raised its min buffer from a flat 30 min to
    `max(30, min(p50_delay_of_first_train, 90))` using measured `train_delays`.
    A transfer where train 1 is usually 40 min late no longer offers a 30-min
    connection. Scanned 8 cross-country pairs: **0 of 27 measured transfers**
    violate the invariant.
  - **Premium class-list cleanup** — `engine._offered_classes` fixes the generic
    `classes` column: AC-sleeper premiums (Rajdhani/Duronto/Humsafar/Garib Rath,
    incl. Tejas *Rajdhani*) drop SL/2S; chair-car premiums (Shatabdi/Vande
    Bharat/Gatimaan/Tejas *Express*) keep only CC/EC/2S. Guards for the
    ambiguous brands: "TEJAS RAJ" and "VANDE BHARAT SL" are AC-sleeper, not
    chair-car. Rajdhani 12301 now shows 3A/2A/1A (was +SL); Vande Bharat →
    CC/2S/EC. (One train, 2003 Swarna Shatabdi, still shows SL/3A/2A because its
    *raw* data lists no CC/EC — unfixable without a better source.)
  - Tests: +3 regressions (planB-departs-later, buffer-covers-p50, premium-class
    cleanup) → **34/34 pass**. All three verified in-browser, no console errors.
- **2026-07-08 (Phase B measured-data upgrade — modelled → measured)** — pulled
  in two free datasets and turned three "modelled" numbers into real ones,
  keeping the honest "est." labels where no free ground truth exists.
  - **Real fares (Step 1):** `scratchpad build_fares` → `app/data/fare_table.json`
    from IRCTC `price_data.csv` (326k priced rows, 6 classes): median `totalFare`
    per (class, 50-km band) + a per-class linear fit fallback. `metrics.real_fare`
    /`rail_fare` now return IRCTC-accurate fares (SL@500 ₹325, 2A@1000 ₹1940),
    premium trains carry a +12% multiplier. Falls back to the old model when a
    class/band is missing.
  - **Real per-stop distances:** `etl/load_schedule_extra.py` →
    `app/data/train_cumdist.json` (8,673 trains) from the delay dump's
    `combined_schedule.csv` `distance_from_origin`. `graph.rail_km` + `engine._rail_km`
    now use exact routed km (Mumbai Rajdhani MMCT→NDLS = **1384 km**, was
    haversine×1.25) instead of straight-line.
  - **Measured delays (Step 2):** `etl/load_delays.py` streams the 1 GB
    `combined_delay.csv` (38.4M rows, a full year Feb-2025→Feb-2026) in one pass →
    `train_delays` table for **7,024 trains** (avg/p50/p80/p90/on_time%/n_obs,
    source='measured'). `graph.TRAIN_DELAY` + `metrics.leg_delay_profile(measured=…)`
    surface real on-time % with modelled fallback, tagged `delaySource`. Avadh
    Exp 122-min avg / 26% on-time, Rajdhani 96% — matches reality.
  - **"Daily but not daily" bug fixed:** the fresh-2026 source marked **7,861/8,366
    trains as 7-day** (and the rest 1-day — nothing in between = broken scrape).
    Recovered true service days from origin (station_no=1) departure weekdays over
    the year: **1,782 trains corrected off false "daily"** (2,555 genuinely
    non-daily); running-days now spread 1→7 (e.g. Arunachal Exp Tue/Sat, Triveni
    Exp Mon/Wed/Fri). New trains get NULL days (no false claim) not fabricated 7-day.
  - **Bigger DB:** +**1,511 trains / 22,462 stops** from the delay-dump schedule
    (not already in DB, ≥2 placeable stops), classes guessed from type_code,
    source='delay-schedule'. DB 8,606→10,117 trains; graph cache v2→v3.
  - **Integrity + UI (Step 3):** `tests/test_metrics.py` (13 tests, metrics.py had
    zero) → **31/31 pass**. "est." affordance added to ReliabilityBadge (compact),
    ConfirmationPill, and a green **"measured"** chip on breakdown factors backed by
    real data. Confirmation stays modelled-and-labelled (no free PNR feed — the
    honest ceiling).
  - **Ranking/explainability (Step 4):** reliability breakdown shows dynamic
    **"On-time record" (measured)** vs "On-time (est.)"; `why`/`planB` refined
    (p90 buffer advice on measured direct routes, hub-rebook advice on risky
    transfers). Verified in-browser (Mumbai→New Delhi): gauge 88%, On-time record
    96% measured, real per-class fares, no console errors.
  - **Test fix:** `test_direct_road_option_for_short_hop` moved Ringas→Salasar →
    **Salasar→Sikar** — with accurate distances the engine correctly prefers
    train-to-Sikar-then-road for Ringas→Salasar (Sikar is 42 km from Salasar vs
    Ringas 92 km), so that pair is no longer a valid "road must win" example.
  - Known (pre-existing, not from this work): premium trains (Rajdhani/Shatabdi)
    still list non-AC classes (SL/2S) because the `classes` column is generic —
    class-list cleanup is a separate follow-up.
- **2026-07-05 (product reframe: multi-modal + cities-first)** — user
  correction: RouteSarthi is a **travel planner, not a train app**.
  - **Direct road option added** (`_road_route`): a door-to-door cab/bus leg
    that competes with rail and is always shown (ranked in place) up to 500 km
    or whenever rail finds nothing. Verified: Ringas→Salasar road is #1 fastest
    (2h59 vs 4h11 rail); Delhi→Jaipur shows road but train wins; Delhi→Mumbai
    (>500km) shows no road. RouteCard renders road-only routes as "Direct by
    road (cab or bus)". `ROAD_KMPH` 35→40.
  - **Autocomplete flipped to cities-first, by state** — every city shows with
    its state; the "Railway station" label is gone (station-towns the gazetteer
    misses, e.g. Ringas, now fill remaining slots with their **real state**).
  - PHASE_B_PLAN §2 "trains-first" decision revised to multi-modal. pytest
    **17/17** (added road-option + cities-first tests). Known: road detail
    links reset on restart (like transfers — Redis at deploy); road distance is
    straight-line×1.3 until OSRM.
- **2026-07-05 (backtracking fix + search relevance + India map)** — all
  user-caught:
  - **Backtracking routes killed (P12):** Ringas→Salasar rode a train back to
    Ringas. Added `_useful()` progress filter (rail leg must end nearer dest +
    farther from origin) on direct + transfer candidates. Regression test added.
  - **"Wrong Khatu":** picking a station suggestion (state="Railway station")
    now geocodes via the station index, not a same-named city elsewhere.
  - **Autocomplete relevance:** railway stations listed FIRST (train app),
    then cities; dedup keyed on (name, state) so both Gorakhpurs surface.
  - **Kanyakumari etc.:** `PLACE_ALIASES` map (Kanyakumari→Kanniyakumari,
    Banaras→Varanasi, Bombay→Mumbai…) + **pg_trgm fuzzy** fallback for other
    misspellings (extension + GIN index; added to load_v2 for rebuilds).
  - **Running days** confirmed multi-day (Sun+Tue → "Tue, Sun").
  - **India map (Option B done):** OSM shows disputed J&K/Ladakh/Arunachal
    borders. Downloaded datameet's India-official boundary (10.7MB), simplified
    it pure-Python to a **43KB** MultiLineString, shipped as
    `frontend/public/india-boundary.json`, overlaid as a subtle brand-colour
    national border line in RouteMap (lazy fetch, graceful fallback). No
    external dep, no state-border clutter. *(Mappls tiles remain the eventual
    "even better" option if a request-capped key is acceptable.)*
  - **load_all.py** hard-guarded as deprecated (breaks current schema).
  - pytest **16/16**, frontend lint+build clean. Verified via live dev server.
- **2026-07-05 (station-wide search + pricing→Step 3)** —
  - **Every railway station is now searchable/routable**, not just GeoNames
    cities. Root cause: geocode + autocomplete only hit the `cities` table, so
    station-towns absent from GeoNames (Ringas Jn — 64 trains!, Khatu, …)
    returned nothing. Added `graph.station_suggestions` + `graph.station_geocode`
    (in-memory over the 8.7k stations); `/api/places` now merges up to 6 cities
    + 4 stations (labelled "Railway station"); `_geocode` falls back to the
    station index when a city lookup misses. Verified: "Ringas" autocompletes
    to Ringas Junction and Ringas→Jaipur now returns 16 routes (was 0).
    *Correctly still unroutable:* Leh/Ladakh (no railway exists there — right
    behaviour for a rail app). *Known residual:* Kanyakumari absent from this
    dataset's stations (a coverage gap, not a search bug) — revisit with the
    station-alias/coverage grind.
  - **Running-days confirmed multi-day:** a Sun+Tue train shows "Tue, Sun"
    (verified train 00961 → "Mon, Tue, Thu, Fri").
  - **Fare accuracy moved into Step 3** (PHASE_B_PLAN §9b step 3b): real
    per-stop cumulative km + fares fitted from the IRCTC-2023 `price_data.csv`.
  - **Map (permanent fix) — decision pending user:** OpenFreeMap/OSM shows
    J&K/Ladakh/Arunachal with disputed borders. Two permanent fixes documented
    for the user to choose (both need a key or a decision): Mappls dev tiles,
    or an official-boundary GeoJSON overlay. pytest 14/14 green throughout.
- **2026-07-04 (4 UX adds + audit + docs)** —
  - **4 UX features shipped:** (1) **Cheapest/Fastest tag** on the best card
    (computed client-side over the visible set); (2) **running days** on cards
    + itinerary ("Daily" / "Mon, Wed, Fri" from `days_of_week`); (3) **class
    filter** — Sleeper/3A/2A/… dropdown filters routes by real `classes`
    (route now carries a `classes` union); (4) **halts + "view all N stops"**
    expander per train leg (`stops` = station names along the path, `halts`
    count). Backend adds `graph.STATION_NAME`, `_days_label`, `_path_stops`,
    `_route_classes`. Verified in-browser + pytest 14/14 green.
  - **File audit (no deletions per user):** codebase clean; only footgun found
    is **`etl/load_all.py`** — its `trains` table lacks the `days_of_week`/
    `classes` columns `graph.py` now needs, so running it would break the
    engine. Marked DEPRECATED with a hard `--force-deprecated` guard; use
    `load_v2.py`. `models.py` (contract schema), `seed.py` (fallback),
    mock data (empty states/map fallback), docker-compose (future infra) all
    intentionally kept. `JourneyBackdrop.jsx` still the only dead file (user
    chose to keep).
  - **README:** added full "rebuild the DB from scratch" path (own Postgres+
    PostGIS → download.py → manual Kaggle timetable → load_v2 → verify →
    cache) for a teammate without the shared DB.
  - **Recommendations logged (not yet done):** *Pricing* — replace haversine×
    1.25 distance with real per-stop cumulative km from the data + fit fares
    from the 124MB IRCTC-2023 `price_data.csv` (telescopic slabs, superfast/
    catering/GST) for true accuracy; current linear per-km is a rough average.
    *Map* — OpenFreeMap/OSM draws J&K/Arunachal with "on-the-ground" (disputed)
    borders, not India's official line; India-compliant fix = Mappls/MapMyIndia
    tiles (free dev key, better tier-2/3 data) or an official-boundary GeoJSON
    overlay. Both are user-key/decision tasks — flagged for later.
- **2026-07-04 (tests + pricing/main-train + docs)** —
  - **Pytest suite** (`backend/tests/`, 14 tests, ~5s): contract shapes +
    live-engine regressions (P9–P11) — route count, Gorakhpur→UP geocode,
    reasoning modes, sane fares, transfer connection safety, weekday filter,
    direct-id rebuild, autocomplete states, class-fares. Engine tests skip
    gracefully without a DB so contract tests run on any clone. `pytest` added
    to requirements.
  - **Per-class fares:** every train leg + route `mainTrain` now carries
    `classFares` [{code,label,fareInr}] (Sleeper/AC 3-tier/… cheapest-first)
    from the calibrated rates × distance; headline shows "from ₹X". New
    `ClassFares` component on RouteCard + LegTimeline.
  - **Main train surfaced:** route `mainTrain` (the longest train leg) shown on
    each card — name + "BOARD dep → ALIGHT arr" — so users see *which* train.
  - **Root `README.md`** added: pull→run-in-3-min steps (backend venv/env →
    frontend proxy → tests), data/credentials note, contributor logging norm.
  - **Codebase audit:** clean — no tracked artifacts, seed.py/mock-data/
    docker-compose all intentionally kept (fallback / empty-states / future
    infra). Only dead file: `frontend/src/components/JourneyBackdrop.jsx`
    (0 imports) — pending user OK to delete.
- **2026-07-04 (Step 2+3 plan locked)** — full execution plan written into
  `PHASE_B_PLAN.md` §9b: commit → pytest suite → Kaggle delay ETL
  (`train_delays` aggregates) → engine wiring (measured `delayProfile`,
  empirical-CDF connection safety, composite reliability, `delaySource`
  honesty flag) → verify → budget-guarded collector skeleton. User tasks:
  download the two Kaggle delay datasets; register a free indianrailapi key
  as the candidate daily-collector provider.
- **2026-07-04 (friend's 📌 list cleared)** — completed the three items left
  for the backend owner: (1) **fares** — done earlier via calibration from 288k
  real IRCTC-2023 quotes (per-class ₹/km), materially better than the ₹0.7/km
  proxy (full telescopic slab table optional later); (2) **geocode
  City,State** — done via the `/api/places` autocomplete + `IN_STATES` map +
  rail-aware re-ranking (P10); (3) **ROUTE_STORE restart/worker safety** —
  added `_rebuild_direct`: direct-route detail ids are semantic
  (`train-board-alight`) so they rebuild statelessly from the graph on a store
  miss (verified: `/api/routes/15004-GKP-ALD` resolves with an empty store).
  Transfer ids still need the store (Redis remains the deploy-phase plan for
  those). Net: detail links no longer 404 after a restart for the common case.
- **2026-07-04 (six-bug batch + sweep)** — all user-caught:
  1. **Station-code renames (P11):** 15004 alighted 61 km out at Gyanpur Road
     while passing Prayagraj Jn — schedule data used renamed codes (PRYJ/PRRB/
     MMCT/CSMT/SMVT/VGLJ/DDU) that carry no geo. ETL now normalises via
     `CODE_RENAMES`; Prayagraj corridors went 10→15 options.
  2. **Reasoning claimed "Direct wins" for an 81-km-away boarding** — direct
     mode now requires transfers==0 AND type=='direct' (local boarding);
     through-train-via-hub gets the cross-origin narrative.
  3. **Filters:** AC-only now uses real per-train `classes`/`acAvailable`
     (fare-proxy kept only for mock routes); avoid-late-night reads the last
     leg that has an arrival time; fewer-transfers uses `transfers`.
  4. **Compare page** no longer shows "No option found" on all-direct
     corridors — compares best two options with honest labels.
  5. **Maurya Exp "should board Raxaul" — NOT a bug:** data shows 15028 runs
     GKP→…→Siwan→…→Rourkela and never serves Raxaul; engine correctly boarded
     the nearest railhead the train actually stops at.
  6. **"Show more trains"** — engine cap 10→16; Results shows 6 + expander.
  Plus: engine now generates **planB** (next-ranked alternative) for every
  route; cleanups from the tracked list (README tagline, duplicate import,
  share-card typo, unused framer-motion dep). Verified in-browser: 15 routes
  GKP→Prayagraj, "Show 9 more trains", Compare shows Direct ₹195 vs Via Basti
  ₹371.
- **2026-07-03 (results/detail depth pass — user-caught batch)** — six fixes
  from testing Gorakhpur→Prayagraj:
  1. **Only 6 options → 10.** Root cause: `_diversify` bucketed ALL direct
     routes under one `_direct` key capped at 2. Fixed: directs are each a
     distinct train (kept in full); only *transfer* routes get hub-deduped.
     Cap raised 6→10. (The "missing" Chauri Chaura Exp 15004 was present all
     along — the cap hid it.)
  2. **Reasoning strip missing on direct corridors.** `_reasoning` now always
     emits, in `mode:"direct"` (green through-train winner + "also checked N
     hubs") or `mode:"cross-origin"` (existing hub-scan). Frontend
     `DecisionReasoning` rewritten to render both modes.
  3. **Reliability breakdown gone** (engine had no delayProfile/confirmationPct
     the derived one needed). Engine now ships `reliabilityBreakdown` per route
     from its real factors (no-transfer / connectivity / first-mile, or
     connection-safety / hub / first-mile for transfers); RouteDetail prefers
     it, falls back to the derived one for mock corridors.
  4. **Empty "% connection safety · min buffer"** on road-access legs — those
     carry null safety; LegTimeline now renders them as a plain road note.
     Real train-transfer legs still show safety + buffer.
  5. **Straight-line map → real rail path.** graph `single_train`/`one_transfer`
     return the intermediate-station `path`; engine attaches `pathCoords` per
     train leg; RouteMap draws the dense polyline through them (verified: GKP→
     Prayagraj now bends through Varanasi, not a diagonal).
  6. Direct `why` copy clarified ("no change of train"). All verified in-browser.
- **2026-07-03 (geocode artifact + autocomplete — user-caught, see P10)** —
  Gorakhpur→Prayagraj routed via Haryana because GeoNames has a duplicate
  "Gorakhpur" (wrong state, bigger population). Fixed with rail-aware geocode
  re-ranking (prefer the candidate with a same-named station within 20 km) +
  new **`/api/places` autocomplete with state names** in the search form
  (admin1→state map derived from our own data; picking a suggestion sends
  "City, State" and the geocoder filters by it). Verified: direct 14111
  GKP→Prayagraj 6h19m now tops the corridor; dropdown shows both Gorakhpurs
  with states. *Note:* suggestion list is population-ordered (artifact rows
  can appear first — harmless since the state label disambiguates); prefix
  LIKE currently seq-scans cities — add a text_pattern_ops index if typing
  latency ever bothers.
- **2026-07-03 (reasoning coherence fix — user-caught, see P9)** — the
  decision strip's winner showed worse numbers than the losers, and a direct
  route scored "51% Risky" while a 2-transfer one scored "92% Safe". Fixed:
  hubs now scored by through-trains-to-destination (the ranker's real metric),
  backend emits an honest `conclusion` sentence the frontend renders verbatim,
  and reliability rebalanced (direct ≥ floor 45, formula favours no-transfer;
  transfers capped at 84 × connection safety). Verified in-browser.
- **2026-07-03 (STEP 1 CLOSED OUT ✅)** — Finished everything in Step 1 that
  runs on this machine, verified end-to-end in the browser:
  - **IRCTC-2023 gap-fill:** +300 trains absent from the 2026 scrape loaded
    with `source='irctc-2023'` (structured codes + dayCount). Totals now
    **8,606 trains / 168,578 stops**; unmatched refs 8.6%→7.9%.
  - **Real fares:** rates calibrated from 288k real Oct-2023 IRCTC quotes
    (median baseFare/km: SL 0.58 · 3A 1.48 · 2A 2.10 · 1A 3.57 · CC 1.58 ·
    2S 0.45); leg fare = haversine km ×1.25 route factor × class rate
    (cheapest class the train offers — Rajdhani/Tejas price as 3A) + ₹40
    reservation. Delhi→Mumbai SL now ~₹897 (was time-proxy nonsense).
  - **Running days enforced:** `date` param flows frontend→API→engine→graph;
    trains filtered by weekday (`TRAIN_DAYS`, graph cache v2); unknown days
    assume daily (conservative).
  - **Live `reasoning`:** engine now emits the hub-scan block from what it
    actually evaluated — the decision animation runs on real searches
    (verified: Imphal→Bengaluru shows Lumding/Hojai/Badarpur scanned, Dimapur
    wins). confirmPct is a labelled connectivity proxy until Step 4.
  - **Endpoints unified:** `/api/search` is now an alias of `/api/routes`
    (same engine + seed fallback + date). Geocode tolerates "City, State"
    input (matches city part; full state disambiguation still needs an
    admin1 map). Benchmark after all changes: mean 11%, no regressions.
  - **Deferred with reasons (needs Docker, absent on this machine):** OSRM
    first/last-mile (straight-line ×1.25 stands in) and Redis route-store —
    both are deploy-phase infra, stubs/config already in docker-compose.yml.
- **2026-07-03 (DATA SWAP DONE ✅)** — **2016 timetable replaced with the
  May-2026 scrape.** New `etl/load_v2.py` (dry-run mode + real load, 18s):
  parses `intermediate_stops` text → stop rows; **station name→code mapping**
  built from the IRCTC-2023 dataset's structured `stationList` (3,773 names)
  + datameet stations (9,426 total) + a hand-built ALIASES table for post-2016
  renames (Ahilyanagar→ANG, C Sambhajinagar→AWB, MGR Chennai→MAS, Hubballi→UBL,
  SMVB, NZM, VGLJ→JHS…) + unique-prefix fuzzy fallback; day-rollover inferred
  from clock resets. Unmatched refs: 19.6% → **8.6%** across three matcher
  iterations. **Result: 8,306 trains / 162,883 stops loaded** (was 5,208 /
  417k — old data counted passing stations, not real halts). `trains` now
  carries `days_of_week`, `classes`, `distance_km`, `source`, `last_verified`.
  **Acceptance:** benchmark mean 11% (durations hold; Rourkela→Ranchi reads
  2.9h on BOTH datasets → our 4.5h reference was wrong, not the engine);
  **identity spot-check matches the manual audit exactly** (12262 CSMT Duronto
  HWH 05:35 ✓, 12510 GHY SMVB 06:15 ✓, 12475→SVDK ✓); Imphal→Bengaluru now
  routes via Dimapur (realistic). **Known residuals:** (1) ~8.6% station refs
  still unmatched → some trains lose head/tail stops (e.g. 12952 truncates to
  Kota) — grow ALIASES to fix; (2) hub count 1,979→384 (threshold vs cleaner
  halt data — fine); (3) `days_of_week` stored but NOT yet enforced in routing
  (needs a travel-date param through the API); (4) price_data.csv (124MB,
  IRCTC Oct-2023) shelved in `candidates/irctc-2023/` as the fare-formula seed.
- **2026-07-03 (data decision)** — **Kaggle vetting done; new base chosen.**
  Three candidates compared: (1) IRCTC scrape Oct-2023, Apache-2.0, 3,292
  trains + per-class fare table (`baseFare`×`classCode`×`distance`) + running
  days; (2) data.gov.in ~2020, GPL-2, 11,114 trains — **rejected: pre-COVID**
  (the era the audit proved everything changed) despite biggest coverage;
  (3) fresh scrape **May-2026, CC0, 8,366 trains** with `days_of_week`,
  `classes`, `distance`, stop-level detail in `intermediate_stops` text —
  **chosen as the new base**. #1 kept as the fare-formula seed + running-days
  cross-check. **Decision: drop 2016 schedules from the DB entirely** (0%
  audit validity makes them a harmful "fallback"), keep the raw file on disk,
  keep `source`/`last_verified` columns for the live-refresh future, keep the
  datameet stations table (geo is stable; ETL must alias renamed codes like
  BCT→MMCT, CST→CSMT). Next: inspect #3's files, build the v2 ETL, reload,
  re-run benchmark + a fresh 10-train audit as acceptance.
- **2026-07-03 (audit results)** — **Train-validity audit DONE (28 trains,
  manual vs erail): 0 SAME · 19 CHANGED (68%) · 9 GONE (32%).** Not one
  sampled train from the 2016 timetable is bookable as-is. Findings:
  every flagship demo train is retimed (e.g. 12262 dep 08:20→05:35) or gone
  (15902); several routes materially changed — 12475/12477/12472 extended
  JAT→SVDK (Katra), 12510 terminus SBC→SMVB (opened 2022), station code
  renames (BCT→MMCT, CST→CSMT); **train-number reuse** (19604 and 56812 now
  belong to entirely different routes — silently wrong results, worse than
  404s); passenger trains hit hardest (4/5 GONE — post-COVID MEMU/special
  renumbering). **Strategy consequence: bulk re-seed from a current dataset is
  now URGENT, the critical path** — lazy refresh can't fix a 100%-stale base.
  Combined with the benchmark (durations ~7% off), the full picture: corridor
  *speeds* are fine, train *identities* are ~100% unreliable. **CRIS portal
  probed (via VPN): it's an internal/partner API gateway** (groups: ntes.cris.in,
  fois.cris.in, eps.cris.in…), sign-in only, no public registration — dead end
  without a formal partnership; noted for a future official-access application.
  Next: vet + load a 2024-25 Kaggle timetable (multi-source ETL with
  `source`/`last_verified`), then re-run `etl/benchmark.py` + re-audit as the
  acceptance test.
- **2026-07-03 (later)** — **Train-validity audit prepared** (zero API calls —
  RapidAPI free tier turned out to be ~10 calls/month, so the audit runs
  manually against NTES/erail instead; the 10 calls are reserved as a guarded
  budget for future automated spot-checks). New `backend/etl/sample_trains.py`
  prints a 28-train checklist: the 8 trains the flagship demos depend on +
  stratified random samples (premium/express/passenger/other). Verdict per
  train: SAME / CHANGED / GONE on erail.in — validity % = SAME/28. Sample
  already surfaced 2016-data dirt: "-Slip" suffixed train ids, missing
  departure times. `RAPIDAPI_KEY` added to config/.env.example (gitignored
  value). CRIS official API portal to be probed via VPN (was unreachable from
  our network).
- **2026-07-03** — **Truth benchmark built + run** (`backend/etl/benchmark.py`:
  10 famous corridors, engine's fastest route vs today's real fastest train).
  **Surprise result that reverses our assumption:** the 2016 timetable's
  *durations* are only **7% off on average** (9/10 corridors within ±10%) —
  trunk-route travel times barely changed in a decade. The one outlier
  (Rourkela→Ranchi −37%) may be a bad reference value, not engine error.
  **Revised data strategy:** staleness risk is NOT travel time — it's **train
  identity** (renumbered/cancelled trains a user can't actually book, missing
  post-2016 trains like Vande Bharats — e.g. our Mumbai→Madgaon "7.4h" train
  may no longer exist even though the duration looks right). So the priority
  order flips: **(1) per-train validity verification via a live API (lazy
  refresh + `last_verified`) is now the main event; (2) bulk re-seed from a
  newer Kaggle scrape is still wanted but demoted to "nice, when vetted";**
  (3) fares remain the most user-visible inaccuracy (still the slab-formula 📌).
  Benchmark doubles as the acceptance test for any data change — re-run it
  after loading anything new. (Windows note: run with `PYTHONIOENCODING=utf-8`.)
- **2026-07-02 (later)** — **Reproducibility + contract fixes applied** (from
  the review below; see ENGINEERING_NOTES P7):
  - `requirements.txt`: uncommented `psycopg[binary]` + added `psycopg-pool`
    (they're imported at module load — fresh clones couldn't boot at all).
  - New `backend/etl/download.py`: fetches stations.json + schedules.json
    (datameet) and IN.txt (GeoNames) into `data/raw/` — repo is now
    reproducible on any machine.
  - `app/main.py`: `/api/routes` now catches *any* engine failure (no `.env`,
    DB unreachable) and serves the seed corridors instead of 500ing.
  - Transfer routes: leg-1 `arrive` now populated (was `null`, contract wants
    HH:MM); hub arrival threaded through `graph.one_transfer`.
  - `graph.py`: documented the `% 1440` connection-wait day-boundary
    limitation (errors skew conservative; proper day-aware math lands with
    Step 3).
  - `sql/schema.sql`: re-synced with `load_all.py` (added
    `cities_name_lower_idx` — the Layer-3 index).
  - Backend README: full reproducible setup steps (env → download → load →
    verify → run).
  - **📌 Left for next backend session (owner: backend):** (1) fares → real
    distance-slab formula (§4F) — current ₹0.7/km proxy is visibly wrong on
    short hops; (2) geocode "City, State" disambiguation (two Aurangabads;
    needs a GeoNames admin1-code→state-name map); (3) move `ROUTE_STORE` +
    result cache to Redis before deploy — in-process versions reset on restart
    (detail links 404) and break under `--workers >1`.
- **2026-07-02** — **Backend code review + data-freshness research** (after
  pulling the Phase B engine).
  - *Review verdict:* engine architecture (in-memory graph + thin DB) is sound
    and well-documented. Issues found, ranked: **(1) Reproducibility blocker —**
    `requirements.txt` still has `psycopg`/`psycopg_pool` commented out although
    `app/db.py` imports them at module load, so a fresh clone can't even boot the
    seed endpoints; and `data/raw/` + `graph_cache.pkl` are gitignored with **no
    download script**, so only the original machine can run the engine (bus
    factor 1 — confirmed: this machine has no `backend/data/` at all).
    **(2) Correctness niggles** — transfer wait uses `% 1440` (conflates day
    boundaries); leg-1 `arrive` is `null` on transfer routes; geocode resolves
    ambiguous names (two Aurangabads) by population only; fare = flat ₹0.7/km
    proxy instead of the slab formula; `schema.sql` drifted from `load_all.py`
    (missing `cities_name_lower_idx`). **(3) Deploy notes** — in-process
    `ROUTE_STORE`/caches vanish on restart (detail links 404) and assume a
    single worker.
  - *Data-freshness research:* **datameet timetable is from Aug 2016** (~10
    years stale — renumbered/new/retimed trains make it materially wrong for
    real users); data.gov.in OGD timetable is ~2017 and bot-blocked (403).
    **No current bulk open download exists.** Practical path chosen to propose:
    (a) re-seed the base timetable from a recent community scrape (Kaggle
    2024-25 sets — vet coverage/licence first); (b) add a **lazy refresh
    layer** — on each searched corridor, verify the involved trains against a
    free-tier live API (RapidAPI `irctc1` / indianrailapi.com), store
    `last_verified` per train so hot corridors self-heal to current data within
    free rate limits; (c) surface freshness honestly in the UI ("timings
    verified <date>"); (d) try the **official CRIS API portal**
    (crisapis.indianrail.gov.in — unreachable from here, likely India-only;
    check from a local browser) and pursue registration; (e) GeoNames cities +
    station geo are fine (stable/continuously updated). Delay seed (Kaggle
    Sep-2025 ETrain scrape) already in the plan.
- **2026-06-30** — Phase B kicked off. Researched + locked the data strategy
  (`PHASE_B_PLAN.md`). Built and verified the backend scaffold (Step 0):
  FastAPI serving the full contract from ported seed fixtures. Provisioned
  Supabase Postgres+PostGIS. **Step 1 data layer + engine:** loaded the full
  rail network + 558k-place gazetteer; built the cross-origin engine
  (`/api/search`) with single-train + one-transfer routing, proven on real data
  for Rourkela→Nashik, Bhuj→Shimla (via Ahmedabad), Imphal→Bengaluru (via
  Howrah). Transfer-search performance + route diversity flagged for
  optimization next.
  **Performance overhaul (same day):** rearchitected routing to run fully
  in-memory (schedule graph + nearest-railhead), added a local graph cache,
  geocode index, connection pool, connection-safety prior, and route
  diversification. Result: ~100s → **0.85s first request, ~0.8s cold, 0.02s
  cached**, startup 37s → 0.47s. Verified end-to-end over HTTP. Full write-up in
  [`ENGINEERING_NOTES.md`](ENGINEERING_NOTES.md). Then connected the frontend to
  the live engine (dev proxy + MSW off) so the whole UI runs on real data.
- *(earlier)* — Phase A built out to completion: full design system, dark mode,
  all 9 screens, the three signature pillars, interactive map, live-journey
  simulation, share, skeletons, toasts, motion, photography. Pushed to GitHub.
