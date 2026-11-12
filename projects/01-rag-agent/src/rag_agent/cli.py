"""Command-line interface: corpus prep, indexing, evaluation, interactive chat.

Typical session (from the project directory)::

    uv run python -m rag_agent.cli prepare-corpus
    uv run python -m rag_agent.cli build-index
    uv run python -m rag_agent.cli evaluate
    uv run python -m rag_agent.cli chat
"""

from pathlib import Path
from typing import Annotated

import typer
from portfolio_core.llm import LLMProviderUnavailableError
from portfolio_core.llm_budget import BudgetExceededError
from portfolio_core.logging import get_logger

from rag_agent.agent import build_agent
from rag_agent.config import RAGConfig
from rag_agent.corpus import load_corpus, prepare_client_corpus
from rag_agent.corpus import prepare_corpus as prepare_corpus_impl
from rag_agent.evaluate import run as run_evaluation
from rag_agent.evaluate import run_citation_eval as run_citation_evaluation
from rag_agent.evaluate import run_heldout as run_heldout_evaluation
from rag_agent.evaluate import run_stress_eval as run_stress_evaluation
from rag_agent.index import (
    CrossEncoderReranker,
    Retriever,
    SentenceTransformerEmbedder,
    chunk_articles,
)
from rag_agent.index import (
    build_index as build_index_impl,
)
from rag_agent.verify import ClaimJudge, build_claim_judge, verify_result

app = typer.Typer(help=__doc__, add_completion=False)
logger = get_logger(__name__)


def load_config() -> RAGConfig:
    """RAGConfig defaults, overlaid with ``params.yaml`` when present (DVC).

    Three environment variables then override the evidence-gate thresholds
    and the verify diagnose flag — diagnostics-only knobs for hosted
    calibration runs (gate-threshold fitting, mechanical-checker audit).
    They never change the committed defaults.
    """
    params_path = Path("params.yaml")
    if params_path.exists():
        import yaml  # type: ignore[import-untyped]  # PyYAML has no stubs; mkdocs transitive dep

        data = yaml.safe_load(params_path.read_text(encoding="utf-8")) or {}
        unknown = set(data) - set(RAGConfig.model_fields)
        if unknown:
            logger.warning("params.yaml has keys outside RAGConfig, ignored: %s", sorted(unknown))
        config = RAGConfig(**{k: v for k, v in data.items() if k in RAGConfig.model_fields})
    else:
        config = RAGConfig()
    _apply_env_overrides(config)
    return config


def _apply_env_overrides(config: RAGConfig) -> None:
    """Apply the R6 diagnostics env overrides onto ``config`` in place.

    ``RAG_GATE_MIN_COVERAGE`` / ``RAG_GATE_MIN_MAX_SIMILARITY`` recalibrate
    the evidence gate (0 opens it: signals still recorded, no refusals except
    empty evidence); ``VERIFY_DIAGNOSE_MECH=true`` sends mechanically-failed
    claims to the judge so the checker's false-rejection rate is measurable.
    Sealed passes stamp the effective values in their run record, so an
    override can never silently change what a run measured.
    """
    import os

    from rag_agent.gate import GateConfig

    updates: dict[str, float] = {}
    if raw := os.environ.get("RAG_GATE_MIN_COVERAGE"):
        updates["min_coverage"] = float(raw)
    if raw := os.environ.get("RAG_GATE_MIN_MAX_SIMILARITY"):
        updates["min_max_similarity"] = float(raw)
    if updates:
        config.evidence_gate = GateConfig(**{**config.evidence_gate.__dict__, **updates})
        logger.info("env override: evidence_gate=%s", config.evidence_gate)
    if raw := os.environ.get("VERIFY_DIAGNOSE_MECH"):
        config.verify.diagnose_mech = raw.strip().lower() in {"1", "true", "yes"}
        logger.info("env override: verify.diagnose_mech=%s", config.verify.diagnose_mech)


