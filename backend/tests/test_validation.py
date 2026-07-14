"""Contract tests for input validation + rate-limit wiring (steps 1-2 of the
hardening pass). Validation rejections (422) happen before the handler runs, so
these need no DB/graph. The autouse ratelimit reset in conftest keeps the
rate-limit test isolated."""


# --- strict input validation (step 2) ---------------------------------------
def test_search_rejects_unknown_pref(client):
    assert client.get("/api/routes", params={"from": "A", "to": "B", "pref": "bogus"}).status_code == 422


def test_search_rejects_malformed_date(client):
    assert client.get("/api/routes", params={"from": "A", "to": "B", "date": "2026/13/40"}).status_code == 422


def test_search_accepts_valid_iso_date(client):
    # valid shape passes validation (200/place-not-found handled downstream, not 422)
    assert client.get("/api/routes", params={"from": "A", "to": "B", "date": "2026-07-20"}).status_code != 422


def test_search_rejects_overlong_place(client):
    assert client.get("/api/routes", params={"from": "x" * 200, "to": "B"}).status_code == 422


def test_places_rejects_overlong_query(client):
    assert client.get("/api/places", params={"q": "x" * 200}).status_code == 422


def test_signup_rejects_unknown_field(client):
    # extra="forbid": an unexpected field (e.g. a smuggled "role") is rejected
    # outright at validation, before any DB/secret is touched.
    r = client.post("/api/auth/signup",
                    json={"email": "a@b.com", "password": "abcd1234", "name": "x", "role": "admin"})
    assert r.status_code == 422


def test_signup_rejects_short_password(client):
    r = client.post("/api/auth/signup", json={"email": "a@b.com", "password": "short"})
    assert r.status_code == 422


# --- rate-limit wiring (step 1) ---------------------------------------------
def test_public_endpoint_is_rate_limited(client):
    # RL_PUBLIC is 60/min; the 61st call from the same client trips 429.
    codes = [client.get("/api/corridors").status_code for _ in range(62)]
    assert 429 in codes
    assert codes[0] == 200          # early calls succeed


# --- generic error handling (step 5) ----------------------------------------
def test_unhandled_error_never_leaks_internals(monkeypatch):
    # An unexpected error (raw DB error, bug) must return a GENERIC 500 with no
    # traceback / file path / secret in the body — full detail goes to the log.
    from fastapi.testclient import TestClient
    from app import main

    def boom(*a, **k):
        raise RuntimeError("leak: /srv/app/db.py connect user=admin password=hunter2")

    monkeypatch.setattr(main.engine, "get_stored_route", boom)
    # raise_server_exceptions=False so we get the handler's RESPONSE, not the raise
    with TestClient(main.app, raise_server_exceptions=False) as c:
        r = c.get("/api/routes/some-route-id")
    assert r.status_code == 500
    for leaked in ("leak", "hunter2", "db.py", "RuntimeError", "Traceback", "/srv"):
        assert leaked not in r.text
    assert "Something went wrong" in r.json()["detail"]
