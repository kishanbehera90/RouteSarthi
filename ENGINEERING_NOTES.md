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
