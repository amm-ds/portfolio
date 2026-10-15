"""Data-module tests on a tiny synthetic fixture (no network)."""

from collections.abc import Callable
from pathlib import Path

import pytest
from nlp_classification.config import NLPConfig
from nlp_classification.data import (
    LABEL_COLUMN,
    TEXT_COLUMN,
    label_names,
    prepare,
    run_dq_gates,
    stratified_split,
    stratified_subsample,
    tokenize_dataset,
)
from nlp_classification.shims import Dataset, DatasetDict, load_from_disk


def _cfg(tmp_path: Path) -> NLPConfig:
    return NLPConfig(
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
        train_samples=120,
        test_samples=100,
    )


def test_stratified_subsample_size_and_balance(tiny_dataset: Dataset) -> None:
    sub = stratified_subsample(tiny_dataset, 100, seed=7)
    assert len(sub) == 100
    labels = sub[LABEL_COLUMN]
    for cls in range(4):
        assert labels.count(cls) == 25  # per-class proportion preserved


def test_stratified_subsample_is_seeded(tiny_dataset: Dataset) -> None:
    a = stratified_subsample(tiny_dataset, 100, seed=7)
    b = stratified_subsample(tiny_dataset, 100, seed=7)
    c = stratified_subsample(tiny_dataset, 100, seed=8)
    assert a[LABEL_COLUMN] == b[LABEL_COLUMN]
    assert a[TEXT_COLUMN] == b[TEXT_COLUMN]
    assert a[TEXT_COLUMN] != c[TEXT_COLUMN]


def test_stratified_subsample_too_large(tiny_dataset: Dataset) -> None:
    with pytest.raises(ValueError, match="exceeds"):
        stratified_subsample(tiny_dataset, 10_000, seed=7)


def test_stratified_split_proportions(tiny_dataset: Dataset) -> None:
    train, val = stratified_split(tiny_dataset, val_fraction=0.1, seed=0)
    assert len(train) + len(val) == len(tiny_dataset)
    assert abs(len(val) / len(tiny_dataset) - 0.1) < 0.05
    # each class present in both parts
    for cls in range(4):
        assert cls in train[LABEL_COLUMN]
        assert cls in val[LABEL_COLUMN]


def test_label_names_from_features(tiny_dataset: Dataset) -> None:
    assert label_names(tiny_dataset) == ["World", "Sports", "Business", "Sci/Tech"]


def test_dq_gates_pass_on_clean_fixture(tiny_dataset: Dataset) -> None:
    report = run_dq_gates(tiny_dataset, "ag_news/train", n_labels=4)
    report.raise_if_failed()
    assert report.n_failed == 0


def test_dq_gates_fail_on_null_text(tiny_dataset: Dataset) -> None:
    broken = tiny_dataset.map(lambda x, i: {TEXT_COLUMN: ""} if i == 0 else x, with_indices=True)
    report = run_dq_gates(broken, "ag_news/train", n_labels=4)
    assert not report.passed
    with pytest.raises(Exception, match="DQ gates failed"):
        report.raise_if_failed()


class _MockTokenizer:
    """Minimal tokenizer stand-in: truncates to ids by whitespace, pads to max."""

    def __call__(
        self, texts: list[str], truncation: bool, padding: str, max_length: int
    ) -> dict[str, list[list[int]]]:
        input_ids = []
        attention_mask = []
        for text in texts:
            ids = [abs(hash(w)) % 1000 + 1 for w in text.split()][:max_length]
            pad = max_length - len(ids)
            input_ids.append(ids + [0] * pad)
            attention_mask.append([1] * len(ids) + [0] * pad)
        return {"input_ids": input_ids, "attention_mask": attention_mask}


def test_tokenize_caps_length(tiny_dataset: Dataset) -> None:
    """Every row must be padded/truncated to exactly max_length tokens."""
    tok = tokenize_dataset(tiny_dataset.select(range(5)), _MockTokenizer(), max_length=16)
    for ids, mask in zip(tok["input_ids"], tok["attention_mask"], strict=True):
        assert len(ids) == 16
        assert len(mask) == 16


def test_prepare_writes_contract_and_splits(
    tmp_path: Path, tiny_loader: Callable[[], DatasetDict]
) -> None:
    cfg = _cfg(tmp_path)
    contract = prepare(cfg, loader=tiny_loader)

    assert contract.n_rows > 0
    assert (cfg.data_dir / "dataset_contract.json").exists()
    assert (cfg.data_dir / "label_names.json").exists()
    for split in ("train", "val", "test"):
        ds = load_from_disk(str(getattr(cfg, f"{split}_dir")))
        assert len(ds) > 0
        assert (cfg.data_dir / f"dq_{split}.md").exists()

    # re-loadable contract round-trips
    from portfolio_core.schemas import DatasetContract

    reloaded = DatasetContract.model_validate_json(
        (cfg.data_dir / "dataset_contract.json").read_text()
    )
    assert reloaded.name == "ag_news_bounded"
    assert len(reloaded.checksum_sha256) == 64
