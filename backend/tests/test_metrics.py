"""Unit tests for app.metrics — the delay / confirmation / fare / reliability
models. Pure functions, no DB, so these always run."""
from app import metrics


# --- tier inference ---------------------------------------------------------
def test_infer_tier_premium_by_name():
    assert metrics.infer_tier("12951", "MUMBAI RAJDHANI") == "premium"
    assert metrics.infer_tier("22435", "VANDE BHARAT EXP") == "premium"


def test_infer_tier_by_number_series():
    assert metrics.infer_tier("12345", "SOME EXP") == "superfast"
    assert metrics.infer_tier("54321", "SOME PASS") == "passenger"
    assert metrics.infer_tier("19037", "AVADH EXP") == "express"


# --- delay model + measured override ---------------------------------------
def test_expected_delay_grows_with_distance_and_halts():
    short = metrics.expected_delay("express", 200, 3)
    long = metrics.expected_delay("express", 2000, 30)
    assert long > short
    # premium is more punctual than passenger over the same route
    assert metrics.expected_delay("premium", 1000, 10) < metrics.expected_delay("passenger", 1000, 10)


def test_leg_delay_profile_modelled_vs_measured():
    modelled = metrics.leg_delay_profile("19038", "AVADH EXP", 1200, 20)
    assert modelled["delaySource"] == "modelled"
    assert 0 <= modelled["onTimePct"] <= 100

    measured = metrics.leg_delay_profile(
        "19038", "AVADH EXP", 1200, 20,
        measured={"avgMins": 122, "onTimePct": 26, "p90": 276, "nObs": 31558})
    assert measured["delaySource"] == "measured"
    assert measured["avgMins"] == 122
    assert measured["onTimePct"] == 26
    assert measured["p90"] == 276


def test_leg_delay_profile_ignores_thin_measured():
    # too few observations -> fall back to the model, don't trust noise
    prof = metrics.leg_delay_profile("19038", "AVADH EXP", 1200, 20,
                                     measured={"avgMins": 5, "onTimePct": 99, "nObs": 3})
    assert prof["delaySource"] == "modelled"


# --- connection safety ------------------------------------------------------
def test_connection_safety_needs_min_buffer():
    assert metrics.connection_safety(20, 30) is None      # < 30 min buffer
    assert metrics.connection_safety(None, 30) is None


def test_connection_safety_bounded_and_monotonic():
    tight = metrics.connection_safety(35, 60)
    roomy = metrics.connection_safety(180, 60)
    assert 35 <= tight <= 98 and 35 <= roomy <= 98
    assert roomy > tight                                   # more buffer = safer


def test_connection_safety_quantile_path():
    # A predicted arriving train passes its quantile dict -> P(delay <= buffer)
    # from the coherent CDF. More buffer must be at least as safe.
    q = {0.1: 0, 0.25: 5, 0.5: 15, 0.75: 40, 0.9: 80}
    tight = metrics.connection_safety(30, q)
    roomy = metrics.connection_safety(120, q)
    assert 35 <= tight <= 98 and 35 <= roomy <= 98
    assert roomy >= tight
    assert metrics.connection_safety(20, q) is None        # still gated under 30 min


# --- demand advisory (fares are regulated; only premium/flexi & scarcity move) ---
def test_demand_level_neutral_when_undated_or_offpeak():
    assert metrics.demand_level(None)["score"] == 0
    assert metrics.demand_level("")["score"] == 0
    # a plain mid-week non-festival day
    assert metrics.demand_level("2026-07-14")["score"] == 0


def test_demand_level_ranks_festival_above_weekend():
    weekend = metrics.demand_level("2026-07-18")["score"]      # a Saturday
    festival = metrics.demand_level("2026-11-08")["score"]     # Diwali
    assert 0 < weekend < festival
    assert "Diwali" in (metrics.demand_level("2026-11-08")["label"] or "")


def test_flexi_multiplier_premium_only_and_monotonic():
    assert metrics.flexi_fare_multiplier("express", 90) == 1.0     # regulated: never moves
    assert metrics.flexi_fare_multiplier("premium", 0) == 1.0      # neutral date: no surge
    hi = metrics.flexi_fare_multiplier("premium", 90)
    mid = metrics.flexi_fare_multiplier("premium", 40)
    assert 1.0 < mid < hi <= 1.40                                  # rises with demand, capped


def test_rail_fare_demand_lifts_premium_not_regulated():
    # same class/distance: a festival multiplier lifts a premium train's fare
    # but leaves a regulated express untouched.
    prem_off = metrics.rail_fare("2A", 2.10, 800, "premium", 1.0)
    prem_peak = metrics.rail_fare("2A", 2.10, 800, "premium", 1.34)
    exp_off = metrics.rail_fare("2A", 2.10, 800, "express", 1.0)
    exp_peak = metrics.rail_fare("2A", 2.10, 800, "express", 1.34)
    assert prem_peak > prem_off
    assert exp_peak == exp_off


