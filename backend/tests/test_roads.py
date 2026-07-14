"""Unit tests for app.roads — the optional real-road-routing client (OSRM or
OpenRouteService). Pure functions with a mocked HTTP layer; no live service or
DB needed. This is the module that turns off (returns None, never raises)
whenever neither backend is configured or the configured one is unreachable —
engine.py's fallback path depends on that contract holding exactly."""
import pytest

from app import roads


@pytest.fixture(autouse=True)
def _reset_circuit_breaker(monkeypatch):
    # _disabled_until (per-backend) and _route_cache are module-level state —
    # without resetting them, a result cached (or a failure) in one test could
    # leak into a later test that reuses the same coordinates with a different
    # mocked response. Also zero every backend key so a real .env can't make a
    # test non-deterministic; individual tests set the ones they exercise.
    monkeypatch.setattr(roads.settings, "osrm_url", "")
    monkeypatch.setattr(roads.settings, "ors_api_key", "")
    monkeypatch.setattr(roads.settings, "geoapify_api_key", "")
    roads._disabled_until = {"osrm": 0.0, "ors": 0.0, "geoapify": 0.0}
    roads._route_cache = {}
    yield
    roads._disabled_until = {"osrm": 0.0, "ors": 0.0, "geoapify": 0.0}
    roads._route_cache = {}


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


def test_have_road_api_false_when_nothing_configured(monkeypatch):
    monkeypatch.setattr(roads.settings, "osrm_url", "")
    monkeypatch.setattr(roads.settings, "ors_api_key", "")
    assert roads.have_road_api() is False


def test_have_road_api_true_with_either_backend(monkeypatch):
    monkeypatch.setattr(roads.settings, "osrm_url", "")
    monkeypatch.setattr(roads.settings, "ors_api_key", "some-key")
    assert roads.have_road_api() is True
    monkeypatch.setattr(roads.settings, "osrm_url", "http://example.com:5000")
    monkeypatch.setattr(roads.settings, "ors_api_key", "")
    assert roads.have_road_api() is True


def test_route_returns_none_when_nothing_configured(monkeypatch):
    monkeypatch.setattr(roads.settings, "osrm_url", "")
    monkeypatch.setattr(roads.settings, "ors_api_key", "")
    assert roads.route(28.6, 77.2, 28.5, 77.1) is None


# --- OpenRouteService (default backend today) -------------------------------
def test_ors_parses_a_successful_response(monkeypatch):
    monkeypatch.setattr(roads.settings, "osrm_url", "")
    monkeypatch.setattr(roads.settings, "ors_api_key", "test-key")
    fake = _FakeResponse(200, {
        "features": [{"properties": {"summary": {"distance": 12345.0, "duration": 900.0}}}],
    })
    monkeypatch.setattr(roads.httpx, "get", lambda *a, **k: fake)
    assert roads.route(28.6, 77.2, 28.5, 77.1) == {"km": 12.345, "mins": 15.0}


def test_ors_returns_none_when_no_features(monkeypatch):
    monkeypatch.setattr(roads.settings, "osrm_url", "")
    monkeypatch.setattr(roads.settings, "ors_api_key", "test-key")
    fake = _FakeResponse(200, {"features": []})
    monkeypatch.setattr(roads.httpx, "get", lambda *a, **k: fake)
    assert roads.route(28.6, 77.2, 28.5, 77.1) is None


# --- self-hosted OSRM (switch-on-later option) -------------------------------
def test_osrm_parses_a_successful_response(monkeypatch):
    monkeypatch.setattr(roads.settings, "osrm_url", "http://example.com:5000")
    fake = _FakeResponse(200, {"code": "Ok", "routes": [{"distance": 12345.0, "duration": 900.0}]})
    monkeypatch.setattr(roads.httpx, "get", lambda *a, **k: fake)
    assert roads.route(28.6, 77.2, 28.5, 77.1) == {"km": 12.345, "mins": 15.0}


def test_osrm_returns_none_on_no_route_found(monkeypatch):
    monkeypatch.setattr(roads.settings, "osrm_url", "http://example.com:5000")
    fake = _FakeResponse(200, {"code": "NoRoute", "routes": []})
    monkeypatch.setattr(roads.httpx, "get", lambda *a, **k: fake)
    assert roads.route(28.6, 77.2, 28.5, 77.1) is None


def test_osrm_takes_priority_over_ors_when_both_configured(monkeypatch):
    # With both configured and OSRM healthy, ORS is never even contacted.
    monkeypatch.setattr(roads.settings, "osrm_url", "http://example.com:5000")
    monkeypatch.setattr(roads.settings, "ors_api_key", "test-key")
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return _FakeResponse(200, {"code": "Ok", "routes": [{"distance": 1000.0, "duration": 60.0}]})

    monkeypatch.setattr(roads.httpx, "get", fake_get)
    roads.route(28.6, 77.2, 28.5, 77.1)
    assert len(calls) == 1
    assert "openrouteservice" not in calls[0]


