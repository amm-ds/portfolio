"""In-process per-key rate limiting on the paid endpoints (/chat, /ingest).

Default 30 requests/minute per key (Settings.rate_limit_per_minute; 0
disables). The limiter is per process and not shared across replicas.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from agent_chat.api.app import create_app
from agent_chat.api.rate_limit import RateLimiter
from agent_chat.config import Settings
from agent_chat.rag.embeddings import HashingEmbedder
from tests import fakes


def _limited_client(tmp_path: Path, per_minute: int = 2) -> TestClient:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/rate-limit.db",
        embedder="hashing",
        ingest_roots=[tmp_path],
        rate_limit_per_minute=per_minute,
    )
    app = create_app(settings=settings, model=fakes.app_model(), embedder=HashingEmbedder())
    return TestClient(app)


def _docs_dir(tmp_path: Path) -> Path:
    docs = tmp_path / "kb"
    docs.mkdir(exist_ok=True)
    (docs / "policies.md").write_text("Passwords rotate every 60 days.\n", encoding="utf-8")
    return docs


class TestRateLimiterUnit:
    def test_window_allows_up_to_limit_then_retries(self) -> None:
        limiter = RateLimiter(per_minute=3, window_s=60.0)
        assert limiter.check("k", now=0.0) is None
        assert limiter.check("k", now=1.0) is None
        assert limiter.check("k", now=2.0) is None
        retry = limiter.check("k", now=3.0)
        assert retry is not None
        assert 0 < retry <= 60.0

    def test_keys_are_independent(self) -> None:
        limiter = RateLimiter(per_minute=1, window_s=60.0)
        assert limiter.check("a", now=0.0) is None
        assert limiter.check("a", now=1.0) is not None
        assert limiter.check("b", now=1.0) is None

    def test_window_resets_after_window_s(self) -> None:
        limiter = RateLimiter(per_minute=1, window_s=60.0)
        assert limiter.check("k", now=0.0) is None
        assert limiter.check("k", now=10.0) is not None
        assert limiter.check("k", now=60.0) is None

    def test_zero_disables(self) -> None:
        limiter = RateLimiter(per_minute=0)
        for i in range(1000):
            assert limiter.check("k", now=float(i)) is None


class TestIngestRateLimit:
    def test_n_plus_first_request_gets_429_with_retry_after(self, tmp_path: Path) -> None:
        client = _limited_client(tmp_path, per_minute=2)
        docs = _docs_dir(tmp_path)
        with client:
            for _ in range(2):
                assert client.post("/ingest", json={"paths": [str(docs)]}).status_code == 200
            blocked = client.post("/ingest", json={"paths": [str(docs)]})
        assert blocked.status_code == 429
        retry_after = blocked.headers.get("Retry-After")
        assert retry_after is not None and float(retry_after) > 0
        assert blocked.json()["error"]["code"] == "http_429"

    def test_different_key_is_not_limited(self, tmp_path: Path) -> None:
        client = _limited_client(tmp_path, per_minute=2)
        docs = _docs_dir(tmp_path)
        headers = {"X-API-Key": "key-a"}
        with client:
            for _ in range(2):
                assert (
                    client.post("/ingest", json={"paths": [str(docs)]}, headers=headers).status_code
                    == 200
                )
            blocked = client.post("/ingest", json={"paths": [str(docs)]}, headers=headers)
            assert blocked.status_code == 429
            other = client.post(
                "/ingest",
                json={"paths": [str(docs)]},
                headers={"X-API-Key": "key-b"},
            )
        assert other.status_code == 200
