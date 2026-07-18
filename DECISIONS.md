# RouteSarthi — Decisions

This document records every major technical decision found in the codebase
and its supporting docs (`PHASE_B_PLAN.md`, `PROJECT_LOG.md`,
`ENGINEERING_NOTES.md`), what alternatives were considered and rejected and
why, trade-offs knowingly accepted, non-obvious assumptions the design
relies on, and things left as deliberate simplifications rather than fully
solved.

Where the codebase itself doesn't spell out a reason and I'm inferring one
from context, I've marked it `UNCLEAR` per the instructions for this
documentation pass, rather than presenting a guess as fact.

---

## 1. Architecture-level decisions

### 1.1 Route in memory, not in the database

**Chosen:** load the entire schedule timetable into plain Python
dictionaries at server startup (`app/graph.py`) and do routing as in-memory
scans.

**Alternatives considered and rejected:**
- *Optimize the SQL* (better indexes, smaller `IN` lists, a precomputed
  "segments" table). Rejected because it would have helped marginally but
  kept the fundamental problem — a network-bound, per-request database
  query for a graph-traversal workload a relational database isn't suited
  to — and a segments table would have ballooned into millions of rows for
  full route coverage.

**Why this one:** it's literally how production transit-routing engines
work (RAPTOR / Connection Scan Algorithm operate on in-memory arrays), and
the dataset (~417k schedule rows at the time) is small enough to fit
comfortably in RAM. Measured impact: pure routing compute went from ~100
seconds to ~0.06 milliseconds. Full narrative in `CHALLENGES.md` Case
Study 1.

**Trade-off accepted knowingly:** the whole timetable must be reloaded (or
loaded from a cache file) at every process start, and a schema/data change
requires bumping `graph._CACHE_VERSION` and restarting every server
process — there is no live update path. For a single-process, manually
restarted deployment this is fine; it would need revisiting for a
zero-downtime multi-instance deployment.

### 1.2 Hosted Supabase Postgres, not local Docker

**Chosen:** PostgreSQL + PostGIS hosted on Supabase's free tier, used
identically for local development and (eventually) production.

**Alternative considered and rejected:** local Docker Compose (a
`docker-compose.yml` with Postgres+PostGIS+Redis+OSRM service definitions
does exist in the repo). Rejected specifically because **Docker was
confirmed unavailable in the development environment this project was
built in** — this isn't a stylistic preference, it's a hard environmental
constraint that was verified directly (a live `docker --version` check)
rather than assumed.

**Why this one:** a hosted database also becomes the eventual production
database with zero migration step, and avoids the entire class of "works
on my machine" Docker-networking problems.

**Assumption this relies on that isn't obvious from the code:** the
`docker-compose.yml` file still exists in the repo, fully filled in
(including an `osrm` service), even though it's not actually usable in this
project's own development environment. It's kept as a **reference
container spec** for a future dedicated cloud VM that *would* have Docker
— reading the file in isolation, without this context, would incorrectly
suggest local Docker is a supported dev path today.

### 1.3 Bearer-token (JWT) sessions, not cookies

**Chosen:** stateless JWT in an `Authorization: Bearer` header, 14-day
expiry, no server-side revocation list.

**Reasoning found in `PROJECT_LOG.md`:** the project's own deploy notes
plan the frontend and backend on separate origins (Vercel + Render, or
similar) — cross-site cookies would be fragile in that arrangement (SameSite
restrictions, third-party-cookie blocking in browsers), whereas a bearer
token in a header has no such cross-origin baggage.

**Trade-off accepted knowingly:** no server-side session revocation exists.
"Logging out" is purely a client-side action (clearing the stored token);
a stolen token remains valid until its 14-day expiry regardless. This is an
explicitly documented, accepted gap for the current stage of the project,
not an oversight.

### 1.4 OpenRouteService as the default road-routing backend, self-hosted OSRM as a switch-on-later option

**Chosen:** a hosted API (OpenRouteService, free tier, ~5-minute signup) is
the default; a dual-backend client (`app/roads.py`) tries `OSRM_URL` first
if set (so self-hosted OSRM can be adopted later with zero code changes),
falling back to `ORS_API_KEY`.

**Timeline of the actual decision** (this one had two rounds): the original
plan (`PHASE_B_PLAN.md`) always specified self-hosted OSRM, treated as
"deploy-phase infrastructure." A full OSRM HTTP client and VM-provisioning
runbook were built first. After seeing the complete self-hosted runbook
(VM provisioning, Docker install, downloading and processing an ~1.5 GB OSM
extract, a multi-stage `osrm-extract`/`osrm-partition`/`osrm-customize`
build), the decision was revisited: that much infrastructure work wasn't
worth taking on immediately just to get real road distances, when a hosted
API achieves the same *user-facing* result (real routed distance/duration
instead of a straight-line estimate) for a five-minute signup.

