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


def _first_train_depart(route):
    for l in route["legs"]:
        if l["mode"] == "train" and l.get("depart"):
            hh, mm = l["depart"].split(":")
            return int(hh) * 60 + int(mm)
    return None


def test_plan_b_next_train_departs_later(client, need_engine):
    # The bug: a route departing 21:30 showed a "next train" Plan B departing
    # 13:45 (already gone). A "miss it -> next train" fallback must depart AT OR
    # AFTER the train you'd be missing.
    import re
    routes = _routes(client, "Gorakhpur", "Prayagraj")["routes"]
    for r in routes:
        pb = r.get("planB") or ""
        m = re.search(r"departing (\d\d):(\d\d)", pb)
        if not m:
            continue
        nxt = int(m.group(1)) * 60 + int(m.group(2))
        own = _first_train_depart(r)
        if own is not None:
            assert nxt >= own, f"planB train departs {m.group(0)} before this route's {own//60:02d}:{own%60:02d}"


def test_transfer_buffer_covers_first_train_typical_delay(client, need_engine):
    # Every multi-train connection must give a buffer that covers the incoming
    # train's TYPICAL (measured p50) delay, capped at 90 min — otherwise you'd
    # miss the transfer more often than not.
    from app import graph
    routes = _routes(client, "Imphal", "Bengaluru")["routes"]
    for r in routes:
        if r.get("transfers", 0) <= 0:
            continue
        t1 = next((l.get("trainNo") for l in r["legs"] if l["mode"] == "train"), None)
        buf = next((l["bufferMins"] for l in r["legs"]
                    if l["mode"] == "connection" and l.get("bufferMins")), None)
        d1 = graph.TRAIN_DELAY.get(t1) if t1 else None
        if d1 and d1.get("p50") is not None and buf is not None:
            assert buf >= min(round(d1["p50"]), 90)


def test_premium_train_class_cleanup(client, need_engine):
    # Rajdhani/Duronto (AC-sleeper) must not list Sleeper/2S; Shatabdi/Vande
    # Bharat (chair-car) must not list AC-sleeper — cleaned from the generic
    # `classes` column.
    from app import engine, graph
    for tn, name in graph.TRAIN_NAME.items():
        u = (name or "").upper()
        cls = set(engine._offered_classes(tn))
        if not cls:
            continue
        if ("RAJDHANI" in u or "DURONTO" in u) and "RAJ" in u.split():
            assert "SL" not in cls and "2S" not in cls
        # chair-car premiums only (exclude the AC-sleeper "Vande Bharat SL")
        if ("VANDE" in u and "SL" not in u.split()) or ("SHATABDI" in u and cls & {"CC", "EC"}):
            assert "1A" not in cls and "SL" not in cls


def test_seasonal_train_is_date_gated(client, need_engine):
    # 5002 GKP JI MAGH MELA ran only in January (Magh Mela). It must be hidden on
    # an undated or off-season search, and surface only when the travel date
    # falls in its window — with a "Seasonal" label.
    import pytest
    from app import graph
    if not graph.is_seasonal("5002"):
        pytest.skip("seasonal data (operating_months) not loaded")

    def find_5002(date=None):
        routes = _routes(client, "Gorakhpur", "Prayagraj", **({"date": date} if date else {}))["routes"]
        for r in routes:
            if any(l.get("trainNo") == "5002" for l in r["legs"]):
                return r
        return None

    assert find_5002(None) is None            # undated search: hidden
    assert find_5002("2026-07-15") is None    # off-season (July): hidden
    inseason = find_5002("2026-01-13")         # Magh Mela season: shown
    assert inseason is not None
    assert "Seasonal" in (inseason["mainTrain"].get("seasonal") or "")


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
    # Salasar<->Sikar has no through train and the towns are close, so a direct
    # cab/bus should win outright. (For Ringas->Salasar, by contrast, training to
    # Sikar first is legitimately faster — Sikar is far closer to Salasar — which
    # is why that pair is NOT a valid "road must win" example.)
    routes = _routes(client, "Salasar", "Sikar", pref="fastest")["routes"]
    assert any(r.get("roadOnly") for r in routes)
    assert routes[0].get("roadOnly")  # fastest for this short hop


def test_no_backtracking_route(client, need_engine):
    # The old bug: Ringas -> cab to Jaipur -> train BACK to Ringas -> cab. No
    # route should alight at the origin's own station.
    for r in _routes(client, "Ringas", "Salasar")["routes"]:
        for l in r["legs"]:
            if l["mode"] == "train":
                assert "RINGAS" not in (l.get("to") or "").upper()
