"""Cross-origin routing engine (Step 1).

Geocodes any two places in India, finds candidate railheads near each (PostGIS),
then routes between them using the in-memory schedule graph (see graph.py) —
single-train and one-transfer journeys — adds first/last-mile road legs, scores
across time / cost / train-density / transfers, and returns ranked routes in the
API-contract shape.

NOT yet modelled (later steps, no data yet): live delays (Step 3) and seat /
waitlist confirmation (Step 4). `reliability` here is a transparent *connectivity*
heuristic (network resilience + directness), clearly a placeholder until then.
"""
from . import graph
from .db import get_pool

# --- tunables -------------------------------------------------------------
ORIGIN_RADIUS_KM = 200
DEST_RADIUS_KM = 60
ROAD_KMPH = 35
ROAD_FARE_PER_KM = 3.0
RAIL_FARE_PER_KM = 0.7
RAIL_FARE_MIN = 120
RAIL_KMPH_PROXY = 50      # turn in-train minutes into a rough distance for fare

_CACHE = {}
_CACHE_MAX = 1000
ROUTE_STORE = {}          # route id -> route dict, so /api/routes/:id resolves engine routes
_ROUTE_STORE_MAX = 8000


def get_stored_route(route_id):
    return ROUTE_STORE.get(route_id)


def _hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def connection_safety(buffer_mins):
    """P(make the transfer) as a function of buffer alone — a transparent prior
    until Step 3 replaces it with per-train historical delay distributions.
    Smooth ramp: ~0 below the min buffer, ~70% at 60min, ~90% at 120min,
    ~97% by 180min."""
    if buffer_mins is None or buffer_mins < graph.CONN_MIN_BUFFER:
        return None
    import math
    # logistic centred ~55 min, gentle slope
    pct = 100 / (1 + math.exp(-(buffer_mins - 55) / 28))
    return max(40, min(97, round(pct)))


_GEOCODE_CACHE = {}


def _geocode(cur, name):
    k = name.strip().lower()
    if k in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[k]
    cur.execute(
        """SELECT name, lat, lng FROM cities
           WHERE lower(asciiname)=lower(%s) OR lower(name)=lower(%s)
           ORDER BY population DESC NULLS LAST LIMIT 1;""",
        (name, name),
    )
    row = cur.fetchone()
    if len(_GEOCODE_CACHE) < 5000:
        _GEOCODE_CACHE[k] = row
    return row


def _fare_road(km):
    return max(20, round(km * ROAD_FARE_PER_KM))


def _fare_rail(in_train_min):
    rail_km = in_train_min / 60 * RAIL_KMPH_PROXY
    return max(RAIL_FARE_MIN, round(rail_km * RAIL_FARE_PER_KM))


def _road_leg(idx, frm, to, km, fromc=None, toc=None):
    return {"id": idx, "mode": "cab", "name": f"{frm} → {to}", "from": frm, "to": to,
            "durationMins": round(km / ROAD_KMPH * 60), "fareInr": _fare_road(km),
            "confirmation": "confirmed", "fromCoords": fromc, "toCoords": toc}


def _coord(node):
    """[lng, lat] for a railhead dict (b/a) — None-safe."""
    if node.get("lng") is None or node.get("lat") is None:
        return None
    return [node["lng"], node["lat"]]


def _hub_coord(code):
    return graph.STATION_COORD.get(code)


