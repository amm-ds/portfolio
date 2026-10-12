"""Models: GBM baseline, p90 quantile GBM, and a hand-rolled PyTorch MLP.

- ``train_baselines``: sklearn ``HistGradientBoostingRegressor`` (mean) and a
  quantile (p90) twin for uncertainty bands. NaN-tolerant, so weather gaps
  need no imputation. Trained on at most ``cfg.max_train_rows`` most-recent
  train rows (bounded slice, documented in DESIGN.md).
- ``TemporalNet``: 64-32 MLP with a fully hand-written training loop
  (DataLoader → Adam → MSE → grad clipping → early stop on val MAE). The
  validation slice comes from ``portfolio_core.timecv.TimeSeriesCV`` with a
  24-step (hour) embargo, so early stopping never peeks at the future.
- Predictions for every model are persisted to one parquet so ``evaluate``
  (and the DVC ``dashboard`` stage) is a pure read.
"""

import json
from pathlib import Path

import numpy as np
import polars as pl
import torch
from portfolio_core.logging import get_logger
from portfolio_core.timecv import TimeSeriesCV
from sklearn.ensemble import HistGradientBoostingRegressor

from mobility.config import MobilityConfig, get_config
from mobility.features import FEATURE_COLUMNS

logger = get_logger(__name__)

PREDICTIONS_PATH = "reports/models/predictions.parquet"


def _xy(df: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    return (
        df.select(FEATURE_COLUMNS).to_numpy().astype(np.float32),
        df["target"].to_numpy().astype(np.float32),
    )


def _bounded_train(train: pl.DataFrame, cfg: MobilityConfig) -> pl.DataFrame:
    """Most-recent ``max_train_rows`` of the train slice (temporal, not random)."""
    if train.height > cfg.max_train_rows:
        logger.info(
            "capping train rows %d -> %d (most recent slice)", train.height, cfg.max_train_rows
        )
        return train.tail(cfg.max_train_rows)
    return train


def train_baselines(cfg: MobilityConfig | None = None) -> pl.DataFrame:
    """Fit GBM mean + p90 quantile on the train window; persist predictions."""
    cfg = cfg or get_config()
    train = _bounded_train(pl.read_parquet(cfg.features_dir / "train.parquet"), cfg)
    test = pl.read_parquet(cfg.features_dir / "test.parquet")
    X_train, y_train = _xy(train)
    X_test, _ = _xy(test)

    gbm = HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=cfg.gbm.max_iter,
        learning_rate=cfg.gbm.learning_rate,
        max_leaf_nodes=cfg.gbm.max_leaf_nodes,
        min_samples_leaf=cfg.gbm.min_samples_leaf,
        l2_regularization=cfg.gbm.l2_regularization,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=20,
        random_state=cfg.seed,
    )
    logger.info("training GBM mean on %d rows x %d cols", *X_train.shape)
    gbm.fit(X_train, y_train)
    logger.info("GBM mean: %d iterations", gbm.n_iter_)

    p90 = HistGradientBoostingRegressor(
        loss="quantile",
        quantile=0.9,
        max_iter=cfg.gbm.quantile_max_iter,
        learning_rate=cfg.gbm.learning_rate,
        max_leaf_nodes=cfg.gbm.max_leaf_nodes,
        min_samples_leaf=cfg.gbm.min_samples_leaf,
        l2_regularization=cfg.gbm.l2_regularization,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=20,
        random_state=cfg.seed,
    )
    logger.info("training GBM p90 quantile")
    p90.fit(X_train, y_train)

    preds = test.select(
        ["zone_id", "borough", "ts", pl.col("target").alias("y_true"), pl.col("lag_24")]
    ).with_columns(
        y_gbm=gbm.predict(X_test),
        y_p90=p90.predict(X_test),
        y_naive=pl.col("lag_24"),
    )
    _persist_predictions(cfg, preds, _baseline_predictions_file(cfg))
    return preds


