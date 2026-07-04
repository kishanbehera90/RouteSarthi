"""ETL v2 — replace the 2016 timetable with the May-2026 scrape.

Sources (backend/data/raw/candidates/, gitignored):
  - fresh-2026/IRCTC_cleaned.csv   -> the new base timetable (8,366 trains,
    station NAMES + times in an `intermediate_stops` text blob)
  - irctc-2023/schedules.csv       -> used ONLY to build the station
    name->code dictionary (its stationList has stationCode+stationName)

Design decisions (PROJECT_LOG 2026-07-03):
  - 2016 schedules are DROPPED from the DB (0% audit validity — a harmful
    fallback). stations + cities tables are kept (geo is stable).
  - trains/stops get `source` + `last_verified` for the live-refresh future.
  - Day rollover per stop is INFERRED (clock time decreasing => next day).

Usage (from backend/):
    python etl/load_v2.py --dry-run   # parse + mapping coverage report only
    python etl/load_v2.py            # actually reload the DB
"""
import ast
import csv
import os
import re
import sys
import time

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
csv.field_size_limit(1 << 24)

CAND = os.path.join(BACKEND, "data", "raw", "candidates")
FRESH = os.path.join(CAND, "fresh-2026", "IRCTC_cleaned.csv")
IRCTC = os.path.join(CAND, "irctc-2023", "schedules.csv")
SOURCE_TAG = "kaggle-2026"
LAST_VERIFIED = "2026-05-01"

_norm_re = re.compile(r"[^A-Z0-9 ]+")


def norm(name):
    s = _norm_re.sub(" ", name.upper()).strip()
    return re.sub(r"\s+", " ", s)


# Post-2016 renames + IRCTC spelling quirks -> codes in our stations table.
ALIASES = {
    "HAZRAT NIZAMUDDIN": "NZM", "H NIZAMUDDIN": "NZM",
    "MGR CHENNAI CTR": "MAS", "MGR CHENNAI CENTRAL": "MAS", "CHENNAI CENTRAL": "MAS",
    "VIRANGANA LAKSHMIBAI": "JHS", "VIRANGANA LAKSHMIBAI JHANSHI": "JHS",
    "YASVANTPUR JN": "YPR", "YESVANTPUR JN": "YPR",
    "TIRUCHCHIRAPPALLI JN": "TPJ", "TIRUCHCHIRAPALLI": "TPJ",
    "C SHIVAJI MAHARAJ T": "CSTM", "CHHATRAPATI SHIVAJI MAHARAJ T": "CSTM",
    "MUMBAI CENTRAL": "BCT", "PT DD UPADHYAYA JN": "MGS", "PANDIT DEEN DAYAL UPADHYAYA JN": "MGS",
    "RANI KAMLAPATI": "HBJ", "PRAYAGRAJ JN": "ALD", "PRAYAGRAJ": "ALD",
    "EKTA NAGAR": "KDCY", "KALABURAGI JN": "GR", "BANARAS": "BSBS",
    "SMVT BENGALURU": "BNC", "SIR M VISVESVARAYA TERMINAL": "BNC",
    "UDHNA JN": "UDN", "AYODHYA CANTT": "FD", "AYODHYA DHAM JN": "AY",
    "BHUSAWAL JN": "BSL", "NAGPUR JN": "NGP", "ITARSI JN": "ET",
    "LOKMANYATILAK": "LTT", "LOKMANYA TILAK T": "LTT",
    "ANAND VIHAR TERMINAL": "ANVT", "DEHRI ON SON": "DOS",
    "CHANDRAPUR MAHARASHTRA": "CD", "SIRPUR KAGHAZNAGAR": "SKZR",
    "HUBBALLI JN": "UBL", "HUBLI JN": "UBL",
    "THIRUVANANTHAPURAM CENTRAL": "TVC", "LONAVLA": "LNL",
    "DHARWAD": "DWR", "VRIDDHACHALAM JN": "VRI",
    "AHILYANAGAR": "ANG", "C SAMBHAJINAGAR": "AWB", "CHH SAMBHAJINAGAR": "AWB",
    "MAA BELHA DEVI DHAM PRATAPGARH JN": "PBH", "MANGALORE CENTRAL": "MAQ",
    "NAGARCOIL JN": "NCJ", "MANTHRALAYAM ROAD": "MALM",
    "GANDHIDHAM JN": "GIMB", "ANUGRAH NARAYAN ROAD": "AUBR",
    "ICHCHAPURAM": "IPM", "MELMARUVATHUR": "MLMR",
}


