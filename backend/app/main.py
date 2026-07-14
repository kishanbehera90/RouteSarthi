"""RouteSarthi backend — Phase B.

Step 0 (scaffold): serves the API contract from seed fixtures, proving the
contract end-to-end with a real server. Endpoints mirror
frontend/API_CONTRACT.md exactly. Real data + the cross-origin engine arrive
in Step 1.
"""
import json
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg.types.json import Json
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger("routesarthi")

# Query-param constraints reused across search endpoints. A place name is a
# short string; pref is a closed set; date is empty or ISO YYYY-MM-DD. FastAPI
# rejects anything outside these with a 422 before our code runs.
_PLACE_MAX = 120
_DATE_PATTERN = r"^(\d{4}-\d{2}-\d{2})?$"
Pref = Literal["confirmed", "cheapest", "fastest"]


class StrictModel(BaseModel):
    """Base for all request bodies: reject unknown fields outright (extra data
    is a red flag, not something to silently ignore) and strip surrounding
    whitespace on strings."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

from . import auth
from . import ratelimit
from . import delay_model
from . import seed
from . import engine
from . import graph
from .config import settings
from .db import get_pool


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
    if delay_model.is_stale():
        print(f"WARNING: delay_model.joblib is {delay_model.age_days()} days old "
              f"(recommended retrain cadence: {delay_model.STALE_AFTER_DAYS} days) — "
              f"run `python -m etl.train_delay_model` to refresh it.")
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
# once Phase C wiring begins. Extra prod origins (e.g. the deployed frontend)
# come from CORS_ORIGINS so this doesn't need another code change to deploy.
_extra_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", *_extra_origins],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# Rate-limit tiers (requests / window, per client IP). Tiered by endpoint type:
# STRICT on auth (brute-force / credential-stuffing — see the inline limits on
# the auth routes), MODERATE on public compute/DB endpoints, LOOSE on
# authenticated per-user actions. /health is intentionally UNLIMITED so the
# uptime keep-alive pinger never trips it.
RL_PUBLIC = ("public", 60, 60)          # 60/min  — cheap public reads
RL_SEARCH = ("search", 30, 60)          # 30/min  — the expensive engine search
RL_AUTOCOMPLETE = ("places", 120, 60)   # 120/min — /api/places fires per keystroke
RL_AUTHED = ("authed", 100, 60)         # 100/min — logged-in user actions
RL_RESET = ("reset", 10, 3600)          # 10/hr   — password-reset token redemption


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Last line of defence: any exception NOT already turned into an
    HTTPException (a raw DB error, a bug, a None deref) reaches here. Log the
    FULL error with traceback server-side for debugging, but return a GENERIC
    message to the client — never a stack trace, file path, SQL, or driver
    error. (FastAPI still handles HTTPException / 422 validation itself with
    their own safe, intentional messages; this only catches the unintended.)"""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500,
                        content={"detail": "Something went wrong on our end. Please try again."})


@app.get("/health")
def health():
    return {"status": "ok", "phase": "B", "step": 1, "graph": graph.stats(),
            "delayModel": {"loaded": delay_model.have_model(),
                           "ageDays": delay_model.age_days(),
                           "stale": delay_model.is_stale()}}


@app.get("/api/delay-model-info", dependencies=[Depends(ratelimit.limiter(*RL_PUBLIC))])
def delay_model_info():
    """Static metadata about the delay-prediction model — surfaced in the
    frontend's 'Predicted' tooltip so users can see what the number is
    actually based on (data through which date), not just that it's ML."""
    return delay_model.info() or {"loaded": False}


@app.get("/api/corridors", dependencies=[Depends(ratelimit.limiter(*RL_PUBLIC))])
def list_corridors():
    return seed.CORRIDORS


