"""Typer CLI: prepare / train-baseline / train-nn / evaluate / all."""

import time

import numpy as np
import torch
import typer
from datasets import Dataset  # type: ignore[import-untyped]
from portfolio_core.logging import get_logger

from nlp_classification.config import NLPConfig
from nlp_classification.data import label_names, tokenize_dataset
from nlp_classification.data import prepare as run_prepare
from nlp_classification.evaluate import evaluate as run_evaluate
from nlp_classification.evaluate import load_tokenizer
from nlp_classification.model import (
    BASELINE_PATH,
    NN_MODEL_PATH,
    predict_baseline,
    save_baseline,
    save_nn_state_dict,
    train_baseline,
    train_nn,
)

app = typer.Typer(help="NLP multi-class classification with Transformers (AG News).")
logger = get_logger(__name__)


def _cfg() -> NLPConfig:
    return NLPConfig()


def _load_split(cfg: NLPConfig, name: str) -> Dataset:
    return Dataset.load_from_disk(str(getattr(cfg, f"{name}_dir")))


@app.command()
def prepare() -> None:
    """Download AG News and persist the bounded, stratified subsample."""
    started = time.perf_counter()
    contract = run_prepare(_cfg())
    typer.echo(f"prepared {contract.n_rows} rows in {time.perf_counter() - started:.1f}s")


@app.command(name="train-baseline")
def train_baseline_cmd() -> None:
    """Fit the TF-IDF + LogisticRegression baseline on the train subsample."""
    started = time.perf_counter()
    cfg = _cfg()
    train_ds = _load_split(cfg, "train")
    model = train_baseline(cfg, train_ds)
    path = save_baseline(model, cfg.models_dir / BASELINE_PATH)
    # Report val accuracy so each stage is self-describing.
    val_ds = _load_split(cfg, "val")
    preds = predict_baseline(model, list(val_ds["text"]))
    acc = float((preds == np.asarray(val_ds["label"])).mean())
    typer.echo(
        f"baseline saved to {path} (val acc={acc:.4f}) in {time.perf_counter() - started:.1f}s"
    )


@app.command(name="train-nn")
def train_nn_cmd() -> None:
    """Fine-tune DistilBERT with the hand-written PyTorch loop (CPU, bounded)."""
    started = time.perf_counter()
    cfg = _cfg()
    train_ds = _load_split(cfg, "train")
    val_ds = _load_split(cfg, "val")
    names = label_names(train_ds)
    tokenizer = load_tokenizer(cfg.model_name)
    train_tok = tokenize_dataset(train_ds, tokenizer, cfg.max_length)
    val_tok = tokenize_dataset(val_ds, tokenizer, cfg.max_length)

    device = torch.device("cpu")
    model, history = train_nn(cfg, train_tok, val_tok, len(names), device)
    model_path = save_nn_state_dict(model, cfg.models_dir / NN_MODEL_PATH)
    history.to_json(cfg.history_path)
    best = history.best_epoch()
    typer.echo(
        f"model saved to {model_path} "
        f"(best epoch={best.epoch}, val_f1={best.val_f1_macro:.4f}) "
        f"in {time.perf_counter() - started:.1f}s"
    )


@app.command()
def evaluate() -> None:
    """Score both approaches on the bounded test split; write report + figures."""
    started = time.perf_counter()
    metrics = run_evaluate(_cfg())
    for run, values in metrics.items():
        typer.echo(f"{run}: " + ", ".join(f"{k}={v:.4f}" for k, v in values.items()))
    typer.echo(f"report written to reports/report.html in {time.perf_counter() - started:.1f}s")


@app.command(name="all")
def run_all() -> None:
    """Run the full pipeline: prepare → baseline → NN fine-tune → evaluate."""
    started = time.perf_counter()
    prepare()
    train_baseline_cmd()
    train_nn_cmd()
    evaluate()
    typer.echo(f"pipeline finished in {time.perf_counter() - started:.1f}s")


def main() -> None:
    """Module entrypoint for ``python -m nlp_classification.cli``."""
    app()


if __name__ == "__main__":
    main()
