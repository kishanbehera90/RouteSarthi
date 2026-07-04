"""Generate the train-validity audit checklist (ZERO external API calls).

Picks a stratified sample of trains from our (2016-era) timetable + the exact
trains the flagship demo corridors depend on, and prints what to verify
manually on NTES (enquiry.indianrail.gov.in) or erail.in — does the number
still exist, same name, roughly same departure?

Run with the API up:   python etl/sample_trains.py
"""
import os
import random
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

import httpx  # noqa: E402
from app import graph  # noqa: E402

FLAGSHIPS = [("Rourkela", "Nashik"), ("Bhuj", "Shimla"), ("Imphal", "Bengaluru"),
             ("Delhi", "Mumbai")]


def flagship_trains():
    out = {}
    for frm, to in FLAGSHIPS:
        try:
            r = httpx.get("http://127.0.0.1:8000/api/search",
                          params={"from": frm, "to": to, "pref": "confirmed"}, timeout=60)
            for route in (r.json().get("routes") or [])[:2]:
                for leg in route["legs"]:
                    if leg["mode"] == "train":
                        num = leg["name"].split()[0]
                        out[num] = f"{frm}→{to} demo"
        except Exception as e:  # noqa: BLE001
            print(f"  (skip {frm}→{to}: {e})")
    return out


def describe(num):
    stops = graph.TRAIN_STOPS.get(num)
    if not stops:
        return None
    first, last = stops[0], stops[-1]
    dep = first[2] if first[2] is not None else first[1]
    dep_s = f"{dep // 60:02d}:{dep % 60:02d}" if dep is not None else "--:--"
    return f"{first[0]} {dep_s} → {last[0]} ({len(stops)} halts)"


def main():
    graph.load()
    nums = list(graph.TRAIN_STOPS)
    random.seed(42)  # reproducible sample

    strata = {
        "premium/SF (12xxx/22xxx)": [n for n in nums if n[:2] in ("12", "22") and len(n) == 5],
        "mail/express (1xxxx)": [n for n in nums if n.startswith("1") and n[:2] != "12" and len(n) == 5],
        "passenger (5xxxx)": [n for n in nums if n.startswith("5") and len(n) == 5],
        "other": [n for n in nums if not (n.startswith(("1", "2", "5")) and len(n) == 5)],
    }

    print("TRAIN-VALIDITY AUDIT CHECKLIST — check each on erail.in/train/<number>")
    print("Mark: SAME (exists, ~same schedule) / CHANGED (exists, retimed/renamed)")
    print("      / GONE (number not found)\n")

    i = 0
    print("— Flagship demo trains (these MUST be valid for demos) —")
    for num, why in flagship_trains().items():
        d = describe(num)
        if d:
            i += 1
            print(f"[{i:2}] {num:6} {graph.TRAIN_NAME.get(num, ''):32.32} {d}   ({why})")

    for label, pool in strata.items():
        take = min(5, len(pool))
        if not take:
            continue
        print(f"\n— Random sample: {label} ({len(pool)} in DB) —")
        for num in random.sample(pool, take):
            i += 1
            print(f"[{i:2}] {num:6} {graph.TRAIN_NAME.get(num, ''):32.32} {describe(num)}")

    print(f"\nTotal to check: {i}. Validity % = SAME / total; note every GONE number.")


if __name__ == "__main__":
    main()
