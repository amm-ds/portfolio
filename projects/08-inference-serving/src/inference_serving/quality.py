"""Harder exact-match quality eval + quantization-matched cross-runner pair.

The committed bench grades a saturated keyword smoke check (ties at 1.00 and
establishes nothing about answer quality). This module adds the pass-4 E10
evidence:

- (a) a fixed 300-item subset of GSM8K (MIT license) with strict exact-match
  grading after numeric normalization, run through every committed serving arm
  with the same items, prompt template, and decode settings;
- (b) a quantization-matched cross-runner pair (GGUF Q4_K_M on llama.cpp vs
  the MLX build of the same model family) measured for speed with the
  committed harness cell and for quality with the same subset.

Everything needed to re-derive the numbers is pinned in the artifacts:
dataset name/commit/license, subset file + sha256, item ids, seed, prompt
template, decode settings, runner observed per arm, and quantization evidence.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import random
import re
import time
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
from portfolio_core.logging import get_logger
from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field

from inference_serving.bench import detect_runner, percentile
from inference_serving.config import BenchConfig, ModelSpec
from inference_serving.schemas import CellResult

logger = get_logger(__name__)

# --- dataset (pinned) ---------------------------------------------------------

GSM8K_NAME = "openai/gsm8k"
GSM8K_SPLIT = "test"
GSM8K_COMMIT = "3101c7d5072418e28b9008a6636bde82a006892c"
GSM8K_URL = (
    "https://raw.githubusercontent.com/openai/grade-school-math/"
    f"{GSM8K_COMMIT}/grade_school_math/data/test.jsonl"
)
GSM8K_LICENSE = "MIT"
GSM8K_LICENSE_URL = "https://github.com/openai/grade-school-math/blob/master/LICENSE"
GSM8K_N_AVAILABLE = 1319

SUBSET_N = 300
SUBSET_SEED = 42
SUBSET_PATH = Path("data/quality_subset.jsonl")

QUALITY_PROMPT_SYSTEM = "You are a precise arithmetic assistant."
QUALITY_USER_TEMPLATE = (
    "Solve the problem. Reply with ONLY the final number "
    "(digits, optional decimal point, no units, no commas, no explanation).\n\n"
    "Problem: {question}"
)

QUALITY_MAX_TOKENS = 128
QUALITY_CONCURRENCY = 4

# --- exact-match grader (pure) ------------------------------------------------

# Valid thousands grouping only ("1,200" yes, "1,00" no) so a malformed number
# is a miss rather than silently re-interpreted.
_THOUSANDS_RE = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")


def gold_answer(answer_text: str) -> str:
    """GSM8K gold: the text after the final '####' marker, stripped."""
    return answer_text.split("####")[-1].strip()


def normalize_number(text: str) -> Decimal | None:
    """Canonical decimal for a short answer string, or None when not numeric.

    Rules (documented in the artifact): strip whitespace; drop one leading '$';
    drop commas only when they form valid thousands grouping; drop one trailing
    '.'; then parse as a decimal. Numeric equality makes '42', '42.0' and
    '042' equivalent; prose, units, '%', and fractions are misses.
    """
    t = text.strip()
    if t.startswith("$"):
        t = t[1:].strip()
    if _THOUSANDS_RE.match(t):
        t = t.replace(",", "")
    if t.endswith("."):
        t = t[:-1]
    if not t:
        return None
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def exact_match(output: str, gold: str) -> bool:
    """Strict exact match after numeric normalization (whole output vs gold)."""
    o = normalize_number(output)
    g = normalize_number(gold)
    return o is not None and g is not None and o == g


# --- subset (deterministic) ---------------------------------------------------


class GsmItem(PortfolioBaseModel):
    """One pinned eval item: stable id, question, extracted gold answer."""

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    gold: str = Field(min_length=1)


def build_subset(
    raw_path: Path,
    out_path: Path = SUBSET_PATH,
    *,
    n: int = SUBSET_N,
    expected_n: int | None = GSM8K_N_AVAILABLE,
) -> list[GsmItem]:
    """Materialize the seeded subset from the pinned GSM8K test JSONL.

    Item ids are ``gsm8k-test-<line index>`` so any subset row traces back to
    the pinned upstream file. Selection is ``random.Random(42).sample`` over
    line indices, sorted for a stable file order. ``expected_n`` guards the
    pinned upstream size (tests pass a small fixture with ``expected_n=None``).
    """
    lines = raw_path.read_text(encoding="utf-8").splitlines()
    items: list[GsmItem] = []
    for i, line in enumerate(lines):
        row = json.loads(line)
        items.append(
            GsmItem(
                id=f"gsm8k-test-{i:04d}",
                question=str(row["question"]),
                gold=gold_answer(str(row["answer"])),
            )
        )
    if expected_n is not None and len(items) != expected_n:
        raise ValueError(f"expected {expected_n} GSM8K test rows, got {len(items)}")
    rng = random.Random(SUBSET_SEED)  # noqa: S311 - seeded eval-subset sampler, not crypto
    chosen = sorted(rng.sample(range(len(items)), n))
    subset = [items[i] for i in chosen]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(it.model_dump(), ensure_ascii=False) for it in subset) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    return subset


def load_subset(path: Path = SUBSET_PATH) -> list[GsmItem]:
    """Read the committed subset file back into typed items."""
    return [
        GsmItem.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def download_gsm8k(dest: Path) -> Path:
    """Fetch the pinned GSM8K test JSONL (one small file, ~0.75 MB)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(GSM8K_URL, timeout=60) as response:  # noqa: S310 (pinned https URL)
        dest.write_bytes(response.read())
    return dest


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prompt_sha256() -> str:
    """Stable fingerprint of the prompt template pair recorded in artifacts."""
    blob = QUALITY_PROMPT_SYSTEM + "\n---\n" + QUALITY_USER_TEMPLATE
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --- artifact contracts -------------------------------------------------------


