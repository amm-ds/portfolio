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


class Citation(PortfolioBaseModel):
    """A retrieved evidence passage referenced by the agent's answer."""

    chunk_id: str = Field(min_length=1)
    article_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    score: float = Field(default=1.0, ge=0.0)


class AnalysisResult(PortfolioBaseModel):
    """Structured agent output: grounded summary plus supporting citations."""

    summary: str = Field(min_length=1)
    citations: list[Citation] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class EvalQuestion(PortfolioBaseModel):
    """A graded retrieval question: relevant articles are known upfront.

    ``expected_behavior`` is ``abstain`` for unanswerable questions (no
    relevant evidence in the corpus): the correct agent behaviour is to refuse
    rather than answer from weakly-related passages.
    """

    question: str = Field(min_length=1)
    relevant_article_ids: list[str] = Field(default_factory=list)
    category: Literal["single_hop", "multi_hop", "unanswerable"] = "single_hop"
    expected_behavior: Literal["answer", "abstain"] = "answer"

    @model_validator(mode="after")
    def _answerable_questions_need_relevance(self) -> "EvalQuestion":
        if self.expected_behavior == "answer" and not self.relevant_article_ids:
            raise ValueError("answerable questions need at least one relevant article id")
        return self
