"""Tabular MLP in PyTorch with a hand-written training loop.

The repo's stack table claims hand-written PyTorch loops, so this class is the
deliverable even where trees win: cyclical-hour embedding + numeric trunk,
AdamW, dropout, weight decay, Huber loss (smooth MAE surrogate in
standardized-y space), early stopping on the validation window, per-epoch
train/validation loss curves, and a seeded, single-threaded, deterministic
fit. Input scaling and y standardization use train statistics only.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import torch
from torch import nn

from tabular_ml_lifecycle.config import LifecycleConfig

HOUR_CARDINALITY = 24


class RentalMLP(nn.Module):
    """Hour-embedding + numeric MLP trunk."""

    def __init__(
        self,
        n_numeric: int,
        embed_dim: int,
        hidden_dims: list[int],
        dropout: float,
    ) -> None:
        super().__init__()
        self.hour_embed = nn.Embedding(HOUR_CARDINALITY, embed_dim)
        layers: list[nn.Module] = []
        in_dim = embed_dim + n_numeric
        for width in hidden_dims:
            layers += [nn.Linear(in_dim, width), nn.ReLU(), nn.Dropout(dropout)]
            in_dim = width
        layers.append(nn.Linear(in_dim, 1))
        self.trunk = nn.Sequential(*layers)

    def forward(self, hour_idx: torch.Tensor, x_num: torch.Tensor) -> torch.Tensor:
        embedded = self.hour_embed(hour_idx)
        out: torch.Tensor = self.trunk(torch.cat([embedded, x_num], dim=1)).squeeze(-1)
        return out


@dataclass
class MLPHistory:
    """Per-epoch losses (the overfitting-control artifact) + fit outcome."""

    train_loss: list[float] = field(default_factory=list)
    val_loss: list[float] = field(default_factory=list)
    best_epoch: int = 0
    epochs_run: int = 0


@dataclass
class MLPAblationRow:
    """One ablation variant, each seeded and scored once per split."""

    variant: str
    dropout_on: bool
    weight_decay_on: bool
    early_stopping_on: bool
    val_mae: float
    test_mae: float
    epochs_run: int


def _huber(pred: torch.Tensor, target: torch.Tensor, delta: float) -> torch.Tensor:
    err = pred - target
    abs_err = err.abs()
    quadratic = torch.clamp(abs_err, max=delta)
    return torch.mean(0.5 * quadratic**2 + delta * (abs_err - quadratic))


class MLPRegressor:
    """sklearn-style wrapper: ``fit`` runs the hand-written loop, ``predict``
    inverts the y standardization. Deterministic for a fixed seed."""

    def __init__(self, cfg: LifecycleConfig, seed: int) -> None:
        self.cfg = cfg
        self.seed = seed
        self.model: RentalMLP | None = None
        self.history = MLPHistory()
        self.numeric_cols: list[str] = []
        self.x_mean: np.ndarray | None = None
        self.x_std: np.ndarray | None = None
        self.y_mean = 0.0
        self.y_std = 1.0

    def _arrays(self, X: pd.DataFrame) -> tuple[torch.Tensor, torch.Tensor]:
        if self.x_mean is None or self.x_std is None:
            raise RuntimeError("MLPRegressor is not fitted yet")
        hour = torch.tensor(X["hour"].to_numpy(dtype=np.int64), dtype=torch.long)
        x_num = torch.tensor(
            (X[self.numeric_cols].to_numpy(dtype=np.float64) - self.x_mean) / self.x_std,
            dtype=torch.float32,
        )
        return hour, x_num

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        numeric_cols: list[str],
        *,
        dropout: float | None = None,
        weight_decay: float | None = None,
        early_stopping: bool = True,
    ) -> "MLPRegressor":
        cfg = self.cfg
        mlp = cfg.mlp
        torch.manual_seed(self.seed)
        torch.set_num_threads(1)
        self.numeric_cols = list(numeric_cols)
        self.x_mean = X_train[self.numeric_cols].to_numpy(dtype=np.float64).mean(axis=0)
        self.x_std = X_train[self.numeric_cols].to_numpy(dtype=np.float64).std(axis=0) + 1e-8
        self.y_mean = float(y_train.mean())
        self.y_std = float(y_train.std()) + 1e-8

        self.model = RentalMLP(
            n_numeric=len(self.numeric_cols),
            embed_dim=mlp.embed_dim,
            hidden_dims=list(mlp.hidden_dims),
            dropout=mlp.dropout if dropout is None else dropout,
        )
        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=mlp.learning_rate,
            weight_decay=mlp.weight_decay if weight_decay is None else weight_decay,
        )
        hour_tr, x_tr = self._arrays(X_train)
        hour_va, x_va = self._arrays(X_val)
        y_tr = torch.tensor(
            ((y_train.to_numpy(dtype=np.float64) - self.y_mean) / self.y_std),
            dtype=torch.float32,
        )
        y_va_np = y_val.to_numpy(dtype=np.float64)

        generator = torch.Generator().manual_seed(self.seed)
        n = x_tr.shape[0]
        best_val = float("inf")
        best_state: dict[str, torch.Tensor] | None = None
        patience_left = mlp.patience

        # Hand-written loop: shuffle, mini-batches, forward/backward/step, then a
        # full-pass train loss and a validation MAE check for early stopping.
        for epoch in range(mlp.max_epochs):
            self.model.train()
            order = torch.randperm(n, generator=generator)
            for start in range(0, n, mlp.batch_size):
                idx = order[start : start + mlp.batch_size]
                optimizer.zero_grad()
                loss: torch.Tensor = _huber(
                    self.model(hour_tr[idx], x_tr[idx]), y_tr[idx], mlp.huber_delta
                )
                loss.backward()  # type: ignore[no-untyped-call]  # torch stubs: backward untyped
                optimizer.step()
            self.model.eval()
            with torch.no_grad():
                train_pred = self._predict_scaled(hour_tr, x_tr)
                train_mae = float(np.mean(np.abs(y_tr.numpy() - train_pred.numpy())))
                val_pred = self._predict_scaled(hour_va, x_va).numpy() * self.y_std + self.y_mean
                val_mae = float(np.mean(np.abs(y_va_np - val_pred)))
            self.history.train_loss.append(train_mae * self.y_std)
            self.history.val_loss.append(val_mae)
            self.history.epochs_run = epoch + 1
            if val_mae < best_val:
                best_val = val_mae
                self.history.best_epoch = epoch + 1
                best_state = {k: v.clone() for k, v in self.model.state_dict().items()}
                patience_left = mlp.patience
            elif early_stopping:
                patience_left -= 1
                if patience_left <= 0:
                    break
        if best_state is not None and early_stopping:
            self.model.load_state_dict(best_state)
        return self

    def _predict_scaled(self, hour: torch.Tensor, x_num: torch.Tensor) -> torch.Tensor:
        if self.model is None:
            raise RuntimeError("MLPRegressor is not fitted yet")
        out: torch.Tensor = self.model(hour, x_num)
        return out

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.model is None or self.x_mean is None or self.x_std is None:
            raise RuntimeError("MLPRegressor is not fitted yet")
        torch.set_num_threads(1)  # multi-thread predict deadlocks on the shared libomp
        self.model.eval()
        hour, x_num = self._arrays(X)
        with torch.no_grad():
            scaled = self._predict_scaled(hour, x_num).numpy()
        return scaled * self.y_std + self.y_mean

    def ablation(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        numeric_cols: list[str],
    ) -> list[MLPAblationRow]:
        """2x2x2 overfitting-control grid (dropout / weight decay / early stop).

        Every variant is seeded and scored once per split; all selection
        decisions use validation — see the limits in the evaluation metadata.
        """
        cfg = self.cfg
        rows: list[MLPAblationRow] = []
        for dropout_on in (True, False):
            for wd_on in (True, False):
                for es_on in (True, False):
                    candidate = MLPRegressor(cfg, self.seed)
                    candidate.fit(
                        X_train,
                        y_train,
                        X_val,
                        y_val,
                        numeric_cols,
                        dropout=cfg.mlp.dropout if dropout_on else 0.0,
                        weight_decay=cfg.mlp.weight_decay if wd_on else 0.0,
                        early_stopping=es_on,
                    )
                    val_pred = candidate.predict(X_val)
                    test_pred = candidate.predict(X_test)
                    variant = (
                        f"dropout={'on' if dropout_on else 'off'}|"
                        f"wd={'on' if wd_on else 'off'}|"
                        f"es={'on' if es_on else 'off'}"
                    )
                    rows.append(
                        MLPAblationRow(
                            variant=variant,
                            dropout_on=dropout_on,
                            weight_decay_on=wd_on,
                            early_stopping_on=es_on,
                            val_mae=float(np.mean(np.abs(y_val.to_numpy() - val_pred))),
                            test_mae=float(np.mean(np.abs(y_test.to_numpy() - test_pred))),
                            epochs_run=candidate.history.epochs_run,
                        )
                    )
        return rows
