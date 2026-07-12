"""Fix mis-identified station stops (data repair).

Background
----------
The timetable name->code matcher (load_v2) sometimes bound a schedule stop to the
WRONG physical station when two stations have similar names. The clearest example:
a train that really stops at "Sangariya" (SGRA, Rajasthan) had that stop matched to
"Sangar" (SGRR, Jammu & Kashmir) — so the train appeared to teleport ~340 km north
and back, and a Gorakhpur train looked like it reached near Katra.

Detection (data-driven, no hand list)
-------------------------------------
For every train, each interior stop has an EXPECTED location: the midpoint of its
two neighbours. Collected across ALL trains that serve a station, those midpoints
cluster tightly around where the station really is. If a station's STORED coordinate
sits far from that cluster in most of its trains, its geo/identity is wrong (this is
distinct from a legitimate reversal junction like Itarsi, which is only an outlier in
some trains and by a small margin).

Repair (high-confidence only)
-----------------------------
For each consistently-wrong station we look for another station whose NAME shares a
long leading prefix AND that sits within REMAP_MAX_KM of the expected location. When
found, that's near-certainly the station the stop meant (SGRR "Sangar" -> SGRA
"Sangaria", 3 km). We remap the affected `stops` rows to the correct code/name and
recompute per-station train counts. Ambiguous cases (no close same-name station) are
NOT auto-remapped here — the engine's geographic-sanity guard (see graph.py) stops
them from ever producing a nonsense route regardless.

Run:
  python -m etl.fix_station_mismatches            # dry run: detect + print, no writes
  python -m etl.fix_station_mismatches --apply     # apply the remap to the DB
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import graph  # noqa: E402
from app.db import connect  # noqa: E402

REMAP_MAX_KM = 10       # a same-name station this close to expected = confident fix
PREFIX_MIN = 5          # names must share this many leading chars to count as "same"
AUDIT = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "station_fixes_audit.json")


def _norm(name):
    return "".join(ch for ch in (name or "").upper() if ch.isalnum())


def _same_name(a, b):
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    n = min(len(na), len(nb))
    if n < PREFIX_MIN:
        return na == nb
    return na[:n] == nb[:n]        # one is a leading-prefix of the other


def detect():
    """Return (remap, flagged). remap: list of dicts for confident fixes;
    flagged: list of all consistently-wrong codes (incl. un-fixable ones).
    Detection itself lives in graph.mislocated_stations (shared with the engine
    guard); here we only add the same-name correction lookup."""
    graph.load()
    H = graph._haversine_km
    NAME = graph.STATION_NAME
    bad = graph.mislocated_stations()

    remap, flagged = [], []
    for code, info in bad.items():
        ex, ey = info["exp"]
        flagged.append((code, NAME.get(code, "?"), info["trains"], info["off_km"]))
        # confident correction: same-name station within REMAP_MAX_KM of expected
        best = None
        for c2, n2, la2, ln2, _cnt in graph.STATIONS:
            if c2 == code or not _same_name(NAME.get(code, ""), n2):
                continue
            dd = H(ey, ex, la2, ln2)
            if best is None or dd < best[0]:
                best = (dd, c2, n2)
        if best and best[0] <= REMAP_MAX_KM:
            remap.append({"bad_code": code, "bad_name": NAME.get(code, ""),
                          "good_code": best[1], "good_name": best[2],
                          "trains": info["trains"], "off_km": info["off_km"],
                          "match_km": round(best[0], 1)})
    remap.sort(key=lambda r: -r["trains"])
    flagged.sort(key=lambda r: -r[2])
    return remap, flagged


def apply_remap(remap):
    """Repoint stops from each bad code to the correct one, in the DB, and
    recompute per-station train counts."""
    with connect() as conn, conn.cursor() as cur:
        total = 0
        for r in remap:
            cur.execute(
                "UPDATE stops SET station_code=%s, station_name=%s WHERE station_code=%s;",
                (r["good_code"], r["good_name"], r["bad_code"]),
            )
            total += cur.rowcount
        # keep num_trains honest for hub classification after the moves
        cur.execute("""UPDATE stations s SET num_trains = COALESCE(sub.c, 0)
                       FROM (SELECT station_code, count(DISTINCT train_number) c
                             FROM stops GROUP BY station_code) sub
                       WHERE s.code = sub.station_code;""")
        conn.commit()
        return total


def main():
    apply_it = "--apply" in sys.argv
    remap, flagged = detect()

    print(f"consistently-mislocated stations: {len(flagged)}")
    print(f"confident remaps (same name within {REMAP_MAX_KM} km): {len(remap)}\n")
    for r in remap:
        print(f"  {r['bad_code']:6s} {r['bad_name'][:22]:22s} -> {r['good_code']:6s} "
              f"{r['good_name'][:22]:22s}  ({r['trains']} trains, off {r['off_km']} km, "
              f"match {r['match_km']} km)")
    unfixed = [f for f in flagged if f[0] not in {r["bad_code"] for r in remap}]
    print(f"\nnot auto-fixed (no close same-name station; engine guard covers these): {len(unfixed)}")
    for code, name, ntr, off in unfixed[:20]:
        print(f"  {code:6s} {name[:24]:24s} {ntr} trains, off {off} km")

    os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
    with open(AUDIT, "w", encoding="utf-8") as f:
        json.dump({"remap": remap, "flagged": [list(x) for x in flagged]}, f, indent=2)
    print(f"\naudit written to {AUDIT}")

    if apply_it:
        moved = apply_remap(remap)
        print(f"\nAPPLIED: {moved} stop rows repointed across {len(remap)} stations.")
        print("Bump graph._CACHE_VERSION so the in-memory graph rebuilds from the DB.")
    else:
        print("\n(dry run — pass --apply to write the remap to the DB)")


if __name__ == "__main__":
    main()