def test_falls_through_osrm_to_ors_when_osrm_fails(monkeypatch):
    # THE fallback chain: OSRM down -> ORS answers on the SAME call, and the
    # result is ORS's (not None). This is what "OSRM -> ORS -> haversine" means.
    monkeypatch.setattr(roads.settings, "osrm_url", "http://example.com:5000")
    monkeypatch.setattr(roads.settings, "ors_api_key", "test-key")
    seen = []

    def fake_get(url, **kwargs):
        seen.append(url)
        if "example.com:5000" in url:                 # OSRM endpoint -> fail
            raise ConnectionError("osrm refused")
        return _FakeResponse(200, {                    # ORS endpoint -> succeed
            "features": [{"properties": {"summary": {"distance": 5000.0, "duration": 300.0}}}],
        })

    monkeypatch.setattr(roads.httpx, "get", fake_get)
    assert roads.route(28.6, 77.2, 28.5, 77.1) == {"km": 5.0, "mins": 5.0}
    assert any("example.com:5000" in u for u in seen)          # tried OSRM
    assert any("openrouteservice" in u for u in seen)          # then ORS
    # OSRM's breaker is now open; ORS's is not.
    assert roads._disabled_until["osrm"] > 0
    assert roads._disabled_until["ors"] == 0.0


def test_geoapify_parses_a_successful_response(monkeypatch):
    monkeypatch.setattr(roads.settings, "geoapify_api_key", "test-key")
    fake = _FakeResponse(200, {
        "features": [{"properties": {"distance": 8000.0, "time": 600.0}}],
    })
    monkeypatch.setattr(roads.httpx, "get", lambda *a, **k: fake)
    assert roads.route(28.6, 77.2, 28.5, 77.1) == {"km": 8.0, "mins": 10.0}


def test_ors_rate_limited_fails_over_to_geoapify(monkeypatch):
    # THE reason to run both: ORS 429 (daily/minute cap) -> its breaker opens
    # and the SAME call falls through to Geoapify, not to haversine.
    monkeypatch.setattr(roads.settings, "ors_api_key", "ors-key")
    monkeypatch.setattr(roads.settings, "geoapify_api_key", "geo-key")
    seen = []

    def fake_get(url, **kwargs):
        seen.append(url)
        if "openrouteservice" in url:
            return _FakeResponse(429, {})          # ORS rate-limited
        return _FakeResponse(200, {"features": [{"properties": {"distance": 4000.0, "time": 240.0}}]})

    monkeypatch.setattr(roads.httpx, "get", fake_get)
    assert roads.route(28.6, 77.2, 28.5, 77.1) == {"km": 4.0, "mins": 4.0}
    assert any("openrouteservice" in u for u in seen)     # tried ORS
    assert any("geoapify" in u for u in seen)             # failed over to Geoapify
    assert roads._disabled_until["ors"] > 0
    assert roads._disabled_until["geoapify"] == 0.0


def test_returns_none_when_both_backends_fail(monkeypatch):
    # Both down -> None, so the engine falls back to haversine.
    monkeypatch.setattr(roads.settings, "osrm_url", "http://example.com:5000")
    monkeypatch.setattr(roads.settings, "ors_api_key", "test-key")

    def boom(*a, **k):
        raise ConnectionError("refused")

    monkeypatch.setattr(roads.httpx, "get", boom)
    assert roads.route(28.6, 77.2, 28.5, 77.1) is None
    assert roads._disabled_until["osrm"] > 0
    assert roads._disabled_until["ors"] > 0


# --- failure handling + circuit breaker (backend-agnostic) ------------------
def test_route_returns_none_on_network_error(monkeypatch):
    monkeypatch.setattr(roads.settings, "osrm_url", "")
    monkeypatch.setattr(roads.settings, "ors_api_key", "test-key")

    def boom(*a, **k):
        raise ConnectionError("no route to host")

    monkeypatch.setattr(roads.httpx, "get", boom)
    assert roads.route(28.6, 77.2, 28.5, 77.1) is None


def test_route_returns_none_on_http_error_status(monkeypatch):
    monkeypatch.setattr(roads.settings, "osrm_url", "")
    monkeypatch.setattr(roads.settings, "ors_api_key", "test-key")
    fake = _FakeResponse(500, {})
    monkeypatch.setattr(roads.httpx, "get", lambda *a, **k: fake)
    assert roads.route(28.6, 77.2, 28.5, 77.1) is None


def test_circuit_breaker_skips_network_call_after_a_failure(monkeypatch):
    monkeypatch.setattr(roads.settings, "osrm_url", "")
    monkeypatch.setattr(roads.settings, "ors_api_key", "test-key")
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise ConnectionError("refused")

    monkeypatch.setattr(roads.httpx, "get", boom)
    assert roads.route(28.6, 77.2, 28.5, 77.1) is None
    assert len(calls) == 1          # first call actually hit the network and failed

    assert roads.route(28.5, 77.1, 28.4, 77.0) is None
    assert len(calls) == 1          # second call skipped the network entirely — breaker is open


def test_circuit_breaker_recovers_after_cooldown(monkeypatch):
    monkeypatch.setattr(roads.settings, "osrm_url", "")
    monkeypatch.setattr(roads.settings, "ors_api_key", "test-key")
    monkeypatch.setattr(roads.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("refused")))
    assert roads.route(28.6, 77.2, 28.5, 77.1) is None

    # simulate the cooldown having already elapsed
    roads._disabled_until = {"osrm": 0.0, "ors": 0.0, "geoapify": 0.0}
    fake = _FakeResponse(200, {
        "features": [{"properties": {"summary": {"distance": 1000.0, "duration": 60.0}}}],
    })
    monkeypatch.setattr(roads.httpx, "get", lambda *a, **k: fake)
    assert roads.route(28.6, 77.2, 28.5, 77.1) == {"km": 1.0, "mins": 1.0}
