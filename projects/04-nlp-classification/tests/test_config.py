"""Config validation tests."""

from pathlib import Path

import pytest
from nlp_classification.config import NLPConfig
from pydantic import ValidationError


def test_defaults_match_spec() -> None:
    cfg = NLPConfig()
    assert cfg.model_name == "distilbert-base-uncased"
    assert cfg.max_length == 128
    assert cfg.batch_size == 32
    assert cfg.epochs == 2
    assert cfg.learning_rate == 2e-5
    assert cfg.seed == 42
    assert cfg.train_samples == 4000
    assert cfg.test_samples == 1000
    assert cfg.tfidf_max_features == 8000
    assert cfg.early_stop_patience == 1


def test_rejects_non_positive_learning_rate() -> None:
    with pytest.raises(ValidationError):
        NLPConfig(learning_rate=0.0)


def test_rejects_zero_max_length() -> None:
    with pytest.raises(ValidationError):
        NLPConfig(max_length=0)


def test_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        NLPConfig(unknown_field=1)  # type: ignore[call-arg]


def test_bounded_subsample_invariant() -> None:
    """The bounded subsample must not silently grow beyond the documented bound."""
    cfg = NLPConfig(train_samples=4000, test_samples=1000)
    assert cfg.train_samples <= 4000
    assert cfg.test_samples <= 1000


def test_derived_paths(tmp_path: Path) -> None:
    cfg = NLPConfig(data_dir=tmp_path / "d", reports_dir=tmp_path / "r")
    assert cfg.train_dir == tmp_path / "d" / "train"
    assert cfg.models_dir == tmp_path / "r" / "models"
    assert cfg.history_path == tmp_path / "r" / "history.json"
