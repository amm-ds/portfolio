"""Tests for the cross-project ``search_documents`` tool.

Unit tests build a tiny fixture FAISS index (deterministic fake embedder — no
network, no dependency on 01's data) and point the tool at it; one integration
test loads 01's real index and is skip-marked when it is absent. The t15 and
held-out h12 ground-truth facts are pinned against the fixture/real index so
graders cannot drift from the corpus.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import numpy as np
import pytest
from agentic_workflows import documents, evals
from agentic_workflows.documents import get_retriever, search_documents
from agentic_workflows.schemas import TaskRunRecord
from pydantic_evals.evaluators import EvaluatorContext
from rag_agent.index import ChunkRecord, Retriever, build_index

# Vocabulary for the deterministic fake embedder: one dimension per keyword.
_VOCAB = ("wright", "flight", "1903", "wind", "2022", "twh")


class _FakeEmbedder:
    """Deterministic bag-of-vocab embedder producing L2-normalized vectors."""

    def __init__(self, model_name: str = "") -> None:
        self.model_name = model_name

    def __call__(self, texts: Sequence[str]) -> np.ndarray:
        rows = []
        for text in texts:
            lowered = text.lower()
            vec = np.array([1.0 if dim in lowered else 0.0 for dim in _VOCAB], dtype=np.float32)
            norm = float(np.linalg.norm(vec))
            rows.append(vec / norm if norm else vec)
        return np.vstack(rows)


WRIGHT_CHUNK = (
    "The Wright brothers made the first controlled, sustained flight of a "
    "powered, heavier-than-air aircraft with the Wright Flyer on "
    "December 17, 1903, at Kitty Hawk, North Carolina."
)
WIND_CHUNK = (
    "In 2022, wind supplied over 2000 TWh of electricity, which was over 7% "
    "of world electricity and about 2% of world energy."
)
SOLAR_CHUNK = "Solar power converts sunlight into electricity using photovoltaic cells."


@pytest.fixture
def fixture_retriever(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Retriever]:
    """A tiny two-article index + the tool pointed at it (fake embedder)."""
    import rag_agent.index

    monkeypatch.setattr(rag_agent.index, "SentenceTransformerEmbedder", _FakeEmbedder)
    get_retriever.cache_clear()
    chunks = [
        ChunkRecord(
            chunk_id="aviation-122#c000",
            article_id="aviation-122",
            text=WRIGHT_CHUNK,
            token_count=40,
            title="Wright brothers",
            topic="Aviation",
        ),
        ChunkRecord(
            chunk_id="renewable-energy-122#c000",
            article_id="renewable-energy-122",
            text=WIND_CHUNK,
            token_count=30,
            title="Wind power",
            topic="Renewable energy",
        ),
        ChunkRecord(
            chunk_id="renewable-energy-200#c000",
            article_id="renewable-energy-200",
            text=SOLAR_CHUNK,
            token_count=20,
            title="Solar power",
            topic="Renewable energy",
        ),
    ]
    build_index(chunks, _FakeEmbedder(), tmp_path, description="fixture")
    retriever = get_retriever(tmp_path)
    monkeypatch.setattr(documents, "get_retriever", lambda index_dir=None: retriever)
    yield retriever
    get_retriever.cache_clear()


def _ctx(task: evals.EvalTask, record: TaskRunRecord) -> EvaluatorContext:
    return EvaluatorContext(
        name=task.id,
        inputs=task,
        metadata=None,
        expected_output=None,
        output=record,
        duration=record.duration_s,
        _span_tree=None,
        attributes={},
        metrics={},
    )


class TestSearchDocuments:
    def test_returns_formatted_snippet_best_first(self, fixture_retriever: Retriever) -> None:
        hits = search_documents("wright brothers flight year 1903")
        assert hits, "expected at least one hit"
        assert hits[0].startswith("aviation-122#c000 | Wright brothers —")
        assert "1903" in hits[0]

    def test_cross_article_query_surfaces_wind_fact(self, fixture_retriever: Retriever) -> None:
        wind_hits = search_documents("wind power electricity TWh share", top_k=2)
        assert any("2022" in hit and "2000 TWh" in hit for hit in wind_hits)

    def test_top_k_bounds(self, fixture_retriever: Retriever) -> None:
        assert len(search_documents("wind solar power energy", top_k=2)) <= 2
        # clamped to [1, 5] like the handbook search
        assert len(search_documents("power", top_k=99)) <= 5

    def test_t15_ground_truth_math(self) -> None:
        # pinned multi-hop: 2022 (wind > 2000 TWh) - 1903 (Wright Flyer) = 119
        assert 2022 - 1903 == 119

    def test_t15_graders_are_deterministic(self, fixture_retriever: Retriever) -> None:
        task = next(t for t in evals.TASK_SUITE if t.id == "t15")
        assert task.category == "lookup"
        # the 119-year gap is arithmetic: calculator is part of the exact set
        assert task.expected_tools == ["search_documents", "calculator"]

        record = TaskRunRecord(
            task_id="t15",
            status="ok",
            answer=(
                "The Wright brothers' first controlled powered flight was in 1903; "
                "wind power supplied over 2000 TWh in 2022; the events are 119 "
                "years apart."
            ),
            steps_taken=["plan (2 steps)", "execute (attempt 1)", "critique: pass"],
            tools_used=["search_documents", "calculator"],
            confidence=0.9,
            duration_s=30.0,
            input_tokens=5000,
            output_tokens=800,
        )
        ctx = _ctx(task, record)
        assert evals.AnswerSuccess().evaluate(ctx) is True
        assert evals.ToolSelection().evaluate(ctx) is True
        assert evals.StepBudget().evaluate(ctx) is True
        assert evals.LatencyBudget().evaluate(ctx) is True

        # deterministic misses: a missing keyword or a wrong tool fails the
        # same grader every time
        bad_answer = record.model_copy(update={"answer": "The two events are 119 years apart."})
        bad_tools = record.model_copy(update={"tools_used": ["search_handbook"]})
        assert evals.AnswerSuccess().evaluate(_ctx(task, bad_answer)) is False
        assert evals.ToolSelection().evaluate(_ctx(task, bad_tools)) is False


_REAL_INDEX_DIR = (
    Path(__file__).resolve().parents[2] / "01-rag-agent" / "data" / "index" / "chunks_200"
)


@pytest.mark.skipif(
    not (_REAL_INDEX_DIR / "faiss.index").exists(),
    reason="01's real index not materialized on this machine",
)
class TestRealCorpusIntegration:
    def test_real_index_finds_t15_facts(self) -> None:
        get_retriever.cache_clear()
        try:
            retriever = get_retriever(_REAL_INDEX_DIR)
            assert len(retriever.chunks) > 3000
            wright = search_documents("Wright brothers first controlled powered flight year")
            assert any("aviation-122#c000" in hit and "1903" in hit for hit in wright)
            wind = search_documents("wind power supplied TWh world electricity share 2022")
            assert any("renewable-energy-122#c000" in hit and "2022" in hit for hit in wind)
        finally:
            get_retriever.cache_clear()

    def test_real_index_finds_h12_facts(self) -> None:
        """Held-out expansion task h12 (photosynthesis, previously unexercised
        Wikipedia topic): the top hit must name chlorophyll a and carry both
        absorbed-wavelength keywords inside the tool's 600-char excerpt."""
        get_retriever.cache_clear()
        try:
            task = next(t for t in evals.HELDOUT_SUITE if t.id == "h12")
            assert task.expected_tools == ["search_documents"]
            hits = search_documents(
                "which form of chlorophyll is the main photosynthetic pigment "
                "and which light wavelengths does it absorb"
            )
            assert hits, "expected at least one hit"
            top = hits[0].lower()
            assert "chlorophyll a" in top
            for keyword in task.expected_keywords:
                assert keyword.lower() in top, keyword
        finally:
            get_retriever.cache_clear()
