"""E2-5 train tuning and validation-only comparator selection."""

import json
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any, cast

import numpy as np

from dynamic_pricing.baselines import Baseline, EpisodeResult, make_baseline, run_baseline
from dynamic_pricing.benchmark import load_calibration
from dynamic_pricing.calibrate import load_params
from dynamic_pricing.env import EpisodeSpec, PricingEnv
from dynamic_pricing.ledger import (
    append_ledger,
    canonical_sha256,
    file_sha256,
    write_json,
)
from dynamic_pricing.specs import (
    load_episode_specs,
    materialize_development_specs,
)


def _evaluate(
    calibrations: dict[str, Any], specs: list[EpisodeSpec], factory: Callable[[], Baseline]
) -> list[EpisodeResult]:
    env = PricingEnv(calibrations)
    return [run_baseline(env, spec, factory()) for spec in specs]


def _mean(results: list[EpisodeResult]) -> float:
    return float(np.mean([result.mean_normalised_profit for result in results]))


def _summarise(results: list[EpisodeResult]) -> dict[str, Any]:
    by_rho = {
        str(rho): _mean([result for result in results if result.spec.rho == rho])
        for rho in (0.7, 1.0, 1.3)
    }
    return {
        "mean_normalised_profit": _mean(results),
        "mean_raw_gross_profit": float(np.mean([result.raw_gross_profit for result in results])),
        "violations": sum(result.violations for result in results),
        "mean_by_rho": by_rho,
    }


def _lock_comparator(params_path: Path, comparator: str) -> None:
    text = params_path.read_text()
    if "\ncomparator:" in text:
        raise ValueError("comparator is already locked")
    params_path.write_text(text.rstrip() + f"\ncomparator: {comparator}\n")


def run_tuning(project_root: Path, repo_root: Path, params_path: Path) -> dict[str, Any]:
    del repo_root
    started = time.perf_counter()
    params = load_params(params_path)
    materialize_development_specs(project_root, params)
    splits_path = project_root / "data" / "splits.json"
    splits = cast(dict[str, Any], json.loads(splits_path.read_text()))
    train_specs = load_episode_specs(splits, "train")
    val_specs = load_episode_specs(splits, "val")
    calibrations = load_calibration(project_root / "data" / "calibration.json")
    prior = params["elasticity_prior"]

    b1_grid: list[dict[str, Any]] = []
    for action in range(7):
        results = _evaluate(
            calibrations, train_specs, partial(make_baseline, "B1", b1_action=action)
        )
        b1_grid.append({"action": action, "mean_normalised_profit": _mean(results)})
    best_b1 = max(b1_grid, key=lambda row: row["mean_normalised_profit"])

    b2_grid: list[dict[str, Any]] = []
    thresholds = params["tuning"]["b2_thresholds_pct"]
    for behind in thresholds:
        for ahead in thresholds:
            results = _evaluate(
                calibrations,
                train_specs,
                partial(
                    make_baseline,
                    "B2",
                    b2_behind_pct=float(behind),
                    b2_ahead_pct=float(ahead),
                ),
            )
            b2_grid.append(
                {
                    "behind_pct": float(behind),
                    "ahead_pct": float(ahead),
                    "mean_normalised_profit": _mean(results),
                }
            )
    best_b2 = max(b2_grid, key=lambda row: row["mean_normalised_profit"])
    train_wall_clock = time.perf_counter() - started
    append_ledger(
        project_root,
        step="E2-5-train",
        change="Tuned B1 and B2 on 2,000 common-random-number train episodes",
        split="train",
        config_sha256=canonical_sha256(params),
        set_sha256=file_sha256(splits_path),
        n=len(train_specs),
        headline={"best_b1": best_b1, "best_b2": best_b2},
        wall_clock_s=train_wall_clock,
        report_path="projects/15-dynamic-pricing-rl/reports/baselines_val.json",
        decision="train tuning complete; no sealed evaluation",
    )

    val_started = time.perf_counter()
    factories: dict[str, Callable[[], Baseline]] = {
        "B0": partial(make_baseline, "B0"),
        "B1": partial(make_baseline, "B1", b1_action=int(best_b1["action"])),
        "B2": partial(
            make_baseline,
            "B2",
            b2_behind_pct=float(best_b2["behind_pct"]),
            b2_ahead_pct=float(best_b2["ahead_pct"]),
        ),
        "B3": partial(
            make_baseline,
            "B3",
            prior_mean=float(prior["mean"]),
            prior_sd=float(prior["sd"]),
            observation_sd=float(params["baselines"]["b3_observation_sd"]),
        ),
    }
    val_results = {
        policy_id: _summarise(_evaluate(calibrations, val_specs, factory))
        for policy_id, factory in factories.items()
    }
    comparator = max(
        val_results, key=lambda policy_id: val_results[policy_id]["mean_normalised_profit"]
    )
    _lock_comparator(params_path, comparator)
    locked_params = load_params(params_path)
    report: dict[str, Any] = {
        "seed": int(params["seed"]),
        "train": {
            "n_episodes": len(train_specs),
            "b1_grid": b1_grid,
            "b2_grid": b2_grid,
            "best_b1": best_b1,
            "best_b2": best_b2,
        },
        "val": {"n_episodes": len(val_specs), "policies": val_results},
        "comparator": comparator,
        "wall_clock_s": {
            "train_tuning": train_wall_clock,
            "validation": time.perf_counter() - val_started,
        },
    }
    write_json(project_root / "reports" / "baselines_val.json", report)
    append_ledger(
        project_root,
        step="E2-5-val",
        change="Evaluated B0-B3 on 300 validation episodes and locked the comparator",
        split="val",
        config_sha256=canonical_sha256(locked_params),
        set_sha256=file_sha256(splits_path),
        n=len(val_specs),
        headline={"comparator": comparator, "policies": val_results},
        wall_clock_s=float(report["wall_clock_s"]["validation"]),
        report_path="projects/15-dynamic-pricing-rl/reports/baselines_val.json",
        decision=f"comparator locked to {comparator}; no sealed evaluation",
    )
    return report
