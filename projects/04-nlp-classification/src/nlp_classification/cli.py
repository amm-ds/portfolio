"""Typer CLI: prepare / train-baseline / train-nn [--full-data] / hpo /
hpo-seeds / train-tuned / train-encoder-b / evaluate / all."""

import json
import time
from pathlib import Path

import numpy as np
import torch
import typer
from portfolio_core.logging import get_logger

from nlp_classification.config import HPOBest, NLPConfig
from nlp_classification.data import label_names, load_full_train, tokenize_dataset
from nlp_classification.data import prepare as run_prepare
from nlp_classification.evaluate import evaluate as run_evaluate
from nlp_classification.evaluate import load_tokenizer
from nlp_classification.hpo import (
    persist_hpo,
    persist_seed_report,
    run_hpo,
    run_multi_seed_hpo,
    tuned_config,
)
from nlp_classification.model import (
    BASELINE_PATH,
    ENCODER_B_MODEL_PATH,
    FULLDATA_MODEL_PATH,
    NN_MODEL_PATH,
    TUNED_MODEL_PATH,
    DeviceGateError,
    predict_baseline,
    resolve_device,
    save_baseline,
    save_nn_state_dict,
    train_baseline,
    train_nn,
)
from nlp_classification.shims import Dataset

PARAMS_PATH = Path("params.yaml")

app = typer.Typer(help="NLP multi-class classification with Transformers (AG News).")
logger = get_logger(__name__)


def _cfg() -> NLPConfig:
    cfg = NLPConfig()
    best_file = Path(cfg.reports_dir) / "hpo_best.json"
    if best_file.exists() and cfg.hpo_best is None:
        cfg = cfg.model_copy(
            update={"hpo_best": HPOBest.model_validate_json(best_file.read_text())}
        )
    return cfg


def _load_split(cfg: NLPConfig, name: str) -> Dataset:
    return Dataset.load_from_disk(str(getattr(cfg, f"{name}_dir")))


def _tokenized_splits(cfg: NLPConfig, model_name: str) -> tuple[Dataset, Dataset, int]:
    train_ds = _load_split(cfg, "train")
    val_ds = _load_split(cfg, "val")
    tokenizer = load_tokenizer(model_name)
    train_tok = tokenize_dataset(train_ds, tokenizer, cfg.max_length)
    val_tok = tokenize_dataset(val_ds, tokenizer, cfg.max_length)
    return train_tok, val_tok, len(label_names(train_ds))


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
def train_nn_cmd(
    full_data: bool = typer.Option(
        False, "--full-data", help="Train on the full AG News train split (GPU-gated)."
    ),
    subset: int | None = typer.Option(
        None,
        "--subset",
        help="Bounded per-class stratified subset of the full split (evidence runs).",
    ),
    force_cpu: bool = typer.Option(
        False, "--force-cpu", help="Run the full-data path on CPU despite the wall-clock estimate."
    ),
    device: str = typer.Option(
        "auto",
        "--device",
        help="Training device: auto (accelerator for --full-data, else CPU), mps, or cpu.",
    ),
    epochs: int | None = typer.Option(
        None, "--epochs", help="Override the epoch budget for this run (default: params.yaml)."
    ),
) -> None:
    """Fine-tune DistilBERT: bounded split by default; --full-data for the GPU track."""
    started = time.perf_counter()
    cfg = _cfg()
    if epochs is not None:
        if epochs < 1:
            raise typer.BadParameter("--epochs must be >= 1")
        cfg = cfg.model_copy(update={"epochs": epochs})
    if subset is not None and not full_data:
        raise typer.BadParameter("--subset only makes sense with --full-data")

    requested = "cpu" if force_cpu else device
    if full_data:
        train_part, val_part = load_full_train(cfg, subset)
        try:
            device_obj = resolve_device(requested, full_data=True, train_rows=len(train_part))
        except DeviceGateError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=2) from exc
        if device_obj.type == "cpu":
            typer.echo(
                f"WARNING: running the full-data path on CPU "
                f"({len(train_part):,} rows) — this is a bounded evidence run, "
                "not the full 120k GPU job."
            )
        model_path = cfg.models_dir / FULLDATA_MODEL_PATH
        history_path = Path(cfg.reports_dir) / "history_fulldata.json"
    else:
        train_part = _load_split(cfg, "train")
        val_part = _load_split(cfg, "val")
        device_obj = resolve_device(requested, full_data=False, train_rows=len(train_part))
        model_path = cfg.models_dir / NN_MODEL_PATH
        history_path = cfg.history_path

    tokenizer = load_tokenizer(cfg.model_name)
    train_tok = tokenize_dataset(train_part, tokenizer, cfg.max_length)
    val_tok = tokenize_dataset(val_part, tokenizer, cfg.max_length)
    n_labels = len(label_names(train_part))

    typer.echo(f"training on device={device_obj} (batch={cfg.batch_size}, epochs={cfg.epochs})")
    model, history = train_nn(cfg, train_tok, val_tok, n_labels, device_obj)
    save_nn_state_dict(model, model_path)
    history.to_json(history_path)
    best = history.best_epoch()
    typer.echo(
        f"model saved to {model_path} "
        f"(best epoch={best.epoch}, val_f1={best.val_f1_macro:.4f}) "
        f"in {time.perf_counter() - started:.1f}s"
    )


