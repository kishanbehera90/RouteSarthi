# RouteSarthi — Interview Preparation Bank

A complete interview question bank for the RouteSarthi project, from the
opening pitch through the most advanced technical curveballs. Every
technical claim, number, and story here traces back to the actual
codebase and its own recorded history (`ENGINEERING_NOTES.md`,
`PROJECT_LOG.md`, `DECISIONS.md`, `CHALLENGES.md`, `ARCHITECTURE.md`) —
nothing here is invented.

## How to use this document

- Read a question, then say the answer out loud before reading the
  written one. Recognizing an answer on the page is a different skill
  from recalling it under mild pressure.
- Every "Tell me about a time…" question follows STAR: Situation (what
  was true before), Task (what needed to happen), Action (what you
  specifically did — the longest part), Result (a measured outcome,
  stated plainly).
- For every "why X, not Y" question, the winning shape is: name the real
  constraint that drove the choice, name what you gave up, say when
  you'd reconsider. A one-sided "X is just better" answer reads as
  junior. A trade-off answer reads as senior.
- Core numbers to have cold, since they recur everywhere: 10,117 trains
  in the live graph, ~100s to ~0.8s search latency, 38.4M delay records
  trained on, 26.9 vs 29.3 min MAE (an 8% improvement), 557,994
  searchable places, 117 test functions, 15s to ~1s cached road-routing
  latency, a 30-second circuit-breaker cooldown.

---

## Section 1 — The Opening Pitch

### Q1. "Tell me about yourself."
Lead with the project, not a biography — it's what makes you memorable.

"I'm a CS undergrad at NIT Rourkela, and the project I'm most proud of is
RouteSarthi — a full-stack travel planner for Indian trains that I
designed, built, and deployed solo. The idea came from a real gap: every
booking app assumes you search from your own city, but a huge number of
Indian towns either have no station or only a couple of weak, waitlisted
trains, when a city 100km away might have dozens of confirmed options. I
built the whole stack — a FastAPI backend that does real cross-origin
route search over 10,000+ real trains, an ML model that predicts train
delays, and a React frontend — and it's live right now on Render and
Vercel. What I like most about this project is that it forced real
engineering trade-offs, not textbook ones — questions like 'this is too
slow, why?' and 'do I actually have the data to justify an ML model
here?' were decisions I had to defend to myself, not just implement."

### Q2. "Walk me through your resume project."
"RouteSarthi solves cross-origin travel planning for India — finding a
better route via a smarter nearby hub when your own city is
poorly-connected by rail. I built the full stack: a FastAPI backend that
loads the entire national timetable into memory and searches it directly
instead of hitting a database — that one change took search latency from
about 100 seconds down to under 1 second. On top of that I trained a
delay-prediction model on 38 million real historical delay records, so
the app can say not just 'here's a train' but 'here's how likely you are
to make your connection.' It's deployed live — React on Vercel, FastAPI
on Render — with real authentication, tiered rate limiting, and a
117-test automated suite."

### Q3. "Why did you build this? What's the actual problem?"
"Because existing tools all make the same assumption: search from your
own city, full stop. A huge fraction of India isn't served that way —
either the town has no station, or it has one with a handful of
waitlisted trains a day, while a city an hour away by road has dozens of
confirmed daily trains toward the same destination. Nobody checks that
manually, because it requires knowing regional rail geography most
people don't have. RouteSarthi automates exactly that lookup."

### Q4. "In one sentence, what is RouteSarthi?"
"An AI-powered travel planner that finds the most reliable way to travel
across India by train — including routing through a better-connected
nearby city when your own has weak options, and telling you how safe
your connections actually are using real delay history."

### Q5. "Is this a class project, an internship deliverable, or personal work?"
"Purely personal — I built it end to end on my own time, including
sourcing and vetting every data source myself. Nobody assigned it and
there's no team; every architectural decision in it is one I made and
can defend."

### Q6. "What tech stack did you use, briefly?"
"Backend: Python, FastAPI, PostgreSQL, scikit-learn for the ML piece,
JWT and bcrypt for auth. Frontend: React 19, Vite, Tailwind CSS, Zustand
for state. Deployed on Render and Vercel. Road-routing goes through
OpenRouteService with Geoapify as an automatic fallback."

---

## Section 2 — Product & Domain Understanding

### Q7. "How is this different from IRCTC, ixigo, or RailYatri?"
"Those tools search exactly the station you type — direct trains only,
from your own city. RouteSarthi's differentiator is cross-origin
routing: if your city's direct options are weak, it automatically checks
nearby better-connected hubs, adds the road leg to get there, and
compares that whole door-to-door journey against the direct option
honestly — sometimes direct still wins, and the app says so plainly. The
second differentiator is that connection safety isn't a guess — it's
computed from a full year of real measured delay data, or an ML model
conditioned on the actual travel date."

### Q8. "Explain cross-origin routing to someone non-technical."
"Imagine you live in a small town with one train a day, always
waitlisted. Two hours away by road is a bigger city with fifteen trains
a day toward where you're going, most of them wide open. Most people
don't know that, because you'd have to already know the regional train
map to think of checking. RouteSarthi checks it automatically, for any
of over half a million towns and cities in India, and tells you 'take a
bus to this city first, then this confirmed train' when that's
genuinely the better plan."

### Q9. "What does the 'reliability score' actually mean — isn't that just marketing?"
"No — it's a real weighted composite of measurable things: how likely
the seat is to get confirmed, how on-time the train historically runs,
and, for a route with a transfer, how likely you are to actually make
that connection given the first train's typical lateness. Each factor
shows its own percentage in a breakdown, and anything not backed by real
measured data is explicitly labelled 'est.' in the UI. I was deliberate
about never presenting a modelled guess as a measured fact."

### Q10. "Tell me honestly — is the 'Lifeline' live-monitoring feature real?"
Answering this with integrity is a stronger move than overselling it.

"Honestly, right now it's a scripted frontend simulation, not a live
system. It plays back a realistic sequence — a leg running late, a
connection at risk, an auto-triggered reroute — to demonstrate the
product vision. There's no real GPS or live-status feed behind it yet;
that's a deliberately separate, not-yet-built phase of the roadmap. I'd
rather say that plainly than have it surface later as a gap you catch me
on."