class QualityItemResult(PortfolioBaseModel):
    """One graded item for one arm."""

    id: str
    correct: bool
    output: str = Field(description="Raw completion text, truncated to 200 chars.")
    latency_s: float | None = None
    output_tokens: int = 0
    error: str | None = None


class QualityArmResult(PortfolioBaseModel):
    """Exact-match result for one serving arm over the fixed subset."""

    model: str
    engine: str = Field(description="Runner reported by /api/ps at run time.")
    quantization: str = Field(description="Recorded quantization + its evidence source.")
    n_items: int = Field(ge=0)
    n_correct: int = Field(ge=0)
    accuracy: float = Field(ge=0.0, le=1.0)
    n_errors: int = Field(ge=0)
    mean_latency_s: float | None = None
    p95_latency_s: float | None = None
    output_tokens_total: int = 0
    wall_time_s: float = 0.0
    items: list[QualityItemResult] = Field(default_factory=list)


class DatasetProvenance(PortfolioBaseModel):
    name: str
    split: str
    source_url: str
    commit: str
    license: str
    license_url: str
    n_items_available: int
    subset_file: str
    subset_sha256: str
    n_items: int


class QualityEvalArtifact(PortfolioBaseModel):
    """reports/quality_eval.json — per-arm exact-match eval, fully pinned."""

    artifact: str = "quality_eval"
    schema_version: int = 1
    created_at: str
    git_sha: str
    ollama_version: str
    platform: str
    dataset: DatasetProvenance
    seed: int
    prompt_system: str
    prompt_user_template: str
    prompt_sha256: str
    grading: str
    decode: dict[str, Any]
    arms: list[QualityArmResult]


class PairSide(PortfolioBaseModel):
    """One side of the quantization-matched pair, with quant evidence."""

    label: str
    model: str
    engine: str
    quantization: str
    quantization_evidence: str
    artifact_config_sha256: str = ""


