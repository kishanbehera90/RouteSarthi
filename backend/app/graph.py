"""In-memory schedule index for fast routing.

The whole timetable (417k stops) is tiny in RAM but murder to self-join in SQL
per request. So we load it once into dict structures and do single-train and
one-transfer search as in-memory scans — microseconds instead of ~100s.

The DB is still used (in engine.py) for what it's genuinely good at: PostGIS
nearest-railhead and city geocoding (one indexed query each).

Loaded lazily on first use and at server startup (see main.py lifespan).
"""
import json
import math
import os
import pickle
import threading
import time

from .db import connect
from . import metrics

_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "graph_cache.pkl")
_CUMDIST_FILE = os.path.join(os.path.dirname(__file__), "data", "train_cumdist.json")
_CACHE_VERSION = 5  # v5: station-mismatch remap applied (etl/fix_station_mismatches)

# tunables
HUB_MIN_TRAINS = 80      # a station busy enough to be a transfer hub
MAX_REACHED_HUBS = 40    # cap transfer hubs to the busiest reached ones
CONN_MIN_BUFFER = 30     # min minutes to make a transfer
CONN_MAX_WAIT = 360      # max sensible wait at a hub (6h)
# A stop whose stored coordinate forces this much back-and-forth detour vs its
# immediate neighbours is almost certainly a mis-identified station (e.g. a
# "Sangariya" stop bound to "Sangar" in J&K). We refuse to board/alight there so
# a bad-geo station can never produce a nonsense route, even one we haven't
# repaired in the data yet. Only judges the stop itself — a legitimate reversal
# junction as an interior pass-through is unaffected.
GUARD_DETOUR_KM = 150

_lock = threading.Lock()
_loaded = False

# train_number -> list of stops in route order: (station_code, arr_min, dep_min, day)
TRAIN_STOPS: dict[str, list] = {}
# station_code -> list of (train_number, index_in_train)
STATION_IDX: dict[str, list] = {}
TRAIN_NAME: dict[str, str] = {}
TRAIN_DAYS: dict[str, str] = {}    # "MON,TUE,…" ("" or missing = assume daily)
TRAIN_CLASSES: dict[str, str] = {} # "SL,3A,…" for fare-class picking
TRAIN_DELAY: dict[str, dict] = {}  # train_no -> measured {avgMins,onTimePct,p50,p80,p90,nObs}
TRAIN_CUMDIST: dict[str, dict] = {}# train_no -> {station_code: cumulative_km} (real distances)
TRAIN_MONTHS: dict[str, frozenset] = {}  # seasonal trains only -> {operating month ints}
HUB_TRAINS: dict[str, int] = {}   # hub code -> num_trains (busy stations only)
STATIONS: list = []               # (code, name, lat, lng, num_trains) for nearest-railhead
STATION_COORD: dict = {}          # code -> [lng, lat] for map drawing
STATION_NAME: dict = {}           # code -> display name (for stop lists)
RAILHEAD_NEAR = 6                 # nearest stations to keep
RAILHEAD_HUBS = 6                 # nearest big hubs to also keep (even if farther)
HUB_RADIUS_KM = 500               # how far to look for a major gateway hub


def _tmin(s):
    if not s or s == "None":
        return None
    h, m, *_ = s.split(":")
    return int(h) * 60 + int(m)


def _populate(trains, stations, train_stops, station_idx, hub_trains, train_days=None,
              train_classes=None, train_delay=None, train_months=None):
    TRAIN_NAME.clear(); STATIONS.clear(); TRAIN_STOPS.clear(); STATION_IDX.clear()
    HUB_TRAINS.clear(); STATION_COORD.clear(); STATION_NAME.clear()
    TRAIN_DAYS.clear(); TRAIN_CLASSES.clear(); TRAIN_DELAY.clear(); TRAIN_MONTHS.clear()
    TRAIN_NAME.update(trains)
    TRAIN_DAYS.update(train_days or {})
    TRAIN_CLASSES.update(train_classes or {})
    TRAIN_DELAY.update(train_delay or {})
    TRAIN_MONTHS.update(train_months or {})
    STATIONS.extend(stations)
    TRAIN_STOPS.update(train_stops)
    STATION_IDX.update(station_idx)
    HUB_TRAINS.update(hub_trains)
    for code, _name, lat, lng, _n in stations:
        STATION_COORD[code] = [lng, lat]
        STATION_NAME[code] = _name
    _load_cumdist()


def is_seasonal(train_no):
    """True for special/seasonal trains (Magh Mela, festival specials) that only
    run in a limited window — they must be date-gated in search."""
    return train_no in TRAIN_MONTHS