**Alternative rejected:** keep the haversine-distance × factor estimate
indefinitely rather than build either integration. Rejected because it
produces measurably wrong numbers — one verified example: a leg's estimated
duration dropped from 243 minutes (haversine-based) to 162 minutes (real
routed) once OpenRouteService was live, a difference large enough to
materially mislead a traveler about door-to-door time.

**Why the dual-backend design specifically (not just switching providers
outright):** the explicit requirement was that adopting self-hosted OSRM
*later*, if/when the infrastructure investment becomes worthwhile, must
require setting exactly one environment variable and nothing else — not a
second implementation pass. `OSRM_URL` takes priority over `ORS_API_KEY`
specifically so this "later" switch is a pure config change.

**A real operational trade-off surfaced after this decision, and was fixed
in the same spirit:** OpenRouteService's free tier has a request-rate
limit tight enough that a single search — which can generate several
candidate routes sharing an identical first/last-mile city pair — could
trip it purely on duplicate calls within one request. The fix (an
in-memory result cache keyed on rounded coordinates, caching only
*successful* lookups) is documented in `ARCHITECTURE.md` §4.6 and
`CHALLENGES.md`.

### 1.5 Brevo over Resend for transactional email

**Chosen:** Brevo's free SMTP relay.

**What was tried first and rejected:** Resend. Its free/no-domain
"sandbox" sender can only deliver to the email address that owns the Resend
account itself — every test signup other than the developer's own address
returned a 403, and this restriction would persist in production for every
real user, not just during testing. A verified custom domain (DNS records,
propagation delay) would have been required before *any* real user could
receive a password-reset email.

**Why Brevo specifically:** its free tier only requires verifying a single
**sender email address** (a one-click confirmation link, no DNS) to send to
*any* recipient — which is the actual constraint that matters for this
app's users (who obviously don't have accounts on whichever email provider
gets chosen). Verified with a direct manual test send to each provider
before committing to the switch, rather than trusting documentation alone.

### 1.6 scikit-learn `HistGradientBoostingRegressor`, not LightGBM

**Chosen:** scikit-learn's histogram gradient-boosting regressor for the
delay-prediction quantile models, even though the project's own original
roadmap (`PHASE_B_PLAN.md` §7) named LightGBM.

**Why the deviation:** `HistGradientBoostingRegressor` is the same
histogram-based gradient-boosting algorithm family LightGBM originated
from — effectively equivalent accuracy on this tabular problem — but ships
inside scikit-learn with no native compiled/OpenMP wheel to manage as a
separate deployment dependency. For a project whose explicit ethos (stated
directly in the root README) is "pull → running in ~3 minutes" with
graceful degradation everywhere, trading a native-library deployment risk
for effectively zero accuracy cost was judged the right call.

### 1.7 Predict a coherent distribution (quantiles only), never a separately-fit mean

**Chosen:** train only quantile-loss models (at levels 0.1, 0.25, 0.5,
0.75, 0.9, 0.99); derive the displayed "average delay" by numerically
integrating that same quantile curve, rather than training a seventh,
separate mean-squared-error model.

**What was tried first and rejected:** an earlier version *did* train a
separate mean model. It was removed after a real, user-caught incident
(`CHALLENGES.md` P20) where the independently-trained mean and the
quantile-derived percentiles had no guaranteed mathematical relationship to
each other, and could — and once visibly did — look contradictory on a real
prediction (a large "average delay" next to a connection-safety percentage
that read as too optimistic given that average), even though both numbers
were individually correct given how they were each computed.

**Why this fix and not a narrower one:** the investigation considered (and
rejected) just adjusting the connection-safety formula, or clamping the
displayed average closer to the median, to make the specific
complained-about screenshot look less alarming. Both were rejected because
the underlying statistical skew (mean substantially exceeding median for
some real long-haul trains) is a *genuine* property of the actual delay
data, not a bug to hide — the real bug was architectural (two disconnected
models with no consistency guarantee). Deriving the mean from the same
curve as everything else makes that entire class of contradiction
structurally impossible by construction, not merely less likely.

### 1.8 Isotonic regression for fares, not IRCTC scraping and not a hardcoded formula

**Chosen:** fit a monotonic (isotonic) regression per travel class directly
on every real (distance, fare) sample already on disk from an earlier
IRCTC price-data scrape, replacing a coarser 50km-bucket-median approach.

