"""Domain schemas: corpus documents, chunks, citations, agent output, eval rows."""

from typing import Literal

from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field, model_validator


class Article(PortfolioBaseModel):
    """One Wikipedia article selected for the topical corpus."""

    article_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    text: str = Field(min_length=1)


class Chunk(PortfolioBaseModel):
    """A retrievable text unit cut from an article."""

    chunk_id: str = Field(min_length=1)
    article_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    token_count: int = Field(ge=1)
    # R7 provenance: body offsets into the source article text (0 for legacy
    # indexes built before offsets were recorded).
    char_start: int = Field(default=0, ge=0)
    char_end: int = Field(default=0, ge=0)


class Citation(PortfolioBaseModel):
    """A retrieved evidence passage referenced by the agent's answer."""

    chunk_id: str = Field(min_length=1)
    article_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    score: float = Field(default=1.0, ge=0.0)


class EvidenceSpan(PortfolioBaseModel):
    """One verbatim evidence span backing a drafted claim."""

    chunk_id: str = Field(min_length=1)
    exact_text: str = Field(min_length=1)


class DraftedClaim(PortfolioBaseModel):
    """A claim with its cited chunks and verbatim supporting span(s).

    Schema v2 (R6): claims are drafted WITH evidence — each span must be an
    exact substring of the cited chunk. Multi-hop claims cite several chunks
    and may carry several spans. The mechanical checker in ``rag_agent.verify``
    enforces this before the entailment judge sees anything.
    """

    text: str = Field(min_length=1)
    citation_chunk_ids: list[str] = Field(min_length=1)
    spans: list[EvidenceSpan] = Field(min_length=1)


class AnalysisResult(PortfolioBaseModel):
    """Structured agent output: grounded summary plus supporting citations.

    Abstention contract (R6): when the evidence cannot answer, the agent
    outputs the refusal summary with ``confidence < 0.3`` and EMPTY
    ``citations``/``claims`` — see the field note below.
    """

    summary: str = Field(min_length=1)
    # R6: empty citations are the HONEST abstention shape — a refusal has
    # nothing worth citing. The pre-R6 min_length=1 forced the agent to cite
    # "the closest passages" to refuse, and on unanswerable questions the
    # citation mandate sent it into a search/read tool loop that burned the
    # run's token budget (Wave Hub, stress pass A). Non-abstention answers
    # with no citations are caught downstream: the entailment judge scores
    # them against an empty evidence set and they fail as unsupported.
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    # Schema v2 (R6): per-claim evidence spans. Absent in older runs and
    # mocks — the verify loop falls back to claim-splitting the summary.
    claims: list[DraftedClaim] = Field(default_factory=list)


class EvalQuestion(PortfolioBaseModel):
    """A graded retrieval question: relevant articles are known upfront.

    ``expected_behavior`` is ``abstain`` for unanswerable questions (no
    relevant evidence in the corpus): the correct agent behaviour is to refuse
    rather than answer from weakly-related passages.
    """

    question: str = Field(min_length=1)
    relevant_article_ids: list[str] = Field(default_factory=list)
    category: Literal["single_hop", "multi_hop", "unanswerable", "ambiguous"] = "single_hop"
    expected_behavior: Literal["answer", "abstain"] = "answer"

    @model_validator(mode="after")
    def _answerable_questions_need_relevance(self) -> "EvalQuestion":
        if self.expected_behavior == "answer" and not self.relevant_article_ids:
            raise ValueError("answerable questions need at least one relevant article id")
        return self
