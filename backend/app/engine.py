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
from . import metrics
from .db import get_pool

# --- tunables -------------------------------------------------------------
ORIGIN_RADIUS_KM = 200
DEST_RADIUS_KM = 60
ROAD_KMPH = 40
ROAD_FARE_PER_KM = 3.0
ROAD_ROUTE_FACTOR = 1.3    # road distance vs straight-line
ROAD_DIRECT_MAX_KM = 500   # offer a direct-road option up to this (else rail/flight)
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


def _first_train_dep_min(route):
    """Clock-minute (0–1439) the traveller boards the FIRST train of a route, or
    None for a road-only route. Used to order 'miss it → next train' fallbacks."""
    for l in route.get("legs", []):
        if l.get("mode") == "train" and l.get("depart"):
            try:
                hh, mm = l["depart"].split(":")
                return int(hh) * 60 + int(mm)
            except (ValueError, AttributeError):
                return None
    return None


_GEOCODE_CACHE = {}

# Well-known places whose common spelling differs from the gazetteer's.
PLACE_ALIASES = {
    "kanyakumari": "kanniyakumari", "kanya kumari": "kanniyakumari",
    "banaras": "varanasi", "benares": "varanasi", "calcutta": "kolkata",
    "bombay": "mumbai", "madras": "chennai", "bangalore": "bengaluru",
    "pondicherry": "puducherry", "trivandrum": "thiruvananthapuram",
    "cochin": "kochi", "gauhati": "guwahati", "poona": "pune",
}


def _alias(name):
    return PLACE_ALIASES.get(name.strip().lower(), name)

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
    # The user explicitly picked a railway-station suggestion — resolve it as a
    # station, not a same-named city elsewhere (fixes "wrong Khatu").
    if state_hint == "railway station":
        row = graph.station_geocode(name)
        if len(_GEOCODE_CACHE) < 5000:
            _GEOCODE_CACHE[k] = row
        return row
    name = _alias(name)  # famous-place spellings (Kanyakumari -> Kanniyakumari)
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
    if row is None:
        # Not a gazetteer city — try the railway-station index (Ringas Jn etc.).
        row = graph.station_geocode(name)
    if len(_GEOCODE_CACHE) < 5000:
        _GEOCODE_CACHE[k] = row
    return row


def _fare_road(km):
    return max(20, round(km * ROAD_FARE_PER_KM))


def _rail_km(tn, bcode, acode, in_train_min):
    # Prefer REAL routed km from the schedule's per-stop cumulative distances;
    # fall back to haversine × factor, then to a speed-based proxy.
    real = graph.rail_km(tn, bcode, acode) if tn else None
    if real:
        return real
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


# Human labels for the coach classes we price.
CLASS_LABEL = {"SL": "Sleeper", "3A": "AC 3-tier", "2A": "AC 2-tier", "1A": "AC First",
               "CC": "Chair Car", "2S": "Second sitting"}
CLASS_ORDER = ["2S", "SL", "CC", "3A", "2A", "1A"]


def _offered_classes(tn):
    """The coach classes a train *actually* offers, cleaning up the generic
    `classes` column (which often lists every class under the sun). Premium
    trains are fully reserved with a fixed profile:
      • chair-car day trains (Shatabdi / Vande Bharat / Gatimaan / Tejas *Express*)
        sell only sitting classes (CC/EC/2S);
      • AC-sleeper premiums (Rajdhani / Duronto / Humsafar / Garib Rath, incl.
        *Tejas Rajdhani*) sell only AC sleeper (1A/2A/3A).
    Note the RAJ guard: "TEJAS RAJDHANI" is an AC-sleeper train, not chair-car.
    Non-premium trains keep their listed classes untouched."""
    have = [x.strip() for x in graph.TRAIN_CLASSES.get(tn, "").split(",") if x.strip()]
    if metrics.infer_tier(tn, graph.TRAIN_NAME.get(tn)) != "premium":
        return have
    name = (graph.TRAIN_NAME.get(tn) or "").upper()
    tokens = name.split()
    # chair-car day trains — but NOT the sleeper variants (Vande Bharat SL,
    # Tejas Rajdhani), which are AC-sleeper despite the shared brand name.
    is_sitting = ("SHATABDI" in name or "GATIMAAN" in name
                  or ("VANDE" in name and "SL" not in tokens)
                  or ("TEJAS" in name and "RAJ" not in tokens))
    allow = ({"CC", "EC", "2S", "EA", "EV"} if is_sitting
             else {"1A", "2A", "3A", "3E", "EA"})   # AC-sleeper premium
    return [c for c in have if c in allow] or have   # never strip to empty


