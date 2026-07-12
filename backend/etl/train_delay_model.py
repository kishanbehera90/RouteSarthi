"""Delay-prediction model  (Phase C, item 1 — the first ML model).

`etl/load_delays.py` collapses a full year of arrivals into ONE flat average
per train. But the raw dump has 38.4M dated, per-station observations — enough
to predict delay *conditioned on the trip*: "on a Tuesday in July, ~55 min late
at this station" instead of "this train averages 39 min late".

This script trains a histogram gradient-boosting model (scikit-learn — same
algorithm family as LightGBM, but no native OpenMP wheel to deploy) on
serve-time-safe features only, and serializes it to app/data/delay_model.joblib.
metrics.leg_delay_profile loads it and adds a delaySource="predicted" tier.

We predict a COHERENT DISTRIBUTION, not just a mean: one squared-error model for
the average, plus quantile models at {0.1,0.25,0.5,0.75,0.9}. p90, on-time %
(P(delay<=30)) and connection safety (P(delay<=buffer)) are all derived from
that one predicted CDF, so they can never disagree.

Features (all known at PLAN time — no live upstream delay, which we don't have):
  baseline          train's historical avg delay (train_delays.avg_delay)
  tier              premium/superfast/express/passenger (metrics.infer_tier)  [cat]
  dist_from_origin  km travelled to the alighting station
  frac_route        dist_from_origin / total route km  (position, normalized)
  sched_hour        scheduled arrival clock-hour at that station
  day_offset        journey day (0 = same day, 1 = next day, ...)
  dow               day-of-week of travel                                     [cat]
  month             month of travel                                          [cat]

Run:  python -m etl.train_delay_model      (from backend/, venv active)
"""
import datetime
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import connect  # noqa: E402
from app import metrics  # noqa: E402

_RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "candidates", "delay")
SRC_DELAY = os.path.join(_RAW, "combined_delay.csv")
SRC_SCHED = os.path.join(_RAW, "combined_schedule.csv")
SRC_DETAILS = os.path.join(_RAW, "train_details.csv")
OUT = os.path.join(os.path.dirname(__file__), "..", "app", "data", "delay_model.joblib")

QUANTILES = [0.1, 0.25, 0.5, 0.75, 0.9]
CAP_PER_TRAIN = 400        # reservoir cap per train — bounds memory + stops busy
                           # trains dominating. ~7k trains -> ~2.8M rows target.
DELAY_MIN, DELAY_MAX = -120, 1440   # clamp, matches load_delays
FEATURES = ["baseline", "tier", "dist_from_origin", "frac_route",
            "sched_hour", "day_offset", "dow", "month"]
CAT_FEATURES = ["tier", "dow", "month"]   # non-monotonic — let the model split freely
_TIER_CODE = {"premium": 0, "superfast": 1, "express": 2, "passenger": 3}
DAY3 = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def _norm_tn(s):
    s = (s or "").strip()
    return s.lstrip("0") or s


def _hour(t):
    """'HH:MM' -> hour int, or -1 if blank/bad."""
    if not t or ":" not in t:
        return -1
    try:
        return int(t.split(":")[0])
    except ValueError:
        return -1


def load_baselines():
    """train -> historical avg delay, from the train_delays table (the flat
    number the predicted model refines). Only these trains are predictable at
    serve time, so we train on exactly this set."""
    base = {}
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT train_number, avg_delay FROM train_delays;")
        for tn, avg in cur.fetchall():
            base[_norm_tn(tn)] = float(avg or 0)
    print(f"baselines: {len(base):,} trains from train_delays", flush=True)
    return base


def load_schedule():
    """(train, station_no) -> (dist_from_origin, arr_hour, day_offset); and
    train -> total route km (for frac_route)."""
    sched, total = {}, {}
    with open(SRC_SCHED, encoding="utf-8", newline="") as f:
        f.readline()  # header
        for line in f:
            p = line.rstrip("\n").split(",")
            if len(p) != 8:
                continue
            station_no, _sname, dist_s, arr_day, arr_time, _dep_day, _dep_time, train_no = p
            tn = _norm_tn(train_no)
            try:
                dist = float(dist_s)
                sn = int(station_no)
                day = int(arr_day)
            except ValueError:
                continue
            sched[(tn, sn)] = (dist, _hour(arr_time), day - 1)   # day_offset 0-based
            if dist > total.get(tn, -1):
                total[tn] = dist
    print(f"schedule: {len(sched):,} (train,stop) rows, {len(total):,} trains", flush=True)
    return sched, total


def load_tiers():
    """train -> tier code, via metrics.infer_tier (SAME tiering the engine uses
    at serve time, so training and serving agree)."""
    tiers = {}
    with open(SRC_DETAILS, encoding="utf-8", newline="") as f:
        f.readline()
        for line in f:
            p = line.rstrip("\n").split(",")
            if len(p) < 2:
                continue
            train_no, train_name = p[0], p[1]
            tn = _norm_tn(train_no)
            tiers[tn] = _TIER_CODE[metrics.infer_tier(tn, train_name)]
    print(f"tiers: {len(tiers):,} trains", flush=True)
    return tiers