def runs_in_month(train_no, month):
    """Whether a train operates in the given calendar month. Regular trains
    (not seasonal) always pass. Seasonal trains pass only in their window; when
    `month` is None (undated search) a seasonal train is hidden."""
    if train_no not in TRAIN_MONTHS:
        return True
    if month is None:
        return False
    return month in TRAIN_MONTHS[train_no]


def _load_cumdist():
    """Real per-stop cumulative distances (etl/load_schedule_extra). Local file,
    so it's loaded fresh outside the DB cache."""
    TRAIN_CUMDIST.clear()
    try:
        with open(_CUMDIST_FILE, encoding="utf-8") as f:
            TRAIN_CUMDIST.update(json.load(f))
    except (OSError, ValueError):
        pass


def rail_km(train_no, from_code, to_code):
    """Exact routed km between two stops of a train from measured cumulative
    distances, or None if we can't (missing train/stop)."""
    d = TRAIN_CUMDIST.get(train_no)
    if not d:
        return None
    a, b = d.get(from_code), d.get(to_code)
    if a is None or b is None:
        return None
    return abs(b - a)


def _load_from_db(attempts=3):
    """Fetch the timetable from Postgres and build the in-memory structures.
    Retries — the transaction pooler occasionally drops a large result mid-stream."""
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            trains, stations, train_stops, station_idx, hub_trains = {}, [], {}, {}, {}
            train_days, train_classes, train_delay, train_months = {}, {}, {}, {}
            with connect() as conn, conn.cursor() as cur:
                try:
                    cur.execute("SELECT number, name, days_of_week, classes, operating_months FROM trains;")
                    rows = cur.fetchall()
                except Exception:  # noqa: BLE001 — column may not exist yet (pre-seasonal ETL)
                    conn.rollback()
                    cur.execute("SELECT number, name, days_of_week, classes FROM trains;")
                    rows = [(a, b, c, d, None) for a, b, c, d in cur.fetchall()]
                for num, name, days, classes, months in rows:
                    trains[num] = name
                    if days:
                        train_days[num] = days
                    if classes:
                        train_classes[num] = classes
                    if months:
                        train_months[num] = frozenset(int(m) for m in months.split(",") if m.strip())
                try:
                    cur.execute("SELECT train_number, avg_delay, p50, p80, p90, on_time_pct, n_obs "
                                "FROM train_delays;")
                    for tn, avg, p50, p80, p90, ontime, n in cur.fetchall():
                        train_delay[tn] = {"avgMins": round(avg or 0), "onTimePct": round(ontime or 0),
                                           "p50": p50, "p80": p80, "p90": p90, "nObs": n}
                except Exception as e:  # noqa: BLE001 — table may not exist yet
                    print("train_delays not loaded:", e)
                cur.execute("SELECT code, name, lat, lng, num_trains FROM stations WHERE lat IS NOT NULL;")
                for code, name, lat, lng, n in cur.fetchall():
                    stations.append((code, name, float(lat), float(lng), n or 0))
                    if (n or 0) >= HUB_MIN_TRAINS:
                        hub_trains[code] = n
                cur.execute("SELECT train_number, station_code, arrival, departure, day, seq "
                            "FROM stops ORDER BY train_number, seq;")
                cur_train, lst = None, None
                for tn, sc, arr, dep, day, _seq in cur.fetchall():
                    if tn != cur_train:
                        cur_train = tn
                        lst = []
                        train_stops[tn] = lst
                    idx = len(lst)
                    lst.append((sc, _tmin(arr), _tmin(dep), day if day is not None else 1))
                    station_idx.setdefault(sc, []).append((tn, idx))
            return (trains, stations, train_stops, station_idx, hub_trains,
                    train_days, train_classes, train_delay, train_months)
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"graph DB load attempt {attempt} failed: {e}")
            time.sleep(2)
    raise last_err


