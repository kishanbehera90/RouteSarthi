"""Truth benchmark: engine output vs real-world fastest journeys.

Purpose: quantify how far the (2016-era) timetable + heuristics are from
reality on well-known corridors, and act as the acceptance test when newer
data is loaded — re-run and the deviations should shrink.

Run with the API up (uvicorn on :8000):   python etl/benchmark.py

Reference times = fastest scheduled train in 2025-26 (Rajdhani/Shatabdi/VB
class), rounded; approximate on purpose — we're hunting order-of-magnitude
staleness, not minutes.
"""
import httpx

API = "http://127.0.0.1:8000/api/search"

# (from, to, real_fastest_hours, reference train)
BENCHMARKS = [
    ("Delhi", "Mumbai", 15.5, "12952 Mumbai Rajdhani"),
    ("Delhi", "Kolkata", 17.0, "12302 Howrah Rajdhani"),
    ("Delhi", "Madgaon", 24.5, "22414 Goa Rajdhani"),
    ("Mumbai", "Madgaon", 8.0, "22119 Tejas Express"),
    ("Delhi", "Jaipur", 4.5, "12015 Ajmer Shatabdi"),
    ("Delhi", "Bengaluru", 34.0, "22692 Bengaluru Rajdhani"),
    ("Chennai", "Bengaluru", 4.7, "12007 Shatabdi"),
    ("Kolkata", "Puri", 7.5, "12277 Shatabdi (Howrah–Puri)"),
    ("Rourkela", "Ranchi", 4.5, "18108/intercity"),
    ("Lucknow", "Delhi", 6.5, "12003 Shatabdi"),
]


def fastest(from_, to):
    r = httpx.get(API, params={"from": from_, "to": to, "pref": "fastest"}, timeout=60)
    r.raise_for_status()
    routes = r.json().get("routes") or []
    if not routes:
        return None
    best = min(routes, key=lambda x: x["totalTimeMins"])
    return best


def main():
    print(f"{'corridor':28} {'real':>6} {'engine':>7} {'dev':>7}  verdict")
    print("-" * 72)
    devs = []
    for frm, to, real_h, ref in BENCHMARKS:
        best = fastest(frm, to)
        if best is None:
            print(f"{frm+' → '+to:28} {real_h:>5.1f}h {'—':>7}  {'—':>6}  NO ROUTE ❌")
            continue
        eng_h = best["totalTimeMins"] / 60
        dev = (eng_h - real_h) / real_h * 100
        devs.append(abs(dev))
        verdict = "OK" if abs(dev) <= 30 else "SUSPICIOUS"
        print(f"{frm+' → '+to:28} {real_h:>5.1f}h {eng_h:>6.1f}h {dev:>+6.0f}%  {verdict}"
              f"   (₹{best['totalFareInr']}, ref: {ref})")
    if devs:
        print("-" * 72)
        print(f"corridors compared: {len(devs)} · mean |deviation|: {sum(devs)/len(devs):.0f}%"
              f" · worst: {max(devs):.0f}%")


if __name__ == "__main__":
    main()
