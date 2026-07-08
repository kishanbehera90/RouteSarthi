# RouteSarthi — Phase B Plan: The Routing + Reliability Engine

Phase B builds the backend "brain" that reproduces the shapes in
[`frontend/API_CONTRACT.md`](frontend/API_CONTRACT.md) — first from seed
fixtures, then from real data, real routing, and ML. When done, the frontend
flips to the real API with `VITE_USE_REAL_API=true` and nothing else changes.

> Step-by-step progress is tracked in [`PROJECT_LOG.md`](PROJECT_LOG.md).

---

## 1. The central truth that shapes everything

*Static* data (schedules, station geo, routes, fares) is abundant and free.
The data behind our differentiators — **historical delays** and
**waitlist→confirmation outcomes** — is scarce: open datasets don't contain it
richly, and the players who have it (ConfirmTkt, RailTC, RailYatri) keep it
proprietary. So our real ML moat is something we **accumulate ourselves from
day one** via a data collector. Everything below follows from this.

## 2. Locked decisions (the strategy)

- **Modes (v1): multi-modal, rail-rich.** RouteSarthi is a *travel planner*,
  not a train app: it compares **direct road (cab/bus)** against rail and picks
  the best per trip — road wins short/poorly-railed hops, rail wins the rest.
  Rail is the deepest layer (open data); road legs use a straight-line×1.3
  heuristic now, real OSRM later. *(Revised 2026-07-05 — was "trains-first";
  a direct-road option that competes on time/cost is now core.)*
- **Data budget: strictly free / open only (₹0).** No paid API. We build our
  own collector instead.
- **City coverage: every city — Census 2011 towns (~8,000)** with coordinates,
  not just metros. Nearest-railhead handles non-station towns.
- **Collector from day one:** a daily job snapshotting live status + PNR so
  historical delay/confirmation data compounds.
- **Build order:** Cross-Origin first (static data only, no ML) → collector →
  delay-aware scoring → confirmation ML → composite ranking.

## 3. Tech stack

Python · FastAPI · PostgreSQL + PostGIS · Redis · self-hosted OSRM. Monorepo:
`backend/` alongside `frontend/`. Routing = Connection Scan Algorithm (CSA) /
RAPTOR over schedules; cross-origin candidate generation via PostGIS
`ST_DWithin`.

---

## 4. The data map (every source — all free/open)

