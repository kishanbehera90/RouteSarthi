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
):
    # Live engine over real data. Falls back to seed only if the engine can't
    # geocode the place (so the 3 mock corridors still demo even pre-load).
    result = engine.search(from_, to, pref)
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


# --- Step 1: live cross-origin engine (real data) ------------------------
# Returns routes computed from the rail network for ANY two places in India.
# Unifies with /api/routes in Phase C; kept separate now so the verified seed
# contract layer stays untouched while the engine matures.
@app.get("/api/search")
def search_engine(
    from_: str = Query("", alias="from"),
    to: str = "",
    pref: str = "confirmed",
):
    return engine.search(from_, to, pref)
