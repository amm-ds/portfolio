"""Model stage: TemporalNet trains and its loss actually decreases."""

from datetime import timedelta

import numpy as np
import polars as pl
import torch
from mobility.config import MobilityConfig
from mobility.features import FEATURE_COLUMNS
from mobility.model import TemporalNet, _bounded_train, _temporal_val_split, train_nn


def _toy_frame(n: int = 200, seed: int = 0) -> pl.DataFrame:
    """Deterministic toy matrix: y driven by lag_1 plus small noise."""
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 20, size=n).astype(np.float32)
    return pl.DataFrame(
        {
            "zone_id": np.ones(n, dtype=np.int64),
            "borough": ["Manhattan"] * n,
            "ts": pl.datetime_range(
                pl.datetime(2024, 1, 1),
                pl.datetime(2024, 1, 1) + timedelta(hours=n - 1),
                "1h",
                eager=True,
            ),
            **{
                f: rng.normal(size=n).astype(np.float32)
                for f in FEATURE_COLUMNS
                if f not in ("hour", "day_of_week", "month")
            },
            "hour": (np.arange(n) % 24).astype(np.int64),
            "day_of_week": (np.arange(n) % 7 + 1).astype(np.int64),
            "month": np.ones(n, dtype=np.int64),
            "target": base,
        }
    ).with_columns(lag_1=pl.col("lag_1") * 0 + pl.col("target"))


def test_temporal_net_forward_shape() -> None:
    net = TemporalNet(n_features=len(FEATURE_COLUMNS), hidden=64, second_hidden=32)
    out = net(torch.randn(7, len(FEATURE_COLUMNS)))
    assert out.shape == (7,)


def test_training_loop_reduces_loss() -> None:
    """One epoch over 200 rows: MSE on a held-out block must drop vs init."""
    torch.manual_seed(42)
    x = torch.randn(200, len(FEATURE_COLUMNS))
    y = x[:, 0] * 3.0 + 0.5
    net = TemporalNet(x.shape[1], 64, 32)
    opt = torch.optim.Adam(net.parameters(), lr=1e-2)
    loss_fn = torch.nn.MSELoss()
    x_fit, y_fit, x_val, y_val = x[:160], y[:160], x[160:], y[160:]
    with torch.no_grad():
        initial = float(loss_fn(net(x_val), y_val))
    for _ in range(200):
        opt.zero_grad()
        loss = loss_fn(net(x_fit), y_fit)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0)
        opt.step()
    with torch.no_grad():
        final = float(loss_fn(net(x_val), y_val))
    assert final < initial * 0.1


def test_temporal_val_split_has_embargo() -> None:
    train_idx, val_idx = _temporal_val_split(n=1000, gap=24)
    assert len(train_idx) + len(val_idx) <= 1000 - 24  # embargo enforced
    assert train_idx.max() < val_idx.min()
    assert val_idx.max() == 999  # expanding window reaches the end


def test_bounded_train_keeps_most_recent(cfg: MobilityConfig) -> None:
    frame = _toy_frame(n=10)
    cfg = cfg.model_copy(update={"max_train_rows": 4})
    bounded = _bounded_train(frame, cfg)
    assert bounded.height == 4
    assert min(bounded["ts"].to_list()) > min(frame["ts"].to_list())


def test_train_nn_end_to_end(cfg: MobilityConfig) -> None:
    """Full hand-written loop on 400 rows: artifacts exist, predictions sane."""
    toy = _toy_frame(n=400)
    toy.write_parquet(cfg.features_dir / "train.parquet")
    toy.tail(80).write_parquet(cfg.features_dir / "test.parquet")
    cfg = cfg.model_copy(update={"nn": cfg.nn.model_copy(update={"epochs": 2, "batch_size": 64})})
    preds = train_nn(cfg)
    assert preds.height == 80
    assert "y_nn" in preds.columns
    assert (preds["y_nn"] >= 0).all()
    assert (cfg.models_dir / "temporal_net.pt").exists()
    assert (cfg.models_dir / "temporal_net_norm.json").exists()