class QuantPairArtifact(PortfolioBaseModel):
    """reports/quant_pair.json — matched-quant cross-runner speed + quality."""

    artifact: str = "quant_pair"
    schema_version: int = 1
    created_at: str
    git_sha: str
    ollama_version: str
    platform: str
    family: str
    pairing: str
    sides: list[PairSide]
    speed_protocol: str
    speed_cells: list[CellResult]
    quality_subset_sha256: str
    quality_n_items: int
    quality_seed: int
    quality_arms: list[QualityArmResult]
    notes: list[str] = Field(default_factory=list)


# --- live runner (Ollama-gated) ------------------------------------------------

_GRADING_RULE = (
    "exact match after numeric normalization: strip whitespace; drop one leading '$'; "
    "drop commas only in valid thousands grouping; drop one trailing '.'; compare as "
    "decimals when both sides parse ('42' == '42.0'); anything else (prose, units, "
    "'%', fractions) is a miss"
)


async def complete_once(
    client: httpx.AsyncClient,
    cfg: BenchConfig,
    spec: ModelSpec,
    item: GsmItem,
) -> QualityItemResult:
    """One streaming completion graded exact-match (never raises for model errors)."""
    reasoning_effort = spec.reasoning_effort or cfg.reasoning_effort
    payload: dict[str, Any] = {
        "model": spec.name,
        "messages": [
            {"role": "system", "content": QUALITY_PROMPT_SYSTEM},
            {"role": "user", "content": QUALITY_USER_TEMPLATE.format(question=item.question)},
        ],
        "max_tokens": QUALITY_MAX_TOKENS,
        "temperature": cfg.temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
        "keep_alive": cfg.keep_alive_s,
    }
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    chunks: list[str] = []
    usage: dict[str, Any] = {}
    start = time.perf_counter()
    try:
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
                        chunks.append(delta)
    except httpx.HTTPStatusError as exc:
        return QualityItemResult(
            id=item.id, correct=False, output="", error=f"http {exc.response.status_code}"
        )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        return QualityItemResult(id=item.id, correct=False, output="", error=type(exc).__name__)
    latency_s = time.perf_counter() - start
    output = "".join(chunks).strip()
    return QualityItemResult(
        id=item.id,
        correct=exact_match(output, item.gold),
        output=output[:200],
        latency_s=latency_s,
        output_tokens=int(usage.get("completion_tokens") or 0),
    )


async def run_quality_arm(
    client: httpx.AsyncClient,
    root_client: httpx.AsyncClient,
    cfg: BenchConfig,
    spec: ModelSpec,
    items: list[GsmItem],
    *,
    quantization: str,
    concurrency: int = QUALITY_CONCURRENCY,
) -> QualityArmResult:
    """Run the fixed subset through one serving arm and aggregate."""
    engine = await detect_runner(root_client, cfg, spec.name)
    semaphore = asyncio.Semaphore(concurrency)

    async def guarded(item: GsmItem) -> QualityItemResult:
        async with semaphore:
            return await complete_once(client, cfg, spec, item)

    start = time.perf_counter()
    results = list(await asyncio.gather(*(guarded(it) for it in items)))
    wall_time_s = time.perf_counter() - start
    ok = [r for r in results if r.error is None]
    latencies = [r.latency_s for r in ok if r.latency_s is not None]
    n_correct = sum(r.correct for r in ok)
    logger.info(
        "quality arm done: %s acc=%d/%d errors=%d",
        spec.name,
        n_correct,
        len(results),
        len(results) - len(ok),
    )
    return QualityArmResult(
        model=spec.name,
        engine=engine or spec.runner or "unknown",
        quantization=quantization,
        n_items=len(results),
        n_correct=n_correct,
        accuracy=n_correct / len(results) if results else 0.0,
        n_errors=len(results) - len(ok),
        mean_latency_s=(sum(latencies) / len(latencies)) if latencies else None,
        p95_latency_s=percentile(latencies, 0.95),
        output_tokens_total=sum(r.output_tokens for r in ok),
        wall_time_s=wall_time_s,
        items=results,
    )