@app.command()
def prepare_corpus(
    source: Annotated[
        str, typer.Option("--source", help="wikimedia (default) | client.")
    ] = "wikimedia",
    client_dir: Annotated[
        Path | None,
        typer.Argument(
            help="Directory of client JSONL files ({title, text, topic?}); "
            "required for --source client.",
        ),
    ] = None,
    license_name: Annotated[
        str,
        typer.Option("--license", help="Dataset license recorded in the contract (source=client)."),
    ] = "Proprietary - client-provided",
) -> None:
    """Download a bounded topical slice of Wikipedia, or onboard a client corpus."""
    config = load_config()
    if source == "client":
        if client_dir is None:
            raise typer.BadParameter("--source client requires the JSONL directory argument")
        contract = prepare_client_corpus(config, client_dir, license_name)
    elif source == "wikimedia":
        contract = prepare_corpus_impl(config)
    else:
        raise typer.BadParameter(f"unknown --source {source!r}; expected 'wikimedia' or 'client'")
    typer.echo(
        f"corpus ready: {contract.n_rows} articles "
        f"(sha256={contract.checksum_sha256[:12]}…) at {config.corpus_path}"
    )


@app.command()
def build_index(
    chunk_size: Annotated[
        list[int] | None,
        typer.Option("--chunk-size", help="Chunk sizes to index (default: config.chunk_sizes)."),
    ] = None,
) -> None:
    """Chunk, embed and persist a FAISS index per chunk size into data/index/."""
    config = load_config()
    sizes = chunk_size or config.chunk_sizes
    articles = load_corpus(config)
    embedder = SentenceTransformerEmbedder(config.embedding_model)
    for size in sizes:
        chunks = chunk_articles(articles, size=size, overlap=config.chunk_overlap)
        path = build_index_impl(
            chunks, embedder, config.index_path(size), description=f"size={size}"
        )
        typer.echo(f"index ready: {len(chunks)} chunks at {path}")


def _run_stress_pass(config: RAGConfig, stress_file: Path | None, stress_tag: str) -> None:
    """Execute a sealed stress pass and echo where its artifacts landed.

    Extracted from ``evaluate`` to keep that command under the complexity
    budget; error mapping (provider/budget) mirrors the other sealed passes.
    """
    try:
        payload = run_stress_evaluation(config, questions_path=stress_file, tag=stress_tag)
    except LLMProviderUnavailableError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except BudgetExceededError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    meter = payload["meter"]
    spend = (
        f", metered ${meter['total']['spend_usd']:.2f} cloud-equivalent" if meter["active"] else ""
    )
    typer.echo(
        f"sealed-set eval written: {config.reports_dir / 'metrics.json'} "
        f"(detail.stress{stress_tag}, backend={payload['ops']['backend']}{spend}; "
        f"question_traces_stress{stress_tag}.json)"
    )


