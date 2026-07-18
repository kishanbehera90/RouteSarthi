# RouteSarthi — Steps to (Re-)Learn This Codebase From Scratch

A self-guided study plan for the day you come back to this project after
enough time has passed that it feels unfamiliar. The goal isn't "skim
every file once" — it's being able to predict what a function will do
*before* running it, and knowing which file to open when something breaks.

Pair this with the four reference docs already in the repo root:
- **`Introduction.md`** — what it is, how to run it, current status.
- **`ARCHITECTURE.md`** — module breakdown, the request lifecycle, algorithms.
- **`DECISIONS.md`** — why things are built the way they are, alternatives rejected.
- **`CHALLENGES.md`** — every hard bug, root cause, and fix.

Those four answer "what and why." This file is about "how do I personally
re-absorb it all, line by line, so it's *mine* again." Read them alongside
the steps below — don't read them cover-to-cover first as a substitute for
reading the code.

Budget: this is realistically a multi-session effort (think a full day,
or several shorter sessions), not a one-sitting read. Check off each box as
you go — the checklist itself is the record of where you left off.

---

## Phase 0 — See it run before you read a single line

You cannot understand code you've never watched execute. Do this first,
every time, even if you're impatient to start reading.

- [ ] Follow `Introduction.md` §4 exactly, from a clean shell, and get the
      backend running with the seed/mock data (no database needed for this
      first pass).
- [ ] Open `http://127.0.0.1:8000/docs` and manually fire every endpoint
      once from the Swagger UI. Look at the actual JSON that comes back.
- [ ] Start the frontend against the mock layer (no `VITE_USE_REAL_API`
      flag) and click through every screen once: onboarding → search →
      results → route detail → live journey → saved trips. Just look. Don't
      read code yet.
- [ ] If you have a `.env` with a real `DATABASE_URL`, repeat the backend
      step with the real engine running, and do one real search
      (e.g. `Gorakhpur` → `Prayagraj`, since that corridor is referenced
      constantly in `CHALLENGES.md` and the tests). Compare the response
      shape to the mock one — they should be structurally identical.

**Why this order:** every subsequent step is you building a mental model
of *this exact running thing*. Reading code first, without having seen it
run, means you're memorizing text instead of understanding a system.

---

## Phase 1 — Learn the vocabulary before the mechanics

Before touching any logic, learn the *shape* everything is built around.
This is deliberately the smallest, most declarative material — no
algorithms yet, just nouns.

- [ ] Read `frontend/API_CONTRACT.md` top to bottom. This defines every
      noun you'll see repeated everywhere else: `Corridor`, `Route`, `Leg`,
      a moving leg vs. a connection leg, `delayProfile`, `reasoning`.
- [ ] Read `frontend/src/data/routes.js` in full. It's just data, but it's
      real example data in the exact contract shape — you now have three
      concrete instances of every field you just read about.
- [ ] Open `backend/app/seed.py` side-by-side and confirm it's the same
      data, ported. You should be able to point at any field in one file
      and find its twin in the other.
- [ ] Read `backend/app/models.py`. These are the same nouns again, as
      Pydantic schemas. Notice which fields are optional (`| None`) —
      that tells you which parts of the contract are allowed to be absent
      (e.g. `hub` is only present for cross-origin routes).

**Checkpoint — don't move on until you can do this without looking:**
sketch, from memory, the nested shape of one `Route` object, including
where `legs` and `connection` markers sit relative to moving legs.

---

## Phase 2 — The backend core, in dependency order, not file-alphabetical order