def _class_fares(tn, bcode, acode, in_train_min):
    """Per-class fares for the classes this train actually offers, cheapest
    first: [{code, label, fareInr}]. Fare = calibrated per-km base + real
    reservation + superfast surcharge (premium/superfast trains) + 5% GST (AC)."""
    km = _rail_km(tn, bcode, acode, in_train_min)
    tier = metrics.infer_tier(tn, graph.TRAIN_NAME.get(tn))
    have = set(_offered_classes(tn))
    out = []
    for c in CLASS_ORDER:
        if c in have and c in FARE_RATE:
            out.append({"code": c, "label": CLASS_LABEL[c],
                        "fareInr": metrics.rail_fare(c, FARE_RATE[c], km, tier)})
    if not out:  # trains with unknown/other classes -> a sleeper-rate estimate
        out.append({"code": "SL", "label": CLASS_LABEL["SL"],
                    "fareInr": metrics.rail_fare("SL", FARE_RATE["SL"], km, tier)})
    return sorted(out, key=lambda x: x["fareInr"])


def _fare_rail(tn, bcode, acode, in_train_min):
    """Cheapest available class — the headline fare for a leg."""
    return _class_fares(tn, bcode, acode, in_train_min)[0]["fareInr"]


def _road_leg(idx, frm, to, km, fromc=None, toc=None):
    return {"id": idx, "mode": "cab", "name": f"{frm} → {to}", "from": frm, "to": to,
            "durationMins": round(km / ROAD_KMPH * 60), "fareInr": _fare_road(km),
            "confirmation": "confirmed", "fromCoords": fromc, "toCoords": toc}


def _coord(node):
    """[lng, lat] for a railhead dict (b/a) — None-safe."""
    if node.get("lng") is None or node.get("lat") is None:
        return None
    return [node["lng"], node["lat"]]


def _useful(b, a, ocoord, dcoord):
    """A rail leg must make geographic sense: alight CLOSER to the destination
    than the board, and FARTHER from the origin. Kills backtracking nonsense
    (e.g. Ringas → cab to Jaipur → train back to Ringas → cab to Salasar)."""
    if None in (b.get("lat"), a.get("lat")) or not ocoord or not dcoord:
        return True  # can't judge without coords — don't over-filter
    hav = graph._haversine_km
    o_lat, o_lng, d_lat, d_lng = ocoord[1], ocoord[0], dcoord[1], dcoord[0]
    b_to_d = hav(b["lat"], b["lng"], d_lat, d_lng)
    a_to_d = hav(a["lat"], a["lng"], d_lat, d_lng)
    b_to_o = hav(b["lat"], b["lng"], o_lat, o_lng)
    a_to_o = hav(a["lat"], a["lng"], o_lat, o_lng)
    return a_to_d < b_to_d - 5 and a_to_o > b_to_o - 5


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


_DAY_ORDER = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_DAY_SHORT = {"MON": "Mon", "TUE": "Tue", "WED": "Wed", "THU": "Thu",
              "FRI": "Fri", "SAT": "Sat", "SUN": "Sun"}


def _days_label(tn):
    """'Daily' / 'Mon, Wed, Fri' / None (unknown)."""
    d = graph.TRAIN_DAYS.get(tn, "")
    if not d:
        return None
    days = [x.strip() for x in d.split(",") if x.strip()]
    if len(days) == 7:
        return "Daily"
    return ", ".join(_DAY_SHORT.get(x, x) for x in _DAY_ORDER if x in days)


def _path_stops(codes):
    """Station names along a train leg (for the 'all stops' expander)."""
    names = [graph.STATION_NAME.get(c, c) for c in (codes or [])]
    return names if len(names) >= 2 else None


_MONTH_ABBR = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}


def _season_label(tn):
    """'Seasonal · runs in Jan' for special trains, else None. Only shown when
    the train surfaces at all (i.e. the user searched within its window)."""
    ms = graph.TRAIN_MONTHS.get(tn)
    if not ms:
        return None
    return "Seasonal · runs in " + ", ".join(_MONTH_ABBR[m] for m in sorted(ms))


def _route_classes(*train_nos):
    """Union of coach classes across a route's trains, in fare order."""
    have = set()
    for tn in train_nos:
        have.update(_offered_classes(tn))
    return [c for c in CLASS_ORDER if c in have] + sorted(have - set(CLASS_ORDER))


