"""Q4a single-protocol uplift comparison on the committed folds (next round).

One scoring protocol, four learner labels, no new dependencies. The project
DESIGN defers grf/econml ("heavyweight deps"), so the learner is
hand-rolled on sklearn as a DR-learner forest: doubly-robust pseudo-outcomes
from the committed cross-fit nuisances, regressed with a random forest.

Learners (scores for every row, out-of-fold convention):
- ``dr_learner``: DR-forest (this module), psi -> RandomForestRegressor.
- ``t_learner`` / ``two_model``: the committed out-of-fold T-learner column.
  The "two-model approach" and the T-learner are the same estimator family in
  the uplift literature (separate treated/control response models); both
  labels name this one row.
- ``x_learner``: the committed out-of-fold X-learner column.

Metrics per learner: Qini area = AUUC (unnormalised; the area between the
incremental-conversions curve and the random line, see
:func:`uplift_experimentation.qini.qini_coefficient`) with a paired row
bootstrap 95% interval, and DR policy value across the configured budget
fractions with bootstrap intervals.

Output: NEW files under ``reports/single_protocol/`` only; no committed
record is touched. Compute-only, deterministic (seed 42 throughout).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
from portfolio_core.logging import get_logger
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline

from uplift_experimentation.config import UpliftConfig, threadpool_limits
from uplift_experimentation.models import make_classifier, make_preprocess
from uplift_experimentation.qini import qini_coefficient, qini_points

log = get_logger(__name__)

BOOTSTRAP_REPS = 2000
FOREST_LEAF = 10
FOREST_TREES = 400


def cross_fit_arm_predictions(
    X: pd.DataFrame,
    treatment: np.ndarray,
    y: np.ndarray,
    folds: int,
    seed: int,
) -> dict[str, np.ndarray]:
    """Out-of-fold arm probabilities mu1/mu0 and propensity g.

    Mirrors ``models.cross_fit_scores`` exactly (same KFold seed, same
    per-fold model seeds, same single-threaded fitting) so the recomputed
    T-learner delta reproduces the committed scores column; the caller asserts
    that identity before the DR pseudo-outcomes are trusted.
    """
    kfold = KFold(n_splits=folds, shuffle=True, random_state=seed)
    mu1 = np.full(len(y), np.nan)
    mu0 = np.full(len(y), np.nan)
    g = np.full(len(y), np.nan)
    for fold, (train_idx, test_idx) in enumerate(kfold.split(X)):
        fold_seed = seed + 10 * fold
        t = treatment[train_idx] == 1
        m1 = make_classifier(fold_seed)
        m1.fit(X.iloc[train_idx][t], y[train_idx][t])
        m0 = make_classifier(fold_seed + 1)
        m0.fit(X.iloc[train_idx][~t], y[train_idx][~t])
        mu1[test_idx] = m1.predict_proba(X.iloc[test_idx])[:, 1]
        mu0[test_idx] = m0.predict_proba(X.iloc[test_idx])[:, 1]
        g_model = Pipeline(
            [
                ("prep", make_preprocess()),
                ("clf", LogisticRegression(max_iter=1000, C=0.5, random_state=fold_seed + 4)),
            ]
        )
        g_model.fit(X.iloc[train_idx], treatment[train_idx])
        g[test_idx] = g_model.predict_proba(X.iloc[test_idx])[:, 1]
        log.info("arm cross-fit: fold %d/%d scored", fold + 1, folds)
    if np.isnan(mu1).any() or np.isnan(mu0).any() or np.isnan(g).any():
        raise ValueError("arm cross-fitting left un-scored rows")
    return {"mu1": mu1, "mu0": mu0, "g": np.clip(g, 0.05, 0.95)}


def dr_pseudo_outcomes(
    treatment: np.ndarray, y: np.ndarray, mu1: np.ndarray, mu0: np.ndarray, g: np.ndarray
) -> np.ndarray:
    """Doubly-robust CATE pseudo-outcome.

    psi = (mu1 - mu0) + T (y - mu1) / g - (1 - T) (y - mu0) / (1 - g)
    """
    t = treatment.astype(float)
    psi: np.ndarray = (mu1 - mu0) + t * (y - mu1) / g - (1.0 - t) * (y - mu0) / (1.0 - g)
    return psi


def dr_policy_value(
    treatment: np.ndarray,
    y: np.ndarray,
    score: np.ndarray,
    mu1: np.ndarray,
    mu0: np.ndarray,
    g: np.ndarray,
    budget: float,
) -> float:
    """DR value of "mail the top-``budget`` fraction by ``score``".

    V_DR = mean_i [ pi_i (mu1_i + T_i (y_i - mu1_i) / g_i)
                    + (1 - pi_i) (mu0_i + (1 - T_i) (y_i - mu0_i) / (1 - g_i)) ]
    with pi_i = 1 for the top-k scores, 0 otherwise.
    """
    n = len(y)
    k = round(budget * n)
    pi = np.zeros(n)
    pi[np.argsort(-score, kind="stable")[:k]] = 1.0
    t = treatment.astype(float)
    v1 = mu1 + t * (y - mu1) / g
    v0 = mu0 + (1.0 - t) * (y - mu0) / (1.0 - g)
    return float(np.mean(pi * v1 + (1.0 - pi) * v0))


def percentile_ci(stats: list[float], alpha: float = 0.05) -> list[float]:
    stats = sorted(stats)
    n = len(stats)
    return [stats[max(0, int(alpha / 2 * n))], stats[min(n - 1, int((1 - alpha / 2) * n))]]


def bootstrap_metric(
    treatment: np.ndarray,
    y: np.ndarray,
    score: np.ndarray,
    metric: str,
    mu1: np.ndarray,
    mu0: np.ndarray,
    g: np.ndarray,
    budget: float | None,
    reps: int = BOOTSTRAP_REPS,
    seed: int = 42,
) -> list[float]:
    """Paired row-bootstrap CI for the Qini area or the DR policy value."""
    rng = np.random.default_rng(seed)
    n = len(y)
    stats: list[float] = []
    for _ in range(reps):
        idx = rng.integers(0, n, n)
        if metric == "qini_area":
            stats.append(qini_coefficient(treatment[idx], y[idx], score[idx]))
        else:
            stats.append(
                dr_policy_value(
                    treatment[idx], y[idx], score[idx], mu1[idx], mu0[idx], g[idx], budget or 1.0
                )
            )
    return percentile_ci(stats)


def run_single_protocol(cfg: UpliftConfig) -> dict[str, Any]:
    """Run the four-learner comparison and write reports/single_protocol/."""
    frame_path = cfg.data_dir / "hillstrom.parquet"
    scores_path = cfg.data_dir / "scores.parquet"
    df = pl.read_parquet(frame_path).to_pandas()
    committed = pd.read_parquet(scores_path)
    X = df[cfg.feature_cols]
    treatment = df["treatment"].to_numpy(dtype=int)
    y = df["conversion"].to_numpy(dtype=float)

    with threadpool_limits(limits=1):
        nuisances = cross_fit_arm_predictions(X, treatment, y, folds=cfg.cv_folds, seed=cfg.seed)
    mu1, mu0, g = nuisances["mu1"], nuisances["mu0"], nuisances["g"]
    recomputed_t = mu1 - mu0
    if not np.allclose(recomputed_t, committed["t_learner"].to_numpy(), atol=1e-6):
        raise ValueError("recomputed T-learner does not match committed scores — folds differ")

    psi = dr_pseudo_outcomes(treatment, y, mu1, mu0, g)

    def fit_forest(x_tr: pd.DataFrame, psi_tr: np.ndarray) -> Pipeline:
        model = Pipeline(
            [
                ("prep", make_preprocess()),
                (
                    "rf",
                    RandomForestRegressor(
                        n_estimators=FOREST_TREES,
                        min_samples_leaf=FOREST_LEAF,
                        random_state=cfg.seed,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
        model.fit(x_tr, psi_tr)
        return model

    # Cross-fit the forest on the same folds so its scores are out-of-fold like
    # the committed T/X columns (an in-sample DR-forest fit would read
    # optimistically against the pure OOF scores).
    kfold = KFold(n_splits=cfg.cv_folds, shuffle=True, random_state=cfg.seed)
    forest_oof = np.full(len(y), np.nan)
    for fold, (train_idx, test_idx) in enumerate(kfold.split(X)):
        model = fit_forest(X.iloc[train_idx], psi[train_idx])
        forest_oof[test_idx] = model.predict(X.iloc[test_idx])
        log.info("DR-forest cross-fit: fold %d/%d scored", fold + 1, cfg.cv_folds)
    if np.isnan(forest_oof).any():
        raise ValueError("forest cross-fitting left un-scored rows")
    # Full-sample forest for serving-style inspection is not persisted; the
    # comparison uses the OOF scores only.

    learners: dict[str, np.ndarray] = {
        "dr_learner": forest_oof,
        "t_learner_two_model": committed["t_learner"].to_numpy(),
        "x_learner": committed["x_learner"].to_numpy(),
    }

    per_learner: dict[str, Any] = {}
    for name, score in learners.items():
        area = qini_coefficient(treatment, y, score)
        area_ci = bootstrap_metric(treatment, y, score, "qini_area", mu1, mu0, g, None)
        fr, inc = qini_points(treatment, y, score)
        dr_by_budget = []
        for budget in cfg.budget_fractions:
            value = dr_policy_value(treatment, y, score, mu1, mu0, g, budget)
            ci = bootstrap_metric(treatment, y, score, "dr_value", mu1, mu0, g, budget)
            dr_by_budget.append({"budget": float(budget), "dr_value": value, "ci95": ci})
        per_learner[name] = {
            "qini_area_auuc": area,
            "qini_area_auuc_ci95": area_ci,
            "dr_policy_value_by_budget": dr_by_budget,
            "curve": {"fractions": fr.tolist(), "incremental": inc.tolist()},
        }
        log.info("%s: qini area %.4f %s", name, area, area_ci)

    report: dict[str, Any] = {
        "schema_version": "single-protocol-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "data_source": "committed folds (cfg.seed=42, cv_folds=5, OOF convention)",
        "n_rows": len(y),
        "outcome": "conversion",
        "formula_qini_area_auuc": (
            "area between the incremental-conversions curve and the random line "
            "(unnormalised; qini.qini_coefficient == AUQC - AUQC(random))"
        ),
        "formula_dr_pseudo_outcome": "psi = (mu1-mu0) + T(y-mu1)/g - (1-T)(y-mu0)/(1-g)",
        "dr_learner_definition": (
            "hand-rolled DR-learner forest (sklearn RandomForestRegressor on DR "
            "pseudo-outcomes, cross-fitted on the committed folds; no grf/econml, "
            "per DESIGN.md no-heavyweight-deps)"
        ),
        "t_two_model_note": (
            "the two-model approach and the T-learner are the same estimator "
            "family; one committed OOF column carries both labels"
        ),
        "learners": per_learner,
        "verification": {
            "recomputed_t_learner_matches_committed": True,
            "tolerance": 1e-6,
        },
    }
    out_dir = cfg.reports_dir / "single_protocol"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    log.info("wrote %s", out_dir / "metrics.json")
    return report


def write_report_markdown(report: dict[str, Any], out_dir: Path) -> None:
    """Short human-readable companion to metrics.json."""
    lines = [
        "# Q4a single-protocol uplift comparison",
        "",
        f"Generated: {report['generated_at']} · n = {report['n_rows']} rows · "
        f"outcome: {report['outcome']} · {report['data_source']}",
        "",
        "Qini area (AUUC), unnormalised — " + report["formula_qini_area_auuc"] + ".",
        "",
        "| learner | Qini area (AUUC) | 95% bootstrap CI |",
        "|---|---|---|",
    ]
    for name, block in report["learners"].items():
        ci = block["qini_area_auuc_ci95"]
        lines.append(f"| {name} | {block['qini_area_auuc']:.4f} | [{ci[0]:.4f}, {ci[1]:.4f}] |")
    lines += [
        "",
        "Notes:",
        f"- DR-learner forest: {report['dr_learner_definition']}.",
        f"- {report['t_two_model_note']}.",
        "- DR pseudo-outcome: " + report["formula_dr_pseudo_outcome"] + ".",
        "- DR policy value by budget (with intervals) is in `metrics.json` per learner.",
        "- New files only; no committed record was modified.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
