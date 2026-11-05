"""Conversation storage: pydantic-ai ``Conversation`` objects, persisted.

The store keeps whole :class:`~pydantic_ai.conversation.Conversation` values
(messages + usage + conversation_id) as JSON — the unit pydantic-ai's
conversation API passes between runs. Postgres via SQLAlchemy async is the
primary store; a stdlib-SQLite fallback (same shape, file-backed) keeps local
development docker-free. Select with ``database_url``.
"""

import asyncio
import sqlite3
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic_ai.conversation import Conversation, ConversationTypeAdapter
from sqlalchemy import String, Text, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agent_chat.config import Settings


@dataclass(frozen=True)
class ConversationMeta:
    """Listing row: what a client needs to render a conversation list."""

    conversation_id: str
    title: str
    updated_at: str
    message_count: int


@dataclass(frozen=True)
class StoredConversation:
    """A full conversation plus its listing metadata."""

    meta: ConversationMeta
    conversation: Conversation


class ConversationStore(Protocol):
    """Save and reload conversations by ``conversation_id``."""

    async def init(self) -> None: ...

    async def save(self, conversation: Conversation, *, title: str) -> None: ...

    async def get(self, conversation_id: str) -> StoredConversation | None: ...

    async def list(self) -> list[ConversationMeta]: ...

    async def delete(self, conversation_id: str) -> bool: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...


def _meta_from(conversation: Conversation, *, title: str) -> ConversationMeta:
    return ConversationMeta(
        conversation_id=conversation.conversation_id,
        title=title,
        updated_at=datetime.now(UTC).isoformat(timespec="microseconds"),
        message_count=len(conversation.messages),
    )


def _dump(conversation: Conversation) -> str:
    return ConversationTypeAdapter.dump_json(conversation).decode("utf-8")


def _load(payload: str) -> Conversation:
    return ConversationTypeAdapter.validate_json(payload)


# --- Postgres ----------------------------------------------------------------


class _Base(DeclarativeBase):
    pass


class ConversationRow(_Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    data: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(String(40))


_DDL = (
    "CREATE TABLE IF NOT EXISTS conversations ("
    "conversation_id VARCHAR(64) PRIMARY KEY, "
    "title VARCHAR(200) NOT NULL, "
    "data TEXT NOT NULL, "
    "updated_at VARCHAR(40) NOT NULL)"
)


class PostgresConversationStore:
    """SQLAlchemy-async conversation store."""

    def __init__(self, database_url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(database_url)
        self._session = async_sessionmaker(self._engine, expire_on_commit=False)

    async def init(self) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(text(_DDL))

    async def save(self, conversation: Conversation, *, title: str) -> None:
        meta = _meta_from(conversation, title=title)
        async with self._session() as session:
            await session.merge(
                ConversationRow(
                    conversation_id=meta.conversation_id,
                    title=meta.title,
                    data=_dump(conversation),
                    updated_at=meta.updated_at,
                )
            )
            await session.commit()

    async def get(self, conversation_id: str) -> StoredConversation | None:
        async with self._session() as session:
            row = await session.get(ConversationRow, conversation_id)
        if row is None:
            return None
        conversation = _load(row.data)
        meta = ConversationMeta(
            conversation_id=row.conversation_id,
            title=row.title,
            updated_at=row.updated_at,
            message_count=len(conversation.messages),
        )
        return StoredConversation(meta=meta, conversation=conversation)

    async def list(self) -> list[ConversationMeta]:
        async with self._session() as session:
            rows = (
                (
                    await session.execute(
                        select(ConversationRow).order_by(ConversationRow.updated_at.desc())
                    )
                )
                .scalars()
                .all()
            )
        return [
            ConversationMeta(
                conversation_id=row.conversation_id,
                title=row.title,
                updated_at=row.updated_at,
                message_count=len(_load(row.data).messages),
            )
            for row in rows
        ]

    async def delete(self, conversation_id: str) -> bool:
        async with self._session() as session:
            row = await session.get(ConversationRow, conversation_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def ping(self) -> bool:
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:  # broad: readiness is a yes/no probe
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()


# --- SQLite fallback ----------------------------------------------------------


class SQLiteConversationStore:
    """File-backed stand-in for local dev and tests (same row shape)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        with self._lock:
            self._conn.execute(_DDL)
            self._conn.commit()

    async def init(self) -> None:
        """The table is created in ``__init__``; nothing further to prepare."""

    async def save(self, conversation: Conversation, *, title: str) -> None:
        meta = _meta_from(conversation, title=title)

        def _upsert() -> None:
            with self._lock:
                self._conn.execute(
                    "INSERT OR REPLACE INTO conversations "
                    "(conversation_id, title, data, updated_at) VALUES (?, ?, ?, ?)",
                    (meta.conversation_id, meta.title, _dump(conversation), meta.updated_at),
                )
                self._conn.commit()

        await asyncio.to_thread(_upsert)

    async def get(self, conversation_id: str) -> StoredConversation | None:
        def _fetch() -> tuple[str, str, str] | None:
            with self._lock:
                row = self._conn.execute(
                    "SELECT title, data, updated_at FROM conversations WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()
            return row if row is None else (str(row[0]), str(row[1]), str(row[2]))

        fetched = await asyncio.to_thread(_fetch)
        if fetched is None:
            return None
        title, data, updated_at = fetched
        conversation = _load(data)
        meta = ConversationMeta(
            conversation_id=conversation_id,
            title=title,
            updated_at=updated_at,
            message_count=len(conversation.messages),
        )
        return StoredConversation(meta=meta, conversation=conversation)

    async def list(self) -> list[ConversationMeta]:
        def _fetchall() -> Sequence[tuple[str, str, str]]:
            with self._lock:
                return self._conn.execute(
                    "SELECT conversation_id, title, updated_at FROM conversations "
                    "ORDER BY updated_at DESC"
                ).fetchall()

        rows = await asyncio.to_thread(_fetchall)
        return [
            ConversationMeta(
                conversation_id=str(row[0]),
                title=str(row[1]),
                updated_at=str(row[2]),
                message_count=0,  # listing stays cheap; counts come from GET /conversations/{id}
            )
            for row in rows
        ]

    async def delete(self, conversation_id: str) -> bool:
        def _delete() -> int:
            with self._lock:
                cursor = self._conn.execute(
                    "DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,)
                )
                self._conn.commit()
            return cursor.rowcount

        return await asyncio.to_thread(_delete) > 0

    async def ping(self) -> bool:
        return self._path.exists()

    async def close(self) -> None:
        await asyncio.to_thread(self._conn.close)


def build_conversation_store(settings: Settings) -> ConversationStore:
    """Postgres for ``postgres*`` URLs; SQLite (file) otherwise."""
    if settings.database_url.startswith("postgres"):
        return PostgresConversationStore(settings.database_url)
    return SQLiteConversationStore(sqlite_path_from_url(settings.database_url))


def sqlite_path_from_url(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError(f"not a sqlite URL: {database_url!r}")
    return Path(database_url[len(prefix) :])