class TemporalNet(torch.nn.Module):
    """Small MLP (n_feat → hidden → second_hidden → 1) for demand nowcasting."""

    def __init__(self, n_features: int, hidden: int, second_hidden: int) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(n_features, hidden),
            torch.nn.GELU(),
            torch.nn.Linear(hidden, second_hidden),
            torch.nn.GELU(),
            torch.nn.Linear(second_hidden, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out: torch.Tensor = self.net(x)
        return out.squeeze(-1)


def _temporal_val_split(n: int, gap: int) -> tuple[np.ndarray, np.ndarray]:
    """Last expanding-window fold of ``TimeSeriesCV`` (embargoed by ``gap``).

    n_splits=4 puts the final validation block at ~20% of the window with a
    24-step embargo between fit and validation — early stopping never sees
    the future of the validation rows.
    """
    folds = list(TimeSeriesCV(n_splits=4, gap=gap).split(n))
    last = folds[-1]
    return last.train_idx, last.val_idx


def train_nn(cfg: MobilityConfig | None = None) -> pl.DataFrame:
    """Hand-written training loop; returns the full predictions frame."""
    cfg = cfg or get_config()
    train = _bounded_train(pl.read_parquet(cfg.features_dir / "train.parquet"), cfg)
    test = pl.read_parquet(cfg.features_dir / "test.parquet")
    X_train, y_train = _xy(train)
    X_test, _ = _xy(test)

    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)

    # Standardise features on the train slice only (no test leakage). The
    # target is trained in log1p space — demand is multiplicative (peaks are
    # proportionally larger), so a Gaussian loss on raw counts over-penalises
    # busy zones and under-trains the tail. Predictions are expm1-back-transformed.
    mu, sigma = X_train.mean(axis=0), X_train.std(axis=0) + 1e-6
    y_log = np.log1p(y_train)
    y_mu, y_sigma = float(y_log.mean()), float(y_log.std() + 1e-6)
    Xs = (X_train - mu) / sigma
    ys = (y_log - y_mu) / y_sigma

    fit_idx, val_idx = _temporal_val_split(len(ys), gap=24)
    logger.info(
        "TemporalNet: %d fit rows, %d val rows (24h embargo), %d test rows",
        len(fit_idx),
        len(val_idx),
        len(X_test),
    )

    net = TemporalNet(Xs.shape[1], cfg.nn.hidden_size, cfg.nn.second_hidden_size)
    opt = torch.optim.Adam(net.parameters(), lr=cfg.nn.lr, weight_decay=cfg.nn.weight_decay)
    loss_fn = torch.nn.MSELoss()
    fit_ds = torch.utils.data.TensorDataset(torch.tensor(Xs[fit_idx]), torch.tensor(ys[fit_idx]))
    gen = torch.Generator().manual_seed(cfg.seed)
    loader = torch.utils.data.DataLoader(
        fit_ds, batch_size=cfg.nn.batch_size, shuffle=True, generator=gen
    )
    x_val = torch.tensor(Xs[val_idx])
    y_val = torch.tensor(ys[val_idx])

    best_val = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    patience_left = cfg.nn.early_stop_patience
    for epoch in range(cfg.nn.epochs):
        net.train()
        for xb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(net(xb), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), cfg.nn.grad_clip)
            opt.step()
        net.eval()
        with torch.no_grad():
            val_mae = float((net(x_val) - y_val).abs().mean()) * y_sigma
        logger.info("epoch %d/%d val MAE %.4f", epoch + 1, cfg.nn.epochs, val_mae)
        if val_mae < best_val:
            best_val = val_mae
            best_state = {k: v.clone() for k, v in net.state_dict().items()}
            patience_left = cfg.nn.early_stop_patience
        else:
            patience_left -= 1
            if patience_left <= 0:
                logger.info("early stop at epoch %d", epoch + 1)
                break
    assert best_state is not None
    net.load_state_dict(best_state)

    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    torch.save(net.state_dict(), cfg.models_dir / "temporal_net.pt")
    (cfg.models_dir / "temporal_net_norm.json").write_text(
        json.dumps(
            {
                "feature_mu": mu.tolist(),
                "feature_sigma": sigma.tolist(),
                "y_mu": y_mu,
                "y_sigma": y_sigma,
            }
        )
    )

    net.eval()
    with torch.no_grad():
        y_log_hat = net(torch.tensor((X_test - mu) / sigma)).numpy() * y_sigma + y_mu
    y_nn = np.clip(np.expm1(y_log_hat), 0.0, None)

    preds = _read_parquet_if_exists(_baseline_predictions_file(cfg))
    if preds is None:
        preds = test.select(
            ["zone_id", "borough", "ts", pl.col("target").alias("y_true"), pl.col("lag_24")]
        )
    preds = preds.with_columns(y_nn=y_nn)
    _persist_predictions(cfg, preds, _predictions_file(cfg))
    logger.info("TemporalNet best val MAE %.4f (standardised-scale MAE x y_sigma)", best_val)
    return preds


def _predictions_file(cfg: MobilityConfig) -> Path:
    return cfg.reports_dir / "models" / "predictions.parquet"


def _baseline_predictions_file(cfg: MobilityConfig) -> Path:
    return cfg.reports_dir / "models" / "predictions_baseline.parquet"


def _persist_predictions(cfg: MobilityConfig, preds: pl.DataFrame, path: Path) -> None:
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    preds.write_parquet(path, compression="zstd")


def _read_parquet_if_exists(path: Path) -> pl.DataFrame | None:
    return pl.read_parquet(path) if path.exists() else None


def _read_predictions(cfg: MobilityConfig) -> pl.DataFrame | None:
    """Read the final (all-models) predictions, e.g. for ad-hoc inspection."""
    return _read_parquet_if_exists(_predictions_file(cfg))
