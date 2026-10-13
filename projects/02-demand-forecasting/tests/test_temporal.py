"""TemporalNet: training-loop correctness on synthetic data."""

import numpy as np
from demand_forecasting.config import ForecastConfig
from demand_forecasting.temporal import TemporalNet


def _synthetic(n: int = 600, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Structured series: weekly seasonality + store offset + trend."""
    rng = np.random.default_rng(seed)
    stores = np.tile(np.array(["s0", "s1", "s2", "s3"]), n // 4)
    t = np.tile(np.arange(n // 4), 4)
    store_off = np.array([10.0 if s == "s0" else 25.0 for s in stores])
    y = store_off + 3.0 * np.sin(2 * np.pi * t / 7) + 0.05 * t + rng.normal(0, 1.0, n)
    x = np.column_stack([rng.normal(size=(n, 10)), stores])
    return x, y


def test_training_loop_decreases_loss() -> None:
    """MSE on structured data must drop substantially within the epoch budget."""
    config = ForecastConfig(n_days=60, temporal_epochs=40, temporal_patience=10)
    x, y = _synthetic()
    net = TemporalNet(config, seed=7).fit(x, y)
    head = float(np.mean(net.train_losses_[:3]))
    tail = float(np.mean(net.train_losses_[-3:]))
    assert tail < head * 0.8, f"loss did not decrease: head={head:.3f} tail={tail:.3f}"


def test_temporal_net_is_seeded() -> None:
    """Same seed → same predictions; different seed → different predictions."""
    config = ForecastConfig(n_days=60, temporal_epochs=20, temporal_patience=5)
    x, y = _synthetic()
    p1 = TemporalNet(config, seed=3).fit(x, y).predict(x)
    p2 = TemporalNet(config, seed=3).fit(x, y).predict(x)
    p3 = TemporalNet(config, seed=4).fit(x, y).predict(x)
    np.testing.assert_allclose(p1, p2, rtol=1e-5)
    assert not np.allclose(p1, p3)


def test_predict_before_fit_raises() -> None:
    config = ForecastConfig(n_days=60)
    net = TemporalNet(config, seed=1)
    x, _ = _synthetic(n=8)
    try:
        net.predict(x)
    except RuntimeError:
        return
    raise AssertionError("predict before fit must raise RuntimeError")
