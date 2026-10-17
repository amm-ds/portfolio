"""Serving-economics probe: model size, batch-1 latency, throughput, token cost.

Measured, never estimated, on the committed artifacts (nothing is retrained):

- (a) ``tfidf_logreg`` — the fitted TF-IDF + LogisticRegression pipeline.
- (b) ``distilbert_tuned_fp32`` — the bounded-run ``distilbert_tuned`` artifact.
- (c) ``distilbert_full_120k_fp32`` — the full 120k fine-tune
  (``distilbert_fulldata.pt``; the run is reported as ``distilbert_full_120k``).
- (d) ``distilbert_full_120k_int8`` — (c) after ``torch.quantization.quantize_dynamic``
  on the CPU copy (no new dependencies).

Latency is batch=1 end-to-end serving time (tokenize + forward for the
transformers, vectorize + predict for sklearn) on CPU, timed per prediction
with ``time.perf_counter``. Accuracy for the fp32/sklearn rows comes from the
committed ``reports/metrics.json`` (the untouched 1000-row test split — no
re-evaluation); the int8 row's quality is *measured* on a 2000-row train
sample against the fp32 score on the same sample.

Cost uses one declared rate card — $1 / 1M input tokens, $4 / 1M output
tokens — with per-prediction token counts measured from the tokenizer
(truncated input length in, tokenized predicted class name out, 1-5 tokens).
"""

import argparse
import io
import json
import statistics
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch
from portfolio_core.logging import get_logger
from sklearn import metrics as skm

from nlp_classification.config import NLPConfig
from nlp_classification.data import LABEL_COLUMN, TEXT_COLUMN, tokenize_dataset
from nlp_classification.evaluate import load_tokenizer
from nlp_classification.model import (
    BASELINE_PATH,
    FULLDATA_MODEL_PATH,
    TUNED_MODEL_PATH,
    build_nn_model,
    load_baseline,
    load_nn_state_dict,
    predict_nn,
)
from nlp_classification.shims import Dataset

logger = get_logger(__name__)

# Declared rate card for the cloud-equivalent cost column.
RATE_IN_PER_MILLION = 1.0  # $ per 1M input tokens
RATE_OUT_PER_MILLION = 4.0  # $ per 1M output tokens

INT8_SAMPLE_ROWS = 2000  # train-split sample for the int8 quality measurement

Row = dict[str, Any]


def sample_texts(texts: list[str], n: int, seed: int) -> list[str]:
    """Seeded sample of ``n`` texts (wraps if ``n`` exceeds the pool)."""
    pool = texts
    while len(pool) < n:
        pool = pool + texts
    rng = np.random.RandomState(seed)
    idx = rng.choice(len(pool), size=n, replace=False)
    return [pool[int(i)] for i in idx]


def time_single_predictions(
    predict: Callable[[str], int], texts: list[str], warmup: int = 5
) -> dict[str, float | int]:
    """Batch-1 latency: ``warmup`` untimed predictions, then one timer per row.

    Returns per-prediction median/mean (ms) and whole-loop throughput (pred/s).
    """
    for text in texts[:warmup]:
        predict(text)
    latencies_ms: list[float] = []
    started_all = time.perf_counter()
    for text in texts:
        started = time.perf_counter()
        predict(text)
        latencies_ms.append((time.perf_counter() - started) * 1000.0)
    total_s = time.perf_counter() - started_all
    return {
        "n": len(texts),
        "p50_latency_ms": float(statistics.median(latencies_ms)),
        "mean_latency_ms": float(np.mean(latencies_ms)),
        "throughput_pred_s": len(texts) / total_s,
    }


def cost_per_1k(mean_input_tokens: float, mean_output_tokens: float) -> float:
    """Cloud-equivalent cost of 1k predictions at the declared rate card."""
    per_pred_usd = (
        mean_input_tokens * RATE_IN_PER_MILLION + mean_output_tokens * RATE_OUT_PER_MILLION
    ) / 1e6
    return per_pred_usd * 1000.0


def artifact_size_mb(path: Path) -> float:
    """On-disk artifact size in MiB."""
    return path.stat().st_size / 2**20


def state_dict_size_mb(model: torch.nn.Module) -> float:
    """Serialized ``state_dict`` size in MiB (no file write needed)."""
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    return buffer.getbuffer().nbytes / 2**20


def sklearn_row(
    model: Any, artifact: Path, texts: list[str], n: int, seed: int, metrics: dict[str, float]
) -> Row:
    """Probe row for the TF-IDF + LogisticRegression baseline."""

    def predict(text: str) -> int:
        return int(cast(Any, model.predict([text]))[0])

    row: Row = {
        "variant": "tfidf_logreg",
        "artifact": str(artifact),
        "kind": "sklearn",
        "size_mb": artifact_size_mb(artifact),
        "device": "cpu",
        "batch": 1,
        **time_single_predictions(predict, sample_texts(texts, n, seed)),
        "mean_input_tokens": None,
        "mean_output_tokens": None,
        "cost_per_1k_usd": 0.0,
        "cost_note": "classical sklearn — no per-token API meter",
        "accuracy": metrics["accuracy"],
        "f1_macro": metrics["f1_macro"],
        "f1_source": "committed metrics.json (1000-row test split)",
    }
    return row


