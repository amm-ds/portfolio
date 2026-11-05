"""RAG: chunking, the SQLite store, ingest end-to-end, and the retrieve tool."""

from pathlib import Path

from agent_chat.rag.chunking import chunk_text, load_documents
from agent_chat.rag.embeddings import HashingEmbedder
from agent_chat.rag.ingest import ingest
from agent_chat.rag.store import SQLiteVectorStore
from agent_chat.rag.tool import build_retrieve_tool


class TestChunking:
    def test_paragraphs_become_chunks(self) -> None:
        text = "First paragraph here.\n\nSecond paragraph here.\n\nThird one."
        chunks = chunk_text("doc.md", text)
        assert [c.index for c in chunks] == list(range(len(chunks)))
        assert all(c.source == "doc.md" for c in chunks)
        assert "First paragraph" in chunks[0].text

    def test_long_document_splits_with_overlap(self) -> None:
        paragraph = "word " * 200  # ~1000 chars, one paragraph
        chunks = chunk_text("big.md", paragraph, max_chars=200, overlap=20)
        assert len(chunks) > 1
        assert all(len(c.text) <= 220 for c in chunks)  # hard-split tolerance
        # overlap carries context between neighbors
        assert chunks[1].text[:20] in chunks[0].text[-40:]

    def test_empty_text_yields_no_chunks(self) -> None:
        assert chunk_text("empty.md", "   \n  \n ") == []


class TestLoadDocuments:
    def test_directory_walk_skips_unsupported_suffixes(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("alpha", encoding="utf-8")
        (tmp_path / "b.txt").write_text("beta", encoding="utf-8")
        (tmp_path / "c.csv").write_text("gamma", encoding="utf-8")
        docs = dict(load_documents([tmp_path]))
        assert len(docs) == 2
        assert str(tmp_path / "c.csv") not in docs

    def test_missing_path_reads_nothing(self, tmp_path: Path) -> None:
        assert load_documents([tmp_path / "nope.md"]) == []


class TestSQLiteStore:
    async def test_add_search_clear_roundtrip(self, vector_store: SQLiteVectorStore) -> None:
        embedder = HashingEmbedder()
        chunks = chunk_text("doc.md", "Refunds are available within 30 days of purchase.")
        vectors = await embedder.embed([c.text for c in chunks])
        assert await vector_store.add(chunks, vectors) == len(chunks)

        hits = await vector_store.search((await embedder.embed(["refund window"]))[0], top_k=3)
        assert hits and "refund" in hits[0].content.lower()
        assert 0.0 < hits[0].score <= 1.0

        await vector_store.clear()
        assert await vector_store.search((await embedder.embed(["refund"]))[0]) == []

    async def test_ping(self, vector_store: SQLiteVectorStore) -> None:
        assert await vector_store.ping() is True


class TestIngestPipeline:
    async def test_ingest_files_then_retrieve(
        self, seeded_store: SQLiteVectorStore, embedder: HashingEmbedder
    ) -> None:
        retrieve = build_retrieve_tool(seeded_store, embedder)
        hits = await retrieve("How fast is the severity-1 first response?")
        assert hits and any("1 hour" in hit for hit in hits)
        assert any("sla.md" in hit for hit in hits)

    async def test_ingest_empty_directory(
        self, vector_store: SQLiteVectorStore, tmp_path: Path
    ) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        result = await ingest([empty], store=vector_store, embedder=HashingEmbedder())
        assert result.files == 0 and result.chunks == 0
