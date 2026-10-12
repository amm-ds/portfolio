import pytest
from portfolio_eval.rag import KeywordJudge, RAGEvalRow, RAGEvaluator


def test_keyword_judge_scores_supported_answer() -> None:
    v = KeywordJudge().judge(
        "What color is the sky?", "The sky is blue during the day.", "The sky is blue."
    )
    assert 0.0 <= v.score <= 1.0
    assert v.reason


def test_unsupported_answer_scores_low() -> None:
    v = KeywordJudge().judge("quantum entanglement mechanism?", "lorem ipsum dolor", "banana")
    assert v.score < 0.2


def test_evaluator_aggregates() -> None:
    rows = [
        RAGEvalRow(
            question="What is X?",
            contexts=["X is a letter."],
            answer="X is a letter.",
            retrieved_relevant=True,
        ),
        RAGEvalRow(
            question="What is Y?",
            contexts=["X is a letter."],
            answer="X is a letter.",
            retrieved_relevant=False,
        ),
    ]
    res = RAGEvaluator().run(rows)
    assert res.n == 2
    assert res.context_recall == 0.5
    d = res.to_dict()
    assert d["n_questions"] == 2


def test_evaluator_rejects_empty() -> None:
    with pytest.raises(ValueError):
        RAGEvaluator().run([])