### Q11. "Why does road transport matter here — isn't this a train app?"
"Because for short trips, or towns with genuinely poor rail access, a
direct cab or bus is often objectively the better answer. Early on I
scoped this as trains-first, road only as a first- and last-mile
connector, but revised that after realizing it was dishonest to the
actual question a traveler is asking — 'what's the best way to get
there,' not 'what's the best train.' Now a direct road option competes
with rail candidates on equal footing and can win outright for short or
poorly-railed hops."

### Q12. "Why should I trust your on-time percentages?"
"Two tiers, both explicitly labelled by source. For most trains I have a
full year of measured real arrival records — over seven thousand
trains' worth — so that percentage is a genuine historical average. For
a dated search I go further: a trained model predicts delay conditioned
on the actual day of week and month you're travelling, using 38 million
historical records. Only when neither exists — a brand-new train with
no history — does it fall back to a transparent class-and-distance
formula, and that's explicitly labelled 'estimate,' never presented as
measured."

### Q13. "What's your target user, and how would you actually acquire them?"
"Primarily travelers from smaller Indian towns the big booking apps
under-serve, since those apps only ever search your own station. I
haven't launched to real users yet, so I'd be speculating on
acquisition, but the honest angle would be regional-language content and
partnerships with local travel agents in exactly the towns this helps
most, since that's where the pain is sharpest and word of mouth travels
fastest."

---

## Section 3 — System Design & Architecture

### Q14. "Walk me through the architecture end to end."
"Two halves. The frontend is a React SPA built first, entirely against a
mocked API — I froze the exact request and response shapes as a
contract before any real backend existed, so swapping the mock for the
real API later needed zero component changes, just an environment flag.
The backend is FastAPI: on startup it loads the entire national rail
timetable into memory as plain Python dictionaries, not a database,
because an earlier version doing this as SQL joins took 80 to 100
seconds per search. A request geocodes both places, finds nearby usable
stations for each side, searches that in-memory structure for direct and
one-transfer journeys, attaches a real road-distance leg through an
external routing API, scores every candidate on time, cost, reliability,
and transfer count, and returns a ranked list. Postgres is still there,
but for what it's genuinely good at — user accounts, saved trips, and
the once-at-startup timetable load — not for per-request routing."

### Q15. "Why PostgreSQL and not MongoDB?"
"The data is genuinely relational — trains have ordered stops, stops
reference stations, saved trips and recent searches belong to a specific
user with real foreign-key integrity I actually rely on. I also
originally needed PostGIS for geospatial nearest-station queries, a
mature, indexed capability Postgres has that Mongo's geospatial support
doesn't match as deeply. If I'd had loosely structured, deeply nested,
schema-varying documents — activity feeds, user-generated content — I'd
have looked at Mongo seriously; this data just isn't that shape. Worth
noting honestly: I later moved the actual per-request routing off
Postgres entirely into an in-memory graph for performance, so today
Postgres does exactly what it's strongest at and nothing it was ever
weak at."

### Q16. "Why FastAPI over Django or Flask?"
"Three concrete reasons. First, FastAPI's built-in Pydantic validation
gave me request and response schema enforcement and auto-generated
Swagger docs for free — I needed to prove the API contract's shape was
right fast, since the frontend was built against it before real logic
existed. Second, Django's batteries-included ORM and admin panel would
have been dead weight — my routing logic bypasses an ORM entirely and
talks to Postgres with tuned raw queries because I needed exact control
over what got indexed. Flask would have meant hand-rolling the
validation FastAPI gives by default. Where I'd reconsider: if this grew
into a large team project needing Django's admin panel and built-in auth
scaffolding for non-technical staff, that calculus changes."

### Q17. "Why React and not Vue or Angular?"
"Mostly ecosystem depth for what I needed to build — a real interactive
map, complex animated state like the reliability gauge and the
route-decision playback — and React's ecosystem for those is the
deepest I had hands-on experience with. Vue's simplicity is genuinely
appealing for a smaller app; Angular's structure would be overkill for a
solo project this size. If I were joining a team already standardized
on Vue, I wouldn't fight that — the underlying component model
translates."

### Q18. "Why Zustand instead of Redux?"
"Scale of state, mostly. I have four small, independent stores — search
state, auth session, theme, toasts — none of which need Redux's
action, reducer, and middleware ceremony. Zustand gets me the same
global-state sharing with a fraction of the boilerplate. Redux Toolkit
narrows that gap somewhat, but for this app's actual state complexity it
would have been process for its own sake. I'd reach for Redux if this
grew into dozens of interdependent stores needing strict action
auditing or time-travel debugging."

### Q19. "Why JWT bearer tokens instead of session cookies?"
"Because the frontend and backend are deployed on separate origins —
Vercel and Render — and cross-site cookies get fragile fast there,
between SameSite restrictions and third-party-cookie blocking. A bearer
token in an Authorization header has no such cross-origin baggage. The
trade-off I accepted knowingly: no server-side session revocation exists
yet — a stolen token is valid until its 14-day expiry regardless of
logout. For a bigger production system I'd add a revocation list or
move to shorter access tokens with refresh tokens."

### Q20. "Why not GraphQL instead of REST?"
"The API surface here is small and its shapes are fixed and well known —
a handful of endpoints returning a frozen contract shape, not a
flexible graph of relations different clients need to query
differently. GraphQL earns its complexity when you have many clients
with genuinely different data needs from the same backend; I have one
frontend consuming a stable, already-designed shape. REST plus FastAPI's
automatic OpenAPI docs gave me everything I needed with far less setup
overhead."

### Q21. "How would you scale this to real production traffic?"
"Three concrete things, not hand-waving. First, the in-memory caches and
the route store are currently per-process — they'd need to move to
Redis so multiple backend workers share one consistent cache instead of
each holding an independent, inconsistent copy; that's already the
documented next step, just not built yet since a single-process
deployment doesn't need it today. Second, the Postgres connection pool
is sized for one worker — I'd need to size it deliberately per worker
count once I actually run more than one. Third, I'd add real
request-level observability — latency percentiles, error rates — since
right now my only signal is manual testing and application logs."