def search(from_place, to_place, pref="confirmed", date=None):
    day3, days_out, month = None, None, None
    if date:
        try:
            import datetime as _dt
            d = _dt.date.fromisoformat(date)
            day3 = DAY3[d.weekday()]
            days_out = (d - _dt.date.today()).days
            month = d.month
        except ValueError:
            pass
    ctx = (days_out, month)
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
        # Seasonal/special trains (Magh Mela etc.) only surface when the travel
        # date falls in their operating window — and are hidden on an undated search.
        if not graph.runs_in_month(c["train"], month):
            continue
        b, a = o_heads[c["board"]], d_heads[c["alight"]]
        if not _useful(b, a, ocoord, dcoord):
            continue
        access = b["km"] + a["km"]
        if c["train"] not in best_by_train or access < best_by_train[c["train"]][0]:
            best_by_train[c["train"]] = (access, c)
    for access, c in best_by_train.values():
        routes.append(_direct_route(from_place, to_place, o_heads[c["board"]], d_heads[c["alight"]], c, ocoord, dcoord, ctx))

    # --- one-transfer cross-origin (when few/no through trains) ---
    if len(routes) < 3:
        for j in graph.one_transfer(o_heads, d_heads, day3):
            if not (graph.runs_in_month(j["t1"], month) and graph.runs_in_month(j["t2"], month)):
                continue
            b, a = o_heads[j["board"]], d_heads[j["alight"]]
            if not _useful(b, a, ocoord, dcoord):
                continue
            routes.append(_transfer_route(from_place, to_place, b, a, j, ocoord, dcoord, ctx))

    # --- direct road option (multi-modal): often best for short/poorly-railed
    # trips. Offered up to a sane distance, or whenever rail found nothing. ---
    straight_km = graph._haversine_km(o[1], o[2], d[1], d[2])
    if straight_km * ROAD_ROUTE_FACTOR <= ROAD_DIRECT_MAX_KM or not routes:
        routes.append(_road_route(from_place, to_place, ocoord, dcoord))

    # Always keep the road option visible (ranked in its rightful place), even
    # when many trains would otherwise crowd it out of the top slots.
    ranked = _diversify(_rank(routes, pref))
    road = [r for r in ranked if r.get("roadOnly")]
    rail = [r for r in ranked if not r.get("roadOnly")][:15]
    routes = _rank(rail + road, pref)[:16]
    # Plan B: "if you miss this train, the next one you could catch" — must be an
    # alternative that departs LATER than this route (an earlier train is already
    # gone). If none departs later, keep the route's own planB (delay/hub advice).
    for r in routes:
        t = _first_train_dep_min(r)
        if t is None:
            continue                       # road-only route keeps its own planB
        best = None                        # (departure_gap, alt_route)
        for alt in routes:
            if alt is r or alt.get("roadOnly"):
                continue
            t2 = _first_train_dep_min(alt)
            if t2 is None or t2 <= t:       # same or earlier departure — not a fallback
                continue
            if best is None or (t2 - t) < best[0]:
                best = (t2 - t, alt)
        if best:
            alt = best[1]
            tleg = next((l for l in alt["legs"] if l["mode"] == "train"), None)
            h = alt["totalTimeMins"]
            r["planB"] = (f"Miss it? Next train: {tleg['name']} departing {tleg['depart']} "
                          f"— ₹{alt['totalFareInr']}, {h // 60}h {h % 60}min door to door.")
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


