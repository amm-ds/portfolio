"""Bounded, stratified preparation of the AG News dataset (real, HF datasets).

The full AG News corpus (120k train / 7.6k test) is far more than a CPU
showcase needs. We download it once, draw a seeded, per-class stratified
subsample (4000 train / 1000 test), carve a stratified validation split out of
the train subsample, run data-quality gates, and persist everything to
``data/`` in the HuggingFace arrow format together with a DatasetContract.
"""

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path
from typing import Any, TypeVar, cast

import numpy as np
from datasets import Dataset, DatasetDict, load_dataset  # type: ignore[import-untyped]
from portfolio_core.dq import DQReport
from portfolio_core.io import sha256_of
from portfolio_core.logging import get_logger
from portfolio_core.schemas import DatasetContract

from nlp_classification.config import NLPConfig

logger = get_logger(__name__)

TEXT_COLUMN = "text"
LABEL_COLUMN = "label"

T = TypeVar("T", bound=Dataset)


def load_ag_news() -> DatasetDict:
    """Download the real AG News dataset from the HuggingFace hub."""
    logger.info("loading dataset fancyzhx/ag_news from the HuggingFace hub")
    return load_dataset("fancyzhx/ag_news")


def load_full_train(
    cfg: NLPConfig, subset: int | None, loader: Callable[[], DatasetDict] = load_ag_news
) -> tuple[Dataset, Dataset]:
    """Full-data path: full AG News train split, optionally bounded per class.

    Used by ``train-nn --full-data`` (GPU-track roadmap item). ``subset``
    draws a seeded per-class stratified slice for bounded evidence runs; the
    same stratified carve-out yields a validation split for early stopping.
    The test split is always the bounded persisted one — never touched here.
    """
    raw = loader()
    full_train = raw["train"]
    train_part = (
        stratified_subsample(full_train, subset, seed=cfg.seed)
        if subset is not None
        else full_train
    )
    train_part, val_part = stratified_split(train_part, cfg.val_fraction, seed=cfg.seed + 2)
    logger.info(
        "full-data path: train=%d val=%d (subset=%s)", len(train_part), len(val_part), subset
    )
    return train_part, val_part


def stratified_subsample[T: Dataset](dataset: T, n_samples: int, seed: int) -> T:
    """Draw exactly ``n_samples`` rows with per-class proportional sampling.

    The per-class quotas come from a seeded ``numpy.random.RandomState`` so the
    subsample is deterministic and the class balance of the source split is
    preserved (AG News is balanced; this stays correct if it were not).
    """
    labels = np.asarray(dataset[LABEL_COLUMN])
    classes, counts = np.unique(labels, return_counts=True)
    n_total = len(labels)
    if n_samples > n_total:
        raise ValueError(f"n_samples={n_samples} exceeds split size {n_total}")

    rng = np.random.RandomState(seed)
    picked: list[int] = []
    for cls, count in zip(classes, counts, strict=True):
        cls_idx = np.flatnonzero(labels == cls)
        n_pick = min(len(cls_idx), round(n_samples * count / n_total))
        chosen = rng.choice(cls_idx, size=n_pick, replace=False)
        picked.extend(int(i) for i in chosen)

    # Fix rounding drift deterministically by topping up from the remainder.
    remainder = np.setdiff1d(np.arange(n_total), np.asarray(picked, dtype=int))
    if len(picked) < n_samples:
        extra = rng.choice(remainder, size=n_samples - len(picked), replace=False)
        picked.extend(int(i) for i in extra)
    picked = sorted(picked[:n_samples])
    return cast(T, dataset.select(picked))


def stratified_split[T: Dataset](dataset: T, val_fraction: float, seed: int) -> tuple[T, T]:
    """Split a dataset into (train, val) preserving class proportions."""
    labels = np.asarray(dataset[LABEL_COLUMN])
    classes = np.unique(labels)
    rng = np.random.RandomState(seed)

    train_idx: list[int] = []
    val_idx: list[int] = []
    for cls in classes:
        cls_idx = np.flatnonzero(labels == cls)
        rng.shuffle(cls_idx)
        n_val = max(1, round(val_fraction * len(cls_idx)))
        val_idx.extend(int(i) for i in cls_idx[:n_val])
        train_idx.extend(int(i) for i in cls_idx[n_val:])

    train_part = cast(T, dataset.select(sorted(train_idx)))
    val_part = cast(T, dataset.select(sorted(val_idx)))
    return train_part, val_part


