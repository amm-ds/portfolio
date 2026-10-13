"""Post-hoc calibration of the selected encoder via temperature scaling.

A single temperature T > 0 is fitted on the validation split by minimizing
NLL of the val logits scaled by 1/T; test predictions are then re-softmaxed.
Expected Calibration Error (ECE, equal-width confidence bins) is reported
before and after — the verdict on whether calibration matters for this model
goes into the story, the numbers go into ``reports/metrics.json`` under
``_meta.calibration``.
"""

import numpy as np
import torch
from datasets import Dataset  # type: ignore[import-untyped]
from portfolio_core.logging import get_logger
from torch import nn
from torch.utils.data import DataLoader

from nlp_classification.model import _collate, predict_proba_nn

logger = get_logger(__name__)


def collect_logits(
    model: nn.Module, dataset: Dataset, device: torch.device, batch_size: int
) -> tuple[torch.Tensor, torch.Tensor]:
    """Stacked logits and labels for a tokenized dataset (no softmax)."""
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, collate_fn=_collate)
    model.eval()
    logits_all: list[torch.Tensor] = []
    labels_all: list[torch.Tensor] = []
    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits if hasattr(outputs, "logits") else outputs
            logits_all.append(logits.cpu())
            labels_all.append(batch["label"].cpu())
    return torch.cat(logits_all), torch.cat(labels_all)


def fit_temperature(
    model: nn.Module, val_ds: Dataset, device: torch.device, batch_size: int, max_iter: int = 100
) -> float:
    """Fit T by LBFGS on validation NLL of logits / T. Returns T (>= 1e-2)."""
    logits, labels = collect_logits(model, val_ds, device, batch_size)
    temperature = nn.Parameter(torch.ones(1))
    optimizer = torch.optim.LBFGS([temperature], max_iter=max_iter)

    def closure() -> torch.Tensor:
        optimizer.zero_grad()
        loss = nn.functional.cross_entropy(logits / temperature.clamp(min=1e-2), labels)
        loss.backward()  # type: ignore[no-untyped-call]
        return loss

    optimizer.step(closure)  # type: ignore[no-untyped-call]
    fitted = float(temperature.clamp(min=1e-2).item())
    nll = float(nn.functional.cross_entropy(logits / fitted, labels).item())
    logger.info("temperature scaling: T=%.4f (val NLL=%.4f)", fitted, nll)
    return fitted


def expected_calibration_error(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
    """ECE over equal-width confidence bins: sum |acc - conf| * bin_weight."""
    if len(probs) == 0:
        raise ValueError("probs must be non-empty")
    confidences = probs.max(axis=1)
    predictions = probs.argmax(axis=1)
    ece = 0.0
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        mask = (confidences > lo) & (confidences <= hi) if b > 0 else confidences <= hi
        if not mask.any():
            continue
        acc = float((predictions[mask] == labels[mask]).mean())
        conf = float(confidences[mask].mean())
        ece += (mask.mean()) * abs(acc - conf)
    return float(ece)


def calibration_report(
    model: nn.Module,
    val_ds: Dataset,
    test_ds: Dataset,
    device: torch.device,
    batch_size: int,
    n_bins: int = 10,
) -> dict[str, float]:
    """Fit T on val, then ECE before/after on test. Returns the full verdict."""
    temperature = fit_temperature(model, val_ds, device, batch_size)
    probs_raw = predict_proba_nn(model, test_ds, device, batch_size)
    logits_test, labels_test = collect_logits(model, test_ds, device, batch_size)
    probs_cal = (
        torch.softmax(logits_test / temperature, dim=-1).cpu().numpy()
        if len(logits_test)
        else probs_raw
    )
    y_test = labels_test.numpy()
    ece_raw = expected_calibration_error(probs_raw, y_test, n_bins)
    ece_cal = expected_calibration_error(probs_cal, y_test, n_bins)
    logger.info("ECE: raw=%.4f calibrated=%.4f (delta=%.4f)", ece_raw, ece_cal, ece_raw - ece_cal)
    return {
        "temperature": temperature,
        "ece_raw": ece_raw,
        "ece_calibrated": ece_cal,
        "ece_delta": ece_raw - ece_cal,
    }