def _direct_route(frm, to, b, a, c, ocoord, dcoord, ctx=(None, None)):
    legs = []
    first_km, last_km = b["km"], a["km"]
    bc, ac = _coord(b), _coord(a)
    halts = len(c.get("path") or []) - 2 if c.get("path") else None
    rail_km = _rail_km(c["train"], b["code"], a["code"], c["in_train"])
    dprofile = metrics.leg_delay_profile(c["train"], c["name"], rail_km, halts,
                                         measured=graph.TRAIN_DELAY.get(c["train"]))
    conf_pct, conf_state = metrics.confirmation_estimate(
        _route_classes(c["train"]), dprofile["tier"], ctx[0], ctx[1])
    reliability = metrics.route_reliability(dprofile["onTimePct"], None, 0, first_km, conf_pct)
    if first_km > 2:
        legs.append(_road_leg(f"{c['train']}-fm", frm, b["name"], first_km, ocoord, bc))
        legs.append({"id": f"{c['train']}-c1", "mode": "connection", "connectionSafetyPct": None,
                     "bufferMins": None, "note": f"~{round(first_km)} km road to {b['name']}"})
    train_leg = {"id": f"{c['train']}-tr", "mode": "train", "trainNo": c["train"],
                 "name": f"{c['train']} {c['name'] or ''}".strip(),
                 "from": b["name"], "to": a["name"], "depart": _hhmm(c["dep"]), "arrive": _hhmm(c["arr"]),
                 "durationMins": c["in_train"],
                 "classFares": _class_fares(c["train"], b["code"], a["code"], c["in_train"]),
                 "fareInr": _fare_rail(c["train"], b["code"], a["code"], c["in_train"]),
                 "confirmation": conf_state,
                 "delayProfile": {"avgMins": dprofile["avgMins"], "onTimePct": dprofile["onTimePct"],
                                  "source": dprofile["delaySource"], "p90": dprofile.get("p90")},
                 "fromCoords": bc, "toCoords": ac, "pathCoords": _path_coords(c.get("path")),
                 "days": _days_label(c["train"]), "stops": _path_stops(c.get("path")),
                 "halts": halts}
    legs.append(train_leg)
    if last_km > 2:
        legs.append({"id": f"{c['train']}-c2", "mode": "connection", "connectionSafetyPct": None,
                     "bufferMins": None, "note": f"~{round(last_km)} km road to {to}"})
        legs.append(_road_leg(f"{c['train']}-lm", a["name"], to, last_km, ac, dcoord))

    is_cross = first_km > 20
    ot = dprofile["onTimePct"]
    ot_measured = dprofile["delaySource"] == "measured"
    ot_label = "On-time record" if ot_measured else "On-time (est.)"
    ot_phrase = (f" ~{ot}% on-time over a year of real runs" if ot_measured
                 else f" ~{ot}% on-time (est.)")
    return {
        "id": f"{c['train']}-{b['code']}-{a['code']}",
        "type": "cross-origin" if is_cross else "direct",
        "totalTimeMins": sum(l.get("durationMins", 0) for l in legs),
        "totalFareInr": sum(l.get("fareInr", 0) for l in legs),
        "reliability": reliability,
        "confirmation": conf_state, "confirmationPct": conf_pct, "clearProbabilityPct": None,
        "hub": {"code": b["code"], "name": b["name"]} if is_cross else None,
        "boardTrains": b["trains"], "transfers": 0,
        "acAvailable": _ac_available(c["train"]),
        "classes": _route_classes(c["train"]),
        "onTimePct": ot,
        "mainTrain": {"trainNo": c["train"], "name": c["name"] or c["train"],
                      "from": b["name"], "to": a["name"],
                      "depart": _hhmm(c["dep"]), "arrive": _hhmm(c["arr"]),
                      "days": _days_label(c["train"]), "halts": train_leg["halts"],
                      "seasonal": _season_label(c["train"]),
                      "classFares": train_leg["classFares"]},
        "reliabilityBreakdown": [
            {"label": "Confirmation (est.)", "value": conf_pct, "weight": 50},
            {"label": ot_label, "value": ot, "weight": 30, "source": dprofile["delaySource"]},
            {"label": "First-mile access", "value": max(30, round(100 - first_km / 2)), "weight": 20},
        ],
        "why": (f"{b['name']} ({round(first_km)} km away) is a far better-connected railhead "
                f"with {b['trains']} trains/day — boarding there beats the limited local options."
                if is_cross else
                f"Direct train from {b['name']} ({b['trains']} trains/day serve this station) — "
                f"no change of train.") +
               ot_phrase + f", ~{conf_pct}% seat-confirm (est.).",
        "planB": (f"9 in 10 runs of this train reach within ~{round(dprofile['p90'])} min of "
                  f"schedule (measured) — keep that buffer for any onward connection."
                  if ot_measured and dprofile.get("p90") else
                  (f"Seats look tight (~{conf_pct}% confirm, est.) — have a road fallback "
                   f"or nearby-date option ready." if conf_pct < 55 else None)),
        "legs": legs,
    }


