"""Vector stores: pgvector-backed (prod) and SQLite-backed (dev/tests).

Both implement the same :class:`VectorStore` protocol — the agent and the
ingest CLI never know which they hold. Similarity is cosine. The SQLite
fallback scans the table in Python: fine for the template's scale (thousands
of chunks), not for corpora — point ``database_url`` at Postgres for
HNSW-accelerated search.
"""

import asyncio
import json
import math
import sqlite3
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, Text, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agent_chat.config import Settings
from agent_chat.rag.chunking import Chunk


@dataclass(frozen=True)
class ChunkHit:
    """One search result: the chunk, its source, and a cosine score in [-1, 1]."""

    chunk_id: int
    source: str
    chunk_index: int
    content: str
    score: float


class VectorStore(Protocol):
    """Chunk + embedding storage with cosine search."""

    async def init(self) -> None: ...

    async def add(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> int: ...

    async def search(self, query_embedding: Sequence[float], top_k: int = 4) -> list[ChunkHit]: ...

    async def clear(self) -> None: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity; pure python so the SQLite store needs no numpy."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# --- Postgres + pgvector ----------------------------------------------------


class _Base(DeclarativeBase):
    pass


class VectorChunk(_Base):
    """ORM mapping for reads/writes; DDL itself is issued raw in ``init`` so a
    process never relies on ``create_all`` for the vector column/HNSW index."""

    __tablename__ = "rag_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(512), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding = Column(Vector())


_DDL_EXTENSION = "CREATE EXTENSION IF NOT EXISTS vector"
_DDL_TABLE = (
    "CREATE TABLE IF NOT EXISTS rag_chunks ("
    "id BIGSERIAL PRIMARY KEY, "
    "source VARCHAR(512) NOT NULL, "
    "chunk_index INTEGER NOT NULL, "
    "content TEXT NOT NULL, "
    "embedding VECTOR({dim}) NOT NULL)"
)
_DDL_INDEX = (
    "CREATE INDEX IF NOT EXISTS rag_chunks_embedding_hnsw ON rag_chunks "
    "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
)


class PgVectorStore:
    """Async SQLAlchemy + pgvector store with an HNSW cosine index."""

    def __init__(self, database_url: str, dim: int) -> None:
        self._engine: AsyncEngine = create_async_engine(database_url)
        self._session = async_sessionmaker(self._engine, expire_on_commit=False)
        self._dim = dim

    async def init(self) -> None:
        """Create the extension, table, and HNSW index when they are missing."""
        async with self._engine.begin() as conn:
            await conn.execute(text(_DDL_EXTENSION))
            await conn.execute(text(_DDL_TABLE.format(dim=self._dim)))
            await conn.execute(text(_DDL_INDEX))

    async def add(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> int:
        rows = [
            VectorChunk(source=c.source, chunk_index=c.index, content=c.text, embedding=list(vec))
            for c, vec in zip(chunks, embeddings, strict=True)
        ]
        async with self._session() as session:
            session.add_all(rows)
            await session.commit()
        return len(rows)

    async def search(self, query_embedding: Sequence[float], top_k: int = 4) -> list[ChunkHit]:
        distance: Any = VectorChunk.embedding.cosine_distance(list(query_embedding))
        async with self._session() as session:
            rows = (
                await session.execute(select(VectorChunk, distance).order_by(distance).limit(top_k))
            ).all()
        return [
            ChunkHit(
                chunk_id=row[0].id,
                source=row[0].source,
                chunk_index=row[0].chunk_index,
                content=row[0].content,
                score=round(1.0 - float(row[1]), 6),
            )
            for row in rows
        ]

    async def clear(self) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE rag_chunks"))

    async def ping(self) -> bool:
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:  # broad: readiness is a yes/no probe
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()


# --- SQLite fallback --------------------------------------------------------


class SQLiteVectorStore:
    """File-backed stand-in for local dev and tests.

    shortcut: full-table scan with in-python cosine — fine at template scale
    (< ~10k chunks); upgrade by pointing database_url at Postgres.
    """

    def __init__(self, path: Path, dim: int) -> None:
        self._path = path
        self._dim = dim
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS rag_chunks ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "source VARCHAR(512) NOT NULL, chunk_index INTEGER NOT NULL, "
                "content TEXT NOT NULL, embedding TEXT NOT NULL)"
            )
            self._conn.commit()

    async def init(self) -> None:
        """Table creation happens in ``__init__``; nothing further to prepare."""

    async def add(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> int:
        rows = [
            (c.source, c.index, c.text, json.dumps(list(vec)))
            for c, vec in zip(chunks, embeddings, strict=True)
        ]

        def _insert() -> int:
            with self._lock:
                self._conn.executemany(
                    "INSERT INTO rag_chunks (source, chunk_index, content, embedding) "
                    "VALUES (?, ?, ?, ?)",
                    rows,
                )
                self._conn.commit()
            return len(rows)

        return await asyncio.to_thread(_insert)

    async def search(self, query_embedding: Sequence[float], top_k: int = 4) -> list[ChunkHit]:
        def _scan() -> list[tuple[int, str, int, str, float]]:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT id, source, chunk_index, content, embedding FROM rag_chunks"
                ).fetchall()
            scored = [
                (row[0], row[1], row[2], row[3], cosine(query_embedding, json.loads(row[4])))
                for row in rows
            ]
            scored.sort(key=lambda r: (-r[4], r[0]))
            return scored[:top_k]

        return [
            ChunkHit(
                chunk_id=r[0], source=r[1], chunk_index=r[2], content=r[3], score=round(r[4], 6)
            )
            for r in await asyncio.to_thread(_scan)
        ]

    async def clear(self) -> None:
        def _wipe() -> None:
            with self._lock:
                self._conn.execute("DELETE FROM rag_chunks")
                self._conn.commit()

        await asyncio.to_thread(_wipe)

    async def ping(self) -> bool:
        return self._path.exists()

    async def close(self) -> None:
        await asyncio.to_thread(self._conn.close)


def sqlite_path_from_url(database_url: str) -> Path:
    """Map ``sqlite:///<path>`` to a filesystem path."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError(f"not a sqlite URL: {database_url!r}")
    return Path(database_url[len(prefix) :])


def build_vector_store(settings: Settings, dim: int) -> VectorStore:
    """Resolve the store from ``database_url``: Postgres when the URL says so,
    SQLite otherwise (including the default local file)."""
    if settings.database_url.startswith("postgres"):
        return PgVectorStore(settings.database_url, dim)
    return SQLiteVectorStore(sqlite_path_from_url(settings.database_url), dim)