# --- delay profile tiers + CDF ----------------------------------------------
def test_leg_delay_profile_modelled_without_data():
    # no measured baseline, no context -> crude modelled fallback
    prof = metrics.leg_delay_profile("19038", "AVADH EXP", 1200, 20)
    assert prof["delaySource"] == "modelled"
    assert 0 <= prof["onTimePct"] <= 100


def test_leg_delay_profile_measured_when_no_context():
    # measured baseline present but undated search (no context) -> measured tier,
    # never predicted (prediction needs the trip's day-of-week)
    measured = {"avgMins": 40, "onTimePct": 55, "p90": 120, "nObs": 5000}
    prof = metrics.leg_delay_profile("12951", "MUMBAI RAJDHANI", 1400, 15, measured=measured)
    assert prof["delaySource"] == "measured"
    assert prof["nObs"] == 5000
    assert prof["confidence"] == "high"


# --- confidence signal + multi-day uncertainty flag --------------------------
def test_confidence_label_thresholds():
    assert metrics.confidence_label(0) == "none"
    assert metrics.confidence_label(None) == "none"
    assert metrics.confidence_label(50) == "limited"
    assert metrics.confidence_label(500) == "moderate"
    assert metrics.confidence_label(5000) == "high"


def test_leg_delay_profile_modelled_has_no_confidence():
    prof = metrics.leg_delay_profile("19038", "AVADH EXP", 1200, 20)
    assert prof["nObs"] == 0
    assert prof["confidence"] == "none"


def test_leg_delay_profile_flags_multiday_regardless_of_tier():
    # The multi-day uncertainty flag is about the JOURNEY, not which delay tier
    # ends up being used — a modelled leg on day 3 is just as uncertain as a
    # measured one would be.
    prof = metrics.leg_delay_profile("19038", "AVADH EXP", 1200, 20,
                                      context={"dow": 1, "month": 6, "day_offset": 2})
    assert prof["multiDay"] is True
    prof2 = metrics.leg_delay_profile("19038", "AVADH EXP", 1200, 20,
                                       context={"dow": 1, "month": 6, "day_offset": 0})
    assert prof2["multiDay"] is False


def test_delay_model_cdf_monotone_and_bounded():
    from app import delay_model
    q = {0.1: 0, 0.25: 5, 0.5: 15, 0.75: 40, 0.9: 80}
    lo = delay_model.cdf(q, 10)
    hi = delay_model.cdf(q, 90)
    assert 0.02 <= lo <= hi <= 0.99
    assert delay_model.cdf(q, 15) >= delay_model.cdf(q, 5)


# --- mean-vs-quantile coherence (P20 regression) -----------------------------
# A user spotted a leg where "average delay" looked bigger than the connection
# buffer, next to a connection-safety % that made it look like the two numbers
# disagreed. Root cause: the average and the quantiles came from two
# INDEPENDENTLY trained models with no guaranteed relationship. Fix: derive the
# average by integrating the quantile curve itself — these tests guard against
# that separation ever being reintroduced.
def test_mean_from_quantiles_matches_symmetric_distribution():
    from app import delay_model
    # A roughly symmetric spread around 50 should integrate close to 50.
    q = {0.1: 20, 0.25: 35, 0.5: 50, 0.75: 65, 0.9: 80, 0.99: 95}
    mean = delay_model.mean_from_quantiles(q)
    assert 40 <= mean <= 60


def test_mean_from_quantiles_reflects_right_skew():
    # A heavily right-skewed distribution (typical of real train delays: most
    # trips are fine, a tail is catastrophic) must show mean > median — the
    # exact shape that made this bug look like a contradiction, except now
    # it's read off ONE curve instead of a second, unrelated model.
    from app import delay_model
    q = {0.1: 0, 0.25: 10, 0.5: 30, 0.75: 60, 0.9: 150, 0.99: 500}
    mean = delay_model.mean_from_quantiles(q)
    assert mean > q[0.5]


def test_mean_from_quantiles_never_negative():
    from app import delay_model
    q = {0.1: -5, 0.25: -1, 0.5: 2, 0.75: 10, 0.9: 20, 0.99: 40}
    assert delay_model.mean_from_quantiles(q) >= 0


