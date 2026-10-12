"""Two approaches on the same bounded subsample:

(a) sklearn baseline — TF-IDF (word 1-2 grams, 8000 features) + LogisticRegression.
(b) DistilBERT fine-tuned with a HAND-WRITTEN PyTorch loop: manual LR schedule
    (linear warmup + linear decay), per-epoch train/val macro-F1, early
    stopping with patience 1. No Trainer, no callbacks — the loop is the point.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

import joblib  # type: ignore[import-untyped]
import numpy as np
import torch
from datasets import Dataset  # type: ignore[import-untyped]
from portfolio_core.logging import get_logger
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from torch import nn
from torch.utils.data import DataLoader

from nlp_classification.config import NLPConfig
from nlp_classification.data import LABEL_COLUMN, TEXT_COLUMN

logger = get_logger(__name__)

BASELINE_PATH = "baseline.joblib"
NN_MODEL_PATH = "distilbert.pt"


# ---------------------------------------------------------------------------
# (a) sklearn baseline
# ---------------------------------------------------------------------------


def train_baseline(cfg: NLPConfig, train_ds: Dataset) -> Pipeline:
    """Fit TF-IDF + LogisticRegression on the *same* train subsample."""
    pipeline: Pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    max_features=cfg.tfidf_max_features,
                    lowercase=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(max_iter=1000, random_state=cfg.seed),
            ),
        ]
    )
    logger.info("fitting sklearn baseline on %d rows", len(train_ds))
    pipeline.fit(train_ds[TEXT_COLUMN], train_ds[LABEL_COLUMN])
    return pipeline


def save_baseline(model: Pipeline, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, p)
    return p


def load_baseline(path: str | Path) -> Pipeline:
    return joblib.load(Path(path))


def predict_baseline(model: Pipeline, texts: list[str]) -> np.ndarray:
    return np.asarray(model.predict(texts), dtype=int)


# ---------------------------------------------------------------------------
# naive reference baselines (no training — sanity floor for every real run)
# ---------------------------------------------------------------------------


def predict_majority(train_labels: list[int], n_rows: int) -> np.ndarray:
    """Predict the most frequent training class for every row."""
    if not train_labels:
        raise ValueError("train_labels must be non-empty")
    majority = max(set(train_labels), key=train_labels.count)
    return np.full(n_rows, majority, dtype=int)


def predict_random_uniform(n_rows: int, n_labels: int, seed: int) -> np.ndarray:
    """Seeded uniform-random class predictions (the chance floor)."""
    rng = np.random.RandomState(seed)
    return rng.randint(0, n_labels, size=n_rows)


# ---------------------------------------------------------------------------
# (b) hand-written fine-tuning loop
# ---------------------------------------------------------------------------


@dataclass
class EpochRecord:
    """One epoch of the hand-written loop: losses + validation macro-F1."""

    epoch: int
    train_loss: float
    val_loss: float
    val_f1_macro: float
    learning_rate: float


@dataclass
class TrainingHistory:
    """Full training history, serialized to reports/history.json."""

    epochs: list[EpochRecord] = field(default_factory=list)

    def best_epoch(self) -> EpochRecord:
        if not self.epochs:
            raise ValueError("history is empty")
        return max(self.epochs, key=lambda e: e.val_f1_macro)

    def to_json(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([asdict(e) for e in self.epochs], indent=2))
        return p

    @classmethod
    def from_json(cls, path: str | Path) -> "TrainingHistory":
        raw = json.loads(Path(path).read_text())
        return cls.from_records(raw)

    @classmethod
    def from_records(cls, records: list[dict[str, Any]]) -> "TrainingHistory":
        """Build a history from serialized epoch dicts."""
        return cls(epochs=[EpochRecord(**e) for e in records])


def lr_at_step(step: int, total_steps: int, warmup_steps: int, base_lr: float) -> float:
    """Linear warmup then linear decay to 0 — implemented by hand, no scheduler."""
    if warmup_steps > 0 and step < warmup_steps:
        return base_lr * (step + 1) / warmup_steps
    progress = (step + 1 - warmup_steps) / max(1, total_steps - warmup_steps)
    return base_lr * max(0.0, 1.0 - progress)


def _collate(batch: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
    """Stack numeric columns of dataset rows into long tensors.

    Non-numeric columns (``text``) are dropped — the loop only needs ids/mask/label.
    """
    return {
        key: torch.tensor([row[key] for row in batch], dtype=torch.long)
        for key in batch[0]
        if key != "text"
    }


def make_loaders(
    cfg: NLPConfig, train_ds: Dataset, val_ds: Dataset
) -> tuple[DataLoader[Dataset], DataLoader[Dataset]]:
    """Loaders with an explicit collate: tokenize_dataset() already padded rows."""
    generator = torch.Generator().manual_seed(cfg.seed)
    train_loader = DataLoader(
        train_ds,
        batch_size=cfg.batch_size,
        shuffle=True,
        generator=generator,
        collate_fn=_collate,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=cfg.batch_size,
        shuffle=False,
        collate_fn=_collate,
    )
    return train_loader, val_loader


@torch.no_grad()
def evaluate_epoch(
    model: nn.Module, loader: DataLoader[Dataset], device: torch.device
) -> tuple[float, float]:
    """Average loss and macro-F1 over a loader (used for validation each epoch)."""
    model.eval()
    losses: list[float] = []
    y_true: list[int] = []
    y_pred: list[int] = []
    for batch in loader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch[LABEL_COLUMN].to(device)
        outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
        losses.append(float(outputs.loss.item()))
        y_true.extend(int(v) for v in labels.tolist())
        y_pred.extend(int(v) for v in outputs.logits.argmax(dim=-1).tolist())
    n_labels = max(y_true) + 1 if y_true else 1
    f1 = _macro_f1(y_true, y_pred, n_labels)
    return float(np.mean(losses)) if losses else float("nan"), f1


def _macro_f1(y_true: list[int], y_pred: list[int], n_labels: int) -> float:
    """Dependency-free macro-F1 so the loop has no sklearn import at train time."""
    f1s: list[float] = []
    for cls in range(n_labels):
        tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == cls and p != cls)
        denom = 2 * tp + fp + fn
        f1s.append(2 * tp / denom if denom else 0.0)
    return float(np.mean(f1s))


def build_nn_model(cfg: NLPConfig, n_labels: int) -> nn.Module:
    """DistilBERT with a fresh classification head (transformers >= 5 API)."""
    from transformers import AutoModelForSequenceClassification

    return cast(
        nn.Module,
        AutoModelForSequenceClassification.from_pretrained(cfg.model_name, num_labels=n_labels),
    )


def train_nn(
    cfg: NLPConfig,
    train_ds: Dataset,
    val_ds: Dataset,
    n_labels: int,
    device: torch.device,
    model: nn.Module | None = None,
) -> tuple[nn.Module, TrainingHistory]:
    """Fine-tune with a hand-written loop: AdamW + manual warmup/decay, early stop.

    Returns the best-state model (restored after early stopping) and the logged
    history. ``model`` is injectable so tests can exercise the loop on a tiny
    random module without downloading any weights.
    """
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    if model is None:
        model = build_nn_model(cfg, n_labels)
    model.to(device)

    train_loader, val_loader = make_loaders(cfg, train_ds, val_ds)
    total_steps = cfg.epochs * len(train_loader)
    warmup_steps = int(cfg.warmup_ratio * total_steps)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay
    )
    loss_fn = nn.CrossEntropyLoss()

    history = TrainingHistory()
    best_f1 = -1.0
    best_state: dict[str, Any] | None = None
    patience_left = cfg.early_stop_patience
    global_step = 0

    for epoch in range(1, cfg.epochs + 1):
        model.train()
        batch_losses: list[float] = []
        for batch in train_loader:
            lr = lr_at_step(global_step, total_steps, warmup_steps, cfg.learning_rate)
            for group in optimizer.param_groups:
                group["lr"] = lr
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch[LABEL_COLUMN].to(device)

            optimizer.zero_grad()
            logits = model(input_ids=input_ids, attention_mask=attention_mask)
            loss = loss_fn(logits.logits if hasattr(logits, "logits") else logits, labels)
            loss.backward()
            optimizer.step()
            batch_losses.append(float(loss.item()))
            global_step += 1

        train_loss = float(np.mean(batch_losses))
        val_loss, val_f1 = evaluate_epoch(model, val_loader, device)
        record = EpochRecord(
            epoch=epoch,
            train_loss=train_loss,
            val_loss=val_loss,
            val_f1_macro=val_f1,
            learning_rate=lr,
        )
        history.epochs.append(record)
        logger.info(
            "epoch %d/%d train_loss=%.4f val_loss=%.4f val_f1=%.4f",
            epoch,
            cfg.epochs,
            train_loss,
            val_loss,
            val_f1,
        )

        if val_f1 > best_f1:
            best_f1 = val_f1
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience_left = cfg.early_stop_patience
        else:
            patience_left -= 1
            if patience_left == 0:
                logger.info("early stopping after epoch %d (best val_f1=%.4f)", epoch, best_f1)
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    return model, history


@torch.no_grad()
def predict_nn(
    model: nn.Module, dataset: Dataset, device: torch.device, batch_size: int
) -> np.ndarray:
    """Predict class indices for a tokenized dataset."""
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, collate_fn=_collate)
    model.eval()
    preds: list[int] = []
    for batch in loader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        logits = outputs.logits if hasattr(outputs, "logits") else outputs
        preds.extend(int(v) for v in logits.argmax(dim=-1).tolist())
    return np.asarray(preds, dtype=int)


def save_nn_state_dict(model: nn.Module, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), p)
    return p


def load_nn_state_dict(model: nn.Module, path: str | Path, device: torch.device) -> nn.Module:
    state = torch.load(Path(path), map_location=device, weights_only=True)
    model.load_state_dict(state)
    model.to(device)
    return model
