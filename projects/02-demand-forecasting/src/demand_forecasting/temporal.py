"""Compact hand-written PyTorch temporal model (wave 3).

Architecture: a learned per-series embedding concatenated with the lag and
calendar features, fed through a small MLP. Trained with a from-scratch loop:
Adam, gradient clipping, MSE on standardized targets, early stopping on a
time-ordered inner validation slice of the training window.

The estimator exposes the sklearn-style ``fit(x, y) / predict(x)`` surface so
it runs through the identical date-aligned backtest as the other models.
Fully seeded and CPU-friendly (seconds per fold).
"""

import contextlib

import numpy as np

# OpenMP runtime sharing (macOS): establish the gradient boosters' libomp
# image *before* torch loads its own copy. Importing xgboost/lightgbm first
# makes dyld share a single OpenMP runtime; the reverse order segfaults
# (documented torch+xgboost coexistence issue on macOS).
try:  # pragma: no cover - environment guard, not behaviour
    import lightgbm  # noqa: F401
    import xgboost  # noqa: F401
except ImportError:  # boosters are optional arms; torch must still work
    pass
import torch
from torch import nn

from demand_forecasting.config import ForecastConfig

EMBED_DIM = 8
HIDDEN = 64
INNER_VAL_FRAC = 0.15  # last slice of the training rows = early-stop monitor
LR = 1e-3
GRAD_CLIP = 1.0
BATCH = 1024


class _TemporalMLP(nn.Module):
    """Embedding lookup + MLP over [numeric features | series embedding]."""

    def __init__(self, n_series: int, n_numeric: int, embed_dim: int = EMBED_DIM) -> None:
        super().__init__()
        self.emb = nn.Embedding(n_series, embed_dim)
        in_dim = n_numeric + embed_dim
        self.net = nn.Sequential(
            nn.Linear(in_dim, HIDDEN),
            nn.ReLU(),
            nn.Linear(HIDDEN, HIDDEN),
            nn.ReLU(),
            nn.Linear(HIDDEN, 1),
        )

    def forward(self, idx: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        out: torch.Tensor = self.net(torch.cat([self.emb(idx), x], dim=1)).squeeze(-1)
        return out


_THREADS_PINNED = False


def _pin_threads_once() -> None:
    """Pin torch to a single thread (process-wide, idempotent).

    Called from every fit because backtest folds reuse the process; the
    interop setting may only be changed before any parallel work has started,
    so a failed second call is expected and swallowed.
    """
    global _THREADS_PINNED
    if _THREADS_PINNED:
        return
    torch.set_num_threads(1)
    with contextlib.suppress(RuntimeError):
        torch.set_num_interop_threads(1)
    _THREADS_PINNED = True


class TemporalNet:
    """sklearn-style wrapper around :class:`_TemporalMLP`.

    ``x`` is the numpy object array from :func:`demand_forecasting.model.to_xy`:
    numeric columns first, the string ``series_id`` column last.
    """

    def __init__(self, config: ForecastConfig, seed: int) -> None:
        self._config = config
        self._seed = seed
        self._vocab: dict[str, int] = {}
        self._x_mean = np.zeros(0)
        self._x_std = np.ones(0)
        self._y_mean = 0.0
        self._y_std = 1.0
        self._module: _TemporalMLP | None = None

    def _arrays(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        series = [str(s) for s in x[:, -1]]
        idx = np.array([self._vocab[s] for s in series], dtype=np.int64)
        xn = x[:, :-1].astype(float)
        return idx, xn

    def fit(self, x: np.ndarray, y: np.ndarray) -> "TemporalNet":
        """Train with Adam + grad clip + early stop on the newest 15% of rows."""
        torch.manual_seed(self._seed)
        np.random.seed(self._seed)
        # Single-threaded torch: the boosters' OpenMP runtime shares this
        # process, and multi-threaded torch + shared libomp deadlocks on
        # macOS. The model is tiny — single-thread changes nothing but risk.
        _pin_threads_once()
        self._vocab = {s: i for i, s in enumerate(sorted({str(v) for v in x[:, -1]}))}
        idx, xn = self._arrays(x)

        # standardization stats from the training rows only (no val/test info)
        self._x_mean, self._x_std = xn.mean(axis=0), xn.std(axis=0) + 1e-8
        self._y_mean, self._y_std = float(y.mean()), float(y.std()) + 1e-8
        xs = (xn - self._x_mean) / self._x_std
        ys = (y - self._y_mean) / self._y_std

        n_val = max(1, int(len(y) * INNER_VAL_FRAC))
        va = slice(len(y) - n_val, len(y))

        module = _TemporalMLP(len(self._vocab), xs.shape[1])
        opt = torch.optim.Adam(module.parameters(), lr=LR)
        loss_fn = nn.MSELoss()
        gen = torch.Generator().manual_seed(self._seed)

        t_idx = torch.tensor(idx, dtype=torch.long)
        t_x = torch.tensor(xs, dtype=torch.float32)
        t_y = torch.tensor(ys, dtype=torch.float32)

        best_val, best_state, stale = float("inf"), None, 0
        self.train_losses_: list[float] = []
        for _ in range(self._config.temporal_epochs):
            module.train()
            perm = torch.randperm(len(t_y), generator=gen)
            for start in range(0, len(perm), BATCH):
                b = perm[start : start + BATCH]
                opt.zero_grad()
                loss = loss_fn(module(t_idx[b], t_x[b]), t_y[b])
                loss.backward()
                nn.utils.clip_grad_norm_(module.parameters(), GRAD_CLIP)
                opt.step()
            self.train_losses_.append(float(loss.detach()))

            module.eval()
            with torch.no_grad():
                v_idx, v_x = t_idx[va], t_x[va]
                val_mae = float((module(v_idx, v_x) - t_y[va]).abs().mean())
            if val_mae < best_val - 1e-4:
                best_val, stale = val_mae, 0
                best_state = {k: v.clone() for k, v in module.state_dict().items()}
            else:
                stale += 1
                if stale >= self._config.temporal_patience:
                    break
        if best_state is not None:
            module.load_state_dict(best_state)
        self._module = module
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Standardized-space prediction mapped back to units."""
        if self._module is None:
            raise RuntimeError("TemporalNet must be fitted before predict")
        idx, xn = self._arrays(x)
        xs = (xn - self._x_mean) / self._x_std
        self._module.eval()
        with torch.no_grad():
            out = self._module(
                torch.tensor(idx, dtype=torch.long), torch.tensor(xs, dtype=torch.float32)
            )
        pred = np.asarray(out.numpy(), dtype=float)
        return pred * self._y_std + self._y_mean
