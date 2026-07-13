"""Reliability / delay / confirmation / fare models.

IMPORTANT — measured vs modelled: none of these are yet fit to *observed* live
data (no historical delay logs or seat/PNR feed on free sources). They are
transparent models driven by REAL train attributes we do have — class/priority,
route length, number of halts, connection buffer, lead time, season — so the
numbers now VARY sensibly per train/route/class instead of being flat
placeholders. This is the planned cold-start; the SAME functions get calibrated
to real numbers once the collector / a Kaggle delay set lands (Step 3).

Everything here is surfaced in the UI with an "est." affordance.
"""
import bisect
import datetime
import json
import math
import os

from . import delay_model

# --- real IRCTC fare table (built from price_data.csv) ----------------------
# Per-class MONOTONIC breakpoints from an isotonic regression fit directly on
# every real (distance, fare) sample — not a 50km-bucket median. Guarantees
# fare never decreases with distance and uses every sample instead of diluting
# ~300k rows into ~80 coarse buckets. Built by etl/load_fares.py (see
# ENGINEERING_NOTES P21 for why). A per-class linear fit covers distances
# beyond the sampled range. When present, these REAL fares replace the
# modelled per-km fare below and are tagged fareSource="measured".
_FARE_PATH = os.path.join(os.path.dirname(__file__), "data", "fare_table.json")
_FARE = {"class": {}, "fit": {}}
try:
    with open(_FARE_PATH, encoding="utf-8") as _f:
        _FARE = json.load(_f)
except (OSError, ValueError):
    pass


def real_fare(class_code, km):
    """Real IRCTC fare for a class over `km`, or None if we have no data for it.
    Linearly interpolates between the class's monotonic breakpoints (dense
    enough, from tens of thousands of real samples per class, that this is a
    smooth curve in practice, not a coarse approximation). Beyond the sampled
    range, extrapolates via the linear fit — but never below the last real
    breakpoint, since fare must keep rising with distance, not dip on
    extrapolation noise."""
    if km is None or km <= 0:
        return None
    cls = (class_code or "").strip().upper()
    pts = _FARE.get("class", {}).get(cls)
    if pts:
        if km <= pts[0][0]:
            return pts[0][1]
        if km >= pts[-1][0]:
            fit = _FARE.get("fit", {}).get(cls)
            if fit:
                return max(pts[-1][1], round(fit["rate"] * km + fit["base"]))
            return pts[-1][1]
        xs = [p[0] for p in pts]
        i = bisect.bisect_right(xs, km)
        (x0, y0), (x1, y1) = pts[i - 1], pts[i]
        if x1 == x0:
            return round(y0)
        return round(y0 + (km - x0) / (x1 - x0) * (y1 - y0))
    fit = _FARE.get("fit", {}).get(cls)
    if fit:
        return max(30, round(fit["rate"] * km + fit["base"]))
    return None


def have_real_fares():
    return bool(_FARE.get("class"))


# --- India demand calendar (festivals + national holidays) ------------------
# Train fares are regulated (fixed distance-slab), so we DON'T fabricate fare
# variation. What genuinely moves on peak dates: (a) flexi-fare premium trains
# (Rajdhani/Shatabdi/Duronto/Vande Bharat) cost more via IRCTC's tier rule, and
# (b) cheaper classes sell out first. This calendar drives an honest "est."
# advisory for both. {"YYYY-MM-DD": {"name","kind": "festival"|"holiday"}}.
_CAL_PATH = os.path.join(os.path.dirname(__file__), "data", "india_calendar.json")
_CALENDAR = {}
try:
    with open(_CAL_PATH, encoding="utf-8") as _cf:
        _CALENDAR = json.load(_cf)
except (OSError, ValueError):
    pass


