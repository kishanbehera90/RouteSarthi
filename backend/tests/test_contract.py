"""Contract layer — seed endpoints, always available (no DB needed).
These lock the API shapes the frontend depends on (frontend/API_CONTRACT.md)."""


def test_health(client):
    d = client.get("/health").json()
    assert d["status"] == "ok"
    assert "graph" in d


def test_corridors_list(client):
    rows = client.get("/api/corridors").json()
    assert isinstance(rows, list) and len(rows) >= 3
    c = rows[0]
    for key in ("id", "from", "to", "tagline"):
        assert key in c
    assert {"code", "name"} <= set(c["from"])


def test_corridor_detail_and_404(client):
    r = client.get("/api/corridors/rourkela-nashik").json()
    assert r["corridor"]["id"] == "rourkela-nashik"
    assert isinstance(r["routes"], list) and r["routes"]
    assert client.get("/api/corridors/does-not-exist").status_code == 404


def test_route_shape(client):
    routes = client.get("/api/corridors/rourkela-nashik").json()["routes"]
    r = routes[0]
    for key in ("id", "type", "totalTimeMins", "totalFareInr", "reliability", "legs"):
        assert key in r
    assert r["type"] in ("direct", "cross-origin")
    assert any(leg["mode"] == "train" for leg in r["legs"])


def test_seed_route_by_id(client):
    r = client.get("/api/routes/ron-cross-1")
    assert r.status_code == 200
    assert r.json()["id"] == "ron-cross-1"
    assert client.get("/api/routes/nope").status_code == 404
