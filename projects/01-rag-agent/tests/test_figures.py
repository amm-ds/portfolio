"""Focused regression tests for retrieval figure semantics."""

from rag_agent.config import RAGConfig, RetrievalBest
from rag_agent.figures import retrieval_funnel_figure
from rag_agent.schemas import EvalQuestion


def test_retrieval_funnel_uses_question_hit_miss_counts() -> None:
    questions = [EvalQuestion(question=f"q{i}", relevant_article_ids=["article"]) for i in range(4)]
    chosen = RetrievalBest(
        embedding_model="encoder",
        embedding_slug="encoder",
        chunk_size=200,
        top_k=3,
    )
    fig = retrieval_funnel_figure(
        RAGConfig(),
        questions,
        {200: {"ranks": [1, 4, None, 2], "token_sums": [], "n_chunks": 100}},
        chosen,
    )

    assert len(fig.data) == 1
    assert fig.data[0].type == "bar"
    assert list(fig.data[0].x) == ["hit", "miss"]
    assert list(fig.data[0].y) == [2, 2]
    assert "975" not in str(fig.layout.title.text)
