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
import math

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


def leg_delay_profile(train_no, name, km, halts):
    """{avgMins, onTimePct, tier} for one train leg — the shape the frontend
    on-time bar already renders."""
    tier = infer_tier(train_no, name)
    avg = round(expected_delay(tier, km, halts))
    return {"avgMins": avg, "onTimePct": round(100 * _p_within(ON_TIME_THRESHOLD, avg)), "tier": tier}


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
    """base per-km (calibrated) + reservation + superfast surcharge + GST(AC)."""
    fare = km * base_rate
    fare += RESV.get(class_code, 40)
    if tier in ("premium", "superfast"):
        fare += _SUPERFAST.get(class_code, 30)
    if class_code in _AC:
        fare *= (1 + GST_AC)
    return max(60, round(fare))
