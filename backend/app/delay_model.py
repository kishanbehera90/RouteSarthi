"""Serve-time delay prediction — loads the model trained by
etl/train_delay_model.py and turns trip context into a delay distribution.

Loaded once at import into a module global (mirrors metrics._FARE); if the
artifact is absent it stays None and callers fall back to the measured/modelled
tiers, so a fresh clone with no model still works.

We predict a COHERENT distribution (mean + quantiles) and derive everything
from it: p90, on-time % (P<=30), and connection safety (P<=buffer) all read the
SAME predicted CDF, so they can never contradict each other.
"""
import os
import warnings

# Narrow, message-specific: joblib's array reload trips a numpy 2.5
# DeprecationWarning on every predict. Silence only that exact message so it
# doesn't spam per-request logs — unrelated deprecations still surface.
warnings.filterwarnings("ignore", message="Setting the shape on a NumPy array",
                        category=DeprecationWarning)

_PATH = os.path.join(os.path.dirname(__file__), "data", "delay_model.joblib")
_MODEL = None
try:
    import joblib
    _MODEL = joblib.load(_PATH)
except Exception as e:  # noqa: BLE001 — missing artifact / sklearn absent → graceful fallback
    print("delay_model not loaded (using measured/modelled fallback):", e)


def have_model():
    return _MODEL is not None


def _feature_row(ctx):
    """Assemble one feature row in the model's exact FEATURES order from a
    serve-time context dict. Requires only baseline + day-of-week + month (the
    predicted-tier essentials). Position features (dist_from_origin, frac_route)
    are OPTIONAL — passed as NaN when the alighting station's code isn't in the
    routed-distance table (the delay dump and the timetable use partly different
    station codes). HistGradientBoosting handles NaN natively, so prediction
    still fires on baseline + date + scheduled hour, just a touch less precise."""
    if not _MODEL:
        return None
    if ctx.get("baseline") is None or ctx.get("dow") is None or ctx.get("month") is None:
        return None
    nan = float("nan")
    tier_code = _MODEL["tier_code"].get(ctx.get("tier"), 2)
    dist = ctx.get("dist_from_origin")
    total = ctx.get("total_km") or 0
    frac = (dist / total) if (dist is not None and total > 0) else nan
    values = {
        "baseline": float(ctx["baseline"]),
        "tier": tier_code,
        "dist_from_origin": float(dist) if dist is not None else nan,
        "frac_route": float(frac),
        "sched_hour": int(ctx.get("sched_hour", -1)),
        "day_offset": int(ctx.get("day_offset", 0)),
        "dow": int(ctx["dow"]),
        "month": int(ctx["month"]),
    }
    return [[values[f] for f in _MODEL["features"]]]


def predict(ctx):
    """Predict a delay distribution for one leg. `ctx` needs at least
    baseline, dist_from_origin, dow, month (the predicted-tier gate). Returns
    {avgMins, p50, p90, quantiles:{level:mins}} or None to signal fallback."""
    row = _feature_row(ctx)
    if row is None:
        return None
    levels = _MODEL["quantile_levels"]
    qs = {q: float(_MODEL["quantiles"][q].predict(row)[0]) for q in levels}
    # enforce monotonicity — quantile models are fit independently and can cross
    vals = sorted(qs.values())
    qs = {q: v for q, v in zip(levels, vals)}
    avg = float(_MODEL["mean"].predict(row)[0])
    return {
        "avgMins": max(0.0, avg),
        "p50": qs.get(0.5),
        "p90": qs.get(0.9),
        "quantiles": qs,
    }


def cdf(quantiles, x):
    """P(delay <= x) from predicted quantiles, by monotone interpolation.
    quantiles = {level: minutes}. Anchors a lower tail at (0 min, ~0 prob) so
    P(<=30) is well-defined even when p50 is small, and clamps to [0.02,0.99]."""
    if not quantiles:
        return None
    pts = sorted(quantiles.items(), key=lambda kv: kv[1])   # (level, minutes) by minutes
    # prepend a floor anchor: essentially no mass below the 10th pct minus a margin
    lo_level, lo_min = pts[0]
    pts = [(max(0.0, lo_level - 0.10), min(lo_min, 0.0))] + pts
    for i in range(len(pts) - 1):
        (p0, m0), (p1, m1) = pts[i], pts[i + 1]
        if x <= m0:
            return round(max(0.02, min(0.99, p0)), 3)
        if m0 <= x <= m1:
            frac = 0 if m1 == m0 else (x - m0) / (m1 - m0)
            return round(max(0.02, min(0.99, p0 + frac * (p1 - p0))), 3)
    # beyond the top quantile — extrapolate slightly toward 1
    return 0.97
