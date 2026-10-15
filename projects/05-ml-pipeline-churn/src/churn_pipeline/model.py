"""Model assembly: one sklearn Pipeline from raw DataFrame to probabilities.

The whole preprocessing (outlier capping, missing-value flags, imputation,
scaling, one-hot encoding) lives inside the fitted estimator, so the trained
artifact is self-contained and safe to score on equally messy raw data.
"""

from typing import Any

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

_LIBOMP_HINT = (
    "On macOS, install OpenMP (the PyPI wheels for xgboost/lightgbm do not "
    "bundle it): brew install libomp. Linux wheels bundle libgomp and need "
    "nothing. Original error: {cause}"
)


def _boosting_import_error(cause: BaseException) -> RuntimeError:
    """Actionable error when the boosting native libraries cannot load."""
    text = str(cause)
    if "libomp" in text or "OpenMP" in text:
        return RuntimeError(_LIBOMP_HINT.format(cause=text))
    return RuntimeError(f"xgboost/lightgbm failed to import: {cause}")


try:  # optional boosting arms; the wave-2 logistic arm needs neither
    from lightgbm import LGBMClassifier
    from xgboost import XGBClassifier
except (ImportError, OSError) as _boost_exc:  # pragma: no cover - env dependent
    raise _boosting_import_error(_boost_exc) from _boost_exc

from churn_pipeline.config import ChurnConfig, pd  # noqa: E402
from churn_pipeline.features import MissingValueIndicator, OutlierCapper  # noqa: E402

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


def _build_classifier(cfg: ChurnConfig, family: str, params: dict[str, Any] | None) -> Any:
    """Classifier step for the pipeline: wave-2 logistic default or HPO params."""
    if family == "logreg":
        kw: dict[str, Any] = {
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
    if family == "xgboost":
        # sklearn-API arm: consumes the same ColumnTransformer output
        # (dense, since the one-hot density exceeds the sparse threshold);
        # single-threaded to avoid the OpenMP oversubscription measured here.
        # Note: XGBClassifier ignores class_weight — imbalance handling is
        # injected per-dataset as scale_pos_weight by the HPO objective.
        kw = {"random_state": cfg.seed, "n_jobs": 1, "eval_metric": "logloss"}
        if params:
            kw.update(params)
        return XGBClassifier(**kw)
    if family == "lightgbm":
        # n_jobs=1: like xgboost, native threads oversubscribe on this host.
        kw = {
            "random_state": cfg.seed,
            "class_weight": "balanced",
            "verbose": -1,
            "n_jobs": 1,
        }
        if params:
            kw.update(params)
        return LGBMClassifier(**kw)
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
