# RouteSarthi — Challenges

Every significant bug, failure mode, or hard problem this project's own
history (`ENGINEERING_NOTES.md`, `PROJECT_LOG.md`, and this session's
direct work) has a record of, in roughly chronological order. Each entry:
symptom → root cause → how it was found → the fix → what changed if it took
multiple iterations. A final section flags fragile/unusual code that's
likely to confuse a reader encountering it cold.

The primary source for this file is `ENGINEERING_NOTES.md`, which the
project itself maintains specifically as a record of hard problems for
future reference — this file restructures and cross-references that
material rather than replacing it; read `ENGINEERING_NOTES.md` directly for
the fullest version of each write-up, including the "interview soundbite"
framing of each one.

---

## Case Study — Route search: ~100 seconds → ~0.8 seconds

The single biggest performance problem in the project's history, solved in
five distinct layers, each of which revealed the next bottleneck once fixed
— a genuinely useful pattern to notice, not just the specific fixes.

**Symptom:** a cross-origin search requiring a train change (e.g.
Bhuj→Shimla) took 80–100 seconds. Even a simple direct search took ~7
seconds. Both unusable.

**Layer 1 — routing was happening inside the database.** The transfer
search ran SQL queries self-joining a 417,000-row `stops` table against
itself, using `IN` lists of ~2,000 station codes, multiple times per
request, each one a network round-trip to a database hosted in another
country — and it opened a second database connection mid-request on top of
that. *Root cause:* asking a relational database to do repeated graph
search is asking it to do a job it's fundamentally wrong for. *Fix:* load
the entire timetable into memory once at startup (`app/graph.py`) as plain
dictionaries; route by scanning them. *Impact:* pure routing compute went
from ~100 seconds to 0.06 milliseconds (measured on a synthetic network,
verified still correct — finds real direct + one-transfer journeys, still
rejects an impossible sub-30-minute connection).

**Layer 2 — "nearest station" was also a database round-trip.** After
Layer 1, cold searches were still 3–11 seconds. *Root cause:* the same
theme — two heavy PostGIS spatial queries per request (origin nearest, and
destination nearest), each over the network, for a dataset of only ~9,000
stations. *Fix:* load the stations into memory too; compute nearest
stations via haversine distance in plain Python (~9,000 calculations,
sub-millisecond).

**Layer 3 — a full-table scan hiding behind an `OR`.** Still ~2–4 seconds,
now all in geocoding. *Root cause:* the query was
`WHERE lower(asciiname)=... OR lower(name)=...`; an index existed on
`lower(asciiname)` but not on `lower(name)`, so Postgres couldn't use
either index for the `OR` and scanned all ~558,000 rows, twice per request.
*Fix:* add the missing index (`CREATE INDEX cities_name_lower_idx ON
cities (lower(name))`), letting Postgres use a bitmap-OR across both
indexes instead.

**Layer 4 — a fresh database connection on every request.** Now ~2
seconds, with the *very first* request costing ~6 seconds. *Root cause:*
every search opened a brand-new connection (TLS handshake + pooler auth)
just to run two tiny indexed lookups. *Fix:* a connection pool
(`psycopg_pool`), explicitly warmed at server startup so even the first
real request reuses an already-open connection.

**Layer 5 — a slow and fragile startup.** Loading the timetable from the
database at startup took 37 seconds, and once **failed outright mid-load**
with `lost synchronization with server` — the connection pooler dropped
the large streamed result. *Root cause:* re-fetching 417k rows over a
transaction-mode pooler on every boot is both slow and something that
pooler wasn't built to reliably stream. *Fix:* build the in-memory graph
from the database once, then persist it to a local file
(`data/processed/graph_cache.pkl`); every later boot loads from that file
in ~0.5 seconds instead. The database-build path also got a 3× retry for
the rare transient drop.

**Overall before/after (measured, not estimated):**

| Metric | Before | After |
|---|---|---|
| Transfer search (cold) | ~80–100 s | ~0.8 s |
| Direct search (cold) | ~7 s | ~0.8 s |
| First request after server startup | ~100 s | 0.85 s |
| Repeat (cached) search | — | 0.02 ms |
| Server startup (graph load) | 37 s | 0.47 s |

---

## Connectivity: the Supabase setup saga

**Symptom:** three separate, sequential connection failures during initial
database setup.
1. **A database password containing special characters** broke the
   connection-string parsing — part of the password was read as the
   hostname. *Fix:* use an alphanumeric-only password.
