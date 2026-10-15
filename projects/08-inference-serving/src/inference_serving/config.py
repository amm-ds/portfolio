"""Configuration: pydantic models only — no constants in logic.

``BenchConfig`` mirrors ``params.yaml`` field for field so the DVC stages and
the CLI stay in sync with the code (platform convention, ADR-0002).
"""

from pathlib import Path

from portfolio_core.config import Settings as CoreSettings
from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field, model_validator


class Settings(CoreSettings):
    """Project settings (env handling inherited from the platform)."""


class ModelSpec(PortfolioBaseModel):
    """One benchmark model cell definition.

    ``runner`` is the runner we *expect* (documented intent); the harness
    always records the runner the server reports via ``/api/ps`` at run time.
    """

    name: str = Field(min_length=1)
    runner: str = Field(default="", description="Expected runner (llamacpp|mlx); informational.")
    role: str = Field(
        default="default",
        description="default | quality (extra quant for quality-vs-quant) | engine (engine panel).",
    )
    reasoning_effort: str | None = Field(
        default=None,
        description="Per-model override for the reasoning-effort knob (gpt-oss needs 'low').",
    )


class BenchConfig(PortfolioBaseModel):
    """Tunables for the benchmark harness and reporting.

    Every field must exist in ``params.yaml`` (defaults apply when the file
    is absent or a key is missing).
    """

    seed: int = Field(default=42)

    base_url: str = Field(default="http://localhost:11434")
    request_timeout_s: float = Field(default=180.0, gt=0)
    max_tokens: int = Field(default=96, gt=0)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    # "none" disables hidden thinking/reasoning tokens so every arm decodes a
    # bounded structured answer (models without reasoning ignore the field).
    reasoning_effort: str = Field(default="none")
    repeats: int = Field(default=5, ge=1, description="Repeats of the prompt suite per cell.")
    cooldown_s: float = Field(
        default=5.0, ge=0.0, description="Pause between cells (thermal/noise)."
    )
    keep_alive_s: int = Field(
        default=600, gt=0, description="Model residency across cells of a run."
    )

    # Bounded default: primary models at 3 concurrency levels. --full adds
    # concurrency 2, the dense qwen3:32b arm, and the extra-quant/engine cells.
    models: list[ModelSpec] = Field(default_factory=list)
    full_models: list[ModelSpec] = Field(
        default_factory=list,
        description="Extra arms only run with --full (bounded default stays short).",
    )
    quality_models: list[ModelSpec] = Field(default_factory=list)
    engine_models: list[ModelSpec] = Field(default_factory=list)
    concurrency_default: list[int] = Field(default_factory=lambda: [1, 4, 8])
    concurrency_full: list[int] = Field(default_factory=lambda: [1, 2, 4, 8])

    @model_validator(mode="after")
    def _concurrency_positive(self) -> "BenchConfig":
        for field_name in ("concurrency_default", "concurrency_full"):
            levels = getattr(self, field_name)
            if not levels or any(c < 1 for c in levels):
                raise ValueError(f"{field_name} must list at least one level >= 1")
        return self

    # Cost section (declared assumptions — see DESIGN.md).
    usd_per_kwh: float = Field(default=0.30, gt=0)
    system_load_watts: float = Field(default=100.0, gt=0)
    cloud_usd_per_mtok_output: dict[str, float] = Field(
        default_factory=dict,
        description="Hypothetical rate-card $/1M output tokens per model tier "
        "(labelled illustrative, not measured).",
    )

    prompts_path: Path = Path("data/prompts.json")
    run_path: Path = Path("data/bench_run.json")
    reports_dir: Path = Path("reports")

    def concurrency(self, full: bool) -> list[int]:
        return self.concurrency_full if full else self.concurrency_default


def default_models() -> list[ModelSpec]:
    """Primary arms: MoE + dense + MXFP4, all served through the local Ollama."""
    return [
        ModelSpec(name="qwen3.6:35b-a3b-q4_K_M", runner="llamacpp"),
        ModelSpec(name="gemma4:31b", runner="mlx"),
        ModelSpec(name="gpt-oss:20b", runner="llamacpp", reasoning_effort="low"),
    ]


def default_full_models() -> list[ModelSpec]:
    """Full-mode-only arm: dense qwen3:32b (slower; excluded from the bounded run)."""
    return [ModelSpec(name="qwen3:32b", runner="llamacpp", role="full")]


def default_quality_models() -> list[ModelSpec]:
    """Second quantization of gemma4:31b on the same (llama.cpp) runner.

    Paired with ``gemma4:31b-it-q8_0`` from the engine arm, both GGUF/llama.cpp,
    so the quant comparison is engine-controlled.
    """
    return [ModelSpec(name="gemma4:31b-it-qat", runner="llamacpp", role="quality")]


def default_engine_models() -> list[ModelSpec]:
    """Same model family on both runners: GGUF/llama.cpp vs safetensors/MLX."""
    return [
        ModelSpec(name="gemma4:31b-it-q8_0", runner="llamacpp", role="engine"),
        ModelSpec(name="gemma4:31b-mlx", runner="mlx", role="engine"),
    ]


def load_config(path: Path = Path("params.yaml")) -> BenchConfig:
    """BenchConfig defaults overlaid with ``params.yaml`` when present (DVC)."""
    from portfolio_core.logging import get_logger

    logger = get_logger(__name__)
    cfg = BenchConfig(
        models=default_models(),
        full_models=default_full_models(),
        quality_models=default_quality_models(),
        engine_models=default_engine_models(),
    )
    if not path.exists():
        return cfg
    import yaml  # type: ignore[import-untyped]

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    known = {k: v for k, v in data.items() if k in BenchConfig.model_fields}
    unknown = sorted(set(data) - set(BenchConfig.model_fields))
    if unknown:
        logger.warning("params.yaml has keys outside BenchConfig, ignored: %s", unknown)
    if "models" in known or "quality_models" in known or "engine_models" in known:
        cfg = BenchConfig(**known)
        return cfg
    return cfg.model_copy(update=known)
