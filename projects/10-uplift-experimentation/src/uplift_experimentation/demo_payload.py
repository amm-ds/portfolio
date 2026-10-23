"""Demo payload for the uplift policy simulator (showcase demo).

Builds ``reports/demo_payload.json`` — a compact, fully precomputed lookup
that lets the showcase UI recompute model-estimated profit for **any**
send-cost / targeting-budget combination client-side, without retraining or
serving model inference:

- per-policy profit grids (best_arm / single_arm / random) over a fine
  (cost per email x fraction targeted) lattice, with paired-bootstrap 95% CIs
  for best_arm and random at every grid point;
- mail-everyone profits per arm over the same cost grid (exact formula, no
  bootstrap);
- the empirical per-arm Qini curves on the randomized arm-vs-control pairs
  (downsampled) and the experiment-segment rates;
- the cumulative recommended-arm mix along the best-uplift ranking at every
  targeted fraction (top-k composition of mens/womens/none recommendations);
- the committed scalars: revenue/cost model, full-send incrementals, arm
  shares, per-arm Qini coefficients + CIs, both committed break-even reads
  (two-arm cost sensitivity and the multi-arm best-arm ≈ $0.31), and the
  honest model-estimated-evaluation note.

Everything is deterministic: per-arm scores are the committed
``data/scores_multi.parquet`` cross-fitted columns, empirical per-arm Qini
numbers are recomputed with the same functions that wrote
``reports/metrics.json`` (and verified against it), and the grid bootstrap
reuses ``multiarm``'s paired row-bootstrap machinery (one shared resample per
replication; the random baseline stays the straight line to the resample's
best-arm full-send total). Policy-level numbers are MODEL-ESTIMATED planning
figures throughout (see ``multiarm``); only the per-arm Qini contrasts are
empirical causal reads.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from portfolio_core.logging import get_logger

from uplift_experimentation.config import UpliftConfig, pd
from uplift_experimentation.multiarm import (
    ARMS,
    assigned_uplift,
    estimated_qini_curve,
    per_arm_qini_read,
    recommend_arm,
)

logger = get_logger(__name__)

DEMO_PAYLOAD_NAME = "demo_payload.json"
# Fine lattice: the UI recomputes profit for arbitrary cost/budget combinations,
# so this is denser than params.yaml's cost_grid x budget_fractions.
DEMO_COSTS = [round(0.01 + 0.01 * i, 2) for i in range(50)]  # 0.01 .. 0.50
DEMO_FRACTIONS = [round(0.01 + 0.01 * i, 2) for i in range(100)]  # 0.01 .. 1.00
QINI_MAX_POINTS = 100  # downsample dense committed curves to <= this many points


def _inc_at_fractions(estimated: NDArray[np.float64], n: int) -> NDArray[np.float64]:
    """Model-estimated incremental conversions at each targeted fraction.

    Reads ``estimated_qini_curve`` (sorted cumsum) at the exact lattice
    fractions; with the committed frame the lattice lands on the curve's
    natural k/n grid, so no interpolation is involved.
    """
    _fr, inc = estimated_qini_curve(estimated)
    idx = np.rint(np.asarray(DEMO_FRACTIONS) * n).astype(np.int64) - np.int64(1)
    return np.asarray(inc[1:][idx], dtype=np.float64)


def _profit_rows(
    inc_at_f: NDArray[np.float64], n_total: int, revenue: float
) -> NDArray[np.float64]:
    """Profit matrix (n_costs, n_fractions): inc(f)*revenue - f*N*cost."""
    fractions = np.asarray(DEMO_FRACTIONS)
    costs = np.asarray(DEMO_COSTS)
    return inc_at_f[None, :] * revenue - n_total * fractions[None, :] * costs[:, None]


def bootstrap_profit_grid(
    uplift_mens: NDArray[np.float64],
    uplift_womens: NDArray[np.float64],
    *,
    n_total: int,
    revenue_per_conversion: float,
    n_boot: int,
    seed: int,
) -> dict[str, dict[str, NDArray[np.float64]]]:
    """Paired row bootstrap of the (cost x fraction) profit grid.

    One shared row resample per replication (the ``multiarm`` convention, so
    the best_arm and random CIs are paired on the same resamples). Per
    replication: the best-arm curve is rebuilt from the resampled scores and
    read at every lattice fraction; the random baseline stays the straight
    line to that resample's best-arm full-send total. Cost enters exactly as
    in the point estimates, so every grid point gets its own CI in one
    vectorized pass. Deterministic under ``seed``.
    """
    u_m = np.asarray(uplift_mens, dtype=float)
    u_w = np.asarray(uplift_womens, dtype=float)
    n = len(u_m)
    rng = np.random.default_rng(seed)
    best_b = np.empty((n_boot, len(DEMO_COSTS), len(DEMO_FRACTIONS)))
    random_b = np.empty_like(best_b)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        est = assigned_uplift(u_m[idx], u_w[idx], recommend_arm(u_m[idx], u_w[idx]))
        best_b[b] = _profit_rows(_inc_at_fractions(est, n), n_total, revenue_per_conversion)
        # Random: straight line to this resample's best-arm full total.
        random_b[b] = (
            np.asarray(DEMO_FRACTIONS)[None, :]
            * (est.sum() * revenue_per_conversion - n_total * np.asarray(DEMO_COSTS))[:, None]
        )
    lo_best, hi_best = np.quantile(best_b, [0.025, 0.975], axis=0)
    lo_rand, hi_rand = np.quantile(random_b, [0.025, 0.975], axis=0)
    return {
        "best_arm": {"lo": lo_best, "hi": hi_best},
        "random": {"lo": lo_rand, "hi": hi_rand},
    }


def _arm_mix_by_fraction(
    uplift_mens: NDArray[np.float64], uplift_womens: NDArray[np.float64]
) -> dict[str, Any]:
    """Cumulative recommended-arm mix along the best-uplift ranking.

    Customers rank by their best-arm uplift ``max(u_m, u_w, 0)`` descending
    (the same score ``estimated_qini_curve`` sorts by); at each lattice
    fraction k/100 the shares are the {mens, womens, none} composition of the
    top ``rint(f·N)`` customers. Stable tie-break on the frame order keeps it
    deterministic — ties only occur at score 0, where the recommendation is
    "none", so the none-share is non-decreasing along the grid and the k = 100
    endpoint reproduces the full-send ``recommended_arm_shares``.
    """
    recommended = recommend_arm(uplift_mens, uplift_womens)
    best = np.maximum(np.maximum(uplift_mens, uplift_womens), 0.0)
    order = np.argsort(-best, kind="stable")
    rec_sorted = recommended[order]
    k = np.rint(np.asarray(DEMO_FRACTIONS) * len(best)).astype(np.int64)
    counts = {
        label: np.cumsum(rec_sorted == label, dtype=np.float64)
        for label in ("mens", "womens", "none")
    }
    return {
        "fractions": DEMO_FRACTIONS,
        "shares": {
            label: [round(float(c / kk), 6) for c, kk in zip(counts[label][k - 1], k, strict=True)]
            for label in counts
        },
    }


def _downsample(fr: NDArray[np.float64], inc: NDArray[np.float64]) -> dict[str, list[float]]:
    """Evenly spaced subsample of a committed curve, endpoints kept, <= 100 pts."""
    n_out = min(QINI_MAX_POINTS, len(fr))
    idx = np.linspace(0, len(fr) - 1, n_out).astype(int)
    return {
        "fractions": [round(float(fr[i]), 4) for i in idx],
        "incremental": [round(float(inc[i]), 4) for i in idx],
    }


def _check_close(name: str, actual: float, committed: float) -> None:
    """Guard against drift between the committed metrics block and the scores."""
    if not np.isclose(actual, committed, rtol=1e-9, atol=1e-9):
        raise ValueError(f"{name}: recomputed {actual} != committed metrics {committed}")


def build_demo_payload(cfg: UpliftConfig) -> dict[str, Any]:
    """Assemble the simulator payload from committed train/evaluate artifacts."""
    scores = pd.read_parquet(cfg.data_dir / "scores_multi.parquet")
    metrics_path = cfg.reports_dir / "metrics.json"
    if not metrics_path.exists():
        raise FileNotFoundError(f"{metrics_path} missing — run the evaluate stage first")
    metrics: dict[str, Any] = json.loads(metrics_path.read_text())
    multi_arm: dict[str, Any] = metrics["multi_arm"]
    meta: dict[str, Any] = metrics["_meta"]

    u_m = scores["uplift_mens"].to_numpy(dtype=float)
    u_w = scores["uplift_womens"].to_numpy(dtype=float)
    seg = scores["segment"].to_numpy()
    y = scores["conversion"].to_numpy(dtype=float)
    n_total = len(scores)
    recommended = recommend_arm(u_m, u_w)
    est = assigned_uplift(u_m, u_w, recommended)

    revenue = float(meta["cost_model"]["revenue_per_conversion"])
    cost_default = float(meta["cost_model"]["cost_per_email"])

    # Empirical per-arm reads, recomputed with the committed functions and
    # verified against the committed metrics block (same data, deterministic).
    arm_reads = per_arm_qini_read(seg, y, u_m, u_w)

    # Point-estimate profit grids on the committed (unresampled) scores.
    profits = {
        "best_arm": _profit_rows(_inc_at_fractions(est, n_total), n_total, revenue),
        "single_arm": _profit_rows(_inc_at_fractions(u_m, n_total), n_total, revenue),
        "random": _profit_rows(np.asarray(DEMO_FRACTIONS) * est.sum(), n_total, revenue),
    }
    boot_seed = cfg.seed + 1999  # multi-arm bootstrap stream (evaluate.py convention)
    bands = bootstrap_profit_grid(
        u_m,
        u_w,
        n_total=n_total,
        revenue_per_conversion=revenue,
        n_boot=cfg.bootstrap_reps,
        seed=boot_seed,
    )

    # Per-arm Qini curves (empirical) + their random lines, downsampled.
    qini_points: dict[str, Any] = {}
    for arm, _seg_name in ARMS:
        read = arm_reads[arm]
        committed = multi_arm["per_arm"][arm]
        _check_close(
            f"per_arm.{arm}.qini_coefficient",
            read["qini_coefficient"],
            committed["qini_coefficient"],
        )
        _check_close(
            f"per_arm.{arm}.incremental_conversions_full",
            read["incremental_conversions_full"],
            committed["incremental_conversions_full"],
        )
        fr, inc = read["curve"]
        entry = _downsample(fr, inc)
        entry["random_fractions"] = [0.0, 1.0]
        entry["random_incremental"] = [0.0, round(read["incremental_conversions_full"], 4)]
        entry["qini_coefficient"] = read["qini_coefficient"]
        entry["qini_ci"] = [float(v) for v in committed["qini_ci"]]
        qini_points[arm] = entry
    qini_points["random"] = {
        "fractions": [0.0, 1.0],
        "incremental": [0.0, round(float(est.sum()), 4)],
        "note": "model-estimated random baseline: straight line to the best-arm "
        "full-send total (Qini 0 by construction)",
    }

    # Experiment-segment rates + per-segment full-send incrementals (summed
    # predicted uplift of the segment's rows — cheaply derivable, model-estimated).
    segments: dict[str, Any] = {}
    for name in [a for _a, a in ARMS] + ["No E-Mail"]:
        rows = scores[scores["segment"] == name]
        segments[name] = {
            "n": len(rows),
            "visit_rate": round(float(rows["visit"].mean()), 6),
            "conversion_rate": round(float(rows["conversion"].mean()), 6),
            "mean_spend": round(float(rows["spend"].mean()), 4),
            "incremental_conversions_full_send_model_estimated": {
                "mens": round(float(rows["uplift_mens"].sum()), 4),
                "womens": round(float(rows["uplift_womens"].sum()), 4),
            },
        }

    # Mail-everyone profits per arm: exact formula over the cost grid, no bootstrap.
    mail_everyone = {}
    for arm, col in (("mens", "uplift_mens"), ("womens", "uplift_womens")):
        total = float(scores[col].sum())
        mail_everyone[arm] = {
            f"{c:.2f}": round(total * revenue - n_total * c, 2) for c in DEMO_COSTS
        }

    # The committed shares ride along as the published read; the payload's live
    # recomputation must agree (same scores, same recommend_arm).
    shares_raw = {
        label: float(np.mean(recommended == label)) for label in ("mens", "womens", "none")
    }
    committed_shares = multi_arm["recommended_arm_shares"]
    for label, share in shares_raw.items():
        _check_close(f"recommended_arm_shares.{label}", share, committed_shares[label])

    scalars: dict[str, Any] = {
        "n_customers": n_total,
        "revenue_per_conversion": revenue,
        "cost_default": cost_default,
        "policy_budget": float(multi_arm["best_arm_break_even"]["policy_budget"]),
        "incremental_conversions_full_send_model_estimated": {
            arm: round(float(scores[col].sum()), 6)
            for arm, col in (("mens", "uplift_mens"), ("womens", "uplift_womens"))
        },
        "incremental_conversions_full_send_best_arm": round(float(est.sum()), 6),
        "per_arm_qini": {
            arm: {
                "qini_coefficient": arm_reads[arm]["qini_coefficient"],
                "qini_ci": [float(v) for v in multi_arm["per_arm"][arm]["qini_ci"]],
                "incremental_conversions_full": arm_reads[arm]["incremental_conversions_full"],
                "incremental_conversions_full_ci": [
                    float(v) for v in multi_arm["per_arm"][arm]["incremental_conversions_full_ci"]
                ],
                "n_arm": arm_reads[arm]["n_arm"],
                "n_control": arm_reads[arm]["n_control"],
            }
            for arm, _seg_name in ARMS
        },
        "recommended_arm_shares": {label: round(share, 6) for label, share in shares_raw.items()},
        "break_even": {
            "two_arm_committed": {
                "cost_per_email": float(meta["cost_sensitivity"]["breakeven_cost_per_email"]),
                "source": "committed two-arm read (_meta.cost_sensitivity, "
                "t_learner vs mail-everyone at 25% budget)",
            },
            "multi_arm_best_arm": {
                "cost_per_email": float(multi_arm["best_arm_break_even"]["cost_per_email"]),
                "vs": multi_arm["best_arm_break_even"]["vs"],
                "policy_budget": float(multi_arm["best_arm_break_even"]["policy_budget"]),
                "source": "committed multi-arm read (multi_arm.best_arm_break_even)",
            },
        },
        "mail_everyone_profit": mail_everyone,
        "model_estimated_note": multi_arm["note"],
    }

    return {
        "schema_version": 1,
        "demo": "uplift-simulator",
        "project": "10-uplift-experimentation",
        "n_customers": n_total,
        "scalars": scalars,
        "profit_grid": {
            "costs": DEMO_COSTS,
            "fractions": DEMO_FRACTIONS,
            "policies": {
                "best_arm": {
                    "profit": np.round(profits["best_arm"], 2).tolist(),
                    "ci": {
                        "lo": np.round(bands["best_arm"]["lo"], 2).tolist(),
                        "hi": np.round(bands["best_arm"]["hi"], 2).tolist(),
                    },
                },
                "single_arm": {"profit": np.round(profits["single_arm"], 2).tolist()},
                "random": {
                    "profit": np.round(profits["random"], 2).tolist(),
                    "ci": {
                        "lo": np.round(bands["random"]["lo"], 2).tolist(),
                        "hi": np.round(bands["random"]["hi"], 2).tolist(),
                    },
                },
            },
            "n_boot": cfg.bootstrap_reps,
            "seed": boot_seed,
            "alpha": 0.05,
            "model_estimated": True,
            "note": "profit(f, c) = inc(f) * revenue_per_conversion - f * N * c; "
            "inc(f) is summed predicted uplift (model-estimated), CIs are paired "
            "row bootstrap (one shared resample per replication), percentile 95%",
        },
        "qini_points": qini_points,
        "arm_mix_by_fraction": _arm_mix_by_fraction(u_m, u_w),
        "segments": segments,
    }


def write_demo_payload(cfg: UpliftConfig) -> Path:
    """Build the payload and persist it to ``reports/demo_payload.json``."""
    payload = build_demo_payload(cfg)
    out = cfg.reports_dir / DEMO_PAYLOAD_NAME
    out.write_text(json.dumps(payload, indent=2))
    logger.info(
        "demo payload: %d customers, %d costs x %d fractions, %d boot reps -> %s",
        payload["n_customers"],
        len(DEMO_COSTS),
        len(DEMO_FRACTIONS),
        cfg.bootstrap_reps,
        out,
    )
    return out
