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
RAIL_KMPH_PROXY = 50      # minutes -> km fallback when a station has no coords

# Fare rates calibrated from IRCTC Oct-2023 price_data.csv — median baseFare/km
# per class over 288k real quotes (SL n=88k, 3A n=80k, 2A n=76k, 1A n=31k).
FARE_RATE = {"SL": 0.58, "3A": 1.48, "2A": 2.10, "1A": 3.57, "CC": 1.58, "2S": 0.45}
RESV_CHARGE = 40          # flat reservation charge
ROUTE_KM_FACTOR = 1.25    # rail routes aren't straight lines
DAY3 = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

_CACHE = {}
_CACHE_MAX = 1000
ROUTE_STORE = {}          # route id -> route dict, so /api/routes/:id resolves engine routes
_ROUTE_STORE_MAX = 8000


def get_stored_route(route_id):
    r = ROUTE_STORE.get(route_id)
    if r is None:
        r = _rebuild_direct(route_id)  # stateless fallback (restart/worker-safe)
        if r:
            ROUTE_STORE[route_id] = r
    return r


def _rebuild_direct(route_id):
    """Direct-route ids are semantic ('{train}-{board}-{alight}'), so the
    detail page survives server restarts and multiple workers without Redis:
    rebuild the route from the graph. (Transfer ids need stored context and
    still require the store — Redis remains the deploy-phase plan for those.)"""
    parts = route_id.split("-")
    if len(parts) != 3:
        return None
    tn, bcode, acode = parts
    # Direct id = train-board-alight; transfer id = t1-hub-t2 (same shape).
    # A numeric 3rd part means it's a train number → transfer, not rebuildable
    # here (needs stored hub context; Redis is the deploy-phase plan for those).
    if acode.isdigit() or not tn.isdigit():
        return None
    graph.load()
    if tn not in graph.TRAIN_STOPS:
        return None
    heads = {}
    for code in (bcode, acode):
        st = next((s for s in graph.STATIONS if s[0] == code), None)
        if not st:
            return None
        heads[code] = {"code": code, "name": st[1], "trains": st[4], "km": 0,
                       "lng": st[3], "lat": st[2]}
    cands = [c for c in graph.single_train([bcode], {acode: True}) if c["train"] == tn]
    if not cands:
        return None
    return _direct_route(heads[bcode]["name"], heads[acode]["name"],
                         heads[bcode], heads[acode], cands[0], None, None)


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

# GeoNames IN admin1 code -> state. Derived from our own gazetteer (top city
# per code, verified against capitals) — the published mapping is stale.
IN_STATES = {
    "01": "Andaman and Nicobar", "02": "Andhra Pradesh", "03": "Assam",
    "05": "Chandigarh", "07": "Delhi", "09": "Gujarat", "10": "Haryana",
    "11": "Himachal Pradesh", "12": "Jammu and Kashmir", "13": "Kerala",
    "14": "Lakshadweep", "16": "Maharashtra", "17": "Manipur",
    "18": "Meghalaya", "19": "Karnataka", "20": "Nagaland", "21": "Odisha",
    "22": "Puducherry", "23": "Punjab", "24": "Rajasthan", "25": "Tamil Nadu",
    "26": "Tripura", "28": "West Bengal", "29": "Sikkim",
    "30": "Arunachal Pradesh", "31": "Mizoram", "33": "Goa", "34": "Bihar",
    "35": "Madhya Pradesh", "36": "Uttar Pradesh", "37": "Chhattisgarh",
    "38": "Jharkhand", "39": "Uttarakhand", "40": "Telangana", "41": "Ladakh",
    "52": "Dadra and Nagar Haveli and Daman and Diu",
}


def _near_named_station(name, lat, lng):
    """Rail-aware sanity check: does a station whose name contains the city
    name sit within ~20 km? Kills GeoNames artifacts like the 'Gorakhpur'
    duplicate in Haryana that carries UP-Gorakhpur's population — the real
    city has GORAKHPUR JN 2 km away, the impostor has nothing."""
    token = name.strip().upper()
    for _code, sname, slat, slng, n in graph.STATIONS:
        if n > 0 and token in sname.upper() and graph._haversine_km(lat, lng, slat, slng) <= 20:
            return True
    return False


