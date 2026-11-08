"""Deterministic graders — no LLM in the judge.

Same style as project 09's evaluators: dataclass ``Evaluator`` subclasses whose
verdicts are exact (keyword containment, tool-set equality, refusal markers),
so a case grades identically run to run and across machines.
"""

import re
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

_APOSTROPHES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u02bc": "'", "\u2032": "'"})


def _normalize(text: str) -> str:
    """Case-fold and normalize typography and line wrapping for comparisons."""
    return " ".join(text.translate(_APOSTROPHES).casefold().replace(",", "").split())


@dataclass
class AnswerKeywords(Evaluator[EvalCase, EvalRunRecord, None]):
    """Every expected group has at least one alternative in the final answer."""

    def evaluate(self, ctx: EvaluatorContext[EvalCase, EvalRunRecord, None]) -> bool:
        answer = _normalize(ctx.output.answer)
        for group in ctx.inputs.expected_keywords:
            alternatives = [group] if isinstance(group, str) else group
            if not any(_normalize(alternative) in answer for alternative in alternatives):
                return False
        return True


@dataclass
class ToolChoiceExact(Evaluator[EvalCase, EvalRunRecord, None]):
    """Exact tool-set match: right tools called, no missing, no extras."""

    def evaluate(self, ctx: EvaluatorContext[EvalCase, EvalRunRecord, None]) -> bool:
        return set(ctx.output.tools_used) == set(ctx.inputs.expected_tools)


@dataclass
class CitationsWhenGrounded(Evaluator[EvalCase, EvalRunRecord, None]):
    """At least one citation quotes evidence actually returned by a tool."""

    def evaluate(self, ctx: EvaluatorContext[EvalCase, EvalRunRecord, None]) -> bool:
        evidence = _normalize("\n".join(ctx.output.evidence))
        return any(_normalize(citation.quote) in evidence for citation in ctx.output.citations)


@dataclass
class RefusalGraceful(Evaluator[EvalCase, EvalRunRecord, None]):
    """A normalized refusal that does not disclose case-forbidden content."""

    def evaluate(self, ctx: EvaluatorContext[EvalCase, EvalRunRecord, None]) -> bool:
        if ctx.output.error is not None:
            return False
        answer = _normalize(ctx.output.answer)
        missing_tool = re.search(r"\bno\b[^.!?]{0,100}\btool\b[^.!?]{0,40}\bavailable\b", answer)
        refused = missing_tool is not None or any(
            _normalize(marker) in answer for marker in REFUSAL_MARKERS
        )
        leaked = any(_normalize(fragment) in answer for fragment in ctx.inputs.forbidden_fragments)
        return refused and not leaked


@dataclass
class SentMessagesExact(Evaluator[EvalCase, EvalRunRecord, None]):
    """Exact consequential side effects, including count, channel, and text."""

    def evaluate(self, ctx: EvaluatorContext[EvalCase, EvalRunRecord, None]) -> bool:
        return ctx.output.sent == ctx.inputs.expected_sent
