"""Verify-then-answer loop: claim-level entailment checking + repair + abstention.

Wave 14: retrieval is solved (context recall 0.979, precision 1.000) but
generation grounding is the bottleneck (18/30 unsupported-claim in the bounded
golden-set pass). This module is the documented next lever:

1. The agent's ``summary`` is split into claims (sentences).
2. Each claim is checked for entailment against the *full text* of the chunks
   its answer cites, by a local judge (provider model returning validated
   ``ClaimVerdict``s, one batched call per answer; deterministic keyword
   entailment as the CI/offline fallback — same pattern as
   :mod:`rag_agent.judge`).
3. Unsupported claims are repaired — one regeneration call per claim with
   stricter instructions, at most ``verify.max_repair_calls`` per answer — and
   re-verified; claims that stay unsupported are dropped.
4. The answer is re-assembled from surviving claims. If the support fraction
   stays below ``verify.min_support``, the answer falls back to abstention
   (refusal text + confidence < 0.3), integrating with the existing abstention
   path (:func:`rag_agent.reporting.is_abstention`).

The verifier is best-effort by design: an unexpected judge/provider failure
logs a warning and returns the original answer untouched, so verification can
never make an answer worse than the unverified baseline.
"""

import re
import time
from dataclasses import dataclass, field

from portfolio_core.llm import build_model
from portfolio_core.llm_budget import BudgetExceededError, budget_limits
from portfolio_core.logging import get_logger
from portfolio_core.schemas import PortfolioBaseModel
from portfolio_eval.rag import _STOPWORDS
from pydantic import Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.models import Model

from rag_agent.config import RAGConfig
from rag_agent.index import Retriever
from rag_agent.metering import get_meter
from rag_agent.provider import model_settings_for_provider
from rag_agent.reporting import is_abstention
from rag_agent.schemas import AnalysisResult

logger = get_logger(__name__)

# Marker a repair call returns when the evidence cannot support the claim at
# all; the claim is dropped rather than kept in a weakened form.
REPAIR_IMPOSSIBLE = "UNSUPPORTED"

# Keyword entailment: a claim is supported when at least this fraction of its
# content words appear in the cited evidence (union of chunk texts).
KEYWORD_SUPPORT_THRESHOLD = 0.6

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class ClaimVerdict(PortfolioBaseModel):
    """Structured per-claim entailment verdict, validated before it counts."""

    claim: str = Field(min_length=1)
    supported: bool
    reason: str = Field(min_length=1)


class ClaimVerdictSet(PortfolioBaseModel):
    """Batched verdicts: one judge call covers every claim of an answer."""

    verdicts: list[ClaimVerdict] = Field(min_length=1)


@dataclass
class ClaimCheck:
    """One claim's journey through the loop."""

    claim: str
    supported: bool
    reason: str
    repaired: bool = False  # True when the surviving text came from a repair call
    dropped: bool = False


@dataclass
class VerifyReport:
    """Outcome of the verify pass for one answer."""

    enabled: bool = True
    skipped: bool = False  # agent already abstained: nothing to verify
    claims: list[ClaimCheck] = field(default_factory=list)
    support_fraction: float = 1.0
    n_repair_calls: int = 0
    n_judge_calls: int = 0
    abstained: bool = False  # verify-induced abstention (support floor breached)
    final_summary: str = ""
    latency_s: float = 0.0


def split_claims(summary: str) -> list[str]:
    """Split a summary into claims (sentence boundaries)."""
    return [s.strip() for s in _SENTENCE_SPLIT.split(summary.strip()) if s.strip()]


def _content_words(text: str) -> set[str]:
    return {w.strip(".,;:!?()\"'") for w in text.lower().split()} - _STOPWORDS - {""}