### Q22. "What's the single biggest weakness in your current architecture?"
"The in-process caches and result store don't survive a restart and
don't coordinate across multiple workers. I know exactly why — avoiding
Redis as extra infrastructure until it was actually needed — but it's a
real, documented limitation, not something I'm unaware of. A
transfer-route's detail page can 404 after a restart until that
corridor gets searched again; direct-route pages don't have this
problem because their IDs are rebuildable purely from the schedule
graph."

---

## Section 4 — Algorithms & Data Structures

### Q23. "Explain the core routing algorithm."
"It's a graph search over an in-memory structure loaded once at
startup — a dictionary mapping each train to its ordered stop list, and
a reverse index mapping each station to every train that stops there.
For a direct search, I scan every train reachable from a candidate
boarding station for a later stop at a candidate alighting station. For
a one-transfer search it's two phases: first find every busy hub
reachable from the origin, keeping only the fastest way to reach each
one; then from each of those hubs, search for a feasible onward
connection to the destination, where 'feasible' means the wait is long
enough to cover the first train's typical lateness. This mirrors the
core idea behind real transit-routing algorithms like RAPTOR and the
Connection Scan Algorithm — route over in-memory arrays, not a
database — though what I built is a simpler two-phase search, not the
full formal multi-round algorithm, since the schedule size didn't need
that level of sophistication."

### Q24. "What's the time complexity of your search?"
"Direct search is roughly the number of trains through the candidate
boarding stations times the average stops per train — in practice a few
thousand list scans, sub-millisecond. The one-transfer search adds a
hub-discovery pass capped at the busiest 40 reached hubs specifically to
bound the search, since a very well-connected hub could otherwise make
the second phase scan an unbounded number of onward trains. The
nearest-station lookup is a separate scan across all stations, around
8,700 comparisons, also sub-millisecond in pure Python."

### Q25. "Why not use a graph library like NetworkX, or a standard shortest-path algorithm like Dijkstra?"
"Because this isn't a generic weighted-graph shortest-path problem — the
actual constraint is time-expanded feasibility, meaning does a train
exist at this station at a time that lets me catch a specific onward
train, which standard Dijkstra doesn't model directly without first
building a time-expanded graph. A general-purpose library also adds
overhead for exactly the array-scanning speed I was optimizing for.
Writing the two-phase scan directly over plain dictionaries let me
control precisely what gets touched per request, which is what actually
got latency down to sub-millisecond."

### Q26. "How would you extend this to support two transfers instead of one?"
"The same two-phase pattern, one layer deeper: after reaching hubs from
the origin, search for a second reachable hub from each of those, then
search onward to the destination from there, with the same busiest-N cap
at each layer to keep the search bounded, since transfer count compounds
branching fast. I haven't built this because the data shows the
overwhelming majority of real routes need at most one change; I'd only
add the complexity if real usage data showed genuine demand for it."

### Q27. "How do you find the nearest railway station to an arbitrary place?"
"A haversine great-circle distance from the query coordinate to every
station with at least one train — about 8,700 of them — kept if within a
search radius. Separately, I also keep any station busy enough to count
as a major hub within a much wider radius even if it's farther away,
specifically so a remote place whose literal nearest station is a tiny
dead-end halt still surfaces the real regional gateway as a candidate.
That's not a spatial-index optimization — it's a product decision to
always show the useful option, not just the technically closest one."

### Q28. "Why haversine and not a proper spatial index like PostGIS or a KD-tree?"
"I actually started with PostGIS doing exactly this as an indexed
spatial query. I removed it for the same reason I removed database-based
routing — a network round trip per request for a lookup over only about
8,700 points is needless overhead once you can just hold them in RAM. A
KD-tree would technically beat a linear haversine scan asymptotically,
but at this size the cost of about 8,700 simple float calculations in
Python is already sub-millisecond — the added complexity of building and
maintaining a tree wouldn't be measurable in real latency. I'd revisit
that trade-off if the station count grew by orders of magnitude."

---

## Section 5 — Machine Learning / Data Science

### Q29. "Walk me through your ML model end to end."
"The goal was replacing 'this train averages 39 minutes late, always'
with a prediction conditioned on the actual trip — day of week, month,
position along the route. I trained on 38.4 million historical,
per-station delay observations, using scikit-learn's histogram
gradient-boosting regressor. Rather than predicting one number, I train
six independent models at six quantile levels — the 10th, 25th, 50th,
75th, 90th, and 99th percentile of delay — so I get a full predicted
distribution, not a point estimate. Everything downstream — the typical
delay shown, the worst-case buffer, on-time probability, and connection
safety — is derived from that one distribution by reading probabilities
off it, so those numbers can never contradict each other."

### Q30. "Why quantile regression instead of a single regression model?"
This is one of the strongest stories in the whole project — lean into it.

"Because a single point prediction throws away exactly the information
that matters for a safety decision — a train that averages 40 minutes
late might be reliably 35 to 45 minutes late, or it might usually be on
time with an occasional catastrophic 3-hour delay, and those are
completely different risk profiles that average to the same number.
Predicting the full quantile curve lets me answer 'what's the
probability I make a 75-minute connection,' not just 'what's the average
delay.' I actually learned this lesson the hard way — an earlier version
trained a separate mean model alongside the quantile models, and because
it had no mathematical relationship to them, a real user caught a case
where the displayed average looked bigger than a connection buffer that
was shown as '56% safe' — which reads like a contradiction even though
the underlying math was fine. I fixed it by deriving the average by
numerically integrating the same quantile curve instead of a separate
model, so that class of contradiction became structurally impossible,
not just unlikely."

