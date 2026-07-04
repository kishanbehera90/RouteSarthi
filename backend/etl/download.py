"""Download the raw data files the ETL needs into data/raw/ (gitignored).

Run from the backend/ directory:
    python etl/download.py

Sources (all free/open):
  - stations.json, schedules.json — datameet/railways (CC0).
    NOTE: this timetable is from ~Aug 2016 — the freshness plan (see
    PROJECT_LOG 2026-07-02) will layer a newer source + lazy refresh on top.
  - IN.zip → IN.txt — GeoNames India gazetteer (CC-BY), updated continuously.

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

    print("\nAll raw files ready. Next: python etl/load_all.py  (needs backend/.env)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
