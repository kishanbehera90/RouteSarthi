"""Measured delays ETL  (Phase B, Step 2).

Streams the Kaggle delay dump (data/raw/candidates/delay/combined_delay.csv,
~1 GB, a full year 2025-02 → 2026-02 of per-station arrival delays) in ONE pass
and produces two things:

  1. train_delays table  — per train: avg / p50 / p80 / p90 delay (min),
     on_time_pct (delay ≤ 30 min), n_obs, source='measured'.  metrics.py uses
     these MEASURED numbers when present and falls back to its model otherwise.

  2. Real running-weekdays — the fresh-2026 source marks 92% of trains "daily"
     (all 7 days) which is wrong. We recover the true service days from the
     ORIGIN departure dates actually observed over the year and correct
     trains.days_of_week where the evidence contradicts "daily".

Delay magnitude is aggregated across ALL stations of a train (more samples, robust);
running-days uses ONLY origin (station_no = 1) rows so overnight rollover to the
next calendar day does not smear a Mon-only train into "Mon+Tue".

Run:  python -m etl.load_delays          (from backend/, venv active)
"""
import csv
import datetime
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import connect  # noqa: E402

SRC = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "candidates", "delay", "combined_delay.csv")
ON_TIME = 30            # min — matches metrics.ON_TIME_THRESHOLD
MIN_OBS = 15           # need this many delay samples to publish measured stats
MIN_ORIGIN = 12        # need this many origin sightings to trust running-days
DAY3 = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def _norm_tn(s):
    s = (s or "").strip()
    return s.lstrip("0") or s


def _pct(hist, q):
    total = sum(hist.values())
    if not total:
        return None
    target = q * total
    cum = 0
    for k in sorted(hist):
        cum += hist[k]
        if cum >= target:
            return k
    return k


def stream():
    """Single pass over the delay dump. Returns (stats, origin_wd)."""
    # train -> [n, sum, on_time_n, {delay:count}]
    stats = defaultdict(lambda: [0, 0, 0, defaultdict(int)])
    # train -> {weekday_index: count}  (origin sightings)
    origin_wd = defaultdict(lambda: defaultdict(int))
    # train -> set of distinct origin dates (for seasonal / special detection)
    origin_dates = defaultdict(set)
    _wd_cache = {}
    n_lines = 0
    with open(SRC, encoding="utf-8", newline="") as f:
        header = f.readline()  # date,station_no,station_name,delay,train_no
        for line in f:
            n_lines += 1
            parts = line.rstrip("\n").split(",")
            if len(parts) != 5:
                continue
            date_s, station_no, _sname, delay_s, train_no = parts
            tn = _norm_tn(train_no)
            if not tn:
                continue
            # delay magnitude (numeric only; blank = no record that day)
            if delay_s not in ("", "None"):
                try:
                    d = int(float(delay_s))
                except ValueError:
                    d = None
                if d is not None and -120 <= d <= 1440:
                    s = stats[tn]
                    s[0] += 1
                    s[1] += d
                    if d <= ON_TIME:
                        s[2] += 1
                    s[3][d] += 1
            # running-day evidence: origin only
            if station_no == "1" and date_s:
                wd = _wd_cache.get(date_s)
                if wd is None:
                    try:
                        wd = datetime.date.fromisoformat(date_s).weekday()
                    except ValueError:
                        wd = -1
                    _wd_cache[date_s] = wd
                if wd >= 0:
                    origin_wd[tn][wd] += 1
                origin_dates[tn].add(date_s)
            if n_lines % 5_000_000 == 0:
                print(f"  ...{n_lines:,} rows", flush=True)
    print(f"  scanned {n_lines:,} rows, {len(stats):,} trains w/ delays, "
          f"{len(origin_wd):,} w/ origin sightings", flush=True)
    return stats, origin_wd, origin_dates


def build_delay_rows(stats):
    rows = []
    for tn, (n, tot, ontime, hist) in stats.items():
        if n < MIN_OBS:
            continue
        rows.append((
            tn, round(tot / n, 1), _pct(hist, 0.50), _pct(hist, 0.80),
            _pct(hist, 0.90), round(100 * ontime / n, 1), n, "measured",
        ))
    return rows


