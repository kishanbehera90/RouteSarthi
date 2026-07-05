"""Live engine tests over real data. Skipped when the graph isn't loaded.
These lock the behaviour we've debugged into place (P9–P11 regressions)."""


def _routes(client, frm, to, **q):
    return client.get("/api/routes", params={"from": frm, "to": to, **q}).json()


def test_direct_corridor_returns_many(client, need_engine):
    d = _routes(client, "Gorakhpur", "Prayagraj")
    assert len(d["routes"]) >= 8  # not capped at the old 6
    top = d["routes"][0]
    assert top["type"] == "direct" and top["transfers"] == 0
    for key in ("id", "totalTimeMins", "totalFareInr", "reliability", "legs"):
        assert key in top and top[key] not in (None, "")


def test_gorakhpur_resolves_to_up(client, need_engine):
    # The GeoNames duplicate Gorakhpur (Haryana) must NOT win — a UP railhead
    # with a same-named station should (P10).
    d = _routes(client, "Gorakhpur", "Prayagraj")
    board = next(l["from"] for l in d["routes"][0]["legs"] if l["mode"] == "train")
    assert "GORAKHPUR" in board.upper()


def test_reasoning_modes(client, need_engine):
    direct = _routes(client, "Gorakhpur", "Prayagraj")["corridor"].get("reasoning")
    assert direct and direct["mode"] == "direct"
    cross = _routes(client, "Imphal", "Bengaluru")["corridor"].get("reasoning")
    assert cross and cross["mode"] == "cross-origin"
    assert "wins" in cross["conclusion"]


def test_fares_are_sane(client, need_engine):
    for frm, to, lo, hi in [("Delhi", "Mumbai", 200, 5000), ("Gorakhpur", "Prayagraj", 60, 2000)]:
        top = _routes(client, frm, to, pref="cheapest")["routes"][0]
        assert lo <= top["totalFareInr"] <= hi


def test_transfer_route_has_real_connection(client, need_engine):
    routes = _routes(client, "Imphal", "Bengaluru")["routes"]
    tr = next((r for r in routes if r.get("transfers") == 1), None)
    assert tr is not None
    conn = next(l for l in tr["legs"] if l["mode"] == "connection" and l.get("connectionSafetyPct") is not None)
    assert 0 < conn["connectionSafetyPct"] <= 100 and conn["bufferMins"] > 0


def test_weekday_filter_does_not_crash(client, need_engine):
    d = _routes(client, "Delhi", "Mumbai", date="2026-07-06")
    assert isinstance(d["routes"], list)


def test_direct_route_id_rebuilds(client, need_engine):
    top = _routes(client, "Gorakhpur", "Prayagraj")["routes"][0]
    got = client.get(f"/api/routes/{top['id']}")
    assert got.status_code == 200 and got.json()["id"] == top["id"]


def test_main_train_and_class_fares(client, need_engine):
    top = _routes(client, "Gorakhpur", "Prayagraj")["routes"][0]
    mt = top["mainTrain"]
    assert mt["name"] and mt["depart"] and mt["arrive"]
    fares = mt["classFares"]
    assert len(fares) >= 1
    assert fares == sorted(fares, key=lambda f: f["fareInr"])  # cheapest first
    assert {"code", "label", "fareInr"} <= set(fares[0])


def test_places_cities_first_with_states(client, need_engine):
    places = client.get("/api/places", params={"q": "gorakh"}).json()["places"]
    assert places
    # Cities lead (travel planner), both Gorakhpurs surface, disambiguated.
    assert any(p["state"] == "Uttar Pradesh" for p in places)
    assert any(p["state"] == "Haryana" for p in places)
    assert all(p["state"] != "Railway station" for p in places)  # no ugly label


def test_station_only_town_is_searchable(client, need_engine):
    # Ringas is absent from GeoNames but is a station — still findable + routable.
    places = client.get("/api/places", params={"q": "ringas"}).json()["places"]
    assert any("ringas" in p["name"].lower() for p in places)
    assert len(_routes(client, "Ringas", "Jaipur")["routes"]) >= 1


def test_direct_road_option_for_short_hop(client, need_engine):
    # A travel planner must offer (and often prefer) direct road for short trips.
    routes = _routes(client, "Ringas", "Salasar", pref="fastest")["routes"]
    assert any(r.get("roadOnly") for r in routes)
    assert routes[0].get("roadOnly")  # fastest for this short hop


def test_no_backtracking_route(client, need_engine):
    # The old bug: Ringas -> cab to Jaipur -> train BACK to Ringas -> cab. No
    # route should alight at the origin's own station.
    for r in _routes(client, "Ringas", "Salasar")["routes"]:
        for l in r["legs"]:
            if l["mode"] == "train":
                assert "RINGAS" not in (l.get("to") or "").upper()