2. **Supabase's "Direct connection" host is IPv6-only** and wouldn't
   resolve on a normal IPv4 home network. *Fix:* use the pooler connection
   string instead.
3. **A college/institutional network blocked outbound port 5432**
   entirely. *Fix:* Supabase's Transaction pooler listens on port 6543,
   which wasn't blocked; switching networks entirely also worked.

Each was diagnosed simply by reading the actual error text rather than
guessing — each one literally stated its own cause.

---

## Cross-origin search returned zero routes for the flagship cases

**Symptom:** the two corridors the entire product concept is built around —
Bhuj→Shimla and Imphal→Bengaluru — returned nothing at all.

**Root causes, two distinct ones found by adding debug prints at each
search stage:**
1. For Imphal, the geographically *nearest* stations were tiny dead-end
   halts with no useful onward connections — "nearest" was simply the wrong
   heuristic; the real regional gateway (Guwahati) is farther away in
   straight-line terms but is where the actual usable trains are.
2. Bhuj→Shimla genuinely requires a train change partway through
   (Bhuj→Ahmedabad→…→Shimla), and the engine at the time only searched for
   a single through-train.

**Fix:** candidate railheads are chosen as "nearest stations **union**
nearest *major hubs*, even if farther away"; one-transfer routing (origin
→ busy hub → destination, with a feasible connection window) was added as
a first-class search mode alongside direct search.

---

## Frontend bundle bloat after adding the map

**Symptom:** adding MapLibre grew the main JS bundle to ~1.5 MB.

**Fix:** lazy-load the map component (`React.lazy` + `Suspense`) so its
weight only downloads when a user actually opens a page that shows a map.
Most pages never need it. **Impact:** main bundle back to ~465 KB; the map
chunk loads on demand.

---

## Bridging the frontend to the real backend surfaced three mismatches

1. The route-detail page fetches by route **id**, but the real engine
   generates ids per-search and they don't exist in the seed data — would
   404. *Fix:* a small in-process route store (`engine.ROUTE_STORE`) so
   `/api/routes/:id` can resolve a route from a recent search.
2. The map component needs coordinates; engine legs originally carried only
   station *names*. *Fix:* attach real station coordinates to every leg.
3. Frontend and backend run on different ports in local development. *Fix:*
   a Vite dev-server proxy (`/api` → the backend), plus an env flag to turn
   the mock layer off — same-origin, so no CORS configuration needed.

---

## A preview-tool verification gotcha (not a real product bug, but worth recording)

**Symptom:** in an automated browser-preview tool, animated elements
sometimes appeared frozen at zero opacity, and screenshots intermittently
timed out.

**Root cause:** the preview tab is frequently backgrounded by the tooling,
and browsers pause `requestAnimationFrame` for backgrounded tabs —
animations simply never advance. **Not a bug in the app.**

**How to verify correctly instead:** take a screenshot (which brings the
tab to the foreground and lets in-flight animations settle) or inspect the
final DOM state rather than a mid-animation snapshot. Documented here
specifically because it cost real debugging time once, purely from
misreading a tooling artifact as a product defect.

---

## The repo only worked on one laptop (a reproducibility audit)

**Symptom:** a fresh `git clone` on a second machine couldn't even boot the
backend — not even the fallback seed-data mode.

**Three stacked gaps, found by attempting a genuine cold-start setup
instead of copying working state over:**
1. `db.py` imports `psycopg`/`psycopg_pool` at module load time, but both
   were still commented out in `requirements.txt` — an immediate
   `ImportError` that took down the seed-data fallback layer too, since it
   lives in the same process.
2. The raw data files and the graph cache are (correctly) gitignored, but
   there was **no download script** — the only copy of the ETL pipeline's
   inputs lived on the original machine.
3. The seed-data fallback in `/api/routes` only caught the specific
   `place_not_found` error signal; a missing `.env` or an unreachable
   database raised a different exception and produced a raw 500 instead of
   degrading gracefully.

**Fix:** uncommented the dependencies (+ added `psycopg-pool`); wrote
`etl/download.py` (an idempotent fetcher for every auto-downloadable
source); widened the exception handling in `main.py` so *any* engine
failure — not just a geocode miss — falls back to the seed corridors.

