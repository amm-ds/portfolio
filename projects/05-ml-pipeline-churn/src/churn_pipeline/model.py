"""Model assembly: one sklearn Pipeline from raw DataFrame to probabilities.

The whole preprocessing (outlier capping, missing-value flags, imputation,
scaling, one-hot encoding) lives inside the fitted estimator, so the trained
artifact is self-contained and safe to score on equally messy raw data.
"""

from typing import Any

import pandas as pd  # type: ignore[import-untyped]
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from churn_pipeline.config import ChurnConfig
from churn_pipeline.features import MissingValueIndicator, OutlierCapper

NUMERIC_COLS = ["age", "tenure_months", "monthly_charges", "support_calls"]
CATEGORICAL_COLS = ["contract"]
TARGET_COL = "churned"


def build_preprocessor(cfg: ChurnConfig) -> ColumnTransformer:
    """Numeric branch (cap → flag → impute → scale) + categorical one-hot."""
    numeric = Pipeline(
        steps=[
            ("capper", OutlierCapper(cfg.cap_quantile_low, cfg.cap_quantile_high)),
            ("missing_flags", MissingValueIndicator()),
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric, NUMERIC_COLS),
            ("cat", categorical, CATEGORICAL_COLS),
        ]
    )


def _build_classifier(
    cfg: ChurnConfig, family: str, params: dict[str, float] | None
) -> LogisticRegression | HistGradientBoostingClassifier:
    """Classifier step for the pipeline: wave-2 logistic default or HPO params."""
    if family == "logreg":
        kw: dict[str, object] = {
            "class_weight": "balanced",
            "max_iter": 1000,
            "random_state": cfg.seed,
        }
        if params:
            kw.update(params)
        return LogisticRegression(**kw)
    if family == "histgb":
        kw = {"random_state": cfg.seed, "class_weight": "balanced"}
        if params:
            kw.update(params)
        return HistGradientBoostingClassifier(**kw)
    raise ValueError(f"unknown model family: {family!r}")


def build_pipeline(
    cfg: ChurnConfig,
    family: str = "logreg",
    params: dict[str, Any] | None = None,
) -> Pipeline:
    """End-to-end Pipeline: preprocessor + classifier (both families supported)."""
    return Pipeline(
        steps=[
            ("prep", build_preprocessor(cfg)),
            ("clf", _build_classifier(cfg, family, params)),
        ]
    )


def split_holdout(
    cfg: ChurnConfig, df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Stratified train/holdout split (no temporal axis in this dataset)."""
    X = df[NUMERIC_COLS + CATEGORICAL_COLS]
    y = df[TARGET_COL].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=cfg.test_frac,
        stratify=y,
        random_state=cfg.seed,
    )
    return X_train, X_test, y_train, y_test


def train_model(cfg: ChurnConfig, X_train: pd.DataFrame, y_train: pd.Series) -> GridSearchCV:
    """Grid-search the regularization strength C on a stratified K-fold."""
    pipe = build_pipeline(cfg)
    grid = GridSearchCV(
        estimator=pipe,
        param_grid={"clf__C": cfg.c_grid},
        scoring="f1",
        cv=StratifiedKFold(n_splits=cfg.cv_folds, shuffle=True, random_state=cfg.seed),
        refit=True,
    )
    grid.fit(X_train, y_train)
    return grid


def feature_names(pipe: Pipeline) -> list[str]:
    """Human-readable feature names of the fitted preprocessor (importance plots)."""
    prep: ColumnTransformer = pipe.named_steps["prep"]
    return [str(n) for n in prep.get_feature_names_out()]
