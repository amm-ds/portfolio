"""4-epoch fine-tuning probe: the measured answer to "why so few epochs?".

Side artifact, deliberately NOT a dvc stage: re-runs the full-120k headline
configuration (seed 42, params.yaml hypers) with the epoch budget raised to 4
and early stopping effectively disabled (patience 4 cannot fire inside the
budget), writing to *probe* paths so the committed ``distilbert_full_120k``
artifact is untouched:

- ``reports/models/distilbert_fulldata_probe4.pt`` (state dict)
- ``reports/history_probe4.json`` (same ``TrainingHistory`` schema)
- ``reports/figures/epochs_probe.{json,html}`` — val macro-F1 vs train loss,
  annotated with the shipped 2-epoch numbers

One honest caveat: the hand-written LR schedule is a function of total steps,
so probe epochs 1-2 do not bit-match the shipped 2-epoch run's epochs 1-2.
The probe answers "what would a 4-epoch budget have delivered?", not
"reproduce epochs 3-4 of the shipped run".

Run: ``uv run python -m nlp_classification.epochs_probe`` (project working
directory; accelerator-gated like ``train-nn --full-data``).
"""

import time
from pathlib import Path

import plotly.graph_objects as go
from portfolio_core.logging import get_logger
from portfolio_core.plotting import apply_theme, save_html, save_json

from nlp_classification.config import NLPConfig
from nlp_classification.data import label_names, load_full_train, tokenize_dataset
from nlp_classification.evaluate import load_tokenizer
from nlp_classification.model import (
    TrainingHistory,
    resolve_device,
    save_nn_state_dict,
    train_nn,
)

logger = get_logger(__name__)

PROBE_EPOCHS = 4
# Patience equal to the budget: even if every epoch after the first degrades,
# the counter cannot reach zero before the last epoch — early stop is off.
PROBE_PATIENCE = PROBE_EPOCHS
PROBE_MODEL_PATH = "distilbert_fulldata_probe4.pt"
PROBE_HISTORY_PATH = "history_probe4.json"
PROBE_FIGURE_NAME = "epochs_probe"

# Shipped 2-epoch headline run (reports/history_fulldata.json /
# reports/metrics.json → distilbert_full_120k) — the annotation anchor.
SHIPPED_VAL_F1 = 0.9464242434561179
SHIPPED_TEST_F1 = 0.9460236394680519
# Below this val-F1 delta, extra epochs are reported as "no material gain".
MATERIAL_GAIN = 0.001


def probe_config(cfg: NLPConfig) -> NLPConfig:
    """Headline hypers with the 4-epoch budget and early stopping disabled."""
    return cfg.model_copy(update={"epochs": PROBE_EPOCHS, "early_stop_patience": PROBE_PATIENCE})


def run_epochs_probe(cfg: NLPConfig) -> TrainingHistory:
    """The ``train-nn --full-data`` path with the probe budget and probe paths."""
    cfg = probe_config(cfg)
    train_part, val_part = load_full_train(cfg, subset=None)
    device = resolve_device("auto", full_data=True, train_rows=len(train_part))
    tokenizer = load_tokenizer(cfg.model_name)
    train_tok = tokenize_dataset(train_part, tokenizer, cfg.max_length)
    val_tok = tokenize_dataset(val_part, tokenizer, cfg.max_length)
    n_labels = len(label_names(train_part))

    logger.info(
        "epochs probe: %d rows, device=%s, epochs=%d, patience=%d",
        len(train_tok),
        device,
        cfg.epochs,
        cfg.early_stop_patience,
    )
    model, history = train_nn(cfg, train_tok, val_tok, n_labels, device)
    save_nn_state_dict(model, cfg.models_dir / PROBE_MODEL_PATH)
    history.to_json(Path(cfg.reports_dir) / PROBE_HISTORY_PATH)
    return history


def epochs_probe_figure(history: TrainingHistory) -> go.Figure:
    """Val macro-F1 vs train loss over the probe epochs, shipped run annotated.

    The verdict on epochs 3-4 is decided by the measured numbers: a val-F1
    gain below ``MATERIAL_GAIN`` is reported as a plateau, a larger one is
    stated plainly as an improvement.
    """
    epochs = [e.epoch for e in history.epochs]
    f1s = [e.val_f1_macro for e in history.epochs]
    losses = [e.train_loss for e in history.epochs]
    if len(history.epochs) < PROBE_EPOCHS:
        raise ValueError(f"probe history has {len(history.epochs)} epochs, expected {PROBE_EPOCHS}")

    e2_f1 = f1s[1]
    late_gain = max(f1s[2:]) - e2_f1
    verdict = (
        "the gain that doesn't materialize — plateau, not progress"
        if late_gain < MATERIAL_GAIN
        else f"val macro-F1 improves by {late_gain:+.4f} — epochs 3-4 DO help"
    )

    fig = go.Figure()
    fig.add_scatter(x=epochs, y=losses, name="train loss")
    fig.add_scatter(x=epochs, y=f1s, name="val macro-F1", yaxis="y2")
    fig.update_layout(
        title=(
            f"4-epoch probe (full 120k, seed 42): val macro-F1 plateaus at "
            f"~{max(f1s):.4f} while train loss keeps falling"
        ),
        xaxis_title="epoch",
        yaxis_title="train loss",
        yaxis2={"title": "val macro-F1", "overlaying": "y", "side": "right"},
        # wider right margin so the overlaid axis title is not clipped
        margin={"l": 60, "r": 70, "t": 60, "b": 50},
        annotations=[
            {
                "x": 2,
                "y": e2_f1,
                "yref": "y2",
                "text": (
                    f"shipped 2-epoch run:<br>val {SHIPPED_VAL_F1:.4f} / test {SHIPPED_TEST_F1:.4f}"
                ),
                "showarrow": True,
                "arrowhead": 2,
                "ax": -40,
                "ay": -60,
            },
            {
                # mid-plot: clear of both curves (val F1 sits high, train loss low)
                "x": 2.8,
                "xref": "x",
                "y": 0.5,
                "yref": "paper",
                "text": (
                    f"epochs 3-4: {f1s[2] - e2_f1:+.4f} / {f1s[3] - e2_f1:+.4f} "
                    f"val F1 vs epoch 2 —<br>{verdict}"
                ),
                "showarrow": False,
                "font": {"size": 12},
            },
        ],
    )
    return apply_theme(fig)


def main() -> None:
    """Run the probe and persist model + history + figure (project cwd)."""
    started = time.perf_counter()
    cfg = NLPConfig()
    history = run_epochs_probe(cfg)
    fig = epochs_probe_figure(history)
    figures_dir = Path(cfg.reports_dir) / "figures"
    save_json(fig, figures_dir / f"{PROBE_FIGURE_NAME}.json")
    save_html(fig, figures_dir / f"{PROBE_FIGURE_NAME}.html")
    best = history.best_epoch()
    logger.info(
        "epochs probe done: best epoch=%d val_f1=%.4f in %.1fs",
        best.epoch,
        best.val_f1_macro,
        time.perf_counter() - started,
    )


if __name__ == "__main__":
    main()