def variants(raw):
    """Candidate normalized names (and direct code aliases) for a raw name."""
    out = []
    bases = [norm(raw)]
    if "(" in raw:                      # "New Name(Old Name" truncations
        bases += [norm(p) for p in raw.split("(") if p.strip()]
    for b in list(bases):
        if b.startswith("RL "):         # scrape artifact prefix
            bases.append(b[3:])
    for b in bases:
        b = b.strip()
        if not b:
            continue
        out.append(b)
        if b in ALIASES:
            out.append(("__CODE__", ALIASES[b]))
        if b.endswith(" JN"):
            out += [b[:-3], b[:-3] + " JUNCTION"]
        elif b.endswith(" JUNCTION"):
            out += [b[:-9], b[:-9] + " JN"]
        else:
            out.append(b + " JN")
    return out


DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Stations RENAMED since the datameet stations table (which carries the geo):
# new code -> old code. Without this, stops land under codes that have no
# geo/num_trains, so the engine can't board/alight there (P11: trains "passing"
# Prayagraj Jn invisibly because it was stored as PRYJ, not ALD).
CODE_RENAMES = {
    "PRYJ": "ALD",   # Prayagraj Jn (Allahabad Jn)
    "PRRB": "ALY",   # Prayagraj Rambag (Allahabad City)
    "PYGS": "SFG",   # Prayagraj Sangam (Allahabad Sangam/Prayag Ghat)
    "MMCT": "BCT",   # Mumbai Central
    "CSMT": "CSTM",  # Chhatrapati Shivaji Maharaj Terminus
    "SMVT": "BNC",   # Sir M Visvesvaraya Terminal (Bengaluru Cantt geo-proxy)
    "SMVB": "BNC",
    "VGLJ": "JHS",   # Virangana Lakshmibai (Jhansi)
    "VGLB": "JHS",
    "DDU": "MGS",    # Pt. Deen Dayal Upadhyaya Jn (Mughalsarai)
}


def fix_code(code):
    return CODE_RENAMES.get(code, code)


