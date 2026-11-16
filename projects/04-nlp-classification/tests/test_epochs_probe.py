"""Probe tests: config override and the combined training figure (offline)."""

import pytest
from nlp_classification.config import NLPConfig
from nlp_classification.epochs_probe import PROBE_EPOCHS, probe_config
from nlp_classification.evaluate import training_curve_figure
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


def test_combined_figure_keeps_headline_and_probe_histories_distinct() -> None:
    headline = TrainingHistory.from_records(
        [_record(e, 0.4 / e, f1) for e, f1 in enumerate([0.93, 0.94], start=1)]
    )
    probe = TrainingHistory.from_records(
        [_record(e, 0.3 / e, f1) for e, f1 in enumerate([0.94, 0.946, 0.9458, 0.9461], start=1)]
    )
    fig = training_curve_figure(headline, probe)

    assert len(fig.data) == 7
    assert list(fig.data[0].x) == [1, 2]
    assert list(fig.data[3].x) == [1, 2, 3, 4]
    assert fig.data[-1].name == "headline endpoint (separate run)"
    assert fig.data[-1].marker.symbol == "star"
    assert fig.data[-1].xaxis == "x2"


def test_combined_figure_rejects_short_probe_history() -> None:
    headline = TrainingHistory.from_records([_record(1, 0.4, 0.93)])
    probe = TrainingHistory.from_records([_record(1, 0.3, 0.94)])
    with pytest.raises(ValueError, match="probe history"):
        training_curve_figure(headline, probe)