def test_predict_refuses_multiday_journeys():
    # Stratified calibration on the trained model showed p50-MAE of 70.7 min
    # for day_offset>=2 (multi-day journeys) — worse than the ~29 min flat
    # baseline. The model must refuse to predict there so a demonstrably worse
    # number can't override the measured/modelled fallback.
    from app import delay_model
    import pytest
    if not delay_model.have_model():
        pytest.skip("delay_model.joblib not present")
    ctx = {"baseline": 60, "tier": "express", "dow": 2, "month": 6,
           "dist_from_origin": None, "total_km": 0, "sched_hour": 10, "day_offset": 2}
    assert delay_model.predict(ctx) is None
    ctx["day_offset"] = 1
    assert delay_model.predict(ctx) is not None


def test_predict_avg_is_derived_from_its_own_quantiles():
    # Structural guard: predict()'s avgMins must equal mean_from_quantiles of
    # the SAME quantiles dict it returns — not an independent model's output.
    # If someone reintroduces a separately-fit mean model, this fails.
    from app import delay_model
    import pytest
    if not delay_model.have_model():
        pytest.skip("delay_model.joblib not present")
    ctx = {"baseline": 60, "tier": "express", "dow": 2, "month": 6,
           "dist_from_origin": None, "total_km": 0, "sched_hour": 10, "day_offset": 0}
    dist = delay_model.predict(ctx)
    assert dist is not None
    expected = delay_model.mean_from_quantiles(dist["quantiles"])
    assert abs(dist["avgMins"] - max(0.0, expected)) < 1e-6


# --- first-mile access (shared by route_reliability AND the engine's
# displayed "First-mile access" breakdown item — must stay in sync) ---------
def test_access_pct_bounded_and_decreasing_with_distance():
    near = metrics.access_pct(5)
    far = metrics.access_pct(300)
    assert near > far                                      # closer access scores higher
    assert 30 <= far <= 100                                 # floors at 30, never negative
    assert metrics.access_pct(None) == 100                  # no first-mile at all = perfect access


# --- route reliability ------------------------------------------------------
def test_route_reliability_bounds():
    lo = metrics.route_reliability(10, None, 0, 300, 20)
    hi = metrics.route_reliability(99, 98, 0, 0, 96)
    assert 25 <= lo <= 97 and 25 <= hi <= 97
    assert hi > lo


def test_route_reliability_transfer_weighs_connection():
    safe = metrics.route_reliability(80, 95, 1, 10, 80)
    risky = metrics.route_reliability(80, 40, 1, 10, 80)
    assert safe > risky                                    # connection safety matters on transfers


# --- confirmation model -----------------------------------------------------
def test_confirmation_more_leadtime_helps():
    near = metrics.confirmation_estimate(["SL", "3A"], "express", days_out=1)[0]
    far = metrics.confirmation_estimate(["SL", "3A"], "express", days_out=30)[0]
    assert far >= near


def test_confirmation_state_thresholds():
    _, state = metrics.confirmation_estimate(["2S"], "passenger", days_out=30)
    assert state in ("confirmed", "rac", "waitlisted")
    pct, _ = metrics.confirmation_estimate(["1A"], "premium", days_out=0, month=5)
    assert 20 <= pct <= 96


# --- fares ------------------------------------------------------------------
def test_real_fare_monotonic_in_distance():
    f500 = metrics.real_fare("SL", 500)
    f1500 = metrics.real_fare("SL", 1500)
    if f500 and f1500:                                     # only if the table is present
        assert f1500 > f500


# --- isotonic fare curve (P21): dense monotonic interpolation, not 50km buckets ---
def test_real_fare_strictly_non_decreasing_across_a_dense_scan():
    # The whole point of isotonic regression over bucket-medians: fare must
    # never dip anywhere, not just at a couple of hand-picked distances.
    if not metrics.have_real_fares():
        return
    prev = 0
    for km in range(50, 3000, 25):
        fare = metrics.real_fare("SL", km)
        if fare is None:
            continue
        assert fare >= prev, f"fare dipped at {km} km: {fare} < {prev}"
        prev = fare


def test_real_fare_extrapolation_never_dips_below_last_real_point():
    # Beyond the sampled range we extrapolate via the linear fit, but it must
    # never fall below the last real (isotonic) breakpoint.
    if not metrics.have_real_fares():
        return
    far_beyond = metrics.real_fare("SL", 5000)
    pts = metrics._FARE.get("class", {}).get("SL")
    if far_beyond is not None and pts:
        assert far_beyond >= pts[-1][1]


def test_rail_fare_uses_real_when_available_else_model():
    fare = metrics.rail_fare("SL", 0.58, 500, "express")
    assert fare >= 60
    # AC class costs more than sleeper over the same distance
    assert metrics.rail_fare("2A", 2.10, 800, "express") > metrics.rail_fare("SL", 0.58, 800, "express")


def test_rail_fare_premium_surcharge():
    base = metrics.rail_fare("2A", 2.10, 800, "superfast")
    premium = metrics.rail_fare("2A", 2.10, 800, "premium")
    assert premium >= base                                 # premium trains cost at least as much