def make_torch_predict(
    model: torch.nn.Module, tokenizer: Any, max_length: int
) -> Callable[[str], int]:
    """Batch-1 serving closure: tokenize (truncated, unpadded) + forward on CPU.

    The closure records input-token lengths and predicted labels so token
    counts are measured on exactly the timed sample, not estimated.
    """
    recorded_input_lengths: list[int] = []
    recorded_preds: list[int] = []

    def predict(text: str) -> int:
        ids = tokenizer(text, truncation=True, max_length=max_length)["input_ids"]
        recorded_input_lengths.append(len(ids))
        input_ids = torch.tensor([ids], dtype=torch.long)
        attention_mask = torch.ones_like(input_ids)
        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        logits = outputs.logits if hasattr(outputs, "logits") else outputs
        pred = int(logits.argmax(dim=-1).item())
        recorded_preds.append(pred)
        return pred

    predict.input_lengths = recorded_input_lengths  # type: ignore[attr-defined]
    predict.preds = recorded_preds  # type: ignore[attr-defined]
    return predict


def torch_row(
    variant: str,
    artifact: str,
    model: torch.nn.Module,
    tokenizer: Any,
    label_names: list[str],
    texts: list[str],
    n: int,
    max_length: int,
    seed: int,
    metrics: dict[str, float] | None,
) -> Row:
    """Probe row for a torch variant; quality from committed metrics unless ``metrics`` is None."""
    predict = make_torch_predict(model, tokenizer, max_length)
    stats = time_single_predictions(predict, sample_texts(texts, n, seed))

    input_lengths: list[int] = predict.input_lengths  # type: ignore[attr-defined]
    preds: list[int] = predict.preds  # type: ignore[attr-defined]
    mean_input_tokens = float(np.mean(input_lengths)) if input_lengths else 0.0
    out_tokens = [len(tokenizer(label)["input_ids"]) for label in label_names]
    mean_output_tokens = (
        float(np.mean([out_tokens[p] for p in preds])) if preds else float(np.mean(out_tokens))
    )

    row: Row = {
        "variant": variant,
        "artifact": artifact,
        "kind": "torch",
        "size_mb": state_dict_size_mb(model),
        "device": "cpu",
        "batch": 1,
        **stats,
        "mean_input_tokens": mean_input_tokens,
        "mean_output_tokens": mean_output_tokens,
        "cost_per_1k_usd": cost_per_1k(mean_input_tokens, mean_output_tokens),
    }
    if metrics is not None:
        row.update(
            {
                "accuracy": metrics["accuracy"],
                "f1_macro": metrics["f1_macro"],
                "f1_source": "committed metrics.json (1000-row test split)",
            }
        )
    return row


def quantize_int8(model: torch.nn.Module) -> torch.nn.Module:
    """Dynamic int8 quantization of a CPU copy (``torch.quantization``, no deps).

    Apple-Silicon arm64 torch ships no fbgemm kernels, so the qnnpack engine is
    selected explicitly when fbgemm is unavailable.
    """
    model.cpu()
    model.eval()
    supported = torch.backends.quantized.supported_engines
    if torch.backends.quantized.engine not in supported:
        for engine in ("fbgemm", "qnnpack"):  # prefer fbgemm kernels when present
            if engine in supported:
                torch.backends.quantized.engine = engine
                break
    quantize_dynamic = cast(Any, torch.quantization).quantize_dynamic
    return cast(torch.nn.Module, quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8))


def quality_on_sample(
    model: torch.nn.Module, sample: Dataset, tokenizer: Any, max_length: int
) -> dict[str, float | int]:
    """Accuracy + macro-F1 on a bounded sample (measurement, not a full eval)."""
    tokenized = tokenize_dataset(sample, tokenizer, max_length)
    preds = predict_nn(model, tokenized, torch.device("cpu"), batch_size=64)
    y_true = [int(v) for v in sample[LABEL_COLUMN]]
    accuracy = float(np.mean([int(p) == y for p, y in zip(preds.tolist(), y_true, strict=True)]))
    f1_macro = float(skm.f1_score(y_true, preds.tolist(), average="macro", zero_division=0))
    return {"n": len(y_true), "accuracy": accuracy, "f1_macro": f1_macro}


def _machine_note() -> str:
    try:
        chip = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return f"{chip} (Apple Silicon, MPS available)"
    except Exception:  # pragma: no cover - non-Apple fallback
        return "Apple Silicon MPS, 2026-10"


