"""Unit tests for app.ratelimit — the in-memory sliding-window limiter.
Pure (no DB), so they always run."""
import time

import pytest
from fastapi import HTTPException

from app import ratelimit


@pytest.fixture(autouse=True)
def _clean():
    ratelimit.reset()
    yield
    ratelimit.reset()


def test_allows_up_to_limit_then_blocks():
    for _ in range(3):
        ratelimit.check("k", limit=3, window_s=60)   # 3 allowed
    with pytest.raises(HTTPException) as ei:
        ratelimit.check("k", limit=3, window_s=60)   # 4th blocked
    assert ei.value.status_code == 429
    assert "Retry-After" in ei.value.headers


def test_keys_are_independent():
    for _ in range(3):
        ratelimit.check("a", limit=3, window_s=60)
    # a different key is unaffected by a's exhausted budget
    ratelimit.check("b", limit=3, window_s=60)


def test_window_slides_old_hits_expire():
    # window of 0s means every prior hit is already outside the window
    ratelimit.check("k", limit=1, window_s=0)
    ratelimit.check("k", limit=1, window_s=0)  # would block within a real window; here it's fine


def test_retry_after_is_positive():
    ratelimit.check("k", limit=1, window_s=30)
    with pytest.raises(HTTPException) as ei:
        ratelimit.check("k", limit=1, window_s=30)
    assert int(ei.value.headers["Retry-After"]) >= 1


class _FakeReq:
    def __init__(self, headers, host):
        self.headers = headers
        self.client = type("C", (), {"host": host})()


def test_client_ip_prefers_forwarded_header():
    req = _FakeReq({"x-forwarded-for": "203.0.113.9, 10.0.0.1"}, "10.0.0.1")
    assert ratelimit.client_ip(req) == "203.0.113.9"


def test_client_ip_falls_back_to_peer():
    req = _FakeReq({}, "192.168.1.5")
    assert ratelimit.client_ip(req) == "192.168.1.5"
