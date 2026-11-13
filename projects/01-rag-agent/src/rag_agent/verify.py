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
from collections.abc import Callable
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
from rag_agent.index import ChunkRecord, Retriever
from rag_agent.metering import get_meter
from rag_agent.provider import model_settings_for_provider
from rag_agent.reporting import is_abstention
from rag_agent.schemas import AnalysisResult, DraftedClaim, EvidenceSpan

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


# R7 claim terminal states — every claim ends in exactly one of these.
TERMINAL_ACCEPTED_ORIGINAL = "accepted_original"
TERMINAL_ACCEPTED_REPAIRED = "accepted_repaired"
TERMINAL_DROPPED_ORIGINAL = "dropped_original"
TERMINAL_DROPPED_REPAIRED = "dropped_repaired"


@dataclass
class ClaimCheck:
    """One claim's journey through the loop."""

    claim: str
    supported: bool
    reason: str
    repaired: bool = False  # True when the surviving text came from a repair call
    dropped: bool = False
    terminal_state: str = ""  # R7: set by VerifyReport.finalize_claim_states


@dataclass
class VerifyReport:
    """Outcome of the verify pass for one answer."""

    enabled: bool = True
    skipped: bool = False  # agent already abstained: nothing to verify
    question: str = ""  # stamped by verify_result: joins the report to its question
    citations: list[dict[str, str]] = field(default_factory=list)  # chunk_id/article_id, same
    claims: list[ClaimCheck] = field(default_factory=list)
    # R7: None = undefined (no claims or verifier failure) — never faked as 1.0.
    support_fraction: float | None = None
    n_repair_calls: int = 0
    n_judge_calls: int = 0
    abstained: bool = False  # verify-induced abstention (support floor breached)
    verifier_failed: bool = False  # R7: the loop itself failed — answer abstained fail-closed
    final_summary: str = ""
    latency_s: float = 0.0
    # R6/R7 claim accounting (schema-v2 path; zeros on the legacy path)
    n_drafted: int = 0
    n_mechanical_fail: int = 0
    n_judged: int = 0
    n_judge_supported: int = 0  # claims the judge confirmed supported (diagnose denominator)
    n_surviving: int = 0
    n_dropped_total: int = 0
    mechanical_false_rejections: int = 0  # diagnose mode: judge-supported but mech-failed

    def finalize_claim_states(self) -> None:
        """Assign each claim its terminal state and enforce the ledger identity.

        drafted = surviving + dropped; surviving = accepted_original +
        accepted_repaired. Aggregates are derived from the per-claim states
        so the two can never disagree.
        """
        accepted_original = accepted_repaired = dropped_original = dropped_repaired = 0
        for check in self.claims:
            if check.supported and not check.dropped:
                if check.repaired:
                    check.terminal_state = TERMINAL_ACCEPTED_REPAIRED
                    accepted_repaired += 1
                else:
                    check.terminal_state = TERMINAL_ACCEPTED_ORIGINAL
                    accepted_original += 1
            elif check.repaired:
                check.terminal_state = TERMINAL_DROPPED_REPAIRED
                dropped_repaired += 1
            else:
                check.terminal_state = TERMINAL_DROPPED_ORIGINAL
                dropped_original += 1
        self.n_surviving = accepted_original + accepted_repaired
        self.n_dropped_total = dropped_original + dropped_repaired


def split_claims(summary: str) -> list[str]:
    """Split a summary into claims (sentence boundaries)."""
    return [s.strip() for s in _SENTENCE_SPLIT.split(summary.strip()) if s.strip()]


def _content_words(text: str) -> set[str]:
    return {w.strip(".,;:!?()\"'") for w in text.lower().split()} - _STOPWORDS - {""}


# --- R6 deterministic span checks -------------------------------------------------

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*%?")
_MONTHS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}
_TEMPORAL = {"until", "before", "after", "during", "since"}
_NEGATIONS = {"no", "not", "never", "none", "without", "nor", "n't"}


