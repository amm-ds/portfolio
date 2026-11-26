"""Official NAB score for the committed NAB track, via the vendored scorer.

The committed detectors emit per-timestamp scores only inside
``anomaly_detection.nab.evaluate_series`` (they are not persisted), so this
stage recomputes them exactly as ``run_nab`` does — same checksum-pinned
series, same ``AnomalyConfig`` (seed, contamination, estimators, windows,
train fraction), same IsolationForest recipe — and refuses to score unless
the recomputed per-series alert counts reproduce the committed
``reports/nab_metrics.json`` exactly (1,609 raw alerts in total).

The vendored official NAB scorer (``anomaly_detection.vendor.nab_scorer``,
ported from numenta/NAB at a pinned commit — see ``vendor/VENDORED.md``) then
scores the nine series that have labelled windows in the scored span, under
the three upstream application profiles (standard, reward_low_FP_rate,
reward_low_FN_rate). The synthetic telemetry stream with injected anomalies
is never part of the official score.

Corpus mapping (documented in the artifact):

- The scored span per series is the post-training 30% the committed pipeline
  scores; the 70% train split plays the role of NAB's probationary period,
  so the sweeper runs with ``probation_percent = 0``.
- Label windows come from the vendored ``nab_combined_windows.json`` (same
  sha256 the ``nab`` stage pins). One window (``realKnownCause/nyc_taxi``,
  first window) starts inside the train span and is clipped to the first
  scored timestamp, matching the committed metrics' "windows overlapping the
  scored portion" semantics.
- Thresholds are optimized per profile over the pooled nine-series corpus,
  exactly as upstream ``optimizeThreshold`` does; scores are normalized as
  ``100 * (raw - null) / (perfect - null)`` (upstream ``Runner.normalize``).

Sanity gates (upstream definitions): the null detector (constant 0.5) must
normalize to 0 and the perfect detector (fires only at window starts) to 100
under every profile; any deviation aborts the run before anything is written.

Artifacts: ``reports/nab_official_score.json`` (scores, thresholds, counts,
sanity results, provenance) and ``reports/nab_official_scores.json`` (the
per-series timestamps/scores/windows the score was computed from, so the
committed score is re-verifiable offline).
"""

import json
from importlib import resources
from pathlib import Path
from typing import Any, Literal

import numpy as np
from portfolio_core.logging import get_logger

from anomaly_detection.config import AnomalyConfig
from anomaly_detection.nab import (
    NAB_LABELS_SHA256,
    NAB_SERIES,
    evaluate_series,
    fetch_labels,
    fetch_series,
    parse_series_csv,
)
from anomaly_detection.vendor import nab_scorer

logger = get_logger(__name__)

UPSTREAM_REPO = "https://github.com/numenta/NAB"
UPSTREAM_COMMIT = "ea702d75cc2258d9d7dd35ca8e5e2539d71f3140"

# The 70% train split precedes the scored span and plays the probation role.
PROBATION_PERCENT = 0.0
# Recomputed metrics must reproduce the committed ones (floats) ...
VERIFY_TOLERANCE = 1e-12
# ... and the null/perfect sanity gates must hold (normalized scores).
SANITY_TOLERANCE = 1e-9

SCORE_PATH = "nab_official_score.json"
SCORES_PATH = "nab_official_scores.json"


def _load_vendored_json(name: str) -> Any:
    return json.loads(resources.files("anomaly_detection.vendor").joinpath(name).read_text())


def load_profiles() -> dict[str, dict[str, float]]:
    """The three upstream application profiles (cost matrices).

    Upstream nests each profile's matrix under ``CostMatrix`` (see
    ``Runner.optimize``); this unwraps it.
    """
    raw: dict[str, dict[str, dict[str, float]]] = _load_vendored_json("nab_profiles.json")
    return {name: profile["CostMatrix"] for name, profile in raw.items()}


def load_official_windows() -> dict[str, list[list[str]]]:
    """Upstream ``labels/combined_windows.json`` (vendored, checksum-pinned)."""
    windows: dict[str, list[list[str]]] = _load_vendored_json("nab_combined_windows.json")
    return windows


