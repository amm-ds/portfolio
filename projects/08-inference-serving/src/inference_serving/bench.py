"""Async benchmark harness against the local Ollama OpenAI-compatible endpoint.

The serving layer IS Ollama (http://localhost:11434/v1, ADR-0004) — we do not
build a gateway (see DESIGN.md). The harness drives a FIXED structured-output
task (``Answer`` schema) over 8 fixed prompts and measures latency percentiles,
throughput, TTFT, schema-valid rate and failures per (model, engine, concurrency)
cell.
"""

from __future__ import annotations

import asyncio
import json
import math
import platform
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from portfolio_core.logging import get_logger
from pydantic import ValidationError

from inference_serving.config import BenchConfig, ModelSpec
from inference_serving.schemas import Answer, BenchPrompt, BenchRun, CellResult, RequestRecord

logger = get_logger(__name__)

# The fixed task suite: 8 prompts with expected keywords for the quality check.
# Kept small on purpose — every cell repeats the suite, and the bench must
# finish in minutes, not hours.
PROMPTS: list[BenchPrompt] = [
    BenchPrompt(
        id="capital-france",
        prompt="Question: What is the capital of France? Answer in one sentence, state your confidence, and cite a source.",  # noqa: E501
        expected_keywords=["paris"],
    ),
    BenchPrompt(
        id="water-boiling",
        prompt="Question: At what temperature does water boil at sea level? One sentence, confidence, citation.",  # noqa: E501
        expected_keywords=["100", "boil"],
    ),
    BenchPrompt(
        id="photosynthesis",
        prompt="Question: Which gas do plants absorb during photosynthesis? One sentence, confidence, citation.",  # noqa: E501
        expected_keywords=["carbon dioxide", "co2"],
    ),
    BenchPrompt(
        id="speed-light",
        prompt="Question: Approximately how fast does light travel in vacuum? One sentence, confidence, citation.",  # noqa: E501
        expected_keywords=["299", "300,000", "300000"],
    ),
    BenchPrompt(
        id="largest-planet",
        prompt="Question: Which planet in the Solar System has the largest mass? One sentence, confidence, citation.",  # noqa: E501
        expected_keywords=["jupiter"],
    ),
    BenchPrompt(
        id="dna",
        prompt="Question: What molecule carries genetic information in humans? One sentence, confidence, citation.",  # noqa: E501
        expected_keywords=["dna"],
    ),
    BenchPrompt(
        id="currency-japan",
        prompt="Question: What is the official currency of Japan? One sentence, confidence, citation.",  # noqa: E501
        expected_keywords=["yen"],
    ),
    BenchPrompt(
        id="first-president",
        prompt="Question: Who was the first president of the United States? One sentence, confidence, citation.",  # noqa: E501
        expected_keywords=["washington"],
    ),
]

_JSON_INSTRUCTION = (
    "Respond with ONLY a JSON object matching this schema: "
    '{"answer": "<one sentence>", "confidence": <0.0-1.0>, "citation": "<short source>"}. '
    "No prose, no markdown fences."
)

SCHEMA_FALLBACK_NOTE = (
    "server rejected json_schema response_format; fell back to instruction-based JSON"
)

