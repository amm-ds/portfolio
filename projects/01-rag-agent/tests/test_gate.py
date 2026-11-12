"""Evidence-gate tests (R6): decision math, threshold edges, label-leak guard.

The gate is the inference-time abstention guard: it sees ONLY the question
text and retrieved chunk texts — never gold metadata. These tests pin the
math, the edge semantics (``<`` threshold: equality passes), and the leakage
guard that keeps ``EvalQuestion.relevant_article_ids`` out of the path.
"""

from rag_agent.gate import GateConfig, assess, content_words, normalize
from rag_agent.schemas import EvalQuestion


def test_assess_refuses_without_question_or_evidence() -> None:
    decision = assess("what is photosynthesis", [])
    assert decision.refuses and decision.coverage == 0.0
    # a question of pure stopwords has no content words → nothing to ground
    decision = assess("what is the", ["photosynthesis converts light energy"])
    assert decision.refuses


def test_assess_computes_coverage_and_max_similarity() -> None:
    chunks = [
        "photosynthesis converts light energy into chemical energy in plants",
        "the wright brothers made the first powered flight in 1903",
    ]
    decision = assess("how does photosynthesis convert light energy in plants", chunks)
    # 4 of 5 question content words occur verbatim ("convert" ≠ "converts" — no stemming)
    assert decision.coverage == 0.8
    # the best single chunk holds all 4; the aviation chunk contributes nothing
    assert decision.max_similarity == 0.8
    assert not decision.refuses
    # continuous signal sits between the two components
    assert 0.0 < decision.evidence_score <= 1.0


def test_assess_threshold_edges_are_strict() -> None:
    """Exactly at the threshold passes (``<`` semantics); one step below refuses."""
    # craft inputs so coverage lands exactly on the threshold
    question = "alpha beta gamma"  # three content words
    chunk = "alpha beta gamma delta"  # all three present → coverage 1.0
    cfg = GateConfig(min_coverage=1.0, min_max_similarity=1.0)
    assert not assess(question, [chunk], cfg).refuses
    cfg = GateConfig(min_coverage=1.01, min_max_similarity=0.0)
    assert assess(question, [chunk], cfg).refuses
    # partial coverage: 2/3 ≈ 0.6667
    cfg = GateConfig(min_coverage=2 / 3, min_max_similarity=0.0)
    decision = assess(question, ["alpha beta other words"], cfg)
    assert round(decision.coverage, 4) == round(2 / 3, 4)
    assert not decision.refuses
    cfg = GateConfig(min_coverage=0.67, min_max_similarity=0.0)
    assert assess(question, ["alpha beta other words"], cfg).refuses


def test_assess_label_leak_guard() -> None:
    """Same question + same chunks ⇒ same decision, regardless of gold labels.

    Two EvalQuestions with DIFFERENT relevant_article_ids must produce
    identical gate outcomes — the gate receives only question text and chunk
    texts, so it cannot leak the answer key.
    """
    chunks = ["solar panels convert sunlight into electricity via the photovoltaic effect"]
    q_answer = EvalQuestion(
        question="how do solar panels generate electricity",
        relevant_article_ids=["energy-000"],
        category="single_hop",
        expected_behavior="answer",
    )
    q_abstain = EvalQuestion(
        question="how do solar panels generate electricity",
        relevant_article_ids=[],
        category="unanswerable",
        expected_behavior="abstain",
    )
    d1 = assess(q_answer.question, chunks)
    d2 = assess(q_abstain.question, chunks)
    assert d1 == d2


def test_content_words_strips_stopwords_and_punctuation() -> None:
    words = content_words("What is the largest offshore wind farm?")
    assert "what" not in words and "the" not in words and "is" not in words
    assert {"largest", "offshore", "wind", "farm"} <= words


def test_normalize_nfkc_whitespace_case():
    # decomposed é (e + combining acute U+0301) matches composed é (U+00E9) after NFKC
    composed = "caf\u00e9 wall"
    decomposed = "cafe\u0301 wall"
    assert composed != decomposed  # genuinely different code points before normalize
    assert normalize(composed) == normalize(decomposed)
    # whitespace collapses, case folds
    assert normalize("  Many   Spaces\tAnd CAPS") == "many spaces and caps"
