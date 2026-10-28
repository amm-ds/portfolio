"""ASGI middleware: per-IP rate limiting, request-body cap, request logging.

Stdlib-only (plus starlette's ASGI/response primitives already in the deps).

Rate limiting is an in-process token bucket per client IP, applied to POST
requests only. Defaults: 30 requests/min/IP with a burst of 10, tunable via
``RATE_LIMIT_PER_MINUTE`` (read once at process startup). Over-limit requests
get 429 with a ``Retry-After`` header.

LIMITATION: the bucket store lives in this process's memory. The deployment
runs a single uvicorn process, so this is a floor against accidental abuse /
buggy clients — it is not DDoS protection (no shared state across replicas,
buckets reset on restart, NATed clients share one bucket). Client identity
comes from ``scope["client"]``; uvicorn only trusts X-Forwarded-For for that
when run with ``--proxy-headers --forwarded-allow-ips …`` (set in the
Dockerfile, restricted to the Caddy container in deploy compose) — otherwise
every visitor behind the proxy shares the proxy's bucket.
"""

import hashlib
import math
import os
import time
import uuid

from portfolio_core.logging import get_logger
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = get_logger(__name__)

_RATE_LIMIT_PER_MINUTE_DEFAULT = 30
_RATE_LIMIT_BURST_DEFAULT = 10
_MAX_BODY_BYTES_DEFAULT = 1_048_576  # 1 MB


class RateLimiter:
    """Per-key token bucket: ``burst`` tokens of capacity, refilled at
    ``per_minute``/60 tokens per second. Not thread-safe by design — the
    single-worker uvicorn process runs one event loop.

    The bucket store is bounded: at most ``max_keys`` entries (default 10k).
    On overflow the stalest bucket is evicted, and empty/refilled-full buckets
    are dropped opportunistically, so a key-spamming client cannot grow
    unbounded memory.
    """

    def __init__(
        self,
        per_minute: int = _RATE_LIMIT_PER_MINUTE_DEFAULT,
        burst: int = _RATE_LIMIT_BURST_DEFAULT,
        max_keys: int = 10_000,
    ):
        self.rate_per_second = per_minute / 60.0
        self.capacity = float(burst)
        self.max_keys = max_keys
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_refill)

    @classmethod
    def from_env(cls) -> "RateLimiter":
        """Build from the environment (read once at startup)."""
        raw = os.environ.get("RATE_LIMIT_PER_MINUTE", "")
        per_minute = int(raw) if raw else _RATE_LIMIT_PER_MINUTE_DEFAULT
        return cls(per_minute=per_minute)

    def check(self, key: str) -> tuple[bool, float]:
        """Consume one token for ``key``. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        if len(self._buckets) >= self.max_keys and key not in self._buckets:
            stalest = min(self._buckets, key=lambda k: self._buckets[k][1])
            del self._buckets[stalest]
            logger.warning("rate-limit store full (%d keys); evicted %r", self.max_keys, stalest)
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.rate_per_second)
        if tokens >= 1.0:
            self._buckets[key] = (tokens - 1.0, now)
            return True, 0.0
        retry_after = (1.0 - tokens) / self.rate_per_second
        self._buckets[key] = (tokens, now)
        return False, retry_after


class RateLimitMiddleware:
    """429 + Retry-After on POSTs once an IP's burst/window is exhausted."""

    def __init__(self, app: ASGIApp, limiter: RateLimiter | None = None):
        self.app = app
        self.limiter = limiter or RateLimiter.from_env()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        key = client[0] if client else "unknown"
        allowed, retry_after = self.limiter.check(key)
        if not allowed:
            from starlette.responses import JSONResponse

            response = JSONResponse(
                {"error": "rate limit exceeded", "request_id": request_id_from(scope)},
                status_code=429,
                headers={"Retry-After": str(math.ceil(retry_after))},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class BodyLimitMiddleware:
    """Global request-body cap: 413 when the body exceeds ~1 MB (buffered and
    replayed, so both Content-Length and chunked bodies are bounded)."""

    def __init__(self, app: ASGIApp, max_bytes: int = _MAX_BODY_BYTES_DEFAULT):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        content_length = headers.get(b"content-length")
        if content_length is not None and int(content_length) > self.max_bytes:
            await self._too_large(scope, receive, send)
            return
        body = bytearray()
        more = True
        while more:
            message = await receive()
            if message["type"] != "http.request":
                continue  # disconnect etc. — pass through to the app
            body.extend(message.get("body", b""))
            more = bool(message.get("more_body"))
            if len(body) > self.max_bytes:
                await self._too_large(scope, receive, send)
                return

        async def replay_receive() -> Message:
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _too_large(scope: Scope, receive: Receive, send: Send) -> None:
        from starlette.responses import JSONResponse

        response = JSONResponse(
            {"error": "request body too large", "request_id": request_id_from(scope)},
            status_code=413,
        )
        await response(scope, receive, send)


class RequestIdMiddleware:
    """Assign every request a short uuid4 id, exposed two ways:

    - ``request.state.request_id`` (via ``scope["state"]``) for exception
      handlers and middlewares downstream;
    - an ``X-Request-ID`` response header, so a client can quote the id when
      reporting a failure.
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex[:12]
        scope.setdefault("state", {})["request_id"] = request_id

        async def wrapped_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append([b"x-request-id", request_id.encode()])
            await send(message)

        await self.app(scope, receive, wrapped_send)

    def __init__(self, app: ASGIApp):
        self.app = app


def request_id_from(scope: Scope) -> str:
    """Best-effort request id for middleware-generated responses (429/413),
    which never see a ``Request`` object. Falls back to a fresh id."""
    state = scope.get("state") or {}
    rid = state.get("request_id")
    if isinstance(rid, str) and rid:
        return rid
    return uuid.uuid4().hex[:12]


def hash_client_ip(ip: str, salt: str | None = None) -> str:
    """Privacy-preserving client key for logs: sha256(ip + salt), 12 hex chars.

    Salt comes from ``IP_HASH_SALT`` (read once by the middleware at process
    startup; default ``dev-salt``). The raw IP never reaches the logs.
    """
    s = (salt if salt is not None else os.environ.get("IP_HASH_SALT", "dev-salt")).encode()
    return hashlib.sha256(s + ip.encode()).hexdigest()[:12]


class RequestLoggingMiddleware:
    """One INFO line per request: method, path, status, latency ms, hashed
    client IP, request id. No bodies, no query strings (they may carry
    tokens), no raw client IPs — the IP is logged only as a salted sha256
    prefix (12 hex chars), which is enough to correlate a session without
    storing the address."""

    def __init__(self, app: ASGIApp, salt: str | None = None):
        self.app = app
        self._salt = salt if salt is not None else os.environ.get("IP_HASH_SALT", "dev-salt")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "?")
        path = scope.get("path", "?")
        start = time.perf_counter()
        status = 500
        client = scope.get("client")
        ip_hash = hash_client_ip(client[0] if client else "unknown", self._salt)
        rid = request_id_from(scope)

        async def wrapped_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            latency_ms = (time.perf_counter() - start) * 1000.0
            logger.info(
                "%s %s -> %d (%.1f ms) ip=%s rid=%s", method, path, status, latency_ms, ip_hash, rid
            )
