# RouteSarthi — Engineering Notes (problems, fixes & impact)

Plain-language case studies of the hard problems in this project. Each one is
written so it's useful later — for interviews, for the team, and for future-me.

**Every entry follows the same shape:**
- **Symptom** — what looked wrong.
- **How I found the cause** — the diagnosis steps.
- **Root cause** — the real reason.
- **The fix** — what I changed.
- **Why this fix (and what I rejected)** — the trade-off thinking.
- **Impact** — measured before/after.
- **Interview soundbite** — a one-paragraph way to tell the story.

> On screenshots: for terminal/performance problems the real evidence is
> *measured numbers*, so those are captured as before/after tables here. For
> visual UI bugs going forward, I'll save a screenshot under `docs/img/` and
> embed it in the relevant entry.

---

# ⭐ Case Study 1 — Cutting route search from ~100 seconds to ~0.8 seconds

This is the headline one. It's a good story because it was solved in **layers**:
each fix removed the current bottleneck and *revealed the next one*. That
"peel the onion" process is the real lesson.

### Symptom
The cross-origin route search (e.g. Bhuj → Shimla, which needs a train change)
took **80–100 seconds** per request. Simple direct searches took ~7 seconds.
Both are unacceptable — a user won't wait.

### Background (what the search has to do)
For any two places it must: find nearby railway stations, then find train
journeys between them (including journeys that change trains at a busy hub).
The data: **8,990 stations, 417,080 schedule stops, 5,208 trains, 557,994
towns**, all in a hosted Postgres database (Supabase, in Tokyo).

---

## Layer 1 — Stop doing routing inside the database

### How I found the cause
I timed each part. The slow part was the transfer search, which ran SQL queries
that **joined the 417,000-row `stops` table to itself** to find "train reaches
a hub, then another train continues from that hub." It did this with lists of
~2,000 station codes, **multiple times per request**, each query travelling over
the network to the database — and it even opened a *second* database connection
mid-request.

### Root cause
A database is great at looking things up by index, but **bad at this kind of
repeated graph search** — especially when every query is a network round-trip to
a server in another country. We were asking the database to do a job it's wrong
for.

### The fix
Load the **entire timetable into memory once** when the server starts
(`app/graph.py`), as plain Python dictionaries:
- `train → its ordered list of stops`
- `station → which trains stop there`

Then routing (single-train and one-transfer) is just **scanning those
dictionaries in memory** — no database, no network.

### Why this fix (and what I rejected)
- This is literally how real transit routing engines (RAPTOR / Connection Scan
  Algorithm) work — they operate on in-memory arrays. The dataset is small
  (~417k rows ≈ tens of MB in RAM), so it fits easily.
- **Rejected:** optimising the SQL (better indexes, smaller `IN` lists,
  precomputed "segments" table). It would have helped a bit but kept the
  fundamental problem — routing over a network, per request — and a segments
  table would balloon to millions of rows.

### Impact
Routing itself went from **~100 s → 0.06 ms** (measured on a synthetic network,
with assertions proving it still finds the right journeys and correctly rejects
an impossible 5-minute connection). ✅

---

## Layer 2 — Stop asking the database for "nearest stations" too

### How I found the cause
After Layer 1, routing was instant but **cold searches were still 3–11 s**. I
timed again: the time was now in the **two PostGIS "nearest railway station"
spatial queries** (one for the origin, one for the destination) — each a
heavy query with window functions, run over the network every request.

### Root cause
Same theme as Layer 1: a per-request, network-bound database query for something
small. There are only 8,990 stations.

### The fix
Load the 8,990 stations into memory too, and compute nearest stations with a
**haversine distance** (the standard great-circle distance formula) in Python —
~8,990 quick calculations, **under a millisecond**.

### Why this fix
8,990 distance calculations in Python is trivially fast and removes two network
round-trips. PostGIS is the right tool at *national scale with millions of
points*; for 9k points in RAM it's overkill.

### Impact
Removed two network queries per request. (The remaining slowness moved to the
next layer.) ✅

---

## Layer 3 — Fix a database query doing a full-table scan

### How I found the cause
Still ~2–4 s. The only database call left per request was **geocoding** (turning
"Bhuj" into coordinates). I looked at the query:
`WHERE lower(asciiname) = ... OR lower(name) = ...`. I had an index on
`lower(asciiname)` but **not** on `lower(name)`.

### Root cause
Because of the `OR` on an **un-indexed** expression, Postgres couldn't use the
index — it scanned **all 557,994 town rows** on every lookup, twice per request.

### The fix
Add the missing index: `CREATE INDEX cities_name_lower_idx ON cities (lower(name))`.
Now Postgres can use both indexes (a "bitmap OR") and jump straight to the row.

### Why this fix
An index is the textbook fix for a full-table scan on a filter column. Took 1.9s
to build once; pays off on every search forever. (Also added it to the ETL so a
fresh database rebuild includes it.)

### Impact
Geocode went from a 558k-row scan to an index lookup. ✅

---

## Layer 4 — Stop opening a new database connection every request

### How I found the cause
Now ~2 s, and the **very first** request was ~6 s. The remaining cost was
**opening a database connection** — the TLS handshake + pooler authentication to
the Tokyo server — which happened fresh on every request.

### Root cause
Each search did `connect()` → new connection → ~1 s of setup, just to run two
tiny indexed lookups.

### The fix
A **connection pool** (`psycopg_pool`): keep a few connections open and reuse
them, instead of opening/closing one per request. And **warm the pool at server
startup** so even the first real request reuses a ready connection.

### Why this fix
A connection pool is the standard way to avoid per-request connection overhead —
the handshake is the expensive part, so you pay it once and reuse. Warming it at
startup moves that one-time cost out of the user's first request.

### Impact
First request **6 s → 0.85 s**; subsequent cold searches **~0.79 s**. ✅

---

## Layer 5 — Make startup fast *and* reliable (local cache)

### How I found the cause
Loading the timetable from the database at startup took **37 seconds**, and once
it **failed mid-download** with `lost synchronization with server` — the
database's connection pooler dropped the big 417k-row transfer.

### Root cause
Re-fetching 417k rows over the pooler on every server start is **slow and
fragile** — the pooler isn't built for one giant result set, so it occasionally
kills the stream.

### The fix
After building the in-memory graph from the database the first time, **save it to
a local cache file** (`data/processed/graph_cache.pkl`). Every later startup
loads from that file in ~0.5 s — no big network fetch. The database build also
got a **3× retry** for the rare transient drop.

### Why this fix
The timetable is static data — there's no reason to re-download it from another
country every boot. A local cache is the obvious win; the retry handles the rare
case when we *do* rebuild.

### Impact
Startup **37 s → 0.47 s**, and no more fragile large fetch on every boot. ✅

---

## Layer 6 — Cache the answers (repeat searches)

