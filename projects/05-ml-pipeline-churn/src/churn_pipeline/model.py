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


def _ensure_libomp() -> None:
    """macOS fallback: give XGBoost/LightGBM wheels one shared libomp.

    Neither project's PyPI wheels (incl. arm64) bundle ``libomp.dylib``
    anymore — upstream expects ``brew install libomp``. This repo stays
    brew-free, so we self-heal the active venv (idempotent): place a single
    ``libomp.dylib`` at ``<venv>/lib`` (sourced from xgboost's bundled copy,
    ``vendor/libomp.dylib``, or the workspace venv — walking up from cwd,
    which also covers DVC-experiment temp venvs) and add an
    ``@loader_path/../../../..//`` rpath to each dylib so both resolve the
    *same* image. Copying a libomp per package instead loads two OpenMP
    runtimes and segfaults (measured: xgboost unpickle after lightgbm
    import). No-op off macOS. See DESIGN.md (wave 11).
    """
    import platform
    import shutil
    import subprocess
    import sys
    from importlib.util import find_spec
    from pathlib import Path

    if platform.system() != "Darwin":
        return

    def _pkg_lib(pkg: str) -> Path | None:
        spec = find_spec(pkg)
        if spec is None or not spec.submodule_search_locations:
            return None
        return Path(next(iter(spec.submodule_search_locations))) / "lib"

    sources: list[Path] = []
    xgb_lib = _pkg_lib("xgboost")
    if xgb_lib is not None:
        sources.append(xgb_lib / "libomp.dylib")
    here = Path(__file__).resolve()
    sources.extend(p / "vendor" / "libomp.dylib" for p in (here.parent, *here.parents[1:4]))
    for base in [Path.cwd(), *Path.cwd().parents][:8]:
        sources.extend(base.glob(".venv/lib/libomp.dylib"))

    target = Path(sys.prefix) / "lib" / "libomp.dylib"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        for source in sources:
            if source.exists() and source != target:
                try:
                    shutil.copy2(source, target)
                except OSError:
                    return  # read-only envs: the libs raise their own error
                break
    if not target.exists():
        return

    rpath = "@loader_path/../../../..//"
    for pkg, dylib_name in (("xgboost", "libxgboost.dylib"), ("lightgbm", "lib_lightgbm.dylib")):
        lib_dir = _pkg_lib(pkg)
        if lib_dir is None:
            continue
        dylib = lib_dir / dylib_name
        if not dylib.exists():
            continue
        try:
            out = subprocess.run(
                ["otool", "-l", str(dylib)], capture_output=True, text=True, check=True
            ).stdout
            if "@loader_path/../../../..//" not in out:
                subprocess.run(
                    ["install_name_tool", "-add_rpath", rpath, str(dylib)],
                    capture_output=True,
                    check=False,
                )
        except (OSError, subprocess.SubprocessError):
            pass


_ensure_libomp()  # must run before `import lightgbm`

from lightgbm import LGBMClassifier  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

from churn_pipeline.config import ChurnConfig  # noqa: E402
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
