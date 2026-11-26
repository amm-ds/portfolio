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


def _decode(value: object) -> list:
    """Plotly typed-array record ({dtype, bdata}) or plain list."""
    import base64
    import struct

    if isinstance(value, dict) and "bdata" in value:
        raw = base64.b64decode(str(value["bdata"]))
        fmt = {"f8": "d", "f4": "f", "i8": "q", "i4": "i", "u4": "I"}[str(value.get("dtype", "f8"))]
        return list(struct.unpack(f"<{len(raw) // struct.calcsize(fmt)}{fmt}", raw))
    return list(value)  # type: ignore[arg-type]


def test_committed_figure_titles_state_their_own_data() -> None:
    """Committed figure payloads (patched without a full re-run) must agree
    with the numbers in their own traces or the committed metrics."""
    import json
    from pathlib import Path

    figures = Path(__file__).parents[1] / "reports" / "figures"

    sweep = json.loads((figures / "chunk_size_sweep.json").read_text())
    traces = {t["name"]: t for t in sweep["data"]}
    recall5 = _decode(traces["recall@5"]["y"])
    mrr5 = _decode(traces["mrr@5"]["y"])
    title = sweep["layout"]["title"]["text"]
    assert len(set(recall5)) == 1 and "tie on recall@5" in title
    assert f"({recall5[0]:.3f})" in title
    assert mrr5[0] == max(mrr5) and f"({mrr5[0]:.3f})" in title

    comp = json.loads((figures / "model_comparison.json").read_text())
    models = {
        t["name"]: dict(zip(_decode(t["x"]), _decode(t["y"]), strict=True)) for t in comp["data"]
    }
    title = comp["layout"]["title"]["text"]
    assert models["minilm"]["recall@5"] == models["bge_small"]["recall@5"]
    assert f"({models['minilm']['recall@5']:.3f})" in title
    assert models["minilm"]["mrr@5"] > models["bge_small"]["mrr@5"]
    metrics = json.loads((figures.parent / "metrics.json").read_text())
    lexical = metrics["detail"]["retrieval"]["200"]["lexical_recall@5"]
    assert f"{lexical:.3f}" in title

    tax = json.loads((figures / "failure_taxonomy.json").read_text())
    counts = dict(zip(_decode(tax["data"][0]["x"]), _decode(tax["data"][0]["y"]), strict=True))
    title = tax["layout"]["title"]["text"]
    assert counts["empty-answer"] == 10 and counts["unsupported-claim"] == 1
    assert "10 empty answers vs 1 unsupported claim" in title
    assert f"n = {sum(counts.values())}" in title

    eda = json.loads((figures / "eda_corpus_composition.json").read_text())
    articles = next(t for t in eda["data"] if t.get("name") == "articles")
    topics = dict(zip(_decode(articles["x"]), _decode(articles["y"]), strict=True))
    title = eda["layout"]["title"]["text"]
    top = max(topics, key=lambda k: topics[k])
    assert top == "Aviation" and f"({topics[top]} of {sum(topics.values())})" in title

    ladder = json.loads((figures / "retrieval_ladder.json").read_text())
    title = ladder["layout"]["title"]["text"]
    for arm, want in (("R0 as-shipped", "0.924"), ("S3 +cap (promoted)", "0.946")):
        trace = next(
            t for t in ladder["data"] if t.get("name") == arm and t.get("yaxis", "y") == "y"
        )
        xs, ys = _decode(trace["x"]), _decode(trace["y"])
        final = next(y for x, y in zip(xs, ys, strict=True) if "final_v3" in str(x))
        assert f"{final:.3f}" == want and want in title