def stream_sample(baselines, sched, total, tiers):
    """Single pass over the 1 GB dump, reservoir-sampling up to CAP_PER_TRAIN
    feature rows per train (keeps memory flat, stops busy trains dominating)."""
    rng = random.Random(42)
    rows = {}     # train -> list of feature tuples (the reservoir)
    seen = {}     # train -> observations seen so far (for reservoir prob)
    n_lines = kept = 0
    _wd = {}
    with open(SRC_DELAY, encoding="utf-8", newline="") as f:
        f.readline()  # date,station_no,station_name,delay,train_no
        for line in f:
            n_lines += 1
            if n_lines % 5_000_000 == 0:
                print(f"  ...{n_lines:,} rows, {kept:,} sampled", flush=True)
            p = line.rstrip("\n").split(",")
            if len(p) != 5:
                continue
            date_s, station_no, _sname, delay_s, train_no = p
            tn = _norm_tn(train_no)
            baseline = baselines.get(tn)
            if baseline is None:            # not predictable at serve time -> skip
                continue
            if delay_s in ("", "None"):
                continue
            try:
                d = int(float(delay_s))
                sn = int(station_no)
            except ValueError:
                continue
            if not (DELAY_MIN <= d <= DELAY_MAX):
                continue
            sc = sched.get((tn, sn))
            if sc is None:                  # no schedule row -> no features
                continue
            dist, sched_hour, day_offset = sc
            wd = _wd.get(date_s)
            if wd is None:
                try:
                    dt = datetime.date.fromisoformat(date_s)
                    wd = (dt.weekday(), dt.month)
                except ValueError:
                    wd = (-1, -1)
                _wd[date_s] = wd
            dow, month = wd
            if dow < 0:
                continue
            tot = total.get(tn, 0) or 0
            frac = dist / tot if tot > 0 else 0.0
            feat = (baseline, tiers.get(tn, 2), dist, frac,
                    sched_hour, day_offset, dow, month, d)   # last = target
            # reservoir sampling per train
            c = seen.get(tn, 0) + 1
            seen[tn] = c
            bucket = rows.setdefault(tn, [])
            if len(bucket) < CAP_PER_TRAIN:
                bucket.append(feat)
                kept += 1
            else:
                j = rng.randint(0, c - 1)
                if j < CAP_PER_TRAIN:
                    bucket[j] = feat
    print(f"  scanned {n_lines:,} rows; sampled {kept:,} across {len(rows):,} trains", flush=True)
    # flatten
    out = []
    for bucket in rows.values():
        out.extend(bucket)
    return out


def main():
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.model_selection import train_test_split
    import joblib

    print("loading feature sources...", flush=True)
    baselines = load_baselines()
    sched, total = load_schedule()
    tiers = load_tiers()

    print("streaming delay dump (reads ~1 GB, a few minutes)...", flush=True)
    rows = stream_sample(baselines, sched, total, tiers)
    if len(rows) < 10_000:
        print(f"ERROR: only {len(rows)} rows sampled — check data files.", flush=True)
        sys.exit(1)

    df = pd.DataFrame(rows, columns=FEATURES + ["delay"])
    del rows
    print(f"training frame: {len(df):,} rows x {len(FEATURES)} features", flush=True)

    # Fit on plain numpy (no column names) so serve-time prediction from bare
    # arrays doesn't warn about missing feature names — order is FEATURES.
    X = df[FEATURES].to_numpy(dtype="float64")
    y = df["delay"].to_numpy()
    cat_idx = [FEATURES.index(c) for c in CAT_FEATURES]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.15, random_state=42)

    common = dict(max_iter=250, learning_rate=0.08, max_leaf_nodes=31,
                  min_samples_leaf=200, categorical_features=cat_idx,
                  early_stopping=True, validation_fraction=0.1, random_state=42)

    print("training mean model...", flush=True)
    mean_model = HistGradientBoostingRegressor(loss="squared_error", **common).fit(X_tr, y_tr)

    q_models = {}
    for q in QUANTILES:
        print(f"training quantile {q}...", flush=True)
        q_models[q] = HistGradientBoostingRegressor(loss="quantile", quantile=q, **common).fit(X_tr, y_tr)

    # --- evaluation vs the flat-baseline it must beat ---
    pred_mean = mean_model.predict(X_te)
    mae_model = float(np.mean(np.abs(pred_mean - y_te)))
    mae_base = float(np.mean(np.abs(X_te[:, FEATURES.index("baseline")] - y_te)))
    print(f"\nheld-out MAE: model={mae_model:.1f} min  vs  flat-baseline={mae_base:.1f} min  "
          f"({100 * (mae_base - mae_model) / mae_base:+.1f}% vs baseline)", flush=True)

    print("quantile calibration (empirical coverage should ~= nominal):", flush=True)
    for q in QUANTILES:
        cover = float(np.mean(y_te <= q_models[q].predict(X_te)))
        print(f"  q={q}: covered {cover:.3f}", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    joblib.dump({
        "mean": mean_model,
        "quantiles": q_models,
        "quantile_levels": QUANTILES,
        "features": FEATURES,
        "cat_features": CAT_FEATURES,
        "tier_code": _TIER_CODE,
        "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "n_rows": int(len(df)),
        "mae_model": mae_model,
        "mae_baseline": mae_base,
    }, OUT, compress=3)
    size_mb = os.path.getsize(OUT) / 1e6
    print(f"\nsaved {OUT} ({size_mb:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
