"""Uplift models, hand-rolled on sklearn (DESIGN.md: no causallib/causalml dep).

- Response model (the marketing-practice baseline): one classifier fit on the
  treated arm only; rank by P(convert | X, treated).
- T-learner: mu1 fit on treated, mu0 on control; uplift = mu1(X) - mu0(X).
- X-learner (Künzel et al. 2019): impute per-row effects D1 = Y - mu0(X) on the
  treated and D0 = mu1(X) - Y on the control, fit two effect regressors, and
  combine them propensity-weighted: tau = g(x)*tau0(x) + (1-g(x))*tau1(x).
  With a ~50/50 randomization g is near-constant, but we fit it anyway — the
  weighting is part of the method and matters for covariate shift.
- Per-arm T-learners (multi-treatment read, ``multiarm``): each campaign arm
  vs the shared control via ``cross_fit_arm_uplift``; the configured treatment
  arm reuses the binary seed stream and reproduces the committed T-learner.

All scores are out-of-fold (cross-fitted): Qini/profit reads never see
in-sample predictions, so model-vs-model comparisons are not confounded by
overfitting.
"""

from collections.abc import Callable
from typing import cast

import numpy as np
from portfolio_core.logging import get_logger
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from uplift_experimentation.config import pd  # untyped re-export, ignore lives there

log = get_logger(__name__)

CATEGORICAL_COLS = ["channel", "zip_code"]
NUMERIC_COLS = ["recency", "history", "log_history", "mens", "womens", "newbie"]
SCORE_POLICIES = ["response", "t_learner", "x_learner"]


def make_preprocess() -> ColumnTransformer:
    """One-hot encode the two low-cardinality categoricals; pass numerics through."""
    return ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_COLS,
            ),
            ("num", "passthrough", NUMERIC_COLS),
        ]
    )


def make_classifier(seed: int) -> Pipeline:
    return Pipeline(
        [
            ("prep", make_preprocess()),
            (
                "clf",
                HistGradientBoostingClassifier(
                    max_iter=200,
                    learning_rate=0.06,
                    max_leaf_nodes=31,
                    early_stopping=True,
                    random_state=seed,
                ),
            ),
        ]
    )


def make_regressor(seed: int) -> Pipeline:
    return Pipeline(
        [
            ("prep", make_preprocess()),
            (
                "reg",
                HistGradientBoostingRegressor(
                    max_iter=150,
                    learning_rate=0.06,
                    max_leaf_nodes=31,
                    early_stopping=True,
                    random_state=seed,
                ),
            ),
        ]
    )


def fit_policy_scores(
    X: pd.DataFrame,
    treatment: np.ndarray,
    y: np.ndarray,
    seed: int,
    X_score: pd.DataFrame | None = None,
) -> dict[str, np.ndarray]:
    """Fit all three policies on (X, treatment, y) and score ``X_score``.

    ``X_score`` defaults to ``X`` (in-sample scoring); cross-fitting passes the
    held-out fold so every row's score comes from a model that never saw it.
    """
    Xs = X if X_score is None else X_score
    t = treatment == 1
    X1, X0, y1, y0 = X[t], X[~t], y[t], y[~t]

    # Response model: treated-arm conversion classifier.
    response_model = make_classifier(seed)
    response_model.fit(X1, y1)
    response = response_model.predict_proba(Xs)[:, 1]

    # T-learner arms.
    mu1_model = make_classifier(seed)
    mu1_model.fit(X1, y1)
    mu0_model = make_classifier(seed + 1)
    mu0_model.fit(X0, y0)
    mu1 = mu1_model.predict_proba(Xs)[:, 1]
    mu0 = mu0_model.predict_proba(Xs)[:, 1]

    # X-learner: imputed effects + propensity-weighted combination.
    d1 = y1 - mu0_model.predict_proba(X1)[:, 1]
    d0 = mu1_model.predict_proba(X0)[:, 1] - y0
    tau1_model = make_regressor(seed + 2)
    tau1_model.fit(X1, d1)
    tau0_model = make_regressor(seed + 3)
    tau0_model.fit(X0, d0)
    # Propensity g(x) = P(T=1|X) for the X-learner combination weighting,
    # fit on the training fold's assignment and clipped away from 0/1.
    g_model = Pipeline(
        [
            ("prep", make_preprocess()),
            ("clf", LogisticRegression(max_iter=1000, C=0.5, random_state=seed + 4)),
        ]
    )
    g_model.fit(X, treatment)
    g = np.clip(g_model.predict_proba(Xs)[:, 1], 0.05, 0.95)
    x_learner = g * tau0_model.predict(Xs) + (1.0 - g) * tau1_model.predict(Xs)

    return {
        "response": response,
        "t_learner": mu1 - mu0,
        "x_learner": x_learner,
    }


