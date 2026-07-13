"""Unit tests for app.roads — the optional real-road-routing client (OSRM or
OpenRouteService). Pure functions with a mocked HTTP layer; no live service or
DB needed. This is the module that turns off (returns None, never raises)
whenever neither backend is configured or the configured one is unreachable —
engine.py's fallback path depends on that contract holding exactly."""
import pytest

from app import roads


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    # _disabled_until and _route_cache are module-level state — without
    # resetting them, a result cached (or a failure) in one test could leak
    # into a later test that reuses the same coordinates with a different
    # mocked response.
    roads._disabled_until = 0.0
    roads._route_cache = {}
    yield
    roads._disabled_until = 0.0
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
    # If the user ever switches to self-hosted OSRM later, setting OSRM_URL
    # alone must be enough — no need to also unset ORS_API_KEY.
    monkeypatch.setattr(roads.settings, "osrm_url", "http://example.com:5000")
    monkeypatch.setattr(roads.settings, "ors_api_key", "test-key")
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return _FakeResponse(200, {"code": "Ok", "routes": [{"distance": 1000.0, "duration": 60.0}]})

    monkeypatch.setattr(roads.httpx, "get", fake_get)
    roads.route(28.6, 77.2, 28.5, 77.1)
    assert "openrouteservice" not in calls[0]


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
    roads._disabled_until = 0.0
    fake = _FakeResponse(200, {
        "features": [{"properties": {"summary": {"distance": 1000.0, "duration": 60.0}}}],
    })
    monkeypatch.setattr(roads.httpx, "get", lambda *a, **k: fake)
    assert roads.route(28.6, 77.2, 28.5, 77.1) == {"km": 1.0, "mins": 1.0}
