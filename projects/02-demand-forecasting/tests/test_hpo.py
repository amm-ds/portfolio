"""HPO determinism and search-space tests (offline, small trial counts)."""

import optuna
import polars as pl
from demand_forecasting.config import ForecastConfig
from demand_forecasting.hpo import make_objective, suggest_params
from demand_forecasting.model import model_specs


def test_seeded_sampler_is_deterministic(features: pl.DataFrame, config: ForecastConfig) -> None:
    """Same seed → same sampled params for the first trials (no fitting needed)."""
    sampler_a = optuna.samplers.TPESampler(seed=42)
    sampler_b = optuna.samplers.TPESampler(seed=42)
    study_a = optuna.create_study(sampler=sampler_a)
    study_b = optuna.create_study(sampler=sampler_b)
    for _ in range(3):
        trial_a = study_a.ask()
        trial_b = study_b.ask()
        pa = suggest_params(trial_a, "hgb")
        pb = suggest_params(trial_b, "hgb")
        assert pa == pb


def test_objective_uses_backtest_folds(features: pl.DataFrame, config: ForecastConfig) -> None:
    """The HPO objective optimizes over the exact same folds as the backtest."""
    from demand_forecasting.evaluate import cv_row_folds

    objective = make_objective(features, config, seed=42)
    folds = cv_row_folds(features, config)
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=1)
    trial = study.trials[0]
    # one intermediate report per fold (before any pruning decision)
    assert len(trial.intermediate_values) == len(folds)


def test_hgb_tuned_spec_uses_config_params(config: ForecastConfig) -> None:
    """hgb_tuned is built from the production (HPO) config, not the default HGB."""
    spec = next(s for s in model_specs() if s.name == "hgb_tuned")
    model = spec.build(config)
    est = model.named_steps["reg"]
    assert est.learning_rate == config.hgb_tuned.learning_rate
    assert est.max_iter == config.hgb_tuned.max_iter


def test_hgb_tuned_matches_hpo_output(config: ForecastConfig) -> None:
    """The tuned kwargs are exactly the HGB constructor's hyperparameters."""
    kwargs = config.hgb_tuned.estimator_kwargs()
    assert set(kwargs) == {
        "learning_rate",
        "max_iter",
        "max_leaf_nodes",
        "min_samples_leaf",
        "l2_regularization",
        "max_features",
    }