def build_name_map():
    """station name -> code from IRCTC-2023 stationList + datameet stations.
    Also returns IRCTC-2023 trains/stops (structured, coded, with dayCount)
    used to GAP-FILL trains missing from the 2026 scrape."""
    m, i_trains, i_stops = {}, [], {}
    with open(IRCTC, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                stops = ast.literal_eval(row["stationList"])
            except Exception:  # noqa: BLE001
                continue
            tn = row["trainNumber"].strip()
            days = ",".join(d.upper() for d in DAYS if row.get(f"trainRunsOn{d}") == "Y")
            srows, dist = [], None
            for s in stops:
                code = fix_code(s.get("stationCode", "").strip().upper())
                n = norm(s.get("stationName", ""))
                if n and code:
                    m.setdefault(n, code)
                arr = s.get("arrivalTime") if ":" in (s.get("arrivalTime") or "") else None
                dep = s.get("departureTime") if ":" in (s.get("departureTime") or "") else None
                try:
                    day = int(s.get("dayCount") or 1)
                    dist = float(s.get("distance") or 0)
                except ValueError:
                    day = 1
                srows.append((tn, code, s.get("stationName", ""),
                              arr, dep, day, len(srows) + 1))
            if len(srows) >= 2:
                i_trains.append((tn, row["trainName"].strip(), len(srows), days, None,
                                 dist, "irctc-2023", "2023-10-15"))
                i_stops[tn] = srows
    irctc_names = len(m)
    try:
        from app.db import connect
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT name, code FROM stations;")
            for name, code in cur.fetchall():
                m.setdefault(norm(name), code)
    except Exception as e:  # noqa: BLE001
        print("  (datameet supplement skipped:", e, ")")
    print(f"  name-map: {irctc_names} from irctc-2023, {len(m)} total; "
          f"irctc-2023 trains parsed: {len(i_trains)}")
    return m, i_trains, i_stops


_stop_re = re.compile(r"(.+?)\s*\(arr=([^,]+),dep=([^)]+)\)")


def parse_time(s):
    s = s.strip()
    if not re.match(r"^\d{1,2}:\d{2}$", s):
        return None
    h, mnt = s.split(":")
    h, mnt = int(h), int(mnt)
    if h > 23 or mnt > 59:
        return None
    return f"{h:02d}:{mnt:02d}"


def parse_fresh(name_map):
    """Yield (train_row, stops_rows). Tracks unmatched station names."""
    trains, all_stops, unmatched = [], [], {}
    spaceless = {k.replace(" ", ""): v for k, v in name_map.items()}
    skeys = sorted(spaceless)

    def fuzzy(q):
        """Unique-prefix match on spaceless names (handles truncations and
        'Terminal/Terminus'-style suffix drift). Requires >=6 chars and a
        single distinct code among candidates."""
        import bisect
        if len(q) < 6:
            return None
        codes = set()
        i = bisect.bisect_left(skeys, q)
        while i < len(skeys) and skeys[i].startswith(q):   # key extends query
            codes.add(spaceless[skeys[i]]); i += 1
        for k in (q[:j] for j in range(len(q), 5, -1)):    # query extends key
            if k in spaceless:
                codes.add(spaceless[k])
                break
        return codes.pop() if len(codes) == 1 else None
    with open(FRESH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tn = row["train_no"].strip()
            raw = row["intermediate_stops"] or ""
            stops, day, prev = [], 1, None
            ok = True
            for part in raw.split(" | "):
                mt = _stop_re.match(part.strip())
                if not mt:
                    continue
                sname, arr_s, dep_s = mt.group(1).strip(), mt.group(2), mt.group(3)
                arr, dep = parse_time(arr_s), parse_time(dep_s)
                code = None
                for v in variants(sname):
                    if isinstance(v, tuple):        # ("__CODE__", code) alias
                        code = v[1]
                    else:
                        q = v.replace(" ", "")
                        code = name_map.get(v) or spaceless.get(q) or fuzzy(q)
                    if code:
                        break
                if not code:
                    unmatched[sname] = unmatched.get(sname, 0) + 1
                    continue
                code = fix_code(code)
                for t in (arr, dep):
                    if t is None:
                        continue
                    tm = int(t[:2]) * 60 + int(t[3:])
                    if prev is not None and tm < prev:
                        day += 1
                    prev = tm
                stops.append((tn, code, sname, arr, dep, day, len(stops) + 1))
            if len(stops) < 2:
                ok = False
            if ok:
                trains.append((tn, row["train_name"].strip(), len(stops),
                               row["days_of_week"], row["classes"],
                               float(row["distance"]) if row["distance"] else None,
                               SOURCE_TAG, LAST_VERIFIED))
                all_stops.extend(stops)
    return trains, all_stops, unmatched


DDL = [
    "DROP TABLE IF EXISTS stops, trains CASCADE;",
    """CREATE TABLE trains (
        number TEXT PRIMARY KEY, name TEXT, num_stops INTEGER DEFAULT 0,
        days_of_week TEXT, classes TEXT, distance_km REAL,
        source TEXT, last_verified DATE);""",
    """CREATE TABLE stops (
        id BIGINT PRIMARY KEY, train_number TEXT, station_code TEXT,
        station_name TEXT, arrival TEXT, departure TEXT, day INTEGER,
        seq INTEGER, source TEXT DEFAULT 'kaggle-2026');""",
]

POST = [
    """UPDATE stations st SET num_trains = COALESCE(c.n, 0) FROM (
        SELECT station_code, COUNT(DISTINCT train_number) n FROM stops GROUP BY station_code
       ) c WHERE st.code = c.station_code;""",
    "UPDATE stations SET num_trains = 0 WHERE code NOT IN (SELECT DISTINCT station_code FROM stops);",
    "CREATE INDEX stops_train_idx ON stops (train_number, seq);",
    "CREATE INDEX stops_station_idx ON stops (station_code);",
    "ANALYZE stops; ANALYZE trains; ANALYZE stations;",
]


def main():
    dry = "--dry-run" in sys.argv
    t0 = time.time()
    print("building station name->code map…")
    name_map, i_trains, i_stops = build_name_map()
    print("parsing fresh-2026…")
    trains, stops, unmatched = parse_fresh(name_map)
    stops = [(*s, SOURCE_TAG) for s in stops]
    # Gap-fill: 2023 trains absent from the 2026 scrape (post-COVID vintage,
    # structured codes + dayCount). Freshest source wins; these only add.
    have = {t[0] for t in trains}
    gap = [t for t in i_trains if t[0] not in have]
    for t in gap:
        trains.append(t)
        stops.extend((*s, "irctc-2023") for s in i_stops[t[0]])
    print(f"  gap-filled from irctc-2023: +{len(gap)} trains")
    total_refs = len(stops) + sum(unmatched.values())
    print(f"  trains kept: {len(trains)}  stops: {len(stops)}")
    print(f"  unmatched station refs: {sum(unmatched.values())}/{total_refs} "
          f"({sum(unmatched.values()) / max(total_refs, 1) * 100:.1f}%)")
    worst = sorted(unmatched.items(), key=lambda x: -x[1])[:10]
    for nme, cnt in worst:
        print(f"    {cnt:5}x {nme}")
    if dry:
        print("dry-run done.")
        return

    from app.db import connect
    print("reloading DB (drops 2016 schedules; stations/cities kept)…")
    with connect() as conn, conn.cursor() as cur:
        for stmt in DDL:
            cur.execute(stmt)
        with cur.copy("COPY trains (number,name,num_stops,days_of_week,classes,distance_km,source,last_verified) FROM STDIN") as cp:
            for t in trains:
                cp.write_row(t)
        with cur.copy("COPY stops (id,train_number,station_code,station_name,arrival,departure,day,seq,source) FROM STDIN") as cp:
            for i, s in enumerate(stops, 1):
                cp.write_row([i, *s])
        conn.commit()
        for stmt in POST:
            cur.execute(stmt)
            conn.commit()
    print(f"DONE in {time.time() - t0:.0f}s — delete data/processed/graph_cache.pkl and restart the API.")


if __name__ == "__main__":
    main()
