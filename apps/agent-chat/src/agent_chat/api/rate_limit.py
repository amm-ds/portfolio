"""In-process fixed-window rate limiter for the paid endpoints.

Keyed per presented ``X-API-Key`` (sha256-truncated; "anonymous" when the
header is absent and auth is off). Authentication runs first: when
``AGENT_CHAT_API_KEY`` is set, unauthenticated requests are rejected by
``require_api_key`` before this limiter runs.

The limiter is per process and per key, in memory. It is NOT shared across
replicas — see the app README. Default 30 requests per minute per key,
configured through ``Settings.rate_limit_per_minute``.
"""

from __future__ import annotations

import hashlib
import math
import threading
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request, status


@dataclass
class _Window:
    start: float
    count: int


class RateLimiter:
    """Fixed-window counter per key. ``check`` returns retry-after seconds."""

    def __init__(self, per_minute: int, window_s: float = 60.0) -> None:
        if per_minute < 0:
            raise ValueError("per_minute must be >= 0")
        self._per_window = per_minute
        self._window_s = window_s
        self._windows: dict[str, _Window] = {}
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> float | None:
        """None when allowed; seconds-until-retry when over the limit."""
        if self._per_window == 0:
            return None
        now = time.monotonic() if now is None else now
        with self._lock:
            window = self._windows.get(key)
            if window is None or now - window.start >= self._window_s:
                self._windows[key] = _Window(start=now, count=1)
                return None
            if window.count < self._per_window:
                window.count += 1
                return None
            return self._window_s - (now - window.start)


def _key_for(request: Request) -> str:
    presented = request.headers.get("X-API-Key", "")
    if not presented:
        return "anonymous"
    return hashlib.sha256(presented.encode()).hexdigest()[:16]


async def rate_limit(request: Request) -> None:
    """Dependency: 429 + Retry-After when the per-key window is exhausted."""
    state = request.app.state.agent_chat
    retry_after = state.rate_limiter.check(_key_for(request))
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded for this API key",
            headers={"Retry-After": str(math.ceil(retry_after))},
        )
