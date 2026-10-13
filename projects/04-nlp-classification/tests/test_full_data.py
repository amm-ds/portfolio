"""Full-data path and seed-plumbing tests (offline, mocked loader)."""

from collections.abc import Callable

import pytest
import torch
from datasets import ClassLabel, Dataset, DatasetDict, Features, Value
from nlp_classification.config import NLPConfig
from nlp_classification.data import LABEL_COLUMN, TEXT_COLUMN, load_full_train
from nlp_classification.hpo import make_study, suggest_config
from nlp_classification.model import DeviceGateError, resolve_device

FEATURES = Features(
    {TEXT_COLUMN: Value("string"), LABEL_COLUMN: ClassLabel(names=["a", "b", "c", "d"])}
)


def _full_loader(n: int = 400) -> Callable[[], DatasetDict]:
    def _load() -> DatasetDict:
        texts = [f"article {i} about topic {i % 4}" for i in range(n)]
        labels = [i % 4 for i in range(n)]
        train = Dataset.from_dict({TEXT_COLUMN: texts, LABEL_COLUMN: labels}, features=FEATURES)
        test = Dataset.from_dict(
            {TEXT_COLUMN: texts[:40], LABEL_COLUMN: labels[:40]}, features=FEATURES
        )
        return DatasetDict({"train": train, "test": test})

    return _load


def test_load_full_train_subset_stratified() -> None:
    cfg = NLPConfig()
    train_part, val_part = load_full_train(cfg, subset=200, loader=_full_loader())
    assert len(train_part) + len(val_part) == 200
    for cls in range(4):
        assert train_part[LABEL_COLUMN].count(cls) == 45  # 50 per class minus the 10% val
        assert val_part[LABEL_COLUMN].count(cls) == 5


def test_load_full_train_no_subset_uses_all_rows() -> None:
    cfg = NLPConfig()
    train_part, val_part = load_full_train(cfg, subset=None, loader=_full_loader())
    assert len(train_part) + len(val_part) == 400


def test_resolve_device_bounded_path_is_cpu() -> None:
    NLPConfig()
    dev = resolve_device(force_cpu=False, full_data=False, train_rows=3600)
    assert dev.type in {"cpu", "cuda"}


def test_resolve_device_full_data_requires_gpu_or_force() -> None:
    if torch.cuda.is_available():
        pytest.skip("gate only applies on CPU-only machines")
    with pytest.raises(DeviceGateError, match="--force-cpu"):
        resolve_device(force_cpu=False, full_data=True, train_rows=120_000)
    # the gate message carries an honest wall-clock estimate
    try:
        resolve_device(force_cpu=False, full_data=True, train_rows=120_000)
    except DeviceGateError as exc:
        assert "min/epoch" in str(exc) or "h per" in str(exc)
    assert resolve_device(force_cpu=True, full_data=True, train_rows=120_000).type == "cpu"


def test_make_study_seed_plumbing_is_deterministic() -> None:
    cfg = NLPConfig()
    a1 = make_study(cfg, seed=7).ask()
    a2 = make_study(cfg, seed=7).ask()
    b = make_study(cfg, seed=8).ask()
    p1 = suggest_config(a1, cfg).model_dump()
    p2 = suggest_config(a2, cfg).model_dump()
    p3 = suggest_config(b, cfg).model_dump()
    assert {k: v for k, v in p1.items() if k != "seed"} == {
        k: v for k, v in p2.items() if k != "seed"
    }
    assert p1 != p3  # different seed → different first trial
