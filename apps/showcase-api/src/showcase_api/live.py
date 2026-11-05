"""Live-call guardrails and bounded wall-clock execution."""

import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from portfolio_core.logging import get_logger

# Keep the original log category: operators and tests filter on showcase_api.main.
logger = get_logger("showcase_api.main")

# --- Live-call guard + wall-clock cap ----------------------------------------
# The live POST endpoints (/forecast, /score, /solve) run real model inference
# on request. Two production guardrails, both fail closed:
#
# - Kill switch: LIVE_KILL_SWITCH=1 in the env, or the file /tmp/live_disabled
#   exists → every live call gets a fast 503 pointing at the precomputed demo
#   replay. Cheap circuit breaker during incidents.
# - Daily budget: a global in-process counter (UTC day) capped by
#   DAILY_LIVE_BUDGET (default 1000). At 80% a WARNING is logged once per day;
#   past the budget every call gets 503 until the day rolls over.

# Spec'd operator kill-switch flag: touching this file disables the live POST
# endpoints (503 + replay hint) until it is removed.
_LIVE_DISABLE_FLAG = Path("/tmp/live_disabled")  # noqa: S108
_LIVE_TIMEOUT_S = 10.0  # wall-clock cap for the live POSTs (/forecast, /score, /solve)
_LIVE_BUDGET_DEFAULT = 1000
_LIVE_REPLAY_HINT = "precomputed demo replay remains available"


class LiveGuard:
    """Kill-switch + daily call budget for the live POST endpoints."""

    def __init__(self, budget: int = _LIVE_BUDGET_DEFAULT, kill_switch: bool = False):
        self.budget = budget
        self.kill_switch = kill_switch
        self._lock = threading.Lock()
        self._day = ""
        self._count = 0
        self._alerted = False

    @classmethod
    def from_env(cls) -> "LiveGuard":
        raw = os.environ.get("DAILY_LIVE_BUDGET", "")
        budget = int(raw) if raw else _LIVE_BUDGET_DEFAULT
        return cls(budget=budget, kill_switch=os.environ.get("LIVE_KILL_SWITCH") == "1")

    def disabled(self) -> bool:
        return self.kill_switch or _LIVE_DISABLE_FLAG.exists()

    def gate(self) -> None:
        """Raise 503 when live calls are disabled or the daily budget is spent."""
        if self.disabled():
            raise LiveCallBlocked("live inference temporarily disabled")
        today = datetime.now(UTC).date().isoformat()
        with self._lock:
            if today != self._day:
                self._day, self._count, self._alerted = today, 0, False
            self._count += 1
            count = self._count
        if count > self.budget:
            logger.warning("live daily budget exhausted: %d/%d calls", count, self.budget)
            raise LiveCallBlocked("daily live-call budget exhausted")
        if not self._alerted and count >= 0.8 * self.budget:
            self._alerted = True
            logger.warning("live daily budget at 80%%: %d/%d calls today", count, self.budget)


class LiveCallBlocked(HTTPException):
    """503 raised by the live-call guard; the handler surfaces ``hint`` so the
    client knows the precomputed demo replay still works."""

    def __init__(self, detail: str):
        super().__init__(status_code=503, detail=detail)
        self.hint = _LIVE_REPLAY_HINT


_LIVE_GUARD = LiveGuard.from_env()


def _run_with_timeout[T](fn: Callable[[], T], seconds: float = _LIVE_TIMEOUT_S) -> T:
    """Run CPU-bound inference work on a worker thread with a wall-clock cap.

    On timeout the worker is abandoned (it cannot be killed mid-predict) and
    the caller gets a 504. Bounded callers release their capacity in the worker
    itself, so an abandoned worker continues to occupy its slot until it exits.
    """
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(fn).result(timeout=seconds)
    except FutureTimeout as e:
        raise HTTPException(
            status_code=504, detail=f"request exceeded the {seconds:.0f}s wall-clock cap"
        ) from e
    finally:
        pool.shutdown(wait=False)


def _run_bounded_with_timeout[T](
    fn: Callable[[], T], semaphore: threading.BoundedSemaphore, busy_detail: str
) -> T:
    """Run at capacity or fail fast; the worker owns and releases its slot."""
    if not semaphore.acquire(blocking=False):
        raise HTTPException(status_code=503, detail=busy_detail)

    def _worker() -> T:
        try:
            return fn()
        finally:
            semaphore.release()

    return _run_with_timeout(_worker)
