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

- **Modes (v1): trains-first.** Full train routing + cross-origin; buses/cabs
  only as first/last-mile road legs. (Rail data is open; bus data isn't.)
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

Two models, live from the start, with heuristic priors so the product works
before the data matures:

1. **Confirmation / waitlist model** — gradient-boosted classifier. Features:
   WL position, quota type, class, days-to-departure, train, segment,
   season/holiday, clearance velocity. Cold-start = quota rules; improves as the
   collector accumulates PNR snapshots.
2. **Delay model** — regression → per-leg arrival-delay distribution (feeds
   connection safety). Cold-start = Kaggle seed (§C); improves from our own
   collected running-status snapshots.

**Enabling step (non-negotiable): the collector runs from week one.** Without
it "real ML" stays theoretical; with it, our dataset compounds into the moat.

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
- **Step 1 — Cross-Origin v1** — load §A network + §B gazetteer into
  Postgres/PostGIS, self-host OSRM, implement nearest-railhead + candidate
  generation, rank on computable-now factors (time, cost, train density,
  transfers). *No ML dependency.*
- **Step 2 — Collector** — daily live-status + PNR snapshots accumulating.
- **Step 3 — Delay-aware scoring** — priors (Kaggle) → ML as data grows;
  connection safety from delay distributions.
- **Step 4 — Confirmation ML** — quota heuristic → model; Redis caching.
- **Step 5 — Composite ranking + explainability** — full Route objects, fully
  computed; "why" + Plan B generators.
- **Phase C** — wire the frontend to the real API (TanStack Query;
  `VITE_USE_REAL_API=true`).

---

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
