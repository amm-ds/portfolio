"""In-process fixed-window rate limiter for the model-cost endpoints.

Keyed per authenticated tenant (``Principal.tenant_id``). Authentication runs
first: the existing ``Identity`` dependency rejects unauthenticated requests
before this limiter runs.

The limiter is per process and per tenant, in memory. It is NOT shared across
replicas — see the app README. Default 30 requests per minute per tenant,
configured through ``Settings.rate_limit_per_minute`` (0 disables).
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from document_intelligence.api.identity import Principal, authenticate


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


async def rate_limit(
    request: Request,
    identity: Annotated[Principal, Depends(authenticate)],
) -> None:
    """Dependency: 429 + Retry-After when the per-tenant window is exhausted."""
    state = request.app.state.app_state
    retry_after = state.rate_limiter.check(identity.tenant_id)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded for this tenant",
            headers={"Retry-After": str(math.ceil(retry_after))},
        )
