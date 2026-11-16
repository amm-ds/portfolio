"""4-epoch fine-tuning probe: the measured answer to "why so few epochs?".

Side artifact, deliberately NOT a dvc stage: re-runs the full-120k headline
configuration (seed 42, params.yaml hypers) with the epoch budget raised to 4
and early stopping effectively disabled (patience 4 cannot fire inside the
budget), writing to *probe* paths so the committed ``distilbert_full_120k``
artifact is untouched:

- ``reports/models/distilbert_fulldata_probe4.pt`` (state dict)
- ``reports/history_probe4.json`` (same ``TrainingHistory`` schema)

The combined ``training_curve`` figure places this history beside the headline
run; no duplicate standalone probe figure is emitted.

One honest caveat: the hand-written LR schedule is a function of total steps,
so probe epochs 1-2 do not bit-match the shipped 2-epoch run's epochs 1-2.
The probe answers "what would a 4-epoch budget have delivered?", not
"reproduce epochs 3-4 of the shipped run".

Run: ``uv run python -m nlp_classification.epochs_probe`` (project working
directory; accelerator-gated like ``train-nn --full-data``).
"""

import time
from pathlib import Path

from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_html, save_json

from nlp_classification.config import NLPConfig
from nlp_classification.data import label_names, load_full_train, tokenize_dataset
from nlp_classification.evaluate import load_tokenizer, training_curve_figure
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


def main() -> None:
    """Run the probe and refresh the combined training figure (project cwd)."""
    started = time.perf_counter()
    cfg = NLPConfig()
    history = run_epochs_probe(cfg)
    headline_path = Path(cfg.reports_dir) / "history_fulldata.json"
    headline = TrainingHistory.from_json(headline_path)
    fig = training_curve_figure(headline, history)
    figures_dir = Path(cfg.reports_dir) / "figures"
    save_json(fig, figures_dir / "training_curve.json")
    save_html(fig, figures_dir / "training_curve.html")
    best = history.best_epoch()
    logger.info(
        "epochs probe done: best epoch=%d val_f1=%.4f in %.1fs",
        best.epoch,
        best.val_f1_macro,
        time.perf_counter() - started,
    )


if __name__ == "__main__":
    main()
