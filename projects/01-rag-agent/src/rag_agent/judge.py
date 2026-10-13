"""LLM rubric judge for RAG evaluation, with graceful offline fallback.

The default judge stays the platform's deterministic `KeywordJudge` (CI-safe,
no credentials). Setting ``JUDGE=llm`` with ``LLM_BASE_URL``/``LLM_API_KEY``
configured switches the evaluator to a pydantic-ai rubric judge that returns a
structured ``JudgeVerdict`` (score 0-1 with reason). Runtime judge failures
fall back to the keyword judge so a flaky provider can never break evaluation.
"""

import os

from portfolio_core.config import get_settings
from portfolio_core.llm import build_model
from portfolio_core.logging import get_logger
from portfolio_eval.rag import JudgeVerdict, KeywordJudge
from pydantic_ai import Agent
from pydantic_ai.models import Model

logger = get_logger(__name__)

RUBRIC_SYSTEM_PROMPT = """You are a strict grader for retrieval-grounded answers.

Score 1.0 only if the answer is fully supported by the provided context AND
addresses the question. Score near 0.0 if the answer contradicts the context,
invents facts not present in it, or fails to address the question. Use
intermediate scores for partial support or partial relevance. Always give a
one-sentence reason.
"""


class LLMRubricJudge:
    """Provider-model judge; every call returns a validated ``JudgeVerdict``."""

    name = "llm-rubric-judge"

    def __init__(self, model: Model | None = None) -> None:
        resolved = model if model is not None else build_model()
        self._agent = Agent(
            resolved,
            output_type=JudgeVerdict,
            system_prompt=RUBRIC_SYSTEM_PROMPT,
        )
        self._fallback = KeywordJudge()

    def judge(self, question: str, context: str, answer: str) -> JudgeVerdict:
        prompt = f"Question: {question}\n\nContext:\n{context}\n\nAnswer:\n{answer}"
        try:
            return self._agent.run_sync(prompt).output
        except Exception as exc:  # provider hiccup must never break the eval
            logger.warning("LLM judge failed (%s); falling back to keyword judge", exc)
            return self._fallback.judge(question, context, answer)


RubricJudge = KeywordJudge | LLMRubricJudge


def build_judge() -> RubricJudge:
    """Judge selection: ``JUDGE=llm`` + credentials → LLM judge, else keyword."""
    want_llm = os.environ.get("JUDGE", "keyword").strip().lower() == "llm"
    settings = get_settings()
    if want_llm and settings.llm_api_key and settings.llm_base_url:
        return LLMRubricJudge()
    return KeywordJudge()
