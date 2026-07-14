"""Real road-routing for road legs (first/last-mile access + the standalone
direct-road option). A fallback CHAIN, tried in order per call; each step is
used only if the previous is absent or its circuit breaker is open:

  1. Self-hosted OSRM (`settings.osrm_url`) — no per-request limits, ~1-5ms
     replies (in-RAM routing), preferred when available. Runs on a persistent
     VM (e.g. Oracle Cloud Always Free ARM) — see backend/README.md's OSRM
     setup runbook. Set OSRM_URL to turn it on; nothing else changes.
  2. OpenRouteService (`settings.ors_api_key`) — hosted, free tier (~2000/day,
     40/min).
  3. Geoapify (`settings.geoapify_api_key`) — hosted, free tier (~3000/day). A
     SECOND independent free quota: when ORS hits its daily/minute limit its
     breaker opens and this call falls straight through to Geoapify (and vice
     versa is easy to reorder), instead of dropping to the haversine estimate.
  4. None reachable -> `route()` returns None and the caller (engine.py) falls
     back to the haversine×1.3 estimate.

Each backend has its OWN circuit breaker, so one being down/limited instantly
skips to the next (rather than one shared breaker disabling all). Note that a
rate-limit (HTTP 429) is treated like any failure: it opens that backend's
breaker for the cooldown, so subsequent legs in the same search skip it and use
the next provider. This module never raises.
"""
import time

import httpx

from .config import settings

_TIMEOUT = 1.5  # seconds — a slow/down routing service must never stall a search

# Per-backend circuit breaker: a single search can have a couple dozen road
# legs, each a separate call. Measured against a refused connection, even a
# "fails immediately" case can take most of a timeout window on some networks
# (~2.9s against a dead port on Windows) — without this, one search with a
# backend down would pay that cost once PER LEG, and every subsequent search
# would too. One failure disables THAT backend for a short cooldown (so one
# provider being down/limited doesn't also mute the others); retried after.
_FAIL_COOLDOWN_SECONDS = 30
_disabled_until = {"osrm": 0.0, "ors": 0.0, "geoapify": 0.0}

# A single search computes several candidate routes that often share the same
# first/last-mile city pair (e.g. every SAMBALPUR-hub route needs the same
# "MANMAD JN -> Nashik" leg) — without this, each one fires its own network
# call for an identical coordinate pair, burning through ORS's free-tier rate
# limit on pure duplicates. Only successful lookups are cached (a real road
# distance between two fixed points doesn't change); failures still go
# through the circuit breaker above so a transient outage can recover.
_route_cache = {}


def have_road_api():
    return bool(settings.osrm_url or settings.ors_api_key or settings.geoapify_api_key)


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


def _geoapify_route(lat1, lng1, lat2, lng2):
    url = "https://api.geoapify.com/v1/routing"
    r = httpx.get(
        url,
        params={"waypoints": f"{lat1},{lng1}|{lat2},{lng2}", "mode": "drive",
                "apiKey": settings.geoapify_api_key},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    features = data.get("features") or []
    if not features:
        return None
    props = features[0].get("properties") or {}
    dist, secs = props.get("distance"), props.get("time")   # metres, seconds
    if dist is None or secs is None:
        return None
    return {"km": dist / 1000, "mins": secs / 60}


def _try(name, fn, lat1, lng1, lat2, lng2):
    """Call one backend behind its own circuit breaker. Returns a result dict,
    or None if the backend is in cooldown, errors, or finds no route. A raised
    error opens THIS backend's breaker for the cooldown window (so the chain
    can still fall through to the next backend on this very call)."""
    if time.monotonic() < _disabled_until[name]:
        return None
    try:
        return fn(lat1, lng1, lat2, lng2)
    except Exception as e:  # noqa: BLE001 — a routing hiccup must never break a search
        print(f"road routing via {name} failed (trying next fallback):", e)
        _disabled_until[name] = time.monotonic() + _FAIL_COOLDOWN_SECONDS
        return None


def route(lat1, lng1, lat2, lng2):
    """Real road (km, mins) between two points via OSRM -> ORS -> Geoapify, or
    None if nothing is configured / all are unreachable / no route exists
    (caller then uses the haversine estimate). Never raises."""
    if not have_road_api():
        return None
    key = (round(lat1, 4), round(lng1, 4), round(lat2, 4), round(lng2, 4))
    if key in _route_cache:
        return _route_cache[key]

    result = None
    if settings.osrm_url:
        result = _try("osrm", _osrm_route, lat1, lng1, lat2, lng2)
    if result is None and settings.ors_api_key:
        result = _try("ors", _ors_route, lat1, lng1, lat2, lng2)
    if result is None and settings.geoapify_api_key:
        result = _try("geoapify", _geoapify_route, lat1, lng1, lat2, lng2)

    if result is not None:
        _route_cache[key] = result
    return result