def _transfer_route(frm, to, b, a, j, ocoord, dcoord, ctx=(None, None)):
    legs = []
    first_km, last_km = b["km"], a["km"]
    bc, ac, hc = _coord(b), _coord(a), _hub_coord(j["hub"])
    km1 = _rail_km(j["t1"], b["code"], j["hub"], j["it1"])
    km2 = _rail_km(j["t2"], j["hub"], a["code"], j["it2"])
    halts1 = len(j.get("path1") or []) - 2 if j.get("path1") else None
    halts2 = len(j.get("path2") or []) - 2 if j.get("path2") else None
    dp1 = metrics.leg_delay_profile(j["t1"], j["t1name"], km1, halts1, measured=graph.TRAIN_DELAY.get(j["t1"]))
    dp2 = metrics.leg_delay_profile(j["t2"], j["t2name"], km2, halts2, measured=graph.TRAIN_DELAY.get(j["t2"]))
    if first_km > 2:
        legs.append(_road_leg(f"{j['t1']}-fm", frm, b["name"], first_km, ocoord, bc))
        legs.append({"id": f"{j['t1']}-c0", "mode": "connection", "connectionSafetyPct": None,
                     "bufferMins": None, "note": f"~{round(first_km)} km road to {b['name']}"})
    leg1 = {"id": f"{j['t1']}-tr", "mode": "train", "trainNo": j["t1"], "name": f"{j['t1']} {j['t1name'] or ''}".strip(),
            "from": b["name"], "to": j["hub"], "depart": _hhmm(j["dep1"]),
            "arrive": _hhmm(j["arr1"]) if j.get("arr1") is not None else None,
            "durationMins": j["it1"], "classFares": _class_fares(j["t1"], b["code"], j["hub"], j["it1"]),
            "fareInr": _fare_rail(j["t1"], b["code"], j["hub"], j["it1"]), "confirmation": "confirmed",
            "delayProfile": {"avgMins": dp1["avgMins"], "onTimePct": dp1["onTimePct"],
                             "source": dp1["delaySource"], "p90": dp1.get("p90")},
            "fromCoords": bc, "toCoords": hc, "pathCoords": _path_coords(j.get("path1")),
            "days": _days_label(j["t1"]), "stops": _path_stops(j.get("path1")), "halts": halts1}
    legs.append(leg1)
    # Connection safety from the ARRIVING train's own delay distribution vs buffer.
    safety = metrics.connection_safety(j["wait"], dp1["avgMins"])
    legs.append({"id": f"{j['t1']}-{j['t2']}-cx", "mode": "connection", "connectionSafetyPct": safety,
                 "bufferMins": j["wait"],
                 "note": f"Change at {j['hub']} ({j['hub_trains']} trains/day) · {j['wait']} min connection"})
    leg2 = {"id": f"{j['t2']}-tr", "mode": "train", "trainNo": j["t2"], "name": f"{j['t2']} {j['t2name'] or ''}".strip(),
            "from": j["hub"], "to": a["name"], "depart": _hhmm(j["dep2"]), "arrive": _hhmm(j["arr2"]),
            "durationMins": j["it2"], "classFares": _class_fares(j["t2"], j["hub"], a["code"], j["it2"]),
            "fareInr": _fare_rail(j["t2"], j["hub"], a["code"], j["it2"]), "confirmation": "confirmed",
            "delayProfile": {"avgMins": dp2["avgMins"], "onTimePct": dp2["onTimePct"],
                             "source": dp2["delaySource"], "p90": dp2.get("p90")},
            "fromCoords": hc, "toCoords": ac, "pathCoords": _path_coords(j.get("path2")),
            "days": _days_label(j["t2"]), "stops": _path_stops(j.get("path2")), "halts": halts2}
    legs.append(leg2)
    if last_km > 2:
        legs.append({"id": f"{j['t2']}-c2", "mode": "connection", "connectionSafetyPct": None,
                     "bufferMins": None, "note": f"~{round(last_km)} km road to {to}"})
        legs.append(_road_leg(f"{j['t2']}-lm", a["name"], to, last_km, ac, dcoord))

    ot = min(dp1["onTimePct"], dp2["onTimePct"])   # weakest leg
    ot_measured = dp1["delaySource"] == "measured" and dp2["delaySource"] == "measured"
    ot_label = "On-time record" if ot_measured else "On-time (est.)"
    conf_pct, conf_state = metrics.confirmation_estimate(
        _route_classes(j["t1"], j["t2"]), max(dp1["tier"], dp2["tier"], key=lambda t: {"premium": 3, "superfast": 2, "express": 1, "passenger": 0}[t]),
        ctx[0], ctx[1])
    reliability = metrics.route_reliability(ot, safety, 1, first_km, conf_pct)
    return {
        "id": f"{j['t1']}-{j['hub']}-{j['t2']}",
        "type": "cross-origin",
        "totalTimeMins": sum(l.get("durationMins", 0) for l in legs) + j["wait"],
        "totalFareInr": sum(l.get("fareInr", 0) for l in legs),
        "reliability": reliability,
        "connectionSafetyPct": safety,
        "confirmation": conf_state, "confirmationPct": conf_pct, "clearProbabilityPct": None,
        "hub": {"code": j["hub"], "name": j["hub"]}, "boardTrains": j["hub_trains"], "transfers": 1,
        "acAvailable": _ac_available(j["t1"], j["t2"]),
        "classes": _route_classes(j["t1"], j["t2"]),
        "onTimePct": ot,
        "mainTrain": (lambda m, tn: {"trainNo": m["trainNo"], "name": m["name"], "from": m["from"],
                                     "to": m["to"], "depart": m["depart"], "arrive": m["arrive"],
                                     "days": m.get("days"), "halts": m.get("halts"),
                                     "seasonal": _season_label(tn),
                                     "classFares": m["classFares"]})(
            *(( leg1, j["t1"]) if j["it1"] >= j["it2"] else (leg2, j["t2"]))),
        "reliabilityBreakdown": [
            {"label": "Confirmation (est.)", "value": conf_pct, "weight": 38},
            {"label": "Connection safety (est.)", "value": safety or 60, "weight": 30},
            {"label": ot_label, "value": ot, "weight": 20,
             "source": "measured" if ot_measured else "modelled"},
        ],
        "why": (f"No through train — but {j['hub']} ({j['hub_trains']} trains/day) links the two "
                f"sides with a {j['wait']}-min connection (~{safety or 60}% safe, est.)."),
        "planB": (f"If the first train is late, {j['hub']} runs {j['hub_trains']} trains/day, so "
                  f"a missed connection isn't a dead end — you can re-book onward there."
                  if (safety or 60) < 75 else None),
        "legs": legs,
    }


