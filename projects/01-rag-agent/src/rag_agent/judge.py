"""LLM rubric judge for RAG evaluation, with graceful offline fallback.

Default (wave 10): the judge is the provider model — env-configured
OpenAI-compatible endpoint first, local Ollama second — returning structured
``JudgeVerdict``s (score 0-1 with reason). ``JUDGE=keyword`` (or the
``--offline`` evaluate path) selects the deterministic platform keyword judge
for CI. Runtime judge failures fall back to the keyword judge per verdict so a
flaky provider can never break evaluation.
"""

import os

from portfolio_core.config import get_settings
from portfolio_core.llm import build_model, ollama_available
from portfolio_core.llm_budget import BudgetExceededError, budget_limits
from portfolio_core.logging import get_logger
from portfolio_eval.rag import JudgeVerdict, KeywordJudge
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.models import Model

from rag_agent.metering import get_meter
from rag_agent.provider import model_settings_for_provider

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
            model_settings=model_settings_for_provider(),
        )
        self._fallback = KeywordJudge()

    def judge(self, question: str, context: str, answer: str) -> JudgeVerdict:
        prompt = f"Question: {question}\n\nContext:\n{context}\n\nAnswer:\n{answer}"
        try:
            result = self._agent.run_sync(prompt, usage_limits=budget_limits())
            get_meter().record("judge", result)
            return result.output
        except (BudgetExceededError, UsageLimitExceeded):
            raise  # the cap must stop the run, never degrade to the keyword floor
        except Exception as exc:  # broad: provider hiccup; logged, keyword fallback
            logger.warning("LLM judge failed (%s); falling back to keyword judge", exc)
            return self._fallback.judge(question, context, answer)


RubricJudge = KeywordJudge | LLMRubricJudge


def provider_available() -> bool:
    """Env provider or local Ollama."""
    s = get_settings()
    return bool(s.llm_api_key and s.llm_base_url) or ollama_available()


def build_judge(prefer: str | None = None) -> RubricJudge:
    """Judge selection.

    ``JUDGE=keyword`` (or ``prefer="keyword"``) forces the deterministic judge;
    otherwise the LLM rubric judge is used whenever a provider exists, falling
    back to the keyword judge when nothing is available (e.g. CI).
    """
    want = (prefer or os.environ.get("JUDGE", "llm")).strip().lower()
    if want == "keyword":
        return KeywordJudge()
    if provider_available():
        return LLMRubricJudge()
    logger.warning("no LLM provider available; using keyword judge")
    return KeywordJudge()
