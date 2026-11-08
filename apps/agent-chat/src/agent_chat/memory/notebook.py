"""A persistent browser-session notebook following the Harness Memory pattern.

Each validated session id maps to one JSON file under the configured data dir.
The agent writes concise facts and retrieves bounded lexical matches on demand;
nothing from the notebook is automatically added to instructions or prompts.
Atomic replacement makes completed writes durable across processes. Concurrent
writers to the same session file are serialized only within one store instance;
use a transactional backend before allowing cross-process concurrent writes.
"""

import asyncio
import os
import re
import tempfile
import threading
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

_SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_MEMORY_KEY = re.compile(r"[a-z][a-z0-9_]{0,63}")
_TERM = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset({"about", "know", "mine", "recall", "remember", "tell", "what", "your"})


class MemoryNote(BaseModel):
    """One session fact; a stable key supports updates without paraphrase duplicates."""

    id: str
    fact: str = Field(min_length=1, max_length=4000)
    created_at: str
    key: str | None = None
    updated_at: str | None = None


class _NotebookData(BaseModel):
    version: int = 2
    notes: list[MemoryNote] = Field(default_factory=list)


class NotebookStore(Protocol):
    """Session-scoped storage; identity never enters model tool arguments."""

    async def remember(
        self, session_id: str, fact: str, *, key: str | None = None
    ) -> MemoryNote: ...

    async def recall(self, session_id: str, query: str, *, limit: int = 5) -> list[MemoryNote]: ...


def _path_for(data_dir: Path, session_id: str) -> Path:
    if _SESSION_ID.fullmatch(session_id) is None or session_id in {".", ".."}:
        raise ValueError("session_id must be 1-128 safe filename characters")
    return data_dir / f"{session_id}.json"


def _read(path: Path) -> _NotebookData:
    if not path.exists():
        return _NotebookData()
    return _NotebookData.model_validate_json(path.read_text(encoding="utf-8"))


def _write(path: Path, data: _NotebookData) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary = handle.name
            handle.write(data.model_dump_json(indent=2))
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def _terms(text: str) -> set[str]:
    return {
        term
        for term in _TERM.findall(text.casefold())
        if len(term) >= 3 and term not in _STOP_WORDS
    }


class FileNotebook:
    """One-file-per-session durable notebook with bounded, ranked recall."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._lock = threading.Lock()

    def path_for(self, session_id: str) -> Path:
        """The backing path, exposed for operations and persistence tests."""
        return _path_for(self.data_dir, session_id)

    async def remember(self, session_id: str, fact: str, *, key: str | None = None) -> MemoryNote:
        """Upsert a keyed fact, or deduplicate an unkeyed exact repeat."""
        normalized = " ".join(fact.split())
        if not normalized:
            raise ValueError("fact must not be empty")
        if len(normalized) > 4000:
            raise ValueError("fact must be at most 4000 characters")
        normalized_key = key.strip().lower() if key is not None else None
        if normalized_key is not None and _MEMORY_KEY.fullmatch(normalized_key) is None:
            raise ValueError("key must be 1-64 lowercase snake_case characters")
        path = self.path_for(session_id)

        def _remember() -> MemoryNote:
            with self._lock:
                data = _read(path)
                folded_fact = normalized.casefold()
                now = datetime.now(UTC).isoformat(timespec="seconds")
                for index, existing in enumerate(data.notes):
                    if normalized_key is not None and existing.key == normalized_key:
                        if existing.fact == normalized:
                            return existing
                        updated = existing.model_copy(
                            update={"fact": normalized, "updated_at": now}
                        )
                        data.notes[index] = updated
                        data.version = 2
                        _write(path, data)
                        return updated
                    if (
                        normalized_key is None
                        and existing.key is None
                        and existing.fact.casefold() == folded_fact
                    ):
                        return existing
                identity = (
                    f"key:{normalized_key}" if normalized_key is not None else f"fact:{folded_fact}"
                )
                note = MemoryNote(
                    id=sha256(identity.encode("utf-8")).hexdigest()[:16],
                    fact=normalized,
                    created_at=now,
                    key=normalized_key,
                )
                data.notes.append(note)
                data.version = 2
                _write(path, data)
                return note

        return await asyncio.to_thread(_remember)

    async def recall(self, session_id: str, query: str, *, limit: int = 5) -> list[MemoryNote]:
        """Return only notes sharing query terms, best matches and newest first."""
        if not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        path = self.path_for(session_id)
        terms = _terms(query)
        if not terms:
            return []
        notes = await asyncio.to_thread(lambda: _read(path).notes)
        ranked: list[tuple[int, int, MemoryNote]] = []
        for position, note in enumerate(notes):
            folded = f"{note.key or ''} {note.fact}".casefold()
            score = sum(folded.count(term) for term in terms)
            if score:
                ranked.append((score, position, note))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [note for _, _, note in ranked[:limit]]
