"""Conversation storage: roundtrips through the SQLite fallback."""

from pathlib import Path

from pydantic_ai.conversation import Conversation
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from agent_chat.config import Settings
from agent_chat.memory import SQLiteConversationStore
from agent_chat.memory.conversations import _dump


def _conversation(conversation_id: str = "conv-1") -> Conversation:
    """A conversation with a user turn, a tool call, and its return."""
    return Conversation(
        conversation_id=conversation_id,
        messages=[
            ModelRequest(parts=[UserPromptPart(content="What is 2+2?")]),
            ModelResponse(
                parts=[
                    ToolCallPart(tool_call_id="c1", tool_name="calculator", args={"expr": "2+2"})
                ]
            ),
            ModelRequest(
                parts=[ToolReturnPart(tool_call_id="c1", tool_name="calculator", content="4.0")]
            ),
            ModelResponse(parts=[TextPart(content="2+2 = 4.")]),
        ],
    )


class TestSQLiteConversationStore:
    async def test_save_get_roundtrip(self, conversation_store: SQLiteConversationStore) -> None:
        conversation = _conversation()
        await conversation_store.save(conversation, title="math question", session_id="session-a")

        stored = await conversation_store.get("conv-1", session_id="session-a")
        assert stored is not None
        assert stored.meta.title == "math question"
        assert stored.meta.message_count == len(conversation.messages) == 4
        # the full message history survives serialization
        first_request = stored.conversation.messages[0]
        assert isinstance(first_request, ModelRequest)
        first_part = first_request.parts[0]
        assert isinstance(first_part, UserPromptPart)
        assert first_part.content == "What is 2+2?"
        last = stored.conversation.messages[-1]
        assert isinstance(last, ModelResponse)
        assert isinstance(last.parts[0], TextPart)

    async def test_get_unknown_returns_none(
        self, conversation_store: SQLiteConversationStore
    ) -> None:
        assert await conversation_store.get("nope", session_id="session-a") is None

    async def test_list_orders_newest_first(
        self, conversation_store: SQLiteConversationStore
    ) -> None:
        await conversation_store.save(
            _conversation("conv-a"), title="first", session_id="session-a"
        )
        await conversation_store.save(
            _conversation("conv-b"), title="second", session_id="session-a"
        )
        metas = await conversation_store.list(session_id="session-a")
        assert [m.conversation_id for m in metas] == ["conv-b", "conv-a"]
        assert {m.title for m in metas} == {"first", "second"}

    async def test_overwrite_keeps_one_row(
        self, conversation_store: SQLiteConversationStore
    ) -> None:
        await conversation_store.save(_conversation(), title="before", session_id="session-a")
        longer = _conversation()
        longer.messages.append(ModelRequest(parts=[UserPromptPart(content="and 3+3?")]))
        await conversation_store.save(longer, title="after", session_id="session-a")
        assert len(await conversation_store.list(session_id="session-a")) == 1
        stored = await conversation_store.get("conv-1", session_id="session-a")
        assert stored is not None and stored.meta.title == "after"
        assert stored.meta.message_count == 5

    async def test_delete(self, conversation_store: SQLiteConversationStore) -> None:
        await conversation_store.save(_conversation(), title="bye", session_id="session-a")
        assert await conversation_store.delete("conv-1", session_id="session-a") is True
        assert await conversation_store.get("conv-1", session_id="session-a") is None
        assert await conversation_store.delete("conv-1", session_id="session-a") is False

    async def test_sessions_cannot_read_list_or_delete_each_other(
        self, conversation_store: SQLiteConversationStore
    ) -> None:
        await conversation_store.save(_conversation("conv-a"), title="A", session_id="session-a")
        await conversation_store.save(_conversation("conv-b"), title="B", session_id="session-b")

        assert [
            m.conversation_id for m in await conversation_store.list(session_id="session-a")
        ] == ["conv-a"]
        assert [
            m.conversation_id for m in await conversation_store.list(session_id="session-b")
        ] == ["conv-b"]
        assert await conversation_store.get("conv-a", session_id="session-b") is None
        assert await conversation_store.delete("conv-a", session_id="session-b") is False
        assert await conversation_store.get("conv-a", session_id="session-a") is not None

    async def test_persistence_across_instances(
        self, conversation_store: SQLiteConversationStore, settings: Settings
    ) -> None:
        """A second store on the same file sees what the first wrote."""
        from agent_chat.memory import build_conversation_store

        await conversation_store.save(_conversation(), title="persisted", session_id="session-a")
        reopened = build_conversation_store(settings)
        assert isinstance(reopened, SQLiteConversationStore)
        stored = await reopened.get("conv-1", session_id="session-a")
        assert stored is not None and stored.meta.title == "persisted"
        await reopened.close()

    async def test_old_schema_gets_additive_session_migration(self, tmp_path: Path) -> None:
        import sqlite3

        path = tmp_path / "old.db"
        connection = sqlite3.connect(path)
        connection.execute(
            "CREATE TABLE conversations ("
            "conversation_id VARCHAR(64) PRIMARY KEY, title VARCHAR(200) NOT NULL, "
            "data TEXT NOT NULL, updated_at VARCHAR(40) NOT NULL)"
        )
        connection.execute(
            "INSERT INTO conversations VALUES (?, ?, ?, ?)",
            ("conv-1", "legacy", _dump(_conversation()), "2026-01-01T00:00:00+00:00"),
        )
        connection.commit()
        connection.close()

        store = SQLiteConversationStore(path)
        columns = {row[1] for row in store._conn.execute("PRAGMA table_info(conversations)")}
        assert "session_id" in columns
        assert await store.get("conv-1", session_id="new-session") is None
        assert await store.get("conv-1", session_id="legacy") is not None
        await store.close()
