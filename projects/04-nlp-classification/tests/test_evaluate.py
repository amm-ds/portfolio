"""Figure builders: smoke tests with tiny inputs (no model artifacts needed)."""

from datasets import Dataset  # type: ignore[import-untyped]
from nlp_classification.evaluate import (
    confusion_matrix_figure,
    eda_class_balance_figure,
    per_class_f1_figure,
    training_curve_figure,
)
from nlp_classification.model import TrainingHistory

CLASS_NAMES = ["World", "Sports", "Business", "Sci/Tech"]


def test_confusion_matrix_figure_smoke() -> None:
    y_true = [0, 1, 2, 3, 0, 1]
    y_pred = [0, 1, 2, 2, 0, 3]
    fig = confusion_matrix_figure(y_true, y_pred, ["a", "b", "c", "d"], "cm")
    assert len(fig.data) == 1
    assert list(fig.data[0].z[0]) == [2, 0, 0, 0]  # class 'a': 2 correct


def test_per_class_f1_figure_bounds() -> None:
    fig = per_class_f1_figure([0, 1, 2], [0, 1, 1], ["a", "b", "c"], "f1")
    assert len(fig.data[0].y) == 3
    assert all(0.0 <= v <= 1.0 for v in fig.data[0].y)


def test_training_curve_figure_from_history() -> None:
    history = TrainingHistory.from_records(
        [
            {
                "epoch": 1,
                "train_loss": 1.2,
                "val_loss": 1.1,
                "val_f1_macro": 0.4,
                "learning_rate": 1e-5,
            },
            {
                "epoch": 2,
                "train_loss": 0.6,
                "val_loss": 0.8,
                "val_f1_macro": 0.7,
                "learning_rate": 0.0,
            },
        ]
    )
    fig = training_curve_figure(history)
    assert len(fig.data) == 3  # train loss, val loss, val macro-F1
    assert list(fig.data[0].y) == [1.2, 0.6]


def test_eda_class_balance_figure(tiny_dataset: Dataset) -> None:
    fig = eda_class_balance_figure(tiny_dataset, tiny_dataset, tiny_dataset, CLASS_NAMES)
    assert len(fig.data) == 4  # 3 class-count bars + 1 length histogram
    # balanced fixture: every class counts for the full 200-row train split
    train_counts = list(fig.data[0].y)
    assert train_counts == [50, 50, 50, 50]