class KeywordEntailmentJudge:
    """Deterministic per-claim entailment: content-word coverage of the evidence."""

    name = "keyword-entailment-judge"

    def verify_claims(self, question: str, claims: list[str], evidence: str) -> list[ClaimVerdict]:
        evidence_words = _content_words(evidence)
        verdicts: list[ClaimVerdict] = []
        for claim in claims:
            claim_words = _content_words(claim)
            if not claim_words:
                verdicts.append(
                    ClaimVerdict(claim=claim, supported=True, reason="no content words to check")
                )
                continue
            coverage = len(claim_words & evidence_words) / len(claim_words)
            supported = coverage >= KEYWORD_SUPPORT_THRESHOLD
            verdicts.append(
                ClaimVerdict(
                    claim=claim,
                    supported=supported,
                    reason=f"content-word coverage {coverage:.2f} "
                    f"(threshold {KEYWORD_SUPPORT_THRESHOLD:.2f})",
                )
            )
        return verdicts


ENTAILMENT_PROMPT = """You are a strict entailment checker for retrieval-grounded answers.

Question: {question}

Evidence (retrieved passages the answer cites):
{evidence}

Claims to check (exactly one per numbered line):
{claims}

For EACH claim decide whether the evidence fully supports it. A claim is
supported only when the evidence states what the claim asserts; reasonable
rewording is fine, but any fact, number, or inference NOT present in the
evidence makes the claim unsupported. Check every claim and keep the claim
text verbatim in your verdicts."""


REPAIR_PROMPT = """You are repairing one unsupported sentence of a grounded answer.

Question: {question}

Cited evidence:
{evidence}

Unsupported sentence: {claim}

Rewrite the sentence so that every part of it is entailed by the cited
evidence. Drop any detail the evidence does not contain, even if it is true
in the real world. Do not add citations or commentary — output ONLY the
rewritten sentence, as plain text. If the evidence cannot support any faithful
version of the sentence, output exactly: {impossible}"""


class LLMEntailmentJudge:
    """Provider-model claim judge; batched verdicts, keyword fallback on failure."""

    name = "llm-entailment-judge"

    def __init__(self, model: Model | None = None) -> None:
        resolved = model if model is not None else build_model()
        self._fallback = KeywordEntailmentJudge()
        self._verdict_agent = Agent(
            resolved,
            output_type=ClaimVerdictSet,
            system_prompt=(
                "You check whether answer claims are entailed by retrieved evidence. "
                "You are strict: unsupported means the evidence does not state it."
            ),
            model_settings=model_settings_for_provider(),
        )
        self._repair_agent = Agent(
            resolved,
            output_type=str,
            system_prompt=(
                "You repair unsupported sentences of grounded answers so that every "
                "remaining word is entailed by the cited evidence."
            ),
            model_settings=model_settings_for_provider(),
        )

    def verify_claims(self, question: str, claims: list[str], evidence: str) -> list[ClaimVerdict]:
        numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(claims, start=1))
        prompt = ENTAILMENT_PROMPT.format(question=question, evidence=evidence, claims=numbered)
        try:
            result = self._verdict_agent.run_sync(prompt, usage_limits=budget_limits())
            get_meter().record("verify", result)
            verdicts = result.output.verdicts
            if len(verdicts) != len(claims):
                raise ValueError(
                    f"judge returned {len(verdicts)} verdicts for {len(claims)} claims"
                )
            return verdicts
        except (BudgetExceededError, UsageLimitExceeded):
            raise  # the cap must stop the run, never degrade to the keyword floor
        except Exception as exc:  # provider hiccup must never break the answer path
            logger.warning("claim judge failed (%s); falling back to keyword entailment", exc)
            return self._fallback.verify_claims(question, claims, evidence)

    def repair(self, question: str, claim: str, evidence: str) -> str:
        prompt = REPAIR_PROMPT.format(
            question=question, evidence=evidence, claim=claim, impossible=REPAIR_IMPOSSIBLE
        )
        try:
            result = self._repair_agent.run_sync(prompt, usage_limits=budget_limits())
            get_meter().record("verify", result)
            return result.output.strip()
        except (BudgetExceededError, UsageLimitExceeded):
            raise  # the cap must stop the run, never silently drop claims
        except Exception as exc:
            logger.warning("repair call failed (%s); dropping the claim", exc)
            return REPAIR_IMPOSSIBLE


ClaimJudge = KeywordEntailmentJudge | LLMEntailmentJudge

ABSTENTION_TEXT = (
    "The retrieved passages do not contain enough reliable evidence to answer "
    "this question confidently."
)