def _slug(s):
    return "".join(ch if ch.isalnum() else "_" for ch in s.lower())[:24]


def _road_route(frm, to, ocoord, dcoord):
    """A direct door-to-door road option (cab/bus). For a travel planner this
    is often the best answer for short hops or poorly-railed pairs — it competes
    with the rail routes and wins on time when it deserves to."""
    km = graph._haversine_km(ocoord[1], ocoord[0], dcoord[1], dcoord[0]) * ROAD_ROUTE_FACTOR
    dur = max(15, round(km / ROAD_KMPH * 60))
    leg = _road_leg("roaddirect", frm, to, km, ocoord, dcoord)
    leg["name"] = f"Road · {frm} → {to}"
    return {
        "id": f"road-{_slug(frm)}-{_slug(to)}",
        "type": "direct", "totalTimeMins": dur, "totalFareInr": leg["fareInr"],
        "reliability": 68, "confirmation": "confirmed", "confirmationPct": None,
        "clearProbabilityPct": None, "hub": None, "transfers": 0, "roadOnly": True,
        "classes": [], "acAvailable": None, "mainTrain": None,
        "reliabilityBreakdown": [
            {"label": "No transfers", "value": 100},
            {"label": "Always available", "value": 90},
            {"label": "Door to door", "value": 95},
        ],
        "why": (f"Direct road (~{round(km)} km, ~{dur // 60}h {dur % 60:02d}m by cab or bus) — "
                f"usually the quickest door-to-door for shorter trips or where there's no "
                f"good direct train."),
        "planB": None, "legs": [leg],
    }


def _rank(routes, pref):
    if pref == "cheapest":
        return sorted(routes, key=lambda r: r["totalFareInr"])
    if pref == "fastest":
        return sorted(routes, key=lambda r: r["totalTimeMins"])
    # Confirmed / default: fewest transfers, then most reliable. On a reliability
    # TIE, prefer a friction-free direct board over a cross-origin one — don't
    # send the traveller on a road trip to another town's railhead when their own
    # station offers an equally-reliable train. Time breaks any remaining tie.
    return sorted(routes, key=lambda r: (r["transfers"], -r["reliability"],
                                         1 if r.get("type") == "cross-origin" else 0,
                                         r["totalTimeMins"]))


def _corridor(o, d):
    return {"id": f"{o[0].lower()}-{d[0].lower()}",
            "from": {"code": "", "name": o[0]}, "to": {"code": "", "name": d[0]},
            "tagline": f"Live options from {o[0]} to {d[0]}, computed from the rail network."}


def _store(key, result):
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = result