### Q31. "Why HistGradientBoostingRegressor instead of LightGBM, XGBoost, or a neural network?"
"LightGBM was actually my original plan, since it's the standard tool
for this kind of tabular problem. I switched to scikit-learn's histogram
gradient boosting specifically because it's the same underlying
algorithm family — LightGBM essentially originated it — but ships with
no native compiled dependency to manage at deploy time, for effectively
zero accuracy difference on this problem. A neural network would be
genuine overkill here — I have about eight structured, low-cardinality
features and a few million training rows after sampling; gradient-
boosted trees are the standard, better-calibrated choice for tabular
data at this scale, and a deep model would add training complexity and
inference latency for no measurable accuracy gain. I'd reconsider a
neural approach only if I had a genuinely different data modality —
sequences, images, text — which this isn't."

### Q32. "What features did you use, and why those specifically?"
"The train's historical average delay as a baseline the model refines,
its tier — premium, superfast, express, or passenger — day of week and
month of travel, scheduled arrival hour, how many days into a multi-day
journey that stop falls on, and the train's position along its route as
a fraction of total distance. I deliberately left out anything that
would only be knowable in real time, like an upstream train's live
current delay — the roadmap originally suggested that feature, but it's
not available when someone's actually planning a future trip, so
training on it would have been feature leakage that could never be
replicated at serve time."

### Q33. "How did you evaluate the model — how do you know it's actually good?"
"A held-out test split, comparing the quantile-derived mean prediction
against the train's flat historical average — the baseline it needs to
beat to be worth using at all. It came out to 26.9 minutes mean absolute
error versus 29.3 for the flat average, about an 8% improvement. I also
checked quantile calibration directly — does the 90th-percentile
prediction actually get exceeded about 10% of the time in held-out
data — and it came out very close to nominal, which is what actually
makes the derived probabilities trustworthy, not just the headline error
number."

### Q34. "What's a real limitation of your model you'd tell an interviewer honestly?"
"I found this myself, not through a complaint — I broke the evaluation
down by how many days into a multi-day journey a leg falls, instead of
trusting one aggregate error number, and found the model is measurably
worse than the flat baseline for legs more than a day into a multi-day
trip — 70 minutes of error there versus a 29-minute baseline. So I added
an explicit guard that refuses to predict past that point and falls back
to the simpler measured average instead — a model that's demonstrably
worse than what it's replacing shouldn't override it just because it
exists."

### Q35. "Why didn't you build ML for seat-confirmation prediction, if delay prediction got ML treatment?"
This is a genuinely great judgment question — it shows restraint.

"Because there's no free source of real seat-confirmation outcomes to
train on — no PNR or booking-status feed exists in the open data I have
access to. Training a model with zero real labels would just be
memorizing noise while looking sophisticated. Instead I built a
transparent, clearly-labelled heuristic based on quota logic and lead
time, and left the real fix — a live data collector accumulating actual
outcomes over time — as an explicit, planned but not-yet-built next
step. I'd rather ship an honest estimate than a fake-precision model."

### Q36. "Someone asks: can you also predict ticket prices by season? What do you say?"
"I actually got this exact request and checked the data before building
anything. Indian train fares in the data I have are government-regulated
distance-slab fares, completely fixed per route and class, with zero
real date variation. Training a model to predict a target that's
genuinely a constant in the ground truth would just output the same
number wrapped in ML-shaped noise, while implying to users that prices
meaningfully move when they legally don't. I built something honest
instead — a festival calendar drives a real fare multiplier for the one
place price actually does move, premium dynamic-fare trains, plus a
scarcity warning for cheaper classes on peak dates."

### Q37. "Why scikit-learn and not TensorFlow or PyTorch?"
"Because this is a tabular regression problem with about eight
structured features, and gradient-boosted trees are the well-established
stronger tool for that data shape — deep learning's advantages show up
on unstructured data like images, text, or sequences, none of which
apply here. Reaching for TensorFlow or PyTorch would have added training
complexity, a heavier runtime dependency, and inference latency, for no
accuracy benefit I could point to. I'd pick a deep framework the moment
the actual problem shape called for it."

---

## Section 6 — Data Engineering

### Q38. "Where did your data actually come from?"
"All free and open sources, since I explicitly ruled out any paid data
or scraping. The rail network structure comes from a CC0 community
dataset; the current timetable from a 2026 scrape; real fares from a
scraped IRCTC price dataset; a full year of measured delays and per-stop
distances from a large Kaggle delay dump; and the city and town
gazetteer from GeoNames, giving over half a million searchable places."

### Q39. "Tell me about a time you found the data itself was the problem, not your code."
Situation: the engine originally ran on a timetable from 2016. Task: I
needed to know if that staleness actually mattered before deciding what
to fix. Action: I ran a real audit, manually checking 28 trains against
a live source. It came back zero exact matches, 19 changed, 9 gone
entirely, and two train numbers had been silently reused for completely
different routes, which is worse than a 404 because it looks correct. I
also ran a duration benchmark on ten famous corridors before concluding
anything, and found travel times were actually only about 7% off — it
was specifically train identity that had rotted, not the network
structure. Result: I swapped in a current scrape, which needed a
three-layer station-name-to-code mapper since the new source used names
instead of codes, and dropped the old schedule data from the database
entirely rather than keeping it as a fallback — a 0%-accurate fallback is
actively harmful, not a safety net.

### Q40. "Tell me about a bug caused by two data sources disagreeing with each other."
Situation: a user reported a train that appeared to travel 340km off its
real route into a completely different state and back. Task: figure out
if this was a display bug or something deeper. Action: I dumped that
specific train's full stop list with coordinates and looked for the
discontinuity by eye, and found one stop whose stored location jumped
about 340km north of its neighbours. The root cause was a fuzzy
name-matcher binding a schedule stop named "Sangariya" to the wrong
station code — a real station in Jammu and Kashmir that happened to
share a similar name with the real station in Rajasthan. Result: I built
a detector with no hardcoded list — every stop's expected location is
the midpoint of its neighbours across every train that serves it, so a
station whose stored coordinate is consistently far from that consensus
gets flagged as mis-identified — and fixed the high-confidence cases
directly in the data. For the cases too ambiguous to auto-fix, I added a
permanent routing guard that refuses to board or alight anywhere that
would force an implausible geographic detour, so the whole bug class
became structurally impossible, not just this one instance.

