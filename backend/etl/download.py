"""Fetch the AUTO-downloadable raw data, and report the status of the datasets
that must be downloaded MANUALLY (Kaggle needs auth, so we can't script those).

Run from the backend/ directory:
    python etl/download.py

------------------------------------------------------------------------------
AUTO (fetched by this script, all free/open, into data/raw/):
  - stations.json, schedules.json — datameet/railways (CC0). NOTE: ~Aug-2016
    timetable; kept only as a structural backbone / fallback.
  - IN.zip -> IN.txt — GeoNames India gazetteer (CC-BY), updated continuously.

MANUAL (Kaggle — download in a browser, unzip into the paths below):
  - data/raw/candidates/fresh-2026/IRCTC_cleaned.csv
        the CURRENT timetable the engine actually runs on (load_v2.py).
  - data/raw/candidates/irctc-2023/price_data.csv   (~124 MB)
        real IRCTC fares -> app/data/fare_table.json  (load_fares.py).
  - data/raw/candidates/delay/combined_delay.csv     (~1 GB)
    data/raw/candidates/delay/combined_schedule.csv
    data/raw/candidates/delay/train_details.csv
    data/raw/candidates/delay/station_full_names.csv
        a full year of measured delays + a schedule with real per-stop
        distances -> train_delays table, running-day fixes, seasonal-train
        detection, +1,511 extra trains, real distances
        (load_delays.py, load_schedule_extra.py).

FULL REBUILD ORDER (from backend/, venv + .env with DATABASE_URL):
    python etl/download.py            # this script (auto files)
    # ...manually place the Kaggle files above...
    python -m etl.load_v2             # timetable -> trains/stops tables
    python -m etl.load_fares          # price_data.csv -> app/data/fare_table.json
    python -m etl.load_delays         # delays -> train_delays, day+season fixes
    python -m etl.load_schedule_extra # real distances + extra trains
    # graph rebuilds its cache from the DB on next server start.

Idempotent: skips files that already exist (delete them to re-download).
"""
import io
import os
import sys
import zipfile

import httpx

RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")

FILES = {
    "stations.json": "https://raw.githubusercontent.com/datameet/railways/master/stations.json",
    "schedules.json": "https://raw.githubusercontent.com/datameet/railways/master/schedules.json",
}
GEONAMES_ZIP = "https://download.geonames.org/export/dump/IN.zip"

# Kaggle files we cannot auto-fetch (auth); we only check they're present.
MANUAL = [
    ("candidates/fresh-2026/IRCTC_cleaned.csv", "current timetable (load_v2)"),
    ("candidates/irctc-2023/price_data.csv", "real fares (load_fares)"),
    ("candidates/delay/combined_delay.csv", "measured delays (load_delays)"),
    ("candidates/delay/combined_schedule.csv", "real per-stop distances (load_schedule_extra)"),
    ("candidates/delay/train_details.csv", "train names/types (load_schedule_extra)"),
    ("candidates/delay/station_full_names.csv", "station names (load_schedule_extra)"),
]


def fetch(url, dest):
    print(f"downloading {url}")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as r:
        r.raise_for_status()
        total = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
                total += len(chunk)
                print(f"\r  {total / 1e6:,.1f} MB", end="", flush=True)
    print(f"\n  saved -> {dest}")


def main():
    os.makedirs(RAW, exist_ok=True)

    for name, url in FILES.items():
        dest = os.path.join(RAW, name)
        if os.path.exists(dest):
            print(f"skip {name} (exists)")
            continue
        fetch(url, dest)

    in_txt = os.path.join(RAW, "IN.txt")
    if os.path.exists(in_txt):
        print("skip IN.txt (exists)")
    else:
        zpath = os.path.join(RAW, "IN.zip")
        fetch(GEONAMES_ZIP, zpath)
        print("extracting IN.txt…")
        with zipfile.ZipFile(zpath) as z:
            with z.open("IN.txt") as src, open(in_txt, "wb") as out:
                out.write(src.read())
        os.remove(zpath)
        print(f"  saved -> {in_txt}")

    print("\nManual Kaggle datasets (download in a browser - see this file's header):")
    missing = 0
    for rel, what in MANUAL:
        path = os.path.join(RAW, *rel.split("/"))
        if os.path.exists(path):
            size = os.path.getsize(path) / 1e6
            print(f"  [ok]      {rel}  ({size:,.1f} MB) - {what}")
        else:
            missing += 1
            print(f"  [MISSING] {rel} - {what}")
    print(f"\nAuto files ready. {missing} manual file(s) missing." if missing
          else "\nAll auto + manual files present. Next: run the ETL pipeline (see header).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
