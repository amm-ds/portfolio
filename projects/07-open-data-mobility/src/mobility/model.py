"""Models: GBM baselines (+ tuned variants), p90 quantile GBMs, hand-rolled MLP.

- ``train_baselines``: sklearn ``HistGradientBoostingRegressor`` mean + p90
  quantile (the wave-1 defaults, kept as ``gbm_mean``), plus — when an HPO
  result exists — the tuned ``gbm_tuned`` mean and its p90 twin. Fitted
  models are persisted (joblib) so ``evaluate`` can score permutation
  importance without retraining.
- ``train_nn``: ``TemporalNet`` (64-32 MLP) with a fully hand-written loop,
  in both the default (``temporal_net``) and HPO-tuned configuration. The
  validation slice comes from ``portfolio_core.timecv.TimeSeriesCV`` with a
  24-step (hour) embargo.
- Predictions for every model land in one parquet so ``evaluate`` (and the
  DVC ``dashboard`` stage) is a pure read.
"""

import json
from pathlib import Path
from typing import Any, NamedTuple

import joblib
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


def _make_gbm(
    params: dict[str, Any], *, seed: int, quantile: float | None = None
) -> HistGradientBoostingRegressor:
    """GBM from a plain param dict (HPO output); quantile=None → squared error."""
    max_iter = (
        int(params.get("quantile_max_iter", 200))
        if quantile is not None
        else int(params["max_iter"])
    )
    return HistGradientBoostingRegressor(
        loss="quantile" if quantile is not None else "squared_error",
        quantile=quantile,
        max_iter=max_iter,
        learning_rate=float(params["learning_rate"]),
        max_leaf_nodes=int(params["max_leaf_nodes"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        l2_regularization=float(params["l2_regularization"]),
        max_features=float(params.get("max_features", 1.0)),
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=20,
        random_state=seed,
    )


def hpo_result(cfg: MobilityConfig, kind: str) -> dict[str, Any] | None:
    """Best HPO params for ``kind`` ∈ {gbm, nn}; None when tuning has not run."""
    path = cfg.models_dir / f"hpo_{kind}.json"
    if not path.exists():
        return None
    result: dict[str, Any] = json.loads(path.read_text())
    return result


def train_baselines(cfg: MobilityConfig | None = None) -> pl.DataFrame:
    """Fit untuned GBM pair; add tuned twins when HPO results exist."""
    cfg = cfg or get_config()
    train = _bounded_train(pl.read_parquet(cfg.features_dir / "train.parquet"), cfg)
    test = pl.read_parquet(cfg.features_dir / "test.parquet")
    X_train, y_train = _xy(train)
    X_test, _ = _xy(test)
    cfg.models_dir.mkdir(parents=True, exist_ok=True)

    default = cfg.gbm.model_dump()
    logger.info("training GBM mean on %d rows x %d cols", *X_train.shape)
    gbm = _make_gbm(default, seed=cfg.seed)
    gbm.fit(X_train, y_train)
    logger.info("GBM mean: %d iterations", gbm.n_iter_)

    p90 = _make_gbm(default, seed=cfg.seed, quantile=0.9)
    logger.info("training GBM p90 quantile")
    p90.fit(X_train, y_train)

    preds = test.select(
        ["zone_id", "borough", "ts", pl.col("target").alias("y_true"), pl.col("lag_24")]
    ).with_columns(
        y_gbm=gbm.predict(X_test),
        y_p90=p90.predict(X_test),
        y_naive=pl.col("lag_24"),
    )
    joblib.dump(gbm, cfg.models_dir / "gbm_mean.joblib")
    joblib.dump(p90, cfg.models_dir / "gbm_p90.joblib")

    tuned = hpo_result(cfg, "gbm")
    if tuned is not None:
        logger.info("training tuned GBM pair with best HPO params: %s", tuned["best_params"])
        gbm_t = _make_gbm(tuned["best_params"], seed=cfg.seed)
        gbm_t.fit(X_train, y_train)
        p90_t = _make_gbm(tuned["best_params"], seed=cfg.seed, quantile=0.9)
        p90_t.fit(X_train, y_train)
        preds = preds.with_columns(
            y_gbm_tuned=gbm_t.predict(X_test),
            y_p90_tuned=p90_t.predict(X_test),
        )
        joblib.dump(gbm_t, cfg.models_dir / "gbm_tuned.joblib")
        joblib.dump(p90_t, cfg.models_dir / "gbm_p90_tuned.joblib")
    else:
        logger.info("no HPO result found — skipping gbm_tuned (run `mobility tune`)")

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


def _fit_net(
    Xs: np.ndarray,
    ys: np.ndarray,
    fit_idx: np.ndarray,
    val_idx: np.ndarray,
    *,
    hidden: int,
    second_hidden: int,
    epochs: int,
    batch_size: int,
    lr: float,
    weight_decay: float,
    grad_clip: float,
    patience: int,
    seed: int,
    y_sigma: float,
) -> tuple[float, dict[str, torch.Tensor]]:
    """The hand-written loop: DataLoader → Adam → MSE → clip → early stop.

    Returns (best raw-scale val MAE, best state_dict). Kept free of config
    objects so the HPO study can drive it with trial parameters.
    """
    torch.manual_seed(seed)
    net = TemporalNet(Xs.shape[1], hidden, second_hidden)
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=weight_decay)
    loss_fn = torch.nn.MSELoss()
    fit_ds = torch.utils.data.TensorDataset(torch.tensor(Xs[fit_idx]), torch.tensor(ys[fit_idx]))
    gen = torch.Generator().manual_seed(seed)
    loader = torch.utils.data.DataLoader(fit_ds, batch_size=batch_size, shuffle=True, generator=gen)
    x_val = torch.tensor(Xs[val_idx])
    y_val = torch.tensor(ys[val_idx])

    best_val = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    patience_left = patience
    for epoch in range(epochs):
        net.train()
        for xb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(net(xb), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), grad_clip)
            opt.step()
        net.eval()
        with torch.no_grad():
            val_mae = float((net(x_val) - y_val).abs().mean()) * y_sigma
        logger.info("epoch %d/%d val MAE %.4f", epoch + 1, epochs, val_mae)
        if val_mae < best_val:
            best_val = val_mae
            best_state = {k: v.clone() for k, v in net.state_dict().items()}
            patience_left = patience
        else:
            patience_left -= 1
            if patience_left <= 0:
                logger.info("early stop at epoch %d", epoch + 1)
                break
    assert best_state is not None  # noqa: S101 - best_val set in the same iteration
    return best_val, best_state