@app.get("/api/corridors/{corridor_id}", dependencies=[Depends(ratelimit.limiter(*RL_PUBLIC))])
def get_corridor(corridor_id: str, response: Response):
    corridor = seed.get_corridor(corridor_id)
    if not corridor:
        response.status_code = 404
        return None
    return {"corridor": corridor, "routes": seed.get_routes(corridor_id)}


@app.get("/api/routes", dependencies=[Depends(ratelimit.limiter(*RL_SEARCH))])
def search_routes(
    from_: str = Query("", alias="from", max_length=_PLACE_MAX),
    to: str = Query("", max_length=_PLACE_MAX),
    pref: Pref = "confirmed",
    date: str = Query("", pattern=_DATE_PATTERN),
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


@app.get("/api/routes/{route_id}", dependencies=[Depends(ratelimit.limiter(*RL_PUBLIC))])
def get_route(route_id: str, response: Response):
    route = engine.get_stored_route(route_id) or seed.find_route(route_id)
    if not route:
        response.status_code = 404
        return None
    return route


@app.get("/api/places", dependencies=[Depends(ratelimit.limiter(*RL_AUTOCOMPLETE))])
def suggest_places(q: str = Query("", max_length=80)):
    """Autocomplete: top places matching a prefix, WITH their state — so users
    pick 'Gorakhpur, Uttar Pradesh' and never hit spelling/ambiguity issues."""
    q = q.strip().lower()
    if len(q) < 2:
        return {"places": []}
    try:
        from .db import get_pool
        from .engine import IN_STATES, _alias
        qa = _alias(q)  # famous-place spelling (kanyakumari -> kanniyakumari)
        out, seen = [], set()

        def add(name, state):
            # Key on (name, state) so two same-named cities in different states
            # both surface (Gorakhpur UP vs Haryana) — that's the disambiguation.
            key = (name.lower(), state)
            if key not in seen:
                seen.add(key)
                out.append({"name": name, "state": state})

        # 1) Cities/towns first — this is a travel planner: show every place
        #    with its state (prefix match, then a trigram fuzzy fallback).
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT name, admin1 FROM cities
                   WHERE lower(name) LIKE %s OR lower(asciiname) LIKE %s
                   ORDER BY population DESC NULLS LAST LIMIT 10;""",
                (qa + "%", qa + "%"),
            )
            for name, admin1 in cur.fetchall():
                add(name, IN_STATES.get(admin1, ""))
            if len(out) < 8:
                cur.execute(
                    """SELECT name, admin1 FROM cities
                       WHERE similarity(lower(name), %s) > 0.45
                       ORDER BY similarity(lower(name), %s) DESC, population DESC NULLS LAST
                       LIMIT 6;""",
                    (qa, qa),
                )
                for name, admin1 in cur.fetchall():
                    add(name, IN_STATES.get(admin1, ""))
            # Station-towns the gazetteer misses (e.g. Ringas) — with real state,
            # so they read as places, not "railway stations".
            if len(out) < 8:
                cur.execute(
                    """SELECT name, state FROM stations
                       WHERE lower(name) LIKE %s AND num_trains > 0
                       ORDER BY num_trains DESC LIMIT 6;""",
                    (q + "%",),
                )
                for name, state in cur.fetchall():
                    add(name, state or "")
        return {"places": out[:8]}
    except Exception as e:  # noqa: BLE001
        print("places suggest unavailable:", e)
        return {"places": []}


# Unified: /api/search is now an alias of /api/routes (same engine + seed
# fallback). Kept for compatibility with earlier scripts/benchmarks.
@app.get("/api/search", dependencies=[Depends(ratelimit.limiter(*RL_SEARCH))])
def search_engine(
    from_: str = Query("", alias="from", max_length=_PLACE_MAX),
    to: str = Query("", max_length=_PLACE_MAX),
    pref: Pref = "confirmed",
    date: str = Query("", pattern=_DATE_PATTERN),
):
    return search_routes(from_, to, pref, date)


# --- Auth ---------------------------------------------------------------


def _valid_email(email: str) -> bool:
    # Loose sanity check, not full RFC822 validation — avoids adding
    # email-validator as a dependency for an MVP-scoped check.
    if "@" not in email or len(email) > 254:
        return False
    local, _, domain = email.rpartition("@")
    return bool(local) and "." in domain and not domain.startswith(".")


class SignupRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=72)
    name: str | None = Field(default=None, max_length=80)


class LoginRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=72)


class ForgotPasswordRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)


class ResetPasswordRequest(StrictModel):
    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(min_length=8, max_length=72)


def _token_response(user: dict):
    return {"token": auth.create_token(user["id"]), "user": user}


@app.post("/api/auth/signup")
def signup(body: SignupRequest, request: Request):
    # Cap account creation per IP so the endpoint can't be used to mass-create
    # accounts (each signup also triggers a bcrypt hash — CPU the pool shares).
    ratelimit.check(f"signup:ip:{ratelimit.client_ip(request)}", limit=5, window_s=3600)
    if not _valid_email(body.email):
        raise HTTPException(400, "Enter a valid email address")
    try:
        user = auth.signup(body.email, body.password, body.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _token_response(user)


@app.post("/api/auth/login")
def login(body: LoginRequest, request: Request):
    # Throttle by BOTH IP and email: the IP cap slows a single host hammering
    # many accounts (credential stuffing); the per-email cap slows a distributed
    # attack converging on one target account. Both are checked before the
    # bcrypt verify, so a flood never even reaches the hash.
    ip = ratelimit.client_ip(request)
    ratelimit.check(f"login:ip:{ip}", limit=15, window_s=300)
    ratelimit.check(f"login:email:{body.email.strip().lower()}", limit=8, window_s=300)
    try:
        user = auth.login(body.email, body.password)
    except ValueError as e:
        raise HTTPException(401, str(e))
    return _token_response(user)


@app.get("/api/auth/me")
def me(user: dict = Depends(auth.get_current_user)):
    return {"user": user}


@app.post("/api/auth/forgot-password")
def forgot_password(body: ForgotPasswordRequest, request: Request):
    # Per-IP cap on top of auth.py's per-email 2-min throttle: stops one host
    # spraying many addresses to fish out valid accounts / burn the email quota.
    ratelimit.check(f"forgot:ip:{ratelimit.client_ip(request)}", limit=10, window_s=3600)
    # Always 200 regardless of outcome — never confirm/deny an email exists.
    if _valid_email(body.email):
        raw_token = auth.create_reset_token(body.email)
        if raw_token:
            from . import email as email_mod
            link = f"{settings.frontend_url}/reset-password?token={raw_token}"
            email_mod.send_reset_email(body.email, link)
    return {"ok": True}


@app.post("/api/auth/reset-password")
def reset_password(body: ResetPasswordRequest, request: Request):
    # Strict: the token is a 32-byte secret, but cap redemption attempts per IP
    # anyway so the endpoint can't be hammered to brute-force tokens or as a
    # password-change oracle.
    ratelimit.check(f"reset:ip:{ratelimit.client_ip(request)}", limit=10, window_s=3600)
    try:
        auth.redeem_reset_token(body.token, body.new_password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


# --- Saved trips (per-user) ----------------------------------------------


class SaveTripRequest(StrictModel):
    route: dict

    @field_validator("route")
    @classmethod
    def _route_is_sane(cls, v: dict) -> dict:
        # A route is engine-generated, but this endpoint takes it back from the
        # client, so treat it as untrusted: require a string id, and cap the
        # serialized size so a caller can't stuff arbitrarily large JSON into
        # the DB (a cheap storage-DoS vector).
        rid = v.get("id")
        if not rid or not isinstance(rid, str) or len(rid) > 200:
            raise ValueError("route.id is required and must be a short string")
        if len(json.dumps(v)) > 64_000:
            raise ValueError("route payload is too large")
        return v


@app.get("/api/saved-trips", dependencies=[Depends(ratelimit.limiter(*RL_AUTHED))])
def list_saved_trips(user: dict = Depends(auth.get_current_user)):
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT route_id, route_json, saved_at FROM saved_trips
               WHERE user_id=%s ORDER BY saved_at DESC;""",
            (user["id"],),
        )
        rows = cur.fetchall()
    return {"trips": [{"routeId": r[0], "route": r[1], "savedAt": r[2].isoformat()} for r in rows]}


