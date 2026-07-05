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
