"""Shared fixtures. TestClient runs the app in-process (no server needed) and
triggers the lifespan graph warmup. Engine tests skip gracefully when the graph
isn't loaded (e.g. a fresh clone with no .env / data) so the contract tests
still run everywhere.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_ratelimit():
    # TestClient sends every request from the same host ("testclient"), so all
    # auth tests would otherwise share one IP counter and trip the limiter.
    # Reset before each test for isolation (the limiter itself is tested
    # directly in test_ratelimit.py).
    from app import ratelimit
    ratelimit.reset()
    yield


@pytest.fixture(scope="session")
def engine_ready(client):
    try:
        return bool(client.get("/health").json().get("graph", {}).get("loaded"))
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture
def need_engine(engine_ready):
    if not engine_ready:
        pytest.skip("engine graph not loaded (needs backend/.env + data)")
