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
from rag_agent.evaluate import run_heldout as run_heldout_evaluation
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
    """RAGConfig defaults, overlaid with ``params.yaml`` when present (DVC)."""
    params_path = Path("params.yaml")
    if params_path.exists():
        import yaml  # type: ignore[import-untyped]  # PyYAML has no stubs; mkdocs transitive dep

        data = yaml.safe_load(params_path.read_text(encoding="utf-8")) or {}
        unknown = set(data) - set(RAGConfig.model_fields)
        if unknown:
            logger.warning("params.yaml has keys outside RAGConfig, ignored: %s", sorted(unknown))
        return RAGConfig(**{k: v for k, v in data.items() if k in RAGConfig.model_fields})
    return RAGConfig()


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
) -> None:
    """Run retrieval HPO + RAG eval + ops, writing reports/.

    The full path needs a model provider (local Ollama by default, or
    LLM_BASE_URL/LLM_API_KEY); use --offline for the CI-safe retrieval-only
    report, and --ragas to add the RAGAS metric set.
    """
    config = load_config()
    if heldout:
        if offline:
            raise typer.BadParameter("--heldout needs a provider and cannot combine with --offline")
        if ragas:
            raise typer.BadParameter("--heldout bounds cost with a verify-on pass only; no --ragas")
        if max_questions is not None:
            raise typer.BadParameter(
                "--heldout always runs the full sealed set; no --max-questions"
            )
        if verify is not None:
            config.verify.enabled = verify
        try:
            payload = run_heldout_evaluation(config)
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
        typer.echo(
            f"held-out eval written: {config.reports_dir / 'metrics.json'} "
            f"(detail.heldout, backend={payload['ops']['backend']}{spend})"
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

    Requires a model provider: local Ollama (default qwen3:32b) or
    LLM_BASE_URL/LLM_API_KEY. There is no runtime mock.
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
