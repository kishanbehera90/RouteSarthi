# RouteSarthi — Architecture

This document assumes you've read `Introduction.md`. It goes module-by-module
through both halves of the codebase, then walks the exact sequence of events
for a real search request, then explains every non-trivial algorithm with
its actual parameters (not just its name), then calls out coupling,
concurrency/timing behavior, and the edge cases the code explicitly guards
against.

---

## 1. Module-by-module breakdown

### 1.1 Backend (`backend/app/`)

**`config.py`** — A single `Settings` object (pydantic-settings,
`env_file=".env"`) that every other module imports `settings` from. Every
field defaults to an empty string / sensible default, so the app never
crashes just because a `.env` file is missing — modules that genuinely
*need* a setting (auth's `SECRET_KEY`, the database's `DATABASE_URL`) raise
their own clear runtime errors lazily, at first use, not at import time.

**`db.py`** — Owns exactly one thing: a `psycopg_pool.ConnectionPool`
(`min_size=1, max_size=4`), created lazily on first `get_pool()` call and
explicitly warmed at server startup (see `main.py`'s `lifespan`). Also
normalizes the `DATABASE_URL` scheme (`postgresql+psycopg://` →
`postgresql://`, since the app stores it SQLAlchemy-style but psycopg wants
the plain scheme) and disables psycopg's server-side prepared statements
(`prepare_threshold=None`) because Supabase's transaction-mode pgBouncer
pooler doesn't support them.

**`auth.py`** — All password/session logic: bcrypt hashing, JWT
encode/decode (`PyJWT`, `HS256`, 14-day expiry), and password-reset token
issuance/redemption (a random URL-safe token is emailed; only its SHA-256
hash is stored in the database, so a leaked database dump doesn't hand out
usable reset links). Every DB-touching function here opens a connection,
does one query, and releases it immediately — a deliberate rule (stated in
the module's own docstring) never to hold a pooled connection across a
bcrypt hash (a CPU-bound, ~100ms+ operation) since the pool only has 4
connections shared with the routing engine.

**`email.py`** — One function, `send_reset_email`, using Python's stdlib
`smtplib`/`email` (no external HTTP library) to send through Brevo's SMTP
relay. Always returns a boolean and never raises — a broken email provider
must not break the "forgot password" endpoint's contract of always
responding 200.

**`models.py`** — Pydantic schemas (`Route`, `Leg`, `Corridor`, etc.)
documenting the contract the frontend/mock API originally froze. In
practice, most endpoints in `main.py` return plain dicts (from `engine.py`
or `seed.py`) rather than instantiating these models — they exist primarily
as documentation/validation scaffolding, not as the actual runtime
serialization path for every response.

**`seed.py`** — Three hardcoded example corridors (Rourkela→Nashik,
Bhuj→Shimla, Imphal→Bengaluru), each with fully fleshed-out routes/legs, a
byte-for-byte port of `frontend/src/data/routes.js`. Used both as the
demo data when there's no database at all, and as the ultimate fallback
inside `/api/routes` when the real engine can't geocode a place.

**`graph.py`** — The in-memory rail-network index and the actual
graph-search routing logic. This is the module `CHALLENGES.md`'s Case
Study 1 is about. Full detail in §4.1 below.

**`metrics.py`** — Pure-function scoring models: delay/on-time estimation,
connection-safety probability, the composite `reliability` score,
confirmation-probability estimation, and fare calculation (including the
real isotonic-regression fare lookup). Also owns the demand/festival
calendar logic for the flexi-fare advisory. Nothing in this module talks to
a database or the network — everything is computed from arguments passed
in. Full detail in §4.

**`delay_model.py`** — Loads a `joblib`-serialized dict (quantile-regression
models + metadata) once at import time into a module global, and exposes
`predict(ctx)` (returns a full delay distribution or `None`) and `cdf(...)`
(reads a probability off that distribution at an arbitrary buffer value).
If the artifact file is missing, `_MODEL` stays `None` and every function
degrades to returning `None`/`False` — callers (`metrics.py`) fall back to
measured or modelled tiers. Full detail in §4.3.

**`roads.py`** — The real road-routing HTTP client (OpenRouteService or
self-hosted OSRM), with a circuit breaker and a result cache. Full detail
in §4.6/§5.

**`engine.py`** — The actual cross-origin search orchestrator: geocoding,
candidate-railhead lookup, calling into `graph.py` for the train search,
attaching road legs via `roads.py`, scoring every candidate through
`metrics.py`, ranking, diversifying, and building the exact response shape
`models.py`/the frontend contract expects. This is the biggest and most
central module — see the full request walkthrough in §2.

**`main.py`** — The FastAPI app object and every HTTP route: `/health`,
`/api/corridors[/…]`, `/api/routes[/…]`, `/api/places` (autocomplete),
`/api/delay-model-info`, and the full auth + saved-trips + recent-searches
CRUD surface. Deliberately thin — it calls into `engine`/`seed`/`auth`
and shapes the HTTP response, but contains no scoring or routing logic
itself.

### 1.2 Backend ETL scripts (`backend/etl/`)

These are one-off or periodic scripts, run manually from the command line,
never imported by the running server. Each has a detailed module docstring
explaining exactly what it reads and writes; the short version:

| Script | Role |
|---|---|
| `download.py` | Auto-fetches the two CC0/CC-BY sources (datameet, GeoNames); lists which Kaggle files still need manual download. |
| `load_v2.py` | Loads the current base timetable (a 2026 CSV scrape) into `trains`/`stops`, with a 3-layer station name→code mapper and a gap-fill from an older structured dataset. **Current, correct** loader. |
| `load_all.py` | **Deprecated.** The original 2016-timetable loader; creates a schema missing columns the current engine needs. Kept only for its stations/cities-loading logic being reused elsewhere; guarded with a loud docstring warning against running it. |
| `load_fares.py` | Fits the isotonic-regression fare table from real scraped IRCTC price data → `app/data/fare_table.json`. |
| `load_delays.py` | Streams a ~1 GB, 38.4M-row delay dump once, producing per-train delay aggregates (`train_delays` table), corrected running-days, and seasonal-train detection. |
| `load_schedule_extra.py` | Extracts real per-stop cumulative distances (→ `app/data/train_cumdist.json`) and inserts ~1,500 extra trains found in the delay dump's own companion schedule but missing from the main timetable. |
| `train_delay_model.py` | Trains the ML delay-prediction model (scikit-learn `HistGradientBoostingRegressor`, quantile loss) → `app/data/delay_model.joblib`. |
| `fix_station_mismatches.py` | Detects and (optionally) repairs stops bound to the wrong physical station (a data-quality bug class — see `CHALLENGES.md` P16). |
| `init_auth_tables.py` | One-time DDL for the `users`/`password_resets`/`saved_trips`/`recent_searches` tables. |
| `verify.py`, `benchmark.py`, `sample_trains.py` | Sanity/acceptance tooling — row-count + query checks, a 10-corridor real-world duration comparison, and a manual train-validity audit generator. |

### 1.3 Frontend (`frontend/src/`)

**`App.jsx`** — The entire route table. `/` (landing) and `/login` and
`/reset-password` are public; every other route is nested inside
`<RequireAuth>` and then `<Layout>` (header + bottom nav chrome).

**`main.jsx`** — Entry point. Its one piece of real logic: decide whether to
start the MSW mock worker (`VITE_USE_REAL_API !== 'true'`) before rendering
the app at all — this must complete first, since the very first render may
already be firing `fetch` calls the mock worker needs to intercept.

**`pages/`** — One file per screen. Each is a page-level component that owns
its own local data fetching (`useState`/`useEffect` + `fetch`, no data
library) and composes the shared `components/`.

**`components/`** — ~35 files, the shared UI vocabulary. The most
structurally important ones: `RouteCard` (a search-result summary card),
`LegTimeline` (the full per-leg itinerary breakdown, including the delay
display logic), `ReliabilityGauge` (the animated score ring + tappable
breakdown), `DecisionReasoning` (the "how we found this route" playback
animation), `RouteMap`/`MapLibreMap`/`MapplsMap` (the interactive map,
provider-swappable), `RequireAuth` (the auth gate), `Layout` (header/nav
chrome).

**`store/`** — Four independent Zustand stores, each with a narrow
responsibility and (mostly) no cross-imports between them:
- `useJourneyStore` — search form state, result filters, saved trips, recent
  searches, and cached delay-model metadata. Persisted to localStorage, but
  only its ephemeral UI-preference keys (`partialize: () => ({})` — nothing
  personal survives a page reload from localStorage; personalization is
  reloaded fresh from the server instead).
- `useAuthStore` — session token + user object + a 4-state auth status
  (`idle`/`checking`/`authenticated`/`unauthenticated`). Persists `token`
  and `user` to localStorage (so a refresh doesn't force a re-login), but
  re-validates the token against `/api/auth/me` on every app boot
  (`hydrate()`).
- `useThemeStore` — light/dark toggle, persisted directly via
  `localStorage` (not Zustand's `persist` middleware — it's simple enough
  to do by hand).
- `useToastStore` — an ephemeral, unpersisted toast-notification queue.

**`lib/api.js`** — `apiFetch`, the one authenticated-fetch wrapper. Attaches
the bearer token from `useAuthStore`, and — this is the one deliberate
cross-store coupling in the whole frontend — clears the auth session on any
401 response, so a token that's expired or been invalidated server-side
doesn't keep silently failing every subsequent request.

**`lib/utils.js`** — Pure formatting/filter helpers (`formatDuration`,
`formatFare`, `isLateNightTime`, the departure-time-window matcher).

**`data/`** — `routes.js` (the mock fixtures, mirrored by
`backend/app/seed.py`), `cityGeo.js` (a small hardcoded lat/lng lookup used
only when a leg has no real coordinates attached — i.e., only for the mock
corridors), `riskCalendar.js` (a synthetic, explicitly-fake "travel risk"
score generator used purely for the date-picker's decorative risk dots —
not connected to any real weather/disruption data).

**`mocks/`** — `handlers.js` (the MSW request handlers, reproducing exactly
the shapes `API_CONTRACT.md` defines) + `browser.js` (registers them as a
service worker).

---

## 2. End-to-end data flow: a real search request, as a sequence

This walks `GET /api/routes?from=Gorakhpur&to=Prayagraj&pref=confirmed&date=2026-08-01`
from the moment it leaves the browser to the moment it's rendered, in order.

1. **Browser → Vite dev proxy.** The frontend's `Results.jsx` calls
   `fetch('/api/routes?...')`. In dev, Vite's proxy config
   (`vite.config.js`) forwards any `/api/*` path to
   `http://127.0.0.1:8000`, so this is same-origin from the browser's
   perspective — no CORS preflight needed locally. (In production, this
   proxy doesn't exist; the two apps would need to actually share an
   origin or the frontend would need an explicit API base URL — this is
   flagged in `DECISIONS.md` as a real gap that deployment will need to
   close.)

2. **FastAPI routing.** `main.py`'s `search_routes` handler receives the
   query params, wraps a call to `engine.search(...)` in a broad
   `try/except`, and falls back to `seed.match_corridor(...)` on *any*
   exception or on the engine's own `{"error": "place_not_found"}` signal.
   This is the single most important resilience seam in the backend: a
   missing `.env`, an unreachable database, a geocoding miss, or a genuine
   bug in the engine all degrade to "serve the mock corridor if this
   happens to be one of the three we have, else return an empty route
   list" rather than a 500.

3. **`engine.search()` begins.** It parses the optional `date` string into
   a weekday name (`"MON"`…), a `days_out` integer, a month integer, and a
   day-of-week integer — these four derived values are the entire
   `ctx` dict threaded through the rest of the request. It also computes
   `metrics.demand_level(date)` once up front (for the flexi-fare
   advisory) and checks an in-process `_CACHE` dict keyed on
   `(from, to, pref, day_of_week)` — an exact cache hit short-circuits
   everything below and returns instantly.

4. **`graph.load()`** is called (a no-op after the first call in this
   process's lifetime — see §5.1) to guarantee the in-memory timetable is
   populated.

5. **Geocoding.** `engine._geocode(cur, "Gorakhpur")` and the same for
   `"Prayagraj"` each do one indexed Postgres query against the `cities`
   table (`WHERE lower(asciiname)=... OR lower(name)=...`, ordered by
   population), with a same-named-railway-station disambiguation pass when
   there's more than one candidate (see §4.5), and a fallback to the
   in-memory station index (`graph.station_geocode`) if the city table has
   no match at all (covers station-only towns like Ringas, absent from the
   GeoNames gazetteer). Results are cached in `engine._GEOCODE_CACHE`
   (capped at 5,000 entries).

6. **Candidate railhead lookup.** `graph.nearest_railheads(lat, lng,
   radius_km)` runs entirely in memory (no DB call) — a haversine distance
   from the query point to all ~8,700 stations that have at least one
   train, unioned with the nearest *major hubs* within a wider radius even
   if farther away. This runs once for the origin (starting at
   `ORIGIN_RADIUS_KM=200`, expanding to 400 then 600 if nothing's found)
   and once for the destination (`DEST_RADIUS_KM=60`, expanding to 150).

7. **Single-train (direct) candidates.** `graph.single_train(o_heads,
   d_heads, day3)` scans every train that stops at any origin-railhead
   station, looking for a *later* stop at any destination-railhead
   station on the same physical run — pure in-memory list/dict traversal,
   no database. For each train, `engine.search` keeps only the
   *shortest-first-mile* candidate (the closest usable boarding station),
   filters out seasonal trains outside their operating window
   (`graph.runs_in_month`), and filters out geographically nonsensical
   candidates (`engine._useful` — see §5.4).

8. **One-transfer candidates** (only attempted if step 7 produced fewer
   than 3 routes). `graph.one_transfer(o_heads, d_heads, day3,
   predict_ctx=ctx)` searches for origin-railhead → busy-hub →
   destination-railhead journeys with a feasible same-day connection —
   see §4.2 for the full algorithm, including where the delay model is
   consulted mid-search to set a data-driven minimum transfer buffer.

9. **Road-only candidate.** If the straight-line distance (× a road
   correction factor) is under 500 km, or if steps 7–8 found nothing at
   all, a direct door-to-door road option (`engine._road_route`) is added
   — this is what lets RouteSarthi function as a general travel planner
   for short/poorly-railed hops, not just a train-only tool.

10. **Per-route enrichment.** For every candidate, `engine._direct_route`
    or `engine._transfer_route`:
    - Resolves each first/last-mile leg's real distance/duration via
      `engine._road_km_mins` → `roads.route(...)` (real API call, or the
      haversine fallback — see §4.6).
    - Resolves each train leg's exact routed kilometres via
      `engine._rail_km` (prefers `graph.TRAIN_CUMDIST`'s real per-stop
      distances; falls back to haversine×1.25; falls back further to a
      speed-based proxy from the scheduled duration).
    - Builds the delay profile for each train leg via
      `metrics.leg_delay_profile(...)`, which internally may call
      `delay_model.predict(...)` — see §4.3.
    - Computes connection safety for any transfer via
      `metrics.connection_safety(...)`.
    - Computes per-class fares via `engine._class_fares` →
      `metrics.rail_fare` → `metrics.real_fare` (the isotonic lookup).
    - Computes the confirmation estimate via
      `metrics.confirmation_estimate(...)`.
    - Computes the composite `reliability` score via
      `metrics.route_reliability(...)`.
    - Assembles the human-readable `why` and `planB` strings.

11. **Ranking + diversification.** `engine._rank(routes, pref)` sorts by
    the requested preference (cheapest/fastest/confirmed — confirmed uses
    transfers-then-reliability-then-a-directness-tiebreak-then-time, see
    §4.7); `engine._diversify(...)` then caps near-duplicate transfer
    routes (at most 2 per hub, 1 per hub+first-train pair) while keeping
    every distinct direct train, so the result doesn't show six
    variations of the same change.

12. **Plan-B backfill.** A second pass over the final route list computes,
    for every route with a train leg, the *soonest-departing-after*
    alternative route as a "miss it → here's your next option" fallback
    string (an earlier bug — see `CHALLENGES.md` P15 — had this pick
    literally "the next item in the ranked list," which could be a train
    that had already departed hours earlier).

13. **Route store + corridor reasoning.** Every returned route is written
    into `engine.ROUTE_STORE` (an in-process dict, capped at 8,000 entries
    with a clear-all eviction — see §5.2) so `/api/routes/:id` can resolve
    it later. `engine._reasoning(...)` builds the "how we found this
    route" data structure for the decision-animation UI, in one of two
    modes (`direct` or `cross-origin`) depending on the winning route.

14. **Response assembly + caching.** The final `{corridor, routes,
    demandAdvisory}` dict is stored in `_CACHE` and returned as JSON.

15. **Frontend rendering.** `Results.jsx` receives the JSON, applies
    *client-side* filters (AC-only, fewer-transfers, avoid-late-night,
    travel-class, departure-time-window — all computed in
    `useMemo`, matching against fields the backend already computed), tags
    the single cheapest/fastest visible option, and renders up to 6
    `RouteCard`s with a "show more" expander.

16. **Route detail.** Clicking "View full plan" navigates to
    `/routes/:routeId`, which does a second `fetch('/api/routes/:id')` —
    resolved by `main.py`'s `get_route` via `engine.get_stored_route(id)`
    (checks the in-process store first, then attempts to statelessly
    rebuild a *direct*-type route purely from the graph if the store
    missed — transfer routes cannot be rebuilt this way and will 404 if
    the store has been cleared or the server restarted since the search
    that produced them).

---

## 3. Backend module coupling (import graph)

```
main.py ──► auth.py, delay_model.py, seed.py, engine.py, graph.py, config.py, db.py
engine.py ──► graph.py, metrics.py, roads.py, db.py
graph.py ──► metrics.py, db.py
metrics.py ──► delay_model.py
delay_model.py ──► (no internal imports; standalone)
roads.py ──► config.py
auth.py ──► config.py, db.py
email.py ──► config.py
```

The one **non-obvious, deliberate** coupling: `graph.py` imports
`metrics.py` (not the reverse) specifically so that `graph.one_transfer`'s
connection-feasibility gate can consult the delay model's predicted p50
*without* `graph.py` importing `delay_model.py` directly — it goes through
`metrics.predicted_p50(...)`, a thin wrapper, keeping the dependency chain
strictly `graph → metrics → delay_model` and never the reverse. This is
called out explicitly in `predicted_p50`'s own docstring as intentional,
because `metrics.py` is meant to be the single place that assembles
delay-model feature context — duplicating that assembly logic inside
`graph.py` would be the alternative, and it was rejected.

`engine.py` is the only module that imports `roads.py` — road-routing is
strictly a leg-building concern, never touched by the graph search itself.

---

## 4. Key algorithms — what they do, and the actual implementation

### 4.1 In-memory rail-network graph and search (`graph.py`)

**What it does, in plain English:** Instead of asking a database "find me
a train from station A to station B," the entire timetable is loaded once
into plain Python dictionaries, and a "search" is just scanning those
dictionaries — the same fundamental approach real-world transit-routing
algorithms (RAPTOR, the Connection Scan Algorithm) use.

**The actual data structures**, populated once per process (from a local
disk cache if present, else from Postgres, then written back to that
cache):
- `TRAIN_STOPS: dict[train_no, list[(station_code, arr_min, dep_min, day)]]`
  — every train's full ordered stop list, arrival/departure as
  minutes-since-midnight, plus which journey-day (1, 2, 3…) that stop falls
  on.
- `STATION_IDX: dict[station_code, list[(train_no, index_in_that_trains_list)]]`
  — the reverse index: for a given station, every train that stops there
  and at which position.
- `TRAIN_DELAY`, `TRAIN_CUMDIST`, `TRAIN_MONTHS`, `TRAIN_DAYS`,
  `TRAIN_CLASSES`, `HUB_TRAINS`, `STATION_COORD`, `STATION_NAME` — parallel
  lookup tables for delay stats, real routed distances, seasonal operating
  windows, running days, coach classes, per-station train density, and
  geo/display data.

**`single_train(boards, alights, day3)`** — for every train that stops at
any of the candidate boarding stations, scan forward through its stop list
for the first stop at any candidate alighting station that comes strictly
later (`in_train` time must be positive after accounting for
day-of-journey). Each candidate boarding/alighting pair is also checked
against `stop_detour_km` (see §5.5) before being accepted.

**`one_transfer(boards, alights, day3, predict_ctx)`** — two-phase search:
1. *Leg 1:* for every train reachable from a boarding station, find every
   **hub** it passes through (a hub = a station in `HUB_TRAINS`, i.e.
   `num_trains >= HUB_MIN_TRAINS = 80`, that isn't itself a
   board/alight candidate), keeping only the *fastest* way to reach each
   distinct hub. Then take only the `MAX_REACHED_HUBS = 40` busiest of
   those reached hubs to bound the search.
2. *Leg 2:* for each of those hubs, compute a **minimum transfer buffer**
   (see below), then scan every *other* train departing that hub for a
   feasible onward connection (`wait` between `CONN_MIN_BUFFER` and
   `CONN_MAX_WAIT=360` minutes) to any alighting station.

   The minimum buffer is computed **once per hub** (not once per candidate
   train — a deliberate performance choice, since `t1`/`hub`/`arr_hub` are
   loop-invariant across every leg-2 candidate at that hub): if a dated
   search context was supplied and the incoming train has at least 15
   measured delay observations, it calls `metrics.predicted_p50(...)` for a
   date-conditioned typical delay; otherwise it falls back to that train's
   flat measured p50. The buffer is
   `max(CONN_MIN_BUFFER=30, min(round(p50), 90))` minutes — i.e., a
   chronically 70-minute-late train needs a 70-minute buffer to even be
   offered as a transfer, but no train's typical lateness can force a
   buffer above 90 minutes (a deliberate cap, so one very unreliable train
   doesn't make every transfer through its hub look absurdly conservative).

   All feasible (leg1, leg2) pairs are deduplicated by
   `(board, hub, alight)`, keeping only the fastest total; the final
   result is the 8 fastest journeys overall.

**Key tunables and what they control** (`graph.py` module constants):
`HUB_MIN_TRAINS=80` (how busy a station must be to count as a transfer
hub), `MAX_REACHED_HUBS=40` (search breadth cap), `CONN_MIN_BUFFER=30` /
`CONN_MAX_WAIT=360` (transfer feasibility window bounds),
`GUARD_DETOUR_KM=150` (the geo-sanity threshold, §5.5), `RAILHEAD_NEAR=6` /
`RAILHEAD_HUBS=6` / `HUB_RADIUS_KM=500` (candidate-railhead search
breadth).

### 4.2 Nearest-railhead lookup (`graph.nearest_railheads`)

Plain English: "which stations should I even consider boarding/alighting
at, for this place?" Implementation: a haversine great-circle distance from
the query lat/lng to every station with at least one train (roughly 8,700
of them), kept if within `radius_km`; separately, any station with
`num_trains >= 60` within a much wider `HUB_RADIUS_KM=500` is *also* kept
even if farther than `radius_km` — this is what lets a remote place whose
nearest station is a tiny dead-end halt still surface the real regional
gateway hub (e.g. Guwahati for Imphal) as a candidate. The two lists are
merged, deduplicated by station code, and returned as a dict keyed by code
for O(1) lookup later. This whole operation is a few thousand haversine
calls in pure Python and takes well under a millisecond — there is no
spatial index involved (PostGIS was used for exactly this originally, and
was removed for performance — see `CHALLENGES.md` Case Study 1, Layer 2).

### 4.3 Delay prediction (`delay_model.py` + the training script)

Plain English: instead of "this train averages 39 minutes late" (one flat
number for every trip on that train, forever), predict "on a Tuesday in
July, arriving at this station, ~55 minutes late" — a number conditioned
on the actual trip being planned.

**Training** (`etl/train_delay_model.py`, run offline, not at serve time):
streams a 38.4-million-row historical delay dump once, reservoir-samples up
to `CAP_PER_TRAIN=400` observations per train (bounding memory and
preventing a handful of very busy trains from dominating the training set)
across ~7,000 trains with a known baseline, joins in that observation's
scheduled position along the route (from a separate schedule file) and its
actual day-of-week/month, and fits **six independent
`HistGradientBoostingRegressor` models**, one per quantile level in
`QUANTILES = [0.1, 0.25, 0.5, 0.75, 0.9, 0.99]`, using `loss="quantile"`.
Features (`FEATURES` list, in this exact order, since the serialized model
expects a bare numpy array with no column names): `baseline` (the train's
flat historical average — the "prior" being refined), `tier` (categorical:
premium/superfast/express/passenger), `dist_from_origin`, `frac_route`
(distance travelled ÷ total route distance — optional, `NaN` when the
alighting station's code doesn't appear in the routed-distance table),
`sched_hour`, `day_offset` (0 = same day, 1 = next day, …), `dow`, `month`.
`HistGradientBoostingRegressor` handles `NaN` features natively, so a
missing position doesn't kill the whole prediction, only makes it slightly
less precise.

**Serving** (`delay_model.predict(ctx)`): assembles one feature row from a
context dict, runs all six quantile models, **re-sorts the six outputs**
(quantile models are fit independently and can — rarely — cross each
other, so monotonicity is enforced post-hoc, not guaranteed by the fitting
process itself), and returns
`{avgMins, p50, p90, quantiles: {level: minutes}}`. Critically, **`avgMins`
is not a seventh model's output** — it is computed by
`mean_from_quantiles(quantiles)`, which numerically integrates the
piecewise-linear quantile curve (trapezoid rule, anchored at `(0, 0min)` on
the low end and a flat extrapolation of the top fitted quantile on the high
end). This is a deliberate architectural choice explained fully in
`DECISIONS.md` and `CHALLENGES.md` P20: an earlier version trained a
*separate* mean-squared-error model for the average, and because it had no
mathematical relationship to the five independently-trained quantile
models, the displayed "average" could visually contradict the displayed
percentiles on a real prediction.

**`cdf(quantiles, x)`** — the inverse operation: given the predicted
quantile dict, what's `P(delay <= x)`? Implemented as monotone linear
interpolation between the known (level, minutes) points, with a synthetic
low-end anchor at `(lowest_level - 0.10, min(lowest_minutes, 0))` so the
probability is well-defined even for very small `x`, and the result
clamped to `[0.02, 0.99]` (never claiming absolute certainty in either
direction). This is what powers both "on-time %" (`cdf(quantiles, 30)`) and
connection safety (`cdf(quantiles, buffer_mins)`) — the same function, same
curve, for both, so they can never disagree with each other or with the
displayed p50/p90.

**`MAX_RELIABLE_DAY_OFFSET = 1`** — the model refuses to produce a
prediction at all for `day_offset > 1` (i.e., any leg more than one day
into a multi-day journey), falling back to the measured/modelled tier
instead. This threshold exists because the training script's own
stratified calibration report (broken out by `day_offset` bucket, not just
one aggregate number) showed a p50 mean-absolute-error of 70.7 minutes for
`day_offset >= 2` — worse than the ~29-minute flat historical baseline the
model exists to beat. See `CHALLENGES.md` P20 for the full investigation
that produced this constant.

### 4.4 Confirmation estimate (`metrics.confirmation_estimate`)

This is explicitly **not** a model fit to any real seat/waitlist data —
there is no free source of that data. It's a transparent heuristic:
`base = max(class-specific availability score for the easiest offered
class)` (a hand-set table, `_CLASS_AVAIL`, e.g. 2S=84, 1A=54), adjusted by
`_TIER_DEMAND` (premium trains −12, passenger trains +8), by lead time
(`min(16, max(-6, days_out * 0.5))` — more advance booking helps, capped),
and by `_PEAK_MONTHS` (−12 in summer-holiday/festival months). Clamped to
`[20, 96]`; the resulting percentage also determines the discrete state
(`confirmed` if ≥78, `rac` if ≥55, else `waitlisted`). Every place this
number appears in the UI is labelled "(est.)" — this is deliberate honesty
about the number's nature, not an oversight.

### 4.5 Rail-aware geocode disambiguation (`engine._geocode` + `_near_named_station`)

Plain English: when a place name matches more than one row in the city
gazetteer (GeoNames contains real duplicate-name artifacts — e.g. a
"Gorakhpur" in Haryana with a *larger* recorded population than the real
Gorakhpur in Uttar Pradesh), don't just trust population ranking. Instead,
among the candidates, prefer the one that has a **real railway station
sharing its name within 20 km** (`_near_named_station`) — since this is
fundamentally a rail-routing app, "the real city" is best defined as "the
one the rail network agrees is there." If a `state_hint` was supplied (the
autocomplete UI sends `"City, State"` once a user picks a suggestion), the
candidate list is filtered to that state first, before the station check.
See `CHALLENGES.md` P10 for the exact bug this was built to fix.

### 4.6 Real road-routing with graceful degradation (`roads.py`)

Two backends tried in priority order: self-hosted OSRM (if `OSRM_URL` is
set) first, else OpenRouteService (if `ORS_API_KEY` is set), else neither
— in which case `route()` returns `None` immediately and the caller
(`engine._road_km_mins`) falls back to a haversine-distance-based estimate
with `mins=None` (letting the caller derive a duration from a flat
`ROAD_KMPH=40` assumption instead).

Two resilience mechanisms layered on top of the actual HTTP call:

- **A circuit breaker.** `_TIMEOUT=1.5` seconds per call; on *any*
  exception (timeout, connection refused, malformed response, HTTP error
  status), the module sets `_disabled_until = now + 30 seconds` and returns
  `None` — every call during that 30-second window skips the network
  entirely rather than re-attempting. This exists because a measured,
  real-world test against a refused connection took ~2.9 seconds before
  failing (close to a naive 3-second timeout) — without the breaker, a
  single search with a dozen-plus road legs would pay that cost once *per
  leg*, and every subsequent search would pay it again for as long as the
  outage lasted.
- **A result cache.** `_route_cache`, a plain in-process dict keyed on
  `(round(lat1,4), round(lng1,4), round(lat2,4), round(lng2,4))` —
  successful lookups only (failures are never cached, so a transient outage
  can recover once the circuit breaker's cooldown expires). This exists
  because a single search's several candidate routes frequently share an
  identical first/last-mile city pair (e.g. every hub-via-Sambalpur route
  needing the same "Manmad Jn → Nashik" leg); without the cache, each one
  fired its own independent network call for identical coordinates,
  measurably burning through OpenRouteService's free-tier rate limit on
  pure duplicates within a single request.

Both mechanisms are backend-agnostic — they apply identically whichever of
OSRM/ORS is actually configured.

### 4.7 Ranking (`engine._rank`)

`pref="cheapest"` sorts purely by `totalFareInr` ascending;
`pref="fastest"` purely by `totalTimeMins` ascending. The default
(`"confirmed"`, and anything else) sorts by a tuple:
`(transfers, -reliability, 1 if cross-origin else 0, totalTimeMins)` — i.e.
fewer transfers always wins first, then higher reliability, and — the
deliberate tie-break — if two routes are equally reliable, a friction-free
**direct** board wins over a cross-origin one (don't send someone on a road
trip to another town's railhead when their own station offers an
equally-reliable train), with total time as the final tiebreaker.

### 4.8 Isotonic-regression fare curve (`etl/load_fares.py` + `metrics.real_fare`)

Plain English: given real (distance, fare) pairs scraped from IRCTC pricing
data, fit a curve that (a) never predicts a lower fare for a longer trip,
and (b) uses every sample instead of averaging them away into coarse
buckets. Implementation: `sklearn.isotonic.IsotonicRegression(increasing=True)`
fit directly on every sample per travel class (SL/3A/2A/1A/CC/2S), then the
fit's own step breakpoints (`X_thresholds_`/`y_thresholds_` — the actual
points its underlying PAVA algorithm found, 52 to 345 per class depending on
how much the data varies in that range, *not* an arbitrary fixed grid) are
saved to `app/data/fare_table.json`. A per-class linear fit is saved
alongside as an extrapolation fallback for distances beyond the sampled
range. At serve time, `metrics.real_fare` does simple linear interpolation
between the two nearest saved breakpoints — no scikit-learn dependency is
needed at serve time at all, only at the one-time ETL step.

---

## 5. Concurrency, timing-sensitive, and networking behavior

### 5.1 The in-memory graph is loaded once per process, guarded by a lock

`graph.load()` uses a module-level `threading.Lock` and a `_loaded`
boolean so concurrent requests during the (rare, startup-only) loading
window don't race to build the structure twice. In normal operation,
`main.py`'s FastAPI `lifespan` calls `graph.load()` once at server startup,
so every request after that sees `_loaded=True` and returns instantly.

### 5.2 Every in-process cache/store resets on restart and has an eviction cliff, not an LRU

`engine._CACHE` (search results), `engine._GEOCODE_CACHE`, and
`engine.ROUTE_STORE` are all plain dicts with a **hard cap and a
clear-everything eviction** (`if len(_CACHE) >= _CACHE_MAX: _CACHE.clear()`)
rather than a proper LRU. This is a deliberate simplification, not an
oversight — see `DECISIONS.md` — but it means a burst of unique searches
right at the cap boundary can cause a visible cache-cold moment for
*everyone's* subsequent request, not just the one that tipped it over.
None of these survive a server restart; a multi-worker deployment (not
currently used — see `DECISIONS.md`) would also give each worker its own
independent copy of all three, silently reducing the effective cache hit
rate.

### 5.3 The road-routing circuit breaker's 30-second cooldown is genuinely time-based, not request-count-based

`roads._disabled_until` is compared against `time.monotonic()` — this
means the cooldown expires in real wall-clock time regardless of how many
(or how few) requests arrive during that window, and is shared across
*every* concurrent request in the process (not per-caller), which is
intentional: the underlying assumption is "the road-routing service itself
is down," a fact about the world, not about any one request.

### 5.4 Geographic-progress filtering (`engine._useful`)

Every candidate rail leg (both direct and one-transfer) is checked: the
alighting station must be strictly closer to the destination than the
boarding station (`a_to_d < b_to_d - 5` km) **and** strictly farther from
the origin (`a_to_o > b_to_o - 5` km). This kills an entire class of
nonsense routes where a nearby big hub gets paired with a nearby station
in a way that produces a train ride that doubles back toward — or even to
— the traveler's own starting town. The 5 km slack on both comparisons
exists to avoid rejecting legitimate short legs purely from
haversine-vs-real-road-distance noise. If either endpoint's coordinates are
missing, the filter passes everything through rather than guessing (`return
True` — the deliberate stance throughout this codebase is "don't
over-filter when you can't judge").

### 5.5 The mis-located-station detour guard (`graph.stop_detour_km` + `GUARD_DETOUR_KM=150`)

For any candidate board/alight stop, compute how much extra back-and-forth
distance that stop's *stored coordinate* adds versus a straight line
between its immediate neighbours in that same train's path. If a stop adds
more than 150 km of pure detour versus its neighbours, it's refused as a
board/alight point (though it's still fine as an interior pass-through
stop the traveler never gets off at). This is a **local, per-candidate**
check — deliberately not a global blocklist of "known bad" station codes,
because a station can look like an outlier purely because its *neighbour*
in one particular train's path has bad data, while the station itself is
perfectly legitimate elsewhere. See `CHALLENGES.md` P16 for the exact
incident (a train appearing to detour ~340 km into Jammu & Kashmir and
back) that this guard was built to make structurally impossible, even for
station-identity errors the data-repair script hasn't caught yet.

### 5.6 Midnight-wraparound connection-wait arithmetic (a known, explicitly-documented limitation)

`graph.one_transfer`'s `wait = (dep2 - arr_hub) % 1440` computes the wait
between an arriving train and a candidate onward train purely as
clock-time-of-day, modulo 1440 minutes (24 hours). This **cannot
distinguish** "the onward train leaves 30 minutes later today" from "the
onward train leaves 30 minutes later, but tomorrow." The code comment
directly above this line calls this out as a known limitation whose error
skews conservative — `CONN_MAX_WAIT=360` minutes rejects anything that
*looks* like a very long wait, so the failure mode is "miss a legitimate
overnight connection," never "invent an impossible one." A fully
day-aware version was explicitly deferred, not forgotten.

---

## 6. Edge cases the code explicitly handles

| Edge case | Where it's handled |
|---|---|
| A place name matches two real, differently-located, same-named entries (e.g. two "Gorakhpur"s in different states) | `engine._geocode` + `_near_named_station` (§4.5) |
| A user picked a station-specific autocomplete suggestion, not a city | `engine._geocode`'s `state_hint == "railway station"` branch routes straight to `graph.station_geocode` |
| A town has no entry in the city gazetteer at all, but does have a railway station (e.g. Ringas) | `graph.station_geocode` fallback inside `_geocode`; `graph.station_suggestions` inside `/api/places` |
| A schedule stop is bound to the wrong physical station (data-quality bug) | `graph.stop_detour_km` guard at search time (§5.5) + the offline `fix_station_mismatches.py` repair |
| A seasonal/special train (e.g. a Magh Mela special) that only runs a few weeks a year | `graph.runs_in_month` — hidden entirely on an undated search, hidden outside its window, shown with a "Seasonal" badge inside it |
| Unknown running days for a train | `graph.runs_on` treats an empty/unknown `days_of_week` as "assume daily" (conservative — never hides a real option due to missing metadata) |
| A route that would require riding a train back toward, or to, the traveler's own origin | `engine._useful` (§5.4) |
| A premium train's generic `classes` column lists classes it doesn't actually sell (e.g. a Rajdhani "offering" Sleeper) | `engine._offered_classes`, with explicit guards for the ambiguous brand names "Tejas Rajdhani" (AC-sleeper despite "Tejas") and "Vande Bharat Sleeper" (AC-sleeper despite "Vande") |
| A thin/unreliable measured-delay sample (too few real observations to trust) | `metrics.leg_delay_profile`'s `has_baseline` check requires `nObs >= 15` before treating a train's measured stats as trustworthy; falls back to the crude modelled tier otherwise |
| A journey leg more than 1 day into a multi-day trip | `delay_model.MAX_RELIABLE_DAY_OFFSET=1` refuses to predict there at all (§4.3) |
| A road-routing feature's distance lookup missing a routed-distance table entry for either train's station code | `engine._delay_ctx`/`delay_model._feature_row` treat position features as optional (`NaN`), not fatal |
| The road-routing service (OSRM/ORS) is unconfigured, down, or rate-limited | `roads.route()` always returns `None` on failure, never raises; circuit breaker + result cache (§4.6) |
| No database reachable at all | Every DB-touching path in `main.py`/`engine.py` is wrapped so the response degrades to the 3 seed corridors instead of a 500 |
| A transfer-route detail page requested after a server restart (its ID was never in the stateless-rebuildable direct-route format) | `engine.get_stored_route` attempts `_rebuild_direct` for direct-shaped IDs; transfer IDs genuinely 404 in this case — a documented, not-yet-fixed gap (Redis is the planned fix) |
| A user tries to access any page except the landing page / auth flow without a valid session | `RequireAuth.jsx`'s 4-state status machine, redirecting to `/login` with the originally-requested path preserved for post-login redirect |
| A different user logs in on the same browser tab right after another user's session | `AuthMenu.jsx`'s logout explicitly clears `useJourneyStore`'s personalization state and does a hard `window.location.href` navigation (not a client-side route change) specifically to guarantee no stale personalized data survives even for a single frame |
| The same (from, to) recent-search recorded with different letter-casing | `recent_searches` table has a unique constraint on lowercase `(from_key, to_key)`, upserting rather than duplicating |
| A festival/holiday date requested for a regulated (non-premium) train | `metrics.flexi_fare_multiplier` returns exactly `1.0` for any non-premium tier — regulated fares are never varied, by construction, regardless of demand score |