def derive_days(origin_wd):
    """train -> corrected 'MON,TUE,...' string, only where evidence is strong
    enough AND differs from a plain daily assumption."""
    out = {}
    for tn, wd in origin_wd.items():
        total = sum(wd.values())
        if total < MIN_ORIGIN:
            continue
        peak = max(wd.values())
        keep = [i for i in range(7) if wd.get(i, 0) >= max(2, 0.25 * peak)]
        if not keep:
            continue
        out[tn] = ",".join(DAY3[i] for i in sorted(keep))
    return out


# Seasonal / special trains (Magh Mela, festival & holiday specials) run only a
# handful of days in one or two months of the year. We detect them from their
# real operating dates so they can be date-gated in search (shown only near
# their season) instead of appearing as if they run any day.
SEASONAL_MAX_DAYS = 30      # a real regular train runs FAR more days than this
SEASONAL_MAX_MONTHS = 3     # ...and across many months, not just one season


def derive_seasonal(origin_dates):
    """train -> 'MM,MM' operating-months string for trains whose observed
    operation is confined to a short seasonal window; {} for regular trains."""
    out = {}
    for tn, dates in origin_dates.items():
        if not dates:
            continue
        months = {int(d[5:7]) for d in dates if len(d) >= 7}
        if len(dates) <= SEASONAL_MAX_DAYS and 0 < len(months) <= SEASONAL_MAX_MONTHS:
            out[tn] = ",".join(str(m) for m in sorted(months))
    return out


def main():
    print("streaming delay dump (this reads ~1 GB, give it a few minutes)...", flush=True)
    stats, origin_wd, origin_dates = stream()

    rows = build_delay_rows(stats)
    days = derive_days(origin_wd)
    seasonal = derive_seasonal(origin_dates)
    non_daily = sum(1 for v in days.values() if len(v.split(",")) < 7)
    print(f"publishing {len(rows):,} measured-delay rows; "
          f"{len(days):,} trains with evidence, {non_daily:,} genuinely NOT daily; "
          f"{len(seasonal):,} seasonal/special trains detected", flush=True)

    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS train_delays (
                train_number TEXT PRIMARY KEY,
                avg_delay REAL, p50 REAL, p80 REAL, p90 REAL,
                on_time_pct REAL, n_obs INTEGER, source TEXT);
        """)
        cur.execute("TRUNCATE train_delays;")
        with cur.copy("COPY train_delays (train_number,avg_delay,p50,p80,p90,on_time_pct,n_obs,source) FROM STDIN") as cp:
            for r in rows:
                cp.write_row(r)

        # correct running-days ONLY for trains we actually have, and only where
        # the observed pattern differs from what's stored (don't churn correct rows)
        cur.execute("SELECT number, days_of_week FROM trains;")
        have = {(num or "").strip(): (dow or "") for num, dow in cur.fetchall()}
        updates, fixed_daily = [], 0
        for tn, newdays in days.items():
            if tn not in have:
                continue
            cur_days = set(x.strip() for x in have[tn].split(",") if x.strip())
            new_set = set(newdays.split(","))
            if cur_days != new_set:
                updates.append((newdays, tn))
                if len(cur_days) >= 7 and len(new_set) < 7:
                    fixed_daily += 1
        cur.executemany("UPDATE trains SET days_of_week=%s WHERE number=%s;", updates)

        # seasonal window: operating_months for special trains (NULL = year-round)
        cur.execute("ALTER TABLE trains ADD COLUMN IF NOT EXISTS operating_months TEXT;")
        cur.execute("UPDATE trains SET operating_months=NULL;")
        season_updates = [(m, tn) for tn, m in seasonal.items() if tn in have]
        cur.executemany("UPDATE trains SET operating_months=%s WHERE number=%s;", season_updates)
        conn.commit()

    print(f"train_delays: {len(rows):,} rows written")
    print(f"days_of_week: {len(updates):,} trains corrected "
          f"({fixed_daily:,} were wrongly marked daily and now run fewer days)")
    print(f"operating_months: {len(season_updates):,} seasonal/special trains date-gated")


if __name__ == "__main__":
    main()
