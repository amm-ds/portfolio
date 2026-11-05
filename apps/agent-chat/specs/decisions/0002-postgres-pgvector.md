# ADR-0002: Postgres + pgvector for storage and retrieval

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

The chassis persists two things: conversations (opaque JSON blobs of
pydantic-ai `Conversation` values) and retrieval chunks with their embeddings.
The template must also run docker-free on a laptop for local development and
in CI, and it must stay lift-out-able — an adopter should not inherit a
migration framework or a second database on day one.

## Decision

One database for both concerns: **Postgres 16 + pgvector** in the compose
stack, reached through SQLAlchemy async + asyncpg.

- The `rag_chunks.embedding` column is `VECTOR(dim)` with an HNSW index using
  `vector_cosine_ops` (`m = 16`, `ef_construction = 64`), created by
  `PgVectorStore.init()` as raw DDL — extension, table, and index exist after
  the first startup, no migration tool.
- Similarity is cosine everywhere; scores are returned in `[-1, 1]`.
- Behind the `VectorStore` and `ConversationStore` protocols, a stdlib-SQLite
  fallback implements the same row shapes for local dev and tests. The SQLite
  vector path scans the table in Python: fine at template scale (< ~10k
  chunks), not for real corpora. `AGENT_CHAT_DATABASE_URL` selects the
  implementation; the agent and ingest CLI never know which they hold.

## Swap points

The protocol seam keeps two upgrades local:

- **pgvecto.rs** (same Postgres box, different extension): replace the DDL
  strings and the distance expression in `rag/store.py`; the table/column
  shapes and the `VectorStore` protocol are unchanged. Motivation is usually
  index build time or recall tuning at larger scale, not features the
  protocol needs.
- **Qdrant** (separate vector service): implement `VectorStore` against the
  Qdrant client — `add` becomes upsert with the embedding as the vector and
  `source`/`chunk_index`/`content` as payload, `search` becomes a query with
  `score` mapped to cosine. Nothing above `rag/store.py` changes.

## When to switch

- **SQLite fallback → pgvector:** from the first real deployment. The SQLite
  path exists so tests and laptop demos need nothing installed.
- **pgvector → pgvecto.rs or Qdrant:** when the corpus or query pattern
  outgrows a single-node Postgres index — think hundreds of thousands of
  chunks, heavy filtered search, multi-tenant isolation, or an ops team
  already running a dedicated vector service. At template scale (thousands of
  chunks) pgvector's HNSW index answers in single-digit milliseconds and the
  extra service is not justified.

## Consequences

- One container in the stack; backups, restores, and credentials are plain
  Postgres (see `specs/operations.md`).
- The embedding dimension is a schema property (`VECTOR(dim)`), so changing
  the embedder requires re-ingesting — recorded in `specs/adapting.md`.
- Adopters with an existing vector estate pay exactly one small adapter, not
  a rewrite.