def search(from_place, to_place, pref="confirmed"):
    key = (from_place.strip().lower(), to_place.strip().lower(), pref)
    if key in _CACHE:
        return _CACHE[key]

    graph.load()
    with get_pool().connection() as conn, conn.cursor() as cur:
        o = _geocode(cur, from_place)
        d = _geocode(cur, to_place)
    if not o or not d:
        return {"corridor": None, "routes": [], "error": "place_not_found"}

    # nearest-railhead is now in-memory (no DB round-trip)
    o_heads = {}
    for radius in (ORIGIN_RADIUS_KM, 400, 600):
        o_heads = graph.nearest_railheads(o[1], o[2], radius)
        if o_heads:
            break
    d_heads = graph.nearest_railheads(d[1], d[2], DEST_RADIUS_KM) or graph.nearest_railheads(d[1], d[2], 150)

    if not o_heads or not d_heads:
        result = {"corridor": _corridor(o, d), "routes": []}
        _store(key, result)
        return result

    ocoord, dcoord = [o[2], o[1]], [d[2], d[1]]
    routes = []

    # --- single-train candidates (best per train) ---
    best_by_train = {}
    for c in graph.single_train(o_heads, d_heads):
        b, a = o_heads[c["board"]], d_heads[c["alight"]]
        access = b["km"] + a["km"]
        if c["train"] not in best_by_train or access < best_by_train[c["train"]][0]:
            best_by_train[c["train"]] = (access, c)
    for access, c in best_by_train.values():
        routes.append(_direct_route(from_place, to_place, o_heads[c["board"]], d_heads[c["alight"]], c, ocoord, dcoord))

    # --- one-transfer cross-origin (when few/no through trains) ---
    if len(routes) < 3:
        for j in graph.one_transfer(o_heads, d_heads):
            routes.append(_transfer_route(from_place, to_place, o_heads[j["board"]], d_heads[j["alight"]], j, ocoord, dcoord))

    routes = _diversify(_rank(routes, pref))[:6]
    if len(ROUTE_STORE) > _ROUTE_STORE_MAX:
        ROUTE_STORE.clear()
    for r in routes:
        ROUTE_STORE[r["id"]] = r
    result = {"corridor": _corridor(o, d), "routes": routes}
    _store(key, result)
    return result


def _diversify(ranked):
    """Avoid showing many near-identical options through the same hub/first-train.
    Keep at most 2 per hub and 1 per (hub, first-train), preserving rank order;
    backfill from the rest if we end up short."""
    kept, per_hub, per_pair, overflow = [], {}, set(), []
    for r in ranked:
        hub = (r.get("hub") or {}).get("code") or "_direct"
        first_train = r["legs"][0]["id"].split("-")[0] if r["legs"] else ""
        pair = (hub, first_train)
        if per_hub.get(hub, 0) < 2 and pair not in per_pair:
            kept.append(r)
            per_hub[hub] = per_hub.get(hub, 0) + 1
            per_pair.add(pair)
        else:
            overflow.append(r)
    return kept + overflow


def _direct_route(frm, to, b, a, c, ocoord, dcoord):
    legs = []
    first_km, last_km = b["km"], a["km"]
    bc, ac = _coord(b), _coord(a)
    if first_km > 2:
        legs.append(_road_leg(f"{c['train']}-fm", frm, b["name"], first_km, ocoord, bc))
        legs.append({"id": f"{c['train']}-c1", "mode": "connection", "connectionSafetyPct": None,
                     "bufferMins": None, "note": f"~{round(first_km)} km road to {b['name']}"})
    legs.append({"id": f"{c['train']}-tr", "mode": "train", "name": f"{c['train']} {c['name'] or ''}".strip(),
                 "from": b["name"], "to": a["name"], "depart": _hhmm(c["dep"]), "arrive": _hhmm(c["arr"]),
                 "durationMins": c["in_train"], "fareInr": _fare_rail(c["in_train"]), "confirmation": "confirmed",
                 "fromCoords": bc, "toCoords": ac})
    if last_km > 2:
        legs.append({"id": f"{c['train']}-c2", "mode": "connection", "connectionSafetyPct": None,
                     "bufferMins": None, "note": f"~{round(last_km)} km road to {to}"})
        legs.append(_road_leg(f"{c['train']}-lm", a["name"], to, last_km, ac, dcoord))

    is_cross = first_km > 20
    return {
        "id": f"{c['train']}-{b['code']}-{a['code']}",
        "type": "cross-origin" if is_cross else "direct",
        "totalTimeMins": sum(l.get("durationMins", 0) for l in legs),
        "totalFareInr": sum(l.get("fareInr", 0) for l in legs),
        "reliability": max(30, min(95, round(50 + b["trains"] / 4 - first_km / 8))),
        "confirmation": "confirmed", "confirmationPct": None, "clearProbabilityPct": None,
        "hub": {"code": b["code"], "name": b["name"]} if is_cross else None,
        "boardTrains": b["trains"], "transfers": 0,
        "why": (f"{b['name']} ({round(first_km)} km away) is a far better-connected railhead "
                f"with {b['trains']} trains/day — boarding there beats the limited local options."
                if is_cross else
                f"Direct from {b['name']} ({b['trains']} trains/day serve this station)."),
        "planB": None, "legs": legs,
    }


