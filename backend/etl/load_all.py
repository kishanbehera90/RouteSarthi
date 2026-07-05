"""[DEPRECATED — superseded by load_v2.py] Original datameet-2016 ETL.

DO NOT RUN THIS to rebuild the live DB. It creates a `trains` table WITHOUT the
`days_of_week`/`classes` columns that app/graph.py now requires — running it
would drop those and break the engine at startup. Use `etl/load_v2.py` (the
current May-2026 timetable + IRCTC-2023 gap-fill). Kept only for historical
reference / the stations+cities loading logic reused elsewhere.

Original purpose: load the rail network + city gazetteer into Postgres/PostGIS.
Sources (data/raw/, gitignored): stations.json, schedules.json (datameet CC0);
IN.txt (GeoNames India, CC-BY).
"""
import json
import os
import sys
import time

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.db import connect  # noqa: E402

RAW = os.path.join(BACKEND, "data", "raw")

DDL = [
    "CREATE EXTENSION IF NOT EXISTS postgis;",
    "DROP TABLE IF EXISTS stops, trains, stations, cities CASCADE;",
    """CREATE TABLE stations (
        code TEXT PRIMARY KEY, name TEXT NOT NULL, state TEXT, zone TEXT,
        address TEXT, lat DOUBLE PRECISION, lng DOUBLE PRECISION,
        num_trains INTEGER DEFAULT 0, geom geography(Point,4326));""",
    """CREATE TABLE trains (
        number TEXT PRIMARY KEY, name TEXT, num_stops INTEGER DEFAULT 0);""",
    """CREATE TABLE stops (
        id BIGINT PRIMARY KEY, train_number TEXT, station_code TEXT,
        station_name TEXT, arrival TEXT, departure TEXT, day INTEGER,
        seq INTEGER);""",
    """CREATE TABLE cities (
        id BIGINT PRIMARY KEY, name TEXT, asciiname TEXT, admin1 TEXT,
        population BIGINT DEFAULT 0, feature_code TEXT,
        lat DOUBLE PRECISION, lng DOUBLE PRECISION, geom geography(Point,4326));""",
]

POST = [
    # spatial geometry from lat/lng
    "UPDATE stations SET geom = ST_SetSRID(ST_MakePoint(lng,lat),4326)::geography WHERE lat IS NOT NULL;",
    "UPDATE cities   SET geom = ST_SetSRID(ST_MakePoint(lng,lat),4326)::geography WHERE lat IS NOT NULL;",
    # order stops along each train's route, then per-station train density
    """UPDATE stops s SET seq = sub.rn FROM (
        SELECT id, row_number() OVER (PARTITION BY train_number ORDER BY id) rn FROM stops
       ) sub WHERE s.id = sub.id;""",
    """UPDATE stations st SET num_trains = c.n FROM (
        SELECT station_code, COUNT(DISTINCT train_number) n FROM stops GROUP BY station_code
       ) c WHERE st.code = c.station_code;""",
    "UPDATE trains t SET num_stops = c.n FROM (SELECT train_number, COUNT(*) n FROM stops GROUP BY train_number) c WHERE t.number = c.train_number;",
    # indexes after load
    "CREATE INDEX stations_geom_idx ON stations USING GIST (geom);",
    "CREATE INDEX stations_name_idx ON stations (lower(name));",
    "CREATE INDEX stops_train_idx ON stops (train_number, seq);",
    "CREATE INDEX stops_station_idx ON stops (station_code);",
    "CREATE INDEX cities_geom_idx ON cities USING GIST (geom);",
    "CREATE INDEX cities_name_idx ON cities (lower(asciiname));",
    "CREATE INDEX cities_name_lower_idx ON cities (lower(name));",
    "ANALYZE stations; ANALYZE stops; ANALYZE cities; ANALYZE trains;",
]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_stations(cur):
    data = json.load(open(os.path.join(RAW, "stations.json"), encoding="utf-8"))
    feats = data["features"]
    n = 0
    with cur.copy("COPY stations (code,name,state,zone,address,lat,lng) FROM STDIN") as cp:
        for f in feats:
            p = f.get("properties", {})
            g = f.get("geometry") or {}
            coords = g.get("coordinates") or [None, None]
            code = p.get("code")
            if not code:
                continue
            cp.write_row([code, p.get("name") or code, p.get("state"),
                          p.get("zone"), p.get("address"), coords[1], coords[0]])
            n += 1
    log(f"stations loaded: {n}")


def load_stops_and_trains(cur):
    data = json.load(open(os.path.join(RAW, "schedules.json"), encoding="utf-8"))
    trains = {}
    n = 0
    with cur.copy("COPY stops (id,train_number,station_code,station_name,arrival,departure,day) FROM STDIN") as cp:
        for r in data:
            tn = r.get("train_number")
            if tn and tn not in trains:
                trains[tn] = r.get("train_name")
            def clean(v):
                return None if v in (None, "None", "") else v
            cp.write_row([r.get("id"), tn, r.get("station_code"), r.get("station_name"),
                          clean(r.get("arrival")), clean(r.get("departure")), r.get("day")])
            n += 1
    log(f"stops loaded: {n}")
    with cur.copy("COPY trains (number,name) FROM STDIN") as cp:
        for number, name in trains.items():
            cp.write_row([number, name])
    log(f"trains loaded: {len(trains)}")


def load_cities(cur):
    path = os.path.join(RAW, "IN.txt")
    n = 0
    with cur.copy("COPY cities (id,name,asciiname,admin1,population,feature_code,lat,lng) FROM STDIN") as cp:
        for line in open(path, encoding="utf-8"):
            c = line.rstrip("\n").split("\t")
            if len(c) < 15 or c[6] != "P":  # populated places only
                continue
            try:
                lat, lng = float(c[4]), float(c[5])
            except ValueError:
                continue
            pop = int(c[14]) if c[14].isdigit() else 0
            cp.write_row([int(c[0]), c[1], c[2], c[10], pop, c[7], lat, lng])
            n += 1
    log(f"cities loaded: {n}")


def main():
    t0 = time.time()
    with connect() as conn:
        with conn.cursor() as cur:
            log("running DDL…")
            for stmt in DDL:
                cur.execute(stmt)
            conn.commit()

            log("loading stations…");  load_stations(cur);          conn.commit()
            log("loading stops+trains…"); load_stops_and_trains(cur); conn.commit()
            log("loading cities…");    load_cities(cur);             conn.commit()

            log("post-processing (geom, seq, density, indexes)…")
            for stmt in POST:
                cur.execute(stmt)
                conn.commit()
    log(f"DONE in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    import sys
    if "--force-deprecated" not in sys.argv:
        sys.exit("REFUSED: load_all.py is deprecated and would break the current "
                 "schema. Use `python etl/load_v2.py`. (Override: --force-deprecated)")
    main()
