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

## Phase B — Backend routing + reliability engine — 🔄 IN PROGRESS

Strategy: trains-first · free/open data only · every city (~8k towns) ·
collector from day one. Full detail in [`PHASE_B_PLAN.md`](PHASE_B_PLAN.md).
Lives in `backend/`.

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
- ⏳ **Step 3 — Delay-aware scoring.** Kaggle priors → ML; connection safety.
- ⏳ **Step 4 — Confirmation ML.** Quota heuristic → model; Redis caching.
- ⏳ **Step 5 — Composite ranking + explainability.** Full computed routes.

---

## Phase C — Wire frontend ↔ real backend — 🔄 STARTED (local verification done)
A working local slice is done (dev proxy + engine-backed `/api/routes`,
`.env.local` turns MSW off — see Step 1). Remaining for full Phase C: replace
the `fetch` calls with TanStack Query (caching/loading/error states), a proper
API base-URL config for deploy (not just a dev proxy), and emit corridor
`reasoning` so the decision animation works on real searches.

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
