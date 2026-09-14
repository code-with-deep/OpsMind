"""In-process sliding-window rate limiter for auth/investigation endpoints (P1-12).

This is a single-process limiter (a dict guarded by a lock). It is NOT correct
across multiple uvicorn workers or replicas — for that, move counters to Redis
or Postgres. It is still meaningfully better than no rate limiting at all, and
is the safe default that requires no new infrastructure dependency.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class _SlidingWindowLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, *, max_hits: int, window_seconds: float) -> None:
        """Raise HTTPException(429) if `key` has exceeded max_hits in the window."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            cutoff = now - window_seconds
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= max_hits:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait a moment and try again.",
                )
            q.append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


_limiter = _SlidingWindowLimiter()


def _client_ip(request: Request) -> str:
    # Trust X-Forwarded-For only if you control the proxy layer (e.g. a reverse proxy you run in front of the API).
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_by_ip(
    request: Request, *, bucket: str, max_hits: int, window_seconds: float
) -> None:
    """Dependency-style helper: call from a route to enforce a per-IP limit."""
    ip = _client_ip(request)
    _limiter.check(f"{bucket}:ip:{ip}", max_hits=max_hits, window_seconds=window_seconds)


def rate_limit_by_key(key: str, *, bucket: str, max_hits: int, window_seconds: float) -> None:
    """Enforce a limit keyed by an arbitrary string (e.g. email, account id)."""
    _limiter.check(f"{bucket}:{key}", max_hits=max_hits, window_seconds=window_seconds)


def reset_rate_limit(key: str, *, bucket: str) -> None:
    _limiter.reset(f"{bucket}:{key}")