class _NNData(NamedTuple):
    Xs: np.ndarray  # standardised train features
    ys: np.ndarray  # standardised log1p target
    X_test: np.ndarray  # raw test features
    mu: np.ndarray
    sigma: np.ndarray
    y_mu: float
    y_sigma: float


def _nn_data(cfg: MobilityConfig, max_rows: int | None = None) -> _NNData:
    """Standardised train features + log1p target, and raw test features.

    Statistics come from the train slice only (no test leakage); the target
    is trained in log1p space because demand is multiplicative — a Gaussian
    loss on raw counts over-penalises busy zones and under-trains the tail.
    ``max_rows`` keeps only the most-recent slice (HPO budget), never random.
    """
    train = _bounded_train(pl.read_parquet(cfg.features_dir / "train.parquet"), cfg)
    if max_rows is not None and train.height > max_rows:
        logger.info("capping NN window %d -> %d rows (most-recent slice)", train.height, max_rows)
        train = train.tail(max_rows)
    test = pl.read_parquet(cfg.features_dir / "test.parquet")
    X_train, y_train = _xy(train)
    X_test, _ = _xy(test)
    mu, sigma = X_train.mean(axis=0), X_train.std(axis=0) + 1e-6
    y_log = np.log1p(y_train)
    y_mu, y_sigma = float(y_log.mean()), float(y_log.std() + 1e-6)
    return _NNData(
        Xs=(X_train - mu) / sigma,
        ys=(y_log - y_mu) / y_sigma,
        X_test=X_test,
        mu=mu,
        sigma=sigma,
        y_mu=y_mu,
        y_sigma=y_sigma,
    )


def _predict_net(
    state: dict[str, torch.Tensor],
    X_test: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
    y_mu: float,
    y_sigma: float,
    hidden: int,
    second_hidden: int,
) -> np.ndarray:
    net = TemporalNet(X_test.shape[1], hidden, second_hidden)
    net.load_state_dict(state)
    net.eval()
    with torch.no_grad():
        y_log_hat = net(torch.tensor((X_test - mu) / sigma)).numpy() * y_sigma + y_mu
    out: np.ndarray = np.clip(np.expm1(y_log_hat), 0.0, None)
    return out


