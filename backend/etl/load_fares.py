"""Build the real IRCTC fare lookup  (Phase B, Step 1; refined Phase C —
see ENGINEERING_NOTES P21 for why isotonic regression replaced 50km buckets).

Reads the IRCTC price dump (data/raw/candidates/irctc-2023/price_data.csv,
~124 MB, 326k priced rows) and fits a MONOTONIC (isotonic) regression per
class directly on every (distance, fare) sample — no distance bucketing:
  - uses every sample instead of diluting ~300k rows into ~80 coarse buckets
  - GUARANTEES fare never decreases with distance (real IR tariffs are
    telescopic/non-decreasing; a bucket-median has no such guarantee — two
    adjacent buckets' medians could dip from sampling noise alone)
  - removes the "staircase jump" a banded lookup has at bucket boundaries

We deliberately do NOT hardcode Indian Railways' official per-km tariff rates
from memory — those figures are revised periodically by government notification
and a wrong-but-confident-looking number would be worse than an approximation
honestly grounded in real, scraped IRCTC fares. This fits directly to actual
computed fares instead of trying to reconstruct the formula that produced them.

Writes app/data/fare_table.json: per-class monotonic breakpoints (the actual
step points from sklearn's isotonic PAVA fit — compact, not an arbitrary
resampled grid) + a per-class linear fit as a fallback for distances beyond
the sampled range. metrics.real_fare interpolates between breakpoints; no
sklearn dependency at serve time — the fit happens once, here, at ETL time.

Run:  python -m etl.load_fares          (from backend/, venv active)
"""
import csv
import json
import os
from collections import defaultdict

from sklearn.isotonic import IsotonicRegression

SRC = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "candidates",
                   "irctc-2023", "price_data.csv")
OUT = os.path.join(os.path.dirname(__file__), "..", "app", "data", "fare_table.json")
MIN_SAMPLES = 30     # per class, to trust an isotonic fit at all


def main():
    pts = defaultdict(list)   # class -> [(km, fare)]

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
            pts[cls].append((km, fare))
            n += 1
    print(f"parsed {n:,} priced rows across {len(pts)} classes")

    table, fit = {}, {}
    for cls, arr in pts.items():
        if len(arr) < MIN_SAMPLES:
            continue
        arr.sort()
        xs = [k for k, _ in arr]
        ys = [v for _, v in arr]

        iso = IsotonicRegression(increasing=True)
        iso.fit(xs, ys)
        # X_thresholds_/y_thresholds_ are the ACTUAL step breakpoints the PAVA
        # algorithm found — typically tens to a couple hundred points, not an
        # arbitrary fixed-resolution grid.
        knots = list(zip(iso.X_thresholds_.tolist(), iso.y_thresholds_.tolist()))
        table[cls] = [[round(k, 1), round(v)] for k, v in knots]

        # Linear fit kept as an extrapolation fallback beyond the sampled range.
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        denom = sum((x - mx) ** 2 for x in xs)
        if denom > 0:
            rate = sum((x - mx) * (y - my) for x, y in arr) / denom
            fit[cls] = {"rate": round(rate, 4), "base": round(my - rate * mx, 1)}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"class": table, "fit": fit}, f, indent=0)
    print(f"wrote {OUT}")
    for cls in sorted(table):
        lo, hi = table[cls][0][0], table[cls][-1][0]
        rate_note = f"  fit rate={fit[cls]['rate']:.3f}/km (extrapolation only)" if cls in fit else ""
        print(f"  {cls:4s} {len(table[cls])} breakpoints, {lo:.0f}-{hi:.0f} km{rate_note}")


if __name__ == "__main__":
    main()