def _write_cache(payload):
    try:
        os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
        with open(_CACHE_FILE, "wb") as f:
            pickle.dump({"version": _CACHE_VERSION, "data": payload}, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:  # noqa: BLE001
        print("graph cache write skipped:", e)


def _read_cache():
    try:
        if not os.path.exists(_CACHE_FILE):
            return None
        with open(_CACHE_FILE, "rb") as f:
            obj = pickle.load(f)
        if obj.get("version") != _CACHE_VERSION:
            return None
        return obj["data"]
    except Exception as e:  # noqa: BLE001
        print("graph cache read skipped:", e)
        return None


def load(force=False):
    """Load the schedule graph. Prefers a local cache file (fast, ~1-2s, no
    network); falls back to building from the DB (with retry) and then writes
    the cache. Pass force=True to rebuild from the DB."""
    global _loaded
    with _lock:
        if _loaded and not force:
            return
        payload = None if force else _read_cache()
        source = "cache"
        if payload is None:
            payload = _load_from_db()
            source = "db"
        _populate(*payload)
        if source == "db":
            _write_cache(payload)
        _loaded = True
        print(f"graph loaded from {source}: {stats()}")


def stats():
    return {"loaded": _loaded, "trains": len(TRAIN_STOPS),
            "stops": sum(len(v) for v in TRAIN_STOPS.values()),
            "stations": len(STATIONS), "hubs": len(HUB_TRAINS)}


def _haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def stop_detour_km(tn, idx):
    """Extra back-and-forth (km) the stop at position `idx` of train `tn` adds
    versus its nearest coord-bearing neighbours on either side. ~0 when the stop
    lies on the line between them; large when its stored location is off in the
    weeds (a mis-identified station). Returns 0 when we can't judge (missing a
    neighbour or coords) so we never over-filter."""
    stops = TRAIN_STOPS.get(tn)
    if not stops or idx <= 0 or idx >= len(stops) - 1:
        return 0.0
    here = STATION_COORD.get(stops[idx][0])
    if not here:
        return 0.0
    prev = nxt = None
    for k in range(idx - 1, -1, -1):
        prev = STATION_COORD.get(stops[k][0])
        if prev:
            break
    for k in range(idx + 1, len(stops)):
        nxt = STATION_COORD.get(stops[k][0])
        if nxt:
            break
    if not prev or not nxt:
        return 0.0
    via = (_haversine_km(prev[1], prev[0], here[1], here[0])
           + _haversine_km(here[1], here[0], nxt[1], nxt[0]))
    direct = _haversine_km(prev[1], prev[0], nxt[1], nxt[0])
    return via - direct


def mislocated_stations(outlier_km=GUARD_DETOUR_KM, far_fraction=0.6):
    """Station codes whose STORED coordinate is consistently far from where the
    timetable expects them (the median of neighbour-midpoints across all their
    trains). These are mis-identified/mis-geocoded stations. Used by the data
    repair (etl/fix_station_mismatches) and for reporting — NOT as a routing
    blocklist (that would wrongly drop a correct station flagged only because a
    neighbour is bad; routing uses the per-candidate stop_detour_km guard
    instead). Returns {code: {"off_km", "exp": [lng, lat], "trains"}}."""
    mids = {}
    for stops in TRAIN_STOPS.values():
        pts = [(s[0], STATION_COORD.get(s[0])) for s in stops]
        pts = [(c, p) for c, p in pts if p]
        for i in range(1, len(pts) - 1):
            (_, a), (cb, b), (_, c2) = pts[i - 1], pts[i], pts[i + 1]
            mids.setdefault(cb, []).append(((a[0] + c2[0]) / 2, (a[1] + c2[1]) / 2))
    out = {}
    for code, ms in mids.items():
        stored = STATION_COORD.get(code)
        if not stored or len(ms) < 3:
            continue
        xs = sorted(m[0] for m in ms)
        ys = sorted(m[1] for m in ms)
        ex, ey = xs[len(xs) // 2], ys[len(ys) // 2]
        off = _haversine_km(stored[1], stored[0], ey, ex)
        far = sum(1 for m in ms if _haversine_km(stored[1], stored[0], m[1], m[0]) > outlier_km) / len(ms)
        if off > outlier_km and far >= far_fraction:
            out[code] = {"off_km": round(off), "exp": [ex, ey], "trains": len(ms)}
    return out


def station_suggestions(q, limit=5):
    """Station names matching a prefix (then substring), busiest first — so
    any place with a railway station is searchable, not just GeoNames cities."""
    q = q.strip().lower()
    if len(q) < 2:
        return []
    pref, cont = [], []
    for _code, name, _lat, _lng, n in STATIONS:
        if n <= 0:
            continue
        low = name.lower()
        if low.startswith(q):
            pref.append((n, name))
        elif q in low:
            cont.append((n, name))
    pref.sort(key=lambda x: -x[0])
    cont.sort(key=lambda x: -x[0])
    seen, out = set(), []
    for _n, name in pref + cont:
        k = name.lower()
        if k not in seen:
            seen.add(k)
            out.append(name)
            if len(out) >= limit:
                break
    return out


def station_geocode(q):
    """(name, lat, lng) for the best station matching q — exact > prefix >
    substring, then busiest. Lets the engine route from any station-town even
    if it's absent from the city gazetteer (e.g. Ringas)."""
    q = q.strip().lower()
    if len(q) < 2:
        return None
    best = None
    for _code, name, lat, lng, n in STATIONS:
        if n <= 0:
            continue
        low = name.lower()
        score = 3 if low == q else 2 if low.startswith(q) else 1 if q in low else 0
        if score == 0:
            continue
        cand = (score, n, name, lat, lng)
        if best is None or (cand[0], cand[1]) > (best[0], best[1]):
            best = cand
    return (best[2], best[3], best[4]) if best else None


def nearest_railheads(lat, lng, radius_km):
    """In-memory equivalent of the old PostGIS query: the nearest stations
    UNION the nearest major hubs (within a wider radius). ~8.5k haversines,
    sub-millisecond — no DB round-trip."""
    near, hubs = [], []
    for code, name, slat, slng, n in STATIONS:
        if n <= 0:
            continue
        km = _haversine_km(lat, lng, slat, slng)
        if km <= radius_km:
            near.append((km, code, name, n))
        if n >= 60 and km <= HUB_RADIUS_KM:
            hubs.append((km, code, name, n))
    near.sort(key=lambda x: x[0])
    hubs.sort(key=lambda x: x[0])
    out = {}
    for km, code, name, n in near[:RAILHEAD_NEAR] + hubs[:RAILHEAD_HUBS]:
        if code not in out:
            c = STATION_COORD.get(code, [None, None])
            out[code] = {"code": code, "name": name, "trains": n, "km": km, "lng": c[0], "lat": c[1]}
    return out


def runs_on(tn, day3):
    """Does this train run on weekday `day3` ('MON'…)? Unknown days => assume
    daily (conservative for coverage; the UI can't show a wrong day it never
    filters). day3=None disables filtering."""
    if day3 is None:
        return True
    days = TRAIN_DAYS.get(tn)
    return not days or day3 in days


def single_train(boards, alights, day3=None):
    """All single-train legs from any board station to any alight station
    (boarding strictly before alighting). Returns list of dicts."""
    out = []
    for bcode in boards:
        for tn, idx in STATION_IDX.get(bcode, []):
            if not runs_on(tn, day3):
                continue
            stops = TRAIN_STOPS[tn]
            b = stops[idx]
            dep = b[2] if b[2] is not None else b[1]
            if dep is None:
                continue
            if stop_detour_km(tn, idx) > GUARD_DETOUR_KM:
                continue                                  # bad-geo boarding stop
            for j in range(idx + 1, len(stops)):
                s = stops[j]
                if s[0] in alights:
                    arr = s[1] if s[1] is not None else s[2]
                    if arr is None:
                        continue
                    in_train = (s[3] - b[3]) * 1440 + (arr - dep)
                    if in_train <= 0:
                        continue
                    if stop_detour_km(tn, j) > GUARD_DETOUR_KM:
                        continue                          # bad-geo alighting stop
                    out.append({"train": tn, "name": TRAIN_NAME.get(tn),
                                "board": bcode, "dep": dep, "alight": s[0],
                                "arr": arr, "in_train": in_train,
                                "path": [stops[k][0] for k in range(idx, j + 1)]})
    return out


def one_transfer(boards, alights, day3=None, predict_ctx=None):
    """origin railhead -> busy hub -> destination railhead, with a feasible
    same-day connection at the hub. All in-memory. (day3 filters leg 2 by the
    same weekday — an approximation consistent with the %1440 wait heuristic.)
    `predict_ctx` = {"dow": int, "month": int} on a DATED search — lets the
    feasibility gate use the date-conditioned PREDICTED p50 instead of the flat
    measured one, so a connection that's genuinely bad for THIS date gets
    filtered upstream instead of only surfacing as a low displayed percentage."""
    boards_set, alights_set = set(boards), set(alights)

    # leg 1: best (shortest in-train) way to reach each hub
    reached = {}   # hub -> (in_train1, train1, board, dep1, arr_hub, path1, arr_day1)
    for bcode in boards_set:
        for tn, idx in STATION_IDX.get(bcode, []):
            if not runs_on(tn, day3):
                continue
            stops = TRAIN_STOPS[tn]
            b = stops[idx]
            dep = b[2] if b[2] is not None else b[1]
            if dep is None:
                continue
            if stop_detour_km(tn, idx) > GUARD_DETOUR_KM:
                continue                                  # bad-geo boarding stop
            for j in range(idx + 1, len(stops)):
                hc = stops[j][0]
                if hc in HUB_TRAINS and hc not in boards_set and hc not in alights_set:
                    s = stops[j]
                    arr = s[1] if s[1] is not None else s[2]
                    if arr is None:
                        continue
                    it1 = (s[3] - b[3]) * 1440 + (arr - dep)
                    if it1 <= 0:
                        continue
                    cur = reached.get(hc)
                    if cur is None or it1 < cur[0]:
                        reached[hc] = (it1, tn, bcode, dep, arr,
                                       [stops[k][0] for k in range(idx, j + 1)], s[3])
    if not reached:
        return []

    # only pursue transfers through the busiest reached hubs
    top = sorted(reached, key=lambda h: -HUB_TRAINS.get(h, 0))[:MAX_REACHED_HUBS]

    # leg 2: hub -> destination with a feasible connection
    journeys = []
    for hc in top:
        it1, t1, bcode, dep1, arr_hub, path1, arr_day1 = reached[hc]
        # The buffer must cover not just a floor but the incoming train's
        # TYPICAL delay: if train 1 is usually p50 min late, a shorter buffer
        # means you miss the connection more often than not. Computed ONCE per
        # hub (t1/hc/arr_hub are loop-invariant across the tn2 candidates below)
        # — a handful of model calls per search, not one per candidate.
        d1 = TRAIN_DELAY.get(t1)
        p50 = None
        if predict_ctx and d1 and d1.get("nObs", 0) >= 15:
            cum = TRAIN_CUMDIST.get(t1) or {}
            dist = cum.get(hc)
            tot = max(cum.values()) if cum else 0
            p50 = metrics.predicted_p50(
                d1.get("avgMins"), metrics.infer_tier(t1, TRAIN_NAME.get(t1)),
                predict_ctx.get("dow"), predict_ctx.get("month"),
                dist_from_origin=dist, total_km=tot, sched_hour=arr_hub // 60,
                day_offset=max(0, (arr_day1 or 1) - 1))
        if p50 is None and d1 and d1.get("p50") is not None:
            p50 = d1["p50"]           # fall back to the flat measured p50
        min_buf = CONN_MIN_BUFFER
        if p50 is not None:
            min_buf = max(CONN_MIN_BUFFER, min(round(p50), 90))

        for tn2, idx in STATION_IDX.get(hc, []):
            if tn2 == t1 or not runs_on(tn2, day3):
                continue
            stops = TRAIN_STOPS[tn2]
            h = stops[idx]
            dep2 = h[2] if h[2] is not None else h[1]
            if dep2 is None:
                continue
            # Clock-time wait with a midnight wrap. KNOWN LIMITATION: this can't
            # tell "30 min later" from "30 min later tomorrow" — but CONN_MAX_WAIT
            # rejects anything that *looks* like a long wait, so errors skew
            # conservative (we may miss overnight connections, not invent bad
            # ones). Proper day-aware connections land with Step 3 delay work.
            wait = (dep2 - arr_hub) % 1440
            if wait < min_buf or wait > CONN_MAX_WAIT:
                continue
            for j in range(idx + 1, len(stops)):
                s = stops[j]
                if s[0] in alights_set:
                    arr2 = s[1] if s[1] is not None else s[2]
                    if arr2 is None:
                        continue
                    it2 = (s[3] - h[3]) * 1440 + (arr2 - dep2)
                    if it2 <= 0:
                        continue
                    if stop_detour_km(tn2, j) > GUARD_DETOUR_KM:
                        continue                          # bad-geo alighting stop
                    journeys.append({
                        "hub": hc, "hub_trains": HUB_TRAINS.get(hc, 0),
                        "board": bcode, "alight": s[0],
                        "t1": t1, "t1name": TRAIN_NAME.get(t1), "dep1": dep1,
                        "arr1": arr_hub, "it1": it1, "path1": path1,
                        "t2": tn2, "t2name": TRAIN_NAME.get(tn2), "dep2": dep2,
                        "arr2": arr2, "it2": it2, "wait": wait,
                        "path2": [stops[k][0] for k in range(idx, j + 1)],
                    })
                    break  # first reachable alight on this train2 is enough

    best = {}
    for j in journeys:
        key = (j["board"], j["hub"], j["alight"])
        cost = j["it1"] + j["wait"] + j["it2"]
        if key not in best or cost < best[key][0]:
            best[key] = (cost, j)
    return [j for _, j in sorted(best.values(), key=lambda x: x[0])[:8]]