def demand_level(date_iso):
    """Travel-demand for a date → {score 0-100, label, drivers}. Undated or a
    plain off-peak weekday → score 0 (no advisory, nothing changes)."""
    neutral = {"score": 0, "label": None, "drivers": []}
    if not date_iso:
        return neutral
    try:
        d = datetime.date.fromisoformat(date_iso)
    except (ValueError, TypeError):
        return neutral

    drivers, score = [], 0
    cal = _CALENDAR.get(date_iso)
    if cal:
        if cal.get("kind") == "festival":
            score = max(score, 85)
            drivers.append(f"{cal['name']} (festival)")
        else:
            score = max(score, 70)
            drivers.append(f"{cal['name']}")

    # long weekend: a holiday/festival within one day of this date + a weekend touching it
    if _is_long_weekend(d):
        score = max(score, 60)
        if "long weekend" not in drivers:
            drivers.append("long weekend")
    elif d.weekday() >= 5:
        score = max(score, 35)
        drivers.append("weekend")

    if d.month in _PEAK_MONTHS:
        score = max(score, 25)
        if not drivers:
            drivers.append("peak travel season")

    return {"score": score, "label": drivers[0] if drivers else None, "drivers": drivers}


def _is_long_weekend(d):
    """A weekend day adjacent to a holiday, or a holiday adjacent to a weekend —
    the 3-day-break pattern that spikes travel demand."""
    day = datetime.timedelta(days=1)
    window = [d - day, d, d + day]
    has_holiday = any(n.isoformat() in _CALENDAR for n in window)
    touches_weekend = any(n.weekday() >= 5 for n in window)
    is_holiday_or_weekend = d.isoformat() in _CALENDAR or d.weekday() >= 5
    return has_holiday and touches_weekend and is_holiday_or_weekend


def flexi_fare_multiplier(tier, demand_score):
    """Expected fare multiplier for a travel date. ONLY premium (flexi-fare)
    trains vary — IRCTC's dynamic fare rises in steps as berths fill, capped
    ~1.4×; we key the EXPECTED multiplier to demand (neutral 1.0 → festival
    ~1.34 → cap 1.40). Regulated trains return exactly 1.0 (fare is fixed by
    law — we never invent variation)."""
    if tier != "premium":
        return 1.0
    return round(min(1.40, 1.0 + 0.40 * (max(0, min(100, demand_score)) / 100)), 3)


# --- train class / priority -------------------------------------------------
_PREMIUM_KW = ("RAJDHANI", "SHATABDI", "VANDE BHARAT", "VANDE", "DURONTO",
               "TEJAS", "GATIMAAN", "HUMSAFAR", "GARIB RATH")


def infer_tier(train_no, name):
    u = (name or "").upper()
    if any(k in u for k in _PREMIUM_KW):
        return "premium"
    n = (train_no or "").strip()
    if n[:2] in ("12", "22", "20", "02"):   # superfast number series
        return "superfast"
    if n[:1] == "5":                          # 5xxxx passenger
        return "passenger"
    return "express"


# --- delay model ------------------------------------------------------------
# Expected arrival delay (minutes) grows with route length and halts, and
# depends on train priority. Anchors are order-of-magnitude realistic for IR.
_TIER_BASE_DELAY = {"premium": 10, "superfast": 22, "express": 33, "passenger": 48}
ON_TIME_THRESHOLD = 30   # IR-style "on time" = within 30 min


def expected_delay(tier, km, halts):
    return _TIER_BASE_DELAY.get(tier, 33) + 8.0 * (km or 0) / 1000 + 0.35 * max(0, halts or 0)


def _p_within(minutes, mean):
    """P(delay <= `minutes`) modelled as exponential with the given mean."""
    return 1 - math.exp(-minutes / max(6.0, mean))


def confidence_label(n_obs):
    """Coarse, honest confidence signal from how many real delay observations
    back a number — a prediction refined from 20,000 observed arrivals and one
    refined from 16 look identical without this. Thresholds are round numbers,
    not fit to anything; the point is distinguishing "plenty of evidence" from
    "thin but real" from "none", not precision."""
    if not n_obs:
        return "none"
    if n_obs >= 1000:
        return "high"
    if n_obs >= 100:
        return "moderate"
    return "limited"


