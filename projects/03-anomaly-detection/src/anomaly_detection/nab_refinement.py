"""Refinement ablation at the fixed 2% alert budget (roadmap wave 17).

The headline NAB pass thresholds IsolationForest scores at the train-window
98th percentile — one raw cut per series. Raw score distributions drift per
hour of week, so this stage measures three detector-layer refinements, each
behind the committed evaluation protocol (70/30 past-only split, train-anchored
budget, lead 0, mean over all 12 series, raw/deduped/budgeted streams):

- ``isolation_forest`` — the committed recipe, re-run as the in-artifact
  baseline so every comparison is apples-to-apples;
- ``if_calibrated`` — conformal calibration: convert each score to an
  empirical p-value against the *non-anomalous* train scores of its own
  hour-of-week context (train minutes inside labelled windows are excluded —
  labels define the calibration set, they never set the threshold value),
  then cut at the budget quantile of the pooled calibration p-values instead
  of the raw score quantile. Fallback chain: thin/absent context →
  series-global calibration → the committed raw cut;
- ``fusion_if_lof`` — rank fusion: the mean of per-window normalized ranks
  under IsolationForest and LOF (the sweep's untuned fits — NAB carries no
  tuned variants by convention), thresholded by the same budget rule on the
  fused reference scores;
- ``fusion_if_lof_norm`` — fusion after z-normalizing each member's scores
  within its hour-of-week context (train statistics, same fallback chain).

Adoption gate: a candidate is adopted only if, against the in-artifact
baseline on identical windows, both pointwise precision at the 2% budget and
event range-F1 improve while incident coverage (windows touched) holds at
16/17. If nothing clears the gate the committed detector stands and the
artifact records the negative result — that is a designed outcome, not a
failure. Artifact: ``reports/nab_refinement.json``.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import polars as pl
from portfolio_core.logging import get_logger
from sklearn.metrics import average_precision_score, roc_auc_score

from anomaly_detection.config import AnomalyConfig
from anomaly_detection.nab import (
    LEAD_STEPS,
    build_series_features,
    match_events,
    windows_to_mask,
)
from anomaly_detection.nab_sweep import (
    COOLDOWN_HOURS,
    _aggregate_runs,
    _ranks,
    _stream_metrics,
    cooldown_budget,
    episode_firing_times,
    fit_detector,
)
from anomaly_detection.nab_tune import _iter_series

logger = get_logger(__name__)

BASELINE = "isolation_forest"
IF_CALIBRATED = "if_calibrated"
FUSION = "fusion_if_lof"
FUSION_NORM = "fusion_if_lof_norm"
CANDIDATES: tuple[str, ...] = (BASELINE, IF_CALIBRATED, FUSION, FUSION_NORM)
REFINED: tuple[str, ...] = (IF_CALIBRATED, FUSION, FUSION_NORM)
FUSION_MEMBERS: tuple[str, ...] = ("isolation_forest", "lof")
FEATURE_SET = "rolling_residual"  # the headline recipe; the sweep owns the feature axis

GLOBAL_CONTEXT = -1  # fallback bucket for thin/absent hour-of-week contexts


def hour_of_week(times: np.ndarray) -> np.ndarray:
    """Hour-of-week bucket 0 (Mon 00:00) … 167 (Sun 23:00); NaT → -1.

    Epoch day 0 (1970-01-01) was a Thursday, hence the +3 weekday offset.
    """
    nat = np.isnat(times)
    safe = np.where(nat, np.datetime64("1970-01-01"), times)
    days = safe.astype("datetime64[D]")
    hours = ((safe - days) / np.timedelta64(1, "h")).astype(np.int64)
    weekday = ((days - np.datetime64("1970-01-01")).astype(np.int64) + 3) % 7
    return np.where(nat, GLOBAL_CONTEXT, weekday * 24 + hours)


@dataclass
class ContextCalibration:
    """Non-anomalous train-window scores bucketed by hour-of-week context.

    Thin buckets (fewer than ``min_context`` scores) and unseen contexts fall
    back to the series-global set; an empty global set means no calibration
    exists and callers must take the committed raw cut instead.
    """

    contexts: dict[int, np.ndarray]
    fallback: np.ndarray
    min_context: int
    n_thin: int = field(default=0)

    def _reference(self, ctx: int) -> np.ndarray:
        ref = self.contexts.get(ctx)
        return ref if ref is not None and ref.size >= self.min_context else self.fallback

    def pvalues(self, scores: np.ndarray, contexts: np.ndarray) -> np.ndarray | None:
        """Empirical conformal p-values (higher = more normal), or None when
        no calibration exists at all. Ties share a p-value, so the mapping
        score → p is monotonically non-increasing."""
        if self.fallback.size == 0:
            return None
        out = np.empty(len(scores), dtype=float)
        for ctx in np.unique(contexts):
            ref = self._reference(int(ctx))
            sel = contexts == ctx
            # +1 correction: a test score above every reference has p = 1/(n+1), never 0.
            out[sel] = [
                (1.0 + float((ref >= value).sum())) / (ref.size + 1.0) for value in scores[sel]
            ]
        return out

    def zscores(self, scores: np.ndarray, contexts: np.ndarray) -> np.ndarray:
        """Standardize per context (train mean/std); degenerate spread falls
        back to the global std, then to the raw scores."""
        out = scores.astype(float).copy()
        global_sd = float(self.fallback.std()) if self.fallback.size else 0.0
        global_mu = float(self.fallback.mean()) if self.fallback.size else 0.0
        for ctx in np.unique(contexts):
            ref = self._reference(int(ctx))
            sel = contexts == ctx
            if ref.size >= 2 and float(ref.std()) > 0.0:
                out[sel] = (scores[sel] - float(ref.mean())) / float(ref.std())
            elif global_sd > 0.0:
                out[sel] = (scores[sel] - global_mu) / global_sd
        return out


def fit_context_calibration(
    ref_scores: np.ndarray,
    ref_contexts: np.ndarray,
    ref_anomalous: np.ndarray,
    min_context: int,
) -> ContextCalibration:
    """Bucket the non-anomalous train scores by hour-of-week context.

    ``ref_anomalous`` marks train minutes inside labelled windows; those
    scores are excluded so incidents never enter the reference distribution.
    """
    normal = ~ref_anomalous
    contexts = {
        int(ctx): ref_scores[(ref_contexts == ctx) & normal] for ctx in np.unique(ref_contexts)
    }
    fallback = ref_scores[normal]
    n_thin = sum(1 for c in contexts.values() if c.size < min_context)
    return ContextCalibration(contexts, fallback, min_context, n_thin=n_thin)


def _alert_stream(
    scores: np.ndarray,
    alert_idx: np.ndarray,
    ts_test: np.ndarray,
    windows: list[list[str]],
    step_ns: float,
    evaluable: bool,
    cooldown_hours: float = COOLDOWN_HOURS,
) -> dict[str, Any]:
    """The three alert streams plus pointwise precision at the budget.

    Mirrors the sweep's stream ladder; ``precision_at_budget`` is the share of
    raw-stream alerts landing inside labelled windows (the metric the adoption
    gate prices), which the shared ``_stream_metrics`` does not retain.
    """
    firings, n_runs = episode_firing_times(alert_idx, scores)
    budgeted = cooldown_budget(firings, step_ns, cooldown_hours=cooldown_hours)
    precision_at_budget = 0.0
    if evaluable:
        _, in_window = match_events(ts_test[alert_idx], windows, LEAD_STEPS, step_ns)
        if alert_idx.size:
            precision_at_budget = float(in_window.sum() / alert_idx.size)
    return {
        "precision_at_budget": precision_at_budget,
        "raw": _stream_metrics(
            alert_idx, int(alert_idx.size), ts_test, windows, step_ns, evaluable
        ),
        "deduped": _stream_metrics(firings, n_runs, ts_test, windows, step_ns, evaluable),
        "budgeted": _stream_metrics(
            budgeted, int(budgeted.size), ts_test, windows, step_ns, evaluable
        ),
    }


def evaluate_refinement_series(
    df: pl.DataFrame,
    windows: list[list[str]],
    config: AnomalyConfig,
    candidate: str,
) -> dict[str, Any]:
    """One (candidate, series) run at the fixed budget: score, threshold, streams.

    Every candidate shares the headline data path (``rolling_residual``
    features, 70/30 split, seeded fits through the sweep's ``fit_detector``)
    so the only difference against the baseline is the decision layer under
    test.
    """
    feat = build_series_features(df, config.windows, feature_set=FEATURE_SET)
    n_train = int(feat.height * config.train_frac)
    if feat.height - n_train < max(config.windows):
        raise ValueError(f"series too short after feature build: {feat.height} rows")
    cols = [c for c in feat.columns if c != "timestamp"]
    x = feat.select(cols).to_numpy()
    times = feat["timestamp"].to_numpy()
    y = windows_to_mask(times, windows)

    budget = config.contamination
    ts_train, ts_test = times[:n_train], times[n_train:]
    y_test = y[n_train:]
    t0 = ts_test[0]
    test_windows = [w for w in windows if np.datetime64(datetime.fromisoformat(w[1])) >= t0]
    evaluable = len(test_windows) > 0
    has_positives = bool(y_test.any())
    step_ns = float(np.median(np.diff(times.astype("datetime64[ns]"))))

    scorers = {
        name: fit_detector(name, x[:n_train], config)
        for name in ({BASELINE} | set(FUSION_MEMBERS) if candidate != BASELINE else {BASELINE})
    }
    ref_if = scorers[BASELINE](x[:n_train])
    scores_if = scorers[BASELINE](x[n_train:])
    calibration_info: dict[str, Any] = {}

    if candidate == BASELINE:
        threshold = float(np.quantile(ref_if, 1.0 - budget))
        alert_idx = np.flatnonzero(scores_if >= threshold)
        auc_scores = scores_if
    elif candidate == IF_CALIBRATED:
        calib = fit_context_calibration(
            ref_if,
            hour_of_week(ts_train),
            windows_to_mask(ts_train, windows),
            config.calibration_min_context,
        )
        calibration_info = {
            "n_contexts": sum(1 for c in calib.contexts.values() if c.size >= calib.min_context),
            "n_thin_contexts": calib.n_thin,
            "n_fallback_scores": int(calib.fallback.size),
        }
        p_ref = calib.pvalues(ref_if, hour_of_week(ts_train))
        p_test = calib.pvalues(scores_if, hour_of_week(ts_test))
        if p_ref is None or p_test is None:  # no non-anomalous reference: committed raw cut
            threshold = float(np.quantile(ref_if, 1.0 - budget))
            alert_idx = np.flatnonzero(scores_if >= threshold)
            auc_scores = scores_if
            calibration_info["fell_back_to_raw_cut"] = True
        else:
            threshold = float(np.quantile(p_ref, budget))
            alert_idx = np.flatnonzero(p_test <= threshold)
            auc_scores = 1.0 - p_test
    else:  # FUSION / FUSION_NORM: mean rank of the two members, budget rule on the fused ref
        member_scorers = [scorers[name] for name in FUSION_MEMBERS]
        if candidate == FUSION_NORM:
            calib = fit_context_calibration(
                ref_if,
                hour_of_week(ts_train),
                windows_to_mask(ts_train, windows),
                config.calibration_min_context,
            )
            ref_ctx, test_ctx = hour_of_week(ts_train), hour_of_week(ts_test)
            z_ref = [calib.zscores(scorer(x[:n_train]), ref_ctx) for scorer in member_scorers]
            z_test = [calib.zscores(scorer(x[n_train:]), test_ctx) for scorer in member_scorers]
            fused_ref = np.mean([_ranks(a) for a in z_ref], axis=0)
            fused_test = np.mean([_ranks(a) for a in z_test], axis=0)
        else:
            fused_ref = np.mean([_ranks(scorer(x[:n_train])) for scorer in member_scorers], axis=0)
            fused_test = np.mean([_ranks(scorer(x[n_train:])) for scorer in member_scorers], axis=0)
        threshold = float(np.quantile(fused_ref, 1.0 - budget))
        alert_idx = np.flatnonzero(fused_test >= threshold)
        auc_scores = fused_test

    streams = _alert_stream(auc_scores, alert_idx, ts_test, test_windows, step_ns, evaluable)
    return {
        "candidate": candidate,
        "n_points": int(feat.height),
        "n_test": len(y_test),
        "n_windows": len(test_windows),
        "evaluable": evaluable,
        "point_prevalence": float(y_test.mean()),
        "pr_auc": float(average_precision_score(y_test, auc_scores)) if has_positives else None,
        "roc_auc": float(roc_auc_score(y_test, auc_scores)) if has_positives else None,
        "threshold": threshold,
        "threshold_budget": float(budget),
        "precision_at_budget": streams.pop("precision_at_budget"),
        "streams": streams,
        **calibration_info,
    }


def _aggregate_candidates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Sweep-style aggregation plus the gate metric (mean over all 12 series,
    non-evaluable contributing 0, matching ``nab._aggregate``)."""
    base = _aggregate_runs(rows)
    base["precision_at_budget"] = float(np.mean([r["precision_at_budget"] for r in rows]))
    return base


def decide_adoption(baseline: dict[str, Any], refined: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The adoption gate, evaluated in code.

    A candidate is adoptable only when it beats the baseline on BOTH
    precision at budget AND event range-F1 while holding incident coverage
    (windows touched). Among adoptable candidates the gate takes the highest
    range-F1, then precision, then declaration order; ``adopted=None`` is the
    designed negative-result path.
    """
    reasons: dict[str, str] = {}
    adoptable: list[str] = []

    def coverage(row: dict[str, Any]) -> str:
        return f"{row['events_detected']}/{row['events_detected'] + row['events_missed']}"

    for name in REFINED:
        cand = refined[name]
        coverage_ok = cand["events_detected"] >= baseline["events_detected"]
        precision_ok = cand["precision_at_budget"] > baseline["precision_at_budget"]
        f1_ok = cand["range_f1"] > baseline["range_f1"]
        reasons[name] = (
            f"coverage {coverage(cand)} vs baseline {coverage(baseline)} "
            f"({'ok' if coverage_ok else 'FAIL'}); "
            f"precision@budget {cand['precision_at_budget']:.3f} vs "
            f"{baseline['precision_at_budget']:.3f} ({'ok' if precision_ok else 'FAIL'}); "
            f"range-F1 {cand['range_f1']:.3f} vs {baseline['range_f1']:.3f} "
            f"({'ok' if f1_ok else 'FAIL'})"
        )
        if coverage_ok and precision_ok and f1_ok:
            adoptable.append(name)
    adopted = min(
        adoptable,
        key=lambda n: (
            -refined[n]["range_f1"],
            -refined[n]["precision_at_budget"],
            REFINED.index(n),
        ),
        default=None,
    )
    return {"adopted": adopted, "reasons": reasons}


def run_nab_refinement(config: AnomalyConfig) -> dict[str, Any]:
    """The refinement stage: every candidate on every series, one artifact."""
    keyed: dict[str, dict[str, dict[str, Any]]] = {c: {} for c in CANDIDATES}
    for key, df, windows in _iter_series(config):
        for candidate in CANDIDATES:
            keyed[candidate][key] = evaluate_refinement_series(df, windows, config, candidate)
        base = keyed[BASELINE][key]
        logger.info(
            "%s: baseline %d raw alerts vs fusion %d (%s)",
            key,
            base["streams"]["raw"]["alerts_fired"],
            keyed[FUSION][key]["streams"]["raw"]["alerts_fired"],
            "evaluable" if base["evaluable"] else "not evaluable",
        )

    candidates: dict[str, Any] = {}
    for candidate in CANDIDATES:
        rows = list(keyed[candidate].values())
        by_family: dict[str, list[dict[str, Any]]] = {}
        for key, r in keyed[candidate].items():
            by_family.setdefault(key.split("/")[0], []).append(r)
        entry: dict[str, Any] = {
            "overall": _aggregate_candidates(rows),
            "by_family": {family: _aggregate_candidates(rs) for family, rs in by_family.items()},
        }
        if candidate == IF_CALIBRATED:  # why the calibration redistributed the budget
            entry["calibration"] = {
                "n_thin_contexts_total": int(sum(r["n_thin_contexts"] for r in rows)),
                "series_on_raw_cut_fallback": int(
                    sum(1 for r in rows if r.get("fell_back_to_raw_cut"))
                ),
            }
        candidates[candidate] = entry

    baseline_overall = candidates[BASELINE]["overall"]
    adoption = decide_adoption(baseline_overall, {c: candidates[c]["overall"] for c in REFINED})
    verdict = (
        f"adopted {adoption['adopted']}"
        if adoption["adopted"]
        else "no candidate clears the gate; the committed detector stands"
    )

    report: dict[str, Any] = {
        "data_source": "nab",
        "stage": "nab_refinement",
        "protocol": {
            "split": "first 70% train / last 30% test per series (past-only)",
            "feature_set": FEATURE_SET,
            "threshold_budget": config.contamination,
            "cooldown_hours": COOLDOWN_HOURS,
            "lead_steps": LEAD_STEPS,
            "aggregation": "mean over all 12 series (non-evaluable contribute 0)",
            "calibration": (
                "conformal p-values against non-anomalous train scores of the same "
                "hour-of-week context; threshold at the budget quantile of pooled "
                "calibration p-values; fallback chain thin/absent context → "
                "series-global calibration → committed raw cut"
            ),
            "calibration_min_context": config.calibration_min_context,
            "fusion_members": list(FUSION_MEMBERS),
            "candidates": list(CANDIDATES),
            "adoption_gate": (
                "adopt only if precision@budget and range-F1 both improve over the "
                "in-artifact baseline while windows touched stays at or above the "
                "baseline's 16/17"
            ),
        },
        "adoption": {**adoption, "verdict": verdict},
        "candidates": candidates,
        "series": {
            f"{key}|{candidate}": row
            for candidate in CANDIDATES
            for key, row in keyed[candidate].items()
        },
    }
    out = config.reports_path / "nab_refinement.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    logger.info("wrote %s — %s", out, verdict)
    return report