def recompute_nab_results(config: AnomalyConfig) -> dict[str, dict[str, Any]]:
    """Refit and score all committed series exactly as ``run_nab`` does."""
    labels = fetch_labels(config)
    results: dict[str, dict[str, Any]] = {}
    for family, series_list in NAB_SERIES.items():
        for name, sha256 in series_list:
            key = f"{family}/{name}"
            df = parse_series_csv(fetch_series(config, family, name, sha256))
            results[key] = evaluate_series(df, labels[f"{key}.csv"], config)
    return results


def verify_against_committed(
    results: dict[str, dict[str, Any]], committed: dict[str, Any]
) -> dict[str, Any]:
    """Stop condition: recomputed metrics must equal the committed artifact.

    Counts must match exactly; float metrics within ``VERIFY_TOLERANCE``.
    Raises ``ValueError`` on any mismatch — scoring must not proceed on a
    drifted detector.
    """
    mismatches: list[str] = []
    for key, row in committed["series"].items():
        r = results[key]
        for field in ("n_test", "n_windows", "alerts_fired", "events_detected", "events_missed"):
            if r[field] != row[field]:
                mismatches.append(f"{key}.{field}: recomputed {r[field]} != committed {row[field]}")
        for field in ("range_precision", "range_recall", "range_f1"):
            if abs(r[field] - row[field]) > VERIFY_TOLERANCE:
                mismatches.append(f"{key}.{field}: recomputed {r[field]} != committed {row[field]}")
    total = sum(r["alerts_fired"] for r in results.values())
    committed_total = int(committed["overall"]["alerts_fired"])
    if total != committed_total:
        mismatches.append(f"total alerts_fired: recomputed {total} != committed {committed_total}")
    if mismatches:
        raise ValueError(
            "recomputed NAB metrics drifted from the committed nab_metrics.json; "
            "refusing to score:\n" + "\n".join(mismatches)
        )
    return {
        "series_checked": len(results),
        "alerts_fired_total": total,
        "tolerance": VERIFY_TOLERANCE,
        "committed_source": "reports/nab_metrics.json",
    }


def _ns(ts: np.datetime64) -> int:
    return int(ts.astype("datetime64[ns]").astype(np.int64))


def _parse_window_bound(bound: str) -> int:
    return _ns(np.datetime64(bound.replace(" ", "T")))


def _iso(ns: int) -> str:
    return str(np.datetime64(ns, "ns").astype("datetime64[s]"))


def build_scoring_corpus(
    results: dict[str, dict[str, Any]], committed: dict[str, Any]
) -> tuple[list[nab_scorer.SeriesInput], list[dict[str, Any]], list[str]]:
    """Nine evaluable series → scorer inputs with test-span-clipped windows.

    Returns the corpus, the clip records (for the artifact), and the excluded
    (train-only) series keys.
    """
    corpus: list[nab_scorer.SeriesInput] = []
    clips: list[dict[str, Any]] = []
    excluded: list[str] = []
    for key, row in committed["series"].items():
        r = results[key]
        if bool(row["evaluable"]) != bool(r["evaluable"]):
            raise ValueError(f"{key}: evaluable flag drifted vs committed metrics")
        if not row["evaluable"]:
            excluded.append(key)
            continue
        ts_ns = [_ns(t) for t in r["ts_test"]]
        ts_set = set(ts_ns)
        scores = [float(s) for s in r["scores"]]
        if not scores or max(scores) >= nab_scorer.INITIAL_THRESHOLD:
            raise ValueError(f"{key}: detector scores must stay below the sweep's initial 1.1")
        # The committed windows overlap the scored span; the scorer needs both
        # bounds inside it, so a window starting in the train span is clipped
        # to the first scored timestamp.
        windows: list[tuple[int, int]] = []
        for start_s, end_s in row["windows"]:
            start, end = _parse_window_bound(start_s), _parse_window_bound(end_s)
            clipped_start = max(start, ts_ns[0])
            if clipped_start != start:
                clips.append(
                    {
                        "series": key,
                        "label_window": [start_s, end_s],
                        "scored_window": [_iso(clipped_start), _iso(end)],
                        "reason": (
                            "window starts inside the train span; "
                            "clipped to the first scored timestamp"
                        ),
                    }
                )
            if clipped_start not in ts_set or end not in ts_set:
                raise ValueError(f"{key}: window bounds must be scored timestamps")
            if windows and clipped_start <= windows[-1][1]:
                raise ValueError(
                    f"{key}: windows must be sorted and non-overlapping after clipping"
                )
            windows.append((clipped_start, end))
        corpus.append(nab_scorer.SeriesInput(key, ts_ns, scores, windows))
    return corpus, clips, excluded


