"""Unit tests for app.auth — password hashing, JWT sessions, reset tokens.
Hashing/JWT tests are pure (no DB) and always run; signup/login flow tests
need the DB and are gated behind need_engine (see conftest.py)."""
import uuid

import jwt
import pytest

from app import auth
from app.config import settings


@pytest.fixture(autouse=True)
def _secret_key(monkeypatch):
    # Deterministic regardless of the developer's real .env.
    monkeypatch.setattr(settings, "secret_key", "test-secret-do-not-use-in-production-32bytes+")


# --- password hashing --------------------------------------------------------
def test_hash_and_verify_roundtrip():
    h = auth.hash_password("correct-password")
    assert auth.verify_password("correct-password", h)
    assert not auth.verify_password("wrong-password", h)


def test_hash_rejects_password_over_72_bytes():
    with pytest.raises(ValueError):
        auth.hash_password("x" * 100)


# --- JWT sessions -------------------------------------------------------------
def test_token_roundtrip():
    token = auth.create_token(42)
    assert auth.decode_token(token) == 42


def test_decode_token_rejects_garbage():
    with pytest.raises(jwt.PyJWTError):
        auth.decode_token("not-a-real-token")


def test_create_token_requires_secret_key(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "")
    with pytest.raises(RuntimeError):
        auth.create_token(1)


# --- live signup/login flow (needs DB) ---------------------------------------
def _client_auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_user(client, need_engine):
    """Signs up a throwaway user via the real API, yields (email, password,
    token, user), deletes the row afterward so the DB doesn't accumulate
    test users across runs."""
    email = f"test-{uuid.uuid4().hex[:12]}@example.com"
    password = "correct-password-123"
    r = client.post("/api/auth/signup", json={"email": email, "password": password, "name": "Test User"})
    assert r.status_code == 200, r.text
    data = r.json()
    yield {"email": email, "password": password, "token": data["token"], "user": data["user"]}
    from app.db import get_pool
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM saved_trips WHERE user_id=%s;", (data["user"]["id"],))
        cur.execute("DELETE FROM recent_searches WHERE user_id=%s;", (data["user"]["id"],))
        cur.execute("DELETE FROM password_resets WHERE user_id=%s;", (data["user"]["id"],))
        cur.execute("DELETE FROM users WHERE id=%s;", (data["user"]["id"],))
        conn.commit()


def test_signup_then_me(client, test_user):
    r = client.get("/api/auth/me", headers=_client_auth_headers(test_user["token"]))
    assert r.status_code == 200
    assert r.json()["user"]["email"] == test_user["email"]


def test_signup_duplicate_email_rejected(client, test_user):
    r = client.post("/api/auth/signup", json={"email": test_user["email"], "password": "whatever123"})
    assert r.status_code == 400


def test_login_wrong_password_rejected(client, test_user):
    r = client.post("/api/auth/login", json={"email": test_user["email"], "password": "totally-wrong"})
    assert r.status_code == 401


def test_login_correct_password(client, test_user):
    r = client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    assert r.status_code == 200
    assert "token" in r.json()


def test_saved_trips_require_auth(client, need_engine):
    assert client.get("/api/saved-trips").status_code == 401
    assert client.post("/api/saved-trips", json={"route": {"id": "x"}}).status_code == 401


def test_recent_searches_require_auth(client, need_engine):
    assert client.get("/api/recent-searches").status_code == 401


def test_saved_trip_roundtrip(client, test_user):
    headers = _client_auth_headers(test_user["token"])
    route = {"id": "12345-ABC-XYZ", "totalFareInr": 500, "legs": []}
    r = client.post("/api/saved-trips", json={"route": route}, headers=headers)
    assert r.status_code == 200

    r = client.get("/api/saved-trips", headers=headers)
    trips = r.json()["trips"]
    assert any(t["routeId"] == "12345-ABC-XYZ" for t in trips)

    r = client.delete("/api/saved-trips/12345-ABC-XYZ", headers=headers)
    assert r.status_code == 200
    r = client.get("/api/saved-trips", headers=headers)
    assert not any(t["routeId"] == "12345-ABC-XYZ" for t in r.json()["trips"])


def test_recent_search_dedup_case_insensitive(client, test_user):
    headers = _client_auth_headers(test_user["token"])
    client.post("/api/recent-searches", json={"from": "Delhi", "to": "Mumbai"}, headers=headers)
    client.post("/api/recent-searches", json={"from": "delhi", "to": "MUMBAI"}, headers=headers)
    r = client.get("/api/recent-searches", headers=headers)
    matches = [s for s in r.json()["searches"] if s["from"].lower() == "delhi"]
    assert len(matches) == 1  # same pair, different casing -> one row, not two