def leg_delay_profile(train_no, name, km, halts, measured=None, context=None):
    """{avgMins, onTimePct, tier, p90, delaySource} for one train leg (predicted
    tier also carries p50 + quantiles). Every tier also carries `nObs` (real
    observation count backing the number — 0/None for modelled, since that tier
    has none by definition) and `multiDay` (True when the journey to this stop
    spans 2+ calendar days — the sparsest, least-certain slice regardless of
    which tier ends up being used).

    Three tiers, best first:
      - PREDICTED: an ML model (etl/train_delay_model) conditioned on the trip —
        day-of-week, month, position along the route. Used only on a DATED search
        for a train we have a measured baseline for, and only up to
        delay_model.MAX_RELIABLE_DAY_OFFSET days into the journey (the model's
        own stratified calibration showed it's WORSE than the flat average past
        that point). Everything is derived from one coherent predicted
        distribution (p90, on-time%, connection safety).
      - MEASURED: the train's flat year-long average (train_delays). Undated
        search, a train the model doesn't cover, or a too-far-in journey day.
      - MODELLED: the crude tier/km/halts formula. No real data for this train.
    Same key shape either way, so the frontend on-time bar just renders it."""
    tier = infer_tier(train_no, name)
    has_baseline = bool(measured and measured.get("nObs", 0) >= 15)
    n_obs = measured.get("nObs") if measured else None
    multi_day = bool(context and (context.get("day_offset") or 0) >= 2)

    # 1) predicted — needs a dated context AND a measured baseline to refine
    if (has_baseline and context and context.get("dow") is not None
            and delay_model.have_model()):
        ctx = dict(context)
        ctx["tier"] = tier
        ctx.setdefault("baseline", measured.get("avgMins"))
        dist = delay_model.predict(ctx)
        if dist:
            on_time = delay_model.cdf(dist["quantiles"], ON_TIME_THRESHOLD)
            return {"avgMins": round(dist["avgMins"]),
                    "onTimePct": round(100 * on_time) if on_time is not None else round(measured["onTimePct"]),
                    "tier": tier,
                    "p50": round(dist["p50"]) if dist.get("p50") is not None else None,
                    "p90": round(dist["p90"]) if dist.get("p90") is not None else None,
                    "quantiles": dist["quantiles"], "delaySource": "predicted",
                    "nObs": n_obs, "confidence": confidence_label(n_obs), "multiDay": multi_day}

    # 2) measured
    if has_baseline:
        return {"avgMins": round(measured["avgMins"]), "onTimePct": round(measured["onTimePct"]),
                "tier": tier, "p90": measured.get("p90"), "delaySource": "measured",
                "nObs": n_obs, "confidence": confidence_label(n_obs), "multiDay": multi_day}

    # 3) modelled
    avg = round(expected_delay(tier, km, halts))
    return {"avgMins": avg, "onTimePct": round(100 * _p_within(ON_TIME_THRESHOLD, avg)),
            "tier": tier, "p90": None, "delaySource": "modelled",
            "nObs": 0, "confidence": "none", "multiDay": multi_day}


def predicted_p50(baseline, tier, dow, month, dist_from_origin=None, total_km=0,
                   sched_hour=-1, day_offset=0):
    """Thin wrapper for graph.py's connection-feasibility gate: the predicted
    TYPICAL (p50) delay for a specific dated leg, or None if the model can't
    produce one (no artifact / no baseline / no date). graph.py has no direct
    dependency on delay_model — it calls this instead, so the module
    dependency chain stays one-directional (graph -> metrics -> delay_model,
    never the reverse) and this feature-assembly logic lives in one place."""
    if baseline is None or dow is None or month is None:
        return None
    ctx = {"baseline": baseline, "tier": tier, "dow": dow, "month": month,
           "dist_from_origin": dist_from_origin, "total_km": total_km,
           "sched_hour": sched_hour, "day_offset": day_offset}
    dist = delay_model.predict(ctx)
    return dist["p50"] if dist else None


def connection_safety(buffer_mins, incoming):
    """P(make the transfer) = P(incoming train's delay <= buffer), from the
    ARRIVING train's own delay distribution — not the buffer alone.

    `incoming` is EITHER a predicted quantile dict {level: mins} (→ read the
    coherent CDF at the buffer) OR a scalar average delay (→ exponential
    approximation). The dict path fixes the old split where the displayed % used
    the average but the feasibility gate used p50 — now both read one distribution."""
    if buffer_mins is None or buffer_mins < 30:
        return None
    if isinstance(incoming, dict):
        p = delay_model.cdf(incoming, buffer_mins)
        if p is not None:
            return max(35, min(98, round(100 * p)))
        return None
    return max(35, min(98, round(100 * _p_within(buffer_mins, incoming))))