def check_claim_spans(
    claim: DraftedClaim, get_chunk: Callable[[str], ChunkRecord | None]
) -> list[str]:
    """Deterministic evidence checks for one drafted claim (R6).

    Returns the list of failure reasons — empty means the claim passes. These
    checks are provenance and class-specific guards (verbatim span, number,
    date, temporal qualifier, negation polarity, entity proximity); the
    entailment judge remains the arbiter for paraphrase and relational claims.
    """
    from rag_agent.gate import content_words as _cw
    from rag_agent.gate import normalize as _norm

    reasons: list[str] = []
    span_texts: list[str] = []
    for span in claim.spans:
        chunk = get_chunk(span.chunk_id)
        if chunk is None:
            reasons.append(f"span chunk {span.chunk_id!r} unknown")
            continue
        norm_span = _norm(span.exact_text)
        norm_chunk = _norm(chunk.text)
        if norm_span not in norm_chunk:
            reasons.append("span not verbatim in its cited chunk")
        span_texts.append(norm_span)
    if not span_texts:
        return reasons or ["no resolvable spans"]

    claim_l = _norm(claim.text)
    words = _cw(claim.text)
    others = {w for w in words if not w.isdigit()} - _NEGATIONS - _TEMPORAL - _MONTHS

    for number in dict.fromkeys(_NUM_RE.findall(claim_l)):
        if not any(number in s for s in span_texts):
            reasons.append(f"number {number!r} not present in any span")
            continue
        for s in span_texts:
            if number in s and not any(w in s.split() for w in others):
                reasons.append(f"value {number!r} shares no claim entity in its span")
                break
    for token in sorted((words & _MONTHS) | ({w for w in words if w in _TEMPORAL})):
        if not any(token in s.split() for s in span_texts):
            reasons.append(f"date/temporal token {token!r} not in any span")
    claim_neg = bool(_NEGATIONS & words)
    span_words: set[str] = set()
    for s in span_texts:
        span_words |= set(s.split())
    span_neg = bool(_NEGATIONS & span_words)
    if claim_neg and not span_neg:
        reasons.append("claim negated but span is affirmative")
    elif span_neg and not claim_neg:
        reasons.append("span negated but claim is affirmative")
    return list(dict.fromkeys(reasons))


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


class RepairedClaim(PortfolioBaseModel):
    """R7: a repair must re-draft its evidence, not just reword the sentence.

    The repairer returns the rewritten claim plus verbatim spans (each an
    exact substring of the cited chunk). The repaired claim then re-passes
    the deterministic span checks and the entailment judge before it can
    survive — a plain-text repair that no evidence backs is dropped. An
    impossible repair is ``{"claim": null, "spans": []}`` (a plain Optional
    output type makes pydantic-ai wrap the schema, so nullability lives in
    the fields instead).
    """

    claim: str | None = None
    spans: list[EvidenceSpan] = Field(default_factory=list)