Read backend modules in the order they actually depend on each other (see
`ARCHITECTURE.md` §3's import graph), so every new file only ever uses
things you've already read.

- [ ] `backend/app/config.py` — small, five minutes. Note that nothing here
      is required to be set; see how defaults work.
- [ ] `backend/app/db.py` — the connection pool. Note the one Supabase
      pooler-specific quirk (`prepare_threshold=None`) and *why* (comment
      explains it) before moving on.
- [ ] `backend/app/graph.py` — the biggest single concept in the backend.
      Do NOT skim this one. For each of these functions, before reading
      the body, write down (on paper or in a scratch file) what you
      *expect* it to do from its name and docstring, then read the body
      and check yourself:
      - [ ] `load()` / `_load_from_db()` / `_read_cache()` / `_write_cache()`
      - [ ] `nearest_railheads()`
      - [ ] `single_train()`
      - [ ] `one_transfer()` — the hardest function in the codebase; budget
            real time here. Trace through it with a concrete example: pick
            two real station codes and manually walk the two-phase search
            (reached-hubs, then feasible-onward-trains) on paper.
      - [ ] `stop_detour_km()` / `mislocated_stations()` — read
            `ARCHITECTURE.md` §5.5 and `CHALLENGES.md`'s Sangar/Sangariya
            entry alongside this one; the code alone doesn't explain why
            it exists.
- [ ] `backend/app/metrics.py` — read top to bottom; every function here is
      a small, independent, pure calculation. For each one, find its
      corresponding test in `backend/tests/test_metrics.py` and read them
      together (see Phase 3 below for why this pairing matters).
- [ ] `backend/app/delay_model.py` — read `ARCHITECTURE.md` §4.3 *first*
      this one time (the "predict a distribution, not a point" idea isn't
      obvious from the code alone), then read the file.
- [ ] `backend/app/roads.py` — small; the circuit breaker + cache pattern
      is worth understanding well since it recurs as a template for any
      future external-API integration in this codebase.
- [ ] `backend/app/auth.py` + `backend/app/email.py` — independent of
      everything above; can be read any time, in either order.
- [ ] `backend/app/engine.py` — the orchestrator, and now the payoff for
      everything above: every function it calls, you've already read.
      Read it in the order a real request actually flows
      (`ARCHITECTURE.md` §2 gives you that exact sequence) rather than
      top-to-bottom by line number.
- [ ] `backend/app/main.py` — last, on purpose. It's thin by design; you
      should recognize almost everything it calls into by now.

**Checkpoint:** without opening the file, describe what happens, in order,
from the moment `/api/routes?from=X&to=Y` is received to the moment JSON is
returned. Then open `ARCHITECTURE.md` §2 and compare — any gap in your
version is a module you need to re-read.

---

## Phase 3 — Read the tests as a second, executable copy of the documentation

Tests in this repo are not an afterthought — they encode the exact
invariants that were bugs once (`CHALLENGES.md` cross-references many of
them directly, e.g. "Plan B departs later," "buffer covers p50 delay").

- [ ] `backend/tests/conftest.py` first — understand the `client` /
      `engine_ready` / `need_engine` fixtures, since every other test file
      depends on them.
- [ ] For each backend module you read in Phase 2, immediately read its
      matching test file (`test_metrics.py`, `test_engine.py`,
      `test_roads.py`, `test_auth.py`, `test_contract.py`). Do this
      *function-by-function*, not file-by-file: read `metrics.route_reliability`,
      then immediately read every test that calls it, then move to the
      next function. A test failing to assert something you'd expect is
      itself information — it usually means that behavior isn't
      guaranteed, just incidental.
- [ ] Actually run the suite (`.venv\Scripts\python -m pytest -q -v`) and
      watch which tests get skipped vs. run, depending on whether you have
      a `.env`/database configured. Confirm you understand *why* each
      skip happened from `need_engine`'s logic, not just that it happened.

---

## Phase 4 — The ETL pipeline (read this after the core, not before)

These scripts explain *why the data looks the way it does* — reading them
before Phase 2 would mean reading about data transformations you have no
context to evaluate yet.

- [ ] Read `backend/etl/download.py` and `backend/etl/load_v2.py` together
      — notice the three-layer station name→code mapping and why it exists
      (cross-reference `CHALLENGES.md`'s timetable-replacement entry).
- [ ] Read `backend/etl/load_delays.py`, `load_schedule_extra.py`, and
      `load_fares.py` — each one is "stream a big CSV once, produce one
      artifact the server loads at runtime." Notice the shared pattern
      before focusing on what's different about each.
- [ ] Read `backend/etl/train_delay_model.py` last, now that you already
      understand `delay_model.py`'s serving side from Phase 2 — read the
      training script specifically looking for where each serving-time
      assumption originates (e.g. why `day_offset` and `sched_hour` are
      computed the way they are).
- [ ] Skim `fix_station_mismatches.py`, `verify.py`, `benchmark.py`,
      `sample_trains.py` — these are diagnostic/one-off tools; understand
      their *purpose* well enough to run them again someday, without
      memorizing their internals.
- [ ] Open `backend/etl/load_all.py` just long enough to read its
      deprecation docstring. Do not study its body in depth — it's kept
      only for historical reference.

---

## Phase 5 — The frontend, now that you know what data it's rendering

Reading the frontend before the backend would mean reading rendering code
for a shape you don't yet understand. Now you do.

- [ ] `frontend/src/App.jsx` and `main.jsx` — the whole route table and
      boot sequence, in about ten minutes.
- [ ] `frontend/src/index.css` — skim for the design-token system
      (`--color-surface`, `--color-content`, etc.) so every `bg-surface`/
      `text-muted` class you see later in components makes sense instead of
      looking like magic.
- [ ] The four Zustand stores, in this order: `useThemeStore` (simplest),
      `useToastStore` (simplest), `useAuthStore`, `useJourneyStore`
      (most complex, and the one with the one deliberate cross-store
      coupling — read `lib/api.js` immediately after this one and notice
      the 401-triggered logout).
- [ ] `frontend/src/pages/`, in the order a real user actually moves
      through the app: `Onboarding.jsx` → `Auth.jsx` →
      `Search.jsx` → `Results.jsx` → `RouteDetail.jsx` →
      `LiveJourney.jsx` → `SavedTrips.jsx` → `Compare.jsx` →
      `HubPicker.jsx` → `ResetPassword.jsx`.
- [ ] `frontend/src/components/`, pulled in as each page above references
      them, rather than as one long alphabetical pass — a component read
      in isolation, without the page that uses it, is much harder to
      understand.
- [ ] `frontend/src/mocks/handlers.js` last — by now you can confirm for
      yourself that it reproduces `API_CONTRACT.md` exactly, rather than
      taking that on faith.

---

## Phase 6 — Trace one real request, live, end to end

This is the step that turns "I read all the files" into "I understand the
system." Do this with the real engine running (a real `.env`), not the
mock layer.

- [ ] Pick one concrete search (e.g. `Imphal` → `Bengaluru`, since it's
      referenced constantly in the docs and exercises a one-transfer
      route).
- [ ] Add temporary `print()` statements (or set breakpoints if you're
      using a debugger) at the start of every function `ARCHITECTURE.md`
      §2 lists in its numbered sequence: `engine.search`, `_geocode`,
      `graph.nearest_railheads`, `graph.single_train`, `graph.one_transfer`,
      `engine._direct_route`/`_transfer_route`, `metrics.leg_delay_profile`,
      `roads.route`.
- [ ] Fire the request, and watch the actual values flow through — real
      station codes, real coordinates, the real cost/time numbers at each
      stage.
- [ ] Remove the temporary instrumentation once you've confirmed your
      mental model matches reality. (Never commit debug prints.)
- [ ] Do the same thing once for a request that should hit the *seed
      fallback* (e.g. search for a nonsense place name), and once for a
      request that exercises the `roads.py` circuit breaker (temporarily
      point `OSRM_URL` at an unreachable address and watch the fallback
      kick in, then remove the override).

---

## Phase 7 — Now read the "why" documents, with the code fresh in your head

Reading these first, before the code, would mean absorbing conclusions
you have no basis to evaluate. Reading them now, you can actually check
each claim against a function you already understand.

- [ ] `ENGINEERING_NOTES.md` — the full, detailed version of every bug
      story. Read it end to end once; for at least the three or four
      entries that most interest you, go back and re-read the *actual
      current code* for the function each one describes, and confirm the
      fix is still there in the form described.
- [ ] `DECISIONS.md` — for each decision, ask yourself "would I have made
      this same call, or a different one, with the same constraints?"
      before reading the reasoning given. This is the step that actually
      builds judgment, not just recall.
- [ ] `CHALLENGES.md` — read its final "fragile/unusual" section
      specifically as a checklist of places to be careful editing later.
- [ ] `PHASE_B_PLAN.md` and `PROJECT_LOG.md` — skim for the parts of the
      roadmap that are still unbuilt (the collector, the confirmation ML,
      learning-to-rank, deployment) so you know what's *intentionally*
      missing versus what might be a regression if you find it missing
      later.

---

## How to actually verify "I understand this line," not just "I read this line"

Use this test on any function that feels important, at any point in the
phases above:

1. **Predict before running.** Cover the function body, read only its
   name/docstring/signature, and write down what you expect it to return
   for two or three concrete inputs — including at least one edge case
   (an empty list, a `None`, a boundary value like exactly 30 minutes for
   a buffer check). Then read the body and check yourself.
2. **Find every caller.** Use the Grep tool (or your editor's
   "find references") to locate every place a function is actually called
   from. If a function has zero callers, that's worth noting — it may be
   dead code, or it may be an ETL/test-only utility, but you should know
   which before moving on.
3. **Find its test, or write one.** If a test already exists, read it as
   the executable specification of the function's guarantees. If no test
   exists for something you're unsure about, write a throwaway one (in a
   scratch file, not committed) — the act of writing an assertion forces
   you to state precisely what you believe the function does.
4. **Ask what happens on the missing/failure path**, specifically for
   anything that touches the network or the database: what does this
   return, or do, when the database is unreachable, when an external API
   times out, when a required field is `None`? This codebase's whole
   design philosophy is graceful degradation everywhere — if you can't
   answer this for a given function, you haven't understood it yet.

---

## A lightweight per-session checklist

Use this at the start of any future re-learning session shorter than a
full pass through all seven phases:

- [ ] Which phase did I stop at last time? (Check your copy of this file
      for unchecked boxes.)
- [ ] Is the code I'm about to read still described accurately by
      `ARCHITECTURE.md`/`DECISIONS.md`? (Check `git log` for commits since
      those docs were last updated — if there's meaningful drift, treat
      the docs as historical context, not current truth, and update them
      once you've re-verified the code yourself.)
- [ ] Before opening any file, can I state in one sentence what I expect
      it to be responsible for? If not, go back one phase.