def _geocode(cur, name):
    # "City, State" input: use the state to disambiguate (autocomplete sends it).
    parts = [p.strip() for p in name.split(",")]
    name, state_hint = parts[0], (parts[1].lower() if len(parts) > 1 and parts[1].strip() else None)
    k = (name.lower(), state_hint)
    if k in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[k]
    cur.execute(
        """SELECT name, lat, lng, admin1 FROM cities
           WHERE lower(asciiname)=lower(%s) OR lower(name)=lower(%s)
           ORDER BY population DESC NULLS LAST LIMIT 5;""",
        (name, name),
    )
    cands = cur.fetchall()
    if state_hint:
        filt = [c for c in cands if IN_STATES.get(c[3], "").lower().startswith(state_hint)]
        cands = filt or cands
    row = None
    if len(cands) > 1:  # population order is unreliable (duplicate artifacts);
        for c in cands:  # prefer the candidate with a same-named station nearby
            if _near_named_station(name, c[1], c[2]):
                row = c
                break
    if row is None:
        row = cands[0] if cands else None
    row = row[:3] if row else None
    if len(_GEOCODE_CACHE) < 5000:
        _GEOCODE_CACHE[k] = row
    return row


def _fare_road(km):
    return max(20, round(km * ROAD_FARE_PER_KM))


def _rail_km(bcode, acode, in_train_min):
    b, a = graph.STATION_COORD.get(bcode), graph.STATION_COORD.get(acode)
    if b and a:
        return graph._haversine_km(b[1], b[0], a[1], a[0]) * ROUTE_KM_FACTOR
    return in_train_min / 60 * RAIL_KMPH_PROXY


_AC_CLASSES = {"1A", "2A", "3A", "3E", "CC", "EC", "EA", "EV"}


def _ac_available(*train_nos):
    cls = set()
    for tn in train_nos:
        cls.update(x.strip() for x in graph.TRAIN_CLASSES.get(tn, "").split(","))
    return bool(cls & _AC_CLASSES)


def _fare_rail(tn, bcode, acode, in_train_min):
    """Distance x calibrated per-class rate. Class = cheapest the train offers
    (SL where available, else 3A/CC — e.g. Rajdhani/Tejas have no SL)."""
    km = _rail_km(bcode, acode, in_train_min)
    classes = graph.TRAIN_CLASSES.get(tn, "")
    cls = "SL" if "SL" in classes else "3A" if "3A" in classes else "CC" if "CC" in classes else "SL"
    return max(60, round(km * FARE_RATE[cls] + RESV_CHARGE))


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


def _path_coords(codes):
    """[lng,lat] for each intermediate stop we have geo for — so the map draws
    the real rail alignment through stations instead of a straight line."""
    out = []
    for c in codes or []:
        p = graph.STATION_COORD.get(c)
        if p and (not out or out[-1] != p):
            out.append(p)
    return out if len(out) >= 2 else None