### A. Rail network: stations + geo + routes + schedules — SOLVED
- **[datameet/railways](https://github.com/datameet/railways)** — **CC0 / public
  domain.** Stations as GeoJSON *with lat/long*, train routes as LineStrings,
  schedules (every stop, arr/dep). The backbone. No key. Caveat:
  community-gathered, a few years old → validate/refresh against live data.
- **[data.gov.in Train Time Table](https://www.data.gov.in/catalog/indian-railways-train-time-table-0)**
  — official OGD (~2,810 trains; free API key; ~2017, stale).
- Cross-checks: **[itzmeanjan/indian-railway](https://github.com/itzmeanjan/indian-railway)**,
  Kaggle [Indian Railways Dataset](https://www.kaggle.com/datasets/sripaadsrinivasan/indian-railways-dataset).

### B. Every-city gazetteer — SOLVED (how non-station towns are covered)
- **[Census 2011 Complete Towns Directory](https://www.data.gov.in/catalog/complete-towns-directory-indiastatedistrictsub-district-level-census-2011)**
  (official; ~8,000 towns).
- Coordinates: **[simplemaps India Cities](https://simplemaps.com/data/in-cities)**,
  **[Kaggle 4000+ Indian Cities lat-lon](https://www.kaggle.com/datasets/mukeshdevrath007/4000-indian-cities-names-states-lat-lon)**,
  GeoNames (CC-BY). Villages later via OSM `place=village` (Overpass).

### C. Historical delays — the hard one (delay-aware scoring + ML)
- **Seed (immediate):** Kaggle
  [Indian Railways Train Delays Dataset 2025](https://www.kaggle.com/datasets/naijilaji/indian-railways-passenger-train-delays-dataset)
  (scraped, Nov 2025) and
  [Indian Railway Delay Dataset](https://www.kaggle.com/datasets/vishwassrivastava1/indian-railway-delay-dataset).
- **Our collector (the moat):** daily poll of live running-status → per-leg
  arrival-delay snapshots, accumulating the real distribution.

### D. Live running status (feeds collector + the Lifeline)
- Free-tier / unofficial endpoints (e.g. RapidAPI
  [Train Running Status](https://rapidapi.com/shivesh96/api/train-running-status-indian-railways),
  [indianrailapi.com](https://indianrailapi.com/api-collection)) + best-effort
  polite polling. NTES is the official upstream (no open API; scraping is
  ToS-grey).

### E. PNR / waitlist-confirmation — HARDEST (confirmation ML)
- No clean open dataset. Signal = quota logic (GNWL > PQWL > RLWL) + clearance
  velocity. Path: encode quota rules as a heuristic *now*; snapshot PNR via the
  collector to learn real clearance curves over time.

### F. Fares — SOLVED
- Distance-slab × class formula (public; rationalised July 2025). Compute from
  distance + class; cross-check with `indianrailapi` fare endpoint /
  [erail calculator](https://erail.in/Indian-Rail-Fare-Calculator.html).

### G. Buses — FRAGMENTED (kept to first/last-mile in v1)
- No unified open API. GTFS only for a few (Delhi
  [OTD](https://otd.delhi.gov.in/documentation/), Kochi Metro). Aggregators
  (AbhiBus, ZuelPay → MSRTC/TSRTC/KSRTC) are paid. RedBus = deep-link only.

### H. Road first/last-mile — SOLVED, free, self-hosted
- **Self-hosted [OSRM](https://github.com/Project-OSRM/osrm-backend)** on an
  India OSM extract (Docker), with
  [India OSRM profiles](https://github.com/osrm-decentralized). Door→railhead
  drive time/distance → cab/bus fare heuristic. No API cost.

### I. Map tiles — SOLVED: OpenFreeMap (already used by the frontend).
### J. Festival/holiday calendar — confirmation seasonality + the Risk
Calendar — government holiday list / a holidays dataset.

---

## 5. "Every city of India" — the generalized cross-origin

1. User enters **any** city/town → look up coordinates in the gazetteer (§B).
2. **PostGIS `ST_DWithin`** finds candidate **boarding railheads** within an
   expanding radius, scored by distance *and* **train density** (daily trains
   serving it — from schedules §A).
3. Same for the destination's nearby railheads.
4. For each (origin-railhead → dest-railhead) pair, run the journey search and
   add the **first/last-mile** road leg (§H, OSRM).
5. Score every door-to-door option holistically and rank.

Most Indian towns aren't on a trunk line, so nearest-viable-railhead *is*
cross-origin applied universally. Big cities are the special case where the
nearest railhead is in-city.

---

## 6. The comparison algorithm (multi-factor)

**Routing:** time-expanded graph (CSA / RAPTOR) over schedules → N-best
multi-leg journeys; cross-origin candidates generated as in §5.

**Score every candidate across all factors that matter:**

| Factor | How computed |
|---|---|
| Door-to-door **time** | legs + first/last-mile (OSRM) + buffers |
| Total **cost** | train fare formula + bus/cab heuristic |
| **Confirmation probability** | ML (§E) |
| **Delay reliability** (on-time %) | ML/stats from historical (§C) |
| **Connection safety** | P(make transfer) from leg-1 delay distribution vs buffer |
| **Train density** on corridor | # daily trains on the segment → resilience/fallback |
| **# of transfers** | fewer is better |
| **First/last-mile burden** | distance railhead↔real city |
| **Comfort** | class available, late-night arrival, etc. |

**Scoring:** hard filters first (e.g. connection safety ≥ 85%), then a
**weighted composite** re-weighted by the user's `pref`
(cheapest/fastest/most-confirmed), evolving into a **learned ranking model** as
usage data arrives. Every route ships a transparent "why".

---

## 7. ML from day one (with honest cold-start)

**Status update (2026-07-08):** the delay cold-start landed — not as ML yet,
but as measured aggregates (`train_delays`: avg/p50/p80/p90/on_time_pct for
7,024 trains, from a full year of the Kaggle delay dump). That's the labelled
dataset a model would train on; before this it didn't exist. See the Phase C
ML roadmap in `PROJECT_LOG.md` for the concrete next-step spec.

Two models, live from the start, with heuristic priors so the product works
before the data matures:

1. **Confirmation / waitlist model** — gradient-boosted classifier. Features:
   WL position, quota type, class, days-to-departure, train, segment,
   season/holiday, clearance velocity. Cold-start = quota rules; improves as the
   collector accumulates PNR snapshots. **Blocked on the collector — no free
   PNR data exists yet, so there's nothing to train on. Do not build a model
   with zero real labels; the honest "(est.)" heuristic is the right interim.**
2. **Delay model** — regression → per-leg arrival-delay distribution (feeds
   connection safety). Cold-start = Kaggle seed (§C) ✅ **done** (measured
   aggregates, not yet a trained model). **Next:** a gradient-boosted regressor
   (LightGBM/XGBoost) over the same 38.4M-row dump, conditioned on
   day-of-week/month/station-position/upstream-delay — turns one flat average
   per train into a per-trip prediction. Unlocked NOW, no collector needed.

**Enabling step (non-negotiable): the collector runs from week one.** Without
it "real ML" stays theoretical for confirmation; with it, our dataset
compounds into the moat. The delay model is the exception — it can start
today on data already on disk.

---

## 8. Limitations & how we solve them

| Limitation | Mitigation |
|---|---|
| **Confirmation/PNR data is the weak spot** (free PNR is ToS-grey/flaky) | Ship confirmation as a transparent **quota-rule heuristic** (needs no dataset); collect PNR best-effort. Accept this is the piece most likely to later need a paid source or official IRCTC/CRIS access for top accuracy. |
| **Free-only delays slow to mature** | Seed the delay model from free **Kaggle** sets immediately; collector augments over time. |
| **datameet data is a few years old** | Treat as the structural backbone; validate timings against live status; refresh periodically. |
| **No open bus API** | v1 keeps buses/cabs to first/last-mile road heuristics (OSRM); scheduled-bus alternatives are a later phase. |
| **Live-status free tiers are rate-limited / unofficial** | Polite, rate-limited polling; cache aggressively (Redis); degrade to historical priors when unavailable. |
| **ToS/legal grey areas (NTES/erail scraping)** | Prefer CC0/open + free-tier APIs; avoid aggressive scraping; pursue official access for anything we productionise long-term. |
| **MapLibre/heavy deps bloat** (frontend lesson) | Keep heavy things lazy/isolated; backend computes, frontend stays light. |

---

## 9. Build order (steps)

- **Step 0 — Backend scaffold** ✅ — FastAPI serving the contract from seed
  fixtures (parity proven with a real server).
- **Step 1 — Cross-Origin v1** ✅ (OSRM deferred) — §A network + §B gazetteer in
  Postgres/PostGIS, in-memory nearest-railhead + candidate generation, ranking
  on computable factors. Multi-modal: a direct road option competes with rail.
  OSRM still pending (road = straight-line×1.3 until deploy).
- **Step 2 — Collector** ⏸️ DEFERRED — no real users to collect PNR/status from
  yet; the delay *cold-start* was instead met with a Kaggle year of delays.
- **Step 3 — Delay-aware scoring** ✅ MEASURED — a full year of observed delays
  (`train_delays`, 7,024 trains) drives on-time %, connection safety, and the
  min transfer buffer; transparent model as fallback. Fares also measured from
  real IRCTC price data. **Next intelligence step: an ML delay *predictor*
  (per-trip, conditioned on day/season) — see §7.**
- **Step 4 — Confirmation** 🟡 MODELLED (honest ceiling) — demand-proxy heuristic
  labelled "est."; becomes an ML model only once the collector lands.
- **Step 5 — Composite ranking + explainability** ✅ — full Route objects, "why"
  + date-aware Plan B, reliability breakdown (measured vs est.), seasonal-train
  date-gating.
- **Phase C** 🔄 — wire the frontend to the real API (TanStack Query;
  `VITE_USE_REAL_API=true`), deploy config, OSRM. See PROJECT_LOG Phase C for
  the ML roadmap.

---

## 9b. Step 2+3 execution plan (locked 2026-07-04) — ✅ DELIVERED 2026-07-08

> **Delivered:** the delay+fare data landed. `train_delays` (7,024 trains, a
> full year of observations), real IRCTC fares (`app/data/fare_table.json`),
> real per-stop distances (`app/data/train_cumdist.json`), running-day
> corrections, seasonal-train gating, and +1,511 trains. ETL:
> `etl/load_fares.py`, `etl/load_delays.py`, `etl/load_schedule_extra.py`. The
> collector (item 6 below) remains deferred. Original plan kept for the record.

**Goal:** replace the three heuristic trust numbers — `reliability`,
`connectionSafetyPct`, per-leg `delayProfile` — with values computed from
historical delay data. The UI already renders all three (contract fields
exist since Phase A), so this is backend-only + instant visual payoff.

**Order (respects dependencies):**
0. **Commit current work first** — two days of data-layer work is unpushed.
1. **Pytest suite** (`backend/tests/`) — lock Step 1 before changing scoring:
   contract shapes, flagship corridors return routes, direct-vs-cross-origin
   reasoning modes, fares within sane bands, weekday filter, geocode
   disambiguation cases (Gorakhpur), `_rebuild_direct`. Run via
   `.venv/Scripts/python -m pytest` with the API in-process (httpx/TestClient,
   no server needed). Benchmark stays the duration acceptance test.
2. **Delay data in** (user task): download the two Kaggle delay sets
   (naijilaji 2025 scrape; vishwassrivastava1) into
   `data/raw/candidates/delays/`. Vet on the page: columns must include train
   number + delay minutes (+ ideally station & date); note licence + rows.
3. **`etl/load_delays.py`** → new `train_delays` table:
   `(train_number, n_obs, avg_delay, p50, p80, p90, on_time_pct, source,
   as_of)` — per-train aggregate first (per-station later if data supports).
   Reuse `CODE_RENAMES`/number hygiene; expect old numbers → match rate
   reported like the station audit; unmatched trains keep priors.
3b. **Fare accuracy (folded into Step 3 — locked 2026-07-05).** Current fares
   use haversine×1.25 distance × a linear per-class rate — a rough average
   (telescopic reality makes long trips cheaper/km; misses superfast, catering
   on Rajdhani/Duronto, GST on AC). Fix: (a) use **real per-stop cumulative
   km** already in the datasets (fresh-2026 end-to-end `distance`; irctc-2023
   `stationList[].distance`) → store cumulative distance per stop, compute
   exact segment km; (b) **fit fares from the 124 MB IRCTC-2023
   `price_data.csv`** — real `totalFare` by train×class×distance → a lookup /
   light regression per class + train-type, so fares match IRCTC within a few
   rupees instead of ±15%. Deliver alongside the delay ETL (same "load a big
   CSV, aggregate, wire into the leg builder" shape).
4. **Engine wiring:**
   - `delayProfile {avgMins, onTimePct}` on every train leg (measured when
     available, else a labelled **class prior**: premium 12xxx/22xxx ≈ 75-85%
     on-time, mail/express ≈ 60-75%, passenger ≈ 50-65% — calibrated to the
     measured distribution so priors aren't invented).
   - `connectionSafetyPct` = P(incoming delay < buffer) from the incoming
     train's p50/p80/p90 (piecewise-linear empirical CDF), replacing the
     logistic prior.
   - `reliability` composite = f(legs' on-time %, connection safety,
     connectivity, first-mile); `reliabilityBreakdown` gains "On-time record".
   - Every route notes `delaySource: measured | prior` (honesty in UI later).
5. **Verify:** pytest green, benchmark unchanged, flagship corridors show
   real on-time bars in the browser; log before/after coverage (% legs with
   measured data).
6. **Step 2 skeleton — `etl/collect_status.py`:** pluggable provider
   interface with a HARD budget guard (RapidAPI free = ~10 calls/mo → useful
   only for spot checks; document indianrailapi free key as the candidate
   daily provider — user registers, we test). Collector writes raw snapshots
   to `status_snapshots`; even 20 trains/day compounds into our own delay
   distribution. Cron/scheduling = friend's task when he's back (or Windows
   Task Scheduler locally).
7. **Parallel (grindy, any time):** station-alias expansion 7.9% → <3%.

**Risks:** Kaggle delay sets may cover few trains / stale numbers (match rate
will tell us — measure before trusting); delays vary by station along the
route (v1 uses end-of-run aggregates, per-station later via collector).

## 10. Sources (quick index)

Network/geo: [datameet/railways](https://github.com/datameet/railways) ·
[data.gov.in timetable](https://www.data.gov.in/catalog/indian-railways-train-time-table-0) ·
[OSM Overpass](https://wiki.openstreetmap.org/wiki/Overpass_API).
Cities: [Census 2011 Towns](https://www.data.gov.in/catalog/complete-towns-directory-indiastatedistrictsub-district-level-census-2011) ·
[simplemaps](https://simplemaps.com/data/in-cities).
Delays: [Kaggle 2025 delays](https://www.kaggle.com/datasets/naijilaji/indian-railways-passenger-train-delays-dataset).
Live/PNR/fare: [indianrailapi.com](https://indianrailapi.com/api-collection) ·
[RapidAPI running status](https://rapidapi.com/shivesh96/api/train-running-status-indian-railways).
Road: [OSRM](https://github.com/Project-OSRM/osrm-backend).
Transit standard: [Mobility Database](https://mobilitydatabase.org/) ·
[Delhi OTD GTFS](https://otd.delhi.gov.in/documentation/).