def tokenize_dataset[T: Dataset](
    dataset: T, tokenizer: Callable[..., Mapping[str, Any]], max_length: int
) -> T:
    """Tokenize and pad every row to exactly ``max_length`` tokens.

    Padding up-front keeps the hand-written DataLoader simple (explicit collate)
    and makes the length bound explicit and testable.
    """
    if max_length < 1:
        raise ValueError("max_length must be >= 1")

    def _encode(batch: dict[str, list[str]]) -> dict[str, list[list[int]]]:
        encoded = tokenizer(
            batch[TEXT_COLUMN], truncation=True, padding="max_length", max_length=max_length
        )
        return {
            "input_ids": [list(ids) for ids in encoded["input_ids"]],
            "attention_mask": [list(m) for m in encoded["attention_mask"]],
        }

    return cast(T, dataset.map(_encode, batched=True, desc="tokenizing"))


def label_names(dataset: Dataset) -> list[str]:
    """Class names from the dataset features (e.g. World/Sports/Business/Sci-Tech)."""
    feature = dataset.features[LABEL_COLUMN]
    names = getattr(feature, "names", None)
    if not names:
        raise ValueError(f"dataset has no label names in features: {feature}")
    return [str(n) for n in names]


def run_dq_gates(dataset: Dataset, name: str, n_labels: int) -> DQReport:
    """Data-quality gates: text completeness and label range."""
    texts = dataset[TEXT_COLUMN]
    null_rate = float(np.mean([not (t and t.strip()) for t in texts]))
    labels = np.asarray(dataset[LABEL_COLUMN], dtype=int)
    report = DQReport(dataset=name, n_rows=len(labels))
    report.check_null_rate(TEXT_COLUMN, null_rate, max_null_rate=0.0)
    report.check_range(
        LABEL_COLUMN,
        min_observed=float(labels.min()),
        max_observed=float(labels.max()),
        lo=0.0,
        hi=float(n_labels - 1),
    )
    return report


def build_dataset_contract(cfg: NLPConfig) -> DatasetContract:
    """Identity card for the prepared snapshot, checksum over the arrow files."""
    files = sorted(
        p for p in cfg.data_dir.rglob("*.arrow") if p.is_file() and p.name.startswith("data-")
    )
    if not files:
        raise FileNotFoundError(f"no prepared data files found under {cfg.data_dir}")
    checksum = sha256_of(files[0]) if len(files) == 1 else _combined_sha256(files)
    n_rows = sum(len(Dataset.from_file(str(p))) for p in files)
    return DatasetContract(
        name="ag_news_bounded",
        source=cfg.dataset_source,
        license=cfg.dataset_license,
        snapshot_date=date.today(),
        checksum_sha256=checksum,
        n_rows=n_rows,
    )


def _combined_sha256(files: list[Path]) -> str:
    h = hashlib.sha256()
    for p in files:
        h.update(p.name.encode())
        h.update(sha256_of(p).encode())
    return h.hexdigest()


def prepare(cfg: NLPConfig, loader: Callable[[], DatasetDict] = load_ag_news) -> DatasetContract:
    """Full prepare stage: download → subsample → DQ gates → persist + contract.

    ``loader`` is injectable so tests can run the whole stage without network.
    """
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    raw = loader()

    train = stratified_subsample(raw["train"], cfg.train_samples, seed=cfg.seed)
    test = stratified_subsample(raw["test"], cfg.test_samples, seed=cfg.seed + 1)
    train_part, val_part = stratified_split(train, cfg.val_fraction, seed=cfg.seed + 2)
    logger.info("subsampled train=%d val=%d test=%d", len(train_part), len(val_part), len(test))

    names = label_names(train)
    n_labels = len(names)
    (cfg.data_dir / "label_names.json").write_text(json.dumps(names))

    for split, ds in (("train", train_part), ("val", val_part), ("test", test)):
        report = run_dq_gates(ds, f"ag_news/{split}", n_labels)
        report.raise_if_failed()
        (cfg.data_dir / f"dq_{split}.md").write_text(report.to_markdown())
        ds.save_to_disk(str(getattr(cfg, f"{split}_dir")))

    contract = build_dataset_contract(cfg)
    (cfg.data_dir / "dataset_contract.json").write_text(contract.model_dump_json(indent=2))
    logger.info("dataset contract written: %s", contract.name)
    return contract
