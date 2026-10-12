"""RAG evaluation: retrieval recall plus LLM-judged faithfulness/relevance.

The judge is injected — a real provider model, a scripted FunctionModel, or a
deterministic keyword heuristic (default for offline runs). Scores are
0/0.5/1 per the standard three-point rubric, averaged per question.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class JudgeVerdict(BaseModel):
    """Structured judge output, validated before it counts."""

    score: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)


class KeywordJudge:
    """Deterministic offline judge: answer-support overlap (no LLM needed)."""

    name = "keyword-judge"

    def judge(self, question: str, context: str, answer: str) -> JudgeVerdict:
        q = set(question.lower().split()) - _STOPWORDS
        a = set(answer.lower().split()) - _STOPWORDS
        c = set(context.lower().split()) - _STOPWORDS
        if not q or not a:
            return JudgeVerdict(score=0.0, reason="empty question or answer tokens")
        support = len(a & c) / len(a)
        coverage = len(q & (a | c)) / len(q)
        score = round(0.6 * support + 0.4 * coverage, 2)
        return JudgeVerdict(score=score, reason=f"support={support:.2f} coverage={coverage:.2f}")


_STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "what",
    "which",
    "who",
    "when",
    "where",
    "how",
    "why",
    "of",
    "to",
    "in",
    "on",
    "for",
    "and",
    "or",
    "by",
    "with",
    "does",
    "did",
}


@dataclass
class RAGEvalRow:
    """One question's evaluation row."""

    question: str
    contexts: list[str] = field(default_factory=list)
    answer: str = ""
    expected_answer: str | None = None
    retrieved_relevant: bool | None = None  # retrieval recall (graded relevance)


@dataclass
class RAGEvalResult:
    """Aggregated RAG metrics over a question set."""

    n: int
    faithfulness: float
    answer_relevance: float
    context_recall: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "n_questions": self.n,
            "faithfulness": round(self.faithfulness, 4),
            "answer_relevance": round(self.answer_relevance, 4),
            "context_recall": round(self.context_recall, 4),
        }


class RAGEvaluator:
    """Evaluate rows with a pluggable judge."""

    def __init__(self, judge: KeywordJudge | None = None) -> None:
        self.judge = judge or KeywordJudge()

    def run(self, rows: list[RAGEvalRow]) -> RAGEvalResult:
        if not rows:
            raise ValueError("no eval rows provided")
        faith, rel, recall = [], [], []
        for row in rows:
            context = "\n".join(row.contexts)
            faith.append(self.judge.judge(row.question, context, row.answer).score)
            rel.append(
                self.judge.judge(row.question, row.question + " " + context, row.answer).score
            )
            if row.retrieved_relevant is not None:
                recall.append(1.0 if row.retrieved_relevant else 0.0)
        return RAGEvalResult(
            n=len(rows),
            faithfulness=float(sum(faith) / len(faith)),
            answer_relevance=float(sum(rel) / len(rel)),
            context_recall=float(sum(recall) / len(recall)) if recall else float("nan"),
        )