ClientFactory = Callable[[], httpx.AsyncClient]
SleepFn = Callable[[float], Awaitable[None]]
CellCallback = Callable[[CellResult], None]


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile (latency SLO convention).

    ``q`` in (0, 1]; rank = ceil(q * n); returns ``None`` for empty input.
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def check_output(text: str, prompt: BenchPrompt) -> tuple[bool, bool]:
    """Validate raw model text: (schema_valid, quality_ok). Pure, testable."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        answer = Answer.model_validate_json(cleaned)
    except ValidationError:
        return False, False
    lower = answer.answer.lower()
    quality = not prompt.expected_keywords or any(
        kw.lower() in lower for kw in prompt.expected_keywords
    )
    return True, quality


def build_cell(
    records: list[RequestRecord],
    *,
    model: str,
    engine: str,
    concurrency: int,
    wall_time_s: float,
) -> CellResult:
    """Aggregate raw records of one cell into a CellResult (pure, testable)."""
    ok = [r for r in records if r.error is None and r.latency_s is not None]
    failures = len(records) - len(ok)
    latencies = [r.latency_s for r in ok if r.latency_s is not None]
    ttfts = [r.ttft_s for r in ok if r.ttft_s is not None]
    per_req_tok_s = [r.output_tokens / r.latency_s for r in ok if r.output_tokens and r.latency_s]
    total_tokens = sum(r.output_tokens for r in ok)
    denom = max(len(ok), 1)
    return CellResult(
        model=model,
        engine=engine,
        concurrency=concurrency,
        n_requests=len(records),
        n_failures=failures,
        p50_latency_s=percentile(latencies, 0.50),
        p95_latency_s=percentile(latencies, 0.95),
        p99_latency_s=percentile(latencies, 0.99),
        mean_ttft_s=(sum(ttfts) / len(ttfts)) if ttfts else None,
        agg_tok_per_s=(total_tokens / wall_time_s) if wall_time_s > 0 else None,
        mean_req_tok_per_s=(sum(per_req_tok_s) / len(per_req_tok_s)) if per_req_tok_s else None,
        schema_valid_rate=sum(r.schema_valid for r in ok) / denom,
        quality_rate=sum(r.quality_ok for r in ok) / denom,
        wall_time_s=wall_time_s,
        total_output_tokens=total_tokens,
    )


def _schema_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {"name": "Answer", "schema": Answer.model_json_schema()},
    }


async def chat_once(
    client: httpx.AsyncClient,
    cfg: BenchConfig,
    model: str,
    prompt: BenchPrompt,
    repeat: int,
    *,
    use_schema_format: bool = True,
    reasoning_effort: str | None = None,
    notes: list[str] | None = None,
) -> RequestRecord:
    """One streaming request; returns a RequestRecord (never raises for model errors)."""
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _JSON_INSTRUCTION},
            {"role": "user", "content": prompt.prompt},
        ],
        "max_tokens": cfg.max_tokens,
        "temperature": cfg.temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
        "keep_alive": cfg.keep_alive_s,
    }
    if reasoning_effort is None:
        reasoning_effort = cfg.reasoning_effort
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    if use_schema_format:
        payload["response_format"] = _schema_format()
    try:
        return await _stream_request(client, cfg, model, prompt, repeat, payload)
    except httpx.HTTPStatusError as exc:
        if use_schema_format and exc.response.status_code in (400, 422):
            # Server lacks json_schema support for this model: retry once with
            # instruction-based JSON (surfaced as a run note, not a failure).
            if notes is not None:
                notes.append(f"{model}: {SCHEMA_FALLBACK_NOTE}")
            return await chat_once(
                client,
                cfg,
                model,
                prompt,
                repeat,
                use_schema_format=False,
                reasoning_effort=reasoning_effort,
                notes=notes,
            )
        return RequestRecord(
            model=model,
            prompt_id=prompt.id,
            repeat=repeat,
            error=f"http {exc.response.status_code}",
        )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        return RequestRecord(
            model=model, prompt_id=prompt.id, repeat=repeat, error=f"{type(exc).__name__}"
        )


async def _stream_request(
    client: httpx.AsyncClient,
    cfg: BenchConfig,
    model: str,
    prompt: BenchPrompt,
    repeat: int,
    payload: dict[str, Any],
) -> RequestRecord:
    chunks: list[str] = []
    usage: dict[str, Any] = {}
    ttft_s: float | None = None
    start = time.perf_counter()
    async with client.stream(
        "POST", "/chat/completions", json=payload, timeout=cfg.request_timeout_s
    ) as response:
        if response.status_code >= 400:
            await response.aread()
            response.raise_for_status()
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if data == "[DONE]":
                break
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            if event.get("usage"):
                usage = event["usage"]
            for choice in event.get("choices") or []:
                delta = (choice.get("delta") or {}).get("content")
                if delta:
                    if ttft_s is None:
                        ttft_s = time.perf_counter() - start
                    chunks.append(delta)
    latency_s = time.perf_counter() - start
    schema_valid, quality_ok = check_output("".join(chunks), prompt)
    return RequestRecord(
        model=model,
        prompt_id=prompt.id,
        repeat=repeat,
        ttft_s=ttft_s,
        latency_s=latency_s,
        output_tokens=int(usage.get("completion_tokens") or 0),
        schema_valid=schema_valid,
        quality_ok=quality_ok,
    )


async def detect_runner(root_client: httpx.AsyncClient, cfg: BenchConfig, model: str) -> str:
    """Runner actually serving ``model`` (from /api/ps), after a load warmup.

    Ollama 0.40.x auto-selects the runner from the model artifact (GGUF →
    llama.cpp; MLX safetensors on Apple Silicon) — this build has no runner
    override env, so we observe rather than control (DESIGN.md).
    """
    try:
        # Warmup: a 1-token request forces the model into memory.
        await root_client.post(
            "/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
                "keep_alive": cfg.keep_alive_s,
            },
            timeout=cfg.request_timeout_s,
        )
        r = await root_client.get("/api/ps", timeout=10.0)
        r.raise_for_status()
        for entry in r.json().get("models", []):
            if entry.get("name") == model:
                return str(entry.get("runner") or "")
    except httpx.HTTPError as exc:
        logger.warning("runner detection failed for %s: %s", model, exc)
    return ""


def plan_cells(cfg: BenchConfig, full: bool) -> list[tuple[ModelSpec, int]]:
    """(model, concurrency) cells — bounded default stays well under 45 min."""
    models = list(cfg.models) + (list(cfg.full_models) if full else [])
    return [(m, c) for m in models for c in cfg.concurrency(full)]


def plan_quality_cells(cfg: BenchConfig, full: bool) -> list[tuple[ModelSpec, int]]:
    """Engine-comparison cells run in every mode (small, 1 request wide);

    extra-quant quality cells only in full mode.
    """
    extra = list(cfg.engine_models) + (list(cfg.quality_models) if full else [])
    return [(m, 1) for m in extra]


async def run_cell(
    client: httpx.AsyncClient,
    cfg: BenchConfig,
    model: str,
    engine: str,
    concurrency: int,
    *,
    seed: int = 42,
    reasoning_effort: str | None = None,
    notes: list[str] | None = None,
) -> tuple[CellResult, list[RequestRecord]]:
    """One (model, concurrency) cell: prompts x repeats under a semaphore."""
    semaphore = asyncio.Semaphore(concurrency)
    rng = random.Random(seed)  # noqa: S311 - seeded bench shuffle RNG, not crypto
    jobs = [(p, rep) for rep in range(cfg.repeats) for p in PROMPTS]
    rng.shuffle(jobs)

    async def guarded(prompt: BenchPrompt, rep: int) -> RequestRecord:
        async with semaphore:
            return await chat_once(
                client,
                cfg,
                model,
                prompt,
                rep,
                reasoning_effort=reasoning_effort,
                notes=notes,
            )

    start = time.perf_counter()
    records = list(await asyncio.gather(*(guarded(p, rep) for p, rep in jobs)))
    wall_time_s = time.perf_counter() - start
    cell = build_cell(
        records, model=model, engine=engine, concurrency=concurrency, wall_time_s=wall_time_s
    )
    return cell, records


async def run_bench(
    cfg: BenchConfig,
    *,
    full: bool = False,
    client_factory: ClientFactory | None = None,
    root_factory: ClientFactory | None = None,
    sleep: SleepFn | None = None,
    on_cell: CellCallback | None = None,
) -> BenchRun:
    """Run the benchmark; returns a BenchRun with cells + raw records.

    ``client_factory`` builds the OpenAI-compatible client and ``root_factory``
    the server-root client (``/api/version``, ``/api/ps``); tests inject httpx
    ASGITransport stubs for both.
    """
    sleep = sleep or asyncio.sleep
    notes: list[str] = []
    version = ""
    cells: list[CellResult] = []
    records: list[RequestRecord] = []
    runners: dict[str, str] = {}

    def make_client() -> httpx.AsyncClient:
        if client_factory is not None:
            return client_factory()
        return httpx.AsyncClient(
            base_url=f"{cfg.base_url.rstrip('/')}/v1",
            timeout=cfg.request_timeout_s,
        )

    def make_root() -> httpx.AsyncClient:
        if root_factory is not None:
            return root_factory()
        return httpx.AsyncClient(base_url=cfg.base_url.rstrip("/"), timeout=10.0)

    async with make_client() as client, make_root() as root_client:
        try:
            version = (await root_client.get("/api/version")).json().get("version", "")
        except (httpx.HTTPError, ValueError):
            notes.append("could not read /api/version")

        cell_plan = plan_cells(cfg, full) + plan_quality_cells(cfg, full)
        for idx, (spec, concurrency) in enumerate(cell_plan):
            if spec.name not in runners:
                runners[spec.name] = await detect_runner(root_client, cfg, spec.name)
                if runners[spec.name] and runners[spec.name] != spec.runner:
                    notes.append(
                        f"{spec.name}: expected runner {spec.runner or '?'}, "
                        f"server reports {runners[spec.name]}"
                    )
            engine = runners[spec.name] or spec.runner or "unknown"
            cell, cell_records = await run_cell(
                client,
                cfg,
                spec.name,
                engine,
                concurrency,
                reasoning_effort=spec.reasoning_effort,
                notes=notes,
            )
            cells.append(cell)
            records.extend(cell_records)
            logger.info(
                "cell done: %s c=%d p95=%.2fs tok/s=%.1f valid=%.2f",
                spec.name,
                concurrency,
                cell.p95_latency_s or -1,
                cell.agg_tok_per_s or -1,
                cell.schema_valid_rate,
            )
            if on_cell is not None:
                on_cell(cell)
            if idx < len(cell_plan) - 1 and cfg.cooldown_s > 0:
                await sleep(cfg.cooldown_s)

    return BenchRun(
        started_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        ollama_version=version,
        platform=platform.platform(),
        base_url=cfg.base_url,
        full=full,
        cells=cells,
        records=records,
        notes=sorted(set(notes)),
    )