**Explicitly rejected, and why:**
- *Scraping IRCTC's live booking flow* to check current fares
  automatically — IRCTC's terms of service prohibit automated access to the
  booking flow, and this is treated in the project's own notes as a
  "don't build this" line on principle, not a technical inconvenience to
  engineer around.
- *Hardcoding Indian Railways' official per-km tariff formula from
  memory* — the formula is genuinely public, but the exact current
  numeric rates are revised periodically by government notification, and
  no verified-current figure was available to trust as ground truth. A
  wrong-but-confident-looking fare was judged worse than an honest
  approximation built from real (if slightly dated) scraped data,
  explicitly labelled where relevant.
- *A finer bucket grid* (shrinking 50km buckets, or resampling the
  isotonic fit onto an arbitrary fixed-resolution grid) — rejected because
  both still carry the same two failure modes (a "staircase" at bucket
  boundaries; no guarantee against a farther bucket pricing lower than a
  nearer one from pure sampling noise) at a smaller scale, whereas
  isotonic regression makes non-decreasing-with-distance a mathematical
  guarantee rather than something to hope holds.

### 1.9 Multi-modal (a real road option), not "trains-first"

**Chosen (a mid-project reframe):** a direct door-to-door road (cab/bus)
option competes with rail options and can win outright, offered up to
`ROAD_DIRECT_MAX_KM=500` km or whenever rail finds nothing at all.