@app.post("/api/saved-trips", dependencies=[Depends(ratelimit.limiter(*RL_AUTHED))])
def save_trip(body: SaveTripRequest, user: dict = Depends(auth.get_current_user)):
    route_id = body.route.get("id")
    if not route_id or not isinstance(route_id, str):
        raise HTTPException(400, "route.id is required")
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO saved_trips (user_id, route_id, route_json)
               VALUES (%s,%s,%s)
               ON CONFLICT (user_id, route_id)
               DO UPDATE SET route_json=EXCLUDED.route_json, saved_at=now();""",
            (user["id"], route_id, Json(body.route)),
        )
        conn.commit()
    return {"ok": True}


@app.delete("/api/saved-trips/{route_id}", dependencies=[Depends(ratelimit.limiter(*RL_AUTHED))])
def delete_saved_trip(route_id: str, user: dict = Depends(auth.get_current_user)):
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM saved_trips WHERE user_id=%s AND route_id=%s;",
            (user["id"], route_id),
        )
        conn.commit()
    return {"ok": True}


# --- Recent searches (per-user) -------------------------------------------

RECENT_SEARCHES_LIMIT = 8


class RecentSearchRequest(StrictModel):
    from_: str = Field(alias="from", min_length=1, max_length=_PLACE_MAX)
    to: str = Field(min_length=1, max_length=_PLACE_MAX)
    date: str = Field(default="", pattern=_DATE_PATTERN)
    pref: Pref = "confirmed"


@app.get("/api/recent-searches", dependencies=[Depends(ratelimit.limiter(*RL_AUTHED))])
def list_recent_searches(user: dict = Depends(auth.get_current_user)):
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT from_place, to_place, travel_date, pref, searched_at
               FROM recent_searches WHERE user_id=%s
               ORDER BY searched_at DESC LIMIT %s;""",
            (user["id"], RECENT_SEARCHES_LIMIT),
        )
        rows = cur.fetchall()
    return {"searches": [
        {"from": r[0], "to": r[1], "date": r[2] or "", "pref": r[3], "searchedAt": r[4].isoformat()}
        for r in rows
    ]}


