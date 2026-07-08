"""Build the real IRCTC fare lookup  (Phase B, Step 1).

Reads the IRCTC price dump (data/raw/candidates/irctc-2023/price_data.csv,
~124 MB, 326k priced rows) and writes app/data/fare_table.json — the median
totalFare (full fare incl. all surcharges + GST, straight from IRCTC) per
(class, 50-km band), plus a per-class linear fit for distances outside the
sampled bands. metrics.real_fare / metrics.rail_fare load this at import; when a
(class, distance) is present here it REPLACES the modelled per-km fare and is
tagged fareSource="measured".

Run:  python -m etl.load_fares          (from backend/, venv active)
"""
import csv
import json
import os
import statistics
from collections import defaultdict

SRC = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "candidates",
                   "irctc-2023", "price_data.csv")
OUT = os.path.join(os.path.dirname(__file__), "..", "app", "data", "fare_table.json")
BAND = 50            # km bucket
MIN_SAMPLES = 12     # per (class, band) cell to trust the median


def main():
    cells = defaultdict(list)   # (class, band_hi) -> [fares]
    pts = defaultdict(list)     # class -> [(km, fare)] for the linear fit

    csv.field_size_limit(10_000_000)
    with open(SRC, newline="", encoding="utf-8") as f:
        n = 0
        for row in csv.DictReader(f):
            try:
                fare = float(row["totalFare"])
                km = float(row["distance"])
                cls = (row["classCode"] or "").strip().upper()
            except (ValueError, KeyError, TypeError):
                continue
            if fare <= 0 or km <= 0 or km > 4000 or not cls:
                continue
            band_hi = int((km // BAND) + 1) * BAND
            cells[(cls, band_hi)].append(fare)
            pts[cls].append((km, fare))
            n += 1
    print(f"parsed {n:,} priced rows across {len(pts)} classes")

    table = {}
    for (cls, band_hi), fares in cells.items():
        if len(fares) >= MIN_SAMPLES:
            table.setdefault(cls, {})[str(band_hi)] = round(statistics.median(fares))

    fit = {}
    for cls, arr in pts.items():
        if len(arr) < 30:
            continue
        xs = [k for k, _ in arr]; ys = [v for _, v in arr]
        mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
        denom = sum((x - mx) ** 2 for x in xs)
        if denom == 0:
            continue
        rate = sum((x - mx) * (y - my) for x, y in arr) / denom
        fit[cls] = {"rate": round(rate, 4), "base": round(my - rate * mx, 1)}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"band": BAND, "class": table, "fit": fit}, f, indent=0)
    print(f"wrote {OUT}")
    for cls in sorted(fit):
        print(f"  {cls:4s} fit rate={fit[cls]['rate']:.3f}/km base={fit[cls]['base']:.0f}"
              f"  bands={len(table.get(cls, {}))}")


if __name__ == "__main__":
    main()