@app.command()
def evaluate(
    ragas: Annotated[
        bool, typer.Option("--ragas", help="Also compute RAGAS metrics (local model as evaluator).")
    ] = False,
    heldout: Annotated[
        bool,
        typer.Option(
            "--heldout",
            help="Evaluate the sealed held-out golden set instead of the tuning set: "
            "retrieval metrics + one verify-on agent pass (no RAGAS), merged into "
            "metrics detail.heldout. Needs a provider.",
        ),
    ] = False,
    citations: Annotated[
        bool,
        typer.Option(
            "--citations",
            help="Citation-correctness pass: re-answer the sealed set once under the "
            "champion config with claim-level verify records persisted "
            "(reports/citation_records_heldout.json, metrics detail.heldout_citations). "
            "Never touches detail.heldout. Needs a provider.",
        ),
    ] = False,
    stress: Annotated[
        bool,
        typer.Option(
            "--stress",
            help="Stress pass: the independent sealed set admitted WITHOUT the "
            "production-retriever answerability gate (reports/question_traces_stress.json, "
            "metrics detail.stress). Needs a provider.",
        ),
    ] = False,
    stress_file: Annotated[
        Path | None,
        typer.Option(
            "--stress-file",
            help="Score a different sealed stress set (e.g. data/golden_stress_b.json) "
            "instead of the default frozen one. Requires --stress.",
        ),
    ] = None,
    stress_tag: Annotated[
        str,
        typer.Option(
            "--stress-tag",
            help="Artifact suffix for a non-default stress pass: traces are written as "
            "question_traces_stress<TAG>.json and metrics under detail.stress<TAG>. "
            "Leading underscore is conventional (e.g. _b). Requires --stress.",
        ),
    ] = "",
    max_questions: Annotated[
        int | None,
        typer.Option(
            "--max-questions",
            help="Bound the LLM phases (agent + RAGAS) to the first N graded questions; "
            "retrieval metrics always use the full set. Local 32B inference is slow.",
        ),
    ] = None,
    offline: Annotated[
        bool,
        typer.Option(
            "--offline",
            help="Retrieval-only: no LLM provider needed (skips agent, judges, RAGAS, telemetry).",
        ),
    ] = False,
    verify: Annotated[
        bool | None,
        typer.Option(
            "--verify/--no-verify",
            help="Override the verify-then-answer loop (params.yaml default: on). "
            "--no-verify reproduces the pre-wave-14 baseline answer path.",
        ),
    ] = None,
    reports_dir: Annotated[
        Path | None,
        typer.Option(
            "--reports-dir",
            help="Optional separate output directory for a challenger run; "
            "the committed incumbent artifacts stay untouched.",
        ),
    ] = None,
) -> None:
    """Run retrieval HPO + RAG eval + ops, writing reports/.

    The full path needs a model provider (local Ollama by default, or
    LLM_BASE_URL/LLM_API_KEY); use --offline for the CI-safe retrieval-only
    report, and --ragas to add the RAGAS metric set.
    """
    config = load_config()
    if reports_dir is not None:
        config.reports_dir = reports_dir
    if heldout or citations or stress:
        if offline:
            raise typer.BadParameter(
                "sealed-set passes need a provider and cannot combine with --offline"
            )
        if ragas:
            raise typer.BadParameter(
                "sealed-set passes bound cost with a verify-on pass only; no --ragas"
            )
        if max_questions is not None:
            raise typer.BadParameter(
                "sealed-set passes always run the full sealed set; no --max-questions"
            )
        if verify is not None:
            config.verify.enabled = verify
        if stress_file is not None and not stress:
            raise typer.BadParameter("--stress-file requires --stress")
        if stress_tag and not stress:
            raise typer.BadParameter("--stress-tag requires --stress")
        if stress:
            _run_stress_pass(config, stress_file, stress_tag)
            return
        runner = run_heldout_evaluation if heldout else run_citation_evaluation
        try:
            payload = runner(config)
        except LLMProviderUnavailableError as exc:
            typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
        except BudgetExceededError as exc:
            typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2) from exc
        meter = payload["meter"]
        spend = (
            f", metered ${meter['total']['spend_usd']:.2f} cloud-equivalent"
            if meter["active"]
            else ""
        )
        section = "detail.heldout" if heldout else "detail.heldout_citations"
        artifact = "question_traces_heldout.json" if heldout else "citation_records_heldout.json"
        typer.echo(
            f"sealed-set eval written: {config.reports_dir / 'metrics.json'} "
            f"({section}, backend={payload['ops']['backend']}{spend}; {artifact})"
        )
        return
    if offline and ragas:
        raise typer.BadParameter("--ragas requires a provider and cannot combine with --offline")
    try:
        run_evaluation(
            config, ragas=ragas, offline=offline, max_questions=max_questions, verify=verify
        )
    except LLMProviderUnavailableError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except BudgetExceededError as exc:
        # The hosted USD cap tripped mid-run: stop cleanly and say exactly what
        # to change (raise LLM_COST_LIMIT_USD or reduce scope) — never silently.
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"evaluation written: {config.reports_dir / 'report.html'}")