def _baseline_corpus(
    corpus: list[nab_scorer.SeriesInput], kind: Literal["null", "perfect"]
) -> list[nab_scorer.SeriesInput]:
    out = []
    for s in corpus:
        if kind == "null":
            scores = nab_scorer.null_detector_scores(len(s.timestamps))
        else:
            scores = nab_scorer.perfect_detector_scores(s.timestamps, s.windows)
        out.append(nab_scorer.SeriesInput(s.name, s.timestamps, scores, s.windows))
    return out


def score_profiles(corpus: list[nab_scorer.SeriesInput]) -> dict[str, Any]:
    """Optimize + score detector, null, and perfect under each profile.

    Applies the sanity gates (null → 0, perfect → 100 normalized) and raises
    before any artifact is written if the port misbehaves.
    """
    profiles = load_profiles()
    null_corpus = _baseline_corpus(corpus, "null")
    perfect_corpus = _baseline_corpus(corpus, "perfect")
    tp_count = sum(len(s.windows) for s in corpus)

    out: dict[str, Any] = {}
    sanity: dict[str, dict[str, float]] = {"null": {}, "perfect": {}}
    for profile_name, cost_matrix in profiles.items():
        tp_weight = cost_matrix["tpWeight"]
        perfect_possible = nab_scorer.perfect_score_possible(tp_count, tp_weight)

        detector_best = nab_scorer.optimize_threshold(corpus, cost_matrix, PROBATION_PERCENT)
        detector_totals, detector_per_series = nab_scorer.score_corpus(
            detector_best.threshold, corpus, cost_matrix, PROBATION_PERCENT
        )

        null_best = nab_scorer.optimize_threshold(null_corpus, cost_matrix, PROBATION_PERCENT)
        null_totals, _ = nab_scorer.score_corpus(
            null_best.threshold, null_corpus, cost_matrix, PROBATION_PERCENT
        )

        perfect_best = nab_scorer.optimize_threshold(perfect_corpus, cost_matrix, PROBATION_PERCENT)
        perfect_totals, _ = nab_scorer.score_corpus(
            perfect_best.threshold, perfect_corpus, cost_matrix, PROBATION_PERCENT
        )
        if abs(perfect_totals.score - perfect_possible) > SANITY_TOLERANCE:
            raise ValueError(
                f"{profile_name}: perfect detector raw {perfect_totals.score} != "
                f"analytic perfect {perfect_possible}; the vendored port is wrong"
            )

        null_norm = nab_scorer.normalized_score(
            null_totals.score, null_totals.score, perfect_possible
        )
        perfect_norm = nab_scorer.normalized_score(
            perfect_totals.score, null_totals.score, perfect_possible
        )
        detector_norm = nab_scorer.normalized_score(
            detector_totals.score, null_totals.score, perfect_possible
        )
        sanity["null"][profile_name] = null_norm
        sanity["perfect"][profile_name] = perfect_norm
        if abs(null_norm) > SANITY_TOLERANCE or abs(perfect_norm - 100.0) > SANITY_TOLERANCE:
            raise ValueError(
                f"{profile_name}: sanity gate failed (null {null_norm}, perfect "
                f"{perfect_norm}); the vendored port is wrong"
            )

        out[profile_name] = {
            "score": detector_norm,
            "threshold": detector_best.threshold,
            "raw_score": detector_totals.score,
            "null_raw_score": null_totals.score,
            "perfect_raw_score": perfect_possible,
            "cost_matrix": cost_matrix,
            "counts": {
                "tp": detector_totals.tp,
                "tn": detector_totals.tn,
                "fp": detector_totals.fp,
                "fn": detector_totals.fn,
                "total_points": detector_totals.total,
            },
            "per_series": {
                name: {
                    "score": row.score,
                    "tp": row.tp,
                    "tn": row.tn,
                    "fp": row.fp,
                    "fn": row.fn,
                }
                for name, row in detector_per_series.items()
            },
        }
        logger.info(
            "NAB official %s: score %.2f (threshold %.6f, raw %.3f, null raw %.3f, perfect %.3f)",
            profile_name,
            detector_norm,
            detector_best.threshold,
            detector_totals.score,
            null_totals.score,
            perfect_possible,
        )
    return {"profiles": out, "sanity": sanity}