@app.command()
def hpo() -> None:
    """Optuna HPO over the fine-tuning loop (median pruning between epochs)."""
    started = time.perf_counter()
    cfg = _cfg()
    train_tok, val_tok, n_labels = _tokenized_splits(cfg, cfg.model_name)

    device = torch.device("cpu")
    best, study = run_hpo(cfg, train_tok, val_tok, n_labels, device)
    persist_hpo(cfg, best, study, PARAMS_PATH)
    typer.echo(
        f"best params: {json.dumps(best.model_dump())} in {time.perf_counter() - started:.1f}s"
    )


@app.command(name="hpo-seeds")
def hpo_seeds_cmd() -> None:
    """Seed-variance study: small independent HPO studies per fixed seed."""
    started = time.perf_counter()
    cfg = _cfg()
    train_tok, val_tok, n_labels = _tokenized_splits(cfg, cfg.model_name)

    device = torch.device("cpu")
    report = run_multi_seed_hpo(cfg, train_tok, val_tok, n_labels, device)
    path = persist_seed_report(cfg, report)
    typer.echo(
        f"seed variance: mean={report['mean']:.4f} std={report['std']:.4f} "
        f"over seeds {cfg.hpo_seeds.seeds} -> {path} "
        f"in {time.perf_counter() - started:.1f}s"
    )


@app.command(name="train-tuned")
def train_tuned_cmd() -> None:
    """Retrain DistilBERT with the HPO best params; saves distilbert_tuned.pt."""
    started = time.perf_counter()
    cfg = _cfg()
    if cfg.hpo_best is None:
        raise typer.BadParameter("hpo_best not found — run the hpo stage first")
    tuned = tuned_config(cfg)
    train_tok, val_tok, n_labels = _tokenized_splits(cfg, cfg.model_name)

    device = torch.device("cpu")
    model, history = train_nn(tuned, train_tok, val_tok, n_labels, device)
    model_path = save_nn_state_dict(model, cfg.models_dir / TUNED_MODEL_PATH)
    history.to_json(cfg.reports_dir / "history_tuned.json")
    best = history.best_epoch()
    typer.echo(
        f"tuned model saved to {model_path} "
        f"(best epoch={best.epoch}, val_f1={best.val_f1_macro:.4f}) "
        f"in {time.perf_counter() - started:.1f}s"
    )


@app.command(name="train-encoder-b")
def train_encoder_b_cmd() -> None:
    """Train the second candidate encoder (default hyperparams, ≤2 epochs)."""
    started = time.perf_counter()
    cfg = _cfg()
    cfg_b = cfg.model_copy(update={"model_name": cfg.encoder_b_name, "epochs": 2})
    train_tok, val_tok, n_labels = _tokenized_splits(cfg_b, cfg_b.model_name)

    device = torch.device("cpu")
    model, history = train_nn(cfg_b, train_tok, val_tok, n_labels, device)
    model_path = save_nn_state_dict(model, cfg.models_dir / ENCODER_B_MODEL_PATH)
    history.to_json(cfg.reports_dir / "history_encoder_b.json")
    best = history.best_epoch()
    typer.echo(
        f"encoder_b saved to {model_path} "
        f"(best epoch={best.epoch}, val_f1={best.val_f1_macro:.4f}) "
        f"in {time.perf_counter() - started:.1f}s"
    )


@app.command()
def evaluate() -> None:
    """Score all six runs on the bounded test split; write report + figures."""
    started = time.perf_counter()
    metrics = run_evaluate(_cfg())
    for run, values in metrics.items():
        if run == "_meta":
            continue  # nested dict (calibration, hpo_seeds) — not a scalar ladder row
        typer.echo(f"{run}: " + ", ".join(f"{k}={v:.4f}" for k, v in values.items()))
    typer.echo(f"report written to reports/report.html in {time.perf_counter() - started:.1f}s")


@app.command(name="all")
def run_all() -> None:
    """Full pipeline: prepare → baseline → train-nn → hpo → seeds → tuned → encoder-b → evaluate."""
    started = time.perf_counter()
    prepare()
    train_baseline_cmd()
    train_nn_cmd()
    hpo()
    hpo_seeds_cmd()
    train_tuned_cmd()
    train_encoder_b_cmd()
    evaluate()
    typer.echo(f"pipeline finished in {time.perf_counter() - started:.1f}s")


def main() -> None:
    """Module entrypoint for ``python -m nlp_classification.cli``."""
    app()


if __name__ == "__main__":
    main()