@app.command()
def compare_challenger(
    challenger_dir: Annotated[
        Path,
        typer.Option(
            "--challenger-dir",
            help="Separate reports directory written by a hosted challenger run.",
        ),
    ] = Path("reports/kimi-for-coding"),
) -> None:
    """Compare a challenger with the committed incumbent, without model calls."""
    from rag_agent.challenger import compare_challenger as compare

    config = load_config()
    result = compare(config, challenger_dir)
    typer.echo(
        f"selected={result['selected']}; comparison written: "
        f"{config.reports_dir / 'kimi_comparison.json'}"
    )


@app.command()
def rebuild_report() -> None:
    """Rebuild report.html offline from committed artifacts (metrics.json,
    figures/*.json, question_traces.json). For template changes; no model calls.
    """
    from rag_agent.reporting import rebuild_report_from_artifacts

    config = load_config()
    path = rebuild_report_from_artifacts(config)
    typer.echo(f"report rebuilt from artifacts: {path}")


@app.command()
def fusion() -> None:
    """Dense / BM25 / RRF(k=60) retrieval arms on tuning + sealed sets.

    Retrieval-only (rerank off, no LLM calls); writes reports/fusion.json and
    the fusion_arm_comparison figure. Compares out of the box (k=60, no
    tuning) whether fusion beats dense — the champion path is untouched.
    """
    from rag_agent.evaluate import run_fusion

    config = load_config()
    path = run_fusion(config)
    typer.echo(f"fusion comparison written to {path}")


@app.command()
def chat(
    question: Annotated[
        str | None, typer.Argument(help="Single question mode (non-interactive).")
    ] = None,
    verify: Annotated[
        bool | None,
        typer.Option(
            "--verify/--no-verify",
            help="Override the verify-then-answer loop (params.yaml default: on): "
            "unsupported claims are repaired/dropped, low-support answers abstain.",
        ),
    ] = None,
) -> None:
    """Interactive REPL: ask questions, get grounded AnalysisResult answers.

    Requires a model provider: local Ollama (platform default
    qwen3.6:35b-a3b-q4_K_M) or LLM_BASE_URL/LLM_API_KEY. There is no runtime mock.
    """
    config = load_config()
    if verify is not None:
        config.verify.enabled = verify
    default_size = config.chunk_sizes[len(config.chunk_sizes) // 2]
    retriever = Retriever.from_index_dir(
        config,
        config.index_path(default_size),
        SentenceTransformerEmbedder(config.embedding_model),
        CrossEncoderReranker(config.reranker_model),
    )
    try:
        agent = build_agent(config)
    except LLMProviderUnavailableError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    claim_judge: ClaimJudge | None = None
    if config.verify.enabled:
        claim_judge = build_claim_judge()
    typer.echo(
        f"RAG assistant ready (chunk_size={default_size}, backend={inference_backend()}, "
        f"verify={'on' if claim_judge else 'off'}). Type :quit to exit."
    )

    while True:
        try:
            prompt_text = question or typer.prompt("\nask", prompt_suffix="> ")
        except (EOFError, typer.Abort):
            typer.echo("\nbye")
            return
        if prompt_text.strip() in {":quit", ":q", "exit", "quit"}:
            typer.echo("bye")
            return
        result = agent.run_sync(prompt_text, deps=retriever)
        output = result.output
        if claim_judge is not None:
            report = verify_result(prompt_text, output, retriever, config, claim_judge)
            note = (
                f" [verified: support {report.support_fraction:.2f}, "
                f"{report.n_repair_calls} repair(s)"
                + (", abstained" if report.abstained else "")
                + (", skipped (already abstained)" if report.skipped else "")
                + "]"
            )
        else:
            note = ""
        typer.echo(f"\n[{output.confidence:.2f} confidence]{note} {output.summary}")
        for citation in output.citations:
            typer.echo(f"  [{citation.chunk_id}] {citation.title}: {citation.excerpt}")
        if question:
            return


def inference_backend() -> str:
    from rag_agent.evaluate import inference_backend as _backend

    return _backend()


if __name__ == "__main__":
    app()
