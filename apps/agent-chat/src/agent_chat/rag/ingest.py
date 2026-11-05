"""The ingest pipeline: markdown/txt files -> chunks -> embeddings -> store.

Runs as a CLI (``agent-chat-ingest`` / ``python -m agent_chat.rag.ingest``)
and as :func:`ingest`, which the API's ``POST /ingest`` reuses. Idempotent in
spirit: ingesting the same file twice duplicates chunks (document versioning
is deliberately out of scope for the template — call ``clear()`` first).
"""

import argparse
import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from agent_chat.config import Settings
from agent_chat.rag.chunking import chunk_text, load_documents
from agent_chat.rag.embeddings import Embedder, build_embedder
from agent_chat.rag.store import VectorStore, build_vector_store


@dataclass(frozen=True)
class IngestResult:
    """What one ingest run read and stored."""

    files: int
    chunks: int


async def ingest(
    paths: Sequence[Path],
    *,
    store: VectorStore,
    embedder: Embedder,
) -> IngestResult:
    """Chunk ``paths`` (files and/or directories), embed, and store."""
    documents = load_documents(paths)
    chunks = [c for source, text in documents for c in chunk_text(source, text)]
    if not chunks:
        return IngestResult(files=0, chunks=0)
    embeddings = await embedder.embed([c.text for c in chunks])
    stored = await store.add(chunks, embeddings)
    return IngestResult(files=len(documents), chunks=stored)


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entry point: ``agent-chat-ingest <paths...> [--embedder NAME]``."""
    parser = argparse.ArgumentParser(
        description="Ingest markdown/txt documents into the vector store."
    )
    parser.add_argument("paths", nargs="+", type=Path, help="Files or directories to ingest.")
    parser.add_argument(
        "--embedder",
        choices=["minilm", "hashing"],
        default=None,
        help="Override AGENT_CHAT_EMBEDDER.",
    )
    args = parser.parse_args(argv)

    settings = Settings() if args.embedder is None else Settings(embedder=args.embedder)
    embedder = build_embedder(settings)
    store = build_vector_store(settings, embedder.dim)

    async def _run() -> IngestResult:
        await store.init()
        try:
            return await ingest(args.paths, store=store, embedder=embedder)
        finally:
            await store.close()

    result = asyncio.run(_run())
    print(json.dumps({"files": result.files, "chunks": result.chunks}))


if __name__ == "__main__":
    main()