### Q41. "Why isotonic regression for fares instead of a simple lookup table or average?"
"The original approach bucketed real fares into 50km bands and took the
median — real data, but diluted, with two real failure modes: a
staircase jump at bucket boundaries, and no guarantee a farther bucket
couldn't price lower than a nearer one from pure sampling noise.
Isotonic regression fits a monotonic curve directly on every real sample
with no bucketing at all, which makes 'fare never decreases with
distance' a mathematical guarantee instead of something I had to hope
held."

### Q42. "Why didn't you just scrape live fares or seat availability from IRCTC directly?"
"Because IRCTC's terms of service prohibit automated access to the
booking flow, and that's a line I decided not to cross regardless of how
the request was framed — not a technical inconvenience to route around,
a deliberate boundary."

---

## Section 7 — Backend Engineering & APIs

### Q43. "How does your authentication actually work?"
"Email and password, hashed with bcrypt, never stored in plain text or
reversibly encrypted. On successful login I issue a signed JWT with a
14-day expiry, sent as an Authorization bearer header rather than a
cookie, specifically because the frontend and backend are deployed on
different origins. Password reset issues a random token that's emailed
to the user, but only its SHA-256 hash is stored server-side, so a
leaked database dump can't be turned into a usable reset link."

### Q44. "How do you prevent someone from brute-forcing logins?"
"Tiered, dual-axis rate limiting specifically on the auth endpoints —
login is capped at 15 attempts per IP and 8 per email address within a
5-minute window, checked before the bcrypt hash even runs so a flood of
attempts doesn't also become a CPU-exhaustion issue. The dual axis
matters: an IP cap alone slows one attacker hammering many accounts, but
a distributed attacker spreading requests across many IPs would sail
past it — the per-email cap catches that case too."

### Q45. "Explain the circuit-breaker pattern you used for the road-routing API."
"I call an external API to get real road distance and duration for
first- and last-mile legs. I measured what happens when that service is
down — a single failed call took nearly 3 seconds before timing out,
which is nothing for one call, but a single search can have a dozen-plus
road legs, so a down provider would cost that once per leg, and every
subsequent search would pay it again. The fix: one failure disables that
specific provider for a 30-second cooldown, returning the fallback
instantly with zero network attempts during that window, then
auto-retries after. I verified it concretely: the first search after a
failure took about 3 seconds, paying the discovery cost once; the very
next search took about a second, breaker already open."

### Q46. "Why do you have two fallback map providers instead of just one?"
"Because free-tier rate limits are real — I actually hit this in
production. Several candidate routes in one search often need the exact
same road leg, say the same last-station-to-destination hop, and each
was independently calling the API for identical coordinates, burning
through the daily quota on pure duplicates. I fixed the duplicate-call
problem with a coordinate-keyed cache, and separately added a second
independent provider so that if the first one's quota or uptime fails,
the same request falls through to the second instead of dropping
straight to the crude distance estimate. Each provider has its own
independent circuit breaker, so one being down doesn't mute the other."

### Q47. "Walk me through what happens if your database goes down."
"Every database-touching path is wrapped so a failure degrades instead
of crashing. If the database is unreachable at startup, the schedule
graph just doesn't load, and search requests fall back to three
hand-built example corridors instead of a 500 error. If it fails
mid-request, say during a geocode lookup, the search endpoint catches
that specific failure and does the same fallback. This was actually a
real, documented incident, not a hypothetical — I found on a second
machine that a missing dependency plus no data-download script meant a
fresh clone couldn't even boot the fallback mode, so I fixed both the
missing dependency and widened the exception handling to actually catch
that class of failure."

### Q48. "How do you test a backend like this?"
"Pytest, with a deliberate split: pure unit tests that need no
infrastructure and always run — scoring formulas, JWT encode and decode,
the road-routing fallback logic with mocked HTTP calls — and integration
tests that hit the real engine and database, gated behind a fixture that
checks whether the database is actually reachable and skips gracefully
if not. That means a fresh clone with no .env file still runs a
meaningful subset of the suite. There are 117 test functions total
across the suite right now."

### Q49. "Why raw SQL through psycopg instead of an ORM like SQLAlchemy?"
"The query surface is genuinely small and performance-sensitive, a
handful of indexed lookups for geocoding and the once-at-startup
timetable load, and I wanted exact control over what indexes get used.
One of my own real bugs was an ORM-style OR clause silently forcing a
full-table scan across half a million rows because only one side of the
OR was indexed. Hand-writing that query let me fix it with a targeted
index instead of fighting an abstraction layer to generate the plan I
wanted. I'd reach for an ORM happily on a bigger CRUD-heavy surface —
this app's actual database usage is narrow enough that I valued the
control more than the productivity."

---

## Section 8 — Frontend Engineering

### Q50. "Why build the frontend against a mock API before the backend existed?"
"So I could build and validate the entire user experience — nine
screens, the map, dark mode, the whole flow — without being blocked on
backend work, and so I'd be forced to freeze the exact API shape as a
contract up front. When the real backend landed, swapping the mock for
real fetch calls needed zero component changes, just an environment
flag, because every page was already written against that frozen
contract."

### Q51. "What is MSW and why use it instead of just hardcoding fixture data in components?"
"Mock Service Worker intercepts actual fetch calls at the network layer,
so from a component's point of view it's indistinguishable from a real
API, no special-casing 'if mock, do this.' That's what let me throw the
mock layer away later with a single environment flag instead of hunting
down hardcoded data scattered through components."

### Q52. "Why Zustand's persist middleware for some stores but not others?"
"Only what's genuinely safe to survive a page reload gets persisted —
theme choice, and the auth token plus user object so you're not logged
out on every refresh. Saved trips and recent searches are deliberately
not persisted to local storage even though they use the same store,
because that data is now server-owned per user — persisting a stale
local copy risks showing one user's saved trips to whoever opens the
browser next on a shared device."

### Q53. "How did you handle dark mode?"
"A single set of semantic CSS variables — background, text, border,
accent colors named by role, not by hex value — defined once, with a
second block of the same variable names overridden inside a dark class.
Every component just uses the semantic class names, so toggling dark
mode is one class flip on the root element, not a per-component
conditional."

