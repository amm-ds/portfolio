"""Durable conversation state, personal notes, and bounded model history.

``conversations`` stores whole pydantic-ai ``Conversation`` values. ``notebook``
implements the pydantic-ai Harness Memory pattern with on-demand recall: one
JSON notebook per user, no automatic notebook injection. ``history`` provides
sliding-window trimming and optional summarize-on-overflow processors.
"""

from agent_chat.memory.conversations import (
    ConversationMeta,
    ConversationStore,
    PostgresConversationStore,
    SQLiteConversationStore,
    StoredConversation,
    build_conversation_store,
    sqlite_path_from_url,
)
from agent_chat.memory.notebook import FileNotebook, MemoryNote, NotebookStore

__all__ = [
    "ConversationMeta",
    "ConversationStore",
    "FileNotebook",
    "MemoryNote",
    "NotebookStore",
    "PostgresConversationStore",
    "SQLiteConversationStore",
    "StoredConversation",
    "build_conversation_store",
    "sqlite_path_from_url",
]