def access_pct(first_km):
    """First-mile access score used by route_reliability AND by the engine's
    displayed 'First-mile access' breakdown item — one formula, so the number
    shown to the user always matches the number actually scored."""
    return max(30, 100 - (first_km or 0) / 6)


def route_reliability(on_time_pct, conn_safety, transfers, first_km, confirmation_pct):
    """Composite 0–100. Weighting reflects what actually ruins a trip:
    getting a *confirmed seat* matters most; for a transfer, *making the
    connection* is critical; a moderate delay matters least (a 20–30 min delay
    rarely breaks a trip, a waitlisted ticket does). First-mile access is a
    minor tie-breaker.

      Direct:   50% confirmation · 30% on-time · 20% access
      Transfer: 38% confirmation · 30% connection-safety · 20% on-time · 12% access
    """
    access = access_pct(first_km)
    conf = confirmation_pct if confirmation_pct is not None else 70
    if transfers <= 0:
        rel = 0.50 * conf + 0.30 * on_time_pct + 0.20 * access
    else:
        cs = conn_safety if conn_safety is not None else 60
        rel = 0.38 * conf + 0.30 * cs + 0.20 * on_time_pct + 0.12 * access
    return max(25, min(97, round(rel)))


# --- confirmation model -----------------------------------------------------
# No seat/PNR feed on free sources, so this is a demand PROXY: easier classes +
# more lead time raise it; premium trains and peak season lower it. Labelled
# "est." in the UI; replaced by real availability/PNR data in Step 4.
_CLASS_AVAIL = {"2S": 84, "SL": 74, "CC": 72, "3A": 66, "2A": 58, "1A": 54}
_TIER_DEMAND = {"premium": -12, "superfast": -4, "express": 0, "passenger": 8}
_PEAK_MONTHS = {5, 6, 10, 11, 12}   # summer holidays + festival/wedding season


def confirmation_estimate(classes, tier, days_out=None, month=None):
    """(confirmationPct, state). `classes` = coach classes the train offers."""
    base = max((_CLASS_AVAIL.get(c, 68) for c in (classes or [])), default=68)
    adj = _TIER_DEMAND.get(tier, 0)
    lead = 8 if days_out is None else min(16, max(-6, days_out * 0.5))
    peak = -12 if (month in _PEAK_MONTHS) else 0
    pct = max(20, min(96, round(base + adj + lead + peak)))
    state = "confirmed" if pct >= 78 else "rac" if pct >= 55 else "waitlisted"
    return pct, state


# --- fares: real surcharge structure on the calibrated per-km base ----------
_AC = {"1A", "2A", "3A", "3E", "CC", "EC", "EA", "EV"}
# Superfast surcharge by class (₹), applied only to premium/superfast trains.
_SUPERFAST = {"2S": 15, "SL": 30, "3A": 45, "CC": 45, "2A": 45, "1A": 75}
GST_AC = 0.05
RESV = {"2S": 15, "SL": 20, "3A": 40, "CC": 40, "2A": 50, "1A": 60}


def rail_fare(class_code, base_rate, km, tier, demand_mult=1.0):
    """Real IRCTC median fare for (class, distance) when we have data; else the
    modelled fare: base per-km (calibrated) + reservation + superfast surcharge
    + GST(AC). Premium trains carry a small real-world premium on top of the
    class median (Rajdhani/Vande Bharat cost more than a plain SF at same km),
    plus an optional flexi-fare demand multiplier on peak travel dates —
    premium only; regulated fares pass demand_mult through as 1.0."""
    mult = demand_mult if tier == "premium" else 1.0
    real = real_fare(class_code, km)
    if real is not None:
        if tier == "premium":
            real = real * 1.12            # premium trains sit above the median
        return max(60, round(real * mult))
    fare = km * base_rate
    fare += RESV.get(class_code, 40)
    if tier in ("premium", "superfast"):
        fare += _SUPERFAST.get(class_code, 30)
    if class_code in _AC:
        fare *= (1 + GST_AC)
    return max(60, round(fare * mult))