def _ollama_models_dir() -> Path:
    env = os.environ.get("OLLAMA_MODELS")
    if env:
        return Path(env)
    return Path.home() / ".ollama" / "models"


def inspect_local_quantization(model: str) -> tuple[str, str, str]:
    """(quantization, evidence, config_sha256) for a pulled Ollama model.

    Reads the local manifest + config blob (no network): GGUF builds record
    ``file_type`` (e.g. Q4_K_M); MLX safetensors builds carry a HF
    ``config.json`` layer whose ``quantization.bits`` is the recorded quant.
    Returns ``("unrecorded", ...)`` when neither is available.
    """
    name, _, tag = model.partition(":")
    manifest_path = (
        _ollama_models_dir()
        / "manifests"
        / "registry.ollama.ai"
        / "library"
        / name
        / (tag or "latest")
    )
    if not manifest_path.exists():
        return ("unrecorded", f"no local manifest at {manifest_path}", "")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    blobs = _ollama_models_dir() / "blobs"
    config_digest = str(manifest.get("config", {}).get("digest", ""))
    config_file = blobs / config_digest.replace(":", "-")
    model_format = ""
    file_type = ""
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
            model_format = str(config.get("model_format", ""))
            file_type = str(config.get("file_type", ""))
        except (ValueError, OSError):
            pass
    if file_type:
        return (file_type, f"manifest config {config_digest} file_type", config_digest)
    if model_format == "safetensors":
        for layer in manifest.get("layers", []):
            digest = str(layer.get("digest", ""))
            blob = blobs / digest.replace(":", "-")
            try:
                if not digest or blob.stat().st_size > 20000:
                    continue
                payload = json.loads(blob.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            quant = payload.get("quantization") if isinstance(payload, dict) else None
            if isinstance(quant, dict) and "bits" in quant:
                bits = quant["bits"]
                group = quant.get("group_size")
                return (
                    f"{bits}-bit",
                    f"artifact config.json quantization bits={bits} group_size={group}",
                    config_digest,
                )
        return ("unrecorded", "safetensors build; no quantization block found", config_digest)
    return ("unrecorded", f"model_format={model_format or 'unknown'}", config_digest)


def dataset_provenance(subset_path: Path = SUBSET_PATH) -> DatasetProvenance:
    return DatasetProvenance(
        name=GSM8K_NAME,
        split=GSM8K_SPLIT,
        source_url=GSM8K_URL,
        commit=GSM8K_COMMIT,
        license=GSM8K_LICENSE,
        license_url=GSM8K_LICENSE_URL,
        n_items_available=GSM8K_N_AVAILABLE,
        subset_file=str(subset_path),
        subset_sha256=sha256_file(subset_path),
        n_items=len(load_subset(subset_path)),
    )


def build_artifact(
    arms: list[QualityArmResult],
    *,
    git_sha: str,
    ollama_version: str,
) -> QualityEvalArtifact:
    return QualityEvalArtifact(
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        git_sha=git_sha,
        ollama_version=ollama_version,
        platform=platform.platform(),
        dataset=dataset_provenance(),
        seed=SUBSET_SEED,
        prompt_system=QUALITY_PROMPT_SYSTEM,
        prompt_user_template=QUALITY_USER_TEMPLATE,
        prompt_sha256=prompt_sha256(),
        grading=_GRADING_RULE,
        decode={
            "temperature": 0.0,
            "max_tokens": QUALITY_MAX_TOKENS,
            "concurrency": QUALITY_CONCURRENCY,
            "reasoning_effort_default": "none",
            "reasoning_effort_overrides": {"gpt-oss:20b": "low"},
        },
        arms=arms,
    )
