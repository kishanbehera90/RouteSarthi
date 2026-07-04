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
