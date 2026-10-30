"""Torch-free GBM factory + HPO result accessor (extracted from model.py).

Wave 15: ``model.py`` imports torch at module level (TemporalNet), which made
every consumer of the GBM factory pull torch into its process — including the
drift-check path (``drift`` → ``serving``). The GBM helpers live here so
``serving``/``drift``/``transfer`` stay torch-free; ``model`` and ``tune``
re-export them for compatibility (same wave-11 rationale that keeps
xgboost/lightgbm out of the torch process — this module imports neither).
"""

import json
from typing import Any

from sklearn.ensemble import HistGradientBoostingRegressor

from mobility.config import MobilityConfig


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
