"""Q4b risk-coverage / AURC for the transformer on the fresh holdout.

Selective-classification read the portfolio lacked: for the headline
full-data transformer (``distilbert_full_120k``), score the committed fresh
holdout (re-drawn exactly by :func:`draw_fresh_holdout`), take max-softmax
confidence, and compute the risk-coverage curve plus the AURC (area under
risk vs coverage) with a paired row-bootstrap interval.

Identity check: the recomputed fresh macro-F1 must equal the committed
``reports/fresh_holdout.json → runs.distilbert_full_120k.f1_macro`` before
the curve is trusted.

Output: NEW files under ``reports/risk_coverage/`` only. Compute-only,
deterministic (seed 42), CPU.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import numpy as np
from portfolio_core.logging import get_logger
from sklearn.metrics import f1_score

from nlp_classification.config import NLPConfig
from nlp_classification.data import LABEL_COLUMN, load_ag_news
from nlp_classification.fresh_holdout import (
    _load_label_names,
    _proba_distilbert,
    draw_fresh_holdout,
)
from nlp_classification.model import FULLDATA_MODEL_PATH

log = get_logger(__name__)

BOOTSTRAP_REPS = 2000
# compact table: risk (1 - accuracy) on the most-confident prefix at these
# coverage levels.
COVERAGE_LEVELS = [1.0, 0.9, 0.75, 0.5, 0.25]


def risk_coverage_curve(y_true: np.ndarray, proba: np.ndarray) -> dict[str, np.ndarray]:
    """Risk (1 - accuracy) on the most-confident prefix at every coverage."""
    conf = proba.max(axis=1)
    correct = (proba.argmax(axis=1) == y_true).astype(float)
    order = np.argsort(-conf, kind="stable")
    corr_sorted = correct[order]
    n = len(y_true)
    prefix_correct = np.cumsum(corr_sorted)
    counts = np.arange(1, n + 1)
    risk = 1.0 - prefix_correct / counts
    coverage = counts / n
    return {"coverage": coverage, "risk": risk}


def aurc(coverage: np.ndarray, risk: np.ndarray) -> float:
    """Area under the risk-coverage curve (mean risk over the sweep)."""
    return float(np.trapezoid(risk, coverage))


def aurc_bootstrap(
    y_true: np.ndarray, proba: np.ndarray, reps: int = BOOTSTRAP_REPS, seed: int = 42
) -> list[float]:
    rng = np.random.default_rng(seed)
    n = len(y_true)
    stats = []
    for _ in range(reps):
        idx = rng.integers(0, n, n)
        curve = risk_coverage_curve(y_true[idx], proba[idx])
        stats.append(aurc(curve["coverage"], curve["risk"]))
    stats.sort()
    return [stats[int(0.025 * len(stats))], stats[int(0.975 * len(stats)) - 1]]


def risk_at_coverage(curve: dict[str, np.ndarray], coverage: float) -> float:
    """Risk on the most-confident prefix containing ``coverage`` of the rows."""
    n = len(curve["coverage"])
    k = max(1, round(coverage * n))
    return float(curve["risk"][k - 1])


def run_risk_coverage(cfg: NLPConfig) -> dict[str, Any]:
    """Run the risk-coverage read and write reports/risk_coverage/."""
    raw_test = load_ag_news()["test"]
    fresh, provenance = draw_fresh_holdout(cfg, raw_test)
    n_labels = len(_load_label_names(cfg.data_dir))
    y_true = np.asarray([int(v) for v in fresh[LABEL_COLUMN]])
    proba = _proba_distilbert(cfg, cfg.models_dir / FULLDATA_MODEL_PATH, fresh, n_labels)
    pred = proba.argmax(axis=1)
    f1 = float(f1_score(y_true, pred, average="macro"))
    committed = json.loads((cfg.reports_dir / "fresh_holdout.json").read_text())
    committed_f1 = float(committed["runs"]["distilbert_full_120k"]["f1_macro"])
    if abs(f1 - committed_f1) > 1e-4:
        raise ValueError(f"fresh macro-F1 {f1} != committed {committed_f1} — draw/scoring drift")

    curve = risk_coverage_curve(y_true, proba)
    area = aurc(curve["coverage"], curve["risk"])
    ci = aurc_bootstrap(y_true, proba)
    table = [
        {
            "coverage": coverage,
            "risk": risk_at_coverage(curve, coverage),
        }
        for coverage in COVERAGE_LEVELS
    ]
    report: dict[str, Any] = {
        "schema_version": "risk-coverage-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "model": "distilbert_full_120k",
        "confidence_score": "max softmax probability",
        "n_fresh": len(y_true),
        "fresh_macro_f1_recomputed": f1,
        "fresh_macro_f1_committed": committed_f1,
        "verification": {"matches_committed": True, "tolerance": 1e-4},
        "aurc": area,
        "aurc_ci95": ci,
        "coverage_at_coverage_levels": table,
        "curve": {
            "coverage": curve["coverage"].tolist(),
            "risk": curve["risk"].tolist(),
        },
        "provenance": provenance,
        "notes": (
            "AURC = area under risk vs coverage (mean risk over the full sweep, "
            "coverage 1/n..1). Lower is better; 0 means perfect ordering. The "
            "fresh holdout is diagnostic; no selection used it."
        ),
    }
    out_dir = cfg.reports_dir / "risk_coverage"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")

    lines = [
        "# Q4b risk-coverage / AURC — distilbert_full_120k on the fresh holdout",
        "",
        f"Generated: {report['generated_at']} · n = {report['n_fresh']} · "
        f"confidence: {report['confidence_score']}",
        "",
        f"- Fresh macro-F1 recomputed {f1:.7f} == committed {committed_f1:.7f} "
        "(identity verified).",
        f"- **AURC = {area:.4f}**, bootstrap 95% [{ci[0]:.4f}, {ci[1]:.4f}] "
        "(mean risk over the coverage sweep; lower is better).",
        "",
        "| coverage (most-confident prefix) | risk (1 - accuracy) |",
        "|---|---|",
    ]
    for row in table:
        lines.append(f"| {row['coverage']:.2f} | {row['risk']:.4f} |")
    lines += [
        "",
        "New files only; no committed record modified. Full curve in `metrics.json`.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    log.info("wrote %s (AURC %.4f %s)", out_dir, area, ci)
    return report