### Q54. "Why lazy-load the map component specifically?"
"Because adding the mapping library alone grew the main JS bundle to
about 1.5MB, and most screens never show a map at all — the search and
results pages don't need it. Lazy-loading it with React's lazy and
Suspense means that weight only downloads when someone actually opens a
screen that needs it, and the main bundle dropped back to under 500KB."

---

## Section 9 — Security

### Q55. "How do you store passwords?"
"Bcrypt hashing, never plain text, never a reversible encryption. Bcrypt
specifically because it's designed to be slow — that's a feature, since
it makes brute-forcing a leaked hash database expensive."

### Q56. "How do you prevent SQL injection?"
"Every query uses parameterized placeholders through the database
driver — user input is never string-formatted directly into SQL. That's
not a special defense I bolted on, it's just how the driver's API is
used throughout."

### Q57. "What input validation do you have on your API?"
"A strict base model that rejects any field it doesn't explicitly
expect, rather than silently ignoring unknown ones, which alone closes
off a class of mass-assignment-style bugs. Every field also has bounded
lengths, and things like the sort preference or date format are typed
as an exact enum or regex pattern rather than an open string, so
malformed input gets rejected at the API boundary instead of reaching
business logic."

### Q58. "What happens if an unhandled exception occurs in production — what does the client see?"
"A global exception handler catches anything unhandled, logs the full
traceback server-side for me to actually debug, but returns a generic
error message to the client — never a raw stack trace, a file path, or
a raw database error string. That's a deliberate boundary: debugging
detail is mine to see, not something to leak to whoever's calling the
API."

### Q59. "If you found a real vulnerability in your own app tomorrow, what would you do?"
"Fix it and ship the fix immediately rather than waiting for a
convenient moment, since this is a live deployed app with real user
accounts — even if traffic is low right now, credentials and personal
data are still real. I'd also check whether the same class of mistake
exists anywhere else in the codebase, not just patch the one instance,
since most of my real security work here was exactly that: a deliberate
pre-launch sweep covering rate limiting, strict validation, and a
dependency audit, rather than a reactive one."

### Q60. "Did you run a dependency vulnerability scan?"
"Yes, before deploying. npm audit came back clean on the frontend, and
pip-audit on the backend flagged exactly one package, a build tool
rather than a runtime dependency, which I bumped to the patched
version."

---

## Section 10 — DevOps & Deployment

