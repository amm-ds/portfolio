"""Domain schemas: corpus documents, chunks, citations, agent output, eval rows."""

from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field


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
    """A graded retrieval question: relevant articles are known upfront."""

    question: str = Field(min_length=1)
    relevant_article_ids: list[str] = Field(min_length=1)