### The fix
An **in-process result cache**: the same `from/to/pref` returns the stored result
instantly. Same idea for geocoding (cache each place's coordinates).

### Impact
Repeat searches: **~0 ms** (0.00–0.02 ms). ✅

---

## The whole journey — before & after

| Metric | Before | After |
|---|---|---|
| Transfer search (cold) | **~80–100 s** | **~0.8 s** |
| Direct search (cold) | ~7 s | ~0.8 s |
| First request after startup | ~100 s | **0.85 s** |
| Repeat (cached) search | — | **0.02 ms** |
| Server startup (graph load) | 37 s | **0.47 s** |
| Pure routing compute | ~100 s | **0.06 ms** |

### Interview soundbite
> "A route search was taking 100 seconds. I profiled it and found we were doing
> graph search *inside the database* — self-joining a 417k-row table over the
> network, per request. I moved the timetable into memory and routed there
> instead (the standard transit-routing approach), which dropped compute to
> sub-millisecond. That exposed the next bottleneck — spatial queries — so I
> moved those in-memory too; then a geocode query doing a full-table scan, which
> I fixed with an index; then per-request connection setup, which I fixed with a
> warmed connection pool; and finally a slow, fragile 37-second startup, which I
> fixed by caching the built graph to disk. End result: 100 s → 0.8 s cold,
> ~instant cached. The big lesson was to **measure, fix the top bottleneck, then
> re-measure** — the cause kept moving."

---

# Other problems & how I solved them

## P2 — Couldn't connect to the database at all (the Supabase saga)
- **Symptom:** connection attempts failed three different ways in a row.
- **Causes & fixes, in order:**
  1. **Password had special characters** → it broke the connection URL parsing
     (part of the password got read as the hostname). *Fix:* use an
     alphanumeric-only database password.
  2. **"Direct connection" host is IPv6-only** → it wouldn't resolve on a normal
     IPv4 home network. *Fix:* use Supabase's **pooler** connection string.
  3. **College Wi-Fi blocked the database port (5432)** entirely. *Fix:* the
     "Transaction pooler" uses port **6543**, which wasn't blocked; switching
     networks also fixed it.
- **Why it matters / impact:** these are classic "works on my machine" network
  gotchas. Documented in `PROJECT_LOG.md` so a teammate setting up their own
  `.env` doesn't lose an hour rediscovering them.
- **Interview soundbite:** "Three separate connectivity issues — URL-encoding,
  IPv6-only DNS, and a blocked port — each with a different fix. The lesson:
  read the actual error text; each one literally told me the cause."

## P3 — Cross-origin search returned **0 routes** for the most important cases
- **Symptom:** Bhuj→Shimla and Imphal→Bengaluru (the flagship "poorly-connected
  origin" cases) returned nothing.
- **Diagnosis:** I added debug prints at each stage. Two real findings:
  1. For Imphal, the *nearest* stations were tiny dead-end halts with no useful
     connections — "nearest" was the **wrong heuristic**; the real gateway
     (Guwahati) is farther away.
  2. Bhuj→Shimla needs a **train change** (Bhuj→Ahmedabad→…→Shimla); my first
     engine only looked for a *single* through-train.
- **Fix:** (a) pick candidate railheads as "nearest stations **+** nearest
  *major hubs* even if farther"; (b) add **one-transfer** routing (origin →
  busy hub → destination, with a feasible connection time).
- **Why:** this is exactly the product's core idea ("route via a smarter hub"),
  so it had to be in the algorithm, not patched around.
- **Impact:** all three flagship corridors now return sensible routes
  (Imphal→Bengaluru via Guwahati, etc.).

## P4 — Frontend bundle was huge after adding the map
- **Symptom:** adding MapLibre ballooned the main JS bundle to ~1.5 MB.
- **Fix:** **lazy-load** the map component (`React.lazy` + `Suspense`) so its
  ~1 MB only downloads when a user actually opens a Route Detail page.
- **Why:** most pages don't need the map; making every visitor download it is
  wasteful. Code-splitting loads it on demand.
- **Impact:** main bundle back to ~465 KB; map chunk loads only when needed.

## P5 — Connecting the frontend to the real engine
- **Problem:** three mismatches to bridge. (1) The detail page fetches a route by
  **id**, but engine route ids are generated per search and aren't in the seed
  data → it would 404. (2) The map needs **coordinates**, but engine legs used
  station *names*. (3) Frontend and backend run on **different ports**.
- **Fixes:** (1) a small in-memory **route store** on the backend so
  `/api/routes/:id` can return a route from the last search; (2) attach real
  **station coordinates** to every leg so the map draws; (3) a **Vite dev proxy**
  (`/api` → backend) plus a flag to turn the mock layer off — same-origin, so no
  CORS needed.
- **Impact:** the whole UI (Search → Results → Route Detail + map) now runs on
  live data for any Indian city pair.

## P6 — Animations looked "stuck" in the preview tool (a verification gotcha)
- **Symptom:** in the preview, animated elements sometimes appeared frozen at
  opacity 0; screenshots intermittently timed out.
- **Root cause:** the preview tab is often *backgrounded*, so the browser pauses
  `requestAnimationFrame` — animations never advance. **Not a real bug.**
- **Fix / how to verify:** take a screenshot (which brings the tab forward and
  lets animations finish), or check the settled DOM state instead of mid-anim.
- **Why note it:** it wasted time once; now it's written down so it doesn't again.

## P7 — The repo worked on exactly one laptop (reproducibility audit)
- **Symptom:** after a fresh `git pull` on a second machine, the backend
  couldn't run at all — and wouldn't have even served the seed corridors.
- **How I found the cause:** attempted a from-scratch setup on the second
  machine and traced each failure instead of copying working state over.
- **Root cause (three stacked gaps):** (1) `db.py` imports `psycopg` /
  `psycopg_pool` at module load, but both were still commented out in
  `requirements.txt` → instant `ImportError`, taking the seed layer down with
  it. (2) The raw data files (`data/raw/`) and the graph cache are gitignored
  (correctly) but there was **no download script** — the only copy of the
  pipeline inputs lived on one laptop. (3) The seed fallback in `/api/routes`
  only caught `place_not_found`; a missing `.env`/unreachable DB raised and
  became a 500.
- **The fix:** uncommented the deps (+ `psycopg-pool`), wrote
  `etl/download.py` (idempotent fetch of all three sources), and wrapped the
  engine call so *any* failure degrades to seed data.
- **Why this fix (and what I rejected):** committing the data files was
  rejected (100+ MB, licence hygiene); a setup shell script was rejected in
  favour of a cross-platform Python script that reuses `httpx` already in the
  stack. The fallback fix restores the original design intent stated in
  `main.py` ("failures here shouldn't block the seed endpoints").
- **Impact:** fresh clone → `pip install` → `uvicorn` now boots and serves the
  demo corridors with zero config; full engine needs only `.env` + two ETL
  commands. Bus factor 1 → gone.
- **Interview soundbite:** "Our engine ran perfectly — on one laptop. The
  moment a second machine pulled the repo, three hidden assumptions surfaced:
  deps that were imported but not declared, input data with no acquisition
  script, and a fallback that didn't actually catch the failure it was designed
  for. The lesson: reproducibility is a feature you have to *test*, by doing a
  cold-start setup on a machine that isn't yours."

## P8 — Replacing a 10-year-stale timetable (evidence-first data swap)
- **Symptom:** the engine ran on a 2016 timetable. A 28-train manual audit vs
  erail.in scored it **0 SAME / 19 CHANGED / 9 GONE** — not one train bookable
  as-is (renumber reuse even made two trains silently *wrong*, not just missing).
- **How I found the cause:** measured before acting — a 10-corridor duration
  benchmark (`etl/benchmark.py`) + the manual identity audit
  (`etl/sample_trains.py`). Surprise: durations were only ~7% off; *identity*
  (numbers, names, timings, termini) was ~100% unreliable. That reframed the
  problem from "re-scrape everything" to "replace the identity layer."
- **The fix:** swap the base to a fresh May-2026 CC0 scrape (8,366 trains) via
  `etl/load_v2.py`. Hard part: it used station *names*, not codes. Solution
  was a **three-layer mapper**: (1) name→code dictionary harvested from an
  Oct-2023 IRCTC dataset whose `stationList` had both fields; (2) a hand-built
  alias table for post-2016 *station renames* (MGR Chennai, Ahilyanagar,
  Virangana Lakshmibai Jhansi, SMVB…); (3) a unique-prefix fuzzy fallback.
  Iterated with a dry-run coverage report: 19.6% → 13.5% → **8.6%** unmatched.
  Day-rollover was inferred from clock-time resets (the scrape had no day
  field). Old schedules dropped from the DB (kept on disk) — a 0%-valid
  fallback is worse than none.
- **Why this fix (and what I rejected):** rejected the biggest candidate
  dataset (11k trains, ~2020) because it was *pre-COVID* — the exact era the
  audit proved everything changed; size of stale data = more confidently wrong
  answers. Rejected keeping 2016 rows as fallback for the same reason.
- **Impact:** 5,208 → **8,306 trains** (+60% coverage); train identities now
  match reality — spot-checks reproduce the manual audit exactly (12262 dep
  05:35 ✓, 12510 → SMVB ✓); benchmark durations hold (~11%); plus three new
  fields we never had (`days_of_week`, `classes`, `distance_km`) unlocking
  run-day-aware routing, real AC filters, and slab fares.
- **Interview soundbite:** "Instead of assuming our decade-old timetable was
  bad, we measured *how* it was bad: travel times were fine (~7%), but train
  identities were 100% stale. So the fix wasn't more data, it was *current
  identity* — we swapped in a fresh scrape, solved its station-name→code
  problem with a mapping harvested from a second dataset plus a rename alias
  table, and validated the swap by reproducing our manual audit's findings
  from inside our own database."

## P9 — The reasoning strip contradicted its own verdict (user-caught)
- **Symptom:** on Imphal→Bengaluru the decision strip declared "DIMAPUR wins —
  65/day · 56%" while the *losing* hubs showed better numbers (Lumding 107/day
  · 66%). And the winning route card said "Confirmed" next to "51% Risky",
  while a 2-transfer alternative showed "92% Safe".
