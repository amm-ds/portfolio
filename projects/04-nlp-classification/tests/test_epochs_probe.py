"""Probe tests: config override and the annotated 4-epoch figure (offline)."""

import pytest
from nlp_classification.config import NLPConfig
from nlp_classification.epochs_probe import (
    PROBE_EPOCHS,
    epochs_probe_figure,
    probe_config,
)
from nlp_classification.model import TrainingHistory


def _record(epoch: int, train_loss: float, val_f1: float) -> dict[str, object]:
    return {
        "epoch": epoch,
        "train_loss": train_loss,
        "val_loss": 0.16,
        "val_f1_macro": val_f1,
        "learning_rate": 1e-5,
    }


def test_probe_config_disables_early_stop() -> None:
    cfg = probe_config(NLPConfig())
    assert cfg.epochs == PROBE_EPOCHS
    # patience == budget: the counter cannot reach zero before the last epoch
    assert cfg.early_stop_patience >= PROBE_EPOCHS
    # headline hypers otherwise untouched
    assert cfg.learning_rate == NLPConfig().learning_rate
    assert cfg.seed == NLPConfig().seed


def test_probe_figure_has_dual_axis_and_annotations() -> None:
    history = TrainingHistory.from_records(
        [_record(e, 0.3 / e, f1) for e, f1 in enumerate([0.94, 0.946, 0.9458, 0.9461], start=1)]
    )
    fig = epochs_probe_figure(history)
    assert len(fig.data) == 2
    assert fig.data[1].yaxis == "y2"
    assert len(fig.layout.annotations) == 2


def test_probe_figure_rejects_short_history() -> None:
    history = TrainingHistory.from_records([_record(1, 0.3, 0.94)])
    with pytest.raises(ValueError, match="probe history"):
        epochs_probe_figure(history)
