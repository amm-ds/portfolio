"""Typed contracts for the inference-serving benchmark (ADR-0002)."""

from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field


class Answer(PortfolioBaseModel):
    """The FIXED structured-output task every request must produce.

    One-sentence answer + calibrated confidence + citation. Validation of this
    schema against raw model output is the "schema-valid rate" metric.
    """

    answer: str = Field(min_length=1, description="Exactly one sentence.")
    confidence: float = Field(ge=0.0, le=1.0)
    citation: str = Field(
        min_length=1, description="Short source phrase, e.g. 'Encyclopedia, Art. 3'."
    )


class BenchPrompt(PortfolioBaseModel):
    """One fixed prompt plus the keyword set used for the tiny quality check."""

    id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    expected_keywords: list[str] = Field(
        default_factory=list,
        description="Case-insensitive keywords the answer should contain (quality check).",
    )


class RequestRecord(PortfolioBaseModel):
    """One request/response observation inside a benchmark cell."""

    model: str
    prompt_id: str
    repeat: int = Field(ge=0)
    ttft_s: float | None = Field(default=None, ge=0)
    latency_s: float | None = Field(default=None, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    schema_valid: bool = False
    quality_ok: bool = False
    error: str | None = None


class CellResult(PortfolioBaseModel):
    """Aggregated metrics for one (model, engine, concurrency) cell."""

    model: str
    engine: str = Field(description="Runner actually serving the model (ollama.ps RUNNER).")
    concurrency: int = Field(ge=1)
    n_requests: int = Field(ge=0)
    n_failures: int = Field(ge=0)
    p50_latency_s: float | None = None
    p95_latency_s: float | None = None
    p99_latency_s: float | None = None
    mean_ttft_s: float | None = None
    agg_tok_per_s: float | None = Field(
        default=None, description="Total output tokens / cell wall time."
    )
    mean_req_tok_per_s: float | None = Field(
        default=None, description="Mean of per-request output tokens / request latency."
    )
    schema_valid_rate: float = Field(ge=0.0, le=1.0)
    quality_rate: float = Field(ge=0.0, le=1.0)
    wall_time_s: float = Field(ge=0.0)
    total_output_tokens: int = Field(default=0, ge=0)


class BenchRun(PortfolioBaseModel):
    """One full benchmark run: metadata + cells (+ raw records for re-analysis)."""

    started_at: str
    ollama_version: str = ""
    platform: str = ""
    base_url: str = ""
    full: bool = False
    cells: list[CellResult] = Field(default_factory=list)
    records: list[RequestRecord] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
