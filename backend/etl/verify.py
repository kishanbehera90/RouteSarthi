"""Post-load sanity + core-query proof. Run from backend/:  python etl/verify.py

Validates row counts, city geocoding, the PostGIS nearest-railhead query, and
direct-train candidate generation — the exact queries the cross-origin engine
is built on.
"""
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
from app.db import connect  # noqa: E402


def geocode(cur, name):
    cur.execute(
        """SELECT name, lat, lng, population FROM cities
           WHERE lower(asciiname) = lower(%s) OR lower(name) = lower(%s)
           ORDER BY population DESC NULLS LAST LIMIT 1;""",
        (name, name),
    )
    return cur.fetchone()


def nearest_railheads(cur, lat, lng, radius_km=200, limit=10):
    cur.execute(
        """SELECT code, name, num_trains,
                  round((ST_Distance(geom, ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography)/1000)::numeric,1) AS km
           FROM stations
           WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography, %s)
           ORDER BY km ASC LIMIT %s;""",
        (lng, lat, lng, lat, radius_km * 1000, limit),
    )
    return cur.fetchall()


def direct_trains(cur, board_codes, alight_codes, limit=15):
    cur.execute(
        """SELECT s1.train_number, t.name, s1.station_code AS board, s1.departure,
                  s2.station_code AS alight, s2.arrival, (s2.day - s1.day) AS daydiff
           FROM stops s1
           JOIN stops s2 ON s1.train_number = s2.train_number AND s2.seq > s1.seq
           LEFT JOIN trains t ON t.number = s1.train_number
           WHERE s1.station_code = ANY(%s) AND s2.station_code = ANY(%s)
           ORDER BY s1.train_number LIMIT %s;""",
        (board_codes, alight_codes, limit),
    )
    return cur.fetchall()


def main():
    with connect() as conn, conn.cursor() as cur:
        print("=== row counts ===")
        for tbl in ("stations", "trains", "stops", "cities"):
            cur.execute(f"SELECT count(*) FROM {tbl};")
            print(f"  {tbl:10} {cur.fetchone()[0]:,}")

        print("\n=== geocode samples ===")
        for city in ("Rourkela", "Nashik", "Ranchi", "Bhuj", "Imphal"):
            print(f"  {city:10}", geocode(cur, city))

        # Cross-origin demo: Rourkela's nearby railheads vs the Ranchi hub.
        roa = geocode(cur, "Rourkela")
        nsk = geocode(cur, "Nashik")
        if roa and nsk:
            print("\n=== nearest railheads to Rourkela (200km, by distance) ===")
            o_heads = nearest_railheads(cur, roa[1], roa[2])
            for r in o_heads:
                print(f"  {r[0]:6} {r[1][:28]:28} trains={r[2]:>3}  {r[3]} km")

            print("\n=== nearest railheads to Nashik (120km) ===")
            d_heads = nearest_railheads(cur, nsk[1], nsk[2], radius_km=120)
            for r in d_heads:
                print(f"  {r[0]:6} {r[1][:28]:28} trains={r[2]:>3}  {r[3]} km")

            boards = [r[0] for r in o_heads]
            alights = [r[0] for r in d_heads]
            print(f"\n=== direct trains: {len(boards)} board candidates -> {len(alights)} alight candidates ===")
            cands = direct_trains(cur, boards, alights)
            for c in cands:
                print(f"  {c[0]:7} {str(c[1])[:26]:26} {c[2]:5} {str(c[3]):8} -> {c[4]:5} {str(c[5]):8} (+{c[6]}d)")
            if not cands:
                print("  (none — engine will need multi-leg/cross-origin via a farther hub)")


if __name__ == "__main__":
    main()
