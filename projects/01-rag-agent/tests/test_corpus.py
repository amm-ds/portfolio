"""Corpus helpers: topic matching, slugging, contract-gated loading (offline)."""

import pytest
from rag_agent.config import RAGConfig
from rag_agent.corpus import load_corpus, match_topic, slugify
from rag_agent.schemas import Article


def test_slugify_is_deterministic_and_lowercase() -> None:
    assert slugify("Renewable energy") == "renewable-energy"
    assert slugify("Machine  learning!") == "machine-learning"
    assert slugify("C3 carbon fixation") == "c3-carbon-fixation"


def test_match_topic_uses_name_then_extra_patterns() -> None:
    config = RAGConfig()
    assert match_topic("Climate change mitigation", config) == "Climate"
    assert match_topic("Machine learning in bioinformatics", config) == "Machine learning"
    assert match_topic("Reinforcement learning robotics", config) == "Machine learning"
    assert match_topic("History of the Roman Empire", config) is None


def test_match_topic_is_case_insensitive() -> None:
    assert match_topic("PHOTOSYNTHESIS variants", RAGConfig()) == "Photosynthesis"


def test_load_corpus_missing_file_raises(config: RAGConfig) -> None:
    with pytest.raises(FileNotFoundError, match="prepare-corpus"):
        load_corpus(config)


def test_load_corpus_roundtrip(config: RAGConfig, articles: list[Article]) -> None:
    config.corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with config.corpus_path.open("w", encoding="utf-8") as fh:
        for article in articles:
            fh.write(article.model_dump_json() + "\n")
    loaded = load_corpus(config)
    assert loaded == articles


def test_config_validation_rejects_bad_overlap() -> None:
    with pytest.raises(ValueError):
        RAGConfig(chunk_sizes=[100, 200], chunk_overlap=100)
    with pytest.raises(ValueError):
        RAGConfig(chunk_sizes=[100, 100])
    with pytest.raises(ValueError):
        RAGConfig(chunk_sizes=[])
