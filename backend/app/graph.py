"""In-memory schedule index for fast routing.

The whole timetable (417k stops) is tiny in RAM but murder to self-join in SQL
per request. So we load it once into dict structures and do single-train and
one-transfer search as in-memory scans — microseconds instead of ~100s.

The DB is still used (in engine.py) for what it's genuinely good at: PostGIS
nearest-railhead and city geocoding (one indexed query each).

Loaded lazily on first use and at server startup (see main.py lifespan).
"""
import math
import os
import pickle
import threading
import time

from .db import connect

_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "graph_cache.pkl")
_CACHE_VERSION = 2  # v2: adds TRAIN_DAYS + TRAIN_CLASSES

# tunables
HUB_MIN_TRAINS = 80      # a station busy enough to be a transfer hub
MAX_REACHED_HUBS = 40    # cap transfer hubs to the busiest reached ones
CONN_MIN_BUFFER = 30     # min minutes to make a transfer
CONN_MAX_WAIT = 360      # max sensible wait at a hub (6h)

_lock = threading.Lock()
_loaded = False

# train_number -> list of stops in route order: (station_code, arr_min, dep_min, day)
TRAIN_STOPS: dict[str, list] = {}
# station_code -> list of (train_number, index_in_train)
STATION_IDX: dict[str, list] = {}
TRAIN_NAME: dict[str, str] = {}
TRAIN_DAYS: dict[str, str] = {}    # "MON,TUE,…" ("" or missing = assume daily)
TRAIN_CLASSES: dict[str, str] = {} # "SL,3A,…" for fare-class picking
HUB_TRAINS: dict[str, int] = {}   # hub code -> num_trains (busy stations only)
STATIONS: list = []               # (code, name, lat, lng, num_trains) for nearest-railhead
STATION_COORD: dict = {}          # code -> [lng, lat] for map drawing
RAILHEAD_NEAR = 6                 # nearest stations to keep
RAILHEAD_HUBS = 6                 # nearest big hubs to also keep (even if farther)
HUB_RADIUS_KM = 500               # how far to look for a major gateway hub


def _tmin(s):
    if not s or s == "None":
        return None
    h, m, *_ = s.split(":")
    return int(h) * 60 + int(m)


def _populate(trains, stations, train_stops, station_idx, hub_trains, train_days=None, train_classes=None):
    TRAIN_NAME.clear(); STATIONS.clear(); TRAIN_STOPS.clear(); STATION_IDX.clear()
    HUB_TRAINS.clear(); STATION_COORD.clear(); TRAIN_DAYS.clear(); TRAIN_CLASSES.clear()
    TRAIN_NAME.update(trains)
    TRAIN_DAYS.update(train_days or {})
    TRAIN_CLASSES.update(train_classes or {})
    STATIONS.extend(stations)
    TRAIN_STOPS.update(train_stops)
    STATION_IDX.update(station_idx)
    HUB_TRAINS.update(hub_trains)
    for code, _name, lat, lng, _n in stations:
        STATION_COORD[code] = [lng, lat]


def _load_from_db(attempts=3):
    """Fetch the timetable from Postgres and build the in-memory structures.
    Retries — the transaction pooler occasionally drops a large result mid-stream."""
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            trains, stations, train_stops, station_idx, hub_trains = {}, [], {}, {}, {}
            train_days, train_classes = {}, {}
            with connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT number, name, days_of_week, classes FROM trains;")
                for num, name, days, classes in cur.fetchall():
                    trains[num] = name
                    if days:
                        train_days[num] = days
                    if classes:
                        train_classes[num] = classes
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
            return trains, stations, train_stops, station_idx, hub_trains, train_days, train_classes
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
            for j in range(idx + 1, len(stops)):
                s = stops[j]
                if s[0] in alights:
                    arr = s[1] if s[1] is not None else s[2]
                    if arr is None:
                        continue
                    in_train = (s[3] - b[3]) * 1440 + (arr - dep)
                    if in_train <= 0:
                        continue
                    out.append({"train": tn, "name": TRAIN_NAME.get(tn),
                                "board": bcode, "dep": dep, "alight": s[0],
                                "arr": arr, "in_train": in_train,
                                "path": [stops[k][0] for k in range(idx, j + 1)]})
    return out


def one_transfer(boards, alights, day3=None):
    """origin railhead -> busy hub -> destination railhead, with a feasible
    same-day connection at the hub. All in-memory. (day3 filters leg 2 by the
    same weekday — an approximation consistent with the %1440 wait heuristic.)"""
    boards_set, alights_set = set(boards), set(alights)

    # leg 1: best (shortest in-train) way to reach each hub
    reached = {}   # hub -> (in_train1, train1, board, dep1, arr_hub)
    for bcode in boards_set:
        for tn, idx in STATION_IDX.get(bcode, []):
            if not runs_on(tn, day3):
                continue
            stops = TRAIN_STOPS[tn]
            b = stops[idx]
            dep = b[2] if b[2] is not None else b[1]
            if dep is None:
                continue
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
                                       [stops[k][0] for k in range(idx, j + 1)])
    if not reached:
        return []

    # only pursue transfers through the busiest reached hubs
    top = sorted(reached, key=lambda h: -HUB_TRAINS.get(h, 0))[:MAX_REACHED_HUBS]

    # leg 2: hub -> destination with a feasible connection
    journeys = []
    for hc in top:
        it1, t1, bcode, dep1, arr_hub, path1 = reached[hc]
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
            if wait < CONN_MIN_BUFFER or wait > CONN_MAX_WAIT:
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