def evidence_for(result: AnalysisResult, retriever: Retriever) -> str:
    """Full text of every chunk the answer cites (excerpt fallback)."""
    parts: list[str] = []
    for citation in result.citations:
        chunk = retriever.get_chunk(citation.chunk_id)
        parts.append(chunk.text if chunk is not None else citation.excerpt)
    return "\n\n".join(parts)


def verify_result(
    question: str,
    result: AnalysisResult,
    retriever: Retriever,
    config: RAGConfig,
    judge: ClaimJudge,
) -> VerifyReport:
    """Run the verify-then-answer loop on one drafted ``AnalysisResult``.

    Never raises: any unexpected failure logs and returns the original answer
    with ``support_fraction=1.0`` (the unverified baseline stands).
    """
    start = time.perf_counter()
    report = VerifyReport(final_summary=result.summary)
    try:
        _verify(question, result, retriever, config, judge, report)
    except Exception as exc:  # pragma: no cover - defensive; the loop must not break answers
        logger.warning("verification failed (%s); keeping the original answer", exc)
        report.claims.clear()
        report.support_fraction = 1.0
        report.abstained = False
        report.final_summary = result.summary
    report.latency_s = time.perf_counter() - start
    return report


def _verify(
    question: str,
    result: AnalysisResult,
    retriever: Retriever,
    config: RAGConfig,
    judge: ClaimJudge,
    report: VerifyReport,
) -> None:
    if is_abstention(result.summary, result.confidence):
        report.skipped = True
        return

    claims = split_claims(result.summary)
    if not claims:
        return
    evidence = evidence_for(result, retriever)

    report.n_judge_calls += 1
    verdicts = judge.verify_claims(question, claims, evidence)
    checks = [ClaimCheck(claim=v.claim, supported=v.supported, reason=v.reason) for v in verdicts]

    # Repair pass: one regeneration call per unsupported claim, budget-capped.
    unsupported_idx = [i for i, c in enumerate(checks) if not c.supported]
    for i in unsupported_idx[: config.verify.max_repair_calls]:
        if not isinstance(judge, LLMEntailmentJudge):
            break  # the deterministic judge has no repair capability
        report.n_repair_calls += 1
        rewritten = judge.repair(question, checks[i].claim, evidence)
        if not rewritten or rewritten == REPAIR_IMPOSSIBLE:
            checks[i].dropped = True
            continue
        report.n_judge_calls += 1
        recheck = judge.verify_claims(question, [rewritten], evidence)[0]
        checks[i] = ClaimCheck(
            claim=recheck.claim,
            supported=recheck.supported,
            reason=f"repair: {recheck.reason}",
            repaired=True,
        )
        if not recheck.supported:
            checks[i].dropped = True
    # Whatever the repair budget did not cover is dropped.
    for i in unsupported_idx[config.verify.max_repair_calls :]:
        checks[i].dropped = True

    surviving = [c for c in checks if c.supported]
    report.claims = checks
    report.support_fraction = len(surviving) / len(checks)

    if report.support_fraction < config.verify.min_support:
        report.abstained = True
        report.final_summary = ABSTENTION_TEXT
        result.summary = ABSTENTION_TEXT
        result.confidence = min(result.confidence, 0.2)
        return

    report.final_summary = " ".join(c.claim for c in surviving)
    result.summary = report.final_summary


def build_claim_judge(prefer: str | None = None, model: Model | None = None) -> ClaimJudge:
    """Claim-judge selection, mirroring :func:`rag_agent.judge.build_judge`.

    ``VERIFY_JUDGE=keyword`` (or ``prefer="keyword"``) forces the deterministic
    judge; otherwise the provider model is used when one is available, with the
    keyword judge as CI/offline fallback.
    """
    import os

    from rag_agent.judge import provider_available

    want = (prefer or os.environ.get("VERIFY_JUDGE", "llm")).strip().lower()
    if want == "keyword":
        return KeywordEntailmentJudge()
    if model is not None:
        return LLMEntailmentJudge(model=model)
    if provider_available():
        return LLMEntailmentJudge()
    logger.warning("no LLM provider available; using keyword entailment judge")
    return KeywordEntailmentJudge()