- **Root cause (two bugs):** (1) the reasoning generator sent generic traffic
  stats (trains/day) but the ranker actually picks on *through-trains to the
  destination* — the display metric didn't match the decision metric, so the
  verdict looked arbitrary. (2) The reliability formulas were backwards:
  transfer routes could out-score no-transfer routes (a hub bonus with a cap
  of 92 vs a direct formula that over-punished first-mile distance) — but a
  transfer is inherent risk and should never rank "safer" than no transfer.
- **The fix:** reasoning hubs are now ranked and scored by through-train count
  to the destination (each hub chip says "N through train(s)" / "no through
  train"), and the backend generates an explicit `conclusion` sentence stating
  the real win reason ("the only nearby railhead with a through train — no
  transfer risk"); the frontend renders that instead of composing its own.
  Reliability rebalanced: direct = 68 + density/8 − firstmile/15 (floor 45),
  transfers capped at 84 and scaled by connection safety.
- **Why this fix:** the display must show the metric the algorithm decided on
  — anything else erodes exactly the trust the feature exists to build.
- **Impact:** winner now carries the best displayed score + a truthful "why";
  no more Risky-winner/Safe-loser inversions (verified in-browser).
- **Interview soundbite:** "Our explainability UI showed one metric while the
  ranker decided on another, so the 'winner' looked wrong. The fix wasn't
  prettier copy — it was making the display metric *be* the decision metric,
  and having the backend state the actual win reason in one sentence."

## P10 — "Gorakhpur" routed via Rajasthan (user-caught geocode artifact)
- **Symptom:** Gorakhpur→Prayagraj (both UP, many direct trains) returned zero
  direct options and routed via Sadulpur/Hisar — Haryana/Rajasthan railheads.
- **How I found the cause:** queried the gazetteer for every "Gorakhpur":
  GeoNames contains a **duplicate artifact** — a Gorakhpur in Haryana carrying
  population 1,324,570 (bigger than the real UP city's 674,246!). Our geocoder
  ranked by population, so the impostor won and the engine faithfully routed
  from the wrong state.
- **The fix (two layers):** (1) **rail-aware geocode re-ranking** — among
  same-named candidates, prefer the one with a same-named railway station
  within 20 km (UP Gorakhpur has GORAKHPUR JN 2 km away; the impostor has
  nothing). Generic, no per-city hacks, and the right prior for a rail app.
  (2) **Autocomplete with states** (user-requested): new `/api/places?q=`
  endpoint returns top prefix matches WITH state names (admin1→state map
  derived from our own data after the published GeoNames doc proved stale);
  the search inputs now show a "Name, State" dropdown, and picking one sends
  the state hint, which the geocoder uses as a filter.
- **Why this fix:** population ranking is fine until the data lies; anchoring
  ambiguity resolution to the rail network (the thing we actually route on)
  makes the failure class disappear rather than whack-a-moling bad rows.
- **Impact:** Gorakhpur→Prayagraj now boards at GORAKHPUR JN (287 trains/day),
  direct train 14111, 6h19m, ₹214 — verified over HTTP and in-browser.
- **Interview soundbite:** "A user searched two UP cities and got routed via
  Rajasthan. The gazetteer had a duplicate 'Gorakhpur' with the wrong state
  but the bigger population. Instead of patching that row, we changed the
  prior: for a railway app, the real city is the one with a same-named
  station next to it — plus a state-labelled autocomplete so ambiguity is
  resolved by the user before it ever reaches the geocoder."

## P11 — The train that "skipped" Prayagraj Jn (station-code renames)
- **Symptom (user-caught):** 15004 Chaurichaura Exp alighted at Gyanpur Road
  (61 km road hop) even though its route passes Prayagraj Jn itself.
- **Diagnosis:** the train's stop list showed `… GYN > PRRB > PRYJ >…` — it
  DOES reach Prayagraj Jn, but stored under the RENAMED code `PRYJ`. Our
  stations table (geo source) only knows the old code `ALD`, so `PRYJ` had no
  geo/num_trains → could never be a railhead → the engine's only matchable
  alight on that train was Gyanpur Road. Same story for PRRB (Rambag/City),
  MMCT, CSMT, SMVT, VGLJ, DDU.
- **The fix:** a `CODE_RENAMES` normalisation layer in the ETL (new code → old
  geo-bearing code) applied to every stop AND to the name→code map, so both
  datasets converge on the codes that carry geo.
- **Impact:** 15004 now alights at Allahabad City (in-town) instead of 61 km
  out; Prayagraj corridors gained 5 extra route options (10→15) because ALD/
  ALY became boardable; Prayagraj→X reasoning now correctly boards locally.
- **Interview soundbite:** "A route detoured 61 km past the station it was
  sitting in. Two datasets disagreed on the station's *code* after a
  government renaming — one had the geography under the old code, one had the
  schedule under the new one. The join key itself had bit-rotted. Fix: a
  rename-normalisation layer at ingestion, so every source converges on the
  geo-bearing code."

## P12 — Routes that backtracked past the origin (user-caught)
- **Symptom:** Ringas → Salasar returned "cab Ringas→Jaipur (55km), train
  Jaipur→**Ringas**, cab Ringas→Salasar (92km)" — a train ride *back to the
  starting town*. Absurd and trust-destroying.
- **Root cause:** the engine generated candidate routes as (any origin-railhead
  → any dest-railhead) train pairs. Jaipur was in the origin's railhead set
  (big hub, within radius) and a Jaipur→Ringas train "connected" it to a
  dest-railhead (Ringas, which happened to be the nearest station to Salasar,
  92km away). Nothing enforced that the journey make *geographic progress*.
- **The fix:** a `_useful(board, alight, origin, dest)` filter — a rail leg is
  kept only if the alight is CLOSER to the destination than the board (progress
  toward goal) AND FARTHER from the origin than the board (never loop back).
  Applied to both direct and transfer candidates.
- **Why this fix:** it's a cheap, universal geometric invariant that encodes
  common sense ("don't ride away from where you're going") without hard-coding
  corridors. Rejected: distance-ratio thresholds (fragile) and post-hoc
  reranking (the bad route would still appear lower down).
- **Impact:** Ringas→Salasar now boards Jaipur→Phulera Jn (toward the
  destination); the backtrack class is gone. Locked with a regression test
  asserting no route alights at the origin's own station.
- **Interview soundbite:** "A route told users to take a train back to the town
  they started in. The engine paired 'any nearby station' with 'any nearby
  station' and one pairing looped backward. The fix was a geometric
  monotonicity check — a rail leg must end closer to the destination and
  farther from the origin than it began — which killed the whole class of
  nonsense routes with four lines of code."

---

## P13 — Reliability/confirmation/delays were flat placeholders (modelled vs measured)

- **Symptom:** the app showed a confident "reliability %", always "confirmed",
  and a buffer-only "connection safety" — numbers that looked authoritative but
  didn't actually reflect the train, route, or class. Fares were a flat ₹/km.
- **Root cause:** the routing engine shipped before the *intelligence* layer.
  The honest blocker is that **there's no free feed of observed delays or seat
  availability** — so we can't yet *measure* these.
- **The key decision — modelled vs measured:** rather than fake "measured"
  numbers or leave flat placeholders, I built **transparent models driven by the
  real train attributes we DO have** (`app/metrics.py`):
  - **Delay / on-time:** expected delay grows with route length + halts and
    depends on train priority (Rajdhani/Shatabdi < Superfast < Express <
    Passenger), turned into an on-time % via an exponential "within 30 min" model.
  - **Connection safety:** `P(arriving train's delay ≤ buffer)` from *that
    train's* delay distribution — not the buffer alone.
  - **Reliability:** a composite of the weakest leg's on-time %, connection
    safety, and first-mile access.
  - **Confirmation:** a demand proxy (class scarcity + train priority + lead
    time from the travel date + peak season) → a varying %, not a constant.
  - **Fares:** the calibrated per-km base **+ reservation + superfast surcharge
    + 5% GST on AC** — the real surcharge structure.
- **Why this and not "measured":** measured needs data we can only get by running
  the collector for weeks or buying a feed. Modelling on real attributes is the
  textbook cold-start: it's honest (everything is labelled **"est."** in the UI
  and `why` text), it *varies sensibly*, and — crucially — **the exact same
  functions get re-fit to observed numbers** the moment Step 2/3 data lands. No
  rewrite, just calibration.
- **Impact:** reliability now spans ~56–95 by train/route (was a flat formula);
  on-time 38–92%; confirmation 20–96% with confirmed/RAC/waitlisted states;
  connection safety derives from the incoming train's delay; fares include real
  surcharges (e.g. AC fares +5% GST, superfast +₹45). Verified end-to-end (17
  tests green; live UI shows the varying "(est.)" values).
- **Interview soundbite:** *"I was explicit about the line between modelled and
  measured. With no free delay/seat feed, I built transparent models on real
  train attributes — priority, distance, halts, buffer, lead time — so the
  numbers vary honestly and are labelled 'estimated', and the same functions
  calibrate to observed data later. Faking 'measured' numbers would've been the
  worse engineering choice."*

---

## P14 — Making the Mappls route look premium (two gotchas)

- **Goal:** the switch to Mappls (MapmyIndia) worked, but the route line was a
  flat heavy indigo and the markers were plain discs — "didn't feel good."
- **Fix (the beautiful-route recipe):** draw the polyline **twice** — a wider
  white "casing" underneath, then a brighter indigo line on top — so the route
  pops off the basemap; and redesign markers as clean **ringed dots** (white
  base + colored core + inner pip) with a soft **translucent-halo** ring.
- **Gotcha 1 — Mappls' vector SDK is built on MapLibre GL.** My "did it fall
  back to MapLibre?" check matched `.maplibregl-map` *inside* the Mappls
  container — it was Mappls' own renderer, not our fallback. There was only ever
  one map. Lesson: verify by container ancestry, not a class name a vendor may
  reuse.
- **Gotcha 2 — `<feDropShadow>` breaks a data-URI SVG used as a marker icon.**
  Adding a drop-shadow filter made the icon invalid, so Mappls silently rendered
  its **default red pins** (detected via `elemsWithOurSvg === 0` while marker
  divs existed). Fix: fake the soft shadow with a translucent halo circle —
  filters are unreliable when an SVG is consumed as an `<img>`/marker image.
- **Impact:** crisp, premium route line + cohesive origin/hub/destination
  markers; verified custom icons apply (not vendor defaults), no console errors.

---

## P15 — Real data exposed three bugs a model could hide (user-caught batch)

- **Background:** P13 built the modelled reliability/delay/fare layer; the very
  next session swapped in **real data** for fares, distances, and delays (IRCTC
  price data + a year of measured arrivals for 7,024 trains). Good news: it
  worked. Side effect: real numbers immediately exposed three latent bugs that
  flat/uniform modelled numbers had been masking. All three caught by the user
  eyeballing a live route card.
- **Bug 1 — Plan B suggested a train that had already left.** A route departing
  21:30 showed "Miss it? Next best: … departing 13:45" — a train from *earlier
  that day*.
  - Root cause: Plan B was `routes[i + 1]` — literally "the next route in the
    ranked list" — with zero regard for departure time. It happened to look
    plausible before because routes were homogeneous; once fares/times started
    varying realistically, the mismatch became obvious.
  - Fix: `_first_train_dep_min()` extracts each route's boarding time; Plan B
    now picks the alternative departing **soonest after** the current route,
    falling back to delay/hub advice if nothing later exists.
  - Verified live on the exact reported route (`5002 GKP JI MAGH MELA`,
    21:30 → Plan B now correctly reads "23:15").
- **Bug 2 — connection buffers didn't account for the incoming train's own
  lateness.** `graph.one_transfer` accepted any transfer with a flat ≥30-min
  buffer, even for trains that are *routinely* 40+ min late — so a "safe"
  30-min connection could statistically fail more often than it succeeded.
  - Fix: minimum buffer is now `max(30, min(measured p50 delay, 90))` — a train
    with no measured history still gets the 30-min floor; a chronically-late
    one needs a bigger buffer to qualify as a transfer at all. Scanned 8
    cross-country corridors after the fix: **0 of 27** measured transfers
    violate the invariant.
- **Bug 3 — premium trains showed classes they don't sell.** The `classes`
  column is a generic per-train field that often lists every class in
  existence; a Rajdhani (AC-only) was showing Sleeper, a Vande Bharat
  (chair-car) was showing 1A.
  - Fix: `_offered_classes()` restricts premium trains to their real sold
    classes by brand — AC-sleeper premiums (Rajdhani/Duronto/Humsafar/Garib
    Rath) → 1A/2A/3A only; chair-car premiums (Shatabdi/Vande Bharat/
    Gatimaan/Tejas *Express*) → CC/EC/2S only.
  - **The gotcha inside the gotcha:** naive brand matching breaks on
    `"TEJAS RAJ"` (Tejas *Rajdhani* — AC-sleeper, despite "Tejas") and
    `"VANDE BHARAT SL"` (the new Vande Bharat *Sleeper* — AC-sleeper, despite
    "Vande"). A test written against the naive rule caught this immediately
    (`27575 VANDE BHARAT SL` failed with `SL` in an "AC-only" assertion) —
    fixed by excluding the `RAJ`/`SL` tokens from the sitting-class match.
- **Why this matters as a pattern:** modelled/uniform data is forgiving —
  every route looks roughly the same, so ordering and edge-case bugs don't
  stand out. The moment real, *varying* data went in, three genuine logic bugs
  became visible in one screenshot. Lesson: don't fully trust a feature tested
  only against synthetic/uniform data — real data is also a bug-finding tool.
- **Impact:** +3 regression tests locking each invariant (Plan B departs later,
  buffer covers p50 delay, premium classes are brand-correct) → 34/34 passing.
  All three verified against the live API and in-browser.

---

## P16 — A Gorakhpur train that "reached" Kashmir (station-identity mismatch)

- **Symptom:** the user searched a route toward Katra (J&K) and saw
  `15909 Avadh Assam Exp` board at Gorakhpur and alight at "Sangar", ~23 km road
  from Katra. But 15909 is a Dibrugarh–Bikaner train that never goes near J&K.
- **How I found the cause:** dumped 15909's stop list with coordinates. Between
  Mandi Dabwali (29.96 N) and Hanumangarh (29.61 N) sat a stop whose stored
  coordinate was **32.8 N — a 340 km jump north into J&K and back**. That stop's
  code was `SGRR "Sangar"`; the real stop there is `SGRA "Sangaria"` (Rajasthan,
  29.79 N), which slots in perfectly. Both are genuine, distinct datameet
  stations — so this wasn't bad geo on one station, it was the schedule stop
  bound to the *wrong* station.
- **Root cause:** the timetable name→code matcher (load_v2) resolved the
  schedule name "Sangariya" to `SGRR "Sangar"` (J&K) instead of `SGRA
  "Sangaria"` (Rajasthan). SGRR had accumulated **35 trains** (vs SGRA's 5) —
  all the misrouted "Sangariya" stops piling onto the wrong code.
- **The fix (two layers):**
  1. **Repair the data.** A detector with no hand list: each stop's *expected*
     location is the midpoint of its neighbours; across all of a station's trains
     those midpoints cluster where it really is. A station whose stored coord is
     >150 km from that cluster in >60% of its trains is mis-identified
     (`graph.mislocated_stations`). 70 found. For the high-confidence subset —
     another station whose name shares a long prefix sitting ≤10 km from the
     expected spot — remap the stops (`etl/fix_station_mismatches --apply`): 9
     stations, 195 stop rows repointed in the DB, cache v4→v5.
  2. **Guard against the rest.** The router (`single_train`/`one_transfer`) now
     refuses to board or alight at a stop that adds >150 km of back-and-forth
     versus its own neighbours (`graph.stop_detour_km`). This covers the 58
     remaining flagged stations that have no clean same-name match, so *no*
     bad-geo station can ever produce a nonsense route — even ones the data
     repair couldn't confidently fix.
- **Why this fix (and what I rejected):** I rejected using the detector's flagged
  set directly as a routing blocklist — it has collateral false-positives (MBY
  "Mandi Dabwali" got flagged only because its neighbour SGRR was wrong; MBY is a
  perfectly real station). A global blocklist would have dropped legitimate
  routes through Mandi Dabwali. The per-candidate *local* detour check
  discriminates: it rejects the stop that is itself off the line (SGRR, 624 km
  detour) while keeping its innocent neighbour (MBY, 64 km). I also rejected a
  purely-runtime fix: the data was genuinely wrong and worth repairing so fares,
  distances, and the drawn map line are correct too — the guard is the safety
  net, not the whole answer.
- **Impact (before → after):** Gorakhpur→Katra went from "board a train to a
  phantom Kashmir stop" to topping with Gorakhpur→Jammu Tawi (the correct J&K
  railhead), 0 legs through "Sangar". 9 stations / 195 stops corrected in data;
  58 more neutralised by the guard. +1 regression test (router never emits a
  gross-outlier board/alight — codes not hardcoded, so it still holds after the
  data is repaired) → 38/38 pass.
- **Interview soundbite:** "A user spotted a Gorakhpur train 'arriving' near
  Kashmir. The bug was upstream: a fuzzy name-matcher had bound a 'Sangariya'
  (Rajasthan) stop to 'Sangar' (J&K). I wrote a data-driven detector — a
  station's real location is the consensus of its neighbours across every train,
  so anything consistently far from that consensus is mis-identified — repaired
  the high-confidence cases in the database, and added a routing guard that
  refuses to board or alight anywhere that forces a geographically impossible
  detour, so the class of bug can't surface again even where the data can't be
  auto-corrected."

---

## P17 — Password-reset emails silently went nowhere (Resend's sandbox restriction)

- **Symptom:** the user signed up, requested a password reset, and never got
  the email — no error shown anywhere, since `/api/auth/forgot-password` is
  designed to always return 200 (no email-enumeration).
- **How I found the cause:** the 200-always design meant the API response
  couldn't tell me anything, so I went straight to the backend log instead:
  `send_reset_email failed: Client error '403 Forbidden' for url
  'https://api.resend.com/emails'`. The 403 was swallowed by the endpoint (by
  design) but not by the log. I then made the exact same call manually with
  `httpx` to read Resend's actual response body instead of just the status code.
- **Root cause:** Resend's free/no-domain "sandbox" sender
  (`onboarding@resend.dev`) can only send to the email address that owns the
  Resend account itself. Resend's own error message says so outright:
  *"You can only send testing emails to your own email address... To send
  emails to other recipients, please verify a domain."* Every signup test
  account other than the developer's own email was doomed to 403, and would
  stay that way in production — a verified domain (DNS records, hours to
  propagate) would be needed before any real user could receive a reset email.
- **The fix:** switched providers to Brevo (`app/email.py`, rewritten on
  Python's stdlib `smtplib`/`email` — zero new dependency). Brevo's free tier
  only requires verifying a single **sender email address** (click a
  confirmation link — no DNS) to send to any recipient, which is the actual
  constraint that matters here: this app's users won't have accounts on
  whatever email provider is chosen, so the provider must not require the
  *recipient* to be pre-approved.
- **Why this fix (and what I rejected):** rejected verifying a domain on
  Resend to keep it — that trades a five-minute provider swap for a DNS
  dependency (needs the user to own a domain, wait for propagation) just to
  keep using the first provider tried. The actual requirement was "any real
  user, not just me, can receive the email," and Brevo satisfies that on its
  free tier with zero infrastructure. Confirmed with a direct test send
  (`httpx.post` to Resend, then the same to Brevo) before wiring it into the
  app, rather than trusting documentation alone.
- **Impact:** password-reset emails now deliver to any recipient, not just
  the developer's own inbox — verified with a real send before/after the
  switch (Resend: 403 to a third-party email, 200 only to the account owner's
  own; Brevo: 200 to an arbitrary recipient once the sender was verified).
- **Interview soundbite:** "A 'silent failure' pattern (always-200, no
  enumeration) meant the API response gave me nothing to debug — so I went to
  the log, then reproduced the exact HTTP call by hand to read the provider's
  real error instead of guessing from the status code alone. The fix wasn't a
  code bug at all — it was picking an email provider whose free-tier
  restriction (sender verification) matched what the app actually needed,
  instead of one whose restriction (recipient verification) didn't."

---

## P18 — The first ML model: predicting delay as a distribution, not a number

- **The problem:** the engine showed ONE flat average delay per train
  (`train_delays.avg_delay`) no matter when or where you travelled. But the raw
  dump has 38.4M dated, per-station observations — the flat average throws away
  the day-of-week, month, and position-along-route structure that's actually in
  the data.
- **Algorithm choice (and why not the obvious one):** the roadmap named
  LightGBM. I chose scikit-learn's `HistGradientBoosting` instead — it's the
  same histogram-GBT algorithm family (LightGBM originated it), accuracy within
  noise on this tabular problem, but with no native OpenMP wheel to deploy.
  For a project whose whole ethos is "pull → running in 3 minutes / graceful
  fallback," dropping a native-lib deploy footgun for ~zero accuracy cost was
  the right call.
- **The key design decision — predict a distribution, derive everything from
  it:** rather than a mean regressor plus a separate on-time classifier plus a
  separate p90 model (which can mutually contradict), I train ONE mean model +
  quantile models at {0.1,0.25,0.5,0.75,0.9}, then derive p90 (the 0.9 model),
  on-time % (P(delay≤30) by interpolating the quantile CDF), AND connection
  safety (P(delay≤buffer) from the same CDF) all from that one coherent
  predicted distribution. They can never disagree, and connection safety
  stopped being a crude single-average exponential — it reads the arriving
  train's actual predicted spread. Held-out quantile calibration came out
  near-perfect (0.5→0.505, 0.75→0.753, 0.9→0.901), which is what makes the
  derived probabilities trustworthy.
- **Serve-time-safe features only (the subtle bit):** the roadmap listed
  "upstream delay" as a feature — but that's a *live* signal we don't have when
  *planning* a trip. Training on it would leak information unavailable at serve
  time. So the model uses the train's historical baseline
  (`train_delays.avg_delay`, known at serve time) as the "prior" it refines,
  plus day-of-week/month/position/scheduled-hour. It predicts the *conditional
  deviation* from a train's own average, not the average from scratch.
- **The bug real data threw (again): cross-source station codes.** First run,
  ZERO legs came back "predicted" — every one fell back to measured. Cause: the
  routed-distance table (`train_cumdist.json`, built from the delay dump's
  schedule) and the engine's alighting-station code (from the DB timetable) use
  partly *different* station codes for the same station (e.g. Allahabad `ALD`) —
  the same code-drift class as P16. My feature assembly had hard-required the
  distance lookup, so a missing code killed the whole prediction.
- **The fix — make position optional, not mandatory.** The scheduled-hour and
  journey-day come from the DB stops (same source as the alighting code, so they
  always resolve); the baseline and travel date are the dominant signals. Only
  `dist_from_origin`/`frac_route` depend on the mismatched table — so I made
  them optional (NaN when the codes don't align; HistGradientBoosting handles
  NaN natively). Prediction now fires on baseline + date + scheduled hour, using
  routed distance as a bonus when the codes happen to agree. Robustness over a
  feature that's only sometimes available.
- **Impact:** on a dated search, delay is now conditioned on the trip
  (delaySource `"predicted"`), held-out MAE 26.9 vs 29.3 min for the flat
  average (+8.4%), with a calibrated spread that also upgrades connection safety.
  Undated searches are unchanged (fall back to the flat measured average — the
  model needs a date). No new infra: a 1.7 MB sidecar artifact loaded like
  `fare_table.json`, no graph-cache bump.
- **Interview soundbite:** "I made the first ML model predict a whole delay
  distribution, not a point estimate — so the on-time %, the 90th-percentile
  buffer, and the connection-safety probability are all read off one calibrated
  curve and can't contradict each other. And I chose the boring histogram-GBT in
  scikit-learn over LightGBM specifically to avoid a native-dependency deploy
  risk for essentially no accuracy loss. Real data bit me the same way twice —
  station codes differ across sources — so I made the position feature optional
  rather than let a missing code silently disable the whole model."

---

## P19 — Refusing to ML-model a constant (the fare-prediction reframe)

- **The request:** "predict per-class price by weekend / holiday / festival /
  season," like a bus or flight app.
- **What the data actually said:** I verified before building anything. Indian
  train fares in our data are government-regulated distance-slab fares — static
  per (route, class), with **zero** date variation. The `dynamicFare`/`tatkalFare`
  columns exist but are 0 in the base rows; there's no festival/holiday calendar
  on disk; the only date-varying signal in the whole dump is seat *availability*,
  not price. An ML model needs a target that *moves* with the features — this
  target doesn't move with date at all.
- **The decision:** I did NOT build a price predictor. Training a model to
  predict a constant would be fabricating sophistication — it would output the
  same regulated fare with a veneer of ML noise, and worse, imply to the user
  that fares fluctuate when they legally don't. I surfaced the data reality to
  the user and offered honest alternatives.
- **What we built instead (chosen by the user):** a transparent *demand
  advisory*, not fake ML. A curated India festival/holiday/long-weekend calendar
  drives (a) a real flexi-fare multiplier for the ONE place price genuinely
  moves — premium (Rajdhani/Shatabdi/Duronto) dynamic-fare trains, via IRCTC's
  published tier rule — and (b) a scarcity advisory ("Diwali week: sleeper likely
  sold out, expect AC-only"). Regulated fares stay exactly fixed
  (`flexi_fare_multiplier` returns 1.0 for non-premium — we never invent
  variation). Everything is labelled "est.", like the confirmation number.
- **Why this matters:** the ML-shaped request had an honest answer that wasn't
  ML. Recognizing "there is no varying target here" and reframing to model where
  variation *actually* exists (dynamic-fare trains + peak-date class scarcity) is
  the difference between a useful feature and a plausible-looking lie.
- **Interview soundbite:** "Someone asked me to ML-predict train fares by
  festival. I checked the data first and found the target is a regulated
  constant — it doesn't vary by date. So I refused to train a model that would
  just predict a constant with noise, and instead built a transparent
  demand-based advisory scoped to the one thing that genuinely moves: flexi-fare
  premium trains and peak-date class scarcity. Knowing when *not* to use ML is
  part of the job."

---

## P20 — "The average is bigger than my buffer, so why does it say 56% safe?"

- **Symptom (user-caught, from a real screenshot):** a leg predicted "~113 min
  delay" on average, feeding into a connection with a 75-min buffer — yet
  connection safety showed 56%, which reads as a contradiction ("if it averages
  worse than my buffer, how am I safe half the time?").
- **How I found the cause:** reproduced the exact leg (train 13020, the exact
  date/context) against the live model rather than guessing. Three checks: (1)
  the displayed % was correct arithmetic on the model's own quantile curve; (2)
  the *raw measured* data for this train — no ML involved — already showed
  avg=91 vs p50=39, more than 2x apart, so the skew is real train behavior
  (long-haul trains have a long tail of catastrophic delays that drag the mean
  up while most runs are much closer to on-time), not something the model
  invented; (3) the OLD pre-ML exponential heuristic, fed the same average and
  buffer, produced 55% — one point off the ML model's 56%. So the "paradox"
  wasn't new, and it wasn't wrong math — it's the classic mean-vs-median gap on
  a right-skewed distribution, which is exactly *why* we compute safety from a
  distribution instead of eyeballing the average against a buffer.
- **But something WAS genuinely wrong, found while verifying:** the "average
  delay" and the five quantiles (p10…p90) came from **six independently
  trained models** — a squared-error model for the mean, plus five separate
  quantile-loss models. Nothing enforced any relationship between them beyond a
  post-hoc sort of the quantiles. They happened to roughly agree on this leg,
  but there was no guarantee they always would — the mean model could in
  principle predict something that visibly contradicts the quantile curve the
  UI shows right next to it, for a *different* reason than the real,
  statistically-legitimate skew.
- **The fix:** stopped training a separate mean model entirely.
  `delay_model.mean_from_quantiles()` derives "average delay" by
  trapezoid-integrating the SAME quantile curve used for p50/p90/on-time%/
  connection-safety (added a 0.99 quantile purely to ground the tail of that
  integration). Average, typical (p50), worst-case (p90), and connection
  safety now all read off one coherent curve — a divergence between "average"
  and "the rest of the numbers" is no longer *possible by construction*, not
  just unlikely.
- **Two more fixes that came out of investigating this properly, not just
  patching the symptom:**
  1. The connection *feasibility gate* (which connections even get offered,
     in `graph.one_transfer`) used the flat, undated measured p50 as its
     minimum-buffer floor — even on a dated search where a date-conditioned
     predicted p50 was available and could be worse. Now it uses the
     predicted p50 when the model can produce one for that date, computed
     ONCE per hub (not per candidate train) to keep it cheap, falling back to
     the flat measured p50 otherwise.
  2. The UI led with "average delay" next to the buffer, which is precisely
     the number most likely to look self-contradictory on a skewed
     distribution. `LegTimeline.jsx` now leads with the TYPICAL (p50) delay
     — "Typically ~57 min late… up to ~250 min on a bad day" — framing the
     average's skew explicitly instead of implicitly.
- **Why this fix (and what I didn't do):** I didn't just adjust the connection-
  safety formula or clamp the average closer to the median — that would have
  hidden a real statistical property (the tail risk that connection safety is
  SUPPOSED to price in) to make a screenshot look less surprising. The actual
  bug was architectural (two disconnected models, no consistency guarantee),
  and the actual UX bug was a display choice (average, not typical, as the
  headline). Fixing both means the numbers can never disagree again and are
  honest about what "average" actually means for a skewed distribution,
  instead of just making the specific complained-about case look nicer.
- **Also added, not directly requested but found while auditing — and it
  proved decisive:** stratified calibration reporting in the training script
  (MAE/coverage broken out by tier and by day_offset bucket), because an
  aggregate calibration number can't tell you a THIN, unusual slice is poorly
  calibrated. Running it on the retrained model showed p50-MAE of **19.9 min**
  at day_offset=0 (same-day, 317k held-out rows), **41.2 min** at day_offset=1,
  and **70.7 min** at day_offset≥2 (9k rows — exactly this train's multi-day
  journey class) — worse than the 29.3-min flat baseline the model exists to
  beat. So for multi-day legs, "predicted" wasn't just imprecise, it was
  actively worse than the plain historical average. Added
  `delay_model.MAX_RELIABLE_DAY_OFFSET = 1`: the model now refuses to predict
  past day_offset 1, falling back to measured/modelled — a demonstrably-worse
  model shouldn't override a better, simpler number just because it exists.
  This is the direct, evidence-backed answer to "check the model's accuracy" —
  not a general "the model seems fine" but a specific number showing exactly
  where it wasn't, and a targeted fix scoped to that exact failure mode.
- **Interview soundbite:** "A user's screenshot looked like the model
  contradicted itself — a huge average delay next to a moderate connection-
  safety percentage. I didn't just trust that it was fine, and I didn't just
  patch the number to make the screenshot look better. I reproduced the exact
  case, confirmed the underlying statistical skew was real (present in the raw
  measured data, and consistent with what the old non-ML heuristic would have
  said), and THEN kept auditing — which is how I found that the average and
  the percentiles were coming from six independently trained models with no
  guaranteed relationship. The actual fix was architectural: derive the
  average by integrating the same quantile curve everything else reads from,
  so that class of contradiction becomes structurally impossible, not just
  unlikely on this one example."

---

## P21 — Improving fare accuracy without scraping IRCTC

- **The ask:** "write a program that finds all the prices for each route and
  updates our pricing accuracy" — implicitly, something that automates
  checking IRCTC's live booking site per route.
- **Why I didn't build that:** IRCTC's terms of service prohibit automated
  access to the booking flow, and unofficial scrapers against it have a real
  history of getting blocked. That's a "don't build this" line, not a
  technical inconvenience to route around.
- **What I also declined to do:** hardcode Indian Railways' "official"
  per-km fare formula from memory. IR's tariff structure IS public — but the
  exact current numeric rates are revised periodically by government
  notification, and I don't have a verified, current figure I'd trust enough
  to ship as ground truth. A wrong-but-confident-looking fare is worse than an
  honest approximation — the same principle as labelling confirmation "(est.)"
  instead of inventing precision the data doesn't support.
- **What actually moved the needle:** the existing `fare_table.json` was a
  median of real IRCTC fares (from a 2023 scrape) bucketed into 50km bands —
  real data, but diluted: ~300k samples flattened into ~80 buckets shared
  across all classes, with two failure modes baked in. (1) A "staircase" —
  every fare within a 50km band collapses to one number, then jumps at the
  boundary, when real telescopic tariffs are smooth. (2) No monotonicity
  guarantee — two adjacent bucket medians could, from sampling noise alone,
  have the FARTHER bucket price LOWER than the nearer one.
- **The fix:** replaced the bucket-median with an **isotonic (monotonic)
  regression** fit directly on every (distance, fare) sample per class — no
  bucketing at all. `etl/load_fares.py` now uses `sklearn.isotonic.
  IsotonicRegression` (already a dependency from the delay model), keeps the
  fit's own step breakpoints (from its PAVA algorithm — 52 to 345 per class,
  denser where the data is denser, not an arbitrary fixed grid), and
  `metrics.real_fare` linearly interpolates between them. This uses the SAME
  data as before — no new source, no scraping — just stops throwing most of
  it away into coarse buckets. Isotonic regression's core property is exactly
  what was missing: it CANNOT produce a decreasing fit, so distance-monotonic
  fares are guaranteed by construction, not by hoping the bucket medians
  behave. Verified with a dense scan (every 25km from 50 to 3000) asserting
  fare never dips anywhere, not just at a couple of hand-picked checkpoints.
- **Why this fix (and what I rejected):** rejected literally shrinking the
  bucket width (still has both failure modes, just smaller); rejected a fixed
  high-resolution grid resampled from the fit (arbitrary resolution choice,
  no better justified than 50km was); isotonic regression's breakpoints are
  the data telling you where it actually changes shape, not a number I chose.
- **The actual place a scraper-shaped tool WOULD add value:** premium/flexi
  fare trains (Rajdhani/Shatabdi/Duronto), whose live price depends on
  real-time seat occupancy that genuinely isn't knowable without live data.
  The codebase already reserves the right pattern for this —
  `settings.rapidapi_key`, planned for IRCTC1 on RapidAPI, used only for tiny
  budget-guarded spot-checks (~10 calls/month free tier), never bulk fetching.
  Left as a user decision (a paid tier removes the ceiling but costs money);
  not built without that call being made explicitly.
- **Interview soundbite:** "Asked to build a program that finds real fares
  per route, I flagged upfront that the obvious version — scraping IRCTC's
  live booking flow — violates its terms of service, so I wasn't going to
  build that regardless of how it was framed. I also declined to hardcode an
  'official' fare formula from memory rather than verified data, because a
  wrong number stated with false confidence is worse than an honest
  approximation. The actual fix used data we already had, just fit better:
  isotonic regression instead of bucket-medians, which is the right tool
  specifically because it makes non-decreasing-with-distance a mathematical
  guarantee instead of something you hope holds."

---

## P22 — Wiring real road-routing (OSRM) surfaced a slow-failure bug before it shipped

- **The task:** replace first/last-mile road legs' haversine-distance guess
  with real routed distance/duration via OSRM, the way `PHASE_B_PLAN.md`
  always intended. `osrm_url` had been a config field since Phase B — read by
  zero code, no HTTP client existed for it at all.
- **The environment constraint that shaped the design:** self-hosting OSRM
  needs Docker, and a live check confirmed Docker isn't available in this
  sandboxed dev environment OR on the user's own machine (the same constraint
  that already pushed Postgres to hosted Supabase instead of local Docker,
  earlier in the project). So OSRM gets the identical treatment: one
  persistent instance on a small cloud VM, shared by dev and prod via
  `OSRM_URL` — not something run locally at all.
- **What I built:** `app/osrm.py`, a thin `httpx` client with the same
  graceful-degradation contract as `delay_model.py` — returns `None` on ANY
  failure, never raises. `engine.py`'s `_road_km_mins()` tries it first, falls
  back to the existing haversine×1.3 estimate otherwise. Along the way, fixed
  a real pre-existing gap: first/last-mile legs had NO correction factor at
  all (only the standalone direct-road option applied the ×1.3 factor) —
  now both paths are consistent, and the fix stays relevant as the fallback
  even after OSRM is live.
- **The bug I found by actually testing the fallback, not just the happy
  path:** I smoke-tested against OSRM's public demo server (fine — the
  integration worked, real routed distances came back sensibly different
  from the haversine guess). Then I deliberately pointed `OSRM_URL` at a
  refused connection to test the OTHER path — the one that matters most for
  reliability, since a self-hosted VM WILL go down eventually. A single
  failed call took **~2.9 seconds** on this network before returning
  `WinError 10061` — nowhere near instant, close to the very timeout I'd set.
  Without a fix, a single search with a dozen-plus road legs (multiple
  candidate routes, each with first-mile and last-mile hops) would pay that
  cost **once per leg** — and EVERY subsequent search would pay it again,
  for as long as OSRM stayed down. A confirmed request that hung past 20
  seconds during testing is exactly what a real production outage would do
  to every user's search, not a one-off local quirk.
- **The fix:** a circuit breaker in `osrm.py` — one failure disables OSRM for
  a 30-second cooldown (returning `None` instantly, no network attempt, for
  every call during that window), then automatically retries after it
  expires. Also dropped the timeout itself from 3.0s to 1.5s. Verified
  concretely: first search after a failure took 3.19s total (pays the cost
  once); the very next search took 1.03s (breaker already open, zero network
  attempts) — versus the pre-fix behavior of a single request hanging past 20
  seconds with no end in sight.
- **Why this fix (and what I rejected):** rejected just lowering the timeout
  further and calling it done — a lower timeout alone still means EVERY leg
  of EVERY search pays that cost independently while OSRM is down, just a
  smaller cost each time; multiplied across many legs it's still materially
  slow, and it never stops paying it until OSRM recovers. A circuit breaker
  is the standard answer to "a dependency can be slow-to-fail, and I have
  many call sites in one request" for exactly this reason — pay the
  discovery cost once, not once per leg, not once per request.
- **Impact:** road-leg duration/fare now reflect real routed distance when
  OSRM is available (verified: e.g. one corridor's leg went from a 243-min
  haversine-based estimate to a 162-min real-routed one — OSRM found a
  meaningfully faster real road than the crude factor assumed), with a
  verified-fast, bounded-cost fallback when it isn't — not a theoretical
  "should be fine," an actually-measured worst case.
- **Interview soundbite:** "I didn't just wire up the happy path and call it
  done — I deliberately tested what happens when the new dependency is down,
  since a self-hosted service WILL go down eventually. That surfaced a real
  problem: a single failed call took nearly 3 seconds on this network, and
  without a circuit breaker, a search with a dozen road legs would pay that
  cost once per leg, and every subsequent search would pay it again for as
  long as the outage lasted. The fix — a short cooldown after one failure —
  is a standard pattern, but I only knew to add it because I measured the
  actual failure cost instead of assuming 'it'll just fall back fine.'"
- **Addendum (2026-07-14):** after seeing the full self-hosted OSRM runbook
  (VM provisioning, Docker, multi-step graph build), the user wanted
  something they could turn on today without any of that. Generalized
  `osrm.py` into `roads.py`: same circuit breaker and fallback contract,
  but now tries `OSRM_URL` first, then falls back to a new OpenRouteService
  client (hosted API, free tier, signup takes minutes, zero infra) — so ORS
  is the practical default, and OSRM becomes a pure "set one env var later if
  you want it" upgrade, not a blocker. The failure-cost lesson above carries
  over unchanged to both backends, since the circuit breaker is
  backend-agnostic.

---

## P23 — Two deploy-only bugs found by actually clicking the live site

Neither of these showed up in local dev or in 116 passing tests — both are
properties of the DEPLOYED environment specifically, which is exactly why
testing the real deployed app (not just `npm run build` succeeding) mattered.

- **Bug 1 — every direct link 404'd (SPA fallback silently dropped).**
  **Symptom:** `route-sarthi.vercel.app/login` and `/reset-password?token=...`
  returned Vercel's static 404 instead of the React app; only the root `/`
  worked. **Root cause:** Vercel auto-adds an SPA fallback (unmatched paths →
  `index.html`) for a Vite project, but that auto-behavior is silently
  disabled the moment a project ships its OWN `vercel.json` with `rewrites` —
  ours had exactly one rule, the `/api/*` → Render proxy, with no fallback for
  everything else. **Why this was the real "forgot password is broken" bug:**
  the emailed reset link is `frontend_url + /reset-password?token=...` — a
  direct navigation from the user's email client, hitting exactly the 404,
  before React Router ever loaded. **The fix:** add a second rewrite,
  `"/((?!api/).*)" -> "/index.html"`, ordered AFTER the `/api` rule (rewrites
  are evaluated in order, first match wins). **Verified safe, not just
  "probably fine":** confirmed via Vercel's own docs that rewrites are only
  applied after a filesystem check — a request for a real built asset
  (`/assets/index-abc.js`) is served directly and never reaches the rewrite,
  so this couldn't have broken JS/CSS loading. Tested live post-fix:
  `/reset-password?token=test123` now renders the actual "Choose a new
  password" form; `/login` renders the login form. Refreshing any page (not
  just cold-loading `/`) was silently broken by the same bug and is fixed by
  the same change.
- **Bug 2 — password-reset emails always "timed out" (host-level SMTP block).**
  **Symptom:** the log showed `send_reset_email failed: timed out` on every
  attempt, even with correct Brevo SMTP host/user/password set as Render env
  vars. **How I ruled out a config typo first:** a wrong password or host
  fails FAST with an auth/DNS error; a `timed out` after the full timeout
  window is the signature of packets being silently dropped, not rejected —
  that's a firewall, not a credentials bug. **Root cause (verified, not
  assumed):** Render blocks ALL outbound traffic to SMTP ports 25/465/587 on
  free web services, as of September 2025 — a platform-level policy change to
  protect their network's spam reputation, undocumented in-app but confirmed
  in Render's own changelog. No amount of correct SMTP configuration can work
  around a port that's blocked before the packet leaves the box. **The fix:**
  switched from raw `smtplib` to Brevo's HTTPS transactional-email API
  (`POST api.brevo.com/v3/smtp/email`) — same provider, same free tier, but
  travels over port 443, which Render never blocks. Needs a DIFFERENT
  credential (a Brevo API key, from SMTP & API > API Keys — not the SMTP
  login/password pair) but no new Python dependency (httpx was already used
  elsewhere). **Why this fix (and what I rejected):** rejected upgrading to a
  paid Render plan just to unblock port 587 — that trades money for a
  protocol choice that has a free, equally-reliable HTTPS alternative already
  on the same provider. Also rejected switching email providers entirely
  (again, Resend/SendGrid/etc. all have this same SMTP-port problem on
  Render — the port is blocked, not the provider). **Impact:** the identical
  Brevo account, sender, and free-tier quota now work from Render; +5 unit
  tests (not-configured no-op, sender-missing no-op, success path asserts the
  exact endpoint/headers/payload, HTTP-error and network-error paths both
  return False without raising) — a gap, since `email.py` had zero test
  coverage before this bug surfaced it.
- **Interview soundbite:** "Two bugs only existed once the app was actually
  deployed — neither showed up in 116 local tests. The routing one taught me
  that a custom `vercel.json` silently opts you OUT of the framework's default
  SPA fallback, so I didn't just re-add a broad rewrite blindly — I confirmed
  from Vercel's own docs that rewrites only apply after a filesystem check, so
  I could be sure it wouldn't break static asset loading before shipping it.
  The email one taught me to read a `timed out` error literally: a fast auth
  failure means bad credentials, but a full-timeout hang after correct
  credentials means the network path itself is blocked — which led me to
  Render's own changelog confirming they block outbound SMTP ports on free
  tier, and to fixing it with the same provider's HTTPS API instead of
  guessing at credential problems that weren't there."

---

## Template for future entries
```
## P# — <short title>
- Symptom:
- How I found the cause:
- Root cause:
- The fix:
- Why this fix (and what I rejected):
- Impact (before → after):
- (screenshot if visual: docs/img/<name>.png)
```
