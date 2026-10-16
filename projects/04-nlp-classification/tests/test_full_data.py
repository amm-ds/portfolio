"""Full-data path and seed-plumbing tests (offline, mocked loader)."""

from collections.abc import Callable

import pytest
import torch
from datasets import ClassLabel, Dataset, DatasetDict, Features, Value
from nlp_classification.config import NLPConfig
from nlp_classification.data import LABEL_COLUMN, TEXT_COLUMN, load_full_train
from nlp_classification.hpo import make_study, suggest_config
from nlp_classification.model import (
    DeviceGateError,
    _shrink_until_fits,
    mps_safe_batch_size,
    resolve_device,
)

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


def test_resolve_device_bounded_path_is_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bounded showcase stays CPU-first even when an accelerator exists."""
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    dev = resolve_device("auto", full_data=False, train_rows=3600)
    assert dev.type == "cpu"


def test_resolve_device_full_data_requires_accelerator(monkeypatch: pytest.MonkeyPatch) -> None:
    """With mps+cuda mocked unavailable, full-data auto raises the honest gate."""
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(DeviceGateError, match="--force-cpu"):
        resolve_device("auto", full_data=True, train_rows=120_000)
    # the gate message carries an honest wall-clock estimate
    try:
        resolve_device("auto", full_data=True, train_rows=120_000)
    except DeviceGateError as exc:
        assert "min/epoch" in str(exc) or "h per" in str(exc)
    assert resolve_device("cpu", full_data=True, train_rows=120_000).type == "cpu"


def test_resolve_device_mps_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    assert resolve_device("auto", full_data=True, train_rows=120_000).type == "mps"
    assert resolve_device("mps", full_data=True, train_rows=120_000).type == "mps"

    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    with pytest.raises(DeviceGateError, match="mps"):
        resolve_device("mps", full_data=False, train_rows=3600)


def test_resolve_device_rejects_unknown() -> None:
    with pytest.raises(DeviceGateError, match="unknown device"):
        resolve_device("tpu", full_data=False, train_rows=3600)


def test_shrink_until_fits_halves_on_mps_oom() -> None:
    calls: list[int] = []

    def probe(batch: int) -> None:
        calls.append(batch)
        if batch > 8:
            raise RuntimeError("MPS backend out of memory: allocation failed")

    assert _shrink_until_fits(probe, 32) == 8
    assert calls == [32, 16, 8]


def test_shrink_until_fits_reraises_other_errors() -> None:
    def probe(batch: int) -> None:
        raise RuntimeError("kernel failed for an unrelated reason")

    with pytest.raises(RuntimeError, match="unrelated"):
        _shrink_until_fits(probe, 32)


def test_mps_safe_batch_size_skips_probe_off_mps() -> None:
    cfg = NLPConfig(batch_size=32)

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("probe must not run off-MPS")

    monkeypatch_free = mps_safe_batch_size(cfg, _boom, torch.device("cpu"), _boom)  # type: ignore[arg-type]
    assert monkeypatch_free == 32


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
