"""A tiny in-memory sliding-window rate limiter for the auth endpoints.

Why in-memory (and not Redis): the same "no extra infra, degrade gracefully"
ethos as the rest of the app — Redis is still deferred. The tradeoff is that
limits are PER-PROCESS, so with N uvicorn workers the effective limit is N×.
For a small single/low-worker deploy that's fine; the moment this runs behind
several workers, move the counters to Redis (the call sites here don't change,
only this module's storage). This is a real brute-force speed bump, not a
distributed guarantee.

Usage (from an endpoint that has the FastAPI Request):
    ratelimit.check(f"login:ip:{client_ip(request)}", limit=10, window_s=300)
raises HTTPException(429) when the caller has exceeded `limit` hits in the
trailing `window_s` seconds.
"""
import threading
import time

from fastapi import HTTPException, Request

_hits: dict[str, list[float]] = {}
_lock = threading.Lock()
_last_prune = 0.0


def client_ip(request: Request) -> str:
    """Best-effort client IP. Honours the FIRST X-Forwarded-For hop when present
    (set by a deploy proxy / load balancer); falls back to the socket peer.
    Note: X-Forwarded-For is client-spoofable UNLESS a trusted proxy overwrites
    it — which is the normal deployed setup (Render/Railway/Fly/nginx all do).
    Locally there's no proxy, so this is just request.client.host."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune(now: float) -> None:
    """Drop keys whose newest hit is older than 1 hour, so the dict can't grow
    unbounded from one-off IPs. Cheap and only runs at most once a minute."""
    global _last_prune
    if now - _last_prune < 60:
        return
    _last_prune = now
    stale = [k for k, ts in _hits.items() if not ts or now - ts[-1] > 3600]
    for k in stale:
        _hits.pop(k, None)


def check(key: str, limit: int, window_s: int) -> None:
    """Record a hit for `key` and raise HTTPException(429) if it now exceeds
    `limit` within the trailing `window_s` seconds."""
    now = time.monotonic()
    with _lock:
        _prune(now)
        cutoff = now - window_s
        ts = [t for t in _hits.get(key, ()) if t > cutoff]
        ts.append(now)
        _hits[key] = ts
        if len(ts) > limit:
            retry = int(ts[0] + window_s - now) + 1
            raise HTTPException(
                429,
                detail=f"Too many attempts. Try again in about {retry} seconds.",
                headers={"Retry-After": str(retry)},
            )


def reset() -> None:
    """Clear all counters — for tests only."""
    with _lock:
        _hits.clear()