### Q61. "How and where did you deploy this?"
"Backend on Render, frontend on Vercel. Vercel's rewrite config forwards
/api/* requests straight to the Render backend, so the deployed frontend
talks to the API same-origin, no CORS configuration needed in
production. Render's free tier sleeps after inactivity, so I have an
external uptime pinger hitting the health endpoint every five minutes to
keep it warm."

### Q62. "Tell me about a bug you only found after actually deploying, not in local testing."
This is a genuinely great story because it shows you test the real
deployed thing, not just a successful build.

Situation: everything passed locally, 116 tests green, manual testing
looked fine. Task: once deployed, direct links like the login page or an
emailed password-reset link returned a static 404 instead of the actual
app. Action: I traced it to my own deploy config — Vercel auto-adds a
fallback that routes any unmatched path to the app's entry point, but
that automatic behavior gets silently disabled the moment you ship your
own rewrite rules, and mine had exactly one rule, the API proxy, with
nothing for everything else. Before shipping the fix, I specifically
checked Vercel's own docs to confirm rewrites only apply after a real
static-file check, so I could be certain the fix wouldn't accidentally
break loading actual JS or CSS files. Result: added a second rule
routing everything else to the app entry point, ordered after the API
rule since rewrite rules are evaluated in order. Verified live: the
emailed reset link, which navigates directly and never goes through
client-side routing first, now works correctly.

### Q63. "Tell me about a second deploy-specific bug."
Situation: password-reset emails always failed with a timeout, even
though the exact same SMTP credentials worked fine locally. Task: figure
out whether this was a config mistake or something environmental.
Action: I reasoned from the failure mode, not just the error message — a
wrong password or host fails fast with a clear authentication or DNS
error; a timeout after the full wait is the signature of packets being
silently dropped, which points to a network-level block, not bad
credentials. I confirmed Render blocks all outbound traffic on standard
SMTP ports on its free tier as a platform policy, which no amount of
correct configuration can work around. Result: switched from raw SMTP to
the same email provider's HTTPS API instead, which travels over port 443
and is never blocked — same provider, same free tier, just a different
transport, and no new dependency since I already had an HTTP client in
the project. I explicitly rejected upgrading to a paid hosting tier just
to unblock one port when a free, equally reliable alternative already
existed on the same provider.

### Q64. "Why Render and Vercel instead of AWS or a single provider for both?"
"Mainly a free-tier and setup-speed decision for a portfolio project
deploying solo, not traffic I've had to handle yet. Vercel is genuinely
excellent specifically for a Vite/React static-plus-rewrites deployment;
Render gave me a straightforward git-push deploy for a long-running
Python process, which matters here since the app holds a large
in-memory graph and ML model in RAM — that needs a persistent process,
not a scale-to-zero serverless function. I'd move to AWS deliberately if
I needed finer control over autoscaling, a custom network setup, or cost
optimization at real scale, none of which this project needs yet."

### Q65. "Do you have CI/CD set up?"
"CI, yes — GitHub Actions runs the full backend pytest suite and the
frontend lint-and-build on every push and pull request to main, so a
regression gets caught before merge. I'll be precise about the CD half
though: there's no automated deploy step in that workflow. Render and
Vercel each auto-deploy independently whenever they see a push to the
connected branch. So it's CI plus two separate platform-level
auto-deploys, not a single unified pipeline that does both."

---

## Section 11 — Behavioral / STAR Challenge Bank

### Q66. "Tell me about the hardest technical problem you solved on this project."
The flagship story. Always have this one ready cold; it comes up in
nearly every interview about this project.

Situation: searching a route that needed a train change took 80 to 100
seconds, completely unusable. Even a simple direct search took about 7
seconds. Task: find the actual bottleneck, not just guess and optimize
randomly. Action: I profiled it in layers instead of assuming one fix
would solve everything. Layer one: the transfer search was running as
SQL self-joins on a 417,000-row table, over the network, multiple times
per request — I moved the whole timetable into memory and searched it
there instead, the same approach real transit-routing engines use. That
alone took pure routing compute from 100 seconds to 0.06 milliseconds,
but the overall search was still slow, which told me there was a second
bottleneck. Layer two: two heavy spatial database queries per request
for "nearest station" — moved that in-memory too, as a simple distance
calculation over about 9,000 points. Layer three: I found a geocode
query doing a full-table scan because of an unindexed OR clause, and
added the missing index. Layer four: a fresh database connection was
being opened on every single request, so I added a connection pool,
warmed at startup. Layer five: startup itself took 37 seconds and once
failed outright mid-load, so I cached the built graph to a local file so
later startups load it in under half a second. Result: cold transfer
search went from 80-100 seconds to about 0.8 seconds, measured, not
estimated, and repeat searches became essentially instant with a result
cache. The real lesson wasn't any one fix, it was that fixing the
biggest bottleneck reliably reveals the next one — I had to keep
re-measuring instead of declaring victory after the first win.

### Q67. "Tell me about a time real data exposed bugs that test data hid."
Situation: once I swapped in real fares, real distances, and a year of
real delay data, three genuine bugs surfaced immediately in ordinary
use, none of them new, all three simply invisible while every route's
numbers looked roughly uniform. Task: fix all three, and understand why
uniform test data had hidden them. Action: one was a "next train"
fallback suggesting a train that had already departed hours earlier —
the logic was literally "the next item in a ranked list," with zero
check on departure time, which only looked wrong once departure times
actually varied realistically. A second was transfer buffers accepting
any 30-minute gap even for a train that's routinely 40-plus minutes
late — I fixed the minimum buffer to scale with that train's actual
measured lateness. Result: all three fixed, with a regression test
locking each invariant so they can't silently come back. The lesson: never
fully trust a feature validated only against uniform or synthetic
data — real, varying data is itself a bug-finding tool.

### Q68. "Tell me about a time you disagreed with your own earlier design decision and changed it."
Situation: I originally scoped this as a trains-first app, with road
transport only as a small first- and last-mile connector. Task: decide
whether that scope was actually right as the product matured. Action: I
revisited it and concluded it was subtly dishonest to the real question
a traveler asks — for a short trip, or a genuinely poorly-railed pair of
cities, a direct cab or bus is often objectively the better answer, and
hiding that behind an always-rail-centric answer wasn't serving the
user, it was serving my own initial framing. Result: I rebuilt the
ranking so a direct road option competes on equal footing with rail
candidates and can win outright, and verified it against real short
corridors where it should and shouldn't win, to make sure I hadn't just
swung the bias the other way.

### Q69. "Tell me about a time you said no to a request, or refused to build something you were asked for."
Situation: I was essentially asked to build something that finds real,
live per-route fares automatically. Task: figure out the right way to do
that. Action: the obvious version would be scraping IRCTC's live booking
site, but their terms of service explicitly prohibit automated access to
that flow, so I ruled that out on principle, not as a technical
inconvenience to route around. I also considered hardcoding the
"official" government fare formula from memory, and rejected that too,
since the exact current rates are revised periodically and I didn't have
a verified-current figure I'd trust as ground truth — a wrong number
stated confidently is worse than an honest approximation. Result: I
improved what I already had instead, real scraped fare data fit with a
proper monotonic regression instead of coarse bucket averages, which
used no new, questionable data source and produced a mathematically
guaranteed correct shape.

### Q70. "Tell me about a time you had to make a trade-off between doing it 'right' and shipping."
Situation: the transfer-route result cache and detail-page store are
both simple in-memory dictionaries that reset on every server restart —
the textbook-correct fix is Redis. Task: decide whether to build that
now or defer it. Action: I deliberately deferred it, because a
single-process local deployment genuinely doesn't suffer the
multi-worker consistency problem Redis exists to solve, and adding a
whole new infrastructure dependency before it was needed would have been
solving a problem I didn't have yet at the cost of real time. Result: I
documented it explicitly as a known, deliberate simplification with a
clear trigger for when to revisit it — the moment this runs behind more
than one worker process or needs to survive restarts without
user-visible breakage.

### Q71. "Tell me about a time you had to learn something completely new to finish this project."
Situation: I'd never trained a real ML model in production before
starting the delay-prediction feature. Task: get from "I have 38 million
rows of raw delay data" to a model I could actually trust enough to show
a percentage to a real user. Action: I read into why a single
point-estimate model wasn't the right shape for a safety-relevant
number, which is what led me to quantile regression instead of a
standard regressor, and I specifically learned to break evaluation down
by slice, by tier, by how far into a multi-day trip a leg falls, rather
than trusting one aggregate accuracy number, because that's exactly what
caught the model being genuinely worse than the baseline for a specific
thin slice of the data. Result: a model that's honest about where it's
reliable and explicitly refuses to predict where it measurably isn't.

---

## Section 12 — Judgment / "Why Didn't You" Questions

### Q72. "Why is seat confirmation still just a heuristic, not ML, if delay prediction got ML treatment?"
"Because delay prediction had 38 million real historical labels sitting
on disk to train on, and seat confirmation has zero — there's no free
feed of real booking or PNR outcomes anywhere I could find. Training a
model on no real labels produces something that looks sophisticated
while being worse than an honest, transparent quota-based rule. That
genuinely blocks on a live data collector I haven't built yet, since
there were no real users to collect from until the app was actually
deployed."

### Q73. "Why didn't you build the live 'Lifeline' monitoring for real yet?"
"Because it needs infrastructure I haven't justified building yet, a
live train-status feed and a way to actually push updates to a user
mid-journey, and I wanted the routing and reliability core to be solid
and genuinely trustworthy first, rather than splitting effort across a
flashy feature and the foundation it would sit on. It's on the roadmap
as its own explicit phase, not forgotten."

### Q74. "If you had unlimited time, what would you build next?"
"The live data collector, honestly, before anything else — it's what
unlocks turning seat confirmation into a real model and what would
eventually make Lifeline real. Everything else, better ranking,
village-level coverage, real scheduled bus data, is genuinely valuable
but secondary to that one dependency."

### Q75. "What would you do differently if you started this project over today?"
"I'd build the staleness and confidence-signal tooling around the ML
model from day one instead of retrofitting it after training the first
version — knowing how many observations back a number, and whether the
model itself is getting old, turned out to matter as much as the
prediction itself. I'd also try to get a real, even tiny, data collector
running earlier, since almost every deferred feature in this project
ultimately traces back to not having one yet."

---

## Section 13 — Scaling & Advanced Curveballs

### Q76. "How would you handle 10x the current traffic?"
"In order of what breaks first: move the in-memory result cache and
transfer-route store to Redis so multiple backend workers share one
consistent view instead of each holding its own; size the database
connection pool deliberately per worker instead of the current
single-worker assumption; and add real observability, latency
percentiles and error rates, since right now my only signal is manual
testing. None of the core routing logic itself would need to change,
since it's already sub-millisecond per request once the graph is
loaded — the scaling problem here is state-sharing across processes, not
compute."

### Q77. "What happens if two servers run this at once right now, unchanged?"
"Each would build its own independent in-memory graph, cache, and route
store. They wouldn't be wrong exactly, but they'd be inconsistent with
each other, and a transfer-route detail request could succeed on
whichever server handled the original search and 404 on the other.
That's precisely the gap Redis would close. I've deliberately documented
it as a known limitation rather than pretending it isn't there."

### Q78. "How would you add real live train-position tracking?"
"I'd need a genuine live-status feed. Most free or unofficial ones are
rate-limited and best-effort, so I'd design around polling politely and
caching aggressively rather than assuming a reliable real-time push feed
exists. That data would feed a real version of the Lifeline re-routing
logic, replacing today's scripted simulation with actual live delay data
driving the same connection-safety math I already use for
planning-time predictions."

### Q79. "What's a part of this project you're not proud of, or would call weak?"
"The connection-wait calculation between two trains at a hub uses a
simple minutes-in-a-day wraparound that can't distinguish 'the next
train is 30 minutes later today' from '30 minutes later, tomorrow.' I
documented it explicitly as a known limitation whose error skews
conservative, it might miss a legitimate overnight connection, but it
won't invent an impossible one, but a fully day-aware version is
genuinely unbuilt, and I'd rather say that than pretend it's perfect."

### Q80. "How would you redesign this to support real-time collaborative trip planning, two people editing a trip together?"
"That's a genuinely different problem. I'd need shared, syncing state
instead of per-request stateless search, probably WebSockets or a
similar push channel, and some conflict-resolution strategy for
simultaneous edits. Today's architecture is deliberately stateless per
search, which is exactly wrong for that use case. I'd treat it as closer
to a fresh feature than an extension of the current design."

---

## Section 14 — Defend Your Resume Metrics (Rapid Fire)

### Q81. "Your resume says ~100 seconds to under 1 second — how did you actually measure that?"
"Direct timing of real search requests against real deployed data,
before and after each fix, not an estimate. I have it documented as a
before-and-after table across five separate fixes, since it was one
problem solved in layers, not one single change."

### Q82. "Your resume says 38M+ records — where does that number come from?"
"The size of the raw historical delay dataset the training script
streams through — it's stated directly in that script's own comments and
I've cross-checked it against the source dataset's own row count."

### Q83. "Your resume says ~8% accuracy improvement — improvement over what, exactly?"
"Over a flat historical average, the train's own overall average delay
used as a naive baseline. My model's held-out mean absolute error was
26.9 minutes versus 29.3 for that flat baseline, on a genuine held-out
test split it never trained on."

### Q84. "Your resume mentions 10,000+ trains — is that the whole Indian rail network, or a subset?"
"It's the number of trains actually loaded into the live routing graph,
which I confirmed directly from the running app's own health-check
endpoint. It's built from several merged real data sources, not the full
historical universe of every train that's ever existed — some smaller or
very new services may not be represented."

### Q85. "Your resume mentions a caching fix cutting 15 seconds to 1 second — walk me through that specific number."
"That's the road-routing API calls specifically. A brand-new corridor's
first search has to make a real network call for each distinct road
leg, which I measured at about 15 seconds total for a typical multi-leg
search. Once I added a coordinate-keyed cache for successful lookups,
repeating that exact same search dropped to about 1 second, same
corridor, zero new network calls, cache hits the whole way."

---

## Section 15 — Closing Questions

### Q86. "What are you most proud of in this project?"
"The performance investigation, honestly, not just that I fixed it, but
that I fixed it by actually measuring where time went at each stage
instead of guessing, and kept re-measuring after each fix instead of
declaring victory early. That habit, measure, fix the real bottleneck,
re-measure, is the thing I'd say generalizes best beyond this specific
project."

### Q87. "What was the hardest part of building this?"
"Knowing when not to build something — refusing to scrape IRCTC,
refusing to fake an ML fare predictor, refusing to ship a confirmation
model with zero real training labels. Those all felt like giving
something up in the moment, but each one was the right call, and being
able to explain exactly why is honestly harder than writing the code for
the feature I did build instead."

### Q88. "If you had one more week, what would you spend it on?"
"Moving the result cache and route store to Redis. It's the single
change that would remove the most real, currently-documented limitation,
and it's a well-scoped, known piece of work rather than something I'd
need to design from scratch."

### Q89. "What would you do differently about how you worked on this, not the code itself?"
"Start the real data-collection dependency earlier. Almost every
deferred feature in this project traces back to not having one, and I
only really felt that cost once I'd already built the routing and ML
layers on top of everything else."

### Q90. "Do you have any questions for me?"
Always have real ones ready. A candidate with none reads as
uninterested. Tailor to the actual company, but here are safe defaults
that connect back to real things this project taught you:

- "How does your team decide when a heuristic is good enough to ship
  versus when it's worth investing in a real model — is that a data
  availability question for you too, or something else?"
- "What does your team's approach to graceful degradation look like —
  how do you handle a dependency going down in production?"
- "What's the biggest technical debt your team is currently living with,
  and how do you decide when to actually pay it down?"