def _transfer_route(frm, to, b, a, j, ocoord, dcoord):
    legs = []
    first_km, last_km = b["km"], a["km"]
    bc, ac, hc = _coord(b), _coord(a), _hub_coord(j["hub"])
    if first_km > 2:
        legs.append(_road_leg(f"{j['t1']}-fm", frm, b["name"], first_km, ocoord, bc))
        legs.append({"id": f"{j['t1']}-c0", "mode": "connection", "connectionSafetyPct": None,
                     "bufferMins": None, "note": f"~{round(first_km)} km road to {b['name']}"})
    legs.append({"id": f"{j['t1']}-tr", "mode": "train", "name": f"{j['t1']} {j['t1name'] or ''}".strip(),
                 "from": b["name"], "to": j["hub"], "depart": _hhmm(j["dep1"]), "arrive": None,
                 "durationMins": j["it1"], "fareInr": _fare_rail(j["it1"]), "confirmation": "confirmed",
                 "fromCoords": bc, "toCoords": hc})
    safety = connection_safety(j["wait"])
    legs.append({"id": f"{j['t1']}-{j['t2']}-cx", "mode": "connection", "connectionSafetyPct": safety,
                 "bufferMins": j["wait"],
                 "note": f"Change at {j['hub']} ({j['hub_trains']} trains/day) · {j['wait']} min connection"})
    legs.append({"id": f"{j['t2']}-tr", "mode": "train", "name": f"{j['t2']} {j['t2name'] or ''}".strip(),
                 "from": j["hub"], "to": a["name"], "depart": _hhmm(j["dep2"]), "arrive": _hhmm(j["arr2"]),
                 "durationMins": j["it2"], "fareInr": _fare_rail(j["it2"]), "confirmation": "confirmed",
                 "fromCoords": hc, "toCoords": ac})
    if last_km > 2:
        legs.append({"id": f"{j['t2']}-c2", "mode": "connection", "connectionSafetyPct": None,
                     "bufferMins": None, "note": f"~{round(last_km)} km road to {to}"})
        legs.append(_road_leg(f"{j['t2']}-lm", a["name"], to, last_km, ac, dcoord))

    base = 48 + j["hub_trains"] / 5 - first_km / 10
    reliability = max(30, min(92, round(base * ((safety or 60) / 100) + (safety or 60) * 0.15)))
    return {
        "id": f"{j['t1']}-{j['hub']}-{j['t2']}",
        "type": "cross-origin",
        "totalTimeMins": sum(l.get("durationMins", 0) for l in legs) + j["wait"],
        "totalFareInr": sum(l.get("fareInr", 0) for l in legs),
        "reliability": reliability,
        "connectionSafetyPct": safety,
        "confirmation": "confirmed", "confirmationPct": None, "clearProbabilityPct": None,
        "hub": {"code": j["hub"], "name": j["hub"]}, "boardTrains": j["hub_trains"], "transfers": 1,
        "why": (f"No through train — but {j['hub']} ({j['hub_trains']} trains/day) links the two "
                f"sides with a {j['wait']}-min connection."),
        "planB": None, "legs": legs,
    }


def _rank(routes, pref):
    if pref == "cheapest":
        return sorted(routes, key=lambda r: r["totalFareInr"])
    if pref == "fastest":
        return sorted(routes, key=lambda r: r["totalTimeMins"])
    return sorted(routes, key=lambda r: (r["transfers"], -r["reliability"], r["totalTimeMins"]))


def _corridor(o, d):
    return {"id": f"{o[0].lower()}-{d[0].lower()}",
            "from": {"code": "", "name": o[0]}, "to": {"code": "", "name": d[0]},
            "tagline": f"Live options from {o[0]} to {d[0]}, computed from the rail network."}


def _store(key, result):
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = result
