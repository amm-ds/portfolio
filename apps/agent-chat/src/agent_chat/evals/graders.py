"""Deterministic graders — no LLM in the judge.

Same style as project 09's evaluators: dataclass ``Evaluator`` subclasses whose
verdicts are exact (keyword containment, tool-set equality, refusal markers),
so a case grades identically run to run and across machines.
"""

from dataclasses import dataclass

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from agent_chat.evals.cases import EvalCase
from agent_chat.evals.records import EvalRunRecord

#: Substrings that mark a graceful refusal (any one suffices, case-insensitive).
REFUSAL_MARKERS: tuple[str, ...] = (
    "cannot",
    "can't",
    "no tool",
    "not available",
    "unable",
    "no such",
    "do not have",
    "don't have",
)


@dataclass
class AnswerKeywords(Evaluator[EvalCase, EvalRunRecord, None]):
    """All expected ground-truth keywords appear in the final answer."""

    def evaluate(self, ctx: EvaluatorContext[EvalCase, EvalRunRecord, None]) -> bool:
        answer = ctx.output.answer.lower()
        return all(keyword.lower() in answer for keyword in ctx.inputs.expected_keywords)


@dataclass
class ToolChoiceExact(Evaluator[EvalCase, EvalRunRecord, None]):
    """Exact tool-set match: right tools called, no missing, no extras."""

    def evaluate(self, ctx: EvaluatorContext[EvalCase, EvalRunRecord, None]) -> bool:
        return set(ctx.output.tools_used) == set(ctx.inputs.expected_tools)


@dataclass
class CitationsWhenGrounded(Evaluator[EvalCase, EvalRunRecord, None]):
    """Answers that relied on retrieved/skill content carry at least one citation."""

    def evaluate(self, ctx: EvaluatorContext[EvalCase, EvalRunRecord, None]) -> bool:
        if not ctx.inputs.expect_citations:
            return True
        return len(ctx.output.citations) >= 1


@dataclass
class RefusalGraceful(Evaluator[EvalCase, EvalRunRecord, None]):
    """Designed-to-fail probe declined in plain words, without a crash."""

    def evaluate(self, ctx: EvaluatorContext[EvalCase, EvalRunRecord, None]) -> bool:
        if ctx.output.error is not None:
            return False
        answer = ctx.output.answer.lower()
        return any(marker in answer for marker in REFUSAL_MARKERS)