REPAIR_PROMPT = """You are repairing one unsupported sentence of a grounded answer.

Question: {question}

Cited evidence (chunk ids in brackets — quote spans from these chunks ONLY):
{evidence}

Unsupported sentence: {claim}

Rewrite the sentence so that every part of it is entailed by the cited
evidence, and prove it: output JSON with `claim` (the rewritten sentence)
and `spans` — one or more {{\"chunk_id\": ..., \"exact_text\": ...}} objects
whose exact_text is copied VERBATIM (character-for-character) from the cited
chunk. Drop any detail the evidence does not contain, even if it is true in
the real world. If the evidence cannot support any faithful version of the
sentence, output {{"claim": null, "spans": []}}."""


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
            output_type=RepairedClaim,
            system_prompt=(
                "You repair unsupported sentences of grounded answers so that every "
                "remaining word is entailed by the cited evidence, and you prove each "
                "repair with verbatim spans from the cited chunks."
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
        except Exception as exc:  # broad: provider hiccup; logged, keyword fallback
            logger.warning("claim judge failed (%s); falling back to keyword entailment", exc)
            return self._fallback.verify_claims(question, claims, evidence)

    def repair(self, question: str, claim: str, evidence: str) -> RepairedClaim | None:
        """Repair one unsupported claim, re-drafting verbatim spans.

        ``evidence`` must be the id-labeled form (:func:`evidence_labeled`).
        Returns ``None`` only when the repair call itself failed; an
        impossible repair comes back as ``RepairedClaim(claim=None)``. Both
        drop the claim.
        """
        prompt = REPAIR_PROMPT.format(question=question, evidence=evidence, claim=claim)
        try:
            result = self._repair_agent.run_sync(prompt, usage_limits=budget_limits())
            get_meter().record("verify", result)
            return result.output
        except (BudgetExceededError, UsageLimitExceeded):
            raise  # the cap must stop the run, never silently drop claims
        except Exception as exc:  # broad: repair is best-effort; failure → drop
            logger.warning("repair call failed (%s); dropping the claim", exc)
            return None


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


def evidence_labeled(result: AnalysisResult, retriever: Retriever) -> str:
    """Id-labeled evidence for the repairer: spans must quote these chunks."""
    parts: list[str] = []
    for citation in result.citations:
        chunk = retriever.get_chunk(citation.chunk_id)
        text = chunk.text if chunk is not None else citation.excerpt
        parts.append(f"[{citation.chunk_id}]\n{text}")
    return "\n\n".join(parts)


def verify_result(
    question: str,
    result: AnalysisResult,
    retriever: Retriever,
    config: RAGConfig,
    judge: ClaimJudge,
) -> VerifyReport:
    """Run the verify-then-answer loop on one drafted ``AnalysisResult``.

    R7: fail-CLOSED. An unexpected verifier failure abstains (refusal text,
    confidence ≤ 0.2, ``verifier_failed=True``) instead of keeping the
    unverified answer; budget/token caps still propagate — they stop the
    run, never the per-answer path.
    """
    start = time.perf_counter()
    report = VerifyReport(final_summary=result.summary)
    report.question = question
    report.citations = [
        {"chunk_id": c.chunk_id, "article_id": c.article_id} for c in result.citations
    ]
    try:
        _verify(question, result, retriever, config, judge, report)
    except (BudgetExceededError, UsageLimitExceeded):
        raise
    except Exception as exc:  # pragma: no cover - defensive (loop must not pass unverified answers)
        logger.warning("verification failed (%s); abstaining fail-closed", exc)
        report.claims.clear()
        report.support_fraction = None
        report.abstained = True
        report.verifier_failed = True
        report.final_summary = ABSTENTION_TEXT
        result.summary = ABSTENTION_TEXT
        result.confidence = min(result.confidence, 0.2)
    report.latency_s = time.perf_counter() - start
    return report


def _repair_and_reverify(
    question: str,
    claim_text: str,
    evidence: str,
    evidence_ids: str,
    retriever: Retriever,
    judge: LLMEntailmentJudge,
    report: VerifyReport,
) -> ClaimCheck:
    """R7: a repair restarts the FULL verification path.

    Structured repair (claim + verbatim spans) → deterministic span checks →
    entailment judge. Any failure drops the claim; ``None`` from the repairer
    (impossible or call failure) drops too.
    """
    repaired = judge.repair(question, claim_text, evidence_ids)
    if repaired is None or not repaired.claim or not repaired.claim.strip():
        return ClaimCheck(
            claim=claim_text,
            supported=False,
            reason="repair impossible or repair call failed",
            repaired=True,
            dropped=True,
        )
    drafted = DraftedClaim(
        text=repaired.claim,
        citation_chunk_ids=list(dict.fromkeys(s.chunk_id for s in repaired.spans)),
        spans=repaired.spans,
    )
    reasons = check_claim_spans(drafted, retriever.get_chunk)
    if reasons:
        return ClaimCheck(
            claim=repaired.claim,
            supported=False,
            reason=f"repair failed span checks: {'; '.join(reasons)}",
            repaired=True,
            dropped=True,
        )
    report.n_judge_calls += 1
    recheck = judge.verify_claims(question, [repaired.claim], evidence)[0]
    check = ClaimCheck(
        claim=recheck.claim,
        supported=recheck.supported,
        reason=f"repair: {recheck.reason}",
        repaired=True,
    )
    if not recheck.supported:
        check.dropped = True
    return check


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

    if result.claims:
        _verify_structured(question, result, retriever, config, judge, report)
        return

    claims = split_claims(result.summary)
    if not claims:
        report.support_fraction = None
        return
    evidence = evidence_for(result, retriever)
    evidence_ids = evidence_labeled(result, retriever)

    report.n_drafted = len(claims)
    report.n_judge_calls += 1
    verdicts = judge.verify_claims(question, claims, evidence)
    report.n_judge_supported += sum(1 for v in verdicts if v.supported)
    checks = [ClaimCheck(claim=v.claim, supported=v.supported, reason=v.reason) for v in verdicts]

    # Repair pass: one regeneration call per unsupported claim, budget-capped.
    # R7: each repair re-passes the full verification path before it survives.
    unsupported_idx = [i for i, c in enumerate(checks) if not c.supported]
    for i in unsupported_idx[: config.verify.max_repair_calls]:
        if not isinstance(judge, LLMEntailmentJudge):
            break  # the deterministic judge has no repair capability
        report.n_repair_calls += 1
        checks[i] = _repair_and_reverify(
            question, checks[i].claim, evidence, evidence_ids, retriever, judge, report
        )
    # Whatever the repair budget did not cover is dropped.
    for i in unsupported_idx[config.verify.max_repair_calls :]:
        checks[i].dropped = True

    surviving = [c for c in checks if c.supported and not c.dropped]
    report.claims = checks
    report.finalize_claim_states()
    report.support_fraction = len(surviving) / len(checks)

    if report.support_fraction < config.verify.min_support:
        report.abstained = True
        report.final_summary = ABSTENTION_TEXT
        result.summary = ABSTENTION_TEXT
        result.confidence = min(result.confidence, 0.2)
        return

    report.final_summary = " ".join(c.claim for c in surviving)
    result.summary = report.final_summary


def _verify_structured(
    question: str,
    result: AnalysisResult,
    retriever: Retriever,
    config: RAGConfig,
    judge: ClaimJudge,
    report: VerifyReport,
) -> None:
    """R6/R7 schema-v2 path: drafted claims carry verbatim spans.

    Order per claim: deterministic span checks (hard-fail on provenance or
    class-specific violations: non-verbatim span, number/date/temporal token
    absent, negation mismatch, value without a claim entity) → entailment
    judge over the survivors → repair/drop with the R7 guarantee that every
    repair re-passes the full path (fresh verbatim spans → span checks →
    judge) before it can survive. In diagnose mode (tuning only)
    mechanically-failed claims are also judged so the false-rejection rate
    can be measured.
    """
    evidence = evidence_for(result, retriever)
    evidence_ids = evidence_labeled(result, retriever)
    diagnose = config.verify.diagnose_mech
    checks: list[ClaimCheck] = []
    mech_failed: list[int] = []
    for drafted in result.claims:
        reasons = check_claim_spans(drafted, retriever.get_chunk)
        if reasons:
            mech_failed.append(len(checks))
            checks.append(
                ClaimCheck(claim=drafted.text, supported=False, reason="; ".join(reasons))
            )
        else:
            checks.append(ClaimCheck(claim=drafted.text, supported=True, reason="mechanical"))
    report.n_drafted = len(checks)
    report.n_mechanical_fail = len(mech_failed)

    to_judge = [i for i in range(len(checks)) if i not in mech_failed or diagnose]
    if to_judge:
        report.n_judge_calls += 1
        verdicts = judge.verify_claims(question, [checks[i].claim for i in to_judge], evidence)
        for k, verdict in enumerate(verdicts):
            i = to_judge[k]
            prior = checks[i].reason
            judge_supported = verdict.supported
            if i in mech_failed:
                if judge_supported:
                    report.mechanical_false_rejections += 1
                checks[i] = ClaimCheck(
                    claim=verdict.claim,
                    supported=judge_supported,
                    reason=f"{prior}; judge: {verdict.reason}",
                )
            else:
                checks[i] = ClaimCheck(
                    claim=verdict.claim,
                    supported=judge_supported,
                    reason=f"mechanical; judge: {verdict.reason}",
                )
    report.n_judged = len(to_judge)
    report.n_judge_supported += sum(1 for v in verdicts if v.supported)

    # Repair/drop over judge-rejected claims — R7 full-path re-verification.
    unsupported_idx = [i for i, c in enumerate(checks) if not c.supported]
    budget = config.verify.max_repair_calls
    for i in unsupported_idx[:budget]:
        if not isinstance(judge, LLMEntailmentJudge):
            break  # the deterministic judge has no repair capability
        report.n_repair_calls += 1
        checks[i] = _repair_and_reverify(
            question, checks[i].claim, evidence, evidence_ids, retriever, judge, report
        )
    for i in unsupported_idx[budget:]:
        checks[i].dropped = True

    surviving = [c for c in checks if c.supported and not c.dropped]
    report.claims = checks
    report.finalize_claim_states()
    report.support_fraction = (
        len(surviving) / len(checks) if checks else None
    )  # None = nothing drafted, never a fake 1.0

    if report.support_fraction is not None and report.support_fraction < config.verify.min_support:
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
