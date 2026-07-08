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


def test_rail_fare_uses_real_when_available_else_model():
    fare = metrics.rail_fare("SL", 0.58, 500, "express")
    assert fare >= 60
    # AC class costs more than sleeper over the same distance
    assert metrics.rail_fare("2A", 2.10, 800, "express") > metrics.rail_fare("SL", 0.58, 800, "express")


def test_rail_fare_premium_surcharge():
    base = metrics.rail_fare("2A", 2.10, 800, "superfast")
    premium = metrics.rail_fare("2A", 2.10, 800, "premium")
    assert premium >= base                                 # premium trains cost at least as much
