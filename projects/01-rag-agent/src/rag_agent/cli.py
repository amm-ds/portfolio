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
from portfolio_core.logging import get_logger

from rag_agent.agent import build_agent
from rag_agent.config import RAGConfig
from rag_agent.corpus import load_corpus, prepare_client_corpus
from rag_agent.corpus import prepare_corpus as prepare_corpus_impl
from rag_agent.evaluate import run as run_evaluation
from rag_agent.index import (
    CrossEncoderReranker,
    Retriever,
    SentenceTransformerEmbedder,
    chunk_articles,
)
from rag_agent.index import (
    build_index as build_index_impl,
)

app = typer.Typer(help=__doc__, add_completion=False)
logger = get_logger(__name__)


def load_config() -> RAGConfig:
    """RAGConfig defaults, overlaid with ``params.yaml`` when present (DVC)."""
    params_path = Path("params.yaml")
    if params_path.exists():
        import yaml  # type: ignore[import-untyped]

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
def evaluate() -> None:
    """Run retrieval sweep + RAG eval + ops, writing reports/."""
    config = load_config()
    run_evaluation(config)
    typer.echo(f"evaluation written: {config.reports_dir / 'report.html'}")


@app.command()
def chat(
    question: Annotated[
        str | None, typer.Argument(help="Single question mode (non-interactive).")
    ] = None,
) -> None:
    """Interactive REPL: ask questions, get grounded AnalysisResult answers."""
    config = load_config()
    default_size = config.chunk_sizes[len(config.chunk_sizes) // 2]
    retriever = Retriever.from_index_dir(
        config,
        config.index_path(default_size),
        SentenceTransformerEmbedder(config.embedding_model),
        CrossEncoderReranker(config.reranker_model),
    )
    agent = build_agent(config)
    typer.echo(
        f"RAG assistant ready (chunk_size={default_size}, model="
        f"{'provider' if _provider_configured() else 'MOCK offline'}). Type :quit to exit."
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
        typer.echo(f"\n[{output.confidence:.2f} confidence] {output.summary}")
        for citation in output.citations:
            typer.echo(f"  [{citation.chunk_id}] {citation.title}: {citation.excerpt}")
        if question:
            return


def _provider_configured() -> bool:
    from portfolio_core.config import get_settings

    settings = get_settings()
    return bool(settings.llm_api_key and settings.llm_base_url)


if __name__ == "__main__":
    app()
