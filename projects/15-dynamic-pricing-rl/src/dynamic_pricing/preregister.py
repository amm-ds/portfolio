"""E2-6 immutable evaluation protocol and sealed-spec generation."""

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from dynamic_pricing.calibrate import load_params
from dynamic_pricing.ledger import (
    append_ledger,
    canonical_sha256,
    file_sha256,
    write_json,
)
from dynamic_pricing.specs import generate_specs


def run_preregistration(project_root: Path, repo_root: Path, params_path: Path) -> dict[str, Any]:
    del repo_root
    started = time.perf_counter()
    params = load_params(params_path)
    if "preregistration" in params:
        raise ValueError("preregistration already exists and must not be changed")
    comparator = params.get("comparator")
    if comparator not in {"B0", "B1", "B2", "B3"}:
        raise ValueError("run E2-5 and lock a valid comparator before E2-6")
    splits_path = project_root / "data" / "splits.json"
    splits = cast(dict[str, Any], json.loads(splits_path.read_text()))
    if splits.get("sealed_evaluation"):
        raise ValueError("sealed evaluation specs already exist; refusing to redraw them")

    prior = params["elasticity_prior"]
    test = generate_specs(
        splits["series_ids"]["test"],
        1000,
        stream=2,
        prior_mean=float(prior["mean"]),
        seed=int(params["seed"]),
        prior_sd=float(prior["sd"]),
        lower=float(prior["lower"]),
        upper=float(prior["upper"]),
    )
    stress_m1_5 = generate_specs(
        splits["series_ids"]["test"],
        500,
        stream=3,
        prior_mean=-1.5,
        seed=int(params["seed"]),
        prior_sd=float(prior["sd"]),
        lower=float(prior["lower"]),
        upper=float(prior["upper"]),
    )
    stress_m3_5 = generate_specs(
        splits["series_ids"]["test"],
        500,
        stream=4,
        prior_mean=-3.5,
        seed=int(params["seed"]),
        prior_sd=float(prior["sd"]),
        lower=float(prior["lower"]),
        upper=float(prior["upper"]),
    )
    sealed_specs = {
        "test": [asdict(spec) for spec in test],
        "stress_mean_m1_5": [asdict(spec) for spec in stress_m1_5],
        "stress_mean_m3_5": [asdict(spec) for spec in stress_m3_5],
    }
    spec_hashes = {split: canonical_sha256(specs) for split, specs in sealed_specs.items()}
    preregistration = {
        "protocol_version": 1,
        "seed": 42,
        "comparator": comparator,
        "policies": ["B0", "B1", "B2", "B3", "RL", "UB"],
        "hypotheses": {
            "P1": {
                "role": "primary",
                "statement": "RL beats the validation-selected best non-RL baseline",
                "comparison": f"RL minus {comparator}",
                "metric": "mean_normalised_profit",
                "relative_lift_min": 0.01,
                "paired_difference_ci_lower_exclusive": 0.0,
            },
            "P2": {
                "role": "hard",
                "statement": "Every policy has zero constraint violations on every test episode",
                "violations_exactly": 0,
                "action_masks_required": True,
            },
            "P3": {
                "role": "context_no_gate",
                "statement": "Report fluid-bound share by rho bucket and shifted stress prior",
            },
        },
        "metric_definitions": {
            "mean_normalised_profit": (
                "Mean sum of daily (price-cost)*sales/R_ref plus terminal salvage*leftover/R_ref"
            ),
            "raw_gross_profit": "Mean unnormalised (price-cost)*sales, excluding salvage",
            "fluid_bound_share": "mean_normalised_profit divided by known-epsilon fluid LP profit",
            "relative_lift": "(RL mean - comparator mean) / comparator mean",
        },
        "paired_bootstrap": {
            "unit": "episode",
            "n_resamples": 2000,
            "seed": 42,
            "confidence": 0.95,
        },
        "seed_formula": "stream * 1000000 + episode_index",
        "evaluation_sets": {
            "test": {"n": 1000, "stream": 2, "specs_sha256": spec_hashes["test"]},
            "stress_mean_m1_5": {
                "n": 500,
                "stream": 3,
                "elasticity_mean": -1.5,
                "specs_sha256": spec_hashes["stress_mean_m1_5"],
            },
            "stress_mean_m3_5": {
                "n": 500,
                "stream": 4,
                "elasticity_mean": -3.5,
                "specs_sha256": spec_hashes["stress_mean_m3_5"],
            },
        },
    }
    preregistration_sha256 = canonical_sha256(preregistration)
    splits["sealed_evaluation"] = sealed_specs
    splits.pop("content_sha256", None)
    splits["content_sha256"] = canonical_sha256(splits)
    params["preregistration"] = preregistration
    write_json(splits_path, splits)
    params_path.write_text(yaml.safe_dump(params, sort_keys=False, allow_unicode=True))
    append_ledger(
        project_root,
        step="E2-6",
        change="Pre-registered P1/P2/P3 and generated untouched test and stress specs",
        split="test and stress specs generated; never evaluated",
        config_sha256=canonical_sha256(params),
        set_sha256=file_sha256(splits_path),
        n=2000,
        headline={
            "preregistration_sha256": preregistration_sha256,
            "comparator": comparator,
            "specs_sha256": spec_hashes,
        },
        wall_clock_s=time.perf_counter() - started,
        request_hosts=[],
        report_path="projects/15-dynamic-pricing-rl/params.yaml",
        decision="owner review and commit required; stopped before E2-7 and E2-8",
    )
    return {
        "preregistration_sha256": preregistration_sha256,
        "comparator": comparator,
        "n_test": len(test),
        "n_stress_each": len(stress_m1_5),
        "specs_sha256": spec_hashes,
    }
