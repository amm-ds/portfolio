"""Fake-server integration tests: stub ASGI mimicking Ollama's OpenAI endpoint.

The stub streams chat-completion SSE chunks (like Ollama with
stream_options.include_usage) through an httpx ASGITransport, so the full
harness path (SSE parse, TTFT, usage, schema validation, cell aggregation,
BenchRun assembly) runs offline and deterministically.
"""

from __future__ import annotations

import json

import httpx
import pytest
from inference_serving import bench as bench_mod
from inference_serving.config import BenchConfig, ModelSpec
from inference_serving.schemas import BenchRun

GOOD_ANSWER = '{"answer": "The capital is Paris.", "confidence": 0.95, "citation": "World Atlas"}'


def _sse(payloads: list[dict[str, object]]) -> bytes:
    body = "".join(f"data: {json.dumps(p)}\n\n" for p in payloads)
    return (body + "data: [DONE]\n\n").encode()


class FakeOllama:
    """Minimal ASGI stub of Ollama: /v1/chat/completions (stream), /api/ps, /api/version."""

    def __init__(self, *, fail_all: bool = False) -> None:
        self.requests: list[dict[str, object]] = []
        self._fail_all = fail_all

    async def __call__(self, scope: dict[str, object], receive: object, send: object) -> None:
        assert scope["type"] == "http"
        path = scope["path"]
        payload: dict[str, object] = {}
        if scope["method"] == "POST":  # type: ignore[comparison-overlap]
            body = b""
            more = True
            while more:
                message = await receive()  # type: ignore[operator]
                body += message.get("body", b"")
                more = message.get("more_body", False)
            payload = json.loads(body)
            self.requests.append(payload)

        if path == "/api/version":
            await self._respond(send, b'{"version": "0.0.0-test"}')
        elif path == "/api/ps":
            models = [{"name": "fake:7b", "runner": "llamacpp"}]
            await self._respond(send, json.dumps({"models": models}).encode())
        elif path == "/v1/chat/completions":
            if self._fail_all:
                await self._respond(send, b'{"error":"boom"}', status=500)
            else:
                await self._stream(send, payload)
        else:
            await self._respond(send, b"{}", status=404)

    async def _respond(self, send: object, body: bytes, status: int = 200) -> None:
        await send(  # type: ignore[operator]
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body})  # type: ignore[operator]

    async def _stream(self, send: object, payload: dict[str, object]) -> None:
        text = GOOD_ANSWER
        max_tokens = int(payload.get("max_tokens") or 16)
        n_chunks = max(1, min(max_tokens // 3, len(text)))
        step = max(1, len(text) // n_chunks)
        parts = [text[i : i + step] for i in range(0, len(text), step)]
        payloads: list[dict[str, object]] = [
            {"choices": [{"index": 0, "delta": {"content": part}}], "usage": None} for part in parts
        ]
        payloads.append(
            {
                "choices": [],
                "usage": {
                    "prompt_tokens": 40,
                    "completion_tokens": max_tokens,
                    "total_tokens": 40 + max_tokens,
                },
            }
        )
        await send(  # type: ignore[operator]
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        await send({"type": "http.response.body", "body": _sse(payloads)})  # type: ignore[operator]


@pytest.fixture
def fake() -> tuple[FakeOllama, bench_mod.ClientFactory, bench_mod.ClientFactory]:
    server = FakeOllama()

    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server),
            base_url="http://testserver/v1",
            timeout=30.0,
        )

    def root_factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server),
            base_url="http://testserver",
            timeout=30.0,
        )

    return server, factory, root_factory


def _cfg(**kw: object) -> BenchConfig:
    base: dict[str, object] = dict(
        base_url="http://testserver",
        repeats=2,
        cooldown_s=0,
        models=[ModelSpec(name="fake:7b", runner="llamacpp")],
        concurrency_default=[1, 2],
        concurrency_full=[1, 2],
        engine_models=[],
        quality_models=[],
    )
    base.update(kw)
    return BenchConfig(**base)  # type: ignore[arg-type]


def test_run_cell_against_fake_server(fake: tuple[FakeOllama, object, object]) -> None:
    import asyncio

    server, factory, _root = fake
    cfg = _cfg()

    async def scenario() -> None:
        async with factory() as client:  # type: ignore[operator]
            return await bench_mod.run_cell(client, cfg, "fake:7b", "llamacpp", 2)

    cell, records = asyncio.run(scenario())
    assert cell.n_requests == 8 * cfg.repeats
    assert cell.n_failures == 0
    assert cell.schema_valid_rate == 1.0
    # Only the capital-france prompt's keyword ("paris") appears in the canned answer.
    assert cell.quality_rate == pytest.approx(1 / 8)
    assert cell.p95_latency_s is not None and cell.p95_latency_s > 0
    assert cell.agg_tok_per_s and cell.agg_tok_per_s > 0
    assert all(r.output_tokens == cfg.max_tokens for r in records)
    # the stub saw streaming requests carrying the json_schema response_format
    assert server.requests, "no requests reached the stub"
    assert all(p["stream"] is True for p in server.requests)
    assert all("response_format" in p for p in server.requests)


def test_run_bench_assembles_benchrun(fake: tuple[FakeOllama, object, object]) -> None:
    import asyncio

    server, factory, root_factory = fake
    run: BenchRun = asyncio.run(
        bench_mod.run_bench(_cfg(), full=False, client_factory=factory, root_factory=root_factory)
    )
    assert len(run.cells) == 2  # 1 model x 2 concurrency levels
    assert run.ollama_version == "0.0.0-test"
    assert run.cells[0].engine == "llamacpp"  # detected via /api/ps
    assert len(run.records) == sum(c.n_requests for c in run.cells)
    assert run.cells[0].schema_valid_rate == 1.0
    assert server.requests, "no requests reached the stub"


def test_chat_once_records_errors_on_500(fake: tuple[FakeOllama, object, object]) -> None:
    import asyncio

    server, factory, _root = fake
    server._fail_all = True

    async def scenario() -> object:
        async with factory() as client:  # type: ignore[operator]
            return await bench_mod.chat_once(
                client, _cfg(), "fake:7b", bench_mod.PROMPTS[0], 0, use_schema_format=False
            )

    record = asyncio.run(scenario())
    assert record.error is not None and record.error.startswith("http 500")
    assert record.latency_s is None


def test_config_validation_rejects_bad_values() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _cfg(repeats=0)
    with pytest.raises(ValidationError):
        _cfg(concurrency_default=[0])
    with pytest.raises(ValidationError):
        _cfg(request_timeout_s=-1)
    with pytest.raises(ValidationError):
        ModelSpec(name="")
