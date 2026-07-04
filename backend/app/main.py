"""RouteSarthi backend — Phase B.

Step 0 (scaffold): serves the API contract from seed fixtures, proving the
contract end-to-end with a real server. Endpoints mirror
frontend/API_CONTRACT.md exactly. Real data + the cross-origin engine arrive
in Step 1.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from . import seed
from . import engine
from . import graph


@asynccontextmanager
async def lifespan(_app):
    # Warm the in-memory schedule index AND the DB connection pool at startup so
    # the first real request is already fast. Failures here shouldn't block the
    # seed endpoints.
    try:
        graph.load()
        from .db import get_pool
        get_pool()  # open the pool now, not on the first request
    except Exception as e:  # noqa: BLE001
        print("startup warmup skipped:", e)
    yield
    try:
        from .db import close_pool
        close_pool()
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(
    title="RouteSarthi API",
    version="0.1.0",
    description="Routing + reliability engine for travel across India.",
    lifespan=lifespan,
)

# The frontend runs on Vite (5173) in dev; allow it to call the API directly
# once Phase C wiring begins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "phase": "B", "step": 1, "graph": graph.stats()}


@app.get("/api/corridors")
def list_corridors():
    return seed.CORRIDORS


@app.get("/api/corridors/{corridor_id}")
def get_corridor(corridor_id: str, response: Response):
    corridor = seed.get_corridor(corridor_id)
    if not corridor:
        response.status_code = 404
        return None
    return {"corridor": corridor, "routes": seed.get_routes(corridor_id)}


@app.get("/api/routes")
def search_routes(
    from_: str = Query("", alias="from"),
    to: str = "",
    pref: str = "confirmed",
    date: str = "",
):
    # Live engine over real data. Falls back to seed if the engine can't
    # geocode the place OR can't run at all (no .env / DB unreachable / no
    # graph cache) — so a fresh clone still serves the 3 demo corridors.
    try:
        result = engine.search(from_, to, pref, date or None)
    except Exception as e:  # noqa: BLE001
        print("engine unavailable, serving seed:", e)
        result = {"error": "place_not_found"}
    if result.get("error") == "place_not_found":
        corridor = seed.match_corridor(from_, to)
        if corridor:
            return {"corridor": corridor, "routes": seed.weight_routes(seed.get_routes(corridor["id"]), pref)}
        return {"corridor": None, "routes": []}
    return result


@app.get("/api/routes/{route_id}")
def get_route(route_id: str, response: Response):
    route = engine.get_stored_route(route_id) or seed.find_route(route_id)
    if not route:
        response.status_code = 404
        return None
    return route


@app.get("/api/places")
def suggest_places(q: str = ""):
    """Autocomplete: top places matching a prefix, WITH their state — so users
    pick 'Gorakhpur, Uttar Pradesh' and never hit spelling/ambiguity issues."""
    q = q.strip().lower()
    if len(q) < 2:
        return {"places": []}
    try:
        from .db import get_pool
        from .engine import IN_STATES
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT name, admin1, population FROM cities
                   WHERE lower(name) LIKE %s OR lower(asciiname) LIKE %s
                   ORDER BY population DESC NULLS LAST LIMIT 12;""",
                (q + "%", q + "%"),
            )
            out, seen = [], set()
            for name, admin1, _pop in cur.fetchall():
                state = IN_STATES.get(admin1, "")
                key = (name.lower(), state)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"name": name, "state": state})
                if len(out) >= 8:
                    break
        return {"places": out}
    except Exception as e:  # noqa: BLE001
        print("places suggest unavailable:", e)
        return {"places": []}


# Unified: /api/search is now an alias of /api/routes (same engine + seed
# fallback). Kept for compatibility with earlier scripts/benchmarks.
@app.get("/api/search")
def search_engine(
    from_: str = Query("", alias="from"),
    to: str = "",
    pref: str = "confirmed",
    date: str = "",
):
    return search_routes(from_, to, pref, date)