**What changed:** `PHASE_B_PLAN.md` originally locked "Modes v1:
trains-first" — rail as the only real mode, buses/cabs only as
first/last-mile connectors. This was explicitly revised after user
feedback that the product should be a general **travel planner**, not a
train-specific tool: for short hops or genuinely poorly-railed pairs, a
straight road trip is often the objectively better answer, and hiding that
in favor of an always-rail-centric answer would be dishonest to the user's
actual question ("what's the best way to get there," not "what's the best
train").

### 1.10 Confirmation stays a heuristic; explicitly refused to build a confirmation ML model

**Chosen:** a transparent, hand-tuned demand-proxy heuristic
(`metrics.confirmation_estimate`), clearly labelled "(est.)" everywhere it
surfaces, with no ML behind it.

**Why, explicitly stated in the project's own planning docs:** there is no
free, real feed of actual seat-availability/PNR-clearance outcomes to train
on. The project's stated position (`PHASE_B_PLAN.md` §7) is direct: *"Do
not build a model with zero real labels; the honest '(est.)' heuristic is
the right interim."* This blocks on a not-yet-built data collector that
would accumulate real booking outcomes over time — building a model on
fabricated or absent ground truth was judged actively worse than an honest,
transparent rule.

### 1.11 Declined to build ML-predicted fares; built a demand advisory instead

**The request, as originally framed:** "predict per-class price by
weekend/holiday/festival/season," analogous to how flight or bus prices
fluctuate.

**What was checked before building anything:** whether the actual data
supports date-varying fares at all. It doesn't — Indian train fares in the
available data are government-regulated, static distance-slab fares with
*zero* real date variation; the only genuinely date-varying signal in the
underlying data is seat *availability*, not price.

**Why an ML model was refused here specifically:** training a model to
predict a target that is, in the ground-truth data, a constant would
produce a system that outputs the same regulated fare wrapped in ML-shaped
noise, while implying to the user that prices meaningfully fluctuate when
they legally don't — judged a worse outcome than being transparent about
what the data actually supports.

**What was built instead:** a curated festival/holiday calendar drives (a)
a real flexi-fare multiplier for the one genuine place price *does* move —
premium dynamic-fare trains (Rajdhani/Shatabdi/Duronto/Vande Bharat), via
IRCTC's own published tier rule, capped at 1.40× — and (b) a scarcity
advisory for cheaper classes on peak dates. Regulated (non-premium) fares
are guaranteed unchanged by date, by construction
(`flexi_fare_multiplier` returns exactly `1.0` for any non-premium tier).

### 1.12 No AI-assistance attribution anywhere in the repository

**Chosen:** commit messages, code comments, and documentation contain no
reference to AI assistance, an AI co-author trailer, or similar. This
applies to every commit and every document in this repo, including these
four documentation files.

**Reasoning:** an explicit, standing preference that the public repository
read as entirely human-authored work, for a portfolio/interview context
where that framing matters to how the work is evaluated.

---

## 2. Assumptions the design relies on that aren't obvious from reading the code in isolation

- **A single backend worker process.** The Postgres connection pool is
  sized `max_size=4` deliberately for one process; the in-memory
  graph/caches/route-store are all per-process globals with no
  cross-process sharing mechanism. Running multiple worker processes today
  would silently multiply the DB pool footprint and give each worker its
  own independent (and therefore inconsistent) copy of every in-memory
  cache and the route store — nothing in the code prevents starting
  multiple workers, but nothing coordinates them either.
- **Unknown running-days means "assume daily."** `graph.runs_on` treats a
  missing/empty `days_of_week` field as "runs every day" rather than "runs
  on an unknown subset of days." This is a conservative choice in one
  direction only: it can show a train on a day it doesn't actually run
  (a false positive), but it will never *hide* a real option purely
  because its running-days metadata happens to be missing.
  `UNCLEAR — please confirm:` whether this asymmetry (favoring "show it,
  possibly wrong" over "hide it, possibly missing a real option") has ever
  been validated against real user complaints of a train that "wasn't
  actually running that day," or whether it's purely a design intention
  that hasn't yet been tested against that specific failure mode in
  practice.
- **`SECRET_KEY` must be byte-identical across every server process.**
  Nothing enforces this at the infrastructure level — it's an operational
  requirement documented in comments and `.env.example`, relying on
  whoever deploys this to actually set it as a fixed environment variable
  rather than, say, letting each process generate its own random one (which
  `auth.py`'s design deliberately avoids doing automatically, specifically
  to fail loudly instead of causing intermittent, worker-dependent 401s).
- **The free-tier rate limits of external services (OpenRouteService,
  Brevo, RapidAPI) are assumed sufficient for current traffic.** There is
  no usage monitoring or alerting for approaching any of these limits — the
  circuit breaker in `roads.py` handles an *outage or a hard rate-limit
  rejection* gracefully, but there's no proactive signal if traffic grows
  enough to make free-tier limits a recurring, not occasional, problem.

## 3. Deliberate simplifications and open TODOs, and why they weren't solved fully

- **Redis for the result cache and the transfer-route store — planned,
  never built.** The in-process dicts (`engine._CACHE`, `engine.ROUTE_STORE`,
  `engine._GEOCODE_CACHE`) are explicitly called out in code comments as
  "the deploy-phase plan" being Redis instead. Not solved because there was
  no deployment yet to make it urgent, and a single-process local
  development setup doesn't suffer from the multi-worker/restart
  consistency problems Redis would fix.
- **Seat-confirmation ML and learning-to-rank for the composite reliability
  weights — both explicitly blocked on a data collector that doesn't exist
  yet.** Both need real user booking/click behavior to learn from; no such
  data exists without first running a live product with real users for a
  while. Deliberately left unstarted rather than half-built on synthetic or
  absent data.
- **A day-aware connection-wait calculation** — the current
  `% 1440`-minutes wraparound (see `ARCHITECTURE.md` §5.6) is explicitly
  documented in the code as an approximation whose errors skew
  conservative (may miss a legitimate overnight connection, will not
  invent an impossible one). Left unsolved because it requires threading a
  same-day-vs-next-day distinction through the connection search that
  wasn't judged worth the complexity yet, given the direction the error
  already skews.
- **Village-level coverage via OpenStreetMap's Overpass API** — named in
  `PHASE_B_PLAN.md` as the eventual answer for places below "town" level,
  never implemented. City/town coverage (GeoNames, ~8,000 places) plus
  every railway station directly already covers the overwhelming majority
  of real search traffic, so this was left for later rather than blocking
  on it.
- **A live data collector for delays and PNR/confirmation status** — the
  single most consequential deferred item in the whole project. The
  project's own plan calls this "the enabling step, non-negotiable" for
  turning confirmation from a heuristic into a real model, but explicitly
  defers it because there were no real users yet to collect *from* — a
  collector polling live status for a product nobody uses yet has nothing
  useful to accumulate.
- **Deployment** — a plan exists (backend on Render, frontend on Vercel,
  with a documented list of environment variables and a needed
  `VITE_API_BASE_URL` change to stop relying on Vite's dev-only proxy) but
  has not been executed as of the most recent work recorded in
  `PROJECT_LOG.md`. `UNCLEAR — please confirm:` the exact current state of
  any deployment attempt beyond what's recorded in `PROJECT_LOG.md`/
  `PHASE_B_PLAN.md`, since this documentation pass is based on the
  repository's own files, not on live infrastructure that may or may not
  exist outside version control.
- **The "Lifeline" live-monitoring feature is a frontend-only scripted
  simulation, with no real backend counterpart at all.** This is a full
  phase of the project's own roadmap (Phase E) that has not been started —
  not a partial implementation, a placeholder for a feature that doesn't
  exist yet in any real form.
