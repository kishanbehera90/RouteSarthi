"""Schedule enrichment ETL  (Phase B — 'bigger & better' data).

Reads the Kaggle delay-dump's companion timetable
(data/raw/candidates/delay/combined_schedule.csv, which uniquely carries a REAL
per-stop cumulative `distance_from_origin`) plus train_details.csv and produces:

  1. app/data/train_cumdist.json  — {train_no: {station_code: cum_km}} for every
     train in the dump. engine._rail_km uses these EXACT distances (via
     graph.TRAIN_CUMDIST) instead of haversine × 1.25, so fares/timings for a leg
     use the real routed kilometres.

  2. New trains — any train in the dump not already in our DB is inserted (with
     its stops, restricted to stations we can place on the map), tagged
     source='delay-schedule', classes guessed from type_code. days_of_week is
     left NULL (unknown ⇒ no false "Daily" claim) rather than fabricated.

Run:  python -m etl.load_schedule_extra      (from backend/, venv active)
"""
import csv
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import connect  # noqa: E402

DELAY_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "candidates", "delay")
SCHED = os.path.join(DELAY_DIR, "combined_schedule.csv")
DETAILS = os.path.join(DELAY_DIR, "train_details.csv")
NAMES = os.path.join(DELAY_DIR, "station_full_names.csv")
CUMDIST_OUT = os.path.join(os.path.dirname(__file__), "..", "app", "data", "train_cumdist.json")

# coach classes we can guess from the dump's train type
_CLASSES_BY_TYPE = {
    "RAJ": "1A,2A,3A", "SHT": "CC,EC", "T18": "CC,EC", "GRB": "3A",
    "PRM": "SL,3A,2A", "SF": "2S,SL,3A,2A", "EXP": "2S,SL,3A,2A", "PASS": "2S",
}


def _norm_tn(s):
    s = (s or "").strip()
    return s.lstrip("0") or s


def _classes_for(type_code):
    key = (type_code or "").split("-")[0].upper()
    return _CLASSES_BY_TYPE.get(key, "SL,3A,2A")


def read_schedule():
    """train -> ordered list of dicts {no, code, cum, aday, atime, dday, dtime}."""
    trains = defaultdict(list)
    with open(SCHED, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tn = _norm_tn(row["train_no"])
            try:
                cum = float(row["distance_from_origin"]) if row.get("distance_from_origin") not in ("", None) else None
            except ValueError:
                cum = None
            trains[tn].append({
                "no": int(row["station_no"]) if row["station_no"].isdigit() else len(trains[tn]) + 1,
                "code": (row["station_name"] or "").strip().upper(),
                "cum": cum,
                "aday": row.get("arrival_day") or "1",
                "atime": (row.get("arrival_time") or "").strip(),
                "dday": row.get("departure_day") or "1",
                "dtime": (row.get("departure_time") or "").strip(),
            })
    for tn in trains:
        trains[tn].sort(key=lambda s: s["no"])
    return trains


def main():
    print("reading schedule + details...", flush=True)
    sched = read_schedule()
    details = {}
    with open(DETAILS, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            details[_norm_tn(row["train_no"])] = (row.get("train_name", "").strip(), row.get("type_code", ""))
    fullname = {}
    with open(NAMES, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fullname[(row["station_name"] or "").strip().upper()] = (row.get("station_full_name") or "").strip()

    # --- 1. cumulative-distance sidecar (all trains) ---
    cumdist = {}
    for tn, stops in sched.items():
        d = {s["code"]: s["cum"] for s in stops if s["cum"] is not None and s["code"]}
        if len(d) >= 2:
            cumdist[tn] = d
    os.makedirs(os.path.dirname(CUMDIST_OUT), exist_ok=True)
    with open(CUMDIST_OUT, "w", encoding="utf-8") as f:
        json.dump(cumdist, f, separators=(",", ":"))
    print(f"train_cumdist.json: {len(cumdist):,} trains with real per-stop distances", flush=True)

    # --- 2. insert trains we don't have, using stations we CAN place ---
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT number FROM trains;")
        have_trains = {(n or "").strip() for (n,) in cur.fetchall()}
        cur.execute("SELECT code FROM stations WHERE lat IS NOT NULL;")
        placeable = {(c or "").strip().upper() for (c,) in cur.fetchall()}
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM stops;")
        next_id = cur.fetchone()[0] + 1

        new_trains, new_stops, skipped = [], [], 0
        for tn, stops in sched.items():
            if tn in have_trains:
                continue
            keep = [s for s in stops if s["code"] in placeable]
            if len(keep) < 2:               # not enough placeable stops to route
                skipped += 1
                continue
            name, type_code = details.get(tn, (f"Train {tn}", ""))
            new_trains.append((tn, name or f"Train {tn}", len(keep), None,
                               _classes_for(type_code),
                               keep[-1]["cum"] if keep[-1]["cum"] is not None else None,
                               "delay-schedule", None))
            for i, s in enumerate(keep, start=1):
                new_stops.append((next_id, tn, s["code"], fullname.get(s["code"]) or s["code"],
                                  s["atime"] or None, s["dtime"] or None,
                                  int(s["aday"]) if str(s["aday"]).isdigit() else 1, i, "delay-schedule"))
                next_id += 1

        print(f"new trains to insert: {len(new_trains):,}  (skipped {skipped:,} with <2 placeable stops)", flush=True)
        if new_trains:
            with cur.copy("COPY trains (number,name,num_stops,days_of_week,classes,distance_km,source,last_verified) FROM STDIN") as cp:
                for r in new_trains:
                    cp.write_row(r)
            with cur.copy("COPY stops (id,train_number,station_code,station_name,arrival,departure,day,seq,source) FROM STDIN") as cp:
                for r in new_stops:
                    cp.write_row(r)
        # keep num_trains counts fresh for the new stations' hubs
        cur.execute("""UPDATE stations s SET num_trains = sub.c
                       FROM (SELECT station_code, count(DISTINCT train_number) c FROM stops GROUP BY station_code) sub
                       WHERE s.code = sub.station_code;""")
        conn.commit()
    print(f"inserted {len(new_trains):,} trains, {len(new_stops):,} stops (source=delay-schedule)")


if __name__ == "__main__":
    main()