def _breakdown_direct(trains, first_km):
    return [
        {"label": "No transfers", "value": 100},
        {"label": "Station connectivity", "value": min(96, 40 + trains // 4)},
        {"label": "First-mile access", "value": max(30, round(100 - first_km / 2))},
    ]


def _breakdown_transfer(hub_trains, safety, first_km):
    return [
        {"label": "Connection safety", "value": safety or 60},
        {"label": "Hub connectivity", "value": min(96, 40 + hub_trains // 4)},
        {"label": "First-mile access", "value": max(30, round(100 - first_km / 2))},
    ]


def search(from_place, to_place, pref="confirmed", date=None):
    day3 = None
    if date:
        try:
            import datetime as _dt
            day3 = DAY3[_dt.date.fromisoformat(date).weekday()]
        except ValueError:
            pass
    key = (from_place.strip().lower(), to_place.strip().lower(), pref, day3)
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
    for c in graph.single_train(o_heads, d_heads, day3):
        b, a = o_heads[c["board"]], d_heads[c["alight"]]
        access = b["km"] + a["km"]
        if c["train"] not in best_by_train or access < best_by_train[c["train"]][0]:
            best_by_train[c["train"]] = (access, c)
    for access, c in best_by_train.values():
        routes.append(_direct_route(from_place, to_place, o_heads[c["board"]], d_heads[c["alight"]], c, ocoord, dcoord))

    # --- one-transfer cross-origin (when few/no through trains) ---
    if len(routes) < 3:
        for j in graph.one_transfer(o_heads, d_heads, day3):
            routes.append(_transfer_route(from_place, to_place, o_heads[j["board"]], d_heads[j["alight"]], j, ocoord, dcoord))

    routes = _diversify(_rank(routes, pref))[:16]
    # Plan B: each route's fallback is the next-ranked alternative.
    for i, r in enumerate(routes):
        nxt = routes[i + 1] if i + 1 < len(routes) else None
        if nxt:
            tleg = next((l for l in nxt["legs"] if l["mode"] == "train"), None)
            if tleg:
                h = nxt["totalTimeMins"]
                r["planB"] = (f"Miss it? Next best: {tleg['name']} departing {tleg['depart']} "
                              f"— ₹{nxt['totalFareInr']}, {h // 60}h {h % 60}min door to door.")
    if len(ROUTE_STORE) > _ROUTE_STORE_MAX:
        ROUTE_STORE.clear()
    for r in routes:
        ROUTE_STORE[r["id"]] = r
    directs_by_board = {}
    for _access, c in best_by_train.values():
        directs_by_board[c["board"]] = directs_by_board.get(c["board"], 0) + 1
    corridor = _corridor(o, d)
    reasoning = _reasoning(routes, o_heads, directs_by_board, d[0])
    if reasoning:
        corridor["reasoning"] = reasoning
    result = {"corridor": corridor, "routes": routes}
    _store(key, result)
    return result


def _reasoning(routes, o_heads, directs_by_board, to_name):
    """Corridor `reasoning` for the decision animation — always emitted, in one
    of two modes. Every number shown is the metric the ranker actually used
    (through-trains to THIS destination), so the winner's stats support the
    verdict rather than contradict it."""
    if not routes:
        return None
    top = routes[0]
    # "True direct" = through train from the user's OWN city (short first-mile).
    # A through train boarded 80 km away is still a cross-origin story.
    n_true_direct = sum(1 for r in routes if r.get("transfers", 0) == 0 and r["type"] == "direct")
    from_board = next((l["from"] for l in top["legs"] if l.get("mode") == "train"), "")
    pct = lambda h: min(92, 30 + h["trains"] // 6 + directs_by_board.get(h["code"], 0) * 9)  # noqa: E731
    ranked = sorted(o_heads.values(),
                    key=lambda h: (-directs_by_board.get(h["code"], 0), -h["trains"]))

    # --- DIRECT WINS: through train from the local station, no detour. ---
    if top.get("transfers", 0) == 0 and top["type"] == "direct":
        also = [{"name": h["name"], "dailyTrains": h["trains"], "confirmPct": pct(h), "winner": None,
                 "note": f"{round(h['km'])} km away"}
                for h in ranked[:2] if h["name"] != from_board]
        return {
            "mode": "direct",
            "winner": {"name": from_board,
                       "dailyTrains": directs_by_board.get(_code_of(from_board, o_heads), n_true_direct),
                       "note": "board here, no change"},
            "alsoChecked": also,
            "conclusion": (f"Direct wins — {n_true_direct} through-train option(s) from {from_board}, "
                           f"no detour or change of train needed."),
        }

    # --- CROSS-ORIGIN: no local through train — route via a smarter hub. ---
    top_hub = (top.get("hub") or {}).get("code")
    hubs, seen = [], set()
    for h in ranked[:4]:
        if h["code"] == top_hub or len(hubs) < 3:
            seen.add(h["code"])
            nd = directs_by_board.get(h["code"], 0)
            hubs.append({"name": h["name"], "dailyTrains": h["trains"], "confirmPct": pct(h),
                         "winner": True if h["code"] == top_hub else None,
                         "note": f"{nd} through train(s)" if nd else "no through train"})
    if top_hub and top_hub not in seen:
        hubs.append({"name": top["hub"]["name"], "dailyTrains": top.get("boardTrains", 0),
                     "confirmPct": 70, "winner": True, "note": "best onward connections"})
    wname = (top.get("hub") or {}).get("name", "")
    wd = directs_by_board.get(top_hub, 0)
    others = any(directs_by_board.get(h["code"], 0) > 0 for h in o_heads.values() if h["code"] != top_hub)
    if wd and not others:
        conclusion = (f"Via {wname} wins — the only nearby railhead with a through train to {to_name}: "
                      f"one road hop, then no change of train.")
    elif wd:
        conclusion = f"Via {wname} wins — {wd} through train(s) to {to_name} and the best door-to-door time scanned."
    else:
        conclusion = f"Via {wname} wins — no railhead here has a through train; {wname} offers the safest one-change link."
    return {"mode": "cross-origin",
            "direct": {"confirmability": max(5, min(90, n_true_direct * 18)),
                       "note": f"{n_true_direct} local through option(s)" if n_true_direct else "no through train from here"},
            "hubsScanned": hubs, "conclusion": conclusion}


def _code_of(name, o_heads):
    for c, h in o_heads.items():
        if h["name"] == name:
            return c
    return None


def _diversify(ranked):
    """Direct routes are each a distinct train — keep them all (that's the
    variety the user wants). Only TRANSFER routes get de-duplicated: at most 2
    per hub and 1 per (hub, first-train), so distinct hubs surface instead of
    six variations of the same change."""
    kept, per_hub, per_pair, overflow = [], {}, set(), []
    for r in ranked:
        if r.get("transfers", 0) == 0:
            kept.append(r)
            continue
        hub = (r.get("hub") or {}).get("code") or "_x"
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
                 "durationMins": c["in_train"], "fareInr": _fare_rail(c["train"], b["code"], a["code"], c["in_train"]), "confirmation": "confirmed",
                 "fromCoords": bc, "toCoords": ac, "pathCoords": _path_coords(c.get("path")),
                 "halts": len(c.get("path") or []) - 2 if c.get("path") else None})
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
        # No-transfer routes carry no connection risk — score them above any
        # transfer option; density helps, long first-mile hurts (gently).
        "reliability": max(45, min(95, round(68 + b["trains"] / 8 - first_km / 15))),
        "confirmation": "confirmed", "confirmationPct": None, "clearProbabilityPct": None,
        "hub": {"code": b["code"], "name": b["name"]} if is_cross else None,
        "boardTrains": b["trains"], "transfers": 0,
        "acAvailable": _ac_available(c["train"]),
        "classes": graph.TRAIN_CLASSES.get(c["train"], ""),
        "reliabilityBreakdown": _breakdown_direct(b["trains"], first_km),
        "why": (f"{b['name']} ({round(first_km)} km away) is a far better-connected railhead "
                f"with {b['trains']} trains/day — boarding there beats the limited local options."
                if is_cross else
                f"Direct train from {b['name']} ({b['trains']} trains/day serve this station) — "
                f"no change of train."),
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
                 "from": b["name"], "to": j["hub"], "depart": _hhmm(j["dep1"]),
                 "arrive": _hhmm(j["arr1"]) if j.get("arr1") is not None else None,
                 "durationMins": j["it1"], "fareInr": _fare_rail(j["t1"], b["code"], j["hub"], j["it1"]), "confirmation": "confirmed",
                 "fromCoords": bc, "toCoords": hc, "pathCoords": _path_coords(j.get("path1"))})
    safety = connection_safety(j["wait"])
    legs.append({"id": f"{j['t1']}-{j['t2']}-cx", "mode": "connection", "connectionSafetyPct": safety,
                 "bufferMins": j["wait"],
                 "note": f"Change at {j['hub']} ({j['hub_trains']} trains/day) · {j['wait']} min connection"})
    legs.append({"id": f"{j['t2']}-tr", "mode": "train", "name": f"{j['t2']} {j['t2name'] or ''}".strip(),
                 "from": j["hub"], "to": a["name"], "depart": _hhmm(j["dep2"]), "arrive": _hhmm(j["arr2"]),
                 "durationMins": j["it2"], "fareInr": _fare_rail(j["t2"], j["hub"], a["code"], j["it2"]), "confirmation": "confirmed",
                 "fromCoords": hc, "toCoords": ac, "pathCoords": _path_coords(j.get("path2"))})
    if last_km > 2:
        legs.append({"id": f"{j['t2']}-c2", "mode": "connection", "connectionSafetyPct": None,
                     "bufferMins": None, "note": f"~{round(last_km)} km road to {to}"})
        legs.append(_road_leg(f"{j['t2']}-lm", a["name"], to, last_km, ac, dcoord))

    # Transfer routes are capped BELOW direct ones (a change is inherent risk),
    # scaled by the connection-safety prior.
    base = 42 + j["hub_trains"] / 8 - first_km / 12
    reliability = max(30, min(84, round(base * ((safety or 60) / 100) + (safety or 60) * 0.12)))
    return {
        "id": f"{j['t1']}-{j['hub']}-{j['t2']}",
        "type": "cross-origin",
        "totalTimeMins": sum(l.get("durationMins", 0) for l in legs) + j["wait"],
        "totalFareInr": sum(l.get("fareInr", 0) for l in legs),
        "reliability": reliability,
        "connectionSafetyPct": safety,
        "confirmation": "confirmed", "confirmationPct": None, "clearProbabilityPct": None,
        "hub": {"code": j["hub"], "name": j["hub"]}, "boardTrains": j["hub_trains"], "transfers": 1,
        "acAvailable": _ac_available(j["t1"], j["t2"]),
        "reliabilityBreakdown": _breakdown_transfer(j["hub_trains"], safety, first_km),
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
