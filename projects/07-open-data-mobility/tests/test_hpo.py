"""Wave-3 tests: HPO determinism on toy studies + quantile coverage correctness."""

import numpy as np
import optuna
import polars as pl
from mobility.evaluate import p90_coverage, p90_coverage_by_borough
from sklearn.ensemble import HistGradientBoostingRegressor


def _toy_xy(seed: int = 0, n: int = 400) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 5)).astype(np.float32)
    y = x[:, 0] * 2.0 + 0.5 * x[:, 1] + 1.0
    return x, y.astype(np.float32)


def _tiny_study() -> optuna.Study:
    X, y = _toy_xy()
    sampler = optuna.samplers.TPESampler(seed=42)
    study = optuna.create_study(direction="minimize", sampler=sampler, study_name="toy")

    def objective(trial: optuna.Trial) -> float:
        model = HistGradientBoostingRegressor(
            learning_rate=trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
            max_iter=trial.suggest_int("max_iter", 20, 60),
            max_leaf_nodes=trial.suggest_int("max_leaf_nodes", 15, 31),
            random_state=42,
        )
        model.fit(X[:300], y[:300])
        pred = model.predict(X[300:])
        return float(np.mean(np.abs(y[300:] - pred)))

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(objective, n_trials=5)
    return study


def test_hpo_study_is_deterministic() -> None:
    """Same seed + same data ⇒ same best params and value (twice)."""
    a, b = _tiny_study(), _tiny_study()
    assert a.best_params == b.best_params
    assert a.best_value == b.best_value


def test_p90_coverage_exact() -> None:
    """Hand-built frame: 9 of 10 actuals ≤ p90 → coverage 0.9 overall."""
    truth = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
    p90 = [10, 10, 10, 10, 10, 10, 10, 10, 10, 50]  # only the 100 breaks the band
    preds = pl.DataFrame({"y_true": truth, "y_p90": p90})
    assert p90_coverage(preds) == 0.9


def test_p90_coverage_by_borough_rows() -> None:
    """Per-borough coverage plus an OVERALL row; target line is a figure concern."""
    preds = pl.DataFrame(
        {
            "borough": ["A", "A", "B", "B"],
            "y_true": [1, 10, 2, 20],
            "y_p90": [5, 5, 50, 50],
        }
    )
    out = p90_coverage_by_borough(preds)
    rows = {r["borough"]: r["coverage"] for r in out.iter_rows(named=True)}
    assert rows["A"] == 0.5  # 1 ≤ 5 covered, 10 > 5 not
    assert rows["B"] == 1.0
    assert rows["OVERALL"] == 0.75