def _write_scores_payload(
    config: AnomalyConfig,
    corpus: list[nab_scorer.SeriesInput],
    clips: list[dict[str, Any]],
) -> Path:
    """Persist the exact scorer inputs so the committed score is re-verifiable."""
    series: dict[str, Any] = {}
    for s in corpus:
        ts_ns: list[int] = []
        for t in s.timestamps:
            if not isinstance(t, int):
                raise ValueError(f"{s.name}: expected int-ns timestamps, got {type(t)}")
            ts_ns.append(t)
        if any(t % 1_000_000_000 for t in ts_ns):
            raise ValueError(f"{s.name}: timestamps must be whole seconds for the JSON payload")
        windows_ns: list[tuple[int, int]] = []
        for a, b in s.windows:
            if not isinstance(a, int) or not isinstance(b, int):
                raise ValueError(f"{s.name}: expected int-ns window bounds")
            windows_ns.append((a, b))
        series[s.name] = {
            "timestamps": [_iso(t) for t in ts_ns],
            "scores": [float(v) for v in s.scores],
            "windows": [[_iso(a), _iso(b)] for a, b in windows_ns],
        }
    payload = {
        "description": (
            "Scorer inputs behind reports/nab_official_score.json: per-series scored-span "
            "timestamps (UTC-naive, second precision), IsolationForest anomaly scores "
            "(-decision_function), and the test-span-clipped label windows."
        ),
        "window_clips": clips,
        "series": series,
    }
    out = config.reports_path / SCORES_PATH
    out.write_text(json.dumps(payload, separators=(",", ":")))
    return out


def run_nab_official(config: AnomalyConfig) -> dict[str, Any]:
    """Recompute, verify, score, gate, and write the official NAB score."""
    committed = json.loads((config.reports_path / "nab_metrics.json").read_text())
    results = recompute_nab_results(config)
    verification = verify_against_committed(results, committed)
    logger.info(
        "recomputed NAB metrics match the committed artifact (%d alerts over %d series)",
        verification["alerts_fired_total"],
        verification["series_checked"],
    )

    corpus, clips, excluded = build_scoring_corpus(results, committed)
    scored = score_profiles(corpus)

    all_scores = [v for s in corpus for v in s.scores]
    report: dict[str, Any] = {
        "artifact": "nab_official_score",
        "generated_by": "uv run python -m anomaly_detection.cli nab-official",
        "upstream": {
            "repo": UPSTREAM_REPO,
            "commit": UPSTREAM_COMMIT,
            "license": "MIT (src/anomaly_detection/vendor/LICENSE-nab.txt)",
            "vendored_module": "src/anomaly_detection/vendor/nab_scorer.py",
            "profiles": "src/anomaly_detection/vendor/nab_profiles.json",
            "labels": "src/anomaly_detection/vendor/nab_combined_windows.json",
            "labels_sha256": NAB_LABELS_SHA256,
        },
        "scored_series": [s.name for s in corpus],
        "excluded_series": {key: "no labelled window in the scored span" for key in excluded},
        "synthetic_stream": (
            "the seeded synthetic telemetry stream (injected anomalies) is never part "
            "of the official score; only real NAB series are scored"
        ),
        "corpus": {
            "n_series": len(corpus),
            "n_windows": sum(len(s.windows) for s in corpus),
            "n_points": sum(len(s.timestamps) for s in corpus),
            "scored_span": "post-training 30% of each series (the committed test window)",
            "probationary_percent": PROBATION_PERCENT,
            "probation_note": (
                "the 70% train split plays the role of NAB's probationary period, "
                "so no additional probation is taken from the scored span"
            ),
            "window_clips": clips,
            "score_range": [min(all_scores), max(all_scores)],
        },
        "verification": verification,
        "sanity": {
            "null": scored["sanity"]["null"],
            "perfect": scored["sanity"]["perfect"],
            "tolerance": SANITY_TOLERANCE,
            "definition": "null = constant 0.5 detector; perfect = fires only at window starts",
        },
        "profiles": scored["profiles"],
    }
    out = config.reports_path / SCORE_PATH
    out.write_text(json.dumps(report, indent=2) + "\n")
    scores_out = _write_scores_payload(config, corpus, clips)
    logger.info("official NAB score -> %s (+ scorer inputs -> %s)", out, scores_out)
    return report
