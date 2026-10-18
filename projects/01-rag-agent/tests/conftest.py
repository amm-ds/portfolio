"""Shared offline fixtures: fake corpus, deterministic hashing embedder, tiny index.

No network, no model downloads — the embedding function is a deterministic
hashing vectorizer so retrieval tests are reproducible.
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest
from rag_agent.config import RAGConfig
from rag_agent.index import EmbedFn, Retriever, build_index, chunk_articles
from rag_agent.schemas import Article

EmbedFnType = EmbedFn

FAKE_ARTICLES: list[Article] = [
    Article(
        article_id="climate-000",
        title="Climate change",
        topic="Climate",
        text=(
            "Climate change refers to long-term shifts in global temperatures and weather "
            "patterns. The primary driver of current global warming is the emission of "
            "greenhouse gases such as carbon dioxide from burning fossil fuels. As carbon "
            "dioxide accumulates in the atmosphere, it traps heat and causes the planet to "
            "warm. Consequences include rising sea levels, melting ice sheets, and more "
            "frequent extreme weather events. International agreements such as the Kyoto "
            "Protocol and the Paris Agreement aim to limit warming by reducing emissions."
        ),
    ),
    Article(
        article_id="energy-000",
        title="Solar energy",
        topic="Renewable energy",
        text=(
            "Solar energy is radiant light and heat from the Sun harnessed using a range of "
            "technologies. Solar panels convert sunlight into electricity through the "
            "photovoltaic effect: photons strike a semiconductor material and knock electrons "
            "loose, generating direct current. Solar is a renewable energy source because the "
            "sunshine is practically inexhaustible on human timescales and produces no direct "
            "emissions."
        ),
    ),
    Article(
        article_id="aviation-000",
        title="Aviation",
        topic="Aviation",
        text=(
            "Aviation is the practical aspect or art of aeronautics, being the design, "
            "development, production, operation and use of aircraft. The Wright brothers made "
            "the first controlled, sustained powered flight in 1903. An aircraft wing "
            "generates lift because air flowing over the curved upper surface moves faster "
            "than air below, creating lower pressure above the wing according to Bernoulli's "
            "principle. After World War II, commercial aviation expanded rapidly with "
            "pressurized airliners such as the Douglas DC-6 and the Boeing 377."
        ),
    ),
    Article(
        article_id="ml-000",
        title="Machine learning",
        topic="Machine learning",
        text=(
            "Machine learning is a field of study in artificial intelligence concerned with "
            "algorithms that improve automatically through experience and the use of data. "
            "Unlike traditional programming, where a developer writes explicit rules, a "
            "machine learning system learns patterns from training data. Artificial neural "
            "networks learn by adjusting connection weights to reduce a loss function via "
            "backpropagation. Reinforcement learning trains agents to maximize rewards."
        ),
    ),
    Article(
        article_id="photo-000",
        title="Photosynthesis",
        topic="Photosynthesis",
        text=(
            "Photosynthesis is a process used by plants and other organisms to convert light "
            "energy into chemical energy that can later be released to fuel the organism's "
            "activities. The general equation combines carbon dioxide and water into glucose "
            "and oxygen using light energy. Photosynthesis takes place in organelles called "
            "chloroplasts. Chlorophyll, the pigment in chloroplasts, absorbs red and blue "
            "light and reflects green light, which is why plants appear green. Algae and some "
            "bacteria also perform photosynthesis."
        ),
    ),
]


def hashing_embed_fn(dim: int = 32) -> EmbedFnType:
    """Deterministic bag-of-hashed-words vectorizer (L2-normalized)."""

    def embed(texts: Sequence[str]) -> np.ndarray:
        vecs = np.zeros((len(texts), dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in set(text.lower().split()):
                bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % dim
                vecs[i, bucket] += 1.0
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms

    return embed


@pytest.fixture
def articles() -> list[Article]:
    return [a.model_copy() for a in FAKE_ARTICLES]


@pytest.fixture
def embed_fn() -> EmbedFnType:
    return hashing_embed_fn()


@pytest.fixture
def config(tmp_path: Path) -> RAGConfig:
    return RAGConfig(
        chunk_sizes=[50],
        chunk_overlap=10,
        top_k=3,
        corpus_path=tmp_path / "data" / "raw" / "corpus.jsonl",
        contract_path=tmp_path / "data" / "raw" / "dataset_contract.json",
        index_dir=tmp_path / "data" / "index",
        eval_questions_path=tmp_path / "eval_questions.json",
        heldout_questions_path=tmp_path / "golden_heldout.json",
        reports_dir=tmp_path / "reports",
    )


@pytest.fixture
def index_dir(config: RAGConfig, articles: list[Article], embed_fn: EmbedFnType) -> Path:
    chunks = chunk_articles(articles, size=50, overlap=10)
    build_index(chunks, embed_fn, config.index_path(50), description="test")
    return config.index_path(50)


@pytest.fixture
def retriever(config: RAGConfig, index_dir: Path, embed_fn: EmbedFnType) -> Retriever:
    return Retriever.from_index_dir(config, index_dir, embed_fn)