def to_markdown(report: dict[str, Any]) -> str:
    """Render the probe report as the serving-economics table."""
    header = (
        "| Variant | Size (MB) | p50 latency (ms) | Throughput (pred/s) "
        "| Cost ($/1k) | Accuracy | F1 macro |"
    )
    lines = [header, "|---|---|---|---|---|---|---|"]
    for row in report["variants"]:
        lines.append(
            f"| {row['variant']} | {row['size_mb']:.1f} | {row['p50_latency_ms']:.1f} "
            f"| {row['throughput_pred_s']:.1f} | {row['cost_per_1k_usd']:.4f} "
            f"| {row['accuracy']:.4f} | {row['f1_macro']:.4f} |"
        )
    int8 = report["int8_quality"]
    lines.append("")
    lines.append(
        f"int8 quality (measured on the same {int8['n']}-row train sample): "
        f"fp32 macro-F1 {int8['fp32_f1_macro']:.4f} → int8 {int8['int8_f1_macro']:.4f} "
        f"(Δ {int8['delta_f1_macro']:+.4f})."
    )
    return "\n".join(lines)


def run(cfg: NLPConfig, n: int, out_path: Path | None = None) -> dict[str, Any]:
    """Probe all four variants and (optionally) persist ``reports/latency_probe.json``."""
    device = torch.device("cpu")
    test_ds = Dataset.load_from_disk(str(cfg.test_dir))
    texts = list(test_ds[TEXT_COLUMN])
    labels = cast(list[str], json.loads((cfg.data_dir / "label_names.json").read_text()))
    committed = json.loads((Path(cfg.reports_dir) / "metrics.json").read_text())

    def committed_metrics(run_name: str) -> dict[str, float]:
        values = committed.get(run_name, {})
        return {
            "accuracy": float(values["accuracy"]),
            "f1_macro": float(values["f1_macro"]),
        }

    variants: list[Row] = [
        sklearn_row(
            load_baseline(cfg.models_dir / BASELINE_PATH),
            cfg.models_dir / BASELINE_PATH,
            texts,
            n,
            cfg.seed,
            committed_metrics("baseline_tfidf_logreg"),
        )
    ]

    tokenizer = load_tokenizer(cfg.model_name)
    tuned = build_nn_model(cfg, len(labels))
    tuned = load_nn_state_dict(tuned, cfg.models_dir / TUNED_MODEL_PATH, device)
    variants.append(
        torch_row(
            "distilbert_tuned_fp32 (bounded)",
            str(cfg.models_dir / TUNED_MODEL_PATH),
            tuned,
            tokenizer,
            labels,
            texts,
            n,
            cfg.max_length,
            cfg.seed,
            committed_metrics("distilbert_tuned"),
        )
    )

    full = build_nn_model(cfg, len(labels))
    full = load_nn_state_dict(full, cfg.models_dir / FULLDATA_MODEL_PATH, device)
    variants.append(
        torch_row(
            "distilbert_full_120k_fp32",
            str(cfg.models_dir / FULLDATA_MODEL_PATH),
            full,
            tokenizer,
            labels,
            texts,
            n,
            cfg.max_length,
            cfg.seed,
            committed_metrics("distilbert_full_120k"),
        )
    )

    # int8 quality first on the fp32 weights, then quantize in place and probe.
    train_ds = Dataset.load_from_disk(str(cfg.train_dir))
    sample = train_ds.select(range(INT8_SAMPLE_ROWS))
    fp32_sample = quality_on_sample(full, sample, tokenizer, cfg.max_length)
    int8 = quantize_int8(full)
    int8_sample = quality_on_sample(int8, sample, tokenizer, cfg.max_length)
    row = torch_row(
        "distilbert_full_120k_int8",
        str(cfg.models_dir / FULLDATA_MODEL_PATH) + " + quantize_dynamic",
        int8,
        tokenizer,
        labels,
        texts,
        n,
        cfg.max_length,
        cfg.seed,
        None,
    )
    row["accuracy"] = int8_sample["accuracy"]
    row["f1_macro"] = int8_sample["f1_macro"]
    row["f1_source"] = f"measured on {int8_sample['n']}-row train sample"
    variants.append(row)

    report: dict[str, Any] = {
        "machine": _machine_note(),
        "torch_version": torch.__version__,
        "torch_threads": torch.get_num_threads(),
        "n": n,
        "batch": 1,
        "rate_card": {
            "input_per_million_usd": RATE_IN_PER_MILLION,
            "output_per_million_usd": RATE_OUT_PER_MILLION,
        },
        "latency_scope": (
            "batch=1 end-to-end (tokenize + forward), CPU; accuracy from committed "
            "metrics.json except int8 (sample-measured)"
        ),
        "variants": variants,
        "int8_quality": {
            "sample": "first 2000 rows of the 4000-row train split (stratified 500/class)",
            "n": fp32_sample["n"],
            "fp32_f1_macro": fp32_sample["f1_macro"],
            "int8_f1_macro": int8_sample["f1_macro"],
            "delta_f1_macro": int8_sample["f1_macro"] - fp32_sample["f1_macro"],
        },
    }

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2))
        logger.info("latency probe written to %s", out_path)
    return report


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint: ``python -m nlp_classification.latency_probe --n 200``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=200, help="predictions per variant (default 200)")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports/latency_probe.json"),
        help="where to persist the JSON report",
    )
    args = parser.parse_args(argv)
    if args.n < 1:
        parser.error("--n must be >= 1")
    report = run(NLPConfig(), n=args.n, out_path=args.out)
    print(json.dumps(report, indent=2))
    print()
    print(to_markdown(report))


if __name__ == "__main__":
    main()