**Impact:** a fresh clone now boots and serves the demo corridors with zero
configuration; the full engine needs only a `.env` file and two ETL
commands.

---

## Replacing a decade-stale timetable (an evidence-first data swap)

**Symptom:** the engine's original timetable dated to 2016. A manual
28-train audit against a live source (erail.in) scored it **0 exact
matches, 19 changed, 9 gone entirely** — not one sampled train was bookable
as displayed, and train-number reuse meant two of them pointed at entirely
different, unrelated routes (silently wrong, worse than simply missing).

**How the problem was actually diagnosed first:** a 10-corridor duration
benchmark (`etl/benchmark.py`) plus the manual identity audit
(`etl/sample_trains.py`), run *before* deciding what to fix. The surprising
finding: travel *durations* were only ~7% off on average — trunk-route
travel times hadn't changed much. It was train *identity* (numbers, names,
exact timings, terminus stations) that was ~100% unreliable. That
reframed the fix from "the timetable is generally stale" to "the timetable's
identity layer specifically needs replacing."

**The fix, and its own hard part:** swap to a fresh 2026 scrape (a CC0
dataset, 8,366 trains) via `etl/load_v2.py`. The new source used station
*names*, not codes, requiring a three-layer name→code mapper: (1) a
name→code dictionary harvested from a second, differently-structured
dataset that happened to carry both; (2) a hand-built alias table for
station renames that had happened since 2016 (e.g. Chennai Central, Ahilyanagar,
Jhansi's renaming); (3) a unique-prefix fuzzy-match fallback. Iterated
across three passes, reducing the unmatched-reference rate from 19.6% to
8.6%. The old, decade-stale schedule rows were dropped from the database
entirely rather than kept as a fallback — a 0%-valid dataset was judged a
harmful fallback, not a safety net.

**Impact:** train coverage went from 5,208 to 8,306 trains (later growing
further as additional sources were merged in); spot-checks against the
manual audit's own findings matched exactly.

---

## The decision-reasoning UI contradicted its own stated verdict

**Symptom (user-caught):** on one corridor, the "how we found this route"
strip declared one hub "wins" while displaying worse numbers for it than
for the hubs it supposedly beat; separately, a route labelled "Confirmed"
showed a lower reliability score than an alternative it was still ranked
above.

**Two distinct bugs, found by tracing exactly what data the ranker used
versus what the UI displayed:**
1. The reasoning generator was showing generic traffic statistics
   (trains/day at each candidate hub), but the ranker actually decided
   based on *through-trains specifically to this destination* — the
   number shown and the number the decision was based on were different
   metrics, so the "winner" looked arbitrary.
2. The reliability-scoring formulas were, independently, backwards: a
   transfer route could out-score a no-transfer route, when a transfer is
   inherent extra risk and should never rank as "safer" than avoiding one
   entirely.

**Fix:** the reasoning display now ranks and scores hubs by the same
through-train-to-destination metric the ranker actually uses, and the
backend generates an explicit `conclusion` sentence stating the real
reason a route won, which the frontend renders verbatim rather than
composing its own summary from partial data. The reliability formula was
rebalanced so a no-transfer route has a meaningfully higher floor than any
transfer route can reach.

---

## A geocode duplicate routed a UP↔UP corridor through a different state

**Symptom:** Gorakhpur→Prayagraj (both firmly in Uttar Pradesh, with many
direct trains) returned zero direct options and instead routed through
Haryana/Rajasthan.

**Root cause, found by directly querying the gazetteer for every row named
"Gorakhpur":** GeoNames contains a genuine duplicate-artifact row — a
"Gorakhpur" in Haryana carrying a recorded population (1,324,570) *larger*
than the real UP city's actual population (674,246). The geocoder ranked
candidates by population, so the artifact won, and the engine faithfully
(and correctly, given its input) routed from the wrong state entirely.

**The fix, in two layers:**
1. **Rail-aware re-ranking:** among same-named candidates, prefer the one
   with a real, same-named railway station within 20 km — the real UP
   Gorakhpur has "Gorakhpur Jn" 2 km away; the Haryana artifact has
   nothing nearby. This is a generic rule, not a hardcoded fix for this one
   city.
2. **State-aware autocomplete:** a new `/api/places` endpoint returns
   suggestions with their state attached, so a user can pick the correct
   one explicitly and the frontend sends a `"City, State"` hint the
   geocoder uses as a hard filter.

---

## A train appeared to "skip" the station it was sitting in

**Symptom (user-caught):** a train's route passed through Prayagraj Jn
directly, but the app showed it alighting 61 km away at a different
station instead.

**Root cause:** the train's stop list stored the station under a code
(`PRYJ`) that reflected a post-2016 government renaming, but the
geo-bearing stations table (sourced from the older, stable dataset) only
recognized the pre-rename code (`ALD`) for the same physical station. With
no geo data attached to `PRYJ`, the engine could never treat it as a valid
board/alight point — the same underlying class of problem as the geocode
duplicate above, but for station *codes* instead of city names: two data
sources disagreeing on the identifier for the same real-world place.

**Fix:** a `CODE_RENAMES` normalization table applied during ETL, mapping
every known renamed code back to the code that actually carries geo data,
applied consistently to both the stop-loading pipeline and the
name→code mapping dictionary.

---

## Routes that rode a train back to the traveler's own starting town

**Symptom:** one corridor's suggested route was, in sequence: cab to a
nearby hub, train *back toward the origin town*, then a second cab onward
— an objectively absurd, trust-destroying itinerary.

**Root cause:** the candidate-generation logic paired "any nearby
origin-railhead" with "any nearby destination-railhead" and searched for a
train connecting them, with nothing enforcing that the journey actually
make geographic progress. One particular hub happened to be reachable both
as a candidate origin-railhead *and* have a train back to a
destination-railhead that was, in this case, extremely close to the true
origin — producing a technically-valid-looking but nonsensical loop.

**Fix:** a geometric invariant, checked for every candidate rail leg — the
alighting point must be measurably closer to the destination than the
boarding point, *and* measurably farther from the origin. A cheap,
universal check that encodes "don't ride away from where you're going"
without hardcoding anything about the specific corridor that exposed it.

---

## Real data exposed three latent bugs that uniform mock/modelled data had been hiding

Once real fares, real distances, and a year of real measured delays
replaced the earlier flat/modelled placeholders, three genuine bugs became
immediately visible in ordinary use — none of them new, all three simply
invisible when every route's numbers looked roughly the same.

1. **A "Plan B" fallback suggested a train that had already departed.** A
   route leaving at 21:30 suggested, as its fallback, a train departing
   13:45 — earlier the same day. *Root cause:* the fallback logic was
   literally "the next route in the ranked list," with no check on
   departure time at all — it happened to look plausible before only
   because every route's numbers were similar enough that ordering bugs
   didn't stand out. *Fix:* extract each route's actual boarding time and
   pick the alternative departing soonest *after* the current route,
   falling back to generic advice only if nothing later exists.
2. **Transfer buffers ignored the incoming train's own typical
   lateness.** Any connection with at least a flat 30-minute gap was
   accepted, even for a train that's *routinely* 40+ minutes late — making
   a nominally "safe" transfer fail more often than it succeeded, in
   practice. *Fix:* the minimum buffer became
   `max(30, min(measured_p50_delay, 90))` minutes — see
   `ARCHITECTURE.md` §4.1.
3. **Premium trains displayed coach classes they don't actually sell** —
   a Rajdhani (AC-sleeper only) showing Sleeper class; a Vande Bharat
   (chair-car) showing First AC. *Root cause:* the underlying data's
   generic `classes` column often lists every class that exists, not what
   that specific train offers. *Fix + its own gotcha:* a brand-based
   cleanup function, which itself needed a second fix once a test caught
   it misclassifying "Vande Bharat **Sleeper**" (a real, newer AC-sleeper
   variant despite the "Vande" brand normally meaning chair-car) and
   "Tejas **Rajdhani**" (AC-sleeper despite "Tejas" normally meaning
   chair-car) — both required explicit token-level exceptions rather than
   a pure substring match on the brand name.

**The pattern worth naming:** uniform or modelled test data is forgiving —
every route looks roughly equivalent, so ordering and edge-case logic
errors don't visually stand out. The moment real, *varying* data went in,
all three genuine bugs surfaced in ordinary screenshots. Don't fully trust
a feature validated only against synthetic/uniform data.

---

## A train appeared to detour ~340 km into a different, unrelated state

**Symptom (user-caught):** a search toward Jammu & Kashmir showed a train
(a Dibrugarh–Bikaner service that never travels anywhere near J&K) boarding
normally and then alighting at a stop 23 km from Katra, in J&K.

**How the cause was actually found:** dumping the full stop list of that
specific train with coordinates attached, and looking for the discontinuity
by eye. Between two stops at roughly 29.6–30.0°N latitude sat one stop
whose *stored* coordinate was 32.8°N — a genuine ~340 km jump north and
back within a single train's path.

**Root cause:** the timetable's fuzzy station name→code matcher had bound
a schedule stop named "Sangariya" to the wrong station code — `SGRR`
("Sangar," in Jammu & Kashmir) instead of the correct `SGRA` ("Sangaria," in
Rajasthan). Both are real, distinct, genuinely-existing datameet stations —
this wasn't one station having bad coordinates, it was a schedule stop
bound to an entirely different, wrong physical station. The wrong code had
accumulated 35 misrouted trains' worth of "Sangariya" stops onto it (versus
the correct code's legitimate 5).

**The fix, in two layers, because a data repair alone wasn't judged
sufficient:**
1. **Repair the data where confidently possible.** A detector with no
   hardcoded station list: every stop's *expected* location is the
   midpoint of its immediate neighbours in a given train's path; across
   every train serving a station, those midpoints cluster tightly around
   where the station really is. A station whose *stored* coordinate sits
   far outside that cluster in the majority of its trains is flagged as
   mis-identified. For the subset with a same-name-prefix station sitting
   close to the *expected* location, the stops were remapped in the
   database (9 stations, 195 stop rows).
2. **Guard against everything the repair couldn't confidently fix.** The
   router itself now refuses to board or alight at any stop that adds a
   large geographic detour versus its own immediate neighbours in that
   train's path (`graph.stop_detour_km`, `GUARD_DETOUR_KM=150`) — see
   `ARCHITECTURE.md` §5.5. This is a deliberately *local, per-candidate*
   check rather than a global blocklist of "known-bad" codes, because a
   station can look like an outlier purely because a *neighbouring*
   station's data is wrong, while the station itself is perfectly
   legitimate — a global blocklist would have incorrectly dropped
   legitimate routes through that innocent neighbour too.

---

## Password-reset emails silently went nowhere

**Symptom:** a real signup, followed by a real password-reset request,
produced no email at all — with no visible error anywhere, because the
forgot-password endpoint is deliberately designed to always return success
(so it never reveals whether a given email address has an account).

**How the cause was found, given the endpoint itself couldn't reveal
anything:** the backend's own server log (not the HTTP response) showed the
actual failure: a `403 Forbidden` from the email provider. The exact same
API call was then reproduced manually to read the provider's own error
message directly, rather than guessing from the status code alone.

**Root cause:** the email provider's free-tier "sandbox" sender can only
deliver to the email address that owns the account itself — every
signup other than the developer's own address was always going to fail,
in production exactly as in testing.

**Fix:** switched providers entirely (see `DECISIONS.md` §1.5) rather than
trying to route around the restriction (e.g. verifying a full domain) on
the original provider.

---

## The first ML model surfaced a cross-source station-code mismatch

**Symptom:** on the very first attempt to serve a "predicted" delay tier,
*zero* legs came back predicted — every single one silently fell back to
the flat measured tier.

**Root cause:** the routed-distance lookup table (built from one bulk data
source's own companion schedule) and the engine's actual alighting-station
code (from the main timetable's data source) use partly different station
code systems for the same physical stations — the same underlying class of
cross-source identifier mismatch as the Prayagraj station-rename bug
above, but between two different pairs of data sources this time. The
model's feature-assembly code had *required* a successful distance lookup
to produce any prediction at all, so any station-code mismatch silently
killed the whole prediction, not just the one optional feature that
depended on it.

**Fix:** made the position-dependent features (`dist_from_origin`,
`frac_route`) optional — `NaN` when the codes don't line up, which
`HistGradientBoostingRegressor` handles natively — while the dominant
features (the train's historical baseline, the travel date, the scheduled
hour) come from a source that always resolves correctly regardless. A
prediction now fires whenever those essentials are available, using routed
distance as a precision bonus only when the codes happen to agree.

---

## "The average is bigger than my buffer — how is this 56% safe?"

**Symptom (user-caught, from a real screenshot):** a leg's predicted
average delay (113 minutes) looked larger than its connection buffer (75
minutes), yet the displayed connection-safety percentage was 56% — reading,
at a glance, like a contradiction.

**How this was actually investigated, not just patched:** the exact leg
was reproduced against the live model. Three checks, in order: (1) the
displayed percentage was correct arithmetic given the model's own quantile
curve; (2) the *raw measured* data for this specific train, with no ML
involved at all, already showed a similarly large average-vs-median gap
(average 91, median 39) — confirming the skew is a real property of that
train's actual delay behavior (a long tail of occasional severe delays
dragging the average well above the typical case), not something the
model invented; (3) the old, pre-ML heuristic, fed the identical average
and buffer, produced a nearly identical percentage (55% vs. the ML model's
56%) — so this specific "paradox" wasn't new and wasn't a math error; it's
the ordinary mean-vs-median gap on a right-skewed distribution, which is
*exactly why* connection safety is computed from a full distribution rather
than compared naively against a single average number in the first place.

**But something genuinely *was* wrong, found while verifying properly
rather than stopping at "the math checks out":** the displayed average and
the five quantile percentiles came from **six independently trained
models** with nothing enforcing any relationship between them beyond a
post-hoc sort. They happened to roughly agree on this particular leg, but
nothing guaranteed they always would. See `DECISIONS.md` §1.7 for the
architectural fix (deriving the average from the same quantile curve
instead of a separate model) that this investigation led to.

**Two further fixes that came out of the same investigation, not the
original complaint directly:**
1. The connection-*feasibility* gate (which connections get offered at
   all) was using the flat, undated measured p50 as its minimum-buffer
   floor even on a dated search where a better, date-conditioned predicted
   p50 was available and could indicate a worse buffer requirement. Fixed
   to prefer the predicted p50 when available.
2. The UI itself led with "average delay" right next to the buffer — the
   single number most likely to look self-contradictory on a
   right-skewed distribution. Changed to lead with the *typical* (median)
   delay instead, framing the skew explicitly ("typically ~X min late… up
   to ~Y min on a bad day") rather than implicitly inviting the "average
   exceeds buffer" reading.

**A stratified-calibration reporting addition, made while auditing this,
then immediately proved its own value:** an aggregate mean-absolute-error
number across *all* predictions can't reveal that one thin, unusual slice
of the data is poorly calibrated while the bulk of predictions are fine.
Adding a report broken out by journey-day-offset showed p50 error of 19.9
minutes for same-day legs but 70.7 minutes for legs more than a day into a
multi-day journey — worse than the flat historical baseline the model
exists to beat. This directly produced the `MAX_RELIABLE_DAY_OFFSET=1`
guard described in `ARCHITECTURE.md` §4.3 and `DECISIONS.md` §1.7 — an
evidence-backed fix targeted at exactly the failure mode the stratified
report revealed, not a general "seems fine" pass.

---

## OSRM circuit breaker, and the OpenRouteService rate-limit that followed it

**Part 1 — testing the failure path, not just the happy path, before
shipping.** Once a real road-routing HTTP client was built (originally for
self-hosted OSRM), it was smoke-tested against a public OSRM demo server
first (worked fine). Then, deliberately, `OSRM_URL` was pointed at a
refused connection to test the *other* path — the one that matters most in
practice, since any self-hosted service will eventually go down. A single
failed call took **~2.9 seconds** before failing outright — close to the
timeout that had been set. Without a fix, a single search with a dozen or
more road legs (several candidate routes, each needing a first-mile and a
last-mile lookup) would pay that cost once *per leg*, and every subsequent
search would pay it again for as long as the outage lasted — a real request
during testing hung past 20 seconds with the pre-fix code.

**Fix:** a circuit breaker — one failure disables further road-routing
network attempts for a 30-second cooldown, returning the graceful
fallback instantly with zero network attempts during that window, then
automatically retrying once the cooldown expires. Verified concretely, not
just reasoned about: the first search after a failure took 3.19 seconds
total (paying the discovery cost exactly once); the very next search took
1.03 seconds (breaker already open, zero network attempts).

**What was explicitly rejected as an alternative:** just lowering the
timeout further and calling it solved. Rejected because a lower timeout
alone still means *every* leg of *every* search independently pays some
cost while the service is down — smaller per-call, but still materially
slow multiplied across many legs, and it never actually stops paying until
the service itself recovers. The circuit breaker pattern exists precisely
for "a dependency can be slow-to-fail, and I have many call sites within
one request."

**Part 2 — the same module, generalized, immediately surfaced a second
real bug once a real API key was actually in use.** After pivoting the
default road-routing backend to OpenRouteService (see `DECISIONS.md`
§1.4), a live search against a real key started logging `429 Too Many
Requests`. *Root cause:* several candidate routes within one search
frequently share an identical first/last-mile city pair — e.g. every
route through a given hub needs the exact same "last station → final
destination" road leg — and each one was firing its own independent
network call for identical coordinates, exhausting the free tier's
request-rate limit purely on duplicate work within a single request. *Fix:*
an in-memory cache keyed on rounded coordinates, caching only *successful*
lookups (a real road distance between two fixed points doesn't change);
failures still go through the existing circuit breaker unchanged, so a
genuine transient outage can still recover on its own cooldown. *Verified:*
a cold search of a brand-new corridor takes roughly 15 seconds (each
genuinely distinct leg pays one real network call, sequentially); a repeat
search of the same corridor drops to roughly 1 second (cache hit, zero
network calls) — and the 429 responses stopped entirely. Also confirmed
directly in the browser: a route-detail page began showing the real,
ORS-routed road distance for a leg instead of the earlier haversine-based
guess.

---

## Fragile, unusual, or likely-to-confuse-a-cold-reader areas — flagged explicitly

- **`engine._CACHE`, `engine.ROUTE_STORE`, and `engine._GEOCODE_CACHE` are
  plain dicts with a hard cap and a clear-everything eviction**, not an
  LRU. A reader might reasonably assume some kind of least-recently-used
  eviction is happening; it isn't — hitting the cap clears the *entire*
  structure at once. See `ARCHITECTURE.md` §5.2.
- **Transfer-route detail pages can 404 after a server restart, while
  direct-route detail pages cannot.** This asymmetry is intentional
  (direct-route IDs are semantically rebuildable purely from the graph;
  transfer-route IDs encode context that only exists in the in-process
  store) but is easy to mistake for an inconsistent bug rather than a
  known, documented gap awaiting the eventual Redis migration.
- **The connection-wait calculation between two trains uses a
  `% 1440`-minutes wraparound** that cannot distinguish a same-day wait
  from a next-day wait. This is explicitly commented in the code as a
  known limitation with a conservative error direction, not an accidental
  bug — but reading the line in isolation, without the surrounding
  comment, would look like a straightforward off-by-a-day bug waiting to
  happen.
- **`graph.mislocated_stations()`'s output is explicitly *not* meant to be
  used as a routing blocklist**, even though it looks, on first read, like
  exactly the kind of "list of bad station codes" one might reach for as a
  filter. The code comments are direct about why: a station can appear on
  that list purely because a *neighbouring* station in one particular
  train's path has bad data, while the flagged station itself is
  completely legitimate elsewhere. The actual runtime guard against bad
  station-identity data is the separate, local, per-candidate
  `stop_detour_km` check — a reader who conflates the two risks
  reintroducing the exact false-positive problem this design deliberately
  avoided.
- **Three different datasets, three different station/train code
  systems, none of them fully in agreement.** The main timetable, the
  delay dump's companion schedule, and the fare-pricing dataset each come
  from different sources and don't always use the same station or train
  identifiers for the same real-world entities. This has independently
  caused at least three distinct, separately-diagnosed bugs across the
  project's history (the Prayagraj station-rename issue, the
  Sangariya/Sangar station-identity mismatch, and the delay-model's
  zero-predictions-at-first issue) — a future contributor extending any
  code that joins across these sources should assume code mismatches are
  the norm to defend against, not a rare edge case.
- **The isotonic fare table's breakpoints are not evenly spaced**, and
  that's intentional, not a data-quality problem to "fix" by resampling
  onto a regular grid — the breakpoints are literally the exact points
  the fitting algorithm found necessary to represent the real data's
  shape; a denser cluster of breakpoints in one distance range means the
  real fare data actually changes more in that range, not that something
  went wrong.
- **The delay model's six sub-models (five quantile levels plus the 0.99
  used only to ground the tail) must always be re-derived together** —
  the `mean_from_quantiles` integration and the `cdf` interpolation both
  assume they're reading from one internally consistent set of quantile
  outputs for the same prediction. Retraining or modifying only one
  quantile level's model in isolation (rather than the whole training
  script as a unit) would risk silently reintroducing the exact
  architectural inconsistency `DECISIONS.md` §1.7 and the "average vs.
  buffer" incident above were about.
