"""Shared fixtures: tiny in-memory AG News-like datasets (no network)."""

from collections.abc import Callable

import pytest
from nlp_classification.data import LABEL_COLUMN, TEXT_COLUMN
from nlp_classification.shims import ClassLabel, Dataset, DatasetDict, Features, Value

N_CLASSES = 4
CLASS_NAMES = ["World", "Sports", "Business", "Sci/Tech"]

FEATURES = Features({TEXT_COLUMN: Value("string"), LABEL_COLUMN: ClassLabel(names=CLASS_NAMES)})


def _rows(n: int) -> dict[str, list[str] | list[int]]:
    texts = [
        f"{CLASS_NAMES[i % N_CLASSES]} news story number {i} with enough words to tokenize"
        for i in range(n)
    ]
    labels = [i % N_CLASSES for i in range(n)]
    return {TEXT_COLUMN: texts, LABEL_COLUMN: labels}


@pytest.fixture()
def tiny_dataset() -> Dataset:
    """200-row balanced in-memory dataset with real ClassLabel features."""
    return Dataset.from_dict(_rows(200), features=FEATURES)


@pytest.fixture()
def tiny_loader(tiny_dataset: Dataset) -> Callable[[], DatasetDict]:
    """Mock replacement for ``load_ag_news`` (the test loader is injected)."""

    def _load() -> DatasetDict:
        return DatasetDict(
            {
                "train": tiny_dataset,
                "test": Dataset.from_dict(_rows(120), features=FEATURES),
            }
        )

    return _load