def _train_one_net(
    cfg: MobilityConfig,
    params: dict[str, Any],
    *,
    state_name: str,
    norm_name: str,
) -> tuple[np.ndarray, float]:
    """Fit one TemporalNet variant; persist weights + normaliser; return (test preds, val MAE)."""
    data = _nn_data(cfg)
    fit_idx, val_idx = _temporal_val_split(len(data.ys), gap=24)
    best_val, best_state = _fit_net(
        data.Xs,
        data.ys,
        fit_idx,
        val_idx,
        hidden=int(params["hidden_size"]),
        second_hidden=int(params.get("second_hidden_size", params["hidden_size"] // 2)),
        epochs=int(params["epochs"]),
        batch_size=int(params.get("batch_size", cfg.nn.batch_size)),
        lr=float(params["lr"]),
        weight_decay=float(params["weight_decay"]),
        grad_clip=float(params.get("grad_clip", cfg.nn.grad_clip)),
        patience=int(params.get("early_stop_patience", cfg.nn.early_stop_patience)),
        seed=cfg.seed,
        y_sigma=data.y_sigma,
    )
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, cfg.models_dir / state_name)
    (cfg.models_dir / norm_name).write_text(
        json.dumps(
            {
                "feature_mu": data.mu.tolist(),
                "feature_sigma": data.sigma.tolist(),
                "y_mu": data.y_mu,
                "y_sigma": data.y_sigma,
                "params": params,
            }
        )
    )
    preds = _predict_net(
        best_state,
        data.X_test,
        data.mu,
        data.sigma,
        data.y_mu,
        data.y_sigma,
        int(params["hidden_size"]),
        int(params.get("second_hidden_size", params["hidden_size"] // 2)),
    )
    return preds, best_val


def train_nn(cfg: MobilityConfig | None = None) -> pl.DataFrame:
    """Hand-written training loop; returns the full predictions frame."""
    cfg = cfg or get_config()
    test = pl.read_parquet(cfg.features_dir / "test.parquet")
    y_nn, best_val = _train_one_net(
        cfg, cfg.nn.model_dump(), state_name="temporal_net.pt", norm_name="temporal_net_norm.json"
    )
    logger.info("TemporalNet best val MAE %.4f (raw pickups/hour scale)", best_val)

    preds = _read_parquet_if_exists(_baseline_predictions_file(cfg))
    if preds is None:
        preds = test.select(
            ["zone_id", "borough", "ts", pl.col("target").alias("y_true"), pl.col("lag_24")]
        )
    # merge challenger-arm predictions (owned by train_arms, separate file)
    arms = _read_parquet_if_exists(cfg.models_dir / "predictions_arms.parquet")
    if arms is not None:
        preds = preds.join(arms, on=["zone_id", "ts"], how="left")
    preds = preds.with_columns(y_nn=y_nn)

    tuned = hpo_result(cfg, "nn")
    if tuned is not None:
        logger.info("training tuned TemporalNet with best HPO params: %s", tuned["best_params"])
        y_nn_t, best_val_t = _train_one_net(
            cfg,
            tuned["best_params"],
            state_name="temporal_net_tuned.pt",
            norm_name="temporal_net_tuned_norm.json",
        )
        logger.info("TemporalNet tuned best val MAE %.4f", best_val_t)
        preds = preds.with_columns(y_nn_tuned=y_nn_t)
    else:
        logger.info("no NN HPO result found — skipping temporal_net_tuned (run `mobility tune`)")

    _persist_predictions(cfg, preds, _predictions_file(cfg))
    return preds


def _predictions_file(cfg: MobilityConfig) -> Path:
    return cfg.reports_dir / "models" / "predictions.parquet"


def _baseline_predictions_file(cfg: MobilityConfig) -> Path:
    return cfg.models_dir / "predictions_baseline.parquet"


def _persist_predictions(cfg: MobilityConfig, preds: pl.DataFrame, path: Path) -> None:
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    preds.write_parquet(path, compression="zstd")


def _read_parquet_if_exists(path: Path) -> pl.DataFrame | None:
    return pl.read_parquet(path) if path.exists() else None