def cross_fit_scores(
    X: pd.DataFrame, treatment: np.ndarray, y: np.ndarray, folds: int, seed: int
) -> pd.DataFrame:
    """Out-of-fold scores for every policy row-wise (the honest evaluation read)."""
    kfold = KFold(n_splits=folds, shuffle=True, random_state=seed)
    scores = {name: np.full(len(y), np.nan) for name in SCORE_POLICIES}
    for fold, (train_idx, test_idx) in enumerate(kfold.split(X)):
        fold_scores = fit_policy_scores(
            X.iloc[train_idx],
            treatment[train_idx],
            y[train_idx],
            seed + 10 * fold,
            X_score=X.iloc[test_idx],
        )
        for name, values in fold_scores.items():
            scores[name][test_idx] = values
        log.info("cross-fit: fold %d/%d scored", fold + 1, folds)
    out = pd.DataFrame(scores)
    if out.isnull().any().any():
        raise ValueError("cross-fitting left un-scored rows")
    return out


# ---------------------------------------------------------------------------
# Per-arm T-learners (multi-treatment uplift, secondary read)
# ---------------------------------------------------------------------------


def fit_arm_uplift(
    X: pd.DataFrame,
    treatment_arm: np.ndarray,
    y: np.ndarray,
    seed: int,
) -> Callable[[pd.DataFrame], np.ndarray]:
    """Fit a T-learner for one arm vs control and return a scorer for new rows.

    Used by the multi-treatment read: out-of-fold scores cover the arm/control
    rows, and rows of the third arm are scored by this pair model refit on all
    its rows — a deployment-style prediction for unseen customers, never an
    in-sample score. ``treatment_arm`` is 1 on the campaign arm, 0 on control.
    """
    t = treatment_arm == 1
    X1, X0, y1, y0 = X[t], X[~t], y[t], y[~t]
    mu1_model = make_classifier(seed)
    mu1_model.fit(X1, y1)
    mu0_model = make_classifier(seed + 1)
    mu0_model.fit(X0, y0)

    def score(Xs: pd.DataFrame) -> np.ndarray:
        uplift = mu1_model.predict_proba(Xs)[:, 1] - mu0_model.predict_proba(Xs)[:, 1]
        return cast(np.ndarray, np.asarray(uplift, dtype=float))

    return score


def cross_fit_arm_uplift(
    X: pd.DataFrame,
    treatment_arm: np.ndarray,
    y: np.ndarray,
    folds: int,
    seed: int,
) -> np.ndarray:
    """Out-of-fold T-learner uplift scores for an arm-vs-control frame.

    Reuses the ``cross_fit_scores`` convention (``KFold(shuffle=True)`` with
    ``seed + 10 * fold``) so per-arm scores are comparable across arms, but
    fits only the two T-learner arm models per fold — the response/X-learner
    machinery is not needed per arm. Callers pick a seed offset distinct from
    the binary run so the streams do not collide.
    """
    kfold = KFold(n_splits=folds, shuffle=True, random_state=seed)
    scores = np.full(len(y), np.nan)
    for fold, (train_idx, test_idx) in enumerate(kfold.split(X)):
        fold_scores = fit_arm_uplift(
            X.iloc[train_idx],
            treatment_arm[train_idx],
            y[train_idx],
            seed + 10 * fold,
        )
        scores[test_idx] = fold_scores(X.iloc[test_idx])
        log.info("cross-fit arm: fold %d/%d scored", fold + 1, folds)
    if np.isnan(scores).any():
        raise ValueError("cross-fitting left un-scored rows")
    return scores