@app.post("/api/recent-searches", dependencies=[Depends(ratelimit.limiter(*RL_AUTHED))])
def record_search(body: RecentSearchRequest, user: dict = Depends(auth.get_current_user)):
    from_place, to_place = body.from_.strip(), body.to.strip()
    if not from_place or not to_place:
        raise HTTPException(400, "from and to are required")
    from_key, to_key = from_place.lower(), to_place.lower()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO recent_searches (user_id, from_key, to_key, from_place, to_place, travel_date, pref)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (user_id, from_key, to_key)
               DO UPDATE SET from_place=EXCLUDED.from_place, to_place=EXCLUDED.to_place,
                             travel_date=EXCLUDED.travel_date, pref=EXCLUDED.pref, searched_at=now();""",
            (user["id"], from_key, to_key, from_place, to_place, body.date or None, body.pref),
        )
        # keep only the most recent RECENT_SEARCHES_LIMIT rows per user
        cur.execute(
            """DELETE FROM recent_searches WHERE user_id=%s AND id NOT IN (
                   SELECT id FROM recent_searches WHERE user_id=%s
                   ORDER BY searched_at DESC LIMIT %s
               );""",
            (user["id"], user["id"], RECENT_SEARCHES_LIMIT),
        )
        conn.commit()
    return {"ok": True}
