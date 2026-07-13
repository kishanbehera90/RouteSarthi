"""Real road-routing for road legs (first/last-mile access + the standalone
direct-road option). Two backends, tried in priority order:

  1. Self-hosted OSRM (`settings.osrm_url`) — no per-request limits, but needs
     a persistent VM (Docker isn't available in this dev environment or on a
     typical Windows machine) — see backend/README.md's OSRM setup runbook.
     Kept as a switch-on-later option: set OSRM_URL and nothing else changes.
  2. OpenRouteService (`settings.ors_api_key`) — a hosted API, free tier
     (2000 req/day), signup takes minutes, no VM/Docker at all. The default
     path today.

Both are genuinely OPTIONAL: with neither configured, or if either is
unreachable, `route()` returns None and callers (engine.py) fall back to the
haversine-based estimate that existed before real road-routing. This module
never raises.
"""
import time

import httpx

from .config import settings

_TIMEOUT = 1.5  # seconds — a slow/down routing service must never stall a search

# Circuit breaker: a single search can have a couple dozen road legs, each a
# separate call. Measured against a refused connection: even a "fails
# immediately" case can take most of a timeout window on some networks (~2.9s
# against a dead port on Windows) — without this, one search with the routing
# service down would pay that cost once PER LEG, and every subsequent search
# would too. One failure disables real routing for a short cooldown; it's
# tried again after the cooldown expires (auto-recovers).
_FAIL_COOLDOWN_SECONDS = 30
_disabled_until = 0.0

# A single search computes several candidate routes that often share the same
# first/last-mile city pair (e.g. every SAMBALPUR-hub route needs the same
# "MANMAD JN -> Nashik" leg) — without this, each one fires its own network
# call for an identical coordinate pair, burning through ORS's free-tier rate
# limit on pure duplicates. Only successful lookups are cached (a real road
# distance between two fixed points doesn't change); failures still go
# through the circuit breaker above so a transient outage can recover.
_route_cache = {}


def have_road_api():
    return bool(settings.osrm_url or settings.ors_api_key)


def _osrm_route(lat1, lng1, lat2, lng2):
    url = f"{settings.osrm_url.rstrip('/')}/route/v1/driving/{lng1},{lat1};{lng2},{lat2}"
    r = httpx.get(url, params={"overview": "false"}, timeout=_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        return None
    leg = data["routes"][0]
    return {"km": leg["distance"] / 1000, "mins": leg["duration"] / 60}


def _ors_route(lat1, lng1, lat2, lng2):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    r = httpx.get(
        url,
        params={"start": f"{lng1},{lat1}", "end": f"{lng2},{lat2}"},
        headers={"Authorization": settings.ors_api_key},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    features = data.get("features") or []
    if not features:
        return None
    summary = features[0]["properties"]["summary"]
    return {"km": summary["distance"] / 1000, "mins": summary["duration"] / 60}


def route(lat1, lng1, lat2, lng2):
    """Real road (km, mins) between two points, or None on ANY failure
    (nothing configured, timeout, connection error, malformed/unrouteable
    response, or still inside the post-failure cooldown)."""
    global _disabled_until
    if not settings.osrm_url and not settings.ors_api_key:
        return None
    key = (round(lat1, 4), round(lng1, 4), round(lat2, 4), round(lng2, 4))
    if key in _route_cache:
        return _route_cache[key]
    if time.monotonic() < _disabled_until:
        return None
    try:
        result = _osrm_route(lat1, lng1, lat2, lng2) if settings.osrm_url else _ors_route(lat1, lng1, lat2, lng2)
    except Exception as e:  # noqa: BLE001 — a routing-service hiccup must never break a search
        print("road routing failed (falling back to haversine):", e)
        _disabled_until = time.monotonic() + _FAIL_COOLDOWN_SECONDS
        return None
    if result is not None:
        _route_cache[key] = result
    return result
