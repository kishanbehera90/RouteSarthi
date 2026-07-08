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
import json
import math
import os

# --- real IRCTC fare table (built from price_data.csv) ----------------------
# Median totalFare (full fare incl. surcharges + GST) per (class, 50-km band),
# with a per-class linear fit for distances outside the sampled bands. Built by
# etl/build_fares (see scripts). When present, these REAL medians replace the
# modelled per-km fare below and are tagged fareSource="measured".
_FARE_PATH = os.path.join(os.path.dirname(__file__), "data", "fare_table.json")
_FARE = {"band": 50, "class": {}, "fit": {}}
try:
    with open(_FARE_PATH, encoding="utf-8") as _f:
        _FARE = json.load(_f)
except (OSError, ValueError):
    pass


def real_fare(class_code, km):
    """Real IRCTC fare for a class over `km`, or None if we have no data for it.
    Prefers the median of the matching 50-km band; falls back to the per-class
    linear fit; interpolates nothing fancier — bands are dense enough."""
    if km is None or km <= 0:
        return None
    cls = (class_code or "").strip().upper()
    band = _FARE.get("band", 50)
    tbl = _FARE.get("class", {}).get(cls)
    if tbl:
        band_hi = int((km // band) + 1) * band
        # exact band, else nearest sampled band on either side
        if str(band_hi) in tbl:
            return tbl[str(band_hi)]
        keys = sorted(int(k) for k in tbl)
        if keys:
            nearest = min(keys, key=lambda k: abs(k - band_hi))
            if abs(nearest - band_hi) <= 3 * band:
                return tbl[str(nearest)]
    fit = _FARE.get("fit", {}).get(cls)
    if fit:
        return max(30, round(fit["rate"] * km + fit["base"]))
    return None


def have_real_fares():
    return bool(_FARE.get("class"))


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


def leg_delay_profile(train_no, name, km, halts, measured=None):
    """{avgMins, onTimePct, tier, p90, delaySource} for one train leg.

    When `measured` is given (a full year of observed arrivals for this train
    from train_delays: {avgMins, onTimePct, p90, nObs}) we surface those REAL
    numbers and tag delaySource='measured'. Otherwise we fall back to the model
    and tag 'modelled'. Same output shape either way, so the frontend on-time
    bar just renders it."""
    tier = infer_tier(train_no, name)
    if measured and measured.get("nObs", 0) >= 15:
        return {"avgMins": round(measured["avgMins"]), "onTimePct": round(measured["onTimePct"]),
                "tier": tier, "p90": measured.get("p90"), "delaySource": "measured"}
    avg = round(expected_delay(tier, km, halts))
    return {"avgMins": avg, "onTimePct": round(100 * _p_within(ON_TIME_THRESHOLD, avg)),
            "tier": tier, "p90": None, "delaySource": "modelled"}


def connection_safety(buffer_mins, incoming_avg_delay):
    """P(make the transfer) = P(incoming train's delay <= buffer), from the
    ARRIVING train's own delay distribution — not the buffer alone."""
    if buffer_mins is None or buffer_mins < 30:
        return None
    return max(35, min(98, round(100 * _p_within(buffer_mins, incoming_avg_delay))))


def route_reliability(on_time_pct, conn_safety, transfers, first_km, confirmation_pct):
    """Composite 0–100. Weighting reflects what actually ruins a trip:
    getting a *confirmed seat* matters most; for a transfer, *making the
    connection* is critical; a moderate delay matters least (a 20–30 min delay
    rarely breaks a trip, a waitlisted ticket does). First-mile access is a
    minor tie-breaker.

      Direct:   50% confirmation · 30% on-time · 20% access
      Transfer: 38% confirmation · 30% connection-safety · 20% on-time · 12% access
    """
    access = max(30, 100 - (first_km or 0) / 6)
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


def rail_fare(class_code, base_rate, km, tier):
    """Real IRCTC median fare for (class, distance) when we have data; else the
    modelled fare: base per-km (calibrated) + reservation + superfast surcharge
    + GST(AC). Premium trains carry a small real-world premium on top of the
    class median (Rajdhani/Vande Bharat cost more than a plain SF at same km)."""
    real = real_fare(class_code, km)
    if real is not None:
        if tier == "premium":
            real = round(real * 1.12)     # premium trains sit above the median
        return max(60, real)
    fare = km * base_rate
    fare += RESV.get(class_code, 40)
    if tier in ("premium", "superfast"):
        fare += _SUPERFAST.get(class_code, 30)
    if class_code in _AC:
        fare *= (1 + GST_AC)
    return max(60, round(fare))
