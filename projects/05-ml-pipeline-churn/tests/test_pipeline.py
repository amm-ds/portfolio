"""Pipeline integration on a tiny real synthetic frame (no network)."""

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from churn_pipeline.config import ChurnConfig
from churn_pipeline.model import (
    NUMERIC_COLS,
    build_pipeline,
    feature_names,
    split_holdout,
    train_model,
)


def test_split_is_stratified_and_disjoint(
    small_cfg: ChurnConfig, tiny_synthetic: pd.DataFrame
) -> None:
    X_train, X_test, y_train, y_test = split_holdout(small_cfg, tiny_synthetic)
    assert len(X_train) + len(X_test) == len(tiny_synthetic)
    assert len(X_test) == round(len(tiny_synthetic) * small_cfg.test_frac)
    rate_train = y_train.mean()
    rate_test = y_test.mean()
    assert abs(rate_train - rate_test) < 0.05, "stratification keeps churn rates close"
    assert set(X_train.index).isdisjoint(X_test.index), "no leakage between splits"


def test_pipeline_fit_predict_shapes(small_cfg: ChurnConfig, tiny_synthetic: pd.DataFrame) -> None:
    X_train, X_test, y_train, _y_test = split_holdout(small_cfg, tiny_synthetic)
    pipe = build_pipeline(small_cfg)
    pipe.fit(X_train, y_train)
    proba = pipe.predict_proba(X_test)
    assert proba.shape == (len(X_test), 2)
    assert np.isfinite(proba).all()
    assert ((proba >= 0) & (proba <= 1)).all()


def test_preprocessor_feature_names_cover_all_inputs(
    small_cfg: ChurnConfig, tiny_synthetic: pd.DataFrame
) -> None:
    X_train, _, y_train, _ = split_holdout(small_cfg, tiny_synthetic)
    pipe = build_pipeline(small_cfg).fit(X_train, y_train)
    names = feature_names(pipe)
    for col in NUMERIC_COLS:
        assert f"num__{col}" in names
    for col in NUMERIC_COLS:
        assert f"num__{col}_was_missing" in names, "indicator flags inside the pipeline"
    onehot = [n for n in names if n.startswith("cat__contract_")]
    assert len(onehot) == 3, "all three contract levels encoded"


def test_grid_search_selects_from_c_grid(
    small_cfg: ChurnConfig, tiny_synthetic: pd.DataFrame
) -> None:
    X_train, _, y_train, _ = split_holdout(small_cfg, tiny_synthetic)
    grid = train_model(small_cfg, X_train, y_train)
    assert grid.best_params_["clf__C"] in small_cfg.c_grid
    assert np.isfinite(grid.best_score_)


def test_pipeline_handles_unseen_category(
    small_cfg: ChurnConfig, tiny_synthetic: pd.DataFrame
) -> None:
    X_train, _, y_train, _ = split_holdout(small_cfg, tiny_synthetic)
    pipe = build_pipeline(small_cfg).fit(X_train, y_train)
    novel = X_train.iloc[:3].copy()
    novel["contract"] = "lifetime-plan-never-seen"
    proba = pipe.predict_proba(novel)
    assert np.isfinite(proba).all(), "handle_unknown='ignore' must not blow up"
