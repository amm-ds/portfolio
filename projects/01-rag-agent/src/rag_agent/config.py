"""Project settings and RAG configuration.

Extends the platform settings (ADR-0002) rather than redefining env handling.
All tunables for the pipeline live in :class:`RAGConfig` so ``params.yaml``
and the DVC stages can mirror them 1:1.
"""

from pathlib import Path

from portfolio_core.config import Settings as CoreSettings
from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field, model_validator


class Settings(CoreSettings):
    """RAG-agent settings: platform env handling, no project-specific env vars."""

    # The platform Settings already carries everything this project needs
    # (paths, LLM provider, seed, logging). Subclassing pins the convention.


DEFAULT_TOPICS: list[str] = [
    "Climate",
    "Renewable energy",
    "Aviation",
    "Machine learning",
    "Photosynthesis",
]

# Extra title substrings per topic. The topic name itself is always used as a
# pattern first; these make sparse topics reach a useful corpus size within a
# bounded streaming scan (measured ~3-65 matches/100k rows in the dump head).
DEFAULT_EXTRA_TITLE_PATTERNS: dict[str, list[str]] = {
    "Climate": ["global warming", "greenhouse", "sea level rise"],
    "Renewable energy": [
        "solar energy",
        "solar power",
        "photovoltaic",
        "wind power",
        "wind turbine",
        "hydroelectric",
        "geothermal",
        "biofuel",
    ],
    "Aviation": ["aircraft", "airliner", "aerospace"],
    "Machine learning": [
        "artificial intelligence",
        "neural network",
        "natural language processing",
        "computer vision",
        "large language model",
        "reinforcement learning",
    ],
    "Photosynthesis": ["chlorophyll", "carbon fixation", "algae", "photosystem", "plastid"],
}

# Exact titles collected regardless of the pattern quota. The Wikipedia dump
# order is not topical, so pattern quotas tend to fill on peripheral articles
# long before these flagships appear in the stream; anchoring them first keeps
# the corpus centred on the articles users actually ask about.
DEFAULT_ANCHOR_TITLES: dict[str, list[str]] = {
    "Climate": ["Climate change", "Climate", "Global warming", "Greenhouse effect"],
    "Renewable energy": [
        "Renewable energy",
        "Solar energy",
        "Wind power",
        "Hydroelectricity",
        "Geothermal energy",
        "Photovoltaics",
        "Biofuel",
    ],
    "Aviation": [
        "Aviation",
        "Wright brothers",
        "Aircraft",
        "Airliner",
        "Jet engine",
        "Airport",
        "History of aviation",
    ],
    "Machine learning": [
        "Machine learning",
        "Artificial intelligence",
        "Deep learning",
        "Artificial neural network",
        "Reinforcement learning",
        "Natural language processing",
        "Large language model",
        "Supervised learning",
    ],
    "Photosynthesis": [
        "Photosynthesis",
        "Chloroplast",
        "Chlorophyll",
        "Light-independent reactions",
        "Carbon fixation",
        "Algae",
    ],
}


class RetrievalBest(PortfolioBaseModel):
    """Production retrieval configuration chosen by the HPO sweep.

    Persisted in ``params.yaml`` as ``retrieval_best`` and mirrored in
    ``reports/metrics.json`` (``detail.hpo.chosen``) — the two must agree.
    """

    embedding_model: str = Field(min_length=1)
    embedding_slug: str = Field(min_length=1, description="Short id used in run/figure names.")
    chunk_size: int = Field(ge=1)
    top_k: int = Field(ge=1)
    rerank: bool = True


class VerifyConfig(PortfolioBaseModel):
    """Verify-then-answer loop tunables (wave 14, see rag_agent.verify).

    After the agent drafts an answer, each claim is entailment-checked against
    its cited chunks; unsupported claims are repaired or dropped, and when the
    support fraction stays below ``min_support`` the answer falls back to
    abstention.
    """

    enabled: bool = True
    min_support: float = Field(default=0.6, ge=0.0, le=1.0)
    max_repair_calls: int = Field(default=2, ge=0)


class RAGConfig(PortfolioBaseModel):
    """Tunables for corpus preparation, indexing, retrieval and evaluation."""

    topics: list[str] = Field(default_factory=lambda: list(DEFAULT_TOPICS))
    extra_title_patterns: dict[str, list[str]] = Field(
        default_factory=lambda: {k: list(v) for k, v in DEFAULT_EXTRA_TITLE_PATTERNS.items()}
    )
    anchor_titles: dict[str, list[str]] = Field(
        default_factory=lambda: {k: list(v) for k, v in DEFAULT_ANCHOR_TITLES.items()}
    )
    articles_per_topic: int = Field(default=120, ge=1, le=500)
    max_scan_rows: int = Field(default=7_000_000, ge=1_000)
    seed: int = Field(default=42, description="Seed for the random-retrieval baseline.")
    max_article_chars: int = Field(default=12_000, ge=500)

    chunk_sizes: list[int] = Field(default_factory=lambda: [200, 400, 800])
    chunk_overlap: int = Field(default=40, ge=0)

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    top_k: int = Field(default=5, ge=1, le=20)
    rerank_multiplier: int = Field(default=5, ge=1)
    excerpt_chars: int = Field(default=240, ge=40)

    corpus_path: Path = Path("data/raw/corpus.jsonl")
    contract_path: Path = Path("data/raw/dataset_contract.json")
    index_dir: Path = Path("data/index")
    eval_questions_path: Path = Path("src/rag_agent/eval_questions.json")
    reports_dir: Path = Path("reports")

    usd_per_mtok_input: float = Field(default=0.15, gt=0)
    usd_per_mtok_output: float = Field(default=0.60, gt=0)

    retrieval_best: RetrievalBest | None = Field(
        default=None, description="Production config chosen by the retrieval HPO sweep."
    )

    verify: VerifyConfig = Field(default_factory=VerifyConfig)

    @model_validator(mode="after")
    def _validate_overlap(self) -> "RAGConfig":
        if not self.chunk_sizes:
            raise ValueError("chunk_sizes must not be empty")
        if self.chunk_overlap >= min(self.chunk_sizes):
            raise ValueError("chunk_overlap must be smaller than every chunk size")
        if len(set(self.chunk_sizes)) != len(self.chunk_sizes):
            raise ValueError("chunk_sizes must not contain duplicates")
        return self

    def title_patterns(self, topic: str) -> list[str]:
        """Case-insensitive title substrings that map an article to ``topic``."""
        extras = self.extra_title_patterns.get(topic, [])
        return [topic.lower(), *[p.lower() for p in extras]]

    def index_path(self, chunk_size: int) -> Path:
        """Directory holding the FAISS index + metadata for one chunk size."""
        return self.index_dir / f"chunks_{chunk_size}"
